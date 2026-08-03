import os
import random
import string
import json
from datetime import datetime, timedelta
import pymysql
try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None
import requests
import sys
import secrets
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Body

from dotenv import load_dotenv

# Importation de vos fonctions utilitaires depuis utils.py
try:
    from .utils import uuid, obtenir_token_odk, lien, telecharger_fichiers
except ImportError:
    from utils import uuid, obtenir_token_odk, lien, telecharger_fichiers

# =========================================================================
# 1. INITIALISATION ET CONFIGURATION DES VARIABLES GLOBALES
# =========================================================================
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

# 2. Initialisation de FastAPI
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Définition des variables globales à partir du fichier externe .env
domaine = os.getenv("DOMAINE", "kodibeol.elementfx.com")
serveur_actuel = os.getenv("DB_HOST", "127.0.0.1")
db_name = os.getenv("DB_DATABASE", "client")


def build_db_config(database_name: str | None = None):
    print("serveur mysql " + serveur_actuel)
    print("serveur database " + db_name )
    return {
        "host": serveur_actuel,
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": database_name or db_name,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }

db_config = build_db_config()

def is_connection_open(conn):
    """Unified check whether a DB connection is open for pymysql or psycopg2."""
    try:
        if conn is None:
            return False
        # pymysql: connection.open is truthy when open
        if hasattr(conn, 'open'):
            return bool(conn.open)
        # psycopg2: connection.closed == 0 when open
        if hasattr(conn, 'closed'):
            return conn.closed == 0
    except Exception:
        return False
    return False

# =========================================================================
# 2. CALCUL DYNAMIQUE DU DOSSIER DIST (Séparé et Externe pour le .EXE)
# =========================================================================
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
    dossier_dist = BASE_DIR / "dist"
    dossier_photos = BASE_DIR / "photos"
else:
    FICHIER_ACTUEL = Path(__file__).resolve()
    BASE_DIR = FICHIER_ACTUEL.parent  # Dossier /backend/
    dossier_dist = BASE_DIR.parent / "frontend" / "dist"
    dossier_photos = BASE_DIR / "photos"  # Ou BASE_DIR.parent / "photos" selon où sont stockées vos images

# S'assurer que le dossier photos existe localement pour éviter une erreur
dossier_photos.mkdir(parents=True, exist_ok=True)

print("[DÉTECTION DIST] Chemin calculé : " + str(dossier_dist.resolve()))
print("[DÉTECTION INDEX] index.html existe ? : " + str((dossier_dist / 'index.html').exists()))


# =========================================================================
# 3. ⚙️ LE VRAI GÉNÉRATEUR DE FLUX ASYNCHRONE COMPATIBLE SSE
# =========================================================================
#async def generateur_traitement_flux(date_cible: str):
async def generateur_traitement_flux_v0(
    date_cible: str, 
    download: str = "local", 
    compute: str = "local"
):
    """
    Cette fonction encapsule toute votre logique métier et utilise 'yield'
    pour envoyer les statuts et la progression en temps réel à Vue.js.
    """
    print(f"🔄 Démarrage du traitement pour la date : {date_cible}")
    yield f"data: {json.dumps({'statut': f'🔄 Initialisation du traitement pour la date : {date_cible} telechargement {download} calcul {compute}'})}\n\n"

    # --- ÉTAPE A : VÉRIFICATION DE LA LICENCE ---
    original_word = ''.join(random.choices(string.ascii_letters, k=10))
    exposant, modulo = 5, 323
    encoded_list = [str(pow(ord(char), exposant, modulo)) for char in original_word]
    cle_generee = "-".join(encoded_list)

    url_licence = f"https://{domaine}/cle.php?tel={str(uuid())}&date={date_cible}&cle={cle_generee}"
    
    #"https://migration.odk.elementfx.com/cle.php?tel=12345&date=2026-07-24&cle=123-456-789"
    try:
        
        response = requests.get(url_licence, timeout=10)
        response.raise_for_status() 
        texte = response.text.strip()
        elements = texte.split("#")
        mdp = elements[0] 
        
        if mdp == original_word:
            db_config_master = {
                "host": elements[1],
                "port": int(elements[2]),
                "user": elements[3],
                "password": elements[4],
                "database": elements[5],
            }

        #if 1: # Laissez à 1 pour vos tests
            sql = """
                SELECT * FROM `logs_importation_odk` 
                WHERE `date` = %s 
                AND TIMESTAMPDIFF(HOUR, CONCAT(`date`, ' ', `heure`, ':00:00'), `update_at`) > 2 
                AND `update_at` > CONCAT(`date`, ' ', `heure`, ':00:00')
            """
            sql_master = """
                SELECT * FROM logs_importation_odk 
                WHERE date = %s 
                AND EXTRACT(EPOCH FROM (update_at::timestamp - (date::date + (heure || ':00:00')::time))) / 3600 > 2 
                AND update_at::timestamp > (date::date + (heure || ':00:00')::time)
            """

            heures_ok = {}
            heures_ok_master = {}
            
            # --- ÉTAPE B : CONNEXION À LA BASE DE DONNÉES ---
            try:
                connection = pymysql.connect(**db_config)
                print("✅ Connexion réussie à MySQL")
                yield f"data: {json.dumps({'statut': '✅ Connexion réussie à la base de données.'})}\n\n"
                if compute == "serveur":
                    try:
                        # Détecte si db_config_master semble être PostgreSQL (Neon)
                        is_postgres = False
                        if isinstance(db_config_master.get('host'), str) and 'neon' in db_config_master.get('host'):
                            is_postgres = True

                        if is_postgres and psycopg2 is not None:
                            # Utilise psycopg2 pour Postgres
                            dsn = (
                                f"host={db_config_master['host']} "
                                f"port={db_config_master.get('port', 5432)} "
                                f"user={db_config_master['user']} "
                                f"password={db_config_master['password']} "
                                f"dbname={db_config_master['database']} "
                                f"sslmode=require"
                            )
                            connection_master = psycopg2.connect(dsn)
                            is_pg = True
                            print("✅ Connexion master réussie à Postgres")
                        else:
                            # Essaie avec pymysql (MySQL)
                            connection_master = pymysql.connect(**db_config_master)
                            is_pg = False
                            print("✅ Connexion master réussie à MySQL")
                    except Exception as e:
                        connection_master = False
                        print(f"❌ Impossible de se connecter à la base de données master: {e}")

            except Exception as e:
                print(f"❌ Impossible de se connecter à la base de données : {e}")
                yield f"data: {json.dumps({'erreur': f'❌ Échec connexion BDD : {str(e)}'})}\n\n"
                return

            try:
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, (date_cible,))
                    for row in cursor.fetchall():
                        clef = f"{row['form']}{row['date']}{row['heure']}"
                        heures_ok[clef] = row["update_at"]
                        print(f"Log existant trouvé : {clef}")
                        yield f"data: {json.dumps({'statut': f'Formulaire déjà traité ignoré : {clef}'})}\n\n"
                
                if connection_master and is_connection_open(connection_master):
                    # psycopg2 uses a different cursor factory
                    if psycopg2 and isinstance(connection_master, psycopg2.extensions.connection):
                        with connection_master.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                            cursor.execute(sql_master, (date_cible,))
                            for row in cursor.fetchall():
                                clef = f"{row['form']}{row['date']}{row['heure']}"
                                heures_ok_master[clef] = row["update_at"]
                                print(f"Log master existant trouvé : {clef}")
                                yield f"data: {json.dumps({'statut': f'Formulaire master déjà traité ignoré : {clef}'})}\n\n"
                    else:
                        with connection_master.cursor(pymysql.cursors.DictCursor) as cursor:
                            cursor.execute(sql, (date_cible,))
                            for row in cursor.fetchall():
                                clef = f"{row['form']}{row['date']}{row['heure']}"
                                heures_ok_master[clef] = row["update_at"]
                                print(f"Log master existant trouvé : {clef}")
                                yield f"data: {json.dumps({'statut': f'Formulaire master déjà traité ignoré : {clef}'})}\n\n"
                   
                # --- ÉTAPE C : FILTRAGE DES ARCS ET DOSSIERS ---
                real_urls = []
                for urls in lien(date_cible):
                    clef_verification = f"{urls['form']}{date_cible}{urls['heure']}"
                    
                    if clef_verification in heures_ok:
                        origine = f"traite/{urls['form']}/{date_cible}/{urls['form']} {urls['heure']}h.zip"
                        destination = f"traite/{date_cible}/{urls['form']}/{urls['form']} {urls['heure']}h.zip"
                        directory = f"traite/{date_cible}/{urls['form']}/"
                            
                        if not os.path.isdir(directory):
                            os.makedirs(directory, mode=0o777, exist_ok=True)
                                
                        if os.path.exists(origine):
                            os.rename(origine, destination)
                    else:
                        real_urls.append(urls)
                
                total = len(real_urls)

                # --- ÉTAPE E : CAS OÙ IL Y A DES TÉLÉCHARGEMENTS À FAIRE ---
                print(f"\n🚀 Total url = {total} --- en telechargement")
                yield f"data: {json.dumps({'statut': f'📥 {total} fichiers à traiter récupérés...', 'progression': 25})}\n\n"
                
                print("📡 Début du transfert du flux asynchrone :")
                
                # 🔥 SÉCURISATION DU PARALLÉLISME : On consomme le générateur ENTIÈREMENT 
                # avant d'autoriser le passage au bloc finally qui ferme MySQL.
                 
                async for message in telecharger_fichiers(date_cible, real_urls, download, connection, connection_master, is_pg):
                    yield message
                
                # La clôture de la journée ne s'exécute que lorsque TOUT le lot parallèle est validé.
                #yield f"data: {json.dumps({'statut': f'🏁 Opérations terminées avec succès pour la journée du {date_cible}', 'progression': 100})}\n\n"

                # 🔥 MODIFICATION : Une fois la boucle asynchrone finie, on ordonne un RECHARGEMENT de contrôle
                
                """
                print(f"🏁 Téléchargements terminés pour le {date_cible}. Envoi de l'ordre de réactualisation de contrôle.")
                yield f"data: {json.dumps({'action': 'rechargement', 'statut': f'🔄 Téléchargements terminés. Réactualisation de contrôle pour le {date_cible}...', 'progression': 100})}\n\n"
                """
            except pymysql.MySQLError as e:
                print(f"❌ Erreur lors de l'exécution de la requête : {e}")
                yield f"data: {json.dumps({'erreur': f'Erreur SQL : {str(e)}'})}\n\n"
            finally:
                if is_connection_open(connection):
                    try:
                        connection.close()
                        print("🔌 Connexion à la base de données fermée.")
                    except Exception:
                        pass
                if connection_master and is_connection_open(connection_master):
                    try:
                        connection_master.close()
                    except Exception:
                        pass
            
        else:
            print("Accès refusé : Clé de licence invalide.")
            yield f"data: {json.dumps({'erreur': 'Accès refusé : Clé de licence invalide.'})}\n\n"
            
    except requests.exceptions.RequestException as e:
        print(f"Erreur de connexion au serveur d'activation : {e}")
        yield f"data: {json.dumps({'erreur': 'Erreur réseau lors de la vérification de licence.'})}\n\n"
    

async def generateur_traitement_flux(
    date_cible: str, 
    download: str = "local", 
    compute: str = "local"
):
    """
    Cette fonction encapsule toute votre logique métier et utilise 'yield'
    pour envoyer les statuts et la progression en temps réel à Vue.js.
    """
    # 🟢 INITIALISATIONS CRITIQUES : Évite les erreurs "UnboundLocalError" et sécurise le bloc finally
    connection_master = None
    connection = None
    db_config_master = None

    print(f"🔄 Démarrage du traitement pour la date : {date_cible}")
    yield f"data: {json.dumps({'statut': f'🔄 Initialisation du traitement pour la date : {date_cible} telechargement {download} calcul {compute}'})}\n\n"

    # --- ÉTAPE A : VÉRIFICATION DE LA LICENCE ---
    original_word = ''.join(random.choices(string.ascii_letters, k=10))
    exposant, modulo = 5, 323
    encoded_list = [str(pow(ord(char), exposant, modulo)) for char in original_word]
    cle_generee = "-".join(encoded_list)

    url_licence = f"https://{domaine}/cle.php?tel={str(uuid())}&date={date_cible}&cle={cle_generee}"
    is_pg = False
    try:
        response = requests.get(url_licence, timeout=10)
        response.raise_for_status() 
        texte = response.text.strip()
        elements = texte.split("#")
        mdp = elements[0] 
        
        if mdp == original_word:
            db_config_master = {
                "host": elements[1],
                "port": int(elements[2]),
                "user": elements[3],
                "password": elements[4],
                "database": elements[5],
            }

            sql = """
                SELECT * FROM `logs_importation_odk` 
                WHERE `date` = %s 
                AND TIMESTAMPDIFF(HOUR, CONCAT(`date`, ' ', `heure`, ':00:00'), `update_at`) > 2 
                AND `update_at` > CONCAT(`date`, ' ', `heure`, ':00:00')
            """
            sql_master = """
                SELECT * FROM logs_importation_odk 
                WHERE date = %s 
                AND EXTRACT(EPOCH FROM (update_at::timestamp - (date::date + (heure || ':00:00')::time))) / 3600 > 2 
                AND update_at::timestamp > (date::date + (heure || ':00:00')::time)
            """

            heures_ok = {}
            heures_ok_master = {}
            
            # --- ÉTAPE B : CONNEXION À LA BASE DE DONNÉES ---
            try:
                connection = pymysql.connect(**db_config)
                print("✅ Connexion réussie à MySQL")
                yield f"data: {json.dumps({'statut': '✅ Connexion réussie à la base de données.'})}\n\n"
                
                # Exécute la connexion Master uniquement si demandé sur l'interface et config valide
                if compute == "serveur" and db_config_master:
                    try:
                        # Détecte si db_config_master semble être PostgreSQL (Neon)
                        is_postgres = False
                        if isinstance(db_config_master.get('host'), str) and 'neon' in db_config_master.get('host'):
                            is_postgres = True

                        if is_postgres and psycopg2 is not None:
                            # Utilise psycopg2 pour Postgres
                            dsn = (
                                f"host={db_config_master['host']} "
                                f"port={db_config_master.get('port', 5432)} "
                                f"user={db_config_master['user']} "
                                f"password={db_config_master['password']} "
                                f"dbname={db_config_master['database']} "
                                f"sslmode=require"
                            )
                            connection_master = psycopg2.connect(dsn)
                            print("✅ Connexion master réussie à Postgres")
                            is_pg = True
                        else:
                            # Essaie avec pymysql (MySQL)
                            connection_master = pymysql.connect(**db_config_master)
                            print("✅ Connexion master réussie à MySQL")
                            is_pg = False
                    except Exception as e:
                        connection_master = None
                        print(f"❌ Impossible de se connecter à la base de données master: {e}")
                else:
                    connection_master = None

            except Exception as e:
                print(f"❌ Impossible de se connecter à la base de données : {e}")
                yield f"data: {json.dumps({'erreur': f'❌ Échec connexion BDD : {str(e)}'})}\n\n"
                return

            # --- ÉTAPE C : TRAITEMENT DES LOGS EXISTANTS ---
            try:
                # Lecture des logs existants sur la BDD locale
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, (date_cible,))
                    for row in cursor.fetchall():
                        clef = f"{row['form']}{row['date']}{row['heure']}"
                        heures_ok[clef] = row["update_at"]
                        print(f"Log existant trouvé : {clef}")
                        yield f"data: {json.dumps({'statut': f'Formulaire déjà traité ignoré : {clef}'})}\n\n"
                """
                # Lecture des logs sur le Master (Uniquement si la connexion a été établie)
                if connection_master and is_connection_open(connection_master):
                    # psycopg2 utilise une fabrique de curseur différente (PostgreSQL)
                    if 'psycopg2' in globals() and psycopg2 is not None and isinstance(connection_master, psycopg2.extensions.connection):
                        with connection_master.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                            cursor.execute(sql_master, (date_cible,))
                            for row in cursor.fetchall():
                                clef = f"{row['form']}{row['date']}{row['heure']}"
                                heures_ok_master[clef] = row["update_at"]
                                print(f"Log master existant trouvé : {clef}")
                                yield f"data: {json.dumps({'statut': f'Formulaire master déjà traité ignoré : {clef}'})}\n\n"
                    else:
                        with connection_master.cursor(pymysql.cursors.DictCursor) as cursor:
                            cursor.execute(sql, (date_cible,))
                            for row in cursor.fetchall():
                                clef = f"{row['form']}{row['date']}{row['heure']}"
                                heures_ok_master[clef] = row["update_at"]
                                print(f"Log master existant trouvé : {clef}")
                                yield f"data: {json.dumps({'statut': f'Formulaire master déjà traité ignoré : {clef}'})}\n\n"
                """
                # Lecture des logs sur le Master (Uniquement si la connexion a été établie)
                
                if connection_master and is_connection_open(connection_master):
                    #is_pg = 'psycopg2' in globals() and psycopg2 is not None and isinstance(connection_master, psycopg2.extensions.connection)
                    if is_pg:
                        cursor_context = connection_master.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                        sql_to_execute = sql_master
                    else:
                        cursor_context = connection_master.cursor(pymysql.cursors.DictCursor)
                        sql_to_execute = sql

                    # 2. Exécution et traitement factorisés
                    with cursor_context as cursor:
                        cursor.execute(sql_to_execute, (date_cible,))
                        for row in cursor.fetchall():
                            clef = f"{row['form']}{row['date']}{row['heure']}"
                            heures_ok_master[clef] = row["update_at"]
                            
                            print(f"Log master existant trouvé : {clef}")
                            yield f"data: {json.dumps({'statut': f'Formulaire master déjà traité ignoré : {clef}'})}\n\n"

                # --- ÉTAPE D : FILTRAGE DES ARCS ET DOSSIERS ---
                real_urls = []
                for urls in lien(date_cible):
                    clef_verification = f"{urls['form']}{date_cible}{urls['heure']}"
                    
                    if clef_verification in heures_ok:
                        origine = f"traite/{urls['form']}/{date_cible}/{urls['form']} {urls['heure']}h.zip"
                        destination = f"traite/{date_cible}/{urls['form']}/{urls['form']} {urls['heure']}h.zip"
                        directory = f"traite/{date_cible}/{urls['form']}/"
                            
                        if not os.path.isdir(directory):
                            os.makedirs(directory, mode=0o777, exist_ok=True)
                                
                        if os.path.exists(origine):
                            os.rename(origine, destination)
                    else:
                        real_urls.append(urls)
                
                total = len(real_urls)

                # --- ÉTAPE E : STREAMING DES TÉLÉCHARGEMENTS ---
                print(f"\n🚀 Total url = {total} --- en telechargement")
                yield f"data: {json.dumps({'statut': f'📥 {total} fichiers à traiter récupérés...', 'progression': 25})}\n\n"
                
                print("📡 Début du transfert du flux asynchrone :")
                
                # Appel de votre fonction de streaming unique fusionnée
                async for message in telecharger_fichiers(date_cible, real_urls, download, connection, connection_master, is_pg):
                    yield message
                
                print(f"🏁 Téléchargements terminés pour le {date_cible}. Envoi de l'ordre de réactualisation de contrôle.")
                #yield f"data: {json.dumps({'action': 'rechargement', 'statut': f'🔄 Téléchargements terminés. Réactualisation de contrôle pour le {date_cible}...', 'progression': 100})}\n\n"
                
            except pymysql.MySQLError as e:
                print(f"❌ Erreur lors de l'exécution de la requête : {e}")
                yield f"data: {json.dumps({'erreur': f'Erreur SQL : {str(e)}'})}\n\n"
            finally:
                # Clôture sécurisée de la BDD locale
                if connection and is_connection_open(connection):
                    try:
                        connection.close()
                        print("🔌 Connexion à la base de données fermée.")
                    except Exception:
                        pass
                # Clôture sécurisée de la BDD master (N'échoue jamais, même si connection_master vaut None)
                if connection_master and is_connection_open(connection_master):
                    try:
                        connection_master.close()
                        print("🔌 Connexion à la base de données master fermée.")
                    except Exception:
                        pass
            
        else:
            print("Accès refusé : Clé de licence invalide.")
            yield f"data: {json.dumps({'erreur': 'Accès refusé : Clé de licence invalide.'})}\n\n"

    except requests.exceptions.RequestException as e:
        print(f"Erreur de connexion au serveur d'activation : {e}")
        yield f"data: {json.dumps({'erreur': 'Erreur réseau lors de la vérification de licence.'})}\n\n"

# =========================================================================
# 4. 🚀 ROUTE API UNIQUE FASTAPI (Attend le paramètre de date web)
# =========================================================================

@app.get("/api/traitement")
async def api_lancer_traitement(
    date: str = Query(None),
    download: str = Query("local"),  # Récupère "local" ou "serveur"
    compute: str = Query("local")    # Récupère "local" ou "serveur"
):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
        
    print(f"📡 Demande de traitement reçue depuis l'interface pour la date : {date}")
    print(f"⚙️ Options choisies -> Téléchargement: {download} | Calcul: {compute}")
 
    # Transmettez les options à votre générateur pour adapter le comportement du traitement
    return StreamingResponse(
        generateur_traitement_flux(date, download=download, compute=compute), 
        media_type="text/event-stream"
    )

def normalize_synthese_rows(rows):
    """Normalise les lignes issues de la table de synthèse vers le contrat attendu par le frontend."""
    normalized_rows = []

    for row in rows or []:
        if not isinstance(row, dict):
            continue

        normalized_row = {
            "periode": row.get("periode") or row.get("mois") or "",
            "ref_formulaire": row.get("ref_formulaire") or row.get("ref") or row.get("formulaire") or "",
            "agence": row.get("agence") or "agence",
            "bloc": row.get("bloc") or "",
            "total": int(row.get("total") or 0),
            "last_realisation": row.get("last_realisation") or row.get("last_action") or "",
            "last_submit": row.get("last_submit") or "",
            "CUMUL_DEPANNAGE": int(row.get("CUMUL_DEPANNAGE") or 0),
            "CUMUL_DETECTION": int(row.get("CUMUL_DETECTION") or 0),
            "CUMUL_DISTRIBUTION": int(row.get("CUMUL_DISTRIBUTION") or 0),
            "CUMUL_INSPECTION": int(row.get("CUMUL_INSPECTION") or 0),
            "CUMUL_NEW_METER": int(row.get("CUMUL_NEW_METER") or 0),
            "CUMUL_NORMALISATION": int(row.get("CUMUL_NORMALISATION") or 0),
            "CUMUL_RECOUVREMENT": int(row.get("CUMUL_RECOUVREMENT") or 0),
            "CUMUL_RELEVE": int(row.get("CUMUL_RELEVE") or 0),
            "CUMUL_BRANCHEMENT": int(row.get("CUMUL_BRANCHEMENT") or 0),
        }

        for day in range(1, 32):
            key = f"J{day}"
            normalized_row[key] = int(row.get(key) or row.get(key.lower()) or 0)

        normalized_rows.append(normalized_row)

    return normalized_rows

# =========================================================================
# 5. 🔐 ROUTE D'AUTHENTIFICATION CONNECTÉE À VOTRE BDD MYSQL
# =========================================================================
@app.get("/api/synthese")
async def api_synthese(
    #cycle: str = Query(None)
    cycle: str = Query(None),
    regions: str = Query(None),
    agences: str = Query(None)
):
    if not cycle:
        return {"rows": [], "cycle": None, "message": "Aucun cycle fourni."}

    connection = None
    try:
        condition_region = ""
        if regions and len(regions.strip()) > 0:
            liste_regions = [r.strip() for r in regions.split(";")]
            elements_sql = ", ".join(f"'{r}'" for r in liste_regions)
            condition_region = f" AND `ref_formulaire` IN ({elements_sql})"

        condition_agence = ""
        if agences and len(agences.strip()) > 0:
            liste_agences = [r.strip() for r in agences.split(";")]
            elements_sql = ", ".join(f"'{r}'" for r in liste_agences)
            condition_agence = f" AND `agence` IN ({elements_sql})"


        connection = pymysql.connect(**build_db_config())
        day_columns = ",\n".join([f"`J{day}`" for day in range(1, 32)])
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = f"""
                            SELECT
                                `periode`,
                                `ref_formulaire`,
                                `agence` AS bloc,
                                `bloc` AS agence,
                                `total`,
                                `last_realisation`,
                                `last_submit`,
                                `CUMUL_DEPANNAGE`,
                                `CUMUL_DETECTION`,
                                `CUMUL_DISTRIBUTION`,
                                `CUMUL_INSPECTION`,
                                `CUMUL_NEW_METER`,
                                `CUMUL_NORMALISATION`,
                                `CUMUL_RECOUVREMENT`,
                                `CUMUL_RELEVE`,
                                `CUMUL_BRANCHEMENT`,
                                {day_columns}
                            FROM `synthese_mensuel_odk`
                            WHERE `periode` = %s {condition_region} {condition_agence}
                            ORDER BY `ref_formulaire`, `bloc`, `periode`
                            """
            cursor.execute(
                sql,
                (cycle,),
            )
            rows = cursor.fetchall()
            #print(rows)
        normalized_rows = normalize_synthese_rows(rows)
        #print(normalized_rows)
        return {"rows": normalized_rows, "cycle": cycle}
    except pymysql.MySQLError as e:
        print("[ERREUR SQL synthese] " + str(e))
        return {"rows": [], "cycle": cycle, "erreur": str(e)}
    finally:
        if is_connection_open(connection):
            try:
                connection.close()
            except Exception:
                pass

@app.post("/api/auth/login")
async def api_login(donnees: dict):
    """
    Reçoit l'identifiant (email ou numéro de contrat) et le mot de passe depuis Vue.js.
    Vérifie les accès dans la base de données SOCADEL.
    """
    identifiant = donnees.get("email")
    mot_de_passe = donnees.get("password")
    
    if not identifiant or not mot_de_passe:
        return {"erreur": "Veuillez remplir tous les champs."}
        
    connection = pymysql.connect(**db_config)
    
    try:
        sql = """
            SELECT DISTINCT `utilisateur`, `password` 
            FROM `utilisateur` 
            WHERE (`utilisateur` = %s AND `password` = %s)
            LIMIT 1
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql, (identifiant, mot_de_passe))
            utilisateur = cursor.fetchone()
            
        if utilisateur:
            import secrets
            token_session = secrets.token_hex(16)
            
            print(f"🔐 Connexion réussie pour le collecteur : {utilisateur}")
            
            return {
                "detail": {
                    "token": token_session,
                    "username": utilisateur["utilisateur"] if isinstance(utilisateur, dict) else utilisateur,
                    "expired_in": 3600
                }
            }
        else:
            return {"erreur": "Identifiants invalides ou collecteur non enregistré."}
            
    except pymysql.MySQLError as e:
        print(f"❌ Erreur SQL d'authentification : {e}")
        return {"erreur": "Erreur technique lors de la vérification en base de données."}
    finally:
        connection.close()

@app.get("/api/limites-agences")
def obtenir_limites_agences():
    """
    Récupère la liste des régions et agences depuis la table `limites_agences`
    """
    connection = None
    try:
        connection = pymysql.connect(**build_db_config())
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = "SELECT DISTINCT region, agency FROM limites_agences"
            cursor.execute(sql)
            resultats = cursor.fetchall()
            #print(resultats)
        connection.close()
        return resultats
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des limites agences: {e}")
        # En cas d'erreur ou si la table n'existe pas encore, on peut retourner une liste vide
        return []

@app.get("/api/pointage-agents")
def obtenir_pointage_agents(
    #cycle: str = Query(None)
    cycle: str = Query(None),
    region: str = Query(None),
    agence: str = Query(None)
):
    condition = ""
    if agence and len(agence.strip()) > 0:
        condition = f" WHERE `periode` = '{cycle}' AND `agence_liee` LIKE '%{agence}%' "
    else:
        if region and len(region.strip()) > 0:
            condition = f" WHERE `periode` = '{cycle}' AND `ref_formulaire` = '{region}'"

    if condition and len(condition.strip()) > 0:
        connection = None
        try:
            connection = pymysql.connect(**build_db_config())
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = f"SELECT DISTINCT * FROM pointage_mensuel_odk {condition} ORDER BY `collecteur` ASC"
                #print(sql)
                cursor.execute(sql)
                resultats = cursor.fetchall()
            connection.close()
            return resultats
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des pointages agents: {e}")
            # En cas d'erreur ou si la table n'existe pas encore, on peut retourner une liste vide
            return []
    else:
        return []

@app.get("/api/pointage-clients")
def obtenir_pointage_clients(
    #cycle: str = Query(None)
    cycle: str = Query(None),
    collecteur: str = Query(None)
):
    connection = None
    try:
        connection = pymysql.connect(**build_db_config())
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = f"SELECT `contrat`, `pl`, `total`, `J1`, `J2`, `J3`, `J4`, `J5`, `J6`, `J7`, `J8`, `J9`, `J10`, `J11`, `J12`, `J13`, `J14`, `J15`, `J16`, `J17`, `J18`, `J19`, `J20`, `J21`, `J22`, `J23`, `J24`, `J25`, `J26`, `J27`, `J28`, `J29`, `J30`, `J31` FROM `pointage_mensuel_contrat_odk` WHERE `periode` = '{cycle}' AND `collecteur` = '{collecteur}'"
            cursor.execute(sql)
            resultats = cursor.fetchall()
            print(sql)
        connection.close()
        return resultats
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des pointages clients: {e}")
        # En cas d'erreur ou si la table n'existe pas encore, on peut retourner une liste vide
        return []

@app.get("/api/chargement-odk")
def obtenir_chargement_odk(cycle: str = Query(None), collecteur: str = None):
    connection = None
    try:
        connection = pymysql.connect(**build_db_config())
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            #sql = "SELECT `ref_formulaire`, `agence_liee`, `bloc`, `entreprise_collecteur`, `collecteur`, `matricule_co`, `action`, `contrat`, `pl_serial_number`, `pl_code_bare`, 'nom client', `mra_pl`, `date_filtre_telechargement`, `SubmissionDate`, `pl_photo_index`, `telephone`FROM `chargement_odk` LIMIT 10"
            sql = f"""
                    SELECT 
                        `ref_formulaire` AS region, 
                        `agence_liee` AS agency, 
                        `bloc` AS itinerary, 
                        `entreprise_collecteur` AS enterprise, 
                        `collecteur` AS agent, 
                        `matricule_co` AS matricule, 
                        `action`, 
                        `contrat`, 
                        `pl_serial_number` AS compteur, 
                        `pl_code_bare` AS barcode, 
                        'nom client' AS client_name, 
                        `mra_pl` AS pl, 
                        `date_filtre_telechargement` AS date_action, 
                        `SubmissionDate` AS date_submit, 
                        `pl_photo_index` AS photo_name, 
                        `telephone` AS phone,
                        `coordonnee_Latitude` AS lat, 
                        `coordonnee_Longitude` AS lng,
                        `pl_type_compteur` AS type_compteur,
                        CASE 
                            WHEN LENGTH(mra_contrat) > 6 AND ST_Distance_Sphere(mra_point, point) < 500 THEN 'identifie proche'
                            WHEN LENGTH(mra_contrat) > 6 AND ST_Distance_Sphere(mra_point, point) >= 500 THEN 'identifie non proche'
                            ELSE 'non identifie'
                        END AS repartition
                    FROM `chargement_odk` 
                    WHERE SUBSTRING(`date_filtre_telechargement`, 1, 7) = '{cycle}'  AND `collecteur` = '{collecteur}'
                """
            #print(sql)
            cursor.execute(sql)
            resultats = cursor.fetchall()
            
            # Ajouter un ID virtuel pour Vue.js
            for idx, item in enumerate(resultats):
                item['id'] = idx + 1

        connection.close()
        return resultats
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des pointages clients: {e}")
        # En cas d'erreur ou si la table n'existe pas encore, on peut retourner une liste vide
        return []
    
@app.get("/api/chart-quantitiesv0")
def get_chart_quantitiesv0():
    connection = None
    try:
        connection = pymysql.connect(**build_db_config())
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT 
                    SUM(`CUMUL_MOIN_500_DEPANNAGE`), SUM(`CUMUL_PLUS_500_DEPANNAGE`), SUM(`CUMUL_NON_IDENTIFIE_DEPANNAGE`),
                    SUM(`CUMUL_MOIN_500_DETECTION`), SUM(`CUMUL_PLUS_500_DETECTION`), SUM(`CUMUL_NON_IDENTIFIE_DETECTION`),
                    SUM(`CUMUL_MOIN_500_DISTRIBUTION`), SUM(`CUMUL_PLUS_500_DISTRIBUTION`), SUM(`CUMUL_NON_IDENTIFIE_DISTRIBUTION`),
                    SUM(`CUMUL_MOIN_500_INSPECTION`), SUM(`CUMUL_PLUS_500_INSPECTION`), SUM(`CUMUL_NON_IDENTIFIE_INSPECTION`),
                    SUM(`CUMUL_MOIN_500_NEW_METER`), SUM(`CUMUL_PLUS_500_NEW_METER`), SUM(`CUMUL_NON_IDENTIFIE_NEW_METER`),
                    SUM(`CUMUL_MOIN_500_NORMALISATION`), SUM(`CUMUL_PLUS_500_NORMALISATION`), SUM(`CUMUL_NON_IDENTIFIE_NORMALISATION`),
                    SUM(`CUMUL_MOIN_500_RECOUVREMENT`), SUM(`CUMUL_PLUS_500_RECOUVREMENT`), SUM(`CUMUL_NON_IDENTIFIE_RECOUVREMENT`),
                    SUM(`CUMUL_MOIN_500_RELEVE`), SUM(`CUMUL_PLUS_500_RELEVE`), SUM(`CUMUL_NON_IDENTIFIE_RELEVE`),
                    SUM(`CUMUL_MOIN_500_BRANCHEMENT`), SUM(`CUMUL_PLUS_500_BRANCHEMENT`), SUM(`CUMUL_NON_IDENTIFIE_BRANCHEMENT`)
                FROM `synthese_mensuel_odk` 
                WHERE 1
            """
            cursor.execute(sql)
            resultats = cursor.fetchall()
            #resultats = cursor.fetchone()
            
        connection.close()
        return resultats
        """
        print("resultat " + resultats)
        # Nettoyage des valeurs NULL -> 0
        clean_row = [int(val or 0) for val in resultats]
        
        # Extraction des 3 catégories (un élément tous les 3 pas)
        bien_realise = clean_row[0::3]   # Index 0, 3, 6, 9... (MOIN_500)
        mal_realise  = clean_row[1::3]   # Index 1, 4, 7, 10... (PLUS_500)
        non_execute  = clean_row[2::3]   # Index 2, 5, 8, 11... (NON_IDENTIFIE)
        
        return {
            "labels": [
                "Dépannage", "Détection", "Distribution", "Inspection", 
                "Nouveau Compteur", "Normalisation", "Recouvrement", "Relevé", "Branchement"
            ],
            "bienRealise": bien_realise,
            "malRealise": mal_realise,
            "nonExecute": non_execute
        }
        """
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des pointages clients: {e}")
        # En cas d'erreur ou si la table n'existe pas encore, on peut retourner une liste vide
        return []
    
@app.get("/api/chart-quantities")
def get_chart_quantities(
    #cycle: str = Query(None)
    cycle: str = Query(None),
    regions: str = Query(None),
    agences: str = Query(None)
):
    print("chart " + cycle)
    print(regions)
    print(agences)
    connection = None
    try:
        condition_region = ""
        if regions and len(regions.strip()) > 0:
            liste_regions = [r.strip() for r in regions.split(";")]
            elements_sql = ", ".join(f"'{r}'" for r in liste_regions)
            condition_region = f" AND `ref_formulaire` IN ({elements_sql})"
        
        condition_agence = ""
        if agences and len(agences.strip()) > 0:
            liste_agences = [r.strip() for r in agences.split(";")]
            elements_sql = ", ".join(f"'{r}'" for r in liste_agences)
            condition_agence = f" AND `agence` IN ({elements_sql})"

        connection = pymysql.connect(**build_db_config())
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = f"""
                SELECT 
                    SUM(`CUMUL_MOIN_500_DEPANNAGE`)      AS dep_moin,
                    SUM(`CUMUL_PLUS_500_DEPANNAGE`)      AS dep_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_DEPANNAGE`) AS dep_non,

                    SUM(`CUMUL_MOIN_500_DETECTION`)      AS det_moin,
                    SUM(`CUMUL_PLUS_500_DETECTION`)      AS det_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_DETECTION`) AS det_non,

                    SUM(`CUMUL_MOIN_500_DISTRIBUTION`)      AS dis_moin,
                    SUM(`CUMUL_PLUS_500_DISTRIBUTION`)      AS dis_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_DISTRIBUTION`) AS dis_non,

                    SUM(`CUMUL_MOIN_500_INSPECTION`)      AS ins_moin,
                    SUM(`CUMUL_PLUS_500_INSPECTION`)      AS ins_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_INSPECTION`) AS ins_non,

                    SUM(`CUMUL_MOIN_500_NEW_METER`)      AS nm_moin,
                    SUM(`CUMUL_PLUS_500_NEW_METER`)      AS nm_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_NEW_METER`) AS nm_non,

                    SUM(`CUMUL_MOIN_500_NORMALISATION`)      AS nor_moin,
                    SUM(`CUMUL_PLUS_500_NORMALISATION`)      AS nor_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_NORMALISATION`) AS nor_non,

                    SUM(`CUMUL_MOIN_500_RECOUVREMENT`)      AS rec_moin,
                    SUM(`CUMUL_PLUS_500_RECOUVREMENT`)      AS rec_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_RECOUVREMENT`) AS rec_non,

                    SUM(`CUMUL_MOIN_500_RELEVE`)      AS rel_moin,
                    SUM(`CUMUL_PLUS_500_RELEVE`)      AS rel_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_RELEVE`) AS rel_non,

                    SUM(`CUMUL_MOIN_500_BRANCHEMENT`)      AS bra_moin,
                    SUM(`CUMUL_PLUS_500_BRANCHEMENT`)      AS bra_plus,
                    SUM(`CUMUL_NON_IDENTIFIE_BRANCHEMENT`) AS bra_non
                FROM `synthese_mensuel_odk`
                WHERE `periode` = %s {condition_region} {condition_agence}
            """
            #cursor.execute(sql)
            
            
            cursor.execute(
                            sql,
                            (cycle,),
                        )
            
            row = cursor.fetchone() or {}

        connection.close()

        # Ordre des barres = ordre des labels dans le graphique
        actions = [
            ("DEPANNAGE",      "dep"),
            ("DETECTION",      "det"),
            ("DISTRIBUTION",   "dis"),
            ("INSPECTION",     "ins"),
            ("NEW_METER",      "nm"),
            ("NORMALISATION",  "nor"),
            ("RECOUVREMENT",   "rec"),
            ("RELEVE",         "rel"),
            ("BRANCHEMENT",    "bra"),
        ]

        labels = []
        bien_realise = []
        mal_realise = []
        non_execute = []

        for label, prefix in actions:
            labels.append(label)
            bien_realise.append(int(row.get(f"{prefix}_moin") or 0))
            mal_realise.append(int(row.get(f"{prefix}_plus") or 0))
            non_execute.append(int(row.get(f"{prefix}_non") or 0))

        return {
            "labels": labels,
            "bienRealise": bien_realise,   # MOIN_500
            "malRealise": mal_realise,     # PLUS_500
            "nonExecute": non_execute      # NON_IDENTIFIE
        }

    except Exception as e:
        print(f"❌ Erreur chart-quantities: {e}")
        return {
            "labels": [],
            "bienRealise": [],
            "malRealise": [],
            "nonExecute": []
        }

@app.get("/api/contours/bloc/{code_bloc}")
def obtenir_contour_bloc(code_bloc: str):
    connection = None
    try:
        connection = pymysql.connect(**build_db_config())
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Récupère la géométrie au format GeoJSON (ST_AsGeoJSON pour MySQL 5.7+)
            sql = "SELECT `block_code`, `ZONE_CODE`, `LOCALITE`, ST_AsGeoJSON(boundary) AS boundary FROM `bloc` WHERE `block_code` = %s"
            cursor.execute(sql, (code_bloc,))
            resultat = cursor.fetchone()
            if resultat and resultat.get('boundary'):
                print(resultat)
                import json
                return {
                    "type": "Feature",
                    "properties": {"code_bloc": resultat["block_code"]},
                    "geometry": json.loads(resultat["boundary"])
                }
        return None
    except Exception as e:
        print(f"❌ Erreur lors de la récupération du contour bloc: {e}")
        return None
    finally:
        if connection:
            connection.close()



@app.post("/api/contours/blocs-multiples")
def obtenir_contours_blocs_multiples(codes_blocs: list[str] = Body(...)):
    if not codes_blocs:
        return {"type": "FeatureCollection", "features": []}
    
    connection = None
    try:
        connection = pymysql.connect(**build_db_config())
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Sécurisation des arguments pour la clause IN (...)
            format_strings = ','.join(['%s'] * len(codes_blocs))
            sql = f"""
                SELECT code_bloc, ST_AsGeoJSON(geometry) AS geojson 
                FROM `contours_blocs` 
                WHERE `code_bloc` IN ({format_strings})
            """
            sql = f"SELECT `block_code`, `ZONE_CODE`, `LOCALITE`, ST_AsGeoJSON(boundary) AS boundary FROM `bloc` WHERE `block_code` IN ({format_strings})"
            cursor.execute(sql, tuple(codes_blocs))
            results = cursor.fetchall()
            features = []
            import json
            for row in results:
                if row.get('boundary'):
                    features.append({
                        "type": "Feature",
                        "properties": {"code_bloc": row["block_code"]},
                        "geometry": json.loads(row["boundary"])
                    })
            print(sql)
            print(features)
            return {
                "type": "FeatureCollection",
                "features": features
            }
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des contours blocs: {e}")
        return {"type": "FeatureCollection", "features": []}
    finally:
        if connection:
            connection.close()
# =========================================================================
# 6. SÉCURITÉ UNIVERSELLE ANTI-404 POUR LES SPA ROUTER (Toutes vos pages)
# =========================================================================
@app.exception_handler(404)
async def redirection_spa_catch_all(request, exc):
    """
    Si l'utilisateur demande une URL que l'exécutable FastAPI ne connaît pas
    (votre 3ème page /telechargement), Python lui renvoie l'index.html de Vue
    pour que l'interface s'affiche proprement sans planter.
    """
    chemin_index = dossier_dist / "index.html"
    if chemin_index.exists():
        return FileResponse(str(chemin_index))
    return HTMLResponse(content="<h1>Interface d'application introuvable</h1>", status_code=404)


# ----------------------------------------------------
# 3. MOUNT DU DOSSIER DES PHOTOS (OBLIGATOIREMENT AVANT LE FRONTEND)
# ----------------------------------------------------
app.mount("/photos", StaticFiles(directory=str(dossier_photos)), name="photos")
print(f"📁 [PHOTOS] Dossier photos servi depuis : {dossier_photos}")

print(f"👉 Le dossier des photos pointe vers : {dossier_photos.resolve()}")
print(f"👉 L'image fulstark.png existe-t-elle ici ? {(dossier_photos / 'fulstark.png').exists()}")


# ----------------------------------------------------
# 4. MOUNT DU FRONTEND (TOUJOURS EN DERNIER)
# ----------------------------------------------------
# =========================================================================
# 7. DISTRIBUTION GLOBALE DE L'INTERFACE GRAPHIQUE (À placer à la fin)
# =========================================================================
if dossier_dist.exists():
    # Monte l'ensemble de la racine de dist/ en mode HTML statique unifié
    app.mount("/", StaticFiles(directory=str(dossier_dist), html=True), name="frontend")
else:
    print("⚠️ [DÉVELOPPEMENT] Le dossier 'dist' est introuvable. Distribuez l'interface manuellement via Vite.")

# =========================================================================
# 8. EXÉCUTION DU SERVEUR WEB (Optimisé pour l'affichage de la Console)
# =========================================================================
if __name__ == "__main__":
    import uvicorn
    print("🚀 [SERVER] Démarrage du serveur Uvicorn sur http://127.0.0.1:8000")
    
    # Configuration nettoyée : la suppression de log_config=None réactive
    # les affichages de requêtes en direct à l'intérieur de votre fenêtre noire.
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000
    )

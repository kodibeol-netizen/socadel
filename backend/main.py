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
    # 🔒 MODE EXÉCUTABLE (.EXE) : Le dossier dist doit rester à l'EXTÉRIEUR
    BASE_DIR = Path(sys.executable).resolve().parent
    dossier_dist = BASE_DIR / "dist"
else:
    # 💻 MODE DÉVELOPPEMENT CLASSIQUE (VS Code)
    FICHIER_ACTUEL = Path(__file__).resolve()
    BASE_DIR = FICHIER_ACTUEL.parent  # Dossier /backend/
    dossier_dist = BASE_DIR.parent / "frontend" / "dist"
    #dossier_dist = BASE_DIR.parent / "socadel" / "dist"

print("[DÉTECTION DIST] Chemin calculé : " + str(dossier_dist.resolve()))
print("[DÉTECTION INDEX] index.html existe ? : " + str((dossier_dist / 'index.html').exists()))


# =========================================================================
# 3. ⚙️ LE VRAI GÉNÉRATEUR DE FLUX ASYNCHRONE COMPATIBLE SSE
# =========================================================================
async def generateur_traitement_flux(date_cible: str):
    """
    Cette fonction encapsule toute votre logique métier et utilise 'yield'
    pour envoyer les statuts et la progression en temps réel à Vue.js.
    """
    print(f"🔄 Démarrage du traitement pour la date : {date_cible}")
    yield f"data: {json.dumps({'statut': f'🔄 Initialisation du traitement pour la date : {date_cible}'})}\n\n"

    # --- ÉTAPE A : VÉRIFICATION DE LA LICENCE ---
    original_word = ''.join(random.choices(string.ascii_letters, k=10))
    exposant, modulo = 5, 323
    encoded_list = [str(pow(ord(char), exposant, modulo)) for char in original_word]
    cle_generee = "-".join(encoded_list)

    url_licence = f"https://{domaine}/cle.php?tel={str(uuid())}&date={date_cible}&cle={cle_generee}"
    
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
                        print("✅ Connexion master réussie à Postgres (psycopg2)")
                    else:
                        # Essaie avec pymysql (MySQL)
                        connection_master = pymysql.connect(**db_config_master)
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
                
                async for message in telecharger_fichiers(date_cible, real_urls, connection, connection_master):
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

# =========================================================================
# 4. 🚀 ROUTE API UNIQUE FASTAPI (Attend le paramètre de date web)
# =========================================================================
@app.get("/api/traitement")
async def api_lancer_traitement(date: str = Query(None)):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
        
    print(f"📡 Demande de traitement reçue depuis l'interface pour la date : {date}")
 
    return StreamingResponse(
        generateur_traitement_flux(date), 
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
async def api_synthese(cycle: str = Query(None)):
    if not cycle:
        return {"rows": [], "cycle": None, "message": "Aucun cycle fourni."}

    connection = None
    try:
        connection = pymysql.connect(**build_db_config())
        day_columns = ",\n".join([f"`J{day}`" for day in range(1, 32)])
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                f"""
                SELECT
                    `periode`,
                    `ref_formulaire`,
                    `agence`,
                    `bloc`,
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
                WHERE `periode` = %s
                ORDER BY `ref_formulaire`, `bloc`, `periode`
                """,
                (cycle,),
            )
            rows = cursor.fetchall()

        normalized_rows = normalize_synthese_rows(rows)
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

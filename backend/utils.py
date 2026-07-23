import os
import re
import sys
import httpx
import urllib.parse
import zipfile
import re
import csv
import pymysql
try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None
import platform
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import requests

import asyncio
import json

"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""
def uuid():
    system = platform.system()

    # --- Cas LINUX ---
    if system == "Linux":
        paths = ["/etc/machine-id", "/var/lib/dbus/machine-id"]
        for path in paths:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read().strip()

    # --- Cas WINDOWS ---
    elif system == "Windows":
        try:
            # On utilise la commande shell pour lire l'UUID dans le registre
            cmd = 'reg query "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography" /v MachineGuid'
            result = subprocess.check_output(cmd, shell=True).decode()
            # On extrait l'UUID de la chaîne de réponse
            return result.split()[-1]
        except Exception:
            return "pas de chemin"

    # --- AUTRES SYSTÈMES ---
    return "pas de chemin"

def is_connection_open(conn):
    """Unified check whether a DB connection is open for pymysql or psycopg2."""
    try:
        if conn is None:
            return False
        if hasattr(conn, 'open'):
            return bool(conn.open)
        if hasattr(conn, 'closed'):
            return conn.closed == 0
    except Exception:
        return False
    return False

def charger(result: list, date: str, heure: str, form: str, connection, connection_master):
    """
    Insère en masse (Bulk Insert) les données CSV, images et logs dans la base MySQL.
    Gère la mise à jour des doublons via ON DUPLICATE KEY UPDATE (Syntaxe optimisée MySQL 8.0+).
    
    :param connection: Une connexion active retournée par pymysql.connect()
    :param connection_master: Une connexion active vers la base master
    """
    result_jpg = result[2]
    result_csv = result[1]

    try:
        # =========================================================================
        # SECTION 1 : TRAITEMENT ET CHARGEMENT DES DONNÉES CSV
        # =========================================================================
        if result_csv:
            # 1. Liste stricte de toutes les colonnes de votre table (incluant 'point')
            colonnes_csv = [
                'SubmissionDate', 'entreprise_collecteur', 'collecteur', 'matricule_co', 'source', 'depart', 'poste', 'Type_de_poste', 'photo_poste', 'nbr_depart',
                'code_depart', 'Eclairage', 'lumiere', 'photo_lanterne', 'existence', 'telephone', 'qualite', 'accesibilite', 'pl_codes_barcodes', 'pl_code_bare',
                'pl_raison', 'pl_status', 'pl_type_compteur', 'pl_nbr_fil', 'pl_batiment', 'pl_type_immeuble', 'pl_mode_alimentation', 'pl_section_cable',
                'pl_activite', 'pl_serial_numbers_list', 'pl_serial_number', 'contrat', 'pl_index', 'pl_photo_index',
                'coordonnee_Latitude', 'coordonnee_Longitude', 'coordonnee_Altitude', 'coordonnee_Accuracy', 'action', 'photo', 'code_anomaly',
                'I1_entre', 'I2_entre', 'I3_entre', 'I4_entre', 'I1_sortie', 'I2_sortie', 'I3_sortie', 'I4_sortie', 'id', 'uuid', 'date_jour', 'note', 'instanceID',
                'cle', 'SubmitterID', 'SubmitterName', 'AttachmentsPresent', 'AttachmentsExpected', 'Status', 'ReviewState', 'DeviceID', 'Edits', 'FormVersion', 'ajout_telephone',
                'agence_liee', 'banoc_code', 'date_submission', 'form', 'ref_formulaire', 'date_filtre_telechargement', 'heure_date_filtre_telechargement',
                'bloc', 'mra_contrat', 'mra_compteur', 'mra_pl', 'point'
            ]

            tuples_csv = []
            for r in result_csv:
                ligne = []
                # On extrait toutes les colonnes standards (sauf la dernière 'point')
                for col in colonnes_csv[:-1]:
                    ligne.append(r.get(col, ''))
                    
                # Validation et extraction sécurisée des coordonnées géospatiales
                try:
                    lat_val = float(r.get('coordonnee_Latitude', 0) or 0)
                    lng_val = float(r.get('coordonnee_Longitude', 0) or 0)
                except (ValueError, TypeError):
                    lat_val, lng_val = 0.0, 0.0
                
                if lat_val != 0.0 and lng_val != 0.0:
                    wkt_point = f"POINT({lng_val} {lat_val})"
                else:
                    wkt_point = "POINT(0 0)"
                    
                # Ajout de la valeur géométrique à la fin du tuple
                ligne.append(wkt_point)
                tuples_csv.append(tuple(ligne))

            # 2. Construction dynamique des marqueurs (%s)
            placeholders = ["%s"] * (len(colonnes_csv) - 1)
            string_placeholders_master = ", ".join(placeholders) + ", ST_GeomFromText(%s, 4326)"
            string_placeholders = ", ".join(placeholders) + ", %s"
                
            # 3. Requêtes SQL optimisées avec alias (évite la lenteur du VALUES() obsolète sur les UUID)
            sql_csv = f"""
                INSERT INTO tmp_chargement_odk (
                    {", ".join(colonnes_csv)}
                )
                VALUES ({string_placeholders})
                ON DUPLICATE KEY UPDATE 
                    action = VALUES(action),
                    pl_serial_number = VALUES(pl_serial_number),
                    coordonnee_Latitude = VALUES(coordonnee_Latitude),
                    coordonnee_Longitude = VALUES(coordonnee_Longitude),
                    coordonnee_Altitude = VALUES(coordonnee_Altitude),
                    coordonnee_Accuracy = VALUES(coordonnee_Accuracy);
            """
            sql_csv_master = f"""
                INSERT INTO tmp_chargement_odk (
                    {", ".join(colonnes_csv)}
                )
                VALUES ({string_placeholders_master})
                ON DUPLICATE KEY UPDATE 
                    action = VALUES(action),
                    pl_serial_number = VALUES(pl_serial_number),
                    coordonnee_Latitude = VALUES(coordonnee_Latitude),
                    coordonnee_Longitude = VALUES(coordonnee_Longitude),
                    coordonnee_Altitude = VALUES(coordonnee_Altitude),
                    coordonnee_Accuracy = VALUES(coordonnee_Accuracy);
            """
            sql_csv_master = f"""
                INSERT INTO tmp_chargement_odk ({", ".join(colonnes_csv)})
                VALUES ({string_placeholders_master})
                ON CONFLICT (id) 
                DO UPDATE SET 
                    action = EXCLUDED.action, pl_serial_number = EXCLUDED.pl_serial_number,
                    coordonnee_Latitude = EXCLUDED.coordonnee_Latitude, coordonnee_Longitude = EXCLUDED.coordonnee_Longitude,
                    coordonnee_Altitude = EXCLUDED.coordonnee_Altitude, coordonnee_Accuracy = EXCLUDED.coordonnee_Accuracy;
            """

            # 4. Exécution optimisée par VRAIS LOTS de 1 000
            if is_connection_open(connection):
                with connection.cursor() as cursor_csv:
                    for i in range(0, len(tuples_csv), 1000):
                        lot_actuel = tuples_csv[i:i + 1000]
                        try:
                            # Envoi du lot complet en une fois
                            lignes_aff = cursor_csv.executemany(sql_csv, lot_actuel)
                            print(f"⚡ [CSV] Lot {i // 1000 + 1} envoyé en mémoire ({len(lot_actuel)} lignes). Affectées : {lignes_aff}")
                            
                        except pymysql.MySQLError as e:
                            connection.rollback()
                            print(f"❌ Erreur MySQL lors du lot CSV {i // 1000 + 1}: {e}")
                            if hasattr(cursor_csv, '_executed') and cursor_csv._executed:
                                print("=== 🚨 DERNIÈRE REQUÊTE EN ERREUR ===")
                                print(cursor_csv._executed[:2000])
                            raise e
                
                # Un seul commit disque pour TOUT le bloc CSV local
                connection.commit()
                print("💾 [SUCCESS] Toutes les données CSV locales ont été validées sur le disque.")

            # Même logique pour la connexion MASTER (si applicable dans votre architecture)
            if connection_master and is_connection_open(connection_master):
                # Support psycopg2 connection cursors as well
                if psycopg2 and isinstance(connection_master, psycopg2.extensions.connection):
                    with connection_master.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor_csv_master:
                        for i in range(0, len(tuples_csv), 1000):
                            lot_actuel = tuples_csv[i:i + 1000]
                            try:
                                cursor_csv_master.executemany(sql_csv_master, lot_actuel)
                            except Exception as e:
                                connection_master.rollback()
                                print(f"❌ Erreur MASTER Postgres lors du lot CSV : {e}")
                                raise e
                else:
                    with connection_master.cursor() as cursor_csv_master:
                        for i in range(0, len(tuples_csv), 1000):
                            lot_actuel = tuples_csv[i:i + 1000]
                            try:
                                cursor_csv_master.executemany(sql_csv_master, lot_actuel)
                            except pymysql.MySQLError as e:
                                connection_master.rollback()
                                print(f"❌ Erreur MySQL MASTER lors du lot CSV : {e}")
                                raise e
                    for i in range(0, len(tuples_csv), 1000):
                        lot_actuel = tuples_csv[i:i + 1000]
                        try:
                            cursor_csv_master.executemany(sql_csv_master, lot_actuel)
                        except pymysql.MySQLError as e:
                            connection_master.rollback()
                            print(f"❌ Erreur MySQL MASTER lors du lot CSV : {e}")
                            raise e
                
                # Un seul commit disque pour TOUT le bloc CSV master
                connection_master.commit()
                print("💾 [SUCCESS] Toutes les données CSV MASTER ont été validées sur le disque.")
            # -----------------------------------------------------------------
            # FIN DE LA SECTION 1 (CSV MASTER) : Exécution optimisée par VRAIS LOTS
            # -----------------------------------------------------------------
            if connection_master and is_connection_open(connection_master):
                if psycopg2 and isinstance(connection_master, psycopg2.extensions.connection):
                    with connection_master.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor_csv_master:
                        for i in range(0, len(tuples_csv), 1000):
                            lot_actuel = tuples_csv[i:i + 1000]
                            try:
                                lignes_aff_master = cursor_csv_master.executemany(sql_csv_master, lot_actuel)
                                print(f"⚡ [CSV MASTER] Lot {i // 1000 + 1} envoyé en mémoire ({len(lot_actuel)} lignes). Affectées : {lignes_aff_master}")
                            except Exception as e:
                                connection_master.rollback()
                                print(f"❌ Erreur MASTER lors du lot CSV {i // 1000 + 1} : {e}")
                                raise e
                else:
                    with connection_master.cursor() as cursor_csv_master:
                        for i in range(0, len(tuples_csv), 1000):
                            lot_actuel = tuples_csv[i:i + 1000]
                            try:
                                lignes_aff_master = cursor_csv_master.executemany(sql_csv_master, lot_actuel)
                                print(f"⚡ [CSV MASTER] Lot {i // 1000 + 1} envoyé en mémoire ({len(lot_actuel)} lignes). Affectées : {lignes_aff_master}")
                            except pymysql.MySQLError as e:
                                connection_master.rollback()
                                print(f"❌ Erreur MySQL MASTER lors du lot CSV {i // 1000 + 1} : {e}")
                                raise e
                    for i in range(0, len(tuples_csv), 1000):
                        lot_actuel = tuples_csv[i:i + 1000]
                        try:
                            lignes_aff_master = cursor_csv_master.executemany(sql_csv_master, lot_actuel)
                            print(f"⚡ [CSV MASTER] Lot {i // 1000 + 1} envoyé en mémoire ({len(lot_actuel)} lignes). Affectées : {lignes_aff_master}")
                                
                        except pymysql.MySQLError as e:
                            connection_master.rollback()
                            print(f"❌ Erreur MySQL MASTER lors du lot CSV {i // 1000 + 1} : {e}")
                            if hasattr(cursor_csv_master, '_executed') and cursor_csv_master._executed:
                                print("=== REQUÊTE MASTER EN FAUTE ===")
                                print(cursor_csv_master._executed[:2000])
                            raise e
                        
                    # Un seul commit final pour le CSV Master
                    connection_master.commit()
                    print(f"💾 [SUCCESS] Tout le lot de {len(tuples_csv)} lignes CSV MASTER a été validé et écrit.")
              
        # =====================================================================
        # SECTION 2 : CHARGEMENT DES IMAGES (JPG)
        # =====================================================================
        if result_jpg:
            # Syntaxe optimisée avec l'alias 'nouveau' (Plus rapide sur l'index de clé primaire)
            sql_image = """
                INSERT INTO image (form, date, heure, nom, taille) 
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE nom = VALUES(nom);
            """
            sql_image = """
                INSERT INTO image (form, date, heure, nom, taille) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (nom) DO UPDATE SET nom = EXCLUDED.nom;
            """
               
            # Transformation en liste de tuples ordonnés pour le moteur MySQL
            tuples_jpg = [
                (r['form'], r['date'], r['heure'], r['nom'], r['taille']) 
                for r in result_jpg
            ]
            
            if connection_master and is_connection_open(connection_master):
                if psycopg2 and isinstance(connection_master, psycopg2.extensions.connection):
                    with connection_master.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor_master:
                        try:
                            for i in range(0, len(tuples_jpg), 1000):
                                lot_actuel = tuples_jpg[i:i + 1000]
                                lignes_affectees = cursor_master.executemany(sql_image, lot_actuel)
                                print(f"⚡ [IMAGES MASTER] Morceau {i // 1000 + 1} envoyé en mémoire ({len(lot_actuel)} images).")
                            connection_master.commit()
                            print(f"💾 [SUCCESS] Les {len(tuples_jpg)} images ont été écrites physiquement sur le disque Master.")
                        except Exception as error_img:
                            connection_master.rollback()
                            print(f"❌ Erreur MASTER spécifique aux images (Transaction annulée) : {error_img}")
                            raise error_img
                else:
                    with connection_master.cursor() as cursor_master:
                        try:
                            for i in range(0, len(tuples_jpg), 1000):
                                lot_actuel = tuples_jpg[i:i + 1000]
                                lignes_affectees = cursor_master.executemany(sql_image, lot_actuel)
                                print(f"⚡ [IMAGES MASTER] Morceau {i // 1000 + 1} envoyé en mémoire ({len(lot_actuel)} images).")
                            connection_master.commit()
                            print(f"💾 [SUCCESS] Les {len(tuples_jpg)} images ont été écrites physiquement sur le disque Master.")
                        except pymysql.MySQLError as error_img:
                            connection_master.rollback()
                            print(f"❌ Erreur MySQL spécifique aux images (Transaction annulée) : {error_img}")
                            raise error_img
                    try:
                        for i in range(0, len(tuples_jpg), 1000):
                            lot_actuel = tuples_jpg[i:i + 1000]
                            lignes_affectees = cursor_master.executemany(sql_image, lot_actuel)
                            print(f"⚡ [IMAGES MASTER] Morceau {i // 1000 + 1} envoyé en mémoire ({len(lot_actuel)} images).")
                        
                        # 🔥 CORRECTIF : Sorti de la boucle. On valide l'écriture de TOUTES les images d'un coup
                        connection_master.commit()
                        print(f"💾 [SUCCESS] Les {len(tuples_jpg)} images ont été écrites physiquement sur le disque Master.")
                            
                    except pymysql.MySQLError as error_img:
                        connection_master.rollback()
                        print(f"❌ Erreur MySQL spécifique aux images (Transaction annulée) : {error_img}")
                        raise error_img



        sql_agence_lies = """
            UPDATE tmp_chargement_odk
            SET agence_liee = COALESCE(rech.agences_liees, 'non identifie')
            FROM (
                SELECT 
                    t.cle, 
                    string_agg(bc.agency, ';') AS agences_liees
                FROM tmp_chargement_odk AS t
                JOIN limites_agences AS bc 
                ON ST_Contains(
                    bc.boundary, 
                    ST_GeomFromText('POINT(' || t.coordonnee_Longitude || ' ' || t.coordonnee_Latitude || ')', 4326)
                    )
                WHERE t.coordonnee_Longitude IS NOT NULL AND t.coordonnee_Latitude IS NOT NULL
                GROUP BY t.cle
            ) AS rech
            WHERE tmp_chargement_odk.cle = rech.cle
            AND (tmp_chargement_odk.agence_liee IS NULL OR tmp_chargement_odk.agence_liee = '');
        """  
        sql_bloc = """
            UPDATE tmp_chargement_odk
            SET 
                bloc = COALESCE(bc.block_code, 'bloc non identifie'),
                agence_liee = COALESCE(bc.agence, 'agence non identifie')
            FROM bloc AS bc
            WHERE ST_Contains(
                    bc.boundary, 
                    ST_GeomFromText('POINT(' || tmp_chargement_odk.coordonnee_Longitude || ' ' || tmp_chargement_odk.coordonnee_Latitude || ')', 4326)
                ) 
            AND bc.agency = ANY(string_to_array(tmp_chargement_odk.agence_liee, ';'))
            AND (tmp_chargement_odk.bloc IS NULL OR tmp_chargement_odk.bloc = '')
            AND tmp_chargement_odk.coordonnee_Longitude IS NOT NULL 
            AND tmp_chargement_odk.coordonnee_Latitude IS NOT NULL;
        """   
        sql_mra = """
            UPDATE tmp_chargement_odk AS target
            SET 
                mra_contrat  = COALESCE(sub.mra_contrat, 'non identifie'),
                mra_compteur = COALESCE(sub.mra_compteur, 'non identifie'),
                mra_pl       = COALESCE(sub.mra_pl, 'non identifie')
            FROM (
                SELECT 
                    t.cle,
                    mra.contrat AS mra_contrat,
                    mra.compteur AS mra_compteur,
                    mra.pl AS mra_pl
                FROM tmp_chargement_odk AS t
                JOIN bloc AS bc ON t.bloc = bc.block_code
                JOIN mra AS mra ON (
                    bc.SALESPOINT = mra.code_agence 
                    AND (
                        mra.compteur = ANY(string_to_array(t.pl_code_bare, ','))
                        OR mra.compteur = ANY(string_to_array(t.pl_serial_number, ','))
                        OR mra.contrat = ANY(string_to_array(t.contrat, ','))
                    )
                )
                WHERE (t.ref_formulaire = 'DRC' OR t.ref_formulaire = 'DCUY') 
                AND (t.mra_contrat IS NULL OR t.mra_contrat = '')
                ORDER BY t.cle ASC
                LIMIT 10000
            ) AS sub
            WHERE target.cle = sub.cle;
        """

        sql_copier_tmp = """
            INSERT INTO chargement_odk
            SELECT t.*
            FROM tmp_chargement_odk AS t
            JOIN logs_importation_odk AS l 
            ON t.form = l.form
            AND t.date_filtre_telechargement = l.date
            AND t.heure_date_filtre_telechargement = l.heure
            WHERE LENGTH(t.bloc) > 0
            ON CONFLICT (id) 
            DO UPDATE SET form = EXCLUDED.form;
        """
        sql_vider_tmp = """
            DELETE FROM tmp_chargement_odk AS t
            USING chargement_odk AS l
            WHERE t.cle = l.cle
            AND LENGTH(t.bloc) > 0;
        """
        # =====================================================================
        # SECTION 3 : LOGS D'IMPORTATION
        # =====================================================================
        limite_temps = datetime.now() - timedelta(hours=2)
        date_time_ligne = datetime.strptime(f"{date} {heure}:00:00", "%Y-%m-%d %H:%M:%S")
            
        if date_time_ligne <= limite_temps:
            sql_logs_master = """
                INSERT INTO logs_importation_odk (form, date, heure, qte_csv, qte_image) 
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    qte_csv = VALUES(qte_csv),
                    qte_image = VALUES(qte_image);
            """
            sql_logs_master = """
                INSERT INTO logs_importation_odk (form, date, heure, qte_csv, qte_image) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (form, date, heure) DO UPDATE SET qte_csv = EXCLUDED.qte_csv, qte_image = EXCLUDED.qte_image;
            """
            sql_logs_master = """
                INSERT INTO logs_importation_odk (form, date, heure, qte_csv, qte_image, update_at) 
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (form, date, heure) 
                DO UPDATE SET 
                    qte_csv = EXCLUDED.qte_csv,
                    qte_image = EXCLUDED.qte_image,
                    update_at = NOW();
            """
            sql_logs = """
                INSERT INTO logs_importation_odk (form, date, heure) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    form = VALUES(form);
            """

            
            # Écriture du log en local
            if is_connection_open(connection):
                with connection.cursor() as cursor_log:
                    cursor_log.execute(sql_logs, [form, date, heure])
                connection.commit()
                
            # Écriture du log sur le Master
            if connection_master and is_connection_open(connection_master):
                if psycopg2 and isinstance(connection_master, psycopg2.extensions.connection):
                    with connection_master.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor_log_master:
                        cursor_log_master.execute(sql_agence_lies)
                        cursor_log_master.execute(sql_bloc)
                        cursor_log_master.execute(sql_mra)
                        cursor_log_master.execute(sql_copier_tmp)
                        cursor_log_master.execute(sql_vider_tmp)
                        cursor_log_master.execute(sql_logs_master, [form, date, heure, result[3], result[4]])
                    connection_master.commit()
                else:
                    with connection_master.cursor() as cursor_log_master:
                        cursor_log_master.execute(sql_logs_master, [form, date, heure, result[3], result[4]])
                    connection_master.commit()
                
            print(f"✅ Logs enregistrés. Données importées avec succès : {len(result_jpg)} images et {len(result_csv)} lignes CSV.")
            
    except pymysql.MySQLError as e:
        # Sécurité globale si une erreur non gérée survient en amont
        if is_connection_open(connection):
            try:
                connection.rollback()
            except Exception:
                pass
        if connection_master and is_connection_open(connection_master):
            try:
                connection_master.rollback()
            except Exception:
                pass
        print(f"❌ Erreur critique globale MySQL, transactions annulées : {e}")
    finally:
        # Les contextes 'with' gèrent la fermeture des curseurs automatiquement.
        pass

def s(texte: str) -> str:
    """
    Nettoie et normalise les chaînes de caractères (Équivalent strict de s() en PHP).
    """
    if not texte:
        return ""
        
    # 1. Remplacer les apostrophes par un espace
    texte = texte.replace("'", " ")

    # 2. Nettoyer le reste des caractères interdits (Conserve uniquement a-z, A-Z, 0-9, ;, _, :, ,, ., -, et espace)
    texte = re.sub(r'[^a-zA-Z0-9;_:,.\- ]', '', texte)

    # 3. Réduire les espaces multiples en un seul espace
    return re.sub(r'\s+', ' ', texte).strip()

def json_geohash_encode(latitude: float, longitude: float, precision: int = 8) -> str:
    """
    Calcule le GeoHash d'une coordonnée (Équivalent strict de json_geohash_encode() en PHP).
    """
    b32 = '0123456789bcdefghjkmnpqrstuvwxyz'
    is_even = True
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    geohash = ''
    bit = 0
    ch = 0

    while len(geohash) < precision:
        if is_even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if longitude > mid:
                ch |= (1 << (4 - bit))
                lon_range[0] = mid
            else:
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if latitude > mid:
                ch |= (1 << (4 - bit))
                lat_range[0] = mid
            else:
                lat_range[1] = mid

        is_even = not is_even
        if bit < 4:
            bit += 1
        else:
            geohash += b32[ch]
            bit = 0
            ch = 0
            
    return geohash

def pos_valeur_matrix(nom_entete: str, form: str, pos: dict, b_bloc: list, normaliser: int) -> str:
    """
    Extrait les données matricielles des lignes CSV (Équivalent strict de pos_valeur_matrix() en PHP).
    """
    result = ""
    
    # if (isset($pos[$form]))
    if form in pos:
        # if($form != "" and ($pos[$form]) >= 0)
        if form != "" and pos[form] >= 0:
            
            # $positions = explode("-", $pos[$nom_entete][$pos[$form]]);
            index_formulaire = pos[form]
            chaine_positions = pos[nom_entete][index_formulaire]
            
            if chaine_positions:
                positions = chaine_positions.split("-")
                
                for position_str in positions:
                    if not position_str:
                        continue
                        
                    position = int(position_str)
                    
                    # if($position > 0)
                    if position > 0:
                        index_reel = position - 1
                        
                        # Sécurité Python : On s'assure que l'index existe dans le tableau b_bloc
                        if index_reel < len(b_bloc):
                            valeur_cellule = str(b_bloc[index_reel])
                            
                            # if(strlen($result) == 0)
                            if len(result) == 0:
                                if normaliser == 1:
                                    result = s(valeur_cellule)
                                else:
                                    result = valeur_cellule
                            else:
                                # if(strlen($b_bloc[$position - 1]) > 0)
                                if len(valeur_cellule) > 0:
                                    if normaliser == 1:
                                        result += "|" + s(valeur_cellule)
                                    else:
                                        result += "|" + valeur_cellule

    # return str_replace("'", "’", $result);
    return result.replace("'", "’")

async def traiter_fichier(date_str: str, urls: dict) -> list:
    """
    Analyse l'archive ZIP d'ODK, extrait et corrige la structure du CSV,
    puis prépare les listes de données structurées pour l'insertion en BDD.
    """
    # Initialisation exacte du dictionnaire $tab_pos
    tab_pos = {}

    tab_pos["drsm"] = 0
    tab_pos["drd"] = 1
    tab_pos["dre"] = 2
    tab_pos["Drsano"] = 3
    tab_pos["drnea"] = 4
    tab_pos["dry"] = 5
    tab_pos["drsom"] = 6
    tab_pos["NORD"] = 7
    tab_pos["EXTREME-NORD"] = 8
    tab_pos["ADAMAOUA"] = 9
    tab_pos["DRC_C"] = 10
    tab_pos["yde1"] = 11
    tab_pos["DRC"] = 12
    tab_pos["drono_"] = 13
    tab_pos["ratissage_drd_2025"] = 14

    tab_pos["forms"] = ["drsm", "drd", "dre", "Drsano", "drnea", "dry", "drsom", "nord", "EXTREME-NORD", "ADAMAOUA", "drc_c", "yde1", "drc", "drono_", "ratissage_drd_2025"]
    tab_pos["id"] = ["55", "56", "55", "55", "55", "55", "56", "111", "111", "111", "233", "234", "214", "49", "20"]
    tab_pos["pl/info_pl/status"] = ["22", "22", "22", "22", "22", "26-60", "23", "19", "19", "19", "238", "239", "219", "54", "25"]
    tab_pos["pl/info_pl/activite"] = ["29", "29", "29", "29", "29", "33", "30", "", "", "", "25-49-63-77-91-101-141-171-190-199-213", "26-50-64-78-92-102-142-191-200-214", "27-49-61-73-85-93-132-158-175-182-196", "44", ""]
    tab_pos["pl/info_pl/batiment"] = ["25", "25", "25", "25", "25", "29", "26", "23", "23", "23", "137-169-188", "138-170-189", "128-156-173", "", "13"]
    tab_pos["pl/info_pl/nbr_fil"] = ["24", "24", "24", "24", "24", "28", "25", "28", "28", "28", "28-136-168-187", "29-137-169-188", "29-127-155-172", "24", ""]
    tab_pos["pl/info_pl/code_bare"] = ["20", "20", "20", "20", "20", "24", "21", "31-38-73", "31-38-73", "31-38-73", "33-56-70-84-94-103-143-163-179-195-215", "34-57-71-85-95-104-144-164-180-196-216", "33-54-66-78-87-95-134-152-166-180-198", "26-37", "6"]
    tab_pos["pl/info_pl/photo_index"] = ["34", "34", "34", "34", "34", "38", "35", "48", "48", "48", "43-147-165-181", "44-148-166-182", "43-136-153-167", "27-41", "16"]
    tab_pos["pl/info_pl/serial_number"] = ["31", "31", "31", "31", "31", "34-35", "32", "33-37-42-72", "33-37-42-72", "33-37-42-72", "180-196-216", "181-197-217", "8", "33-34-38", "7"]
    tab_pos["pl/info_pl/type_compteur"] = ["23", "23", "23", "23", "23", "27", "24", "29", "29", "29", "26-50-64-78-92-102-135-161-177-193", "27-51-65-79-93-103-136-162-178-194", "28-50-62-74-86-94-126-150-164-178", "22", "5"]
    tab_pos["pl/info_pl/index"] = ["33", "33", "33", "33", "33", "37", "24", "44", "44", "44", "32-34-68-82-96-146-166-182-183-184-185-197", "33-35-69-83-97-147-167-183-184-185-186-198", "32-34-65-77-89-135-154-168-169-170-171-181", "35-40", ""]
    tab_pos["pl/info_pl/raison"] = ["21", "21", "21", "21", "21", "25", "22", "32", "32", "32", "218", "219", "199", "", ""]
    tab_pos["pl/info_pl/contrat"] = ["32", "32", "32", "32", "32", "36", "33", "35", "35", "35", "27-52-66-80-97-117-145-167-186-198-217", "28-53-67-81-98-118-146-168-187-199-218", "9", "43", ""]
    tab_pos["pl/info_pl/image_url"] = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
    tab_pos["date"] = ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "1", "0"]
    tab_pos["action"] = ["39", "39", "39", "39", "39", "39", "40", "6", "6", "6", "5", "5", "5", "15", ""]
    tab_pos["nbr_pl"] = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
    tab_pos["contrat"] = ["32", "32", "32", "32", "32", "36", "33", "35", "35", "35", "27-52-66-80-97-117-145-167-186-198-217", "28-53-67-81-98-118-146-168-187-199-218", "9", "43", ""]
    tab_pos["montant"] = ["", "", "", "", "", "", "", "", "", "", "53-67-81-222", "54-68-82-223", "52-64-76-203", "20", ""]
    tab_pos["Collecteur"] = ["3", "3", "3", "3", "3", "7", "3", "7", "7", "7", "6", "6", "6", "3", "4-22"]
    tab_pos["_geolocation"] = ["35-36-37-38", "35-36-37-38", "35-36-37-38", "35-36-37-38", "35-36-37-38", "2-3-4-5", "36-37-38-39", "93-94-95-96", "93-94-95-96", "93-94-95-96", "16-17-18-19", "17-18-19-20", "18-19-20-21", "6-7-8-9", "9-10-11-12"]
    tab_pos["source"] = ["5", "5", "5", "5", "5", "9", "6", "12", "12", "12", "21-120", "22-121", "23-111", "", ""]
    tab_pos["depart"] = ["6", "6", "6", "6", "6", "10", "7", "13", "13", "13", "22-121", "23-122", "24-112", "", ""]
    tab_pos["poste"] = ["7", "7", "7", "7", "7", "11", "8", "14", "14", "14", "23-122", "24-123", "25-113", "", ""]
    tab_pos["poste_type"] = ["8", "8", "8", "8", "8", "12", "9", "15", "15", "15", "24-123", "24-124", "26-114", "", ""]
    tab_pos["poste_image_url"] = ["9", "9", "9", "9", "9", "13", "10", "", "", "", "124", "125", "115", "", ""]
    tab_pos["depart_nbr"] = ["10", "10", "10", "10", "10", "14", "11", "", "", "", "125", "126", "116", "", ""]
    tab_pos["depart_code"] = ["11", "11", "11", "11", "11", "15", "12", "", "", "", "126", "127", "117", "", ""]
    tab_pos["existence"] = ["15", "15", "15", "15", "15", "19", "16", "", "", "", "130", "131", "121", "", ""]
    tab_pos["telephone"] = ["16", "16", "16", "16", "16", "20", "17", "83", "83", "83", "131-158-174-202-209", "132-159-175-203-210", "122-147-161-185-192", "45", "15-15"]
    tab_pos["quality"] = ["17", "17", "17", "17", "17", "21", "18", "11", "11", "11", "132-159-175", "133-160-176", "123-148-162", "", ""]
    tab_pos["lighting"] = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
    tab_pos["i1_input"] = ["42", "43", "42", "42", "42", "43", "43", "99", "99", "99", "149", "150", "138", "", ""]
    tab_pos["i1_output"] = ["43", "44", "43", "43", "43", "44", "44", "103", "103", "103", "153", "154", "142", "", ""]
    tab_pos["i2_input"] = ["44", "45", "44", "44", "44", "45", "45", "100", "100", "100", "150", "151", "139", "", ""]
    tab_pos["i2_output"] = ["45", "46", "45", "45", "45", "46", "46", "104", "104", "104", "154", "155", "143", "", ""]
    tab_pos["i3_input"] = ["46", "47", "46", "46", "46", "47", "47", "101", "101", "101", "151", "152", "140", "", ""]
    tab_pos["i3_output"] = ["47", "48", "47", "47", "47", "48", "48", "105", "105", "105", "155", "156", "144", "", ""]
    tab_pos["i4_input"] = ["48", "49", "48", "48", "48", "49", "49", "102", "102", "102", "152", "153", "141", "", ""]
    tab_pos["i4_output"] = ["49", "50", "49", "49", "49", "50", "50", "106", "106", "106", "156", "157", "145", "", ""]
    tab_pos["accesibilite"] = ["18", "18", "18", "18", "18", "22", "19", "", "", "", "160", "161", "149", "", ""]
    tab_pos["code_anomaly"] = ["41", "41", "41", "41", "41", "41", "42", "107", "107", "107", "148-172-191-206-212", "149-173-192-207-213", "137-159-176-189-195", "", "17-18"]
    tab_pos["matricule_co"] = ["", "", "", "", "", "8", "", "8", "8", "8", "7", "7", "7", "", ""]
    tab_pos["phone_number_co"] = ["16", "16", "16", "16", "16", "", "17", "", "", "", "", "", "", "", ""]
    tab_pos["numero_scelle"] = ["", "", "", "", "", "", "", "", "", "", "", "", "", "39", ""]
    tab_pos["action_coupure"] = ["", "", "", "", "", "", "", "6", "6", "6", "", "", "", "", ""]
    tab_pos["entreprise_collecteur"] = ["2", "2", "2", "2", "2", "6", "2", "9", "9", "9", "14-15", "14-15", "16-17", "14", ""]

    # --- BLOC 1 : Configuration des correspondances (Mappings) ---
    form_mapping = {
        "yde1":               {"region": "DCUY",          "action": "infos_generales-ACTION"},
        "DRC":                {"region": "DRC",           "action": "infos_generales-ACTION"},
        "DRC_C":              {"region": "DRC",           "action": "infos_generales-ACTION"},
        "drono_":             {"region": "DRONO",         "action": "Activite_Travail_a_faire"},
        "EXTREME-NORD":       {"region": "DRNEA",         "action": "ACTION"},
        "NORD":               {"region": "DRNEA",         "action": "ACTION"},
        "ADAMAOUA":           {"region": "DRNEA",         "action": "ACTION"},
        "dry":                {"region": "DCUY",          "action": "action"},
        "drd":                {"region": "DCUD",          "action": "action"},
        "T_DRD":              {"region": "T_DRD",         "action": "action"},
        "dre":                {"region": "DRE",           "action": "action"},
        "drono":              {"region": "DRONO",         "action": "action"},
        "Drsano":             {"region": "DRSANO",        "action": "action"},
        "T_DRSANO":           {"region": "T_DRSANO",      "action": "action"},
        "drsm":               {"region": "DRSM",          "action": "action"},
        "drsom":              {"region": "DRSOM",         "action": "action"},
        "drnea":              {"region": "DRNEA",         "action": "action"},
        "ratissage_drd_2025": {"region": "DRD_RATISSAGE", "action": "action"}
    }
    
    action_mapping = {
        "BRANCHEMENT":                    "BRANCHEMENT", 
        "Branchement":                    "BRANCHEMENT", 
        "COLLECTE":                       "INSPECTION", 
        "collecte":                       "INSPECTION", 
        "DISTRIBUTION":                   "DISTRIBUTION", 
        "Distribution":                   "DISTRIBUTION", 
        "INSPECTION":                     "INSPECTION", 
        "Inspection":                     "INSPECTION", 
        "Collecte":                       "INSPECTION", 
        "RECOUVREMENT":                   "RECOUVREMENT", 
        "recouvrement":                   "RECOUVREMENT", 
        "RECOUVREMENTBAD_DEBT":           "RECOUVREMENT", 
        "RECOUVREMENTBT":                 "RECOUVREMENT", 
        "RECOUVREMENTPNT":                "RECOUVREMENT", 
        "Releve":                         "RELEVE", 
        "RELEVE":                         "RELEVE", 
        "DETECTION":                      "DETECTION", 
        "Detection":                      "DETECTION", 
        "detection":                      "DETECTION", 
        "NORMALISATION_ILLEGAUX":         "NORMALISATION", 
        "ZERO VENDING":                   "ZEROVENDING", 
        "ZEROVENDING":                    "ZEROVENDING", 
        "NORMALISATION":                  "NORMALISATION", 
        "Depannage":                      "DEPANNAGE", 
        "New_Meter":                      "NEW METER", 
        "Reouvrement":                    "RECOUVREMENT", 
        "Recouvrement":                   "RECOUVREMENT", 
        "CNPC":                           "DETECTION", 
        "Normalisation/illegaux":         "NORMALISATION", 
        "Normalisation":                  "NORMALISATION", 
        "Normalisationillegaux":          "NORMALISATION", 
        "Inspection_Releve/Distribution": "INSPECTION", 
        "Inspection_ReleveDistribution":  "INSPECTION", 
        "Normalisation PNT":              "NORMALISATION", 
        "Recouvrement PNT":               "RECOUVREMENT", 
        "NormalisationPNT":               "NORMALISATION", 
        "coupure - remise":               "RECOUVREMENT", 
        "relève":                         "RELEVE", 
        "PNT":                            "RECOUVREMENT", 
        "coupureremise":                  "RECOUVREMENT", 
        "Visite des OCR":                 "VISITE DES OCR", 
        "Visite des Points de Livraisons": "VISITE DES POINTS DE LIVRAISONS", 
        "Visite des Postes":              "VISITE DES POSTES", 
        "Visite Ligne BT":                "VISITE LIGNE BT", 
        "Visite Ligne MT":                "VISITE LIGNE MT", 
        "ligne_mt":                       "VISITE LIGNE MT", 
        "ocr":                            "VISITE DES OCR", 
        "poste":                          "VISITE DES POSTES", 
        "RATISSAGE":                      "RATISSAGE"
    }
    
    valeur_return = False
    tab_csv = []
    tab_jpg = []
    #base_dir = os.path.dirname(os.path.abspath(__file__))
    #zip_path = os.path.join(base_dir, "traite", date_str, urls['form'], f"{urls['form']} {urls['heure']}h.zip")

    #zip_path = f"{BASE_DIR}/traite/{date_str}/{urls['form']}/{urls['form']} {urls['heure']}h.zip"
    zip_path = f"traite/{date_str}/{urls['form']}/{urls['form']} {urls['heure']}h.zip"
    #regex = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z.*?collect:[A-Za-z0-9]+,\d+,.*?', re.DOTALL)
    regex = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z.*?collect:[A-Za-z0-9]+,\d+,.*?', re.DOTALL | re.MULTILINE)
    # --- BLOC 2 : Traitement de l'archive ZIP ---
    
    if not os.path.exists(zip_path):
    #if 0:
        print(f"❌ Impossible d'ouvrir le fichier ZIP. Inexistant : {zip_path}")
        return [valeur_return, tab_csv, tab_jpg, 0, 0]
    else:
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    nom_fichier = file_info.filename
                    taille_octets = file_info.file_size
    
                    # Ignorer les dossiers vides
                    if taille_octets == 0 and nom_fichier.endswith('/'):
                        continue
                    
                    # --- CAS A : Analyse du fichier CSV ---
                    if nom_fichier.lower().endswith('.csv'):
                        texte = zip_ref.read(nom_fichier).decode('utf-8', errors='ignore')
                        #if texte:
                        #    directory = f"CSV corrige/{date_str}/{urls['form']}/"
                        #    os.makedirs(directory, exist_ok=True)
                            
                        #nom_csv_corrige = f"{directory}{urls['form']} {urls['heure']}h.csv"
                        
                        lignes_brutes = texte.strip().split('\n')
                        #entetes = []
                        if lignes_brutes:
                            #entetes = lignes_brutes[0].strip().split(',')
                        
                        #with open(nom_csv_corrige, 'w', encoding='utf-8', newline='') as c_output:
                        #    c_output.write(';'.join(entetes) + "\r\n")
                            
                            matches = regex.findall(texte)
                            
                            for bloc in matches:
                                #reader = csv.reader([bloc], delimiter=',', quotechar='"')
                                #b_bloc = next(reader)
                                
                                #b_bloc_nettoye = [s(x) for x in b_bloc]
                                #c_output.write(';'.join(b_bloc_nettoye) + "\r\n")
                                
                                # Reparsing pour les extractions géospatiales
                                reader = csv.reader([bloc], delimiter=',', quotechar='"')
                                b_bloc = next(reader)
                                
                                lat, lng, alt, acc = 0, 0, 0, 0
                                geo_val = pos_valeur_matrix("_geolocation", urls["form"], tab_pos, b_bloc, 0)
                                
                                if geo_val:
                                    geo_parts = geo_val.split('|')
                                    if len(geo_parts) > 3:
                                        lat, lng, alt, acc = geo_parts[0], geo_parts[1], geo_parts[2], geo_parts[3]
                                        
                                date_de_soumission = pos_valeur_matrix("date", urls["form"], tab_pos, b_bloc, 0) or ''
                                
                                # --- BLOC 3 : Préparation du dictionnaire de données ---
                                action_brute = pos_valeur_matrix("action", urls["form"], tab_pos, b_bloc, 0)
                                action_mappee = action_mapping.get(action_brute, action_brute)
                                
                                try:
                                    banoc_code = json_geohash_encode(float(lat), float(lng), 8) if (lat and lng) else ''
                                except ValueError:
                                    banoc_code = ''
                                
                                ligne_dictionnaire = {
                                    'SubmissionDate':                     date_de_soumission,
                                    'entreprise_collecteur':               pos_valeur_matrix("entreprise_collecteur", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'collecteur':                          pos_valeur_matrix("Collecteur", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'matricule_co':                        pos_valeur_matrix("matricule_co", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'source':                              pos_valeur_matrix("source", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'depart':                              pos_valeur_matrix("depart", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'poste':                               pos_valeur_matrix("poste", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'Type_de_poste':                       pos_valeur_matrix("poste_type", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'photo_poste':                         pos_valeur_matrix("poste_image_url", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'nbr_depart':                          pos_valeur_matrix("depart_nbr", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'code_depart':                         pos_valeur_matrix("depart_code", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'Eclairage':                           "Eclairage",
                                    'lumiere':                             "lumiere",
                                    'photo_lanterne':                      "photo_lanterne",
                                    'existence':                           pos_valeur_matrix("existence", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'telephone':                           pos_valeur_matrix("telephone", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'qualite':                             pos_valeur_matrix("quality", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'accesibilite':                        pos_valeur_matrix("accesibilite", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'pl_codes_barcodes':                   "codes_barcodes",
                                    'pl_code_bare':                        pos_valeur_matrix("pl/info_pl/code_bare", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'pl_raison':                           pos_valeur_matrix("pl/info_pl/raison", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'pl_status':                           pos_valeur_matrix("pl/info_pl/status", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'pl_type_compteur':                    pos_valeur_matrix("pl/info_pl/type_compteur", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'pl_nbr_fil':                          pos_valeur_matrix("pl/info_pl/nbr_fil", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'pl_batiment':                         pos_valeur_matrix("pl/info_pl/batiment", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'pl_type_immeuble':                    "pl_type_immeuble",
                                    'pl_mode_alimentation':                "mode_alimentation",
                                    'pl_section_cable':                    "section_cable",
                                    'pl_activite':                         pos_valeur_matrix("pl/info_pl/activite", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'pl_serial_numbers_list':              "serial_numbers_list",
                                    'pl_serial_number':                    pos_valeur_matrix("pl/info_pl/serial_number", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'contrat':                             pos_valeur_matrix("pl/info_pl/contrat", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'pl_index':                            pos_valeur_matrix("pl/info_pl/index", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'pl_photo_index':                      pos_valeur_matrix("pl/info_pl/photo_index", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'coordonnee_Latitude':                 lat,
                                    'coordonnee_Longitude':                lng,
                                    'coordonnee_Altitude':                 alt,
                                    'coordonnee_Accuracy':                 acc,
                                    'action':                              action_mappee,
                                    'photo':                               pos_valeur_matrix("pl/info_pl/image_url", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'code_anomaly':                        pos_valeur_matrix("code_anomaly", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'I1_entre':                            pos_valeur_matrix("i1_input", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'I2_entre':                            pos_valeur_matrix("i2_input", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'I3_entre':                            pos_valeur_matrix("i3_input", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'I4_entre':                            pos_valeur_matrix("i4_input", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'I1_sortie':                           pos_valeur_matrix("i1_output", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'I2_sortie':                           pos_valeur_matrix("i2_output", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'I3_sortie':                           pos_valeur_matrix("i3_output", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'I4_sortie':                           pos_valeur_matrix("i4_output", urls["form"], tab_pos, b_bloc, 1) or '',
                                    'id':                                  pos_valeur_matrix("id", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'uuid':                                "uuid",
                                    'date_jour':                           pos_valeur_matrix("id", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'note':                                "note",
                                    'instanceID':                          pos_valeur_matrix("id", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'cle':                                 pos_valeur_matrix("id", urls["form"], tab_pos, b_bloc, 0) or '',
                                    'SubmitterID':                         "SubmitterID",
                                    'SubmitterName':                       "SubmitterName",
                                    'AttachmentsPresent':                  "AttachmentsPresent",
                                    'AttachmentsExpected':                 "AttachmentsExpected",
                                    'Status':                              "Status",
                                    'ReviewState':                         "ReviewState",
                                    'DeviceID':                            "DeviceID",
                                    'Edits':                               "Edits",
                                    'FormVersion':                         "FormVersion",
                                    'ajout_telephone':                     "telephone",
                                    'point':                               f"POINT({lng} {lat})",
                                    'agence_liee':                         '',
                                    'banoc_code':                          banoc_code,
                                    'date_submission':                     date_de_soumission[0:10] if date_de_soumission else '',
                                    'form':                                urls.get("form", ""),
                                    'ref_formulaire':                      form_mapping.get(urls["form"], {}).get("region", ""),
                                    'date_filtre_telechargement':          date_str,
                                    'heure_date_filtre_telechargement':    urls.get("heure", ""),
                                    'bloc':                                '',
                                    'mra_contrat':                         '',
                                    'mra_compteur':                        '',
                                    'mra_pl':                              ''
                                    }
                                tab_csv.append(ligne_dictionnaire)
                                # --- BLOC 4 : Traitement des fichiers Images JPG ---
                    elif nom_fichier.lower().endswith('.jpg'):
                        nom_nettoye = nom_fichier.replace("media/", "")
                        donnees_jpg = {
                            'form':   urls.get("form", ""),
                            'date':   date_str,
                            'heure':  urls.get("heure", ""),
                            'nom':    nom_nettoye,
                            'taille': taille_octets
                        }
                        tab_jpg.append(donnees_jpg)
                        valeur_return = True
                        #charger(valeur_return, date_str, urls['heure'], urls['form'], connection)
        except zipfile.BadZipFile:
            print(f"❌ Impossible d'ouvrir le fichier ZIP corrompu. {zip_path}")
            valeur_return = False
        except Exception as e:
            print(f"❌ Erreur critique globale dans traiter_odk : {e}")
            valeur_return = False
        
        return [valeur_return, tab_csv, tab_jpg, len(tab_csv), len(tab_jpg)]

def extraire(date_str: str, urls: dict) -> str:
    """
    Vérifie l'existence du fichier ZIP, l'ouvre, extrait le fichier CSV interne,
    et le renomme selon la nomenclature attendue.
    """
    message = ""
    # En Python, os.getcwd() ou le chemin relatif simule le dossier racine __DIR__
    zip_file = f"traite/{date_str}/{urls['form']}/{urls['form']} {urls['heure']}h.zip"
    
    # 1. if (!file_exists($zipFile))
    if not os.path.exists(zip_file):
        message += f"Erreur avec : non existant {zip_file}--- "
        print(message)
        return message

    try:
        # Note: Si fixZipHeader(zip_file) est indispensable, vous devez la traduire.
        # Souvent, le module zipfile de Python gère mieux les entêtes altérés que PHP.
        # fixZipHeader(zip_file) 
        
        # 2. Ouverture de l'archive (équivalent de $zip->open)
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            message += f"Test Dézippé OK : {zip_file}<br>"
            """
            extract_file = f"{urls['form']}.csv" # Nom du fichier à l'intérieur du ZIP
            extract_path = f"CSV/{date_str}/{urls['form']}/"
            
            # Création du dossier de destination s'il n'existe pas
            os.makedirs(extract_path, exist_ok=True)
            
            # Extraction du fichier spécifique (équivalent de $zip->extractTo)
            # En Python, on vérifie d'abord si le fichier CSV existe bien dans le ZIP
            if extract_file in zip_ref.namelist():
                zip_ref.extract(extract_file, path=extract_path)
                
                chemin_extrait = os.path.join(extract_path, extract_file)
                chemin_final = os.path.join(extract_path, f"{urls['form']} {urls['heure']}h.csv")
                
                # if (file_exists($extractPath . $extractFile)) -> rename(...)
                if os.path.exists(chemin_extrait):
                    # Si le fichier de destination existe déjà, on le supprime pour pouvoir renommer sans erreur
                    if os.path.exists(chemin_final):
                        os.remove(chemin_final)
                    os.rename(chemin_extrait, chemin_final)
                    message += f"Test Dézippé OK : {zip_file}<br>"
                else:
                    message += f"Fichier Vide Test Dézippé OK : {zip_file}<br>"
            else:
                message += f"Fichier Vide Test Dézippé OK : {zip_file}<br>"
            """   
    except zipfile.BadZipFile:
        # Équivalent des cas ZipArchive::ER_NOZIP et ER_INCONS
        description = ""
        if os.path.exists(zip_file):
            with open(zip_file, "rb") as f:
                description = f.read(10).decode('utf-8', errors='ignore')
        message += f"Erreur avec : {zip_file} {description} --- Le fichier n'est pas une archive ZIP ou est incohérent."
        
    except Exception as e:
        # Gestion des autres erreurs génériques (mémoire, lecture, etc.)
        message += f"Erreur avec : {zip_file} --- {str(e)}"
        
    print(message)
    return message

async def obtenir_token_odk():
        # Configuration ODK (extraite de votre PHP)
    ODK_USER = "memarice.nyale@eneo.cm"
    ODK_PASSWORD = "Memarice.237"
    ODK_URL_SESSION = "https://position.cm"

    """Version sécurisée avec l'IP de secours comme votre PHP d'origine"""
    donnees_auth = {
        "email": ODK_USER,
        "password": ODK_PASSWORD
    }
    
    # 1. On remplace l'URL par l'IP directe pour contourner le bogue getaddrinfo
    url_secours = "https://207.180.230.194/v1/sessions"

    # 2. Le header doit obligatoirement préciser l'hôte d'origine pour que le serveur ODK accepte la connexion
    headers_speciaux = {
        "Host": "odk.position.cm",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # verify=False désactive la vérification stricte SSL puisque nous passons par une IP directe
    async with httpx.AsyncClient(verify=False) as client:
        try:
            print("🌐 Tentative de connexion directe à l'IP du serveur ODK...")
            reponse = await client.post(url_secours, json=donnees_auth, headers=headers_speciaux)
            
            if reponse.status_code == 200:
                resultat = reponse.json()
                return resultat.get("token")
            else:
                print(f"❌ Échec ODK. Code HTTP: {reponse.status_code}")
                print(f"Détails : {reponse.text}")
                return None
        except Exception as e:
            print(f"❌ Erreur critique de connexion ODK : {e}")
            return None
"""
def lien(date_str: str) -> list:
    tab = []
    
    # Configuration des formulaires : ["nom_du_formulaire", "id_du_projet"]
    config_formulaires = [
        ["yde1", "2"], ["drd", "2"], ["dre", "2"], ["drono_", "2"],
        ["Drsano", "2"], ["drsm", "2"], ["drsom", "2"], ["EXTREME-NORD", "2"],
        ["NORD", "2"], ["DRC", "2"], ["DRC_C", "2"], ["ADAMAOUA", "2"],
        ["drnea", "2"], ["drono", "2"], ["dry", "2"],
        ["ratissage_drd_2025", "10"],
        ["T_DRD", "13"], ["T_DRSANO", "13"]
    ]
    
    # Boucle de 00h à 23h
    for i in range(24):
        # Formate l'heure sur 2 chiffres (ex: 8 devient "08")
        heure = f"{i:02d}"
        
        for form, project_id in config_formulaires:
            # Construction propre de l'URL ODK
            url = (
                f"https://odk.position.cm/v1/projects/{project_id}/forms/{form}/submissions.csv.zip"
                f"?$filter=__system/submissionDate ge {date_str}T{heure}:00:00.000+01:00 "
                f"and __system/submissionDate le {date_str}T{heure}:59:59.999+01:00"
                f"&splitSelectMultiples=false&groupPaths=true&deletedFields=false"
            )
            
            tab.append({
                "form": form,
                "heure": heure,
                "url": url
            })
            
    return tab
"""

def lien(date_str: str) -> list:
    tab = []
    
    config_formulaires = [
        ["yde1", "2"], ["drd", "2"], ["dre", "2"], ["drono_", "2"],
        ["Drsano", "2"], ["drsm", "2"], ["drsom", "2"], ["EXTREME-NORD", "2"],
        ["NORD", "2"], ["DRC", "2"], ["DRC_C", "2"], ["ADAMAOUA", "2"],
        ["drnea", "2"], ["drono", "2"], ["dry", "2"],
        ["ratissage_drd_2025", "10"],
        ["T_DRD", "13"], ["T_DRSANO", "13"]
    ]
    
    for i in range(24):
        heure = f"{i:02d}"
        
        for form, project_id in config_formulaires:
            # 1. Base de l'URL (sans les paramètres de filtre)
            base_url = f"https://odk.position.cm/v1/projects/{project_id}/forms/{form}/submissions.csv.zip"
            
            # 2. Définition des paramètres sous forme de dictionnaire Python
            # Le filtre ODK s'écrit ici avec des caractères normaux
            parametres = {
                "$filter": f"__system/submissionDate ge {date_str}T{heure}:00:00.000+01:00 and __system/submissionDate le {date_str}T{heure}:59:59.999+01:00",
                "splitSelectMultiples": "false",
                "groupPaths": "true",
                "deletedFields": "false"
            }
            
            # 3. Encodage automatique des paramètres (Équivalent strict de votre chaîne PHP)
            # safe=" " empêche d'encoder les espaces en '+' (comme requis par l'OData d'ODK qui préfère %20 ou des vrais espaces selon les cas)
            url_encodee = base_url + "?" + urllib.parse.urlencode(parametres, safe="$")
            
            tab.append({
                "form": form,
                "heure": heure,
                "url": url_encodee
            })
            
    return tab

"""
async def telecharger_un_fichier(client: httpx.AsyncClient, url_info: dict, date_str: str, headers: dict):
    #Télécharge un seul fichier ZIP depuis l'API ODK et le sauvegarde sur le disque
    # 1. Création dynamique du dossier de destination (comme mkdir 0777 en PHP)
    dossier = f"traite/{date_str}/{url_info['form']}"
    os.makedirs(dossier, exist_ok=True)
    
    chemin_complet_zip = f"{dossier}/{url_info['form']} {url_info['heure']}h.zip"
  
    try:
        tester = extraire(date_str, url_info)
        if "Test Dézippé OK" in tester:
            print(f"📦 Fichier deja téléchargé : {chemin_complet_zip}")
            return {"statut": "ok", "chemin": chemin_complet_zip, "info": url_info}
        else:
            # Envoi de la requête de téléchargement
            reponse = await client.get(url_info["url"], headers=headers, timeout=300.0)
            
            if reponse.status_code == 200:
                # Sauvegarde du fichier en mode binaire ("wb")
                with open(chemin_complet_zip, "wb") as f:
                    f.write(reponse.content)
                # Message en temps réel destiné à Vue.js
                print(f"📦 Fichier téléchargé : {chemin_complet_zip}")
                return {"statut": "ok", "chemin": chemin_complet_zip, "info": url_info}
            else:
                print(f"❌ Erreur ODK ({reponse.status_code}) sur le formulaire : {url_info['form']} reponse ({reponse})")
                return {"statut": "erreur", "message": f"Code HTTP {reponse.status_code}", "info": url_info}
            
    except Exception as e:
        print(f"❌ Erreur réseau sur le formulaire {url_info['form']} : {e}")
        return {"statut": "erreur", "message": str(e), "info": url_info}

async def telecharger_fichiers(date_str: str, real_urls: list, connexion_bdd):
#async def telecharger_fichiers(date_str: str, real_urls: list, headers: dict, connexion_bdd):
    #Équivalent moderne de votre boucle de traitement multi-flux curl_multi en PHP.
    #Télécharge par paquets asynchrones (sécurité anti-surcharge).

    # On demande à asyncio de gérer l'attente de la fonction asynchrone
    token = await obtenir_token_odk()    
    # 3. Construction des headers équivalents
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}" if token else ""
    }

    total = len(real_urls)
    if total == 0:
        return
        
    print(f"🚀 Début du téléchargement asynchrone de {total} fichiers...")

    # Limite de connexions simultanées (comme votre $maxConn = 5 en PHP)
    semaphore = asyncio.Semaphore(2)
    
    # httpx.AsyncClient gère automatiquement le pool de connexions
    async with httpx.AsyncClient(verify=False) as client:
        
        for index, url_info in enumerate(real_urls):
            # Cette fonction protège le serveur en limitant à 5 téléchargements simultanés
            async with semaphore:
                # Calcul de la progression pour Vue.js (entre 45% et 90% du traitement global)
                progression_actuelle = int((index / total) * 45) + 45
                
                # Notification en temps réel à l'écran de l'utilisateur
                yield f"data: {json.dumps({'statut': f'Téléchargement de {url_info['form']} ({url_info['heure']}h) [Fichier {index+1}/{total}]...', 'progression': progression_actuelle})}\n\n"
                
                #result = await traiter_fichier(date_str, url_info, connexion_bdd)
                #result = await asyncio.to_thread(traiter_fichier, date_str, url_info, connexion_bdd)
        

                #print(result[0])
                #if result[0]:
                #    charger(result, date_str, url_info['heure'], url_info['form'], connexion_bdd)
                #else:
                #    print(result)
                #    print(date_str)
                #    print(url_info['heure'])
                #    print(url_info['form'])
                #    print(url_info)
                #    print(connexion_bdd)
                
                # Exécution du téléchargement
                resultat = await telecharger_un_fichier(client, url_info, date_str, headers)
                #await traiter_fichier(date, url_info, connexion_bdd)
                #exit()
                # Si le téléchargement a réussi, on enchaîne avec le traitement (Lecture ZIP/CSV)
                if resultat["statut"] == "ok":
                    # 1. Appel de la fonction de vérification et d'extraction ZIP
                    tester = extraire(date_str, url_info)
                    #print(tester)
                    # 2. Utilisation du mot-clé 'in' en Python pour simplifier la double condition 'or'
                    if "Test Dézippé OK" in tester:
                        #print("")
                        # On enchaîne avec le traitement en base de données uniquement si le test est validé
                        #await traiter_fichier_telecharge(resultat["chemin"], connexion_bdd)
                        result = await traiter_fichier(date_str, url_info, connexion_bdd)
                        charger(result, date_str, url_info['heure'], url_info['form'], connexion_bdd)
                        #print(result)
                    else:
                        print(f"⚠️ Fichier ignoré pour le traitement BDD car le zip est invalide.")
                
 

# =========================================================================
# 🔄 1. FONCTION PRINCIPALE : BOUCLE DE NAVIGATION ET DE PROGRESSION
# =========================================================================
async def telecharger_fichiers(date_str: str, real_urls: list, connexion_bdd):
    #Équivalent moderne de votre boucle de traitement multi-flux curl_multi en PHP.
    Té#lécharge par paquets asynchrones avec suivi de progression en temps réel.
    
    token = await obtenir_token_odk()    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}" if token else ""
    }

    total = len(real_urls)
    if total == 0:
        return
        
    print(f"🚀 Début du téléchargement asynchrone de {total} fichiers...")

    # Limite à 2 téléchargements simultanés maximum pour protéger la bande passante et le serveur
    semaphore = asyncio.Semaphore(2)
    
    async with httpx.AsyncClient(verify=False) as client:
        for index, url_info in enumerate(real_urls):
            async with semaphore:
                # Calcul de la progression pour Vue.js (entre 45% et 95%)
                progression_actuelle = int((index / total) * 50) + 45
                
                # Notification en temps réel à l'écran de l'utilisateur
                yield f"data: {json.dumps({'statut': f'Téléchargement de {url_info['form']} ({url_info['heure']}h) [Fichier {index+1}/{total}]...', 'progression': progression_actuelle})}\n\n"
                
                # Exécution du téléchargement par morceaux (Streaming)
                resultat = await telecharger_un_fichier(client, url_info, date_str, headers)
                
                # Si le téléchargement a réussi, on procède à l'extraction et l'insertion SQL
                if resultat["statut"] == "ok":
                    tester = extraire(date_str, url_info)
                    
                    if "Test Dézippé OK" in tester:
                        # On enchaîne avec le traitement en base de données
                        result = await traiter_fichier(date_str, url_info, connexion_bdd)
                        charger(result, date_str, url_info['heure'], url_info['form'], connexion_bdd)
                    else:
                        print(f"⚠️ Fichier {url_info['form']} {url_info['heure']}h ignoré car le zip est invalide ou corrompu.")


# =========================================================================
# 📥 2. SOUS-FONCTION : TÉLÉCHARGEMENT ASYNCHRONE PAR MORCEAUX (STREAMING)
# =========================================================================
async def telecharger_un_fichier(client: httpx.AsyncClient, url_info: dict, date_str: str, headers: dict):
    #Télécharge un seul fichier ZIP depuis l'API ODK en Streaming et le sauvegarde par blocs
    dossier = f"traite/{date_str}/{url_info['form']}"
    os.makedirs(dossier, exist_ok=True)
    
    chemin_complet_zip = f"{dossier}/{url_info['form']} {url_info['heure']}h.zip"
  
    try:
        # Vérification de sécurité avant téléchargement (évite de re-télécharger si déjà OK)
        if os.path.exists(chemin_complet_zip):
            tester = extraire(date_str, url_info)
            if "Test Dézippé OK" in tester:
                print(f"📦 Fichier déjà présent et valide : {chemin_complet_zip}")
                return {"statut": "ok", "chemin": chemin_complet_zip, "info": url_info}

        # 🔥 CORRECTIF CRITIQUE POUR LES GROS FICHIERS : Utilisation de client.stream
        # timeout=600.0 (10 minutes) laisse le temps aux très gros fichiers de finir sans coupure
        async with client.stream("GET", url_info["url"], headers=headers, timeout=600.0) as reponse:
            
            if reponse.status_code == 200:
                # Ouverture du fichier sur le disque dur immédiatement
                with open(chemin_complet_zip, "wb") as f:
                    # On lit le flux par blocs de 16 Ko au fur et à mesure de l'arrivée réseau
                    async for chunk in reponse.aiter_bytes(chunk_size=16384):
                        f.write(chunk)
                        f.flush()  # Force l'écriture Windows pour voir le fichier grossir à l'écran
                        
                        # Permet aux autres tâches de respirer pendant l'écriture du gros fichier
                        await asyncio.sleep(0) 

                print(f"📦 Fichier téléchargé avec succès : {chemin_complet_zip}")
                return {"statut": "ok", "chemin": chemin_complet_zip, "info": url_info}
            else:
                print(f"❌ Erreur ODK ({reponse.status_code}) sur le formulaire : {url_info['form']}")
                return {"statut": "erreur", "message": f"Code HTTP {reponse.status_code}", "info": url_info}
            
    except Exception as e:
        print(f"❌ Erreur réseau / écriture sur le formulaire {url_info['form']} : {e}")
        return {"statut": "erreur", "message": str(e), "info": url_info}











async def telecharger_fichiers(date_str: str, real_urls: list, connexion_bdd):
    token = await obtenir_token_odk()    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}" if token else ""
    }

    total = len(real_urls)
    if total == 0:
        return
        
    print(f"🚀 Début du téléchargement asynchrone de {total} fichiers...")
    semaphore = asyncio.Semaphore(2)
    
    async with httpx.AsyncClient(verify=False) as client:
        for index, url_info in enumerate(real_urls):
            async with semaphore:
                progression_base = int((index / total) * 50) + 45
                
                # 🛠️ CRÉATION DE LA QUEUE DE SUIVI DE TAILLE
                queue_taille = asyncio.Queue()
                
                # On lance le téléchargement en tâche de fond pour pouvoir lire la queue en simultané
                tache_telechargement = asyncio.create_task(
                    telecharger_un_fichier(client, url_info, date_str, headers, queue_taille)
                )
                
                # Tant que le fichier télécharge, on lit la taille et on yield vers Vue.js
                while not tache_telechargement.done() or not queue_taille.empty():
                    try:
                        # On attend un message de taille pendant max 0.2 secondes pour ne pas bloquer
                        taille_texte = await asyncio.wait_for(queue_taille.get(), timeout=0.2)
                        yield f"data: {json.dumps({'statut': f'📥 Téléchargement de {url_info['form']} ({url_info['heure']}h) : {taille_texte}', 'progression': progression_base})}\n\n"
                    except asyncio.TimeoutError:
                        pass
                
                # Récupération du résultat final une fois la tâche terminée
                resultat = await tache_telechargement
                
                if resultat["statut"] == "ok":
                    tester = extraire(date_str, url_info)
                    if "Test Dézippé OK" in tester:
                        result = await traiter_fichier(date_str, url_info, connexion_bdd)
                        charger(result, date_str, url_info['heure'], url_info['form'], connexion_bdd)

"""

async def telecharger_un_fichier(client: httpx.AsyncClient, url_info: dict, date_str: str, headers: dict, queue_progression: asyncio.Queue = None):
    """Télécharge un seul fichier ZIP depuis l'API ODK en Streaming et calcule la taille en direct"""
    dossier = f"traite/{date_str}/{url_info['form']}"
    os.makedirs(dossier, exist_ok=True)
    
    chemin_complet_zip = f"{dossier}/{url_info['form']} {url_info['heure']}h.zip"
    try: 
        if os.path.exists(chemin_complet_zip):
            print("ok " + chemin_complet_zip)
            tester = extraire(date_str, url_info)
            if "Test Dézippé OK" in tester:
                return {"statut": "ok", "chemin": chemin_complet_zip, "info": url_info}
        
        async with client.stream("GET", url_info["url"], headers=headers, timeout=600.0) as reponse:
            #return {"statut": "ok", "chemin": chemin_complet_zip, "info": url_info}
            if reponse.status_code == 200:
                # 📊 RÉCUPÉRATION DE LA TAILLE TOTALE DU FICHIER
                taille_totale = int(reponse.headers.get("Content-Length", 0))
                taille_totale_mo = round(taille_totale / (1024 * 1024), 1) if taille_totale else 0
                
                octets_telecharges = 0
                dernier_envoi = 0

                with open(chemin_complet_zip, "wb") as f:
                    async_chunks = reponse.aiter_bytes(chunk_size=16384)
                    async for chunk in async_chunks:
                        f.write(chunk)
                        f.flush()
                        
                        # 📈 CALCUL DU TRANSFERT EN TEMPS RÉEL
                        octets_telecharges += len(chunk)
                        mo_actuels = round(octets_telecharges / (1024 * 1024), 1)
                        
                        # Évite de surcharger le réseau : on envoie l'info tous les 0.5 Mo d'avancement
                        if queue_progression and (mo_actuels - dernier_envoi >= 0.5 or mo_actuels == taille_totale_mo):
                            dernier_envoi = mo_actuels
                            texte_taille = f"{mo_actuels} Mo / {taille_totale_mo} Mo" if taille_totale_mo else f"{mo_actuels} Mo"
                            # On transmet l'information de taille au générateur parent
                            await queue_progression.put(texte_taille)

                        await asyncio.sleep(0)

                return {"statut": "ok", "chemin": chemin_complet_zip, "info": url_info}
            else:
                return {"statut": "erreur", "message": f"Code HTTP {reponse.status_code}", "info": url_info}
          
    except Exception as e:
        return {"statut": "erreur", "message": str(e), "info": url_info}
    
async def telecharger_fichiers(date_str: str, real_urls: list, connexion_bdd, connexion_bdd_master):
    """
    Télécharge et traite les fichiers en PARALLÈLE par lots de 5.
    Correction absolue de l'erreur TypeError pour Python 3.14+.
    """
    
    total = len(real_urls)
    if total == 0:
        # 1. Calcul de la date du jour précédent
        date_initiale = datetime.strptime(date_str, "%Y-%m-%d")
        date_prochaine_obj = date_initiale - timedelta(days=1)
        dateprochaine = date_prochaine_obj.strftime("%Y-%m-%d")

        print(f"🎉 Tous les fichiers du {date_str} ont été traités.")
        print(f"🔄 Ordre de redirection envoyé vers la journée précédente : {dateprochaine}")
            
        # 2. On envoie un signal JSON spécifique que Vue.js va intercepter
        yield f"data: {json.dumps({'action': 'redirection', 'prochaine_date': dateprochaine, 'statut': f'🎉 Tous les fichiers du {date_str} sont OK. Passage automatique au {dateprochaine}...'})}\n\n"
        
        # 3. On quitte la fonction proprement sans casser le serveur (.exe)
        return
        
    print(f"🚀 Lancement du téléchargement parallèle de {total} fichiers (Lots de 5)...")
    
    token = "" #await obtenir_token_odk()    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}" if token else ""
    }
    
    semaphore = asyncio.Semaphore(5)
    queue_messages = asyncio.Queue()

    # --- SOUS-FONCTION DE SÉCURITÉ POUR CHAQUE FICHIER ---
    async def gerer_un_telechargement_et_traitement(index, url_info, client):
        
        async with semaphore:
            progression_base = int((index / total) * 50) + 45
            queue_taille = asyncio.Queue()
            
            # 1. Lancement du téléchargement asynchrone par morceaux
            tache = asyncio.create_task(
                telecharger_un_fichier(client, url_info, date_str, headers, queue_taille)
            )
            
            # Suivi visuel des Mo à l'écran
            while not tache.done() or not queue_taille.empty():
                try:
                    taille_texte = await asyncio.wait_for(queue_taille.get(), timeout=0.05)
                    await queue_messages.put({
                        'statut': f"📥 Téléchargement de {url_info['form']} ({url_info['heure']}h) : {taille_texte}",
                        'progression': progression_base
                    })
                except asyncio.TimeoutError:
                    pass
            
            resultat = await tache
            
            # 2. Une fois le téléchargement terminé et le fichier fermé sur le disque :
            if resultat["statut"] == "ok":
                # Petite pause de sécurité pour laisser Windows libérer le fichier ZIP
                await asyncio.sleep(0.1)
                
                tester = extraire(date_str, url_info)
                if "Test Dézippé OK" in tester:
                    # Traitement BDD
                    result = await traiter_fichier(date_str, url_info)
                    #result = [1, [], [], 0, 0]
                    charger(result, date_str, url_info['heure'], url_info['form'], connexion_bdd, connexion_bdd_master)
                    await queue_messages.put({
                        'statut': f"✅ Insertion réussie : {url_info['form']} ({url_info['heure']}h)",
                        'progression': progression_base
                    })
                else:
                    await queue_messages.put({
                        'statut': f"⚠️ Échec vérification archive : {url_info['form']} ({url_info['heure']}h)",
                        'progression': progression_base
                    })
            
    # 🔥 CORRECTIF TYPING PYTHON 3.14 : Encapsulation dans une coroutine propre
    async def executer_groupe_parallele():
        async with httpx.AsyncClient(verify=False) as client:
            taches = [
                gerer_un_telechargement_et_traitement(i, url, client) 
                for i, url in enumerate(real_urls)
            ]
            # gather est attendu directement avec 'await', sans create_task autour
            await asyncio.gather(*taches)
    
    # Lancement de la coroutine globale
    execution_globale = asyncio.create_task(executer_groupe_parallele())
    
    # Distribution continue des flux d'informations vers Vue.js
    while not execution_globale.done() or not queue_messages.empty():
        try:
            msg = await asyncio.wait_for(queue_messages.get(), timeout=0.1)
            yield f"data: {json.dumps(msg)}\n\n"
        except asyncio.TimeoutError:
            pass
            
    await execution_globale
    



# 1. On crée une fonction intermédiaire asynchrone pour encapsuler le test
async def lancer_le_test():
    # Définition de vos variables de test
    date = "2026-06-23"
    urls = {'form': 'yde1', 'heure': '00', 'url': 'tet'}
    connexion_simulation = "tes"
    
    print("🚀 Initialisation de l'environnement de test...")
    
    # 2. Utilisation obligatoire de 'await' pour exécuter la fonction asynchrone
    resultat = await traiter_fichier(date, urls, connexion_simulation)
    
    # Affichage du résultat retourné (votre liste)
    print(f"📊 Résultat retourné : {resultat}")

# 3. Point d'entrée obligatoire pour démarrer le moteur asynchrone de Python
if __name__ == "__main__":
    print(uuid)
    asyncio.run(lancer_le_test())
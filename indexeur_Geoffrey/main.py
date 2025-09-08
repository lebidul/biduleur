import os
import fitz  # PyMuPDF
import shutil
from datetime import datetime
import time
import re

from DecoupePages import decoupe_avant_2000, decoupe_apres_2000, decoupe_en_3, decoupe_horizontal
from Tesseract import traiter_images_decoupees_via_tesseract
from Misatral import traiter_images_decoupees_via_mistral

# demande à l'utilisateur de choisir l'outil OCR
# 1 pour Mistral, 2 pour Tesseract
def choix_de_ORC():
    print("\n=== Choix de l'OCR ===")
    print("1 : Utiliser Mistral (OCR rapide, nécessite une configuration spécifique)")
    print("2 : Utiliser Tesseract (OCR classique, nécessite Tesseract installé)")
    choix = input("Veuillez entrer votre choix (1 pour Mistral, 2 pour Tesseract) : ")
    if choix == "1":
        print("Vous avez choisi Mistral pour l'OCR.")
        return 1
    elif choix == "2":
        print("Vous avez choisi Tesseract pour l'OCR.")
        return 2
    else:
        print("Choix invalide, veuillez entrer 1 ou 2.")
        return choix_de_ORC()

# Convertit chaque page PDF en images
def convertir_pdf_en_images(chemin_pdf, dossier_sortie):
    doc = fitz.open(chemin_pdf)
    noms_images = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=200)
        nom_image = f"{os.path.splitext(os.path.basename(chemin_pdf))[0]}_page{i+1}.png"
        chemin_image = os.path.join(dossier_sortie, nom_image)
        pix.save(chemin_image)
        noms_images.append(chemin_image)
    doc.close()
    return noms_images

# Traite un seul PDF et place les fichiers temporaires dans un dossier de sortie dédié
def traiter_un_pdf(chemin_pdf, dossier_sortie_temporaire):
    """
    Traite un seul fichier PDF : le convertit en images et les découpe.
    Retourne le chemin du dossier temporaire créé pour ce PDF.
    """
    print(f"📄 Traitement du fichier : {chemin_pdf}")

    # Crée un sous-dossier "tempo" dans le dossier de sortie spécifié
    dossier_images_temporaire = os.path.join(dossier_sortie_temporaire, "tempo")
    os.makedirs(dossier_images_temporaire, exist_ok=True)

    # Conversion PDF → images
    images_pages = convertir_pdf_en_images(chemin_pdf, dossier_images_temporaire)
    
    # Découpe les images générées
    decoupe_selon_date(images_pages)
    
    return dossier_images_temporaire




def decoupe_selon_date(images_pages):
    for image_path in images_pages:
        fichier = os.path.basename(image_path)
        try:
            # Récupère la date au format YYYY-MM
            date_str = fichier[:7]
            annee = int(fichier[:4])
            mois = int(fichier[5:7])
            date_pdf = datetime(annee, mois, 1)

            # Vérifie si c'est un "_page3.png"
            est_page3 = re.search(r'_page3\.png$', fichier) is not None

            # Vérifie si c'est une première page
            est_page1 = re.search(r'_page1\.png$', fichier) is not None

            # Vérifie la règle spéciale "Bidul après mars 2019"
            est_bidul_apres_2019_03 = ("Bidul" in fichier) and (date_pdf >= datetime(2019, 3, 1))

            # Vérifie la règle spéciale "Bidul numéro 174–227"
            match_numero = re.search(r'Bidul-(\d+)', fichier)
            numero = int(match_numero.group(1)) if match_numero else None
            est_bidul_numero_174_227 = ("Bidul" in fichier) and numero and 174 <= numero <= 227

            # === Nouvelle priorité : découpe horizontale pour page1 ===
            if est_page1 and est_bidul_numero_174_227:
                print(f"✂️ Découpe horizontale spéciale (Bidul 174–227, page1) pour {image_path}")
                decoupe_horizontal(image_path)
                continue

            # === Règles existantes ===
            if annee < 2000:
                if est_page3:
                    print(f"✂️ Découpe spéciale en 3 (avant 2000) pour {image_path}")
                    decoupe_en_3(image_path)
                else:
                    decoupe_avant_2000(image_path)
            else:
                if est_page3 and est_bidul_apres_2019_03:
                    print(f"✂️ Découpe spéciale en 3 (après 2019-03 Bidul) pour {image_path}")
                    decoupe_en_3(image_path)
                else:
                    decoupe_apres_2000(image_path)

        except ValueError:
            print(f"⚠️ Impossible de déterminer l'année pour {fichier}, découpe par défaut (après 2000).")
            decoupe_apres_2000(image_path)





def convertir_csv_en_bdd(chemin_csv):
    import pandas as pd
    import sqlite3
    from sqlite3 import Error
    conn = None
    try:
        df = pd.read_csv(chemin_csv, sep=';', on_bad_lines='warn', engine='python')
        conn = sqlite3.connect(':memory:')
        df.to_sql('evenements', conn, if_exists='replace', index=False)
        chemin_sql = os.path.splitext(chemin_csv)[0] + '.sql'
        with open(chemin_sql, 'w') as f:
            for _, row in df.iterrows():
                columns = ', '.join([f'"{col}"' for col in df.columns])
                values = ', '.join([f'"{val}"' if isinstance(val, str) else str(val) for val in row])
                insert_stmt = f'INSERT INTO evenements ({columns}) VALUES ({values});\n'
                f.write(insert_stmt)
        print(f"Fichier SQL généré avec succès : {chemin_sql}")
    except Error as e:
        print(f"Une erreur s'est produite : {e}")
    finally:
        if conn:
            conn.close()

# === Point d'entrée ===
if __name__ == "__main__":
    # **Nouveaux chemins de dossiers découplés**
    DOSSIER_DES_PDFS = "pdfs_a_traiter"         # Dossier contenant les PDF à analyser
    DOSSIER_TEMPORAIRE_RACINE = "fichiers_temporaires" # Dossier où sera créé le sous-dossier "tempo"
    
    prompt_filepath = "prompt_mistral_13.txt"
    
    # Choix de l'OCR
    #i_orc = choix_de_ORC()
    i_orc = 3  # Pour le test, on force l'utilisation de Mistral

    # 1. Lister tous les fichiers PDF dans le dossier source
    fichiers_pdf_a_traiter = []
    for racine, _, fichiers in os.walk(DOSSIER_DES_PDFS):
        for fichier in fichiers:
            if fichier.lower().endswith(".pdf"):
                fichiers_pdf_a_traiter.append(os.path.join(racine, fichier))

    if not fichiers_pdf_a_traiter:
        print(f"❌ Aucun fichier PDF trouvé dans le dossier '{DOSSIER_DES_PDFS}'.")
    else:
        print(f"✅ {len(fichiers_pdf_a_traiter)} PDF trouvés. Début du traitement...")

    # 2. Boucler sur chaque PDF trouvé
    for chemin_pdf in fichiers_pdf_a_traiter:
        dossier_tempo_specifique = None
        try:
            # Crée les images découpées et récupère le nom du dossier temporaire
            dossier_tempo_specifique = traiter_un_pdf(chemin_pdf, DOSSIER_TEMPORAIRE_RACINE)
            dossier_images_decoupees = os.path.join(dossier_tempo_specifique, "découpé")

            if not os.path.exists(dossier_images_decoupees):
                print(f"⚠️  Le dossier 'découpé' n'a pas été trouvé pour {chemin_pdf}. Passage au suivant.")
                continue

            # Appliquer le traitement OCR choisi
            input("Appuyez sur Entrée pour continuer...")

            if i_orc == 1:
                print(f"🔍 Traitement de '{os.path.basename(chemin_pdf)}' avec Mistral OCR...")
                texte_resultat = traiter_images_decoupees_via_mistral(dossier_images_decoupees, prompt_filepath)
                
                os.makedirs("csv", exist_ok=True)
                pdf_basename = os.path.splitext(os.path.basename(chemin_pdf))[0]
                chemin_sortie = f"csv/{pdf_basename}_evenements.sql"
                
                with open(chemin_sortie, "w", encoding='utf-8') as f:
                    f.write(texte_resultat)
                print(f"✨ Résultat sauvegardé dans : {chemin_sortie}")

            elif i_orc == 2:
                print(f"🔍 Traitement de '{os.path.basename(chemin_pdf)}' avec Tesseract OCR...")
                traiter_images_decoupees_via_tesseract(dossier_images_decoupees)
            elif i_orc == 3:
                #nothing for now
                print("🔍 OCR non implémenté pour le moment.")
            else:
                print("❌ Aucune OCR sélectionnée, arrêt du traitement.")
                break 
        
        except Exception as e:
            print(f"❌ Une erreur critique est survenue lors du traitement de {chemin_pdf}: {e}")

        finally:
            # 3. Supprimer le dossier temporaire spécifique à ce PDF
            if dossier_tempo_specifique and os.path.exists(dossier_tempo_specifique):
                print(f"🗑️  Nettoyage des fichiers temporaires pour '{os.path.basename(chemin_pdf)}'...")
                shutil.rmtree(dossier_tempo_specifique)
                print("👍 Nettoyage terminé.\n" + "-"*50)

    print("🎉 Traitement de tous les fichiers PDF terminé.")
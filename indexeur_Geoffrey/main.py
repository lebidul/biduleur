import os
import fitz  # PyMuPDF
from DecoupePages import decoupe_avant_2000, decoupe_apres_2000
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
        # Importer ici pour éviter les dépendances inutiles si Mistral est utilisé
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


# Récupére tout les PDF d'un dossier
def traiter_dossier(dossier_principal):
    print(f"🔍 Analyse du dossier : {dossier_principal}")

    for racine, _, fichiers in os.walk(dossier_principal):
        for fichier in fichiers:
            if not fichier.lower().endswith(".pdf"):
                continue

            chemin_pdf = os.path.join(racine, fichier)
            print(f"📄 Traitement du fichier : {chemin_pdf}")

            # Crée un sous-dossier "tempo" à la racine pour stocker les images
            dossier_images = os.path.join(dossier_principal, "tempo")
            os.makedirs(dossier_images, exist_ok=True)

            # Conversion PDF → images
            images_pages = convertir_pdf_en_images(chemin_pdf, dossier_images)
            
            decoupe_selon_date(images_pages)

                    
def decoupe_selon_date(images_pages):
     # Découpe selon la date
            for image_path in images_pages:
                # Découpe en fonction de l'année du nom de fichier
                fichier = os.path.basename(image_path)
                if int(fichier[:4]) < 2000:
                    print(f"✂️ Découpe pour PDF avant 2000 : {image_path}")
                    decoupe_apres_2000(image_path)
                elif int(fichier[:4]) >= 2000:
                    print(f"✂️ Découpe pour PDF après 2000 : {image_path}")
                    decoupe_apres_2000(image_path)
                    

    




def convertir_csv_en_bdd(chemin_csv):
    import pandas as pd
    import sqlite3
    from sqlite3 import Error
    conn = None
    try:
        # Lire le fichier CSV avec gestion des erreurs de format
        df = pd.read_csv(chemin_csv, sep=';', on_bad_lines='warn', engine='python')

        # Connexion à une base de données SQLite en mémoire
        conn = sqlite3.connect(':memory:')

        # Écrire le DataFrame dans une table SQLite
        df.to_sql('evenements', conn, if_exists='replace', index=False)

        # Récupérer les instructions SQL INSERT
        chemin_sql = os.path.splitext(chemin_csv)[0] + '.sql'
        with open(chemin_sql, 'w') as f:
            for _, row in df.iterrows():
                # Construire l'instruction INSERT
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
    DOSSIER_A_ANALYSER = "temporaire" # Dossier à analyser, à adapter selon vos besoins
    traiter_dossier(DOSSIER_A_ANALYSER)
    
    prompt_filepath = "prompt_mistral_13.txt"  # Chemin du fichier de prompt pour Mistral

    
    #i_orc = choix_de_ORC()
    i_orc = 1  # Pour le test, on force l'utilisation de Mistral
    
    
    if i_orc == 1:
        print("🔍 Traitement avec Mistral OCR...")
        texte_resultat = traiter_images_decoupees_via_mistral(os.path.join(DOSSIER_A_ANALYSER, "tempo/découpé"), prompt_filepath)
        
        os.makedirs("csv", exist_ok=True)
        with open(f"csv/evenements_{os.path.splitext(os.path.basename(prompt_filepath))[0]}.sql", "w") as f:
                f.write(texte_resultat)


    elif i_orc == 2:
        print("🔍 Traitement avec Tesseract OCR...")
        traiter_images_decoupees_via_tesseract(os.path.join(DOSSIER_A_ANALYSER, "tempo/découpé"))
    else:
        print("❌ Aucune OCR sélectionnée, arrêt du traitement.")
        exit(1) 
        
    print("✅ Traitement OCR terminé avec succès.")
    


    
    if (False):
        print("🔄 Conversion du CSV en base de données...")
        chemin_csv = "csv/evenements_mistral.csv"
        if os.path.exists(chemin_csv):
            convertir_csv_en_bdd(chemin_csv)
            print("✅ Conversion terminée.")

        else:
            print(f"❌ Le fichier CSV n'existe pas : {chemin_csv}")
        print("📁 Tous les fichiers ont été traités avec succès.")
    
    

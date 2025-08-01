from config import API_KEY, FOLDER_ID, ORIENTATION_FOLDER_ID, ENABLE_EXTRACTION, ENABLE_POSTPROCESSING, OUTPUT_DIRECTORY, TMP_DIRECTORY
from extractor.pdf_extractor import extract_text_from_pdf
from extractor.ocr_extractor import ocr_with_orientation_correction
from postprocessing.text_corrector import correct_text_with_model
from postprocessing.text_cleaner import clean_text
# from utils.google_drive import list_files_in_folder
#from utils.google_drive_2 import list_files_in_folder
from utils.logging import log_processing
import os
import requests
from datetime import datetime
import pdb; pdb.set_trace()


USE_GOOGLE_DRIVE = False  # True pour Drive, False pour Local

def get_files_from_local():
    """Retourne une liste de chemins de fichiers PDF dans un dossier local (sous-dossiers inclus)"""
    files = []
    root_dir = "../indexer/archives/test/"
    #root_dir = "/Users/attadeurtia/Desktop/test/"

    for dirpath, dirnames, filenames in os.walk(root_dir):
        for file_name in filenames:
            if file_name.lower().endswith(".pdf"):
                full_path = os.path.join(dirpath, file_name)
                files.append(full_path)

    return files

# premiere étape 
def process_files(extraction=False, postprocessing=False):

    input_files = get_files_from_local()

    if extraction:
        for local_file_path in input_files:
            file_name = os.path.basename(local_file_path)

            # Extraire le texte des deux premières pages
            text = extract_text_from_pdf(local_file_path)

            if text.strip():
                # Enregistrer le texte extrait dans un fichier texte
                output_file_path = os.path.join(OUTPUT_DIRECTORY, f'{os.path.splitext(file_name)[0]}_pages_1_2.txt')
                with open(output_file_path, 'w', encoding='utf-8') as output_file:
                    output_file.write(text)

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"{timestamp} - Texte des pages 1 et 2 enregistré dans {output_file_path}")
                log_processing(file_name, None, os.path.basename(output_file_path), "Text Extraction")
                #TODO
            else:
                # Si aucun texte n'est trouvé, utiliser l'API OCR avec correction d'orientation
                ocr_text = ocr_with_orientation_correction(local_file_path, API_KEY, ORIENTATION_FOLDER_ID)

                # Enregistrer le texte OCR dans un fichier texte
                output_file_path = os.path.join(OUTPUT_DIRECTORY, f'{os.path.splitext(file_name)[0]}_pages_1_2_ocr.txt')
                with open(output_file_path, 'w', encoding='utf-8') as output_file:
                    output_file.write(ocr_text)

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"{timestamp} - Texte OCR des pages 1 et 2 enregistré dans {output_file_path}")
                log_processing(file_name, None, os.path.basename(output_file_path), "OCR")

            # # Supprimer le fichier temporaire
            # if os.path.exists(local_file_path):
            #     try:
            #         os.remove(local_file_path)
            #         # print(f"Fichier temporaire {local_file_path} supprimé.")
            #     except PermissionError:
            #         print(f"{local_file_path} ne peut pas etre supprimé.")

            if postprocessing:
                for file in os.listdir(OUTPUT_DIRECTORY):
                    if file.lower().endswith("_corrected.txt"):
                        continue

                    # Appliquer le post-traitement sur le fichier texte
                    corrected_file_path = os.path.join(OUTPUT_DIRECTORY, f'{os.path.splitext(file)[0]}_corrected.txt')
                    with open(os.path.join(OUTPUT_DIRECTORY, file), 'r', encoding='utf-8') as original_file:
                        text_to_correct = original_file.read()

                    # Nettoyer et corriger le texte
                    cleaned_text = clean_text(text_to_correct)
                    corrected_text = correct_text_with_model(cleaned_text)
                    # corrected_text = cleaned_text

                    # Enregistrer le texte corrigé dans un nouveau fichier
                    with open(corrected_file_path, 'w', encoding='utf-8') as corrected_file:
                        corrected_file.write(corrected_text)

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"{timestamp} - Texte corrigé dans {corrected_file_path}")
                    log_processing(file, None, os.path.basename(corrected_file_path), "Post-processing")

if __name__ == "__main__":
    process_files(extraction=True, postprocessing=True)

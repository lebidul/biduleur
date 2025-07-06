
import os
from utils.rotate_pdf import rotate_pdf_to_correct_orientation

PDF_INPUT_DIR = "./indexer/archives/"
PDF_OUTPUT_DIR = "./indexer/rotated/"

def rotate_all_pdfs():
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
    for dirpath, _, filenames in os.walk(PDF_INPUT_DIR):
        for filename in filenames:
            if not filename.lower().endswith(".pdf"):
                continue
            input_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(input_path, PDF_INPUT_DIR)
            output_path = os.path.join(PDF_OUTPUT_DIR, rel_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            print(f"🔁 Rotation : {rel_path}")
            try:
                rotate_pdf_to_correct_orientation(input_path, output_path)
                print(f"✔️  Fichier corrigé : {rel_path}")
            except Exception as e:
                print(f"❌  Erreur sur {rel_path} : {e}")

if __name__ == "__main__":
    rotate_all_pdfs()

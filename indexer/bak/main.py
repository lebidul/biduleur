from utils.pdf_helpers import get_pages_to_process
from utils.ocr_strategies import get_best_text_from_page
from datetime import datetime
import os
import pandas as pd
from pdf2image import convert_from_path
import fitz

PDF_ROOT_DIR = "./indexer/archives/"
TXT_OUTPUT_DIR = "./indexer/archives.txt/"

def process_all_pdfs():
    log = []
    for dirpath, _, filenames in os.walk(PDF_ROOT_DIR):
        for filename in filenames:
            if not filename.lower().endswith(".pdf"):
                continue

            timestamp = datetime.now().isoformat(timespec='seconds')
            print(f"[{timestamp}] → Traitement de : {filename}")

            pdf_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(pdf_path, PDF_ROOT_DIR)
            txt_path = os.path.join(TXT_OUTPUT_DIR, rel_path.replace(".pdf", ".txt"))
            os.makedirs(os.path.dirname(txt_path), exist_ok=True)

            try:
                text_final = ""
                methods_used = []
                scores = []

                pdf2img_pages = convert_from_path(pdf_path, dpi=300)
                with fitz.open(pdf_path) as doc:
                    max_pages, ignore_last = get_pages_to_process(doc, filename)
                    for i in range(max_pages):
                        page = doc[i]
                        img2 = pdf2img_pages[i] if i < len(pdf2img_pages) else None
                        text, method, score = get_best_text_from_page(page, img2)
                        text_final += text + "\n"
                        methods_used.append(method)
                        scores.append(score)

                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text_final)

                log.append({
                    "fichier_pdf": rel_path,
                    "caractères": len(text_final),
                    "status": "succès",
                    "méthodes_par_page": methods_used,
                    "scores_qualité": scores,
                    "score_moyen": round(sum(scores)/len(scores), 3) if scores else 0.0,
                    "page_3_ignorée": "oui" if ignore_last else "non",
                    "horodatage": timestamp
                })

            except Exception as e:
                log.append({
                    "fichier_pdf": rel_path,
                    "caractères": 0,
                    "status": f"erreur : {str(e)}",
                    "méthodes_par_page": [],
                    "scores_qualité": [],
                    "score_moyen": 0.0,
                    "page_3_ignorée": "inconnu",
                    "horodatage": timestamp
                })

    os.makedirs(TXT_OUTPUT_DIR, exist_ok=True)
    df = pd.DataFrame(log)
    df.to_csv(os.path.join(TXT_OUTPUT_DIR, "log_extraction.csv"), index=False, encoding="utf-8")
    print("✅ Extraction terminée. Résultats dans :", TXT_OUTPUT_DIR)

if __name__ == "__main__":
    process_all_pdfs()

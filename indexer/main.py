# Importation des modules nécessaires
from utils.pdf_helpers import get_pages_to_process
from utils.ocr_strategies import get_best_text_from_page
from datetime import datetime
import os
import pandas as pd
from pdf2image import convert_from_path
import fitz  # PyMuPDF

# Définition des répertoires d'entrée et de sortie pour les fichiers PDF et TXT.
PDF_ROOT_DIR = "./archives/2013 - du 174 au 184"
TXT_OUTPUT_DIR = "./archives.txt/2013 - du 174 au 184"

# Mode OCR utilisé pour l'extraction de texte. Options : 'fast', 'smart', 'opencv'
OCR_MODE = "smart"

def process_all_pdfs():
    """
    Traite tous les fichiers PDF dans le répertoire spécifié, extrait le texte et sauvegarde les résultats dans des fichiers texte.
    Un fichier de log est également généré pour suivre le processus et les résultats.
    """
    log = []  # Liste pour stocker les logs de traitement

    # Parcourt récursivement tous les fichiers dans le répertoire PDF_ROOT_DIR
    for dirpath, _, filenames in os.walk(PDF_ROOT_DIR):
        for filename in filenames:
            # Ignore les fichiers qui ne sont pas des PDF
            if not filename.lower().endswith(".pdf"):
                continue

            # Horodatage pour le suivi du traitement
            timestamp = datetime.now().isoformat(timespec='seconds')
            print(f"[{timestamp}] → Traitement de : {filename}")

            # Chemins d'accès pour le fichier PDF et le fichier texte de sortie
            pdf_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(pdf_path, PDF_ROOT_DIR)
            txt_path = os.path.join(TXT_OUTPUT_DIR, rel_path.replace(".pdf", ".txt"))

            # Crée les répertoires nécessaires pour le fichier de sortie
            os.makedirs(os.path.dirname(txt_path), exist_ok=True)

            try:
                text_final = ""  # Variable pour stocker le texte extrait
                methods_used = []  # Méthodes utilisées pour chaque page
                scores = []  # Scores de qualité pour chaque page

                # Convertit le PDF en images pour une meilleure extraction de texte
                pdf2img_pages = convert_from_path(pdf_path, dpi=300)

                # Ouvre le fichier PDF avec PyMuPDF
                with fitz.open(pdf_path) as doc:
                    # Détermine le nombre de pages à traiter et si la dernière page doit être ignorée
                    max_pages, ignore_last = get_pages_to_process(doc, filename)

                    # Traite chaque page du PDF
                    for i in range(max_pages):
                        page = doc[i]
                        # Utilise l'image convertie si disponible
                        img2 = pdf2img_pages[i] if i < len(pdf2img_pages) else None
                        # Obtient le meilleur texte extrait de la page
                        text, method, score = get_best_text_from_page(page, img2, ocr_mode=OCR_MODE)
                        text_final += text + "\n"
                        methods_used.append(method)
                        scores.append(score)

                # Écrit le texte extrait dans un fichier texte
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text_final)

                # Ajoute les résultats au log
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

                # Affiche les résultats du traitement
                print(f"✔️  {rel_path} ({timestamp})")
                print(f"    → statut         : succès")
                print(f"    → score_moyen    : {round(sum(scores)/len(scores), 3) if scores else 0.0}")
                print(f"    → méthode(s)     : {methods_used}")
                print(f"    → pages ignorées : page 3 ignorée : {'oui' if ignore_last else 'non'}")

            except Exception as e:
                # En cas d'erreur, ajoute une entrée d'erreur au log
                print(f"❌  {rel_path} ({timestamp})")
                print(f"    → statut         : erreur")
                print(f"    → raison         : {str(e)}")
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

    # Crée le répertoire de sortie pour les logs s'il n'existe pas
    os.makedirs(TXT_OUTPUT_DIR, exist_ok=True)

    # Sauvegarde les logs dans un fichier CSV
    df = pd.DataFrame(log)
    df.to_csv(os.path.join(TXT_OUTPUT_DIR, "log_extraction.csv"), index=False, encoding="utf-8")
    print("✅ Extraction terminée. Résultats dans :", TXT_OUTPUT_DIR)

if __name__ == "__main__":
    # Exécute la fonction principale si le script est exécuté directement
    process_all_pdfs()

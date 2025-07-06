
import os
import io
import fitz
import pytesseract
import pandas as pd
from PIL import Image, ImageOps, ImageFilter
from datetime import datetime
from langdetect import detect, DetectorFactory
from pip._internal.cli.cmdoptions import python
from spellchecker import SpellChecker
from pdf2image import convert_from_path

# === CONFIGURATION ===
# PDF_ROOT_DIR = "./indexer/archives/"
PDF_ROOT_DIR = "./indexer/archives/2025 - du 298 au 308"
TXT_OUTPUT_DIR = "./indexer/archives.txt/"
LANG_OCR = "fra"
os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"
DetectorFactory.seed = 42
spell = SpellChecker(language="fr")

# === OUTILS ===
def preprocess_image(img):
    gray = img.convert("L")
    enhanced = ImageOps.autocontrast(gray)
    filtered = enhanced.filter(ImageFilter.MedianFilter(size=3))
    bw = filtered.point(lambda x: 0 if x < 128 else 255, "1")
    return bw

def is_french(text):
    try:
        return detect(text.strip()) == "fr"
    except:
        return False

def ocr_quality_score(text):
    words = [w.lower() for w in text.strip().split() if w.isalpha()]
    if not words:
        return 0.0
    valid = [w for w in words if w in spell]
    return round(len(valid) / len(words), 3)

# === MÉTHODES OCR ===
def ocr_fitz_rotation(page):
    best_text = ""
    best_angle = 0
    for angle in [0, 90, 180, 270]:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).rotate(angle, expand=True)

        from ocr_utils_with_opencv import preprocess_image_opencv
        preprocessed = preprocess_image_opencv(img)

        text = pytesseract.image_to_string(preprocessed, lang=LANG_OCR, config="--psm 6")
        if is_french(text):
            return text, "fitz_rotation"
        if len(text.strip()) > len(best_text.strip()):
            best_text = text
            best_angle = angle
    return best_text, "fitz_rotation"

def ocr_langdetect_rotation(page):
    best_text = ""
    best_score = 0.0
    method = "langdetect"
    for angle in [0, 90, 180, 270]:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).rotate(angle, expand=True)
        preprocessed = preprocess_image(img)
        text = pytesseract.image_to_string(preprocessed, lang=LANG_OCR, config="--psm 6")
        score = ocr_quality_score(text)
        if is_french(text) and score > best_score:
            best_text = text
            best_score = score
    return best_text, method

def ocr_pdf2image_page(image):
    text = pytesseract.image_to_string(image, lang=LANG_OCR, config="--psm 6")
    return text, "pdf2image"

# === COMPARAISON DES MÉTHODES ===
def compare_ocr_methods_per_page(page, page_image=None):
    # Vérifier si la page contient déjà du texte accessible
    pdf_text = page.get_text().strip()
    if pdf_text:
        return pdf_text, "pdf_texte", 1.0

    candidates = []

    # Méthode 1 : fitz + rotation
    text1, method1 = ocr_fitz_rotation(page)
    score1 = ocr_quality_score(text1)
    candidates.append((text1, method1, score1))

    # Méthode 2 : fitz + rotation + langdetect + score
    text2, method2 = ocr_langdetect_rotation(page)
    score2 = ocr_quality_score(text2)
    candidates.append((text2, method2, score2))

    # Méthode 3 : pdf2image (si image dispo)
    if page_image:
        text3, method3 = ocr_pdf2image_page(page_image)
        score3 = ocr_quality_score(text3)
        candidates.append((text3, method3, score3))

    # Choisir la meilleure
    best = max(candidates, key=lambda x: x[2])  # basé sur score qualité
    return best  # (text, method_name, score)

# === TRAITEMENT PRINCIPAL ===
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

                # OCR via pdf2image (en entier)
                pdf2img_pages = convert_from_path(pdf_path, dpi=300)

                with fitz.open(pdf_path) as doc:
                    for i, page in enumerate(doc):
                        img2 = pdf2img_pages[i] if i < len(pdf2img_pages) else None
                        best_text, best_method, best_score = compare_ocr_methods_per_page(page, img2)
                        text_final += best_text + "\n"
                        methods_used.append(best_method)
                        scores.append(best_score)

                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text_final)

                log.append({
                    "fichier_pdf": rel_path,
                    "caractères": len(text_final),
                    "status": "succès",
                    "méthodes_par_page": methods_used,
                    "scores_qualité": scores,
                    "score_moyen": round(sum(scores)/len(scores), 3) if scores else 0.0,
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
                    "horodatage": timestamp
                })

    os.makedirs(TXT_OUTPUT_DIR, exist_ok=True)
    df = pd.DataFrame(log)
    df.to_csv(os.path.join(TXT_OUTPUT_DIR, "log_extraction.csv"), index=False, encoding="utf-8")
    print("✅ Extraction terminée. Résultats dans :", TXT_OUTPUT_DIR)

if __name__ == "__main__":
    process_all_pdfs()

import io
import pytesseract
from PIL import Image, ImageOps, ImageFilter
from langdetect import detect, DetectorFactory
from spellchecker import SpellChecker
from .image_processing import auto_preprocess_image

DetectorFactory.seed = 42
spell = SpellChecker(language="fr")
LANG_OCR = "fra"

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

def ocr_fitz_rotation(page):
    best_text = ""
    best_angle = 0
    for angle in [0, 90, 180, 270]:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).rotate(angle, expand=True)
        preprocessed = auto_preprocess_image(img)
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
        preprocessed = auto_preprocess_image(img)
        text = pytesseract.image_to_string(preprocessed, lang=LANG_OCR, config="--psm 6")
        score = ocr_quality_score(text)
        if is_french(text) and score > best_score:
            best_text = text
            best_score = score
    return best_text, method

def ocr_pdf2image_page(image):
    text = pytesseract.image_to_string(image, lang=LANG_OCR, config="--psm 6")
    return text, "pdf2image"

def get_best_text_from_page(page, page_image=None, ocr_mode="fast"):
    pdf_text = page.get_text().strip()

    if ocr_mode == "fast":
        text, method = ocr_fitz_rotation(page)
        return text, method, ocr_quality_score(text)
    elif ocr_mode == "opencv":
        text, method = ocr_pdf2image_page(page_image)
        return text, method, ocr_quality_score(text)
    # Sinon, on continue avec le comparatif complet ("smart")
    
    if pdf_text:
        return pdf_text, "pdf_texte", 1.0

    candidates = []

    text1, method1 = ocr_fitz_rotation(page)
    score1 = ocr_quality_score(text1)
    candidates.append((text1, method1, score1))

    text2, method2 = ocr_langdetect_rotation(page)
    score2 = ocr_quality_score(text2)
    candidates.append((text2, method2, score2))

    if page_image:
        text3, method3 = ocr_pdf2image_page(page_image)
        score3 = ocr_quality_score(text3)
        candidates.append((text3, method3, score3))

    return max(candidates, key=lambda x: x[2])

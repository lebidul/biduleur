
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
from .image_processing import auto_preprocess_image
from .ocr_strategies import is_french, ocr_quality_score

LANG_OCR = "fra"

def detect_best_rotation_for_page(page):
    best_angle = 0
    best_score = 0
    for angle in [0, 90, 180, 270]:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).rotate(angle, expand=True)
        preprocessed = auto_preprocess_image(img, mode="pil")  # rapide par défaut
        text = pytesseract.image_to_string(preprocessed, lang=LANG_OCR, config="--psm 6")
        score = ocr_quality_score(text)
        if is_french(text) and score > best_score:
            best_score = score
            best_angle = angle
    return best_angle, best_score

def rotate_pdf_to_correct_orientation(input_path, output_path):
    doc = fitz.open(input_path)
    rotated_doc = fitz.open()  # nouveau PDF

    for i, page in enumerate(doc):
        angle, score = detect_best_rotation_for_page(page)
        if angle != 0:
            page.set_rotation(angle)
        rotated_doc.insert_pdf(doc, from_page=i, to_page=i)

    rotated_doc.save(output_path)
    rotated_doc.close()
    doc.close()
    return output_path

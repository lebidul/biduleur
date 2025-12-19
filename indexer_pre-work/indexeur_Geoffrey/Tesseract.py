from PIL import Image
import pytesseract
import os
import cv2
import numpy as np

def preprocess_image_for_ocr(image_path, output_path=None):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        15, 10
    )

    coords = np.column_stack(np.where(binary > 0))
    if len(coords) == 0:
        print(f"⚠️ Aucun texte détecté dans {image_path}")
        return image_path

    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = gray.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    deskewed = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    final = cv2.bitwise_not(deskewed)

    output_path = output_path or os.path.splitext(image_path)[0] + "_preprocessed.png"
    cv2.imwrite(output_path, final)

    return output_path


def traiter_images_decoupees_via_tesseract(dossier_images, pretraitement=False):
    print(f"📂 Traitement OCR Tesseract du dossier : {dossier_images}")
    print(f"🔧 Prétraitement activé : {'Oui' if pretraitement else 'Non'}")

    for nom_fichier in os.listdir(dossier_images):
        chemin_image = os.path.join(dossier_images, nom_fichier)

        if not os.path.isfile(chemin_image) or not nom_fichier.lower().endswith((".png", ".jpg", ".jpeg")):
            continue

        try:
            print(f"📸 Lecture de l'image : {chemin_image}")

            if pretraitement:
                chemin_prep = preprocess_image_for_ocr(chemin_image)
                image = Image.open(chemin_prep)
            else:
                image = Image.open(chemin_image)

            texte = pytesseract.image_to_string(image, lang="fra")

            print(f"🔤 Texte extrait : {texte[:200]}...")

            nom_fichier_txt = os.path.splitext(nom_fichier)[0] + ".txt"
            chemin_texte = os.path.join(dossier_images, nom_fichier_txt)

            with open(chemin_texte, "w", encoding="utf-8") as f:
                f.write(texte)

            print(f"✅ Texte OCR sauvegardé dans : {chemin_texte}")

        except Exception as e:
            print(f"❌ Erreur OCR sur {chemin_image} : {e}")

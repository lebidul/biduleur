from PIL import ImageStat

DEFAULT_PREPROCESS_MODE = "pil"  # 'pil', 'opencv', 'auto'
from PIL import ImageOps, ImageFilter

def preprocess_image(img):
    gray = img.convert("L")
    enhanced = ImageOps.autocontrast(gray)
    filtered = enhanced.filter(ImageFilter.MedianFilter(size=3))
    bw = filtered.point(lambda x: 0 if x < 128 else 255, "1")
    return bw

import cv2
import numpy as np
from PIL import Image

def preprocess_image_opencv(pil_img):
    """
    Prétraitement avancé avec OpenCV :
    - niveaux de gris
    - égalisation d'histogramme
    - binarisation adaptative
    - nettoyage léger
    """
    cv_img = np.array(pil_img.convert("L"))

    # Égalisation d'histogramme
    cv_img = cv2.equalizeHist(cv_img)

    # Binarisation adaptative
    bin_img = cv2.adaptiveThreshold(
        cv_img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15, 11
    )

    # Nettoyage (morphologie)
    kernel = np.ones((1, 1), np.uint8)
    cleaned = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, kernel)

    return Image.fromarray(cleaned).convert("1")


def auto_preprocess_image(img, mode=None):
    """
    Choix intelligent du prétraitement :
    - 'opencv'  : toujours utiliser OpenCV (fond compliqué)
    - 'pil'     : utiliser la méthode PIL de base (rapide)
    - 'auto'    : si l’image est trop "complexe", utiliser OpenCV, sinon PIL
    """
    mode = mode or DEFAULT_PREPROCESS_MODE

    if mode == "opencv":
        return preprocess_image_opencv(img)
    elif mode == "pil":
        return preprocess_image(img)
    elif mode == "auto":
        # Heuristique simple : variance de l’image
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        if stat.stddev[0] > 40:  # image très contrastée/graphique
            return preprocess_image_opencv(img)
        else:
            return preprocess_image(img)
    else:
        raise ValueError("Mode inconnu pour le prétraitement : 'pil', 'opencv' ou 'auto'")

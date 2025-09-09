import os
import re
from datetime import datetime
from PIL import Image
import cv2
import numpy as np
def deskew_image(pil_image, max_angle=5):
    """
    marche moyen à voir si je garde cette fonction
    Redresse légèrement une image scannée.
    max_angle = correction maximale autorisée en degrés.
    """
    import cv2
    import numpy as np

    # Convertit en niveaux de gris
    img = np.array(pil_image.convert("L"))

    # Binarisation
    _, img_bin = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Coordonnées des pixels non vides
    coords = np.column_stack(np.where(img_bin > 0))
    if coords.size == 0:
        return pil_image  # si vide → pas de correction

    # Calcule l'angle
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # 🔑 Correction : ignorer les angles trop grands
    if abs(angle) > max_angle:
        # On considère que l'image est déjà droite
        return pil_image

    # Rotation
    (h, w) = img.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        np.array(pil_image), M, (w, h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )

    return Image.fromarray(rotated)

# Découpe pour les PDF d'avant 2000 (en deux moitiés horizontales)
def decoupe_avant_2000(image_path):
    img = Image.open(image_path)
    largeur, hauteur = img.size
    moitié = hauteur // 2

    haut = img.crop((0, 0, largeur, moitié))
    bas = img.crop((0, moitié, largeur, hauteur))

    base = image_path.rsplit(".", 1)[0]
    haut.save(f"{base}_part1.png")
    bas.save(f"{base}_part2.png")
    print(f"✂️ Découpe <2000 : {base}_part1.png + {base}_part2.png")


# Découpe alternative pour les PDF >= 2000 (verticalement en deux colonnes)
def decoupe_vertical(image_path):
    img = deskew_image(Image.open(image_path))
    largeur, hauteur = img.size
    moitié = largeur // 2

    gauche = img.crop((0, 0, moitié, hauteur))
    droite = img.crop((moitié, 0, largeur, hauteur))

    base = image_path.rsplit(".", 1)[0]
    dossier = os.path.join(os.path.dirname(image_path), "découpé")
    os.makedirs(dossier, exist_ok=True)

    gauche_path = os.path.join(dossier, f"{os.path.basename(base)}_col1.png")
    droite_path = os.path.join(dossier, f"{os.path.basename(base)}_col2.png")

    gauche.save(gauche_path)
    droite.save(droite_path)
    print(f"✂️ Découpe >=2000 : {gauche_path} + {droite_path}")
    
    


# Découpe spéciale en 3 colonnes égales
def decoupe_en_3(image_path):
    img = deskew_image(Image.open(image_path))
    largeur, hauteur = img.size
    tiers = largeur // 3  # largeur d'une colonne

    # Découpage en 3 parties
    col1 = img.crop((0, 0, tiers, hauteur))
    col2 = img.crop((tiers, 0, 2 * tiers, hauteur))
    col3 = img.crop((2 * tiers, 0, largeur, hauteur))

    base = image_path.rsplit(".", 1)[0]
    dossier = os.path.join(os.path.dirname(image_path), "découpé")
    os.makedirs(dossier, exist_ok=True)

    col1_path = os.path.join(dossier, f"{os.path.basename(base)}_col1.png")
    col2_path = os.path.join(dossier, f"{os.path.basename(base)}_col2.png")
    col3_path = os.path.join(dossier, f"{os.path.basename(base)}_col3.png")

    col1.save(col1_path)
    col2.save(col2_path)
    col3.save(col3_path)

    print(f"✂️ Découpe en 3 colonnes : {col1_path} + {col2_path} + {col3_path}")

def decoupe_horizontal(image_path):
    img = deskew_image(Image.open(image_path))
    largeur, hauteur = img.size
    moitié = hauteur // 2

    haut = img.crop((0, 0, largeur, moitié))
    bas = img.crop((0, moitié, largeur, hauteur))

    base = image_path.rsplit(".", 1)[0]
    dossier = os.path.join(os.path.dirname(image_path), "découpé")
    os.makedirs(dossier, exist_ok=True)

    haut_path = os.path.join(dossier, f"{os.path.basename(base)}_haut.png")
    bas_path = os.path.join(dossier, f"{os.path.basename(base)}_bas.png")

    haut.save(haut_path)
    bas.save(bas_path)
    print(f"✂️ Découpe horizontale : {haut_path} + {bas_path}")

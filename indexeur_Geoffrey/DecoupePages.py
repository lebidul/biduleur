from PIL import Image
import os

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
def decoupe_apres_2000(image_path):
    img = Image.open(image_path)
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
    img = Image.open(image_path)
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


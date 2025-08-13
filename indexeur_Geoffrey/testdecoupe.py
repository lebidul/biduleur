import fitz  # PyMuPDF
import os
from PIL import Image

def convertir_pdf_en_images(pdf_path, dpi=200):
    doc = fitz.open(pdf_path)
    images = []

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        images.append((i + 1, image))

    return images

def decouper_image_en_colonnes(image, seuil_largeur=2000):
    largeur, hauteur = image.size
    if largeur < seuil_largeur:
        return [image]

    largeur_moitie = largeur // 2
    image_gauche = image.crop((0, 0, largeur_moitie, hauteur))
    image_droite = image.crop((largeur_moitie, 0, largeur, hauteur))

    return [image_gauche, image_droite]

def sauvegarder_images(images, dossier_sortie, nom_pdf):
    os.makedirs(dossier_sortie, exist_ok=True)

    for numero_page, image in images:
        images_colonnes = decouper_image_en_colonnes(image)

        if len(images_colonnes) == 1:
            nom_fichier = f"{nom_pdf}_page{numero_page}.png"
            chemin_image = os.path.join(dossier_sortie, nom_fichier)
            images_colonnes[0].save(chemin_image)
            print(f"🖼️ Image sauvegardée : {chemin_image}")
        else:
            for i, img_col in enumerate(images_colonnes):
                nom_fichier = f"{nom_pdf}_page{numero_page}_col{i+1}.png"
                chemin_image = os.path.join(dossier_sortie, nom_fichier)
                img_col.save(chemin_image)
            print(f"✂️ Découpe >=2000 : {nom_pdf}_page{numero_page}_col1.png + col2.png")

def traiter_dossier_pdf(dossier):
    for nom_fichier in os.listdir(dossier):
        if not nom_fichier.lower().endswith(".pdf"):
            continue

        chemin_pdf = os.path.join(dossier, nom_fichier)
        nom_pdf = os.path.splitext(nom_fichier)[0]

        print(f"📄 Traitement du fichier : {chemin_pdf}")
        images = convertir_pdf_en_images(chemin_pdf)

        # Dossier de sortie pour les images converties
        dossier_sortie = os.path.join(dossier, "images_converties")
        sauvegarder_images(images, dossier_sortie, nom_pdf)

if __name__ == "__main__":
    dossier_pdf = "test"  # À adapter
    print(f"🔍 Analyse du dossier : {dossier_pdf}")
    traiter_dossier_pdf(dossier_pdf)

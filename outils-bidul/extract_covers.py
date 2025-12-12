#!/usr/bin/env python3
"""
Extracteur de couvertures du Bidul
Extrait la couverture A5 (coin supérieur droit) de chaque PDF
"""

import os
import re
import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
import argparse

# Configuration
DPI = 300  # Résolution d'extraction
OUTPUT_FORMAT = "jpg"  # jpg ou png
JPEG_QUALITY = 90


def extract_cover_from_pdf(pdf_path, output_dir, position="top_right"):
    """
    Extrait la couverture A5 d'un PDF du Bidul.

    Args:
        pdf_path: Chemin vers le PDF
        output_dir: Dossier de sortie
        position: Position de la couverture ("top_right", "top_left", "full_page")

    Returns:
        Chemin du fichier extrait ou None si erreur
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]  # Première page

        # Dimensions de la page
        page_rect = page.rect
        width = page_rect.width
        height = page_rect.height

        # Déterminer la zone à extraire (format A5 = moitié de la page)
        if position == "top_right":
            # Coin supérieur droit - format A5 portrait
            clip_rect = fitz.Rect(
                width / 2,  # x0: milieu
                0,  # y0: haut
                width,  # x1: droite
                height / 2  # y1: milieu (pour garder le ratio A5)
            )
        elif position == "top_left":
            clip_rect = fitz.Rect(0, 0, width / 2, height / 2)
        elif position == "right_full":
            # Moitié droite complète
            clip_rect = fitz.Rect(width / 2, 0, width, height)
        else:
            # Page entière
            clip_rect = page_rect

        # Matrice de transformation pour le DPI
        zoom = DPI / 72
        matrix = fitz.Matrix(zoom, zoom)

        # Rendu de la zone
        pix = page.get_pixmap(matrix=matrix, clip=clip_rect)

        # Convertir en image PIL pour traitement
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Générer le nom de fichier de sortie
        pdf_name = Path(pdf_path).stem
        # Extraire année-mois et numéro du nom de fichier
        # Format attendu: "YYYY-MM Bidul NNN" ou variations
        match = re.search(r'(\d{4})-?(\d{2}).*?[Bb]idul.*?(\d{2,3})', pdf_name)

        if match:
            year, month, num = match.groups()
            output_name = f"bidul_{num.zfill(3)}_{year}{month}.{OUTPUT_FORMAT}"
        else:
            # Fallback: utiliser le nom original
            output_name = f"{pdf_name}_cover.{OUTPUT_FORMAT}"

        output_path = os.path.join(output_dir, output_name)

        # Sauvegarder
        if OUTPUT_FORMAT == "jpg":
            img.save(output_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
        else:
            img.save(output_path, "PNG", optimize=True)

        doc.close()
        print(f"✓ Extrait: {output_name}")
        return output_path

    except Exception as e:
        print(f"✗ Erreur avec {pdf_path}: {e}")
        return None


def detect_cover_position(pdf_path):
    """
    Tente de détecter automatiquement la position de la couverture.
    Analyse la densité de pixels/couleurs pour trouver la zone illustrée.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]

        # Rendu basse résolution pour analyse rapide
        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        width, height = img.size

        # Découper en 4 quadrants et analyser la variance des couleurs
        quadrants = {
            "top_left": img.crop((0, 0, width // 2, height // 2)),
            "top_right": img.crop((width // 2, 0, width, height // 2)),
            "bottom_left": img.crop((0, height // 2, width // 2, height)),
            "bottom_right": img.crop((width // 2, height // 2, width, height))
        }

        # Calculer la variance (plus de variance = plus d'image/couleurs)
        variances = {}
        for name, quad in quadrants.items():
            import numpy as np
            arr = np.array(quad)
            variances[name] = np.var(arr)

        # Le quadrant avec le plus de variance est probablement la couverture
        best = max(variances, key=variances.get)

        doc.close()
        return best

    except:
        return "top_right"  # Défaut


def process_all_pdfs(input_dir, output_dir, auto_detect=False):
    """
    Traite tous les PDF d'un dossier.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Trouver tous les PDF récursivement
    pdf_files = []
    for root, dirs, files in os.walk(input_dir):
        for f in files:
            if f.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, f))

    pdf_files.sort()
    print(f"Trouvé {len(pdf_files)} fichiers PDF\n")

    results = {"success": [], "failed": []}

    for pdf_path in pdf_files:
        print(f"Traitement: {os.path.basename(pdf_path)}")

        if auto_detect:
            position = detect_cover_position(pdf_path)
            print(f"  Position détectée: {position}")
        else:
            position = "top_right"

        result = extract_cover_from_pdf(pdf_path, output_dir, position)

        if result:
            results["success"].append(result)
        else:
            results["failed"].append(pdf_path)

    # Résumé
    print(f"\n{'=' * 50}")
    print(f"Extraction terminée!")
    print(f"  ✓ Réussies: {len(results['success'])}")
    print(f"  ✗ Échouées: {len(results['failed'])}")

    if results["failed"]:
        print("\nFichiers en erreur:")
        for f in results["failed"]:
            print(f"  - {f}")

    return results


def extract_single_pdf_interactive(pdf_path, output_dir):
    """
    Mode interactif pour extraire et ajuster manuellement si besoin.
    """
    import matplotlib.pyplot as plt

    doc = fitz.open(pdf_path)
    page = doc[0]

    # Afficher la page complète
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    fig, axes = plt.subplots(1, 3, figsize=(15, 8))

    # Page complète
    axes[0].imshow(img)
    axes[0].set_title("Page complète")
    axes[0].axhline(y=img.height // 2, color='r', linestyle='--')
    axes[0].axvline(x=img.width // 2, color='r', linestyle='--')

    # Coin supérieur droit
    w, h = img.size
    top_right = img.crop((w // 2, 0, w, h // 2))
    axes[1].imshow(top_right)
    axes[1].set_title("Coin supérieur droit (défaut)")

    # Moitié droite
    right_half = img.crop((w // 2, 0, w, h))
    axes[2].imshow(right_half)
    axes[2].set_title("Moitié droite")

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "preview.png"))
    plt.show()

    doc.close()

    # Demander à l'utilisateur
    print("\nQuelle zone extraire?")
    print("  1. Coin supérieur droit (A5)")
    print("  2. Moitié droite complète")
    print("  3. Coin supérieur gauche")
    print("  4. Page entière")

    choice = input("Choix [1]: ").strip() or "1"

    positions = {
        "1": "top_right",
        "2": "right_full",
        "3": "top_left",
        "4": "full_page"
    }

    return extract_cover_from_pdf(pdf_path, output_dir, positions.get(choice, "top_right"))


def generate_wordpress_csv(covers_dir, base_url="https://www.lebidul.com/wp-content/uploads/couv/"):
    """
    Génère un fichier CSV pour faciliter l'import WordPress.
    """
    covers = sorted(Path(covers_dir).glob(f"*.{OUTPUT_FORMAT}"))

    csv_path = os.path.join(covers_dir, "import_wordpress.csv")

    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("filename,title,url,numero,date\n")

        for cover in covers:
            name = cover.stem
            # Parser le nom: bidul_NNN_YYYYMM
            match = re.search(r'bidul_(\d{3})_(\d{4})(\d{2})', name)
            if match:
                num, year, month = match.groups()
                title = f"Bidul N°{int(num)} - {month}/{year}"
                url = f"{base_url}{cover.name}"
                f.write(f'"{cover.name}","{title}","{url}",{num},{year}-{month}\n')

    print(f"CSV généré: {csv_path}")
    return csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extracteur de couvertures du Bidul")
    parser.add_argument("input", help="Dossier contenant les PDF ou fichier PDF unique")
    parser.add_argument("-o", "--output", default="./covers", help="Dossier de sortie")
    parser.add_argument("--auto", action="store_true", help="Détection automatique de la position")
    parser.add_argument("--interactive", action="store_true", help="Mode interactif (un PDF à la fois)")
    parser.add_argument("--csv", action="store_true", help="Générer un CSV pour WordPress")
    parser.add_argument("--dpi", type=int, default=300, help="Résolution (défaut: 300)")

    args = parser.parse_args()

    DPI = args.dpi

    if os.path.isfile(args.input):
        # Fichier unique
        if args.interactive:
            extract_single_pdf_interactive(args.input, args.output)
        else:
            os.makedirs(args.output, exist_ok=True)
            extract_cover_from_pdf(args.input, args.output)
    else:
        # Dossier
        results = process_all_pdfs(args.input, args.output, auto_detect=args.auto)

    if args.csv:
        generate_wordpress_csv(args.output)

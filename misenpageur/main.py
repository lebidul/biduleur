import os
import urllib.parse
import argparse
from misenpageur import image_processing, html_processing, template_rendering, pdf_generation
from weasyprint import CSS

import logging
logging.basicConfig(level=logging.DEBUG)

def main():
    parser = argparse.ArgumentParser(description="Generate Bidul PDF")
    parser.add_argument("--input-html", default="fichier_biduleur/biduleur.html", help="Input HTML file")
    parser.add_argument("--input-ours", default="ours/ours.txt", help="Input ours text file")
    parser.add_argument("--input-sponsors", default="logos", help="Input sponsors directory")
    parser.add_argument("--input-cover", default="couv/couverture.png", help="Input cover image")
    parser.add_argument("--output-html", default="bidul/output.html", help="Output HTML file")
    parser.add_argument("--output-pdf", default="bidul/output.pdf", help="Output PDF file")
    args = parser.parse_args()

    # Désactiver Fontconfig
    os.environ['FONTCONFIG_PATH'] = ''
    os.environ['FONTCONFIG_FILE'] = ''

    # Obtenez le chemin absolu du répertoire courant
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Assurez-vous que les dossiers de sortie existent
    os.makedirs(os.path.join(base_dir, 'optimised_logos'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'bidul'), exist_ok=True)

    # Resize images
    image_processing.resize_images(args.input_sponsors, os.path.join(base_dir, 'optimised_logos'))
    image_processing.resize_cover_image(args.input_cover, os.path.join(base_dir, 'bidul', "couverture_optimised.jpg"))

    # Extract and split events
    events = html_processing.extract_events(args.input_html)
    blocs = html_processing.split_events_into_blocks(events)

    # Read constant text
    with open(args.input_ours, "r", encoding="utf-8") as f:
        ours = f.read()

    # Prepare logos paths
    logos_dir = os.path.join(base_dir, 'optimised_logos')
    logos = [
        f'file:///{urllib.parse.quote(os.path.abspath(os.path.join(logos_dir, logo)).replace("\\", "/"))}'
        for logo in os.listdir(logos_dir)
    ]

    # Prepare image couverture path
    image_couverture = f'file:///{urllib.parse.quote(os.path.abspath(os.path.join(base_dir, "bidul", "couverture_optimised.jpg")).replace("\\", "/"))}'

    # Remplacer les espaces et caractères spéciaux dans les chemins
    logos = [logo.replace("%20", " ").replace("%3A", ":") for logo in logos]
    image_couverture = image_couverture.replace("%20", " ").replace("%3A", ":")

    # Render template
    context = {
        "logos": logos,
        "ours": ours,
        "image_couverture": image_couverture,
        "blocs": blocs,
    }
    template_rendering.render_template(os.path.join(base_dir, 'templates'), "template.html", context, args.output_html)

    # Generate PDF
    pdf_generation.generate_pdf(args.output_html, args.output_pdf)

if __name__ == "__main__":
    main()

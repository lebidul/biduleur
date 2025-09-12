# misenpageur/misenpageur/svgbuild.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import tempfile
import os
import base64
from pathlib import Path
from lxml import etree

from .config import Config
from .layout import Layout
from .pdfbuild import build_pdf


def _embed_resources_in_svg(svg_path: Path):
    """
    Ouvre un fichier SVG, trouve les références aux polices et images externes,
    les lit, les encode en base64 et les intègre directement dans le SVG.
    """
    if not svg_path.exists():
        return

    print(f"[INFO] Intégration des ressources pour {svg_path.name}...")

    # On utilise lxml pour parser le SVG, qui est un dialecte XML
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(svg_path), parser)
    root = tree.getroot()

    # L'espace de nom SVG est nécessaire pour trouver les éléments
    ns = {'svg': 'http://www.w3.org/2000/svg', 'xlink': 'http://www.w3.org/1999/xlink'}

    # 1. Intégrer les images
    for image_tag in root.xpath('//svg:image', namespaces=ns):
        href = image_tag.get('{http://www.w3.org/1999/xlink}href')
        if href and not href.startswith('data:'):
            image_path = svg_path.parent / href
            if image_path.exists():
                with open(image_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')

                ext = image_path.suffix.lower().replace('.', '')
                if ext == "jpg": ext = "jpeg"  # MIME type correct

                image_tag.set('{http://www.w3.org/1999/xlink}href', f"data:image/{ext};base64,{encoded}")

    # 2. Intégrer les polices (via les @font-face dans <style>)
    for style_tag in root.xpath('//svg:style', namespaces=ns):
        if style_tag.text:
            new_style_text = ""
            for line in style_tag.text.splitlines():
                if "src: url(" in line:
                    try:
                        font_filename = line.split('url(')[1].split(')')[0].strip('\'"')
                        font_path = svg_path.parent / font_filename
                        if font_path.exists():
                            with open(font_path, "rb") as f:
                                encoded = base64.b64encode(f.read()).decode('utf-8')

                            # On remplace la ligne par la version encodée en base64
                            line = f"src: url(data:font/opentype;base64,{encoded});"
                    except Exception:
                        pass  # On garde la ligne originale en cas d'erreur
                new_style_text += line + "\n"
            style_tag.text = new_style_text

    # On réécrit le fichier SVG avec les ressources intégrées
    tree.write(str(svg_path), pretty_print=True, xml_declaration=True, encoding="utf-8")


def build_svg(project_root: str, cfg: Config, layout: Layout, out_path: str, config_path: str) -> dict:
    """
    Génère des SVGs autonomes en convertissant un PDF temporaire, puis en intégrant
    les ressources externes (polices, images) via un post-traitement.
    """
    report = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        temp_pdf_path = tmp.name

    try:
        report = build_pdf(project_root, cfg, layout, temp_pdf_path, config_path)
        output_dir = Path(out_path).parent
        output_prefix = Path(out_path).stem
        output_dir.mkdir(parents=True, exist_ok=True)

        # 3. Préparer la commande de conversion avec les bonnes options
        # Ce chemin peut être nécessaire sur Windows si le PATH n'est pas configuré
        # pdf2svg_executable = "pdf2svg"
        pdf2svg_executable = r"C:\Program Files\pdf2svg\pdf2svg.exe"

        command = [pdf2svg_executable, "-o", str(output_dir), "--prefix", output_prefix, temp_pdf_path]

        print(f"[INFO] Lancement de la conversion SVG avec la commande : {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stdout: print(f"[INFO] Sortie de pdf2svg: {result.stdout}")

        # --- POST-TRAITEMENT ---
        # Lister tous les fichiers générés par pdf2svg
        generated_files = os.listdir(output_dir)
        svg_files_to_process = []
        other_files_to_delete = []

        for f_name in generated_files:
            if f_name.startswith(output_prefix):
                if f_name.endswith(".svg"):
                    svg_files_to_process.append(output_dir / f_name)
                elif not f_name.endswith((".pdf")):  # Ne pas supprimer le PDF final
                    other_files_to_delete.append(output_dir / f_name)

        # Intégrer les ressources dans chaque SVG
        for svg_path in svg_files_to_process:
            _embed_resources_in_svg(svg_path)

        # Supprimer les fichiers annexes
        print(f"[INFO] Nettoyage de {len(other_files_to_delete)} fichier(s) annexe(s)...")
        for f_path in other_files_to_delete:
            try:
                os.remove(f_path)
            except OSError as e:
                print(f"[WARN] Impossible de supprimer le fichier annexe {f_path.name}: {e}")

        print(f"[INFO] Fichiers SVG autonomes sauvegardés dans : {output_dir}")

    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print("[ERR] Commande 'pdf2svg' introuvable. Assurez-vous qu'elle est installée et dans votre PATH système.")
        return {"error": "pdf2svg introuvable"}
    except subprocess.CalledProcessError as e:
        print("[ERR] La conversion PDF vers SVG a échoué.")
        if e.stdout: print(f"[INFO] stdout: {e.stdout}")
        if e.stderr: print(f"[ERR] stderr: {e.stderr}")
        return {"error": "La conversion pdf2svg a échoué."}
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

    return report
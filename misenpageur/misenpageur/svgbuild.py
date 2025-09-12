# misenpageur/misenpageur/svgbuild.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import tempfile
import os
from pathlib import Path

from .config import Config
from .layout import Layout
from .pdfbuild import build_pdf


def build_svg(project_root: str, cfg: Config, layout: Layout, out_path: str, config_path: str) -> dict:
    """
    Génère un SVG par page en convertissant un PDF temporaire via la
    version open-source de 'pdf2svg'.
    """
    report = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        temp_pdf_path = tmp.name

    try:
        report = build_pdf(project_root, cfg, layout, temp_pdf_path, config_path)
        output_dir = Path(out_path).parent
        output_prefix = Path(out_path).stem

        # On suppose 3 pages pour l'instant
        num_pages = 3

        pdf2svg_executable = "pdf2svg"

        for page_num in range(1, num_pages + 1):
            svg_out_path = output_dir / f"{output_prefix}_{page_num}.svg"

            command = [
                pdf2svg_executable,
                temp_pdf_path,
                str(svg_out_path),
                str(page_num)  # On spécifie le numéro de page
            ]

            print(f"[INFO] Lancement de la conversion SVG pour la page {page_num}...")
            subprocess.run(command, capture_output=True, text=True, check=True)
            print(f"[INFO] Fichier SVG sauvegardé : {svg_out_path}")

    except FileNotFoundError:
        print("[ERR] Commande 'pdf2svg' introuvable. Assurez-vous qu'elle est installée et dans votre PATH système.")
        return {"error": "pdf2svg introuvable"}
    except subprocess.CalledProcessError as e:
        print(f"[ERR] La conversion PDF vers SVG a échoué.")
        if e.stdout: print(f"[INFO] stdout: {e.stdout}")
        if e.stderr: print(f"[ERR] stderr: {e.stderr}")
        return {"error": "La conversion pdf2svg a échoué."}
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

    return report
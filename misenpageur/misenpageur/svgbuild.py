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


def _post_process_svg(svg_path: Path):
    """
    Ouvre un fichier SVG et effectue des corrections spécifiques.
    - Remplace les puces de secours par le glyphe correct.
    """
    if not svg_path.exists():
        return

    print(f"[INFO] Post-traitement de {svg_path.name}...")

    try:
        # Lire le contenu du fichier
        content = svg_path.read_text(encoding="utf-8")

        # ==================== LA CORRECTION EST ICI ====================
        # pdf2svg remplace souvent '❑' (U+2751) par '☐' (U+2610) ou un autre glyphe.
        # Nous allons remplacer toutes les puces visuellement incorrectes par la bonne.
        # C'est une approche "brute" mais efficace.
        # Ajoutez d'autres caractères à remplacer si nécessaire.
        bad_bullets = ["☐", "▫"]
        good_bullet = "❑"

        replacements_made = 0
        for bad_bullet in bad_bullets:
            if bad_bullet in content:
                count = content.count(bad_bullet)
                content = content.replace(bad_bullet, good_bullet)
                replacements_made += count

        if replacements_made > 0:
            print(f"[INFO] {replacements_made} puce(s) corrigée(s).")
            # Réécrire le fichier avec le contenu corrigé
            svg_path.write_text(content, encoding="utf-8")
        # =============================================================

    except Exception as e:
        print(f"[WARN] Échec du post-traitement pour {svg_path.name}: {e}")


def build_svg(project_root: str, cfg: Config, layout: Layout, out_path: str, config_path: str) -> dict:
    """
    Génère un SVG par page en convertissant un PDF temporaire, puis
    applique un post-traitement pour corriger les glyphes.
    """
    report = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        temp_pdf_path = tmp.name

    try:
        report = build_pdf(project_root, cfg, layout, temp_pdf_path, config_path)
        output_dir = Path(out_path).parent
        output_prefix = Path(out_path).stem

        pdf2svg_executable = "pdf2svg"
        command = [pdf2svg_executable, temp_pdf_path, str(output_dir / f"{output_prefix}_%d.svg"), "all"]

        print(f"[INFO] Lancement de la conversion SVG...")
        subprocess.run(command, capture_output=True, text=True, check=True)

        # --- POST-TRAITEMENT ---
        num_pages = 3  # A adapter si le nombre de pages devient dynamique
        for i in range(1, num_pages + 1):
            svg_path = output_dir / f"{output_prefix}_{i}.svg"
            if svg_path.exists():
                _post_process_svg(svg_path)

        print(f"[INFO] Fichiers SVG sauvegardés et corrigés dans : {output_dir}")

    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"[ERR] La conversion PDF vers SVG a échoué.")
        if e.stdout: print(f"[INFO] stdout: {e.stdout}")
        if e.stderr: print(f"[ERR] stderr: {e.stderr}")
        return {"error": "La conversion pdf2svg a échoué."}
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

    return report
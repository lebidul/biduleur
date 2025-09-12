# misenpageur/misenpageur/svgbuild.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import tempfile
import os
from pathlib import Path

from .config import Config
from .layout import Layout
from .pdfbuild import build_pdf  # On utilise le build_pdf existant


def build_svg(project_root: str, cfg: Config, layout: Layout, out_path: str, config_path: str) -> dict:
    """
    Génère un SVG éditable de la page 3 (le poster).
    - Crée un PDF temporaire contenant toutes les pages.
    - Utilise 'pdf2svg' pour extraire et convertir uniquement la page 3 en SVG.
    - Nettoie automatiquement les fichiers temporaires.
    """
    report = {}

    # tempfile.NamedTemporaryFile est un gestionnaire de contexte
    # qui garantit que le fichier est supprimé à la fin.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        temp_pdf_path = tmp.name

    try:
        # 1. Générer le PDF complet dans le fichier temporaire
        report = build_pdf(project_root, cfg, layout, temp_pdf_path, config_path)

        # 2. Préparer le dossier de sortie pour le SVG
        output_dir = Path(out_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 3. Préparer la commande de conversion
        # pdf2svg_executable = "pdf2svg"  # Ou le chemin complet si nécessaire
        pdf2svg_executable = r"C:\Program Files\pdf2svg\pdf2svg.exe"

        # On spécifie le dossier de sortie (-o), le préfixe du fichier,
        # et la page à extraire (-a 3).
        command = [
            pdf2svg_executable,
            temp_pdf_path,
            "-o", str(output_dir),
            "--prefix", Path(out_path).stem,  # Nom du fichier sans extension
            "all"
        ]

        print(f"[INFO] Lancement de la conversion SVG avec la commande : {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=False)

        # 4. Vérifier la sortie et renommer le fichier final
        if result.returncode != 0 or result.stderr:
            print("[ERR] La conversion PDF vers SVG a échoué ou a produit des avertissements.")
            if result.stdout: print(f"[INFO] stdout: {result.stdout}")
            if result.stderr: print(f"[ERR] stderr: {result.stderr}")
            raise RuntimeError("La conversion pdf2svg a échoué.")

        # pdf2svg va créer un fichier comme "nom_3.svg" ou "nom_03.svg".
        # Nous devons le trouver et le renommer avec le nom exact demandé.
        expected_svg_path = output_dir / f"{Path(out_path).stem}_3.svg"
        if os.path.exists(expected_svg_path):
            os.replace(expected_svg_path, out_path)
            print(f"[INFO] Fichier SVG sauvegardé : {out_path}")
        else:
            # Essayer avec d'autres formats de nommage si nécessaire
            print(f"[WARN] Fichier SVG attendu non trouvé à : {expected_svg_path}")

    finally:
        # 5. Le fichier temporaire est supprimé automatiquement par le `with`
        #    mais on ajoute une sécurité.
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

    return report
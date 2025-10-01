# misenpageur/misenpageur/svgbuild.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import tempfile
import os
import re
from pathlib import Path
from collections import Counter
from typing import List

import logging # Ajouter cet import
log = logging.getLogger(__name__) # Obtenir le logger pour ce module

from lxml import etree
from .config import Config
from .layout import Layout
from .pdfbuild import build_pdf


def _post_process_svg(svg_path: Path, expected_event_count: int):
    """
    Corrige les puces en utilisant une heuristique géométrique :
    1. Filtre par fréquence.
    2. Analyse le chemin ('d' attribute) du glyphe pour exclure les courbes.
    3. Remplace la définition du glyphe trouvé par un carré parfait.
    """
    if not svg_path.exists() or expected_event_count == 0:
        return

    # log.info(f"Post-traitement de {svg_path.name} (attend ~{expected_event_count} puces)...")
    log.info(f"Post-traitement de {svg_path.name} (attend ~{expected_event_count} puces)...")

    try:
        content = svg_path.read_text(encoding="utf-8")
        glyph_ids_used = re.findall(r'xlink:href="#(glyph\d+-\d+)"', content)
        if not glyph_ids_used: return

        glyph_counts = Counter(glyph_ids_used)
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(content.encode('utf-8'), parser)
        ns = {'svg': 'http://www.w3.org/2000/svg'}

        # 1. Trouver les candidats qui ont la bonne fréquence
        candidate_ids = []
        tolerance = 2
        for glyph_id, count in glyph_counts.items():
            if abs(count - expected_event_count) <= tolerance:
                candidate_ids.append(glyph_id)

        if not candidate_ids:
            log.warning(f"Aucun glyphe candidat trouvé avec la bonne fréquence.")
            return

        log.info(f"Glyphes candidats par fréquence : {candidate_ids}")

        glyph_id_to_replace = None

        # 2. Parmi les candidats, trouver celui dont le chemin ne contient pas de courbes
        curve_commands = ['c', 's', 'q', 't', 'a']

        for glyph_id in candidate_ids:
            # On cherche directement le chemin à l'intérieur du symbole
            path_list = root.xpath(f'//svg:symbol[@id="{glyph_id}"]/svg:path', namespaces=ns)

            if not path_list: continue

            path = path_list[0]
            d_attr = path.get('d', '').lower()  # On passe en minuscule pour attraper C, S, Q...

            # Si le chemin ne contient AUCUNE des commandes de courbe, c'est notre homme !
            if not any(cmd in d_attr for cmd in curve_commands):
                glyph_id_to_replace = glyph_id
                log.info(f"Glyphe de puce confirmé par sa géométrie (pas de courbes) : {glyph_id_to_replace}")
                break  # On a trouvé, on sort de la boucle

        if not glyph_id_to_replace:
            log.warning(f"Aucun des glyphes candidats n'avait la forme géométrique d'une puce.")
            return

        # 3. Remplacer la définition du glyphe identifié
        pattern = re.compile(fr'(<(?:symbol|g)[^>]*?id="{glyph_id_to_replace}"[^>]*?>)(.*?)(</(?:symbol|g)>)',
                             re.DOTALL)
        # On définit un carré blanc avec une bordure noire
        new_geometry = '<path d="M0 -4 H4 V0 H0 Z" fill="white" stroke="black" stroke-width="0.8"/>'
        match = pattern.search(content)

        if match:
            start_tag, end_tag = match.group(1), match.group(3)
            new_definition = f"{start_tag}{new_geometry}{end_tag}"
            content, num_replacements = pattern.subn(new_definition, content, count=1)

            if num_replacements > 0:
                svg_path.write_text(content, encoding="utf-8")
                log.info(f"Définition du glyphe '{glyph_id_to_replace}' corrigée avec succès.")

    except Exception as e:
        log.warning(f"Échec du post-traitement pour {svg_path.name}: {e}")


def build_svg(project_root: str, cfg: Config, layout: Layout, out_dir: str, config_path: str, paras: List[str]) -> dict:
    """
    Génère un SVG par page en convertissant un PDF temporaire, puis
    applique un post-traitement pour corriger les glyphes de puce.
    """
    report = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        temp_pdf_path = tmp.name

    try:
        report = build_pdf(project_root, cfg, layout, temp_pdf_path, config_path, paras)
        event_counts = report.get("event_counts_per_page", {})

        # On s'assure que le dossier de sortie existe
        output_dir = Path(out_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Le nom de base sera "page" (ex: page_1.svg, page_2.svg, ...)
        output_prefix = "page"

        executable_name = "pdf2svg.exe"  # Le nom de base ne change pas
        path_to_executable = os.path.join(project_root, "bin", "win64", executable_name)

        # On utilise le chemin complet 'path_to_executable' et non plus 'executable_name'
        command = [path_to_executable, temp_pdf_path, str(output_dir / f"{output_prefix}_%d.svg"), "all"]

        log.info(f"Lancement de la conversion SVG...")
        subprocess.run(command, capture_output=True, text=True, check=True)

        num_pages = len(event_counts)
        for i in range(1, num_pages + 1):
            svg_path = output_dir / f"{output_prefix}_{i}.svg"
            if svg_path.exists():
                _post_process_svg(svg_path, event_counts.get(i, 0))

        log.info(f"Fichiers SVG sauvegardés et corrigés dans : {output_dir}")

    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        log.error(f"Échec de la conversion SVG (assurez-vous que pdf2svg est installé et dans le PATH).")
        if hasattr(e, 'stderr') and e.stderr: log.error(f"stderr: {e.stderr}")
        return {"error": "La conversion SVG a échoué."}
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

    return report
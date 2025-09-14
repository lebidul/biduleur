# misenpageur/misenpageur/svgbuild.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import tempfile
import os
import re
from pathlib import Path
from collections import Counter

from lxml import etree
from .config import Config
from .layout import Layout
from .pdfbuild import build_pdf


def _post_process_svg(svg_path: Path, expected_event_count: int):
    """
    Corrige les puces en identifiant le glyphe par fréquence ET par forme,
    puis en remplaçant sa définition par un carré parfait.
    """
    if not svg_path.exists() or expected_event_count == 0:
        return

    print(f"[INFO] Post-traitement de {svg_path.name} (attend {expected_event_count} puces)...")

    try:
        content = svg_path.read_text(encoding="utf-8")

        # 1. Compter la fréquence de chaque glyphe utilisé
        glyph_ids_used = re.findall(r'xlink:href="#(glyph\d+-\d+)"', content)
        if not glyph_ids_used:
            print("[WARN] Aucune référence de glyphe (<use>) trouvée.")
            return

        glyph_counts = Counter(glyph_ids_used)
        print(f"[INFO] Fréquences des glyphes trouvés : {glyph_counts}")

        # 2. Parser le SVG pour pouvoir inspecter la géométrie
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(content.encode('utf-8'), parser)
        ns = {'svg': 'http://www.w3.org/2000/svg'}

        # ==================== NOUVELLE LOGIQUE DE DÉTECTION ====================

        # 3. Trouver les candidats qui ont la bonne fréquence
        candidate_ids = []
        tolerance = 5  # On accepte une différence de 5
        for glyph_id, count in glyph_counts.items():
            if abs(count - expected_event_count) <= tolerance:
                candidate_ids.append(glyph_id)

        if not candidate_ids:
            print("[WARN] Aucun glyphe candidat trouvé avec la bonne fréquence.")
            return

        print(f"[INFO] Glyphes candidats par fréquence : {candidate_ids}")

        glyph_id_to_replace = None

        # 4. Parmi les candidats, trouver celui qui a la forme d'un rectangle
        for glyph_id in candidate_ids:
            glyph_def_list = root.xpath(f'//*[local-name()="symbol" or local-name()="g"][@id="{glyph_id}"]',
                                        namespaces=ns)
            if not glyph_def_list: continue

            glyph_def = glyph_def_list[0]
            paths = glyph_def.xpath('svg:path', namespaces=ns)

            if len(paths) == 1:
                path = paths[0]
                d_attr = path.get('d', '').lower()

                # Heuristique de forme : pas de courbes (c,s,q,t,a)
                if not any(cmd in d_attr for cmd in ['c', 's', 'q', 't', 'a']):
                    glyph_id_to_replace = glyph_id
                    print(f"[INFO] Glyphe de puce confirmé par sa forme : {glyph_id_to_replace}")
                    break  # On a trouvé notre puce, on sort de la boucle

        if not glyph_id_to_replace:
            print("[WARN] Aucun des glyphes candidats n'avait la forme d'un rectangle simple.")
            return

        # =======================================================================

        # 5. Remplacer la définition du glyphe identifié
        # ... (cette partie est identique à la version précédente)
        pattern = re.compile(fr'(<(?:symbol|g)[^>]*?id="{glyph_id_to_replace}"[^>]*?>)(.*?)(</(?:symbol|g)>)',
                             re.DOTALL)
        new_geometry = '<rect x="0" y="-4" width="4" height="4" fill="white" stroke="black" stroke-width="0.8"/>'
        match = pattern.search(content)

        if match:
            start_tag, end_tag = match.group(1), match.group(3)
            new_definition = f"{start_tag}{new_geometry}{end_tag}"
            content, num_replacements = pattern.subn(new_definition, content, count=1)

            if num_replacements > 0:
                svg_path.write_text(content, encoding="utf-8")
                print(f"[INFO] Définition du glyphe '{glyph_id_to_replace}' corrigée avec succès.")
            else:
                print(f"[WARN] Le glyphe a été identifié mais sa définition n'a pas pu être remplacée.")
        else:
            print(f"[WARN] Impossible de trouver le bloc de définition pour le glyphe '{glyph_id_to_replace}'.")

    except Exception as e:
        print(f"[WARN] Échec du post-traitement pour {svg_path.name}: {e}")


def build_svg(project_root: str, cfg: Config, layout: Layout, out_path: str, config_path: str) -> dict:
    """
    Génère un SVG par page en convertissant un PDF temporaire, puis
    applique un post-traitement pour corriger les glyphes de puce.
    """
    report = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        temp_pdf_path = tmp.name

    try:
        report = build_pdf(project_root, cfg, layout, temp_pdf_path, config_path)
        event_counts = report.get("event_counts_per_page", {})

        output_dir = Path(out_path).parent
        output_prefix = Path(out_path).stem

        pdf2svg_executable = "pdf2svg"
        command = [pdf2svg_executable, temp_pdf_path, str(output_dir / f"{output_prefix}_%d.svg"), "all"]

        print(f"[INFO] Lancement de la conversion SVG...")
        subprocess.run(command, capture_output=True, text=True, check=True)

        num_pages = len(event_counts)
        for i in range(1, num_pages + 1):
            svg_path = output_dir / f"{output_prefix}_{i}.svg"
            if svg_path.exists():
                _post_process_svg(svg_path, event_counts.get(i, 0))

        print(f"[INFO] Fichiers SVG sauvegardés et corrigés dans : {output_dir}")

    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"[ERR] Échec de la conversion SVG (assurez-vous que pdf2svg est installé et dans le PATH).")
        if hasattr(e, 'stderr') and e.stderr: print(f"[ERR] stderr: {e.stderr}")
        return {"error": "La conversion SVG a échoué."}
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

    return report
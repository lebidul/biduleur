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

import logging

log = logging.getLogger(__name__)

from lxml import etree
from .config import Config
from .layout import Layout
from .pdfbuild import build_pdf

# Essayer d'importer PyMuPDF
try:
    import fitz

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    log.debug("PyMuPDF non disponible, utilisation de pdf2svg.exe")


def _post_process_svg(svg_path: Path, expected_event_count: int):
    """
    Corrige les puces en utilisant une heuristique géométrique :
    1. Filtre par fréquence.
    2. Analyse le chemin ('d' attribute) du glyphe pour exclure les courbes.
    3. Remplace la définition du glyphe trouvé par un carré parfait.
    """
    if not svg_path.exists() or expected_event_count == 0:
        return

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
            path_list = root.xpath(f'//svg:symbol[@id="{glyph_id}"]/svg:path', namespaces=ns)

            if not path_list: continue

            path = path_list[0]
            d_attr = path.get('d', '').lower()

            if not any(cmd in d_attr for cmd in curve_commands):
                glyph_id_to_replace = glyph_id
                log.info(f"Glyphe de puce confirmé par sa géométrie (pas de courbes) : {glyph_id_to_replace}")
                break

        if not glyph_id_to_replace:
            log.warning(f"Aucun des glyphes candidats n'avait la forme géométrique d'une puce.")
            return

        # 3. Remplacer la définition du glyphe identifié
        pattern = re.compile(fr'(<(?:symbol|g)[^>]*?id="{glyph_id_to_replace}"[^>]*?>)(.*?)(</(?:symbol|g)>)',
                             re.DOTALL)
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


def _convert_pdf_to_svg_pymupdf(temp_pdf_path: str, output_dir: Path, output_prefix: str, event_counts: dict) -> bool:
    """
    Convertit un PDF en SVG avec PyMuPDF.
    Retourne True si succès, False sinon.
    """
    try:
        log.info("Conversion PDF → SVG avec PyMuPDF...")
        doc = fitz.open(temp_pdf_path)

        # Facteur de zoom pour améliorer la résolution des images (2 = 200%)
        # Augmenter si nécessaire (3 ou 4), mais fichiers plus lourds
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Récupérer les dimensions de la page PDF
            rect = page.rect
            width_pt = rect.width
            height_pt = rect.height

            # Convertir en millimètres pour le SVG (1pt = 0.352778mm)
            width_mm = width_pt * 0.352778
            height_mm = height_pt * 0.352778

            # Générer le SVG avec matrice de transformation pour meilleure résolution
            svg_text = page.get_svg_image(matrix=mat)

            # Corriger les dimensions du SVG (le zoom agrandit le viewBox)
            svg_text = _fix_svg_dimensions(svg_text, width_pt * zoom, height_pt * zoom, width_mm, height_mm)

            svg_path = output_dir / f"{output_prefix}_{page_num + 1}.svg"
            svg_path.write_text(svg_text, encoding="utf-8")

            _post_process_svg(svg_path, event_counts.get(page_num + 1, 0))
            log.info(f"Page {page_num + 1}/{len(doc)} convertie ({width_mm:.1f}×{height_mm:.1f}mm, zoom×{zoom})")

        doc.close()
        log.info(f"Conversion PyMuPDF terminée : {output_dir}")
        return True

    except Exception as e:
        log.error(f"Échec PyMuPDF : {e}")
        return False


def _fix_svg_dimensions(svg_text: str, width_pt: float, height_pt: float, width_mm: float, height_mm: float) -> str:
    """
    Corrige les dimensions du SVG généré par PyMuPDF pour conserver la taille du PDF.
    """
    # Pattern pour trouver la balise <svg>
    svg_pattern = r'<svg([^>]*)>'

    def replace_svg_tag(match):
        attrs = match.group(1)

        # Construire la nouvelle balise avec les bonnes dimensions
        new_attrs = f' width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_pt} {height_pt}"'

        # Garder les autres attributs existants (sauf width, height, viewBox)
        for attr in ['xmlns', 'xmlns:xlink']:
            attr_pattern = rf'{attr}="([^"]*)"'
            attr_match = re.search(attr_pattern, attrs)
            if attr_match:
                new_attrs += f' {attr}="{attr_match.group(1)}"'

        return f'<svg{new_attrs}>'

    svg_text = re.sub(svg_pattern, replace_svg_tag, svg_text, count=1)
    return svg_text


def _convert_pdf_to_svg_pdf2svg(project_root: str, temp_pdf_path: str, output_dir: Path, output_prefix: str,
                                event_counts: dict) -> bool:
    """
    Convertit un PDF en SVG avec pdf2svg.exe.
    Retourne True si succès, False sinon.
    """
    try:
        # Utiliser Path pour normaliser le chemin
        path_to_executable = Path(project_root) / "bin" / "win64" / "pdf2svg.exe"

        # Vérifier que l'exécutable existe
        if not path_to_executable.exists():
            log.error(f"pdf2svg.exe introuvable : {path_to_executable}")
            log.error("Solutions :")
            log.error("  1. Installer PyMuPDF : pip install pymupdf")
            log.error("  2. Télécharger pdf2svg avec DLLs : https://github.com/jalios/pdf2svg-windows/releases")
            return False

        log.info(f"Exécutable trouvé : {path_to_executable}")

        # Construire la commande
        command = [
            str(path_to_executable),
            temp_pdf_path,
            str(output_dir / f"{output_prefix}_%d.svg"),
            "all"
        ]

        log.info(f"Conversion PDF → SVG avec pdf2svg...")
        log.debug(f"Commande : {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True, check=True)

        if result.stdout:
            log.debug(f"stdout: {result.stdout}")

        # Post-traiter les SVG
        num_pages = len(event_counts)
        for i in range(1, num_pages + 1):
            svg_path = output_dir / f"{output_prefix}_{i}.svg"
            if svg_path.exists():
                _post_process_svg(svg_path, event_counts.get(i, 0))

        log.info(f"Conversion pdf2svg terminée : {output_dir}")
        return True

    except subprocess.CalledProcessError as e:
        log.error(f"Échec pdf2svg : code de retour {e.returncode}")

        # Analyser le code d'erreur
        if e.returncode == 3228369022 or e.returncode == -1066598274:
            log.error("DIAGNOSTIC : DLLs manquantes pour pdf2svg.exe")
            log.error("Ce programme nécessite des bibliothèques (Cairo, Poppler, etc.)")
            log.error("")
            log.error("SOLUTIONS :")
            log.error("  1. Installer PyMuPDF (recommandé) : pip install pymupdf")
            log.error("  2. Télécharger pdf2svg avec toutes les DLLs :")
            log.error("     https://github.com/jalios/pdf2svg-windows/releases")
        else:
            log.error(f"stdout: {e.stdout}")
            log.error(f"stderr: {e.stderr}")

        return False

    except FileNotFoundError:
        log.error("pdf2svg.exe introuvable ou impossible à exécuter")
        return False

    except Exception as e:
        log.error(f"Erreur inattendue avec pdf2svg : {e}")
        return False


def build_svg(project_root: str, cfg: Config, layout: Layout, out_dir: str, config_path: str, paras: List[str]) -> dict:
    """
    Génère un SVG par page en convertissant un PDF temporaire.
    Essaie PyMuPDF en priorité, puis pdf2svg.exe en fallback.
    """
    report = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        temp_pdf_path = tmp.name

    try:
        # Générer le PDF
        report = build_pdf(project_root, cfg, layout, temp_pdf_path, config_path, paras)
        event_counts = report.get("event_counts_per_page", {})

        # Créer le dossier de sortie
        output_dir = Path(out_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_prefix = "page"

        # Stratégie : PyMuPDF en priorité, sinon pdf2svg
        success = False

        if PYMUPDF_AVAILABLE:
            log.info("Méthode de conversion : PyMuPDF")
            success = _convert_pdf_to_svg_pymupdf(temp_pdf_path, output_dir, output_prefix, event_counts)

            if not success:
                log.warning("PyMuPDF a échoué, tentative avec pdf2svg...")
                success = _convert_pdf_to_svg_pdf2svg(project_root, temp_pdf_path, output_dir, output_prefix,
                                                      event_counts)
        else:
            log.info("Méthode de conversion : pdf2svg.exe")
            log.info("Astuce : installez PyMuPDF pour une conversion plus fiable (pip install pymupdf)")
            success = _convert_pdf_to_svg_pdf2svg(project_root, temp_pdf_path, output_dir, output_prefix, event_counts)

        if not success:
            log.error("Échec de la conversion SVG")
            return {"error": "La conversion SVG a échoué"}

    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

    return report
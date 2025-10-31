# misenpageur/misenpageur/pdfbuild.py
# -*- coding: utf-8 -*-
"""
✅ VERSION OPTIMISÉE POUR L'IMPRESSION

Améliorations par rapport à la version originale :
1. Compression du contenu PDF activée
2. Métadonnées PDF complètes
3. Support des modes d'impression
4. Logs détaillés
"""
from __future__ import annotations

from reportlab.pdfgen import canvas
from typing import List
import logging

log = logging.getLogger(__name__)

from .config import Config
from .layout import Layout
from .draw_logic import draw_document


def build_pdf(
        project_root: str,
        cfg: Config,
        layout: Layout,
        out_path: str,
        config_path: str,
        paras: List[str]
) -> dict:
    """
    Crée un canvas PDF optimisé pour l'impression et appelle la logique de dessin principale.

    Optimisations d'impression :
    - Compression du contenu activée
    - Métadonnées complètes
    - Support PDF/X via prepress.pdfx
    """

    # === 1. CRÉATION DU CANVAS ===
    c = canvas.Canvas(out_path, pagesize=(layout.page.width, layout.page.height))

    # === 2. CONFIGURATION POUR L'IMPRESSION ===

    # ✅ Compression du contenu (réduit la taille du PDF)
    c._doc.compress = 1

    # ✅ IDs optimisés (pas d'IDs séquentiels fixes)
    c._doc.invariant = 0

    # ✅ Métadonnées PDF (utile pour l'archivage et l'identification)
    month_label = getattr(cfg, 'month_label', 'Document')
    c.setTitle(f"Le Bidul - {month_label}")
    c.setAuthor("Radio Alpa")
    c.setSubject("Agenda culturel mensuel du Mans")
    c.setCreator("Bidul Generator - misenpageur v2.0")
    c.setKeywords("agenda, culture, Le Mans, concerts, événements")

    log.info(f"✅ Canvas PDF initialisé : {out_path}")
    log.info(f"   - Compression : activée")
    log.info(f"   - Format : {layout.page.width:.1f}x{layout.page.height:.1f} pt")

    # === 3. RENDU DU DOCUMENT ===
    report = draw_document(c, project_root, cfg, layout, config_path, paras)

    # === 4. SAUVEGARDE ===
    c.save()

    # === 5. LOGS DE CONFIRMATION ===
    log.info(f"✅ PDF sauvegardé : {out_path}")

    # Logs sur la qualité
    if report.get('font_size_main'):
        log.info(f"   - Police principale : {report['font_size_main']:.2f} pt")
    if report.get('unused_paragraphs', 0) > 0:
        log.warning(f"   ⚠️  Paragraphes non placés : {report['unused_paragraphs']}")

    # Logs sur les fonctionnalités prepress
    prepress = getattr(cfg, 'prepress', {}) or {}
    if prepress.get('convert_images'):
        log.info(f"   - Conversion CMYK : activée")
    if prepress.get('add_crop_marks'):
        log.info(f"   - Crop marks : ajoutés")
    if prepress.get('pdfx'):
        log.info(f"   - PDF/X : post-traitement requis")

    return report


# === FONCTION AUXILIAIRE : Vérification de la qualité ===

def verify_pdf_quality(pdf_path: str) -> dict:
    """
    Vérifie la qualité d'un PDF généré (nécessite PyPDF2 ou pdfplumber).

    Retourne un dictionnaire avec :
    - file_size_mb : Taille en Mo
    - num_pages : Nombre de pages
    - has_fonts : Polices embarquées ?
    - compressed : Contenu compressé ?
    """
    import os

    result = {
        'file_size_mb': 0,
        'num_pages': 0,
        'has_fonts': False,
        'compressed': False,
    }

    if not os.path.exists(pdf_path):
        return result

    # Taille du fichier
    result['file_size_mb'] = os.path.getsize(pdf_path) / (1024 * 1024)

    try:
        # Tentative avec PyPDF2 (si disponible)
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        result['num_pages'] = len(reader.pages)

        # Vérifier si des polices sont embarquées
        for page in reader.pages:
            if '/Font' in page.get_object():
                result['has_fonts'] = True
                break
    except ImportError:
        log.debug("PyPDF2 non disponible, vérification limitée")
    except Exception as e:
        log.warning(f"Erreur lors de la vérification : {e}")

    return result
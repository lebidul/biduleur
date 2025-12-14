# misenpageur/misenpageur/pdfbuild.py
# -*- coding: utf-8 -*-
"""
✅ VERSION OPTIMISÉE POUR L'IMPRESSION

Améliorations par rapport à la version originale :
1. Compression du contenu PDF activée
2. Métadonnées PDF complètes
3. Support des modes d'impression
4. Logs détaillés
5. Split PDF en pages individuelles (v1.4.5)
"""
from __future__ import annotations

from reportlab.pdfgen import canvas
from typing import List
import logging
import os

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


def split_pdf_pages(pdf_path: str, output_dir: str = None) -> List[str]:
    """
    Divise un PDF multi-pages en fichiers PDF individuels.

    Args:
        pdf_path: Chemin vers le PDF source
        output_dir: Dossier de sortie (défaut: même dossier que le PDF source)

    Returns:
        Liste des chemins des fichiers PDF créés

    Exemple:
        bidul.pdf -> bidul_page1.pdf, bidul_page2.pdf, bidul_page3.pdf
    """
    if not os.path.exists(pdf_path):
        log.error(f"Fichier PDF introuvable : {pdf_path}")
        return []

    try:
        import fitz  # PyMuPDF
    except ImportError:
        log.error("PyMuPDF (fitz) requis pour split_pdf_pages. Installez avec: pip install pymupdf")
        return []

    # Déterminer le dossier et le préfixe de sortie
    pdf_dir = os.path.dirname(pdf_path)
    pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]

    if output_dir is None:
        output_dir = pdf_dir

    os.makedirs(output_dir, exist_ok=True)

    created_files = []

    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)

        log.info(f"Splitting PDF : {num_pages} pages détectées")

        for page_num in range(num_pages):
            # Créer un nouveau document avec une seule page
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

            # Nom du fichier de sortie
            output_filename = f"{pdf_basename}_page{page_num + 1}.pdf"
            output_path = os.path.join(output_dir, output_filename)

            new_doc.save(output_path)
            new_doc.close()

            created_files.append(output_path)
            log.info(f"   ✅ Page {page_num + 1} -> {output_filename}")

        doc.close()

        log.info(f"Split terminé : {len(created_files)} fichiers créés dans {output_dir}")

    except Exception as e:
        log.error(f"Erreur lors du split PDF : {e}")

    return created_files
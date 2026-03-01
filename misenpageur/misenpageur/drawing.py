# misenpageur/misenpageur/drawing.py
# -*- coding: utf-8 -*-
import os
import io
import re
import xml.etree.ElementTree as ET
import qrcode
from typing import List

from PIL import Image  # Assurez-vous que Pillow (PIL) est importé
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import grey
from reportlab.pdfbase import pdfmetrics
from reportlab.graphics.renderSVG import SVGCanvas
import math
import rectpack
from rectpack import float2dec, PackerGlobal, PackerBFF, PackerBNF

import logging  # Ajouter cet import

log = logging.getLogger(__name__)  # Obtenir le logger pour ce module

# Support SVG pour les logos
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF

    SVGLIB_AVAILABLE = True
except ImportError:
    SVGLIB_AVAILABLE = False
    log.debug("svglib non disponible - les logos SVG seront ignorés")

from .fonts import register_arial
from .layout import Layout, Section
from .config import Config
from .utils import mm_to_pt

# Cache pour les images haute qualité chargées
# Clé: (chemin, largeur_pt, hauteur_pt, dpi), Valeur: ImageReader
_HIGH_QUALITY_IMAGE_CACHE: dict[tuple[str, float, float, int], ImageReader] = {}


def _load_high_quality_image(image_path: str, target_width_pt: float, target_height_pt: float, min_dpi: int = 300):
    """
    Charge une image avec optimisation pour la qualité d'impression.
    Utilise un cache pour éviter de recharger/redimensionner la même image.

    Args:
        image_path: Chemin vers l'image
        target_width_pt: Largeur cible en points
        target_height_pt: Hauteur cible en points
        min_dpi: Résolution minimale souhaitée (défaut: 300 DPI)

    Returns:
        ImageReader: Image optimisée prête pour ReportLab
    """
    # Arrondir les dimensions pour la clé de cache (éviter les variations mineures)
    cache_key = (image_path, round(target_width_pt, 1), round(target_height_pt, 1), min_dpi)

    if cache_key in _HIGH_QUALITY_IMAGE_CACHE:
        log.debug(f"Cache hit pour image: {image_path}")
        return _HIGH_QUALITY_IMAGE_CACHE[cache_key]

    img = Image.open(image_path)

    # Convertir en RGB si nécessaire
    if img.mode not in ('RGB', 'L'):
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert('RGB')

    # Calculer dimensions cibles en pixels pour le DPI souhaité
    target_width_px = int((target_width_pt / 72.0) * min_dpi)
    target_height_px = int((target_height_pt / 72.0) * min_dpi)

    img_width, img_height = img.size

    # Redimensionner si nécessaire avec LANCZOS pour la meilleure qualité
    if img_width < target_width_px or img_height < target_height_px:
        # Upscale si trop petit
        ratio = max(target_width_px / img_width, target_height_px / img_height)
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        log.debug(f"Upscaling: {img_width}x{img_height} → {new_width}x{new_height}px ({min_dpi} DPI)")
    elif img_width > target_width_px * 2 or img_height > target_height_px * 2:
        # Downscale si beaucoup trop grand (économie de taille de fichier)
        ratio = min(target_width_px / img_width, target_height_px / img_height)
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        log.debug(f"Downscaling: {img_width}x{img_height} → {new_width}x{new_height}px")

    result = ImageReader(img)
    _HIGH_QUALITY_IMAGE_CACHE[cache_key] = result
    return result


def clear_image_cache() -> None:
    """Vide le cache des images haute qualité. Utile entre plusieurs générations."""
    _HIGH_QUALITY_IMAGE_CACHE.clear()


def list_images(path: str, max_images: int = 100) -> List[str]:
    if not os.path.isdir(path):
        return []
    res = []
    for f in sorted(os.listdir(path)):
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
            res.append(os.path.join(path, f))
            if len(res) >= max_images:
                break
    return res


def paragraph_style(font_name: str, font_size: float, leading_ratio: float) -> ParagraphStyle:
    return ParagraphStyle(
        "base",
        fontName=font_name,
        fontSize=font_size,
        leading=font_size * leading_ratio,
    )


def draw_paragraph(c: canvas.Canvas, p: Paragraph, x: float, y: float):
    """
    Dessine un objet Paragraph sur le canvas, en s'adaptant s'il s'agit
    d'un SVGCanvas (qui ne supporte pas drawOn).
    """
    if not isinstance(c, SVGCanvas):
        # Méthode standard pour le PDF
        p.drawOn(c, x, y)
        return

    # --- Logique de secours pour le SVGCanvas ---
    # On dessine le texte ligne par ligne manuellement
    c.saveState()
    c.setFont(p.style.fontName, p.style.fontSize)
    c.setFillColor(p.style.textColor)

    y_pos = y + p.height  # On commence par le haut du paragraphe
    for line in p.blPara.lines:
        y_pos -= p.style.leading
        # Gérer l'alignement
        if p.style.alignment == TA_CENTER:
            c.drawCentredString(x + p.width / 2, y_pos, line.text)
        elif p.style.alignment == TA_RIGHT:
            c.drawRightString(x + p.width, y_pos, line.text)
        else:  # TA_LEFT
            c.drawString(x, y_pos, line.text)
    c.restoreState()


def _draw_ours_from_svg(c: canvas.Canvas, col_coords: tuple, cfg: Config):
    """
    Dessine l'ours depuis un fichier SVG pré-composé.
    Extrait et applique les hyperliens définis dans le SVG.
    """
    x, y, w, h = col_coords
    svg_path = getattr(cfg, 'ours_svg_file', '')
    project_root = getattr(cfg, 'project_root', '.')

    if svg_path and not os.path.isabs(svg_path):
        svg_path = os.path.join(project_root, svg_path)

    if not svg_path or not os.path.exists(svg_path):
        log.warning(f"SVG ours non trouvé: {svg_path}")
        return False

    if not SVGLIB_AVAILABLE:
        log.warning("svglib non disponible - impossible de charger le SVG ours")
        return False

    try:
        # 1. Extraire les liens AVANT le rendu
        links = _extract_svg_links(svg_path)

        # 2. Charger et dessiner le SVG
        drawing = svg2rlg(svg_path)
        if not drawing:
            log.warning(f"Impossible de charger le SVG: {svg_path}")
            return False

        # Calculer le scale pour remplir la box (remplir la hauteur)
        scale_x = w / drawing.width if drawing.width > 0 else 1
        scale_y = h / drawing.height if drawing.height > 0 else 1
        scale = scale_y  # Remplir la hauteur

        # Centrer dans la box
        scaled_w = drawing.width * scale
        scaled_h = drawing.height * scale
        offset_x = x + (w - scaled_w) / 2
        offset_y = y + (h - scaled_h) / 2

        # Dessiner le SVG avec clip
        c.saveState()
        clip_path = c.beginPath()
        clip_path.rect(x, y, w, h)
        c.clipPath(clip_path, stroke=0, fill=0)
        c.translate(offset_x, offset_y)
        c.scale(scale, scale)
        renderPDF.draw(drawing, c, 0, 0)
        c.restoreState()

        # 3. Ajouter les liens PDF avec les positions transformées
        for url, lx, ly, lw, lh in links:
            pdf_x = offset_x + lx * scale
            pdf_y = offset_y + ly * scale
            pdf_w = lw * scale
            pdf_h = lh * scale

            # Clipper le lien à la zone visible
            clip_x1, clip_y1 = x, y
            clip_x2, clip_y2 = x + w, y + h
            link_x1 = max(pdf_x, clip_x1)
            link_y1 = max(pdf_y, clip_y1)
            link_x2 = min(pdf_x + pdf_w, clip_x2)
            link_y2 = min(pdf_y + pdf_h, clip_y2)

            if link_x1 < link_x2 and link_y1 < link_y2:
                link_rect = (link_x1, link_y1, link_x2, link_y2)
                c.linkURL(url, link_rect, relative=0, thickness=0)
                log.debug(f"Lien PDF ours ajouté: {url[:40]}...")

        log.info(f"Ours SVG chargé depuis {os.path.basename(svg_path)} (scale={scale:.3f}, {len(links)} liens)")
        return True

    except Exception as e:
        log.warning(f"Erreur chargement SVG ours: {e}")
        return False


def _draw_ours_column(c: canvas.Canvas, col_coords: tuple, cfg: Config):
    """
    Dessine la colonne "ours" et adapte la position ET la taille de tous ses
    éléments en calculant un ratio d'échelle.
    """
    x_col, y_col, w_col, h_col = col_coords
    s1_cfg = cfg.section_1
    project_root = getattr(cfg, 'project_root', '.')

    # 1. Dimensions de référence (inchangées)
    REF_COL_WIDTH = 297.63 * 0.5
    REF_COL_HEIGHT = 420.94

    # 2. Ratios d'échelle (inchangés)
    scale_x = w_col / REF_COL_WIDTH if REF_COL_WIDTH > 0 else 1.0
    scale_y = h_col / REF_COL_HEIGHT if REF_COL_HEIGHT > 0 else 1.0

    # 3. Dessin du fond (SVG ou PNG)
    ours_layout = getattr(cfg, 'ours_layout', 'png')
    svg_drawn = False

    if ours_layout == 'svg':
        svg_drawn = _draw_ours_from_svg(c, col_coords, cfg)

    if not svg_drawn:
        # Fallback sur PNG ou mode PNG explicite
        bg_path = os.path.join(project_root, s1_cfg.get('ours_background_png', ''))
        if os.path.exists(bg_path):
            try:
                if not isinstance(c, SVGCanvas):
                    img_reader = _load_high_quality_image(bg_path, w_col, h_col, min_dpi=300)
                    c.drawImage(img_reader, x_col, y_col, width=w_col, height=h_col, preserveAspectRatio=True,
                                anchor='c',
                                mask='auto')
                else:
                    c.drawImage(bg_path, x_col, y_col, width=w_col, height=h_col, preserveAspectRatio=True, anchor='c',
                                mask='auto')
            except Exception as e:
                log.warning(f"Erreur chargement background ours: {e}")
                c.drawImage(bg_path, x_col, y_col, width=w_col, height=h_col, preserveAspectRatio=True, anchor='c',
                            mask='auto')

    # 4. Dessin du nom de l'auteur et de son lien (avec mise à l'échelle)
    auteur_text = getattr(cfg, 'auteur_couv', '')
    if auteur_text and 'auteur_pos_x_mm' in s1_cfg:
        # On met à l'échelle la police en se basant sur le ratio vertical (le plus contraignant)
        font_size = s1_cfg.get('auteur_font_size', 9) * scale_y
        font_name = s1_cfg.get('auteur_font_name', 'Helvetica')
        align = s1_cfg.get('auteur_align', 'center')

        ref_pos_x_pt = mm_to_pt(s1_cfg.get('auteur_pos_x_mm', 0))
        ref_pos_y_pt = mm_to_pt(s1_cfg.get('auteur_pos_y_mm', 0))

        # Ajustement vertical pour compenser la différence SVG/PNG
        auteur_offset_y_mm = s1_cfg.get('auteur_offset_y_mm', 0)
        offset_y_pt = mm_to_pt(auteur_offset_y_mm)

        abs_pos_x = x_col + (ref_pos_x_pt * scale_x)
        abs_pos_y = y_col + (ref_pos_y_pt * scale_y) + offset_y_pt

        c.setFont(font_name, font_size)
        c.setFillColorRGB(0, 0, 0)

        if align == 'center':
            c.drawCentredString(abs_pos_x, abs_pos_y, auteur_text)
        elif align == 'right':
            c.drawRightString(abs_pos_x, abs_pos_y, auteur_text)
        else:
            c.drawString(abs_pos_x, abs_pos_y, auteur_text)

        auteur_url = getattr(cfg, 'auteur_couv_url', '')
        if auteur_url:
            text_width = c.stringWidth(auteur_text, font_name, font_size)
            link_height = font_size * 1.2
            if align == 'center':
                x1 = abs_pos_x - (text_width / 2)
            elif align == 'right':
                x1 = abs_pos_x - text_width
            else:
                x1 = abs_pos_x
            y1 = abs_pos_y - (font_size * 0.2)
            link_rect = (x1, y1, x1 + text_width, y1 + link_height)
            c.linkURL(auteur_url, link_rect, relative=0, thickness=0)

    # 5. Dessin des rectangles de lien de l'ours (avec mise à l'échelle)
    ours_hyperlinks = s1_cfg.get('ours_hyperlinks', [])
    for link in ours_hyperlinks:
        if 'rect_mm' in link and 'href' in link:
            ref_x, ref_y, ref_w, ref_h = [mm_to_pt(v) for v in link['rect_mm']]

            rel_x = ref_x * scale_x
            rel_y = ref_y * scale_y
            link_w = ref_w * scale_x
            link_h = ref_h * scale_y

            abs_x1 = x_col + rel_x
            abs_y1 = y_col + rel_y
            abs_x2 = abs_x1 + link_w
            abs_y2 = abs_y1 + link_h

            c.linkURL(link['href'], (abs_x1, abs_y1, abs_x2, abs_y2), relative=0, thickness=0)

    # 6. Dessin du QR Code et de son titre (avec mise à l'échelle)
    qr_code_size_ref_pt = mm_to_pt(s1_cfg.get('qr_code_height_mm', 25))
    # La taille d'un carré doit être mise à l'échelle par le plus petit des deux ratios
    qr_scale = min(scale_x, scale_y)
    qr_code_size_pt = qr_code_size_ref_pt * qr_scale

    padding_ref_pt = mm_to_pt(2.5)
    # Le padding vertical est mis à l'échelle verticalement, etc.
    padding_x_pt = padding_ref_pt * scale_x
    padding_y_pt = padding_ref_pt * scale_y

    qr_x_pos = x_col + (w_col - qr_code_size_pt) / 2
    qr_y_pos = y_col + padding_y_pt

    # On utilise cfg.section_1 pour être cohérent
    qr_value = s1_cfg.get('qr_code_value', '')
    qr_style = s1_cfg.get('qr_code_style', 'standard')  # Options: standard, rounded, circles, gapped
    qr_color = s1_cfg.get('qr_code_color', '#000000')  # Couleur en hex

    # Convertir couleur hex en RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    try:
        front_color_rgb = hex_to_rgb(qr_color)
    except:
        front_color_rgb = (0, 0, 0)  # Noir par défaut

    qr_gen = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Haute correction pour meilleure qualité
        box_size=10,
        border=0
    )
    qr_gen.add_data(qr_value)
    qr_gen.make(fit=True)
    buffer = io.BytesIO()

    # Essayer d'utiliser les styles avancés si disponibles
    try:
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers import (
            RoundedModuleDrawer,
            CircleModuleDrawer,
            GappedSquareModuleDrawer
        )
        from qrcode.image.styles.colormasks import SolidFillColorMask

        # Sélectionner le style de module
        module_drawer = None
        if qr_style == 'rounded':
            module_drawer = RoundedModuleDrawer()
        elif qr_style == 'circles':
            module_drawer = CircleModuleDrawer()
        elif qr_style == 'gapped':
            module_drawer = GappedSquareModuleDrawer()

        if module_drawer:
            qr_img = qr_gen.make_image(
                image_factory=StyledPilImage,
                module_drawer=module_drawer,
                color_mask=SolidFillColorMask(
                    back_color=(255, 255, 255),
                    front_color=front_color_rgb
                )
            )
            log.info(f"QR code généré avec style '{qr_style}'")
        else:
            # Style standard avec couleur personnalisée
            qr_img = qr_gen.make_image(
                fill_color=f"#{front_color_rgb[0]:02x}{front_color_rgb[1]:02x}{front_color_rgb[2]:02x}",
                back_color="white"
            )
            log.info("QR code généré avec style standard")

        qr_img.save(buffer, format='PNG')

    except (ImportError, AttributeError) as e:
        # Fallback vers la méthode standard si les modules stylisés ne sont pas disponibles
        log.warning(f"Styles avancés QR code non disponibles: {e}")
        log.info("Utilisation du style QR code standard. Pour les styles avancés, installez: pip install qrcode[pil]")
        qr_gen.make_image(fill_color="black", back_color="white").save(buffer, format='PNG')

    buffer.seek(0)

    c.drawImage(ImageReader(buffer), qr_x_pos, qr_y_pos, width=qr_code_size_pt, height=qr_code_size_pt, mask='auto')

    title_text = s1_cfg.get('qr_code_title', "")
    if title_text:
        # La police est mise à l'échelle par le ratio vertical
        title_font_size = s1_cfg.get('qr_code_title_font_size', 9) * scale_y
        title_font_name = s1_cfg.get('qr_code_title_font_name', 'Helvetica-Bold')
        title_style = ParagraphStyle('OursTitle', fontName=title_font_name, fontSize=title_font_size,
                                     alignment=TA_CENTER)
        p = Paragraph(title_text, title_style)

        p_w, p_h = p.wrapOn(c, w_col, h_col)

        title_x_pos = x_col + (w_col - p_w) / 2
        # L'espacement est mis à l'échelle verticalement
        title_y_pos = qr_y_pos + qr_code_size_pt + (mm_to_pt(1) * scale_y)

        p.drawOn(c, title_x_pos, title_y_pos)


# --- FONCTION PRINCIPALE (ROUTEUR) ---


# =====================================================================
# FONCTIONS POUR EXTRACTION LIENS SVG
# =====================================================================

def _parse_svg_transform(transform_str: str):
    """
    Parse une chaîne de transformation SVG et retourne une matrice 2D.
    Supporte: translate, matrix, scale, rotate.

    Returns:
        tuple: (a, b, c, d, e, f) représentant la matrice:
               | a c e |
               | b d f |
               | 0 0 1 |
    """
    if not transform_str:
        return (1, 0, 0, 1, 0, 0)  # Identité

    # Matrice identité
    result = [1, 0, 0, 1, 0, 0]

    # Pattern pour extraire les transformations
    pattern = r'(translate|matrix|scale|rotate)\s*\(([^)]+)\)'

    for match in re.finditer(pattern, transform_str):
        func = match.group(1)
        values = [float(v.strip()) for v in re.split(r'[,\s]+', match.group(2).strip()) if v.strip()]

        if func == 'translate':
            tx = values[0] if len(values) > 0 else 0
            ty = values[1] if len(values) > 1 else 0
            # Multiplier: result = result * translate
            result[4] += tx * result[0] + ty * result[2]
            result[5] += tx * result[1] + ty * result[3]

        elif func == 'matrix':
            if len(values) >= 6:
                a, b, c, d, e, f = values[:6]
                # Multiplier les matrices
                new = [
                    result[0] * a + result[2] * b,
                    result[1] * a + result[3] * b,
                    result[0] * c + result[2] * d,
                    result[1] * c + result[3] * d,
                    result[0] * e + result[2] * f + result[4],
                    result[1] * e + result[3] * f + result[5]
                ]
                result = new

        elif func == 'scale':
            sx = values[0] if len(values) > 0 else 1
            sy = values[1] if len(values) > 1 else sx
            result[0] *= sx
            result[1] *= sx
            result[2] *= sy
            result[3] *= sy

    return tuple(result)


def _apply_transform(x, y, matrix):
    """Applique une matrice de transformation à un point."""
    a, b, c, d, e, f = matrix
    return (a * x + c * y + e, b * x + d * y + f)


def _multiply_matrices(m1, m2):
    """Multiplie deux matrices de transformation SVG."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1
    )


def _extract_images_from_svg(svg_path: str):
    """
    Extrait les images (avec données) et leurs liens depuis un fichier SVG.

    Note: Les images dans <defs> sont ignorées car ce sont des définitions
    réutilisables, pas des images affichées directement.

    Returns:
        list: [(image_data, url, original_width, original_height), ...]
        image_data peut être un chemin de fichier ou des données base64
    """
    import base64
    from io import BytesIO

    images = []

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        svg_dir = os.path.dirname(svg_path)

        def find_images(elem, current_url=None, in_defs=False):
            """Parcourt récursivement pour trouver les images."""
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            # Ignorer les éléments dans <defs> (définitions, pas affichés)
            if tag == 'defs':
                in_defs = True

            # Si c'est un lien, récupérer l'URL
            if tag == 'a':
                url = elem.get('{http://www.w3.org/1999/xlink}href') or elem.get('href', '')
                if url and not url.startswith('data:'):
                    current_url = url

            # Si c'est une image (et pas dans <defs>)
            if tag == 'image' and not in_defs:
                href = elem.get('{http://www.w3.org/1999/xlink}href') or elem.get('href', '')
                img_w = float(elem.get('width', '0').replace('mm', '').replace('px', ''))
                img_h = float(elem.get('height', '0').replace('mm', '').replace('px', ''))

                if href:
                    if href.startswith('data:'):
                        # Image embarquée en base64
                        try:
                            # Format: data:image/png;base64,XXXX
                            header, data = href.split(',', 1)
                            img_bytes = base64.b64decode(data)
                            images.append((BytesIO(img_bytes), current_url, img_w, img_h))
                        except Exception as e:
                            log.warning(f"Erreur décodage image base64: {e}")
                    else:
                        # Image externe (chemin relatif ou absolu)
                        if not os.path.isabs(href):
                            href = os.path.join(svg_dir, href)
                        if os.path.exists(href):
                            images.append((href, current_url, img_w, img_h))
                        else:
                            log.warning(f"Image non trouvée: {href}")

            # Parcourir les enfants
            for child in elem:
                find_images(child, current_url, in_defs)

        find_images(root)
        log.info(f"Extraction SVG: {len(images)} images trouvées (hors <defs>)")

    except Exception as e:
        log.warning(f"Erreur extraction images SVG: {e}")

    return images


def _extract_svg_links(svg_path: str):
    """
    Extrait les liens et leurs bounding boxes depuis un fichier SVG.

    Returns:
        list: [(url, x, y, width, height), ...] en points (coordonnées PDF)
    """
    MM_TO_PT = 2.834645
    links = []

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()

        # Récupérer viewBox pour les dimensions (en mm pour Inkscape)
        viewbox = root.get('viewBox', '').split()
        svg_height_mm = float(viewbox[3]) if len(viewbox) >= 4 else float(root.get('height', '100').replace('mm', ''))
        svg_height_pt = svg_height_mm * MM_TO_PT

        def get_transform(elem):
            """Récupère la transformation d'un élément."""
            t = elem.get('transform', '')
            return _parse_svg_transform(t)

        def find_links(elem, parent_matrix=(1, 0, 0, 1, 0, 0)):
            """Parcourt récursivement pour trouver les liens."""
            # Calculer la matrice cumulée
            local_matrix = get_transform(elem)
            current_matrix = _multiply_matrices(parent_matrix, local_matrix)

            # Tag sans namespace
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            if tag == 'a':
                # Récupérer l'URL
                url = elem.get('{http://www.w3.org/1999/xlink}href') or elem.get('href', '')

                if url and not url.startswith('data:'):
                    # Chercher l'image enfant
                    for child in elem:
                        child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                        if child_tag == 'image':
                            # Récupérer les attributs de l'image
                            child_matrix = _multiply_matrices(current_matrix, get_transform(child))

                            img_x = float(child.get('x', 0))
                            img_y = float(child.get('y', 0))
                            img_w = float(child.get('width', 0))
                            img_h = float(child.get('height', 0))

                            # Appliquer la transformation aux coins (coordonnées en mm)
                            x1, y1 = _apply_transform(img_x, img_y, child_matrix)
                            x2, y2 = _apply_transform(img_x + img_w, img_y + img_h, child_matrix)

                            # Normaliser (en cas de scale négatif)
                            final_x_mm = min(x1, x2)
                            final_y_mm = min(y1, y2)
                            final_w_mm = abs(x2 - x1)
                            final_h_mm = abs(y2 - y1)

                            # Convertir mm → points
                            final_x_pt = final_x_mm * MM_TO_PT
                            final_w_pt = final_w_mm * MM_TO_PT
                            final_h_pt = final_h_mm * MM_TO_PT

                            # Inverser Y pour PDF (SVG: origine en haut, PDF: origine en bas)
                            final_y_pt = svg_height_pt - (final_y_mm * MM_TO_PT) - final_h_pt

                            links.append((url, final_x_pt, final_y_pt, final_w_pt, final_h_pt))
                            log.debug(
                                f"Lien extrait: {url[:50]}... @ ({final_x_pt:.1f}, {final_y_pt:.1f}, {final_w_pt:.1f}x{final_h_pt:.1f})")
                            break

            # Parcourir les enfants
            for child in elem:
                find_links(child, current_matrix)

        find_links(root)
        log.info(f"Extraction SVG: {len(links)} liens trouvés")

    except Exception as e:
        log.warning(f"Erreur extraction liens SVG: {e}")

    return links


def _draw_logos_from_svg(c: canvas.Canvas, col_coords: tuple, cfg: Config, fill_height: bool = False):
    """
    Dessine les logos depuis un fichier SVG pré-composé.
    Extrait et applique les hyperliens définis dans le SVG.

    Args:
        c: Canvas ReportLab
        col_coords: (x, y, w, h) de la zone
        cfg: Configuration
        fill_height: Si True, scale pour remplir la hauteur (sinon garde aspect ratio)
    """
    x, y, w, h = col_coords
    svg_path = getattr(cfg, 'logos_svg_file', '')
    project_root = getattr(cfg, 'project_root', '.')

    if svg_path and not os.path.isabs(svg_path):
        svg_path = os.path.join(project_root, svg_path)

    if not svg_path or not os.path.exists(svg_path):
        log.warning(f"SVG logos non trouvé: {svg_path}")
        return

    if not SVGLIB_AVAILABLE:
        log.warning("svglib non disponible - impossible de charger le SVG logos")
        return

    try:
        # 1. Extraire les liens AVANT le rendu
        links = _extract_svg_links(svg_path)

        # 2. Charger et dessiner le SVG
        drawing = svg2rlg(svg_path)
        if not drawing:
            log.warning(f"Impossible de charger le SVG: {svg_path}")
            return

        # Calculer le scale pour remplir la box
        scale_x = w / drawing.width if drawing.width > 0 else 1
        scale_y = h / drawing.height if drawing.height > 0 else 1

        # Option pour forcer le remplissage en hauteur
        force_fill_height = getattr(cfg, 'logos_svg_fill_height', False)

        if fill_height or force_fill_height:
            # Remplir la hauteur (centré horizontalement, peut être croppé)
            scale = scale_y
        else:
            # Garder l'aspect ratio (comportement par défaut)
            scale = min(scale_x, scale_y)

        # Centrer dans la box
        scaled_w = drawing.width * scale
        scaled_h = drawing.height * scale
        offset_x = x + (w - scaled_w) / 2
        offset_y = y + (h - scaled_h) / 2

        # Dessiner le SVG
        c.saveState()

        # Si fill_height, ajouter un clip pour éviter le débordement
        if fill_height or force_fill_height:
            # Créer un rectangle de clip sur la zone autorisée
            clip_path = c.beginPath()
            clip_path.rect(x, y, w, h)
            c.clipPath(clip_path, stroke=0, fill=0)

        c.translate(offset_x, offset_y)
        c.scale(scale, scale)
        renderPDF.draw(drawing, c, 0, 0)
        c.restoreState()

        # 3. Ajouter les liens PDF avec les positions transformées
        for url, lx, ly, lw, lh in links:
            # Appliquer le scale et l'offset aux coordonnées du lien
            pdf_x = offset_x + lx * scale
            pdf_y = offset_y + ly * scale
            pdf_w = lw * scale
            pdf_h = lh * scale

            # Clipper le lien à la zone visible si fill_height
            if fill_height or force_fill_height:
                # Bornes de la zone
                clip_x1, clip_y1 = x, y
                clip_x2, clip_y2 = x + w, y + h

                # Ajuster le rectangle du lien
                link_x1 = max(pdf_x, clip_x1)
                link_y1 = max(pdf_y, clip_y1)
                link_x2 = min(pdf_x + pdf_w, clip_x2)
                link_y2 = min(pdf_y + pdf_h, clip_y2)

                # Ignorer si le lien est complètement hors zone
                if link_x1 >= link_x2 or link_y1 >= link_y2:
                    continue

                link_rect = (link_x1, link_y1, link_x2, link_y2)
            else:
                link_rect = (pdf_x, pdf_y, pdf_x + pdf_w, pdf_y + pdf_h)

            c.linkURL(url, link_rect, relative=0, thickness=0)
            log.debug(f"Lien PDF ajouté: {url[:40]}... @ rect{link_rect}")

        log.info(f"Logos SVG chargés depuis {os.path.basename(svg_path)} (scale={scale:.3f}, {len(links)} liens)")

    except Exception as e:
        log.warning(f"Erreur chargement SVG logos: {e}")


# =====================================================================
# FONCTIONS HELPER POUR SUPPORT SVG
# =====================================================================

def _load_and_measure_logo(logo_path: str):
    """
    Charge un logo (PNG, JPG ou SVG) et retourne ses dimensions.

    Args:
        logo_path: Chemin vers le fichier logo

    Returns:
        tuple: (image_object, width, height, is_svg)
            - image_object: ImageReader ou Drawing selon le type
            - width, height: Dimensions en points
            - is_svg: True si c'est un SVG
    """
    ext = os.path.splitext(logo_path)[1].lower()

    if ext == '.svg':
        if not SVGLIB_AVAILABLE:
            log.warning(f"SVG ignoré (svglib non disponible): {os.path.basename(logo_path)}")
            return (None, 0, 0, False)

        try:
            drawing = svg2rlg(logo_path)
            if drawing is None:
                log.warning(f"Impossible de charger le SVG: {os.path.basename(logo_path)}")
                return (None, 0, 0, False)

            # Obtenir dimensions natives
            width = drawing.width
            height = drawing.height

            log.debug(f"Logo SVG chargé: {os.path.basename(logo_path)} ({width:.1f}x{height:.1f}pt)")
            return (drawing, width, height, True)

        except Exception as e:
            log.warning(f"Erreur chargement SVG {os.path.basename(logo_path)}: {e}")
            return (None, 0, 0, False)
    else:
        # PNG/JPG - code existant
        try:
            img_reader = ImageReader(logo_path)
            img_w, img_h = img_reader.getSize()
            return (img_reader, img_w, img_h, False)
        except Exception as e:
            log.warning(f"Erreur chargement image {os.path.basename(logo_path)}: {e}")
            return (None, 0, 0, False)


def _draw_logo_at_position(c: canvas.Canvas, logo_obj, logo_x, logo_y, w_fit, h_fit, is_svg):
    """
    Dessine un logo (SVG ou bitmap) à la position spécifiée.

    Args:
        c: Canvas ReportLab
        logo_obj: ImageReader (bitmap) ou Drawing (SVG)
        logo_x, logo_y: Position en points
        w_fit, h_fit: Dimensions cibles en points
        is_svg: True si c'est un SVG
    """
    if is_svg and logo_obj:
        # Dessin SVG
        native_w = logo_obj.width
        native_h = logo_obj.height

        if native_w == 0 or native_h == 0:
            log.warning("SVG avec dimensions nulles, ignoré")
            return

        scale_x = w_fit / native_w
        scale_y = h_fit / native_h

        # Sauvegarder l'état et appliquer transformation
        c.saveState()
        c.translate(logo_x, logo_y)
        c.scale(scale_x, scale_y)

        try:
            renderPDF.draw(logo_obj, c, 0, 0)
        except Exception as e:
            log.warning(f"Erreur rendu SVG: {e}")

        c.restoreState()
    else:
        # Dessin bitmap (code existant)
        kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
        c.drawImage(logo_obj, logo_x, logo_y, width=w_fit, height=h_fit, **kwargs)


def _draw_logos_column(c: canvas.Canvas, col_coords: tuple, logos: List[str], cfg: Config):
    """
    Gère la colonne des logos : dessine d'abord la cucaracha_box si elle existe,
    puis utilise l'espace restant pour dessiner les logos avec la méthode choisie.
    """
    x, y, w, h = col_coords

    # 1. Vérifier et calculer la hauteur de la cucaracha_box
    c_cfg = getattr(cfg, "cucaracha_box", {}) or {}
    content_type = c_cfg.get("content_type", "none")
    content_value = c_cfg.get("content_value", "")

    cucaracha_h = 0
    if content_type != "none":
        cucaracha_h = c_cfg.get("height_mm", 35) * mm

    # 2. Définir les zones pour les logos et la cucaracha_box
    logo_zone_h = h - cucaracha_h
    # La zone des logos est en haut, la cucaracha en bas
    logo_zone_coords = (x, y + cucaracha_h, w, logo_zone_h)

    # 3. Dessiner la cucaracha_box si nécessaire
    if cucaracha_h > 0:
        cucaracha_box_coords = (x, y, w, cucaracha_h)
        _draw_cucaracha_box(c, cucaracha_box_coords, cfg)
        # On ajoute une petite marge entre les deux zones
        logo_zone_h -= (2 * mm)  # Marge de 2mm
        logo_zone_coords = (x, y + cucaracha_h + (2 * mm), w, logo_zone_h)

    # 4. Appeler la bonne fonction de dessin pour la zone des logos
    layout_type = getattr(cfg, "logos_layout", "colonnes")
    if layout_type == "svg" and logo_zone_h > 0:
        # Layout depuis fichier SVG pré-composé
        # Si pas de cucaracha_box, remplir toute la hauteur
        fill_height = (cucaracha_h == 0)
        _draw_logos_from_svg(c, logo_zone_coords, cfg, fill_height=fill_height)
    elif layout_type == "optimise" and logos and logo_zone_h > 0:
        # On passe cfg pour lire la stratégie de packing
        _draw_logos_optimized(c, logo_zone_coords, logos, cfg)
    elif logo_zone_h > 0:
        _draw_logos_two_columns(c, logo_zone_coords, logos, cfg)


def _draw_logos_two_columns(c: canvas.Canvas, col_coords: tuple, logos: List[str], cfg: Config):
    """Dessine les logos sur 2 colonnes fixes dans l'espace fourni."""
    zone_x, zone_y, zone_w, zone_h = col_coords

    if not logos or zone_h <= 0: return

    # 1. Créer le dictionnaire de recherche pour les liens (identique à l'autre fonction)
    links_map = {os.path.basename(link.get('image', '')): link.get('href')
                 for link in getattr(cfg, 'logo_hyperlinks', [])}

    num_logos = len(logos)
    cols, rows = 2, (num_logos + 1) // 2
    if rows == 0: return

    cell_w, cell_h = zone_w / cols, zone_h / rows
    padding = 1 * mm

    for i, logo_path in enumerate(logos):
        row = rows - 1 - (i // cols)
        col = i % cols
        cell_x, cell_y = zone_x + col * cell_w, zone_y + row * cell_h

        try:
            # Charger logo (SVG ou bitmap)
            logo_obj, img_w, img_h, is_svg = _load_and_measure_logo(logo_path)
            if not logo_obj:
                continue

            # Calculer fit (identique pour SVG et bitmap)
            aspect = img_h / img_w if img_w > 0 else 1

            w_fit = cell_w - (2 * padding)
            h_fit = w_fit * aspect
            if h_fit > cell_h - (2 * padding):
                h_fit = cell_h - (2 * padding)
                w_fit = h_fit / aspect

            logo_x = cell_x + (cell_w - w_fit) / 2
            logo_y = cell_y + (cell_h - h_fit) / 2

            # Dessiner (SVG ou bitmap)
            _draw_logo_at_position(c, logo_obj, logo_x, logo_y, w_fit, h_fit, is_svg)

            # Ajouter hyperlink si présent (identique pour SVG et bitmap)
            logo_basename = os.path.basename(logo_path)
            url = links_map.get(logo_basename)

            if url:
                link_rect = (logo_x, logo_y, logo_x + w_fit, logo_y + h_fit)
                c.linkURL(url, link_rect, relative=0, thickness=0)
                log.info(f"Lien créé pour '{logo_basename}' vers '{url}'")

        except Exception as e:
            log.warning(f"Erreur avec le logo {os.path.basename(logo_path)}: {e}")


def _draw_logos_optimized(c: canvas.Canvas, col_coords: tuple, logo_paths: List[str], cfg: Config):
    """
    Dessine les logos en utilisant une stratégie de packing et de tri
    configurable pour un meilleur contrôle esthétique.
    """
    x_offset, y_offset, w, h = col_coords
    if not logo_paths or w <= 0 or h <= 0: return

    # On lit la marge depuis l'objet de configuration
    padding_mm = getattr(cfg, 'logos_padding_mm', 1.0)
    padding_pt = mm_to_pt(padding_mm)

    logos_data = []
    for path in logo_paths:
        try:
            # Charger logo (SVG ou bitmap) pour obtenir ses dimensions
            logo_obj, img_w, img_h, is_svg = _load_and_measure_logo(path)
            if logo_obj and img_w > 0 and img_h > 0:
                # Pour le packing, on utilise les dimensions natives
                logos_data.append({
                    'path': path,
                    'w': img_w,
                    'h': img_h,
                    'ratio': img_h / img_w,
                    'is_svg': is_svg,
                    'obj': logo_obj  # Garder l'objet pour le dessin
                })
        except Exception as e:
            log.debug(f"Logo ignoré dans packing: {os.path.basename(path)} - {e}")
            pass
    if not logos_data: return

    # 1. Lire la stratégie directement depuis l'objet config
    strategy = cfg.packing_strategy
    algo_choice = strategy.algorithm
    sort_choice = strategy.sort_algo

    # Recherche binaire de la surface optimale
    min_area, max_area = 1.0, w * h
    best_placements = None

    for _ in range(15):
        test_area = (min_area + max_area) / 2
        if test_area < 1: break

        # 2. Choisir le bon algorithme et FORCER rotation=False
        if algo_choice == 'BFF':
            packer = PackerBFF(rotation=False)
        elif algo_choice == 'BNF':
            packer = PackerBNF(rotation=False)
        else:
            packer = PackerGlobal(rotation=False)

        packer.add_bin(w, h)

        can_pack_all = True
        rectangles_to_add = []
        for logo in logos_data:
            rect_w = math.sqrt(test_area / logo['ratio'])
            rect_h = rect_w * logo['ratio']
            padded_w = rect_w + (2 * padding_pt)
            padded_h = rect_h + (2 * padding_pt)

            if padded_w > w or padded_h > h:
                can_pack_all = False
                break
            rectangles_to_add.append({'w': padded_w, 'h': padded_h, 'rid': logo['path']})

        if not can_pack_all:
            max_area = test_area
            continue

        # 3. Appliquer la bonne méthode de tri
        if sort_choice == 'AREA':
            rectangles_to_add.sort(key=lambda r: r['w'] * r['h'], reverse=True)
        elif sort_choice == 'HEIGHT':
            rectangles_to_add.sort(key=lambda r: r['h'], reverse=True)
        elif sort_choice == 'WIDTH':
            rectangles_to_add.sort(key=lambda r: r['w'], reverse=True)
        else:  # MAXSIDE (défaut)
            rectangles_to_add.sort(key=lambda r: max(r['w'], r['h']), reverse=True)

        for r in rectangles_to_add:
            packer.add_rect(r['w'], r['h'], rid=r['rid'])
        packer.pack()

        if len(packer[0]) == len(logos_data):
            best_placements = packer[0]
            min_area = test_area
        else:
            max_area = test_area

    if not best_placements:
        log.warning(f"Aucune solution de packing n'a pu être trouvée.")
        _draw_logos_two_columns(c, col_coords, logo_paths, Config())
        return

    # 4. Créer un dictionnaire de recherche pour un accès rapide aux liens
    #    (plus efficace qu'une recherche dans une boucle)
    links_map = {os.path.basename(link.get('image', '')): link.get('href')
                 for link in getattr(cfg, 'logo_hyperlinks', [])}

    # 5. Dessiner les logos en utilisant la surface optimale et les positions trouvées
    final_area = min_area

    for rect in best_placements:
        logo_path = rect.rid
        logo_data = next(l for l in logos_data if l['path'] == logo_path)
        logo_ratio = logo_data['ratio']

        # Calculer la taille finale à partir de la surface optimale.
        # C'est la garantie que tous les logos auront la même surface et le bon ratio.
        final_w = math.sqrt(final_area / logo_ratio)
        final_h = final_w * logo_ratio

        # Positionner le logo à l'intérieur de la boîte que le packer a trouvée.
        logo_x = x_offset + float(rect.x) + padding_pt
        logo_y = y_offset + float(rect.y) + padding_pt

        try:
            # Récupérer l'objet logo et son type depuis logo_data
            is_svg = logo_data.get('is_svg', False)
            logo_obj = logo_data.get('obj')

            if logo_obj:
                _draw_logo_at_position(c, logo_obj, logo_x, logo_y, final_w, final_h, is_svg)
            else:
                # Fallback si l'objet n'est pas disponible
                log.warning(f"Objet logo non disponible pour {os.path.basename(logo_path)}")
        except Exception as e:
            log.warning(f"Erreur avec le logo {os.path.basename(logo_path)} lors du dessin: {e}")

        # 3. Vérifier si un lien existe pour ce logo et le dessiner
        logo_basename = os.path.basename(logo_path)
        url = links_map.get(logo_basename)

        if url:
            # Créer le rectangle pour le lien invisible
            link_rect = (logo_x, logo_y, logo_x + final_w, logo_y + final_h)
            c.linkURL(url, link_rect, relative=0, thickness=0)
            log.info(f"Lien créé pour '{logo_basename}' vers '{url}'")


def draw_s1(c: canvas.Canvas, S1_coords, logos: List[str], cfg: Config, lay: Layout):
    """
    Divise la section S1 et passe les coordonnées absolues de chaque
    colonne aux fonctions de dessin respectives.
    """
    register_arial()
    x_sec, y_sec, w_sec, h_sec = S1_coords.x, S1_coords.y, S1_coords.w, S1_coords.h

    # Calcul de la division des deux colonnes (inchangé)
    split_ratio = lay.s1_split.get('logos_ratio', 0.5)
    logos_col_width = w_sec * split_ratio
    ours_col_width = w_sec - logos_col_width

    # Calcul des coordonnées absolues de chaque colonne sur la page
    logos_col_coords = (x_sec, y_sec, logos_col_width, h_sec)
    ours_col_coords = (x_sec + logos_col_width, y_sec, ours_col_width, h_sec)

    # On passe ces coordonnées absolues aux fonctions de dessin
    _draw_logos_column(c, logos_col_coords, logos, cfg)
    _draw_ours_column(c, ours_col_coords, cfg)


def draw_s2_cover(c: canvas.Canvas, S2_coords, image_path: str, inner_pad: float):
    """
    Dessine l'image de couverture avec haute qualité (300 DPI minimum).
    """
    x, y, w, h = S2_coords.x, S2_coords.y, S2_coords.w, S2_coords.h

    if not image_path or not os.path.exists(image_path):
        c.saveState()
        c.setStrokeColor(grey)
        c.rect(x, y, w, h, stroke=1, fill=0)
        c.setFont("Helvetica", 12)
        c.drawCentredString(x + w / 2, y + h / 2, "(Image de couverture absente)")
        c.restoreState()
        return

    # Pour SVG, comportement original
    if isinstance(c, SVGCanvas):
        image_to_draw = Image.open(image_path)
        c.drawImage(image_to_draw, x, y, w, h, preserveAspectRatio=True, anchor='c')
        return

    # Pour PDF : optimisation haute qualité avec fonction helper
    try:
        img_reader = _load_high_quality_image(image_path, w, h, min_dpi=300)
        c.drawImage(img_reader, x, y, w, h, preserveAspectRatio=True, anchor='c', mask='auto')
        log.debug(f"Image de couverture insérée: {w:.1f}x{h:.1f}pt (300 DPI)")
    except Exception as e:
        log.error(f"Erreur lors du chargement de l'image de couverture: {e}")
        # Fallback: méthode originale (seulement si le fichier existe)
        if os.path.exists(image_path):
            c.drawImage(image_path, x, y, w, h, preserveAspectRatio=True, anchor='c', mask='auto')
        else:
            log.warning(f"Image de couverture introuvable : {image_path}")


def draw_poster_logos(c: canvas.Canvas, s_coords: Section, logos: List[str], cfg: Config = None):
    """
    Dessine les logos des partenaires en ligne horizontale pour le poster.
    Si logos_layout == 'svg', extrait les images du SVG et les redispose horizontalement.
    """
    from io import BytesIO

    x, y, w, h = s_coords.x, s_coords.y, s_coords.w, s_coords.h
    if not w > 0 or not h > 0: return

    # Mode SVG : extraire les images et les redisposer horizontalement
    layout_type = getattr(cfg, "logos_layout", "colonnes") if cfg else "colonnes"
    if layout_type == "svg" and cfg:
        svg_path = getattr(cfg, 'logos_svg_file', '')
        project_root = getattr(cfg, 'project_root', '.')

        if svg_path and not os.path.isabs(svg_path):
            svg_path = os.path.join(project_root, svg_path)

        if svg_path and os.path.exists(svg_path):
            # Extraire les images du SVG
            svg_images = _extract_images_from_svg(svg_path)

            if svg_images:
                num_logos = len(svg_images)
                cell_w = w / num_logos
                padding = 2

                for i, (img_data, url, orig_w, orig_h) in enumerate(svg_images):
                    cell_x = x + i * cell_w
                    try:
                        # Charger l'image
                        if isinstance(img_data, BytesIO):
                            # Image base64
                            img_data.seek(0)
                            pil_img = Image.open(img_data)
                            img_w, img_h = pil_img.size
                        elif isinstance(img_data, str) and os.path.exists(img_data):
                            # Fichier externe
                            pil_img = Image.open(img_data)
                            img_w, img_h = pil_img.size
                        else:
                            continue

                        # Calculer dimensions avec aspect ratio
                        aspect = img_h / img_w if img_w > 0 else 1

                        box_w = cell_w - (2 * padding)
                        box_h = h - (2 * padding)
                        w_fit = box_w
                        h_fit = w_fit * aspect
                        if h_fit > box_h:
                            h_fit = box_h
                            w_fit = h_fit / aspect

                        logo_x = cell_x + (cell_w - w_fit) / 2
                        logo_y = y + (h - h_fit) / 2

                        # Dessiner l'image
                        if isinstance(c, SVGCanvas):
                            c.drawImage(pil_img, logo_x, logo_y, width=w_fit, height=h_fit)
                        else:
                            # Convertir en ImageReader pour PDF
                            if isinstance(img_data, BytesIO):
                                img_data.seek(0)
                                img_reader = ImageReader(img_data)
                            else:
                                img_reader = ImageReader(img_data)
                            c.drawImage(img_reader, logo_x, logo_y, width=w_fit, height=h_fit, mask='auto')

                        # Ajouter hyperlink si présent
                        if url:
                            link_rect = (logo_x, logo_y, logo_x + w_fit, logo_y + h_fit)
                            c.linkURL(url, link_rect, relative=0, thickness=0)
                            log.debug(f"Lien poster créé: {url[:40]}...")

                    except Exception as e:
                        log.warning(f"Erreur logo poster depuis SVG: {e}")

                log.info(f"Poster: {num_logos} logos extraits du SVG et disposés horizontalement")
                return  # Fin du mode SVG

    # Mode classique : dessiner les logos individuels
    if not logos: return

    # Récupérer les hyperlinks depuis cfg si disponible
    links_map = {}
    if cfg:
        links_map = {os.path.basename(link.get('image', '')): link.get('href')
                     for link in getattr(cfg, 'logo_hyperlinks', [])}

    num_logos = len(logos)
    cell_w = w / num_logos
    padding = 2

    for i, logo_path in enumerate(logos):
        cell_x = x + i * cell_w
        try:
            # Charger logo (SVG ou bitmap)
            logo_obj, img_w, img_h, is_svg = _load_and_measure_logo(logo_path)
            if not logo_obj:
                continue

            # Calculer dimensions avec aspect ratio
            aspect = img_h / img_w if img_w > 0 else 1

            box_w = cell_w - (2 * padding)
            box_h = h - (2 * padding)
            w_fit = box_w
            h_fit = w_fit * aspect
            if h_fit > box_h:
                h_fit = box_h
                w_fit = h_fit / aspect

            logo_x = cell_x + (cell_w - w_fit) / 2
            logo_y = y + (h - h_fit) / 2

            # Dessiner (SVG ou bitmap avec haute qualité)
            if is_svg:
                _draw_logo_at_position(c, logo_obj, logo_x, logo_y, w_fit, h_fit, True)
            else:
                # Pour bitmap : utiliser haute qualité si pas SVGCanvas
                if isinstance(c, SVGCanvas):
                    c.drawImage(logo_obj, logo_x, logo_y, width=w_fit, height=h_fit)
                else:
                    img_reader_hq = _load_high_quality_image(logo_path, w_fit, h_fit, min_dpi=300)
                    c.drawImage(img_reader_hq, logo_x, logo_y, width=w_fit, height=h_fit, mask='auto')

            # Ajouter hyperlink si présent
            logo_basename = os.path.basename(logo_path)
            url = links_map.get(logo_basename)
            if url:
                link_rect = (logo_x, logo_y, logo_x + w_fit, logo_y + h_fit)
                c.linkURL(url, link_rect, relative=0, thickness=0)

        except Exception as e:
            log.warning(f"Impossible de dessiner le logo du poster {os.path.basename(logo_path)}: {e}")


def _draw_cucaracha_box(c: canvas.Canvas, box_coords: tuple, cfg: Config):
    x, y, w, h = box_coords
    c_cfg = cfg.cucaracha_box
    content_type = c_cfg.get("content_type", "none")
    content_value = c_cfg.get("content_value", ".")

    if content_type == "none": return

    # --- IMAGE EN BACKGROUND (dessinée AVANT le titre) ---
    if content_type == "image":
        if os.path.exists(content_value):
            try:
                if isinstance(c, SVGCanvas):
                    image_to_draw = Image.open(content_value)
                else:
                    image_to_draw = ImageReader(content_value)

                # Image couvre toute la box (pas de padding)
                kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
                c.drawImage(image_to_draw, x, y, width=w, height=h,
                            preserveAspectRatio=True, anchor='c', **kwargs)
            except Exception as e:
                log.warning(f"Erreur avec l'image de la Cucaracha Box : {e}")

    # --- TITRE (toujours par-dessus) ---
    title = c_cfg.get("title", "Cucaracha")
    if title:
        c.saveState()
        title_style = ParagraphStyle('CucarachaTitle',
                                     fontName=c_cfg.get("title_font_name", "Arial-Italic"),
                                     fontSize=c_cfg.get("title_font_size", 8),
                                     leading=c_cfg.get("title_font_size", 8) * 1.2,
                                     underline=1)
        title_p = Paragraph(title, title_style)
        title_w, title_h = title_p.wrapOn(c, w - 4, h)
        title_p.drawOn(c, x + 2, y + h - title_h - 2)
        c.restoreState()

    # --- TEXTE (si content_type == "text") ---
    if content_type == "text":
        padding = 2 * mm
        title_h = c_cfg.get("title_font_size", 8) * 1.2 + 4  # Approximation hauteur titre
        content_x, content_y = x + padding, y + padding
        content_w, content_h = w - (2 * padding), h - title_h - (2 * padding)

        font_name = c_cfg.get("text_font_name", "Arial")
        try:
            font_size = float(c_cfg.get("text_font_size", 10))
        except (ValueError, TypeError):
            font_size = 10.0

        text_content = content_value.replace('\n', '<br/>')
        if c_cfg.get("text_style", "normal") == "italic":
            text_content = f"<i>{text_content}</i>"

        align_map = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}
        alignment = align_map.get(c_cfg.get("text_align", "center"), TA_CENTER)

        text_style = ParagraphStyle(
            'CucarachaText',
            fontName=font_name,
            fontSize=font_size,
            leading=font_size * 1.3,
            alignment=alignment
        )
        story = [Paragraph(text_content, text_style)]
        frame = Frame(content_x, content_y, content_w, content_h, showBoundary=0)
        frame.addFromList(story, c)
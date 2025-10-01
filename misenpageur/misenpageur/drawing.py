# misenpageur/misenpageur/drawing.py
# -*- coding: utf-8 -*-
import os
import io
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

import logging # Ajouter cet import
log = logging.getLogger(__name__) # Obtenir le logger pour ce module

from .fonts import register_arial
from .layout import Layout, Section
from .config import Config
from .utils import mm_to_pt


def list_images(path: str, max_images: int = 100) -> List[str]:
    if not os.path.isdir(path):
        return []
    res = []
    for f in sorted(os.listdir(path)):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
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

    y_pos = y + p.height # On commence par le haut du paragraphe
    for line in p.blPara.lines:
        y_pos -= p.style.leading
        # Gérer l'alignement
        if p.style.alignment == TA_CENTER:
            c.drawCentredString(x + p.width / 2, y_pos, line.text)
        elif p.style.alignment == TA_RIGHT:
            c.drawRightString(x + p.width, y_pos, line.text)
        else: # TA_LEFT
            c.drawString(x, y_pos, line.text)
    c.restoreState()


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

    # 3. Dessin de l'image de fond (inchangé)
    bg_path = os.path.join(project_root, s1_cfg.get('ours_background_png', ''))
    if os.path.exists(bg_path):
        c.drawImage(bg_path, x_col, y_col, width=w_col, height=h_col, preserveAspectRatio=True, anchor='c', mask='auto')

    # 4. Dessin du nom de l'auteur et de son lien (avec mise à l'échelle)
    auteur_text = getattr(cfg, 'auteur_couv', '')
    if auteur_text and 'auteur_pos_x_mm' in s1_cfg:
        # On met à l'échelle la police en se basant sur le ratio vertical (le plus contraignant)
        font_size = s1_cfg.get('auteur_font_size', 9) * scale_y
        font_name = s1_cfg.get('auteur_font_name', 'Helvetica')
        align = s1_cfg.get('auteur_align', 'center')

        ref_pos_x_pt = mm_to_pt(s1_cfg.get('auteur_pos_x_mm', 0))
        ref_pos_y_pt = mm_to_pt(s1_cfg.get('auteur_pos_y_mm', 0))

        abs_pos_x = x_col + (ref_pos_x_pt * scale_x)
        abs_pos_y = y_col + (ref_pos_y_pt * scale_y)

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
    qr_gen = qrcode.QRCode(version=1, border=0)
    qr_gen.add_data(qr_value)
    qr_gen.make(fit=True)
    buffer = io.BytesIO()
    qr_gen.make_image(fill_color="black", back_color="white").save(buffer, format='PNG')
    buffer.seek(0)

    c.drawImage(ImageReader(buffer), qr_x_pos, qr_y_pos, width=qr_code_size_pt, height=qr_code_size_pt, mask='auto')

    title_text = s1_cfg.get('qr_code_title', "")
    if title_text:
        # La police est mise à l'échelle par le ratio vertical
        title_font_size = s1_cfg.get('qr_code_title_font_size', 9) * scale_y
        title_font_name = s1_cfg.get('qr_code_title_font_name', 'Helvetica-Bold')
        title_style = ParagraphStyle('OursTitle', fontName=title_font_name, fontSize=title_font_size, alignment=TA_CENTER)
        p = Paragraph(title_text, title_style)

        p_w, p_h = p.wrapOn(c, w_col, h_col)

        title_x_pos = x_col + (w_col - p_w) / 2
        # L'espacement est mis à l'échelle verticalement
        title_y_pos = qr_y_pos + qr_code_size_pt + (mm_to_pt(1) * scale_y)

        p.drawOn(c, title_x_pos, title_y_pos)

# --- FONCTION PRINCIPALE (ROUTEUR) ---
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
    if layout_type == "optimise" and logos and logo_zone_h > 0:
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
            if isinstance(c, SVGCanvas):
                image_to_draw = Image.open(logo_path)
            else:
                image_to_draw = logo_path  # Le canvas PDF gère les chemins

            # On utilise ImageReader juste pour obtenir les dimensions
            img_reader = ImageReader(logo_path)
            img_w, img_h = img_reader.getSize()
            aspect = img_h / img_w if img_w > 0 else 1

            w_fit = cell_w - (2 * padding)
            h_fit = w_fit * aspect
            if h_fit > cell_h - (2 * padding):
                h_fit = cell_h - (2 * padding)
                w_fit = h_fit / aspect

            logo_x = cell_x + (cell_w - w_fit) / 2
            logo_y = cell_y + (cell_h - h_fit) / 2

            kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
            c.drawImage(image_to_draw, logo_x, logo_y, width=w_fit, height=h_fit, **kwargs)

            # 2. Vérifier si un lien existe pour ce logo et le dessiner
            logo_basename = os.path.basename(logo_path)
            url = links_map.get(logo_basename)

            if url:
                # Créer le rectangle pour le lien invisible
                link_rect = (logo_x, logo_y, logo_x + w_fit, logo_y + h_fit)
                c.linkURL(url, link_rect, relative=0, thickness=0)
                log.info(f"Lien créé pour '{logo_basename}' vers '{url}'") # Optionnel

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
            with Image.open(path) as img:
                img_rgba = img.convert("RGBA")
                bbox = img_rgba.getbbox()
                if bbox:
                    true_w, true_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    if true_w > 0 and true_h > 0:
                        logos_data.append({'path': path, 'w': true_w, 'h': true_h, 'ratio': true_h / true_w})
        except Exception:
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
            kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
            c.drawImage(logo_path, logo_x, logo_y, width=final_w, height=final_h, **kwargs)
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
    x, y, w, h = S2_coords.x, S2_coords.y, S2_coords.w, S2_coords.h
    if not image_path or not os.path.exists(image_path):
        c.saveState()
        c.setStrokeColor(grey)
        c.rect(x, y, w, h, stroke=1, fill=0)
        c.setFont("Helvetica", 12)
        c.drawCentredString(x + w / 2, y + h / 2, "(Image de couverture absente)")
        c.restoreState()
        return

    if isinstance(c, SVGCanvas):
        image_to_draw = Image.open(image_path)
    else:
        image_to_draw = image_path
    kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
    c.drawImage(image_to_draw, x, y, w, h, preserveAspectRatio=True, anchor='c', **kwargs)


def draw_poster_logos(c: canvas.Canvas, s_coords: Section, logos: List[str]):
    x, y, w, h = s_coords.x, s_coords.y, s_coords.w, s_coords.h
    if not logos or not w > 0 or not h > 0: return

    num_logos = len(logos)
    cell_w = w / num_logos
    padding = 2

    for i, logo_path in enumerate(logos):
        cell_x = x + i * cell_w
        try:
            if isinstance(c, SVGCanvas):
                image_to_draw = Image.open(logo_path)
            else:
                image_to_draw = logo_path

            img_reader = ImageReader(logo_path)
            img_w, img_h = img_reader.getSize()
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

            kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
            c.drawImage(image_to_draw, logo_x, logo_y, width=w_fit, height=h_fit, **kwargs)
        except Exception as e:
            log.warning(f"Impossible de dessiner le logo du poster {os.path.basename(logo_path)}: {e}")


def _draw_cucaracha_box(c: canvas.Canvas, box_coords: tuple, cfg: Config):
    x, y, w, h = box_coords
    c_cfg = cfg.cucaracha_box
    content_type = c_cfg.get("content_type", "none")
    content_value = c_cfg.get("content_value", ".")

    if content_type == "none": return

    c.saveState()
    title = c_cfg.get("title", "Cucaracha")
    title_style = ParagraphStyle('CucarachaTitle', fontName=c_cfg.get("title_font_name", "Arial-Italic"),
                                 fontSize=c_cfg.get("title_font_size", 8),
                                 leading=c_cfg.get("title_font_size", 8) * 1.2, underline=1)
    title_p = Paragraph(title, title_style)
    title_w, title_h = title_p.wrapOn(c, w - 4, h)
    title_p.drawOn(c, x + 2, y + h - title_h - 2)
    c.restoreState()

    padding = 2 * mm
    content_x, content_y = x + padding, y + padding
    content_w, content_h = w - (2 * padding), h - title_h - (2 * padding)

    if content_type == "text":
        font_name = c_cfg.get("text_font_name", "Arial")

        font_size_value_from_cfg = c_cfg.get("text_font_size", 10)

        # 1. Récupérer la taille de police et la convertir en nombre
        try:
            font_size = float(c_cfg.get("text_font_size", 10))
        except (ValueError, TypeError):
            font_size = 10.0 # Fallback

        # 2. On gère le style italique avec des balises, ce qui est plus robuste.
        text_content = content_value.replace('\n', '<br/>')
        if c_cfg.get("text_style", "normal") == "italic":
            text_content = f"<i>{text_content}</i>"

        align_map = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}
        alignment = align_map.get(c_cfg.get("text_align", "center"), TA_CENTER)

        # 3. On crée le style avec la variable `font_size` qui est garantie d'être un nombre.
        text_style = ParagraphStyle(
            'CucarachaText',
            fontName=font_name,
            fontSize=font_size,
            leading=font_size * 1.3,  # Ce calcul est maintenant sûr.
            alignment=alignment
        )
        story = [Paragraph(text_content, text_style)]

        # 4. On dessine le cadre avec une bordure pour le débogage si le texte est vide.
        frame = Frame(content_x, content_y, content_w, content_h, showBoundary=0)
        frame.addFromList(story, c)

    elif content_type == "image":
        if os.path.exists(content_value):
            try:
                if isinstance(c, SVGCanvas):
                    image_to_draw = Image.open(content_value)
                else:
                    image_to_draw = ImageReader(content_value)

                img_reader = ImageReader(content_value)
                img_w, img_h = img_reader.getSize()
                aspect = img_h / img_w if img_w > 0 else 1

                w_fit = content_w
                h_fit = w_fit * aspect
                if h_fit > content_h:
                    h_fit = content_h
                    w_fit = h_fit / aspect

                logo_x = content_x + (content_w - w_fit) / 2
                logo_y = content_y + (content_h - h_fit) / 2

                kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
                c.drawImage(image_to_draw, logo_x, logo_y, width=w_fit, height=h_fit, **kwargs)
            except Exception as e:
                log.warning(f"Erreur avec l'image de la Cucaracha Box : {e}")
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
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import grey
from reportlab.pdfbase import pdfmetrics
from reportlab.graphics.renderSVG import SVGCanvas

from .fonts import register_arial
from .layout import Layout, Section
from .config import Config


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


def _draw_ours_column(c: canvas.Canvas, col_coords: tuple, ours_text: str, cfg: Config):
    x, y, w, h = col_coords
    s1_cfg = cfg.section_1
    border_width = s1_cfg.get('ours_border_width', 0.5)
    if border_width > 0:
        c.setLineWidth(border_width)
        c.setStrokeColor(grey)
        c.rect(x, y, w, h)

    qr_code_size = s1_cfg['qr_code_height_mm'] * mm
    padding = 2 * mm
    max_qr_size = w - (2 * padding)
    if qr_code_size > max_qr_size:
        qr_code_size = max_qr_size

    qr_gen = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=0)
    qr_gen.add_data(s1_cfg['qr_code_value'])
    qr_gen.make(fit=True)
    img_pillow = qr_gen.make_image(fill_color="black", back_color="white")

    # ==================== CORRECTION : GESTION DU TYPE DE CANVAS ====================
    if isinstance(c, SVGCanvas):
        image_to_draw = img_pillow  # Le SVGCanvas veut l'objet Pillow
    else:
        buffer = io.BytesIO()
        img_pillow.save(buffer, format='PNG')
        buffer.seek(0)
        image_to_draw = ImageReader(buffer)  # Le canvas PDF veut un ImageReader

    qr_x_pos = x + (w - qr_code_size) / 2
    qr_y_pos = y + padding

    kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
    c.drawImage(image_to_draw, qr_x_pos, qr_y_pos, width=qr_code_size, height=qr_code_size, **kwargs)
    # ==============================================================================

    title_text = s1_cfg.get('qr_code_title', "Agenda culturel")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('OursTitle', parent=styles['Normal'],
                                 fontName=s1_cfg.get('qr_code_title_font_name', 'Arial-Bold'),
                                 fontSize=s1_cfg.get('qr_code_title_font_size', 9),
                                 leading=s1_cfg.get('qr_code_title_font_size', 9) * 1.2, alignment=TA_CENTER)
    title_p = Paragraph(title_text, title_style)
    title_w, title_h = title_p.wrapOn(c, w - 2 * padding, h)
    title_y_pos = y + qr_code_size + padding + (2 * mm)

    draw_paragraph(c, title_p, x + padding, title_y_pos)

    ours_style = ParagraphStyle('OursText', parent=styles['Normal'], fontName=s1_cfg['ours_font_name'],
                                fontSize=s1_cfg['ours_font_size'],
                                leading=s1_cfg['ours_font_size'] * s1_cfg['ours_line_spacing'], alignment=TA_CENTER)

    if isinstance(c, SVGCanvas):
        # Logique simplifiée pour le SVG
        y_pos = y + h - title_h - (7 * mm)
        c.setFont(ours_style.fontName, ours_style.fontSize)
        for line in ours_text.split('\n'):
            if line.strip():
                c.drawCentredString(x + w / 2, y_pos, line.strip())
                y_pos -= ours_style.leading
    else:
        # Logique standard pour le PDF avec Frame
        story = [Paragraph(line.strip(), ours_style) for line in ours_text.split('\n') if line.strip()]
        frame_x, frame_y, frame_w, frame_h = x, title_y_pos + title_h, w, h - (title_y_pos + title_h - y)
        frame = Frame(frame_x, frame_y, frame_w, frame_h, topPadding=5 * mm, showBoundary=0)
        frame.addFromList(story, c)


def _draw_logos_column(c: canvas.Canvas, col_coords: tuple, logos: List[str], cfg: Config):
    x, y, w, h = col_coords
    c_cfg = cfg.cucaracha_box
    content_type = c_cfg.get("content_type", "none")

    if content_type != "none":
        cucaracha_h = c_cfg.get("height_mm", 35) * mm
    else:
        cucaracha_h = 0

    logo_margin = 2 * mm
    logos_h = h - cucaracha_h - logo_margin if cucaracha_h > 0 else h

    cucaracha_box_coords = (x, y, w, cucaracha_h)
    logo_zone_coords = (x, y + cucaracha_h + logo_margin if cucaracha_h > 0 else y, w, logos_h)

    if cucaracha_h > 0:
        _draw_cucaracha_box(c, cucaracha_box_coords, cfg)

    zone_x, zone_y, zone_w, zone_h = logo_zone_coords
    if not logos or zone_h <= 0: return

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
            # ==================== CORRECTION : GESTION DU TYPE DE CANVAS ====================
            if isinstance(c, SVGCanvas):
                image_to_draw = Image.open(logo_path)
            else:
                image_to_draw = logo_path  # Le canvas PDF gère les chemins

            # On utilise ImageReader juste pour obtenir les dimensions
            img_reader = ImageReader(logo_path)
            img_w, img_h = img_reader.getSize()
            aspect = img_h / img_w if img_w > 0 else 1
            # ==============================================================================

            w_fit = cell_w - (2 * padding)
            h_fit = w_fit * aspect
            if h_fit > cell_h - (2 * padding):
                h_fit = cell_h - (2 * padding)
                w_fit = h_fit / aspect

            logo_x = cell_x + (cell_w - w_fit) / 2
            logo_y = cell_y + (cell_h - h_fit) / 2

            kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
            c.drawImage(image_to_draw, logo_x, logo_y, width=w_fit, height=h_fit, **kwargs)
        except Exception as e:
            print(f"[WARN] Erreur avec le logo {os.path.basename(logo_path)}: {e}")


def draw_s1(c: canvas.Canvas, S1_coords, ours_text: str, logos: List[str], cfg: Config, lay: Layout):
    register_arial()
    x, y, w, h = S1_coords.x, S1_coords.y, S1_coords.w, S1_coords.h
    split_ratio = lay.s1_split.get('logos_ratio', 0.5)
    logos_col_width = w * split_ratio
    ours_col_width = w - logos_col_width
    logos_col_coords = (x, y, logos_col_width, h)
    ours_col_coords = (x + logos_col_width, y, ours_col_width, h)
    _draw_logos_column(c, logos_col_coords, logos, cfg)
    _draw_ours_column(c, ours_col_coords, ours_text, cfg)


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

    # ==================== CORRECTION : GESTION DU TYPE DE CANVAS ====================
    if isinstance(c, SVGCanvas):
        image_to_draw = Image.open(image_path)
    else:
        image_to_draw = image_path
    kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
    c.drawImage(image_to_draw, x, y, w, h, preserveAspectRatio=True, anchor='c', **kwargs)
    # ==============================================================================


def draw_poster_logos(c: canvas.Canvas, s_coords: Section, logos: List[str]):
    x, y, w, h = s_coords.x, s_coords.y, s_coords.w, s_coords.h
    if not logos or not w > 0 or not h > 0: return

    num_logos = len(logos)
    cell_w = w / num_logos
    padding = 2

    for i, logo_path in enumerate(logos):
        cell_x = x + i * cell_w
        try:
            # ==================== CORRECTION : GESTION DU TYPE DE CANVAS ====================
            if isinstance(c, SVGCanvas):
                image_to_draw = Image.open(logo_path)
            else:
                image_to_draw = logo_path

            img_reader = ImageReader(logo_path)
            img_w, img_h = img_reader.getSize()
            aspect = img_h / img_w if img_w > 0 else 1
            # ==============================================================================

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
            print(f"[WARN] Impossible de dessiner le logo du poster {os.path.basename(logo_path)}: {e}")


def _draw_cucaracha_box(c: canvas.Canvas, box_coords: tuple, cfg: Config):
    x, y, w, h = box_coords
    c_cfg = cfg.cucaracha_box
    content_type = c_cfg.get("content_type", "none")
    content_value = c_cfg.get("content_value", "")
    if content_type == "none" or not content_value.strip(): return

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
        if c_cfg.get("text_style", "normal") == "italic":
            try:
                pdfmetrics.getFont(font_name + "-Italic")
                font_name += "-Italic"
            except:
                pass
        align_map = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}
        alignment = align_map.get(c_cfg.get("text_align", "center"), TA_CENTER)
        text_style = ParagraphStyle('CucarachaText', fontName=font_name, fontSize=c_cfg.get("text_font_size", 10),
                                    leading=c_cfg.get("text_font_size", 10) * 1.3, alignment=alignment)
        story = [Paragraph(content_value.replace('\n', '<br/>'), text_style)]
        frame = Frame(content_x, content_y, content_w, content_h, showBoundary=0)
        frame.addFromList(story, c)
    elif content_type == "image":
        if os.path.exists(content_value):
            try:
                # ==================== CORRECTION : GESTION DU TYPE DE CANVAS ====================
                if isinstance(c, SVGCanvas):
                    image_to_draw = Image.open(content_value)
                else:
                    image_to_draw = ImageReader(content_value)

                img_reader = ImageReader(content_value)
                img_w, img_h = img_reader.getSize()
                aspect = img_h / img_w if img_w > 0 else 1
                # ==============================================================================

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
                print(f"[WARN] Erreur avec l'image de la Cucaracha Box : {e}")
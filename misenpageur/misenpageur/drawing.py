# misenpageur/misenpageur/drawing.py

import os
import io
import qrcode
from typing import List

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader  # <--- CET IMPORT EST CRUCIAL
from reportlab.lib.colors import grey

from .fonts import register_arial
from .layout import Layout
from .config import Config  # Importer Config pour l'autocomplétion


# =====================================================================
# Fonctions de base (non modifiées)
# =====================================================================

def list_images(path: str, max_images: int = 100) -> List[str]:
    """Liste les chemins complets des images dans un dossier."""
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
    """Crée un style de paragraphe de base."""
    return ParagraphStyle(
        "base",
        fontName=font_name,
        fontSize=font_size,
        leading=font_size * leading_ratio,
    )


# =====================================================================
# Section 1 : Colonne OURS (avec la correction ImageReader)
# =====================================================================

def _draw_ours_column(c: canvas.Canvas, col_coords: tuple, ours_text: str, cfg: Config):
    """Dessine la colonne de droite de S1 (Ours + QR code) en utilisant la bibliothèque 'qrcode'."""
    x, y, w, h = col_coords
    s1_cfg = cfg.section_1

    # --- Cadre (inchangé) ---
    border_width = s1_cfg.get('ours_border_width', 0.5)
    if border_width > 0:
        c.setLineWidth(border_width)
        c.setStrokeColor(grey)
        c.rect(x, y, w, h)

    # --- QR Code (avec la correction finale) ---
    qr_code_size = s1_cfg['qr_code_height_mm'] * mm
    padding = 2 * mm
    max_qr_size = w - (2 * padding)
    if qr_code_size > max_qr_size:
        qr_code_size = max_qr_size

    qr_gen = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=0)
    qr_gen.add_data(s1_cfg['qr_code_value'])
    qr_gen.make(fit=True)
    img = qr_gen.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    # === LA CORRECTION EST ICI ===
    # On doit envelopper le buffer dans ImageReader avant de le passer à drawImage.
    image_reader = ImageReader(buffer)
    # =============================

    qr_x_pos = x + (w - qr_code_size) / 2
    qr_y_pos = y + padding

    # === ET ICI ===
    # On passe bien l'objet 'image_reader' et non le 'buffer'.
    c.drawImage(image_reader, qr_x_pos, qr_y_pos, width=qr_code_size, height=qr_code_size, mask='auto')
    # =============================

    # --- Titre au-dessus du QR code ---

    # 1. Définir le texte et le style du titre
    title_text = s1_cfg.get('qr_code_title', "Agenda culturel")  # Paramétrable depuis conf.yml
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'OursTitle',
        parent=styles['Normal'],
        fontName=s1_cfg.get('qr_code_title_font_name', 'Arial-Bold'),  # Police en gras
        fontSize=s1_cfg.get('qr_code_title_font_size', 9),
        leading=s1_cfg.get('qr_code_title_font_size', 9) * 1.2,
        alignment=TA_CENTER,
    )

    # 2. Créer le paragraphe et calculer sa hauteur
    title_p = Paragraph(title_text, title_style)
    title_w, title_h = title_p.wrapOn(c, w - 2 * padding, h)  # Calculer la place qu'il prend

    # 3. Calculer sa position et le dessiner
    title_y_pos = y + qr_code_size + padding + (2 * mm)  # Positionné au-dessus du QR code, avec un petit espace
    title_p.drawOn(c, x + padding, title_y_pos)
    # ====================== FIN DE LA MODIFICATION ======================

    # --- Texte de l'ours (avec ajustement de sa position) ---
    styles = getSampleStyleSheet()
    ours_style = ParagraphStyle(
        'OursText',
        parent=styles['Normal'],
        fontName=s1_cfg['ours_font_name'],
        fontSize=s1_cfg['ours_font_size'],
        leading=s1_cfg['ours_font_size'] * s1_cfg['ours_line_spacing'],
        alignment=TA_CENTER,
    )

    story = [Paragraph(line.strip(), ours_style) for line in ours_text.split('\n') if line.strip()]

    # --- Ajustement de la zone du Frame ---
    # Le Frame commence maintenant au-dessus du titre
    frame_x = x
    frame_y = title_y_pos + title_h
    frame_w = w
    frame_h = h - (frame_y - y)  # La hauteur restante
    frame = Frame(frame_x, frame_y, frame_w, frame_h, topPadding=5 * mm, showBoundary=0)
    frame.addFromList(story, c)

    # --- Texte de l'ours (inchangé) ---
    styles = getSampleStyleSheet()
    ours_style = ParagraphStyle(
        'OursText',
        parent=styles['Normal'],
        fontName=s1_cfg['ours_font_name'],
        fontSize=s1_cfg['ours_font_size'],
        leading=s1_cfg['ours_font_size'] * s1_cfg['ours_line_spacing'],
        alignment=TA_CENTER,
    )

    story = [Paragraph(line.strip(), ours_style) for line in ours_text.split('\n') if line.strip()]

    frame_x = x
    frame_y = y + qr_code_size + padding
    frame_w = w
    frame_h = h - (qr_code_size + padding)
    frame = Frame(frame_x, frame_y, frame_w, frame_h, topPadding=5 * mm, showBoundary=0)
    frame.addFromList(story, c)


# =====================================================================
# Section 1 : Colonne LOGOS (non modifiée)
# =====================================================================

def _draw_logos_column(c: canvas.Canvas, col_coords: tuple, logos: List[str], cfg: Config):
    """Dessine la colonne de gauche de S1 (Logos + boîte additionnelle)."""
    x, y, w, h = col_coords
    s1_cfg = cfg.section_1

    additional_box_h = s1_cfg['additional_box_height_mm'] * mm
    logo_margin = s1_cfg['logo_box_bottom_margin_mm'] * mm
    logos_h = h - additional_box_h - logo_margin

    # --- LECTURE SÉCURISÉE DE LA CONFIGURATION ---
    # On utilise .get(key, 0) pour s'assurer que si la clé n'est pas dans conf.yml,
    # la valeur par défaut est 0, ce qui supprime la boîte et la marge.
    additional_box_h = s1_cfg.get('additional_box_height_mm', 0) * mm
    logo_margin = s1_cfg.get('logo_box_bottom_margin_mm', 0) * mm

    # --- CALCUL CORRECT DES HAUTEURS ---
    # La hauteur de la zone des logos est bien la hauteur totale de la colonne
    # moins la boîte additionnelle et sa marge.
    logos_h = h - additional_box_h - logo_margin

    # --- Définition des zones ---
    additional_box_coords = (x, y, w, additional_box_h)
    logo_zone_coords = (x, y + additional_box_h + logo_margin, w, logos_h)

    # --- Dessin des cadres de debug ---
    c.saveState()
    c.setStrokeColor(grey)
    c.setLineWidth(0.5)
    # On ne dessine le cadre de la boîte que si sa hauteur est supérieure à zéro
    if additional_box_h > 0:
        c.rect(*additional_box_coords)
    c.rect(*logo_zone_coords)
    c.restoreState()

    # --- Disposition des logos (inchangé) ---
    zone_x, zone_y, zone_w, zone_h = logo_zone_coords
    if not logos or zone_h <= 0: return

    num_logos = len(logos)
    cols = 2
    rows = (num_logos + cols - 1) // cols
    if rows == 0: return

    cell_w = zone_w / cols
    cell_h = zone_h / rows
    padding = 1 * mm

    for i, logo_path in enumerate(logos):
        row = rows - 1 - (i // cols)
        col = i % cols
        cell_x = zone_x + col * cell_w
        cell_y = zone_y + row * cell_h

        try:
            img = ImageReader(logo_path)
            img_w, img_h = img.getSize()
            aspect = img_h / img_w if img_w > 0 else 1

            w_fit = cell_w - (2 * padding)
            h_fit = w_fit * aspect

            if h_fit > cell_h - (2 * padding):
                h_fit = cell_h - (2 * padding)
                w_fit = h_fit / aspect

            logo_x = cell_x + (cell_w - w_fit) / 2
            logo_y = cell_y + (cell_h - h_fit) / 2

            c.drawImage(logo_path, logo_x, logo_y, width=w_fit, height=h_fit, mask='auto')

        except Exception as e:
            print(f"[WARN] Erreur avec le logo {os.path.basename(logo_path)}: {e}")


# =====================================================================
# Fonctions principales de dessin (draw_s1, draw_s2_cover)
# =====================================================================

def draw_s1(c: canvas.Canvas, S1_coords, ours_text: str, logos: List[str], cfg: Config, lay: Layout):
    """Fonction principale pour dessiner toute la Section 1."""
    register_arial()

    try:
        x, y, w, h = S1_coords.x, S1_coords.y, S1_coords.w, S1_coords.h
    except AttributeError:
        x, y, w, h = S1_coords['x'], S1_coords['y'], S1_coords['w'], S1_coords['h']

    split_ratio = lay.s1_split.get('logos_ratio', 0.5)

    logos_col_width = w * split_ratio
    ours_col_width = w - logos_col_width

    logos_col_coords = (x, y, logos_col_width, h)
    ours_col_coords = (x + logos_col_width, y, ours_col_width, h)

    _draw_logos_column(c, logos_col_coords, logos, cfg)
    _draw_ours_column(c, ours_col_coords, ours_text, cfg)


def draw_s2_cover(c: canvas.Canvas, S2_coords, image_path: str, inner_pad: float):
    """Dessine l'image de couverture dans la Section 2."""
    try:
        x, y, w, h = S2_coords.x, S2_coords.y, S2_coords.w, S2_coords.h
    except AttributeError:
        x, y, w, h = S2_coords['x'], S2_coords['y'], S2_coords['w'], S2_coords['h']

    if not image_path or not os.path.exists(image_path):
        c.saveState()
        c.setStrokeColor(grey)
        c.rect(x, y, w, h, stroke=1, fill=0)
        c.setFillColor(grey)
        c.setFont("Helvetica", 12)
        c.drawCentredString(x + w / 2, y + h / 2, "(Image de couverture absente)")
        c.restoreState()
        return

    c.drawImage(image_path, x, y, w, h, preserveAspectRatio=True, anchor='c')


def draw_poster_logos(c: canvas.Canvas, s_coords, logos: List[str]):
    """Dessine une ligne de logos pour le poster."""
    x, y, w, h = s_coords.x, s_coords.y, s_coords.w, s_coords.h
    if not logos or not w > 0 or not h > 0: return

    num_logos = len(logos)
    padding = 1 * mm
    cell_w = w / num_logos

    for i, logo_path in enumerate(logos):
        cell_x = x + i * cell_w
        try:
            img = ImageReader(logo_path)
            img_w, img_h = img.getSize()
            aspect = img_h / img_w if img_w > 0 else 1

            h_fit = h - (2 * padding)
            w_fit = h_fit / aspect

            if w_fit > cell_w - (2 * padding):
                w_fit = cell_w - (2 * padding)
                h_fit = w_fit * aspect

            logo_x = cell_x + (cell_w - w_fit) / 2
            logo_y = y + (h - h_fit) / 2

            c.drawImage(logo_path, logo_x, logo_y, width=w_fit, height=h_fit, mask='auto')
        except Exception as e:
            print(f"[WARN] Impossible de dessiner le logo du poster {os.path.basename(logo_path)}: {e}")
# misenpageur/misenpageur/drawing.py

import os
from typing import List

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.barcode import qr
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import grey
from .fonts import register_arial
from .layout import Layout
from .config import Config


# --- Fonctions existantes (à conserver si vous en avez d'autres) ---

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


# --- NOUVELLES FONCTIONS DÉDIÉES À LA SECTION 1 ---

def _draw_ours_column(c: canvas.Canvas, col_coords: tuple, ours_text: str, cfg):
    """Dessine la colonne de droite de S1 (Ours + QR code)."""
    x, y, w, h = col_coords
    s1_cfg = cfg.section_1

    border_width = s1_cfg.get('ours_border_width', 0.5) # Nouvelle config
    if border_width > 0:
        c.setLineWidth(border_width)
        c.setStrokeColor(grey) # Ou une couleur de config
        c.rect(x, y, w, h)

    # Style du paragraphe, centré
    styles = getSampleStyleSheet()
    ours_style = ParagraphStyle(
        'OursText',
        parent=styles['Normal'],
        fontName=s1_cfg['ours_font_name'],
        fontSize=s1_cfg['ours_font_size'],
        leading=s1_cfg['ours_font_size'] * s1_cfg['ours_line_spacing'],
        alignment=TA_CENTER,
    )

    # QR Code en bas de la colonne
    qr_code_size = s1_cfg['qr_code_height_mm'] * mm
    padding = 2 * mm
    max_qr_size = w - (2 * padding)
    if qr_code_size > max_qr_size:
        qr_code_size = max_qr_size

    if qr_code_size > w:
        qr_code_size = w

    qr_x_pos = x + (w - qr_code_size) / 2
    qr_y_pos = y + padding
    qr.QrCode(s1_cfg['qr_code_value'], border=0).drawOn(c, qr_x_pos, qr_y_pos, qr_code_size)

    # Texte de l'ours dans un Frame au-dessus du QR code
    story = [Paragraph(line.strip(), ours_style) for line in ours_text.split('\n') if line.strip()]

    frame_x = x
    frame_y = y + qr_code_size
    frame_w = w
    frame_h = h - qr_code_size
    frame = Frame(frame_x, frame_y, frame_w, frame_h, topPadding=5 * mm, showBoundary=0)
    frame.addFromList(story, c)


def _draw_logos_column(c: canvas.Canvas, col_coords: tuple, logos: List[str], cfg):
    """Dessine la colonne de gauche de S1 (Logos + boîte additionnelle)."""
    x, y, w, h = col_coords
    s1_cfg = cfg.section_1

    # Calcul des hauteurs des zones
    additional_box_h = s1_cfg['additional_box_height_mm'] * mm
    logo_margin = s1_cfg['logo_box_bottom_margin_mm'] * mm
    logos_h = h - additional_box_h - logo_margin

    # Zone de la boîte additionnelle (en bas)
    additional_box_coords = (x, y, w, additional_box_h)

    # Zone des logos (au-dessus)
    logo_zone_coords = (x, y + additional_box_h + logo_margin, w, logos_h)

    # Debug: Dessiner les cadres des zones
    c.saveState()
    c.setStrokeColor(grey)
    c.setLineWidth(0.5)
    c.rect(*additional_box_coords)
    c.rect(*logo_zone_coords)
    c.restoreState()

    # --- Algorithme de disposition des logos (VERSION SIMPLIFIÉE) ---
    # NOTE: Ceci est une ébauche qui empile les logos. L'algorithme de packing
    # optimisé pour remplir l'espace avec des surfaces égales est une étape suivante.

    zone_x, zone_y, zone_w, zone_h = logo_zone_coords
    if not logos or zone_h <= 0:
        return

    num_logos = len(logos)
    cols = 2
    # Calculer le nombre de lignes nécessaires (arrondi au supérieur)
    rows = (num_logos + cols - 1) // cols

    if rows == 0: return

    cell_w = zone_w / cols
    cell_h = zone_h / rows
    padding = 1 * mm  # Petit espace autour de chaque logo dans sa cellule

    for i, logo_path in enumerate(logos):
        row = rows - 1 - (i // cols)  # On commence par le haut (ligne 0 = en haut)
        col = i % cols

        # Calculer les coordonnées de la cellule
        cell_x = zone_x + col * cell_w
        cell_y = zone_y + row * cell_h

        try:
            img = ImageReader(logo_path)
            img_w, img_h = img.getSize()
            aspect = img_h / img_w if img_w > 0 else 1

            # Redimensionner pour tenir dans la cellule (en gardant les proportions)
            # D'abord, on ajuste à la largeur de la cellule
            w_fit = cell_w - (2 * padding)
            h_fit = w_fit * aspect

            # Si ça dépasse en hauteur, on ajuste à la hauteur
            if h_fit > cell_h - (2 * padding):
                h_fit = cell_h - (2 * padding)
                w_fit = h_fit / aspect

            # Centrer l'image dans sa cellule
            logo_x = cell_x + (cell_w - w_fit) / 2
            logo_y = cell_y + (cell_h - h_fit) / 2

            c.drawImage(logo_path, logo_x, logo_y, width=w_fit, height=h_fit, mask='auto')

        except Exception as e:
            print(f"[WARN] Erreur avec le logo {os.path.basename(logo_path)}: {e}")


def draw_s1(c: canvas.Canvas, S1_coords, ours_text: str, logos: List[str], cfg: Config, lay: Layout):
    """
    Fonction principale pour dessiner toute la Section 1.
    Divise S1 en deux colonnes et appelle les fonctions de dessin dédiées.
    """
    # Enregistrer la police Arial avant de l'utiliser.
    register_arial() # <<< AJOUTER CETTE LIGNE

    # S1_coords peut être un dict ou un objet, on accède aux clés
    try:
        x, y, w, h = S1_coords.x, S1_coords.y, S1_coords.w, S1_coords.h
    except AttributeError:
        x, y, w, h = S1_coords['x'], S1_coords['y'], S1_coords['w'], S1_coords['h']

    # On utilise le ratio du VRAI layout.yml
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
        x, y, w, h = S2_coords['x'], S2_coords['y'], S2_coords['w'], S2_coords['h']
    except TypeError:
        x, y, w, h = S2_coords.x, S2_coords.y, S2_coords.w, S2_coords.h

    if not image_path or not os.path.exists(image_path):
        # Fallback si pas d'image : dessine un cadre et un texte
        c.saveState()
        c.setStrokeColor(grey)
        c.rect(x, y, w, h, stroke=1, fill=0)
        c.setFillColor(grey)
        c.setFont("Helvetica", 12)
        c.drawCentredString(x + w / 2, y + h / 2, "(Image de couverture absente)")
        c.restoreState()
        return

    # Dessine l'image en la faisant remplir la section (preserveAspectRatio='xMidYMid slice')
    c.drawImage(image_path, x, y, w, h, preserveAspectRatio=True, anchor='c')
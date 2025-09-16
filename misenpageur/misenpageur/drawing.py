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
from rectpack import float2dec, PackerGlobal

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
    Dessine la colonne "ours" en utilisant une image de fond PNG
    et en ajoutant les éléments dynamiques (auteur, QR code, hyperlinks).
    """
    x, y, w, h = col_coords
    s1_cfg = cfg.section_1
    project_root = getattr(cfg, 'project_root', '.')

    # 1. Dessin de l'image de fond
    bg_path = os.path.join(project_root, s1_cfg['ours_background_png'])
    if os.path.exists(bg_path):
        c.drawImage(bg_path, x, y, width=w, height=h, preserveAspectRatio=True, anchor='c', mask='auto')
    else:
        print(f"[WARN] Image de fond de l'ours introuvable : {bg_path}")

    # 2. Dessin du nom de l'auteur
    auteur_text = getattr(cfg, 'auteur_couv', '')
    if auteur_text:
        # Récupérer les paramètres depuis la config
        auteur_url = getattr(cfg, 'auteur_couv_url', '')
        font_name = s1_cfg.get('auteur_font_name', 'Helvetica')
        font_size = s1_cfg.get('auteur_font_size', 9)
        align = s1_cfg.get('auteur_align', 'left')

        # Définir les coordonnées et la police
        abs_pos_x = x + mm_to_pt(s1_cfg.get('auteur_pos_x_mm', 0))
        abs_pos_y = y + mm_to_pt(s1_cfg.get('auteur_pos_y_mm', 0))
        c.setFont(font_name, font_size)
        c.setFillColorRGB(0, 0, 0)

        # Dessiner le texte en fonction de l'alignement
        if align == 'center':
            c.drawCentredString(abs_pos_x, abs_pos_y, auteur_text)
        elif align == 'right':
            c.drawRightString(abs_pos_x, abs_pos_y, auteur_text)
        else:  # left
            c.drawString(abs_pos_x, abs_pos_y, auteur_text)

        # ==================== AJOUT DE LA GESTION DE L'URL ====================
        if auteur_url:
            # Mesurer la largeur du texte pour créer un rectangle de lien précis
            text_width = c.stringWidth(auteur_text, font_name, font_size)

            # La hauteur du lien est approximativement la taille de la police
            link_height = font_size

            # Calculer le coin bas-gauche du rectangle de lien en fonction de l'alignement
            if align == 'center':
                x1 = abs_pos_x - (text_width / 2)
            elif align == 'right':
                x1 = abs_pos_x - text_width
            else:  # left
                x1 = abs_pos_x

            # Le y de la ligne de base du texte est en bas, donc c'est notre y1
            y1 = abs_pos_y

            # Définir le rectangle (x1, y1, x2, y2)
            link_rect = (x1, y1, x1 + text_width, y1 + link_height)

            # Dessiner le lien invisible
            c.linkURL(auteur_url, link_rect, relative=0, thickness=0)
            print(f"[INFO] Lien pour l'auteur '{auteur_text}' créé vers '{auteur_url}'")

    # 3. Dessin des rectangles de lien invisibles
    hyperlinks = s1_cfg.get('ours_hyperlinks', [])
    for link in hyperlinks:
        href, rect_mm = link.get('href'), link.get('rect_mm')
        if not href or not rect_mm or len(rect_mm) != 4: continue
        rel_x_pt, rel_y_pt, rel_w_pt, rel_h_pt = [mm_to_pt(v) for v in rect_mm]
        abs_x1, abs_y1 = x + rel_x_pt, y + rel_y_pt
        c.linkURL(href, (abs_x1, abs_y1, abs_x1 + rel_w_pt, abs_y1 + rel_h_pt), relative=0, thickness=0)

    # 4. Dessin du QR Code
    qr_code_size = mm_to_pt(s1_cfg.get('qr_code_height_mm', 25))
    padding = mm_to_pt(2)
    qr_x_pos = x + (w - qr_code_size) / 2
    qr_y_pos = y + padding

    qr_gen = qrcode.QRCode(version=1, border=0)
    qr_gen.add_data(s1_cfg['qr_code_value'])
    qr_gen.make(fit=True)
    buffer = io.BytesIO()
    qr_gen.make_image(fill_color="black", back_color="white").save(buffer, format='PNG')
    buffer.seek(0)

    c.drawImage(ImageReader(buffer), qr_x_pos, qr_y_pos, width=qr_code_size, height=qr_code_size, mask='auto')

    # Titre du QR Code
    title_text = s1_cfg.get('qr_code_title', "")
    if title_text:
        title_style = ParagraphStyle('OursTitle', fontName=s1_cfg.get('qr_code_title_font_name', 'Helvetica-Bold'),
                                     fontSize=9, alignment=TA_CENTER)
        title_p = Paragraph(title_text, title_style)
        title_w, title_h = title_p.wrapOn(c, w - 2 * padding, h)
        title_y_pos = qr_y_pos + qr_code_size + mm_to_pt(1)
        title_p.drawOn(c, x + padding, title_y_pos)

# --- FONCTION PRINCIPALE (ROUTEUR) ---
def _draw_logos_column(c: canvas.Canvas, col_coords: tuple, logos: List[str], cfg: Config):
    """
    Routeur qui appelle la bonne fonction de dessin des logos en fonction de la config.
    """
    layout_type = getattr(cfg, "logos_layout", "colonnes")
    if layout_type == "optimise" and logos:
        _draw_logos_optimized(c, col_coords, logos)
    else:
        _draw_logos_two_columns(c, col_coords, logos, cfg)


def _draw_logos_two_columns(c: canvas.Canvas, col_coords: tuple, logos: List[str], cfg: Config):
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


def _draw_logos_optimized(c: canvas.Canvas, col_coords: tuple, logo_paths: List[str]):
    """
    Dessine les logos en trouvant le plus grand facteur d'échelle commun,
    puis en ajustant chaque logo à l'intérieur de sa boîte allouée pour
    garantir le respect du ratio d'aspect.
    """
    x_offset, y_offset, w, h = col_coords
    if not logo_paths or w <= 0 or h <= 0:
        return

    padding_mm = 1.0
    padding_pt = mm_to_pt(padding_mm)

    logos_data = []
    # Charger les dimensions réelles (bounding box) des logos (cette partie est correcte)
    for path in logo_paths:
        try:
            with Image.open(path) as img:
                img_rgba = img.convert("RGBA")
                bbox = img_rgba.getbbox()
                if bbox:
                    true_w, true_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    logos_data.append(
                        {'path': path, 'w': true_w, 'h': true_h, 'ratio': true_h / true_w if true_w > 0 else 1})
                else:
                    logos_data.append({'path': path, 'w': img.width, 'h': img.height,
                                       'ratio': img.height / img.width if img.width > 0 else 1})
        except Exception:
            pass
    if not logos_data: return

    # 1. Recherche binaire du meilleur facteur d'échelle (cette partie est correcte)
    low_scale, high_scale = 0.0, 1.0
    best_placements = None

    total_area = sum(ld['w'] * ld['h'] for ld in logos_data)
    if total_area > 0:
        high_scale = math.sqrt((w * h) / total_area) * 2.0

    for _ in range(15):
        scale = (low_scale + high_scale) / 2
        if scale == 0: break

        packer = PackerGlobal()
        packer.add_bin(w, h)

        rectangles_to_add = []
        for logo in logos_data:
            rect_w = logo['w'] * scale
            rect_h = logo['h'] * scale
            padded_w = rect_w + (2 * padding_pt)
            padded_h = rect_h + (2 * padding_pt)
            rectangles_to_add.append({'w': padded_w, 'h': padded_h, 'rid': logo['path']})

        for r in rectangles_to_add:
            packer.add_rect(r['w'], r['h'], rid=r['rid'])
        packer.pack()

        if len(packer[0]) == len(logos_data):
            best_placements = packer[0]
            low_scale = scale
        else:
            high_scale = scale

    if not best_placements:
        print("[WARN] Aucune solution de packing n'a pu être trouvée.")
        _draw_logos_two_columns(c, col_coords, logo_paths, Config())
        return

    # ==================== LOGIQUE DE DESSIN FINALE ET DÉFINITIVE ====================
    # 2. Dessiner chaque logo en l'ajustant à sa boîte allouée
    for rect in best_placements:
        logo_path = rect.rid
        logo_data = next(l for l in logos_data if l['path'] == logo_path)
        logo_ratio = logo_data['ratio']

        # 1. Déterminer la zone de dessin réelle (conteneur)
        available_w = float(rect.width) - (2 * padding_pt)
        available_h = float(rect.height) - (2 * padding_pt)

        if available_w <= 0 or available_h <= 0:
            continue

        # 2. Calculer la taille finale du logo pour qu'il rentre dans le conteneur
        #    tout en conservant son ratio d'aspect.
        if logo_ratio > (available_h / available_w):
            # Le logo est plus "grand" que la boîte -> on ajuste à la hauteur
            final_h = available_h
            final_w = final_h / logo_ratio
        else:
            # Le logo est plus "large" que la boîte -> on ajuste à la largeur
            final_w = available_w
            final_h = final_w * logo_ratio

        # 3. Calculer la position pour centrer le logo dans sa zone de dessin
        available_area_x = x_offset + float(rect.x) + padding_pt
        available_area_y = y_offset + float(rect.y) + padding_pt

        centering_offset_x = (available_w - final_w) / 2
        centering_offset_y = (available_h - final_h) / 2

        logo_x = available_area_x + centering_offset_x
        logo_y = available_area_y + centering_offset_y

        try:
            kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
            c.drawImage(logo_path, logo_x, logo_y, width=final_w, height=final_h, **kwargs)
        except Exception as e:
            print(f"[WARN] Erreur avec le logo {os.path.basename(logo_path)} lors du dessin: {e}")
    # ==============================================================================

def draw_s1(c: canvas.Canvas, S1_coords, logos: list[str], cfg: Config, lay: Layout):
    """
    Dessine la section S1 en la divisant en une colonne pour les logos
    et une colonne pour l'ours (dessiné en mode PNG Hybride).
    """
    register_arial()
    x, y, w, h = S1_coords.x, S1_coords.y, S1_coords.w, S1_coords.h

    split_ratio = lay.s1_split.get('logos_ratio', 0.5)
    logos_col_width = w * split_ratio
    ours_col_width = w - logos_col_width

    logos_col_coords = (x, y, logos_col_width, h)
    ours_col_coords = (x + logos_col_width, y, ours_col_width, h)

    _draw_logos_column(c, logos_col_coords, logos, cfg)
    # L'appel n'a plus besoin de passer de données SVG
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
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from typing import List

from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, KeepInFrame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.utils import ImageReader

from .layout import Section


def paragraph_style(font_name: str, font_size: float, leading_ratio: float) -> ParagraphStyle:
    return ParagraphStyle(
        name=f"Body_{font_size:.2f}",
        fontName=font_name,
        fontSize=font_size,
        leading=max(1.0, font_size * leading_ratio),
        alignment=TA_JUSTIFY,
        spaceBefore=0.0,
        spaceAfter=1.0,
    )


def list_images(dir_path: str, max_images: int = 10) -> List[str]:
    if not os.path.isdir(dir_path):
        return []
    imgs = [
        os.path.join(dir_path, p)
        for p in os.listdir(dir_path)
        if p.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"))
    ]
    imgs.sort()
    return imgs[:max_images]


def draw_s1(
    c: canvas.Canvas,
    s1: Section,
    ours_text: str,
    logos: List[str],
    font_name: str,
    leading_ratio: float,
    inner_pad: float,
    s1_split: dict,
) -> None:
    # Clip exact de la zone S1 (aucun débordement possible)
    c.saveState()
    clip = c.beginPath()
    clip.rect(s1.x, s1.y, s1.w, s1.h)
    c.clipPath(clip, stroke=0, fill=0)

    logos_ratio = s1_split.get("logos_ratio", 0.60)
    logos_w = s1.w * logos_ratio
    ours_w = s1.w - logos_w

    # --- Zone logos (grille top-align) ---
    lg_x = s1.x + inner_pad
    lg_y = s1.y + inner_pad
    lg_w = max(1.0, logos_w - 2 * inner_pad)
    lg_h = max(1.0, s1.h - 2 * inner_pad)

    cols = 2
    rows = max(1, (len(logos) + cols - 1) // cols)
    cell_w = lg_w / cols
    cell_h = lg_h / rows

    idx = 0
    for r in range(rows):
        for col in range(cols):
            if idx >= len(logos):
                break
            path = logos[idx]
            idx += 1
            if not os.path.exists(path):
                continue
            cx = lg_x + col * cell_w
            cy = lg_y + (rows - 1 - r) * cell_h  # ligne 0 en haut
            img = ImageReader(path)
            iw, ih = img.getSize()
            scale = min(cell_w / iw, cell_h / ih)
            dw, dh = iw * scale, ih * scale
            dx = cx + (cell_w - dw) / 2.0
            dy = cy + (cell_h - dh)  # TOP-align dans la cellule
            c.drawImage(img, dx, dy, dw, dh, preserveAspectRatio=True, mask="auto")

    # --- Zone ours (TOP manuel + centré horizontalement) ---
    ours_x = s1.x + logos_w + inner_pad
    ours_y = s1.y + inner_pad
    ours_wi = max(1.0, ours_w - 2 * inner_pad)
    ours_hi = max(1.0, s1.h - 2 * inner_pad)

    base = paragraph_style(font_name, 8.5, leading_ratio)
    style_ours = ParagraphStyle(
        name="Ours",
        parent=base,
        alignment=TA_CENTER,  # centré horizontalement
        spaceBefore=0.0,
        spaceAfter=0.0,
    )

    # Nettoyage minimal (trim + normalisation des retours)
    ours_txt = (ours_text or "").strip().replace("\r\n", "\n").replace("\r", "\n")
    ours_txt = re.sub(r"\n{3,}", "\n\n", ours_txt).replace("\n", "<br/>")
    # Retirer <br/> de tête/queue s'il y en a
    ours_txt = re.sub(r"^(?:\s*<br/>\s*)+", "", ours_txt)
    ours_txt = re.sub(r"(?:\s*<br/>\s*)+$", "", ours_txt)

    p = Paragraph(ours_txt, style_ours)

    # Mesure pour top-align manuel
    _w, ph = p.wrap(ours_wi, ours_hi)
    offset_y = max(0.0, ours_hi - ph)

    kif = KeepInFrame(
        maxWidth=ours_wi,
        maxHeight=ours_hi,
        content=[p],
        hAlign="LEFT",
        vAlign="BOTTOM",  # avec offset -> haut du texte au sommet de la zone
        mode="shrink",
    )

    c.translate(ours_x, ours_y + offset_y)
    kif.wrapOn(c, ours_wi, ours_hi)
    kif.drawOn(c, 0, 0)

    c.restoreState()  # fin S1


def draw_s2_cover(c: canvas.Canvas, s2: Section, cover_path: str, inner_pad: float) -> None:
    if not (cover_path and os.path.exists(cover_path)):
        return

    # Clip exact au rectangle S2 (sans padding)
    x, y, w, h = s2.x, s2.y, s2.w, s2.h

    img = ImageReader(cover_path)
    iw, ih = img.getSize()
    scale = max(w / iw, h / ih)  # "cover" intégral
    dw, dh = iw * scale, ih * scale
    dx = x + (w - dw) / 2.0
    dy = y + (h - dh) / 2.0

    c.saveState()
    p = c.beginPath()
    p.rect(x, y, w, h)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(img, dx, dy, dw, dh, preserveAspectRatio=True, mask="auto")
    c.restoreState()

# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.units import mm
from reportlab.lib.colors import black
from reportlab.lib.utils import ImageReader

from reportlab.platypus import Paragraph, KeepInFrame, Frame
from reportlab.pdfgen.canvas import Canvas

# Barcodes / QR
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing as RLDrawing
from reportlab.graphics import renderPDF

# --- util commun (mettre en haut de drawing.py) ---
def _sec_get(sec, key):
    v = getattr(sec, key, None)
    if v is None:
        # si sec est un dict, on peut indexer; sinon on renvoie None
        try:
            return sec[key]
        except Exception:
            return None
    return v


# --------------------------------------------------------------------
# Styles & utilitaires généraux
# --------------------------------------------------------------------

def paragraph_style(font_name: str, font_size: float, leading_ratio: float) -> ParagraphStyle:
    """
    Style justifié pour le corps de texte (S3..S6), réutilisable ailleurs.
    """
    leading = font_size * float(leading_ratio or 1.15)
    return ParagraphStyle(
        name=f"Body_{font_size:.2f}",
        fontName=font_name or "Helvetica",
        fontSize=font_size,
        leading=leading,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )


def list_images(folder: str, exts: tuple = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"), max_images: int = 10) -> List[str]:
    """
    Retourne une liste triée de chemins d’images depuis un dossier.
    """
    paths: List[str] = []
    if not folder:
        return paths
    p = Path(folder)
    if not p.exists() or not p.is_dir():
        return paths
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in exts:
            paths.append(str(f))
            if len(paths) >= max_images:
                break
    return paths


# --------------------------------------------------------------------
# Aides dessin Ours “riche”
# --------------------------------------------------------------------

def _hr(c: Canvas, x: float, y: float, w: float, style: str = "dotted", thick: float = 0.8, gap: float = 2.0):
    c.saveState()
    c.setLineWidth(thick)
    if style == "dotted":
        c.setDash(gap, gap)
    elif style == "solid":
        c.setDash()
    else:
        c.restoreState()
        return
    c.line(x, y, x + w, y)
    c.restoreState()


def _draw_icon(c: Canvas, path: str, x: float, y: float, h: float) -> float:
    """
    Dessine une icône (si dispo) de hauteur h, retourne la largeur peinte.
    """
    try:
        if not path or not os.path.exists(path):
            return 0.0
        img = ImageReader(path)
        iw, ih = img.getSize()
        w = (iw / ih) * h if ih else h
        c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, mask='auto')
        return float(w)
    except Exception:
        return 0.0


def _wrap_text(c: Canvas, text: str, max_w: float, font: str, size: float) -> List[str]:
    """
    Word-wrap très simple pour éviter les dépassements.
    """
    if not text:
        return [""]
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if c.stringWidth(test, font, size) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_qr(c: Canvas, url: str, x: float, y: float, size_pt: float):
    if not url:
        return
    w = qr.QrCodeWidget(url)
    b = w.getBounds()
    bw = b[2] - b[0]
    bh = b[3] - b[1]
    d = RLDrawing(size_pt, size_pt, transform=[size_pt / bw, 0, 0, size_pt / bh, 0, 0])
    d.add(w)
    renderPDF.draw(d, c, x, y)
    # zone cliquable
    c.linkURL(url, (x, y, x + size_pt, y + size_pt), relative=0)


def _text(c: Canvas, s: str, x: float, y: float, font: str, size: float):
    c.setFont(font, size)
    c.drawString(x, y, s)


def _link(c: Canvas, s: str, url: str, x: float, y: float, font: str, size: float):
    c.setFont(font, size)
    c.drawString(x, y, s)
    w = c.stringWidth(s, font, size)
    c.linkURL(url, (x, y - 1, x + w, y + size * 1.1), relative=0)


def _block_gap_y(y: float, gap: float) -> float:
    return y - gap


# --------------------------------------------------------------------
# Ours “riche” (logos à gauche + colonne info à droite)
# --------------------------------------------------------------------

def draw_s1_rich(
    c: Canvas,
    sec: Union[dict, Any],
    cfg: Any,
    ours_cfg: Dict[str, Any],
    logos: List[str],
    default_font: str,
    leading_ratio: float,
):
    """
    S1 => logos à gauche + ours structuré à droite (titre, contact, socials, notes, QR).
    Supporte des icônes pour :
      - address_lines  -> ours_rich.icons.address
      - notes          -> via item.icon ou mapping ours_rich.icons.{riso, volunteer, cover}
    """
    # Frame S1
    x = _sec_get(sec, "x"); y = _sec_get(sec, "y")
    w = _sec_get(sec, "w"); h = _sec_get(sec, "h")


    pad = float(ours_cfg.get("padding", 6))
    split = float(ours_cfg.get("split", 0.42))
    left_w = w * split
    right_w = w - left_w

    # Sous-frames (logos / ours)
    lx = x + pad
    ly = y + pad
    lw = left_w - 2 * pad
    lh = h - 2 * pad

    rx = x + left_w + pad
    ry = y + pad
    rw = right_w - 2 * pad
    rh = h - 2 * pad

    # 1) Grille LOGOS (simple 2 colonnes si aucun helper spécifique)
    cols = 2
    gutter = 6
    cell_w = (lw - gutter) / cols
    cell_h = cell_w * 0.6
    cx, cy = 0, 0
    for p in logos[:10]:
        try:
            img = ImageReader(p)
        except Exception:
            continue
        gx = lx + (cx * (cell_w + gutter))
        gy = ly + lh - (cy + 1) * (cell_h + gutter)
        if gy < ly:
            break
        c.drawImage(img, gx, gy, width=cell_w, height=cell_h, preserveAspectRatio=True, anchor='sw', mask='auto')
        cx += 1
        if cx >= cols:
            cx = 0
            cy += 1

    # 2) Colonne droite (ours)
    title = ours_cfg.get("title", "")
    title_size = float(ours_cfg.get("title_size", 18))
    body_size = float(ours_cfg.get("body_size", 9.5))
    lead_ratio = float(ours_cfg.get("leading_ratio", leading_ratio))
    L_body = body_size * lead_ratio

    sep_style = ours_cfg.get("separators", "dotted")
    sep_th = float(ours_cfg.get("sep_thickness", 0.8))
    sep_gap = float(ours_cfg.get("sep_gap", 2))
    block_gap = float(ours_cfg.get("block_gap", 6))

    icons_map: Dict[str, str] = dict(ours_cfg.get("icons", {}) or {})

    usable_top = ry + rh
    cursor_y = usable_top

    # Titre
    if title:
        c.setFont(default_font, title_size)
        cursor_y -= title_size
        _text(c, title, rx, cursor_y, default_font, title_size)
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    c.setFont(default_font, body_size)

    # Bloc adresse (avec icône)
    addr_lines: List[str] = list(ours_cfg.get("address_lines", []) or [])
    if addr_lines:
        icon_h = body_size
        used_w = _draw_icon(c, icons_map.get("address", ""), rx, cursor_y - body_size + 1, icon_h)
        text_x = rx + (used_w + 4 if used_w else 0)

        for i, line in enumerate(addr_lines):
            if i == 0:
                cursor_y -= body_size
            else:
                cursor_y -= L_body
            _text(c, line, text_x, cursor_y, default_font, body_size)

        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # Coordonnées (mail / téléphone / web) – icônes facultatives
    icon_h = body_size

    email = ours_cfg.get("email", "")
    phone = ours_cfg.get("phone", "")
    site  = ours_cfg.get("site", "")

    if email:
        cursor_y -= body_size
        used = _draw_icon(c, icons_map.get("mail", ""), rx, cursor_y - 1, icon_h)
        _link(c, f"Courriel : {email}", f"mailto:{email}", rx + used + 4, cursor_y, default_font, body_size)
    if phone:
        cursor_y -= L_body
        used = _draw_icon(c, icons_map.get("phone", ""), rx, cursor_y - 1, icon_h)
        _text(c, f"Tél : {phone}", rx + used + 4, cursor_y, default_font, body_size)
    if site:
        cursor_y -= L_body
        used = _draw_icon(c, icons_map.get("web", ""), rx, cursor_y - 1, icon_h)
        site_url = f"https://{site}" if not str(site).lower().startswith("http") else site
        _link(c, str(site), site_url, rx + used + 4, cursor_y, default_font, body_size)

    if email or phone or site:
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # Socials (inchangé ; s'il y a des icônes, place-les dans notes `icons_map`)
    for s in ours_cfg.get("socials", []):
        label = s.get("label", "")
        url   = s.get("url", "")
        icon  = s.get("icon", "")
        if not label:
            continue
        cursor_y -= body_size
        used = _draw_icon(c, icon, rx, cursor_y - 1, icon_h)
        if url:
            _link(c, label, url, rx + used + 4, cursor_y, default_font, body_size)
        else:
            _text(c, label, rx + used + 4, cursor_y, default_font, body_size)

    if ours_cfg.get("socials"):
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # Notes – avec icônes :
    #   - soit items dict: { text: "...", icon: "path.png" }
    #   - soit strings + mapping icons_map['riso'|'volunteer'|'cover'] selon le contenu
    notes_raw = ours_cfg.get("notes", []) or []
    for note in notes_raw:
        if isinstance(note, dict):
            text = note.get("text", "")
            icon = note.get("icon", "")
        else:
            text = str(note)
            low = text.lower()
            if "riso" in low:
                icon = icons_map.get("riso", "")
            elif "bénévol" in low or "benevol" in low:
                icon = icons_map.get("volunteer", "")
            elif "dessin" in low or "couverture" in low:
                icon = icons_map.get("cover", "")
            else:
                icon = ""

        if not text:
            continue

        # Word-wrap pour rester dans la colonne
        left_indent = 0.0
        if icon:
            used = _draw_icon(c, icon, rx, cursor_y - body_size + 1, icon_h)
            left_indent = used + 4

        wrapped = _wrap_text(c, text, rw - left_indent, default_font, body_size)
        for i, line in enumerate(wrapped):
            cursor_y -= body_size if i == 0 else (body_size * 1.05)
            _text(c, line, rx + left_indent, cursor_y, default_font, body_size)

        # espace entre notes
        cursor_y -= 2

    if notes_raw:
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # Ligne "Visuel : …" (si cfg.auteur_couv présent)
    if getattr(cfg, "auteur_couv", ""):
        cursor_y -= body_size
        vis = f"Visuel : {cfg.auteur_couv}"
        if getattr(cfg, "auteur_couv_url", ""):
            _link(c, vis, cfg.auteur_couv_url, rx, cursor_y, default_font, body_size)
        else:
            _text(c, vis, rx, cursor_y, default_font, body_size)

        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # QR code final
    qr_cfg = ours_cfg.get("qr", {}) or {}
    qr_url = qr_cfg.get("url", "")
    qr_title = qr_cfg.get("title", "")
    qr_size = float(qr_cfg.get("size_mm", 28)) * mm
    qr_gap  = float(qr_cfg.get("top_gap", 8))

    if qr_url:
        if qr_title:
            cursor_y -= body_size
            _text(c, qr_title, rx, cursor_y, default_font, body_size)
        cursor_y -= (qr_gap + qr_size)
        _draw_qr(c, qr_url, rx, cursor_y, qr_size)


# --------------------------------------------------------------------
# Ours “simple” (rendu existant) et couverture
# --------------------------------------------------------------------

def _split_ratio(split_info: Any, default: float = 0.42) -> float:
    """
    Extrait un ratio de split (logos/textes) depuis un dict/objet/float.
    """
    if split_info is None:
        return default
    if isinstance(split_info, (int, float)):
        return float(split_info)
    # objets/dicts possibles
    for k in ("ratio", "split", "left_ratio", "logos_ratio"):
        v = getattr(split_info, k, None) if not isinstance(split_info, dict) else split_info.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return default


def draw_s1(
    c: Canvas,
    sec: Union[dict, Any],
    ours_text: str,
    logos: List[str],
    font_name: str,
    leading_ratio: float,
    inner_pad: float,
    split_info: Any,
):
    """
    Rendu S1 historique :
      - logos à gauche
      - ours (Markdown -> plaintext Paragraph) à droite, aligné en haut
    """
    x = _sec_get(sec, "x"); y = _sec_get(sec, "y")
    w = _sec_get(sec, "w"); h = _sec_get(sec, "h")

    pad = float(inner_pad or 0.0)
    ratio = _split_ratio(split_info, default=0.42)
    left_w = w * ratio
    right_w = w - left_w

    # zone logos
    lx = x + pad
    ly = y + pad
    lw = left_w - 2 * pad
    lh = h - 2 * pad

    # zone texte
    tx = x + left_w + pad
    ty = y + pad
    tw = right_w - 2 * pad
    th = h - 2 * pad

    # --- Logos (grille simple 2 colonnes) ---
    cols = 2
    gutter = 6
    cell_w = (lw - gutter) / cols
    cell_h = cell_w * 0.6
    cx, cy = 0, 0
    for p in logos[:10]:
        try:
            img = ImageReader(p)
        except Exception:
            continue
        gx = lx + (cx * (cell_w + gutter))
        gy = ly + lh - (cy + 1) * (cell_h + gutter)
        if gy < ly:
            break
        c.drawImage(img, gx, gy, width=cell_w, height=cell_h, preserveAspectRatio=True, anchor='sw', mask='auto')
        cx += 1
        if cx >= cols:
            cx = 0
            cy += 1

    # --- Ours texte (Paragraph dans KeepInFrame, aligné haut) ---
    style = ParagraphStyle(
        name="Ours",
        fontName=font_name or "Helvetica",
        fontSize=9.5,
        leading=9.5 * float(leading_ratio or 1.15),
        alignment=TA_LEFT,
        spaceBefore=0,
        spaceAfter=0,
    )
    p = Paragraph(ours_text or "", style)
    kif = KeepInFrame(maxWidth=tw, maxHeight=th, content=[p], hAlign='LEFT', vAlign='TOP', mode='shrink')
    # wrap/draw
    kif.wrapOn(c, tw, th)
    kif.drawOn(c, tx, ty)

def draw_s1_rich(
    c: Canvas,
    sec,                      # frame S1 (dict ou obj avec x,y,w,h)
    cfg: "Config",
    ours_cfg: Dict[str, Any],
    logos: List[str],
    default_font: str,
    leading_ratio: float,
):
    """S1 => logos à gauche + ours 'riche' à droite (titre, contact, socials, notes, QR)."""

    # Frame S1
    x = getattr(sec, "x", None) or sec["x"]
    y = getattr(sec, "y", None) or sec["y"]
    w = getattr(sec, "w", None) or sec["w"]
    h = getattr(sec, "h", None) or sec["h"]

    pad = float(ours_cfg.get("padding", 6))
    split = float(ours_cfg.get("split", 0.42))
    left_w = w * split
    right_w = w - left_w

    # Sous-frames
    lx = x + pad
    ly = y + pad
    lw = left_w - 2 * pad
    lh = h - 2 * pad

    rx = x + left_w + pad
    ry = y + pad
    rw = right_w - 2 * pad
    rh = h - 2 * pad

    # 1) Grille logos existante (réutilise ta routine actuelle si tu en as une)
    #    Ici on recycle draw_s1 logos-only en lui passant un ours vide si besoin.
    try:
        draw_logos_grid = globals().get("draw_logos_grid")  # si tu as ce helper
    except Exception:
        draw_logos_grid = None
    if draw_logos_grid:
        draw_logos_grid(c, lx, ly, lw, lh, logos)
    else:
        # fallback simple: range les logos en colonnes
        from reportlab.lib.utils import ImageReader
        cols = 2
        gutter = 6
        cell_w = (lw - gutter) / cols
        cell_h = cell_w * 0.6
        cx, cy = 0, 0
        for idx, p in enumerate(logos[:10]):
            try:
                img = ImageReader(p)
            except Exception:
                continue
            gx = lx + (cx * (cell_w + gutter))
            gy = ly + lh - (cy + 1) * (cell_h + gutter)
            if gy < ly:
                break
            c.drawImage(img, gx, gy, width=cell_w, height=cell_h, preserveAspectRatio=True, anchor='sw', mask='auto')
            cx += 1
            if cx >= cols:
                cx = 0
                cy += 1

    # 2) Colonne droite (ours riche)
    title = ours_cfg.get("title", "")
    title_size = float(ours_cfg.get("title_size", 18))
    body_size = float(ours_cfg.get("body_size", 9.5))
    lead_ratio = float(ours_cfg.get("leading_ratio", leading_ratio))
    L_body = body_size * lead_ratio
    sep_style = ours_cfg.get("separators", "dotted")
    sep_th = float(ours_cfg.get("sep_thickness", 0.8))
    sep_gap = float(ours_cfg.get("sep_gap", 2))
    block_gap = float(ours_cfg.get("block_gap", 6))

    usable_top = ry + rh
    cursor_y = usable_top

    # Titre
    if title:
        c.setFont(default_font, title_size)
        cursor_y -= title_size
        _text(c, title, rx, cursor_y, default_font, title_size)
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    c.setFont(default_font, body_size)

    # Bloc adresse
    for line in ours_cfg.get("address_lines", []):
        cursor_y -= body_size
        _text(c, line, rx, cursor_y, default_font, body_size)
    if ours_cfg.get("address_lines"):
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    icon_h = body_size  # taille icône ≈ hauteur texte

    # Coordonnées
    email = ours_cfg.get("email", "")
    phone = ours_cfg.get("phone", "")
    site  = ours_cfg.get("site", "")
    icons = ours_cfg.get("icons", {})  # optionnel: {mail:..., phone:..., web:...}

    if email:
        cursor_y -= body_size
        used = _draw_icon(c, icons.get("mail", ""), rx, cursor_y - 1, icon_h)
        _link(c, f"Courriel : {email}", f"mailto:{email}", rx + used + 4, cursor_y, default_font, body_size)
    if phone:
        cursor_y -= L_body
        used = _draw_icon(c, icons.get("phone", ""), rx, cursor_y - 1, icon_h)
        _text(c, f"Tél : {phone}", rx + used + 4, cursor_y, default_font, body_size)
    if site:
        cursor_y -= L_body
        used = _draw_icon(c, icons.get("web", ""), rx, cursor_y - 1, icon_h)
        _link(c, site, f"https://{site}" if not site.startswith("http") else site, rx + used + 4, cursor_y, default_font, body_size)

    if email or phone or site:
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # Socials
    for s in ours_cfg.get("socials", []):
        label = s.get("label", "")
        url   = s.get("url", "")
        icon  = s.get("icon", "")
        if not label:
            continue
        cursor_y -= body_size
        used = _draw_icon(c, icon, rx, cursor_y - 1, icon_h)
        if url:
            _link(c, label, url, rx + used + 4, cursor_y, default_font, body_size)
        else:
            _text(c, label, rx + used + 4, cursor_y, default_font, body_size)

    if ours_cfg.get("socials"):
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # Notes diverses
    for line in ours_cfg.get("notes", []):
        lines = [line]  # simple; sinon, wrapper si tu veux
        for t in lines:
            cursor_y -= body_size
            _text(c, t, rx, cursor_y, default_font, body_size)

    if ours_cfg.get("notes"):
        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # Ligne "Visuel : …" (déjà injectée dans l’ours .md -> si tu tiens à l’afficher ici aussi)
    # Tu peux la tirer de cfg.auteur_couv / cfg.auteur_couv_url si tu préfères l’avoir ici :
    if getattr(cfg, "auteur_couv", ""):
        cursor_y -= body_size
        vis = f"Visuel : {cfg.auteur_couv}"
        if getattr(cfg, "auteur_couv_url", ""):
            _link(c, vis, cfg.auteur_couv_url, rx, cursor_y, default_font, body_size)
        else:
            _text(c, vis, rx, cursor_y, default_font, body_size)

        cursor_y = _block_gap_y(cursor_y, block_gap)
        _hr(c, rx, cursor_y, rw, style=sep_style, thick=sep_th, gap=sep_gap)
        cursor_y = _block_gap_y(cursor_y, block_gap)

    # QR code
    qr_cfg = ours_cfg.get("qr", {}) or {}
    qr_url = qr_cfg.get("url", "")
    qr_title = qr_cfg.get("title", "")
    qr_size = float(qr_cfg.get("size_mm", 28)) * mm
    qr_gap  = float(qr_cfg.get("top_gap", 8))

    if qr_url:
        if qr_title:
            cursor_y -= body_size
            _text(c, qr_title, rx, cursor_y, default_font, body_size)
        cursor_y -= (qr_gap + qr_size)
        _draw_qr(c, qr_url, rx, cursor_y, qr_size)


def draw_s2_cover(
    c: Canvas,
    sec: Union[dict, Any],
    cover_path: Optional[str],
    inner_pad: float,
):
    """
    Dessine l'image de couverture (S2), pleine largeur dans la frame, en conservant le ratio.
    """
    if not cover_path or not os.path.exists(cover_path):
        return
    x = _sec_get(sec, "x"); y = _sec_get(sec, "y")
    w = _sec_get(sec, "w"); h = _sec_get(sec, "h")

    pad = float(inner_pad or 0.0)
    box_x = x + pad
    box_y = y + pad
    box_w = w - 2 * pad
    box_h = h - 2 * pad

    try:
        img = ImageReader(cover_path)
        iw, ih = img.getSize()
        if iw <= 0 or ih <= 0:
            return
        # fit-contain dans la box
        scale = min(box_w / iw, box_h / ih)
        dw = iw * scale
        dh = ih * scale
        ox = box_x + (box_w - dw) / 2.0
        oy = box_y + (box_h - dh) / 2.0
        c.drawImage(img, ox, oy, width=dw, height=dh, preserveAspectRatio=True, mask='auto')
    except Exception:
        return

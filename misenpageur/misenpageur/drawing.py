# drawing.py
# -*- coding: utf-8 -*-
"""
S1 : colonne LOGOS (gauche) + OURS "rich" (droite)

- La colonne logos utilise TOUTE la hauteur de la section.
- L'ours est top-aligned, avec icônes mappées depuis le YAML
  (ours_rich.icons) et QR code cliquable.
- Compatible avec fonts custom : conf["fonts"] = {"regular": "...", "bold": "..."}.
- Debug : conf["debug_boxes"] = True affiche les cadres de layout.

Attendu dans config.yml (extrait) :
    ours_mode: rich
    ours_rich:
      split: 0.42
      padding: 6
      title: "Les Arts Services"
      title_size: 18
      body_size: 9.5
      separators: dotted
      icons:
        address: "misenpageur/assets/icons/address.png"
        mail:    "misenpageur/assets/icons/mail.png"
        phone:   "misenpageur/assets/icons/phone.png"
        web:     "misenpageur/assets/icons/web.png"
        riso:       "misenpageur/assets/icons/riso.png"
        volunteer:  "misenpageur/assets/icons/volunteer.png"
        cover:      "misenpageur/assets/icons/cover.png"
      address_lines:
        - "16, rue Guillaume Apollinaire"
        - "72000 LE MANS"
      email: "lebidul@live.fr"
      phone: "07 82 52 63 00"
      site:  "lebidul.com"
      notes:
        - { text: "Numéro imprimé en Riso à 2000 exemplaires", icon: "riso" }
        - { text: "Nous recrutons toujours des bénévoles…",   icon: "volunteer" }
        - { text: "Nous attendons vos dessins…",              icon: "cover" }
      qr:
        url: "https://agenda.lebidul.com"
        title: "Agenda culturel !"
        size_mm: 28
    auteur_couv: "@Steph"
    auteur_couv_url: "https://exemple.com/steph"

Optionnel (logos) :
    s1_logos:
      padding: 6        # padding interne (pt)
      gap: 8            # espace vertical entre logos (pt)
      fit: "width"      # "width" (par défaut) ou "height"
      items:
        - "misenpageur/assets/logos/biocoop.png"
        - "misenpageur/assets/logos/brasserie.png"
        - ...

Publié sous licence MIT.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF


# --------------------------------------------------------------------------------------
# Utils
# --------------------------------------------------------------------------------------

Number = Union[int, float]

def _box(sec) -> Tuple[Number, Number, Number, Number]:
    """Robuste : accepte dict-like ou objet .x/.y/.w/.h."""
    try:
        return sec["x"], sec["y"], sec["w"], sec["h"]
    except Exception:
        return sec.x, sec.y, sec.w, sec.h  # type: ignore[attr-defined]


def _fonts(conf: dict) -> Tuple[str, str]:
    """Retourne (regular, bold) à partir de conf["fonts"]. Fallback Helvetica."""
    fonts = conf.get("fonts") or {}
    reg = fonts.get("regular") or "Helvetica"
    bold = fonts.get("bold") or "Helvetica-Bold"
    return reg, bold


def _text_width(text: str, font_name: str, size: Number) -> float:
    return pdfmetrics.stringWidth(text or "", font_name, size)


def _norm_url(url: str) -> str:
    if not url:
        return url
    u = url.strip()
    if u.startswith(("http://", "https://", "mailto:", "tel:")):
        return u
    if "@" in u and " " not in u:
        return "mailto:" + u
    if all(c.isdigit() or c in " +().-" for c in u):
        return "tel:" + u
    return "https://" + u


# --------------------------------------------------------------------------------------
# Icons & QR
# --------------------------------------------------------------------------------------

def _icon_path(icon_key_or_path: str, icons_map: Dict[str, str], assets_root: Path) -> str:
    """Accepte clé ('riso') ou chemin relatif/absolu. Retourne un chemin absolu."""
    if icon_key_or_path in icons_map:
        p = assets_root / icons_map[icon_key_or_path]
    else:
        p = assets_root / icon_key_or_path
    return str(p.resolve())


def draw_icon(canvas, x_left: Number, y_top: Number, size_pt: Number,
              icon_key_or_path: str, icons_map: Dict[str, str], assets_root: Path) -> bool:
    """Dessine une icône carrée dont le coin SUPÉRIEUR GAUCHE est (x_left, y_top)."""
    try:
        path = _icon_path(icon_key_or_path, icons_map, assets_root)
        canvas.drawImage(
            path,
            x_left,
            y_top - size_pt,
            width=size_pt,
            height=size_pt,
            preserveAspectRatio=True,
            mask="auto",
        )
        return True
    except Exception:
        return False


def draw_qr(canvas, x: Number, y: Number, w: Number, h: Number, qr_conf: Optional[dict]) -> float:
    """Dessine un QR en haut-droite du bloc (x,y,w,h). Retourne la taille (pt) du QR ou 0."""
    if not qr_conf:
        return 0.0
    url = (qr_conf or {}).get("url")
    if not url:
        return 0.0

    size_pt = float(qr_conf.get("size_mm") or 28) * mm
    pad = 6
    qr_x = x + w - pad - size_pt
    qr_y = y + h - pad - size_pt

    widget = qr.QrCodeWidget(url)
    bounds = widget.getBounds()
    bw = bounds[2] - bounds[0]
    bh = bounds[3] - bounds[1]
    scale = min(size_pt / bw, size_pt / bh)

    d = Drawing(size_pt, size_pt)
    d.add(widget)
    d.transform(scale, 0, 0, scale, 0, 0)
    renderPDF.draw(d, canvas, qr_x, qr_y)

    # Lien cliquable
    canvas.linkURL(url, (qr_x, qr_y, qr_x + size_pt, qr_y + size_pt), relative=0, thickness=0)

    title = qr_conf.get("title")
    if title:
        canvas.setFont("Helvetica", 8.5)  # titre discret
        canvas.drawString(qr_x, qr_y - 10, title)

    return size_pt


# --------------------------------------------------------------------------------------
# Wrapping text
# --------------------------------------------------------------------------------------

def wrap_text(text: str, font_name: str, size: Number, max_width: Number) -> List[str]:
    """Word-wrap simple pour dessiner des paragraphes en drawString."""
    text = (text or "").replace("\n", " ").strip()
    if not text:
        return []
    words = text.split()
    lines: List[str] = []
    cur: List[str] = []
    cur_w = 0.0
    space_w = _text_width(" ", font_name, size)

    for w in words:
        ww = _text_width(w, font_name, size)
        if not cur:
            cur = [w]
            cur_w = ww
            continue
        if cur_w + space_w + ww <= max_width:
            cur.append(w)
            cur_w += space_w + ww
        else:
            lines.append(" ".join(cur))
            cur = [w]
            cur_w = ww
    if cur:
        lines.append(" ".join(cur))
    return lines


# --------------------------------------------------------------------------------------
# LOGOS (colonne gauche)
# --------------------------------------------------------------------------------------

def draw_logos_column(canvas, x: Number, y: Number, w: Number, h: Number,
                      conf: dict, assets_root: Path) -> None:
    """
    Empile les logos verticalement avec un espacement constant.
    Config attendue : conf["s1_logos"] = {padding, gap, fit, items: [paths...]}

    Si conf["s1_logos"] est absent, la fonction ne fait rien (safe).
    """
    s1 = conf.get("s1_logos") or {}
    items: List[str] = s1.get("items") or []
    if not items:
        return

    pad = float(s1.get("padding", 6))
    gap = float(s1.get("gap", 8))
    fit_mode = (s1.get("fit") or "width").lower()  # "width" or "height"

    inner_x = x + pad
    inner_y = y + pad
    inner_w = w - 2 * pad
    inner_h = h - 2 * pad

    # Calcule une hauteur par logo simple : on répartit à peu près la hauteur
    # en tenant compte des gaps (n-1).
    n = len(items)
    if n <= 0:
        return
    total_gap = gap * max(0, n - 1)
    # taille max disponible (si fit "height", on s'en servira directement)
    max_h_per_logo = max(1.0, (inner_h - total_gap) / n)

    y_cursor = inner_y + inner_h  # top
    for p in items:
        try:
            path = str((assets_root / p).resolve())
            img = ImageReader(path)
            iw, ih = img.getSize()
        except Exception:
            # Passe si l'image est introuvable
            iw, ih, img = 100, 100, None

        if fit_mode == "height":
            target_h = max_h_per_logo
            scale = target_h / ih
            target_w = iw * scale
            if target_w > inner_w:
                scale = inner_w / iw
                target_w = inner_w
                target_h = ih * scale
        else:
            # fit width (par défaut)
            target_w = inner_w
            scale = target_w / iw
            target_h = ih * scale
            if target_h > max_h_per_logo:
                target_h = max_h_per_logo
                scale = target_h / ih
                target_w = iw * scale

        y_cursor -= target_h
        if img:
            canvas.drawImage(
                path,
                inner_x,
                y_cursor,
                width=target_w,
                height=target_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        y_cursor -= gap
        if (y_cursor - gap) < inner_y:
            break  # plus de place, on arrête


# --------------------------------------------------------------------------------------
# OURS RICH (colonne droite)
# --------------------------------------------------------------------------------------

def draw_ours_rich(canvas, x: Number, y: Number, w: Number, h: Number,
                   conf: dict, assets_root: Path) -> None:
    """
    Dessine l'ours "rich" : titre, adresse, email/tel/site (avec icônes),
    séparateurs, notes (icônes), crédit visuel (lien), QR en haut-droite.
    """
    pad = float(conf.get("padding", 6))
    title = conf.get("title", "")
    title_size = float(conf.get("title_size", 18))
    body_size = float(conf.get("body_size", 9.5))
    icons_map: Dict[str, str] = conf.get("icons", {}) or {}

    font_reg, font_bold = _fonts(conf)

    top = y + h
    cx = x + pad
    cw = w - 2 * pad
    cursor = top - pad

    # Titre
    if title:
        canvas.setFont(font_bold, title_size)
        canvas.drawString(cx, cursor - title_size, title)
        cursor -= (title_size + 6)

    canvas.setFont(font_reg, body_size)

    # Helper ligne avec icône + wrapping
    def line_with_icon(icon_key: Optional[str], text: Optional[str], indent_no_icon: float = 18.0):
        nonlocal cursor
        if not text:
            return
        icon_px = body_size + 2
        icon_drawn = False
        tx = cx
        max_w = cw
        if icon_key:
            icon_drawn = draw_icon(canvas, cx, cursor, icon_px, icon_key, icons_map, assets_root)
            if icon_drawn:
                tx = cx + icon_px + 4
                max_w = cw - (icon_px + 4)

        lines = wrap_text(text, font_reg, body_size, max_w)
        for i, ln in enumerate(lines):
            canvas.drawString(tx if i == 0 else (cx + (icon_px + 4 if icon_drawn else indent_no_icon)),
                              cursor - body_size, ln)
            cursor -= (body_size + 2)

    # Adresse
    addr = conf.get("address_lines") or []
    if addr:
        # première ligne avec icône
        line_with_icon("address", addr[0])
        # suivantes sans icône
        for extra in addr[1:]:
            line_with_icon(None, extra)

    # Mail / Phone / Web (avec liens cliquables)
    def linked_line(icon_key: str, raw: Optional[str]):
        if not raw:
            return
        nonlocal cursor
        text = raw.strip()
        url = _norm_url(text)
        x0 = cx
        y0 = cursor - body_size - 2
        line_with_icon(icon_key, text)
        # on mesure la dernière ligne écrite (simple : on prend la première ligne)
        wtxt = _text_width(text, font_reg, body_size)
        canvas.linkURL(url, (x0, y0, x0 + wtxt + 40, y0 + body_size + 6), relative=0, thickness=0)

    linked_line("mail", conf.get("email"))
    linked_line("phone", conf.get("phone"))
    linked_line("web", conf.get("site"))

    # Séparateur optionnel
    if (conf.get("separators") or "").lower() == "dotted":
        canvas.setDash(1, 2)
        canvas.line(cx, cursor - 4, cx + cw, cursor - 4)
        canvas.setDash()
        cursor -= 10

    # Notes avec icônes
    for note in conf.get("notes", []) or []:
        icon_key = note.get("icon")
        text = note.get("text")
        if not text:
            continue
        line_with_icon(icon_key, text)

    # Crédit visuel
    a = conf.get("auteur_couv") or ""
    a_url = conf.get("auteur_couv_url")
    if a:
        txt = f"Visuel : {a}"
        canvas.drawString(cx, cursor - body_size, txt)
        if a_url:
            w_txt = _text_width(txt, font_reg, body_size)
            canvas.linkURL(a_url, (cx, cursor - body_size - 2, cx + w_txt, cursor + 2),
                           relative=0, thickness=0)
        cursor -= (body_size + 6)

    # QR en haut-droite (ne consomme pas la hauteur du contenu)
    draw_qr(canvas, x, y, w, h, conf.get("qr"))


# --------------------------------------------------------------------------------------
# S1 : orchestration
# --------------------------------------------------------------------------------------

def draw_s1(canvas, sec, conf: dict, assets_root: Union[str, Path]) -> None:
    """
    S1 : logos (gauche) + ours (droite).
    - La colonne logos utilise TOUTE la hauteur de la section.
    - L'ours est dessiné à droite (mode 'rich' si configuré).
    - assets_root peut être un str ou un Path.
    """
    assets_root = Path(assets_root)
    x, y, w, h = _box(sec)

    ours_mode = conf.get("ours_mode", "rich")
    ours_conf = dict(conf.get("ours_rich", {}) or {})
    # Propager les métadonnées auteur de couv définies à la racine
    for k in ("auteur_couv", "auteur_couv_url"):
        if conf.get(k) is not None:
            ours_conf[k] = conf[k]

    split = float(ours_conf.get("split", 0.42))
    split = max(0.10, min(0.90, split))  # garde-fous

    left_w = w * split
    right_w = w - left_w
    right_x = x + left_w

    # LOGOS (pleine hauteur)
    draw_logos_column(canvas, x, y, left_w, h, conf, assets_root)

    # OURS
    if ours_mode == "rich":
        draw_ours_rich(canvas, right_x, y, right_w, h, ours_conf, assets_root)
    else:
        # Fallback très simple (texte brut)
        font_reg, font_bold = _fonts(conf)
        pad = float(ours_conf.get("padding", 6))
        cx, cy, cw, ch = right_x + pad, y + pad, right_w - 2 * pad, h - 2 * pad
        top = y + h - pad
        canvas.setFont(font_bold, float(ours_conf.get("title_size", 18)))
        canvas.drawString(cx, top - float(ours_conf.get("title_size", 18)),
                          ours_conf.get("title", ""))
        canvas.setFont(font_reg, float(ours_conf.get("body_size", 9.5)))
        canvas.drawString(cx, top - 28, ours_conf.get("email", ""))

    # Debug boxes
    if conf.get("debug_boxes"):
        canvas.saveState()
        try:
            canvas.setLineWidth(0.5)
            canvas.setDash(2, 2)
            # Section
            canvas.setStrokeColorRGB(1, 0, 0)
            canvas.rect(x, y, w, h, stroke=1, fill=0)
            # Colonne logos
            canvas.setStrokeColorRGB(0, 0, 1)
            canvas.rect(x, y, left_w, h, stroke=1, fill=0)
            # Colonne ours
            canvas.setStrokeColorRGB(0, 0.5, 0)
            canvas.rect(right_x, y, right_w, h, stroke=1, fill=0)
        finally:
            canvas.restoreState()

# =========================
# Compat / Helpers attendus
# =========================

# Alias rétro-compat : si un ancien code appelle draw_s1_rich
def draw_s1_rich(canvas, sec, conf, assets_root):
    return draw_s1(canvas, sec, conf, assets_root)

# list_images: lister les images d'un dossier
from pathlib import Path
def list_images(folder, exts=(".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".gif")):
    p = Path(folder)
    if not p.exists():
        return []
    exts_low = tuple(e.lower() for e in exts)
    return sorted(str(fp) for fp in p.iterdir() if fp.is_file() and fp.suffix.lower() in exts_low)

# paragraph_style: petit wrapper pour créer un ParagraphStyle
from reportlab.lib.styles import ParagraphStyle
def paragraph_style(font_name="Helvetica", font_size=10.0, leading_ratio=1.25, **kw):
    leading = kw.pop("leading", None)
    if leading is None:
        leading = round(float(font_size) * float(leading_ratio))
    return ParagraphStyle(name=f"{font_name}-{font_size}",
                          fontName=font_name, fontSize=font_size, leading=leading, **kw)

# draw_s2_cover: place l'image de couverture centrée et à l'échelle dans S2
from reportlab.lib.utils import ImageReader
def draw_s2_cover(canvas, sec, conf, assets_root):
    """
    conf peut contenir:
      - "cover_image": chemin vers l'image finale à placer
      - sinon (optionnel) "cover": {"image": "..."}
    """
    # _box vient du fichier (helper déjà défini plus haut)
    x, y, w, h = _box(sec)

    cover_path = (conf or {}).get("cover_image") \
                 or ((conf or {}).get("cover") or {}).get("image")
    if not cover_path:
        return

    p = Path(assets_root) / cover_path if not Path(cover_path).is_absolute() else Path(cover_path)
    p = p.resolve()
    if not p.exists():
        return

    try:
        img = ImageReader(str(p))
        iw, ih = img.getSize()
    except Exception:
        return

    # Fit dans la boîte en conservant le ratio
    scale = min(w / iw, h / ih)
    tw, th = iw * scale, ih * scale
    ox = x + (w - tw) / 2.0
    oy = y + (h - th) / 2.0

    canvas.drawImage(str(p), ox, oy, width=tw, height=th,
                     preserveAspectRatio=True, mask="auto")


# en tête de fichier si pas déjà présent
from __future__ import annotations
import re
from typing import List, Tuple
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, KeepInFrame
from reportlab.pdfbase import pdfmetrics
from .drawing import paragraph_style
from .layout import Section
from .html_utils import sanitize_inline_markup

def _apply_glyph_fallbacks(text: str) -> str:
    text = text.replace("&euro;", "€")
    if "DejaVuSans" in pdfmetrics.getRegisteredFontNames():
        text = text.replace("€", '<font name="DejaVuSans">€</font>')
    return text

def _strip_head_tail_breaks(s: str) -> str:
    # retire <br/> de tête/queue et compresse les suites
    s = re.sub(r"^(?:\s*<br/>\s*)+", "", s)
    s = re.sub(r"(?:\s*<br/>\s*)+$", "", s)
    s = re.sub(r"(?:\s*<br/>\s*){3,}", "<br/><br/>", s)
    return s.strip()

def measure_fit_at_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float
) -> int:
    """Combien de paragraphes tiennent à font_size (sans shrink), après nettoyage strict."""
    w = max(1.0, section.w - 2*inner_pad)
    h = max(1.0, section.h - 2*inner_pad)
    style = paragraph_style(font_name, font_size, leading_ratio)

    used = 0
    total_h = 0.0
    for t in paras_text:
        st = _strip_head_tail_breaks(sanitize_inline_markup(t))
        if not st:
            continue  # zappe les vides réels
        p = Paragraph(st, style)
        _w, ph = p.wrap(w, h)
        if used == 0 or total_h + ph <= h:
            used += 1
            total_h += ph
        else:
            break
    return used

def draw_section_fixed_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float
) -> Tuple[List[str], float]:
    """Dessine la section à taille commune en top-align strict (sans KeepInFrame)."""
    # 1) Sanitize + trim + drop vides (identique à la mesure)
    cleaned: List[str] = []
    for t in paras_text:
        st = _strip_head_tail_breaks(sanitize_inline_markup(t))
        if st:
            cleaned.append(st)
    if not cleaned:
        return [], font_size

    # 2) Zone & style
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2*inner_pad)
    h  = max(1.0, section.h - 2*inner_pad)
    y_top = y0 + h  # on part du haut et on descend

    style = paragraph_style(font_name, font_size, leading_ratio)  # justification incluse
    flows = [Paragraph(_apply_glyph_fallbacks(st), style) for st in cleaned]

    # 3) Dessin manuel, paragraphe par paragraphe (top-align réel)
    c.saveState()
    y = y_top
    for p in flows:
        pw, ph = p.wrap(w, h)           # calcul hauteur à largeur w
        y_draw = y - ph                 # placer le paragraphe juste sous la "ligne" courante
        if y_draw < y0:                 # sécurité (on ne devrait pas déborder avec fs commun)
            break
        p.drawOn(c, x0, y_draw)
        y = y_draw
    c.restoreState()

    return cleaned, font_size


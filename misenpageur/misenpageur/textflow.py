# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import List, Tuple

from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics

from .layout import Section
from .drawing import paragraph_style
from .html_utils import sanitize_inline_markup


# ---------- Helpers communs ----------

def _apply_glyph_fallbacks(text: str) -> str:
    text = text.replace("&euro;", "€")
    if "DejaVuSans" in pdfmetrics.getRegisteredFontNames():
        text = text.replace("€", '<font name="DejaVuSans">€</font>')
    return text


def _strip_head_tail_breaks(s: str) -> str:
    """Retire <br/> de tête/queue et compresse les suites."""
    s = re.sub(r"^(?:\s*<br/>\s*)+", "", s)
    s = re.sub(r"(?:\s*<br/>\s*)+$", "", s)
    s = re.sub(r"(?:\s*<br/>\s*){3,}", "<br/><br/>", s)
    return s.strip()


def _mk_para(txt: str, font_name: str, font_size: float, leading_ratio: float) -> Paragraph:
    style = paragraph_style(font_name, font_size, leading_ratio)
    cleaned = _strip_head_tail_breaks(sanitize_inline_markup(txt))
    return Paragraph(_apply_glyph_fallbacks(cleaned), style)


# ---------- Mesure pour la recherche de taille commune ----------

def measure_fit_at_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float
) -> int:
    """
    Combien de paragraphes (entiers) tiennent dans la section à une taille donnée (sans shrink),
    en partant du début de 'paras_text'.
    """
    w = max(1.0, section.w - 2 * inner_pad)
    h = max(1.0, section.h - 2 * inner_pad)

    used = 0
    total_h = 0.0
    for t in paras_text:
        p = _mk_para(t, font_name, font_size, leading_ratio)
        _w, ph = p.wrap(w, h)
        if used == 0 or (total_h + ph) <= h:
            used += 1
            total_h += ph
        else:
            break
    return used


# ---------- Rendu manuel top-align (sans KeepInFrame) ----------

def draw_section_fixed_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float
) -> Tuple[List[str], float]:
    """Dessine la section (paragraphes entiers) en top-align STRICT (aucun blanc en tête)."""
    # Nettoyage + drop vides
    cleaned: List[str] = []
    for t in paras_text:
        st = _strip_head_tail_breaks(sanitize_inline_markup(t))
        if st:
            cleaned.append(st)
    if not cleaned:
        return [], font_size

    # Zone & style
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    style = paragraph_style(font_name, font_size, leading_ratio)
    flows = [Paragraph(_apply_glyph_fallbacks(st), style) for st in cleaned]

    # Dessin paragraphe par paragraphe depuis le haut
    c.saveState()
    y = y_top
    for p in flows:
        _w, ph = p.wrap(w, h)
        y_draw = y - ph
        if y_draw < y0:
            break
        p.drawOn(c, x0, y_draw)
        y = y_draw
    c.restoreState()

    return cleaned, font_size


def draw_section_fixed_fs_with_prelude(
    c: canvas.Canvas,
    section: Section,
    prelude_flows: List[Paragraph],
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float
) -> None:
    """
    Dessine d'abord 'prelude_flows' (morceau césuré provenant de la section précédente),
    puis des paragraphes entiers. Top-align strict.
    """
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    c.saveState()
    y = y_top

    # 1) préface (déjà en Paragraph)
    for pf in prelude_flows or []:
        _w, ph = pf.wrap(w, h)
        y_draw = y - ph
        if y_draw < y0:
            break
        pf.drawOn(c, x0, y_draw)
        y = y_draw

    # 2) paragraphes entiers
    style = paragraph_style(font_name, font_size, leading_ratio)
    for raw in paras_text or []:
        cleaned = _strip_head_tail_breaks(sanitize_inline_markup(raw))
        if not cleaned:
            continue
        p = Paragraph(_apply_glyph_fallbacks(cleaned), style)
        _w, ph = p.wrap(w, h)
        y_draw = y - ph
        if y_draw < y0:
            break
        p.drawOn(c, x0, y_draw)
        y = y_draw

    c.restoreState()


def draw_section_fixed_fs_with_tail(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    tail_flows: List[Paragraph],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float
) -> None:
    """
    Variante : dessine d'abord des paragraphes entiers, puis 'tail_flows' (morceau césuré
    placé en fin de section). Top-align strict.
    """
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    c.saveState()
    y = y_top

    # 1) paragraphes entiers
    style = paragraph_style(font_name, font_size, leading_ratio)
    for raw in paras_text or []:
        cleaned = _strip_head_tail_breaks(sanitize_inline_markup(raw))
        if not cleaned:
            continue
        p = Paragraph(_apply_glyph_fallbacks(cleaned), style)
        _w, ph = p.wrap(w, h)
        y_draw = y - ph
        if y_draw < y0:
            break
        p.drawOn(c, x0, y_draw)
        y = y_draw

    # 2) tail (morceau de fin pour A si césure A→B)
    for tf in tail_flows or []:
        _w, ph = tf.wrap(w, h)
        y_draw = y - ph
        if y_draw < y0:
            break
        tf.drawOn(c, x0, y_draw)
        y = y_draw

    c.restoreState()


# ---------- Planification par paire avec césure A→B autorisée ----------
def plan_pair_with_split(
    c: canvas.Canvas,
    secA: Section, secB: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    split_min_gain_ratio: float = 0.10,
) -> Tuple[List[str], List[Paragraph], List[Paragraph], List[str], List[str]]:
    """
    Simule l’écoulement dans (A puis B) en autorisant UNE césure A→B sur le premier
    paragraphe qui dépasse A, **seulement si** le gain de remplissage est significatif.
    - split_min_gain_ratio: part minimale de la hauteur de A à combler par la césure
      (ex. 0.10 => au moins 10% de hA). On exige aussi >= ~1 interligne.

    Retourne :
      - A_full     : paragraphes (entiers) pour A
      - A_tail     : liste de Paragraph (morceau césuré final pour A), sinon []
      - B_prelude  : liste de Paragraph (début césuré en tête de B), sinon []
      - B_full     : paragraphes (entiers) pour B
      - remaining  : paragraphes non placés (entiers) pour la paire suivante
    """
    wA = max(1.0, secA.w - 2 * inner_pad)
    hA = max(1.0, secA.h - 2 * inner_pad)
    wB = max(1.0, secB.w - 2 * inner_pad)
    hB = max(1.0, secB.h - 2 * inner_pad)

    # Leading pour fixer une taille mini de césure (au moins ~1 ligne)
    styleA = paragraph_style(font_name, font_size, leading_ratio)
    min_gain_pt = max(split_min_gain_ratio * hA, 0.9 * styleA.leading)

    remA = hA
    remB = hB

    A_full: List[str] = []
    A_tail: List[Paragraph] = []
    B_prelude: List[Paragraph] = []
    B_full: List[str] = []

    i = 0
    n = len(paras_text)

    # Remplir A (entier + éventuelle césure significative)
    while i < n and remA > 0:
        raw = paras_text[i]
        p = _mk_para(raw, font_name, font_size, leading_ratio)
        _, full_h = p.wrap(wA, 1e6)

        if full_h <= remA:
            A_full.append(raw)
            remA -= full_h
            i += 1
            continue

        # Proposer une césure A→B seulement si possible ET significative
        if remA > 0 and full_h <= (remA + remB):
            parts = p.split(wA, remA)  # coupe au reste de A
            if parts and len(parts) >= 2:
                # Mesures
                _w0, h0 = parts[0].wrap(wA, remA)  # gain réel en A
                if h0 >= min_gain_pt:
                    needed_B = 0.0
                    for k in range(1, len(parts)):
                        _wk, hk = parts[k].wrap(wB, remB)
                        needed_B += hk
                    if needed_B <= remB:
                        # Commit : on accepte la césure
                        A_tail.append(parts[0])
                        remA -= h0
                        for k in range(1, len(parts)):
                            _wk, hk = parts[k].wrap(wB, remB)
                            B_prelude.append(parts[k])
                            remB -= hk
                        i += 1
                    # sinon: césure refusaée (ne rentre pas en B) -> on ne césure pas
                # sinon: pas assez de gain -> pas de césure
            # Dans tous les cas, on arrête A ici (le paragraphe courant reste entier pour B)
        break

    # Remplir B (préface déjà comptée), avec des paragraphes entiers
    while i < n and remB > 0:
        raw = paras_text[i]
        p = _mk_para(raw, font_name, font_size, leading_ratio)
        _, h = p.wrap(wB, 1e6)
        if h <= remB:
            B_full.append(raw)
            remB -= h
            i += 1
        else:
            break

    remaining = paras_text[i:]
    return A_full, A_tail, B_prelude, B_full, remaining

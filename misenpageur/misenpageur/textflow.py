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


# ---------- Classification "date" vs "événement" ----------
# Événements = lignes qui DÉBUTENT par le caractère ❑ (standard workflow).
# On ajoute quelques équivalents proches pour la robustesse (□, ■, &#9643;).
_BULLET_RE = re.compile(r'^\s*(?:❑|□|■|&#9643;)\s*', re.I)

def _is_event(raw: str) -> bool:
    return bool(_BULLET_RE.match(raw or ""))


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


# ---------- Espacement paramétrable (date vs événement) ----------

def _spacing_defaults(spacing: dict | None, style_leading: float) -> dict:
    s = spacing or {}
    return {
        "date_spaceBefore":                         float(s.get("date_spaceBefore", 6.0)),
        "date_spaceAfter":                          float(s.get("date_spaceAfter", 3.0)),
        "event_spaceBefore":                        float(s.get("event_spaceBefore", 1.0)),
        "event_spaceAfter":                         float(s.get("event_spaceAfter", 1.0)),
        "event_spaceAfter_perLine":                 float(s.get("event_spaceAfter_perLine", 0.4)),
        "min_event_spaceAfter":                     float(s.get("min_event_spaceAfter", 1.0)),
        "first_non_event_spaceBefore_in_S5":        float(s.get("first_non_event_spaceBefore_in_S5", 0.0)),
    }

def _event_space_after(ph: float, leading: float, base: float, per_line: float, min_sa: float) -> float:
    lines = max(1, int(round(ph / max(1.0, leading))))
    extra = max(0, lines - 1) * per_line
    return max(min_sa, base + extra)


# ---------- Rendu manuel top-align (sans KeepInFrame) + espacement ----------

def draw_section_fixed_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str | None = None,
    spacing: dict | None = None,
) -> Tuple[List[str], float]:
    """Dessine la section (paragraphes entiers) en top-align STRICT, avec espacement date/événement."""
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
    lead = style.leading
    S = _spacing_defaults(spacing, lead)

    # exception : pas de spaceBefore pour la 1re ligne non-événement en S5
    first_non_event_seen_in_S5 = False

    c.saveState()
    y = y_top
    for raw in cleaned:
        kind = "event" if _is_event(raw) else "date"
        p = Paragraph(_apply_glyph_fallbacks(raw), style)
        _w, ph = p.wrap(w, h)

        # spaceBefore
        if kind == "date":
            if section_name == "S5" and not first_non_event_seen_in_S5:
                sb = S["first_non_event_spaceBefore_in_S5"]
                first_non_event_seen_in_S5 = True
            else:
                sb = S["date_spaceBefore"]
        else:
            sb = S["event_spaceBefore"]

        # spaceAfter
        if kind == "date":
            sa = S["date_spaceAfter"]
        else:
            sa = _event_space_after(ph, lead, S["event_spaceAfter"], S["event_spaceAfter_perLine"], S["min_event_spaceAfter"])

        needed = sb + ph + sa
        if (y - needed) < y0:
            break
        y -= sb
        p.drawOn(c, x0, y - ph)
        y -= ph + sa

    c.restoreState()
    return cleaned, font_size


def draw_section_fixed_fs_with_prelude(
    c: canvas.Canvas,
    section: Section,
    prelude_flows: List[Paragraph],
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str | None = None,
    spacing: dict | None = None,
) -> None:
    """Dessine une préface (suite césurée) PUIS des paragraphes entiers, avec espacement."""
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    base = paragraph_style(font_name, font_size, leading_ratio)
    lead = base.leading
    S = _spacing_defaults(spacing, lead)

    first_non_event_seen_in_S5 = False

    c.saveState()
    y = y_top

    # 1) préface (continuation : pas de spaceBefore, petit spaceAfter)
    for pf in prelude_flows or []:
        _w, ph = pf.wrap(w, h)
        sa = S["event_spaceAfter"]
        needed = ph + sa
        if (y - needed) < y0:
            c.restoreState()
            return
        pf.drawOn(c, x0, y - ph)
        y -= ph + sa

    # 2) paragraphes entiers
    for raw in (paras_text or []):
        kind = "event" if _is_event(raw) else "date"
        p = Paragraph(_apply_glyph_fallbacks(_strip_head_tail_breaks(sanitize_inline_markup(raw))), base)
        _w, ph = p.wrap(w, h)

        if kind == "date":
            if section_name == "S5" and not first_non_event_seen_in_S5:
                sb = S["first_non_event_spaceBefore_in_S5"]
                first_non_event_seen_in_S5 = True
            else:
                sb = S["date_spaceBefore"]
            sa = S["date_spaceAfter"]
        else:
            sb = S["event_spaceBefore"]
            sa = _event_space_after(ph, lead, S["event_spaceAfter"], S["event_spaceAfter_perLine"], S["min_event_spaceAfter"])

        needed = sb + ph + sa
        if (y - needed) < y0:
            break
        y -= sb
        p.drawOn(c, x0, y - ph)
        y -= ph + sa

    c.restoreState()


def draw_section_fixed_fs_with_tail(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    tail_flows: List[Paragraph],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str | None = None,
    spacing: dict | None = None,
) -> None:
    """Dessine des paragraphes entiers PUIS une 'tail' (fin césurée), avec espacement."""
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    base = paragraph_style(font_name, font_size, leading_ratio)
    lead = base.leading
    S = _spacing_defaults(spacing, lead)

    first_non_event_seen_in_S5 = False

    c.saveState()
    y = y_top

    # 1) paragraphes entiers
    for raw in (paras_text or []):
        kind = "event" if _is_event(raw) else "date"
        p = Paragraph(_apply_glyph_fallbacks(_strip_head_tail_breaks(sanitize_inline_markup(raw))), base)
        _w, ph = p.wrap(w, h)

        if kind == "date":
            if section_name == "S5" and not first_non_event_seen_in_S5:
                sb = S["first_non_event_spaceBefore_in_S5"]
                first_non_event_seen_in_S5 = True
            else:
                sb = S["date_spaceBefore"]
            sa = S["date_spaceAfter"]
        else:
            sb = S["event_spaceBefore"]
            sa = _event_space_after(ph, lead, S["event_spaceAfter"], S["event_spaceAfter_perLine"], S["min_event_spaceAfter"])

        needed = sb + ph + sa
        if (y - needed) < y0:
            c.restoreState()
            return
        y -= sb
        p.drawOn(c, x0, y - ph)
        y -= ph + sa

    # 2) tail (continuation : pas de spaceBefore ; petit spaceAfter)
    for tf in tail_flows or []:
        _w, ph = tf.wrap(w, h)
        sa = S["event_spaceAfter"]
        if (y - (ph + sa)) < y0:
            break
        tf.drawOn(c, x0, y - ph)
        y -= ph + sa

    c.restoreState()


# ---------- Planification par paire avec césure A→B autorisée (gain significatif) ----------

def plan_pair_with_split(
    c: canvas.Canvas,
    secA: Section, secB: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    split_min_gain_ratio: float = 0.10,
) -> Tuple[List[str], List[Paragraph], List[Paragraph], List[str], List[str]]:
    """
    Simule l’écoulement dans (A puis B) en autorisant UNE césure A→B sur le premier
    paragraphe qui dépasse A, seulement si le gain de remplissage est significatif.
    Retourne : A_full, A_tail, B_prelude, B_full, remaining
    """
    wA = max(1.0, secA.w - 2 * inner_pad)
    hA = max(1.0, secA.h - 2 * inner_pad)
    wB = max(1.0, secB.w - 2 * inner_pad)
    hB = max(1.0, secB.h - 2 * inner_pad)

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

        # Proposer une césure A→B si possible ET significative
        if remA > 0 and full_h <= (remA + remB):
            parts = p.split(wA, remA)  # coupe au reste de A
            if parts and len(parts) >= 2:
                _w0, h0 = parts[0].wrap(wA, remA)  # gain en A
                if h0 >= min_gain_pt:
                    needed_B = 0.0
                    for k in range(1, len(parts)):
                        _wk, hk = parts[k].wrap(wB, remB)
                        needed_B += hk
                    if needed_B <= remB:
                        # Commit césure
                        A_tail.append(parts[0])
                        remA -= h0
                        for k in range(1, len(parts)):
                            _wk, hk = parts[k].wrap(wB, remB)
                            B_prelude.append(parts[k])
                            remB -= hk
                        i += 1
                # sinon: gain insuffisant -> pas de césure
        # Dans tous les cas, on arrête A ici (le paragraphe courant restera entier pour B)
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

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
from .glyphs import apply_glyph_fallbacks
from .spacing import SpacingPolicy, SpacingConfig


# ---------- Classification "date" vs "événement" ----------
# Événements = lignes qui DÉBUTENT par ❑ (standard workflow).
# On ajoute quelques équivalents proches pour robustesse (□, ■, &#9643;).
_BULLET_RE = re.compile(r'^\s*(?:❑|□|■|&#9643;)\s*', re.I)

def _is_event(raw: str) -> bool:
    return bool(_BULLET_RE.match(raw or ""))


# ---------- Helpers communs ----------

def _strip_head_tail_breaks(s: str) -> str:
    """Retire <br/> de tête/queue et compresse les suites."""
    if not s:
        return ""
    s = re.sub(r"^(?:\s*<br/>\s*)+", "", s)
    s = re.sub(r"(?:\s*<br/>\s*)+$", "", s)
    s = re.sub(r"(?:\s*<br/>\s*){3,}", "<br/><br/>", s)
    return s.strip()

def _mk_para(txt: str, font_name: str, font_size: float, leading_ratio: float) -> Paragraph:
    style = paragraph_style(font_name, font_size, leading_ratio)
    cleaned = _strip_head_tail_breaks(sanitize_inline_markup(txt))
    return Paragraph(apply_glyph_fallbacks(cleaned), style)


# ---------- Mesure pour la recherche de taille commune (avec espacement) ----------

def measure_fit_at_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str,
    spacing_policy: SpacingPolicy,
) -> int:
    """
    Compte combien de paragraphes ENTIERs tiennent dans 'section' à font_size,
    en intégrant spaceBefore/spaceAfter via spacing_policy.
    """
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y  = y0 + h

    used = 0
    first_non_event_seen_in_S5 = False

    for t in paras_text:
        p = _mk_para(t, font_name, font_size, leading_ratio)
        _w, ph = p.wrap(w, 1e6)

        kind = "EVENT" if _is_event(t) else "DATE"
        sb = spacing_policy.space_before(kind if kind=="DATE" else "EVENT",
                                         section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind if kind=="DATE" else "EVENT", ph)

        need = sb + ph + sa
        if (y - need) < y0:
            break
        y -= need
        used += 1

    return used


# ---------- Rendu manuel top-align (sans KeepInFrame) + espacement ----------

def draw_section_fixed_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str,
    spacing_policy: SpacingPolicy,
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

    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    style = paragraph_style(font_name, font_size, leading_ratio)

    first_non_event_seen_in_S5 = False

    c.saveState()
    y = y_top
    for raw in cleaned:
        kind = "EVENT" if _is_event(raw) else "DATE"
        p = Paragraph(apply_glyph_fallbacks(raw), style)
        _w, ph = p.wrap(w, h)

        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)

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
    section_name: str,
    spacing_policy: SpacingPolicy,
) -> None:
    """Dessine une préface (suite césurée) PUIS des paragraphes entiers, avec espacement."""
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    base = paragraph_style(font_name, font_size, leading_ratio)

    first_non_event_seen_in_S5 = False

    c.saveState()
    y = y_top

    # 1) préface : pas de spaceBefore ; petit spaceAfter comme un EVENT "continuation"
    for pf in prelude_flows or []:
        _w, ph = pf.wrap(w, h)
        sa = spacing_policy.space_after("EVENT", ph)
        need = ph + sa
        if (y - need) < y0:
            c.restoreState()
            return
        pf.drawOn(c, x0, y - ph)
        y -= need

    # 2) paragraphes entiers
    for raw in (paras_text or []):
        kind = "EVENT" if _is_event(raw) else "DATE"
        p = Paragraph(apply_glyph_fallbacks(_strip_head_tail_breaks(sanitize_inline_markup(raw))), base)
        _w, ph = p.wrap(w, h)

        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)

        need = sb + ph + sa
        if (y - need) < y0:
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
    section_name: str,
    spacing_policy: SpacingPolicy,
) -> None:
    """Dessine des paragraphes entiers PUIS une 'tail' (fin césurée), avec espacement."""
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    base = paragraph_style(font_name, font_size, leading_ratio)

    first_non_event_seen_in_S5 = False

    c.saveState()
    y = y_top

    # 1) paragraphes entiers
    for raw in (paras_text or []):
        kind = "EVENT" if _is_event(raw) else "DATE"
        p = Paragraph(apply_glyph_fallbacks(_strip_head_tail_breaks(sanitize_inline_markup(raw))), base)
        _w, ph = p.wrap(w, h)

        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)

        need = sb + ph + sa
        if (y - need) < y0:
            c.restoreState()
            return
        y -= sb
        p.drawOn(c, x0, y - ph)
        y -= ph + sa

    # 2) tail (continuation EVENT) : pas de spaceBefore ; petit spaceAfter
    for tf in tail_flows or []:
        _w, ph = tf.wrap(w, h)
        sa = spacing_policy.space_after("EVENT", ph)
        if (y - (ph + sa)) < y0:
            break
        tf.drawOn(c, x0, y - ph)
        y -= ph + sa

    c.restoreState()


# ---------- Planification par paire avec césure A→B autorisée (gain significatif) ----------
def plan_pair_with_split(
    c: canvas.Canvas,
    secA: Section, secB: Section,
    nameA: str, nameB: str,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    split_min_gain_ratio: float,
    spacing_policy: SpacingPolicy,
) -> Tuple[List[str], List[Paragraph], List[Paragraph], List[str], List[str]]:
    """
    Planifie (A puis B) avec UNE césure A→B possible (si gain significatif),
    en tenant compte des espacement (spaceBefore/After) pour la place disponible.
    Retourne : A_full, A_tail, B_prelude, B_full, remaining
    """
    wA = max(1.0, secA.w - 2 * inner_pad)
    hA = max(1.0, secA.h - 2 * inner_pad)
    wB = max(1.0, secB.w - 2 * inner_pad)
    hB = max(1.0, secB.h - 2 * inner_pad)

    style = paragraph_style(font_name, font_size, leading_ratio)
    min_gain_pt = max(split_min_gain_ratio * hA, 0.9 * style.leading)

    remA = hA
    remB = hB

    A_full: List[str] = []
    A_tail: List[Paragraph] = []
    B_prelude: List[Paragraph] = []
    B_full: List[str] = []

    i = 0
    n = len(paras_text)

    first_non_event_seen_in_S5_A = False  # S5 only
    first_non_event_seen_in_S5_B = False

    # Remplir A (entier + éventuelle césure)
    while i < n and remA > 0:
        raw = paras_text[i]
        p = Paragraph(apply_glyph_fallbacks(_strip_head_tail_breaks(sanitize_inline_markup(raw))), style)
        _w, ph = p.wrap(wA, 1e6)
        kind = "EVENT" if _is_event(raw) else "DATE"

        sbA = spacing_policy.space_before(kind, nameA, first_non_event_seen_in_S5_A)
        if nameA == "S5" and kind == "DATE" and not first_non_event_seen_in_S5_A:
            first_non_event_seen_in_S5_A = True
        saA = spacing_policy.space_after(kind, ph)

        needA_full = sbA + ph + saA

        if needA_full <= remA:
            A_full.append(raw)
            remA -= needA_full
            i += 1
            continue

        # Trop grand pour A -> tenter césure A→B si le gain en A est significatif
        # Hauteur disponible pour la "miette" dans A (hors saA, qu'on veut garder après)
        avail_for_split_in_A = max(0.0, remA - sbA - spacing_policy.space_after("EVENT", style.leading))
        if avail_for_split_in_A > 0 and (ph > avail_for_split_in_A) and (ph <= (remA + remB)):
            parts = p.split(wA, avail_for_split_in_A)
            if parts and len(parts) >= 2:
                _w0, h0 = parts[0].wrap(wA, avail_for_split_in_A)
                if h0 >= min_gain_pt:
                    # Vérifier que le(s) reste(s) tien(nen)t en B (préface), avec spaceAfter pour chaque morceau
                    needed_B = 0.0
                    for k in range(1, len(parts)):
                        _wk, hk = parts[k].wrap(wB, remB)
                        needed_B += hk + spacing_policy.space_after("EVENT", hk)
                    if needed_B <= remB:
                        # Commit césure
                        A_tail.append(parts[0])
                        remA -= (sbA + h0 + spacing_policy.space_after("EVENT", h0))  # on réserve la fin en A
                        # Préface en B
                        for k in range(1, len(parts)):
                            _wk, hk = parts[k].wrap(wB, remB)
                            B_prelude.append(parts[k])
                            remB -= (hk + spacing_policy.space_after("EVENT", hk))
                        i += 1
                # sinon: gain insuffisant -> pas de césure
        # Quoi qu'il arrive, on s'arrête sur ce paragraphe pour A (entier ira à B)
        break

    # Remplir B (préface déjà comptée), avec des paragraphes ENTIERs
    while i < n and remB > 0:
        raw = paras_text[i]
        q = Paragraph(apply_glyph_fallbacks(_strip_head_tail_breaks(sanitize_inline_markup(raw))), style)
        _w, hq = q.wrap(wB, 1e6)
        kind = "EVENT" if _is_event(raw) else "DATE"

        sbB = spacing_policy.space_before(kind, nameB, first_non_event_seen_in_S5_B)
        if nameB == "S5" and kind == "DATE" and not first_non_event_seen_in_S5_B:
            first_non_event_seen_in_S5_B = True
        saB = spacing_policy.space_after(kind, hq)

        needB = sbB + hq + saB
        if needB <= remB:
            B_full.append(raw)
            remB -= needB
            i += 1
        else:
            break

    remaining = paras_text[i:]
    return A_full, A_tail, B_prelude, B_full, remaining

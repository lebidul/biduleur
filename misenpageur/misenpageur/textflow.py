# misenpageur/misenpageur/textflow.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional

from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY

from .layout import Section
from .drawing import paragraph_style
from .html_utils import sanitize_inline_markup
from .glyphs import apply_glyph_fallbacks
from .spacing import SpacingPolicy

from .config import BulletConfig, DateBoxConfig, DateLineConfig, PosterConfig # Importer les configs

PT_PER_INCH = 72.0
MM_PER_INCH = 25.4
def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_INCH / MM_PER_INCH

_BULLET_RE = re.compile(r'^\s*(?:❑|□|■|&#9643;)\s*', re.I)

def _is_event(raw: str) -> bool:
    return bool(_BULLET_RE.match(raw or ""))

def _strip_leading_bullet(raw: str) -> str:
    return _BULLET_RE.sub("", raw or "", count=1).lstrip()

def _strip_head_tail_breaks(s: str) -> str:
    if not s: return ""
    s = re.sub(r"^(?:\s*<br/>\s*)+", "", s)
    s = re.sub(r"(?:\s*<br/>\s*)+$", "", s)
    s = re.sub(r"(?:\s*<br/>\s*){3,}", "<br/><br/>", s)
    return s.strip()

def _mk_style_for_kind(base: ParagraphStyle, kind: str,
                       bullet_cfg: BulletConfig,
                       date_box: DateBoxConfig) -> ParagraphStyle:
    if kind == "EVENT":
        # ==================== LA CORRECTION EST ICI (1/2) ====================
        # On utilise un simple `leftIndent`. C'est lui qui contrôle la position
        # de TOUT le texte (ligne 1, 2, 3...).
        # On retire `firstLineIndent`.
        return ParagraphStyle(
            name=f"{base.name}_event", parent=base,
            leftIndent=bullet_cfg.event_hanging_indent,
            alignment=TA_JUSTIFY,
        )
    if kind == "DATE" and date_box.enabled:
        return ParagraphStyle(
            name=f"{base.name}_date", parent=base,
            borderWidth=date_box.border_width,
            borderColor=HexColor(date_box.border_color) if date_box.border_color else None,
            backColor=HexColor(date_box.back_color) if date_box.back_color else None,
            borderPadding=date_box.padding,
        )
    return base

def _mk_text_for_kind(
    raw: str, kind: str, bullet_cfg: BulletConfig
) -> Tuple[str, Optional[str]]:
    txt = _strip_head_tail_breaks(sanitize_inline_markup(raw))
    bullet_text = None
    if kind == "EVENT":
        if bullet_cfg.show_event_bullet:
            # On ajoute des espaces (insécables) APRÈS la puce.
            # C'est cela qui va créer la distance visuelle fixe.
            bullet_char = bullet_cfg.event_bullet_replacement or "❑"
            # bullet_char = bullet_cfg.event_bullet_replacement or "■"
            bullet_text = f"{bullet_char}"  # Puce (possibilité d'ajouter des) espaces insécables)
            # bullet_text = f"{bullet_char}"

        # On nettoie TOUJOURS la puce du texte principal
        txt = _strip_leading_bullet(txt)
    return apply_glyph_fallbacks(txt), bullet_text

def measure_fit_at_fs(
    c: canvas.Canvas, section: Section, paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str, spacing_policy: SpacingPolicy,
    bullet_cfg: BulletConfig, date_box: DateBoxConfig
) -> int:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y = y0 + h
    used = 0
    first_non_event_seen_in_S5 = False
    base = paragraph_style(font_name, font_size, leading_ratio)
    for raw in paras_text:
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, 1e6)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa
        if (y - need) < y0: break
        y -= need
        used += 1
    return used

def draw_section_fixed_fs_with_prelude(
    c: canvas.Canvas, section: Section, prelude_flows: List[Paragraph],
    paras_text: List[str], font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str, spacing_policy: SpacingPolicy, bullet_cfg: BulletConfig,
    date_box: DateBoxConfig, date_line: DateLineConfig
) -> None:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h
    base = paragraph_style(font_name, font_size, leading_ratio)
    first_non_event_seen_in_S5 = False
    c.saveState()
    y = y_top
    for pf in prelude_flows or []:
        _w, ph = pf.wrap(w, h)
        sa = spacing_policy.space_after("EVENT", ph)
        need = ph + sa
        if (y - need) < y0: c.restoreState(); return
        pf.drawOn(c, x0, y - ph)
        y -= need
    for raw in (paras_text or []):
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, h)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa
        if (y - need) < y0: break
        y -= sb
        if kind == "DATE" and date_line.enabled:
            plain_text = re.sub(r'<[^>]+>', '', txt)
            text_width = c.stringWidth(plain_text, st.fontName, st.fontSize)
            gap_pt = mm_to_pt(date_line.gap_after_text_mm)
            line_x_start = x0 + text_width + gap_pt
            line_x_end = x0 + w
            if line_x_start < line_x_end:
                y_line = (y - ph) + (st.leading / 2)
                c.saveState()
                c.setStrokeColor(HexColor(date_line.color))
                c.setLineWidth(date_line.width)
                c.line(line_x_start, y_line, line_x_end, y_line)
                c.restoreState()
        p.drawOn(c, x0, y - ph)
        y -= ph + sa
    c.restoreState()

def draw_section_fixed_fs_with_tail(
    c: canvas.Canvas, section: Section, paras_text: List[str],
    tail_flows: List[Paragraph], font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str, spacing_policy: SpacingPolicy, bullet_cfg: BulletConfig,
    date_box: DateBoxConfig, date_line: DateLineConfig
) -> None:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h
    base = paragraph_style(font_name, font_size, leading_ratio)
    first_non_event_seen_in_S5 = False
    c.saveState()
    y = y_top
    for raw in (paras_text or []):
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, h)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa
        if (y - need) < y0: c.restoreState(); return
        y -= sb
        if kind == "DATE" and date_line.enabled:
            plain_text = re.sub(r'<[^>]+>', '', txt)
            text_width = c.stringWidth(plain_text, st.fontName, st.fontSize)
            gap_pt = mm_to_pt(date_line.gap_after_text_mm)
            line_x_start = x0 + text_width + gap_pt
            line_x_end = x0 + w
            if line_x_start < line_x_end:
                y_line = (y - ph) + (st.leading / 2)
                c.saveState()
                c.setStrokeColor(HexColor(date_line.color))
                c.setLineWidth(date_line.width)
                c.line(line_x_start, y_line, line_x_end, y_line)
                c.restoreState()
        p.drawOn(c, x0, y - ph)
        y -= ph + sa
    for tf in tail_flows or []:
        _w, ph = tf.wrap(w, h)
        sa = spacing_policy.space_after("EVENT", ph)
        if (y - (ph + sa)) < y0: break
        tf.drawOn(c, x0, y - ph)
        y -= ph + sa
    c.restoreState()

def plan_pair_with_split(
    c: canvas.Canvas, secA: Section, secB: Section,
    nameA: str, nameB: str, paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    split_min_gain_ratio: float, spacing_policy: SpacingPolicy,
    bullet_cfg: BulletConfig, date_box: DateBoxConfig
) -> Tuple[List[str], List[Paragraph], List[Paragraph], List[str], List[str]]:
    wA, hA = max(1.0, secA.w - 2 * inner_pad), max(1.0, secA.h - 2 * inner_pad)
    wB, hB = max(1.0, secB.w - 2 * inner_pad), max(1.0, secB.h - 2 * inner_pad)
    base = paragraph_style(font_name, font_size, leading_ratio)
    min_gain_pt = max(split_min_gain_ratio * hA, 0.9 * base.leading)
    remA, remB = hA, hB
    A_full, A_tail, B_prelude, B_full = [], [], [], []
    i, n = 0, len(paras_text)
    first_non_event_seen_in_S5_A, first_non_event_seen_in_S5_B = False, False
    while i < n and remA > 0:
        raw = paras_text[i]
        kind = "EVENT" if _is_event(raw) else "DATE"
        stA = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txtA, bulletA = _mk_text_for_kind(raw, kind, bullet_cfg)
        p = Paragraph(txtA, stA, bulletText=bulletA)
        _w, ph = p.wrap(wA, 1e6)
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
        avail_for_split_in_A = max(0.0, remA - sbA - spacing_policy.space_after("EVENT", base.leading))
        if avail_for_split_in_A > 0 and (ph > avail_for_split_in_A) and (ph <= (remA + remB)):
            parts = p.split(wA, avail_for_split_in_A)
            if parts and len(parts) >= 2:
                _w0, h0 = parts[0].wrap(wA, avail_for_split_in_A)
                if h0 >= min_gain_pt:
                    needB = sum(part.wrap(wB, remB)[1] + spacing_policy.space_after("EVENT", part.wrap(wB, remB)[1]) for part in parts[1:])
                    if needB <= remB:
                        A_tail.append(parts[0])
                        remA -= (sbA + h0 + spacing_policy.space_after("EVENT", h0))
                        for part in parts[1:]:
                            _wk, hk = part.wrap(wB, remB)
                            B_prelude.append(part)
                            remB -= (hk + spacing_policy.space_after("EVENT", hk))
                        i += 1
        break
    while i < n and remB > 0:
        raw = paras_text[i]
        kind = "EVENT" if _is_event(raw) else "DATE"
        stB = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txtB, bulletB = _mk_text_for_kind(raw, kind, bullet_cfg)
        q = Paragraph(txtB, stB, bulletText=bulletB)
        _w, hq = q.wrap(wB, 1e6)
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
    return A_full, A_tail, B_prelude, B_full, paras_text[i:]


def measure_poster_fit_at_fs(
        c: canvas.Canvas, frames: List[Section], paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float,
        bullet_cfg: BulletConfig,
        poster_cfg: PosterConfig,
        text_color: str = "#000000"
) -> bool:
    """
    Simule le remplissage des cadres en calculant la hauteur de chaque paragraphe,
    en incluant l'espacement spécifique du poster pour les dates.
    """
    base_style = paragraph_style(font_name, font_size, leading_ratio)
    base_style.textColor = HexColor(text_color)
    para_idx = 0
    num_paras = len(paras_text)
    for section in frames:
        if para_idx >= num_paras: break
        remaining_height = section.h
        while remaining_height > 0 and para_idx < num_paras:
            raw = paras_text[para_idx]
            kind = "EVENT" if _is_event(raw) else "DATE"
            st = _mk_style_for_kind(base_style, kind, bullet_cfg, DateBoxConfig())
            txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg)
            p = Paragraph(txt, st, bulletText=bullet)

            _w, p_h = p.wrapOn(c, section.w, section.h)

            # ==================== LA CORRECTION EST ICI ====================
            # Si c'est une date, on ajoute l'espacement du poster au calcul
            if kind == "DATE":
                p_h += poster_cfg.date_spaceBefore + poster_cfg.date_spaceAfter
            # =============================================================

            if p_h <= remaining_height:
                remaining_height -= p_h
                para_idx += 1
            else:
                remaining_height = 0
    return para_idx >= num_paras


def draw_poster_text_in_frames(
        c: canvas.Canvas, frames: List[Section], paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float,
        bullet_cfg: BulletConfig,
        poster_cfg: PosterConfig,
        text_color: str = "#000000"
):
    """
    Dessine le texte dans une série de cadres, en insérant des espaces
    verticaux (Spacers) avant et après les dates.
    """
    base_style = paragraph_style(font_name, font_size, leading_ratio)
    base_style.textColor = HexColor(text_color)
    story = []
    for raw in paras_text:
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base_style, kind, bullet_cfg, DateBoxConfig())
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg)

        # ==================== LA CORRECTION EST ICI ====================
        # Si c'est une date, on ajoute des objets Spacer à la story
        if kind == "DATE":
            story.append(Spacer(1, poster_cfg.date_spaceBefore))

        story.append(Paragraph(txt, st, bulletText=bullet))

        if kind == "DATE":
            story.append(Spacer(1, poster_cfg.date_spaceAfter))
        # =============================================================

    for section in frames:
        if not story: break
        frame = Frame(section.x, section.y, section.w, section.h, showBoundary=0)
        frame.addFromList(story, c)
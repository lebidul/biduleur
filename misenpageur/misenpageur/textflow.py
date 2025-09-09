# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor

from .layout import Section
from .drawing import paragraph_style
from .html_utils import sanitize_inline_markup
from .glyphs import apply_glyph_fallbacks
from .spacing import SpacingPolicy

# Ajout d'un convertisseur mm -> points, car nous en avons besoin ici pour l'affichage des lignes de dates.
PT_PER_INCH = 72.0
MM_PER_INCH = 25.4
def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_INCH / MM_PER_INCH


# ---------- Classification "date" vs "événement" ----------
# Événements = lignes qui DÉBUTENT par ❑ (standard workflow).
# On ajoute quelques équivalents proches pour robustesse (□, ■, &#9643;).
_BULLET_RE = re.compile(r'^\s*(?:❑|□|■|&#9643;)\s*', re.I)

def _is_event(raw: str) -> bool:
    return bool(_BULLET_RE.match(raw or ""))

def _strip_leading_bullet(raw: str) -> str:
    return _BULLET_RE.sub("", raw or "", count=1)


# ---------- Bullet / Hanging indent ----------
@dataclass
class BulletConfig:
    show_event_bullet: bool = True            # True: garder le symbole; False: masquer
    event_bullet_replacement: str | None = None  # ex. "■" ; si None => garder l'entrée
    event_hanging_indent: float = 10.0        # retrait suspendu (pt) pour les événements


# ---------- Cadre/fond pour les "DATE" ----------
@dataclass
class DateBoxConfig:
    enabled: bool = False
    padding: float = 2.0
    border_width: float = 0.5
    border_color: str | None = "#000000"
    back_color: str | None = None

# ---------- Ligne de séparation les "DATE" ----------
@dataclass
class DateLineConfig:
    """Configuration pour la ligne horizontale sur les dates."""
    enabled: bool = False
    width: float = 0.5  # Épaisseur en points
    color: str = "#000000"
    gap_after_text_mm: float = 3.0 # Espace entre le texte et le début de la ligne

# ---------- Helpers communs ----------
def _strip_head_tail_breaks(s: str) -> str:
    """Retire <br/> de tête/queue et compresse les suites."""
    if not s:
        return ""
    s = re.sub(r"^(?:\s*<br/>\s*)+", "", s)
    s = re.sub(r"(?:\s*<br/>\s*)+$", "", s)
    s = re.sub(r"(?:\s*<br/>\s*){3,}", "<br/><br/>", s)
    return s.strip()

def _mk_style_for_kind(base: ParagraphStyle, kind: str,
                       bullet_cfg: BulletConfig,
                       date_box: DateBoxConfig) -> ParagraphStyle:
    """Clone le style de base et applique, pour EVENT, un retrait suspendu; pour DATE, un cadre/fond optionnel."""
    if kind == "EVENT":
        return ParagraphStyle(
            name=f"{base.name}_event",
            parent=base,
            leftIndent=bullet_cfg.event_hanging_indent,
            firstLineIndent=-bullet_cfg.event_hanging_indent,
        )
    if kind == "DATE" and date_box.enabled:
        return ParagraphStyle(
            name=f"{base.name}_date",
            parent=base,
            borderWidth=date_box.border_width,
            borderColor=HexColor(date_box.border_color) if date_box.border_color else None,
            backColor=HexColor(date_box.back_color) if date_box.back_color else None,
            borderPadding=date_box.padding,
        )
    return base

def _mk_text_for_kind(raw: str, kind: str, bullet_cfg: BulletConfig) -> str:
    """Prépare le texte: nettoyage, bullet visible/masqué/remplacé, glyphes."""
    txt = _strip_head_tail_breaks(sanitize_inline_markup(raw))
    if kind == "EVENT":
        if bullet_cfg.event_bullet_replacement:
            if _is_event(txt):
                txt = _BULLET_RE.sub(bullet_cfg.event_bullet_replacement + " ", txt, count=1)
        elif not bullet_cfg.show_event_bullet:
            txt = _strip_leading_bullet(txt)
    return apply_glyph_fallbacks(txt)


# ---------- Mesure pour la recherche de taille commune (avec espacement & styles) ----------
def measure_fit_at_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str,
    spacing_policy: SpacingPolicy,
    bullet_cfg: BulletConfig,
    date_box: DateBoxConfig,
) -> int:
    """
    Compte combien de paragraphes ENTIERs tiennent dans 'section' à font_size,
    en intégrant spaceBefore/spaceAfter + hanging indent (EVENT) + cadre/fond (DATE).
    """
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y  = y0 + h

    used = 0
    first_non_event_seen_in_S5 = False

    base = paragraph_style(font_name, font_size, leading_ratio)

    for raw in paras_text:
        kind = "EVENT" if _is_event(raw) else "DATE"
        st   = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txt  = _mk_text_for_kind(raw, kind, bullet_cfg)

        p = Paragraph(txt, st)
        _w, ph = p.wrap(w, 1e6)

        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)

        need = sb + ph + sa
        if (y - need) < y0:
            break
        y -= need
        used += 1

    return used


# ---------- Rendu (top-align) avec espacement & styles ----------
def draw_section_fixed_fs(
    c: canvas.Canvas,
    section: Section,
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str,
    spacing_policy: SpacingPolicy,
    bullet_cfg: BulletConfig,
    date_box: DateBoxConfig,
) -> Tuple[List[str], float]:
    """Dessine la section (paragraphes entiers) en top-align STRICT, avec espacement + hanging indent (EVENT) + cadre/fond (DATE)."""
    # Nettoyage + drop vides
    cleaned: List[str] = []
    for t in paras_text:
        stxt = _strip_head_tail_breaks(sanitize_inline_markup(t))
        if stxt:
            cleaned.append(stxt)
    if not cleaned:
        return [], font_size

    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    base = paragraph_style(font_name, font_size, leading_ratio)

    first_non_event_seen_in_S5 = False

    c.saveState()
    y = y_top
    for raw in cleaned:
        kind = "EVENT" if _is_event(raw) else "DATE"
        st   = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txt  = _mk_text_for_kind(raw, kind, bullet_cfg)

        p = Paragraph(txt, st)
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
    return cleaned, font_size


def draw_section_fixed_fs_with_prelude(
    c: canvas.Canvas,
    section: Section,
    prelude_flows: List[Paragraph],
    paras_text: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    section_name: str,
    spacing_policy: SpacingPolicy,
    bullet_cfg: BulletConfig,
    date_box: DateBoxConfig,
    date_line: DateLineConfig,
) -> None:
    """Dessine une préface (suite césurée) PUIS des paragraphes entiers, avec espacement & styles."""
    x0 = section.x + inner_pad
    y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2 * inner_pad)
    h  = max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h

    base = paragraph_style(font_name, font_size, leading_ratio)

    first_non_event_seen_in_S5 = False

    c.saveState()
    y = y_top

    # 1) préface (continuation : pas de spaceBefore ; on considère EVENT pour spaceAfter)
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
        st   = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txt  = _mk_text_for_kind(raw, kind, bullet_cfg)

        p = Paragraph(txt, st)
        _w, ph = p.wrap(w, h)

        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)

        need = sb + ph + sa
        if (y - need) < y0:
            break
        y -= sb
        # ==================== DESSIN DE LA LIGNE ====================
        if kind == "DATE" and date_line.enabled:
            # 1. Obtenir le texte brut (sans balises HTML) pour la mesure
            plain_text = re.sub(r'<[^>]+>', '', txt)
            # 2. Mesurer la largeur du texte
            text_width = c.stringWidth(plain_text, st.fontName, st.fontSize)
            # 3. Calculer le point de départ de la ligne
            gap_pt = mm_to_pt(date_line.gap_after_text_mm)
            line_x_start = x0 + text_width + gap_pt
            line_x_end = x0 + w

            # 4. S'assurer qu'il y a de la place pour dessiner la ligne
            if line_x_start < line_x_end:
                y_line = (y - ph) + (st.leading / 2)
                c.saveState()
                c.setStrokeColor(HexColor(date_line.color))
                c.setLineWidth(date_line.width)
                c.line(line_x_start, y_line, line_x_end, y_line)
                c.restoreState()
        # ===========================================================

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
    bullet_cfg: BulletConfig,
    date_box: DateBoxConfig,
    date_line: DateLineConfig,
) -> None:
    """Dessine des paragraphes entiers PUIS une 'tail' (fin césurée), avec espacement & styles."""
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
        st   = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txt  = _mk_text_for_kind(raw, kind, bullet_cfg)

        p = Paragraph(txt, st)
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
        # ==================== DESSIN DE LA LIGNE ====================
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
        # ===========================================================

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
    bullet_cfg: BulletConfig,
    date_box: DateBoxConfig,
) -> Tuple[List[str], List[Paragraph], List[Paragraph], List[str], List[str]]:
    """
    Planifie (A puis B) avec UNE césure A→B possible (si gain significatif),
    en tenant compte des espacements, hanging indent et cadre/fond.
    Retourne : A_full, A_tail, B_prelude, B_full, remaining
    """
    from reportlab.platypus import Paragraph  # éviter import cycles

    wA = max(1.0, secA.w - 2 * inner_pad)
    hA = max(1.0, secA.h - 2 * inner_pad)
    wB = max(1.0, secB.w - 2 * inner_pad)
    hB = max(1.0, secB.h - 2 * inner_pad)

    base = paragraph_style(font_name, font_size, leading_ratio)
    min_gain_pt = max(split_min_gain_ratio * hA, 0.9 * base.leading)

    remA = hA
    remB = hB

    A_full: List[str] = []
    A_tail: List[Paragraph] = []
    B_prelude: List[Paragraph] = []
    B_full: List[str] = []

    i = 0
    n = len(paras_text)

    first_non_event_seen_in_S5_A = False
    first_non_event_seen_in_S5_B = False

    # Remplir A (entier + éventuelle césure)
    while i < n and remA > 0:
        raw = paras_text[i]
        kind = "EVENT" if _is_event(raw) else "DATE"
        stA  = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txtA = _mk_text_for_kind(raw, kind, bullet_cfg)

        p = Paragraph(txtA, stA)
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

        # Trop grand pour A -> tenter césure A→B (gain significatif)
        avail_for_split_in_A = max(0.0, remA - sbA - spacing_policy.space_after("EVENT", base.leading))
        if avail_for_split_in_A > 0 and (ph > avail_for_split_in_A) and (ph <= (remA + remB)):
            parts = p.split(wA, avail_for_split_in_A)
            if parts and len(parts) >= 2:
                _w0, h0 = parts[0].wrap(wA, avail_for_split_in_A)
                if h0 >= min_gain_pt:
                    # Vérifier place en B pour les suites
                    needB = 0.0
                    for k in range(1, len(parts)):
                        _wk, hk = parts[k].wrap(wB, remB)
                        needB += hk + spacing_policy.space_after("EVENT", hk)
                    if needB <= remB:
                        # Commit césure
                        A_tail.append(parts[0])
                        remA -= (sbA + h0 + spacing_policy.space_after("EVENT", h0))
                        for k in range(1, len(parts)):
                            _wk, hk = parts[k].wrap(wB, remB)
                            B_prelude.append(parts[k])
                            remB -= (hk + spacing_policy.space_after("EVENT", hk))
                        i += 1
        # Quoi qu'il arrive, on s'arrête pour A (paragraphe entier ira à B)
        break

    # Remplir B (préface déjà comptée), avec des paragraphes ENTIERs
    while i < n and remB > 0:
        raw = paras_text[i]
        kind = "EVENT" if _is_event(raw) else "DATE"
        stB  = _mk_style_for_kind(base, kind, bullet_cfg, date_box)
        txtB = _mk_text_for_kind(raw, kind, bullet_cfg)

        q = Paragraph(txtB, stB)
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

    remaining = paras_text[i:]
    return A_full, A_tail, B_prelude, B_full, remaining


def measure_poster_fit_at_fs(
        c: canvas.Canvas,
        frames: List[Section],
        paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float,
        bullet_cfg: BulletConfig
) -> bool:
    """
    Simule le remplissage des cadres en calculant la hauteur de chaque paragraphe
    et retourne True si tout le texte rentre.
    """
    base_style = paragraph_style(font_name, font_size, leading_ratio)

    # On garde une trace de l'index du paragraphe en cours
    para_idx = 0
    num_paras = len(paras_text)

    for section in frames:
        if para_idx >= num_paras:
            break  # Tout le texte est placé

        remaining_height = section.h

        while remaining_height > 0 and para_idx < num_paras:
            raw = paras_text[para_idx]
            kind = "EVENT" if _is_event(raw) else "DATE"
            st = _mk_style_for_kind(base_style, "EVENT", bullet_cfg, DateBoxConfig())
            txt = _mk_text_for_kind(raw, kind, bullet_cfg)
            p = Paragraph(txt, st)

            # On mesure la hauteur que prend le paragraphe dans ce cadre
            _w, p_h = p.wrapOn(c, section.w, section.h)

            # Est-ce que ça rentre ?
            if p_h < remaining_height:
                remaining_height -= p_h
                para_idx += 1  # On passe au paragraphe suivant
            else:
                # Le paragraphe ne rentre pas, on arrête de remplir ce cadre
                remaining_height = 0

    # Si on a réussi à placer tous les paragraphes, on retourne True
    return para_idx >= num_paras


def draw_poster_text_in_frames(
        c: canvas.Canvas,
        frames: List[Section],
        paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float,
        bullet_cfg: BulletConfig
):
    """Dessine le texte dans une série de cadres."""
    base_style = paragraph_style(font_name, font_size, leading_ratio)

    story = []
    for raw in paras_text:
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base_style, "EVENT", bullet_cfg, DateBoxConfig())
        txt = _mk_text_for_kind(raw, kind, bullet_cfg)
        story.append(Paragraph(txt, st))

    for section in frames:
        if not story: break
        frame = Frame(section.x, section.y, section.w, section.h, showBoundary=0)
        frame.addFromList(story, c)
# misenpageur/misenpageur/textflow.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase.pdfmetrics import stringWidth

from .layout import Section
from .drawing import paragraph_style
from .html_utils import sanitize_inline_markup
from .glyphs import apply_glyph_fallbacks
from .spacing import SpacingPolicy

from .config import BulletConfig, DateBoxConfig, DateLineConfig, DateStyleConfig, PosterConfig

PT_PER_INCH = 72.0
MM_PER_INCH = 25.4

# Chemin vers les icônes (relatif au dossier parent du module)
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_DIR = os.path.dirname(_MODULE_DIR)  # Remonter d'un niveau (misenpageur/misenpageur -> misenpageur)
CHAPEAU_ICON_PATH = os.path.join(_PACKAGE_DIR, "assets", "icons", "chapeau.png")
FREE_ICON_PATH = os.path.join(_PACKAGE_DIR, "assets", "icons", "free.png")

# Placeholders ASCII simples qui ne seront pas modifiés par sanitize_inline_markup
CHAPEAU_PLACEHOLDER = "{{CHAPEAU}}"
FREE_PLACEHOLDER = "{{FREE}}"

# Regex compilées au niveau module pour éviter la recompilation à chaque appel
# Pattern pour "au chapeau" avec espaces normaux, &nbsp; et espaces insécables Unicode
_CHAPEAU_PATTERN = re.compile(r',?(?:\s|&nbsp;|\u00A0)*au(?:\s|&nbsp;|\u00A0)+chapeau', re.IGNORECASE)
# Pattern pour "0€" avec gestion des espaces et &euro;
# (?<![0-9]) = lookbehind négatif pour éviter de matcher "10€", "20€", etc.
_FREE_PATTERN = re.compile(r',?(?:\s|&nbsp;|\u00A0)*(?<![0-9])0(?:\s|&nbsp;|\u00A0)*(?:€|&euro;)', re.IGNORECASE)
# Pattern pour nettoyer les balises HTML (utilisé pour date_line)
_HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
# Pattern pour nettoyer les <br/> en début/fin de chaîne
_HEAD_BR_PATTERN = re.compile(r'^(?:\s*<br/>\s*)+')
_TAIL_BR_PATTERN = re.compile(r'(?:\s*<br/>\s*)+$')
_MULTI_BR_PATTERN = re.compile(r'(?:\s*<br/>\s*){3,}')

# Cache pour les métadonnées des icônes (aspect ratio)
# Clé: chemin de l'icône, Valeur: aspect ratio (width/height) ou None si erreur
_ICON_ASPECT_CACHE: dict[str, float | None] = {}


def _get_icon_aspect(icon_path: str) -> float | None:
    """
    Récupère l'aspect ratio d'une icône avec mise en cache.

    Returns:
        float: aspect ratio (width/height) ou None si l'icône n'existe pas ou erreur
    """
    if icon_path in _ICON_ASPECT_CACHE:
        return _ICON_ASPECT_CACHE[icon_path]

    if not os.path.exists(icon_path):
        _ICON_ASPECT_CACHE[icon_path] = None
        return None

    try:
        img = Image.open(icon_path)
        aspect = img.width / img.height
        img.close()
        _ICON_ASPECT_CACHE[icon_path] = aspect
        return aspect
    except Exception as e:
        print(f"[WARN] Erreur chargement icône {icon_path}: {e}")
        _ICON_ASPECT_CACHE[icon_path] = None
        return None


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_INCH / MM_PER_INCH


def _get_icon_img_tag(icon_path: str, font_size: float, scale: float = 0.8) -> str:
    """
    Génère la balise img pour une icône, dimensionnée selon la police.
    Utilise le cache pour éviter de recharger l'image à chaque appel.

    Args:
        icon_path: Chemin vers l'icône
        font_size: Taille de la police en points
        scale: Facteur d'échelle par rapport à la taille de police (défaut 0.8)

    Returns:
        str: Balise <img> ReportLab ou chaîne vide si l'icône n'existe pas
    """
    aspect = _get_icon_aspect(icon_path)
    if aspect is None:
        return ""

    img_h_pt = font_size * scale
    img_w_pt = img_h_pt * aspect

    return f'<img src="{icon_path}" width="{img_w_pt:.1f}" height="{img_h_pt:.1f}" valign="middle"/>'


def _get_chapeau_img_tag(font_size: float) -> str:
    """Génère la balise img pour l'icône chapeau."""
    return _get_icon_img_tag(CHAPEAU_ICON_PATH, font_size, scale=0.8)


def _get_free_img_tag(font_size: float) -> str:
    """Génère la balise img pour l'icône free."""
    return _get_icon_img_tag(FREE_ICON_PATH, font_size, scale=0.8)


def _replace_chapeau_placeholder(txt: str, font_size: float) -> str:
    """Remplace le placeholder chapeau par l'image avec la taille correcte."""
    if CHAPEAU_PLACEHOLDER not in txt:
        return txt

    img_tag = _get_chapeau_img_tag(font_size)
    if img_tag:
        return txt.replace(CHAPEAU_PLACEHOLDER, img_tag)
    return txt


def _replace_free_placeholder(txt: str, font_size: float) -> str:
    """Remplace le placeholder free par l'image avec la taille correcte."""
    if FREE_PLACEHOLDER not in txt:
        return txt

    img_tag = _get_free_img_tag(font_size)
    if img_tag:
        return txt.replace(FREE_PLACEHOLDER, img_tag)
    return txt


def _replace_all_placeholders(txt: str, font_size: float) -> str:
    """Remplace tous les placeholders d'icônes par les images."""
    txt = _replace_chapeau_placeholder(txt, font_size)
    txt = _replace_free_placeholder(txt, font_size)
    return txt


def apply_chapeau_to_paragraphs(paras: List[str]) -> List[str]:
    """
    Remplace "au chapeau" par un placeholder court dans les paragraphes.

    Cette fonction doit être appelée AVANT le calcul de la taille de police
    pour que le gain d'espace soit pris en compte. Le placeholder sera
    remplacé par l'image réelle lors du rendu (dans _mk_text_for_kind).

    Args:
        paras: Liste des paragraphes HTML

    Returns:
        Liste des paragraphes avec le placeholder
    """
    # Vérifier que l'icône existe
    if not os.path.exists(CHAPEAU_ICON_PATH):
        print(f"[WARN] Icône chapeau non trouvée: {CHAPEAU_ICON_PATH}")
        return paras

    result = []
    count = 0
    for p in paras:
        # Remplacer par ", " + placeholder pour garder la virgule
        new_p, n = _CHAPEAU_PATTERN.subn(', ' + CHAPEAU_PLACEHOLDER, p)
        count += n
        result.append(new_p)

    if count > 0:
        print(f"[CHAPEAU] {count} occurrences remplacées")

    return result


def apply_free_to_paragraphs(paras: List[str]) -> List[str]:
    """
    Remplace ", 0€" par un placeholder court dans les paragraphes.

    Args:
        paras: Liste des paragraphes HTML

    Returns:
        Liste des paragraphes avec le placeholder
    """
    # Vérifier que l'icône existe
    if not os.path.exists(FREE_ICON_PATH):
        print(f"[WARN] Icône free non trouvée: {FREE_ICON_PATH}")
        return paras

    result = []
    count = 0
    for p in paras:
        # Remplacer par ", " + placeholder pour garder la virgule
        new_p, n = _FREE_PATTERN.subn(', ' + FREE_PLACEHOLDER, p)
        count += n
        result.append(new_p)

    if count > 0:
        print(f"[FREE] {count} occurrences remplacées")

    return result


def apply_icon_replacements(paras: List[str], chapeau_enabled: bool = False, free_enabled: bool = False) -> List[str]:
    """
    Applique les remplacements d'icônes activés sur les paragraphes.

    Cette fonction doit être appelée AVANT le calcul de la taille de police.

    Args:
        paras: Liste des paragraphes HTML
        chapeau_enabled: Activer le remplacement "au chapeau"
        free_enabled: Activer le remplacement "0€"

    Returns:
        Liste des paragraphes avec les placeholders
    """
    result = paras

    if chapeau_enabled:
        result = apply_chapeau_to_paragraphs(result)

    if free_enabled:
        result = apply_free_to_paragraphs(result)

    return result


_BULLET_RE = re.compile(r'^\s*(?:❑|□|■|&#9643;)\s*', re.I)

# Cache pour les ParagraphStyle créés par _mk_style_for_kind
# Clé: tuple des paramètres pertinents, Valeur: ParagraphStyle
_STYLE_CACHE: dict[tuple, ParagraphStyle] = {}


def clear_style_cache() -> None:
    """Vide le cache des styles. À appeler entre les sessions de rendu si les configs changent."""
    _STYLE_CACHE.clear()


def _is_event(raw: str) -> bool:
    return bool(_BULLET_RE.match(raw or ""))


def _strip_leading_bullet(raw: str) -> str:
    return _BULLET_RE.sub("", raw or "", count=1).lstrip()


def _strip_head_tail_breaks(s: str) -> str:
    if not s: return ""
    s = _HEAD_BR_PATTERN.sub("", s)
    s = _TAIL_BR_PATTERN.sub("", s)
    s = _MULTI_BR_PATTERN.sub("<br/><br/>", s)
    return s.strip()


_ALIGNMENT_MAP = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}


def _mk_style_for_kind(base: ParagraphStyle, kind: str,
                       bullet_cfg: BulletConfig,
                       date_box: DateBoxConfig,
                       font_size: float = 10.0,
                       date_style: DateStyleConfig | None = None) -> ParagraphStyle:
    # Créer une clé de cache basée sur les paramètres qui influencent le style
    # NB: on inclut base.fontName pour invalider le cache quand la police du corps change
    base_font = getattr(base, 'fontName', '')
    if kind == "EVENT":
        cache_key = (
            "EVENT", base_font, font_size,
            bullet_cfg.event_hanging_indent,
            bullet_cfg.bullet_text_indent,
            bullet_cfg.bullet_size_ratio,
        )
        if cache_key in _STYLE_CACHE:
            return _STYLE_CACHE[cache_key]

        bullet_font_size = font_size * bullet_cfg.bullet_size_ratio
        style = ParagraphStyle(
            name=f"{base.name}_event", parent=base,
            leftIndent=bullet_cfg.event_hanging_indent,
            bulletFontSize=bullet_font_size,
            bulletIndent=bullet_cfg.bullet_text_indent,
            alignment=TA_JUSTIFY,
        )
        _STYLE_CACHE[cache_key] = style
        return style

    if kind == "DATE":
        ds = date_style or DateStyleConfig()
        ta = _ALIGNMENT_MAP.get(ds.alignment, TA_LEFT)
        cache_key = (
            "DATE", base_font, font_size,
            date_box.enabled,
            date_box.border_width,
            date_box.border_color,
            date_box.back_color,
            date_box.padding,
            ta,
            ds.font_name,
        )
        if cache_key in _STYLE_CACHE:
            return _STYLE_CACHE[cache_key]

        kwargs = {"alignment": ta}
        if ds.font_name:
            kwargs["fontName"] = ds.font_name
        if date_box.enabled:
            kwargs.update(
                borderWidth=date_box.border_width,
                borderColor=HexColor(date_box.border_color) if date_box.border_color else None,
                backColor=HexColor(date_box.back_color) if date_box.back_color else None,
                borderPadding=date_box.padding,
            )

        style = ParagraphStyle(
            name=f"{base.name}_date", parent=base,
            **kwargs,
        )
        _STYLE_CACHE[cache_key] = style
        return style

    return base


def _mk_text_for_kind(
        raw: str, kind: str, bullet_cfg: BulletConfig, font_size: float = 10.0,
        date_style: DateStyleConfig | None = None
) -> Tuple[str, Optional[str]]:
    txt = _strip_head_tail_breaks(sanitize_inline_markup(raw))
    bullet_text = None
    if kind == "EVENT":
        if bullet_cfg.show_event_bullet:
            bullet_char = bullet_cfg.event_bullet_replacement or "❑"
            bullet_text = bullet_char
        txt = _strip_leading_bullet(txt)

    # Remplacer tous les placeholders d'icônes par les images
    txt = _replace_all_placeholders(txt, font_size)

    # Appliquer bold/italic pour les dates
    if kind == "DATE" and date_style:
        if date_style.italic:
            txt = f"<i>{txt}</i>"
        if date_style.bold:
            txt = f"<b>{txt}</b>"

    return apply_glyph_fallbacks(txt), bullet_text


def measure_fit_at_fs(
        c: canvas.Canvas, section: Section, paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
        section_name: str, spacing_policy: SpacingPolicy,
        bullet_cfg: BulletConfig, date_box: DateBoxConfig,
        date_style: DateStyleConfig | None = None
) -> int:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y = y0 + h
    used = 0
    first_non_event_seen_in_S5 = False
    base = paragraph_style(font_name, font_size, leading_ratio)

    for i, raw in enumerate(paras_text):
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, 1e6)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa

        # Vérifier si le paragraphe actuel rentre
        if (y - need) < y0:
            break

        # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas
        # Si c'est une DATE et qu'il reste des paragraphes après
        if kind == "DATE" and i < len(paras_text) - 1:
            # Regarder le prochain paragraphe
            next_raw = paras_text[i + 1]
            next_kind = "EVENT" if _is_event(next_raw) else "DATE"

            # Si le suivant est un EVENT, vérifier qu'on peut en placer au moins un
            if next_kind == "EVENT":
                # Calculer la valeur qu'aura first_non_event_seen_in_S5 APRÈS avoir placé la DATE actuelle
                first_non_event_after_current = first_non_event_seen_in_S5

                next_st = _mk_style_for_kind(base, next_kind, bullet_cfg, date_box, font_size, date_style)
                next_txt, next_bullet = _mk_text_for_kind(next_raw, next_kind, bullet_cfg, font_size, date_style)
                next_p = Paragraph(next_txt, next_st, bulletText=next_bullet)
                _next_w, next_ph = next_p.wrap(w, 1e6)
                next_sb = spacing_policy.space_before(next_kind, section_name, first_non_event_after_current)
                next_sa = spacing_policy.space_after(next_kind, next_ph)
                next_need = next_sb + next_ph + next_sa

                # Si on n'a pas assez de place pour la DATE + au moins un EVENT, ne pas placer la DATE
                if (y - need - next_need) < y0:
                    break

        # Le paragraphe peut être placé
        y -= need
        used += 1

    return used


def draw_section_fixed_fs_with_prelude(
        c: canvas.Canvas, section: Section, prelude_flows: List[Paragraph],
        paras_text: List[str], font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
        section_name: str, spacing_policy: SpacingPolicy, bullet_cfg: BulletConfig,
        date_box: DateBoxConfig, date_line: DateLineConfig,
        date_style: DateStyleConfig | None = None
) -> None:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h
    base = paragraph_style(font_name, font_size, leading_ratio)
    first_non_event_seen_in_S5 = False
    c.saveState()
    y = y_top

    # Dessiner le prélude
    for pf in prelude_flows or []:
        _w, ph = pf.wrap(w, h)
        sa = spacing_policy.space_after("EVENT", ph)
        need = ph + sa
        if (y - need) < y0: c.restoreState(); return
        pf.drawOn(c, x0, y - ph)
        y -= need

    # Dessiner les paragraphes principaux
    for i, raw in enumerate(paras_text or []):
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, h)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa

        # Vérifier si le paragraphe actuel rentre
        if (y - need) < y0:
            break

        # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas
        if kind == "DATE" and i < len(paras_text) - 1:
            next_raw = paras_text[i + 1]
            next_kind = "EVENT" if _is_event(next_raw) else "DATE"

            if next_kind == "EVENT":
                # Calculer la valeur qu'aura first_non_event_seen_in_S5 APRÈS avoir placé la DATE actuelle
                first_non_event_after_current = first_non_event_seen_in_S5

                next_st = _mk_style_for_kind(base, next_kind, bullet_cfg, date_box, font_size, date_style)
                next_txt, next_bullet = _mk_text_for_kind(next_raw, next_kind, bullet_cfg, font_size, date_style)
                next_p = Paragraph(next_txt, next_st, bulletText=next_bullet)
                _next_w, next_ph = next_p.wrap(w, h)
                next_sb = spacing_policy.space_before(next_kind, section_name, first_non_event_after_current)
                next_sa = spacing_policy.space_after(next_kind, next_ph)
                next_need = next_sb + next_ph + next_sa

                if (y - need - next_need) < y0:
                    break

        # Dessiner le paragraphe
        y -= sb
        if kind == "DATE" and date_line.enabled:
            plain_text = _HTML_TAG_PATTERN.sub('', txt)
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
        date_box: DateBoxConfig, date_line: DateLineConfig,
        date_style: DateStyleConfig | None = None
) -> None:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h
    base = paragraph_style(font_name, font_size, leading_ratio)
    first_non_event_seen_in_S5 = False
    c.saveState()
    y = y_top

    # Dessiner les paragraphes principaux
    for i, raw in enumerate(paras_text or []):
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, h)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa

        # Vérifier si le paragraphe actuel rentre
        if (y - need) < y0:
            c.restoreState()
            return

        # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas
        if kind == "DATE" and i < len(paras_text) - 1:
            next_raw = paras_text[i + 1]
            next_kind = "EVENT" if _is_event(next_raw) else "DATE"

            if next_kind == "EVENT":
                # Calculer la valeur qu'aura first_non_event_seen_in_S5 APRÈS avoir placé la DATE actuelle
                first_non_event_after_current = first_non_event_seen_in_S5

                next_st = _mk_style_for_kind(base, next_kind, bullet_cfg, date_box, font_size, date_style)
                next_txt, next_bullet = _mk_text_for_kind(next_raw, next_kind, bullet_cfg, font_size, date_style)
                next_p = Paragraph(next_txt, next_st, bulletText=next_bullet)
                _next_w, next_ph = next_p.wrap(w, h)
                next_sb = spacing_policy.space_before(next_kind, section_name, first_non_event_after_current)
                next_sa = spacing_policy.space_after(next_kind, next_ph)
                next_need = next_sb + next_ph + next_sa

                if (y - need - next_need) < y0:
                    c.restoreState()
                    return

        # Dessiner le paragraphe
        y -= sb
        if kind == "DATE" and date_line.enabled:
            plain_text = _HTML_TAG_PATTERN.sub('', txt)
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

    # Dessiner le tail
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
        bullet_cfg: BulletConfig, date_box: DateBoxConfig,
        date_style: DateStyleConfig | None = None
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
        stA = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txtA, bulletA = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        p = Paragraph(txtA, stA, bulletText=bulletA)
        _w, ph = p.wrap(wA, 1e6)
        sbA = spacing_policy.space_before(kind, nameA, first_non_event_seen_in_S5_A)
        if nameA == "S5" and kind == "DATE" and not first_non_event_seen_in_S5_A:
            first_non_event_seen_in_S5_A = True
        saA = spacing_policy.space_after(kind, ph)
        needA_full = sbA + ph + saA
        if needA_full <= remA:
            # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas de A
            if kind == "DATE" and i < n - 1:
                next_raw = paras_text[i + 1]
                next_kind = "EVENT" if _is_event(next_raw) else "DATE"

                if next_kind == "EVENT":
                    # Calculer si le prochain EVENT peut rentrer dans A
                    first_non_event_after_current = first_non_event_seen_in_S5_A
                    next_st = _mk_style_for_kind(base, next_kind, bullet_cfg, date_box, font_size, date_style)
                    next_txt, next_bullet = _mk_text_for_kind(next_raw, next_kind, bullet_cfg, font_size, date_style)
                    next_p = Paragraph(next_txt, next_st, bulletText=next_bullet)
                    _next_w, next_ph = next_p.wrap(wA, 1e6)
                    next_sb = spacing_policy.space_before(next_kind, nameA, first_non_event_after_current)
                    next_sa = spacing_policy.space_after(next_kind, next_ph)
                    next_need = next_sb + next_ph + next_sa

                    # Si on n'a pas assez de place pour DATE + EVENT, ne pas placer la DATE dans A
                    if next_need > remA - needA_full:
                        # La DATE ne rentre pas dans A avec son EVENT, on arrête le remplissage de A
                        break

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
                    needB = sum(
                        part.wrap(wB, remB)[1] + spacing_policy.space_after("EVENT", part.wrap(wB, remB)[1]) for part in
                        parts[1:])
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
        stB = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txtB, bulletB = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        q = Paragraph(txtB, stB, bulletText=bulletB)
        _w, hq = q.wrap(wB, 1e6)
        sbB = spacing_policy.space_before(kind, nameB, first_non_event_seen_in_S5_B)
        if nameB == "S5" and kind == "DATE" and not first_non_event_seen_in_S5_B:
            first_non_event_seen_in_S5_B = True
        saB = spacing_policy.space_after(kind, hq)
        needB = sbB + hq + saB
        if needB <= remB:
            # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas de B
            if kind == "DATE" and i < n - 1:
                next_raw = paras_text[i + 1]
                next_kind = "EVENT" if _is_event(next_raw) else "DATE"

                if next_kind == "EVENT":
                    # Calculer si le prochain EVENT peut rentrer dans B
                    first_non_event_after_current = first_non_event_seen_in_S5_B
                    next_st = _mk_style_for_kind(base, next_kind, bullet_cfg, date_box, font_size, date_style)
                    next_txt, next_bullet = _mk_text_for_kind(next_raw, next_kind, bullet_cfg, font_size, date_style)
                    next_p = Paragraph(next_txt, next_st, bulletText=next_bullet)
                    _next_w, next_ph = next_p.wrap(wB, 1e6)
                    next_sb = spacing_policy.space_before(next_kind, nameB, first_non_event_after_current)
                    next_sa = spacing_policy.space_after(next_kind, next_ph)
                    next_need = next_sb + next_ph + next_sa

                    # Si on n'a pas assez de place pour DATE + EVENT, ne pas placer la DATE dans B
                    if next_need > remB - needB:
                        # La DATE ne rentre pas dans B avec son EVENT, on arrête le remplissage de B
                        break

            B_full.append(raw)
            remB -= needB
            i += 1
        else:
            break
    return A_full, A_tail, B_prelude, B_full, paras_text[i:]


def _build_poster_story(
        paras_text: List[str],
        base_style: ParagraphStyle,
        bullet_cfg: BulletConfig,
        poster_cfg: PosterConfig,
        font_size: float,
) -> list:
    """
    Construit la liste de flowables (Paragraphs) pour le poster.
    L'espacement des dates est intégré au style (spaceBefore/spaceAfter)
    plutôt qu'en Spacer séparés, ce qui évite le gaspillage d'espace
    aux transitions entre colonnes et permet à Frame de gérer
    correctement l'espacement (ignoré en haut de colonne, etc.).
    Utilisée à la fois par la mesure et le rendu pour garantir un résultat identique.
    """
    story: list = []
    for raw in paras_text:
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base_style, kind, bullet_cfg, DateBoxConfig(), font_size)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg, font_size)

        if kind == "DATE":
            # Intégrer l'espacement dans le style (pas de Spacer séparés)
            st = ParagraphStyle(
                name=f"{st.name}_poster",
                parent=st,
                spaceBefore=poster_cfg.date_spaceBefore,
                spaceAfter=poster_cfg.date_spaceAfter,
            )

        story.append(Paragraph(txt, st, bulletText=bullet))

    return story


def measure_poster_fit_at_fs(
        c: canvas.Canvas, frames: List[Section], paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float,
        bullet_cfg: BulletConfig,
        poster_cfg: PosterConfig,
        text_color: str = "#000000"
) -> bool:
    """
    Teste si tout le contenu tient dans les cadres à la taille de police donnée.
    Utilise le même pipeline Frame que le rendu réel (canvas jetable) pour
    éliminer toute divergence de mesure (padding Frame, gestion des Spacers, etc.).
    """
    from io import BytesIO

    base_style = paragraph_style(font_name, font_size, leading_ratio)
    base_style.textColor = HexColor(text_color)
    story = _build_poster_story(paras_text, base_style, bullet_cfg, poster_cfg, font_size)

    # Canvas jetable pour la mesure (on ne veut pas dessiner sur le vrai canvas)
    dummy_c = canvas.Canvas(BytesIO())

    for section in frames:
        if not story:
            break
        frame = Frame(section.x, section.y, section.w, section.h, showBoundary=0)
        frame.addFromList(story, dummy_c)

    return len(story) == 0


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
    story = _build_poster_story(paras_text, base_style, bullet_cfg, poster_cfg, font_size)

    for section in frames:
        if not story:
            break
        frame = Frame(section.x, section.y, section.w, section.h, showBoundary=0)
        frame.addFromList(story, c)
# misenpageur/image_builder.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import textwrap
import re
import html
from pathlib import Path
from typing import List

import logging # Ajouter cet import
log = logging.getLogger(__name__) # Obtenir le logger pour ce module


from PIL import Image, ImageDraw, ImageFont

from .config import Config, StoryConfig
from .textflow import _is_event, _strip_leading_bullet, _MONTH_HEADER_RE

# Préfixes des événements de sous-groupe de festival : à traiter comme des événements
_STORY_EVENT_MARKERS = ("{{SUBEV}}", "{{SUBFEST}}")


# --- Fonctions utilitaires ---

def _has_euro_glyph(font: ImageFont.FreeTypeFont) -> bool:
    """Vrai si la police a un vrai glyphe « € » (et pas le carré de remplacement)."""
    return font.getmask("€").getbbox() != font.getmask("�").getbbox()


def _get_font(font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
    # Tenter la résolution via la découverte dynamique
    try:
        from .font_discovery import get_ttf_path_for_pil
        ttf_path = get_ttf_path_for_pil(font_name)
        if ttf_path:
            font = ImageFont.truetype(ttf_path, font_size)
            if _has_euro_glyph(font):
                return font
            # La copie embarquée de certaines polices n'a pas le symbole € : on préfère la version système.
            system_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / Path(ttf_path).name
            if system_path.exists():
                system_font = ImageFont.truetype(str(system_path), font_size)
                if _has_euro_glyph(system_font):
                    return system_font
            return font
    except Exception:
        pass
    # Fallback : essayer le nom directement (fonctionne si c'est un chemin ou un nom système)
    try:
        return ImageFont.truetype(font_name, font_size)
    except IOError:
        try:
            return ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            log.warning(f"Polices '{font_name}' et 'arial.ttf' introuvables, fallback sur la police par défaut.")
            return ImageFont.load_default()


def _clean_html_for_pillow(html_text: str) -> str:
    # ... (fonction inchangée)
    if not html_text: return ""
    text_no_tags = re.sub(r'<[^>]+>', '', html_text)
    decoded_text = html.unescape(text_no_tags)
    return decoded_text.strip()


# ==================== MODIFICATION ICI ====================
def _draw_text_wrapped(
        draw: ImageDraw, text: str, pos: tuple[int, int], font: ImageFont.FreeTypeFont,
        max_width: int, fill: str, line_spacing: float = 1.2
):
    """
    Dessine du texte avec retour à la ligne automatique et interligne personnalisable.
    """
    x, y = pos
    avg_char_width = font.size * 0.55
    wrap_width = int(max_width / avg_char_width) if avg_char_width > 0 else 20
    wrapped_lines = textwrap.wrap(text, width=wrap_width, replace_whitespace=False)

    # On utilise la variable 'line_spacing' au lieu d'une valeur codée en dur
    line_height = font.size * line_spacing

    for line in wrapped_lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


# ==========================================================

# --- Fonctions principales ---

def _create_story_cover(cfg: StoryConfig, main_cfg: Config, project_root: str):
    """Génère l'image de couverture et retourne 1 en cas de succès, 0 sinon."""
    # ... (fonction inchangée)
    cover_path = Path(project_root) / main_cfg.cover_image
    if not cover_path.exists():
        log.warning(f"Image de couverture introuvable, la story de couv ne sera pas générée.")
        return 0 # Retourne 0 car aucun fichier n'a été créé
    background = Image.new("RGB", (cfg.width, cfg.height), color="#000000")
    with Image.open(cover_path) as img:
        img.thumbnail((cfg.width, cfg.height), Image.Resampling.LANCZOS)
        paste_x = (cfg.width - img.width) // 2
        paste_y = (cfg.height - img.height) // 2
        background.paste(img, (paste_x, paste_y))
    output_path = Path(cfg.output_dir) / "story_cover.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    background.save(output_path, "PNG")
    log.info(f"Story de couverture générée : {output_path}")
    return 1 # Retourne 1 car le fichier a été créé avec succès


def _make_story_background(cfg: StoryConfig):
    """Crée le fond d'une image de story (image voilée ou aplat de couleur)."""
    bg_type = getattr(cfg, 'background_type', 'color')
    bg_image_path = getattr(cfg, 'background_image', '')

    if bg_type == 'image' and bg_image_path and os.path.exists(bg_image_path):
        try:
            with Image.open(bg_image_path) as bg_img:
                img_ratio = bg_img.width / bg_img.height
                story_ratio = cfg.width / cfg.height
                if img_ratio > story_ratio:
                    new_height, new_width = cfg.height, int(cfg.height * img_ratio)
                else:
                    new_width, new_height = cfg.width, int(cfg.width / img_ratio)

                resized = bg_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                left, top = (resized.width - cfg.width) / 2, (resized.height - cfg.height) / 2
                img = resized.crop((left, top, left + cfg.width, top + cfg.height)).convert("RGBA")

            alpha = getattr(cfg, 'background_image_alpha', 0.5)
            veil = Image.new("RGBA", img.size, (255, 255, 255, int(alpha * 255)))
            return Image.alpha_composite(img, veil).convert("RGB")
        except Exception as e:
            log.warning(f"Impossible de charger l'image de fond '{bg_image_path}': {e}. Utilisation du fond de couleur.")

    return Image.new("RGB", (cfg.width, cfg.height), color=cfg.background_color)


def _wrap_measured(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Découpe `text` en lignes tenant dans `max_width` pixels (mesure réelle de la police)."""
    lines: List[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and font.getlength(candidate) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _group_agenda_days(paragraphs: List[str]) -> List[tuple[str, List[str]]]:
    """Regroupe les paragraphes en (titre du jour, [événements]). Les événements
    placés avant le premier titre sont rattachés à un titre vide."""
    days: List[tuple[str, List[str]]] = []
    for para_html in paragraphs:
        text = _clean_html_for_pillow(para_html)
        if text.startswith("{{IMG:"):
            continue  # placeholder d'image inline : sans objet sur une story
        month = _MONTH_HEADER_RE.match(text)
        if month:
            days.append((month.group(1).upper(), []))
        elif _is_event(para_html) or text.startswith(_STORY_EVENT_MARKERS):
            if not days:
                days.append(("", []))
            text = text.removeprefix("{{SUBEV}}").removeprefix("{{SUBFEST}}").strip()
            days[-1][1].append(_strip_leading_bullet(text))
        else:
            days.append((text.upper(), []))
    return days


def _create_story_agenda(cfg: StoryConfig, paragraphs: List[str]):
    """Génère les stories de l'agenda.

    Un jour n'est jamais coupé entre deux images tant qu'il tient sur une page ;
    s'il est trop long, il continue sur l'image suivante avec « (suite) ».
    Le contenu reste dans la zone sûre (safe_top / safe_bottom) d'Instagram.
    """
    font_date = _get_font(cfg.agenda_font_name, int(cfg.agenda_font_size * 1.2))
    font_event = _get_font(cfg.agenda_font_name, cfg.agenda_font_size)
    text_color = cfg.text_color

    margin = cfg.margin
    line_spacing = cfg.line_spacing_ratio

    content_width = cfg.width - 2 * margin
    indent = int(font_event.getlength("□ "))
    event_width = content_width - indent
    date_line_h = font_date.size * line_spacing
    event_line_h = font_event.size * line_spacing
    day_gap = int(cfg.agenda_font_size * 0.9)     # espace avant un titre de jour
    date_after = int(cfg.agenda_font_size * 0.3)  # espace entre le titre et le 1er événement
    event_gap = int(cfg.agenda_font_size * 0.25)  # espace entre deux événements

    avail = cfg.height - cfg.safe_top - cfg.safe_bottom

    def _date_item(title: str):
        lines = _wrap_measured(title, font_date, content_width)
        return ("date", lines, len(lines) * date_line_h + date_after)

    def _event_item(text: str):
        lines = _wrap_measured(text, font_event, event_width)
        return ("event", lines, len(lines) * event_line_h + event_gap)

    pages: List[List[tuple]] = [[]]
    used = 0.0  # hauteur utilisée sur la page courante

    def _new_page():
        nonlocal used
        pages.append([])
        used = 0.0

    for title, events in _group_agenda_days(paragraphs):
        date_item = _date_item(title) if title else None
        event_items = [_event_item(e) for e in events]
        gap = day_gap if (pages[-1] and date_item) else 0
        block_h = gap + (date_item[2] if date_item else 0) + sum(i[2] for i in event_items)

        # Le jour entier ne tient pas ici mais tient sur une page : on le déplace.
        if pages[-1] and used + block_h > avail and block_h <= avail:
            _new_page()
            gap = 0

        if date_item:
            # Un titre ne reste jamais seul en bas de page : il doit tenir avec son 1er événement.
            first_chunk = date_item[2] + (event_items[0][2] if event_items else 0)
            if pages[-1] and used + gap + first_chunk > avail:
                _new_page()
                gap = 0
            if gap:
                pages[-1].append(("gap", gap))
            pages[-1].append(date_item)
            used += gap + date_item[2]

        for item in event_items:
            if used + item[2] > avail and pages[-1]:
                _new_page()
                if title:  # rappel du jour en tête de page
                    cont = _date_item(f"{title} (SUITE)")
                    pages[-1].append(cont)
                    used += cont[2]
            pages[-1].append(item)
            used += item[2]

    page_num = 0
    for page in pages:
        if not page:
            continue
        page_num += 1
        img = _make_story_background(cfg)
        draw = ImageDraw.Draw(img)
        y = float(cfg.safe_top)
        for item in page:
            kind = item[0]
            if kind == "gap":
                y += item[1]
            elif kind == "date":
                for line in item[1]:
                    draw.text((margin, y), line, font=font_date, fill=text_color)
                    y += date_line_h
                y += date_after
            else:
                for n, line in enumerate(item[1]):
                    if n == 0:
                        draw.text((margin, y), "□", font=font_event, fill=text_color)
                    draw.text((margin + indent, y), line, font=font_event, fill=text_color)
                    y += event_line_h
                y += event_gap

        output_path = Path(cfg.output_dir) / f"story_agenda_{page_num:02d}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG")
        log.info(f"Story de l'agenda générée : {output_path}")

    return page_num  # Retourne le nombre total de pages créées


def generate_story_images(project_root: str, cfg: Config, paras: List[str]):
    """
    Point d'entrée pour la génération des images.
    Retourne le nombre total d'images (PNG) créées.
    """
    story_cfg_dict = cfg.stories
    if not story_cfg_dict.get("enabled", False):
        return 0 # Retourne 0 si la fonctionnalité est désactivée

    story_cfg = StoryConfig(**story_cfg_dict)

    print("\n--- Génération des images pour Stories ---")

    # On capture les valeurs retournées et on les additionne
    cover_images_created = _create_story_cover(story_cfg, cfg, project_root)
    agenda_images_created = _create_story_agenda(story_cfg, paras)

    total_images = cover_images_created + agenda_images_created

    print("------------------------------------------\n")
    return total_images  # On retourne le total
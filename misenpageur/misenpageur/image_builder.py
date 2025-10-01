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
from .textflow import _is_event, _strip_leading_bullet


# --- Fonctions utilitaires ---

def _get_font(font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
    # ... (fonction inchangée)
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


def _create_story_agenda(cfg: StoryConfig, paragraphs: List[str]):
    """Génère les stories avec marges et interligne personnalisés."""

    font_date = _get_font(cfg.agenda_font_name, int(cfg.agenda_font_size * 1.1))
    font_event = _get_font(cfg.agenda_font_name, cfg.agenda_font_size)
    text_color = cfg.text_color

    margin = getattr(cfg, 'margin', 60)
    line_spacing = getattr(cfg, 'line_spacing_ratio', 1.2)

    content_width = cfg.width - (2 * margin)
    para_idx, page_num = 0, 0

    while para_idx < len(paragraphs):
        # ... (le reste de la fonction est correct et n'a pas besoin de changer)
        page_num += 1
        img = None
        bg_type = getattr(cfg, 'background_type', 'color')
        bg_image_path = getattr(cfg, 'background_image', '')

        if bg_type == 'image' and bg_image_path and os.path.exists(bg_image_path):
            try:
                with Image.open(bg_image_path) as bg_img:
                    # Logique de redimensionnement/recadrage
                    img_ratio = bg_img.width / bg_img.height
                    story_ratio = cfg.width / cfg.height
                    if img_ratio > story_ratio:
                        new_height, new_width = cfg.height, int(cfg.height * img_ratio)
                    else:
                        new_width, new_height = cfg.width, int(cfg.width / img_ratio)

                    resized = bg_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    left, top = (resized.width - cfg.width) / 2, (resized.height - cfg.height) / 2
                    img = resized.crop((left, top, left + cfg.width, top + cfg.height)).convert("RGBA")

                # Appliquer le voile de transparence
                alpha = getattr(cfg, 'background_image_alpha', 0.5)
                veil = Image.new("RGBA", img.size, (255, 255, 255, int(alpha * 255)))
                img = Image.alpha_composite(img, veil).convert("RGB")
            except Exception as e:
                log.warning(f"Impossible de charger l'image de fond '{bg_image_path}': {e}. Utilisation du fond de couleur.")
                img = None

        # Si le type est 'color' ou si l'image a échoué, on crée le fond uni
        if img is None:
            img = Image.new("RGB", (cfg.width, cfg.height), color=cfg.background_color)

        draw = ImageDraw.Draw(img)
        current_y = 80

        while current_y < cfg.height - 100 and para_idx < len(paragraphs):
            # ... (logique de préparation du texte)
            para_html = paragraphs[para_idx]
            text = _clean_html_for_pillow(para_html)
            is_event = _is_event(para_html)

            final_text, font_to_use, x_pos, width_to_use = "", font_event, 0, 0
            if is_event:
                final_text = "□ " + _strip_leading_bullet(text)
                font_to_use = font_event
                x_pos, width_to_use = margin + 40, content_width - 40
            else:
                final_text = text.upper()
                font_to_use = font_date
                x_pos, width_to_use = margin, content_width
                current_y += 20

            # L'appel est maintenant correct car la fonction a été mise à jour
            y_after_draw = _draw_text_wrapped(draw, final_text, (x_pos, current_y), font_to_use, width_to_use,
                                              text_color, line_spacing=line_spacing)

            if y_after_draw >= cfg.height - 100 and para_idx < len(paragraphs) - 1:
                if not is_event: current_y -= 20
                break

            current_y = y_after_draw
            if not is_event:
                current_y += 10

            para_idx += 1

        # ... (sauvegarde)
        output_filename = f"story_agenda_{page_num:02d}.png"
        output_path = Path(cfg.output_dir) / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG")
        log.info(f"Story de l'agenda générée : {output_path}")

    return page_num # Retourne le nombre total de pages créées


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
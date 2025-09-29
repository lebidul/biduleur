from __future__ import annotations

import os
import textwrap
import re
import html
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw, ImageFont

from .config import Config, StoryConfig
from .textflow import _is_event, _strip_leading_bullet  # On réutilise la détection


# --- Fonctions utilitaires ---

def _get_font(font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
    """Tente de charger une police avec des fallbacks."""
    try:
        return ImageFont.truetype(font_name, font_size)
    except IOError:
        try:
            return ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            print("[WARN] Police introuvable, utilisation de la police par défaut.")
            return ImageFont.load_default()


def _clean_html_for_pillow(html_text: str) -> str:
    """
    Nettoie une chaîne HTML pour un rendu texte brut :
    1. Supprime toutes les balises HTML.
    2. Décode les entités HTML (ex: &eacute; -> é, &nbsp; -> ' ').
    """
    if not html_text:
        return ""
    # 1. Supprimer les balises
    text_no_tags = re.sub(r'<[^>]+>', '', html_text)
    # 2. Décoder les entités
    decoded_text = html.unescape(text_no_tags)
    return decoded_text.strip()


def _draw_text_wrapped(
        draw: ImageDraw, text: str, pos: tuple[int, int], font: ImageFont.FreeTypeFont,
        max_width: int, fill: str, line_spacing: float = 1.2
):
    """
    Dessine du texte avec retour à la ligne automatique et retourne la position Y finale.
    """
    x, y = pos

    # Textwrap a du mal avec les longues lignes sans espaces. On l'aide un peu.
    avg_char_width = font.size * 0.55
    wrap_width = int(max_width / avg_char_width) if avg_char_width > 0 else 20

    wrapped_lines = textwrap.wrap(text, width=wrap_width, replace_whitespace=False)

    line_height = font.size * line_spacing
    for line in wrapped_lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


# --- Fonctions principales de génération d'images ---

def _create_story_cover(cfg: StoryConfig, main_cfg: Config, project_root: str):
    """Génère l'image de couverture en mode 'letterbox' pour éviter de tronquer."""

    cover_path = Path(project_root) / main_cfg.cover_image
    if not cover_path.exists():
        print("[WARN] Image de couverture introuvable, la story de couv ne sera pas générée.")
        return

    # 1. Créer une image de fond noire aux dimensions de la story
    background = Image.new("RGB", (cfg.width, cfg.height), color="#000000")

    with Image.open(cover_path) as img:
        # 2. Calculer les nouvelles dimensions pour que l'image tienne dans le cadre
        img.thumbnail((cfg.width, cfg.height), Image.Resampling.LANCZOS)

        # 3. Calculer la position pour centrer l'image redimensionnée
        paste_x = (cfg.width - img.width) // 2
        paste_y = (cfg.height - img.height) // 2

        # 4. Coller l'image sur le fond noir
        background.paste(img, (paste_x, paste_y))

    # 5. Sauvegarder l'image
    output_path = Path(cfg.output_dir) / "story_cover.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    background.save(output_path, "PNG")
    print(f"[INFO] Story de couverture générée : {output_path}")


def _create_story_agenda(cfg: StoryConfig, paragraphs: List[str]):
    """Génère une ou plusieurs images de l'agenda avec pagination."""

    font_date = _get_font(cfg.agenda_font_name, int(cfg.agenda_font_size * 1.1))
    font_event = _get_font(cfg.agenda_font_name, cfg.agenda_font_size)

    margin = 60
    content_width = cfg.width - (2 * margin)

    para_idx = 0
    page_num = 0

    while para_idx < len(paragraphs):
        page_num += 1

        # 1. Créer une nouvelle image pour chaque page
        img = Image.new("RGB", (cfg.width, cfg.height), color=cfg.background_color)
        draw = ImageDraw.Draw(img)

        current_y = 80  # Marge haute

        # 2. Remplir la page actuelle
        while current_y < cfg.height - 100 and para_idx < len(paragraphs):
            para_html = paragraphs[para_idx]
            text = _clean_html_for_pillow(para_html)

            # Estimer la hauteur avant de dessiner pour éviter de dépasser
            y_after_draw = current_y

            if _is_event(para_html):
                clean_text = "• " + _strip_leading_bullet(text)
                y_after_draw = _draw_text_wrapped(draw, clean_text, (margin + 40, current_y), font_event,
                                                  content_width - 40, cfg.text_color)
            else:  # C'est une date
                y_after_draw = current_y + 20
                y_after_draw = _draw_text_wrapped(draw, text.upper(), (margin, y_after_draw), font_date, content_width,
                                                  cfg.text_color)
                y_after_draw += 10

            # Si on dépasse, on ne dessine pas et on passe à la page suivante
            if y_after_draw >= cfg.height - 100:
                break

            # Si c'est bon, on dessine vraiment (en redessinant par-dessus l'estimation)
            if _is_event(para_html):
                clean_text = "• " + _strip_leading_bullet(text)
                current_y = _draw_text_wrapped(draw, clean_text, (margin + 40, current_y), font_event,
                                               content_width - 40, cfg.text_color)
            else:  # C'est une date
                current_y += 20
                current_y = _draw_text_wrapped(draw, text.upper(), (margin, current_y), font_date, content_width,
                                               cfg.text_color)
                current_y += 10

            para_idx += 1

        # 3. Sauvegarder la page terminée
        output_filename = f"story_agenda_{page_num:02d}.png"
        output_path = Path(cfg.output_dir) / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG")
        print(f"[INFO] Story de l'agenda générée : {output_path}")


def generate_story_images(project_root: str, cfg: Config, paras: List[str]):
    """Point d'entrée pour la génération de toutes les images pour les Stories."""
    story_cfg_dict = cfg.stories
    if not story_cfg_dict.get("enabled", False):
        return

    story_cfg = StoryConfig(**story_cfg_dict)

    print("\n--- Génération des images pour Stories ---")
    _create_story_cover(story_cfg, cfg, project_root)
    _create_story_agenda(story_cfg, paras)
    print("------------------------------------------\n")
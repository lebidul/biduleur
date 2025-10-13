#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire de configuration pour l'application Le Truc (PyQt6)
"""
import os
from utils.helpers import get_resource_path, project_defaults


class ConfigManager:
    """Gère le chargement des valeurs par défaut depuis config.yml"""

    def __init__(self):
        self.defaults = self._load_defaults()

    def _load_defaults(self) -> dict:
        """Charge les valeurs par défaut depuis config.yml"""
        # Valeurs de secours codées en dur
        fallback = {
            "cover": "",
            "ours_background_png": "",
            "logos_dir": "",
            "auteur_couv": "",
            "auteur_couv_url": "",
            "skip_cover": False,
            "page_margin_mm": 1.0,
            "date_separator_type": "ligne",
            "date_spacing": "4",
            "poster_design": 0,
            "font_size_safety_factor": 0.98,
            "background_alpha": 0.85,
            "poster_title": "",
            "cucaracha_type": "none",
            "cucaracha_value": "",
            "cucaracha_text_font": "Arial",
            "cucaracha_font_size": 8,
            "font_size_mode": "auto",
            "font_size_forced": 10.0,
            "stories_enabled": True,
            "stories_font_name": "Arial",
            "stories_font_size": 45,
            "stories_font_color": "#000000",
            "stories_bg_type": "color",
            "stories_bg_color": "#FFFFFF",
            "stories_bg_image": "",
            "stories_alpha": 0.5,
        }

        try:
            from misenpageur.misenpageur.config import Config
            defaults = project_defaults()
            cfg_path = defaults.get("config")

            if not cfg_path or not os.path.exists(cfg_path):
                print(f"[WARN] Fichier de configuration introuvable : {cfg_path}")
                return fallback

            cfg = Config.from_yaml(cfg_path)
            resource_root = get_resource_path('.')

            def make_abs_path(rel_path):
                """Convertit un chemin relatif en absolu"""
                if not rel_path or os.path.isabs(rel_path):
                    return rel_path
                return os.path.join(resource_root, rel_path)

            # Mise à jour avec les valeurs du config.yml
            fallback.update({
                "cover": make_abs_path(cfg.cover_image or ""),
                "logos_dir": make_abs_path(cfg.logos_dir or ""),
                "auteur_couv": getattr(cfg, "auteur_couv", "") or "",
                "auteur_couv_url": getattr(cfg, "auteur_couv_url", "") or "",
                "skip_cover": getattr(cfg, "skip_cover", False),
                "date_spacing": str(cfg.date_spaceBefore),
            })

            if isinstance(cfg.section_1, dict):
                fallback["ours_background_png"] = make_abs_path(
                    cfg.section_1.get("ours_background_png", "")
                )

            if isinstance(cfg.pdf_layout, dict):
                fallback["page_margin_mm"] = cfg.pdf_layout.get("page_margin_mm", 1.0)

            if cfg.date_line.get("enabled", True):
                fallback["date_separator_type"] = "ligne"
            elif cfg.date_box.get("enabled", False):
                fallback["date_separator_type"] = "box"
            else:
                fallback["date_separator_type"] = "aucun"

            if isinstance(cfg.poster, dict):
                fallback.update({
                    "poster_design": cfg.poster.get("design", 0),
                    "font_size_safety_factor": cfg.poster.get("font_size_safety_factor", 0.98),
                    "background_alpha": cfg.poster.get("background_image_alpha", 0.85),
                    "poster_title": cfg.poster.get("title", "")
                })

            if isinstance(cfg.cucaracha_box, dict):
                fallback.update({
                    "cucaracha_type": cfg.cucaracha_box.get("content_type", "none"),
                    "cucaracha_value": cfg.cucaracha_box.get("content_value", ""),
                    "cucaracha_text_font": cfg.cucaracha_box.get("text_font_name", "Arial"),
                    "cucaracha_font_size": cfg.cucaracha_box.get("text_font_size", 8),
                })

            fallback["font_size_mode"] = getattr(cfg, "font_size_mode", "auto")
            fallback["font_size_forced"] = getattr(cfg, "font_size_forced", 10.0)

            if isinstance(cfg.stories, dict):
                fallback["stories_enabled"] = cfg.stories.get("enabled", True)
                fallback["stories_font_name"] = cfg.stories.get("agenda_font_name", "Arial")
                fallback["stories_font_size"] = cfg.stories.get("agenda_font_size", 45)
                fallback["stories_font_color"] = cfg.stories.get("text_color", "#000000")
                fallback["stories_bg_color"] = cfg.stories.get("background_color", "#FFFFFF")
                fallback["stories_bg_type"] = "color"  # Par défaut
                fallback["stories_alpha"] = cfg.stories.get("background_image_alpha", 0.5)

        except Exception as e:
            print(f"[WARN] Erreur lors du chargement de config.yml : {e}")

        return fallback

    def get(self, key: str, default=None):
        """Récupère une valeur de configuration"""
        return self.defaults.get(key, default)
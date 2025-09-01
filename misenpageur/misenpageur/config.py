# -*- coding: utf-8 -*-
"""
Configuration loading utilities.
"""
from __future__ import annotations

import os
import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections.abc import Mapping


def _as_bool(v, default=False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    return default


def _as_float(v, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


@dataclass
class Config:
    # --- essentiels projet ---
    month_label: str = ""
    input_html: str = "assets/biduleur.html"
    template_pdf: str = ""
    output_pdf: str = "bidul/bidul.pdf"
    logos_dir: str = "assets/logos"
    cover_image: str = ""
    ours_md: str = "assets/ours.md"

    # --- typo ---
    font_name: str = "Helvetica"
    leading_ratio: float = 1.12
    font_size_min: float = 6.5
    font_size_max: float = 10.0

    # --- mise en page ---
    inner_padding: float = 12.0
    # ordre des sections texte (par défaut: 2 colonnes S5→S6 puis S3→S4)
    text_sections_order: List[str] = field(default_factory=lambda: ["S5", "S6", "S3", "S4"])

    # --- espacements dates/événements ---
    date_spaceBefore: float = 6.0
    date_spaceAfter: float = 3.0
    event_spaceBefore: float = 1.0
    event_spaceAfter: float = 1.0
    event_spaceAfter_perLine: float = 0.4
    min_event_spaceAfter: float = 1.0
    # S5: pas de marge avant pour la toute première ligne non-événement (ex. "En bref")
    first_non_event_spaceBefore_in_S5: float = 0.0

    # --- césure utile entre colonnes ---
    split_min_gain_ratio: float = 0.10

    # --- bullets / hanging indent ---
    show_event_bullet: bool = True
    event_bullet_replacement: Optional[str] = None  # ex. "■" ; sinon None
    event_hanging_indent: float = 10.0              # retrait suspendu en pt

    # --- date box (bloc YAML ou clés à plat) ---
    date_box: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = yaml.safe_load(f) or {}

        # point de départ: valeurs par défaut
        cfg = cls()

        # helper d’affectation
        def setv(attr: str, key: Optional[str] = None, cast=None):
            k = key or attr
            if k in data and data[k] is not None:
                v = data[k]
                if cast is not None:
                    try:
                        v = cast(v)
                    except Exception:
                        pass
                setattr(cfg, attr, v)

        # chemins & champs simples
        setv("month_label", "month_label", str)
        setv("input_html", "input_html", str)
        setv("template_pdf", "template_pdf", str)
        setv("output_pdf", "output_pdf", str)
        setv("logos_dir", "logos_dir", str)
        setv("cover_image", "cover_image", str)
        setv("ours_md", "ours_md", str)

        setv("font_name", "font_name", str)
        setv("leading_ratio", "leading_ratio", float)
        setv("font_size_min", "font_size_min", float)
        setv("font_size_max", "font_size_max", float)

        setv("inner_padding", "inner_padding", float)

        # ordre des sections (liste de str)
        if "text_sections_order" in data and isinstance(data["text_sections_order"], list):
            cfg.text_sections_order = [str(x) for x in data["text_sections_order"]]

        # espacements
        setv("date_spaceBefore", "date_spaceBefore", float)
        setv("date_spaceAfter", "date_spaceAfter", float)
        setv("event_spaceBefore", "event_spaceBefore", float)
        setv("event_spaceAfter", "event_spaceAfter", float)
        setv("event_spaceAfter_perLine", "event_spaceAfter_perLine", float)
        setv("min_event_spaceAfter", "min_event_spaceAfter", float)
        setv("first_non_event_spaceBefore_in_S5", "first_non_event_spaceBefore_in_S5", float)

        # césure utile
        setv("split_min_gain_ratio", "split_min_gain_ratio", float)

        # bullets / indent
        if "show_event_bullet" in data:
            cfg.show_event_bullet = _as_bool(data["show_event_bullet"], cfg.show_event_bullet)
        setv("event_bullet_replacement", "event_bullet_replacement", str)
        setv("event_hanging_indent", "event_hanging_indent", float)

        # --- date_box : bloc ou clés à plat ---
        block = data.get("date_box", None)
        if block is not None:
            # Support dict / Mapping ou objets de type "namespace"
            def get_from_block(b, key, default=None):
                if isinstance(b, Mapping):
                    return b.get(key, default)
                return getattr(b, key, default)
            cfg.date_box = {
                "enabled": _as_bool(get_from_block(block, "enabled"), False),
                "padding": _as_float(get_from_block(block, "padding"), 2.0),
                "border_width": _as_float(get_from_block(block, "border_width"), 0.5),
                "border_color": get_from_block(block, "border_color", "#000000"),
                "back_color": get_from_block(block, "back_color", None),
            }
        else:
            # clés à plat
            flat_enabled = data.get("date_box_enabled", None)
            flat_padding = data.get("date_box_padding", None)
            flat_bw = data.get("date_box_border_width", None)
            flat_bc = data.get("date_box_border_color", None)
            flat_bg = data.get("date_box_back_color", None)
            cfg.date_box = {
                "enabled": _as_bool(flat_enabled, False),
                "padding": _as_float(flat_padding, 2.0),
                "border_width": _as_float(flat_bw, 0.5),
                "border_color": flat_bc if flat_bc is not None else "#000000",
                "back_color": flat_bg,
            }

        # normaliser/expanduser certains chemins
        for attr in ("input_html", "template_pdf", "output_pdf", "logos_dir", "cover_image", "ours_md"):
            val = getattr(cfg, attr, "")
            if isinstance(val, str):
                setattr(cfg, attr, os.path.expanduser(val))

        return cfg

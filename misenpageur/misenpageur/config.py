# -*- coding: utf-8 -*-
"""
Configuration loading utilities.
"""
from __future__ import annotations
import os, yaml
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Config:
    month_label: str
    input_html: str
    template_pdf: str
    output_pdf: str
    logos_dir: str
    cover_image: str
    ours_md: str
    font_name: str
    leading_ratio: float
    font_size_min: float
    font_size_max: float
    inner_padding: float
    text_sections_order: list[str]

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = yaml.safe_load(f)
        return cls(
            month_label = data.get("month_label",""),
            input_html  = data["input_html"],
            template_pdf= data.get("template_pdf",""),
            output_pdf  = data["output_pdf"],
            logos_dir   = data["logos_dir"],
            cover_image = data.get("cover_image",""),
            ours_md     = data["ours_md"],
            font_name   = data.get("font_name","Helvetica"),
            leading_ratio = float(data.get("leading_ratio", 1.12)),
            font_size_min = float(data.get("font_size_min", 6.5)),
            font_size_max = float(data.get("font_size_max", 10.0)),
            inner_padding = float(data.get("inner_padding", 12)),
            text_sections_order = list(data.get("text_sections_order", ["S5","S7","S6","S8","S3","S4"])),
        )

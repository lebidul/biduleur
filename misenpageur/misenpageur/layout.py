# -*- coding: utf-8 -*-
"""
Layout section coordinates and helpers.
"""
from __future__ import annotations
import yaml
from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class Section:
    name: str
    page: int
    x: float
    y: float
    w: float
    h: float

@dataclass
class PageSpec:
    width: float
    height: float

@dataclass
class Layout:
    page: PageSpec
    sections: dict[str, Section]
    s1_split: dict

    @classmethod
    def from_yaml(cls, path: str) -> "Layout":
        with open(path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = yaml.safe_load(f)
        page = PageSpec(width=float(data["page_size"]["width"]),
                        height=float(data["page_size"]["height"]))
        secs = {}
        for name, info in data["sections"].items():
            secs[name] = Section(name=name, page=int(info["page"]), x=float(info["x"]), y=float(info["y"]), w=float(info["w"]), h=float(info["h"]))
        return cls(page=page, sections=secs, s1_split=data.get("s1_split", {"logos_ratio":0.6,"ours_ratio":0.4}))

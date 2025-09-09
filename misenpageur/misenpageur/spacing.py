# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SpacingConfig:
    date_spaceBefore: float = 6.0
    date_spaceAfter: float  = 3.0
    event_spaceBefore: float = 1.0
    event_spaceAfter: float  = 1.0
    event_spaceAfter_perLine: float = 0.4
    min_event_spaceAfter: float = 1.0
    # Spécifique S5 : pas de marge avant pour la toute première ligne non-événement (ex. "En bref")
    first_non_event_spaceBefore_in_S5: float = 0.0

class SpacingPolicy:
    """Calcule spaceBefore/spaceAfter en fonction du type (DATE/EVENT), de la section et de la hauteur réelle."""
    def __init__(self, cfg: SpacingConfig, leading: float):
        self.cfg = cfg
        self.leading = max(1.0, leading)

    def space_before(self, kind: str, section_name: str, first_non_event_seen_in_S5: bool) -> float:
        if kind == "DATE":
            if section_name == "S5" and not first_non_event_seen_in_S5:
                return self.cfg.first_non_event_spaceBefore_in_S5
            return self.cfg.date_spaceBefore
        return self.cfg.event_spaceBefore

    def space_after(self, kind: str, para_height: float) -> float:
        if kind == "DATE":
            return self.cfg.date_spaceAfter
        # dynamique pour événements, à la ligne
        lines = max(1, int(round(para_height / self.leading)))
        extra = max(0, lines - 1) * self.cfg.event_spaceAfter_perLine
        return max(self.cfg.min_event_spaceAfter, self.cfg.event_spaceAfter + extra)

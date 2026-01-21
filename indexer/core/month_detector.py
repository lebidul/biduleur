"""
Détection des sections de mois (juillet/août) dans les Biduls d'été.

Les Biduls de juillet (~27 numéros) contiennent les événements de juillet ET août
dans un seul PDF. Ce module détecte les sections de mois pour permettre au parser
d'attribuer les bonnes dates aux événements.

Patterns supportés:
- Headers simples: "juillet", "aout", "août" (minuscules)
- Headers Title Case: "Juillet", "Août"
- Headers majuscules: "JUILLET", "AOÛT", "AOUT"
- Headers composés: "FIN JUILLET", "DÉBUT AOÛT"
- Ranges: "Du X au Y juillet", "Du X au Y août"
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class MonthSection:
    """Une section de mois dans le texte."""
    line_number: int      # Numéro de ligne du header
    month: int            # 7 = juillet, 8 = août
    header_text: str      # Texte original du header
    start_pos: int        # Position caractère de début


# Patterns de détection des headers de mois
# Ordonnés du plus spécifique au plus général
MONTH_HEADER_PATTERNS = [
    # Format FIN JUILLET / DÉBUT AOÛT
    (r'^(?:FIN|DÉBUT|DEBUT)\s+(JUILLET)(?:\s|$)', 7),
    (r'^(?:FIN|DÉBUT|DEBUT)\s+(AO[UÛ]T)(?:\s|$)', 8),

    # Format Du X au Y mois (ranges avec mois explicite)
    (r'^Du\s+\d+(?:er)?\s+au\s+\d+\s+(juillet)\b', 7),
    (r'^Du\s+\d+(?:er)?\s+au\s+\d+\s+(ao[uû]t)\b', 8),

    # Format "En juillet :" / "En août :" / "En septembre :"
    (r'^En\s+(juillet)\s*:?\s*$', 7),
    (r'^En\s+(ao[uû]t)\s*:?\s*$', 8),
    (r'^En\s+(septembre)\s*:?\s*$', 9),

    # Format "Juillet:" / "Août :" / "Septembre :"
    (r'^(Juillet)\s*:?\s*$', 7),
    (r'^(Ao[uû]t)\s*:?\s*$', 8),
    (r'^(Septembre)\s*:?\s*$', 9),

    # Format simple seul sur la ligne
    (r'^(juillet)\s*$', 7),
    (r'^(aout)\s*$', 8),
    (r'^(août)\s*$', 8),
    (r'^(septembre)\s*$', 9),

    # Format majuscules
    (r'^(JUILLET)\s*$', 7),
    (r'^(AO[UÛ]T)\s*$', 8),
    (r'^(AOUT)\s*$', 8),
    (r'^(SEPTEMBRE)\s*$', 9),

    # Variations OCR tronquées ou avec erreurs
    (r'^(AO)\s*$', 8),            # "AOÛT" tronqué en "AO"
    (r'^(AQU?T)\s*$', 8),         # OCR "Q" au lieu de "O"
    (r'^(AQUT)\s*$', 8),          # OCR sans accent
]


def strip_html_tags(text: str) -> str:
    """Supprime les balises HTML d'une chaîne."""
    return re.sub(r'<[^>]+>', '', text)


def detect_month_sections(text: str) -> List[MonthSection]:
    """
    Détecte toutes les sections de mois dans le texte.

    Args:
        text: Texte complet extrait du PDF

    Returns:
        Liste des sections de mois détectées, ordonnées par position
    """
    sections = []
    lines = text.split('\n')
    current_pos = 0

    for line_num, line in enumerate(lines):
        line_stripped = line.strip()
        # Nettoyer les balises HTML pour la détection (ex: "<bi>Juillet </bi>" → "Juillet")
        line_clean = strip_html_tags(line_stripped).strip()

        for pattern, month in MONTH_HEADER_PATTERNS:
            match = re.match(pattern, line_clean, re.IGNORECASE)
            if match:
                sections.append(MonthSection(
                    line_number=line_num,
                    month=month,
                    header_text=line_stripped,  # Garder le texte original pour le debug
                    start_pos=current_pos
                ))
                break  # Un seul pattern par ligne

        current_pos += len(line) + 1  # +1 pour le \n

    return sections


def get_month_for_line(sections: List[MonthSection],
                       line_number: int,
                       default_month: int = 7) -> int:
    """
    Détermine le mois applicable pour un numéro de ligne donné.

    Args:
        sections: Liste des sections de mois détectées
        line_number: Numéro de ligne (0-indexed)
        default_month: Mois par défaut (7 = juillet)

    Returns:
        Numéro du mois (7 ou 8)
    """
    if not sections:
        return default_month

    applicable_month = default_month
    for section in sections:
        if section.line_number <= line_number:
            applicable_month = section.month
        else:
            break

    return applicable_month


def get_month_for_position(sections: List[MonthSection],
                           char_position: int,
                           default_month: int = 7) -> int:
    """
    Détermine le mois applicable pour une position de caractère donnée.

    Args:
        sections: Liste des sections de mois détectées
        char_position: Position du caractère dans le texte
        default_month: Mois par défaut (7 = juillet)

    Returns:
        Numéro du mois (7 ou 8)
    """
    if not sections:
        return default_month

    applicable_month = default_month
    for section in sections:
        if section.start_pos <= char_position:
            applicable_month = section.month
        else:
            break

    return applicable_month


def is_summer_bidul(bidul_mois: Optional[int]) -> bool:
    """
    Vérifie si c'est un Bidul d'été (juillet couvrant juillet+août).

    Args:
        bidul_mois: Mois du Bidul

    Returns:
        True si c'est un Bidul de juillet
    """
    return bidul_mois == 7

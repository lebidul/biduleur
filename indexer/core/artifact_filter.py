"""
Détection des faux événements (artifacts) à filtrer lors de l'extraction.

Un artifact est un bloc de texte qui n'est pas un vrai événement :
- Texte trop court (< 15 caractères)
- Informations/annonces (contacts, inscriptions, URLs)
- Événements sans lieu ni contenu (artiste/spectacle)

Ces critères correspondent à ceux de scripts/clean_database.py.
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Patterns indiquant une info/annonce plutôt qu'un événement
# (repris de scripts/clean_database.py)
INFO_PATTERNS = [
    r'\brens\.\s',
    r'\bcontact\s*:',
    r'\bwww\.',
    r'\bhttps?://',
    r'\binscription',
    r'\+ d\'infos',
    r'\bdans divers lieux\b',
    r'\bplus d\'infos\b',
    r'\bréservation\b',
]

# Longueur minimale du raw_text_clean
MIN_TEXT_LENGTH = 15


@dataclass
class ArtifactDetection:
    """Résultat de la détection d'artifact."""
    is_artifact: bool
    reason: str


def detect_artifact(raw_text: str, raw_text_clean: Optional[str] = None,
                    lieu_raw: Optional[str] = None,
                    artistes: Optional[list] = None,
                    spectacles: Optional[list] = None) -> ArtifactDetection:
    """
    Détecte si un événement est un artifact (faux événement).

    Args:
        raw_text: Texte brut de l'événement (avec balises)
        raw_text_clean: Texte sans balises (optionnel, calculé si absent)
        lieu_raw: Nom du lieu extrait
        artistes: Liste des artistes extraits
        spectacles: Liste des spectacles extraits

    Returns:
        ArtifactDetection avec is_artifact et reason
    """
    # Calculer raw_text_clean si non fourni
    if raw_text_clean is None:
        # Retirer les balises HTML simples
        raw_text_clean = re.sub(r'<[^>]+>', '', raw_text or '')

    # Normaliser les espaces
    raw_text_clean = ' '.join(raw_text_clean.split()).strip()

    # === CRITÈRE 1: Texte trop court ===
    if len(raw_text_clean) < MIN_TEXT_LENGTH:
        return ArtifactDetection(
            is_artifact=True,
            reason=f"Texte trop court ({len(raw_text_clean)} < {MIN_TEXT_LENGTH} chars)"
        )

    # === CRITÈRE 2: Info/annonce (patterns) ===
    text_lower = raw_text_clean.lower()
    for pattern in INFO_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return ArtifactDetection(
                is_artifact=True,
                reason=f"Info/annonce détectée (pattern: {pattern})"
            )

    # === CRITÈRE 3: Sans lieu ni contenu ===
    has_lieu = bool(lieu_raw and lieu_raw.strip())
    has_artiste = bool(artistes and len(artistes) > 0)
    has_spectacle = bool(spectacles and len(spectacles) > 0)

    if not has_lieu and not has_artiste and not has_spectacle:
        return ArtifactDetection(
            is_artifact=True,
            reason="Sans lieu ni artiste ni spectacle"
        )

    # === Pas un artifact ===
    return ArtifactDetection(
        is_artifact=False,
        reason="Événement valide"
    )


def is_artifact(raw_text: str, raw_text_clean: Optional[str] = None,
                lieu_raw: Optional[str] = None,
                artistes: Optional[list] = None,
                spectacles: Optional[list] = None) -> bool:
    """Version simplifiée: retourne True si c'est un artifact."""
    return detect_artifact(raw_text, raw_text_clean, lieu_raw, artistes, spectacles).is_artifact

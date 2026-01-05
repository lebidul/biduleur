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
from typing import Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Biduls sans événements (cas particuliers)
# - 255: COVID confinement, contenu informatif uniquement
BIDULS_SANS_EVENEMENTS: Set[int] = {
    255,
}


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
    # Rubriques éditoriales des anciens Biduls (bruit OCR)
    r'Rubrique Cucaracha',
    r'Dicton du mois',
    r'Blagounette',
    r'Le Bidul est tiré à',
    r'tiré à \d+ exemplaires',
]

# Patterns de fragments de date/en-tête à exclure
# Ex: "au 31 juillet 2011", "au 31 Août 2011 Les Arts SERVICES", "janvier au 1er février"
DATE_FRAGMENT_PATTERNS = [
    r'^au\s+\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{4}',
    # "mois au Xer mois" - fragment de période sans événement
    # Ex: "janvier au 1er février", "mars au 15 avril"
    r'^(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s+au\s+\d{1,2}(?:er)?\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s*$',
]

# Patterns de références lieu hors région à exclure
# Ex: "Le Fool, Quiberon (56)", "La Grange, Nantes (44)"
# Ces fragments ne sont pas des événements mais des références à des lieux hors Sarthe (72)
LIEU_REFERENCE_PATTERNS = [
    # "Lieu/Nom, Ville (code)" où code != 72
    r'^[A-Za-zÀ-ÿ\s\-\']+,\s*[A-Za-zÀ-ÿ\s\-\']+\s*\((?!72\b)\d{2,3}\)\s*$',
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
                    spectacles: Optional[list] = None,
                    nom_evenement: Optional[str] = None) -> ArtifactDetection:
    """
    Détecte si un événement est un artifact (faux événement).

    Args:
        raw_text: Texte brut de l'événement (avec balises)
        raw_text_clean: Texte sans balises (optionnel, calculé si absent)
        lieu_raw: Nom du lieu extrait
        artistes: Liste des artistes extraits
        spectacles: Liste des spectacles extraits
        nom_evenement: Nom de l'événement extrait (Soirée X, Festival X, etc.)

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

    # === CRITÈRE 2b: Fragment de date/en-tête ===
    # Ex: "au 31 juillet 2011", "au 31 Août 2011 Les Arts SERVICES"
    for pattern in DATE_FRAGMENT_PATTERNS:
        if re.match(pattern, text_lower, re.IGNORECASE):
            return ArtifactDetection(
                is_artifact=True,
                reason=f"Fragment de date/en-tête (pattern: {pattern})"
            )

    # === CRITÈRE 2c: Référence lieu hors région ===
    # Ex: "Le Fool, Quiberon (56)" - juste un lieu + ville + code postal hors Sarthe
    for pattern in LIEU_REFERENCE_PATTERNS:
        if re.match(pattern, raw_text_clean, re.IGNORECASE):
            return ArtifactDetection(
                is_artifact=True,
                reason=f"Référence lieu hors région (pattern: {pattern})"
            )

    # === CRITÈRE 3: Sans lieu ni contenu ===
    has_lieu = bool(lieu_raw and lieu_raw.strip())
    has_artiste = bool(artistes and len(artistes) > 0)
    has_spectacle = bool(spectacles and len(spectacles) > 0)
    has_nom_evenement = bool(nom_evenement and nom_evenement.strip())

    # Un événement avec un nom reconnu (Soirée X, Festival X) est valide même sans lieu/artiste/spectacle
    if not has_lieu and not has_artiste and not has_spectacle and not has_nom_evenement:
        return ArtifactDetection(
            is_artifact=True,
            reason="Sans lieu ni artiste ni spectacle ni nom d'événement"
        )

    # === Pas un artifact ===
    return ArtifactDetection(
        is_artifact=False,
        reason="Événement valide"
    )


def is_bidul_sans_evenements(numero: int) -> bool:
    """
    Vérifie si un bidul est un cas particulier sans événements.

    Args:
        numero: Numéro du bidul

    Returns:
        True si le bidul n'a pas d'événements (cas particulier)
    """
    return numero in BIDULS_SANS_EVENEMENTS


def is_artifact(raw_text: str, raw_text_clean: Optional[str] = None,
                lieu_raw: Optional[str] = None,
                artistes: Optional[list] = None,
                spectacles: Optional[list] = None,
                nom_evenement: Optional[str] = None) -> bool:
    """Version simplifiée: retourne True si c'est un artifact."""
    return detect_artifact(raw_text, raw_text_clean, lieu_raw, artistes, spectacles, nom_evenement).is_artifact

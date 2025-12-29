"""
Validateurs pour filtrer les événements avant insertion.

Ces validateurs sont utilisés pour:
1. Rejeter les faux événements (infos, annonces, textes trop courts)
2. Nettoyer les artistes invalides (heures, prix parsés comme artistes)
3. Valider la qualité des données extraites
"""

import re
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ValidationResult:
    """Résultat de validation."""
    is_valid: bool
    reason: Optional[str] = None


# Patterns indiquant un faux événement (info/annonce plutôt qu'événement)
FALSE_EVENT_PATTERNS = [
    (r'\brens\.\s', "Contient 'rens.'"),
    (r'\bcontact\s*:', "Contient 'contact:'"),
    (r'\bwww\.', "Contient URL"),
    (r'\bhttps?://', "Contient URL"),
    (r'\binscription\b', "Contient 'inscription'"),
    (r'\+ d\'infos', "Contient '+ d'infos'"),
    (r'\bdans divers lieux\b', "Contient 'dans divers lieux'"),
    (r'\bplus d\'infos\b', "Contient 'plus d'infos'"),
    (r'\bréservation\s*:', "Contient 'réservation:'"),
]

# Patterns d'artistes invalides
INVALID_ARTISTE_PATTERNS = [
    (r'^\d{1,2}h\d{0,2}$', "Juste une heure"),
    (r',\s*\d{1,2}h', "Contient heure"),
    (r'\d+\s*€', "Contient prix"),
    (r'\bgratuit\b', "Contient 'gratuit'"),
    (r'^[A-Z]{1,2}$', "Trop court (1-2 chars maj)"),
    (r'^\.\.\.*$', "Juste des points"),
    (r'^\d+[Ff]$', "Prix en francs"),
    (r'^\d+h\d*$', "Heure seule"),
    (r'^nc$', "Non communiqué"),
    (r'^\.\s*$', "Point seul"),
]

# Artistes à ignorer (parsés par erreur)
ARTISTE_BLACKLIST = {
    'DJ', 'Dj', 'dj',
    'nc', 'NC', 'n.c', 'N.C',
    '...', '..',
    'BO', 'bo',
}


def validate_event(raw_text: str, lieu_raw: Optional[str], artistes: List[str]) -> ValidationResult:
    """
    Valide un événement avant insertion.

    Args:
        raw_text: Texte brut de l'événement
        lieu_raw: Lieu extrait (peut être None)
        artistes: Liste des artistes extraits

    Returns:
        ValidationResult avec is_valid=True si OK, sinon reason explique le rejet
    """
    # Vérifier longueur minimale
    if not raw_text or len(raw_text.strip()) < 15:
        return ValidationResult(False, f"raw_text trop court ({len(raw_text or '')} chars)")

    # Vérifier patterns de faux événements
    raw_lower = raw_text.lower()
    for pattern, reason in FALSE_EVENT_PATTERNS:
        if re.search(pattern, raw_lower, re.IGNORECASE):
            return ValidationResult(False, reason)

    # Vérifier qu'il y a au moins un lieu OU un artiste valide
    has_lieu = bool(lieu_raw and lieu_raw.strip())
    has_valid_artiste = any(validate_artiste(a).is_valid for a in artistes) if artistes else False

    if not has_lieu and not has_valid_artiste:
        return ValidationResult(False, "Ni lieu ni artiste valide")

    return ValidationResult(True)


def validate_artiste(artiste: str) -> ValidationResult:
    """
    Valide un nom d'artiste.

    Args:
        artiste: Nom de l'artiste à valider

    Returns:
        ValidationResult avec is_valid=True si OK
    """
    if not artiste:
        return ValidationResult(False, "Vide")

    artiste_stripped = artiste.strip()

    if len(artiste_stripped) < 2:
        return ValidationResult(False, "Trop court")

    # Vérifier blacklist
    if artiste_stripped in ARTISTE_BLACKLIST:
        return ValidationResult(False, f"Blacklisté: {artiste_stripped}")

    # Vérifier patterns invalides
    for pattern, reason in INVALID_ARTISTE_PATTERNS:
        if re.search(pattern, artiste_stripped, re.IGNORECASE):
            return ValidationResult(False, reason)

    return ValidationResult(True)


def clean_artiste(artiste: str) -> Optional[str]:
    """
    Nettoie un nom d'artiste. Retourne None si invalide.

    Args:
        artiste: Nom de l'artiste à nettoyer

    Returns:
        Nom nettoyé ou None si invalide
    """
    if not validate_artiste(artiste).is_valid:
        return None

    # Nettoyer espaces
    cleaned = ' '.join(artiste.split())

    # Supprimer trailing ponctuation
    cleaned = cleaned.rstrip('.,;:')

    return cleaned if len(cleaned) >= 2 else None


def validate_lieu(lieu: str) -> ValidationResult:
    """
    Valide un nom de lieu.

    Args:
        lieu: Nom du lieu à valider

    Returns:
        ValidationResult avec is_valid=True si OK
    """
    if not lieu:
        return ValidationResult(False, "Vide")

    lieu_stripped = lieu.strip()

    if len(lieu_stripped) < 3:
        return ValidationResult(False, "Trop court")

    # Patterns invalides pour les lieux
    invalid_patterns = [
        (r'^Scène ouverte', "Scène ouverte n'est pas un lieu"),
        (r'^\d{1,2}h', "Commence par une heure"),
        (r'^à\s+\d{1,2}h', "Commence par 'à Xh'"),
        (r'^dans\s+divers', "Dans divers lieux"),
    ]

    for pattern, reason in invalid_patterns:
        if re.search(pattern, lieu_stripped, re.IGNORECASE):
            return ValidationResult(False, reason)

    return ValidationResult(True)


def is_false_event_text(text: str) -> bool:
    """
    Vérifie si le texte ressemble à une info/annonce plutôt qu'un événement.

    Args:
        text: Texte à vérifier

    Returns:
        True si c'est probablement un faux événement
    """
    if not text:
        return True

    text_lower = text.lower()

    # Patterns caractéristiques d'infos/annonces
    for pattern, _ in FALSE_EVENT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True

    # Texte trop court
    if len(text.strip()) < 15:
        return True

    return False


def extract_valid_artistes(artistes: List[str]) -> List[str]:
    """
    Filtre une liste d'artistes pour ne garder que les valides.

    Args:
        artistes: Liste d'artistes à filtrer

    Returns:
        Liste des artistes valides uniquement
    """
    valid = []
    for artiste in artistes:
        cleaned = clean_artiste(artiste)
        if cleaned:
            valid.append(cleaned)
    return valid

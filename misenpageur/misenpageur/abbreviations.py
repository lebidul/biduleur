# misenpageur/misenpageur/abbreviations.py
# -*- coding: utf-8 -*-
"""
Module de gestion des abréviations pour réduire la longueur du texte
avant le calcul de la taille de police optimale.

Fonctionnalités :
- Chargement depuis abbreviations.yml
- Remplacement insensible à la casse
- Préservation de la casse d'origine (MAJUSCULE, Capitalisé, minuscule)
"""

import os
import re
import logging
import yaml
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

log = logging.getLogger(__name__)

# Chemin vers le fichier YAML des abréviations
_ABBREVIATIONS_YAML = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),  # misenpageur/
    "abbreviations.yml"
)


@dataclass
class Abbreviation:
    """Représente une abréviation avec ses métadonnées."""
    key: str  # Identifiant unique
    original: str  # Texte à remplacer
    replacement: str  # Texte de remplacement
    description: str  # Description pour l'UI
    enabled: bool = False  # Activé par défaut?


@dataclass
class AbbreviationsConfig:
    """Configuration des abréviations."""
    abbreviations: Dict[str, Abbreviation] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "AbbreviationsConfig":
        """Crée une config depuis un dictionnaire YAML."""
        abbrevs = {}
        if not data:
            return cls(abbreviations=abbrevs)

        for key, value in data.items():
            if isinstance(value, dict):
                abbrevs[key] = Abbreviation(
                    key=key,
                    original=value.get("original", key),
                    replacement=value.get("replacement", ""),
                    description=value.get("description", f"{key}"),
                    enabled=value.get("enabled", False)
                )
        return cls(abbreviations=abbrevs)

    def to_dict(self) -> dict:
        """Exporte la config vers un dictionnaire pour YAML."""
        return {
            key: {
                "original": abbr.original,
                "replacement": abbr.replacement,
                "description": abbr.description,
                "enabled": abbr.enabled
            }
            for key, abbr in self.abbreviations.items()
        }

    def get_enabled(self) -> List[Abbreviation]:
        """Retourne uniquement les abréviations activées."""
        return [a for a in self.abbreviations.values() if a.enabled]


# =============================================================================
# CHARGEMENT DEPUIS FICHIER YAML
# =============================================================================

def load_abbreviations_from_yaml(yaml_path: str = None) -> dict:
    """
    Charge les abréviations depuis un fichier YAML.

    Args:
        yaml_path: Chemin vers le fichier YAML (par défaut: abbreviations.yml)

    Returns:
        Dictionnaire des abréviations
    """
    if yaml_path is None:
        yaml_path = _ABBREVIATIONS_YAML

    log.info(f"Tentative de chargement des abréviations depuis: {yaml_path}")

    try:
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # Normaliser tous les champs "original" en NFC pour uniformiser les accents
            for key, value in data.items():
                if isinstance(value, dict) and 'original' in value:
                    value['original'] = unicodedata.normalize('NFC', value['original'])

            log.info(f"✓ Chargé {len(data)} abréviations depuis {yaml_path}")
            # Log des clés chargées
            if data:
                log.debug(f"  Clés chargées: {', '.join(sorted(data.keys()))}")
            return data
        else:
            log.warning(f"✗ Fichier d'abréviations introuvable: {yaml_path}")
            log.warning(f"  Dossier parent existe: {os.path.exists(os.path.dirname(yaml_path))}")
            # Liste les fichiers du dossier parent pour aider au debug
            parent_dir = os.path.dirname(yaml_path)
            if os.path.exists(parent_dir):
                files = [f for f in os.listdir(parent_dir) if f.endswith('.yml')]
                log.warning(f"  Fichiers YAML dans {parent_dir}: {files}")
            return {}
    except Exception as e:
        log.error(f"✗ Erreur de lecture de {yaml_path}: {e}", exc_info=True)
        return {}


# Cache pour éviter de relire le fichier à chaque appel
_cached_abbreviations = None


def get_default_abbreviations() -> dict:
    """
    Retourne les abréviations par défaut (depuis abbreviations.yml).
    Utilise un cache pour éviter les lectures répétées.
    """
    global _cached_abbreviations
    if _cached_abbreviations is None:
        _cached_abbreviations = load_abbreviations_from_yaml()
    return _cached_abbreviations


def get_default_config() -> AbbreviationsConfig:
    """Retourne la configuration par défaut des abréviations."""
    return AbbreviationsConfig.from_dict(get_default_abbreviations())


def reload_abbreviations():
    """Force le rechargement des abréviations depuis le fichier YAML."""
    global _cached_abbreviations
    _cached_abbreviations = None
    return get_default_abbreviations()


# Constante pour compatibilité avec le code existant
# Chargé dynamiquement depuis le YAML
DEFAULT_ABBREVIATIONS = None


def _ensure_loaded():
    """S'assure que DEFAULT_ABBREVIATIONS est chargé."""
    global DEFAULT_ABBREVIATIONS
    if DEFAULT_ABBREVIATIONS is None:
        DEFAULT_ABBREVIATIONS = get_default_abbreviations()
    return DEFAULT_ABBREVIATIONS


# =============================================================================
# LOGIQUE DE REMPLACEMENT AVEC PRÉSERVATION DE CASSE
# =============================================================================

def _preserve_case(original: str, replacement: str) -> str:
    """
    Applique la casse de l'original au remplacement.

    Exemples:
        - "SAINTE" -> "STE"
        - "Sainte" -> "Ste"
        - "sainte" -> "ste"
        - "SaInTe" -> "Ste" (mixed -> Title case)
        - "Centre Culturel" -> "CC" (Title Case multi-mots -> Upper)
    """
    if not original or not replacement:
        return replacement

    # Tout en majuscules
    if original.isupper():
        return replacement.upper()

    # Tout en minuscules
    if original.islower():
        return replacement.lower()

    # Title Case (chaque mot commence par une majuscule)
    words = original.split()
    if len(words) > 1 and all(w[0].isupper() for w in words if w):
        return replacement.upper()

    # Première lettre majuscule (Title case simple)
    if original[0].isupper():
        return replacement.capitalize()

    # Cas mixte ou autre
    return replacement.capitalize()


def _create_replacement_pattern(original: str) -> re.Pattern:
    """
    Crée un pattern regex pour le remplacement insensible à la casse.
    Utilise des word boundaries pour éviter les remplacements partiels.
    Normalise l'Unicode pour gérer les accents correctement.
    """
    # Normaliser en NFC (forme composée) pour uniformiser les accents
    normalized = unicodedata.normalize('NFC', original)
    escaped = re.escape(normalized)
    return re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)


def apply_abbreviations(text: str, abbreviations: List[Abbreviation]) -> str:
    """
    Applique les abréviations au texte avec préservation de la casse.

    Args:
        text: Le texte à traiter
        abbreviations: Liste des abréviations activées

    Returns:
        Le texte avec les remplacements appliqués
    """
    if not text or not abbreviations:
        return text

    result = text

    # Trier par longueur décroissante (expressions longues d'abord)
    sorted_abbrevs = sorted(abbreviations, key=lambda a: len(a.original), reverse=True)

    for abbr in sorted_abbrevs:
        pattern = _create_replacement_pattern(abbr.original)

        def replacer(match):
            matched_text = match.group(0)
            return _preserve_case(matched_text, abbr.replacement)

        result = pattern.sub(replacer, result)

    return result


def apply_abbreviations_to_paragraphs(
        paragraphs: List[str],
        abbreviations: List[Abbreviation],
        nobr_expressions: List[str] = None
) -> Tuple[List[str], Dict[str, int]]:
    """
    Applique les abréviations à une liste de paragraphes.

    Args:
        paragraphs: Liste des paragraphes HTML
        abbreviations: Liste des abréviations activées
        nobr_expressions: Liste des expressions à protéger (nobr.txt)

    Returns:
        Tuple (paragraphes modifiés, compteur de remplacements par clé)
    """
    if not paragraphs or not abbreviations:
        return paragraphs, {}

    result = []
    replacement_counts = {abbr.key: 0 for abbr in abbreviations}

    # Trier par longueur décroissante
    sorted_abbrevs = sorted(abbreviations, key=lambda a: len(a.original), reverse=True)

    for para in paragraphs:
        # Normaliser le paragraphe en NFC pour uniformiser les accents
        modified = unicodedata.normalize('NFC', para)

        # Protection des expressions nobr
        protected_zones = []
        if nobr_expressions:
            # Créer des placeholders pour chaque expression nobr
            for i, nobr_expr in enumerate(nobr_expressions):
                # Normaliser l'expression nobr aussi
                nobr_normalized = unicodedata.normalize('NFC', nobr_expr)
                placeholder = f"___NOBR_{i}___"

                # Remplacer l'expression nobr par un placeholder (insensible à la casse)
                pattern = re.compile(re.escape(nobr_normalized), re.IGNORECASE)
                matches = pattern.findall(modified)

                if matches:
                    # Sauvegarder les matches originaux (avec leur casse)
                    for match in matches:
                        protected_zones.append((placeholder, match))

                    # Remplacer par le placeholder
                    modified = pattern.sub(placeholder, modified)

        # Appliquer les abréviations (les nobr sont protégés par les placeholders)
        for abbr in sorted_abbrevs:
            pattern = _create_replacement_pattern(abbr.original)

            matches = pattern.findall(modified)
            if matches:
                replacement_counts[abbr.key] += len(matches)

                def replacer(match):
                    matched_text = match.group(0)
                    return _preserve_case(matched_text, abbr.replacement)

                modified = pattern.sub(replacer, modified)

        # Restaurer les expressions nobr protégées
        if protected_zones:
            # Trier par placeholder pour restaurer dans l'ordre inverse
            protected_zones.sort(reverse=True)
            for placeholder, original_text in protected_zones:
                # Restaurer TOUTES les occurrences du placeholder
                modified = modified.replace(placeholder, original_text, 1)

        result.append(modified)

    # Log des remplacements effectués
    total = sum(replacement_counts.values())
    if total > 0:
        log.info(f"Abréviations: {total} remplacement(s) effectué(s)")
        for key, count in replacement_counts.items():
            if count > 0:
                abbr = next((a for a in abbreviations if a.key == key), None)
                if abbr:
                    log.debug(f"  - {abbr.original} → {abbr.replacement}: {count}x")

    if nobr_expressions:
        log.debug(f"  {len(nobr_expressions)} expression(s) nobr protégée(s)")

    return result, replacement_counts
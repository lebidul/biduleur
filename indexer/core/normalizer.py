"""
Normalisation des lieux et villes vers les référentiels.

Matching fuzzy avec gestion des abréviations, préfixes et variantes.
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Chemin par défaut vers la base
DEFAULT_DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'

# Abréviations courantes pour les lieux
LIEU_ABBREVIATIONS = {
    'th.': 'théâtre',
    'th ': 'théâtre ',
    'thé.': 'théâtre',
    'thé ': 'théâtre ',
    'mpt': 'maison pour tous',
    'mais.': 'maison ',
    'mjc': 'mjc',
    'cc ': 'centre culturel ',
    'esp.': 'espace',
    'esp ': 'espace ',
    'méd.': 'médiathèque',
    'méd ': 'médiathèque ',
    'sal.': 'salle',
    'sal ': 'salle ',
    'ab.': 'abbaye',
    'coll.': 'collégiale',
    'chap.': 'chapiteau',
    'st ': 'saint ',
    'st-': 'saint-',
}

# Préfixes à ignorer pour le matching
LIEU_PREFIXES = ['bar ', 'le ', 'la ', 'l\'', 'les ', 'au ', 'à ', 'chez ']


def normalize_text(text: str) -> str:
    """Normalise le texte pour comparaison (minuscules, sans accents)."""
    if not text:
        return ''
    text = text.lower().strip()
    # Retirer accents
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    # Normaliser espaces
    text = re.sub(r'\s+', ' ', text)
    return text


def expand_abbreviations(text: str) -> str:
    """Expand les abréviations courantes."""
    text_lower = text.lower()
    for abbrev, full in LIEU_ABBREVIATIONS.items():
        text_lower = text_lower.replace(abbrev, full)
    return text_lower


def strip_prefixes(text: str) -> str:
    """Retire les préfixes pour matching."""
    text_lower = text.lower().strip()
    for prefix in LIEU_PREFIXES:
        if text_lower.startswith(prefix):
            text_lower = text_lower[len(prefix):]
    return text_lower.strip()


@lru_cache(maxsize=1)
def load_lieu_ref(db_path: str = None) -> dict[int, str]:
    """Charge le référentiel des lieux."""
    import sqlite3
    path = db_path or str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute('SELECT id, nom FROM lieu_ref')
    lieux = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return lieux


@lru_cache(maxsize=1)
def load_ville_ref(db_path: str = None) -> dict[int, str]:
    """Charge le référentiel des villes."""
    import sqlite3
    path = db_path or str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute('SELECT id, nom FROM ville_ref')
    villes = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return villes


def build_lieu_index(lieux_ref: dict[int, str]) -> dict[str, tuple[int, str]]:
    """
    Construit un index de matching pour les lieux.
    Retourne dict: {normalized_variant: (lieu_id, lieu_nom_officiel)}
    """
    index = {}

    for lieu_id, nom in lieux_ref.items():
        # Forme originale normalisée
        norm = normalize_text(nom)
        index[norm] = (lieu_id, nom)

        # Sans préfixes
        stripped = strip_prefixes(nom)
        index[normalize_text(stripped)] = (lieu_id, nom)

        # Avec expansion abréviations
        expanded = expand_abbreviations(nom)
        index[normalize_text(expanded)] = (lieu_id, nom)

    return index


def normalize_lieu(lieu_raw: str, db_path: str = None) -> tuple[Optional[int], Optional[str]]:
    """
    Normalise un nom de lieu extrait vers le référentiel.

    Retourne (lieu_ref_id, lieu_nom_normalise) ou (None, lieu_raw) si non trouvé.

    Exemples:
    - "Th. Paul Scarron" → (173, "Théâtre Paul Scarron")
    - "bar le Lézard" → (252, "Le Lézard")
    - "L'oasis" → (68, "L'Oasis")
    """
    if not lieu_raw:
        return None, None

    path = db_path or str(DEFAULT_DB_PATH)
    lieux_ref = load_lieu_ref(path)
    index = build_lieu_index(lieux_ref)

    # Essayer différentes normalisations
    candidates = [
        normalize_text(lieu_raw),
        normalize_text(strip_prefixes(lieu_raw)),
        normalize_text(expand_abbreviations(lieu_raw)),
        normalize_text(strip_prefixes(expand_abbreviations(lieu_raw))),
    ]

    for candidate in candidates:
        if candidate in index:
            return index[candidate]

    # Matching partiel (le lieu extrait contient le nom de référence ou vice-versa)
    lieu_norm = normalize_text(lieu_raw)
    if not lieu_norm:
        return None, lieu_raw

    for ref_norm, (lieu_id, lieu_nom) in index.items():
        if ref_norm in lieu_norm or lieu_norm in ref_norm:
            # Vérifier que c'est un match significatif (>50% de longueur)
            if len(ref_norm) > 3 and (len(ref_norm) / len(lieu_norm) > 0.5 or len(lieu_norm) / len(ref_norm) > 0.5):
                return (lieu_id, lieu_nom)

    # Non trouvé
    return None, lieu_raw


def normalize_ville(ville_raw: str, db_path: str = None) -> tuple[Optional[int], str]:
    """
    Normalise un nom de ville extrait vers le référentiel.

    Retourne (ville_ref_id, ville_nom_normalise).
    Si ville_raw est vide/None → retourne l'id du Mans.
    """
    path = db_path or str(DEFAULT_DB_PATH)
    villes_ref = load_ville_ref(path)

    # Règle : si ville nulle → Le Mans
    if not ville_raw or not ville_raw.strip():
        # Chercher l'id du Mans
        for ville_id, nom in villes_ref.items():
            if nom.lower() == 'le mans':
                return ville_id, 'Le Mans'
        return None, 'Le Mans'

    # Matching exact normalisé
    ville_norm = normalize_text(ville_raw)

    for ville_id, nom in villes_ref.items():
        if normalize_text(nom) == ville_norm:
            return ville_id, nom

    # Matching partiel
    for ville_id, nom in villes_ref.items():
        ref_norm = normalize_text(nom)
        if ref_norm in ville_norm or ville_norm in ref_norm:
            if len(ref_norm) > 3:
                return ville_id, nom

    # Non trouvé mais pas vide → garder le raw
    return None, ville_raw


def clear_caches():
    """Vide les caches (utile après rechargement de la base)."""
    load_lieu_ref.cache_clear()
    load_ville_ref.cache_clear()


# =============================================================================
# Test
# =============================================================================

if __name__ == '__main__':
    tests_lieux = [
        'Th. Paul Scarron',
        'bar le Lézard',
        'L\'oasis',
        'le barouf',
        'Blue Zinc',
        'MJC Ronceray',
        'L\'Alambik',
        'Le Mans Bowling',
    ]

    print('=== LIEUX ===')
    for lieu in tests_lieux:
        ref_id, normalized = normalize_lieu(lieu)
        status = '[OK]' if ref_id else '[--]'
        print(f'{status} {lieu:25} -> id={ref_id}, nom={normalized}')

    tests_villes = [
        'Le Mans',
        'le mans',
        '',
        None,
        'Allonnes',
        'Saint-Pavace',
        'Arnage',
    ]

    print('\n=== VILLES ===')
    for ville in tests_villes:
        ref_id, normalized = normalize_ville(ville)
        status = '[OK]' if ref_id else '[--]'
        print(f'{status} {str(ville):20} -> id={ref_id}, nom={normalized}')

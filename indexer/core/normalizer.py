"""
Module de normalisation des lieux et artistes.

Source de verite : fichiers CSV dans corpus/
Les CSV sont charges en memoire au demarrage et utilises pour le matching.

Strategie de matching (par ordre de priorite):
1. Match exact (case-sensitive)
2. Match case-insensitive
3. Match par alias exact (case-insensitive)
4. Match par nom normalise (apres transformation)
5. Match par alias normalise

Ce module fournit:
- LieuNormalizer: Normalisation et matching des lieux depuis CSV
- ArtisteNormalizer: Normalisation et matching des artistes depuis CSV
- Fonctions legacy pour compatibilite avec l'existant (normalize_lieu, normalize_ville)
"""

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Chemins
CORPUS_DIR = Path(__file__).parent.parent / 'corpus'
DEFAULT_DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'

# =============================================================================
# Fonctions de normalisation de texte
# =============================================================================

# Abreviations courantes pour les lieux
# IMPORTANT: Les abreviations doivent etre dans l'ordre du plus specifique au moins specifique
# et doivent avoir des espaces/points pour eviter les faux positifs (ex: 'cie ' pas 'cie')
LIEU_ABBREVIATIONS = {
    # Lieux
    'th.': 'theatre',
    'the.': 'theatre',
    'theat.': 'theatre',
    'mpt ': 'maison pour tous ',
    'mais.': 'maison ',
    'mjc ': 'mjc ',  # Garder mjc tel quel, c'est connu
    'cc ': 'centre culturel ',
    'esp.': 'espace',
    'esp ': 'espace ',
    'med.': 'mediatheque',
    'med ': 'mediatheque ',
    'sal.': 'salle',
    'sal ': 'salle ',
    's.': 'salle ',
    'ab.': 'abbaye',
    'coll.': 'collegiale',
    'chap.': 'chapiteau',
    'egl.': 'eglise',
    'pl.': 'place',
    'bd ': 'boulevard ',
    'av.': 'avenue',
    # Geographie
    'st ': 'saint ',
    'st-': 'saint-',
    'ste ': 'sainte ',
    'ste-': 'sainte-',
    # Compagnies - AVEC espace pour eviter faux positifs
    'cie ': 'compagnie ',
    'cie.': 'compagnie ',
    # Musique
    'ch.': 'chanson',
    'ch. fr.': 'chanson francaise',
    'ch.fr.': 'chanson francaise',
    'mus.': 'musique',
    'feat.': 'feat',
    'ft.': 'feat',
    # Ponctuation
    '&': 'et',
    ' / ': ' ',
}

# Prefixes a ignorer pour le matching
LIEU_PREFIXES = ['bar ', 'le ', 'la ', 'l\'', 'les ', 'au ', 'a ', 'chez ', 'du ', 'de la ', 'des ', 'd\'']


def normalize_name(name: str) -> str:
    """
    Normalise un nom pour le matching.

    Transformations appliquees:
    - Lowercase
    - Expansion des abreviations (Th. -> theatre, Cie -> compagnie, etc.)
    - Suppression des accents
    - Normalisation de la ponctuation
    - Suppression des articles en debut
    - Normalisation des espaces

    Exemples:
        "Th. de la Halle au Ble" -> "theatre halle au ble"
        "L'Oasis" -> "oasis"
        "DJ SUPER LUCIEN" -> "dj super lucien"
        "Cie Pieces & Main d'Oeuvre" -> "compagnie pieces et main oeuvre"
    """
    if not name:
        return ""

    s = name.lower()

    # Expand abreviations AVANT de supprimer la ponctuation
    for abbr, full in LIEU_ABBREVIATIONS.items():
        s = s.replace(abbr, full)

    # Supprimer accents
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))

    # Normaliser ponctuation (remplacer par espaces)
    # Le tiret doit etre en fin de classe pour eviter d'etre interprete comme range
    s = re.sub(r"[''\"«»„"",./:;!?(){}—–-]", ' ', s)
    s = s.replace('[', ' ').replace(']', ' ')

    # Supprimer articles en debut
    s = re.sub(r'^(le |la |l |les |un |une |des )', '', s)

    # Normaliser espaces multiples
    s = ' '.join(s.split())

    return s.strip()


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
    """Expand les abreviations courantes."""
    text_lower = text.lower()
    for abbrev, full in LIEU_ABBREVIATIONS.items():
        text_lower = text_lower.replace(abbrev, full)
    return text_lower


def strip_prefixes(text: str) -> str:
    """Retire les prefixes pour matching."""
    text_lower = text.lower().strip()
    for prefix in LIEU_PREFIXES:
        if text_lower.startswith(prefix):
            text_lower = text_lower[len(prefix):]
    return text_lower.strip()


# =============================================================================
# Classes de normalisation basees sur CSV
# =============================================================================

class LieuNormalizer:
    """
    Normalisation et matching des lieux.

    Source: corpus/lieu.csv et corpus/lieu_alias.csv

    Usage:
        normalizer = LieuNormalizer()
        result = normalizer.find_lieu("Th. Paul Scarron")
        # -> ("Theatre Paul Scarron", "Le Mans")
    """

    def __init__(self, corpus_dir: Path = CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self._cache: Dict[str, Optional[tuple[str, str]]] = {}
        self._load_from_csv()

    def _load_from_csv(self):
        """Charge les referentiels depuis les CSV."""

        # Index principal : nom_lower -> {nom, ville, nom_normalise}
        self.lieux: Dict[str, Dict] = {}
        # Index par nom normalise : nom_normalise -> nom
        self.lieux_by_normalise: Dict[str, str] = {}

        lieu_path = self.corpus_dir / 'lieu.csv'
        if lieu_path.exists():
            with open(lieu_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nom = row['nom']
                    ville = row.get('ville', 'Le Mans')
                    nom_norm = row.get('nom_normalise') or normalize_name(nom)

                    self.lieux[nom.lower()] = {
                        'nom': nom,
                        'ville': ville,
                        'nom_normalise': nom_norm
                    }
                    if nom_norm:
                        self.lieux_by_normalise[nom_norm] = nom

            logger.debug(f"Charge {len(self.lieux)} lieux depuis lieu.csv")
        else:
            logger.warning(f"Fichier non trouve: {lieu_path}")

        # Aliases : variante_lower -> nom_canonique
        self.aliases: Dict[str, str] = {}
        # Aliases normalises : variante_normalise -> nom_canonique
        self.aliases_normalise: Dict[str, str] = {}

        alias_path = self.corpus_dir / 'lieu_alias.csv'
        if alias_path.exists():
            with open(alias_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    variante = row['variante']
                    lieu_nom = row['lieu_nom']

                    self.aliases[variante.lower()] = lieu_nom
                    norm = normalize_name(variante)
                    if norm:
                        self.aliases_normalise[norm] = lieu_nom

            logger.debug(f"Charge {len(self.aliases)} aliases depuis lieu_alias.csv")
        else:
            logger.debug(f"Fichier non trouve (optionnel): {alias_path}")

    def find_lieu(self, lieu_raw: str) -> Optional[tuple[str, str]]:
        """
        Trouve le lieu correspondant.

        Args:
            lieu_raw: Nom du lieu tel qu'extrait

        Returns:
            (nom_canonique, ville) ou None si non trouve
        """
        if not lieu_raw or not lieu_raw.strip():
            return None

        # Verifier le cache
        cache_key = lieu_raw.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._match_lieu(lieu_raw.strip())
        self._cache[cache_key] = result
        return result

    def _match_lieu(self, lieu_raw: str) -> Optional[tuple[str, str]]:
        """Logique de matching par ordre de priorite."""

        lieu_lower = lieu_raw.lower()
        lieu_norm = normalize_name(lieu_raw)

        # 1. Match exact (case-insensitive) dans lieux
        if lieu_lower in self.lieux:
            data = self.lieux[lieu_lower]
            return (data['nom'], data['ville'])

        # 2. Match par alias exact (case-insensitive)
        if lieu_lower in self.aliases:
            nom_canonique = self.aliases[lieu_lower]
            if nom_canonique.lower() in self.lieux:
                data = self.lieux[nom_canonique.lower()]
                return (data['nom'], data['ville'])

        # 3. Match par nom normalise dans lieux
        if lieu_norm and lieu_norm in self.lieux_by_normalise:
            nom_canonique = self.lieux_by_normalise[lieu_norm]
            if nom_canonique.lower() in self.lieux:
                data = self.lieux[nom_canonique.lower()]
                return (data['nom'], data['ville'])

        # 4. Match par alias normalise
        if lieu_norm and lieu_norm in self.aliases_normalise:
            nom_canonique = self.aliases_normalise[lieu_norm]
            if nom_canonique.lower() in self.lieux:
                data = self.lieux[nom_canonique.lower()]
                return (data['nom'], data['ville'])

        return None

    def get_all_lieux(self) -> List[Dict]:
        """Retourne tous les lieux sous forme de liste."""
        return list(self.lieux.values())

    def reload(self):
        """Recharge les donnees depuis les CSV."""
        self._cache = {}
        self._load_from_csv()


class ArtisteNormalizer:
    """
    Normalisation et matching des artistes.

    Source: corpus/artiste.csv et corpus/artiste_alias.csv

    Usage:
        normalizer = ArtisteNormalizer()
        result = normalizer.find_artiste("Dj SUPER LUCIEN")
        # -> ("DJ SUPER LUCIEN", "dj")
    """

    def __init__(self, corpus_dir: Path = CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self._cache: Dict[str, Optional[tuple[str, str]]] = {}
        self._load_from_csv()

    def _load_from_csv(self):
        """Charge les referentiels depuis les CSV."""

        self.artistes: Dict[str, Dict] = {}
        self.artistes_by_normalise: Dict[str, str] = {}

        artiste_path = self.corpus_dir / 'artiste.csv'
        if artiste_path.exists():
            with open(artiste_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nom = row['nom_canonique']
                    nom_norm = row.get('nom_normalise') or normalize_name(nom)
                    style = row.get('style', '')

                    self.artistes[nom.lower()] = {
                        'nom': nom,
                        'nom_normalise': nom_norm,
                        'style': style
                    }
                    if nom_norm:
                        self.artistes_by_normalise[nom_norm] = nom

            logger.debug(f"Charge {len(self.artistes)} artistes depuis artiste.csv")
        else:
            logger.debug(f"Fichier non trouve (optionnel): {artiste_path}")

        self.aliases: Dict[str, str] = {}
        self.aliases_normalise: Dict[str, str] = {}

        alias_path = self.corpus_dir / 'artiste_alias.csv'
        if alias_path.exists():
            with open(alias_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    variante = row['variante']
                    artiste_nom = row['artiste_nom']

                    self.aliases[variante.lower()] = artiste_nom
                    norm = normalize_name(variante)
                    if norm:
                        self.aliases_normalise[norm] = artiste_nom

            logger.debug(f"Charge {len(self.aliases)} aliases depuis artiste_alias.csv")

    def find_artiste(self, artiste_raw: str) -> Optional[tuple[str, str]]:
        """
        Trouve l'artiste correspondant.

        Args:
            artiste_raw: Nom de l'artiste tel qu'extrait

        Returns:
            (nom_canonique, style) ou None si non trouve
        """
        if not artiste_raw or not artiste_raw.strip():
            return None

        cache_key = artiste_raw.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._match_artiste(artiste_raw.strip())
        self._cache[cache_key] = result
        return result

    def _match_artiste(self, artiste_raw: str) -> Optional[tuple[str, str]]:
        """Logique de matching par ordre de priorite."""

        artiste_lower = artiste_raw.lower()
        artiste_norm = normalize_name(artiste_raw)

        # 1. Match exact (case-insensitive)
        if artiste_lower in self.artistes:
            data = self.artistes[artiste_lower]
            return (data['nom'], data['style'])

        # 2. Match par alias exact
        if artiste_lower in self.aliases:
            nom_canonique = self.aliases[artiste_lower]
            if nom_canonique.lower() in self.artistes:
                data = self.artistes[nom_canonique.lower()]
                return (data['nom'], data['style'])

        # 3. Match par nom normalise
        if artiste_norm and artiste_norm in self.artistes_by_normalise:
            nom_canonique = self.artistes_by_normalise[artiste_norm]
            if nom_canonique.lower() in self.artistes:
                data = self.artistes[nom_canonique.lower()]
                return (data['nom'], data['style'])

        # 4. Match par alias normalise
        if artiste_norm and artiste_norm in self.aliases_normalise:
            nom_canonique = self.aliases_normalise[artiste_norm]
            if nom_canonique.lower() in self.artistes:
                data = self.artistes[nom_canonique.lower()]
                return (data['nom'], data['style'])

        return None

    def get_all_artistes(self) -> List[Dict]:
        """Retourne tous les artistes sous forme de liste."""
        return list(self.artistes.values())

    def reload(self):
        """Recharge les donnees depuis les CSV."""
        self._cache = {}
        self._load_from_csv()


# =============================================================================
# Instances singleton et fonctions utilitaires
# =============================================================================

_lieu_normalizer: Optional[LieuNormalizer] = None
_artiste_normalizer: Optional[ArtisteNormalizer] = None


def get_lieu_normalizer() -> LieuNormalizer:
    """Retourne l'instance singleton du normaliseur de lieux."""
    global _lieu_normalizer
    if _lieu_normalizer is None:
        _lieu_normalizer = LieuNormalizer()
    return _lieu_normalizer


def get_artiste_normalizer() -> ArtisteNormalizer:
    """Retourne l'instance singleton du normaliseur d'artistes."""
    global _artiste_normalizer
    if _artiste_normalizer is None:
        _artiste_normalizer = ArtisteNormalizer()
    return _artiste_normalizer


def reload_normalizers():
    """Recharge tous les normaliseurs depuis les CSV."""
    global _lieu_normalizer, _artiste_normalizer
    if _lieu_normalizer:
        _lieu_normalizer.reload()
    if _artiste_normalizer:
        _artiste_normalizer.reload()


# =============================================================================
# Fonctions de matching avec DB (incluant aliases)
# =============================================================================

@lru_cache(maxsize=1)
def load_lieu_index_with_aliases(db_path: str = None) -> dict[str, tuple[int, str]]:
    """
    Charge un index de matching pour les lieux (incluant les alias).
    Retourne dict: {nom_lower: (lieu_id, nom_canonique)}
    """
    import sqlite3
    path = db_path or str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    index = {}

    # Charger lieu_ref (actifs uniquement)
    cur.execute('SELECT id, nom FROM lieu_ref WHERE actif = 1')
    for lieu_id, nom in cur.fetchall():
        index[nom.lower()] = (lieu_id, nom)
        # Ajouter forme normalisee
        norm = normalize_name(nom)
        if norm:
            index[norm] = (lieu_id, nom)

    # Charger lieu_alias -> pointer vers lieu_ref
    cur.execute('''
        SELECT la.variante, lr.id, lr.nom
        FROM lieu_alias la
        JOIN lieu_ref lr ON la.lieu_nom = lr.nom AND lr.actif = 1
    ''')
    for variante, lieu_id, nom_canonique in cur.fetchall():
        index[variante.lower()] = (lieu_id, nom_canonique)
        norm = normalize_name(variante)
        if norm:
            index[norm] = (lieu_id, nom_canonique)

    conn.close()
    return index


@lru_cache(maxsize=1)
def load_artiste_index_with_aliases(db_path: str = None) -> dict[str, tuple[int, str]]:
    """
    Charge un index de matching pour les artistes (incluant les alias).
    Retourne dict: {nom_lower: (artiste_id, nom_canonique)}
    """
    import sqlite3
    path = db_path or str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    index = {}

    # Charger artiste_ref (actifs uniquement)
    cur.execute('SELECT id, nom FROM artiste_ref WHERE actif = 1')
    for artiste_id, nom in cur.fetchall():
        index[nom.lower()] = (artiste_id, nom)
        norm = normalize_name(nom)
        if norm:
            index[norm] = (artiste_id, nom)

    # Charger artiste_alias -> pointer vers artiste_ref
    cur.execute('''
        SELECT aa.variante, ar.id, ar.nom
        FROM artiste_alias aa
        JOIN artiste_ref ar ON aa.artiste_nom = ar.nom AND ar.actif = 1
    ''')
    for variante, artiste_id, nom_canonique in cur.fetchall():
        index[variante.lower()] = (artiste_id, nom_canonique)
        norm = normalize_name(variante)
        if norm:
            index[norm] = (artiste_id, nom_canonique)

    conn.close()
    return index


def find_lieu_ref_id(lieu_raw: str, db_path: str = None) -> tuple[Optional[int], Optional[str]]:
    """
    Trouve l'ID de lieu_ref pour un lieu brut (via matching avec aliases).

    Retourne (lieu_ref_id, nom_canonique) ou (None, None) si non trouve.
    """
    if not lieu_raw or not lieu_raw.strip():
        return None, None

    index = load_lieu_index_with_aliases(db_path)

    # Match exact (case-insensitive)
    key = lieu_raw.lower().strip()
    if key in index:
        return index[key]

    # Match par nom normalise
    norm = normalize_name(lieu_raw)
    if norm and norm in index:
        return index[norm]

    # Match partiel (le lieu brut contient le nom de reference ou vice-versa)
    if norm and len(norm) > 4:
        for ref_key, (lieu_id, nom_canonique) in index.items():
            if len(ref_key) > 4:
                if ref_key in norm or norm in ref_key:
                    ratio = min(len(ref_key), len(norm)) / max(len(ref_key), len(norm))
                    if ratio > 0.5:
                        return (lieu_id, nom_canonique)

    return None, None


def find_artiste_ref_id(artiste_raw: str, db_path: str = None) -> tuple[Optional[int], Optional[str]]:
    """
    Trouve l'ID de artiste_ref pour un artiste brut (via matching avec aliases).

    Retourne (artiste_ref_id, nom_canonique) ou (None, None) si non trouve.
    """
    if not artiste_raw or not artiste_raw.strip():
        return None, None

    index = load_artiste_index_with_aliases(db_path)

    # Match exact (case-insensitive)
    key = artiste_raw.lower().strip()
    if key in index:
        return index[key]

    # Match par nom normalise
    norm = normalize_name(artiste_raw)
    if norm and norm in index:
        return index[norm]

    # Match partiel plus strict pour artistes
    if norm and len(norm) > 5:
        for ref_key, (artiste_id, nom_canonique) in index.items():
            if len(ref_key) > 5:
                if ref_key in norm or norm in ref_key:
                    ratio = min(len(ref_key), len(norm)) / max(len(ref_key), len(norm))
                    if ratio > 0.7:  # Plus strict
                        return (artiste_id, nom_canonique)

    return None, None


# =============================================================================
# Fonctions legacy (compatibilite avec l'existant)
# =============================================================================

@lru_cache(maxsize=1)
def load_lieu_ref(db_path: str = None) -> dict[int, str]:
    """Charge le referentiel des lieux depuis la DB."""
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
    """Charge le referentiel des villes depuis la DB."""
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
        # Forme originale normalisee
        norm = normalize_text(nom)
        index[norm] = (lieu_id, nom)

        # Sans prefixes
        stripped = strip_prefixes(nom)
        index[normalize_text(stripped)] = (lieu_id, nom)

        # Avec expansion abreviations
        expanded = expand_abbreviations(nom)
        index[normalize_text(expanded)] = (lieu_id, nom)

    return index


def normalize_lieu(lieu_raw: str, db_path: str = None) -> tuple[Optional[int], Optional[str]]:
    """
    Normalise un nom de lieu extrait vers le referentiel.

    Retourne (lieu_ref_id, lieu_nom_normalise) ou (None, lieu_raw) si non trouve.

    Exemples:
    - "Th. Paul Scarron" -> (173, "Theatre Paul Scarron")
    - "bar le Lezard" -> (252, "Le Lezard")
    - "L'oasis" -> (68, "L'Oasis")
    """
    if not lieu_raw:
        return None, None

    path = db_path or str(DEFAULT_DB_PATH)
    lieux_ref = load_lieu_ref(path)
    index = build_lieu_index(lieux_ref)

    # Essayer differentes normalisations
    candidates = [
        normalize_text(lieu_raw),
        normalize_text(strip_prefixes(lieu_raw)),
        normalize_text(expand_abbreviations(lieu_raw)),
        normalize_text(strip_prefixes(expand_abbreviations(lieu_raw))),
    ]

    for candidate in candidates:
        if candidate in index:
            return index[candidate]

    # Matching partiel (le lieu extrait contient le nom de reference ou vice-versa)
    lieu_norm = normalize_text(lieu_raw)
    if not lieu_norm:
        return None, lieu_raw

    for ref_norm, (lieu_id, lieu_nom) in index.items():
        if ref_norm in lieu_norm or lieu_norm in ref_norm:
            # Verifier que c'est un match significatif (>50% de longueur)
            if len(ref_norm) > 3 and (len(ref_norm) / len(lieu_norm) > 0.5 or len(lieu_norm) / len(ref_norm) > 0.5):
                return (lieu_id, lieu_nom)

    # Non trouve
    return None, lieu_raw


def normalize_ville(ville_raw: str, db_path: str = None) -> tuple[Optional[int], str]:
    """
    Normalise un nom de ville extrait vers le referentiel.

    Retourne (ville_ref_id, ville_nom_normalise).
    Si ville_raw est vide/None -> retourne l'id du Mans.
    """
    path = db_path or str(DEFAULT_DB_PATH)
    villes_ref = load_ville_ref(path)

    # Regle : si ville nulle -> Le Mans
    if not ville_raw or not ville_raw.strip():
        # Chercher l'id du Mans
        for ville_id, nom in villes_ref.items():
            if nom.lower() == 'le mans':
                return ville_id, 'Le Mans'
        return None, 'Le Mans'

    # Matching exact normalise
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

    # Non trouve mais pas vide -> garder le raw
    return None, ville_raw


def clear_caches():
    """Vide les caches (utile apres rechargement de la base)."""
    load_lieu_ref.cache_clear()
    load_ville_ref.cache_clear()
    load_lieu_index_with_aliases.cache_clear()
    load_artiste_index_with_aliases.cache_clear()
    reload_normalizers()


# =============================================================================
# Test
# =============================================================================

if __name__ == '__main__':
    print("=== TEST NORMALISATION ===\n")

    # Test nouveau systeme CSV
    print("--- LieuNormalizer (CSV) ---")
    lieu_norm = get_lieu_normalizer()
    print(f"Lieux charges: {len(lieu_norm.lieux)}")
    print(f"Aliases charges: {len(lieu_norm.aliases)}")

    tests_lieux = [
        'Th. Paul Scarron',
        'bar le Lezard',
        "L'oasis",
        'le barouf',
        'Blue Zinc',
        'MJC Ronceray',
        "L'Alambik",
        'Le Mans Bowling',
        'S.Jean Carmet',
        'La Peniche Excelsior',
    ]

    for lieu in tests_lieux:
        result = lieu_norm.find_lieu(lieu)
        status = '[OK]' if result else '[--]'
        if result:
            print(f'{status} {lieu:25} -> {result[0]} ({result[1]})')
        else:
            print(f'{status} {lieu:25} -> non trouve')

    # Test artistes
    print("\n--- ArtisteNormalizer (CSV) ---")
    artiste_norm = get_artiste_normalizer()
    print(f"Artistes charges: {len(artiste_norm.artistes)}")
    print(f"Aliases charges: {len(artiste_norm.aliases)}")

    tests_artistes = [
        'DJ SUPER LUCIEN',
        'Dj Super Lucien',
        'AZURYTE',
        'azuryte',
    ]

    for artiste in tests_artistes:
        result = artiste_norm.find_artiste(artiste)
        status = '[OK]' if result else '[--]'
        if result:
            print(f'{status} {artiste:25} -> {result[0]} (style: {result[1] or "-"})')
        else:
            print(f'{status} {artiste:25} -> non trouve')

    # Test legacy (DB)
    print("\n--- Legacy (DB) ---")
    for lieu in tests_lieux[:5]:
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

    print('\n--- Villes (legacy) ---')
    for ville in tests_villes:
        ref_id, normalized = normalize_ville(ville)
        status = '[OK]' if ref_id else '[--]'
        print(f'{status} {str(ville):20} -> id={ref_id}, nom={normalized}')

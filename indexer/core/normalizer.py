"""
Module de normalisation des lieux, villes, artistes et styles.

Normalisation automatique (sans CSV):
- Case insensitive
- Tirets/espaces interchangeables
- Accents insensitifs
- Apostrophes normalisées
- Abréviations expandées (th., esp., st., ste., s/)

Les fichiers CSV d'aliases sont utilisés uniquement pour les cas spéciaux
non couverts par les règles automatiques.

Stratégie de matching (par ordre de priorité):
1. Match exact (case-sensitive)
2. Match case-insensitive
3. Match normalisé automatique (sans accents, tirets=espaces, abréviations)
4. Match par alias CSV (cas spéciaux)
"""

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

# Chemins
CORPUS_DIR = Path(__file__).parent.parent / 'corpus'
DEFAULT_DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


# =============================================================================
# Abréviations et règles de transformation
# =============================================================================

# Abréviations à expander AVANT normalisation
# IMPORTANT: Ordre du plus spécifique au moins spécifique
ABBREVIATIONS = {
    # Théâtre
    'thé. ': 'théâtre ',
    'théat. ': 'théâtre ',
    'th. ': 'théâtre ',
    'th ': 'théâtre ',
    # Espace
    'esp. ': 'espace ',
    'esp ': 'espace ',
    # Saints
    'ste. ': 'sainte ',
    'ste ': 'sainte ',
    'ste-': 'sainte-',
    'st. ': 'saint ',
    'st ': 'saint ',
    'st-': 'saint-',
    # Sur (géographie)
    ' s/ ': '-sur-',
    's/': '-sur-',
    # Compagnies
    'cie. ': 'compagnie ',
    'cie ': 'compagnie ',
    # Lieux
    'mpt ': 'maison pour tous ',
    'mjc ': 'mjc ',  # Garder tel quel
    'cc ': 'centre culturel ',
    'méd. ': 'médiathèque ',
    'med. ': 'médiathèque ',
    'sal. ': 'salle ',
    's. ': 'salle ',
    'pl. ': 'place ',
    'bd ': 'boulevard ',
    'av. ': 'avenue ',
    'ab. ': 'abbaye ',
    'coll. ': 'collégiale ',
    'chap. ': 'chapiteau ',
    'égl. ': 'église ',
    'egl. ': 'église ',
    # Musique/Styles
    'ch. fr.': 'chanson française',
    'ch.fr.': 'chanson française',
    'ch. ': 'chanson ',
    'mus. ': 'musique ',
    'feat. ': 'feat ',
    'ft. ': 'feat ',
    # Ponctuation
    '&': ' et ',
    ' / ': ' ',
}

# Préfixes à ignorer pour le matching
PREFIXES_TO_STRIP = ['bar ', 'le ', 'la ', "l'", "l'", 'les ', 'au ', 'a ', 'chez ', 'du ', 'de la ', 'des ', "d'", "d'"]


# =============================================================================
# Fonctions de normalisation de texte
# =============================================================================

def remove_accents(text: str) -> str:
    """
    Supprime les accents d'un texte.

    Exemple: "Chemiré-le-Gaudin" -> "Chemire-le-Gaudin"
    """
    if not text:
        return ""
    # NFD décompose les caractères accentués (é → e + accent)
    # On filtre ensuite les "combining characters" (les accents)
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if not unicodedata.combining(c))


def normalize_separators(text: str) -> str:
    """
    Normalise les séparateurs (tirets, espaces, apostrophes).
    Tous deviennent des espaces pour comparaison.

    Exemple: "Saint-Mars-la-Brière" -> "Saint Mars la Brière"
    """
    if not text:
        return ""
    # Remplacer tirets et apostrophes par des espaces
    # Inclut: - – — ' ` ' ' (U+2018 LEFT, U+2019 RIGHT SINGLE QUOTATION MARK)
    s = re.sub(r"[-–—'`\u2018\u2019]", ' ', text)
    # Normaliser les espaces multiples
    s = ' '.join(s.split())
    return s


def expand_abbreviations(text: str) -> str:
    """
    Expande les abréviations courantes.

    Exemple: "Th. Paul Scarron" -> "théâtre Paul Scarron"
    """
    if not text:
        return ""
    s = text.lower()

    # Appliquer les abréviations (ordre du dict préservé en Python 3.7+)
    for abbr, full in ABBREVIATIONS.items():
        s = s.replace(abbr, full)

    return s


def strip_prefixes(text: str) -> str:
    """
    Retire les préfixes courants (articles, etc.) pour le matching.

    Exemple: "Le Barouf" -> "Barouf"
    """
    if not text:
        return ""
    s = text.lower().strip()
    for prefix in PREFIXES_TO_STRIP:
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s.strip()


def normalize_for_matching(text: str) -> str:
    """
    Normalise un texte pour le matching automatique.

    Applique dans l'ordre:
    1. Lowercase
    2. Expansion des abréviations
    3. Suppression des accents
    4. Normalisation des séparateurs (tirets/espaces/apostrophes → espaces)
    5. Normalisation des espaces multiples

    Exemples:
        "Th. Paul Scarron" → "theatre paul scarron"
        "AZURYTE" → "azuryte"
        "Auvers le-Hamon" → "auvers le hamon"
        "Chemiré-le-Gaudin" → "chemire le gaudin"
        "L'Écluse" → "l ecluse"
        "St Pavace" → "saint pavace"
        "Moncé s/Loir" → "monce sur loir"
    """
    if not text:
        return ""

    # 1. Lowercase
    s = text.lower().strip()

    # 2. Expansion des abréviations
    s = expand_abbreviations(s)

    # 3. Suppression des accents
    s = remove_accents(s)

    # 4. Normalisation des séparateurs
    s = normalize_separators(s)

    # 5. Normalisation des espaces
    s = ' '.join(s.split())

    return s


def normalize_name(name: str) -> str:
    """
    Alias pour normalize_for_matching (compatibilité).
    """
    return normalize_for_matching(name)


def normalize_text(text: str) -> str:
    """
    Normalise le texte pour comparaison (compatibilité legacy).
    """
    return normalize_for_matching(text)


# =============================================================================
# Classes de normalisation basées sur CSV
# =============================================================================

class LieuNormalizer:
    """
    Normalisation et matching des lieux.

    Source: corpus/lieu.csv et corpus/lieu_alias.csv

    Stratégie de matching (par ordre de priorité):
    1. Match exact case-insensitive dans les lieux
    2. Match normalisé automatique (accents, tirets, abréviations)
    3. Match par alias CSV exact
    4. Match par alias CSV normalisé
    5. Match sans préfixes (le, la, l', etc.)
    """

    def __init__(self, corpus_dir: Path = CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self._cache: Dict[str, Optional[Tuple[str, str]]] = {}
        self._load_from_csv()

    def _load_from_csv(self):
        """Charge les référentiels depuis les CSV."""

        # Index principal: nom_lower -> {nom, ville}
        self.lieux: Dict[str, Dict] = {}

        # Index par nom normalisé: nom_normalise -> nom_original
        self.lieux_by_normalized: Dict[str, str] = {}

        # Index sans préfixes: nom_sans_prefix -> nom_original
        self.lieux_by_stripped: Dict[str, str] = {}

        lieu_path = self.corpus_dir / 'lieu.csv'
        if lieu_path.exists():
            with open(lieu_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nom = row['nom'].strip()
                    ville = row.get('ville', 'Le Mans').strip()

                    # Stocker avec clé lowercase
                    self.lieux[nom.lower()] = {'nom': nom, 'ville': ville}

                    # Index normalisé pour matching automatique
                    nom_norm = normalize_for_matching(nom)
                    if nom_norm and nom_norm not in self.lieux_by_normalized:
                        self.lieux_by_normalized[nom_norm] = nom

                    # Index sans préfixes
                    nom_stripped = strip_prefixes(nom)
                    nom_stripped_norm = normalize_for_matching(nom_stripped)
                    if nom_stripped_norm and nom_stripped_norm not in self.lieux_by_stripped:
                        self.lieux_by_stripped[nom_stripped_norm] = nom

            logger.debug(f"Chargé {len(self.lieux)} lieux depuis lieu.csv")
        else:
            logger.warning(f"Fichier non trouvé: {lieu_path}")

        # Aliases CSV (cas spéciaux uniquement)
        self.aliases: Dict[str, str] = {}  # variante_lower -> nom_canonique
        self.aliases_normalized: Dict[str, str] = {}  # variante_norm -> nom_canonique

        alias_path = self.corpus_dir / 'lieu_alias.csv'
        if alias_path.exists():
            with open(alias_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    variante = row['variante'].strip()
                    lieu_nom = row['lieu_nom'].strip()

                    self.aliases[variante.lower()] = lieu_nom

                    variante_norm = normalize_for_matching(variante)
                    if variante_norm:
                        self.aliases_normalized[variante_norm] = lieu_nom

            logger.debug(f"Chargé {len(self.aliases)} aliases depuis lieu_alias.csv")

    def find_lieu(self, lieu_raw: str) -> Optional[Tuple[str, str]]:
        """
        Trouve le lieu correspondant.

        Args:
            lieu_raw: Nom du lieu tel qu'extrait

        Returns:
            (nom_canonique, ville) ou None si non trouvé
        """
        if not lieu_raw or not lieu_raw.strip():
            return None

        cache_key = lieu_raw.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._match_lieu(lieu_raw.strip())
        self._cache[cache_key] = result
        return result

    def _match_lieu(self, lieu_raw: str) -> Optional[Tuple[str, str]]:
        """Logique de matching multi-niveaux."""

        lieu_lower = lieu_raw.lower()
        lieu_norm = normalize_for_matching(lieu_raw)
        lieu_stripped = normalize_for_matching(strip_prefixes(lieu_raw))

        # 1. Match exact case-insensitive dans les lieux
        if lieu_lower in self.lieux:
            d = self.lieux[lieu_lower]
            return (d['nom'], d['ville'])

        # 2. Match normalisé automatique (accents, tirets, abréviations)
        if lieu_norm and lieu_norm in self.lieux_by_normalized:
            nom = self.lieux_by_normalized[lieu_norm]
            d = self.lieux[nom.lower()]
            return (d['nom'], d['ville'])

        # 3. Match par alias exact (cas spéciaux CSV)
        if lieu_lower in self.aliases:
            nom = self.aliases[lieu_lower]
            if nom.lower() in self.lieux:
                d = self.lieux[nom.lower()]
                return (d['nom'], d['ville'])

        # 4. Match par alias normalisé
        if lieu_norm and lieu_norm in self.aliases_normalized:
            nom = self.aliases_normalized[lieu_norm]
            if nom.lower() in self.lieux:
                d = self.lieux[nom.lower()]
                return (d['nom'], d['ville'])

        # 5. Match sans préfixes (le, la, l', etc.)
        if lieu_stripped and lieu_stripped in self.lieux_by_stripped:
            nom = self.lieux_by_stripped[lieu_stripped]
            d = self.lieux[nom.lower()]
            return (d['nom'], d['ville'])

        return None

    def get_all_lieux(self) -> List[Dict]:
        """Retourne tous les lieux sous forme de liste."""
        return [{'nom': d['nom'], 'ville': d['ville']} for d in self.lieux.values()]

    def reload(self):
        """Recharge les données depuis les CSV."""
        self._cache = {}
        self._load_from_csv()


class VilleNormalizer:
    """
    Normalisation des villes.

    Mêmes règles automatiques que LieuNormalizer.
    Par défaut, retourne "Le Mans" si ville non trouvée ou vide.
    """

    def __init__(self, corpus_dir: Path = CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self._cache: Dict[str, Tuple[str, bool]] = {}
        self._load_from_csv()

    def _load_from_csv(self):
        """Charge les villes depuis le CSV."""
        self.villes: Dict[str, str] = {}  # nom_lower -> nom_canonique
        self.villes_by_normalized: Dict[str, str] = {}  # nom_norm -> nom_canonique
        self.le_mans = 'Le Mans'

        ville_path = self.corpus_dir / 'ville.csv'
        if ville_path.exists():
            with open(ville_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nom = row['nom'].strip()
                    self.villes[nom.lower()] = nom

                    nom_norm = normalize_for_matching(nom)
                    if nom_norm and nom_norm not in self.villes_by_normalized:
                        self.villes_by_normalized[nom_norm] = nom

                    if nom.lower() == 'le mans':
                        self.le_mans = nom

            logger.debug(f"Chargé {len(self.villes)} villes depuis ville.csv")

    def find_ville(self, ville_raw: str) -> Tuple[str, bool]:
        """
        Trouve la ville correspondante.

        Args:
            ville_raw: Nom de la ville tel qu'extrait

        Returns:
            (nom_canonique, found) - Si non trouvé, retourne ("Le Mans", False)
        """
        # Défaut: Le Mans
        if not ville_raw or not ville_raw.strip():
            return (self.le_mans, False)

        cache_key = ville_raw.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._match_ville(ville_raw.strip())
        self._cache[cache_key] = result
        return result

    def _match_ville(self, ville_raw: str) -> Tuple[str, bool]:
        """Logique de matching."""

        ville_lower = ville_raw.lower()
        ville_norm = normalize_for_matching(ville_raw)

        # 1. Match exact case-insensitive
        if ville_lower in self.villes:
            return (self.villes[ville_lower], True)

        # 2. Match normalisé (accents, tirets, etc.)
        if ville_norm and ville_norm in self.villes_by_normalized:
            return (self.villes_by_normalized[ville_norm], True)

        # Non trouvé - retourner Le Mans par défaut
        return (self.le_mans, False)

    def reload(self):
        """Recharge les données depuis les CSV."""
        self._cache = {}
        self._load_from_csv()


class ArtisteNormalizer:
    """
    Normalisation et matching des artistes.

    Source: corpus/artiste.csv et corpus/artiste_alias.csv

    Stratégie de matching:
    1. Match exact case-insensitive
    2. Match normalisé automatique
    3. Match par alias CSV
    """

    def __init__(self, corpus_dir: Path = CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self._cache: Dict[str, Optional[Tuple[str, str]]] = {}
        self._load_from_csv()

    def _load_from_csv(self):
        """Charge les référentiels depuis les CSV."""

        self.artistes: Dict[str, Dict] = {}  # nom_lower -> {nom, style}
        self.artistes_by_normalized: Dict[str, str] = {}  # nom_norm -> nom

        artiste_path = self.corpus_dir / 'artiste.csv'
        if artiste_path.exists():
            with open(artiste_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nom = row['nom_canonique'].strip()
                    style = row.get('style', '').strip()

                    self.artistes[nom.lower()] = {'nom': nom, 'style': style}

                    nom_norm = normalize_for_matching(nom)
                    if nom_norm and nom_norm not in self.artistes_by_normalized:
                        self.artistes_by_normalized[nom_norm] = nom

            logger.debug(f"Chargé {len(self.artistes)} artistes depuis artiste.csv")

        self.aliases: Dict[str, str] = {}  # variante_lower -> nom_canonique
        self.aliases_normalized: Dict[str, str] = {}

        alias_path = self.corpus_dir / 'artiste_alias.csv'
        if alias_path.exists():
            with open(alias_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    variante = row['variante'].strip()
                    artiste_nom = row['artiste_nom'].strip()

                    self.aliases[variante.lower()] = artiste_nom

                    variante_norm = normalize_for_matching(variante)
                    if variante_norm:
                        self.aliases_normalized[variante_norm] = artiste_nom

            logger.debug(f"Chargé {len(self.aliases)} aliases depuis artiste_alias.csv")

    def find_artiste(self, artiste_raw: str) -> Optional[Tuple[str, str]]:
        """
        Trouve l'artiste correspondant.

        Returns:
            (nom_canonique, style) ou None si non trouvé
        """
        if not artiste_raw or not artiste_raw.strip():
            return None

        cache_key = artiste_raw.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._match_artiste(artiste_raw.strip())
        self._cache[cache_key] = result
        return result

    def _match_artiste(self, artiste_raw: str) -> Optional[Tuple[str, str]]:
        """Logique de matching."""

        artiste_lower = artiste_raw.lower()
        artiste_norm = normalize_for_matching(artiste_raw)

        # 1. Match exact case-insensitive
        if artiste_lower in self.artistes:
            d = self.artistes[artiste_lower]
            return (d['nom'], d['style'])

        # 2. Match normalisé automatique
        if artiste_norm and artiste_norm in self.artistes_by_normalized:
            nom = self.artistes_by_normalized[artiste_norm]
            d = self.artistes[nom.lower()]
            return (d['nom'], d['style'])

        # 3. Match par alias exact
        if artiste_lower in self.aliases:
            nom = self.aliases[artiste_lower]
            if nom.lower() in self.artistes:
                d = self.artistes[nom.lower()]
                return (d['nom'], d['style'])

        # 4. Match par alias normalisé
        if artiste_norm and artiste_norm in self.aliases_normalized:
            nom = self.aliases_normalized[artiste_norm]
            if nom.lower() in self.artistes:
                d = self.artistes[nom.lower()]
                return (d['nom'], d['style'])

        return None

    def get_all_artistes(self) -> List[Dict]:
        """Retourne tous les artistes sous forme de liste."""
        return list(self.artistes.values())

    def reload(self):
        """Recharge les données depuis les CSV."""
        self._cache = {}
        self._load_from_csv()


class StyleNormalizer:
    """
    Normalisation des styles/genres.

    Règles automatiques + aliases CSV.
    """

    # Styles canoniques et leurs variations automatiques
    STYLE_EXPANSIONS = {
        'th.': 'théâtre',
        'th': 'théâtre',
        'theatre': 'théâtre',
        'chanson fr.': 'chanson française',
        'chanson fr': 'chanson française',
        'ch. fr.': 'chanson française',
        'ch.fr.': 'chanson française',
        'ch fr': 'chanson française',
    }

    def __init__(self, corpus_dir: Path = CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self._load_data()

    def _load_data(self):
        """Charge les aliases depuis le CSV."""
        self.aliases: Dict[str, str] = {}

        # Charger les expansions automatiques
        for variante, canonique in self.STYLE_EXPANSIONS.items():
            self.aliases[variante.lower()] = canonique

        # Charger les aliases CSV (prioritaires)
        style_alias_path = self.corpus_dir / 'style_alias.csv'
        if style_alias_path.exists():
            with open(style_alias_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    variante = row['variante'].strip().lower()
                    canonique = row['style_canonique'].strip()
                    self.aliases[variante] = canonique

            logger.debug(f"Chargé {len(self.aliases)} aliases de styles")

    def normalize(self, style_raw: str) -> str:
        """
        Normalise un style.

        Returns:
            Style canonique ou l'original si non trouvé
        """
        if not style_raw:
            return style_raw

        style_lower = style_raw.lower().strip()

        # Lookup direct
        if style_lower in self.aliases:
            return self.aliases[style_lower]

        # Lookup sans accents
        style_no_accent = remove_accents(style_lower)
        if style_no_accent in self.aliases:
            return self.aliases[style_no_accent]

        return style_raw

    def reload(self):
        """Recharge les données."""
        self._load_data()


# =============================================================================
# Instances singleton et fonctions utilitaires
# =============================================================================

_lieu_normalizer: Optional[LieuNormalizer] = None
_ville_normalizer: Optional[VilleNormalizer] = None
_artiste_normalizer: Optional[ArtisteNormalizer] = None
_style_normalizer: Optional[StyleNormalizer] = None


def get_lieu_normalizer() -> LieuNormalizer:
    """Retourne l'instance singleton du normaliseur de lieux."""
    global _lieu_normalizer
    if _lieu_normalizer is None:
        _lieu_normalizer = LieuNormalizer()
    return _lieu_normalizer


def get_ville_normalizer() -> VilleNormalizer:
    """Retourne l'instance singleton du normaliseur de villes."""
    global _ville_normalizer
    if _ville_normalizer is None:
        _ville_normalizer = VilleNormalizer()
    return _ville_normalizer


def get_artiste_normalizer() -> ArtisteNormalizer:
    """Retourne l'instance singleton du normaliseur d'artistes."""
    global _artiste_normalizer
    if _artiste_normalizer is None:
        _artiste_normalizer = ArtisteNormalizer()
    return _artiste_normalizer


def get_style_normalizer() -> StyleNormalizer:
    """Retourne l'instance singleton du normaliseur de styles."""
    global _style_normalizer
    if _style_normalizer is None:
        _style_normalizer = StyleNormalizer()
    return _style_normalizer


def reload_normalizers():
    """Recharge tous les normaliseurs depuis les CSV."""
    global _lieu_normalizer, _ville_normalizer, _artiste_normalizer, _style_normalizer
    for norm in [_lieu_normalizer, _ville_normalizer, _artiste_normalizer, _style_normalizer]:
        if norm:
            norm.reload()


# =============================================================================
# Fonctions de matching avec DB (incluant aliases)
# =============================================================================

@lru_cache(maxsize=1)
def load_lieu_index_with_aliases(db_path: str = None) -> dict[str, tuple[int, str]]:
    """
    Charge un index de matching pour les lieux (incluant les alias).
    Retourne dict: {nom_lower_or_norm: (lieu_id, nom_canonique)}
    """
    import sqlite3
    path = db_path or str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    index = {}

    # Charger lieu_ref (actifs uniquement)
    cur.execute('SELECT id, nom FROM lieu_ref WHERE actif = 1')
    for lieu_id, nom in cur.fetchall():
        # Forme lowercase
        index[nom.lower()] = (lieu_id, nom)
        # Forme normalisée automatique
        norm = normalize_for_matching(nom)
        if norm:
            index[norm] = (lieu_id, nom)
        # Forme sans préfixes
        stripped = normalize_for_matching(strip_prefixes(nom))
        if stripped and stripped != norm:
            index[stripped] = (lieu_id, nom)

    # Charger lieu_alias -> pointer vers lieu_ref
    cur.execute('''
        SELECT la.variante, lr.id, lr.nom
        FROM lieu_alias la
        JOIN lieu_ref lr ON la.lieu_nom = lr.nom AND lr.actif = 1
    ''')
    for variante, lieu_id, nom_canonique in cur.fetchall():
        index[variante.lower()] = (lieu_id, nom_canonique)
        norm = normalize_for_matching(variante)
        if norm:
            index[norm] = (lieu_id, nom_canonique)

    conn.close()
    return index


@lru_cache(maxsize=1)
def load_artiste_index_with_aliases(db_path: str = None) -> dict[str, tuple[int, str]]:
    """
    Charge un index de matching pour les artistes (incluant les alias).
    Retourne dict: {nom_lower_or_norm: (artiste_id, nom_canonique)}
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
        norm = normalize_for_matching(nom)
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
        norm = normalize_for_matching(variante)
        if norm:
            index[norm] = (artiste_id, nom_canonique)

    conn.close()
    return index


def find_lieu_ref_id(lieu_raw: str, db_path: str = None) -> tuple[Optional[int], Optional[str]]:
    """
    Trouve l'ID de lieu_ref pour un lieu brut (via matching avec aliases).
    Retourne (lieu_ref_id, nom_canonique) ou (None, None) si non trouvé.
    """
    if not lieu_raw or not lieu_raw.strip():
        return None, None

    index = load_lieu_index_with_aliases(db_path)

    # Match exact (case-insensitive)
    key = lieu_raw.lower().strip()
    if key in index:
        return index[key]

    # Match par nom normalisé
    norm = normalize_for_matching(lieu_raw)
    if norm and norm in index:
        return index[norm]

    # Match sans préfixes
    stripped = normalize_for_matching(strip_prefixes(lieu_raw))
    if stripped and stripped in index:
        return index[stripped]

    return None, None


def find_artiste_ref_id(artiste_raw: str, db_path: str = None) -> tuple[Optional[int], Optional[str]]:
    """
    Trouve l'ID de artiste_ref pour un artiste brut (via matching avec aliases).
    Retourne (artiste_ref_id, nom_canonique) ou (None, None) si non trouvé.
    """
    if not artiste_raw or not artiste_raw.strip():
        return None, None

    index = load_artiste_index_with_aliases(db_path)

    # Match exact (case-insensitive)
    key = artiste_raw.lower().strip()
    if key in index:
        return index[key]

    # Match par nom normalisé
    norm = normalize_for_matching(artiste_raw)
    if norm and norm in index:
        return index[norm]

    return None, None


# =============================================================================
# Fonctions legacy (compatibilité avec l'existant)
# =============================================================================

@lru_cache(maxsize=1)
def load_lieu_ref(db_path: str = None) -> dict[int, str]:
    """Charge le référentiel des lieux depuis la DB."""
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
    """Charge le référentiel des villes depuis la DB."""
    import sqlite3
    path = db_path or str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute('SELECT id, nom FROM ville_ref')
    villes = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return villes


def normalize_lieu(lieu_raw: str, db_path: str = None) -> tuple[Optional[int], Optional[str]]:
    """
    Normalise un nom de lieu extrait vers le référentiel.
    Retourne (lieu_ref_id, lieu_nom_normalise) ou (None, lieu_raw) si non trouvé.
    """
    if not lieu_raw:
        return None, None

    # Utiliser la fonction avec index
    lieu_id, nom = find_lieu_ref_id(lieu_raw, db_path)
    if lieu_id:
        return lieu_id, nom

    return None, lieu_raw


def normalize_ville(ville_raw: str, db_path: str = None) -> tuple[Optional[int], str]:
    """
    Normalise un nom de ville extrait vers le référentiel.
    Retourne (ville_ref_id, ville_nom_normalise).
    Si ville_raw est vide/None -> retourne l'id du Mans.
    """
    path = db_path or str(DEFAULT_DB_PATH)
    villes_ref = load_ville_ref(path)

    # Règle : si ville nulle -> Le Mans
    if not ville_raw or not ville_raw.strip():
        for ville_id, nom in villes_ref.items():
            if nom.lower() == 'le mans':
                return ville_id, 'Le Mans'
        return None, 'Le Mans'

    # Matching avec normalisation
    ville_norm = normalize_for_matching(ville_raw)

    for ville_id, nom in villes_ref.items():
        # Match exact lowercase
        if nom.lower() == ville_raw.lower().strip():
            return ville_id, nom
        # Match normalisé
        if normalize_for_matching(nom) == ville_norm:
            return ville_id, nom

    # Non trouvé -> Le Mans par défaut
    for ville_id, nom in villes_ref.items():
        if nom.lower() == 'le mans':
            return ville_id, 'Le Mans'

    return None, ville_raw


def clear_caches():
    """Vide les caches (utile après rechargement de la base)."""
    load_lieu_ref.cache_clear()
    load_ville_ref.cache_clear()
    load_lieu_index_with_aliases.cache_clear()
    load_artiste_index_with_aliases.cache_clear()
    reload_normalizers()


# =============================================================================
# Test
# =============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("TEST NORMALISATION AUTOMATIQUE")
    print("=" * 60)

    # Test fonction normalize_for_matching
    print("\n--- normalize_for_matching() ---")
    tests = [
        ("AZURYTE", "azuryte"),
        ("Th. Paul Scarron", "theatre paul scarron"),
        ("Auvers le-Hamon", "auvers le hamon"),
        ("Chemiré-le-Gaudin", "chemire le gaudin"),
        ("L'Écluse", "l ecluse"),
        ("L Écluse", "l ecluse"),
        ("L\u2019Oasis", "l oasis"),  # apostrophe typographique U+2019
        ("L\u2018Inventaire", "l inventaire"),  # apostrophe gauche U+2018
        ("St Pavace", "saint pavace"),
        ("St. Pavace", "saint pavace"),
        ("Moncé s/Loir", "monce sur loir"),
        ("Esp. Culturel", "espace culturel"),
        ("La Flèche", "la fleche"),
        ("Ste-Jamme-sur-Sarthe", "sainte jamme sur sarthe"),
        ("DJ SUPER LUCIEN", "dj super lucien"),
    ]

    all_pass = True
    for input_str, expected in tests:
        result = normalize_for_matching(input_str)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_pass = False
        print(f"  {status} '{input_str}' → '{result}' (attendu: '{expected}')")

    print(f"\nRésultat: {'TOUS OK' if all_pass else 'ÉCHECS DÉTECTÉS'}")

    # Test LieuNormalizer
    print("\n--- LieuNormalizer ---")
    lieu_norm = get_lieu_normalizer()
    print(f"Lieux chargés: {len(lieu_norm.lieux)}")
    print(f"Aliases chargés: {len(lieu_norm.aliases)}")

    lieu_tests = [
        "Th. Paul Scarron",
        "th paul scarron",
        "THEATRE PAUL SCARRON",
        "L'Oasis",
        "l oasis",
        "L OASIS",
        "Le Barouf",
        "le barouf",
        "BAROUF",
        "Le Mackeson",
        "le mackeson",
    ]

    for lieu in lieu_tests:
        result = lieu_norm.find_lieu(lieu)
        status = "✓" if result else "✗"
        if result:
            print(f"  {status} '{lieu}' → '{result[0]}' ({result[1]})")
        else:
            print(f"  {status} '{lieu}' → non trouvé")

    # Test VilleNormalizer
    print("\n--- VilleNormalizer ---")
    ville_norm = get_ville_normalizer()
    print(f"Villes chargées: {len(ville_norm.villes)}")

    ville_tests = [
        "Le Mans",
        "le mans",
        "LE MANS",
        "La Flèche",
        "La Fleche",
        "la fleche",
        "Chemiré-le-Gaudin",
        "Chemire le Gaudin",
        "Saint-Pavace",
        "St Pavace",
        "Auvers-le-Hamon",
        "Auvers le-Hamon",
        "",
    ]

    for ville in ville_tests:
        result, found = ville_norm.find_ville(ville)
        status = "✓" if found else "→"
        print(f"  {status} '{ville}' → '{result}' (found={found})")

    # Test StyleNormalizer
    print("\n--- StyleNormalizer ---")
    style_norm = get_style_normalizer()

    style_tests = [
        ("th.", "théâtre"),
        ("Th.", "théâtre"),
        ("th", "théâtre"),
        ("théâtre", "théâtre"),
        ("chanson fr.", "chanson française"),
        ("ch. fr.", "chanson française"),
        ("rock", "rock"),
    ]

    for style_in, expected in style_tests:
        result = style_norm.normalize(style_in)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{style_in}' → '{result}' (attendu: '{expected}')")

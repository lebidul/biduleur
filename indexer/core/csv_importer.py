"""
Import des événements depuis les CSV/XLSX de tapages.

Les CSV/XLSX sont la source de vérité pour les événements récents (2022+).
Ils ont une confidence de 1.0 car saisis manuellement.

Formats supportés:
- CSV 2022: tapage_biduleur_janvier_2022.csv
- CSV 2023+: 202301_tapage_biduleur_janvier_2023.csv
- XLSX 2025+: 202510_tapage_biduleur_Octobre_2025.xlsx (nouveau format avec colonnes différentes)
"""

import csv
import re
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Chemin vers le fichier de configuration des biduls
CORPUS_DIR = Path(__file__).parent.parent / 'corpus'
BIDULS_DESCRIPTION_CSV = CORPUS_DIR / 'biduls.description.csv'

# Mapping genre CSV -> type événement
CSV_GENRE_MAP = {
    'c': 'concert',
    'sv': 'spectacle vivant',
    'c & sv': 'concert & spectacle vivant',
    'c&sv': 'concert & spectacle vivant',
}

# Mapping mois français -> numéro
MOIS_FR = {
    'janvier': 1, 'fevrier': 2, 'février': 2, 'mars': 3, 'avril': 4, 'april': 4,
    'mai': 5, 'juin': 6, 'juillet': 7, 'aout': 8, 'août': 8,
    'septembre': 9, 'octobre': 10, 'novembre': 11, 'decembre': 12, 'décembre': 12
}

# Mapping des colonnes XLSX 2025+ vers format interne
# Les noms de colonnes dans le XLSX peuvent contenir des newlines et espaces
XLSX_COLUMN_PATTERNS = {
    'festival': ['festoche', 'evenement'],
    'style_festival': ['style', 'festoche', 'evenement'],
    'date': ['date'],
    'horaire': ['heure'],
    'lieu': ['lieu'],
    'ville': ['ville'],
    'prix': ['prix'],
    'genre': ['genre'],
}


def get_source_files_from_config(bidul_numero: int) -> list[str]:
    """
    Récupère la liste des fichiers sources depuis biduls.description.csv.

    Args:
        bidul_numero: Numéro du Bidul

    Returns:
        Liste des noms de fichiers (peut être vide si non défini)
    """
    if not BIDULS_DESCRIPTION_CSV.exists():
        return []

    # Lire le CSV de configuration
    try:
        with open(BIDULS_DESCRIPTION_CSV, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(
                (row for row in f if not row.startswith('#') and not row.startswith('"#'))
            )
            for row in reader:
                try:
                    num = int(row.get('numero', 0))
                except (ValueError, TypeError):
                    continue

                if num == bidul_numero:
                    source_file = (row.get('source_file') or '').strip()
                    if source_file:
                        # Multi-fichiers séparés par |
                        return [f.strip() for f in source_file.split('|') if f.strip()]
                    return []
    except Exception as e:
        logger.debug(f"Erreur lecture biduls.description.csv: {e}")

    return []


def normalize_xlsx_column(col_name: str) -> str:
    """
    Normalise un nom de colonne XLSX pour matching.

    Enlève les newlines, normalise les espaces, met en minuscules.
    """
    # Remplacer newlines par espaces
    normalized = col_name.replace('\n', ' ').replace('\r', ' ')
    # Réduire les espaces multiples
    normalized = ' '.join(normalized.split())
    # Minuscules
    return normalized.lower().strip()


def find_xlsx_column(df_columns: list[str], patterns: list[str]) -> Optional[str]:
    """
    Trouve une colonne dans le DataFrame par patterns.

    Args:
        df_columns: Liste des noms de colonnes du DataFrame
        patterns: Liste de mots-clés à chercher (tous doivent être présents)

    Returns:
        Nom de la colonne originale ou None
    """
    for col in df_columns:
        normalized = normalize_xlsx_column(col)
        if all(p.lower() in normalized for p in patterns):
            return col
    return None


def import_xlsx(xlsx_path: Path, bidul_numero: int,
                annee: int, mois: int) -> list[dict]:
    """
    Importe un fichier XLSX (format 2025+) et retourne liste d'événements.

    Args:
        xlsx_path: Chemin vers le fichier XLSX
        bidul_numero: Numéro du Bidul
        annee: Année du Bidul
        mois: Mois du Bidul

    Returns:
        Liste de dictionnaires représentant les événements
    """
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas requis pour les fichiers XLSX: pip install pandas openpyxl")
        return []

    events = []

    try:
        df = pd.read_excel(xlsx_path)
    except Exception as e:
        logger.error(f"Erreur lecture XLSX {xlsx_path}: {e}")
        return []

    # Mapper les colonnes
    columns = list(df.columns)
    col_map = {}

    # Colonnes de base
    col_map['date'] = find_xlsx_column(columns, ['date']) or 'DATE'
    col_map['horaire'] = find_xlsx_column(columns, ['heure']) or 'HEURE'
    col_map['lieu'] = find_xlsx_column(columns, ['lieu']) or 'LIEU'
    col_map['ville'] = find_xlsx_column(columns, ['ville']) or 'VILLE'
    col_map['prix'] = find_xlsx_column(columns, ['prix']) or 'PRIX'
    col_map['festival'] = find_xlsx_column(columns, ['festoche', 'evenement'])
    col_map['style_festival'] = find_xlsx_column(columns, ['style', 'festoche'])
    col_map['genre'] = find_xlsx_column(columns, ['genre', '1']) or find_xlsx_column(columns, ['genre'])

    # Colonnes artistes/spectacles (1-4)
    for i in range(1, 5):
        col_map[f'spectacle{i}'] = find_xlsx_column(columns, ['nom', 'spectacle', str(i)])
        col_map[f'artiste{i}'] = (
            find_xlsx_column(columns, ['compagnie', str(i)]) or
            find_xlsx_column(columns, ['groupe', str(i)]) or
            find_xlsx_column(columns, ['artiste', str(i)])
        )
        col_map[f'style{i}'] = find_xlsx_column(columns, ['style', str(i)])

    logger.debug(f"XLSX column mapping: {col_map}")

    for _, row in df.iterrows():
        # Fonction helper pour récupérer valeur d'une colonne mappée
        def get_val(key: str, default: str = '') -> str:
            col = col_map.get(key)
            if col and col in row.index:
                val = row[col]
                if pd.notna(val):
                    return str(val).strip()
            return default

        # Parser les artistes
        artistes = []
        spectacles = []
        genres = []

        for i in range(1, 5):
            spec = get_val(f'spectacle{i}')
            art = get_val(f'artiste{i}')
            style = get_val(f'style{i}')

            if art:
                artistes.append({
                    "nom": art,
                    "genre": style or None,
                    "spectacle": spec or None
                })
            if spec and spec not in spectacles:
                spectacles.append(spec)
            if style and style not in genres:
                genres.append(style)

        # Prix
        prix_min, prix_max, gratuit, tarif_raw = parse_price(get_val('prix'))

        # Date
        date_text = get_val('date')
        date_evenement = parse_date(date_text, annee, mois)

        # Ville par défaut
        ville = get_val('ville') or 'Le Mans'

        # Nom (festival)
        nom = get_val('festival') or None

        # Genre événement
        genre_evenement = get_val('style_festival') or None

        # Type événement
        genre_raw = get_val('genre').lower()
        type_evt = CSV_GENRE_MAP.get(genre_raw, genre_raw if genre_raw else None)

        # Construire raw_text
        raw_parts = [date_text, get_val('horaire')]
        if artistes:
            artiste_names = [a['nom'] for a in artistes if a.get('nom')]
            raw_parts.append(' + '.join(artiste_names))
        if spectacles:
            raw_parts.append(', '.join(f'"{s}"' for s in spectacles))
        raw_parts.extend([get_val('lieu'), ville, get_val('prix')])
        raw_text = ', '.join(p for p in raw_parts if p)

        # Ignorer les lignes vides
        if not raw_text or not any([artistes, spectacles, nom]):
            continue

        event = {
            'bidul_numero': bidul_numero,
            'raw_text': raw_text,
            'nom': nom,
            'date_evenement': date_evenement,
            'heure': get_val('horaire') or None,
            'lieu_raw': get_val('lieu') or None,
            'ville_raw': ville,
            'artistes': json.dumps(artistes, ensure_ascii=False) if artistes else None,
            'spectacles': json.dumps(spectacles, ensure_ascii=False) if spectacles else None,
            'genres_raw': json.dumps(genres, ensure_ascii=False) if genres else None,
            'genre_evenement': genre_evenement,
            'type_evenement': type_evt,
            'tarif_raw': tarif_raw,
            'prix_min': prix_min,
            'prix_max': prix_max,
            'gratuit': gratuit,
            'confidence': 1.0,
            'source': 'xlsx'
        }
        events.append(event)

    logger.info(f"Importé {len(events)} événements depuis {xlsx_path.name}")
    return events


def find_source_files(bidul_numero: int, mois: int, annee: int,
                      csv_dir: Path) -> list[Path]:
    """
    Trouve tous les fichiers sources (CSV ou XLSX) pour un Bidul.

    Priorité:
    1. Fichiers définis dans biduls.description.csv (colonne source_file)
    2. Fallback sur la détection automatique par nom

    Args:
        bidul_numero: Numéro du Bidul
        mois: Mois du Bidul
        annee: Année du Bidul
        csv_dir: Répertoire contenant les fichiers sources

    Returns:
        Liste des chemins trouvés (CSV ou XLSX)
    """
    if not csv_dir.exists():
        return []

    # 1. Chercher dans la config source_file
    source_files = get_source_files_from_config(bidul_numero)
    if source_files:
        found_paths = []
        for filename in source_files:
            # Chercher le fichier dans csv_dir (corpus)
            path = csv_dir / filename
            if path.exists():
                found_paths.append(path)
            else:
                logger.warning(f"Fichier source non trouvé: {path}")
        if found_paths:
            return found_paths

    # 2. Fallback: détection automatique par nom (CSV uniquement)
    return find_csv_for_bidul(bidul_numero, mois, annee, csv_dir)


def parse_csv_filename(filename: str) -> tuple[Optional[int], Optional[int]]:
    """
    Parse le nom d'un fichier CSV pour extraire année et mois.

    Formats supportés:
    - 202301_tapage_biduleur_janvier_2023.csv
    - tapage_biduleur_octobre_2022.csv

    Returns:
        (annee, mois) ou (None, None) si non parsable
    """
    name = Path(filename).stem.lower()

    # Format avec préfixe YYYYMM
    match = re.match(r'^(\d{4})(\d{2})_', name)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Format avec mois en texte
    for mois_nom, mois_num in MOIS_FR.items():
        if mois_nom in name:
            # Chercher l'année
            year_match = re.search(r'(\d{4})', name)
            if year_match:
                return int(year_match.group(1)), mois_num

    return None, None


def get_bidul_numero_from_date(annee: int, mois: int) -> int:
    """
    Calcule le numéro de Bidul à partir de l'année et du mois.

    Référence: Bidul 280 = mai 2023
    """
    return 280 + (annee - 2023) * 12 + (mois - 5)


def find_csv_for_bidul(bidul_numero: int, mois: int, annee: int,
                       csv_dir: Path) -> list[Path]:
    """
    Trouve tous les CSV correspondant à un Bidul.

    Args:
        bidul_numero: Numéro du Bidul
        mois: Mois du Bidul
        annee: Année du Bidul
        csv_dir: Répertoire contenant les CSV

    Returns:
        Liste des chemins CSV trouvés
    """
    if not csv_dir.exists():
        return []

    # Pattern avec préfixe YYYYMM
    prefix = f"{annee}{mois:02d}"
    csv_files = []

    for csv_file in csv_dir.glob("*.csv"):
        name = csv_file.name.lower()

        # Ignorer les fichiers _utf8.csv ou .v3.csv (variantes d'encodage)
        if 'utf8' in name or '.v3.' in name:
            continue

        # Vérifier si le fichier correspond au mois/année
        file_annee, file_mois = parse_csv_filename(csv_file.name)
        if file_annee == annee and file_mois == mois:
            csv_files.append(csv_file)

    return sorted(csv_files)


def parse_price(prix_raw: str) -> tuple[Optional[float], Optional[float], bool, Optional[str]]:
    """
    Parse le champ prix.

    Returns:
        (prix_min, prix_max, gratuit, tarif_raw)
    """
    if not prix_raw:
        return None, None, False, None

    prix = prix_raw.lower().strip()

    # Gratuit
    if prix in ['au chapeau', 'prix libre', 'libre', '0€', '0 €', '0', 'gratuit']:
        return None, None, True, prix_raw

    # Abréviations (garder tel quel)
    if prix in ['tnc', 'hnc']:
        return None, None, False, prix_raw

    # Parser les montants (ex: "4/8€", "4 à 8€", "5 à 10€", "4 à 10 €")
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*[/àa&\s-]+\s*(\d+(?:[.,]\d+)?)', prix)
    if match:
        min_val = float(match.group(1).replace(',', '.'))
        max_val = float(match.group(2).replace(',', '.'))
        return min_val, max_val, False, prix_raw

    # Montant unique
    match = re.search(r'(\d+(?:[.,]\d+)?)', prix)
    if match:
        val = float(match.group(1).replace(',', '.'))
        return val, val, val == 0, prix_raw

    return None, None, False, prix_raw


def parse_artists_from_csv(row: dict) -> tuple[list[dict], list[str], list[str]]:
    """
    Extrait artistes avec relations, spectacles et genres du CSV.

    Gère les deux formats:
    - 2023+: spectacle1, artiste1, style1, spectacle2, ...
    - 2022: spectacle, artiste1, style1, ...

    Returns:
        (artistes_avec_relations, spectacles, genres)
        artistes_avec_relations: [{"nom": "X", "genre": "rock", "spectacle": "Y"}, ...]
    """
    artistes = []
    spectacles = []
    genres = []

    # Détecter le format (2023+ a spectacle1, 2022 a spectacle)
    if 'spectacle1' in row:
        # Format 2023+: chaque artiste a son propre spectacle/style
        for i in range(1, 5):
            spec = row.get(f'spectacle{i}', '').strip()
            art = row.get(f'artiste{i}', '').strip()
            style = row.get(f'style{i}', '').strip()
            if art:
                artistes.append({
                    "nom": art,
                    "genre": style or None,
                    "spectacle": spec or None
                })
            if spec and spec not in spectacles:
                spectacles.append(spec)
            if style and style not in genres:
                genres.append(style)
    else:
        # Format 2022: spectacle commun pour tous les artistes
        spec = row.get('spectacle', '').strip()
        if spec:
            spectacles.append(spec)
        for i in range(1, 5):
            art = row.get(f'artiste{i}', '').strip()
            style = row.get(f'style{i}', '').strip()
            if art:
                artistes.append({
                    "nom": art,
                    "genre": style or None,
                    "spectacle": spec or None
                })
            if style and style not in genres:
                genres.append(style)

    return artistes, spectacles, genres


def parse_date(date_text: str, annee: int, mois: int) -> Optional[str]:
    """
    Parse 'Dimanche 12' + année/mois → date ISO.

    Returns:
        Date au format YYYY-MM-DD ou None
    """
    if not date_text:
        return None

    match = re.search(r'(\d{1,2})', date_text)
    if match:
        jour = int(match.group(1))
        # Valider le jour
        if 1 <= jour <= 31:
            return f"{annee}-{mois:02d}-{jour:02d}"
    return None


def import_csv(csv_path: Path, bidul_numero: int,
               annee: int, mois: int) -> list[dict]:
    """
    Importe un CSV et retourne liste d'événements.

    Args:
        csv_path: Chemin vers le fichier CSV
        bidul_numero: Numéro du Bidul
        annee: Année du Bidul
        mois: Mois du Bidul

    Returns:
        Liste de dictionnaires représentant les événements
    """
    events = []

    # Essayer différents encodages
    content = None
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        logger.error(f"Impossible de lire {csv_path}")
        return []

    # Parser le CSV
    import io
    reader = csv.DictReader(io.StringIO(content))

    for row in reader:
        # Parser les champs
        artistes, spectacles, genres = parse_artists_from_csv(row)
        prix_min, prix_max, gratuit, tarif_raw = parse_price(row.get('prix', ''))
        date_evenement = parse_date(row.get('date', ''), annee, mois)

        # Ville par défaut
        ville = row.get('ville', '').strip() or 'Le Mans'

        # Construire le nom (festival si présent)
        nom = row.get('festival', '').strip() or None

        # Genre événement (style_festival)
        genre_evenement = row.get('style_festival', '').strip() or None

        # Type événement (c, sv, c & sv)
        genre_raw = row.get('genre', '').strip().lower()
        type_evt = CSV_GENRE_MAP.get(genre_raw, genre_raw if genre_raw else None)

        # Construire raw_text pour référence
        raw_parts = [row.get('date', ''), row.get('horaire', '')]
        if artistes:
            # artistes est maintenant une liste de dicts avec "nom"
            artiste_names = [a['nom'] for a in artistes if a.get('nom')]
            raw_parts.append(' + '.join(artiste_names))
        if spectacles:
            raw_parts.append(', '.join(f'"{s}"' for s in spectacles))
        raw_parts.extend([row.get('lieu', ''), ville, row.get('prix', '')])
        raw_text = ', '.join(p for p in raw_parts if p)

        event = {
            'bidul_numero': bidul_numero,
            'raw_text': raw_text,
            'nom': nom,
            'date_evenement': date_evenement,
            'heure': row.get('horaire', '').strip() or None,
            'lieu_raw': row.get('lieu', '').strip() or None,
            'ville_raw': ville,
            'artistes': json.dumps(artistes, ensure_ascii=False) if artistes else None,
            'spectacles': json.dumps(spectacles, ensure_ascii=False) if spectacles else None,
            'genres_raw': json.dumps(genres, ensure_ascii=False) if genres else None,
            'genre_evenement': genre_evenement,
            'type_evenement': type_evt,
            'tarif_raw': tarif_raw,
            'prix_min': prix_min,
            'prix_max': prix_max,
            'gratuit': gratuit,
            'confidence': 1.0,
            'source': 'csv'
        }
        events.append(event)

    logger.info(f"Importé {len(events)} événements depuis {csv_path.name}")
    return events


def dedupe_events(events: list[dict]) -> list[dict]:
    """
    Dédoublonne sur (date, lieu, artiste principal ou spectacle).
    Garde l'événement avec le plus d'infos.

    Args:
        events: Liste d'événements

    Returns:
        Liste dédoublonnée
    """
    seen = {}
    for e in events:
        # Clé de déduplication
        artistes = json.loads(e['artistes']) if e['artistes'] else []
        spectacles = json.loads(e['spectacles']) if e['spectacles'] else []

        # Utiliser artiste principal ou spectacle principal
        identifier = ''
        if artistes:
            # artistes peut être une liste de dicts ou de strings
            first = artistes[0]
            if isinstance(first, dict):
                identifier = first.get('nom', '').lower().strip()
            else:
                identifier = first.lower().strip()
        elif spectacles:
            identifier = spectacles[0].lower().strip()
        elif e['nom']:
            identifier = e['nom'].lower().strip()

        key = (
            e['date_evenement'],
            (e['lieu_raw'] or '').lower().strip(),
            identifier
        )

        if key not in seen:
            seen[key] = e
        else:
            # Garder celui avec le plus de champs remplis
            existing = seen[key]
            score_new = sum(1 for v in e.values() if v)
            score_old = sum(1 for v in existing.values() if v)
            if score_new > score_old:
                seen[key] = e

    return list(seen.values())


def import_bidul_from_source(bidul_numero: int, source_paths: list[Path],
                              annee: int, mois: int) -> list[dict]:
    """
    Importe les événements depuis un ou plusieurs fichiers sources (CSV ou XLSX).

    Args:
        bidul_numero: Numéro du Bidul
        source_paths: Liste des fichiers sources (CSV ou XLSX)
        annee: Année du Bidul
        mois: Mois du Bidul

    Returns:
        Liste des événements dédoublonnés
    """
    all_events = []
    for path in source_paths:
        if path.suffix.lower() == '.xlsx':
            events = import_xlsx(path, bidul_numero, annee, mois)
        else:
            events = import_csv(path, bidul_numero, annee, mois)
        all_events.extend(events)

    deduped = dedupe_events(all_events)
    logger.info(f"Bidul {bidul_numero}: {len(all_events)} événements, "
                f"{len(deduped)} après déduplication")

    return deduped


# Alias pour compatibilité avec le code existant
def import_bidul_from_csv(bidul_numero: int, csv_paths: list[Path],
                          annee: int, mois: int) -> list[dict]:
    """
    Alias de import_bidul_from_source pour compatibilité.
    """
    return import_bidul_from_source(bidul_numero, csv_paths, annee, mois)

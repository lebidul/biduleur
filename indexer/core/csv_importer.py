"""
Import des événements depuis les CSV de tapages.

Les CSV sont la source de vérité pour les événements récents (2022+).
Ils ont une confidence de 1.0 car saisis manuellement.
"""

import csv
import re
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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


def parse_artists_from_csv(row: dict) -> tuple[list[str], list[str], list[str]]:
    """
    Extrait artistes, spectacles et genres du CSV.

    Gère les deux formats:
    - 2023+: spectacle1, artiste1, style1, spectacle2, ...
    - 2022: spectacle, artiste1, style1, ...

    Returns:
        (artistes, spectacles, genres)
    """
    artistes = []
    spectacles = []
    genres = []

    # Détecter le format (2023+ a spectacle1, 2022 a spectacle)
    if 'spectacle1' in row:
        # Format 2023+
        for i in range(1, 5):
            spec = row.get(f'spectacle{i}', '').strip()
            art = row.get(f'artiste{i}', '').strip()
            style = row.get(f'style{i}', '').strip()
            if art:
                artistes.append(art)
            if spec:
                spectacles.append(spec)
            if style:
                genres.append(style)
    else:
        # Format 2022
        spec = row.get('spectacle', '').strip()
        if spec:
            spectacles.append(spec)
        for i in range(1, 5):
            art = row.get(f'artiste{i}', '').strip()
            style = row.get(f'style{i}', '').strip()
            if art:
                artistes.append(art)
            if style:
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
            raw_parts.append(' + '.join(artistes))
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
            identifier = artistes[0].lower().strip()
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


def import_bidul_from_csv(bidul_numero: int, csv_paths: list[Path],
                          annee: int, mois: int) -> list[dict]:
    """
    Importe les événements depuis un ou plusieurs CSV.

    Args:
        bidul_numero: Numéro du Bidul
        csv_paths: Liste des fichiers CSV
        annee: Année du Bidul
        mois: Mois du Bidul

    Returns:
        Liste des événements dédoublonnés
    """
    all_events = []
    for path in csv_paths:
        events = import_csv(path, bidul_numero, annee, mois)
        all_events.extend(events)

    deduped = dedupe_events(all_events)
    logger.info(f"Bidul {bidul_numero}: {len(all_events)} événements, "
                f"{len(deduped)} après déduplication")

    return deduped

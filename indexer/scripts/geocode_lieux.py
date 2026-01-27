"""
Script de géocodage des lieux du référentiel.

Utilise Nominatim (OpenStreetMap) pour récupérer les coordonnées géographiques.
Les résultats sont sauvegardés dans la base ET dans corpus/lieu.csv.

Usage:
    python scripts/geocode_lieux.py [--limit N] [--dry-run] [--force]

Options:
    --limit N    Limite le nombre de lieux à géocoder (pour tests)
    --dry-run    Affiche les résultats sans sauvegarder
    --force      Regéocode même les lieux qui ont déjà des coordonnées
"""

import argparse
import csv
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import urllib.request
import urllib.parse
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Chemins
DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"
LIEU_CSV_PATH = Path(__file__).parent.parent / "corpus" / "lieu.csv"

# Configuration Nominatim
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "BiduLIndexer/1.0 (https://github.com/lebidul/biduleur)"
RATE_LIMIT_SECONDS = 1.1  # Nominatim demande 1 requête/seconde max


@dataclass
class GeoResult:
    """Résultat de géocodage."""
    latitude: float
    longitude: float
    source: str = "nominatim"
    precision: str = "exact"
    display_name: Optional[str] = None


def geocode_nominatim(lieu: str, ville: str) -> Optional[GeoResult]:
    """
    Géocode un lieu via Nominatim.

    Stratégie de recherche:
    1. Cherche "lieu, ville, France"
    2. Si pas trouvé, cherche "lieu, ville, Sarthe, France"
    3. Si pas trouvé, essaie avec des noms simplifiés
    4. Si pas trouvé, cherche juste "ville, Sarthe, France" (précision: city)
    """
    # Normaliser la ville
    ville_norm = ville.strip() if ville else "Le Mans"

    # Requêtes principales
    queries = [
        f"{lieu}, {ville_norm}, France",
        f"{lieu}, {ville_norm}, Sarthe, France",
    ]

    for query in queries:
        result = _nominatim_search(query)
        if result:
            return result

    # Essai avec des variantes du nom du lieu
    lieu_clean = _simplify_lieu_name(lieu)
    if lieu_clean != lieu:
        for query in [
            f"{lieu_clean}, {ville_norm}, France",
            f"{lieu_clean}, {ville_norm}, Sarthe, France",
        ]:
            result = _nominatim_search(query)
            if result:
                result.precision = "approximate"
                return result

    # Fallback: coordonnées de la ville
    city_query = f"{ville_norm}, Sarthe, France"
    result = _nominatim_search(city_query)
    if result:
        result.precision = "city"
        return result

    return None


def _simplify_lieu_name(lieu: str) -> str:
    """Simplifie le nom d'un lieu pour améliorer le géocodage."""
    import re

    # Supprime les préfixes courants
    prefixes = [
        r"^(Bar|Café|Restaurant|Pub|Brasserie|Salle|Le|La|L'|Les|Au|Aux)\s+",
        r"^(Espace|Centre|Maison|Hôtel|Auberge|Théâtre|Cinéma)\s+",
    ]
    result = lieu
    for prefix in prefixes:
        result = re.sub(prefix, "", result, flags=re.IGNORECASE)

    # Supprime les suffixes
    suffixes = [
        r"\s+(Le Mans|Allonnes|La Flèche)$",
    ]
    for suffix in suffixes:
        result = re.sub(suffix, "", result, flags=re.IGNORECASE)

    return result.strip()


def _nominatim_search(query: str) -> Optional[GeoResult]:
    """Effectue une requête Nominatim."""
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "fr"
    }

    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        if data and len(data) > 0:
            result = data[0]
            return GeoResult(
                latitude=float(result['lat']),
                longitude=float(result['lon']),
                source="nominatim",
                precision="exact",
                display_name=result.get('display_name')
            )
    except Exception as e:
        logger.warning(f"Erreur Nominatim pour '{query}': {e}")

    return None


def load_lieux_to_geocode(conn: sqlite3.Connection, force: bool = False) -> list[tuple]:
    """Charge les lieux à géocoder."""
    cursor = conn.cursor()

    if force:
        # Tous les lieux actifs
        cursor.execute('''
            SELECT id, nom, ville
            FROM lieu_ref
            WHERE actif = 1
            ORDER BY ville, nom
        ''')
    else:
        # Seulement les lieux sans coordonnées
        cursor.execute('''
            SELECT id, nom, ville
            FROM lieu_ref
            WHERE actif = 1 AND latitude IS NULL
            ORDER BY ville, nom
        ''')

    return cursor.fetchall()


def update_lieu_coordinates(
    conn: sqlite3.Connection,
    lieu_id: int,
    result: GeoResult,
    dry_run: bool = False
) -> None:
    """Met à jour les coordonnées d'un lieu dans la base."""
    if dry_run:
        return

    cursor = conn.cursor()
    cursor.execute('''
        UPDATE lieu_ref
        SET latitude = ?, longitude = ?, geo_source = ?, geo_precision = ?
        WHERE id = ?
    ''', (result.latitude, result.longitude, result.source, result.precision, lieu_id))


def export_to_lieu_csv(conn: sqlite3.Connection) -> None:
    """Met à jour corpus/lieu.csv avec les coordonnées géographiques."""
    # Lire le fichier existant pour préserver nom_normalise
    existing = {}
    if LIEU_CSV_PATH.exists():
        with open(LIEU_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row['nom'], row.get('ville', 'Le Mans'))
                existing[key] = row.get('nom_normalise', '')

    # Récupérer les données depuis la base
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nom, ville, latitude, longitude, geo_source, geo_precision
        FROM lieu_ref
        WHERE actif = 1
        ORDER BY ville, nom
    ''')

    rows = cursor.fetchall()

    # Écrire le fichier avec toutes les colonnes
    fieldnames = ['nom', 'ville', 'nom_normalise', 'latitude', 'longitude', 'geo_source', 'geo_precision']
    with open(LIEU_CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for nom, ville, lat, lon, source, precision in rows:
            key = (nom, ville or 'Le Mans')
            writer.writerow({
                'nom': nom,
                'ville': ville or 'Le Mans',
                'nom_normalise': existing.get(key, ''),
                'latitude': lat if lat is not None else '',
                'longitude': lon if lon is not None else '',
                'geo_source': source or '',
                'geo_precision': precision or ''
            })

    logger.info(f"Mis à jour {len(rows)} lieux dans {LIEU_CSV_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Géocode les lieux du référentiel")
    parser.add_argument('--limit', type=int, help="Limite le nombre de lieux")
    parser.add_argument('--dry-run', action='store_true', help="Mode simulation")
    parser.add_argument('--force', action='store_true', help="Regéocode tous les lieux")
    parser.add_argument('-v', '--verbose', action='store_true', help="Affichage détaillé")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    conn = sqlite3.connect(DB_PATH)

    try:
        lieux = load_lieux_to_geocode(conn, force=args.force)

        if args.limit:
            lieux = lieux[:args.limit]

        logger.info(f"Lieux à géocoder: {len(lieux)}")

        if args.dry_run:
            logger.info("[MODE DRY-RUN - aucune modification]")

        stats = {'success': 0, 'city': 0, 'failed': 0}

        for i, (lieu_id, nom, ville) in enumerate(lieux, 1):
            logger.info(f"[{i}/{len(lieux)}] {nom}, {ville}")

            result = geocode_nominatim(nom, ville)

            if result:
                if result.precision == "city":
                    logger.warning(f"  -> Coordonnées de la ville uniquement")
                    stats['city'] += 1
                else:
                    logger.debug(f"  -> {result.latitude}, {result.longitude}")
                    stats['success'] += 1

                update_lieu_coordinates(conn, lieu_id, result, dry_run=args.dry_run)
            else:
                logger.warning(f"  -> Non trouvé")
                stats['failed'] += 1

            # Rate limiting
            time.sleep(RATE_LIMIT_SECONDS)

        if not args.dry_run:
            conn.commit()
            export_to_lieu_csv(conn)

        # Résumé
        print(f"\n=== RÉSUMÉ ===")
        print(f"  Exact: {stats['success']}")
        print(f"  Ville: {stats['city']}")
        print(f"  Échec: {stats['failed']}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()

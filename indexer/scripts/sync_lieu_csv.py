"""
Script de synchronisation lieu.csv → lieu_ref.

Met à jour la table lieu_ref avec les données de corpus/lieu.csv.
Synchronise: coordonnées géographiques, adresse, code postal.

Usage:
    python scripts/sync_lieu_csv.py [--dry-run] [-v]

Options:
    --dry-run    Affiche les modifications sans les appliquer
    -v           Affichage détaillé
"""

import argparse
import csv
import logging
import sqlite3
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Chemins
DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"
LIEU_CSV_PATH = Path(__file__).parent.parent / "corpus" / "lieu.csv"


def load_csv_data() -> dict:
    """Charge les données du CSV."""
    data = {}
    with open(LIEU_CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row['nom']
            data[key] = {
                'ville': row.get('ville', 'Le Mans') or 'Le Mans',
                'adresse_numero': row.get('adresse_numero', '') or None,
                'adresse_voie': row.get('adresse_voie', '') or None,
                'code_postal': row.get('code_postal', '') or None,
                'latitude': float(row['latitude']) if row.get('latitude') else None,
                'longitude': float(row['longitude']) if row.get('longitude') else None,
                'geo_source': row.get('geo_source', '') or None,
                'geo_precision': row.get('geo_precision', '') or None,
            }
    return data


def sync_to_database(csv_data: dict, dry_run: bool = False) -> dict:
    """Synchronise les données CSV vers la base."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {'updated': 0, 'not_found': 0, 'unchanged': 0}

    for nom, data in csv_data.items():
        # Chercher le lieu en base
        cursor.execute('SELECT id, latitude, longitude, adresse_numero, adresse_voie, code_postal FROM lieu_ref WHERE nom = ?', (nom,))
        row = cursor.fetchone()

        if not row:
            logger.warning(f"Lieu non trouvé en base: {nom}")
            stats['not_found'] += 1
            continue

        lieu_id, db_lat, db_lon, db_num, db_voie, db_cp = row

        # Vérifier si mise à jour nécessaire
        needs_update = (
            db_lat != data['latitude'] or
            db_lon != data['longitude'] or
            db_num != data['adresse_numero'] or
            db_voie != data['adresse_voie'] or
            db_cp != data['code_postal']
        )

        if not needs_update:
            stats['unchanged'] += 1
            continue

        logger.debug(f"Mise à jour: {nom}")

        if not dry_run:
            cursor.execute('''
                UPDATE lieu_ref
                SET latitude = ?, longitude = ?, geo_source = ?, geo_precision = ?,
                    adresse_numero = ?, adresse_voie = ?, code_postal = ?
                WHERE id = ?
            ''', (
                data['latitude'], data['longitude'],
                data['geo_source'], data['geo_precision'],
                data['adresse_numero'], data['adresse_voie'], data['code_postal'],
                lieu_id
            ))

        stats['updated'] += 1

    if not dry_run:
        conn.commit()

    conn.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Synchronise lieu.csv vers lieu_ref")
    parser.add_argument('--dry-run', action='store_true', help="Mode simulation")
    parser.add_argument('-v', '--verbose', action='store_true', help="Affichage détaillé")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Chargement de {LIEU_CSV_PATH}")
    csv_data = load_csv_data()
    logger.info(f"  {len(csv_data)} lieux chargés")

    if args.dry_run:
        logger.info("[MODE DRY-RUN - aucune modification]")

    logger.info("Synchronisation vers la base...")
    stats = sync_to_database(csv_data, dry_run=args.dry_run)

    print(f"\n=== RÉSUMÉ ===")
    print(f"  Mis à jour: {stats['updated']}")
    print(f"  Inchangés: {stats['unchanged']}")
    print(f"  Non trouvés: {stats['not_found']}")


if __name__ == '__main__':
    main()

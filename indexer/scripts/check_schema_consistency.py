"""
Verifie la coherence entre evenement.artistes/spectacles et contenu_evenement
avant la migration du schema.

Identifie:
1. Evenements avec JSON mais sans contenu_evenement
2. Differences entre les deux sources
3. Statistiques globales
"""

import sqlite3
import json
import logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def parse_json_field(value: str) -> list:
    """Parse un champ JSON, retourne liste vide si invalide."""
    if not value:
        return []
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return data
        return [data] if data else []
    except (json.JSONDecodeError, TypeError):
        return []


def extract_names_from_json(json_list: list) -> set:
    """Extrait les noms depuis une liste JSON (dicts ou strings)."""
    names = set()
    for item in json_list:
        if isinstance(item, dict):
            if 'nom' in item:
                names.add(item['nom'].strip().lower())
            elif 'name' in item:
                names.add(item['name'].strip().lower())
        elif isinstance(item, str):
            names.add(item.strip().lower())
    return names


def check_consistency(conn: sqlite3.Connection) -> dict:
    """Verifie la coherence des donnees."""
    cur = conn.cursor()

    stats = {
        'total_events': 0,
        'events_with_json_artistes': 0,
        'events_with_json_spectacles': 0,
        'events_with_contenu': 0,
        'json_only': [],      # Evenements avec JSON mais sans contenu_evenement
        'contenu_only': [],   # Evenements avec contenu mais sans JSON
        'mismatches': [],     # Differences entre JSON et contenu
        'ok': 0,              # Coherents
    }

    # Recuperer tous les evenements avec leurs champs JSON
    cur.execute("""
        SELECT id, artistes, spectacles, genres_raw
        FROM evenement
    """)
    events = cur.fetchall()
    stats['total_events'] = len(events)

    for evt_id, artistes_json, spectacles_json, genres_json in events:
        artistes_from_json = extract_names_from_json(parse_json_field(artistes_json))
        spectacles_from_json = extract_names_from_json(parse_json_field(spectacles_json))

        has_json = bool(artistes_from_json or spectacles_from_json)

        if artistes_from_json:
            stats['events_with_json_artistes'] += 1
        if spectacles_from_json:
            stats['events_with_json_spectacles'] += 1

        # Recuperer le contenu_evenement correspondant
        cur.execute("""
            SELECT artiste, nom_spectacle, style
            FROM contenu_evenement
            WHERE evenement_id = ?
        """, (evt_id,))
        contenus = cur.fetchall()

        artistes_from_contenu = set()
        spectacles_from_contenu = set()
        for artiste, spectacle, style in contenus:
            if artiste:
                artistes_from_contenu.add(artiste.strip().lower())
            if spectacle:
                spectacles_from_contenu.add(spectacle.strip().lower())

        has_contenu = bool(artistes_from_contenu or spectacles_from_contenu)

        if has_contenu:
            stats['events_with_contenu'] += 1

        # Comparer
        if has_json and not has_contenu:
            stats['json_only'].append({
                'id': evt_id,
                'artistes_json': list(artistes_from_json),
                'spectacles_json': list(spectacles_from_json)
            })
        elif has_contenu and not has_json:
            stats['contenu_only'].append(evt_id)
        elif has_json and has_contenu:
            # Verifier si coherent
            artistes_match = artistes_from_json == artistes_from_contenu
            spectacles_match = spectacles_from_json == spectacles_from_contenu

            if artistes_match and spectacles_match:
                stats['ok'] += 1
            else:
                stats['mismatches'].append({
                    'id': evt_id,
                    'artistes_json': list(artistes_from_json),
                    'artistes_contenu': list(artistes_from_contenu),
                    'spectacles_json': list(spectacles_from_json),
                    'spectacles_contenu': list(spectacles_from_contenu),
                })

    return stats


def print_report(stats: dict):
    """Affiche le rapport de coherence."""
    print("\n" + "=" * 70)
    print("RAPPORT DE COHERENCE SCHEMA")
    print("=" * 70)

    print(f"\n## Statistiques generales")
    print(f"  Evenements total: {stats['total_events']:,}")
    print(f"  Avec JSON artistes: {stats['events_with_json_artistes']:,}")
    print(f"  Avec JSON spectacles: {stats['events_with_json_spectacles']:,}")
    print(f"  Avec contenu_evenement: {stats['events_with_contenu']:,}")

    print(f"\n## Coherence")
    print(f"  [OK] Coherents (JSON = contenu): {stats['ok']:,}")
    print(f"  [!] JSON seulement (pas de contenu): {len(stats['json_only'])}")
    print(f"  [!] Contenu seulement (pas de JSON): {len(stats['contenu_only'])}")
    print(f"  [X] Differences JSON vs contenu: {len(stats['mismatches'])}")

    # Details des problemes
    if stats['json_only']:
        print(f"\n## Evenements avec JSON mais sans contenu_evenement")
        print(f"   (Ces donnees seront PERDUES si on supprime les colonnes JSON)")
        for item in stats['json_only'][:10]:
            print(f"   [{item['id']}] artistes={item['artistes_json'][:3]}, spectacles={item['spectacles_json'][:2]}")
        if len(stats['json_only']) > 10:
            print(f"   ... et {len(stats['json_only']) - 10} autres")

    if stats['mismatches']:
        print(f"\n## Exemples de differences JSON vs contenu")
        for item in stats['mismatches'][:5]:
            print(f"   [{item['id']}]")
            print(f"      JSON artistes: {item['artistes_json'][:3]}")
            print(f"      Contenu artistes: {item['artistes_contenu'][:3]}")

    # Conclusion
    print("\n" + "=" * 70)
    if stats['json_only']:
        print("[!] ATTENTION: Il y a des donnees dans les colonnes JSON qui ne sont")
        print("    pas dans contenu_evenement. Il faut d'abord migrer ces donnees.")
        print("\n    Executer: python scripts/migrate_json_to_contenu.py")
    else:
        print("[OK] Toutes les donnees JSON sont presentes dans contenu_evenement.")
        print("     La migration du schema peut etre effectuee en toute securite.")
    print("=" * 70)


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        stats = check_consistency(conn)
        print_report(stats)

        # Retourner un code d'erreur si incoherences critiques
        if stats['json_only']:
            return 1
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    sys.exit(main())

"""
Migre les donnees des colonnes JSON vers contenu_evenement.

Pour les evenements qui ont des donnees JSON mais pas de contenu_evenement,
cree les entrees correspondantes.
"""

import sqlite3
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def parse_json_field(value: str) -> list:
    """Parse un champ JSON."""
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else [data] if data else []
    except (json.JSONDecodeError, TypeError):
        return []


def migrate_event(conn: sqlite3.Connection, evt_id: int, artistes_json: str,
                  spectacles_json: str, genres_json: str) -> int:
    """Migre un evenement, retourne le nombre d'entrees creees."""
    cur = conn.cursor()

    artistes = parse_json_field(artistes_json)
    spectacles = parse_json_field(spectacles_json)
    genres = parse_json_field(genres_json)

    created = 0
    ordre = 0

    # Normaliser les artistes
    norm_artistes = []
    for a in artistes:
        if isinstance(a, dict):
            norm_artistes.append({
                'nom': a.get('nom', a.get('name', '')),
                'style': a.get('genre') or a.get('style')
            })
        elif isinstance(a, str) and a.strip():
            style = genres[len(norm_artistes)] if len(norm_artistes) < len(genres) else None
            if isinstance(style, dict):
                style = style.get('nom', style.get('name'))
            norm_artistes.append({'nom': a.strip(), 'style': style})

    # Normaliser les spectacles
    norm_spectacles = []
    for s in spectacles:
        if isinstance(s, dict):
            norm_spectacles.append({
                'nom': s.get('nom', s.get('name', '')),
                'style': s.get('style') or s.get('genre')
            })
        elif isinstance(s, str) and s.strip():
            norm_spectacles.append({'nom': s.strip(), 'style': None})

    # Cas 1: Spectacles + Artistes
    if norm_spectacles and norm_artistes:
        # Premier spectacle avec premier artiste
        first_spec = norm_spectacles[0]
        first_art = norm_artistes[0]
        style = first_spec.get('style') or first_art.get('style')

        cur.execute("""
            INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
            VALUES (?, ?, ?, ?, ?)
        """, (evt_id, first_art.get('nom'), first_spec.get('nom'), style, ordre))
        created += 1
        ordre += 1

        # Artistes supplementaires
        for art in norm_artistes[1:]:
            cur.execute("""
                INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                VALUES (?, ?, ?, ?, ?)
            """, (evt_id, art.get('nom'), None, art.get('style'), ordre))
            created += 1
            ordre += 1

        # Spectacles supplementaires
        for spec in norm_spectacles[1:]:
            cur.execute("""
                INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                VALUES (?, ?, ?, ?, ?)
            """, (evt_id, None, spec.get('nom'), spec.get('style'), ordre))
            created += 1
            ordre += 1

    # Cas 2: Spectacles seuls
    elif norm_spectacles:
        for spec in norm_spectacles:
            cur.execute("""
                INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                VALUES (?, ?, ?, ?, ?)
            """, (evt_id, None, spec.get('nom'), spec.get('style'), ordre))
            created += 1
            ordre += 1

    # Cas 3: Artistes seuls
    elif norm_artistes:
        for art in norm_artistes:
            cur.execute("""
                INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                VALUES (?, ?, ?, ?, ?)
            """, (evt_id, art.get('nom'), None, art.get('style'), ordre))
            created += 1
            ordre += 1

    return created


def migrate_all(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Migre tous les evenements avec JSON mais sans contenu_evenement."""
    cur = conn.cursor()

    # Trouver les evenements a migrer
    cur.execute("""
        SELECT e.id, e.artistes, e.spectacles, e.genres_raw
        FROM evenement e
        WHERE (e.artistes IS NOT NULL AND e.artistes != '[]' AND e.artistes != '')
           OR (e.spectacles IS NOT NULL AND e.spectacles != '[]' AND e.spectacles != '')
    """)

    events_with_json = cur.fetchall()
    logger.info(f"Evenements avec donnees JSON: {len(events_with_json)}")

    # Filtrer ceux qui n'ont pas de contenu_evenement
    to_migrate = []
    for evt_id, artistes, spectacles, genres in events_with_json:
        cur.execute("""
            SELECT COUNT(*) FROM contenu_evenement
            WHERE evenement_id = ? AND (artiste IS NOT NULL OR nom_spectacle IS NOT NULL)
        """, (evt_id,))
        if cur.fetchone()[0] == 0:
            to_migrate.append((evt_id, artistes, spectacles, genres))

    logger.info(f"Evenements a migrer (JSON sans contenu): {len(to_migrate)}")

    if dry_run:
        logger.info("[DRY RUN] Aucune modification effectuee")
        for evt_id, artistes, spectacles, genres in to_migrate[:10]:
            artistes_list = parse_json_field(artistes)
            spectacles_list = parse_json_field(spectacles)
            logger.info(f"  [{evt_id}] {len(artistes_list)} artistes, {len(spectacles_list)} spectacles")
        return len(to_migrate)

    total_created = 0
    for evt_id, artistes, spectacles, genres in to_migrate:
        created = migrate_event(conn, evt_id, artistes, spectacles, genres)
        total_created += created

    conn.commit()
    logger.info(f"[OK] Migre {len(to_migrate)} evenements, cree {total_created} entrees contenu_evenement")

    return len(to_migrate)


def main(dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("MIGRATION JSON -> CONTENU_EVENEMENT")
    if dry_run:
        logger.info(">>> MODE DRY RUN <<<")
    logger.info("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    try:
        migrate_all(conn, dry_run)
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    main(dry_run=dry_run)

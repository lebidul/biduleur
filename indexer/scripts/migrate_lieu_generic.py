#!/usr/bin/env python3
"""
Migration script for generic locations (lieux génériques).

This script modifies lieu_ref to use a composite unique key (nom, ville)
instead of just (nom), allowing the same location name to exist in
multiple cities (e.g., "Salle des fêtes" in Arnage, Mamers, Le Mans, etc.)

Usage:
    python scripts/migrate_lieu_generic.py --dry-run  # Preview changes
    python scripts/migrate_lieu_generic.py            # Apply migration
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"

# Patterns for generic location names (case-insensitive)
GENERIC_PATTERNS = [
    "salle des fêtes",
    "salle des fetes",
    "salle polyvalente",
    "salle municipale",
    "église",
    "eglise",
    "halles",
    "place de la mairie",
    "place de l'église",
    "place de l'eglise",
    "mairie",
    "médiathèque",
    "mediatheque",
    "bibliothèque",
    "bibliotheque",
    "gymnase",
    "stade",
    "foyer rural",
    "foyer des jeunes",
    "centre culturel",
    "espace culturel",
]


def is_generic_location(nom: str) -> bool:
    """Check if a location name is generic."""
    nom_lower = nom.lower().strip()
    for pattern in GENERIC_PATTERNS:
        if nom_lower == pattern:
            return True
    return False


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def backup_database():
    """Create a backup of the database."""
    backup_path = DB_PATH.parent / f"bidul_archives_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    import shutil
    shutil.copy(DB_PATH, backup_path)
    print(f"[OK] Backup created: {backup_path}")
    return backup_path


def analyze_generic_locations(conn: sqlite3.Connection) -> dict:
    """
    Analyze which generic locations need to be duplicated.

    Returns a dict: {lieu_raw: {ville_raw: count, ...}, ...}
    """
    cursor = conn.cursor()

    # Find all events with generic location names
    result = {}

    cursor.execute("""
        SELECT DISTINCT lieu_raw, ville_raw, COUNT(*) as cnt
        FROM evenement
        WHERE lieu_raw IS NOT NULL AND ville_raw IS NOT NULL
        GROUP BY lieu_raw, ville_raw
        ORDER BY lieu_raw, cnt DESC
    """)

    for row in cursor.fetchall():
        lieu_raw = row['lieu_raw']
        ville_raw = row['ville_raw']
        cnt = row['cnt']

        if is_generic_location(lieu_raw):
            if lieu_raw not in result:
                result[lieu_raw] = {}
            result[lieu_raw][ville_raw] = cnt

    return result


def get_existing_lieu_ref(conn: sqlite3.Connection) -> dict:
    """Get existing lieu_ref entries."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, nom, ville FROM lieu_ref")
    return {(row['nom'], row['ville']): row['id'] for row in cursor.fetchall()}


def migrate_schema(conn: sqlite3.Connection, dry_run: bool = True):
    """
    Migrate lieu_ref to use composite unique key (nom, ville).
    """
    cursor = conn.cursor()

    print("\n=== Analyzing current state ===")

    # Get current schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lieu_ref'")
    old_schema = cursor.fetchone()['sql']
    print(f"Current schema:\n{old_schema}\n")

    # Analyze generic locations
    generic_locs = analyze_generic_locations(conn)

    print(f"\n=== Generic locations found: {len(generic_locs)} ===")
    total_new_entries = 0
    for lieu, villes in sorted(generic_locs.items(), key=lambda x: -sum(x[1].values())):
        total_events = sum(villes.values())
        print(f"  {lieu:<30} : {len(villes)} villes, {total_events} events")
        for ville, cnt in sorted(villes.items(), key=lambda x: -x[1])[:5]:
            print(f"    - {ville}: {cnt} events")
        if len(villes) > 5:
            print(f"    ... and {len(villes) - 5} more cities")
        total_new_entries += len(villes)

    print(f"\n=== Migration plan ===")
    print(f"  New lieu_ref entries to create: {total_new_entries}")

    if dry_run:
        print("\n[DRY-RUN] No changes made. Use --apply to execute migration.")
        return

    print("\n=== Executing migration ===")

    # Step 1: Create new table with composite unique key
    print("1. Creating new lieu_ref table with UNIQUE(nom, ville)...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lieu_ref_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            ville TEXT DEFAULT 'Le Mans',
            actif BOOLEAN DEFAULT TRUE,
            is_generic BOOLEAN DEFAULT FALSE,
            latitude REAL,
            longitude REAL,
            geo_source TEXT,
            geo_precision TEXT,
            adresse_numero TEXT,
            adresse_voie TEXT,
            code_postal TEXT,
            nom_osm TEXT,
            UNIQUE(nom, ville)
        )
    """)

    # Step 2: Copy existing data
    print("2. Copying existing lieu_ref data...")
    cursor.execute("""
        INSERT INTO lieu_ref_new (id, nom, ville, actif, is_generic, latitude, longitude,
                                   geo_source, geo_precision, adresse_numero, adresse_voie,
                                   code_postal, nom_osm)
        SELECT id, nom, ville, actif, 0, latitude, longitude,
               geo_source, geo_precision, adresse_numero, adresse_voie,
               code_postal, nom_osm
        FROM lieu_ref
    """)
    copied = cursor.rowcount
    print(f"   Copied {copied} entries")

    # Step 3: Create new entries for generic locations in different cities
    print("3. Creating entries for generic locations in other cities...")
    existing = get_existing_lieu_ref(conn)

    # Get max ID for new entries
    cursor.execute("SELECT MAX(id) FROM lieu_ref_new")
    max_id = cursor.fetchone()[0] or 0

    new_entries = []
    for lieu_raw, villes in generic_locs.items():
        for ville_raw in villes:
            # Normalize names
            lieu_normalized = lieu_raw.strip()
            ville_normalized = ville_raw.strip()

            # Check if this combination already exists
            if (lieu_normalized, ville_normalized) not in existing:
                max_id += 1
                new_entries.append((max_id, lieu_normalized, ville_normalized, True, True))

    if new_entries:
        cursor.executemany("""
            INSERT OR IGNORE INTO lieu_ref_new (id, nom, ville, actif, is_generic)
            VALUES (?, ?, ?, ?, ?)
        """, new_entries)
        print(f"   Created {len(new_entries)} new entries for generic locations")

    # Step 4: Build mapping from (lieu_raw, ville_raw) to new lieu_ref_id
    print("4. Building mapping for evenement.lieu_ref_id updates...")
    cursor.execute("SELECT id, nom, ville FROM lieu_ref_new")
    new_mapping = {(row['nom'].lower(), row['ville'].lower()): row['id'] for row in cursor.fetchall()}

    # Step 5: Update evenement.lieu_ref_id for generic locations
    print("5. Updating evenement.lieu_ref_id for generic locations...")
    updates = 0

    for lieu_raw, villes in generic_locs.items():
        for ville_raw in villes:
            key = (lieu_raw.lower().strip(), ville_raw.lower().strip())
            if key in new_mapping:
                new_id = new_mapping[key]
                cursor.execute("""
                    UPDATE evenement
                    SET lieu_ref_id = ?
                    WHERE LOWER(TRIM(lieu_raw)) = ? AND LOWER(TRIM(ville_raw)) = ?
                """, (new_id, key[0], key[1]))
                updates += cursor.rowcount

    print(f"   Updated {updates} events")

    # Step 6: Replace old table with new one
    print("6. Replacing old lieu_ref table...")

    # First, drop views that depend on lieu_ref
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
    views = [row[0] for row in cursor.fetchall()]
    for view in views:
        cursor.execute(f"DROP VIEW IF EXISTS {view}")
        print(f"   Dropped view: {view}")

    cursor.execute("DROP TABLE lieu_ref")
    cursor.execute("ALTER TABLE lieu_ref_new RENAME TO lieu_ref")

    # Recreate views
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_evenements AS
        SELECT
            e.*,
            b.mois AS bidul_mois,
            b.annee AS bidul_annee,
            b.source AS bidul_source,
            COALESCE(lr.nom, e.lieu_raw) AS lieu,
            COALESCE(vr.nom, e.ville_raw) AS ville
        FROM evenement e
        JOIN bidul b ON e.bidul_numero = b.numero
        LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
        LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
    """)
    print("   Recreated view: v_evenements")

    # Step 7: Recreate indexes
    print("7. Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lieu_ref_nom ON lieu_ref(nom)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lieu_ref_ville ON lieu_ref(ville)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lieu_ref_generic ON lieu_ref(is_generic)")

    conn.commit()
    print("\n[OK] Migration completed successfully!")

    # Show summary
    cursor.execute("SELECT COUNT(*) FROM lieu_ref")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM lieu_ref WHERE is_generic = 1")
    generic = cursor.fetchone()[0]
    print(f"\n=== Summary ===")
    print(f"  Total lieu_ref entries: {total}")
    print(f"  Generic locations: {generic}")


def verify_migration(conn: sqlite3.Connection):
    """Verify the migration was successful."""
    cursor = conn.cursor()

    print("\n=== Verification ===")

    # Check schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lieu_ref'")
    schema = cursor.fetchone()['sql']
    if "UNIQUE(nom, ville)" in schema:
        print("[OK] Schema has UNIQUE(nom, ville) constraint")
    else:
        print("[FAIL] Schema missing UNIQUE(nom, ville) constraint")
        print(f"  Current schema: {schema}")

    # Check is_generic column
    cursor.execute("PRAGMA table_info(lieu_ref)")
    columns = [row['name'] for row in cursor.fetchall()]
    if 'is_generic' in columns:
        print("[OK] is_generic column exists")
    else:
        print("[FAIL] is_generic column missing")

    # Check matching for a generic location
    cursor.execute("""
        SELECT e.lieu_raw, e.ville_raw, e.lieu_ref_id, lr.nom, lr.ville
        FROM evenement e
        LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
        WHERE LOWER(e.lieu_raw) = 'salle des fêtes'
        AND e.ville_raw != 'Le Mans'
        LIMIT 5
    """)

    print("\nSample: 'Salle des fêtes' events (non-Le Mans):")
    for row in cursor.fetchall():
        match = "[OK]" if row['ville_raw'] == row['ville'] else "[FAIL]"
        print(f"  {match} {row['lieu_raw']}, {row['ville_raw']} -> ref: {row['nom']}, {row['ville']}")


def backfill_lieu_ref_id(conn: sqlite3.Connection, dry_run: bool = True):
    """
    Backfill lieu_ref_id for all events, using the new (nom, ville) matching.
    """
    cursor = conn.cursor()

    print("\n=== Backfilling lieu_ref_id ===")

    # Build mapping (lieu_raw_lower, ville_raw_lower) -> lieu_ref_id
    cursor.execute("SELECT id, nom, ville, is_generic FROM lieu_ref WHERE actif = 1")
    mapping = {}
    for row in cursor.fetchall():
        lieu_id, nom, ville, is_generic = row
        ville = ville or 'Le Mans'

        if is_generic:
            # For generic locations, key is (nom, ville)
            key = (nom.lower().strip(), ville.lower().strip())
            mapping[key] = lieu_id
        else:
            # For normal locations, key is just nom
            mapping[nom.lower().strip()] = lieu_id

    print(f"  Loaded {len(mapping)} mappings")

    # Find events that need updating
    cursor.execute("""
        SELECT e.id, e.lieu_raw, e.ville_raw, e.lieu_ref_id, lr.ville as current_ref_ville
        FROM evenement e
        LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
        WHERE e.lieu_raw IS NOT NULL
    """)

    updates = []
    for row in cursor.fetchall():
        event_id, lieu_raw, ville_raw, current_ref_id, current_ref_ville = row

        if not lieu_raw:
            continue

        lieu_lower = lieu_raw.lower().strip()
        ville_lower = (ville_raw or 'Le Mans').lower().strip()

        # Try composite key first (for generic locations)
        new_ref_id = mapping.get((lieu_lower, ville_lower))

        # If not found, try simple key (for normal locations)
        if new_ref_id is None:
            new_ref_id = mapping.get(lieu_lower)

        # Only update if different
        if new_ref_id is not None and new_ref_id != current_ref_id:
            updates.append((new_ref_id, event_id))

    print(f"  Found {len(updates)} events to update")

    if dry_run:
        # Show sample
        print("\n  Sample updates:")
        for new_id, event_id in updates[:10]:
            cursor.execute("""
                SELECT e.lieu_raw, e.ville_raw, lr_old.ville as old_ville, lr_new.ville as new_ville
                FROM evenement e
                LEFT JOIN lieu_ref lr_old ON e.lieu_ref_id = lr_old.id
                LEFT JOIN lieu_ref lr_new ON lr_new.id = ?
                WHERE e.id = ?
            """, (new_id, event_id))
            row = cursor.fetchone()
            if row:
                print(f"    Event {event_id}: {row[0]} @ {row[1]} : {row[2]} -> {row[3]}")
        print("\n[DRY-RUN] No changes made.")
        return

    # Apply updates
    cursor.executemany("UPDATE evenement SET lieu_ref_id = ? WHERE id = ?", updates)
    conn.commit()

    print(f"  [OK] Updated {len(updates)} events")


def main():
    parser = argparse.ArgumentParser(description="Migrate lieu_ref for generic locations")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--apply", action="store_true", help="Apply the migration")
    parser.add_argument("--verify", action="store_true", help="Verify migration status")
    parser.add_argument("--backfill", action="store_true", help="Backfill lieu_ref_id for all events")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup (not recommended)")
    args = parser.parse_args()

    if not args.apply and not args.verify and not args.backfill:
        args.dry_run = True

    conn = get_connection()

    try:
        if args.verify:
            verify_migration(conn)
        elif args.backfill:
            if args.apply and not args.no_backup:
                backup_database()
            backfill_lieu_ref_id(conn, dry_run=not args.apply)
            if args.apply:
                verify_migration(conn)
        else:
            if args.apply and not args.no_backup:
                backup_database()

            migrate_schema(conn, dry_run=not args.apply)

            if args.apply:
                verify_migration(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""
Migration du schema v3: suppression des colonnes redondantes.

Colonnes supprimees de evenement:
- artistes (JSON)
- spectacles (JSON)
- genres_raw (JSON)
- style

SQLite ne supporte pas DROP COLUMN avant 3.35, donc on recree la table.
"""

import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def get_sqlite_version() -> tuple:
    """Retourne la version SQLite."""
    conn = sqlite3.connect(':memory:')
    version = conn.execute('SELECT sqlite_version()').fetchone()[0]
    conn.close()
    return tuple(map(int, version.split('.')))


def check_prerequisites(conn: sqlite3.Connection) -> bool:
    """Verifie les prerequis avant migration."""
    cur = conn.cursor()

    # Verifier qu'il n'y a pas de donnees JSON orphelines
    cur.execute("""
        SELECT COUNT(*) FROM evenement e
        WHERE (e.artistes IS NOT NULL AND e.artistes != '[]' AND e.artistes != '')
          AND NOT EXISTS (
              SELECT 1 FROM contenu_evenement ce
              WHERE ce.evenement_id = e.id AND (ce.artiste IS NOT NULL OR ce.nom_spectacle IS NOT NULL)
          )
    """)
    orphans = cur.fetchone()[0]

    if orphans > 0:
        logger.error(f"[!] {orphans} evenements ont des donnees JSON sans contenu_evenement")
        logger.error("    Executer d'abord: python scripts/migrate_json_to_contenu.py")
        return False

    logger.info("[OK] Prerequis OK: toutes les donnees JSON sont dans contenu_evenement")
    return True


def backup_database(db_path: Path) -> Path:
    """Cree une sauvegarde de la base."""
    import shutil
    from datetime import datetime

    backup_name = f"{db_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{db_path.suffix}"
    backup_path = db_path.parent / backup_name
    shutil.copy2(db_path, backup_path)
    logger.info(f"[OK] Sauvegarde creee: {backup_path}")
    return backup_path


def migrate_schema(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """Migre le schema en supprimant les colonnes redondantes."""
    cur = conn.cursor()

    # Verifier prerequis
    if not check_prerequisites(conn):
        return False

    if dry_run:
        logger.info("[DRY RUN] Migration simulee")
        logger.info("Colonnes a supprimer: artistes, spectacles, genres_raw, style")

        # Compter les donnees qui seront "perdues" (deja migrees)
        cur.execute("SELECT COUNT(*) FROM evenement WHERE artistes IS NOT NULL AND artistes != '[]'")
        logger.info(f"  evenement.artistes rempli: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM evenement WHERE spectacles IS NOT NULL AND spectacles != '[]'")
        logger.info(f"  evenement.spectacles rempli: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM evenement WHERE genres_raw IS NOT NULL AND genres_raw != '[]'")
        logger.info(f"  evenement.genres_raw rempli: {cur.fetchone()[0]}")

        return True

    # Verifier version SQLite
    sqlite_version = get_sqlite_version()
    logger.info(f"Version SQLite: {'.'.join(map(str, sqlite_version))}")

    if sqlite_version >= (3, 35, 0):
        # SQLite 3.35+ supporte DROP COLUMN
        logger.info("Utilisation de ALTER TABLE DROP COLUMN")

        columns_to_drop = ['artistes', 'spectacles', 'genres_raw', 'style']
        for col in columns_to_drop:
            try:
                cur.execute(f"ALTER TABLE evenement DROP COLUMN {col}")
                logger.info(f"  [OK] Supprime: {col}")
            except sqlite3.OperationalError as e:
                if 'no such column' in str(e).lower():
                    logger.info(f"  [-] {col} n'existe pas (deja supprime?)")
                else:
                    raise

        conn.commit()
    else:
        # Ancienne methode: recreer la table
        logger.info("Recreation de la table (SQLite < 3.35)")

        cur.executescript("""
            -- Desactiver les foreign keys temporairement
            PRAGMA foreign_keys = OFF;

            -- Creer la nouvelle table sans les colonnes redondantes
            CREATE TABLE evenement_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bidul_numero INTEGER NOT NULL REFERENCES bidul(numero),
                raw_text TEXT NOT NULL,
                raw_text_clean TEXT,
                nom TEXT,
                date_evenement DATE,
                heure TEXT,
                lieu_raw TEXT,
                lieu_ref_id INTEGER REFERENCES lieu_ref(id),
                ville_raw TEXT,
                ville_ref_id INTEGER REFERENCES ville_ref(id),
                tarif_raw TEXT,
                prix_min REAL,
                prix_max REAL,
                gratuit BOOLEAN DEFAULT FALSE,
                type_evenement TEXT,
                genre_evenement TEXT,
                confidence REAL DEFAULT 0.5,
                needs_review BOOLEAN DEFAULT FALSE,
                verified BOOLEAN DEFAULT FALSE,
                verified_by TEXT,
                verified_at TIMESTAMP,
                review_status TEXT DEFAULT 'pending',
                review_notes TEXT,
                source TEXT DEFAULT 'pdf',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- Copier les donnees (sans les colonnes supprimees)
            INSERT INTO evenement_new (
                id, bidul_numero, raw_text, raw_text_clean, nom, date_evenement, heure,
                lieu_raw, lieu_ref_id, ville_raw, ville_ref_id,
                tarif_raw, prix_min, prix_max, gratuit,
                type_evenement, genre_evenement, confidence,
                needs_review, verified, verified_by, verified_at,
                review_status, review_notes, source, created_at
            )
            SELECT
                id, bidul_numero, raw_text, raw_text_clean, nom, date_evenement, heure,
                lieu_raw, lieu_ref_id, ville_raw, ville_ref_id,
                tarif_raw, prix_min, prix_max, gratuit,
                type_evenement, genre_evenement, confidence,
                needs_review, verified, verified_by, verified_at,
                review_status, review_notes, source, created_at
            FROM evenement;

            -- Supprimer l'ancienne table
            DROP TABLE evenement;

            -- Renommer la nouvelle
            ALTER TABLE evenement_new RENAME TO evenement;

            -- Recreer les index
            CREATE INDEX idx_evt_date ON evenement(date_evenement);
            CREATE INDEX idx_evt_bidul ON evenement(bidul_numero);
            CREATE INDEX idx_evt_lieu ON evenement(lieu_ref_id);
            CREATE INDEX idx_evt_ville ON evenement(ville_ref_id);
            CREATE INDEX idx_evenement_review_status ON evenement(review_status);
            CREATE INDEX idx_evenement_verified ON evenement(verified);

            -- Reactiver les foreign keys
            PRAGMA foreign_keys = ON;
        """)

        conn.commit()

    # Verification
    cur.execute("SELECT COUNT(*) FROM evenement")
    count = cur.fetchone()[0]
    logger.info(f"[OK] Migration terminee: {count} evenements")

    # Verifier les colonnes
    cur.execute("PRAGMA table_info(evenement)")
    columns = [row[1] for row in cur.fetchall()]
    removed = ['artistes', 'spectacles', 'genres_raw', 'style']
    still_present = [c for c in removed if c in columns]
    if still_present:
        logger.warning(f"[!] Colonnes encore presentes: {still_present}")
    else:
        logger.info("[OK] Colonnes redondantes supprimees")

    # Vacuum pour recuperer l'espace
    logger.info("Optimisation de la base (VACUUM)...")
    conn.execute("VACUUM")

    return True


def update_view(conn: sqlite3.Connection):
    """Met a jour la vue v_evenements."""
    cur = conn.cursor()

    # Supprimer l'ancienne vue
    cur.execute("DROP VIEW IF EXISTS v_evenements")

    # Creer la nouvelle vue (sans les colonnes supprimees)
    cur.execute("""
        CREATE VIEW v_evenements AS
        SELECT
            e.id,
            e.bidul_numero,
            e.raw_text,
            e.raw_text_clean,
            e.nom,
            e.date_evenement,
            e.heure,
            e.lieu_raw,
            e.lieu_ref_id,
            e.ville_raw,
            e.ville_ref_id,
            e.tarif_raw,
            e.prix_min,
            e.prix_max,
            e.gratuit,
            e.type_evenement,
            e.genre_evenement,
            e.confidence,
            e.needs_review,
            e.verified,
            e.review_status,
            e.source,
            e.created_at,
            b.mois AS bidul_mois,
            b.annee AS bidul_annee,
            COALESCE(lr.nom, e.lieu_raw) AS lieu,
            COALESCE(vr.nom, e.ville_raw) AS ville
        FROM evenement e
        JOIN bidul b ON e.bidul_numero = b.numero
        LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
        LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
    """)

    # Creer une vue pour evenements avec contenu
    cur.execute("DROP VIEW IF EXISTS v_evenements_complets")
    cur.execute("""
        CREATE VIEW v_evenements_complets AS
        SELECT
            e.id,
            e.bidul_numero,
            e.date_evenement,
            e.heure,
            COALESCE(lr.nom, e.lieu_raw) AS lieu,
            COALESCE(vr.nom, e.ville_raw) AS ville,
            e.tarif_raw,
            e.gratuit,
            e.type_evenement,
            e.confidence,
            GROUP_CONCAT(DISTINCT ce.artiste) AS artistes,
            GROUP_CONCAT(DISTINCT ce.nom_spectacle) AS spectacles,
            GROUP_CONCAT(DISTINCT ce.style) AS styles
        FROM evenement e
        JOIN bidul b ON e.bidul_numero = b.numero
        LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
        LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
        LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
        GROUP BY e.id
    """)

    conn.commit()
    logger.info("[OK] Vues v_evenements et v_evenements_complets mises a jour")


def main(dry_run: bool = False, no_backup: bool = False):
    logger.info("=" * 60)
    logger.info("MIGRATION SCHEMA V3")
    logger.info("Suppression des colonnes: artistes, spectacles, genres_raw, style")
    if dry_run:
        logger.info(">>> MODE DRY RUN <<<")
    logger.info("=" * 60)

    # Backup
    if not dry_run and not no_backup:
        backup_database(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    try:
        success = migrate_schema(conn, dry_run)

        if success and not dry_run:
            update_view(conn)

            # Stats finales
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM evenement")
            evt_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM contenu_evenement")
            contenu_count = cur.fetchone()[0]

            print("\n" + "=" * 60)
            print("MIGRATION TERMINEE")
            print("=" * 60)
            print(f"  Evenements: {evt_count:,}")
            print(f"  contenu_evenement: {contenu_count:,}")
            print(f"  Colonnes supprimees: artistes, spectacles, genres_raw, style")

    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    no_backup = '--no-backup' in sys.argv
    main(dry_run=dry_run, no_backup=no_backup)

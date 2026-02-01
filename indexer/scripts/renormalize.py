#!/usr/bin/env python3
"""
Script de re-normalisation des lieux et artistes.

Recharge les référentiels CSV et re-applique la normalisation
sur tous les événements existants.
"""

import sqlite3
import logging
import sys
from pathlib import Path

# Ajouter le parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.normalizer import find_lieu_ref_id, find_artiste_ref_id, normalize_ville, clear_caches

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def reload_referentiels(conn: sqlite3.Connection):
    """Recharge les référentiels depuis les fichiers CSV."""
    import csv
    from pathlib import Path

    CORPUS_DIR = Path(__file__).parent.parent / 'corpus'
    cur = conn.cursor()

    # Lieux
    lieu_file = CORPUS_DIR / 'lieu.csv'
    if lieu_file.exists():
        with open(lieu_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO lieu_ref (nom, ville) VALUES (?, ?)",
                        (row['nom'], row.get('ville', 'Le Mans'))
                    )
                except Exception as e:
                    logger.debug(f"Erreur insertion lieu: {e}")
        conn.commit()
        count = cur.execute("SELECT COUNT(*) FROM lieu_ref").fetchone()[0]
        logger.info(f"Lieux dans référentiel: {count}")

    # Villes
    ville_file = CORPUS_DIR / 'ville.csv'
    if ville_file.exists():
        with open(ville_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO ville_ref (nom) VALUES (?)",
                        (row['nom'],)
                    )
                except Exception as e:
                    logger.debug(f"Erreur insertion ville: {e}")
        conn.commit()
        count = cur.execute("SELECT COUNT(*) FROM ville_ref").fetchone()[0]
        logger.info(f"Villes dans référentiel: {count}")


def renormalize_lieux(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Re-normalise tous les lieux.

    Utilise ville_raw pour le matching des lieux génériques
    (Salle des fêtes, Église, etc.) qui peuvent exister dans plusieurs villes.
    """
    cur = conn.cursor()
    db_path_str = str(DB_PATH)

    # Stats avant
    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_ref_id IS NOT NULL")
    before = cur.fetchone()[0]

    # Récupérer tous les événements avec lieu_raw ET ville_raw
    cur.execute("""
        SELECT id, lieu_raw, ville_raw FROM evenement
        WHERE lieu_raw IS NOT NULL AND lieu_raw != ''
    """)
    events = cur.fetchall()

    updated = 0
    newly_normalized = 0

    for evt_id, lieu_raw, ville_raw in events:
        # find_lieu_ref_id retourne (lieu_id, nom, ville)
        lieu_id, _, _ = find_lieu_ref_id(lieu_raw, db_path_str, ville_raw)
        if lieu_id:
            # Vérifier si c'est une nouvelle normalisation
            cur.execute("SELECT lieu_ref_id FROM evenement WHERE id = ?", (evt_id,))
            old_id = cur.fetchone()[0]

            if old_id != lieu_id:
                if not dry_run:
                    cur.execute(
                        "UPDATE evenement SET lieu_ref_id = ? WHERE id = ?",
                        (lieu_id, evt_id)
                    )
                updated += 1
                if old_id is None:
                    newly_normalized += 1

    if not dry_run:
        conn.commit()

    # Stats après
    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_ref_id IS NOT NULL")
    after = cur.fetchone()[0] if not dry_run else before + newly_normalized

    return {
        'before': before,
        'after': after,
        'updated': updated,
        'newly_normalized': newly_normalized,
    }


def renormalize_artistes(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Re-normalise tous les artistes dans contenu_evenement."""
    cur = conn.cursor()
    db_path_str = str(DB_PATH)

    # Stats avant
    cur.execute("SELECT COUNT(*) FROM contenu_evenement WHERE artiste_ref_id IS NOT NULL")
    before = cur.fetchone()[0]

    # Récupérer tous les contenus avec artiste
    cur.execute("""
        SELECT id, artiste FROM contenu_evenement
        WHERE artiste IS NOT NULL AND artiste != ''
    """)
    contenus = cur.fetchall()

    updated = 0
    newly_normalized = 0

    for ce_id, artiste in contenus:
        artiste_id, _ = find_artiste_ref_id(artiste, db_path_str)
        if artiste_id:
            # Vérifier si c'est une nouvelle normalisation
            cur.execute("SELECT artiste_ref_id FROM contenu_evenement WHERE id = ?", (ce_id,))
            old_id = cur.fetchone()[0]

            if old_id != artiste_id:
                if not dry_run:
                    cur.execute(
                        "UPDATE contenu_evenement SET artiste_ref_id = ? WHERE id = ?",
                        (artiste_id, ce_id)
                    )
                updated += 1
                if old_id is None:
                    newly_normalized += 1

    if not dry_run:
        conn.commit()

    # Stats après
    cur.execute("SELECT COUNT(*) FROM contenu_evenement WHERE artiste_ref_id IS NOT NULL")
    after = cur.fetchone()[0] if not dry_run else before + newly_normalized

    return {
        'before': before,
        'after': after,
        'updated': updated,
        'newly_normalized': newly_normalized,
    }


def renormalize_villes(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Re-normalise toutes les villes."""
    cur = conn.cursor()
    db_path_str = str(DB_PATH)

    # Stats avant
    cur.execute("SELECT COUNT(*) FROM evenement WHERE ville_ref_id IS NOT NULL")
    before = cur.fetchone()[0]

    # Récupérer tous les événements
    cur.execute("SELECT id, ville_raw FROM evenement")
    events = cur.fetchall()

    updated = 0
    newly_normalized = 0

    for evt_id, ville_raw in events:
        ville_id, ville_norm = normalize_ville(ville_raw, db_path_str)

        # Vérifier si mise à jour nécessaire
        cur.execute("SELECT ville_ref_id, ville_raw FROM evenement WHERE id = ?", (evt_id,))
        old_id, old_ville = cur.fetchone()

        if old_id != ville_id or old_ville != ville_norm:
            if not dry_run:
                cur.execute(
                    "UPDATE evenement SET ville_ref_id = ?, ville_raw = ? WHERE id = ?",
                    (ville_id, ville_norm, evt_id)
                )
            updated += 1
            if old_id is None and ville_id is not None:
                newly_normalized += 1

    if not dry_run:
        conn.commit()

    # Stats après
    cur.execute("SELECT COUNT(*) FROM evenement WHERE ville_ref_id IS NOT NULL")
    after = cur.fetchone()[0] if not dry_run else before + newly_normalized

    return {
        'before': before,
        'after': after,
        'updated': updated,
        'newly_normalized': newly_normalized,
    }


def show_stats(conn: sqlite3.Connection):
    """Affiche les statistiques de normalisation."""
    cur = conn.cursor()

    print("\n" + "="*60)
    print("STATISTIQUES DE NORMALISATION")
    print("="*60)

    # Lieux
    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_ref_id IS NOT NULL")
    lieu_norm = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_raw IS NOT NULL AND lieu_raw != ''")
    lieu_total = cur.fetchone()[0]
    if lieu_total > 0:
        print(f"Lieux normalisés: {lieu_norm:,}/{lieu_total:,} ({lieu_norm/lieu_total*100:.1f}%)")

    # Top lieux non normalisés
    print("\nTop 10 lieux non normalisés:")
    cur.execute("""
        SELECT lieu_raw, COUNT(*) as n
        FROM evenement
        WHERE lieu_raw IS NOT NULL AND lieu_ref_id IS NULL
        GROUP BY lieu_raw
        ORDER BY n DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(f"  {row[1]:4d}x {row[0]}")

    # Artistes
    cur.execute("SELECT COUNT(*) FROM contenu_evenement WHERE artiste_ref_id IS NOT NULL")
    art_norm = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM contenu_evenement WHERE artiste IS NOT NULL AND artiste != ''")
    art_total = cur.fetchone()[0]
    if art_total > 0:
        print(f"\nArtistes normalisés: {art_norm:,}/{art_total:,} ({art_norm/art_total*100:.1f}%)")

    # Villes
    cur.execute("SELECT COUNT(*) FROM evenement WHERE ville_ref_id IS NOT NULL")
    ville_norm = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM evenement")
    ville_total = cur.fetchone()[0]
    if ville_total > 0:
        print(f"Villes normalisées: {ville_norm:,}/{ville_total:,} ({ville_norm/ville_total*100:.1f}%)")


def main(dry_run: bool = False, lieux: bool = True, artistes: bool = True, villes: bool = True):
    logger.info("="*60)
    logger.info("RE-NORMALISATION")
    if dry_run:
        logger.info(">>> MODE DRY RUN <<<")
    logger.info("="*60)

    # Vider les caches pour utiliser les dernières règles de normalisation
    clear_caches()
    logger.info("Caches de normalisation vidés")

    conn = sqlite3.connect(DB_PATH)

    try:
        # Recharger les référentiels d'abord
        logger.info("\n1. Rechargement des référentiels...")
        reload_referentiels(conn)

        if lieux:
            logger.info("\n2. Re-normalisation des lieux...")
            stats = renormalize_lieux(conn, dry_run)
            logger.info(f"  Avant: {stats['before']:,} normalisés")
            logger.info(f"  Après: {stats['after']:,} normalisés (+{stats['newly_normalized']})")
            logger.info(f"  Mis à jour: {stats['updated']}")

        if artistes:
            logger.info("\n3. Re-normalisation des artistes...")
            stats = renormalize_artistes(conn, dry_run)
            logger.info(f"  Avant: {stats['before']:,} normalisés")
            logger.info(f"  Après: {stats['after']:,} normalisés (+{stats['newly_normalized']})")
            logger.info(f"  Mis à jour: {stats['updated']}")

        if villes:
            logger.info("\n4. Re-normalisation des villes...")
            stats = renormalize_villes(conn, dry_run)
            logger.info(f"  Avant: {stats['before']:,} normalisés")
            logger.info(f"  Après: {stats['after']:,} normalisés (+{stats['newly_normalized']})")
            logger.info(f"  Mis à jour: {stats['updated']}")

        if not dry_run:
            show_stats(conn)

    finally:
        conn.close()

    logger.info("\n✓ Re-normalisation terminée")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Re-normalisation des données')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Simule sans modifier')
    parser.add_argument('--lieux-only', action='store_true',
                        help='Re-normaliser uniquement les lieux')
    parser.add_argument('--artistes-only', action='store_true',
                        help='Re-normaliser uniquement les artistes')
    parser.add_argument('--villes-only', action='store_true',
                        help='Re-normaliser uniquement les villes')

    args = parser.parse_args()

    # Par défaut tout, sinon ce qui est demandé
    if args.lieux_only or args.artistes_only or args.villes_only:
        main(
            dry_run=args.dry_run,
            lieux=args.lieux_only,
            artistes=args.artistes_only,
            villes=args.villes_only
        )
    else:
        main(dry_run=args.dry_run)

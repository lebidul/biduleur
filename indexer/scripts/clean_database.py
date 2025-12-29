#!/usr/bin/env python3
"""
Nettoyage de la base de données existante.

Actions:
1. Supprimer les faux événements (raw_text trop court, infos/annonces)
2. Supprimer les événements sans contenu utile
3. Nettoyer les artistes suspects dans contenu_evenement
4. Mettre à jour les statistiques
"""

import sqlite3
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'

# Patterns indiquant une info/annonce plutôt qu'un événement
INFO_PATTERNS = [
    r'\brens\.\s',
    r'\bcontact\s*:',
    r'\bwww\.',
    r'\bhttps?://',
    r'\binscription',
    r'\+ d\'infos',
    r'\bdans divers lieux\b',
    r'\bplus d\'infos\b',
    r'\bréservation\b',
]

# Patterns d'artistes invalides
INVALID_ARTISTE_PATTERNS = [
    r'^\d{1,2}h\d{0,2}$',           # Juste une heure "21h"
    r',\s*\d{1,2}h',                 # Contient ", 21h"
    r'\d+\s*€',                      # Contient un prix
    r'\bgratuit\b',                  # Contient "gratuit"
    r'\bLe Mans\b.*,',               # "Le Mans," dans l'artiste
    r'^[A-Z]{1,2}$',                 # 1-2 lettres majuscules seulement
    r'^\.\.\.*$',                    # Juste des points
    r'^\s*$',                        # Vide
    r'^\d+F$',                       # Prix en francs (30F, 60F)
    r'^\d+h\d*$',                    # Heure seule
]


def clean_false_events(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Supprime les faux événements."""
    cur = conn.cursor()

    # 1. Événements avec raw_text trop court
    cur.execute("""
        SELECT id, raw_text_clean FROM evenement
        WHERE LENGTH(COALESCE(raw_text_clean, '')) < 15
    """)
    short_events = cur.fetchall()
    short_ids = [row[0] for row in short_events]
    logger.info(f"Événements avec raw_text < 15 chars: {len(short_ids)}")
    if short_events[:5]:
        for evt_id, text in short_events[:5]:
            logger.info(f"  Exemple: [{evt_id}] '{text}'")

    # 2. Événements qui sont des infos/annonces
    info_ids = []
    cur.execute("SELECT id, raw_text_clean FROM evenement WHERE raw_text_clean IS NOT NULL")
    for row in cur.fetchall():
        evt_id, text = row
        if text:
            text_lower = text.lower()
            for pattern in INFO_PATTERNS:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    info_ids.append(evt_id)
                    break
    logger.info(f"Événements info/annonces détectés: {len(info_ids)}")

    # 3. Événements sans lieu ET sans artiste dans contenu_evenement
    cur.execute("""
        SELECT e.id FROM evenement e
        WHERE (e.lieu_raw IS NULL OR e.lieu_raw = '')
          AND NOT EXISTS (
              SELECT 1 FROM contenu_evenement ce
              WHERE ce.evenement_id = e.id AND ce.artiste IS NOT NULL
          )
    """)
    empty_ids = [row[0] for row in cur.fetchall()]
    logger.info(f"Événements sans lieu ni artiste: {len(empty_ids)}")

    # Combiner et dédupliquer
    all_ids = list(set(short_ids + info_ids + empty_ids))
    logger.info(f"Total à supprimer: {len(all_ids)}")

    if dry_run:
        logger.info("[DRY RUN] Aucune suppression effectuée")
        return len(all_ids)

    if all_ids:
        # Supprimer d'abord les contenu_evenement associés
        placeholders = ','.join('?' * len(all_ids))
        cur.execute(f"DELETE FROM contenu_evenement WHERE evenement_id IN ({placeholders})", all_ids)
        deleted_contenu = cur.rowcount

        # Puis les événements
        cur.execute(f"DELETE FROM evenement WHERE id IN ({placeholders})", all_ids)
        deleted_events = cur.rowcount

        conn.commit()
        logger.info(f"✓ Supprimé: {deleted_events} événements, {deleted_contenu} contenu_evenement")
        return deleted_events

    return 0


def clean_invalid_artistes(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Nettoie les artistes invalides dans contenu_evenement."""
    cur = conn.cursor()

    cur.execute("SELECT id, artiste FROM contenu_evenement WHERE artiste IS NOT NULL")
    rows = cur.fetchall()

    invalid_entries = []
    for row in rows:
        ce_id, artiste = row
        if not artiste:
            continue
        # Vérifier longueur
        if len(artiste.strip()) < 2:
            invalid_entries.append((ce_id, artiste, "trop court"))
            continue
        # Vérifier patterns
        for pattern in INVALID_ARTISTE_PATTERNS:
            if re.search(pattern, artiste, re.IGNORECASE):
                invalid_entries.append((ce_id, artiste, pattern))
                break

    logger.info(f"Artistes invalides détectés: {len(invalid_entries)}")
    for ce_id, artiste, reason in invalid_entries[:10]:
        logger.info(f"  [{ce_id}] '{artiste}' ({reason})")

    if dry_run:
        logger.info("[DRY RUN] Aucune modification effectuée")
        return len(invalid_entries)

    if invalid_entries:
        invalid_ids = [e[0] for e in invalid_entries]
        placeholders = ','.join('?' * len(invalid_ids))
        cur.execute(f"""
            UPDATE contenu_evenement
            SET artiste = NULL
            WHERE id IN ({placeholders})
        """, invalid_ids)
        conn.commit()
        logger.info(f"✓ Artistes mis à NULL: {cur.rowcount}")
        return cur.rowcount

    return 0


def clean_orphan_contenu(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Supprime les contenu_evenement sans artiste ni spectacle."""
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM contenu_evenement
        WHERE artiste IS NULL AND nom_spectacle IS NULL
    """)
    count = cur.fetchone()[0]
    logger.info(f"contenu_evenement orphelins (sans artiste ni spectacle): {count}")

    if dry_run:
        logger.info("[DRY RUN] Aucune suppression effectuée")
        return count

    cur.execute("""
        DELETE FROM contenu_evenement
        WHERE artiste IS NULL AND nom_spectacle IS NULL
    """)
    deleted = cur.rowcount
    conn.commit()

    logger.info(f"✓ Supprimé: {deleted} contenu_evenement orphelins")
    return deleted


def show_stats(conn: sqlite3.Connection):
    """Affiche les statistiques après nettoyage."""
    cur = conn.cursor()

    print("\n" + "="*60)
    print("STATISTIQUES APRÈS NETTOYAGE")
    print("="*60)

    cur.execute("SELECT COUNT(*) FROM evenement")
    print(f"Événements: {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(*) FROM contenu_evenement")
    print(f"contenu_evenement: {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(DISTINCT artiste) FROM contenu_evenement WHERE artiste IS NOT NULL")
    print(f"Artistes distincts: {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_ref_id IS NOT NULL")
    lieu_norm = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_raw IS NOT NULL")
    lieu_total = cur.fetchone()[0]
    if lieu_total > 0:
        print(f"Lieux normalisés: {lieu_norm:,}/{lieu_total:,} ({lieu_norm/lieu_total*100:.1f}%)")

    cur.execute("SELECT COUNT(*) FROM evenement WHERE ville_ref_id IS NOT NULL")
    ville_norm = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM evenement WHERE ville_raw IS NOT NULL")
    ville_total = cur.fetchone()[0]
    if ville_total > 0:
        print(f"Villes normalisées: {ville_norm:,}/{ville_total:,} ({ville_norm/ville_total*100:.1f}%)")


def main(dry_run: bool = False):
    logger.info("="*60)
    logger.info("NETTOYAGE DE LA BASE DE DONNÉES")
    if dry_run:
        logger.info(">>> MODE DRY RUN - Aucune modification <<<")
    logger.info("="*60)

    conn = sqlite3.connect(DB_PATH)

    try:
        logger.info("\n1. Suppression des faux événements...")
        clean_false_events(conn, dry_run)

        logger.info("\n2. Nettoyage des artistes invalides...")
        clean_invalid_artistes(conn, dry_run)

        logger.info("\n3. Suppression des contenu_evenement orphelins...")
        clean_orphan_contenu(conn, dry_run)

        if not dry_run:
            show_stats(conn)

    finally:
        conn.close()

    logger.info("\n✓ Nettoyage terminé")


if __name__ == '__main__':
    import sys
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    main(dry_run=dry_run)

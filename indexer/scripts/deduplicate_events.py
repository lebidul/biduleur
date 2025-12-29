#!/usr/bin/env python3
"""
Déduplication des événements.

Stratégie:
1. Identifier les doublons par signature (date + lieu + raw_text normalisé)
2. Garder l'événement avec le plus de contenu (artistes, spectacles)
3. Supprimer les autres
"""

import sqlite3
import logging
import re
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def normalize_for_dedup(text: str) -> str:
    """Normalise le texte pour la déduplication."""
    if not text:
        return ""
    # Lowercase, supprimer ponctuation, normaliser espaces
    s = text.lower()
    s = re.sub(r'[^\w\s]', ' ', s)
    s = ' '.join(s.split())
    return s


def find_duplicates(conn: sqlite3.Connection) -> dict:
    """
    Trouve les groupes de doublons.
    Returns: {signature: [event_ids]}
    """
    cur = conn.cursor()

    # Récupérer tous les événements avec leur contenu
    cur.execute("""
        SELECT e.id, e.date_evenement, e.lieu_raw, e.raw_text_clean,
               COUNT(ce.id) as contenu_count
        FROM evenement e
        LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
        WHERE e.raw_text_clean IS NOT NULL
        GROUP BY e.id
    """)

    # Grouper par signature
    groups = defaultdict(list)
    for row in cur.fetchall():
        evt_id, date_evt, lieu, raw_text, contenu_count = row
        # Signature = date + lieu normalisé + premiers mots du raw_text
        raw_norm = normalize_for_dedup(raw_text)[:100]  # Premiers 100 chars normalisés
        lieu_norm = normalize_for_dedup(lieu or '')
        signature = f"{date_evt}|{lieu_norm}|{raw_norm}"
        groups[signature].append((evt_id, contenu_count, len(raw_text or '')))

    # Garder seulement les groupes avec doublons
    duplicates = {sig: evts for sig, evts in groups.items() if len(evts) > 1}

    return duplicates


def deduplicate(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """
    Supprime les doublons, garde celui avec le plus de contenu.
    """
    cur = conn.cursor()
    duplicates = find_duplicates(conn)

    logger.info(f"Groupes de doublons trouvés: {len(duplicates)}")

    total_duplicates = sum(len(evts) - 1 for evts in duplicates.values())
    logger.info(f"Événements en double à supprimer: {total_duplicates}")

    if dry_run:
        # Afficher quelques exemples
        for sig, evts in list(duplicates.items())[:5]:
            logger.info(f"  Signature: {sig[:80]}...")
            for evt_id, contenu_count, raw_len in evts:
                logger.info(f"    [{evt_id}] contenu={contenu_count}, len={raw_len}")
        logger.info("[DRY RUN] Aucune suppression effectuée")
        return total_duplicates

    ids_to_delete = []
    for sig, evts in duplicates.items():
        # Trier: garder celui avec le plus de contenu, puis le plus long raw_text
        evts_sorted = sorted(evts, key=lambda x: (-x[1], -x[2]))
        keep_id = evts_sorted[0][0]
        delete_ids = [e[0] for e in evts_sorted[1:]]
        ids_to_delete.extend(delete_ids)

    if ids_to_delete:
        # Supprimer les contenu_evenement
        placeholders = ','.join('?' * len(ids_to_delete))
        cur.execute(f"DELETE FROM contenu_evenement WHERE evenement_id IN ({placeholders})", ids_to_delete)
        deleted_contenu = cur.rowcount

        # Supprimer les événements
        cur.execute(f"DELETE FROM evenement WHERE id IN ({placeholders})", ids_to_delete)
        deleted_events = cur.rowcount

        conn.commit()
        logger.info(f"✓ Supprimé: {deleted_events} événements, {deleted_contenu} contenu_evenement")
        return deleted_events

    return 0


def find_exact_duplicates(conn: sqlite3.Connection) -> dict:
    """
    Trouve les événements avec raw_text_clean identique.
    Plus strict que find_duplicates.
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT raw_text_clean, GROUP_CONCAT(id) as ids, COUNT(*) as count
        FROM evenement
        WHERE raw_text_clean IS NOT NULL AND raw_text_clean != ''
        GROUP BY raw_text_clean
        HAVING count > 1
        ORDER BY count DESC
    """)

    exact_dups = {}
    for row in cur.fetchall():
        raw_text, ids_str, count = row
        ids = [int(i) for i in ids_str.split(',')]
        exact_dups[raw_text[:100]] = ids

    return exact_dups


def main(dry_run: bool = False, exact: bool = False):
    logger.info("="*60)
    logger.info("DÉDUPLICATION DES ÉVÉNEMENTS")
    if dry_run:
        logger.info(">>> MODE DRY RUN <<<")
    logger.info("="*60)

    conn = sqlite3.connect(DB_PATH)
    try:
        if exact:
            logger.info("\nRecherche des doublons exacts (raw_text identique)...")
            exact_dups = find_exact_duplicates(conn)
            logger.info(f"Groupes de doublons exacts: {len(exact_dups)}")
            for text, ids in list(exact_dups.items())[:10]:
                logger.info(f"  '{text[:60]}...' -> {len(ids)} doublons")
        else:
            deduplicate(conn, dry_run)
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    exact = '--exact' in sys.argv or '-e' in sys.argv
    main(dry_run=dry_run, exact=exact)

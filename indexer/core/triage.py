"""Triage automatique des événements par niveau de confiance"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"


def triage_all(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, int]:
    """
    Classe tous les événements par review_status.

    Règles:
    - 'ok' : confidence >= 0.9 ET lieu_ref_id NOT NULL ET date_evenement NOT NULL
    - 'to_review' : 0.7 <= confidence < 0.9 OU lieu_ref_id IS NULL
    - 'flagged' : confidence < 0.7 OU champs critiques manquants
    """
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Reset pending
    cur.execute("UPDATE evenement SET review_status = 'pending' WHERE verified = FALSE OR verified = 0")

    # OK
    cur.execute('''
        UPDATE evenement SET review_status = 'ok'
        WHERE confidence >= 0.9
          AND lieu_ref_id IS NOT NULL
          AND date_evenement IS NOT NULL
          AND (verified = FALSE OR verified = 0)
    ''')
    ok_count = cur.rowcount

    # TO_REVIEW
    cur.execute('''
        UPDATE evenement SET review_status = 'to_review'
        WHERE ((confidence >= 0.7 AND confidence < 0.9)
           OR (lieu_ref_id IS NULL AND lieu_raw IS NOT NULL))
          AND (verified = FALSE OR verified = 0)
          AND review_status = 'pending'
    ''')
    review_count = cur.rowcount

    # FLAGGED
    cur.execute('''
        UPDATE evenement SET review_status = 'flagged'
        WHERE (confidence < 0.7
           OR date_evenement IS NULL
           OR (lieu_raw IS NULL AND artistes IS NULL AND spectacles IS NULL))
          AND (verified = FALSE OR verified = 0)
          AND review_status = 'pending'
    ''')
    flagged_count = cur.rowcount

    conn.commit()
    conn.close()

    return {'ok': ok_count, 'to_review': review_count, 'flagged': flagged_count}


def detect_duplicates(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Détecte et flag les doublons potentiels"""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute('''
        SELECT e1.id, e2.id
        FROM evenement e1
        JOIN evenement e2 ON e1.date_evenement = e2.date_evenement
                         AND e1.lieu_ref_id = e2.lieu_ref_id
                         AND e1.id < e2.id
                         AND e1.bidul_numero = e2.bidul_numero
        WHERE e1.lieu_ref_id IS NOT NULL
    ''')

    duplicates = cur.fetchall()

    for dup in duplicates:
        cur.execute('''
            UPDATE evenement
            SET review_status = 'flagged',
                review_notes = COALESCE(review_notes || '; ', '') || 'Doublon potentiel avec id=' || ?
            WHERE id = ?
        ''', (dup[0], dup[1]))

    conn.commit()
    conn.close()
    return len(duplicates)


def get_triage_stats(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, int]:
    """Stats de triage"""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute('SELECT review_status, COUNT(*) FROM evenement GROUP BY review_status')
    stats = {row[0] or 'pending': row[1] for row in cur.fetchall()}

    cur.execute('SELECT COUNT(*) FROM evenement WHERE verified = TRUE OR verified = 1')
    stats['verified'] = cur.fetchone()[0]

    conn.close()
    return stats

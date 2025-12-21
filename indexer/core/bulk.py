"""Corrections en masse avec tracking"""

import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"


class BulkCorrector:
    """Gestionnaire de corrections en masse avec logging."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

    def log_bulk_correction(
        self,
        event_ids: list[int],
        type_correction: str,
        champ: str,
        avant: str | None,
        apres: str | None,
        notes: str = ''
    ):
        """Logge une correction bulk dans correction_log."""
        if not event_ids:
            return
        for eid in event_ids:
            if eid is not None:
                self.cur.execute('''
                    INSERT INTO correction_log (evenement_id, champ, ancienne_valeur, nouvelle_valeur, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    eid,
                    champ,
                    str(avant) if avant else None,
                    str(apres) if apres else None,
                    f'bulk_{type_correction}' + (f': {notes}' if notes else ''),
                    datetime.now().isoformat()
                ))
        self.conn.commit()

    # ========== LIEU ==========

    def list_unmatched_lieux(self, min_count: int = 1) -> list:
        """Liste les lieux non matchés avec leur fréquence."""
        self.cur.execute('''
            SELECT lieu_raw, COUNT(*) as n
            FROM evenement
            WHERE lieu_ref_id IS NULL AND lieu_raw IS NOT NULL AND review_status != 'deleted'
            GROUP BY lieu_raw HAVING n >= ?
            ORDER BY n DESC
        ''', (min_count,))
        return self.cur.fetchall()

    def bulk_match_lieu(self, lieu_raw: str, lieu_ref_id: int, dry_run: bool = False) -> int:
        """Matche tous les événements avec ce lieu_raw vers lieu_ref_id."""
        self.cur.execute('''
            SELECT id FROM evenement
            WHERE lieu_raw = ? AND lieu_ref_id IS NULL AND review_status != 'deleted'
        ''', (lieu_raw,))
        event_ids = [row[0] for row in self.cur.fetchall()]

        if not event_ids:
            print(f"Aucun événement trouvé avec lieu_raw='{lieu_raw}'")
            return 0

        self.cur.execute('SELECT nom FROM lieu_ref WHERE id = ?', (lieu_ref_id,))
        row = self.cur.fetchone()
        lieu_nom = row[0] if row else f"id={lieu_ref_id}"

        if dry_run:
            print(f"[DRY-RUN] Matcherait {len(event_ids)} événements: '{lieu_raw}' -> '{lieu_nom}'")
            return len(event_ids)

        self.cur.execute('''
            UPDATE evenement SET lieu_ref_id = ?
            WHERE lieu_raw = ? AND lieu_ref_id IS NULL AND review_status != 'deleted'
        ''', (lieu_ref_id, lieu_raw))

        self.log_bulk_correction(event_ids, 'match_lieu', 'lieu_ref_id', lieu_raw, lieu_nom)
        self.conn.commit()
        return len(event_ids)

    def bulk_add_lieu_to_ref(self, lieu_nom: str, ville: str = 'Le Mans') -> tuple[int, int]:
        """Ajoute un lieu au référentiel et matche les événements correspondants."""
        self.cur.execute('INSERT INTO lieu_ref (nom, ville) VALUES (?, ?)', (lieu_nom, ville))
        lieu_ref_id = self.cur.lastrowid
        self.conn.commit()
        count = self.bulk_match_lieu(lieu_nom, lieu_ref_id)
        return lieu_ref_id, count

    def search_lieu_ref(self, query: str) -> list:
        """Recherche dans le référentiel des lieux."""
        self.cur.execute('''
            SELECT id, nom, ville FROM lieu_ref WHERE nom LIKE ? ORDER BY nom LIMIT 20
        ''', (f'%{query}%',))
        return self.cur.fetchall()

    # ========== ARTISTES (nouvelle table contenu_evenement) ==========

    def list_artistes(self, min_count: int = 1) -> list:
        """Liste les artistes par fréquence (depuis contenu_evenement)."""
        self.cur.execute('''
            SELECT artiste, COUNT(*) as n
            FROM contenu_evenement
            WHERE artiste IS NOT NULL AND artiste != ''
            GROUP BY artiste HAVING n >= ?
            ORDER BY n DESC
        ''', (min_count,))
        return self.cur.fetchall()

    def list_styles(self, min_count: int = 1) -> list:
        """Liste les styles par fréquence."""
        self.cur.execute('''
            SELECT style, COUNT(*) as n
            FROM contenu_evenement
            WHERE style IS NOT NULL AND style != ''
            GROUP BY style HAVING n >= ?
            ORDER BY n DESC
        ''', (min_count,))
        return self.cur.fetchall()

    def bulk_rename_artiste(self, old_name: str, new_name: str, dry_run: bool = False) -> int:
        """Renomme un artiste dans contenu_evenement et crée un alias."""
        self.cur.execute('SELECT id, evenement_id FROM contenu_evenement WHERE artiste = ?', (old_name,))
        rows = self.cur.fetchall()

        if not rows:
            print(f"Aucun artiste trouvé avec nom='{old_name}'")
            return 0

        if dry_run:
            print(f"[DRY-RUN] Renommerait '{old_name}' -> '{new_name}' dans {len(rows)} contenus")
            return len(rows)

        self.cur.execute('UPDATE contenu_evenement SET artiste = ? WHERE artiste = ?', (new_name, old_name))

        # Ajouter alias
        self.cur.execute(
            'INSERT OR IGNORE INTO artiste_alias (nom_variante, nom_normalise) VALUES (?, ?)',
            (old_name, new_name)
        )

        event_ids = list(set([r[1] for r in rows]))
        self.log_bulk_correction(event_ids, 'rename_artiste', 'artiste', old_name, new_name)

        self.conn.commit()
        return len(rows)

    def bulk_rename_style(self, old_style: str, new_style: str, dry_run: bool = False) -> int:
        """Renomme un style dans contenu_evenement."""
        self.cur.execute('SELECT id FROM contenu_evenement WHERE style = ?', (old_style,))
        rows = self.cur.fetchall()

        if not rows:
            print(f"Aucun style trouvé: '{old_style}'")
            return 0

        if dry_run:
            print(f"[DRY-RUN] Renommerait style '{old_style}' -> '{new_style}' dans {len(rows)} contenus")
            return len(rows)

        self.cur.execute('UPDATE contenu_evenement SET style = ? WHERE style = ?', (new_style, old_style))
        self.conn.commit()
        return len(rows)

    # ========== VALIDATION / SUPPRESSION ==========

    def bulk_validate_by_status(self, status: str = 'ok', dry_run: bool = False) -> int:
        """Valide tous les événements avec ce review_status."""
        self.cur.execute('SELECT id FROM evenement WHERE review_status = ? AND (verified = FALSE OR verified = 0)', (status,))
        event_ids = [row[0] for row in self.cur.fetchall()]

        if not event_ids:
            print(f"Aucun événement à valider avec status='{status}'")
            return 0

        if dry_run:
            print(f"[DRY-RUN] Validerait {len(event_ids)} événements status='{status}'")
            return len(event_ids)

        self.cur.execute('''
            UPDATE evenement SET verified = TRUE, verified_by = 'bulk', verified_at = ?
            WHERE review_status = ? AND (verified = FALSE OR verified = 0)
        ''', (datetime.now().isoformat(), status))

        self.log_bulk_correction(event_ids, 'validate', 'verified', 'FALSE', 'TRUE')
        self.conn.commit()
        return len(event_ids)

    def bulk_delete_by_pattern(self, pattern: str, field: str = 'raw_text', dry_run: bool = False) -> int:
        """Marque comme 'deleted' les événements matchant un pattern."""
        self.cur.execute(f'''
            SELECT id, {field} FROM evenement
            WHERE {field} LIKE ? AND review_status != 'deleted'
        ''', (f'%{pattern}%',))
        rows = self.cur.fetchall()

        if not rows:
            print(f"Aucun événement trouvé avec pattern '{pattern}'")
            return 0

        if dry_run:
            print(f"[DRY-RUN] Supprimerait {len(rows)} événements matchant '{pattern}'")
            for row in rows[:5]:
                print(f"  - [{row[0]}] {str(row[1])[:60]}...")
            if len(rows) > 5:
                print(f"  ... et {len(rows)-5} autres")
            return len(rows)

        event_ids = [row[0] for row in rows]
        self.cur.execute(f'''
            UPDATE evenement SET review_status = 'deleted', review_notes = ?
            WHERE {field} LIKE ? AND review_status != 'deleted'
        ''', (f'Bulk delete: pattern={pattern}', f'%{pattern}%'))

        self.log_bulk_correction(event_ids, 'delete', field, pattern, 'deleted')
        self.conn.commit()
        return len(event_ids)

    def bulk_delete_by_confidence(self, max_confidence: float = 0.5, dry_run: bool = False) -> int:
        """Marque comme 'deleted' les événements avec confidence très basse."""
        self.cur.execute(
            'SELECT id FROM evenement WHERE confidence <= ? AND review_status != "deleted"',
            (max_confidence,)
        )
        event_ids = [row[0] for row in self.cur.fetchall()]

        if not event_ids:
            print(f"Aucun événement avec confidence <= {max_confidence}")
            return 0

        if dry_run:
            print(f"[DRY-RUN] Supprimerait {len(event_ids)} événements confidence <= {max_confidence}")
            return len(event_ids)

        self.cur.execute('''
            UPDATE evenement SET review_status = 'deleted', review_notes = ?
            WHERE confidence <= ? AND review_status != 'deleted'
        ''', (f'Bulk delete: confidence <= {max_confidence}', max_confidence))

        self.log_bulk_correction(event_ids, 'delete', 'confidence', f'<= {max_confidence}', 'deleted')
        self.conn.commit()
        return len(event_ids)

    def bulk_set_default_ville(self, dry_run: bool = False) -> int:
        """Met 'Le Mans' pour les événements sans ville."""
        self.cur.execute('''
            SELECT id FROM evenement
            WHERE (ville_raw IS NULL OR ville_raw = '') AND review_status != 'deleted'
        ''')
        event_ids = [row[0] for row in self.cur.fetchall()]

        if not event_ids:
            print("Aucun événement sans ville")
            return 0

        if dry_run:
            print(f"[DRY-RUN] Mettrait 'Le Mans' pour {len(event_ids)} événements")
            return len(event_ids)

        self.cur.execute('''
            UPDATE evenement SET ville_raw = 'Le Mans'
            WHERE (ville_raw IS NULL OR ville_raw = '') AND review_status != 'deleted'
        ''')

        self.log_bulk_correction(event_ids, 'set_ville', 'ville_raw', None, 'Le Mans')
        self.conn.commit()
        return len(event_ids)

    def close(self):
        """Ferme la connexion."""
        self.conn.close()

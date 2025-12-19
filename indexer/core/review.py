"""Interface de review interactive"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .aliases import normalize_artiste, load_artiste_aliases, add_artiste_alias

DEFAULT_DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"


class ReviewSession:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH, filters: dict | None = None):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self.reviewed_count = 0
        self.artiste_aliases = load_artiste_aliases(db_path)
        self.filters = filters or {}
        self.status_filter = self.filters.get('status', 'to_review')
        self.bidul_filter = self.filters.get('bidul_numero')

    def get_events_to_review(self, status: str = 'flagged', limit: int = 100, bidul_numero: Optional[int] = None) -> list:
        query = '''
            SELECT e.*, b.mois, b.annee, l.nom as lieu_nom
            FROM evenement e
            LEFT JOIN bidul b ON e.bidul_numero = b.numero
            LEFT JOIN lieu_ref l ON e.lieu_ref_id = l.id
            WHERE e.review_status = ? AND (e.verified = FALSE OR e.verified = 0)
        '''
        params: list = [status]
        if bidul_numero:
            query += ' AND e.bidul_numero = ?'
            params.append(bidul_numero)
        query += ' ORDER BY e.confidence ASC LIMIT ?'
        params.append(limit)
        self.cur.execute(query, params)
        return self.cur.fetchall()

    def get_events_no_lieu(self, limit: int = 100) -> list:
        self.cur.execute('''
            SELECT e.*, b.mois, b.annee
            FROM evenement e
            LEFT JOIN bidul b ON e.bidul_numero = b.numero
            WHERE e.lieu_ref_id IS NULL AND e.lieu_raw IS NOT NULL AND (e.verified = FALSE OR e.verified = 0)
            ORDER BY e.lieu_raw LIMIT ?
        ''', (limit,))
        return self.cur.fetchall()

    def get_random_sample(self, n: int = 20) -> list:
        self.cur.execute('''
            SELECT e.*, b.mois, b.annee, l.nom as lieu_nom
            FROM evenement e
            LEFT JOIN bidul b ON e.bidul_numero = b.numero
            LEFT JOIN lieu_ref l ON e.lieu_ref_id = l.id
            WHERE (e.verified = FALSE OR e.verified = 0)
            ORDER BY RANDOM() LIMIT ?
        ''', (n,))
        return self.cur.fetchall()

    def display_event(self, event: sqlite3.Row):
        print("\n" + "=" * 70)
        print(f" EVENT #{event['id']} (Bidul {event['bidul_numero']})")
        print("=" * 70)
        print(f"\nRAW: {event['raw_text']}")
        print(f"\nPARSED:")

        # Nom de l'événement
        print(f"  Nom:        {event['nom'] or 'N/A'}")

        spectacles = json.loads(event['spectacles']) if event['spectacles'] else []
        artistes = json.loads(event['artistes']) if event['artistes'] else []

        print(f"  Spectacles: {spectacles}")
        print(f"  Artistes:   {artistes}")

        # Style/genre
        style = event['style'] if 'style' in event.keys() else None
        print(f"  Style:      {style or 'N/A'}")

        lieu_status = "+" if event['lieu_ref_id'] else "x"
        lieu_nom = event['lieu_nom'] if 'lieu_nom' in event.keys() else None
        print(f"  Lieu:       {event['lieu_raw']} -> {lieu_nom or 'N/A'} {lieu_status}")
        print(f"  Ville:      {event['ville_raw'] or 'N/A'}")
        print(f"  Date:       {event['date_evenement']} | Heure: {event['heure']}")
        print(f"  Prix:       {event['tarif_raw']} {'(gratuit)' if event['gratuit'] else ''}")
        print(f"  Confidence: {event['confidence']:.2f}")

        if event['review_notes']:
            print(f"\n!! NOTES: {event['review_notes']}")
        print("-" * 70)

    def validate(self, event_id: int, reviewer: str = 'cli'):
        self.cur.execute('''
            UPDATE evenement
            SET verified = TRUE, verified_by = ?, verified_at = ?, review_status = 'ok'
            WHERE id = ?
        ''', (reviewer, datetime.now().isoformat(), event_id))
        self.conn.commit()
        self.reviewed_count += 1

    def flag(self, event_id: int, note: str = ''):
        self.cur.execute('''
            UPDATE evenement
            SET review_status = 'flagged',
                review_notes = COALESCE(review_notes || '; ', '') || ?
            WHERE id = ?
        ''', (note, event_id))
        self.conn.commit()

    def delete(self, event_id: int, reason: str = ''):
        self.log_correction(event_id, 'delete', 'event', None, 'deleted', reason)
        self.cur.execute('''
            UPDATE evenement SET review_status = 'deleted', review_notes = ?
            WHERE id = ?
        ''', (f'Supprime: {reason}', event_id))
        self.conn.commit()

    def update_field(self, event_id: int, field: str, old_value, new_value):
        self.log_correction(event_id, 'edit', field, old_value, new_value)
        self.cur.execute(f'UPDATE evenement SET {field} = ? WHERE id = ?', (new_value, event_id))
        self.conn.commit()

    def log_correction(self, event_id: Optional[int], type_correction: str, champ: str, avant, apres, notes: str = ''):
        self.cur.execute('''
            INSERT INTO correction_log (evenement_id, champ, ancienne_valeur, nouvelle_valeur, source)
            VALUES (?, ?, ?, ?, ?)
        ''', (event_id, champ, str(avant) if avant else None, str(apres) if apres else None, type_correction))
        self.conn.commit()

    def search_lieu(self, query: str) -> list:
        self.cur.execute('SELECT id, nom FROM lieu_ref WHERE nom LIKE ? ORDER BY nom LIMIT 10', (f'%{query}%',))
        return self.cur.fetchall()

    def match_lieu(self, event_id: int, lieu_ref_id: int):
        self.cur.execute('SELECT lieu_raw, lieu_ref_id FROM evenement WHERE id = ?', (event_id,))
        old = self.cur.fetchone()
        self.cur.execute('SELECT nom FROM lieu_ref WHERE id = ?', (lieu_ref_id,))
        lieu_nom = self.cur.fetchone()[0]
        self.log_correction(event_id, 'match', 'lieu_ref_id', old[1], lieu_ref_id, f'{old[0]} -> {lieu_nom}')
        self.cur.execute('UPDATE evenement SET lieu_ref_id = ? WHERE id = ?', (lieu_ref_id, event_id))
        self.conn.commit()

    def add_artiste_alias_interactive(self, variante: str, normalise: str):
        """Ajoute un alias artiste et l'applique"""
        add_artiste_alias(variante, normalise, self.db_path)
        self.artiste_aliases[variante] = normalise
        self.log_correction(None, 'alias', 'artiste', variante, normalise)
        print(f"Alias ajoute: '{variante}' -> '{normalise}'")

    def split_event(self, event_id: int, new_events_data: list[dict]) -> list[int]:
        """Split un événement en plusieurs"""
        self.cur.execute('SELECT * FROM evenement WHERE id = ?', (event_id,))
        row = self.cur.fetchone()
        original = {key: row[key] for key in row.keys()}

        self.log_correction(event_id, 'split', 'event', original['raw_text'], f'Split en {len(new_events_data)} evenements')
        self.cur.execute("UPDATE evenement SET review_status = 'deleted', review_notes = 'Splitte' WHERE id = ?", (event_id,))

        new_ids = []
        for data in new_events_data:
            new_event = {**original, **data}
            del new_event['id']
            new_event['verified'] = True
            new_event['verified_at'] = datetime.now().isoformat()
            new_event['review_status'] = 'ok'
            new_event['review_notes'] = f'Cree par split de #{event_id}'

            cols = ', '.join(new_event.keys())
            placeholders = ', '.join(['?' for _ in new_event])
            self.cur.execute(f'INSERT INTO evenement ({cols}) VALUES ({placeholders})', list(new_event.values()))
            new_ids.append(self.cur.lastrowid)

        self.conn.commit()
        return new_ids

    def close(self):
        self.conn.close()
        print(f"\nSession: {self.reviewed_count} evenements reviewes.")

    def start(self):
        """Lance la session de review interactive."""
        print(f"\n{'='*60}")
        print(f"SESSION DE REVIEW - Status: {self.status_filter}")
        if self.bidul_filter:
            print(f"Filtre Bidul: #{self.bidul_filter}")
        print(f"{'='*60}")

        events = self.get_events_to_review(
            status=self.status_filter,
            bidul_numero=self.bidul_filter
        )

        if not events:
            print("\nAucun événement à reviewer avec ces filtres.")
            self.close()
            return

        print(f"\n{len(events)} événements à reviewer.\n")
        print("Commandes: [v]alider, [f]lagger, [d]éléter, [e]diter, [m]atcher lieu, [s]kip, [q]uitter")

        for event in events:
            self.display_event(event)

            while True:
                try:
                    cmd = input("\n> ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\n")
                    self.close()
                    return

                if cmd == 'v':
                    self.validate(event['id'])
                    print("  -> Validé")
                    break
                elif cmd == 'f':
                    note = input("  Note (optionnel): ").strip()
                    self.flag(event['id'], note)
                    print("  -> Flaggé")
                    break
                elif cmd == 'd':
                    reason = input("  Raison: ").strip()
                    self.delete(event['id'], reason)
                    print("  -> Supprimé")
                    break
                elif cmd == 's':
                    print("  -> Skippé")
                    break
                elif cmd == 'q':
                    self.close()
                    return
                elif cmd == 'm':
                    query = input("  Recherche lieu: ").strip()
                    lieux = self.search_lieu(query)
                    if lieux:
                        for i, lieu in enumerate(lieux):
                            print(f"    [{i}] {lieu['nom']} (id={lieu['id']})")
                        try:
                            choice = int(input("  Choix: ").strip())
                            if 0 <= choice < len(lieux):
                                self.match_lieu(event['id'], lieux[choice]['id'])
                                print(f"  -> Lieu matché: {lieux[choice]['nom']}")
                        except (ValueError, IndexError):
                            print("  Choix invalide")
                    else:
                        print("  Aucun lieu trouvé")
                elif cmd == 'e':
                    field = input("  Champ à éditer (nom, lieu_raw, artistes, date_evenement, heure, style, tarif_raw, prix_min, prix_max, gratuit): ").strip()
                    if field in ('nom', 'lieu_raw', 'artistes', 'date_evenement', 'heure', 'ville_raw', 'tarif_raw', 'style', 'prix_min', 'prix_max', 'gratuit'):
                        old_val = event[field]
                        new_val = input(f"  Nouvelle valeur (actuel: {old_val}) [NULL pour vider]: ").strip()
                        if new_val:
                            # NULL ou None -> mettre à NULL en base
                            if new_val.upper() in ('NULL', 'NONE'):
                                new_val = None
                            # Conversion de type pour les champs numériques/booléens
                            elif field in ('prix_min', 'prix_max'):
                                try:
                                    new_val = float(new_val)
                                except ValueError:
                                    print("  Erreur: valeur numérique attendue")
                                    continue
                            elif field == 'gratuit':
                                new_val = new_val.lower() in ('true', '1', 'oui', 'yes', 'o')
                            self.update_field(event['id'], field, old_val, new_val)
                            print(f"  -> {field} mis à jour")
                    else:
                        print("  Champ non modifiable")
                elif cmd == '?':
                    print("  [v]alider, [f]lagger, [d]éléter, [e]diter, [m]atcher lieu, [s]kip, [q]uitter")
                else:
                    print("  Commande inconnue. Tapez ? pour l'aide.")

        self.close()

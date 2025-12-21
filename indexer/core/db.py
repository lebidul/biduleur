"""
Module de gestion de la base de données SQLite.

Utilise le schéma simplifié v2.
"""

import csv
import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional
from datetime import date, datetime

from .parser import ParsedEvent, strip_formatting_tags

logger = logging.getLogger(__name__)

# Chemins par défaut
SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema_v2.sql"
DEFAULT_DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"
CORPUS_DIR = Path(__file__).parent.parent / "corpus"


class BidulDB:
    """
    Gestionnaire de la base de données des archives du Bidul.

    Utilise le schéma v2 simplifié avec:
    - bidul: métadonnées des exemplaires
    - evenement: événements extraits avec raw_text
    - lieu_ref / ville_ref: référentiels pour normalisation
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialise la connexion à la base.

        Args:
            db_path: Chemin vers la base SQLite (défaut: database/bidul_archives.db)
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Ouvre la connexion."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self):
        """Ferme la connexion."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def init_schema(self):
        """Initialise le schéma de la base."""
        conn = self.connect()
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()
        logger.info(f"Schéma initialisé: {self.db_path}")

    def load_referentiels(self):
        """Charge les référentiels lieux et villes depuis les CSV."""
        conn = self.connect()

        # Lieux
        lieu_file = CORPUS_DIR / "lieu.csv"
        if lieu_file.exists():
            with open(lieu_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO lieu_ref (nom, ville) VALUES (?, ?)",
                            (row['nom'], row.get('ville', 'Le Mans'))
                        )
                    except Exception as e:
                        logger.debug(f"Erreur insertion lieu: {e}")
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM lieu_ref").fetchone()[0]
            logger.info(f"Lieux chargés: {count}")

        # Villes
        ville_file = CORPUS_DIR / "ville.csv"
        if ville_file.exists():
            with open(ville_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO ville_ref (nom) VALUES (?)",
                            (row['nom'],)
                        )
                    except Exception as e:
                        logger.debug(f"Erreur insertion ville: {e}")
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM ville_ref").fetchone()[0]
            logger.info(f"Villes chargées: {count}")

    # -------------------------------------------------------------------------
    # CRUD Bidul
    # -------------------------------------------------------------------------

    def get_bidul(self, numero: int) -> Optional[dict]:
        """Récupère un Bidul par son numéro."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM bidul WHERE numero = ?", (numero,)
        ).fetchone()
        return dict(row) if row else None

    def insert_bidul(
        self,
        numero: int,
        mois: Optional[int] = None,
        annee: Optional[int] = None,
        pdf_filename: Optional[str] = None,
        type_source: str = 'texte',
        config_extraction: Optional[str] = None
    ) -> int:
        """Insère ou met à jour un Bidul."""
        conn = self.connect()

        existing = self.get_bidul(numero)
        if existing:
            conn.execute("""
                UPDATE bidul SET
                    mois = COALESCE(?, mois),
                    annee = COALESCE(?, annee),
                    pdf_filename = COALESCE(?, pdf_filename),
                    type_source = COALESCE(?, type_source),
                    config_extraction = COALESCE(?, config_extraction)
                WHERE numero = ?
            """, (mois, annee, pdf_filename, type_source, config_extraction, numero))
        else:
            conn.execute("""
                INSERT INTO bidul (numero, mois, annee, pdf_filename, type_source, config_extraction)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (numero, mois, annee, pdf_filename, type_source, config_extraction))

        conn.commit()
        return numero

    def update_bidul_status(self, numero: int, status: str):
        """Met à jour le statut d'extraction."""
        conn = self.connect()
        conn.execute("""
            UPDATE bidul
            SET extraction_status = ?, extraction_date = CURRENT_TIMESTAMP
            WHERE numero = ?
        """, (status, numero))
        conn.commit()

    # -------------------------------------------------------------------------
    # CRUD Evenement
    # -------------------------------------------------------------------------

    def insert_evenement(self, bidul_numero: int, event: ParsedEvent) -> int:
        """Insère un événement depuis un ParsedEvent (extraction PDF)."""
        conn = self.connect()

        # Chercher les IDs de référence pour lieu et ville (matching fuzzy)
        lieu_ref_id = self._find_lieu_ref(event.lieu_raw) if event.lieu_raw else None
        ville_ref_id, ville_normalized = self._find_ville_ref(event.ville_raw)

        # Générer raw_text_clean (sans balises de formatage)
        raw_text_clean = strip_formatting_tags(event.raw_text) if event.raw_text else None

        cursor = conn.execute("""
            INSERT INTO evenement (
                bidul_numero, raw_text, raw_text_clean, nom, date_evenement, heure,
                lieu_raw, lieu_ref_id, ville_raw, ville_ref_id,
                artistes, spectacles, genres_raw,
                tarif_raw, prix_min, prix_max, gratuit,
                type_evenement, confidence, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pdf')
        """, (
            bidul_numero,
            event.raw_text,
            raw_text_clean,
            event.nom,
            event.date_evenement.isoformat() if event.date_evenement else None,
            event.heure,
            event.lieu_raw,
            lieu_ref_id,
            ville_normalized,  # Normalisé (Le Mans si vide)
            ville_ref_id,
            json.dumps([a.to_dict() if hasattr(a, 'to_dict') else a for a in event.artistes], ensure_ascii=False) if event.artistes else None,
            json.dumps(event.spectacles, ensure_ascii=False),
            json.dumps(event.genres_raw, ensure_ascii=False),
            event.tarif_raw,
            event.prix_min,
            event.prix_max,
            event.gratuit,
            event.type_evenement,
            event.confidence
        ))
        evenement_id = cursor.lastrowid

        # Insérer dans contenu_evenement
        self._insert_contenu_evenement(conn, evenement_id, event.artistes, event.spectacles)

        conn.commit()
        return evenement_id

    def insert_evenement_from_dict(self, event: dict) -> int:
        """Insère un événement depuis un dictionnaire (import CSV)."""
        conn = self.connect()

        # Chercher les IDs de référence pour lieu et ville (matching fuzzy)
        lieu_ref_id = self._find_lieu_ref(event.get('lieu_raw')) if event.get('lieu_raw') else None
        ville_ref_id, ville_normalized = self._find_ville_ref(event.get('ville_raw'))

        # Générer raw_text_clean (sans balises de formatage)
        raw_text = event.get('raw_text', '')
        raw_text_clean = strip_formatting_tags(raw_text) if raw_text else None

        cursor = conn.execute("""
            INSERT INTO evenement (
                bidul_numero, raw_text, raw_text_clean, nom, date_evenement, heure,
                lieu_raw, lieu_ref_id, ville_raw, ville_ref_id,
                artistes, spectacles, genres_raw, genre_evenement,
                tarif_raw, prix_min, prix_max, gratuit,
                type_evenement, confidence, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event['bidul_numero'],
            raw_text,
            raw_text_clean,
            event.get('nom'),
            event.get('date_evenement'),
            event.get('heure'),
            event.get('lieu_raw'),
            lieu_ref_id,
            ville_normalized,  # Normalisé (Le Mans si vide)
            ville_ref_id,
            event.get('artistes'),
            event.get('spectacles'),
            event.get('genres_raw'),
            event.get('genre_evenement'),
            event.get('tarif_raw'),
            event.get('prix_min'),
            event.get('prix_max'),
            event.get('gratuit', False),
            event.get('type_evenement'),
            event.get('confidence', 0.5),
            event.get('source', 'pdf')
        ))
        evenement_id = cursor.lastrowid

        # Insérer dans contenu_evenement (parser le JSON artistes/spectacles)
        artistes_json = event.get('artistes')
        spectacles_json = event.get('spectacles')
        genres_json = event.get('genres_raw')

        artistes = []
        spectacles = []
        genres = []

        if artistes_json:
            try:
                artistes = json.loads(artistes_json)
            except (json.JSONDecodeError, TypeError):
                pass

        if spectacles_json:
            try:
                spectacles = json.loads(spectacles_json)
            except (json.JSONDecodeError, TypeError):
                pass

        if genres_json:
            try:
                genres = json.loads(genres_json)
            except (json.JSONDecodeError, TypeError):
                pass

        self._insert_contenu_from_json(conn, evenement_id, artistes, spectacles, genres)

        conn.commit()
        return evenement_id

    def get_evenements(self, bidul_numero: int) -> list[dict]:
        """Récupère tous les événements d'un Bidul."""
        conn = self.connect()
        rows = conn.execute("""
            SELECT * FROM evenement WHERE bidul_numero = ?
            ORDER BY date_evenement, heure
        """, (bidul_numero,)).fetchall()
        return [dict(row) for row in rows]

    def delete_evenements(self, bidul_numero: int):
        """Supprime tous les événements d'un Bidul (et leurs contenus associés)."""
        conn = self.connect()
        # Supprimer d'abord les contenus (FK constraint)
        conn.execute("""
            DELETE FROM contenu_evenement
            WHERE evenement_id IN (SELECT id FROM evenement WHERE bidul_numero = ?)
        """, (bidul_numero,))
        conn.execute("DELETE FROM evenement WHERE bidul_numero = ?", (bidul_numero,))
        conn.commit()

    def count_evenements(self, bidul_numero: Optional[int] = None) -> int:
        """Compte les événements."""
        conn = self.connect()
        if bidul_numero:
            return conn.execute(
                "SELECT COUNT(*) FROM evenement WHERE bidul_numero = ?",
                (bidul_numero,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM evenement").fetchone()[0]

    # -------------------------------------------------------------------------
    # Contenu événement (artistes/spectacles)
    # -------------------------------------------------------------------------

    def _insert_contenu_evenement(self, conn, evenement_id: int, artistes: list, spectacles: list):
        """Insère les artistes/spectacles dans contenu_evenement depuis un ParsedEvent."""
        ordre = 1

        # Artistes (peuvent être des ArtisteInfo ou des dicts)
        for artiste in artistes:
            if hasattr(artiste, 'nom'):
                # ArtisteInfo object
                conn.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                    VALUES (?, ?, ?, ?, ?)
                ''', (evenement_id, artiste.nom, artiste.spectacle, artiste.genre, ordre))
            elif isinstance(artiste, dict):
                conn.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                    VALUES (?, ?, ?, ?, ?)
                ''', (evenement_id, artiste.get('nom'), artiste.get('spectacle'), artiste.get('genre'), ordre))
            elif isinstance(artiste, str):
                conn.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, style, ordre)
                    VALUES (?, ?, ?, ?)
                ''', (evenement_id, artiste, None, ordre))
            ordre += 1

        # Spectacles sans artiste (si pas déjà associés à un artiste)
        for spectacle in spectacles:
            if isinstance(spectacle, str):
                conn.execute('''
                    INSERT INTO contenu_evenement (evenement_id, nom_spectacle, ordre)
                    VALUES (?, ?, ?)
                ''', (evenement_id, spectacle, ordre))
                ordre += 1

    def _insert_contenu_from_json(self, conn, evenement_id: int, artistes: list, spectacles: list, genres: list):
        """
        Insère les artistes/spectacles dans contenu_evenement depuis des listes JSON.

        Logique de combinaison:
        - Si 1 spectacle + N artistes → 1 ligne avec spectacle + premier artiste, puis N-1 lignes artistes seuls
        - Si N spectacles + M artistes → combiner par index quand possible
        - Chaque ligne a: artiste, nom_spectacle, style
        """
        ordre = 1

        # Normaliser les spectacles en liste de dicts
        norm_spectacles = []
        for spec in (spectacles or []):
            if isinstance(spec, dict):
                norm_spectacles.append({
                    'nom': spec.get('nom'),
                    'style': spec.get('style') or spec.get('genre')
                })
            else:
                norm_spectacles.append({'nom': spec, 'style': None})

        # Normaliser les artistes en liste de dicts
        norm_artistes = []
        for i, art in enumerate(artistes or []):
            if isinstance(art, dict):
                norm_artistes.append({
                    'nom': art.get('nom'),
                    'style': art.get('genre') or art.get('style')
                })
            else:
                style = genres[i] if i < len(genres) else None
                norm_artistes.append({'nom': art, 'style': style})

        # Cas 1: Spectacles + Artistes → combiner intelligemment
        if norm_spectacles and norm_artistes:
            # Premier spectacle avec premier artiste (cas typique: 1 spectacle, 1+ artistes)
            first_spec = norm_spectacles[0]
            first_art = norm_artistes[0]
            # Le style vient du spectacle en priorité, sinon de l'artiste
            style = first_spec.get('style') or first_art.get('style')
            conn.execute('''
                INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                VALUES (?, ?, ?, ?, ?)
            ''', (evenement_id, first_art.get('nom'), first_spec.get('nom'), style, ordre))
            ordre += 1

            # Artistes supplémentaires (sans spectacle, juste l'artiste)
            for art in norm_artistes[1:]:
                conn.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                    VALUES (?, ?, ?, ?, ?)
                ''', (evenement_id, art.get('nom'), None, art.get('style'), ordre))
                ordre += 1

            # Spectacles supplémentaires (sans artiste)
            for spec in norm_spectacles[1:]:
                conn.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                    VALUES (?, ?, ?, ?, ?)
                ''', (evenement_id, None, spec.get('nom'), spec.get('style'), ordre))
                ordre += 1

        # Cas 2: Spectacles seuls
        elif norm_spectacles:
            for spec in norm_spectacles:
                conn.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                    VALUES (?, ?, ?, ?, ?)
                ''', (evenement_id, None, spec.get('nom'), spec.get('style'), ordre))
                ordre += 1

        # Cas 3: Artistes seuls
        elif norm_artistes:
            for art in norm_artistes:
                conn.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                    VALUES (?, ?, ?, ?, ?)
                ''', (evenement_id, art.get('nom'), None, art.get('style'), ordre))
                ordre += 1

    # -------------------------------------------------------------------------
    # Référentiels
    # -------------------------------------------------------------------------

    def get_lieu_ref_list(self) -> list[tuple]:
        """Retourne la liste des lieux du référentiel pour le parser.

        Returns:
            Liste de tuples (id, nom, ville)
        """
        conn = self.connect()
        rows = conn.execute("SELECT id, nom, ville FROM lieu_ref").fetchall()
        return [(row['id'], row['nom'], row['ville']) for row in rows]

    def get_ville_ref_list(self) -> list[tuple]:
        """Retourne la liste des villes du référentiel pour le parser.

        Returns:
            Liste de tuples (id, nom)
        """
        conn = self.connect()
        rows = conn.execute("SELECT id, nom FROM ville_ref").fetchall()
        return [(row['id'], row['nom']) for row in rows]

    def _find_lieu_ref(self, lieu_raw: str) -> Optional[int]:
        """Cherche un lieu dans le référentiel (matching fuzzy)."""
        from core.normalizer import normalize_lieu
        lieu_id, _ = normalize_lieu(lieu_raw, str(self.db_path))
        return lieu_id

    def _find_ville_ref(self, ville_raw: str) -> tuple[Optional[int], str]:
        """
        Cherche une ville dans le référentiel (matching fuzzy).
        Retourne (ville_id, ville_normalisee).
        Si ville_raw est vide, retourne Le Mans par défaut.
        """
        from core.normalizer import normalize_ville
        return normalize_ville(ville_raw, str(self.db_path))

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Retourne les statistiques globales."""
        conn = self.connect()
        stats = {}

        stats['biduls'] = conn.execute("SELECT COUNT(*) FROM bidul").fetchone()[0]
        stats['evenements'] = conn.execute("SELECT COUNT(*) FROM evenement").fetchone()[0]
        stats['lieux_ref'] = conn.execute("SELECT COUNT(*) FROM lieu_ref").fetchone()[0]
        stats['villes_ref'] = conn.execute("SELECT COUNT(*) FROM ville_ref").fetchone()[0]

        # Stats par source (csv/pdf)
        sources = conn.execute("""
            SELECT source, COUNT(*) as count
            FROM evenement GROUP BY source
        """).fetchall()
        stats['par_source'] = {row['source'] or 'unknown': row['count'] for row in sources}

        # Stats par statut
        statuses = conn.execute("""
            SELECT extraction_status, COUNT(*) as count
            FROM bidul GROUP BY extraction_status
        """).fetchall()
        stats['par_statut'] = {row['extraction_status']: row['count'] for row in statuses}

        # Confidence moyenne
        row = conn.execute("""
            SELECT AVG(confidence) as avg_conf, MIN(confidence) as min_conf, MAX(confidence) as max_conf
            FROM evenement
        """).fetchone()
        if row and row['avg_conf']:
            stats['confidence_avg'] = round(row['avg_conf'], 3)
            stats['confidence_min'] = round(row['min_conf'], 3)
            stats['confidence_max'] = round(row['max_conf'], 3)

        # Plage de Biduls
        row = conn.execute("""
            SELECT MIN(numero) as min_num, MAX(numero) as max_num
            FROM bidul
        """).fetchone()
        if row and row['min_num']:
            stats['bidul_min'] = row['min_num']
            stats['bidul_max'] = row['max_num']

        # Plage de dates
        row = conn.execute("""
            SELECT MIN(date_evenement) as min_date, MAX(date_evenement) as max_date
            FROM evenement WHERE date_evenement IS NOT NULL
        """).fetchone()
        if row and row['min_date']:
            stats['date_min'] = row['min_date']
            stats['date_max'] = row['max_date']

        # Top 5 villes
        villes = conn.execute("""
            SELECT ville_raw, COUNT(*) as count
            FROM evenement
            WHERE ville_raw IS NOT NULL
            GROUP BY ville_raw
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()
        stats['top_villes'] = [(row['ville_raw'], row['count']) for row in villes]

        # Top 5 lieux
        lieux = conn.execute("""
            SELECT lieu_raw, COUNT(*) as count
            FROM evenement
            WHERE lieu_raw IS NOT NULL
            GROUP BY lieu_raw
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()
        stats['top_lieux'] = [(row['lieu_raw'], row['count']) for row in lieux]

        # Événements gratuits vs payants
        row = conn.execute("""
            SELECT
                SUM(CASE WHEN gratuit = 1 THEN 1 ELSE 0 END) as gratuits,
                SUM(CASE WHEN gratuit = 0 AND prix_min IS NOT NULL THEN 1 ELSE 0 END) as payants,
                SUM(CASE WHEN gratuit = 0 AND prix_min IS NULL THEN 1 ELSE 0 END) as prix_inconnu
            FROM evenement
        """).fetchone()
        if row:
            stats['gratuits'] = row['gratuits'] or 0
            stats['payants'] = row['payants'] or 0
            stats['prix_inconnu'] = row['prix_inconnu'] or 0

        # Stats par type d'événement
        types = conn.execute("""
            SELECT type_evenement, COUNT(*) as count
            FROM evenement
            WHERE type_evenement IS NOT NULL
            GROUP BY type_evenement
            ORDER BY count DESC
        """).fetchall()
        stats['par_type'] = {row['type_evenement']: row['count'] for row in types}

        return stats


# Test standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    db = BidulDB()
    db.init_schema()
    db.load_referentiels()

    print("\nStats:")
    stats = db.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

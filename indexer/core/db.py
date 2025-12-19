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

from .parser import ParsedEvent

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
        """Insère un événement."""
        conn = self.connect()

        # Chercher les IDs de référence pour lieu et ville
        lieu_ref_id = self._find_lieu_ref(event.lieu_raw) if event.lieu_raw else None
        ville_ref_id = self._find_ville_ref(event.ville_raw) if event.ville_raw else None

        cursor = conn.execute("""
            INSERT INTO evenement (
                bidul_numero, raw_text, nom, date_evenement, heure,
                lieu_raw, lieu_ref_id, ville_raw, ville_ref_id,
                artistes, spectacles, genres_raw,
                tarif_raw, prix_min, prix_max, gratuit,
                type_evenement, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bidul_numero,
            event.raw_text,
            event.nom,
            event.date_evenement.isoformat() if event.date_evenement else None,
            event.heure,
            event.lieu_raw,
            lieu_ref_id,
            event.ville_raw,
            ville_ref_id,
            json.dumps(event.artistes, ensure_ascii=False),
            json.dumps(event.spectacles, ensure_ascii=False),
            json.dumps(event.genres_raw, ensure_ascii=False),
            event.tarif_raw,
            event.prix_min,
            event.prix_max,
            event.gratuit,
            event.type_evenement,
            event.confidence
        ))
        conn.commit()
        return cursor.lastrowid

    def get_evenements(self, bidul_numero: int) -> list[dict]:
        """Récupère tous les événements d'un Bidul."""
        conn = self.connect()
        rows = conn.execute("""
            SELECT * FROM evenement WHERE bidul_numero = ?
            ORDER BY date_evenement, heure
        """, (bidul_numero,)).fetchall()
        return [dict(row) for row in rows]

    def delete_evenements(self, bidul_numero: int):
        """Supprime tous les événements d'un Bidul."""
        conn = self.connect()
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
    # Référentiels
    # -------------------------------------------------------------------------

    def _find_lieu_ref(self, lieu_raw: str) -> Optional[int]:
        """Cherche un lieu dans le référentiel (matching exact)."""
        conn = self.connect()
        row = conn.execute(
            "SELECT id FROM lieu_ref WHERE nom = ?", (lieu_raw,)
        ).fetchone()
        return row['id'] if row else None

    def _find_ville_ref(self, ville_raw: str) -> Optional[int]:
        """Cherche une ville dans le référentiel (matching exact)."""
        conn = self.connect()
        row = conn.execute(
            "SELECT id FROM ville_ref WHERE nom = ?", (ville_raw,)
        ).fetchone()
        return row['id'] if row else None

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

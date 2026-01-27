"""
Module d'overrides pour les corrections manuelles (mode sync).

Le CSV représente l'état final souhaité - pas de colonnes .expected.
Les valeurs du CSV écrasent directement les valeurs en base.

Usage:
    python -m core.overrides corpus/overrides/teriaki.csv [--dry-run]

Format CSV:
    bidul_numero,raw_text,nom,lieu_raw,ville_raw,tarif_raw,nom_spectacle,artiste,style

Logique:
    1. Pour chaque (bidul_numero, raw_text) unique:
       - UPDATE evenement avec nom, lieu_raw, ville_raw, tarif_raw
    2. DELETE tous les contenu_evenement pour cet evenement_id
    3. INSERT les nouveaux contenu_evenement depuis les lignes CSV (nom_spectacle, artiste, style)

Note: Une valeur vide dans le CSV = NULL en base
"""

import csv
import logging
import argparse
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from .db import BidulDB

logger = logging.getLogger(__name__)

OVERRIDES_DIR = Path(__file__).parent.parent / "corpus" / "overrides"


@dataclass
class EventData:
    """Données d'un événement à synchroniser."""
    nom: Optional[str] = None
    lieu_raw: Optional[str] = None
    ville_raw: Optional[str] = None
    tarif_raw: Optional[str] = None


@dataclass
class ContenuData:
    """Données d'un contenu à insérer."""
    nom_spectacle: Optional[str] = None
    artiste: Optional[str] = None
    style: Optional[str] = None


@dataclass
class OverrideEntry:
    """Entrée d'override pour un événement."""
    bidul_numero: int
    raw_text: str
    event_data: EventData
    contenus: list[ContenuData] = field(default_factory=list)


def _parse_value(value: str) -> Optional[str]:
    """Parse une valeur CSV: vide = None, sinon la valeur."""
    if not value or not value.strip():
        return None
    return value.strip()


def load_overrides_from_csv(csv_path: Path) -> dict[tuple[int, str], OverrideEntry]:
    """
    Charge les overrides depuis un CSV.

    Returns:
        Dict (bidul_numero, raw_text) -> OverrideEntry
    """
    overrides: dict[tuple[int, str], OverrideEntry] = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            bidul_numero = row.get('bidul_numero')
            raw_text = row.get('raw_text', '').strip()

            if not bidul_numero or not raw_text:
                continue

            bidul_numero = int(bidul_numero)
            key = (bidul_numero, raw_text)

            # Créer ou récupérer l'entrée
            if key not in overrides:
                overrides[key] = OverrideEntry(
                    bidul_numero=bidul_numero,
                    raw_text=raw_text,
                    event_data=EventData(
                        nom=_parse_value(row.get('nom', '')),
                        lieu_raw=_parse_value(row.get('lieu_raw', '')),
                        ville_raw=_parse_value(row.get('ville_raw', '')),
                        tarif_raw=_parse_value(row.get('tarif_raw', '')),
                    ),
                    contenus=[]
                )

            # Ajouter le contenu si artiste présent
            artiste = _parse_value(row.get('artiste', ''))
            if artiste:
                overrides[key].contenus.append(ContenuData(
                    nom_spectacle=_parse_value(row.get('nom_spectacle', '')),
                    artiste=artiste,
                    style=_parse_value(row.get('style', '')),
                ))

    return overrides


def _find_evenement(conn, bidul_numero: int, raw_text: str) -> Optional[dict]:
    """Trouve un événement par bidul_numero et raw_text."""
    cursor = conn.execute('''
        SELECT id, nom, lieu_raw, ville_raw, tarif_raw
        FROM evenement
        WHERE bidul_numero = ? AND raw_text = ?
        LIMIT 1
    ''', (bidul_numero, raw_text))

    row = cursor.fetchone()
    if row:
        return {
            'id': row[0],
            'nom': row[1],
            'lieu_raw': row[2],
            'ville_raw': row[3],
            'tarif_raw': row[4]
        }
    return None


def apply_overrides_from_csv(
    csv_path: Path,
    db: BidulDB,
    dry_run: bool = False
) -> dict:
    """
    Applique les overrides d'un CSV (mode sync).

    Args:
        csv_path: Chemin vers le CSV
        db: Instance BidulDB
        dry_run: Si True, n'applique pas les modifications

    Returns:
        Statistiques {updated, not_found, errors}
    """
    stats = {'updated': 0, 'not_found': 0, 'errors': 0}
    conn = db.connect()

    overrides = load_overrides_from_csv(csv_path)
    logger.info(f"Chargé {len(overrides)} événements à synchroniser")

    for (bidul_numero, raw_text), entry in overrides.items():
        try:
            # Trouver l'événement
            evenement = _find_evenement(conn, bidul_numero, raw_text)
            if not evenement:
                logger.warning(f"Événement non trouvé: bidul {bidul_numero}, raw_text={raw_text[:50]}...")
                stats['not_found'] += 1
                continue

            evenement_id = evenement['id']

            if dry_run:
                logger.info(f"[DRY-RUN] Sync evenement {evenement_id} (bidul {bidul_numero})")
                logger.info(f"  -> nom={entry.event_data.nom}, lieu_raw={entry.event_data.lieu_raw}, "
                           f"ville_raw={entry.event_data.ville_raw}, tarif_raw={entry.event_data.tarif_raw}")
                logger.info(f"  -> {len(entry.contenus)} contenus: {[c.artiste for c in entry.contenus]}")
            else:
                # 1. UPDATE evenement
                conn.execute('''
                    UPDATE evenement
                    SET nom = ?, lieu_raw = ?, ville_raw = ?, tarif_raw = ?
                    WHERE id = ?
                ''', (
                    entry.event_data.nom,
                    entry.event_data.lieu_raw,
                    entry.event_data.ville_raw,
                    entry.event_data.tarif_raw,
                    evenement_id
                ))

                # 2. DELETE tous les contenu_evenement
                conn.execute('DELETE FROM contenu_evenement WHERE evenement_id = ?', (evenement_id,))

                # 3. INSERT les nouveaux contenus
                for contenu in entry.contenus:
                    conn.execute('''
                        INSERT INTO contenu_evenement (evenement_id, nom_spectacle, artiste, style)
                        VALUES (?, ?, ?, ?)
                    ''', (evenement_id, contenu.nom_spectacle, contenu.artiste, contenu.style))

                logger.debug(f"Synced evenement {evenement_id}: {len(entry.contenus)} contenus")

            stats['updated'] += 1

        except Exception as e:
            logger.error(f"Erreur bidul {bidul_numero}: {e}")
            stats['errors'] += 1

    if not dry_run:
        conn.commit()

    return stats


# ============================================================================
# Intégration avec le parsing (pour application automatique après insert)
# ============================================================================

@dataclass
class OverrideManager:
    """Gestionnaire d'overrides pour application automatique après parsing."""
    overrides: dict[tuple[int, str], OverrideEntry] = field(default_factory=dict)
    _loaded: bool = False

    def load_all(self, overrides_dir: Optional[Path] = None) -> int:
        """Charge tous les CSV du répertoire overrides."""
        overrides_dir = overrides_dir or OVERRIDES_DIR

        if not overrides_dir.exists():
            overrides_dir.mkdir(parents=True, exist_ok=True)
            return 0

        total = 0
        for csv_file in overrides_dir.glob("*.csv"):
            file_overrides = load_overrides_from_csv(csv_file)
            self.overrides.update(file_overrides)
            total += len(file_overrides)
            logger.debug(f"Chargé {len(file_overrides)} overrides de {csv_file.name}")

        self._loaded = True
        logger.info(f"Total: {total} overrides chargés")
        return total

    def apply_to_event(self, conn, evenement_id: int, bidul_numero: int, raw_text: str) -> bool:
        """
        Applique l'override à un événement après insertion.

        Returns:
            True si un override a été appliqué
        """
        if not self._loaded:
            return False

        key = (bidul_numero, raw_text)
        entry = self.overrides.get(key)

        if not entry:
            return False

        # 1. UPDATE evenement
        conn.execute('''
            UPDATE evenement
            SET nom = ?, lieu_raw = ?, ville_raw = ?, tarif_raw = ?
            WHERE id = ?
        ''', (
            entry.event_data.nom,
            entry.event_data.lieu_raw,
            entry.event_data.ville_raw,
            entry.event_data.tarif_raw,
            evenement_id
        ))

        # 2. DELETE tous les contenu_evenement existants
        conn.execute('DELETE FROM contenu_evenement WHERE evenement_id = ?', (evenement_id,))

        # 3. INSERT les nouveaux contenus
        for contenu in entry.contenus:
            conn.execute('''
                INSERT INTO contenu_evenement (evenement_id, nom_spectacle, artiste, style)
                VALUES (?, ?, ?, ?)
            ''', (evenement_id, contenu.nom_spectacle, contenu.artiste, contenu.style))

        logger.debug(f"Override appliqué: evenement {evenement_id}, {len(entry.contenus)} contenus")
        return True


# Instance globale
_global_manager: Optional[OverrideManager] = None


def get_override_manager() -> OverrideManager:
    """Retourne le gestionnaire global d'overrides."""
    global _global_manager
    if _global_manager is None:
        _global_manager = OverrideManager()
        _global_manager.load_all()
    return _global_manager


def apply_overrides(conn, evenement_id: int, bidul_numero: int, raw_text: str) -> bool:
    """
    Fonction utilitaire pour appliquer les overrides après insertion.

    Usage:
        from core.overrides import apply_overrides

        event_id = db.insert_evenement(bidul_numero, event)
        apply_overrides(db.connect(), event_id, bidul_numero, event.raw_text)
    """
    mgr = get_override_manager()
    return mgr.apply_to_event(conn, evenement_id, bidul_numero, raw_text)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Applique les overrides d'un CSV (mode sync)"
    )
    parser.add_argument('csv_file', type=Path, help="Fichier CSV d'overrides")
    parser.add_argument('--dry-run', action='store_true',
                        help="Affiche les modifications sans les appliquer")
    parser.add_argument('--db', type=Path, default=None,
                        help="Chemin vers la base de données")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Affichage détaillé")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    if not args.csv_file.exists():
        logger.error(f"Fichier CSV non trouvé: {args.csv_file}")
        return 1

    db = BidulDB(args.db)

    print(f"Synchronisation depuis {args.csv_file}")
    if args.dry_run:
        print("[MODE DRY-RUN - aucune modification ne sera appliquée]")

    stats = apply_overrides_from_csv(args.csv_file, db, dry_run=args.dry_run)

    print(f"\nRésultats:")
    print(f"  - Synchronisés: {stats['updated']}")
    print(f"  - Non trouvés: {stats['not_found']}")
    print(f"  - Erreurs: {stats['errors']}")

    return 0


if __name__ == '__main__':
    exit(main())

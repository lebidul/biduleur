"""Gestion des alias et normalisation des noms"""

import sqlite3
import json
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"
ALIASES_JSON_PATH = Path(__file__).parent.parent / "corpus" / "artistes_aliases.json"


def load_artiste_aliases(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, str]:
    """Charge les alias artistes depuis la DB"""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        cur.execute('SELECT nom_variante, nom_normalise FROM artiste_alias')
        aliases = {row[0]: row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        # Table n'existe pas encore
        aliases = {}
    conn.close()
    return aliases


def load_artiste_aliases_json(json_path: str | Path = ALIASES_JSON_PATH) -> dict[str, str]:
    """Charge les alias depuis le fichier JSON"""
    path = Path(json_path)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def normalize_artiste(nom: str, aliases: dict[str, str] | None = None) -> str:
    """Normalise un nom d'artiste via les alias"""
    if aliases is None:
        aliases = load_artiste_aliases()
    return aliases.get(nom, nom)


def add_artiste_alias(nom_variante: str, nom_normalise: str, db_path: str | Path = DEFAULT_DB_PATH):
    """Ajoute un alias artiste"""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute('''
        INSERT OR REPLACE INTO artiste_alias (nom_variante, nom_normalise)
        VALUES (?, ?)
    ''', (nom_variante, nom_normalise))
    conn.commit()
    conn.close()


def apply_artiste_aliases(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """
    Applique tous les alias artistes aux événements existants.
    Met à jour le champ artistes (JSON) en remplaçant les variantes.
    """
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    aliases = load_artiste_aliases(db_path)
    if not aliases:
        print("Aucun alias à appliquer")
        conn.close()
        return 0

    cur.execute('SELECT id, artistes FROM evenement WHERE artistes IS NOT NULL')
    updated = 0

    for row in cur.fetchall():
        event_id, artistes_json = row
        try:
            artistes = json.loads(artistes_json)
            modified = False

            for i, art in enumerate(artistes):
                if isinstance(art, dict) and 'nom' in art:
                    if art['nom'] in aliases:
                        art['nom'] = aliases[art['nom']]
                        modified = True
                elif isinstance(art, str):
                    # Ancien format (liste de strings)
                    if art in aliases:
                        artistes[i] = aliases[art]
                        modified = True

            if modified:
                cur.execute('UPDATE evenement SET artistes = ? WHERE id = ?',
                           (json.dumps(artistes, ensure_ascii=False), event_id))
                updated += 1
        except json.JSONDecodeError:
            continue

    conn.commit()
    conn.close()
    return updated


def sync_aliases_from_json(json_path: str | Path = ALIASES_JSON_PATH, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Synchronise les alias du JSON vers la DB"""
    aliases = load_artiste_aliases_json(json_path)
    for variante, normalise in aliases.items():
        add_artiste_alias(variante, normalise, db_path)
    return len(aliases)

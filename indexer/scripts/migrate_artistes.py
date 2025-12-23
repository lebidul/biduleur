"""Migration des artistes/spectacles JSON vers la nouvelle table contenu_evenement"""

import sqlite3
import json
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"


def migrate(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """
    Migre les artistes/spectacles stockés en JSON dans evenement
    vers la nouvelle table contenu_evenement.

    Returns:
        Nombre de contenus créés
    """
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Créer la nouvelle table si elle n'existe pas
    cur.execute('''
        CREATE TABLE IF NOT EXISTS contenu_evenement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evenement_id INTEGER NOT NULL,
            artiste TEXT,
            nom_spectacle TEXT,
            style TEXT,
            ordre INTEGER DEFAULT 1,
            FOREIGN KEY (evenement_id) REFERENCES evenement(id) ON DELETE CASCADE
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_contenu_evenement_id ON contenu_evenement(evenement_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_contenu_artiste ON contenu_evenement(artiste)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_contenu_style ON contenu_evenement(style)')
    conn.commit()

    # Vérifier si déjà migré
    cur.execute('SELECT COUNT(*) FROM contenu_evenement')
    if cur.fetchone()[0] > 0:
        print("Table contenu_evenement déjà peuplée, skip migration")
        conn.close()
        return 0

    # Récupérer les événements avec artistes/spectacles
    cur.execute('''
        SELECT id, artistes, spectacles, genres_raw
        FROM evenement
        WHERE artistes IS NOT NULL OR spectacles IS NOT NULL
    ''')

    migrated = 0
    for row in cur.fetchall():
        event_id = row[0]
        artistes_json = row[1]
        spectacles_json = row[2]
        genres_json = row[3]

        artistes = []
        spectacles = []
        genres = []

        try:
            if artistes_json:
                artistes = json.loads(artistes_json)
        except json.JSONDecodeError:
            pass

        try:
            if spectacles_json:
                spectacles = json.loads(spectacles_json)
        except json.JSONDecodeError:
            pass

        try:
            if genres_json:
                genres = json.loads(genres_json)
        except json.JSONDecodeError:
            pass

        ordre = 1

        # Cas 1: artistes est une liste d'objets [{nom, genre, spectacle}, ...]
        if artistes and isinstance(artistes[0], dict):
            for art in artistes:
                cur.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                    VALUES (?, ?, ?, ?, ?)
                ''', (event_id, art.get('nom'), art.get('spectacle'), art.get('genre'), ordre))
                ordre += 1
                migrated += 1

        # Cas 2: artistes est une liste de strings ["ARTISTE1", "ARTISTE2"]
        elif artistes and isinstance(artistes[0], str):
            for i, art in enumerate(artistes):
                style = genres[i] if i < len(genres) else None
                spec = spectacles[i] if i < len(spectacles) else (spectacles[0] if spectacles else None)
                cur.execute('''
                    INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                    VALUES (?, ?, ?, ?, ?)
                ''', (event_id, art, spec, style, ordre))
                ordre += 1
                migrated += 1

        # Cas 3: spectacles sans artistes
        elif spectacles:
            for i, spec in enumerate(spectacles):
                if isinstance(spec, dict):
                    cur.execute('''
                        INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (event_id, None, spec.get('nom'), spec.get('genre'), ordre))
                else:
                    style = genres[i] if i < len(genres) else None
                    cur.execute('''
                        INSERT INTO contenu_evenement (evenement_id, artiste, nom_spectacle, style, ordre)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (event_id, None, spec, style, ordre))
                ordre += 1
                migrated += 1

    conn.commit()
    conn.close()

    print(f"Migration terminée: {migrated} contenus créés")
    return migrated


if __name__ == '__main__':
    migrate()

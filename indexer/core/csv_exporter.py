"""
Export des événements vers des fichiers CSV/XLSX.

Permet d'exporter les données de la base avec une clause WHERE personnalisable.
Le format d'export est le format XLSX 2025+ utilisé par les fichiers sources.
"""

import csv
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Colonnes pour l'export au format XLSX 2025+
# Ces noms correspondent exactement aux colonnes du format source
XLSX_EXPORT_COLUMNS = [
    'FESTOCHE\nEVENEMENT ',
    'STYLE \nFESTOCHE / EVENEMENT ',
    'DATE',
    'HEURE',
    'LIEU',
    'VILLE',
    'PRIX',
    'GENRE 1',
    'NOM SPECTACLE 1 ( SV )',
    'COMPAGNIE 1 ( SV ) ou\nGROUPE 1 / ARTISTE 1 ( C )',
    'STYLE \nSPECTACLE 1 (SV) / CONCERT 1 (C)',
    'GENRE 2',
    'NOM SPECTACLE 2 ( SV )',
    'COMPAGNIE 2 ( SV ) ou\nGROUPE 2 / ARTISTE 2 ( C )',
    'STYLE \nSPECTACLE 2 ( SV ) / CONCERT 2 ( C )',
    'GENRE 3',
    'NOM SPECTACLE 3 ( SV )',
    'COMPAGNIE 3 ( SV ) ou\nGROUPE 3 / ARTISTE 3 ( C )',
    'STYLE \nSPECTACLE 3 ( SV ) / CONCERT 3 ( C )',
    'GENRE 4',
    'NOM SPECTACLE 4 ( SV )',
    'COMPAGNIE 4 ( SV ) ou\nGROUPE 4 / ARTISTE 4 ( C )',
    'STYLE \nSPECTACLE 4 ( SV ) / CONCERT 4 ( C )',
]

# Mapping interne -> colonnes XLSX
INTERNAL_TO_XLSX = {
    'festival': 'FESTOCHE\nEVENEMENT ',
    'style_festival': 'STYLE \nFESTOCHE / EVENEMENT ',
    'date': 'DATE',
    'horaire': 'HEURE',
    'lieu': 'LIEU',
    'ville': 'VILLE',
    'prix': 'PRIX',
    'genre1': 'GENRE 1',
    'spectacle1': 'NOM SPECTACLE 1 ( SV )',
    'artiste1': 'COMPAGNIE 1 ( SV ) ou\nGROUPE 1 / ARTISTE 1 ( C )',
    'style1': 'STYLE \nSPECTACLE 1 (SV) / CONCERT 1 (C)',
    'genre2': 'GENRE 2',
    'spectacle2': 'NOM SPECTACLE 2 ( SV )',
    'artiste2': 'COMPAGNIE 2 ( SV ) ou\nGROUPE 2 / ARTISTE 2 ( C )',
    'style2': 'STYLE \nSPECTACLE 2 ( SV ) / CONCERT 2 ( C )',
    'genre3': 'GENRE 3',
    'spectacle3': 'NOM SPECTACLE 3 ( SV )',
    'artiste3': 'COMPAGNIE 3 ( SV ) ou\nGROUPE 3 / ARTISTE 3 ( C )',
    'style3': 'STYLE \nSPECTACLE 3 ( SV ) / CONCERT 3 ( C )',
    'genre4': 'GENRE 4',
    'spectacle4': 'NOM SPECTACLE 4 ( SV )',
    'artiste4': 'COMPAGNIE 4 ( SV ) ou\nGROUPE 4 / ARTISTE 4 ( C )',
    'style4': 'STYLE \nSPECTACLE 4 ( SV ) / CONCERT 4 ( C )',
}


def export_events(
    db_path: Path,
    output_path: Path,
    where_clause: Optional[str] = None,
    params: Optional[tuple] = None,
    output_format: str = 'csv'
) -> int:
    """
    Exporte les événements vers un fichier CSV ou XLSX.

    La requête joint evenement et contenu_evenement pour reconstruire
    le format des fichiers sources.

    Args:
        db_path: Chemin vers la base de données SQLite
        output_path: Chemin du fichier de sortie
        where_clause: Clause WHERE SQL (sans le mot WHERE), ex: "bidul_numero = 280"
        params: Paramètres pour la clause WHERE (tuple de valeurs pour les ?)
        output_format: 'csv' ou 'xlsx'

    Returns:
        Nombre d'événements exportés
    """
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Construire la requête
    base_query = """
        SELECT
            e.id as event_id,
            e.bidul_numero,
            e.date_evenement,
            e.heure as horaire,
            e.lieu_raw as lieu,
            e.ville_raw as ville,
            e.tarif_raw as prix,
            e.nom as festival,
            e.genre_evenement as style_festival,
            e.type_evenement as genre,
            c.nom_spectacle,
            c.artiste,
            c.style,
            c.ordre
        FROM evenement e
        LEFT JOIN contenu_evenement c ON c.evenement_id = e.id
    """

    if where_clause:
        query = f"{base_query} WHERE {where_clause}"
    else:
        query = base_query

    query += " ORDER BY e.bidul_numero, e.date_evenement, e.id, c.ordre"

    try:
        if params:
            cursor = conn.execute(query, params)
        else:
            cursor = conn.execute(query)

        rows = cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Erreur SQL: {e}")
        logger.error(f"Query: {query}")
        conn.close()
        return 0

    # Grouper par événement pour reconstruire les colonnes spectacle1/artiste1/style1...
    events_data = {}
    for row in rows:
        event_id = row['event_id']

        if event_id not in events_data:
            events_data[event_id] = {
                'bidul_numero': row['bidul_numero'],
                'date_evenement': format_date(row['date_evenement']),
                'horaire': row['horaire'] or '',
                'lieu': row['lieu'] or '',
                'ville': row['ville'] or '',
                'prix': row['prix'] or '',
                'festival': row['festival'] or '',
                'style_festival': row['style_festival'] or '',
                'genre': row['genre'] or '',
                'contents': []
            }

        # Ajouter le contenu
        if row['artiste'] or row['nom_spectacle']:
            events_data[event_id]['contents'].append({
                'spectacle': row['nom_spectacle'] or '',
                'artiste': row['artiste'] or '',
                'style': row['style'] or '',
            })

    conn.close()

    # Transformer en liste avec colonnes au format XLSX 2025+
    export_rows = []
    for event in events_data.values():
        row = {
            INTERNAL_TO_XLSX['festival']: event['festival'],
            INTERNAL_TO_XLSX['style_festival']: event['style_festival'],
            INTERNAL_TO_XLSX['date']: event['date_evenement'],
            INTERNAL_TO_XLSX['horaire']: event['horaire'],
            INTERNAL_TO_XLSX['lieu']: event['lieu'],
            INTERNAL_TO_XLSX['ville']: event['ville'],
            INTERNAL_TO_XLSX['prix']: event['prix'],
        }

        # Remplir les colonnes genre1-4, spectacle1-4, artiste1-4, style1-4
        for i in range(4):
            idx = i + 1
            if i < len(event['contents']):
                content = event['contents'][i]
                row[INTERNAL_TO_XLSX[f'genre{idx}']] = event['genre'] if i == 0 else ''
                row[INTERNAL_TO_XLSX[f'spectacle{idx}']] = content['spectacle']
                row[INTERNAL_TO_XLSX[f'artiste{idx}']] = content['artiste']
                row[INTERNAL_TO_XLSX[f'style{idx}']] = content['style']
            else:
                row[INTERNAL_TO_XLSX[f'genre{idx}']] = ''
                row[INTERNAL_TO_XLSX[f'spectacle{idx}']] = ''
                row[INTERNAL_TO_XLSX[f'artiste{idx}']] = ''
                row[INTERNAL_TO_XLSX[f'style{idx}']] = ''

        export_rows.append(row)

    if not export_rows:
        logger.warning("Aucun événement à exporter")
        return 0

    # Écrire le fichier
    if output_format == 'xlsx':
        count = write_xlsx(export_rows, output_path)
    else:
        count = write_csv(export_rows, output_path)

    logger.info(f"Exporté {count} événements vers {output_path}")
    return count


def format_date(date_str: Optional[str]) -> str:
    """
    Formate une date ISO en format lisible pour export.

    Args:
        date_str: Date au format YYYY-MM-DD

    Returns:
        Date formatée ou chaîne vide
    """
    if not date_str:
        return ''

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        # Format: "Samedi 15" (jour de la semaine + numéro)
        jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        jour_semaine = jours[date.weekday()]
        return f"{jour_semaine} {date.day}"
    except ValueError:
        return date_str


def write_csv(rows: list[dict], output_path: Path) -> int:
    """
    Écrit les données en format CSV (format XLSX 2025+).

    Args:
        rows: Liste des lignes à écrire
        output_path: Chemin du fichier de sortie

    Returns:
        Nombre de lignes écrites
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=XLSX_EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def write_xlsx(rows: list[dict], output_path: Path) -> int:
    """
    Écrit les données en format XLSX (format 2025+).

    Args:
        rows: Liste des lignes à écrire
        output_path: Chemin du fichier de sortie

    Returns:
        Nombre de lignes écrites
    """
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas requis pour les fichiers XLSX: pip install pandas openpyxl")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows, columns=XLSX_EXPORT_COLUMNS)
    df.to_excel(output_path, index=False)

    return len(rows)


def export_bidul(
    db_path: Path,
    bidul_numero: int,
    output_path: Path,
    output_format: str = 'csv'
) -> int:
    """
    Exporte un bidul spécifique.

    Args:
        db_path: Chemin vers la base de données
        bidul_numero: Numéro du bidul à exporter
        output_path: Chemin du fichier de sortie
        output_format: 'csv' ou 'xlsx'

    Returns:
        Nombre d'événements exportés
    """
    return export_events(
        db_path,
        output_path,
        where_clause="e.bidul_numero = ?",
        params=(bidul_numero,),
        output_format=output_format
    )


def export_range(
    db_path: Path,
    start_numero: int,
    end_numero: int,
    output_dir: Path,
    output_format: str = 'csv'
) -> int:
    """
    Exporte une plage de biduls dans un dossier.

    Args:
        db_path: Chemin vers la base de données
        start_numero: Premier numéro de bidul
        end_numero: Dernier numéro de bidul (inclus)
        output_dir: Dossier de sortie
        output_format: 'csv' ou 'xlsx'

    Returns:
        Nombre total d'événements exportés
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    total = 0

    for numero in range(start_numero, end_numero + 1):
        ext = 'xlsx' if output_format == 'xlsx' else 'csv'
        output_path = output_dir / f"bidul_{numero:03d}.{ext}"
        count = export_bidul(db_path, numero, output_path, output_format)
        total += count

    return total

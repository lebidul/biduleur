"""
Générateur de dashboard HTML pour les statistiques Bidul.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Mapping des noms de jours français
JOURS_SEMAINE = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']


def get_quality_data(db_path: str) -> Dict[str, Any]:
    """
    Récupère les métriques de qualité du dataset.

    Returns:
        Dict avec:
        - score_global: % événements complets
        - complets: nb événements complets
        - total: nb total événements
        - completude: dict par champ (lieu, heure, tarif, contenu)
        - evolution: liste par période
        - score_par_bidul: liste {bidul, score}
        - top_lieux_non_norm: liste {lieu, count}
        - top_artistes_non_norm: liste {artiste, count}
        - distribution_styles: liste {style, count}
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    result = {}

    # Score global - événements complets avec contenu
    cur.execute("""
        SELECT COUNT(DISTINCT e.id)
        FROM evenement e
        JOIN contenu_evenement ce ON ce.evenement_id = e.id
        WHERE e.lieu_ref_id IS NOT NULL
          AND e.ville_ref_id IS NOT NULL
          AND e.heure IS NOT NULL AND e.heure != ''
          AND e.tarif_raw IS NOT NULL AND e.tarif_raw != ''
          AND (ce.artiste_ref_id IS NOT NULL OR (ce.style IS NOT NULL AND ce.style != ''))
    """)
    complets_avec_contenu = cur.fetchone()[0]

    # Événements complets sans contenu (avec nom obligatoire)
    cur.execute("""
        SELECT COUNT(*)
        FROM evenement e
        LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
        WHERE ce.id IS NULL
          AND e.nom IS NOT NULL AND e.nom != ''
          AND e.lieu_ref_id IS NOT NULL
          AND e.ville_ref_id IS NOT NULL
          AND e.heure IS NOT NULL AND e.heure != ''
          AND e.tarif_raw IS NOT NULL AND e.tarif_raw != ''
    """)
    complets_sans_contenu = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM evenement")
    total = cur.fetchone()[0]

    result['complets'] = complets_avec_contenu + complets_sans_contenu
    result['total'] = total
    result['score_global'] = round(result['complets'] / total * 100, 1) if total > 0 else 0

    # Distinction local/régional
    cur.execute("SELECT COUNT(*) FROM evenement WHERE is_regional = 1")
    result['total_regional'] = cur.fetchone()[0]
    result['total_local'] = total - result['total_regional']

    # Score global par type
    cur.execute("""
        SELECT COUNT(DISTINCT e.id)
        FROM evenement e
        JOIN contenu_evenement ce ON ce.evenement_id = e.id
        WHERE e.is_regional = 1
          AND e.lieu_ref_id IS NOT NULL
          AND e.ville_ref_id IS NOT NULL
          AND e.heure IS NOT NULL AND e.heure != ''
          AND e.tarif_raw IS NOT NULL AND e.tarif_raw != ''
          AND (ce.artiste_ref_id IS NOT NULL OR (ce.style IS NOT NULL AND ce.style != ''))
    """)
    complets_regional = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM evenement e
        LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
        WHERE e.is_regional = 1
          AND ce.id IS NULL
          AND e.nom IS NOT NULL AND e.nom != ''
          AND e.lieu_ref_id IS NOT NULL
          AND e.ville_ref_id IS NOT NULL
          AND e.heure IS NOT NULL AND e.heure != ''
          AND e.tarif_raw IS NOT NULL AND e.tarif_raw != ''
    """)
    complets_regional += cur.fetchone()[0]

    result['complets_regional'] = complets_regional
    result['complets_local'] = result['complets'] - complets_regional
    result['score_regional'] = round(complets_regional / result['total_regional'] * 100, 1) if result['total_regional'] > 0 else 0
    result['score_local'] = round(result['complets_local'] / result['total_local'] * 100, 1) if result['total_local'] > 0 else 0

    # Complétude par champ
    cur.execute("""
        SELECT
            ROUND(SUM(CASE WHEN lieu_ref_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN lieu_raw IS NOT NULL AND lieu_raw != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN heure IS NOT NULL AND heure != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN tarif_raw IS NOT NULL AND tarif_raw != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN nom IS NOT NULL AND nom != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN ville_ref_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
        FROM evenement
    """)
    row = cur.fetchone()
    result['completude'] = {
        'lieu_normalise': row[0] or 0,
        'lieu_raw': row[1] or 0,
        'heure': row[2] or 0,
        'tarif': row[3] or 0,
        'nom': row[4] or 0,
        'ville_normalise': row[5] or 0
    }

    # Complétude contenus
    cur.execute("""
        SELECT
            ROUND(SUM(CASE WHEN artiste_ref_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN artiste IS NOT NULL AND artiste != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN style IS NOT NULL AND style != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN nom_spectacle IS NOT NULL AND nom_spectacle != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
        FROM contenu_evenement
    """)
    row = cur.fetchone()
    result['completude']['artiste_normalise'] = row[0] or 0
    result['completude']['artiste_raw'] = row[1] or 0
    result['completude']['style'] = row[2] or 0
    result['completude']['spectacle'] = row[3] or 0

    # Évolution par période
    cur.execute("""
        SELECT
            CASE
                WHEN b.annee < 2000 THEN '1997-1999'
                WHEN b.annee < 2005 THEN '2000-2004'
                WHEN b.annee < 2010 THEN '2005-2009'
                WHEN b.annee < 2015 THEN '2010-2014'
                WHEN b.annee < 2020 THEN '2015-2019'
                ELSE '2020-2025'
            END as periode,
            COUNT(*) as total,
            ROUND(SUM(CASE WHEN e.lieu_ref_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN e.heure IS NOT NULL AND e.heure != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1),
            ROUND(SUM(CASE WHEN e.tarif_raw IS NOT NULL AND e.tarif_raw != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
        FROM evenement e
        JOIN bidul b ON b.numero = e.bidul_numero
        GROUP BY periode
        ORDER BY periode
    """)
    result['evolution'] = [
        {'periode': r[0], 'total': r[1], 'lieu': r[2] or 0, 'heure': r[3] or 0, 'tarif': r[4] or 0}
        for r in cur.fetchall()
    ]

    # Score par Bidul
    cur.execute("""
        WITH event_quality AS (
            SELECT
                e.bidul_numero,
                CASE WHEN e.lieu_ref_id IS NOT NULL THEN 1 ELSE 0 END as lieu_ok,
                CASE WHEN e.heure IS NOT NULL AND e.heure != '' THEN 1 ELSE 0 END as heure_ok,
                CASE WHEN e.tarif_raw IS NOT NULL AND e.tarif_raw != '' THEN 1 ELSE 0 END as tarif_ok,
                CASE
                    WHEN EXISTS (SELECT 1 FROM contenu_evenement ce WHERE ce.evenement_id = e.id AND (ce.artiste_ref_id IS NOT NULL OR (ce.style IS NOT NULL AND ce.style != ''))) THEN 1
                    WHEN NOT EXISTS (SELECT 1 FROM contenu_evenement ce WHERE ce.evenement_id = e.id) AND e.nom IS NOT NULL AND e.nom != '' THEN 1
                    ELSE 0
                END as contenu_ok
            FROM evenement e
        )
        SELECT bidul_numero, ROUND((AVG(lieu_ok) + AVG(heure_ok) + AVG(tarif_ok) + AVG(contenu_ok)) / 4 * 100, 1)
        FROM event_quality
        GROUP BY bidul_numero
        ORDER BY bidul_numero
    """)
    result['score_par_bidul'] = [{'bidul': r[0], 'score': r[1] or 0} for r in cur.fetchall()]

    # Top lieux non normalisés
    cur.execute("""
        SELECT lieu_raw, COUNT(*) FROM evenement
        WHERE lieu_ref_id IS NULL AND lieu_raw IS NOT NULL AND lieu_raw != ''
        GROUP BY lieu_raw ORDER BY COUNT(*) DESC LIMIT 10
    """)
    result['top_lieux_non_norm'] = [{'lieu': r[0], 'count': r[1]} for r in cur.fetchall()]

    # Top artistes non normalisés
    cur.execute("""
        SELECT artiste, COUNT(*) FROM contenu_evenement
        WHERE artiste_ref_id IS NULL AND artiste IS NOT NULL AND artiste != ''
        GROUP BY artiste ORDER BY COUNT(*) DESC LIMIT 10
    """)
    result['top_artistes_non_norm'] = [{'artiste': r[0], 'count': r[1]} for r in cur.fetchall()]

    # Distribution styles
    cur.execute("""
        SELECT style, COUNT(*) FROM contenu_evenement
        WHERE style IS NOT NULL AND style != ''
        GROUP BY style ORDER BY COUNT(*) DESC LIMIT 15
    """)
    result['distribution_styles'] = [{'style': r[0], 'count': r[1]} for r in cur.fetchall()]

    conn.close()
    return result


def get_stats_data(db_path: str) -> List[Dict[str, Any]]:
    """
    Récupère les statistiques d'événements et contenus par Bidul.

    Returns:
        Liste de dicts avec: bidul, events, events_local, events_regional, content, missing
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Récupérer les numéros existants dans la table bidul
    cur.execute("SELECT numero FROM bidul ORDER BY numero")
    existing_biduls = set(row[0] for row in cur.fetchall())

    # Récupérer les stats avec CTE récursive - incluant local/regional
    cur.execute("""
        WITH RECURSIVE all_numeros(numero) AS (
            SELECT 1
            UNION ALL
            SELECT numero + 1 FROM all_numeros WHERE numero < 308
        )
        SELECT
            a.numero as bidul_numero,
            COUNT(DISTINCT e.id) as nb_evenements,
            COUNT(DISTINCT CASE WHEN e.is_regional = 0 OR e.is_regional IS NULL THEN e.id END) as nb_local,
            COUNT(DISTINCT CASE WHEN e.is_regional = 1 THEN e.id END) as nb_regional,
            COALESCE(COUNT(CASE WHEN ce.artiste IS NOT NULL OR ce.nom_spectacle IS NOT NULL THEN 1 END), 0) as nb_contenus
        FROM all_numeros a
        LEFT JOIN evenement e ON e.bidul_numero = a.numero
        LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
        GROUP BY a.numero
        ORDER BY a.numero
    """)

    data = []
    for row in cur.fetchall():
        data.append({
            "bidul": row[0],
            "events": row[1],
            "events_local": row[2],
            "events_regional": row[3],
            "content": row[4],
            "missing": row[0] not in existing_biduls
        })

    conn.close()
    return data


def get_aggregated_stats(db_path: str, axis: str = 'numero_bidul') -> Dict[str, Any]:
    """
    Récupère les statistiques agrégées selon l'axe choisi.

    Args:
        db_path: Chemin vers la base de données
        axis: Axe d'agrégation ('numero_bidul', 'mois', 'semaine', 'jour')

    Returns:
        Dict avec labels et données par série
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    result = {'labels': [], 'events': [], 'local': [], 'regional': [], 'content': []}

    if axis == 'numero_bidul':
        # Agrégation par numéro de bidul (existant)
        cur.execute("""
            SELECT
                b.numero,
                COUNT(DISTINCT e.id) as nb_evenements,
                COUNT(DISTINCT CASE WHEN e.is_regional = 0 OR e.is_regional IS NULL THEN e.id END) as nb_local,
                COUNT(DISTINCT CASE WHEN e.is_regional = 1 THEN e.id END) as nb_regional,
                COALESCE(COUNT(CASE WHEN ce.artiste IS NOT NULL OR ce.nom_spectacle IS NOT NULL THEN 1 END), 0) as nb_contenus
            FROM bidul b
            LEFT JOIN evenement e ON e.bidul_numero = b.numero
            LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
            GROUP BY b.numero
            ORDER BY b.numero
        """)
        for row in cur.fetchall():
            result['labels'].append(str(row[0]))
            result['events'].append(row[1])
            result['local'].append(row[2])
            result['regional'].append(row[3])
            result['content'].append(row[4])

    elif axis == 'mois':
        # Agrégation par mois calendaire (YYYY-MM)
        cur.execute("""
            SELECT
                strftime('%Y-%m', e.date_evenement) as mois,
                COUNT(DISTINCT e.id) as nb_evenements,
                COUNT(DISTINCT CASE WHEN e.is_regional = 0 OR e.is_regional IS NULL THEN e.id END) as nb_local,
                COUNT(DISTINCT CASE WHEN e.is_regional = 1 THEN e.id END) as nb_regional,
                COALESCE(COUNT(CASE WHEN ce.artiste IS NOT NULL OR ce.nom_spectacle IS NOT NULL THEN 1 END), 0) as nb_contenus
            FROM evenement e
            LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
            WHERE e.date_evenement IS NOT NULL
            GROUP BY mois
            ORDER BY mois
        """)
        for row in cur.fetchall():
            if row[0]:
                result['labels'].append(row[0])
                result['events'].append(row[1])
                result['local'].append(row[2])
                result['regional'].append(row[3])
                result['content'].append(row[4])

    elif axis == 'semaine':
        # Agrégation par semaine ISO (YYYY-WXX)
        cur.execute("""
            SELECT
                strftime('%Y-W%W', e.date_evenement) as semaine,
                COUNT(DISTINCT e.id) as nb_evenements,
                COUNT(DISTINCT CASE WHEN e.is_regional = 0 OR e.is_regional IS NULL THEN e.id END) as nb_local,
                COUNT(DISTINCT CASE WHEN e.is_regional = 1 THEN e.id END) as nb_regional,
                COALESCE(COUNT(CASE WHEN ce.artiste IS NOT NULL OR ce.nom_spectacle IS NOT NULL THEN 1 END), 0) as nb_contenus
            FROM evenement e
            LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
            WHERE e.date_evenement IS NOT NULL
            GROUP BY semaine
            ORDER BY semaine
        """)
        for row in cur.fetchall():
            if row[0]:
                result['labels'].append(row[0])
                result['events'].append(row[1])
                result['local'].append(row[2])
                result['regional'].append(row[3])
                result['content'].append(row[4])

    elif axis == 'jour':
        # Agrégation par jour de la semaine (0=lundi, 6=dimanche)
        cur.execute("""
            SELECT
                CAST(strftime('%w', e.date_evenement) AS INTEGER) as dow,
                COUNT(DISTINCT e.id) as nb_evenements,
                COUNT(DISTINCT CASE WHEN e.is_regional = 0 OR e.is_regional IS NULL THEN e.id END) as nb_local,
                COUNT(DISTINCT CASE WHEN e.is_regional = 1 THEN e.id END) as nb_regional,
                COALESCE(COUNT(CASE WHEN ce.artiste IS NOT NULL OR ce.nom_spectacle IS NOT NULL THEN 1 END), 0) as nb_contenus
            FROM evenement e
            LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
            WHERE e.date_evenement IS NOT NULL
            GROUP BY dow
            ORDER BY dow
        """)
        # SQLite %w: 0=dimanche, 1=lundi, ..., 6=samedi
        # On veut: 0=lundi, ..., 6=dimanche
        rows = list(cur.fetchall())
        # Réorganiser: dimanche (0) -> 6, lundi (1) -> 0, etc.
        day_data = {(row[0] - 1) % 7 if row[0] > 0 else 6: row for row in rows}
        for i in range(7):
            result['labels'].append(JOURS_SEMAINE[i])
            if i in day_data:
                row = day_data[i]
                result['events'].append(row[1])
                result['local'].append(row[2])
                result['regional'].append(row[3])
                result['content'].append(row[4])
            else:
                result['events'].append(0)
                result['local'].append(0)
                result['regional'].append(0)
                result['content'].append(0)

    conn.close()
    return result


def get_events_by_day_over_time(db_path: str, granularity: str = 'monthly') -> Dict[str, Any]:
    """
    Récupère l'évolution du nombre d'événements par jour de la semaine dans le temps.

    Args:
        db_path: Chemin vers la base de données
        granularity: 'monthly' pour agrégation mensuelle, 'weekly' pour hebdomadaire

    Returns:
        Dict avec:
        - labels: liste des périodes (YYYY-MM ou YYYY-WXX)
        - datasets: dict {jour: [valeurs par période]}
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if granularity == 'weekly':
        # Récupérer toutes les semaines
        cur.execute("""
            SELECT DISTINCT strftime('%Y-W%W', date_evenement) as semaine
            FROM evenement
            WHERE date_evenement IS NOT NULL
            ORDER BY semaine
        """)
        all_periods = [row[0] for row in cur.fetchall() if row[0]]
        period_format = '%Y-W%W'
    else:
        # Récupérer tous les mois
        cur.execute("""
            SELECT DISTINCT strftime('%Y-%m', date_evenement) as mois
            FROM evenement
            WHERE date_evenement IS NOT NULL
            ORDER BY mois
        """)
        all_periods = [row[0] for row in cur.fetchall() if row[0]]
        period_format = '%Y-%m'

    # Pour chaque jour de la semaine, récupérer le nombre d'événements par période
    # SQLite %w: 0=dimanche, 1=lundi, ..., 6=samedi
    datasets = {jour: [] for jour in JOURS_SEMAINE}

    for period in all_periods:
        cur.execute(f"""
            SELECT
                CAST(strftime('%w', date_evenement) AS INTEGER) as dow,
                COUNT(*) as nb
            FROM evenement
            WHERE strftime('{period_format}', date_evenement) = ?
            GROUP BY dow
        """, (period,))
        counts = {row[0]: row[1] for row in cur.fetchall()}

        # Convertir SQLite dow (0=dim) vers notre format (0=lun)
        for sqlite_dow in range(7):
            # 0(dim)->6, 1(lun)->0, 2(mar)->1, etc.
            our_dow = (sqlite_dow - 1) % 7 if sqlite_dow > 0 else 6
            jour_name = JOURS_SEMAINE[our_dow]
            datasets[jour_name].append(counts.get(sqlite_dow, 0))

    conn.close()
    return {'labels': all_periods, 'datasets': datasets}


def get_top_lieux_evolution(db_path: str, top_n: int = 10, granularity: str = 'monthly') -> Dict[str, Any]:
    """
    Récupère l'évolution temporelle des top N lieux.

    Args:
        db_path: Chemin vers la base de données
        top_n: Nombre de lieux à inclure
        granularity: 'monthly' pour mensuel, 'yearly' pour annuel

    Returns:
        Dict avec:
        - labels: liste des périodes (YYYY-MM ou YYYY)
        - datasets: dict {lieu: [valeurs par période]}
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Identifier les top N lieux
    cur.execute("""
        SELECT COALESCE(lr.nom, e.lieu_raw) as lieu, COUNT(*) as nb
        FROM evenement e
        LEFT JOIN lieu_ref lr ON lr.id = e.lieu_ref_id
        WHERE e.lieu_raw IS NOT NULL AND e.lieu_raw != ''
        GROUP BY lieu
        ORDER BY nb DESC
        LIMIT ?
    """, (top_n,))
    top_lieux = [row[0] for row in cur.fetchall() if row[0]]

    # Récupérer toutes les périodes
    if granularity == 'yearly':
        period_format = '%Y'
        cur.execute("""
            SELECT DISTINCT strftime('%Y', date_evenement) as periode
            FROM evenement
            WHERE date_evenement IS NOT NULL
            ORDER BY periode
        """)
    else:
        period_format = '%Y-%m'
        cur.execute("""
            SELECT DISTINCT strftime('%Y-%m', date_evenement) as periode
            FROM evenement
            WHERE date_evenement IS NOT NULL
            ORDER BY periode
        """)
    all_periods = [row[0] for row in cur.fetchall() if row[0]]

    datasets = {lieu: [] for lieu in top_lieux}

    for period in all_periods:
        cur.execute(f"""
            SELECT COALESCE(lr.nom, e.lieu_raw) as lieu, COUNT(*) as nb
            FROM evenement e
            LEFT JOIN lieu_ref lr ON lr.id = e.lieu_ref_id
            WHERE strftime('{period_format}', e.date_evenement) = ?
              AND e.lieu_raw IS NOT NULL AND e.lieu_raw != ''
            GROUP BY lieu
        """, (period,))
        counts = {row[0]: row[1] for row in cur.fetchall()}

        for lieu in top_lieux:
            datasets[lieu].append(counts.get(lieu, 0))

    conn.close()
    return {'labels': all_periods, 'datasets': datasets, 'top_lieux': top_lieux}


def get_top_artistes_evolution(db_path: str, top_n: int = 10, granularity: str = 'monthly') -> Dict[str, Any]:
    """
    Récupère l'évolution temporelle des top N artistes.

    Args:
        db_path: Chemin vers la base de données
        top_n: Nombre d'artistes à inclure
        granularity: 'monthly' pour mensuel, 'yearly' pour annuel

    Returns:
        Dict avec:
        - labels: liste des périodes (YYYY-MM ou YYYY)
        - datasets: dict {artiste: [valeurs par période]}
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Identifier les top N artistes
    cur.execute("""
        SELECT COALESCE(ar.nom, ce.artiste) as artiste_nom, COUNT(*) as nb
        FROM contenu_evenement ce
        LEFT JOIN artiste_ref ar ON ar.id = ce.artiste_ref_id
        WHERE ce.artiste IS NOT NULL AND ce.artiste != ''
        GROUP BY artiste_nom
        ORDER BY nb DESC
        LIMIT ?
    """, (top_n,))
    top_artistes = [row[0] for row in cur.fetchall() if row[0]]

    # Récupérer toutes les périodes
    if granularity == 'yearly':
        period_format = '%Y'
        cur.execute("""
            SELECT DISTINCT strftime('%Y', e.date_evenement) as periode
            FROM evenement e
            WHERE e.date_evenement IS NOT NULL
            ORDER BY periode
        """)
    else:
        period_format = '%Y-%m'
        cur.execute("""
            SELECT DISTINCT strftime('%Y-%m', e.date_evenement) as periode
            FROM evenement e
            WHERE e.date_evenement IS NOT NULL
            ORDER BY periode
        """)
    all_periods = [row[0] for row in cur.fetchall() if row[0]]

    datasets = {artiste: [] for artiste in top_artistes}

    for period in all_periods:
        cur.execute(f"""
            SELECT COALESCE(ar.nom, ce.artiste) as artiste_nom, COUNT(*) as nb
            FROM contenu_evenement ce
            JOIN evenement e ON e.id = ce.evenement_id
            LEFT JOIN artiste_ref ar ON ar.id = ce.artiste_ref_id
            WHERE strftime('{period_format}', e.date_evenement) = ?
              AND ce.artiste IS NOT NULL AND ce.artiste != ''
            GROUP BY artiste_nom
        """, (period,))
        counts = {row[0]: row[1] for row in cur.fetchall()}

        for artiste in top_artistes:
            datasets[artiste].append(counts.get(artiste, 0))

    conn.close()
    return {'labels': all_periods, 'datasets': datasets, 'top_artistes': top_artistes}


def get_extended_stats(db_path: str) -> Dict[str, Any]:
    """
    Récupère toutes les statistiques étendues pour le dashboard.

    Returns:
        Dict avec toutes les données pré-calculées pour les différents axes et KPIs
    """
    return {
        'by_bidul': get_aggregated_stats(db_path, 'numero_bidul'),
        'by_mois': get_aggregated_stats(db_path, 'mois'),
        'by_semaine': get_aggregated_stats(db_path, 'semaine'),
        'by_jour': get_aggregated_stats(db_path, 'jour'),
        'events_by_day_monthly': get_events_by_day_over_time(db_path, 'monthly'),
        'events_by_day_weekly': get_events_by_day_over_time(db_path, 'weekly'),
        'top_lieux_monthly': get_top_lieux_evolution(db_path, granularity='monthly'),
        'top_lieux_yearly': get_top_lieux_evolution(db_path, granularity='yearly'),
        'top_artistes_monthly': get_top_artistes_evolution(db_path, granularity='monthly'),
        'top_artistes_yearly': get_top_artistes_evolution(db_path, granularity='yearly'),
    }


def generate_html(data: List[Dict[str, Any]], output_path: str, quality_data: Dict[str, Any] = None,
                  extended_stats: Dict[str, Any] = None) -> str:
    """
    Génère le fichier HTML avec le dashboard.

    Args:
        data: Données des stats par Bidul
        output_path: Chemin du fichier à créer
        quality_data: Données de qualité (optionnel)
        extended_stats: Données étendues pour les nouvelles visualisations (optionnel)

    Returns:
        Chemin absolu du fichier créé
    """
    data_json = json.dumps(data)
    quality_json = json.dumps(quality_data or {})
    extended_json = json.dumps(extended_stats or {})
    html_content = HTML_TEMPLATE.replace('__DATA_PLACEHOLDER__', data_json)
    html_content = html_content.replace('__QUALITY_PLACEHOLDER__', quality_json)
    html_content = html_content.replace('__EXTENDED_PLACEHOLDER__', extended_json)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_content, encoding='utf-8')

    return str(output_file.absolute())


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bidul Indexer - Statistiques</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #111827;
            color: #f3f4f6;
            padding: 20px;
            min-height: 100vh;
        }
        h1 { text-align: center; margin-bottom: 10px; font-size: 1.5rem; }
        h2 { text-align: center; margin: 20px 0 15px; font-size: 1.2rem; color: #9ca3af; }
        h3.section-title {
            font-size: 1rem;
            color: #9ca3af;
            margin: 25px 0 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid #374151;
        }

        .stats {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .stat {
            background: #1f2937;
            padding: 10px 15px;
            border-radius: 8px;
            text-align: center;
        }
        .stat.missing { border: 1px solid #831843; }
        .stat.empty { border: 1px solid #991b1b; }
        .stat.quality { border: 2px solid #8b5cf6; background: linear-gradient(135deg, #1f2937 0%, #2d1f47 100%); }
        .stat-label { color: #9ca3af; font-size: 0.8rem; }
        .stat-value { font-size: 1.3rem; font-weight: bold; }
        .stat-value.cyan { color: #06b6d4; }
        .stat-value.amber { color: #f59e0b; }
        .stat-value.green { color: #22c55e; }
        .stat-value.pink { color: #ec4899; }
        .stat-value.red { color: #ef4444; }
        .stat-value.purple { color: #8b5cf6; }
        .stat-sub { color: #6b7280; font-size: 0.7rem; }

        .controls {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        .btn {
            background: #374151;
            border: none;
            color: #f3f4f6;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .btn:hover { background: #4b5563; }
        .btn.active { background: #4f46e5; }
        .btn.purple.active { background: #7c3aed; }
        .btn.teal.active { background: #0d9488; }

        /* Axis selector */
        .axis-selector {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        .axis-selector label {
            color: #9ca3af;
            font-size: 0.85rem;
        }
        .axis-selector select {
            background: #374151;
            border: 1px solid #4b5563;
            color: #f3f4f6;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
        }
        .axis-selector select:focus {
            outline: none;
            border-color: #6366f1;
        }

        /* Collapsible sections */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            padding: 10px 15px;
            background: #1f2937;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .section-header:hover { background: #374151; }
        .section-header h3 { margin: 0; font-size: 0.95rem; }
        .section-header .toggle-icon {
            font-size: 1.2rem;
            transition: transform 0.3s;
        }
        .section-header.collapsed .toggle-icon { transform: rotate(-90deg); }
        .section-content { margin-bottom: 20px; }
        .section-content.hidden { display: none; }

        .legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 10px;
            font-size: 0.8rem;
            flex-wrap: wrap;
        }
        .legend-item { display: flex; align-items: center; gap: 5px; }
        .legend-color { width: 12px; height: 12px; border-radius: 2px; }

        .chart-container {
            background: #1f2937;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            height: 400px;
        }

        /* Completeness section */
        .completeness-section {
            background: #1f2937;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .completeness-section h3 {
            font-size: 0.95rem;
            margin-bottom: 15px;
            color: #9ca3af;
            text-align: center;
        }
        .progress-bars {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 12px;
        }
        .progress-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .progress-label {
            width: 140px;
            font-size: 0.8rem;
            color: #9ca3af;
        }
        .progress-bar {
            flex: 1;
            height: 8px;
            background: #374151;
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        .progress-fill.high { background: #22c55e; }
        .progress-fill.medium { background: #f59e0b; }
        .progress-fill.low { background: #ef4444; }
        .progress-value {
            width: 50px;
            text-align: right;
            font-size: 0.8rem;
            font-weight: bold;
        }

        /* Evolution chart */
        .evolution-container {
            background: #1f2937;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            height: 250px;
        }

        .details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }
        .detail-box {
            background: #1f2937;
            padding: 15px;
            border-radius: 8px;
        }
        .detail-box.missing { border: 1px solid #831843; }
        .detail-box h3 { margin-bottom: 10px; font-size: 0.95rem; }
        .detail-box h3.pink { color: #ec4899; }
        .detail-box h3.red { color: #ef4444; }
        .detail-box h3.yellow { color: #eab308; }
        .detail-box h3.purple { color: #a855f7; }
        .detail-box h3.orange { color: #f97316; }
        .detail-box h3.blue { color: #06b6d4; }
        .detail-box h3.green { color: #22c55e; }
        .detail-list { font-size: 0.85rem; max-height: 150px; overflow-y: auto; }
        .detail-row { display: flex; justify-content: space-between; padding: 2px 0; }
        .detail-row span:first-child {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 180px;
        }
        .mono { font-family: monospace; }

        .footer { text-align: center; margin-top: 20px; color: #6b7280; font-size: 0.8rem; }
    </style>
</head>
<body>
    <h1>Bidul Indexer - Dashboard</h1>

    <div class="stats">
        <div class="stat">
            <div class="stat-label">Evenements</div>
            <div class="stat-value cyan" id="totalEvents">-</div>
            <div class="stat-sub" id="avgEvents">-</div>
        </div>
        <div class="stat">
            <div class="stat-label">Locaux</div>
            <div class="stat-value cyan" id="totalLocal">-</div>
            <div class="stat-sub" id="pctLocal">-</div>
        </div>
        <div class="stat">
            <div class="stat-label">Regionaux</div>
            <div class="stat-value" style="color:#a78bfa" id="totalRegional">-</div>
            <div class="stat-sub" id="pctRegional">-</div>
        </div>
        <div class="stat">
            <div class="stat-label">Contenus</div>
            <div class="stat-value amber" id="totalContent">-</div>
            <div class="stat-sub" id="avgContent">-</div>
        </div>
        <div class="stat">
            <div class="stat-label">Ratio</div>
            <div class="stat-value green" id="ratio">-</div>
            <div class="stat-sub">contenu/evenement</div>
        </div>
        <div class="stat quality">
            <div class="stat-label">Score Qualite</div>
            <div class="stat-value purple" id="qualityScore">-</div>
            <div class="stat-sub" id="qualityDetail">-</div>
        </div>
        <div class="stat missing">
            <div class="stat-label">PDFs manquants</div>
            <div class="stat-value pink" id="missingCount">-</div>
        </div>
        <div class="stat empty">
            <div class="stat-label">Biduls vides</div>
            <div class="stat-value red" id="emptyCount">-</div>
        </div>
    </div>

    <!-- Completeness bars -->
    <div class="completeness-section" id="completenessSection" style="display:none">
        <h3>Completude des champs</h3>
        <div class="progress-bars">
            <div class="progress-item">
                <span class="progress-label">Lieu normalise</span>
                <div class="progress-bar"><div class="progress-fill" id="pctLieu"></div></div>
                <span class="progress-value" id="valLieu">-</span>
            </div>
            <div class="progress-item">
                <span class="progress-label">Lieu raw</span>
                <div class="progress-bar"><div class="progress-fill" id="pctLieuRaw"></div></div>
                <span class="progress-value" id="valLieuRaw">-</span>
            </div>
            <div class="progress-item">
                <span class="progress-label">Heure</span>
                <div class="progress-bar"><div class="progress-fill" id="pctHeure"></div></div>
                <span class="progress-value" id="valHeure">-</span>
            </div>
            <div class="progress-item">
                <span class="progress-label">Tarif</span>
                <div class="progress-bar"><div class="progress-fill" id="pctTarif"></div></div>
                <span class="progress-value" id="valTarif">-</span>
            </div>
            <div class="progress-item">
                <span class="progress-label">Artiste normalise</span>
                <div class="progress-bar"><div class="progress-fill" id="pctArtiste"></div></div>
                <span class="progress-value" id="valArtiste">-</span>
            </div>
            <div class="progress-item">
                <span class="progress-label">Style</span>
                <div class="progress-bar"><div class="progress-fill" id="pctStyle"></div></div>
                <span class="progress-value" id="valStyle">-</span>
            </div>
        </div>
    </div>

    <!-- Axis selector -->
    <div class="axis-selector">
        <label for="axisSelect">Axe horizontal:</label>
        <select id="axisSelect" onchange="changeAxis(this.value)">
            <option value="numero_bidul">Numero Bidul</option>
            <option value="mois">Mois (YYYY-MM)</option>
            <option value="semaine">Semaine (YYYY-WXX)</option>
            <option value="jour">Jour de la semaine</option>
        </select>
    </div>

    <div class="controls">
        <button class="btn active" onclick="setView('both')">Tous</button>
        <button class="btn" onclick="setView('events')">Evenements</button>
        <button class="btn" onclick="setView('local')">Locaux</button>
        <button class="btn" onclick="setView('regional')">Regionaux</button>
        <button class="btn" onclick="setView('content')">Contenus</button>
        <button class="btn purple" id="qualityBtn" onclick="toggleQuality()">Qualite</button>
        <button class="btn teal" id="kpiBtn" onclick="toggleKPI()">KPI Avances</button>
    </div>

    <div class="legend">
        <div class="legend-item"><div class="legend-color" style="background:#06b6d4"></div> Evenements locaux</div>
        <div class="legend-item"><div class="legend-color" style="background:#a78bfa"></div> Evenements regionaux</div>
        <div class="legend-item"><div class="legend-color" style="background:#f59e0b"></div> Artistes/Spectacles</div>
        <div class="legend-item"><div class="legend-color" style="background:#8b5cf6"></div> Score Qualite</div>
        <div class="legend-item"><div class="legend-color" style="background:#831843; border: 1px solid #be185d"></div> PDF manquant</div>
        <div class="legend-item"><div class="legend-color" style="background:#ef4444"></div> Vide (0)</div>
    </div>

    <div class="chart-container">
        <canvas id="mainChart"></canvas>
    </div>

    <!-- Evolution chart -->
    <div class="evolution-container" id="evolutionContainer" style="display:none">
        <canvas id="evolutionChart"></canvas>
    </div>

    <!-- Advanced KPI section -->
    <div id="kpiSection" style="display:none">
        <!-- Events by day of week over time -->
        <div class="section-header" onclick="toggleSection('dayOfWeek')">
            <h3 style="color:#14b8a6">Evolution par jour de la semaine</h3>
            <span class="toggle-icon">&#9660;</span>
        </div>
        <div class="section-content" id="dayOfWeekContent">
            <div class="axis-selector" style="margin-bottom:10px">
                <label for="dowGranularity">Granularite:</label>
                <select id="dowGranularity" onchange="changeDowGranularity(this.value)">
                    <option value="monthly">Mensuelle</option>
                    <option value="weekly">Hebdomadaire</option>
                </select>
            </div>
            <div class="chart-container" style="height:350px">
                <canvas id="dayOfWeekChart"></canvas>
            </div>
        </div>

        <!-- Top 10 lieux evolution -->
        <div class="section-header" onclick="toggleSection('topLieux')">
            <h3 style="color:#f97316">Top 10 Lieux - Evolution</h3>
            <span class="toggle-icon">&#9660;</span>
        </div>
        <div class="section-content" id="topLieuxContent">
            <div class="axis-selector" style="margin-bottom:10px">
                <label for="lieuxGranularity">Granularite:</label>
                <select id="lieuxGranularity" onchange="changeLieuxGranularity(this.value)">
                    <option value="monthly">Mensuelle</option>
                    <option value="yearly">Annuelle</option>
                </select>
            </div>
            <div class="chart-container" style="height:350px">
                <canvas id="topLieuxChart"></canvas>
            </div>
        </div>

        <!-- Top 10 artistes evolution -->
        <div class="section-header" onclick="toggleSection('topArtistes')">
            <h3 style="color:#06b6d4">Top 10 Artistes - Evolution</h3>
            <span class="toggle-icon">&#9660;</span>
        </div>
        <div class="section-content" id="topArtistesContent">
            <div class="axis-selector" style="margin-bottom:10px">
                <label for="artistesGranularity">Granularite:</label>
                <select id="artistesGranularity" onchange="changeArtistesGranularity(this.value)">
                    <option value="monthly">Mensuelle</option>
                    <option value="yearly">Annuelle</option>
                </select>
            </div>
            <div class="chart-container" style="height:350px">
                <canvas id="topArtistesChart"></canvas>
            </div>
        </div>
    </div>

    <div class="details">
        <div class="detail-box missing">
            <h3 class="pink">PDFs manquants</h3>
            <div class="mono" id="missingList">-</div>
        </div>
        <div class="detail-box">
            <h3 class="red">Biduls vides</h3>
            <div class="detail-list" id="emptyList">-</div>
        </div>
        <div class="detail-box">
            <h3 class="yellow">Ratios anormaux</h3>
            <div class="detail-list" id="anomaliesList">-</div>
        </div>
        <div class="detail-box">
            <h3 class="purple">Top 10 Biduls</h3>
            <div class="detail-list" id="topList">-</div>
        </div>
        <div class="detail-box" id="lieuxBox" style="display:none">
            <h3 class="orange">Lieux a normaliser</h3>
            <div class="detail-list" id="lieuxNonNorm">-</div>
        </div>
        <div class="detail-box" id="artistesBox" style="display:none">
            <h3 class="blue">Artistes a normaliser</h3>
            <div class="detail-list" id="artistesNonNorm">-</div>
        </div>
        <div class="detail-box" id="stylesBox" style="display:none">
            <h3 class="green">Top styles</h3>
            <div class="detail-list" id="topStyles">-</div>
        </div>
    </div>

    <div class="footer">
        Genere par Bidul Indexer v1.15 - <span id="genDate"></span>
    </div>

    <script>
        const data = __DATA_PLACEHOLDER__;
        const quality = __QUALITY_PLACEHOLDER__;
        const extended = __EXTENDED_PLACEHOLDER__;
        const hasQuality = quality && Object.keys(quality).length > 0;
        const hasExtended = extended && Object.keys(extended).length > 0;

        // Calculs
        const existing = data.filter(d => !d.missing);
        const eventsTotal = existing.reduce((s, d) => s + d.events, 0);
        const eventsLocalTotal = existing.reduce((s, d) => s + (d.events_local || 0), 0);
        const eventsRegionalTotal = existing.reduce((s, d) => s + (d.events_regional || 0), 0);
        const contentTotal = existing.reduce((s, d) => s + d.content, 0);
        const eventsAvg = eventsTotal / existing.length;
        const contentAvg = contentTotal / existing.length;
        const ratio = eventsTotal > 0 ? contentTotal / eventsTotal : 0;
        const missingBiduls = data.filter(d => d.missing).map(d => d.bidul);
        const emptyBiduls = data.filter(d => d.events === 0 && !d.missing).map(d => d.bidul);
        const pctLocal = eventsTotal > 0 ? (eventsLocalTotal / eventsTotal * 100).toFixed(1) : 0;
        const pctRegional = eventsTotal > 0 ? (eventsRegionalTotal / eventsTotal * 100).toFixed(1) : 0;

        // Anomalies (ratio tres different)
        const anomalies = existing.filter(d => {
            if (d.events < 10) return false;
            const r = d.content / d.events;
            return r < 0.5 || r > 3;
        }).map(d => ({ ...d, ratio: (d.content / d.events).toFixed(2) }));

        // Top 10
        const top10 = [...existing].sort((a, b) => b.events - a.events).slice(0, 10);

        // Mise a jour stats
        document.getElementById('totalEvents').textContent = eventsTotal.toLocaleString();
        document.getElementById('avgEvents').textContent = `moy: ${eventsAvg.toFixed(0)}`;
        document.getElementById('totalLocal').textContent = eventsLocalTotal.toLocaleString();
        document.getElementById('pctLocal').textContent = `${pctLocal}%`;
        document.getElementById('totalRegional').textContent = eventsRegionalTotal.toLocaleString();
        document.getElementById('pctRegional').textContent = `${pctRegional}%`;
        document.getElementById('totalContent').textContent = contentTotal.toLocaleString();
        document.getElementById('avgContent').textContent = `moy: ${contentAvg.toFixed(0)}`;
        document.getElementById('ratio').textContent = ratio.toFixed(2);
        document.getElementById('missingCount').textContent = missingBiduls.length;
        document.getElementById('emptyCount').textContent = emptyBiduls.length;
        document.getElementById('genDate').textContent = new Date().toLocaleString('fr-FR');

        // Quality score
        if (hasQuality) {
            const scoreEl = document.getElementById('qualityScore');
            scoreEl.textContent = quality.score_global + '%';
            scoreEl.style.color = quality.score_global >= 70 ? '#22c55e' :
                                   quality.score_global >= 50 ? '#f59e0b' : '#ef4444';
            document.getElementById('qualityDetail').textContent =
                `${quality.complets.toLocaleString()} / ${quality.total.toLocaleString()} complets`;

            // Progress bars
            function setProgress(id, value) {
                const fill = document.getElementById('pct' + id);
                const val = document.getElementById('val' + id);
                if (!fill || !val) return;
                fill.style.width = value + '%';
                fill.className = 'progress-fill ' + (value >= 80 ? 'high' : value >= 50 ? 'medium' : 'low');
                val.textContent = value + '%';
                val.style.color = value >= 80 ? '#22c55e' : value >= 50 ? '#f59e0b' : '#ef4444';
            }

            setProgress('Lieu', quality.completude.lieu_normalise);
            setProgress('LieuRaw', quality.completude.lieu_raw);
            setProgress('Heure', quality.completude.heure);
            setProgress('Tarif', quality.completude.tarif);
            setProgress('Artiste', quality.completude.artiste_normalise);
            setProgress('Style', quality.completude.style);

            // Lieux non normalises
            if (quality.top_lieux_non_norm && quality.top_lieux_non_norm.length > 0) {
                document.getElementById('lieuxNonNorm').innerHTML = quality.top_lieux_non_norm
                    .map(d => `<div class="detail-row"><span>${d.lieu.substring(0, 35)}</span><span style="color:#f97316">${d.count}</span></div>`)
                    .join('');
            }

            // Artistes non normalises
            if (quality.top_artistes_non_norm && quality.top_artistes_non_norm.length > 0) {
                document.getElementById('artistesNonNorm').innerHTML = quality.top_artistes_non_norm
                    .map(d => `<div class="detail-row"><span>${d.artiste.substring(0, 35)}</span><span style="color:#06b6d4">${d.count}</span></div>`)
                    .join('');
            }

            // Styles
            if (quality.distribution_styles && quality.distribution_styles.length > 0) {
                document.getElementById('topStyles').innerHTML = quality.distribution_styles
                    .map(d => `<div class="detail-row"><span>${d.style}</span><span style="color:#22c55e">${d.count}</span></div>`)
                    .join('');
            }
        }

        // Details
        document.getElementById('missingList').textContent = missingBiduls.length > 0 ? missingBiduls.join(', ') : 'Aucun';
        document.getElementById('emptyList').innerHTML = emptyBiduls.length > 0
            ? emptyBiduls.map(b => `<div>Bidul ${b}</div>`).join('')
            : 'Aucun';
        document.getElementById('anomaliesList').innerHTML = anomalies.length > 0
            ? anomalies.slice(0, 10).map(d =>
                `<div class="detail-row"><span>B${d.bidul}</span><span>${d.events}->${d.content}</span><span style="color:${d.ratio < 1 ? '#ef4444' : '#22c55e'}">${d.ratio}</span></div>`
              ).join('')
            : 'Aucun';
        document.getElementById('topList').innerHTML = top10.map((d, i) =>
            `<div class="detail-row"><span>${i+1}. B${d.bidul}</span><span style="color:#06b6d4">${d.events}</span><span style="color:#f59e0b">${d.content}</span></div>`
        ).join('');

        // Couleurs pour les barres
        function getLocalColors() {
            return data.map(d => {
                if (d.missing) return '#831843';
                if (d.events === 0) return '#ef4444';
                return '#06b6d4';
            });
        }

        function getRegionalColors() {
            return data.map(d => {
                if (d.missing) return '#831843';
                return '#a78bfa';
            });
        }

        function getContentColors() {
            return data.map(d => {
                if (d.missing) return '#831843';
                if (d.content === 0) return '#ef4444';
                return '#f59e0b';
            });
        }

        // Main Chart
        const ctx = document.getElementById('mainChart').getContext('2d');
        const datasets = [
            {
                label: 'Evenements locaux',
                data: data.map(d => d.events_local || 0),
                backgroundColor: getLocalColors(),
                borderColor: data.map(d => d.missing ? '#be185d' : 'transparent'),
                borderWidth: data.map(d => d.missing ? 2 : 0),
                stack: 'events',
            },
            {
                label: 'Evenements regionaux',
                data: data.map(d => d.events_regional || 0),
                backgroundColor: getRegionalColors(),
                borderColor: data.map(d => d.missing ? '#be185d' : 'transparent'),
                borderWidth: data.map(d => d.missing ? 2 : 0),
                stack: 'events',
            },
            {
                label: 'Contenus',
                data: data.map(d => d.content),
                backgroundColor: getContentColors(),
                borderColor: data.map(d => d.missing ? '#be185d' : 'transparent'),
                borderWidth: data.map(d => d.missing ? 2 : 0),
                stack: 'content',
            }
        ];

        // Add quality dataset if available
        if (hasQuality && quality.score_par_bidul) {
            const qualityMap = {};
            quality.score_par_bidul.forEach(q => { qualityMap[q.bidul] = q.score; });
            datasets.push({
                label: 'Score Qualite',
                data: data.map(d => qualityMap[d.bidul] || 0),
                type: 'line',
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                yAxisID: 'y1',
                hidden: true
            });
        }

        let chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.bidul),
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1f2937',
                        titleColor: '#f3f4f6',
                        bodyColor: '#9ca3af',
                        callbacks: {
                            title: (items) => `Bidul ${items[0].label}`,
                            label: (item) => {
                                const d = data[item.dataIndex];
                                if (d.missing) return 'PDF MANQUANT';
                                if (item.dataset.label === 'Score Qualite') return `Qualite: ${item.raw}%`;
                                return `${item.dataset.label}: ${item.raw}`;
                            },
                            afterBody: (items) => {
                                const d = data[items[0].dataIndex];
                                if (d.missing || d.events === 0) return '';
                                const lines = [];
                                lines.push(`Total: ${d.events} (${d.events_local || 0} local + ${d.events_regional || 0} regional)`);
                                lines.push(`Ratio: ${(d.content / d.events).toFixed(2)}`);
                                return lines;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#9ca3af',
                            maxRotation: 90,
                            callback: (val, idx) => idx % 10 === 0 ? data[idx].bidul : ''
                        },
                        grid: { display: false }
                    },
                    y: {
                        ticks: { color: '#9ca3af' },
                        grid: { color: '#374151' }
                    },
                    y1: {
                        type: 'linear',
                        display: false,
                        position: 'right',
                        min: 0,
                        max: 100,
                        grid: { drawOnChartArea: false },
                        ticks: {
                            color: '#8b5cf6',
                            callback: v => v + '%'
                        }
                    }
                }
            }
        });

        // Evolution chart
        let evolutionChart = null;
        if (hasQuality && quality.evolution && quality.evolution.length > 0) {
            const evoCtx = document.getElementById('evolutionChart').getContext('2d');
            evolutionChart = new Chart(evoCtx, {
                type: 'bar',
                data: {
                    labels: quality.evolution.map(e => e.periode),
                    datasets: [
                        {
                            label: 'Lieu norm.',
                            data: quality.evolution.map(e => e.lieu),
                            backgroundColor: '#06b6d4',
                        },
                        {
                            label: 'Heure',
                            data: quality.evolution.map(e => e.heure),
                            backgroundColor: '#22c55e',
                        },
                        {
                            label: 'Tarif',
                            data: quality.evolution.map(e => e.tarif),
                            backgroundColor: '#f59e0b',
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            labels: { color: '#9ca3af', boxWidth: 12 }
                        },
                        title: {
                            display: true,
                            text: 'Evolution de la completude par periode',
                            color: '#9ca3af'
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#9ca3af' },
                            grid: { display: false }
                        },
                        y: {
                            min: 0,
                            max: 100,
                            ticks: {
                                color: '#9ca3af',
                                callback: v => v + '%'
                            },
                            grid: { color: '#374151' }
                        }
                    }
                }
            });
        }

        // Boutons de vue
        function setView(view) {
            document.querySelectorAll('.btn:not(.purple)').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            // Datasets: 0=local, 1=regional, 2=content, 3=quality(si existe)
            switch(view) {
                case 'both':
                    chart.data.datasets[0].hidden = false;  // local
                    chart.data.datasets[1].hidden = false;  // regional
                    chart.data.datasets[2].hidden = false;  // content
                    break;
                case 'events':
                    chart.data.datasets[0].hidden = false;  // local
                    chart.data.datasets[1].hidden = false;  // regional
                    chart.data.datasets[2].hidden = true;   // content
                    break;
                case 'local':
                    chart.data.datasets[0].hidden = false;  // local
                    chart.data.datasets[1].hidden = true;   // regional
                    chart.data.datasets[2].hidden = true;   // content
                    break;
                case 'regional':
                    chart.data.datasets[0].hidden = true;   // local
                    chart.data.datasets[1].hidden = false;  // regional
                    chart.data.datasets[2].hidden = true;   // content
                    break;
                case 'content':
                    chart.data.datasets[0].hidden = true;   // local
                    chart.data.datasets[1].hidden = true;   // regional
                    chart.data.datasets[2].hidden = false;  // content
                    break;
            }
            chart.update();
        }

        // Toggle quality view
        let qualityVisible = false;
        function toggleQuality() {
            qualityVisible = !qualityVisible;
            const btn = document.getElementById('qualityBtn');
            btn.classList.toggle('active', qualityVisible);

            // Toggle quality dataset in main chart (index 3 = quality line)
            if (chart.data.datasets.length > 3) {
                chart.data.datasets[3].hidden = !qualityVisible;
                chart.options.scales.y1.display = qualityVisible;
                chart.update();
            }

            // Toggle sections
            document.getElementById('completenessSection').style.display = qualityVisible ? 'block' : 'none';
            document.getElementById('evolutionContainer').style.display = qualityVisible ? 'block' : 'none';
            document.getElementById('lieuxBox').style.display = qualityVisible ? 'block' : 'none';
            document.getElementById('artistesBox').style.display = qualityVisible ? 'block' : 'none';
            document.getElementById('stylesBox').style.display = qualityVisible ? 'block' : 'none';
        }

        // =====================================================
        // NOUVELLES FONCTIONNALITES v1.15
        // =====================================================

        // Colors for days of week
        const dayColors = [
            '#ef4444', // lundi - red
            '#f97316', // mardi - orange
            '#eab308', // mercredi - yellow
            '#22c55e', // jeudi - green
            '#06b6d4', // vendredi - cyan
            '#8b5cf6', // samedi - purple
            '#ec4899'  // dimanche - pink
        ];

        // Colors for top lieux (orange scale)
        const lieuxColors = [
            '#ea580c', '#f97316', '#fb923c', '#fdba74', '#fed7aa',
            '#c2410c', '#9a3412', '#7c2d12', '#d97706', '#b45309'
        ];

        // Colors for top artistes (cyan scale)
        const artistesColors = [
            '#0891b2', '#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc',
            '#0e7490', '#155e75', '#164e63', '#14b8a6', '#0d9488'
        ];

        // Change main chart axis
        function changeAxis(axis) {
            if (!hasExtended) return;

            let newData;
            switch(axis) {
                case 'numero_bidul': newData = extended.by_bidul; break;
                case 'mois': newData = extended.by_mois; break;
                case 'semaine': newData = extended.by_semaine; break;
                case 'jour': newData = extended.by_jour; break;
                default: newData = extended.by_bidul;
            }

            // Update labels
            chart.data.labels = newData.labels;

            // Update datasets
            chart.data.datasets[0].data = newData.local;
            chart.data.datasets[1].data = newData.regional;
            chart.data.datasets[2].data = newData.content;

            // Update colors for the new axis
            const len = newData.labels.length;
            chart.data.datasets[0].backgroundColor = Array(len).fill('#06b6d4');
            chart.data.datasets[1].backgroundColor = Array(len).fill('#a78bfa');
            chart.data.datasets[2].backgroundColor = Array(len).fill('#f59e0b');

            // Update x-axis tick callback
            if (axis === 'numero_bidul') {
                chart.options.scales.x.ticks.callback = (val, idx) => idx % 10 === 0 ? newData.labels[idx] : '';
            } else if (axis === 'semaine') {
                chart.options.scales.x.ticks.callback = (val, idx) => idx % 4 === 0 ? newData.labels[idx] : '';
            } else {
                chart.options.scales.x.ticks.callback = (val, idx) => newData.labels[idx];
            }

            chart.update();
        }

        // Toggle KPI section
        let kpiVisible = false;
        let kpiChartsInitialized = false;
        let dayOfWeekChart = null;
        let topLieuxChart = null;
        let topArtistesChart = null;

        function toggleKPI() {
            kpiVisible = !kpiVisible;
            const btn = document.getElementById('kpiBtn');
            btn.classList.toggle('active', kpiVisible);

            document.getElementById('kpiSection').style.display = kpiVisible ? 'block' : 'none';

            // Initialize charts on first show
            if (kpiVisible && !kpiChartsInitialized && hasExtended) {
                initKPICharts();
                kpiChartsInitialized = true;
            }
        }

        // Toggle collapsible section
        function toggleSection(sectionName) {
            const content = document.getElementById(sectionName + 'Content');
            const header = content.previousElementSibling;
            content.classList.toggle('hidden');
            header.classList.toggle('collapsed');
        }

        // Initialize KPI charts
        // Current granularity for day of week chart
        let currentDowGranularity = 'monthly';

        // Change day of week chart granularity
        function changeDowGranularity(granularity) {
            currentDowGranularity = granularity;
            if (!dayOfWeekChart || !hasExtended) return;

            const dowData = granularity === 'weekly' ? extended.events_by_day_weekly : extended.events_by_day_monthly;
            if (!dowData || !dowData.labels) return;

            const jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'];

            // Update labels
            dayOfWeekChart.data.labels = dowData.labels;

            // Update each dataset
            jours.forEach((jour, i) => {
                dayOfWeekChart.data.datasets[i].data = dowData.datasets[jour] || [];
            });

            // Update title
            const titleText = granularity === 'weekly'
                ? 'Nombre d\\'evenements par jour de la semaine (evolution hebdomadaire)'
                : 'Nombre d\\'evenements par jour de la semaine (evolution mensuelle)';
            dayOfWeekChart.options.plugins.title.text = titleText;

            // Update x-axis tick callback based on data density
            const tickInterval = granularity === 'weekly' ? 12 : 6;
            dayOfWeekChart.options.scales.x.ticks.callback = (val, idx) => idx % tickInterval === 0 ? dowData.labels[idx] : '';

            dayOfWeekChart.update();
        }

        function initKPICharts() {
            // 1. Events by day of week over time
            if (extended.events_by_day_monthly && extended.events_by_day_monthly.labels.length > 0) {
                const dowData = extended.events_by_day_monthly;
                const jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'];
                const dowDatasets = jours.map((jour, i) => ({
                    label: jour.charAt(0).toUpperCase() + jour.slice(1),
                    data: dowData.datasets[jour] || [],
                    borderColor: dayColors[i],
                    backgroundColor: dayColors[i] + '20',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false
                }));

                dayOfWeekChart = new Chart(document.getElementById('dayOfWeekChart').getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: dowData.labels,
                        datasets: dowDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top',
                                labels: { color: '#9ca3af', boxWidth: 12, padding: 10 }
                            },
                            title: {
                                display: true,
                                text: 'Nombre d\\'evenements par jour de la semaine (evolution mensuelle)',
                                color: '#9ca3af'
                            }
                        },
                        scales: {
                            x: {
                                ticks: {
                                    color: '#9ca3af',
                                    maxRotation: 45,
                                    callback: (val, idx) => idx % 6 === 0 ? dowData.labels[idx] : ''
                                },
                                grid: { display: false }
                            },
                            y: {
                                ticks: { color: '#9ca3af' },
                                grid: { color: '#374151' }
                            }
                        }
                    }
                });
            }

            // 2. Top 10 lieux evolution
            if (extended.top_lieux_monthly && extended.top_lieux_monthly.labels.length > 0) {
                const lieuxData = extended.top_lieux_monthly;
                const lieuxDatasets = lieuxData.top_lieux.map((lieu, i) => ({
                    label: lieu.length > 25 ? lieu.substring(0, 22) + '...' : lieu,
                    data: lieuxData.datasets[lieu] || [],
                    borderColor: lieuxColors[i % lieuxColors.length],
                    backgroundColor: lieuxColors[i % lieuxColors.length] + '20',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false
                }));

                topLieuxChart = new Chart(document.getElementById('topLieuxChart').getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: lieuxData.labels,
                        datasets: lieuxDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'right',
                                labels: { color: '#9ca3af', boxWidth: 12, padding: 5, font: { size: 10 } }
                            },
                            title: {
                                display: true,
                                text: 'Top 10 lieux - evolution mensuelle',
                                color: '#9ca3af'
                            }
                        },
                        scales: {
                            x: {
                                ticks: {
                                    color: '#9ca3af',
                                    maxRotation: 45,
                                    callback: (val, idx) => idx % 6 === 0 ? lieuxData.labels[idx] : ''
                                },
                                grid: { display: false }
                            },
                            y: {
                                ticks: { color: '#9ca3af' },
                                grid: { color: '#374151' }
                            }
                        }
                    }
                });
            }

            // 3. Top 10 artistes evolution
            if (extended.top_artistes_monthly && extended.top_artistes_monthly.labels.length > 0) {
                const artistesData = extended.top_artistes_monthly;
                const artistesDatasets = artistesData.top_artistes.map((artiste, i) => ({
                    label: artiste.length > 25 ? artiste.substring(0, 22) + '...' : artiste,
                    data: artistesData.datasets[artiste] || [],
                    borderColor: artistesColors[i % artistesColors.length],
                    backgroundColor: artistesColors[i % artistesColors.length] + '20',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false
                }));

                topArtistesChart = new Chart(document.getElementById('topArtistesChart').getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: artistesData.labels,
                        datasets: artistesDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'right',
                                labels: { color: '#9ca3af', boxWidth: 12, padding: 5, font: { size: 10 } }
                            },
                            title: {
                                display: true,
                                text: 'Top 10 artistes - evolution mensuelle',
                                color: '#9ca3af'
                            }
                        },
                        scales: {
                            x: {
                                ticks: {
                                    color: '#9ca3af',
                                    maxRotation: 45,
                                    callback: (val, idx) => idx % 6 === 0 ? artistesData.labels[idx] : ''
                                },
                                grid: { display: false }
                            },
                            y: {
                                ticks: { color: '#9ca3af' },
                                grid: { color: '#374151' }
                            }
                        }
                    }
                });
            }
        }

        // Change top lieux chart granularity
        let currentLieuxGranularity = 'monthly';
        function changeLieuxGranularity(granularity) {
            currentLieuxGranularity = granularity;
            if (!topLieuxChart || !hasExtended) return;

            const lieuxData = granularity === 'yearly' ? extended.top_lieux_yearly : extended.top_lieux_monthly;
            if (!lieuxData || !lieuxData.labels) return;

            // Update labels
            topLieuxChart.data.labels = lieuxData.labels;

            // Update each dataset
            lieuxData.top_lieux.forEach((lieu, i) => {
                topLieuxChart.data.datasets[i].data = lieuxData.datasets[lieu] || [];
            });

            // Update title
            const titleText = granularity === 'yearly'
                ? 'Top 10 lieux - evolution annuelle'
                : 'Top 10 lieux - evolution mensuelle';
            topLieuxChart.options.plugins.title.text = titleText;

            // Update x-axis tick callback based on data density
            const tickInterval = granularity === 'yearly' ? 1 : 6;
            topLieuxChart.options.scales.x.ticks.callback = (val, idx) => idx % tickInterval === 0 ? lieuxData.labels[idx] : '';

            topLieuxChart.update();
        }

        // Change top artistes chart granularity
        let currentArtistesGranularity = 'monthly';
        function changeArtistesGranularity(granularity) {
            currentArtistesGranularity = granularity;
            if (!topArtistesChart || !hasExtended) return;

            const artistesData = granularity === 'yearly' ? extended.top_artistes_yearly : extended.top_artistes_monthly;
            if (!artistesData || !artistesData.labels) return;

            // Update labels
            topArtistesChart.data.labels = artistesData.labels;

            // Update each dataset
            artistesData.top_artistes.forEach((artiste, i) => {
                topArtistesChart.data.datasets[i].data = artistesData.datasets[artiste] || [];
            });

            // Update title
            const titleText = granularity === 'yearly'
                ? 'Top 10 artistes - evolution annuelle'
                : 'Top 10 artistes - evolution mensuelle';
            topArtistesChart.options.plugins.title.text = titleText;

            // Update x-axis tick callback based on data density
            const tickInterval = granularity === 'yearly' ? 1 : 6;
            topArtistesChart.options.scales.x.ticks.callback = (val, idx) => idx % tickInterval === 0 ? artistesData.labels[idx] : '';

            topArtistesChart.update();
        }
    </script>
</body>
</html>'''

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


def get_geo_data(db_path: str) -> Dict[str, Any]:
    """
    Récupère les données géographiques pour la carte interactive.

    Returns:
        Dict avec:
        - lieux: liste de {nom, ville, lat, lng, count}
        - lieux_by_year: dict {année: liste de lieux}
        - years: liste des années disponibles
        - bounds: {min_lat, max_lat, min_lng, max_lng}
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    result = {'lieux': [], 'lieux_by_year': {}, 'lieux_by_month': {}, 'lieux_by_week': {}, 'lieux_by_day': {}, 'years': [], 'months': [], 'weeks': [], 'days': [], 'bounds': None}

    # Données agrégées par lieu (tous temps)
    cur.execute("""
        SELECT
            lr.id,
            lr.nom,
            lr.ville,
            lr.latitude,
            lr.longitude,
            COUNT(e.id) as event_count
        FROM lieu_ref lr
        INNER JOIN evenement e ON e.lieu_ref_id = lr.id
        WHERE lr.latitude IS NOT NULL AND lr.longitude IS NOT NULL
        GROUP BY lr.id
        ORDER BY event_count DESC
    """)

    lieux_data = cur.fetchall()
    lieu_ids = [row[0] for row in lieux_data]

    # Récupérer TOUS les événements pour chaque lieu (pour filtrage dynamique)
    events_by_lieu = {}
    if lieu_ids:
        placeholders = ','.join('?' * len(lieu_ids))
        cur.execute(f"""
            SELECT
                e.lieu_ref_id,
                e.date_evenement,
                e.heure,
                e.tarif_raw,
                e.nom as event_nom,
                GROUP_CONCAT(ce.artiste, ' + ') as artistes,
                GROUP_CONCAT(ce.nom_spectacle, ' / ') as spectacles
            FROM evenement e
            LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
            WHERE e.lieu_ref_id IN ({placeholders})
            GROUP BY e.id
            ORDER BY e.lieu_ref_id, e.date_evenement DESC
        """, lieu_ids)

        for row in cur.fetchall():
            lieu_id = row[0]
            if lieu_id not in events_by_lieu:
                events_by_lieu[lieu_id] = []
            # Stocker tous les événements avec la date pour filtrage côté JS
            events_by_lieu[lieu_id].append({
                'date': row[1],
                'heure': row[2],
                'tarif': row[3],
                'nom': row[4],
                'artistes': row[5],
                'spectacles': row[6]
            })

    lats, lngs = [], []
    for row in lieux_data:
        lieu_id = row[0]
        result['lieux'].append({
            'nom': row[1],
            'ville': row[2] or 'Le Mans',
            'lat': row[3],
            'lng': row[4],
            'count': row[5],
            'events': events_by_lieu.get(lieu_id, [])
        })
        lats.append(row[3])
        lngs.append(row[4])

    # Calculer les bounds
    if lats and lngs:
        result['bounds'] = {
            'min_lat': min(lats),
            'max_lat': max(lats),
            'min_lng': min(lngs),
            'max_lng': max(lngs)
        }

    # Données par année (pour filtre temporel)
    cur.execute("""
        SELECT DISTINCT strftime('%Y', date_evenement) as year
        FROM evenement
        WHERE date_evenement IS NOT NULL
        ORDER BY year
    """)
    result['years'] = [row[0] for row in cur.fetchall() if row[0]]

    # Données agrégées par lieu et par année
    cur.execute("""
        SELECT
            strftime('%Y', e.date_evenement) as year,
            lr.nom,
            lr.ville,
            lr.latitude,
            lr.longitude,
            COUNT(e.id) as event_count
        FROM lieu_ref lr
        INNER JOIN evenement e ON e.lieu_ref_id = lr.id
        WHERE lr.latitude IS NOT NULL
          AND lr.longitude IS NOT NULL
          AND e.date_evenement IS NOT NULL
        GROUP BY year, lr.id
        ORDER BY year, event_count DESC
    """)

    for row in cur.fetchall():
        year = row[0]
        if year not in result['lieux_by_year']:
            result['lieux_by_year'][year] = []
        result['lieux_by_year'][year].append({
            'nom': row[1],
            'ville': row[2] or 'Le Mans',
            'lat': row[3],
            'lng': row[4],
            'count': row[5]
        })

    # Données agrégées par lieu et par mois (YYYY-MM)
    cur.execute("""
        SELECT
            strftime('%Y-%m', e.date_evenement) as month,
            lr.nom,
            lr.ville,
            lr.latitude,
            lr.longitude,
            COUNT(e.id) as event_count
        FROM lieu_ref lr
        INNER JOIN evenement e ON e.lieu_ref_id = lr.id
        WHERE lr.latitude IS NOT NULL
          AND lr.longitude IS NOT NULL
          AND e.date_evenement IS NOT NULL
        GROUP BY month, lr.id
        ORDER BY month, event_count DESC
    """)

    for row in cur.fetchall():
        month = row[0]
        if month not in result['lieux_by_month']:
            result['lieux_by_month'][month] = []
        result['lieux_by_month'][month].append({
            'nom': row[1],
            'ville': row[2] or 'Le Mans',
            'lat': row[3],
            'lng': row[4],
            'count': row[5]
        })

    # Liste des mois disponibles (triée)
    result['months'] = sorted(result['lieux_by_month'].keys())

    # Données agrégées par lieu et par semaine (YYYY-WNN)
    cur.execute("""
        SELECT
            strftime('%Y-W%W', e.date_evenement) as week,
            lr.nom,
            lr.ville,
            lr.latitude,
            lr.longitude,
            COUNT(e.id) as event_count
        FROM lieu_ref lr
        INNER JOIN evenement e ON e.lieu_ref_id = lr.id
        WHERE lr.latitude IS NOT NULL
          AND lr.longitude IS NOT NULL
          AND e.date_evenement IS NOT NULL
        GROUP BY week, lr.id
        ORDER BY week, event_count DESC
    """)

    for row in cur.fetchall():
        week = row[0]
        if week and week not in result['lieux_by_week']:
            result['lieux_by_week'][week] = []
        if week:
            result['lieux_by_week'][week].append({
                'nom': row[1],
                'ville': row[2] or 'Le Mans',
                'lat': row[3],
                'lng': row[4],
                'count': row[5]
            })

    # Liste des semaines disponibles (triée)
    result['weeks'] = sorted(result['lieux_by_week'].keys())

    # Données agrégées par lieu et par jour (YYYY-MM-DD)
    # Limité aux 5 dernières années pour éviter trop de données
    cur.execute("""
        SELECT
            date(e.date_evenement) as day,
            lr.nom,
            lr.ville,
            lr.latitude,
            lr.longitude,
            COUNT(e.id) as event_count
        FROM lieu_ref lr
        INNER JOIN evenement e ON e.lieu_ref_id = lr.id
        WHERE lr.latitude IS NOT NULL
          AND lr.longitude IS NOT NULL
          AND e.date_evenement IS NOT NULL
          AND e.date_evenement >= date('now', '-5 years')
        GROUP BY day, lr.id
        ORDER BY day, event_count DESC
    """)

    for row in cur.fetchall():
        day = row[0]
        if day and day not in result['lieux_by_day']:
            result['lieux_by_day'][day] = []
        if day:
            result['lieux_by_day'][day].append({
                'nom': row[1],
                'ville': row[2] or 'Le Mans',
                'lat': row[3],
                'lng': row[4],
                'count': row[5]
            })

    # Liste des jours disponibles (triée)
    result['days'] = sorted(result['lieux_by_day'].keys())

    conn.close()
    return result


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
        'geo_data': get_geo_data(db_path),
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
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
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
        .btn.green.active { background: #059669; }

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

        /* Map section */
        .map-section {
            background: #1f2937;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .map-container {
            height: 700px;
            border-radius: 8px;
            overflow: hidden;
        }
        /* Fullscreen map mode */
        .map-section.fullscreen {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 9999;
            margin: 0;
            border-radius: 0;
            padding: 10px;
            box-sizing: border-box;
        }
        .map-section.fullscreen .map-container {
            height: calc(100vh - 70px);
            border-radius: 0;
        }
        .map-section.fullscreen .map-controls {
            background: #1f2937;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .btn-fullscreen {
            background: #374151;
            border: 1px solid #4b5563;
            color: #f3f4f6;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
        }
        .btn-fullscreen:hover {
            background: #4b5563;
        }
        .map-tooltip {
            background: #1f2937 !important;
            border: 1px solid #374151 !important;
            color: #f3f4f6 !important;
            font-family: system-ui;
            font-size: 13px;
            font-weight: 500;
            padding: 6px 10px !important;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            z-index: 1000 !important;
        }
        .leaflet-tooltip {
            z-index: 1000 !important;
        }
        .map-tooltip::before {
            border-top-color: #374151 !important;
        }
        .leaflet-tooltip-left.map-tooltip::before {
            border-left-color: #374151 !important;
        }
        .leaflet-tooltip-right.map-tooltip::before {
            border-right-color: #374151 !important;
        }
        .leaflet-popup-content-wrapper {
            background: #1f2937;
            color: #f3f4f6;
            border-radius: 8px;
        }
        .leaflet-popup-tip {
            background: #1f2937;
        }
        .leaflet-popup-close-button {
            color: #9ca3af !important;
        }
        .map-controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 10px;
        }
        .time-filter {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .time-filter label {
            color: #9ca3af;
            font-size: 0.85rem;
        }
        .time-filter select {
            background: #374151;
            border: 1px solid #4b5563;
            color: #f3f4f6;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
        }
        .map-stats {
            display: flex;
            gap: 15px;
            font-size: 0.85rem;
            color: #9ca3af;
        }
        .map-stats span {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .map-stats .count {
            color: #22c55e;
            font-weight: bold;
        }
        .leaflet-popup-content-wrapper {
            background: #1f2937;
            color: #f3f4f6;
            border-radius: 8px;
        }
        .leaflet-popup-tip {
            background: #1f2937;
        }
        .leaflet-popup-content {
            margin: 10px 12px;
        }
        .leaflet-popup-content b {
            color: #22c55e;
        }
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
        <button class="btn green active" id="cumulativeBtn" onclick="toggleCumulative()">Total cumule</button>
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

    <!-- Map section -->
    <div class="section-header" onclick="toggleSection('map')">
        <h3 style="color:#22c55e">Carte des evenements</h3>
        <span class="toggle-icon">&#9660;</span>
    </div>
    <div class="section-content" id="mapContent">
        <div class="map-section">
            <div class="map-controls">
                <div class="time-filter">
                    <label>Filtre:</label>
                    <select id="mapFilterType" onchange="changeMapFilterType(this.value)">
                        <option value="all">Tout</option>
                        <option value="year">Par année</option>
                        <option value="month">Par mois</option>
                        <option value="week">Par semaine</option>
                        <option value="day">Par jour</option>
                    </select>
                    <div id="yearSliderContainer" style="display:none;flex:1;align-items:center;gap:10px">
                        <input type="range" id="mapYearSlider" min="0" max="100" value="0"
                               style="flex:1;accent-color:#22c55e" oninput="filterMapByYearSlider(this.value)">
                        <span id="mapYearLabel" style="min-width:50px;color:#f3f4f6;font-weight:500">-</span>
                        <button class="btn" id="btnPlayYear" onclick="toggleYearAnimation()" style="padding:4px 10px">▶</button>
                    </div>
                    <div id="monthSliderContainer" style="display:none;flex:1;align-items:center;gap:10px">
                        <input type="range" id="mapMonthSlider" min="0" max="100" value="0"
                               style="flex:1;accent-color:#8b5cf6" oninput="filterMapByMonth(this.value)">
                        <span id="mapMonthLabel" style="min-width:80px;color:#f3f4f6;font-weight:500">-</span>
                        <button class="btn" id="btnPlayMonth" onclick="toggleMonthAnimation()" style="padding:4px 10px">▶</button>
                    </div>
                    <div id="weekSliderContainer" style="display:none;flex:1;align-items:center;gap:10px">
                        <input type="range" id="mapWeekSlider" min="0" max="100" value="0"
                               style="flex:1;accent-color:#14b8a6" oninput="filterMapByWeek(this.value)">
                        <span id="mapWeekLabel" style="min-width:100px;color:#f3f4f6;font-weight:500">-</span>
                        <button class="btn" id="btnPlayWeek" onclick="toggleWeekAnimation()" style="padding:4px 10px">▶</button>
                    </div>
                    <div id="daySliderContainer" style="display:none;flex:1;align-items:center;gap:10px">
                        <input type="range" id="mapDaySlider" min="0" max="100" value="0"
                               style="flex:1;accent-color:#f59e0b" oninput="filterMapByDay(this.value)">
                        <span id="mapDayLabel" style="min-width:100px;color:#f3f4f6;font-weight:500">-</span>
                        <button class="btn" id="btnPlayDay" onclick="toggleDayAnimation()" style="padding:4px 10px">▶</button>
                    </div>
                </div>
                <div class="controls" style="margin:0">
                    <button class="btn active" id="btnMarkers" onclick="setMapView('markers')">Marqueurs</button>
                    <button class="btn" id="btnHeat" onclick="setMapView('heat')">Heatmap</button>
                    <button class="btn" id="btnBoth" onclick="setMapView('both')">Les deux</button>
                </div>
                <div class="map-stats">
                    <span>Lieux: <span class="count" id="mapLieuxCount">-</span></span>
                    <span>Evenements: <span class="count" id="mapEventsCount">-</span></span>
                </div>
                <button class="btn-fullscreen" id="btnFullscreen" onclick="toggleMapFullscreen()" title="Plein écran">⛶</button>
            </div>
            <div id="map" class="map-container"></div>
        </div>
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

        // Calcul du total cumulé (courbe d'évolution)
        // Fonction pour calculer le cumulatif à partir d'un array
        function computeCumulative(arr) {
            let total = 0;
            return arr.map(v => {
                total += v;
                return total;
            });
        }

        // Cumulatif initial basé sur les données par bidul
        let cumulativeData = computeCumulative(data.map(d => d.events));

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

        // Add cumulative total dataset
        datasets.push({
            label: 'Total cumule',
            data: cumulativeData,
            type: 'line',
            borderColor: '#10b981',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
            yAxisID: 'y2',
            hidden: false
        });

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
                            title: (items) => items[0].label,
                            label: (item) => {
                                if (item.dataset.label === 'Score Qualite') return `Qualite: ${item.raw}%`;
                                if (item.dataset.label === 'Total cumule') return `Total cumule: ${item.raw.toLocaleString()}`;
                                return `${item.dataset.label}: ${item.raw}`;
                            },
                            afterBody: (items) => {
                                const idx = items[0].dataIndex;
                                // Get local and regional values from their datasets
                                const localVal = chart.data.datasets[0].data[idx] || 0;
                                const regionalVal = chart.data.datasets[1].data[idx] || 0;
                                const contentVal = chart.data.datasets[2].data[idx] || 0;
                                const totalEvents = localVal + regionalVal;
                                if (totalEvents === 0) return '';
                                const lines = [];
                                lines.push(`Total: ${totalEvents} (${localVal} local + ${regionalVal} regional)`);
                                if (contentVal > 0) lines.push(`Ratio: ${(contentVal / totalEvents).toFixed(2)}`);
                                lines.push(`Cumul: ${cumulativeData[idx].toLocaleString()} evenements`);
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
                    },
                    y2: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        min: 0,
                        grid: { drawOnChartArea: false },
                        ticks: {
                            color: '#10b981',
                            callback: v => v >= 1000 ? (v/1000).toFixed(0) + 'k' : v
                        },
                        title: {
                            display: true,
                            text: 'Total cumule',
                            color: '#10b981'
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

        // Toggle cumulative view
        let cumulativeVisible = true;
        function toggleCumulative() {
            cumulativeVisible = !cumulativeVisible;
            const btn = document.getElementById('cumulativeBtn');
            btn.classList.toggle('active', cumulativeVisible);

            // Find cumulative dataset (last one added)
            const cumulativeIndex = chart.data.datasets.findIndex(ds => ds.label === 'Total cumule');
            if (cumulativeIndex >= 0) {
                chart.data.datasets[cumulativeIndex].hidden = !cumulativeVisible;
                chart.options.scales.y2.display = cumulativeVisible;
                chart.update();
            }
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

            // Recalculate cumulative data for the new axis
            // Sum local + regional to get total events for cumulative
            const eventsForCumul = newData.local.map((v, i) => v + (newData.regional[i] || 0));
            cumulativeData = computeCumulative(eventsForCumul);

            // Update cumulative dataset
            const cumulativeIndex = chart.data.datasets.findIndex(ds => ds.label === 'Total cumule');
            if (cumulativeIndex >= 0) {
                chart.data.datasets[cumulativeIndex].data = cumulativeData;
            }

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

        // =====================================================
        // MAP FUNCTIONALITY
        // =====================================================

        const geoData = hasExtended && extended.geo_data ? extended.geo_data : null;
        let map = null;
        let markersLayer = null;
        let tooltipLayer = null;  // Invisible markers with tooltips (always visible)
        let heatLayer = null;
        let currentMapView = 'markers';
        let currentMapData = null;
        let allLieuxWithEvents = null;  // Store full lieu data with events
        let currentFilterType = null;   // 'year', 'month', 'week', 'day' or null
        let currentFilterValue = null;  // The selected filter value

        function initMap() {
            if (!geoData || !geoData.lieux || geoData.lieux.length === 0) {
                document.getElementById('mapContent').innerHTML = '<div class="map-section"><p style="text-align:center;color:#9ca3af;padding:40px">Aucune donnee geographique disponible</p></div>';
                return;
            }

            // Center on Le Mans by default
            const center = [47.9960, 0.1906];
            map = L.map('map').setView(center, 11);

            // Dark map tiles (CartoDB Dark Matter)
            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 19
            }).addTo(map);

            // Markers layer (visible markers)
            markersLayer = L.layerGroup().addTo(map);
            // Tooltip layer (invisible markers for tooltips, always visible)
            tooltipLayer = L.layerGroup().addTo(map);

            // Store full lieu data with events for popup filtering
            allLieuxWithEvents = geoData.lieux;

            // Initial map update
            currentMapData = geoData.lieux;
            updateMap(geoData.lieux);

            // Fit to bounds if available
            if (geoData.bounds) {
                map.fitBounds([
                    [geoData.bounds.min_lat, geoData.bounds.min_lng],
                    [geoData.bounds.max_lat, geoData.bounds.max_lng]
                ], { padding: [20, 20] });
            }
        }

        function updateMap(data) {
            if (!map) return;

            currentMapData = data;

            // Clear existing layers
            markersLayer.clearLayers();
            tooltipLayer.clearLayers();
            if (heatLayer) {
                map.removeLayer(heatLayer);
                heatLayer = null;
            }

            if (!data || data.length === 0) {
                document.getElementById('mapLieuxCount').textContent = '0';
                document.getElementById('mapEventsCount').textContent = '0';
                return;
            }

            // Prepare data
            const heatPoints = [];
            const maxCount = Math.max(...data.map(l => l.count));
            let totalEvents = 0;

            data.forEach(lieu => {
                if (!lieu.lat || !lieu.lng) return;

                totalEvents += lieu.count;

                // Find full lieu data with events (for popup)
                let lieuWithEvents = lieu;
                if (allLieuxWithEvents) {
                    const fullLieu = allLieuxWithEvents.find(l => l.nom === lieu.nom && l.ville === lieu.ville);
                    if (fullLieu) {
                        lieuWithEvents = {...lieu, events: fullLieu.events};
                    }
                }

                // Circle marker with popup and tooltip (visible)
                const radius = Math.min(5 + (lieu.count / maxCount) * 15, 20);
                const marker = L.circleMarker([lieu.lat, lieu.lng], {
                    radius: radius,
                    fillColor: getHeatColor(lieu.count, maxCount),
                    fillOpacity: 0.8,
                    stroke: true,
                    color: '#fff',
                    weight: 1
                });

                // Build popup content with event details (filtered by current time filter)
                const popupContent = buildLieuPopup(lieuWithEvents, currentFilterType, currentFilterValue);

                // Popup with details on click
                marker.bindPopup(popupContent, {maxWidth: 350, maxHeight: 400});
                // Tooltip with name on hover
                marker.bindTooltip(lieu.nom, {
                    permanent: false,
                    direction: 'top',
                    className: 'map-tooltip'
                });
                markersLayer.addLayer(marker);

                // Invisible marker for tooltip (always visible, even in heatmap mode)
                const tooltipMarker = L.circleMarker([lieu.lat, lieu.lng], {
                    radius: radius,
                    fillOpacity: 0,
                    stroke: false
                });
                tooltipMarker.bindPopup(popupContent, {maxWidth: 350, maxHeight: 400});
                tooltipMarker.bindTooltip(lieu.nom, {
                    permanent: false,
                    direction: 'top',
                    className: 'map-tooltip'
                });
                tooltipLayer.addLayer(tooltipMarker);

                // Heatmap point (with logarithmic intensity for better variation display)
                // Log scale: log(count+1) / log(maxCount+1) spreads values more evenly
                const logIntensity = Math.log(lieu.count + 1) / Math.log(maxCount + 1);
                heatPoints.push([lieu.lat, lieu.lng, logIntensity]);
            });

            // Create heatmap layer
            heatLayer = L.heatLayer(heatPoints, {
                radius: 25,
                blur: 15,
                maxZoom: 15,
                max: 1.0,
                gradient: {
                    0.0: '#1e3a5f',
                    0.2: '#22c55e',
                    0.4: '#84cc16',
                    0.6: '#f59e0b',
                    0.8: '#ef4444',
                    1.0: '#dc2626'
                }
            });

            // Update stats
            document.getElementById('mapLieuxCount').textContent = data.length;
            document.getElementById('mapEventsCount').textContent = totalEvents.toLocaleString();

            // Apply current view
            applyMapView();
        }

        function buildLieuPopup(lieu, filterType, filterValue) {
            // Filtrer les événements selon le filtre actif
            let filteredEvents = lieu.events || [];
            let filterLabel = 'Tous les événements';

            if (filterType && filterValue && filteredEvents.length > 0) {
                filteredEvents = filteredEvents.filter(function(evt) {
                    if (!evt.date) return false;
                    if (filterType === 'year') {
                        return evt.date.substring(0, 4) === filterValue;
                    } else if (filterType === 'month') {
                        return evt.date.substring(0, 7) === filterValue;
                    } else if (filterType === 'week') {
                        // filterValue format: YYYY-WNN
                        const evtDate = new Date(evt.date);
                        const evtWeek = getWeekString(evtDate);
                        return evtWeek === filterValue;
                    } else if (filterType === 'day') {
                        return evt.date === filterValue;
                    }
                    return true;
                });

                // Label du filtre
                if (filterType === 'year') filterLabel = 'Année ' + filterValue;
                else if (filterType === 'month') filterLabel = filterValue;
                else if (filterType === 'week') filterLabel = 'Semaine ' + filterValue;
                else if (filterType === 'day') filterLabel = filterValue;
            }

            // Limiter à 15 événements pour l'affichage
            const displayEvents = filteredEvents.slice(0, 15);
            const totalFiltered = filteredEvents.length;

            let html = '<div style="font-family:system-ui;min-width:200px;max-width:320px">';
            html += '<b style="font-size:14px;color:#f8fafc">' + escapeHtml(lieu.nom) + '</b><br>';
            html += '<span style="color:#9ca3af">' + escapeHtml(lieu.ville) + '</span><br>';
            html += '<span style="color:#f59e0b;font-weight:600">' + totalFiltered + ' événement(s)</span>';
            if (filterType && filterValue) {
                html += '<span style="color:#6b7280;font-size:11px"> (' + filterLabel + ')</span>';
            }

            if (displayEvents.length > 0) {
                html += '<div style="margin-top:8px;border-top:1px solid #374151;padding-top:8px;max-height:280px;overflow-y:auto">';

                displayEvents.forEach(function(evt) {
                    html += '<div style="margin-bottom:8px;padding:6px;background:#1f2937;border-radius:4px;font-size:12px">';

                    // Date et heure
                    if (evt.date) {
                        html += '<div style="color:#60a5fa;font-weight:500">';
                        html += escapeHtml(evt.date);
                        if (evt.heure) html += ' - ' + escapeHtml(evt.heure);
                        html += '</div>';
                    }

                    // Nom de l'événement
                    if (evt.nom) {
                        html += '<div style="color:#fbbf24;font-style:italic">' + escapeHtml(evt.nom) + '</div>';
                    }

                    // Artistes
                    if (evt.artistes) {
                        html += '<div style="color:#f8fafc">' + escapeHtml(evt.artistes) + '</div>';
                    }

                    // Spectacles
                    if (evt.spectacles) {
                        html += '<div style="color:#a78bfa">« ' + escapeHtml(evt.spectacles) + ' »</div>';
                    }

                    // Tarif
                    if (evt.tarif) {
                        html += '<div style="color:#34d399;font-size:11px">' + escapeHtml(evt.tarif) + '</div>';
                    }

                    html += '</div>';
                });

                if (totalFiltered > 15) {
                    html += '<div style="color:#6b7280;font-size:11px;text-align:center">... et ' + (totalFiltered - 15) + ' autres</div>';
                }

                html += '</div>';
            } else if (filterType && filterValue) {
                html += '<div style="margin-top:8px;color:#6b7280;font-size:12px;font-style:italic">Aucun événement pour cette période</div>';
            }

            html += '</div>';
            return html;
        }

        function getWeekString(date) {
            // Retourne YYYY-WNN format
            const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
            const dayNum = d.getUTCDay() || 7;
            d.setUTCDate(d.getUTCDate() + 4 - dayNum);
            const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
            const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
            return d.getUTCFullYear() + '-W' + String(weekNo).padStart(2, '0');
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function getHeatColor(count, max) {
            const ratio = count / max;
            if (ratio > 0.7) return '#ef4444';
            if (ratio > 0.4) return '#f59e0b';
            if (ratio > 0.2) return '#22c55e';
            return '#06b6d4';
        }

        function setMapView(view) {
            currentMapView = view;

            // Update button states
            document.getElementById('btnMarkers').classList.toggle('active', view === 'markers');
            document.getElementById('btnHeat').classList.toggle('active', view === 'heat');
            document.getElementById('btnBoth').classList.toggle('active', view === 'both');

            applyMapView();
        }

        function applyMapView() {
            if (!map || !markersLayer || !heatLayer) return;

            // tooltipLayer stays always visible for hover tooltips
            if (!map.hasLayer(tooltipLayer)) tooltipLayer.addTo(map);

            if (currentMapView === 'markers') {
                if (!map.hasLayer(markersLayer)) markersLayer.addTo(map);
                if (map.hasLayer(heatLayer)) map.removeLayer(heatLayer);
            } else if (currentMapView === 'heat') {
                if (map.hasLayer(markersLayer)) map.removeLayer(markersLayer);
                if (!map.hasLayer(heatLayer)) heatLayer.addTo(map);
            } else { // both
                if (!map.hasLayer(markersLayer)) markersLayer.addTo(map);
                if (!map.hasLayer(heatLayer)) heatLayer.addTo(map);
            }
        }

        // Month slider variables
        let monthAnimationInterval = null;
        let isMonthAnimating = false;

        function changeMapFilterType(type) {
            const yearContainer = document.getElementById('yearSliderContainer');
            const monthContainer = document.getElementById('monthSliderContainer');
            const weekContainer = document.getElementById('weekSliderContainer');
            const dayContainer = document.getElementById('daySliderContainer');

            // Stop any running animations
            if (isYearAnimating) toggleYearAnimation();
            if (isMonthAnimating) toggleMonthAnimation();
            if (isWeekAnimating) toggleWeekAnimation();
            if (isDayAnimating) toggleDayAnimation();

            // Hide all containers
            yearContainer.style.display = 'none';
            monthContainer.style.display = 'none';
            weekContainer.style.display = 'none';
            dayContainer.style.display = 'none';

            if (type === 'all') {
                currentFilterType = null;
                currentFilterValue = null;
                updateMap(geoData.lieux);
            } else if (type === 'year') {
                yearContainer.style.display = 'flex';
                initYearSlider();
            } else if (type === 'month') {
                monthContainer.style.display = 'flex';
                initMonthSlider();
            } else if (type === 'week') {
                weekContainer.style.display = 'flex';
                initWeekSlider();
            } else if (type === 'day') {
                dayContainer.style.display = 'flex';
                initDaySlider();
            }
        }

        // Year slider functions
        let yearAnimationInterval = null;
        let isYearAnimating = false;

        function initYearSlider() {
            if (!geoData || !geoData.years || geoData.years.length === 0) return;

            const slider = document.getElementById('mapYearSlider');
            slider.min = 0;
            slider.max = geoData.years.length - 1;
            slider.value = geoData.years.length - 1; // Start at most recent year

            filterMapByYearSlider(slider.value);
        }

        function filterMapByYearSlider(index) {
            if (!geoData || !geoData.years) return;

            const year = geoData.years[index];
            const label = document.getElementById('mapYearLabel');

            if (year) {
                label.textContent = year;
                currentFilterType = 'year';
                currentFilterValue = year;

                if (geoData.lieux_by_year && geoData.lieux_by_year[year]) {
                    updateMap(geoData.lieux_by_year[year]);
                } else {
                    updateMap([]);
                }
            }
        }

        function toggleYearAnimation() {
            const btn = document.getElementById('btnPlayYear');
            const slider = document.getElementById('mapYearSlider');

            if (isYearAnimating) {
                clearInterval(yearAnimationInterval);
                yearAnimationInterval = null;
                isYearAnimating = false;
                btn.textContent = '▶';
            } else {
                isYearAnimating = true;
                btn.textContent = '⏸';

                if (parseInt(slider.value) >= parseInt(slider.max)) {
                    slider.value = 0;
                }

                yearAnimationInterval = setInterval(() => {
                    const currentValue = parseInt(slider.value);
                    if (currentValue < parseInt(slider.max)) {
                        slider.value = currentValue + 1;
                        filterMapByYearSlider(slider.value);
                    } else {
                        toggleYearAnimation();
                    }
                }, 1000); // 1s between each year
            }
        }

        // Month slider functions
        function initMonthSlider() {
            if (!geoData || !geoData.months || geoData.months.length === 0) return;

            const slider = document.getElementById('mapMonthSlider');
            slider.min = 0;
            slider.max = geoData.months.length - 1;
            slider.value = geoData.months.length - 1; // Start at most recent month

            filterMapByMonth(slider.value);
        }

        function filterMapByMonth(index) {
            if (!geoData || !geoData.months) return;

            const month = geoData.months[index];
            const label = document.getElementById('mapMonthLabel');

            if (month) {
                // Format YYYY-MM to "Mois YYYY"
                const [year, m] = month.split('-');
                const monthNames = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
                                   'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc'];
                label.textContent = `${monthNames[parseInt(m) - 1]} ${year}`;
                currentFilterType = 'month';
                currentFilterValue = month;

                if (geoData.lieux_by_month && geoData.lieux_by_month[month]) {
                    updateMap(geoData.lieux_by_month[month]);
                } else {
                    updateMap([]);
                }
            }
        }

        function toggleMonthAnimation() {
            const btn = document.getElementById('btnPlayMonth');
            const slider = document.getElementById('mapMonthSlider');

            if (isMonthAnimating) {
                // Stop animation
                clearInterval(monthAnimationInterval);
                monthAnimationInterval = null;
                isMonthAnimating = false;
                btn.textContent = '▶';
            } else {
                // Start animation
                isMonthAnimating = true;
                btn.textContent = '⏸';

                // If at the end, restart from beginning
                if (parseInt(slider.value) >= parseInt(slider.max)) {
                    slider.value = 0;
                }

                monthAnimationInterval = setInterval(() => {
                    const currentValue = parseInt(slider.value);
                    if (currentValue < parseInt(slider.max)) {
                        slider.value = currentValue + 1;
                        filterMapByMonth(slider.value);
                    } else {
                        // End of animation
                        toggleMonthAnimation();
                    }
                }, 500); // 500ms between each month
            }
        }

        // Week slider functions
        let weekAnimationInterval = null;
        let isWeekAnimating = false;

        function initWeekSlider() {
            if (!geoData || !geoData.weeks || geoData.weeks.length === 0) {
                document.getElementById('mapWeekLabel').textContent = 'Pas de données';
                return;
            }

            const slider = document.getElementById('mapWeekSlider');
            slider.min = 0;
            slider.max = geoData.weeks.length - 1;
            slider.value = geoData.weeks.length - 1; // Start at most recent week

            filterMapByWeek(slider.value);
        }

        function filterMapByWeek(index) {
            if (!geoData || !geoData.weeks) return;

            const week = geoData.weeks[index];
            const label = document.getElementById('mapWeekLabel');

            if (week) {
                // Format YYYY-WNN to "Semaine NN, YYYY"
                const [year, w] = week.split('-W');
                label.textContent = `Sem. ${parseInt(w)}, ${year}`;
                currentFilterType = 'week';
                currentFilterValue = week;

                if (geoData.lieux_by_week && geoData.lieux_by_week[week]) {
                    updateMap(geoData.lieux_by_week[week]);
                } else {
                    updateMap([]);
                }
            }
        }

        function toggleWeekAnimation() {
            const btn = document.getElementById('btnPlayWeek');
            const slider = document.getElementById('mapWeekSlider');

            if (isWeekAnimating) {
                clearInterval(weekAnimationInterval);
                weekAnimationInterval = null;
                isWeekAnimating = false;
                btn.textContent = '▶';
            } else {
                isWeekAnimating = true;
                btn.textContent = '⏸';

                if (parseInt(slider.value) >= parseInt(slider.max)) {
                    slider.value = 0;
                }

                weekAnimationInterval = setInterval(() => {
                    const currentValue = parseInt(slider.value);
                    if (currentValue < parseInt(slider.max)) {
                        slider.value = currentValue + 1;
                        filterMapByWeek(slider.value);
                    } else {
                        toggleWeekAnimation();
                    }
                }, 200); // 200ms between each week
            }
        }

        // Day slider functions
        let dayAnimationInterval = null;
        let isDayAnimating = false;

        function initDaySlider() {
            if (!geoData || !geoData.days || geoData.days.length === 0) {
                document.getElementById('mapDayLabel').textContent = 'Pas de données';
                return;
            }

            const slider = document.getElementById('mapDaySlider');
            slider.min = 0;
            slider.max = geoData.days.length - 1;
            slider.value = geoData.days.length - 1; // Start at most recent day

            filterMapByDay(slider.value);
        }

        function filterMapByDay(index) {
            if (!geoData || !geoData.days) return;

            const day = geoData.days[index];
            const label = document.getElementById('mapDayLabel');

            if (day) {
                // Format YYYY-MM-DD to "DD Mois YYYY"
                const [year, m, d] = day.split('-');
                const monthNames = ['jan', 'fév', 'mar', 'avr', 'mai', 'juin',
                                   'juil', 'août', 'sep', 'oct', 'nov', 'déc'];
                label.textContent = `${parseInt(d)} ${monthNames[parseInt(m) - 1]} ${year}`;
                currentFilterType = 'day';
                currentFilterValue = day;

                if (geoData.lieux_by_day && geoData.lieux_by_day[day]) {
                    updateMap(geoData.lieux_by_day[day]);
                } else {
                    updateMap([]);
                }
            }
        }

        function toggleDayAnimation() {
            const btn = document.getElementById('btnPlayDay');
            const slider = document.getElementById('mapDaySlider');

            if (isDayAnimating) {
                clearInterval(dayAnimationInterval);
                dayAnimationInterval = null;
                isDayAnimating = false;
                btn.textContent = '▶';
            } else {
                isDayAnimating = true;
                btn.textContent = '⏸';

                if (parseInt(slider.value) >= parseInt(slider.max)) {
                    slider.value = 0;
                }

                dayAnimationInterval = setInterval(() => {
                    const currentValue = parseInt(slider.value);
                    if (currentValue < parseInt(slider.max)) {
                        slider.value = currentValue + 1;
                        filterMapByDay(slider.value);
                    } else {
                        toggleDayAnimation();
                    }
                }, 100); // 100ms between each day (fast animation)
            }
        }

        // Fullscreen mode
        let isMapFullscreen = false;

        function toggleMapFullscreen() {
            const mapSection = document.querySelector('.map-section');
            const btn = document.getElementById('btnFullscreen');

            isMapFullscreen = !isMapFullscreen;

            if (isMapFullscreen) {
                mapSection.classList.add('fullscreen');
                btn.textContent = '✕';
                btn.title = 'Quitter le plein écran';
                document.body.style.overflow = 'hidden';
            } else {
                mapSection.classList.remove('fullscreen');
                btn.textContent = '⛶';
                btn.title = 'Plein écran';
                document.body.style.overflow = '';
            }

            // Invalidate map size after transition
            setTimeout(() => {
                if (map) map.invalidateSize();
            }, 100);
        }

        // ESC key to exit fullscreen
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && isMapFullscreen) {
                toggleMapFullscreen();
            }
        });

        // Initialize map on page load
        document.addEventListener('DOMContentLoaded', function() {
            if (geoData) {
                initMap();
            }
        });
    </script>
</body>
</html>'''

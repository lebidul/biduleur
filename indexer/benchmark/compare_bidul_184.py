#!/usr/bin/env python3
"""
Benchmark pour comparer l'extraction du Bidul 184 avec les résultats attendus.

Usage:
    python benchmark/compare_bidul_184.py
"""

import csv
import sqlite3
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher


def normalize_text(text: str | None) -> str:
    """Normalise le texte pour la comparaison."""
    if not text:
        return ""
    # Normaliser les espaces et la casse
    text = " ".join(text.split()).strip()
    return text


def normalize_lieu(text: str | None) -> str:
    """Normalise un nom de lieu pour la comparaison."""
    if not text:
        return ""
    text = normalize_text(text).lower()
    # Supprimer les préfixes communs
    prefixes = ['bar ', 'bar le ', 'bar la ', 'centre culturel ', 'espace culturel ',
                'salle ', 'pub ', 'médiathèque ', 'la péniche ', 'péniche ']
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text


def normalize_tarif(text: str | None) -> str:
    """Normalise un tarif pour la comparaison."""
    if not text:
        return ""
    text = normalize_text(text).lower()
    # Supprimer les espaces autour du symbole €
    text = text.replace(' €', '€').replace('€ ', '€')
    return text


def normalize_date(date_val) -> str:
    """Normalise une date pour la comparaison."""
    if not date_val:
        return ""
    if isinstance(date_val, str):
        # Format attendu: 12/1/2013 ou 2013-12-01
        if "/" in date_val:
            parts = date_val.split("/")
            if len(parts) == 3:
                return f"{int(parts[2])}-{int(parts[0]):02d}-{int(parts[1]):02d}"
        return date_val
    return str(date_val)


def similarity(a: str, b: str) -> float:
    """Calcule la similarité entre deux chaînes."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def load_expected(csv_path: Path) -> list[dict]:
    """Charge le fichier CSV de référence."""
    expected = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            expected.append(row)
    return expected


def load_actual(db_path: Path, bidul_numero: int) -> list[dict]:
    """Charge les données actuelles de la base de données."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT
            e.raw_text,
            e.nom,
            e.date_evenement,
            e.heure,
            e.lieu_raw,
            e.ville_raw,
            e.tarif_raw,
            ce.nom_spectacle,
            ce.artiste,
            ce.style
        FROM evenement e
        LEFT JOIN contenu_evenement ce ON e.id = ce.evenement_id
        WHERE e.bidul_numero = ?
        ORDER BY e.date_evenement, e.id, ce.ordre
    """

    cursor = conn.execute(query, (bidul_numero,))
    actual = []
    for row in cursor:
        actual.append({
            'raw_text': row['raw_text'],
            'nom': row['nom'],
            'date_evenement': row['date_evenement'],
            'heure': row['heure'],
            'lieu_raw': row['lieu_raw'],
            'ville_raw': row['ville_raw'],
            'tarif_raw': row['tarif_raw'],
            'nom_spectacle': row['nom_spectacle'],
            'artiste': row['artiste'],
            'style': row['style']
        })
    conn.close()
    return actual


def compare_field(expected: str | None, actual: str | None, field_name: str) -> tuple[bool, str]:
    """Compare deux valeurs de champ."""
    exp_norm = normalize_text(expected)
    act_norm = normalize_text(actual)

    if field_name == 'date_evenement':
        exp_norm = normalize_date(expected)
        act_norm = normalize_date(actual)
    elif field_name == 'lieu_raw':
        exp_norm = normalize_lieu(expected)
        act_norm = normalize_lieu(actual)
    elif field_name == 'tarif_raw':
        exp_norm = normalize_tarif(expected)
        act_norm = normalize_tarif(actual)

    if exp_norm == act_norm:
        return True, ""

    sim = similarity(exp_norm, act_norm)
    if sim > 0.9:
        return True, f"~{sim:.0%}"  # Close match

    return False, f"'{exp_norm}' vs '{act_norm}'"


def find_matching_actual(expected_row: dict, actual_rows: list[dict]) -> dict | None:
    """Trouve la ligne actuelle correspondante basée sur raw_text + artiste."""
    exp_raw = normalize_text(expected_row.get('raw_text', ''))
    exp_artiste = normalize_text(expected_row.get('artiste', ''))

    best_match = None
    best_score = 0

    for actual in actual_rows:
        act_raw = normalize_text(actual.get('raw_text', ''))
        act_artiste = normalize_text(actual.get('artiste', ''))

        # Score basé sur raw_text et artiste
        raw_sim = similarity(exp_raw, act_raw)
        art_sim = similarity(exp_artiste, act_artiste) if exp_artiste else 1.0

        score = raw_sim * 0.7 + art_sim * 0.3

        if score > best_score and score > 0.5:
            best_score = score
            best_match = actual

    return best_match


def run_benchmark():
    """Exécute le benchmark."""
    base_dir = Path(__file__).parent.parent
    csv_path = base_dir / 'benchmark' / 'bidul_184_expected.csv'
    db_path = base_dir / 'database' / 'bidul_archives.db'

    print("=" * 80)
    print("BENCHMARK BIDUL 184 - Comparaison avec référence")
    print("=" * 80)
    print()

    # Charger les données
    expected = load_expected(csv_path)
    actual = load_actual(db_path, 184)

    print(f"Lignes attendues: {len(expected)}")
    print(f"Lignes extraites: {len(actual)}")
    print()

    # Champs à comparer
    fields = ['nom', 'date_evenement', 'heure', 'lieu_raw', 'ville_raw',
              'tarif_raw', 'nom_spectacle', 'artiste', 'style']

    # Statistiques
    stats = {field: {'correct': 0, 'incorrect': 0, 'missing': 0} for field in fields}
    errors = []

    # Comparer chaque ligne attendue
    matched_actual = set()
    for i, exp_row in enumerate(expected):
        actual_row = find_matching_actual(exp_row, actual)

        if not actual_row:
            # Ligne manquante
            errors.append({
                'row': i + 1,
                'type': 'MISSING',
                'raw_text': exp_row.get('raw_text', '')[:50] + '...',
                'artiste': exp_row.get('artiste', '')
            })
            for field in fields:
                if exp_row.get(field):
                    stats[field]['missing'] += 1
            continue

        matched_actual.add(id(actual_row))

        # Comparer les champs
        for field in fields:
            is_correct, detail = compare_field(exp_row.get(field), actual_row.get(field), field)

            if is_correct:
                stats[field]['correct'] += 1
            else:
                stats[field]['incorrect'] += 1
                if detail and not detail.startswith('~'):
                    errors.append({
                        'row': i + 1,
                        'type': 'MISMATCH',
                        'field': field,
                        'expected': exp_row.get(field, ''),
                        'actual': actual_row.get(field, ''),
                        'artiste': exp_row.get('artiste', '')
                    })

    # Lignes en trop
    extra_count = len(actual) - len(matched_actual)

    # Afficher le résumé
    print("-" * 80)
    print("RÉSUMÉ PAR CHAMP")
    print("-" * 80)
    print(f"{'Champ':<20} {'Correct':>10} {'Incorrect':>10} {'Manquant':>10} {'Score':>10}")
    print("-" * 80)

    total_correct = 0
    total_total = 0

    for field in fields:
        s = stats[field]
        total = s['correct'] + s['incorrect'] + s['missing']
        if total > 0:
            score = s['correct'] / total * 100
        else:
            score = 100

        total_correct += s['correct']
        total_total += total

        print(f"{field:<20} {s['correct']:>10} {s['incorrect']:>10} {s['missing']:>10} {score:>9.1f}%")

    print("-" * 80)
    overall_score = total_correct / total_total * 100 if total_total > 0 else 100
    print(f"{'TOTAL':<20} {total_correct:>10} {'':<10} {'':<10} {overall_score:>9.1f}%")
    print()

    if extra_count > 0:
        print(f"Lignes en trop dans l'extraction: {extra_count}")
        print()

    # Afficher les erreurs détaillées
    if errors:
        print("-" * 80)
        print("ERREURS DÉTAILLÉES (max 30)")
        print("-" * 80)

        for err in errors[:30]:
            if err['type'] == 'MISSING':
                print(f"[MANQUANT] Ligne {err['row']}: {err['artiste']} - {err['raw_text']}")
            else:
                print(f"[{err['field'].upper()}] Ligne {err['row']} ({err['artiste']})")
                print(f"  Attendu: {err['expected']}")
                print(f"  Obtenu:  {err['actual']}")
            print()

    print("=" * 80)
    print(f"Score global: {overall_score:.1f}%")
    print("=" * 80)

    return overall_score


if __name__ == '__main__':
    run_benchmark()

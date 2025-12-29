#!/usr/bin/env python3
"""
Migration pour ajouter artiste_ref_id à contenu_evenement et améliorer le matching lieu/artiste.

Actions:
1. Ajouter colonne artiste_ref_id à contenu_evenement
2. Améliorer le matching lieu pour utiliser lieu_alias
3. Créer le matching artiste avec artiste_alias
4. Back-populate les colonnes ref_id existantes

Usage:
    python scripts/migrate_ref_matching.py migrate      # Ajoute les colonnes
    python scripts/migrate_ref_matching.py backfill     # Back-populate les ref_id
    python scripts/migrate_ref_matching.py stats        # Statistiques de matching
"""

import argparse
import sqlite3
import unicodedata
import re
from pathlib import Path
from functools import lru_cache

DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# Normalisation
# =============================================================================

def normalize_text(text: str) -> str:
    """Normalise un texte pour le matching (minuscules, sans accents, sans ponctuation)."""
    if not text:
        return ''

    # Minuscules
    s = text.lower().strip()

    # Supprimer accents
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))

    # Normaliser apostrophes et tirets
    s = s.replace("'", "'").replace("'", "'").replace("`", "'")
    s = s.replace("–", "-").replace("—", "-")

    # Supprimer ponctuation sauf apostrophe
    s = re.sub(r'[\"«»„"",./:;!?()\{\}\[\]]', ' ', s)

    # Normaliser espaces
    s = ' '.join(s.split())

    return s


def normalize_for_matching(text: str) -> str:
    """Normalisation aggressive pour le matching (sans articles, sans espaces)."""
    s = normalize_text(text)

    # Supprimer articles
    s = re.sub(r"\b(le|la|l'|les|de|du|des|d'|au|aux|a|the|un|une)\b", '', s)

    # Supprimer espaces et apostrophes
    s = s.replace("'", "").replace("-", "").replace(" ", "")

    return s


# =============================================================================
# Chargement des référentiels avec alias
# =============================================================================

@lru_cache(maxsize=1)
def load_lieu_ref_with_aliases(db_path: str = None) -> dict[str, tuple[int, str]]:
    """
    Charge le référentiel des lieux avec leurs alias.
    Retourne dict: {normalized_name: (lieu_id, nom_canonique)}
    """
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    index = {}

    # Charger lieu_ref (actifs uniquement)
    cur.execute('SELECT id, nom FROM lieu_ref WHERE actif = 1')
    for row in cur.fetchall():
        lieu_id, nom = row
        # Ajouter forme originale
        index[normalize_for_matching(nom)] = (lieu_id, nom)
        # Ajouter forme sans accents
        index[normalize_text(nom).replace(' ', '')] = (lieu_id, nom)

    # Charger lieu_alias -> pointer vers lieu_ref
    cur.execute('''
        SELECT la.variante, lr.id, lr.nom
        FROM lieu_alias la
        JOIN lieu_ref lr ON la.lieu_nom = lr.nom AND lr.actif = 1
    ''')
    for row in cur.fetchall():
        variante, lieu_id, nom_canonique = row
        index[normalize_for_matching(variante)] = (lieu_id, nom_canonique)
        index[normalize_text(variante).replace(' ', '')] = (lieu_id, nom_canonique)

    conn.close()
    return index


@lru_cache(maxsize=1)
def load_artiste_ref_with_aliases(db_path: str = None) -> dict[str, tuple[int, str]]:
    """
    Charge le référentiel des artistes avec leurs alias.
    Retourne dict: {normalized_name: (artiste_id, nom_canonique)}
    """
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    index = {}

    # Charger artiste_ref (actifs uniquement)
    cur.execute('SELECT id, nom FROM artiste_ref WHERE actif = 1')
    for row in cur.fetchall():
        artiste_id, nom = row
        index[normalize_for_matching(nom)] = (artiste_id, nom)
        index[normalize_text(nom).replace(' ', '')] = (artiste_id, nom)

    # Charger artiste_alias -> pointer vers artiste_ref
    cur.execute('''
        SELECT aa.variante, ar.id, ar.nom
        FROM artiste_alias aa
        JOIN artiste_ref ar ON aa.artiste_nom = ar.nom AND ar.actif = 1
    ''')
    for row in cur.fetchall():
        variante, artiste_id, nom_canonique = row
        index[normalize_for_matching(variante)] = (artiste_id, nom_canonique)
        index[normalize_text(variante).replace(' ', '')] = (artiste_id, nom_canonique)

    conn.close()
    return index


def clear_caches():
    """Vide les caches après modification des référentiels."""
    load_lieu_ref_with_aliases.cache_clear()
    load_artiste_ref_with_aliases.cache_clear()


# =============================================================================
# Fonctions de matching
# =============================================================================

def _match_from_index(raw: str, index: dict, strict: bool = False) -> tuple[int | None, str | None]:
    """
    Matche un texte brut vers un index préchargé.
    Args:
        raw: texte brut à matcher
        index: dict {normalized_name: (ref_id, nom_canonique)}
        strict: si True, matching partiel plus strict (ratio > 0.7)
    Retourne (ref_id, nom_canonique) ou (None, None)
    """
    if not raw or not raw.strip():
        return None, None

    # Essayer matching exact
    key = normalize_for_matching(raw)
    if key in index:
        return index[key]

    # Essayer sans espaces
    key2 = normalize_text(raw).replace(' ', '')
    if key2 in index:
        return index[key2]

    # Matching partiel
    min_len = 5 if strict else 4
    min_ratio = 0.7 if strict else 0.5

    if len(key) > min_len:
        for ref_key, (ref_id, nom_canonique) in index.items():
            if len(ref_key) > min_len:
                if ref_key in key or key in ref_key:
                    ratio = min(len(ref_key), len(key)) / max(len(ref_key), len(key))
                    if ratio > min_ratio:
                        return (ref_id, nom_canonique)

    return None, None


def match_lieu(lieu_raw: str, db_path: str = None) -> tuple[int | None, str | None]:
    """
    Matche un lieu brut vers le référentiel (incluant alias).
    Retourne (lieu_ref_id, nom_canonique) ou (None, None) si non trouvé.
    """
    if not lieu_raw or not lieu_raw.strip():
        return None, None

    index = load_lieu_ref_with_aliases(db_path)

    # Essayer matching exact
    key = normalize_for_matching(lieu_raw)
    if key in index:
        return index[key]

    # Essayer sans espaces
    key2 = normalize_text(lieu_raw).replace(' ', '')
    if key2 in index:
        return index[key2]

    # Matching partiel (le lieu brut contient le nom de référence ou vice-versa)
    for ref_key, (lieu_id, nom_canonique) in index.items():
        if len(ref_key) > 4:  # Ignorer les clés trop courtes
            if ref_key in key or key in ref_key:
                # Vérifier que c'est un match significatif
                ratio = min(len(ref_key), len(key)) / max(len(ref_key), len(key))
                if ratio > 0.5:
                    return (lieu_id, nom_canonique)

    return None, None


def match_artiste(artiste_raw: str, db_path: str = None) -> tuple[int | None, str | None]:
    """
    Matche un artiste brut vers le référentiel (incluant alias).
    Retourne (artiste_ref_id, nom_canonique) ou (None, None) si non trouvé.
    """
    if not artiste_raw or not artiste_raw.strip():
        return None, None

    index = load_artiste_ref_with_aliases(db_path)

    # Essayer matching exact
    key = normalize_for_matching(artiste_raw)
    if key in index:
        return index[key]

    # Essayer sans espaces
    key2 = normalize_text(artiste_raw).replace(' ', '')
    if key2 in index:
        return index[key2]

    # Matching partiel pour les noms longs
    if len(key) > 5:
        for ref_key, (artiste_id, nom_canonique) in index.items():
            if len(ref_key) > 5:
                if ref_key in key or key in ref_key:
                    ratio = min(len(ref_key), len(key)) / max(len(ref_key), len(key))
                    if ratio > 0.7:  # Plus strict pour les artistes
                        return (artiste_id, nom_canonique)

    return None, None


# =============================================================================
# Migration
# =============================================================================

def migrate():
    """Ajoute la colonne artiste_ref_id à contenu_evenement."""
    conn = get_connection()
    cur = conn.cursor()

    print("=== Migration: ajout artiste_ref_id ===\n")

    # Vérifier si la colonne existe déjà
    cur.execute("PRAGMA table_info(contenu_evenement)")
    columns = {row['name'] for row in cur.fetchall()}

    if 'artiste_ref_id' in columns:
        print("Colonne artiste_ref_id existe déjà!")
    else:
        cur.execute('''
            ALTER TABLE contenu_evenement
            ADD COLUMN artiste_ref_id INTEGER REFERENCES artiste_ref(id)
        ''')
        print("+ Ajouté colonne artiste_ref_id à contenu_evenement")

        # Créer index
        cur.execute('CREATE INDEX IF NOT EXISTS idx_contenu_artiste_ref ON contenu_evenement(artiste_ref_id)')
        print("+ Créé index idx_contenu_artiste_ref")

    conn.commit()
    conn.close()
    print("\nMigration terminée!")


# =============================================================================
# Back-populate
# =============================================================================

def backfill():
    """Back-populate les colonnes lieu_ref_id et artiste_ref_id."""
    print("=== Back-populate ref_id ===\n")

    # Vider les caches pour charger les données fraîches
    clear_caches()

    # Charger les index une seule fois (hors connexion principale)
    print("Chargement des référentiels...")
    lieu_index = load_lieu_ref_with_aliases(str(DB_PATH))
    artiste_index = load_artiste_ref_with_aliases(str(DB_PATH))
    print(f"  - {len(lieu_index)} variantes de lieux")
    print(f"  - {len(artiste_index)} variantes d'artistes")

    # Maintenant ouvrir la connexion pour les updates
    conn = get_connection()
    cur = conn.cursor()

    # 1. Back-populate lieu_ref_id dans evenement
    print("\n1. Matching lieux...")
    cur.execute('''
        SELECT id, lieu_raw FROM evenement
        WHERE lieu_raw IS NOT NULL AND lieu_raw != ''
    ''')
    events = cur.fetchall()

    lieu_matched = 0
    lieu_total = len(events)

    for event in events:
        event_id, lieu_raw = event['id'], event['lieu_raw']
        lieu_id, _ = _match_from_index(lieu_raw, lieu_index)
        if lieu_id:
            cur.execute('UPDATE evenement SET lieu_ref_id = ? WHERE id = ?', (lieu_id, event_id))
            lieu_matched += 1

    print(f"   Lieux matchés: {lieu_matched}/{lieu_total} ({100*lieu_matched/lieu_total:.1f}%)")

    # 2. Back-populate artiste_ref_id dans contenu_evenement
    print("\n2. Matching artistes...")
    cur.execute('''
        SELECT id, artiste FROM contenu_evenement
        WHERE artiste IS NOT NULL AND artiste != ''
    ''')
    contenus = cur.fetchall()

    artiste_matched = 0
    artiste_total = len(contenus)

    for contenu in contenus:
        contenu_id, artiste_raw = contenu['id'], contenu['artiste']
        artiste_id, _ = _match_from_index(artiste_raw, artiste_index, strict=True)
        if artiste_id:
            cur.execute('UPDATE contenu_evenement SET artiste_ref_id = ? WHERE id = ?', (artiste_id, contenu_id))
            artiste_matched += 1

    print(f"   Artistes matchés: {artiste_matched}/{artiste_total} ({100*artiste_matched/artiste_total:.1f}%)")

    conn.commit()
    conn.close()
    print("\nBack-populate terminé!")


def stats():
    """Affiche les statistiques de matching."""
    conn = get_connection()
    cur = conn.cursor()

    print("=== Statistiques de matching ===\n")

    # Lieux
    cur.execute('SELECT COUNT(*) FROM evenement WHERE lieu_raw IS NOT NULL')
    total_lieux = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM evenement WHERE lieu_ref_id IS NOT NULL')
    matched_lieux = cur.fetchone()[0]

    print(f"Lieux:")
    print(f"  Total avec lieu_raw: {total_lieux}")
    print(f"  Matchés (lieu_ref_id): {matched_lieux} ({100*matched_lieux/total_lieux:.1f}%)")
    print(f"  Non matchés: {total_lieux - matched_lieux}")

    # Artistes
    cur.execute('SELECT COUNT(*) FROM contenu_evenement WHERE artiste IS NOT NULL')
    total_artistes = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM contenu_evenement WHERE artiste_ref_id IS NOT NULL')
    matched_artistes = cur.fetchone()[0]

    print(f"\nArtistes:")
    print(f"  Total avec artiste: {total_artistes}")
    print(f"  Matchés (artiste_ref_id): {matched_artistes} ({100*matched_artistes/total_artistes:.1f}%)")
    print(f"  Non matchés: {total_artistes - matched_artistes}")

    # Top 10 lieux non matchés
    print("\n--- Top 10 lieux non matchés ---")
    cur.execute('''
        SELECT lieu_raw, COUNT(*) as cnt
        FROM evenement
        WHERE lieu_raw IS NOT NULL AND lieu_ref_id IS NULL
        GROUP BY lieu_raw
        ORDER BY cnt DESC
        LIMIT 10
    ''')
    for row in cur.fetchall():
        print(f"  {row['cnt']:4} x {row['lieu_raw']}")

    # Top 10 artistes non matchés
    print("\n--- Top 10 artistes non matchés ---")
    cur.execute('''
        SELECT artiste, COUNT(*) as cnt
        FROM contenu_evenement
        WHERE artiste IS NOT NULL AND artiste_ref_id IS NULL
        GROUP BY artiste
        ORDER BY cnt DESC
        LIMIT 10
    ''')
    for row in cur.fetchall():
        print(f"  {row['cnt']:4} x {row['artiste']}")

    conn.close()


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Migration et matching ref_id')
    parser.add_argument('action', choices=['migrate', 'backfill', 'stats'],
                        help='Action à effectuer')

    args = parser.parse_args()

    if args.action == 'migrate':
        migrate()
    elif args.action == 'backfill':
        backfill()
    elif args.action == 'stats':
        stats()


if __name__ == '__main__':
    main()

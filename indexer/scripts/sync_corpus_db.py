#!/usr/bin/env python3
"""
Synchronisation bidirectionnelle entre les corpus CSV et la base de données.

Workflow:
1. corpus-to-db: Importe les CSV du corpus dans la DB (lieu, artiste, alias)
2. db-to-corpus: Exporte les tables DB vers les CSV du corpus
3. dedupe-db: Deduplique les tables ref en DB et migre vers alias

Usage:
    python sync_corpus_db.py corpus-to-db   # CSV -> DB
    python sync_corpus_db.py db-to-corpus   # DB -> CSV
    python sync_corpus_db.py dedupe-db      # Dedupe lieu_ref et artiste_ref
    python sync_corpus_db.py init-tables    # Crée les tables manquantes
"""

import argparse
import csv
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

CORPUS_DIR = Path(__file__).parent.parent / 'corpus'
DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def get_connection():
    """Crée une connexion à la DB."""
    return sqlite3.connect(DB_PATH)


def init_tables(conn):
    """Crée les tables manquantes pour le référentiel complet."""
    cursor = conn.cursor()

    # Table lieu_alias (n'existe pas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lieu_alias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            variante TEXT NOT NULL UNIQUE,
            lieu_nom TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table artiste_ref (n'existe pas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artiste_ref (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            nom_normalise TEXT,
            style TEXT,
            actif INTEGER DEFAULT 1
        )
    """)

    # Renommer colonnes de artiste_alias pour cohérence si nécessaire
    # Vérifier structure actuelle
    cursor.execute("PRAGMA table_info(artiste_alias)")
    cols = {row[1] for row in cursor.fetchall()}

    if 'nom_variante' in cols and 'variante' not in cols:
        # Recréer la table avec le bon schéma
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS artiste_alias_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variante TEXT NOT NULL UNIQUE,
                artiste_nom TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO artiste_alias_new (variante, artiste_nom, created_at)
            SELECT nom_variante, nom_normalise, created_at FROM artiste_alias
        """)
        cursor.execute("DROP TABLE artiste_alias")
        cursor.execute("ALTER TABLE artiste_alias_new RENAME TO artiste_alias")

    conn.commit()
    print("+ Tables initialisées/mises à jour")


def normalize_for_grouping(name: str) -> str:
    """Normalisation aggressive pour regrouper les variantes."""
    s = name.lower().strip()

    # Supprimer accents
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))

    # Supprimer ponctuation
    s = re.sub(r"[''\"«»„"",./:;!?(){}—–-]", ' ', s)
    s = s.replace('[', ' ').replace(']', ' ')
    s = s.replace('&', 'et')

    # Supprimer articles
    s = re.sub(r'\b(le|la|l|les|de|du|des|d|au|aux|a|the)\b', '', s)

    # Normaliser espaces
    s = ''.join(s.split())

    return s


def choose_canonical_lieu(group):
    """Choisit la forme canonique parmi un groupe de lieux."""
    def score(lieu):
        nom = lieu['nom']
        s = 0
        if any(c in nom for c in 'éèêëàâäùûüôöîïç'):
            s += 10
        s += len(nom) / 10
        if nom[0].isupper():
            s += 5
        if 'royale' in nom.lower() or 'royal' in nom.lower():
            s += 3
        if '(' in nom or '[' in nom:
            s -= 2
        return s
    return max(group, key=score)


def choose_canonical_artiste(group):
    """Choisit la forme canonique parmi un groupe d'artistes."""
    def score(artiste):
        nom = artiste['nom']
        s = 0
        if any(c in nom for c in 'éèêëàâäùûüôöîïçÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ'):
            s += 10
        s += len(nom) / 10
        if nom[0].isupper() and not nom.isupper():
            s += 5
        if nom.isupper():
            s -= 3
        if '(' in nom or '[' in nom:
            s -= 2
        if artiste.get('style'):
            s += 2
        return s
    return max(group, key=score)


# =============================================================================
# Corpus -> DB
# =============================================================================

def import_lieux_to_db(conn, reset=True):
    """Importe lieu.csv et lieu_alias.csv dans la DB."""
    cursor = conn.cursor()

    # Reset: supprimer les anciennes données si demandé
    if reset:
        cursor.execute("DELETE FROM lieu_ref")
        cursor.execute("DELETE FROM lieu_alias")
        print("  (tables lieu_ref et lieu_alias vidées)")

    # Importer lieu.csv -> lieu_ref (avec toutes les colonnes géographiques)
    lieu_csv = CORPUS_DIR / 'lieu.csv'
    if lieu_csv.exists():
        with open(lieu_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                # Convertir les coordonnées en float si présentes
                lat = float(row['latitude']) if row.get('latitude') else None
                lon = float(row['longitude']) if row.get('longitude') else None

                cursor.execute("""
                    INSERT OR REPLACE INTO lieu_ref (
                        nom, ville, actif,
                        adresse_numero, adresse_voie, code_postal,
                        latitude, longitude, geo_source, geo_precision, nom_osm
                    )
                    VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['nom'],
                    row.get('ville', '') or 'Le Mans',
                    row.get('adresse_numero') or None,
                    row.get('adresse_voie') or None,
                    row.get('code_postal') or None,
                    lat,
                    lon,
                    row.get('geo_source') or None,
                    row.get('geo_precision') or None,
                    row.get('nom_osm') or None
                ))
                count += 1
        print(f"+ Importé {count} lieux dans lieu_ref (avec coordonnées)")

    # Importer lieu_alias.csv -> lieu_alias
    alias_csv = CORPUS_DIR / 'lieu_alias.csv'
    if alias_csv.exists():
        with open(alias_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cursor.execute("""
                    INSERT OR IGNORE INTO lieu_alias (variante, lieu_nom)
                    VALUES (?, ?)
                """, (row['variante'], row['lieu_nom']))
                count += 1
        print(f"+ Importé {count} alias de lieux dans lieu_alias")

    conn.commit()


def import_artistes_to_db(conn, reset=True):
    """Importe artiste.csv et artiste_alias.csv dans la DB."""
    cursor = conn.cursor()

    # Reset: supprimer les anciennes données si demandé
    if reset:
        cursor.execute("DELETE FROM artiste_ref")
        cursor.execute("DELETE FROM artiste_alias")
        print("  (tables artiste_ref et artiste_alias vidées)")

    # Importer artiste.csv -> artiste_ref
    artiste_csv = CORPUS_DIR / 'artiste.csv'
    if artiste_csv.exists():
        with open(artiste_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cursor.execute("""
                    INSERT OR REPLACE INTO artiste_ref (nom, nom_normalise, style, actif)
                    VALUES (?, ?, ?, 1)
                """, (row['nom_canonique'], row.get('nom_normalise', ''), row.get('style', '')))
                count += 1
        print(f"+ Importé {count} artistes dans artiste_ref")

    # Importer artiste_alias.csv -> artiste_alias
    alias_csv = CORPUS_DIR / 'artiste_alias.csv'
    if alias_csv.exists():
        with open(alias_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cursor.execute("""
                    INSERT OR IGNORE INTO artiste_alias (variante, artiste_nom)
                    VALUES (?, ?)
                """, (row['variante'], row['artiste_nom']))
                count += 1
        print(f"+ Importé {count} alias d'artistes dans artiste_alias")

    conn.commit()


def import_villes_to_db(conn, reset=True):
    """Importe ville.csv dans la DB."""
    cursor = conn.cursor()

    # Reset: supprimer les anciennes données si demandé
    if reset:
        cursor.execute("DELETE FROM ville_ref")
        print("  (table ville_ref vidée)")

    ville_csv = CORPUS_DIR / 'ville.csv'
    if ville_csv.exists():
        with open(ville_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cursor.execute("""
                    INSERT OR IGNORE INTO ville_ref (nom)
                    VALUES (?)
                """, (row['nom'],))
                count += 1
        print(f"+ Importé {count} villes dans ville_ref")

    conn.commit()


def corpus_to_db():
    """Importe tous les corpus CSV dans la DB."""
    conn = get_connection()
    init_tables(conn)

    print("\n=== Import Corpus CSV -> DB ===\n")
    import_lieux_to_db(conn)
    import_artistes_to_db(conn)
    import_villes_to_db(conn)

    conn.close()
    print("\n+ Import terminé!")


# =============================================================================
# DB -> Corpus
# =============================================================================

def export_lieux_from_db(conn):
    """Exporte lieu_ref et lieu_alias vers les CSV."""
    cursor = conn.cursor()

    # Exporter lieu_ref -> lieu.csv (avec toutes les colonnes géographiques)
    cursor.execute("""
        SELECT nom, ville, adresse_numero, adresse_voie, code_postal,
               latitude, longitude, geo_source, geo_precision, nom_osm
        FROM lieu_ref WHERE actif = 1 ORDER BY ville, nom
    """)
    rows = cursor.fetchall()

    with open(CORPUS_DIR / 'lieu.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['nom', 'ville', 'nom_normalise', 'adresse_numero', 'adresse_voie',
                         'code_postal', 'latitude', 'longitude', 'geo_source', 'geo_precision', 'nom_osm'])
        for nom, ville, addr_num, addr_voie, cp, lat, lon, source, precision, nom_osm in rows:
            # Calculer nom_normalise
            norm = normalize_for_grouping(nom)
            writer.writerow([
                nom,
                ville or 'Le Mans',
                norm,
                addr_num or '',
                addr_voie or '',
                cp or '',
                lat if lat is not None else '',
                lon if lon is not None else '',
                source or '',
                precision or '',
                nom_osm or ''
            ])

    print(f"+ Exporté {len(rows)} lieux vers lieu.csv (avec coordonnées)")

    # Exporter lieu_alias -> lieu_alias.csv
    cursor.execute("SELECT variante, lieu_nom FROM lieu_alias ORDER BY variante")
    rows = cursor.fetchall()

    with open(CORPUS_DIR / 'lieu_alias.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['variante', 'lieu_nom'])
        for variante, lieu_nom in rows:
            writer.writerow([variante, lieu_nom])

    print(f"+ Exporté {len(rows)} alias vers lieu_alias.csv")


def export_artistes_from_db(conn):
    """Exporte artiste_ref et artiste_alias vers les CSV."""
    cursor = conn.cursor()

    # Exporter artiste_ref -> artiste.csv
    cursor.execute("SELECT nom, nom_normalise, style FROM artiste_ref WHERE actif = 1 ORDER BY nom")
    rows = cursor.fetchall()

    with open(CORPUS_DIR / 'artiste.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['nom_canonique', 'nom_normalise', 'style'])
        for nom, nom_normalise, style in rows:
            # Recalculer nom_normalise si vide
            if not nom_normalise:
                nom_normalise = normalize_for_grouping(nom)
            writer.writerow([nom, nom_normalise, style or ''])

    print(f"+ Exporté {len(rows)} artistes vers artiste.csv")

    # Exporter artiste_alias -> artiste_alias.csv
    cursor.execute("SELECT variante, artiste_nom FROM artiste_alias ORDER BY variante")
    rows = cursor.fetchall()

    with open(CORPUS_DIR / 'artiste_alias.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['variante', 'artiste_nom'])
        for variante, artiste_nom in rows:
            writer.writerow([variante, artiste_nom])

    print(f"+ Exporté {len(rows)} alias vers artiste_alias.csv")


def export_villes_from_db(conn):
    """Exporte ville_ref vers ville.csv."""
    cursor = conn.cursor()

    cursor.execute("SELECT nom FROM ville_ref ORDER BY nom")
    rows = cursor.fetchall()

    with open(CORPUS_DIR / 'ville.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['nom'])
        for (nom,) in rows:
            writer.writerow([nom])

    print(f"+ Exporté {len(rows)} villes vers ville.csv")


def db_to_corpus():
    """Exporte toutes les tables DB vers les corpus CSV."""
    conn = get_connection()

    print("\n=== Export DB -> Corpus CSV ===\n")
    export_lieux_from_db(conn)
    export_artistes_from_db(conn)
    export_villes_from_db(conn)

    conn.close()
    print("\n+ Export terminé!")


# =============================================================================
# Deduplication en DB
# =============================================================================

def dedupe_lieu_ref(conn, apply=False):
    """Trouve et fusionne les doublons dans lieu_ref."""
    cursor = conn.cursor()

    # Charger tous les lieux
    cursor.execute("SELECT id, nom, ville FROM lieu_ref WHERE actif = 1")
    lieux = [{'id': r[0], 'nom': r[1], 'ville': r[2]} for r in cursor.fetchall()]

    # Grouper par clé normalisée
    groups = defaultdict(list)
    for lieu in lieux:
        key = normalize_for_grouping(lieu['nom'])
        groups[key].append(lieu)

    # Trouver les doublons
    duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    if not duplicates:
        print("Aucun doublon de lieu détecté!")
        return

    print(f"\n{'='*60}")
    print(f"DOUBLONS LIEU_REF - {len(duplicates)} groupes trouvés")
    print(f"{'='*60}\n")

    to_deactivate = []
    to_alias = []

    for key, group in sorted(duplicates.items()):
        canonical = choose_canonical_lieu(group)
        others = [l for l in group if l['id'] != canonical['id']]

        if others:
            print(f"Groupe: {canonical['nom']}")
            for other in others:
                print(f"  - {other['nom']} (id={other['id']}) -> alias")
                to_deactivate.append(other['id'])
                to_alias.append((other['nom'], canonical['nom']))

    print(f"\n{'='*60}")
    print(f"RÉSUMÉ:")
    print(f"  - {len(to_deactivate)} lieux à désactiver")
    print(f"  - {len(to_alias)} alias à créer")
    print(f"{'='*60}")

    if apply and to_alias:
        # Désactiver les doublons
        for lid in to_deactivate:
            cursor.execute("UPDATE lieu_ref SET actif = 0 WHERE id = ?", (lid,))

        # Créer les alias
        for variante, canonical in to_alias:
            cursor.execute("""
                INSERT OR IGNORE INTO lieu_alias (variante, lieu_nom)
                VALUES (?, ?)
            """, (variante, canonical))

        conn.commit()
        print(f"\n+ Appliqué: {len(to_deactivate)} désactivés, {len(to_alias)} alias créés")
    elif to_alias:
        print("\n[dry-run] Utilisez --apply pour appliquer")


def dedupe_artiste_ref(conn, apply=False):
    """Trouve et fusionne les doublons dans artiste_ref."""
    cursor = conn.cursor()

    # Charger tous les artistes
    cursor.execute("SELECT id, nom, nom_normalise, style FROM artiste_ref WHERE actif = 1")
    artistes = [{'id': r[0], 'nom': r[1], 'nom_normalise': r[2], 'style': r[3]} for r in cursor.fetchall()]

    # Grouper par clé normalisée
    groups = defaultdict(list)
    for artiste in artistes:
        key = normalize_for_grouping(artiste['nom'])
        groups[key].append(artiste)

    # Trouver les doublons
    duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    if not duplicates:
        print("Aucun doublon d'artiste détecté!")
        return

    print(f"\n{'='*60}")
    print(f"DOUBLONS ARTISTE_REF - {len(duplicates)} groupes trouvés")
    print(f"{'='*60}\n")

    to_deactivate = []
    to_alias = []

    for key, group in sorted(duplicates.items()):
        canonical = choose_canonical_artiste(group)
        others = [a for a in group if a['id'] != canonical['id']]

        if others:
            print(f"Groupe: {canonical['nom']}")
            for other in others:
                print(f"  - {other['nom']} (id={other['id']}) -> alias")
                to_deactivate.append(other['id'])
                to_alias.append((other['nom'], canonical['nom']))

    print(f"\n{'='*60}")
    print(f"RÉSUMÉ:")
    print(f"  - {len(to_deactivate)} artistes à désactiver")
    print(f"  - {len(to_alias)} alias à créer")
    print(f"{'='*60}")

    if apply and to_alias:
        # Désactiver les doublons
        for aid in to_deactivate:
            cursor.execute("UPDATE artiste_ref SET actif = 0 WHERE id = ?", (aid,))

        # Créer les alias
        for variante, canonical in to_alias:
            cursor.execute("""
                INSERT OR IGNORE INTO artiste_alias (variante, artiste_nom)
                VALUES (?, ?)
            """, (variante, canonical))

        conn.commit()
        print(f"\n+ Appliqué: {len(to_deactivate)} désactivés, {len(to_alias)} alias créés")
    elif to_alias:
        print("\n[dry-run] Utilisez --apply pour appliquer")


def dedupe_db(apply=False):
    """Deduplique lieu_ref et artiste_ref en DB."""
    conn = get_connection()

    print("\n=== Deduplication en DB ===\n")
    dedupe_lieu_ref(conn, apply)
    print()
    dedupe_artiste_ref(conn, apply)

    conn.close()


# =============================================================================
# Stats
# =============================================================================

def show_stats():
    """Affiche les statistiques des tables."""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n=== Statistiques DB ===\n")

    tables = [
        ('lieu_ref', 'SELECT COUNT(*) FROM lieu_ref WHERE actif = 1'),
        ('lieu_ref (inactifs)', 'SELECT COUNT(*) FROM lieu_ref WHERE actif = 0'),
        ('lieu_alias', 'SELECT COUNT(*) FROM lieu_alias'),
        ('artiste_ref', 'SELECT COUNT(*) FROM artiste_ref WHERE actif = 1'),
        ('artiste_ref (inactifs)', 'SELECT COUNT(*) FROM artiste_ref WHERE actif = 0'),
        ('artiste_alias', 'SELECT COUNT(*) FROM artiste_alias'),
        ('ville_ref', 'SELECT COUNT(*) FROM ville_ref'),
    ]

    for name, query in tables:
        try:
            cursor.execute(query)
            count = cursor.fetchone()[0]
            print(f"  {name:25} {count:>6} entrées")
        except sqlite3.OperationalError:
            print(f"  {name:25} (table inexistante)")

    conn.close()


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Synchronisation Corpus CSV <-> DB')
    parser.add_argument('action', choices=['corpus-to-db', 'db-to-corpus', 'dedupe-db', 'init-tables', 'stats'],
                        help='Action à effectuer')
    parser.add_argument('--apply', '-a', action='store_true',
                        help='Appliquer les changements (pour dedupe-db)')

    args = parser.parse_args()

    if args.action == 'corpus-to-db':
        corpus_to_db()
    elif args.action == 'db-to-corpus':
        db_to_corpus()
    elif args.action == 'dedupe-db':
        dedupe_db(args.apply)
    elif args.action == 'init-tables':
        conn = get_connection()
        init_tables(conn)
        conn.close()
    elif args.action == 'stats':
        show_stats()


if __name__ == '__main__':
    main()

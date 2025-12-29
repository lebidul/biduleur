"""
Genere les fichiers CSV de corpus a partir de la base existante.
A executer une fois pour initialiser, puis enrichir manuellement.

Usage:
    python scripts/generate_corpus_csv.py
"""

import csv
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

# Ajouter le parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.normalizer import normalize_name

CORPUS_DIR = Path(__file__).parent.parent / 'corpus'
DB_PATH = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'


def update_lieu_csv():
    """Met a jour lieu.csv avec la colonne nom_normalise."""
    lieu_path = CORPUS_DIR / 'lieu.csv'

    if not lieu_path.exists():
        print(f"! {lieu_path} n'existe pas")
        return

    # Lire le CSV existant
    lieux = []
    with open(lieu_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['nom_normalise'] = normalize_name(row['nom'])
            lieux.append(row)

    # Reecrire avec nom_normalise
    with open(lieu_path, 'w', encoding='utf-8', newline='') as f:
        out_fieldnames = ['nom', 'ville', 'nom_normalise']
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        for lieu in lieux:
            writer.writerow({
                'nom': lieu['nom'],
                'ville': lieu.get('ville', 'Le Mans'),
                'nom_normalise': lieu['nom_normalise']
            })

    print(f"+ Mis a jour {len(lieux)} lieux dans lieu.csv")


def generate_lieu_alias_csv():
    """Genere lieu_alias.csv avec les aliases courants."""

    aliases = [
        # Abreviations theatres
        ("S.Jean Carmet", "Salle Jean Carmet"),
        ("S. Jean Carmet", "Salle Jean Carmet"),
        ("Th. Paul Scarron", "Theatre Paul Scarron"),
        ("Th. de Chaoue", "Theatre de Chaoue"),
        ("Th. du Passeur", "Theatre du Passeur"),
        ("Th. de la Halle au Ble", "Theatre de la Halle-au-Ble"),
        ("Th. Municipal", "Theatre Municipal"),
        ("MJC J.Prevert", "MJC Prevert"),
        ("MJC J. Prevert", "MJC Prevert"),

        # Variantes PCV / Palais
        ("Le PCV", "PCC"),
        ("le PCV", "PCC"),
        ("PCV", "PCC"),
        ("Bar Le Palais", "Le Palace"),
        ("bar Le Palais", "Le Palace"),
        ("Bar le Palais", "Le Palace"),

        # Variantes Peniche
        ("Peniche Excelsior", "La Peniche Excelsior"),
        ("Peniche", "La Peniche Excelsior"),
        ("La Peniche", "La Peniche Excelsior"),
        ("la Peniche Excelsior", "La Peniche Excelsior"),
        ("PENICHE EXCELSIOR", "La Peniche Excelsior"),
        ("Peniche Excelsior", "Peniche Excelsior"),

        # Variantes de casse
        ("l'Oasis", "L'Oasis"),
        ("L'OASIS", "L'Oasis"),
        ("l'oasis", "L'Oasis"),
        ("le Zoo", "Le Zoo"),
        ("LE ZOO", "Le Zoo"),
        ("le Barouf", "Le Barouf"),
        ("LE BAROUF", "Le Barouf"),
        ("le Lezard", "Le Lezard"),
        ("LE LEZARD", "Le Lezard"),
        ("Bar le Lezard", "Le Lezard"),
        ("bar le Lezard", "Le Lezard"),
        ("l'Espal", "L'Espal"),
        ("L'ESPAL", "L'Espal"),
        ("la Fonderie", "La Fonderie"),
        ("LA FONDERIE", "La Fonderie"),
        ("les Saulnieres", "Les Saulnieres"),
        ("LES SAULNIERES", "Les Saulnieres"),
        ("les Quinconces", "Les Quinconces"),
        ("LES QUINCONCES", "Les Quinconces"),

        # Autres variantes
        ("Circuit de la Biere", "Le Circuit de la Biere"),
        ("White - UNDR Club", "White-UNDR Club"),
        ("White - Undr Club", "White-UNDR Club"),
        ("WHITE-UNDR CLUB", "White-UNDR Club"),
        ("L'Epicerie sur le Zinc", "L'Epicerie sur le Zinc"),
        ("l'Epicerie sur le Zinc", "L'Epicerie sur le Zinc"),
        ("Bar le Passeport", "Le Passeport"),
        ("bar le Passeport", "Le Passeport"),
    ]

    alias_path = CORPUS_DIR / 'lieu_alias.csv'
    with open(alias_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['variante', 'lieu_nom'])
        for variante, lieu_nom in aliases:
            writer.writerow([variante, lieu_nom])

    print(f"+ Cree {len(aliases)} aliases dans lieu_alias.csv")


def generate_artiste_csv_from_db():
    """Genere artiste.csv depuis les artistes frequents de la base."""

    if not DB_PATH.exists():
        print(f"! Base non trouvee: {DB_PATH}")
        return {}

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Verifier si la table existe
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contenu_evenement'")
    if not cur.fetchone():
        print("! Table contenu_evenement non trouvee")
        conn.close()
        return {}

    # Recuperer tous les artistes avec frequence
    cur.execute("""
        SELECT artiste, COUNT(*) as n
        FROM contenu_evenement
        WHERE artiste IS NOT NULL AND artiste != ''
        GROUP BY artiste
        ORDER BY n DESC
    """)

    artistes_raw = cur.fetchall()
    conn.close()

    print(f"Trouve {len(artistes_raw)} artistes distincts dans la base")

    if not artistes_raw:
        return {}

    # Grouper par nom normalise
    groups = defaultdict(list)
    for artiste, count in artistes_raw:
        norm = normalize_name(artiste)
        if norm:
            groups[norm].append((artiste, count))

    print(f"Groupes en {len(groups)} groupes normalises")

    # Pour chaque groupe, le canonique est le plus frequent
    artistes = []
    for norm, variants in groups.items():
        variants.sort(key=lambda x: -x[1])
        total_count = sum(v[1] for v in variants)

        # Garder seulement les artistes avec >= 3 occurrences
        if total_count >= 3:
            canonique = variants[0][0]
            artistes.append({
                'nom_canonique': canonique,
                'nom_normalise': norm,
                'style': ''
            })

    # Trier alphabetiquement
    artistes.sort(key=lambda x: x['nom_canonique'].lower())

    artiste_path = CORPUS_DIR / 'artiste.csv'
    with open(artiste_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['nom_canonique', 'nom_normalise', 'style'])
        writer.writeheader()
        writer.writerows(artistes)

    print(f"+ Cree {len(artistes)} artistes dans artiste.csv")

    return groups


def generate_artiste_alias_csv(groups: dict):
    """Genere artiste_alias.csv depuis les groupes."""

    if not groups:
        print("! Aucun groupe d'artistes pour generer les aliases")
        return

    aliases = []

    for norm, variants in groups.items():
        if len(variants) < 2:
            continue

        total_count = sum(v[1] for v in variants)
        if total_count < 3:
            continue

        variants.sort(key=lambda x: -x[1])
        canonique = variants[0][0]

        # Les autres variantes deviennent des aliases
        for variante, _ in variants[1:]:
            if variante.lower() != canonique.lower():
                aliases.append({
                    'variante': variante,
                    'artiste_nom': canonique
                })

    # Aliases manuels supplementaires
    manual_aliases = [
        ("Dj SUPER LUCIEN", "DJ SUPER LUCIEN"),
        ("Dj Super Lucien", "DJ SUPER LUCIEN"),
        ("DJ Super Lucien", "DJ SUPER LUCIEN"),
        ("Dj DOUBLE FIRE", "DJ DOUBLE FIRE"),
        ("Dj Double fire", "DJ DOUBLE FIRE"),
        ("SMAK FLY", "SMAC FLY"),
        ("Smac Fly", "SMAC FLY"),
        ("Cie Pieces & Main d'Oeuvre", "Cie Pieces et Main d'Oeuvre"),
        ("Cie Pieces et Main d'oeuvre", "Cie Pieces et Main d'Oeuvre"),
        ("Cie Pieces et Main d'oeuvre", "Cie Pieces et Main d'Oeuvre"),
        ("Cie Pieces & M.O", "Cie Pieces et Main d'Oeuvre"),
        ("Apero jazz manouche", "Apero Jazz Manouche"),
        ("APERO JAZZ MANOUCHE", "Apero Jazz Manouche"),
        ("Boeuf Bal Folk, L'", "Boeuf Bal Folk"),
        ("Boeuf Bal Folk", "Boeuf Bal Folk"),
        ("Session mus.irlandaise", "Session Musique Irlandaise"),
        ("SESSION MUSIQUE IRLANDAISE", "Session Musique Irlandaise"),
    ]

    for variante, artiste_nom in manual_aliases:
        if not any(a['variante'] == variante for a in aliases):
            aliases.append({'variante': variante, 'artiste_nom': artiste_nom})

    # Trier
    aliases.sort(key=lambda x: (x['artiste_nom'].lower(), x['variante'].lower()))

    alias_path = CORPUS_DIR / 'artiste_alias.csv'
    with open(alias_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['variante', 'artiste_nom'])
        writer.writeheader()
        writer.writerows(aliases)

    print(f"+ Cree {len(aliases)} aliases dans artiste_alias.csv")


def main():
    print("=" * 60)
    print("GENERATION DES FICHIERS CSV DE CORPUS")
    print("=" * 60)

    print("\n1. Mise a jour lieu.csv...")
    update_lieu_csv()

    print("\n2. Generation lieu_alias.csv...")
    generate_lieu_alias_csv()

    print("\n3. Generation artiste.csv...")
    groups = generate_artiste_csv_from_db()

    print("\n4. Generation artiste_alias.csv...")
    generate_artiste_alias_csv(groups)

    print("\n" + "=" * 60)
    print("TERMINE")
    print("Fichiers crees dans corpus/")
    print("Enrichir manuellement puis commiter dans Git")


if __name__ == '__main__':
    main()

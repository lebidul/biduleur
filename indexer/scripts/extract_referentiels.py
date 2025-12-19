#!/usr/bin/env python3
"""
Script pour extraire les référentiels lieux et villes depuis les CSV de tapage.
"""

import csv
import os
from pathlib import Path


def extract_from_tapages():
    """Extrait les lieux et villes uniques depuis les CSV de tapage."""
    tapages_dir = Path(__file__).parent.parent.parent / "biduleur" / "tapages" / "toBeConverted"

    lieux = set()
    villes = set()

    for csv_file in tapages_dir.glob("*.csv"):
        # Ignorer les fichiers de sortie
        if ".new." in csv_file.name:
            continue

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    lieu = row.get('lieu', '').strip()
                    ville = row.get('ville', '').strip()

                    if lieu and lieu not in ('', 'lieu'):
                        lieux.add(lieu)
                    if ville and ville not in ('', 'ville'):
                        villes.add(ville)
        except Exception as e:
            print(f"Erreur lecture {csv_file.name}: {e}")

    return sorted(lieux), sorted(villes)


def save_referentiels(lieux: list, villes: list):
    """Sauvegarde les référentiels en CSV."""
    corpus_dir = Path(__file__).parent.parent / "corpus"
    corpus_dir.mkdir(exist_ok=True)

    # Lieux
    lieu_file = corpus_dir / "lieu.csv"
    with open(lieu_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['nom', 'ville'])
        for lieu in lieux:
            writer.writerow([lieu, 'Le Mans'])  # Ville par défaut
    print(f"Lieux sauvegardés: {lieu_file} ({len(lieux)} entrées)")

    # Villes
    ville_file = corpus_dir / "ville.csv"
    with open(ville_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['nom'])
        for ville in villes:
            writer.writerow([ville])
    print(f"Villes sauvegardées: {ville_file} ({len(villes)} entrées)")


if __name__ == "__main__":
    print("Extraction des référentiels depuis les CSV de tapage...")
    lieux, villes = extract_from_tapages()

    print(f"\nLieux trouvés: {len(lieux)}")
    print(f"Villes trouvées: {len(villes)}")

    save_referentiels(lieux, villes)

    print("\nExemples de lieux:")
    for lieu in lieux[:10]:
        print(f"  - {lieu}")

    print("\nExemples de villes:")
    for ville in villes[:10]:
        print(f"  - {ville}")

#!/usr/bin/env python3
"""
Outil de déduplication des artistes dans artiste.csv

Identifie les groupes d'artistes similaires et propose de les fusionner
en gardant une forme canonique et migrant les variantes vers artiste_alias.csv
"""

import csv
import re
import unicodedata
from pathlib import Path
from collections import defaultdict

CORPUS_DIR = Path(__file__).parent.parent / 'corpus'


def load_artistes():
    """Charge les artistes depuis artiste.csv"""
    artistes = []
    with open(CORPUS_DIR / 'artiste.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            artistes.append(row)
    return artistes


def load_existing_aliases():
    """Charge les alias existants"""
    aliases = set()
    alias_path = CORPUS_DIR / 'artiste_alias.csv'
    if alias_path.exists():
        with open(alias_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                aliases.add(row['variante'])
    return aliases


def normalize_for_grouping(name: str) -> str:
    """
    Normalisation aggressive pour regrouper les variantes.
    Supprime articles, accents, ponctuation, espaces.
    """
    s = name.lower().strip()

    # Supprimer accents
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))

    # Supprimer ponctuation
    s = re.sub(r"[''\"«»„"",./:;!?(){}—–-]", ' ', s)
    s = s.replace('[', ' ').replace(']', ' ')

    # Remplacer & par et
    s = s.replace('&', 'et')

    # Supprimer articles
    s = re.sub(r'\b(le|la|l|les|de|du|des|d|au|aux|a|the)\b', '', s)

    # Normaliser espaces
    s = ''.join(s.split())

    return s


def find_duplicate_groups(artistes):
    """
    Trouve les groupes d'artistes qui semblent être des doublons.
    Retourne un dict: clé_normalisée -> [artistes]
    """
    groups = defaultdict(list)

    for artiste in artistes:
        key = normalize_for_grouping(artiste['nom_canonique'])
        groups[key].append(artiste)

    # Ne garder que les groupes avec plus d'un artiste
    return {k: v for k, v in groups.items() if len(v) > 1}


def choose_canonical(group):
    """
    Choisit la forme canonique parmi un groupe de doublons.
    Critères:
    - Préférer les formes avec accents
    - Préférer les formes plus longues (plus explicites)
    - Préférer les formes avec majuscules correctes
    """
    def score(artiste):
        nom = artiste['nom_canonique']
        s = 0

        # Bonus pour accents (forme correcte)
        if any(c in nom for c in 'éèêëàâäùûüôöîïçÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ'):
            s += 10

        # Bonus pour longueur (plus explicite)
        s += len(nom) / 10

        # Bonus pour majuscule initiale (pas tout en majuscules)
        if nom[0].isupper() and not nom.isupper():
            s += 5

        # Malus pour tout en majuscules
        if nom.isupper():
            s -= 3

        # Malus pour parenthèses/crochets (souvent des notes)
        if '(' in nom or '[' in nom:
            s -= 2

        # Bonus si a un style renseigné
        if artiste.get('style'):
            s += 2

        return s

    return max(group, key=score)


def batch_review(groups):
    """
    Revue batch (non-interactive) des groupes.
    Affiche les changements proposés.
    """
    to_remove = []  # noms à retirer de artiste.csv
    to_alias = []   # (variante, canonique) à ajouter à artiste_alias.csv

    print(f"\n{'='*60}")
    print(f"ANALYSE DES DOUBLONS - {len(groups)} groupes trouvés")
    print(f"{'='*60}\n")

    for key, group in sorted(groups.items()):
        canonical = choose_canonical(group)
        others = [a for a in group if a != canonical]

        if others:
            print(f"\nGroupe: {canonical['nom_canonique']}")
            for other in others:
                print(f"  - {other['nom_canonique']} -> alias")
                to_remove.append(other['nom_canonique'])
                to_alias.append((other['nom_canonique'], canonical['nom_canonique']))

    print(f"\n{'='*60}")
    print(f"RÉSUMÉ:")
    print(f"  - {len(to_remove)} artistes à retirer de artiste.csv")
    print(f"  - {len(to_alias)} alias à ajouter à artiste_alias.csv")
    print(f"{'='*60}")

    return to_remove, to_alias


def apply_changes(to_remove, to_alias):
    """Applique les changements aux fichiers CSV."""

    # 1. Retirer les doublons de artiste.csv
    artistes = load_artistes()
    remove_set = set(to_remove)

    new_artistes = [a for a in artistes if a['nom_canonique'] not in remove_set]

    with open(CORPUS_DIR / 'artiste.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['nom_canonique', 'nom_normalise', 'style'])
        writer.writeheader()
        writer.writerows(new_artistes)

    print(f"+ Retiré {len(artistes) - len(new_artistes)} doublons de artiste.csv")

    # 2. Ajouter les alias
    existing_aliases = load_existing_aliases()
    new_aliases = [(v, c) for v, c in to_alias if v not in existing_aliases]

    if new_aliases:
        with open(CORPUS_DIR / 'artiste_alias.csv', 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for variante, canonique in new_aliases:
                writer.writerow([variante, canonique])

        print(f"+ Ajouté {len(new_aliases)} alias à artiste_alias.csv")


def export_report(groups, output_path=None):
    """Exporte un rapport CSV des doublons détectés."""
    if output_path is None:
        output_path = CORPUS_DIR / 'artiste_duplicates_report.csv'

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['groupe', 'nom', 'style', 'est_canonique', 'action'])

        for key, group in sorted(groups.items()):
            canonical = choose_canonical(group)
            for artiste in group:
                is_canon = artiste == canonical
                action = 'GARDER' if is_canon else 'MIGRER_ALIAS'
                writer.writerow([key, artiste['nom_canonique'], artiste.get('style', ''), is_canon, action])

    print(f"+ Rapport exporté: {output_path}")


def find_by_keyword(artistes, keyword):
    """Trouve les artistes contenant un mot-clé."""
    return [a for a in artistes if keyword.lower() in a['nom_canonique'].lower()]


def interactive_keyword_review(artistes, keyword):
    """
    Revue interactive par mot-clé.
    Permet de fusionner manuellement des artistes liés.
    """
    matches = find_by_keyword(artistes, keyword)

    if not matches:
        print(f"Aucun artiste contenant '{keyword}'")
        return [], []

    to_remove = []
    to_alias = []

    print(f"\n{'='*60}")
    print(f"ARTISTES CONTENANT '{keyword.upper()}' ({len(matches)} trouvés)")
    print(f"{'='*60}\n")

    for i, artiste in enumerate(sorted(matches, key=lambda x: x['nom_canonique']), 1):
        style = f" [{artiste['style']}]" if artiste.get('style') else ""
        print(f"  {i}. {artiste['nom_canonique']}{style}")

    print("\nCommandes:")
    print("  merge 1,2,3 -> 2   : Fusionne 1,2,3 vers l'artiste 2 (2 devient canonique)")
    print("  skip               : Passer au mot-clé suivant")
    print("  quit               : Quitter")

    while True:
        choice = input("\n> ").strip().lower()

        if choice == 'quit' or choice == 'q':
            break
        elif choice == 'skip' or choice == 's':
            break
        elif choice.startswith('merge '):
            try:
                # Parse: merge 1,2,3 -> 2
                parts = choice[6:].split('->')
                if len(parts) != 2:
                    print("Format: merge 1,2,3 -> 2")
                    continue

                indices = [int(x.strip()) for x in parts[0].split(',')]
                canon_idx = int(parts[1].strip())

                if canon_idx not in indices:
                    print(f"L'index canonique {canon_idx} doit être dans la liste")
                    continue

                sorted_matches = sorted(matches, key=lambda x: x['nom_canonique'])
                canonical = sorted_matches[canon_idx - 1]
                others = [sorted_matches[i - 1] for i in indices if i != canon_idx]

                print(f"\nFusion vers: {canonical['nom_canonique']}")
                for other in others:
                    print(f"  - {other['nom_canonique']} -> alias")
                    to_remove.append(other['nom_canonique'])
                    to_alias.append((other['nom_canonique'], canonical['nom_canonique']))

            except (ValueError, IndexError) as e:
                print(f"Erreur: {e}")
        else:
            print("Commande non reconnue")

    return to_remove, to_alias


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Déduplication des artistes')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Mode interactif (revue manuelle)')
    parser.add_argument('--apply', '-a', action='store_true',
                        help='Appliquer les changements (sinon dry-run)')
    parser.add_argument('--report', '-r', action='store_true',
                        help='Exporter un rapport CSV des doublons')
    parser.add_argument('--min-group', '-m', type=int, default=2,
                        help='Taille minimum de groupe (défaut: 2)')
    parser.add_argument('--keyword', '-k', type=str,
                        help='Mot-clé pour filtrer les artistes (mode manuel)')

    args = parser.parse_args()

    # Charger les artistes
    artistes = load_artistes()
    print(f"Chargé {len(artistes)} artistes depuis artiste.csv")

    # Mode mot-clé: revue manuelle par mot-clé
    if args.keyword:
        to_remove, to_alias = interactive_keyword_review(artistes, args.keyword)
        if args.apply and to_alias:
            print("\nApplication des changements...")
            apply_changes(to_remove, to_alias)
            print("Terminé!")
        elif to_alias:
            print("\n[dry-run] Utilisez --apply pour appliquer les changements")
        return

    # Trouver les doublons automatiques
    groups = find_duplicate_groups(artistes)
    groups = {k: v for k, v in groups.items() if len(v) >= args.min_group}

    if not groups:
        print("Aucun doublon détecté!")
        return

    # Exporter rapport si demandé
    if args.report:
        export_report(groups)

    # Revue
    to_remove, to_alias = batch_review(groups)

    # Appliquer si demandé
    if args.apply and to_alias:
        print("\nApplication des changements...")
        apply_changes(to_remove, to_alias)
        print("Terminé!")
    elif to_alias:
        print("\n[dry-run] Utilisez --apply pour appliquer les changements")


if __name__ == '__main__':
    main()

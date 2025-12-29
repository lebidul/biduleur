#!/usr/bin/env python3
"""
Outil de déduplication des lieux dans lieu.csv

Identifie les groupes de lieux similaires et propose de les fusionner
en gardant une forme canonique et migrant les variantes vers lieu_alias.csv
"""

import csv
import re
from pathlib import Path
from collections import defaultdict
from difflib import SequenceMatcher

CORPUS_DIR = Path(__file__).parent.parent / 'corpus'


def load_lieux():
    """Charge les lieux depuis lieu.csv"""
    lieux = []
    with open(CORPUS_DIR / 'lieu.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lieux.append(row)
    return lieux


def load_existing_aliases():
    """Charge les alias existants"""
    aliases = set()
    alias_path = CORPUS_DIR / 'lieu_alias.csv'
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
    import unicodedata

    s = name.lower().strip()

    # Supprimer accents
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))

    # Supprimer ponctuation
    s = re.sub(r"[''\"«»„"",./:;!?(){}—–-]", ' ', s)
    s = s.replace('[', ' ').replace(']', ' ')

    # Supprimer articles
    s = re.sub(r'\b(le|la|l|les|de|du|des|d|au|aux|a)\b', '', s)

    # Normaliser espaces
    s = ''.join(s.split())

    return s


def find_prefix_duplicates(lieux, min_prefix_len=6):
    """
    Trouve les lieux qui partagent un préfixe commun significatif.
    Utile pour détecter "Abbaye" vs "Abbaye Royale de l'Epau".
    """
    prefix_groups = defaultdict(list)

    for lieu in lieux:
        norm = normalize_for_grouping(lieu['nom'])
        if len(norm) >= min_prefix_len:
            prefix = norm[:min_prefix_len]
            prefix_groups[prefix].append(lieu)

    # Trouver les groupes avec des noms de longueurs très différentes
    potential_duplicates = []

    for prefix, group in prefix_groups.items():
        if len(group) < 2:
            continue

        # Trier par longueur de nom normalisé
        sorted_group = sorted(group, key=lambda x: len(normalize_for_grouping(x['nom'])))

        # Vérifier si le plus court est un préfixe du plus long
        shortest = normalize_for_grouping(sorted_group[0]['nom'])
        for other in sorted_group[1:]:
            other_norm = normalize_for_grouping(other['nom'])
            if other_norm.startswith(shortest) and len(other_norm) > len(shortest) + 3:
                potential_duplicates.append({
                    'short': sorted_group[0],
                    'long': other,
                    'prefix': shortest
                })

    return potential_duplicates


def find_duplicate_groups(lieux):
    """
    Trouve les groupes de lieux qui semblent être des doublons.
    Retourne un dict: clé_normalisée -> [lieux]
    """
    groups = defaultdict(list)

    for lieu in lieux:
        key = normalize_for_grouping(lieu['nom'])
        groups[key].append(lieu)

    # Ne garder que les groupes avec plus d'un lieu
    return {k: v for k, v in groups.items() if len(v) > 1}


def choose_canonical(group):
    """
    Choisit la forme canonique parmi un groupe de doublons.
    Critères:
    - Préférer les formes avec accents
    - Préférer les formes plus longues (plus explicites)
    - Préférer les formes avec majuscules correctes
    """
    def score(lieu):
        nom = lieu['nom']
        s = 0

        # Bonus pour accents (forme correcte)
        if any(c in nom for c in 'éèêëàâäùûüôöîïç'):
            s += 10

        # Bonus pour longueur (plus explicite)
        s += len(nom) / 10

        # Bonus pour majuscule initiale
        if nom[0].isupper():
            s += 5

        # Bonus pour "Abbaye Royale" vs "Abbaye" (préférer complet)
        if 'royale' in nom.lower() or 'royal' in nom.lower():
            s += 3

        # Malus pour parenthèses/crochets (souvent des notes)
        if '(' in nom or '[' in nom:
            s -= 2

        return s

    return max(group, key=score)


def interactive_review(groups):
    """
    Revue interactive des groupes de doublons.
    L'utilisateur peut valider, modifier ou ignorer chaque groupe.
    """
    to_keep = []  # (lieu canonique)
    to_alias = []  # (variante, canonique)

    print(f"\n{'='*60}")
    print(f"REVUE DES DOUBLONS - {len(groups)} groupes trouvés")
    print(f"{'='*60}\n")

    for i, (key, group) in enumerate(sorted(groups.items()), 1):
        canonical = choose_canonical(group)
        others = [l for l in group if l != canonical]

        print(f"\n[{i}/{len(groups)}] Groupe '{key}':")
        print(f"  Canonique suggéré: {canonical['nom']}")
        print(f"  Variantes à migrer vers alias:")
        for j, other in enumerate(others, 1):
            print(f"    {j}. {other['nom']}")

        print("\nActions: [Enter]=Valider, [s]=Skip, [c]=Changer canonique, [q]=Quitter")
        choice = input("> ").strip().lower()

        if choice == 'q':
            break
        elif choice == 's':
            # Garder tous comme lieux séparés
            continue
        elif choice == 'c':
            # Changer le canonique
            print("Numéro du nouveau canonique (1=premier de la liste):")
            for j, l in enumerate(group, 1):
                marker = " <- actuel" if l == canonical else ""
                print(f"  {j}. {l['nom']}{marker}")
            try:
                num = int(input("> ")) - 1
                if 0 <= num < len(group):
                    canonical = group[num]
                    others = [l for l in group if l != canonical]
            except ValueError:
                pass

        # Valider: garder canonique, migrer les autres en alias
        to_keep.append(canonical)
        for other in others:
            to_alias.append((other['nom'], canonical['nom']))

    return to_keep, to_alias


def batch_review(groups, auto_approve=False):
    """
    Revue batch (non-interactive) des groupes.
    Affiche les changements proposés.
    """
    to_remove = []  # noms à retirer de lieu.csv
    to_alias = []   # (variante, canonique) à ajouter à lieu_alias.csv

    print(f"\n{'='*60}")
    print(f"ANALYSE DES DOUBLONS - {len(groups)} groupes trouvés")
    print(f"{'='*60}\n")

    for key, group in sorted(groups.items()):
        canonical = choose_canonical(group)
        others = [l for l in group if l != canonical]

        if others:
            print(f"\nGroupe: {canonical['nom']}")
            for other in others:
                print(f"  - {other['nom']} -> alias")
                to_remove.append(other['nom'])
                to_alias.append((other['nom'], canonical['nom']))

    print(f"\n{'='*60}")
    print(f"RÉSUMÉ:")
    print(f"  - {len(to_remove)} lieux à retirer de lieu.csv")
    print(f"  - {len(to_alias)} alias à ajouter à lieu_alias.csv")
    print(f"{'='*60}")

    return to_remove, to_alias


def apply_changes(to_remove, to_alias):
    """Applique les changements aux fichiers CSV."""

    # 1. Retirer les doublons de lieu.csv
    lieux = load_lieux()
    remove_set = set(to_remove)

    new_lieux = [l for l in lieux if l['nom'] not in remove_set]

    with open(CORPUS_DIR / 'lieu.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['nom', 'ville', 'nom_normalise'])
        writer.writeheader()
        writer.writerows(new_lieux)

    print(f"+ Retiré {len(lieux) - len(new_lieux)} doublons de lieu.csv")

    # 2. Ajouter les alias
    existing_aliases = load_existing_aliases()
    new_aliases = [(v, c) for v, c in to_alias if v not in existing_aliases]

    if new_aliases:
        with open(CORPUS_DIR / 'lieu_alias.csv', 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for variante, canonique in new_aliases:
                writer.writerow([variante, canonique])

        print(f"+ Ajouté {len(new_aliases)} alias à lieu_alias.csv")


def export_report(groups, output_path=None):
    """Exporte un rapport CSV des doublons détectés."""
    if output_path is None:
        output_path = CORPUS_DIR / 'lieu_duplicates_report.csv'

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['groupe', 'nom', 'ville', 'est_canonique', 'action'])

        for key, group in sorted(groups.items()):
            canonical = choose_canonical(group)
            for lieu in group:
                is_canon = lieu == canonical
                action = 'GARDER' if is_canon else 'MIGRER_ALIAS'
                writer.writerow([key, lieu['nom'], lieu['ville'], is_canon, action])

    print(f"+ Rapport exporté: {output_path}")


def find_by_keyword(lieux, keyword):
    """Trouve les lieux contenant un mot-clé."""
    return [l for l in lieux if keyword.lower() in l['nom'].lower()]


def interactive_keyword_review(lieux, keyword):
    """
    Revue interactive par mot-clé.
    Permet de fusionner manuellement des lieux liés.
    """
    matches = find_by_keyword(lieux, keyword)

    if not matches:
        print(f"Aucun lieu contenant '{keyword}'")
        return [], []

    to_remove = []
    to_alias = []

    print(f"\n{'='*60}")
    print(f"LIEUX CONTENANT '{keyword.upper()}' ({len(matches)} trouvés)")
    print(f"{'='*60}\n")

    for i, lieu in enumerate(sorted(matches, key=lambda x: x['nom']), 1):
        print(f"  {i}. {lieu['nom']}")

    print("\nCommandes:")
    print("  merge 1,2,3 -> 2   : Fusionne 1,2,3 vers le lieu 2 (2 devient canonique)")
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

                sorted_matches = sorted(matches, key=lambda x: x['nom'])
                canonical = sorted_matches[canon_idx - 1]
                others = [sorted_matches[i - 1] for i in indices if i != canon_idx]

                print(f"\nFusion vers: {canonical['nom']}")
                for other in others:
                    print(f"  - {other['nom']} -> alias")
                    to_remove.append(other['nom'])
                    to_alias.append((other['nom'], canonical['nom']))

            except (ValueError, IndexError) as e:
                print(f"Erreur: {e}")
        else:
            print("Commande non reconnue")

    return to_remove, to_alias


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Déduplication des lieux')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Mode interactif (revue manuelle)')
    parser.add_argument('--apply', '-a', action='store_true',
                        help='Appliquer les changements (sinon dry-run)')
    parser.add_argument('--report', '-r', action='store_true',
                        help='Exporter un rapport CSV des doublons')
    parser.add_argument('--min-group', '-m', type=int, default=2,
                        help='Taille minimum de groupe (défaut: 2)')
    parser.add_argument('--keyword', '-k', type=str,
                        help='Mot-clé pour filtrer les lieux (mode manuel)')

    args = parser.parse_args()

    # Charger les lieux
    lieux = load_lieux()
    print(f"Chargé {len(lieux)} lieux depuis lieu.csv")

    # Mode mot-clé: revue manuelle par mot-clé
    if args.keyword:
        to_remove, to_alias = interactive_keyword_review(lieux, args.keyword)
        if args.apply and to_alias:
            print("\nApplication des changements...")
            apply_changes(to_remove, to_alias)
            print("Terminé!")
        elif to_alias:
            print("\n[dry-run] Utilisez --apply pour appliquer les changements")
        return

    # Trouver les doublons automatiques
    groups = find_duplicate_groups(lieux)
    groups = {k: v for k, v in groups.items() if len(v) >= args.min_group}

    if not groups:
        print("Aucun doublon détecté!")
        return

    # Exporter rapport si demandé
    if args.report:
        export_report(groups)

    # Revue
    if args.interactive:
        to_keep, to_alias = interactive_review(groups)
        to_remove = [a[0] for a in to_alias]
    else:
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

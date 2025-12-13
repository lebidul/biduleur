#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du remplacement de "Théâtre" → "Th."
Usage: python test_theatre_replacement.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from misenpageur.abbreviations import Abbreviation, apply_abbreviations_to_paragraphs


def test_theatre_replacement():
    """Teste le remplacement du mot 'Théâtre' dans différents contextes."""

    print("=" * 60)
    print("TEST DE REMPLACEMENT : Théâtre → Th.")
    print("=" * 60)

    # Créer l'abréviation
    abbrev = Abbreviation(
        key="theatre",
        original="théâtre",
        replacement="th.",
        description="Théâtre → Th.",
        enabled=True
    )

    # Paragraphes de test
    test_paragraphs = [
        '<p>Théâtre Municipal, 20h</p>',
        '<p>THÉÂTRE DES BASSES OEUVRES</p>',
        '<p>Le théâtre de l\'Écluse</p>',
        '<p>Théâtre de la Halle-au-Grain</p>',
        '<p>Au théâtre ce soir</p>',
        '<p>Le Théâtre National</p>',
    ]

    print("\n1. Paragraphes originaux:")
    for i, para in enumerate(test_paragraphs, 1):
        print(f"   {i}. {para}")

    # Appliquer les abréviations
    print("\n2. Application de l'abréviation...")
    result, stats = apply_abbreviations_to_paragraphs(test_paragraphs, [abbrev])

    print("\n3. Résultats:")
    for i, (original, modified) in enumerate(zip(test_paragraphs, result), 1):
        changed = "✓" if original != modified else "✗"
        print(f"   {changed} {i}. {modified}")

    print(f"\n4. Statistiques:")
    print(f"   Total remplacements: {stats.get('theatre', 0)}")

    # Vérification
    expected_count = 6  # On attend 6 remplacements
    actual_count = stats.get('theatre', 0)

    print("\n" + "=" * 60)
    if actual_count == expected_count:
        print(f"✓ TEST RÉUSSI ({actual_count}/{expected_count} remplacements)")
    else:
        print(f"✗ TEST ÉCHOUÉ ({actual_count}/{expected_count} remplacements)")
    print("=" * 60)

    return actual_count == expected_count


if __name__ == '__main__':
    success = test_theatre_replacement()
    sys.exit(0 if success else 1)
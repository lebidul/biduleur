#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de normalisation Unicode pour les abréviations.
Usage: python test_unicode_normalization.py
"""

import unicodedata


def test_unicode_normalization():
    """Teste la normalisation Unicode des caractères accentués."""

    print("=" * 60)
    print("TEST DE NORMALISATION UNICODE")
    print("=" * 60)

    # Exemple 1 : "théâtre" peut être encodé de 2 façons
    text_nfc = "théâtre"  # Forme composée (1 caractère pour â)
    text_nfd = "the\u0302a\u0302tre"  # Forme décomposée (a + accent)

    print("\n1. Comparaison avant normalisation:")
    print(f"   NFC: '{text_nfc}' (len={len(text_nfc)})")
    print(f"   NFD: '{text_nfd}' (len={len(text_nfd)})")
    print(f"   Égalité stricte: {text_nfc == text_nfd}")

    # Normaliser les deux en NFC
    normalized_nfc = unicodedata.normalize('NFC', text_nfc)
    normalized_nfd = unicodedata.normalize('NFC', text_nfd)

    print("\n2. Comparaison après normalisation NFC:")
    print(f"   NFC normalisé: '{normalized_nfc}' (len={len(normalized_nfc)})")
    print(f"   NFD normalisé: '{normalized_nfd}' (len={len(normalized_nfd)})")
    print(f"   Égalité stricte: {normalized_nfc == normalized_nfd}")

    # Test avec différents cas
    test_cases = [
        ("Théâtre", "théâtre"),  # Majuscule vs minuscule
        ("THÉÂTRE", "théâtre"),  # Tout majuscule vs minuscule
        ("Théâtre", "Theatre"),  # Avec vs sans accent
    ]

    print("\n3. Tests de correspondance (case-insensitive):")
    for text1, text2 in test_cases:
        norm1 = unicodedata.normalize('NFC', text1).lower()
        norm2 = unicodedata.normalize('NFC', text2).lower()
        match = norm1 == norm2
        status = "✓" if match else "✗"
        print(f"   {status} '{text1}' vs '{text2}': {match}")

    # Test avec regex
    import re

    print("\n4. Test avec regex IGNORECASE:")
    pattern = re.compile(r'\bthéâtre\b', re.IGNORECASE)

    test_texts = [
        "Théâtre Municipal",
        "THÉÂTRE MUNICIPAL",
        "Le théâtre est ouvert",
        "Theatre Municipal",  # Sans accent
    ]

    for text in test_texts:
        normalized = unicodedata.normalize('NFC', text)
        matches = pattern.findall(normalized)
        status = "✓" if matches else "✗"
        print(f"   {status} '{text}': {len(matches)} match(es)")

    print("\n" + "=" * 60)
    print("✓ TEST TERMINÉ")
    print("=" * 60)


if __name__ == '__main__':
    test_unicode_normalization()
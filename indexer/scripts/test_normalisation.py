#!/usr/bin/env python3
"""
Script de test de normalisation.

Teste les cas de normalisation automatique (sans alias CSV)
pour les lieux, artistes, villes et styles.
"""

import sys
from pathlib import Path

# Ajouter le parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.normalizer import (
    normalize_for_matching,
    get_lieu_normalizer,
    get_ville_normalizer,
    get_artiste_normalizer,
    get_style_normalizer,
    strip_prefixes,
    expand_abbreviations,
    remove_accents,
    normalize_separators,
)


def test_normalize_for_matching():
    """Test de la fonction principale de normalisation."""
    print("\n" + "=" * 60)
    print("TEST normalize_for_matching()")
    print("=" * 60)

    tests = [
        # Case insensitive
        ("AZURYTE", "azuryte"),
        ("azuryte", "azuryte"),
        ("Azuryte", "azuryte"),
        # Accents
        ("Chemire-le-Gaudin", "chemire le gaudin"),
        ("La Fleche", "la fleche"),
        ("L'Ecluse", "l ecluse"),
        # Separateurs (tirets = espaces)
        ("Saint-Mars-la-Briere", "saint mars la briere"),
        ("Auvers le-Hamon", "auvers le hamon"),
        # Apostrophes
        ("L'Oasis", "l oasis"),
        ("D'Artagnan", "d artagnan"),
        # Abreviations
        ("Th. Paul Scarron", "theatre paul scarron"),
        ("th paul scarron", "theatre paul scarron"),
        ("St Pavace", "saint pavace"),
        ("St. Pavace", "saint pavace"),
        ("St-Pavace", "saint pavace"),
        ("Ste Jamme", "sainte jamme"),
        ("Ste-Jamme-sur-Sarthe", "sainte jamme sur sarthe"),
        ("Monce s/Loir", "monce sur loir"),
        ("Esp. Culturel", "espace culturel"),
        ("MJC Prevert", "mjc prevert"),
        # Combinaisons
        ("TH. PAUL SCARRON", "theatre paul scarron"),
        ("La Fleche", "la fleche"),
        ("DJ SUPER LUCIEN", "dj super lucien"),
    ]

    passed = 0
    failed = 0

    for input_str, expected in tests:
        result = normalize_for_matching(input_str)
        ok = result == expected
        status = "OK" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"  [{status}] {input_str!r}")
            print(f"           got:      {result!r}")
            print(f"           expected: {expected!r}")

    if failed == 0:
        print(f"  Tous les {passed} tests passes!")
    else:
        print(f"\n  Passes: {passed}, Echecs: {failed}")

    return failed == 0


def test_lieu_normalizer():
    """Test du LieuNormalizer."""
    print("\n" + "=" * 60)
    print("TEST LieuNormalizer")
    print("=" * 60)

    ln = get_lieu_normalizer()
    print(f"  Lieux charges: {len(ln.lieux)}")
    print(f"  Aliases charges: {len(ln.aliases)}")

    # Tests: (input, expected_nom or None)
    # Note: expected_nom doit correspondre au nom canonique dans le CSV
    tests = [
        # Case insensitive
        ("Le Barouf", "Le Barouf"),
        ("le barouf", "Le Barouf"),
        ("LE BAROUF", "Le Barouf"),
        # Sans prefixes
        ("Barouf", "Le Barouf"),
        ("BAROUF", "Le Barouf"),
        # Accents - le CSV a "Théâtre Paul Scarron" avec accents
        ("Théâtre Paul Scarron", "Théâtre Paul Scarron"),
        ("Theatre Paul Scarron", "Théâtre Paul Scarron"),
        # Abreviations
        ("Th. Paul Scarron", "Théâtre Paul Scarron"),
        ("th paul scarron", "Théâtre Paul Scarron"),
        ("TH PAUL SCARRON", "Théâtre Paul Scarron"),
        # Avec separateurs
        ("L'Oasis", "L'Oasis"),
        ("l oasis", "L'Oasis"),
    ]

    passed = 0
    failed = 0

    for input_str, expected_nom in tests:
        result = ln.find_lieu(input_str)
        if expected_nom is None:
            # On s'attend a ne pas trouver
            ok = result is None
        else:
            ok = result is not None and result[0] == expected_nom

        status = "OK" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
            result_str = f"{result[0]}" if result else "None"
            print(f"  [{status}] {input_str!r} -> {result_str} (attendu: {expected_nom})")

    if failed == 0:
        print(f"  Tous les {passed} tests passes!")
    else:
        print(f"\n  Passes: {passed}, Echecs: {failed}")

    return failed == 0


def test_ville_normalizer():
    """Test du VilleNormalizer."""
    print("\n" + "=" * 60)
    print("TEST VilleNormalizer")
    print("=" * 60)

    vn = get_ville_normalizer()
    print(f"  Villes chargees: {len(vn.villes)}")

    # Tests: (input, should_be_found)
    # On verifie juste que la normalisation trouve la ville
    tests = [
        ("Le Mans", True),
        ("le mans", True),
        ("LE MANS", True),
        ("La Fleche", True),  # Sans accent -> doit matcher "La Flèche"
        ("la fleche", True),
        ("La Flèche", True),
        # Avec tirets/accents
        ("Saint-Pavace", True),
        ("saint pavace", True),
        # Vide -> Le Mans par defaut (found=False car pas de match explicite)
        ("", False),
    ]

    passed = 0
    failed = 0

    for input_str, expected_found in tests:
        result_nom, found = vn.find_ville(input_str or "")
        ok = found == expected_found

        status = "OK" if ok else "FAIL"
        if ok:
            passed += 1
            if found:
                print(f"  [OK] {input_str!r} -> {result_nom}")
        else:
            failed += 1
            print(f"  [{status}] {input_str!r}")
            print(f"           got:      ({result_nom!r}, found={found})")
            print(f"           expected: found={expected_found}")

    if failed == 0:
        print(f"  Tous les {passed} tests passes!")
    else:
        print(f"\n  Passes: {passed}, Echecs: {failed}")

    return failed == 0


def test_style_normalizer():
    """Test du StyleNormalizer."""
    print("\n" + "=" * 60)
    print("TEST StyleNormalizer")
    print("=" * 60)

    sn = get_style_normalizer()

    # Tests: (input, expected)
    # Note: les styles canoniques gardent les accents (théâtre, électro, etc.)
    # Apres nettoyage des alias redondants, seuls les cas speciaux sont mappes
    tests = [
        ("th.", "théâtre"),
        ("Th.", "théâtre"),
        ("TH", "théâtre"),
        ("th", "théâtre"),
        ("chanson fr.", "chanson française"),
        ("chanson", "chanson française"),
        ("CHANSON", "chanson française"),
        ("musique du monde", "world music"),
        ("slam", "slam poésie"),
        ("électronique", "électro"),
        ("rnb", "R&B"),
        ("variété", "variété française"),
    ]

    passed = 0
    failed = 0

    for input_str, expected in tests:
        result = sn.normalize(input_str)
        ok = result == expected

        status = "OK" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"  [{status}] {input_str!r} -> {result!r} (attendu: {expected!r})")

    if failed == 0:
        print(f"  Tous les {passed} tests passes!")
    else:
        print(f"\n  Passes: {passed}, Echecs: {failed}")

    return failed == 0


def test_db_matching():
    """Test du matching avec la base de donnees."""
    print("\n" + "=" * 60)
    print("TEST Matching avec DB")
    print("=" * 60)

    from core.normalizer import find_lieu_ref_id, find_artiste_ref_id

    # Test quelques lieux
    lieu_tests = [
        "Le Barouf",
        "le barouf",
        "BAROUF",
        "Th. Paul Scarron",
        "th paul scarron",
    ]

    print("\n  Lieux:")
    for lieu in lieu_tests:
        lieu_id, nom = find_lieu_ref_id(lieu)
        if lieu_id:
            print(f"    {lieu!r} -> ID={lieu_id}, nom={nom}")
        else:
            print(f"    {lieu!r} -> non trouve")

    # Test quelques artistes connus
    artiste_tests = [
        "Les Ogres de Barback",
        "LES OGRES DE BARBACK",
        "ogres de barback",
    ]

    print("\n  Artistes:")
    for artiste in artiste_tests:
        artiste_id, nom = find_artiste_ref_id(artiste)
        if artiste_id:
            print(f"    {artiste!r} -> ID={artiste_id}, nom={nom}")
        else:
            print(f"    {artiste!r} -> non trouve")


def main():
    """Execute tous les tests."""
    print("=" * 60)
    print("TESTS DE NORMALISATION")
    print("=" * 60)

    all_passed = True

    # Tests unitaires
    all_passed = test_normalize_for_matching() and all_passed
    all_passed = test_lieu_normalizer() and all_passed
    all_passed = test_ville_normalizer() and all_passed
    all_passed = test_style_normalizer() and all_passed

    # Tests avec DB
    try:
        test_db_matching()
    except Exception as e:
        print(f"\n  Erreur DB: {e}")

    print("\n" + "=" * 60)
    if all_passed:
        print("TOUS LES TESTS PASSES!")
    else:
        print("CERTAINS TESTS ONT ECHOUE")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

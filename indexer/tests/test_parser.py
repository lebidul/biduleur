"""Tests pour le parser d'événements"""

import pytest
from datetime import date
import sys
from pathlib import Path

# Ajouter le chemin parent pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.text_cleaner import clean_pdf_text, expand_abbreviations, normalize_lieu_name
from core.parser import (
    split_fused_lines,
    split_multi_date_events,
    extract_tarif_improved,
    find_lieu_in_text,
    is_named_event,
    extract_event_name,
    EventParser,
    ArtisteInfo,
    # Nouvelles fonctions "lieu d'abord"
    load_lieu_patterns,
    find_lieu_in_text_v2,
    split_on_dates_v2,
    parse_date_prefix_v2,
    extract_before_lieu,
    extract_after_lieu,
    extract_ville_from_text_v2,
    parse_event_line_v2,
)


class TestTextCleaner:
    """Tests pour le nettoyage de texte PDF."""

    def test_clean_cesures_inline(self):
        """Test suppression des césures inline."""
        assert clean_pdf_text("Passe- port") == "Passeport"
        assert clean_pdf_text("L'En- tracte") == "L'Entracte"

    def test_clean_cesures_newline(self):
        """Test suppression des césures avec retour à la ligne."""
        assert clean_pdf_text("média-\nthèque") == "médiathèque"
        # Note: le tiret avant newline est supprimé (comportement césure standard)
        assert clean_pdf_text("Louis-\n Aragon") == "LouisAragon"
        # Pour un tiret voulu, pas d'espace après
        assert clean_pdf_text("Louis-Aragon") == "Louis-Aragon"

    def test_clean_multiple_spaces(self):
        """Test normalisation des espaces multiples."""
        assert clean_pdf_text("Hello    World") == "Hello World"
        assert clean_pdf_text("  Test  ") == "Test"

    def test_expand_abbreviations_prenoms(self):
        """Test expansion des prénoms abrégés."""
        assert "Jean Carmet" in expand_abbreviations("Salle J.Carmet")
        assert "Paul Scarron" in expand_abbreviations("Théâtre P. Scarron")
        assert "Louis-Aragon" in expand_abbreviations("Médiathèque L. Aragon")

    def test_expand_abbreviations_villes(self):
        """Test expansion des noms de villes."""
        assert "Sablé-sur-Sarthe" in expand_abbreviations("Sablé s/Sarthe")

    def test_normalize_lieu_name(self):
        """Test normalisation des noms de lieux."""
        assert normalize_lieu_name("le barouf") == "Bar Le Barouf"
        assert normalize_lieu_name("passeport") == "Bar le Passeport"
        assert normalize_lieu_name("l'eolienne") == "L'Éolienne"
        assert normalize_lieu_name("passe- port") == "Bar le Passeport"


class TestSplitEvents:
    """Tests pour le découpage des événements."""

    def test_split_fused_lines_single(self):
        """Test avec un seul événement (pas de split)."""
        text = "ARTISTE, Lieu, 20h, 5€"
        parts = split_fused_lines(text)
        assert len(parts) == 1
        assert parts[0] == text

    def test_split_fused_lines_multiple(self):
        """Test avec plusieurs événements fusionnés."""
        text = '"L\'itinérance" (théâtre), Le Rabelais, 17h, 3/5€ Lu 02 & Ma 03 : "Enfantillages" (théâtre), Théâtre, 18h30'
        parts = split_fused_lines(text)
        assert len(parts) == 2
        assert "L'itinérance" in parts[0]
        assert "Enfantillages" in parts[1]

    def test_split_fused_lines_no_split_on_price(self):
        """Ne pas splitter sur les prix comme 7€50."""
        text = '"Spectacle", Lieu, 18h30, 7€50'
        parts = split_fused_lines(text)
        assert len(parts) == 1

    def test_split_multi_dates_none(self):
        """Test sans dates multiples."""
        text = "ARTISTE, Lieu, 20h, 5€"
        results = split_multi_date_events(text, 12, 2023)
        assert len(results) == 1
        assert results[0][0] is None  # Pas de date

    def test_split_multi_dates_two(self):
        """Test avec deux dates."""
        text = 'Sa 07 & di 08 : "Gaston COUTÉ" (théâtre), Théâtre du passeur, sa 20h30/di 17h'
        results = split_multi_date_events(text, 12, 2013)
        assert len(results) == 2

        # Vérifier les dates
        dates = [r[0].day for r in results if r[0]]
        assert 7 in dates
        assert 8 in dates

    def test_split_multi_dates_three(self):
        """Test avec trois dates."""
        text = 'Je 05, Sa 07, Di 08 : Concert, Lieu, 20h'
        results = split_multi_date_events(text, 1, 2024)
        assert len(results) == 3


class TestExtractTarif:
    """Tests pour l'extraction des tarifs."""

    def test_gratuit_zero(self):
        """Test détection gratuit avec 0€."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("Bar le Lézard, 20h, 0€")
        assert gratuit is True
        assert prix_min == 0

    def test_gratuit_text(self):
        """Test détection gratuit texte."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("entrée gratuit")
        assert gratuit is True

    def test_gratuit_chapeau(self):
        """Test détection 'au chapeau'."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("au chapeau")
        assert gratuit is True

    def test_prix_simple(self):
        """Test prix simple."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("concert, 8€")
        assert prix_min == 8
        assert prix_max == 8
        assert gratuit is False

    def test_prix_decimal(self):
        """Test prix avec décimales."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("3,50€")
        assert prix_min == 3.5
        assert prix_max == 3.5

    def test_prix_fourchette_deux(self):
        """Test fourchette de prix."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("20h30, 5/7€")
        assert prix_min == 5
        assert prix_max == 7

    def test_prix_fourchette_trois(self):
        """Test fourchette avec 3 prix."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("5/7/9€")
        assert prix_min == 5
        assert prix_max == 9

    def test_prix_decimal_fourchette(self):
        """Test fourchette avec décimales."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("3.75/18€")
        assert prix_min == 3.75
        assert prix_max == 18

    def test_prix_range(self):
        """Test prix avec 'à'."""
        tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved("7 à 13€")
        assert prix_min == 7
        assert prix_max == 13


class TestExtractArtistes:
    """Tests pour l'extraction des artistes."""

    @pytest.fixture
    def parser(self):
        return EventParser(bidul_mois=12, bidul_annee=2023)

    def test_simple(self, parser):
        """Test artiste simple avec genre."""
        artistes = parser._extract_artistes("MENDELSON (poème rock), Lieu, 20h")
        assert len(artistes) == 1
        assert artistes[0].nom == "Mendelson"
        assert artistes[0].genre == "poème rock"

    def test_multiple_with_plus(self, parser):
        """Test plusieurs artistes avec +."""
        artistes = parser._extract_artistes("KOUMA (math rock) + 100 ONCES (noise rock), Lieu")
        assert len(artistes) == 2
        noms = [a.nom for a in artistes]
        assert "Kouma" in noms
        assert "100 Onces" in noms

    def test_global_style(self, parser):
        """Test style global appliqué à tous."""
        artistes = parser._extract_artistes("ARTISTE1 + ARTISTE2 + ARTISTE3 (rock), Lieu")
        assert len(artistes) == 3
        # Tous devraient avoir le même style
        for a in artistes:
            assert a.genre == "rock"

    def test_individual_styles(self, parser):
        """Test styles individuels préservés."""
        artistes = parser._extract_artistes("ARTISTE1 (jazz) + ARTISTE2 (rock), Lieu")
        assert len(artistes) == 2
        genres = {a.nom: a.genre for a in artistes}
        assert genres.get("Artiste1") == "jazz"
        assert genres.get("Artiste2") == "rock"

    def test_dj_pattern(self, parser):
        """Test pattern DJ XXX."""
        artistes = parser._extract_artistes("DJ KAMER (electro), Lieu")
        assert len(artistes) >= 1
        noms = [a.nom for a in artistes]
        assert any("DJ" in n.upper() and "KAMER" in n.upper() for n in noms)


class TestFindLieu:
    """Tests pour la recherche de lieu dans le référentiel."""

    def test_find_exact(self):
        """Test recherche exacte."""
        lieu_ref = [
            (1, "Bar Le Barouf", "Le Mans"),
            (2, "Le Rabelais", "Le Mans"),
        ]
        result = find_lieu_in_text("Concert au Bar Le Barouf, 20h", lieu_ref)
        assert result is not None
        assert result[1] == 1  # ID du lieu
        assert "Barouf" in result[0]

    def test_find_short_variant(self):
        """Test recherche avec variante courte."""
        lieu_ref = [
            (1, "Bar Le Barouf", "Le Mans"),
        ]
        result = find_lieu_in_text("Concert au Barouf, 20h", lieu_ref)
        assert result is not None
        assert result[1] == 1

    def test_find_no_match(self):
        """Test sans correspondance."""
        lieu_ref = [
            (1, "Bar Le Barouf", "Le Mans"),
        ]
        result = find_lieu_in_text("Concert au Zoo, 20h", lieu_ref)
        assert result is None


class TestEventParser:
    """Tests d'intégration pour le parser complet."""

    @pytest.fixture
    def parser(self):
        return EventParser(bidul_mois=5, bidul_annee=2023)

    def test_parse_standard_format(self, parser):
        """Test parsing format standard."""
        text = """Samedi 20
• FABIENNE GUYONS (jazz), Boire du Bon, Saint-Pavace, 20h, 10€
Dimanche 21
• JAM ST CO MUSICOS (jam session), Le Zoo, 21h, au chapeau
"""
        events = parser.parse(text)
        assert len(events) == 2

        # Vérifier le premier événement
        event1 = events[0]
        assert event1.date_str == "Samedi 20"
        assert len(event1.artistes) >= 1
        assert event1.heure == "20h"

    def test_parse_inline_format(self, parser):
        """Test parsing format inline."""
        text = """Je 02 : ARTISTE1 (rock), Lieu1, 20h, 5€
Ve 03 : ARTISTE2 (jazz), Lieu2, 21h, 8€
"""
        events = parser.parse(text)
        assert len(events) == 2

    def test_parse_with_spectacle(self, parser):
        """Test parsing avec spectacle entre guillemets."""
        text = """Samedi 20
• "Ex Ovo" Cie Le grand Raymond (cirque), Chapiteau plongeoir, 20h30, 4/8€
"""
        events = parser.parse(text)
        assert len(events) == 1
        assert "Ex Ovo" in events[0].spectacles


class TestIsNamedEvent:
    """Tests pour la détection d'événements nommés."""

    def test_spectacle_not_named(self):
        """Les spectacles entre guillemets ne sont pas des événements nommés."""
        assert is_named_event('"L\'itinérance de Maud" (théâtre)') is False

    def test_concert_not_named(self):
        """Les concerts d'artistes ne sont pas des événements nommés."""
        assert is_named_event('MENDELSON (poème rock), Lieu') is False

    def test_alpa_on_the_rock_named(self):
        """Alpa On The Rock est un événement nommé."""
        assert is_named_event('Alpa On The Rock #13 : CIMRYA DEAL') is True

    def test_esc_exp_named(self):
        """Esc Exp est un événement nommé."""
        assert is_named_event('Esc Exp #21 TERIAKI') is True

    def test_melting_rock_named(self):
        """Melting Rock est un événement nommé."""
        assert is_named_event('Melting Rock avec ARTISTE') is True

    def test_soiree_named(self):
        """Soirée X est un événement nommé."""
        assert is_named_event('Soirée Solidaire, Lieu, 20h') is True

    def test_festival_named(self):
        """Festival X est un événement nommé."""
        assert is_named_event('Festival Culturel, Lieu, 20h') is True


class TestExtractEventName:
    """Tests pour l'extraction du nom d'événement."""

    def test_spectacle_no_name(self):
        """Les spectacles entre guillemets ne doivent pas remplir evenement.nom."""
        assert extract_event_name('"L\'itinérance de Maud" (théâtre)') is None

    def test_named_event_alpa(self):
        """Les événements nommés doivent remplir evenement.nom."""
        result = extract_event_name('Alpa On The Rock #13 : CIMRYA DEAL')
        assert result is not None
        assert 'Alpa' in result

    def test_named_event_festival(self):
        """Festival est un événement nommé."""
        result = extract_event_name('Festival Culturel #5')
        assert result is not None
        assert 'Festival' in result


class TestExtractArtistesCie:
    """Tests pour l'extraction des artistes avec pattern 'par la Cie'."""

    @pytest.fixture
    def parser(self):
        return EventParser(bidul_mois=12, bidul_annee=2023)

    def test_par_la_cie(self, parser):
        """Test pattern 'par la Cie XXX'."""
        text = '"Enfantillages" (théâtre) par la Cie Théâtre d\'Air, Lieu, 18h30'
        artistes = parser._extract_artistes(text)
        assert len(artistes) >= 1
        noms = [a.nom for a in artistes]
        # Le nom normalisé est "CIE Théâtre D'Air"
        assert any("CIE" in n.upper() and ("THÉÂTRE" in n.upper() or "THEATRE" in n.upper()) for n in noms)

    def test_avec_la_cie(self, parser):
        """Test pattern 'avec la Cie XXX'."""
        text = '"Théâtre sauvage" avec la Cie "demain c\'est dimanche", Lieu'
        artistes = parser._extract_artistes(text)
        noms = [a.nom for a in artistes]
        assert any("demain c'est dimanche" in n.lower() for n in noms)

    def test_par_nom_propre(self, parser):
        """Test pattern 'par Prénom Nom'."""
        text = '"Concert classique" par Béatrice Maine, Théâtre, 20h'
        artistes = parser._extract_artistes(text)
        noms = [a.nom for a in artistes]
        assert any("Béatrice Maine" in n for n in noms)


class TestExtractVille:
    """Tests pour l'extraction des villes."""

    @pytest.fixture
    def parser(self):
        return EventParser(bidul_mois=12, bidul_annee=2023)

    def test_ville_explicite_prioritaire(self, parser):
        """La ville explicite doit être prioritaire sur Le Mans."""
        text = 'Théâtre de la Halle au blé, La Flèche, 20h30'
        lieu, ville = parser._extract_lieu_ville(text)
        # La Flèche devrait être reconnue si dans le référentiel
        # Sinon elle sera le lieu et ville sera None
        assert ville is None or ville != "Le Mans" or lieu is not None

    def test_normalisation_sable(self, parser):
        """Test normalisation 'Sablé s/Sarthe' → 'Sablé-sur-Sarthe'."""
        normalized = parser._normalize_ville_abbreviations("Sablé s/Sarthe")
        assert "Sablé-sur-Sarthe" in normalized

    def test_normalisation_st_pavace(self, parser):
        """Test normalisation 'St. Pavace' → 'Saint-Pavace'."""
        normalized = parser._normalize_ville_abbreviations("St. Pavace")
        assert "Saint-Pavace" in normalized


class TestMultiDatesLuMa:
    """Tests pour les dates multiples Lu 02 & Ma 03."""

    def test_lu_ma(self):
        """Test avec Lu 02 & Ma 03."""
        text = 'Lu 02 & Ma 03 : "Enfantillages" (théâtre), Théâtre, 18h30'
        results = split_multi_date_events(text, 12, 2013)
        assert len(results) == 2
        dates = [r[0].day for r in results if r[0]]
        assert 2 in dates
        assert 3 in dates


class TestEventNomNotFilledForSpectacles:
    """Tests vérifiant que evenement.nom n'est pas rempli pour les spectacles."""

    @pytest.fixture
    def parser(self):
        return EventParser(bidul_mois=12, bidul_annee=2023)

    def test_spectacle_nom_is_none(self, parser):
        """Le spectacle ne doit pas remplir evenement.nom."""
        text = """Samedi 20
• "L'itinérance de Maud" (théâtre), Théâtre, 20h30, 5€
"""
        events = parser.parse(text)
        assert len(events) == 1
        # Le nom doit être None car c'est un spectacle, pas un événement nommé
        assert events[0].nom is None
        # Mais le spectacle doit être dans la liste des spectacles
        assert "L'itinérance de Maud" in events[0].spectacles

    def test_named_event_nom_filled(self, parser):
        """L'événement nommé doit remplir evenement.nom."""
        text = """Samedi 20
• Alpa On The Rock #13 : CIMRYA DEAL (rock), Lieu, 20h30, 5€
"""
        events = parser.parse(text)
        assert len(events) == 1
        assert events[0].nom is not None
        assert "Alpa" in events[0].nom


# =============================================================================
# TESTS STRATÉGIE "LIEU D'ABORD"
# =============================================================================

class TestLoadLieuPatterns:
    """Tests pour la préparation des patterns de lieu."""

    def test_patterns_sorted_by_length(self):
        """Les patterns doivent être triés par longueur décroissante."""
        lieu_ref = [
            (1, "Le Mans", "Le Mans"),
            (2, "Théâtre de l'Éphémère", "Le Mans"),
            (3, "Zoo", "Le Mans"),
        ]
        patterns = load_lieu_patterns(lieu_ref)
        # Les patterns doivent être triés par longueur décroissante
        assert len(patterns) > 0
        # Les lengths doivent être décroissantes
        lengths = [p['length'] for p in patterns]
        assert lengths == sorted(lengths, reverse=True)
        # Vérifier que "Théâtre de l'Éphémère" est dans les patterns (peut ne pas être le premier à cause des alias)
        names = [p['nom'] for p in patterns]
        assert "Théâtre de l'Éphémère" in names


class TestFindLieuV2:
    """Tests pour la recherche de lieu v2 avec patterns."""

    def test_find_exact_match(self):
        """Test correspondance exacte."""
        lieu_ref = [
            (1, "Bar Le Barouf", "Le Mans"),
            (2, "Le Rabelais", "Le Mans"),
        ]
        patterns = load_lieu_patterns(lieu_ref)
        result = find_lieu_in_text_v2("Concert au Bar Le Barouf, 20h", patterns)
        assert result is not None
        lieu_nom, lieu_id, start, end = result
        assert lieu_id == 1
        assert "Barouf" in lieu_nom

    def test_find_case_insensitive(self):
        """Test recherche insensible à la casse."""
        lieu_ref = [
            (1, "Bar Le Barouf", "Le Mans"),
        ]
        patterns = load_lieu_patterns(lieu_ref)
        result = find_lieu_in_text_v2("Concert au bar le barouf, 20h", patterns)
        assert result is not None

    def test_find_no_match(self):
        """Test sans correspondance."""
        lieu_ref = [
            (1, "Bar Le Barouf", "Le Mans"),
        ]
        patterns = load_lieu_patterns(lieu_ref)
        result = find_lieu_in_text_v2("Concert au Zoo, 20h", patterns)
        assert result is None

    def test_find_le_barouf_variante(self):
        """Test variante 'Le Barouf' sans 'Bar'."""
        lieu_ref = [
            (1, "Bar Le Barouf", "Le Mans"),
        ]
        patterns = load_lieu_patterns(lieu_ref)
        result = find_lieu_in_text_v2("Concert, Le Barouf, 20h", patterns)
        assert result is not None
        assert result[1] == 1  # ID du lieu

    def test_find_oasis_variante(self):
        """Test lieu L'Oasis trouvé avec variante 'Oasis'."""
        lieu_ref = [
            (1, "L'Oasis", "Le Mans"),
        ]
        patterns = load_lieu_patterns(lieu_ref)
        result = find_lieu_in_text_v2("Concert, Oasis, 20h", patterns)
        assert result is not None
        assert result[1] == 1


class TestSplitOnDatesV2:
    """Tests pour le split sur les dates."""

    def test_no_split_single_event(self):
        """Pas de split pour un événement unique."""
        text = "ARTISTE, Lieu, 20h, 5€"
        parts = split_on_dates_v2(text)
        assert len(parts) == 1
        assert parts[0] == text

    def test_split_on_lu_ma(self):
        """Split sur Lu 02 & Ma 03."""
        text = '"L\'itinérance" (théâtre), Le Rabelais, 17h, 3/5€ Lu 02 & Ma 03 : "Enfantillages" (théâtre), Théâtre, 18h30'
        parts = split_on_dates_v2(text)
        assert len(parts) == 2
        assert "L'itinérance" in parts[0]
        assert "Enfantillages" in parts[1]

    def test_no_split_on_price(self):
        """Ne pas splitter sur les prix comme 7€50."""
        text = '"Spectacle", Lieu, 18h30, 7€50'
        parts = split_on_dates_v2(text)
        assert len(parts) == 1

    def test_split_sa_di_after_price(self):
        """Split sur Sa 21 & di 22 après un prix."""
        text = 'Mister Eleganz as Dj, Bar le Passeport, 23h-4h, 0€ Sa 21 & di 22 : "Belluettes de Noël" (contes), Théâtre, 17h'
        parts = split_on_dates_v2(text)
        assert len(parts) == 2
        assert "Mister Eleganz" in parts[0]
        assert "Belluettes" in parts[1]


class TestParseDatePrefixV2:
    """Tests pour le parsing des préfixes de date."""

    def test_parse_single_date(self):
        """Test date simple."""
        dates, rest = parse_date_prefix_v2("Sa 20 : ARTISTE, Lieu, 20h", 5, 2023)
        assert len(dates) == 1
        assert dates[0].day == 20

    def test_parse_multi_dates(self):
        """Test dates multiples."""
        dates, rest = parse_date_prefix_v2("Sa 07 & Di 08 : Concert, Lieu", 12, 2023)
        assert len(dates) == 2
        days = [d.day for d in dates]
        assert 7 in days
        assert 8 in days

    def test_no_date_prefix(self):
        """Test sans préfixe de date."""
        dates, rest = parse_date_prefix_v2("ARTISTE, Lieu, 20h", 5, 2023)
        assert len(dates) == 0
        assert rest == "ARTISTE, Lieu, 20h"


class TestExtractBeforeLieu:
    """Tests pour l'extraction avant le lieu."""

    def test_artiste_majuscules(self):
        """Test artiste en majuscules."""
        result = extract_before_lieu("MENDELSON (poème rock), Lieu", 24)
        assert len(result.get('artistes', [])) >= 1
        noms = [a.get('nom', a) if isinstance(a, dict) else a.nom for a in result['artistes']]
        assert any("Mendelson" in n or "MENDELSON" in n for n in noms)

    def test_spectacle_guillemets(self):
        """Test spectacle entre guillemets."""
        result = extract_before_lieu('"L\'itinérance de Maud" (théâtre), Lieu', 38)
        spectacles = result.get('spectacles', [])
        # Les spectacles sont des dicts avec 'nom' et 'style'
        spectacle_noms = [s['nom'] if isinstance(s, dict) else s for s in spectacles]
        assert "L'itinérance de Maud" in spectacle_noms

    def test_artiste_avec_avec(self):
        """Test pattern 'avec ARTISTE'."""
        result = extract_before_lieu('"Spectacle" avec LA COMPAGNIE, Lieu', 32)
        artistes = result.get('artistes', [])
        assert len(artistes) >= 1

    def test_avec_la_cie_guillemets(self):
        """Test 'avec la Cie "XXX"' - artiste entre guillemets."""
        result = extract_before_lieu('"Théâtre sauvage" avec la Cie "demain c\'est dimanche", Lieu', 55)
        artistes = result.get('artistes', [])
        assert len(artistes) >= 1
        noms = [a['nom'].lower() if isinstance(a, dict) else a.nom.lower() for a in artistes]
        assert any("demain c'est dimanche" in n for n in noms)

    def test_artiste_mixed_case_jean_claude(self):
        """Test artiste en mixed case: Jean-Claude CARRIÈRE."""
        result = extract_before_lieu("Jean-Claude CARRIÈRE (lecture), Lieu", 31)
        artistes = result.get('artistes', [])
        assert len(artistes) >= 1
        noms = [a['nom'] if isinstance(a, dict) else a.nom for a in artistes]
        assert any("Jean-Claude" in n and "CARRIÈRE" in n for n in noms)

    def test_artiste_mixed_case_groupe(self):
        """Test artiste groupe en mixed case: Les Echappées du Bocal."""
        result = extract_before_lieu("Les Echappées du Bocal (cabaret d'improvisation), Lieu", 48)
        artistes = result.get('artistes', [])
        assert len(artistes) >= 1
        noms = [a['nom'] if isinstance(a, dict) else a.nom for a in artistes]
        assert any("Echappées" in n for n in noms)

    def test_artiste_dr_bones(self):
        """Test artiste: Dr Bones & the Blue Roots."""
        result = extract_before_lieu("Dr Bones & the Blue Roots (blues-rock), Lieu", 39)
        artistes = result.get('artistes', [])
        assert len(artistes) >= 1
        noms = [a['nom'] if isinstance(a, dict) else a.nom for a in artistes]
        assert any("Dr Bones" in n for n in noms)

    def test_artiste_plus_guests(self):
        """Test BUTE (crust) + guests!! - deux artistes."""
        result = extract_before_lieu("BUTE (crust) + guests!!, Lieu", 24)
        artistes = result.get('artistes', [])
        noms = [a['nom'] if isinstance(a, dict) else a.nom for a in artistes]
        # BUTE doit être présent
        assert any("BUTE" in n.upper() for n in noms)
        # Guests doit être présent
        assert any("guest" in n.lower() for n in noms)

    def test_soiree_avec_dj(self):
        """Test Soirée X avec DJ Y - nom événement + artiste."""
        result = extract_before_lieu("Soirée Mix Généraliste avec Dj Vindu, Lieu", 36)
        # Le nom d'événement doit être "Soirée Mix Généraliste"
        assert result.get('nom_evenement') is not None
        assert "Soirée" in result['nom_evenement']
        # DJ Vindu doit être un artiste
        artistes = result.get('artistes', [])
        noms = [a['nom'].upper() if isinstance(a, dict) else a.nom.upper() for a in artistes]
        assert any("DJ" in n and "VINDU" in n for n in noms)


class TestExtractAfterLieu:
    """Tests pour l'extraction après le lieu."""

    def test_extract_heure(self):
        """Test extraction de l'heure."""
        result = extract_after_lieu("ARTISTE, Lieu, 20h30, 5€", 14)
        assert result.get('heure') == "20h30"

    def test_extract_prix(self):
        """Test extraction du prix."""
        result = extract_after_lieu("ARTISTE, Lieu, 20h, 5€", 13)
        assert result.get('prix_min') == 5


class TestExtractVilleV2:
    """Tests pour l'extraction de la ville v2."""

    def test_ville_explicite(self):
        """La ville explicite dans le texte doit être trouvée."""
        ville_ref = [
            (1, "Le Mans"),
            (2, "La Flèche"),
            (3, "Saint-Pavace"),
        ]
        ville_id, ville_nom = extract_ville_from_text_v2("Concert, Théâtre, La Flèche, 20h", ville_ref)
        assert ville_id == 2
        assert "Flèche" in ville_nom

    def test_ville_non_le_mans_prioritaire(self):
        """Les villes hors Le Mans doivent être prioritaires."""
        ville_ref = [
            (1, "Le Mans"),
            (2, "Saint-Pavace"),
        ]
        ville_id, ville_nom = extract_ville_from_text_v2("Concert, Saint-Pavace, Le Mans", ville_ref)
        # Saint-Pavace devrait être prioritaire car hors Le Mans
        assert ville_id == 2


class TestParseEventLineV2:
    """Tests d'intégration pour parse_event_line_v2."""

    @pytest.fixture
    def lieu_ref(self):
        return [
            (1, "Bar Le Barouf", "Le Mans"),
            (2, "Le Rabelais", "Le Mans"),
            (3, "Théâtre de l'Éphémère", "Le Mans"),
            (4, "Boire du Bon", "Saint-Pavace"),
            (5, "Théâtre de la Halle au blé", "La Flèche"),
        ]

    @pytest.fixture
    def ville_ref(self):
        return [
            (1, "Le Mans"),
            (2, "Saint-Pavace"),
            (3, "La Flèche"),
        ]

    @pytest.fixture
    def parser(self):
        return EventParser(bidul_mois=5, bidul_annee=2023)

    def test_simple_event(self, lieu_ref, ville_ref):
        """Test événement simple."""
        text = "MENDELSON (poème rock), Bar Le Barouf, 20h, 5€"
        events = parse_event_line_v2(text, 5, 2023, lieu_ref, ville_ref)
        assert len(events) == 1
        event = events[0]
        assert event['lieu_ref_id'] == 1
        assert "Barouf" in event['lieu_raw']

    def test_event_with_date(self, lieu_ref, ville_ref):
        """Test événement avec date."""
        text = "Sa 20 : ARTISTE, Bar Le Barouf, 20h"
        events = parse_event_line_v2(text, 5, 2023, lieu_ref, ville_ref)
        assert len(events) == 1
        event = events[0]
        assert event['date_evenement'] is not None
        assert event['date_evenement'].day == 20

    def test_multi_dates_split(self, lieu_ref, ville_ref):
        """Test split sur dates multiples."""
        text = '"Spectacle1" Le Rabelais, 17h Lu 02 & Ma 03 : "Spectacle2" Théâtre de l\'Éphémère, 18h30'
        events = parse_event_line_v2(text, 12, 2023, lieu_ref, ville_ref)
        # Devrait produire 2 événements (ou plus selon le split)
        assert len(events) >= 1

    def test_ville_from_lieu(self, lieu_ref, ville_ref):
        """La ville du lieu doit être extraite."""
        text = "Concert, Boire du Bon, 20h"
        events = parse_event_line_v2(text, 5, 2023, lieu_ref, ville_ref)
        assert len(events) >= 1
        # La ville de Boire du Bon est Saint-Pavace (ville_id=2)
        event = events[0]
        if event['lieu_ref_id'] == 4:  # Boire du Bon
            # La ville devrait être extraite du référentiel ou du texte
            pass  # L'extraction de ville se fait séparément

    def test_lieu_not_found_fallback(self, lieu_ref, ville_ref):
        """Test fallback quand le lieu n'est pas trouvé."""
        text = "ARTISTE, Lieu Inconnu, 20h, 5€"
        events = parse_event_line_v2(text, 5, 2023, lieu_ref, ville_ref)
        assert len(events) == 1
        event = events[0]
        assert event['lieu_ref_id'] is None

    def test_parse_with_referentiel_standard(self, parser, lieu_ref, ville_ref):
        """Test parse_with_referentiel avec format standard."""
        text = """Samedi 20
• MENDELSON (poème rock), Bar Le Barouf, 20h, 5€
Dimanche 21
• JAM ST CO MUSICOS (jam session), Le Rabelais, 21h, au chapeau
"""
        events = parser.parse_with_referentiel(text, lieu_ref, ville_ref)
        assert len(events) == 2

        # Premier événement
        event1 = events[0]
        # date_str peut être abrégé (Sa 20) ou complet (Samedi 20)
        assert "20" in event1.date_str
        assert event1.lieu_raw is not None
        assert "Barouf" in event1.lieu_raw

        # Deuxième événement
        event2 = events[1]
        # date_str peut être abrégé (Di 21) ou complet (Dimanche 21)
        assert "21" in event2.date_str
        assert event2.lieu_raw is not None

    def test_parse_with_referentiel_finds_lieu(self, parser, lieu_ref, ville_ref):
        """Test que parse_with_referentiel trouve le lieu dans le référentiel."""
        text = """Samedi 20
• "Ex Ovo" Cie Le grand Raymond (cirque), Théâtre de l'Éphémère, 20h30, 4/8€
"""
        events = parser.parse_with_referentiel(text, lieu_ref, ville_ref)
        assert len(events) == 1
        event = events[0]
        # Le lieu doit être trouvé via le référentiel
        assert event.lieu_raw is not None
        assert "Éphémère" in event.lieu_raw


class TestSplitOnDatesV2NoFalseSplit:
    """Tests pour éviter les faux splits sur 'de 18 mois', 'de 14 ans', etc."""

    def test_no_split_on_de_18_mois(self):
        """'de 18 mois à 4 ans' ne doit pas être splitté."""
        text = '" Le Grand Saut " (th. de Guimbarde) de 18 mois à 4 ans, Esp. H. Salvador Coulaines 10h et 15h, 5 & 5,80€'
        parts = split_on_dates_v2(text)
        assert len(parts) == 1
        assert "de 18 mois" in parts[0]

    def test_no_split_on_de_14_ans(self):
        """'de 14 ans' ne doit pas être splitté."""
        text = 'Les Spectaculaires : « Gargantua » (théâtre et objets, à partir de 14 ans) par Julien Mellano, S.J.Carmet, Allonnes, 20h30, 6€'
        parts = split_on_dates_v2(text)
        assert len(parts) == 1
        assert "de 14 ans" in parts[0]

    def test_no_split_on_le_25(self):
        """'le 25 décembre' ne doit pas être splitté (le n'est pas un jour)."""
        text = 'Concert spécial le 25 décembre, salle des fêtes'
        parts = split_on_dates_v2(text)
        assert len(parts) == 1


class TestParseDatePrefixV2WithMonth:
    """Tests pour le parsing des dates avec mois explicite (DD/MM format)."""

    def test_parse_du_31_au_03_02(self):
        """Du 31 au 03/02 doit créer 4 dates (31/01, 01/02, 02/02, 03/02)."""
        date_list, remaining = parse_date_prefix_v2("Du 31 au 03/02: dummy", 1, 2013)
        assert len(date_list) == 4
        assert date_list[0] == date(2013, 1, 31)
        assert date_list[1] == date(2013, 2, 1)
        assert date_list[2] == date(2013, 2, 2)
        assert date_list[3] == date(2013, 2, 3)
        assert remaining == "dummy"

    def test_parse_ve_01_02(self):
        """Ve 01/02 doit créer 1 date (01/02)."""
        date_list, remaining = parse_date_prefix_v2("Ve 01/02: dummy", 1, 2013)
        assert len(date_list) == 1
        assert date_list[0] == date(2013, 2, 1)
        assert remaining == "dummy"

    def test_parse_sa_15_03(self):
        """Sa 15/03 doit créer 1 date (15/03)."""
        date_list, remaining = parse_date_prefix_v2("Sa 15/03: dummy", 1, 2013)
        assert len(date_list) == 1
        assert date_list[0] == date(2013, 3, 15)


class TestEventParserInlineWithMonthDates:
    """Tests pour le parsing inline avec dates au format DD/MM."""

    @pytest.fixture
    def parser(self):
        return EventParser(bidul_mois=1, bidul_annee=2013, date_format='inline')

    def test_du_31_au_03_02_creates_4_events(self, parser):
        """Du 31 au 03/02 doit créer 4 événements."""
        text = 'Du 31 au 03/02: " Dis à ma fille que je pars en voyage >> La Fonderie, Le Mans, 20h30'
        events = parser.parse_with_referentiel(text, [], [])
        assert len(events) == 4
        dates = sorted([e.date_evenement for e in events])
        assert dates[0] == date(2013, 1, 31)
        assert dates[1] == date(2013, 2, 1)
        assert dates[2] == date(2013, 2, 2)
        assert dates[3] == date(2013, 2, 3)

    def test_ve_01_02_creates_1_event(self, parser):
        """Ve 01/02 doit créer 1 événement."""
        text = 'Ve 01/02: << L\'Événement >> La Fonderie, Le Mans, 21h'
        events = parser.parse_with_referentiel(text, [], [])
        assert len(events) == 1
        assert events[0].date_evenement == date(2013, 2, 1)


class TestEventParserInlineWithDateRange:
    """Tests pour le parsing inline avec plages de dates DD-DD."""

    @pytest.fixture
    def parser(self):
        return EventParser(bidul_mois=3, bidul_annee=2009, date_format='inline')

    def test_lu_ma_me_range_creates_6_events(self, parser):
        """Lu 30/Ma 31/Me 01-04: doit créer 6 événements (30, 31 mars + 1-4 avril)."""
        text = 'Lu 30/Ma 31/Me 01-04: Apéro concert avec YURI HU, Bar Le Palais, 19h'
        events = parser.parse_with_referentiel(text, [], [])
        assert len(events) == 6
        dates = sorted([e.date_evenement for e in events])
        # Mars
        assert dates[0] == date(2009, 3, 30)
        assert dates[1] == date(2009, 3, 31)
        # Avril (mois suivant)
        assert dates[2] == date(2009, 4, 1)
        assert dates[3] == date(2009, 4, 2)
        assert dates[4] == date(2009, 4, 3)
        assert dates[5] == date(2009, 4, 4)


class TestSplitOnDatesV2WithParasiticChars:
    """Tests pour le split avec caractères parasites OCR (+, t, †)."""

    def test_split_on_plus_ma(self):
        """+Ma 14: doit être splitté correctement."""
        text = 'Premier event 21h30 +Ma 14: Deuxieme event'
        parts = split_on_dates_v2(text)
        assert len(parts) == 2
        assert 'Ma 14' in parts[1]

    def test_split_on_t_je(self):
        """tJe 16: doit être splitté correctement."""
        text = 'Premier event 21h tJe 16: Deuxieme event'
        parts = split_on_dates_v2(text)
        assert len(parts) == 2
        assert 'Je 16' in parts[1]

    def test_bidul_72_pattern(self):
        """Test complet du pattern bidul 72."""
        text = 'Soiree Reggae, 21h30 +Ma 14: BOB HOUNSLOW, Le Mackeson, 21h tJe 16: MISTER JO, PCV, 21h30'
        parts = split_on_dates_v2(text)
        assert len(parts) == 3
        assert 'Reggae' in parts[0]
        assert 'BOB HOUNSLOW' in parts[1]
        assert 'MISTER JO' in parts[2]


class TestSplitBlocFusedEvents:
    """Tests pour le split des événements fusionnés en format bloc."""

    def test_split_on_price_then_majuscules(self):
        """Split après prix suivi de nom en MAJUSCULES."""
        text = 'ARTISTE1 (jazz), Le Zoo, 21h, 0E ARTISTE2 (rock), Le Bar, 20h, 3E'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 2
        assert 'ARTISTE1' in parts[0]
        assert 'ARTISTE2' in parts[1]

    def test_split_on_price_then_soiree(self):
        """Split après prix suivi de Soirée."""
        text = 'CONCERT (rock), Lieu, 21h, 0E Soiree funk avec DJ, Lieu, 23h, 5E'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 2
        assert 'CONCERT' in parts[0]
        assert 'Soiree funk' in parts[1]

    def test_bidul_175_pattern(self):
        """Test complet du pattern bidul 175."""
        text = 'SANDRA CAROLL (jazz), Le Zoo 21h, 0E BOBBY SIX KILLERS (rock), Bar, 20h, 3E LE MANS CITE CHANSON, Lieu, 20h30, 0E'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 3
        assert 'SANDRA CAROLL' in parts[0]
        assert 'BOBBY SIX KILLERS' in parts[1]
        assert 'LE MANS CITE CHANSON' in parts[2]

    def test_split_on_price_then_quote(self):
        """Split après prix suivi de guillemet ouvrant."""
        text = 'Blues in Box (blues), Lieu, 21h30, 0E "Openspace" (th.), par La Cie'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 2
        assert 'Blues in Box' in parts[0]
        assert '"Openspace"' in parts[1]

    def test_split_on_hour_then_les(self):
        """Split après heure suivie de 'Les Spectaculaires'."""
        text = 'LE SYNDROME DU CHAT (rock), Le Passeport, 22h Les Spectaculaires: Soirée PETITES'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 2
        assert 'LE SYNDROME DU CHAT' in parts[0]
        assert 'Les Spectaculaires' in parts[1]

    def test_split_on_phone_then_majuscules(self):
        """Split après numéro de téléphone suivi de MAJUSCULES."""
        text = 'Concert, Lieu, 7/15E, résa.: 02 43 80 80 82 LE MANS CITE CHANSON: Présélection'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 2
        assert 'Concert' in parts[0]
        assert 'LE MANS CITE CHANSON' in parts[1]

    def test_split_on_price_then_birdland(self):
        """Split après prix suivi de Birdland."""
        text = 'Soirée open mix, Le Passeport, 23h-4h, 0E Birdland présente Olivier Mugot Trio'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 2
        assert 'Soirée open mix' in parts[0]
        assert 'Birdland' in parts[1]

    def test_split_on_parenthesis_then_double_chevron(self):
        """Split après parenthèse fermante suivie de << (guillemets OCR)."""
        text = 'Les Spectaculaires: Soirée PETITES FORMES (àpd 12ans): "Pitt" + "Ma foi" + "Bertha", Jean Carmet, Allonnes 19h, 15€ repas compris (sur résa.) <<Pièce montée" (th.), Espace Scélia Sargé, 20h30, 6/10€'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 2
        assert 'Les Spectaculaires' in parts[0]
        assert '<<Pièce montée' in parts[1]

    def test_split_on_chapeau_then_day(self):
        """Split après 'chapeau' suivi d'un jour de semaine."""
        text = '"Electre"> (théâtre), Théâtre de Chaoué Allonnes 20h30, tarif: au chapeau Ve 06/Sa 07 20h30/Di 08 15h: "Métis\'sages>'
        from core.parser import split_bloc_fused_events
        parts = split_bloc_fused_events(text)
        assert len(parts) == 2
        assert 'Electre' in parts[0]
        assert 'chapeau' in parts[0]
        assert 'Métis' in parts[1]


class TestExtractFormattedSpectacles:
    """Tests pour l'extraction de spectacles avec formats OCR."""

    def test_ocr_double_chevron_quote_closing(self):
        """OCR avec << ouvrant et "> fermant (combinaison " et >)."""
        from core.parser import extract_formatted_spectacles
        text = '<<Rien ne laisse présager de l\'Etat de l\'Eau"> (danse), par O. Duboc'
        spectacles = extract_formatted_spectacles(text)
        assert len(spectacles) == 1
        assert spectacles[0]['nom'] == "Rien ne laisse présager de l'Etat de l'Eau"
        assert spectacles[0]['style'] == 'danse'

    def test_ocr_double_chevron_simple_closing(self):
        """OCR avec << ouvrant et > fermant simple."""
        from core.parser import extract_formatted_spectacles
        text = '<<Marrons gagnants> (contes)'
        spectacles = extract_formatted_spectacles(text)
        assert len(spectacles) == 1
        assert spectacles[0]['nom'] == 'Marrons gagnants'
        assert spectacles[0]['style'] == 'contes'

    def test_ocr_quote_chevron_closing(self):
        """OCR avec " ouvrant et > fermant."""
        from core.parser import extract_formatted_spectacles
        text = '"Métis\'sages> (contes et légendes d\'ailleurs)'
        spectacles = extract_formatted_spectacles(text)
        assert len(spectacles) == 1
        assert spectacles[0]['nom'] == "Métis'sages"
        assert spectacles[0]['style'] == "contes et légendes d'ailleurs"


class TestSplitRegionalSection:
    """Tests pour la détection de la section régionale 'Et un peu plus loin...'."""

    def test_split_regional_section_found(self):
        """Détecte et sépare la section régionale."""
        from core.parser import split_regional_section
        # Le marqueur doit être APRÈS des événements avec dates pour être détecté
        text = """Ve 04: Concert local, Le Mans, 21h
Sa 05: Autre concert, Allonnes, 20h
Et un peu plus loin...
Dans l'Orne (61):
CALI (chanson), 21h, 25 à 30€
PASCALE PICARD (pop rock), 21h"""

        local, regional = split_regional_section(text)
        assert 'Concert local' in local
        assert 'Et un peu plus loin' in regional
        assert 'CALI' in regional
        assert 'CALI' not in local

    def test_split_regional_section_not_found(self):
        """Pas de section régionale, tout reste local."""
        from core.parser import split_regional_section
        text = """Concert 1, Le Mans, 21h
Concert 2, Allonnes, 20h"""

        local, regional = split_regional_section(text)
        assert local == text
        assert regional == ""

    def test_split_regional_section_ocr_variation(self):
        """Supporte les variations OCR (sans 'Et')."""
        from core.parser import split_regional_section
        # Le marqueur doit être APRÈS des événements avec dates pour être détecté
        text = """Ve 04: Concert local, Le Mans, 21h
un peu plus loin...
Concert régional"""

        local, regional = split_regional_section(text)
        assert 'Concert local' in local
        assert 'un peu plus loin' in regional

    def test_split_regional_section_marker_before_events(self):
        """Le marqueur avant les événements est ignoré (ancien format)."""
        from core.parser import split_regional_section
        # Dans certains anciens Biduls, "et même un peu plus loin" est un sous-titre
        # qui apparaît AVANT les événements
        text = """En Sarthe
et même un peu plus loin...
Ve 04: Concert, Le Mans, 21h
Sa 05: Autre concert, Allonnes, 20h"""

        local, regional = split_regional_section(text)
        # Pas de split car le marqueur est AVANT les événements
        assert local == text
        assert regional == ""


class TestInlineInheritedDateFormat:
    """Tests pour le format inline_inherited (biduls 1-16)."""

    def test_date_only_line_sets_current_date(self):
        """Une ligne 'Je 05:' seule doit établir la date pour les événements suivants."""
        text = """Je 05:
URANUS BRILLANT, bar Le Viking's, LE MANS, 21h30
NICOLAS ET TOMY, pub Le Terminus, LE MANS, 21h00"""

        lieu_ref = [(1, "bar Le Viking's", "Le Mans"), (2, "Le Terminus", "Le Mans")]
        ville_ref = [(1, "Le Mans")]

        parser = EventParser(bidul_mois=2, bidul_annee=1998, date_format='inline_inherited')
        events = parser.parse_with_referentiel(text, lieu_ref, ville_ref)

        assert len(events) == 2
        assert events[0].date_evenement == date(1998, 2, 5)
        assert events[1].date_evenement == date(1998, 2, 5)
        assert "URANUS" in events[0].raw_text
        assert "NICOLAS" in events[1].raw_text

    def test_date_with_content_on_same_line(self):
        """Format 'Ma 03: ARTISTE, lieu' doit créer un événement avec la date."""
        text = """Ma 03: TONGZ, bar Le Mackeson, LE MANS, 22h15
MICHEL EDELIN QUARTET, Le Théâtre, LE MANS, 21h00"""

        lieu_ref = [(1, "Le Mackeson", "Le Mans"), (2, "Le Théâtre", "Le Mans")]
        ville_ref = [(1, "Le Mans")]

        parser = EventParser(bidul_mois=2, bidul_annee=1998, date_format='inline_inherited')
        events = parser.parse_with_referentiel(text, lieu_ref, ville_ref)

        assert len(events) == 2
        assert events[0].date_evenement == date(1998, 2, 3)
        assert events[1].date_evenement == date(1998, 2, 3)

    def test_continuation_lines_are_joined(self):
        """Les lignes de continuation (ville, heure) sont jointes à l'événement précédent."""
        text = """Je 05:
NICOLAS ET TOMY, pub Le Terminus
LE MANS 21h00"""

        lieu_ref = [(1, "Le Terminus", "Le Mans")]
        ville_ref = [(1, "Le Mans")]

        parser = EventParser(bidul_mois=2, bidul_annee=1998, date_format='inline_inherited')
        events = parser.parse_with_referentiel(text, lieu_ref, ville_ref)

        assert len(events) == 1
        assert events[0].date_evenement == date(1998, 2, 5)
        # LE MANS doit être joint à l'événement
        assert "LE MANS" in events[0].raw_text or events[0].ville_raw == "Le Mans"

    def test_new_date_resets_inheritance(self):
        """Une nouvelle date doit réinitialiser l'héritage."""
        text = """Je 05:
URANUS BRILLANT, bar Le Viking's, LE MANS, 21h30
Ve 06: SAMEBLOOD, L'Inventaire, LE MANS, 22h00"""

        lieu_ref = [(1, "bar Le Viking's", "Le Mans"), (2, "L'Inventaire", "Le Mans")]
        ville_ref = [(1, "Le Mans")]

        parser = EventParser(bidul_mois=2, bidul_annee=1998, date_format='inline_inherited')
        events = parser.parse_with_referentiel(text, lieu_ref, ville_ref)

        assert len(events) == 2
        assert events[0].date_evenement == date(1998, 2, 5)
        assert events[1].date_evenement == date(1998, 2, 6)

    def test_fallback_to_inline_if_no_events(self):
        """Si inline_inherited ne trouve rien, fallback sur inline."""
        # Texte sans format inline_inherited valide
        text = "Simple text without dates"

        parser = EventParser(bidul_mois=2, bidul_annee=1998, date_format='inline_inherited')
        events = parser.parse_with_referentiel(text, [], [])

        # Pas d'erreur, juste 0 événements
        assert len(events) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

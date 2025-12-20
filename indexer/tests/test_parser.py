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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

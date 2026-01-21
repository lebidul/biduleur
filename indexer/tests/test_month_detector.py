"""Tests pour le module month_detector (détection des sections de mois)."""

import pytest
from core.month_detector import (
    detect_month_sections,
    get_month_for_line,
    get_month_for_position,
    is_summer_bidul,
    strip_html_tags,
    MonthSection,
)


class TestStripHtmlTags:
    """Tests pour la fonction strip_html_tags."""

    def test_simple_tags(self):
        """Test suppression de balises simples."""
        assert strip_html_tags("<b>Juillet</b>") == "Juillet"
        assert strip_html_tags("<bi>Août</bi>") == "Août"

    def test_multiple_tags(self):
        """Test avec plusieurs balises."""
        assert strip_html_tags("<b><i>JUILLET</i></b>") == "JUILLET"

    def test_no_tags(self):
        """Test sans balises."""
        assert strip_html_tags("JUILLET") == "JUILLET"

    def test_tag_with_space(self):
        """Test balise avec espace avant fermeture."""
        assert strip_html_tags("<b>JUILLET </b>") == "JUILLET "


class TestDetectMonthSections:
    """Tests pour la fonction detect_month_sections."""

    def test_simple_juillet(self):
        """Test détection simple de 'Juillet'."""
        text = "Juillet\nVe 01: Concert"
        sections = detect_month_sections(text)
        assert len(sections) == 1
        assert sections[0].month == 7
        assert sections[0].line_number == 0

    def test_simple_aout(self):
        """Test détection simple de 'Août'."""
        text = "Août\nVe 01: Concert"
        sections = detect_month_sections(text)
        assert len(sections) == 1
        assert sections[0].month == 8

    def test_juillet_et_aout(self):
        """Test détection de juillet et août."""
        text = """JUILLET
Ve 01: Concert
Sa 02: Festival
AOÛT
Ve 01: Autre concert"""
        sections = detect_month_sections(text)
        assert len(sections) == 2
        assert sections[0].month == 7
        assert sections[1].month == 8

    def test_with_html_tags(self):
        """Test détection avec balises HTML."""
        text = """<bi>Juillet </bi>
Ve 01: Concert
<bi>Août</bi>
Ve 01: Autre concert"""
        sections = detect_month_sections(text)
        assert len(sections) == 2
        assert sections[0].month == 7
        assert sections[1].month == 8

    def test_en_juillet_format(self):
        """Test format 'En juillet :'."""
        text = "En juillet :\nVe 01: Concert"
        sections = detect_month_sections(text)
        assert len(sections) == 1
        assert sections[0].month == 7

    def test_du_au_format(self):
        """Test format 'Du X au Y juillet'."""
        text = "Du 1er au 31 juillet 2011\nVe 01: Concert"
        sections = detect_month_sections(text)
        assert len(sections) == 1
        assert sections[0].month == 7

    def test_ocr_truncated_ao(self):
        """Test OCR tronqué 'AO' pour AOÛT."""
        text = """JUILLET
Ve 01: Concert
AO
Ve 01: Autre"""
        sections = detect_month_sections(text)
        assert len(sections) == 2
        assert sections[1].month == 8

    def test_ocr_aqut(self):
        """Test erreur OCR 'AQUT' pour AOÛT."""
        text = """JUILLET
Ve 01: Concert
AQUT
Ve 01: Autre"""
        sections = detect_month_sections(text)
        assert len(sections) == 2
        assert sections[1].month == 8

    def test_septembre(self):
        """Test détection de septembre."""
        text = """JUILLET
Ve 01: Concert
AOUT
Ve 01: Autre
SEPTEMBRE
Di 01: Festival"""
        sections = detect_month_sections(text)
        assert len(sections) == 3
        assert sections[2].month == 9

    def test_majuscules(self):
        """Test formats majuscules."""
        text = """JUILLET
Ve 01: Concert
AOUT
Ve 01: Autre"""
        sections = detect_month_sections(text)
        assert len(sections) == 2
        assert sections[0].month == 7
        assert sections[1].month == 8

    def test_minuscules(self):
        """Test formats minuscules."""
        text = """juillet
Ve 01: Concert
aout
Ve 01: Autre"""
        sections = detect_month_sections(text)
        assert len(sections) == 2

    def test_no_month_headers(self):
        """Test texte sans headers de mois."""
        text = "Ve 01: Concert\nSa 02: Festival"
        sections = detect_month_sections(text)
        assert len(sections) == 0


class TestGetMonthForLine:
    """Tests pour la fonction get_month_for_line."""

    def test_before_first_section(self):
        """Test ligne avant la première section."""
        sections = [
            MonthSection(line_number=5, month=7, header_text="JUILLET", start_pos=50)
        ]
        assert get_month_for_line(sections, 3, default_month=7) == 7

    def test_after_july_section(self):
        """Test ligne après section juillet."""
        sections = [
            MonthSection(line_number=5, month=7, header_text="JUILLET", start_pos=50),
            MonthSection(line_number=50, month=8, header_text="AOÛT", start_pos=500),
        ]
        assert get_month_for_line(sections, 20, default_month=7) == 7

    def test_after_august_section(self):
        """Test ligne après section août."""
        sections = [
            MonthSection(line_number=5, month=7, header_text="JUILLET", start_pos=50),
            MonthSection(line_number=50, month=8, header_text="AOÛT", start_pos=500),
        ]
        assert get_month_for_line(sections, 60, default_month=7) == 8

    def test_empty_sections(self):
        """Test avec liste de sections vide."""
        assert get_month_for_line([], 10, default_month=7) == 7


class TestGetMonthForPosition:
    """Tests pour la fonction get_month_for_position."""

    def test_after_august_position(self):
        """Test position après section août."""
        sections = [
            MonthSection(line_number=5, month=7, header_text="JUILLET", start_pos=50),
            MonthSection(line_number=50, month=8, header_text="AOÛT", start_pos=500),
        ]
        assert get_month_for_position(sections, 600, default_month=7) == 8

    def test_empty_sections(self):
        """Test avec liste de sections vide."""
        assert get_month_for_position([], 100, default_month=7) == 7


class TestIsSummerBidul:
    """Tests pour la fonction is_summer_bidul."""

    def test_july_is_summer(self):
        """Test que juillet est un bidul d'été."""
        assert is_summer_bidul(7) is True

    def test_other_months_not_summer(self):
        """Test que les autres mois ne sont pas des biduls d'été."""
        assert is_summer_bidul(1) is False
        assert is_summer_bidul(6) is False
        assert is_summer_bidul(8) is False
        assert is_summer_bidul(12) is False

    def test_none_is_not_summer(self):
        """Test que None n'est pas un bidul d'été."""
        assert is_summer_bidul(None) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

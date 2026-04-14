"""Tests pour le module section_extractor."""

import pytest
import numpy as np

from core.section_extractor import (
    Section,
    Orientation,
    PageSectionConfig,
    BidulSectionConfig,
    SectionConfigLoader,
    SectionCropper,
    load_section_config,
    SECTION_ORDER_PORTRAIT,
    SECTION_ORDER_PAYSAGE,
)


class TestSection:
    """Tests pour l'enum Section."""

    def test_section_values(self):
        assert Section.S1.value == 'S1'
        assert Section.S2.value == 'S2'
        assert Section.S3.value == 'S3'
        assert Section.S4.value == 'S4'


class TestOrientation:
    """Tests pour l'enum Orientation."""

    def test_orientation_values(self):
        assert Orientation.PORTRAIT.value == 'portrait'
        assert Orientation.PAYSAGE.value == 'paysage'


class TestPageSectionConfig:
    """Tests pour PageSectionConfig."""

    def test_default_values(self):
        config = PageSectionConfig()
        assert config.orientation_pdf == Orientation.PORTRAIT
        assert config.orientation_texte == Orientation.PORTRAIT
        assert config.colonnes_par_section == 1
        assert len(config.sections_utiles) == 4

    def test_needs_rotation_portrait(self):
        config = PageSectionConfig(orientation_texte=Orientation.PORTRAIT)
        assert not config.needs_rotation()

    def test_needs_rotation_paysage(self):
        config = PageSectionConfig(orientation_texte=Orientation.PAYSAGE)
        assert config.needs_rotation()

    def test_section_order_portrait(self):
        config = PageSectionConfig(orientation_texte=Orientation.PORTRAIT)
        order = config.get_section_order()
        assert order == SECTION_ORDER_PORTRAIT
        assert order == [Section.S1, Section.S2, Section.S3, Section.S4]

    def test_section_order_paysage(self):
        config = PageSectionConfig(orientation_texte=Orientation.PAYSAGE)
        order = config.get_section_order()
        assert order == SECTION_ORDER_PAYSAGE
        assert order == [Section.S1, Section.S3, Section.S2, Section.S4]


class TestBidulSectionConfig:
    """Tests pour BidulSectionConfig."""

    def test_is_scan(self):
        config = BidulSectionConfig(numero=99, type_source='scan')
        assert config.is_scan()

        config = BidulSectionConfig(numero=280, type_source='texte')
        assert not config.is_scan()

    def test_get_pages_to_process_3_pages(self):
        config = BidulSectionConfig(
            numero=99,
            page1=PageSectionConfig(sections_utiles=[Section.S3]),
            page2=PageSectionConfig(sections_utiles=[Section.S1, Section.S2, Section.S3, Section.S4])
        )
        # Avec 3 pages, on utilise page 3
        pages = config.get_pages_to_process(num_pages=3)
        assert pages == [3]

    def test_get_pages_to_process_2_pages(self):
        config = BidulSectionConfig(
            numero=99,
            page1=PageSectionConfig(sections_utiles=[Section.S3]),
            page2=PageSectionConfig(sections_utiles=[Section.S1, Section.S2, Section.S3, Section.S4])
        )
        # Avec 2 pages, on utilise les pages configurées
        pages = config.get_pages_to_process(num_pages=2)
        assert pages == [1, 2]

    def test_get_pages_to_process_override(self):
        config = BidulSectionConfig(
            numero=228,
            page1=PageSectionConfig(),
            page2=PageSectionConfig(),
            pages_override=[1, 2]
        )
        # pages_override a la priorité
        pages = config.get_pages_to_process(num_pages=3)
        assert pages == [1, 2]

    def test_get_page_config(self):
        page1 = PageSectionConfig(sections_utiles=[Section.S3])
        page2 = PageSectionConfig(sections_utiles=[Section.S1, Section.S2, Section.S3, Section.S4])
        config = BidulSectionConfig(numero=99, page1=page1, page2=page2)

        assert config.get_page_config(1) == page1
        assert config.get_page_config(2) == page2
        # Page 3+ utilise config page 2
        assert config.get_page_config(3) == page2


class TestSectionCropper:
    """Tests pour SectionCropper."""

    def test_crop_section_s1(self):
        # Image 100x100 pixels
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Marquer la zone S1 (haut-gauche)
        image[0:50, 0:50] = [255, 0, 0]  # Rouge

        cropper = SectionCropper(margin_percent=0)
        section = cropper.crop_section(image, Section.S1)

        # S1 devrait être la moitié supérieure gauche
        assert section.shape[0] == 50  # hauteur
        assert section.shape[1] == 50  # largeur
        assert np.all(section == [255, 0, 0])  # tout rouge

    def test_crop_section_s4(self):
        # Image 100x100 pixels
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Marquer la zone S4 (bas-droite)
        image[50:100, 50:100] = [0, 255, 0]  # Vert

        cropper = SectionCropper(margin_percent=0)
        section = cropper.crop_section(image, Section.S4)

        # S4 devrait être la moitié inférieure droite
        assert section.shape[0] == 50
        assert section.shape[1] == 50
        assert np.all(section == [0, 255, 0])

    def test_crop_sections_multiple(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        cropper = SectionCropper(margin_percent=0)

        sections = cropper.crop_sections(image, [Section.S1, Section.S3])

        assert Section.S1 in sections
        assert Section.S3 in sections
        assert Section.S2 not in sections

    def test_rotate_for_text(self):
        # Image 100x50 pixels (plus large que haute)
        image = np.zeros((50, 100, 3), dtype=np.uint8)
        cropper = SectionCropper()

        rotated = cropper.rotate_for_text(image, clockwise=False)

        # Après rotation 90° anti-horaire, dimensions inversées
        assert rotated.shape == (100, 50, 3)


class TestSectionConfigLoader:
    """Tests pour le chargement des configs depuis CSV."""

    def test_load_configs(self):
        loader = SectionConfigLoader()
        # Doit charger des configs
        assert len(loader.configs) > 0

    def test_get_config_existing(self):
        loader = SectionConfigLoader()
        config = loader.get_config(99)
        assert config is not None
        assert config.numero == 99

    def test_get_config_non_existing(self):
        loader = SectionConfigLoader()
        config = loader.get_config(9999)
        assert config is None

    def test_get_nearest_config(self):
        loader = SectionConfigLoader()
        # Bidul 60 n'a pas de sections, doit hériter d'un proche
        config = loader.get_nearest_config(60)
        assert config is not None
        # Doit avoir des sections
        assert config.page1 is not None or config.page2 is not None


class TestLoadSectionConfig:
    """Tests pour la fonction load_section_config."""

    def test_load_with_sections(self):
        # Bidul 99 a des sections définies
        config = load_section_config(99)
        assert config is not None
        assert config.page1 is not None or config.page2 is not None

    def test_load_inherits_from_nearest(self):
        # Bidul 500 n'existe pas, doit hériter d'un proche
        config = load_section_config(500)
        assert config is not None
        # Doit avoir hérité des sections
        assert config.page1 is not None or config.page2 is not None
        # Le numéro doit être celui du bidul source (pas 500)
        assert config.numero != 500

    def test_load_bidul_6_paysage(self):
        # Bidul 6 a un texte en paysage avec 2 colonnes
        config = load_section_config(6)
        assert config is not None
        assert config.page2 is not None
        assert config.page2.orientation_texte == Orientation.PAYSAGE
        assert config.page2.colonnes_par_section == 2


class TestPageSectionConfigRotation:
    """Tests pour la logique de rotation PDF vs texte."""

    def test_needs_rotation_same_orientation(self):
        """Pas de rotation si PDF et texte ont la même orientation."""
        # Portrait/Portrait
        config = PageSectionConfig(
            orientation_pdf=Orientation.PORTRAIT,
            orientation_texte=Orientation.PORTRAIT
        )
        assert not config.needs_rotation()

        # Paysage/Paysage
        config = PageSectionConfig(
            orientation_pdf=Orientation.PAYSAGE,
            orientation_texte=Orientation.PAYSAGE
        )
        assert not config.needs_rotation()

    def test_needs_rotation_different_orientation(self):
        """Rotation si PDF et texte ont des orientations différentes."""
        # PDF portrait, texte paysage (cas biduls 2-11)
        config = PageSectionConfig(
            orientation_pdf=Orientation.PORTRAIT,
            orientation_texte=Orientation.PAYSAGE
        )
        assert config.needs_rotation()

        # PDF paysage, texte portrait
        config = PageSectionConfig(
            orientation_pdf=Orientation.PAYSAGE,
            orientation_texte=Orientation.PORTRAIT
        )
        assert config.needs_rotation()

    def test_from_csv_row_with_orientation_pdf(self):
        """Test parsing CSV avec colonnes p*_orientation_pdf."""
        row = {
            'p2_sections': 'S1 S2 S3',
            'p2_orientation': 'paysage',
            'p2_orientation_pdf': 'portrait',
            'p2_colonnes': '2'
        }
        config = PageSectionConfig.from_csv_row(row, 2)
        assert config is not None
        assert config.orientation_texte == Orientation.PAYSAGE
        assert config.orientation_pdf == Orientation.PORTRAIT
        assert config.needs_rotation()
        assert config.colonnes_par_section == 2

    def test_from_csv_row_orientation_pdf_defaults_to_texte(self):
        """Si orientation_pdf n'est pas défini, il prend la valeur de orientation."""
        row = {
            'p2_sections': 'S1 S2 S3 S4',
            'p2_orientation': 'paysage',
            # p2_orientation_pdf non défini
            'p2_colonnes': '1'
        }
        config = PageSectionConfig.from_csv_row(row, 2)
        assert config is not None
        assert config.orientation_texte == Orientation.PAYSAGE
        assert config.orientation_pdf == Orientation.PAYSAGE  # Défaut = texte
        assert not config.needs_rotation()  # Pas de rotation car même orientation


class TestSectionCropperRotation:
    """Tests pour la rotation de SectionCropper."""

    def test_rotate_clockwise(self):
        """Test rotation 90° horaire."""
        # Image 50x100 (plus haute que large)
        # Marquer le coin supérieur gauche en rouge
        image = np.zeros((100, 50, 3), dtype=np.uint8)
        image[0:25, 0:25] = [255, 0, 0]  # Rouge en haut-gauche

        cropper = SectionCropper()
        rotated = cropper.rotate_for_text(image, clockwise=True)

        # Après rotation CW, dimensions inversées: 50x100
        assert rotated.shape == (50, 100, 3)
        # Le coin haut-gauche devient haut-droite après rotation CW
        assert np.all(rotated[0:25, 75:100] == [255, 0, 0])

    def test_rotate_counter_clockwise(self):
        """Test rotation 90° anti-horaire."""
        # Image 50x100 (plus haute que large)
        # Marquer le coin supérieur gauche en rouge
        image = np.zeros((100, 50, 3), dtype=np.uint8)
        image[0:25, 0:25] = [255, 0, 0]  # Rouge en haut-gauche

        cropper = SectionCropper()
        rotated = cropper.rotate_for_text(image, clockwise=False)

        # Après rotation CCW, dimensions inversées: 50x100
        assert rotated.shape == (50, 100, 3)
        # Le coin haut-gauche devient bas-gauche après rotation CCW
        assert np.all(rotated[25:50, 0:25] == [255, 0, 0])


class TestOrientation180:
    """Tests pour le support de la rotation 180° (retourne)."""

    def test_orientation_retourne_enum(self):
        """L'enum Orientation a la valeur RETOURNE."""
        assert Orientation.RETOURNE.value == 'retourne'

    def test_get_rotation_degrees_retourne(self):
        """get_rotation_degrees() retourne 180 quand orientation_pdf == RETOURNE."""
        config = PageSectionConfig(
            orientation_pdf=Orientation.RETOURNE,
            orientation_texte=Orientation.PORTRAIT
        )
        assert config.get_rotation_degrees() == 180
        assert config.needs_rotation()

    def test_get_rotation_degrees_90(self):
        """get_rotation_degrees() retourne 90 quand PDF != texte (portrait vs paysage)."""
        config = PageSectionConfig(
            orientation_pdf=Orientation.PORTRAIT,
            orientation_texte=Orientation.PAYSAGE
        )
        assert config.get_rotation_degrees() == 90

    def test_get_rotation_degrees_0(self):
        """get_rotation_degrees() retourne 0 quand pas de rotation nécessaire."""
        config = PageSectionConfig(
            orientation_pdf=Orientation.PORTRAIT,
            orientation_texte=Orientation.PORTRAIT
        )
        assert config.get_rotation_degrees() == 0
        assert not config.needs_rotation()

    def test_from_csv_row_retourne(self):
        """PageSectionConfig.from_csv_row() parse correctement 'retourne'."""
        row = {
            'p2_sections': 'S1 S2 S4',
            'p2_orientation': 'portrait',
            'p2_orientation_pdf': 'retourne',
            'p2_colonnes': '1'
        }
        config = PageSectionConfig.from_csv_row(row, 2)
        assert config is not None
        assert config.orientation_pdf == Orientation.RETOURNE
        assert config.orientation_texte == Orientation.PORTRAIT
        assert config.get_rotation_degrees() == 180

    def test_rotate_for_text_180(self):
        """SectionCropper.rotate_for_text(degrees=180) applique une rotation 180°."""
        image = np.zeros((100, 50, 3), dtype=np.uint8)
        image[0:25, 0:25] = [255, 0, 0]  # Rouge en haut-gauche

        cropper = SectionCropper()
        rotated = cropper.rotate_for_text(image, degrees=180)

        # Après rotation 180°, mêmes dimensions
        assert rotated.shape == (100, 50, 3)
        # Le coin haut-gauche devient bas-droite
        assert np.all(rotated[75:100, 25:50] == [255, 0, 0])

    def test_bidul_15_config_retourne(self):
        """Bidul 15 page2 a orientation_pdf=retourne dans le CSV."""
        config = load_section_config(15)
        assert config is not None
        assert config.page2 is not None
        assert config.page2.orientation_pdf == Orientation.RETOURNE
        assert config.page2.get_rotation_degrees() == 180


class TestBidulSectionConfigOrientationPdf:
    """Tests pour BidulSectionConfig avec orientation_pdf."""

    def test_bidul_5_config(self):
        """Bidul 5 a page2: PDF portrait, texte paysage, 2 colonnes."""
        config = load_section_config(5)
        assert config is not None
        assert config.page2 is not None
        assert config.page2.orientation_pdf == Orientation.PORTRAIT
        assert config.page2.orientation_texte == Orientation.PAYSAGE
        assert config.page2.needs_rotation()
        assert config.page2.colonnes_par_section == 2

    def test_bidul_5_section_order(self):
        """Bidul 5 en paysage utilise l'ordre S1→S3→S2→S4."""
        config = load_section_config(5)
        assert config is not None
        assert config.page2 is not None
        order = config.page2.get_section_order()
        assert order == [Section.S1, Section.S3, Section.S2, Section.S4]

    def test_bidul_5_sections(self):
        """Bidul 5 page2 a sections S1, S2, S3 (pas S4)."""
        config = load_section_config(5)
        assert config is not None
        assert config.page2 is not None
        sections = config.page2.sections_utiles
        assert Section.S1 in sections
        assert Section.S2 in sections
        assert Section.S3 in sections
        assert Section.S4 not in sections

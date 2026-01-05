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
        # Bidul 60 n'a pas de sections, doit hériter
        config = load_section_config(60)
        assert config is not None
        # Doit avoir hérité des sections
        assert config.page1 is not None or config.page2 is not None
        # Le numéro doit être celui du bidul source (pas 60)
        assert config.numero != 60

    def test_load_bidul_6_paysage(self):
        # Bidul 6 a un texte en paysage avec 2 colonnes
        config = load_section_config(6)
        assert config is not None
        assert config.page2 is not None
        assert config.page2.orientation_texte == Orientation.PAYSAGE
        assert config.page2.colonnes_par_section == 2

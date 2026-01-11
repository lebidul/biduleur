"""Tests pour le module svg_template."""

import pytest
import tempfile
from pathlib import Path

from core.svg_template import (
    ExtractionZone,
    SVGTemplate,
    SVGTemplateLoader,
    SVGTemplateGenerator,
    SVGTemplateManager,
    A4_WIDTH_PX,
    A4_HEIGHT_PX,
)


class TestExtractionZone:
    """Tests pour la dataclass ExtractionZone."""

    def test_creation_basic(self):
        zone = ExtractionZone(
            id='p2-s1-col1',
            x=100,
            y=200,
            width=300,
            height=400,
            order=1
        )
        assert zone.id == 'p2-s1-col1'
        assert zone.x == 100
        assert zone.y == 200
        assert zone.width == 300
        assert zone.height == 400
        assert zone.order == 1
        assert zone.exclude is False
        assert zone.rotation is None
        assert zone.page_num == 1

    def test_creation_with_all_params(self):
        zone = ExtractionZone(
            id='p2-exclude-header',
            x=0,
            y=0,
            width=1654,
            height=50,
            order=0,
            exclude=True,
            rotation=90,
            page_num=2
        )
        assert zone.exclude is True
        assert zone.rotation == 90
        assert zone.page_num == 2

    def test_invalid_dimensions_raises(self):
        with pytest.raises(ValueError):
            ExtractionZone(id='test', x=0, y=0, width=0, height=100)

        with pytest.raises(ValueError):
            ExtractionZone(id='test', x=0, y=0, width=100, height=-10)

    def test_negative_position_raises(self):
        with pytest.raises(ValueError):
            ExtractionZone(id='test', x=-10, y=0, width=100, height=100)

    def test_to_bbox(self):
        zone = ExtractionZone(id='test', x=100.5, y=200.7, width=300.3, height=400.9)
        bbox = zone.to_bbox()
        assert bbox == (100, 200, 400, 601)

    def test_to_dict(self):
        zone = ExtractionZone(
            id='p2-s1',
            x=100,
            y=200,
            width=300,
            height=400,
            order=2,
            exclude=False,
            rotation=90,
            page_num=2
        )
        d = zone.to_dict()
        assert d['id'] == 'p2-s1'
        assert d['x'] == 100
        assert d['y'] == 200
        assert d['width'] == 300
        assert d['height'] == 400
        assert d['order'] == 2
        assert d['exclude'] is False
        assert d['rotation'] == 90
        assert d['page_num'] == 2


class TestSVGTemplate:
    """Tests pour la dataclass SVGTemplate."""

    def test_creation_default(self):
        template = SVGTemplate(numero=5)
        assert template.numero == 5
        assert template.viewbox_width == A4_WIDTH_PX
        assert template.viewbox_height == A4_HEIGHT_PX
        assert template.orientation_pdf == 'portrait'
        assert template.orientation_texte == 'portrait'
        assert template.zones == []

    def test_needs_rotation_same_orientation(self):
        template = SVGTemplate(
            numero=5,
            orientation_pdf='portrait',
            orientation_texte='portrait'
        )
        assert template.needs_rotation() is False

    def test_needs_rotation_different_orientation(self):
        template = SVGTemplate(
            numero=5,
            orientation_pdf='portrait',
            orientation_texte='paysage'
        )
        assert template.needs_rotation() is True

    def test_get_zones_for_page(self):
        template = SVGTemplate(numero=5)
        template.zones = [
            ExtractionZone(id='p1-s1', x=0, y=0, width=100, height=100, page_num=1, order=1),
            ExtractionZone(id='p2-s1', x=0, y=0, width=100, height=100, page_num=2, order=1),
            ExtractionZone(id='p2-s2', x=100, y=0, width=100, height=100, page_num=2, order=2),
            ExtractionZone(id='p2-exclude', x=0, y=0, width=50, height=50, page_num=2, exclude=True),
        ]

        page1_zones = template.get_zones_for_page(1)
        assert len(page1_zones) == 1
        assert page1_zones[0].id == 'p1-s1'

        page2_zones = template.get_zones_for_page(2)
        assert len(page2_zones) == 2
        assert page2_zones[0].id == 'p2-s1'
        assert page2_zones[1].id == 'p2-s2'

    def test_get_exclusion_zones(self):
        template = SVGTemplate(numero=5)
        template.zones = [
            ExtractionZone(id='p2-s1', x=0, y=0, width=100, height=100, page_num=2),
            ExtractionZone(id='p2-exclude', x=0, y=0, width=50, height=50, page_num=2, exclude=True),
        ]

        exclusions = template.get_exclusion_zones(2)
        assert len(exclusions) == 1
        assert exclusions[0].id == 'p2-exclude'

    def test_get_all_page_nums(self):
        template = SVGTemplate(numero=5)
        template.zones = [
            ExtractionZone(id='p1-s1', x=0, y=0, width=100, height=100, page_num=1),
            ExtractionZone(id='p2-s1', x=0, y=0, width=100, height=100, page_num=2),
            ExtractionZone(id='p3-s1', x=0, y=0, width=100, height=100, page_num=3),
        ]

        pages = template.get_all_page_nums()
        assert pages == [1, 2, 3]


class TestSVGTemplateLoader:
    """Tests pour SVGTemplateLoader."""

    def test_load_valid_svg(self):
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1654 2339" xmlns="http://www.w3.org/2000/svg">
  <metadata>
    <bidul numero="5" orientation_pdf="portrait" orientation_texte="paysage"/>
  </metadata>
  <g id="page-2">
    <rect id="p2-s1-col1" x="100" y="200" width="300" height="400"
          data-order="1"/>
    <rect id="p2-s1-col2" x="500" y="200" width="300" height="400"
          data-order="2"/>
  </g>
</svg>'''

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a filename with the bidul number pattern
            svg_path = Path(tmpdir) / 'bidul_005.svg'
            svg_path.write_text(svg_content, encoding='utf-8')

            template = SVGTemplateLoader.load(svg_path)

            assert template is not None
            assert template.numero == 5  # Extracted from filename
            assert template.viewbox_width == 1654
            assert template.viewbox_height == 2339
            assert len(template.zones) == 2

            zone1 = next(z for z in template.zones if z.id == 'p2-s1-col1')
            assert zone1.x == 100
            assert zone1.y == 200
            assert zone1.width == 300
            assert zone1.height == 400
            assert zone1.order == 1

    def test_load_nonexistent_file(self):
        template = SVGTemplateLoader.load(Path('/nonexistent/file.svg'))
        assert template is None

    def test_load_svg_with_exclude(self):
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1654 2339" xmlns="http://www.w3.org/2000/svg">
  <rect id="p2-exclude-header" x="0" y="0" width="1654" height="50"
        data-exclude="true" data-order="0"/>
</svg>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8') as f:
            f.write(svg_content)
            svg_path = Path(f.name)

        try:
            template = SVGTemplateLoader.load(svg_path)
            assert len(template.zones) == 1
            assert template.zones[0].exclude is True
        finally:
            svg_path.unlink()

    def test_extract_page_num_from_id(self):
        # Test différents formats d'ID
        assert SVGTemplateLoader._extract_page_num('p2-s1-col1', None) == 2
        assert SVGTemplateLoader._extract_page_num('p1-s3', None) == 1
        assert SVGTemplateLoader._extract_page_num('page-3-zone', None) == 3
        assert SVGTemplateLoader._extract_page_num('unknown-format', None) == 1


class TestSVGTemplateGenerator:
    """Tests pour SVGTemplateGenerator."""

    def test_generate_from_config_portrait(self):
        from core.section_extractor import BidulSectionConfig, PageSectionConfig, Section, Orientation

        page_config = PageSectionConfig(
            orientation_pdf=Orientation.PORTRAIT,
            orientation_texte=Orientation.PORTRAIT,
            sections_utiles=[Section.S1, Section.S2, Section.S3, Section.S4],
            colonnes_par_section=1
        )
        config = BidulSectionConfig(
            numero=132,
            page2=page_config
        )

        generator = SVGTemplateGenerator()
        template = generator.generate_from_config(config)

        assert template.numero == 132
        assert template.orientation_pdf == 'portrait'
        assert template.orientation_texte == 'portrait'
        assert len(template.zones) == 4  # 4 sections

    def test_generate_from_config_paysage_2col(self):
        from core.section_extractor import BidulSectionConfig, PageSectionConfig, Section, Orientation

        page_config = PageSectionConfig(
            orientation_pdf=Orientation.PORTRAIT,
            orientation_texte=Orientation.PAYSAGE,
            sections_utiles=[Section.S1, Section.S2, Section.S3, Section.S4],
            colonnes_par_section=2
        )
        config = BidulSectionConfig(
            numero=5,
            page2=page_config
        )

        generator = SVGTemplateGenerator()
        template = generator.generate_from_config(config)

        assert template.numero == 5
        assert template.orientation_texte == 'paysage'
        assert len(template.zones) == 8  # 4 sections x 2 colonnes

    def test_to_svg_string(self):
        from core.section_extractor import BidulSectionConfig, PageSectionConfig, Section, Orientation

        page_config = PageSectionConfig(
            orientation_pdf=Orientation.PORTRAIT,
            orientation_texte=Orientation.PORTRAIT,
            sections_utiles=[Section.S1],
            colonnes_par_section=1
        )
        config = BidulSectionConfig(
            numero=100,
            page2=page_config
        )

        generator = SVGTemplateGenerator()
        template = generator.generate_from_config(config)
        svg_string = generator.to_svg_string(template)

        assert '<?xml version="1.0"' in svg_string
        assert 'viewBox="0 0' in svg_string
        assert '<metadata>' in svg_string
        assert 'bidul numero="100"' in svg_string
        assert '<rect' in svg_string

    def test_save_and_reload(self):
        from core.section_extractor import BidulSectionConfig, PageSectionConfig, Section, Orientation

        page_config = PageSectionConfig(
            orientation_pdf=Orientation.PORTRAIT,
            orientation_texte=Orientation.PORTRAIT,
            sections_utiles=[Section.S1, Section.S3],
            colonnes_par_section=1
        )
        config = BidulSectionConfig(
            numero=99,
            page2=page_config
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'test_bidul_099.svg'

            generator = SVGTemplateGenerator()
            template = generator.generate_from_config(config)

            assert generator.save(template, output_path)
            assert output_path.exists()

            # Recharger et vérifier
            reloaded = SVGTemplateLoader.load(output_path)
            assert reloaded is not None
            assert reloaded.numero == 99
            assert len(reloaded.zones) == 2


class TestSVGTemplateManager:
    """Tests pour SVGTemplateManager."""

    def test_manager_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SVGTemplateManager(
                templates_dir=Path(tmpdir),
                csv_path=Path(tmpdir) / 'nonexistent.csv'
            )
            assert manager.templates_dir == Path(tmpdir)

    def test_get_template_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SVGTemplateManager(
                templates_dir=Path(tmpdir),
                csv_path=Path(tmpdir) / 'nonexistent.csv'
            )
            template = manager.get_template(999)
            assert template is None

    def test_get_template_from_file(self):
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1654 2339" xmlns="http://www.w3.org/2000/svg">
  <metadata><bidul numero="42"/></metadata>
  <rect id="p2-s1" x="100" y="100" width="200" height="200" data-order="1"/>
</svg>'''

        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)
            svg_path = templates_dir / 'bidul_042.svg'
            svg_path.write_text(svg_content, encoding='utf-8')

            manager = SVGTemplateManager(
                templates_dir=templates_dir,
                csv_path=Path(tmpdir) / 'nonexistent.csv'
            )

            template = manager.get_template(42)
            assert template is not None
            assert template.numero == 42
            assert len(template.zones) == 1

    def test_has_template(self):
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1654 2339" xmlns="http://www.w3.org/2000/svg">
  <rect id="p2-s1" x="100" y="100" width="200" height="200" data-order="1"/>
</svg>'''

        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)
            svg_path = templates_dir / 'bidul_007.svg'
            svg_path.write_text(svg_content, encoding='utf-8')

            manager = SVGTemplateManager(
                templates_dir=templates_dir,
                csv_path=Path(tmpdir) / 'nonexistent.csv'
            )

            assert manager.has_template(7) is True
            assert manager.has_template(999) is False

    def test_list_templates(self):
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1654 2339" xmlns="http://www.w3.org/2000/svg">
  <rect id="test" x="0" y="0" width="100" height="100" data-order="1"/>
</svg>'''

        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)

            # Créer quelques templates
            for num in [5, 10, 15]:
                svg_path = templates_dir / f'bidul_{num:03d}.svg'
                svg_path.write_text(svg_content, encoding='utf-8')

            # Créer un fichier qui ne match pas le pattern
            (templates_dir / 'other.svg').write_text(svg_content, encoding='utf-8')

            manager = SVGTemplateManager(
                templates_dir=templates_dir,
                csv_path=Path(tmpdir) / 'nonexistent.csv'
            )

            templates = manager.list_templates()
            assert len(templates) == 3
            assert templates[0][0] == 5
            assert templates[1][0] == 10
            assert templates[2][0] == 15

    def test_clear_cache(self):
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1654 2339" xmlns="http://www.w3.org/2000/svg">
  <rect id="p2-s1" x="100" y="100" width="200" height="200" data-order="1"/>
</svg>'''

        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)
            svg_path = templates_dir / 'bidul_001.svg'
            svg_path.write_text(svg_content, encoding='utf-8')

            manager = SVGTemplateManager(
                templates_dir=templates_dir,
                csv_path=Path(tmpdir) / 'nonexistent.csv'
            )

            # Charger et cacher
            template1 = manager.get_template(1)
            assert template1 is not None
            assert 1 in manager._cache

            # Vider le cache
            manager.clear_cache()
            assert 1 not in manager._cache


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

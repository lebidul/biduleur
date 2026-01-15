"""
Module de gestion des templates SVG pour les zones d'extraction OCR.

Un template SVG définit précisément les zones de texte à extraire d'une page PDF.
Les templates peuvent être :
1. Générés automatiquement depuis la config CSV existante
2. Édités manuellement dans un éditeur SVG (Inkscape, navigateur)
3. Utilisés en priorité lors de l'extraction OCR

Format SVG:
    - viewBox correspondant aux dimensions de l'image PDF (pixels à 200 DPI)
    - Éléments <rect> pour définir les zones d'extraction
    - Attributs data-* pour l'ordre de lecture et les exclusions

Conventions de nommage des IDs:
    - page-{n}: Groupe de page
    - p{n}-s{s}: Groupe de section (S1, S2, S3, S4)
    - p{n}-s{s}-col{c}: Zone de colonne
    - p{n}-exclude-{name}: Zone à exclure
"""

import base64
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Namespace SVG
SVG_NS = 'http://www.w3.org/2000/svg'
NAMESPACES = {'svg': SVG_NS}

# Résolution standard pour les templates (doit correspondre à l'OCR)
DEFAULT_DPI = 200

# Dimensions A4 en pixels à 200 DPI
A4_WIDTH_PX = int(210 * DEFAULT_DPI / 25.4)   # ~1654 px
A4_HEIGHT_PX = int(297 * DEFAULT_DPI / 25.4)  # ~2339 px


@dataclass
class ExtractionZone:
    """
    Zone d'extraction de texte.

    Définit une région rectangulaire dans une image de page PDF
    où le texte doit être extrait via OCR.

    Attributs:
        id: Identifiant unique de la zone (ex: 'p2-s1-col1')
        x: Position X en pixels (depuis le bord gauche)
        y: Position Y en pixels (depuis le bord haut)
        width: Largeur en pixels
        height: Hauteur en pixels
        order: Ordre de lecture (1, 2, 3...) - les zones sont triées par cet ordre
        exclude: Si True, cette zone est ignorée (headers, logos, etc.)
        rotation: Rotation à appliquer avant OCR (degrés, généralement 0 ou 90)
        page_num: Numéro de la page (1-indexed)
    """
    id: str
    x: float
    y: float
    width: float
    height: float
    order: int = 1
    exclude: bool = False
    rotation: Optional[int] = None
    page_num: int = 1

    def __post_init__(self):
        """Validation des valeurs."""
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Zone {self.id}: width et height doivent être > 0")
        if self.x < 0 or self.y < 0:
            raise ValueError(f"Zone {self.id}: x et y doivent être >= 0")

    def to_bbox(self) -> tuple[int, int, int, int]:
        """
        Retourne les coordonnées comme bounding box (x1, y1, x2, y2).

        Returns:
            Tuple (x_start, y_start, x_end, y_end) en pixels entiers
        """
        return (
            int(self.x),
            int(self.y),
            int(self.x + self.width),
            int(self.y + self.height)
        )

    def to_dict(self) -> dict:
        """Convertit en dictionnaire."""
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'order': self.order,
            'exclude': self.exclude,
            'rotation': self.rotation,
            'page_num': self.page_num,
        }


@dataclass
class SVGTemplate:
    """
    Template SVG complet pour un Bidul.

    Contient toutes les zones d'extraction pour toutes les pages.

    Attributs:
        numero: Numéro du Bidul
        viewbox_width: Largeur du viewBox SVG (pixels)
        viewbox_height: Hauteur du viewBox SVG (pixels)
        orientation_pdf: Orientation du PDF ('portrait' ou 'paysage')
        orientation_texte: Orientation du texte ('portrait' ou 'paysage')
        zones: Liste des zones d'extraction
        source_path: Chemin du fichier SVG (si chargé depuis un fichier)
    """
    numero: int
    viewbox_width: int = A4_WIDTH_PX
    viewbox_height: int = A4_HEIGHT_PX
    orientation_pdf: str = 'portrait'
    orientation_texte: str = 'portrait'
    zones: list[ExtractionZone] = field(default_factory=list)
    source_path: Optional[Path] = None

    def get_zones_for_page(self, page_num: int) -> list[ExtractionZone]:
        """
        Retourne les zones d'extraction pour une page, triées par ordre.

        Args:
            page_num: Numéro de la page (1-indexed)

        Returns:
            Liste des zones triées par 'order', excluant les zones avec exclude=True
        """
        page_zones = [z for z in self.zones if z.page_num == page_num and not z.exclude]
        return sorted(page_zones, key=lambda z: z.order)

    def get_exclusion_zones(self, page_num: int) -> list[ExtractionZone]:
        """Retourne les zones d'exclusion pour une page."""
        return [z for z in self.zones if z.page_num == page_num and z.exclude]

    def get_all_page_nums(self) -> list[int]:
        """Retourne la liste des numéros de pages présentes dans le template."""
        return sorted(set(z.page_num for z in self.zones))

    def needs_rotation(self) -> bool:
        """True si une rotation est nécessaire (PDF et texte ont des orientations différentes)."""
        return self.orientation_pdf != self.orientation_texte


class SVGTemplateLoader:
    """
    Charge et parse des templates SVG.

    Lit un fichier SVG et extrait les zones d'extraction définies par des
    éléments <rect> avec les attributs appropriés.
    """

    @staticmethod
    def load(svg_path: Path) -> Optional[SVGTemplate]:
        """
        Charge un template SVG depuis un fichier.

        Args:
            svg_path: Chemin vers le fichier SVG

        Returns:
            SVGTemplate chargé ou None si erreur
        """
        if not svg_path.exists():
            logger.warning(f"Template SVG non trouvé: {svg_path}")
            return None

        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()

            # Extraire le viewBox
            viewbox = root.get('viewBox', '')
            parts = viewbox.split()
            if len(parts) >= 4:
                vb_width = float(parts[2])
                vb_height = float(parts[3])
            else:
                vb_width = A4_WIDTH_PX
                vb_height = A4_HEIGHT_PX

            # Extraire les métadonnées
            numero = 0
            orientation_pdf = 'portrait'
            orientation_texte = 'portrait'

            metadata = root.find('.//metadata', NAMESPACES) or root.find('.//metadata')
            if metadata is not None:
                bidul_elem = metadata.find('bidul')
                if bidul_elem is not None:
                    numero = int(bidul_elem.get('numero', 0))
                    orientation_pdf = bidul_elem.get('orientation_pdf', 'portrait')
                    orientation_texte = bidul_elem.get('orientation_texte', 'portrait')

            # Si numero non trouvé, essayer de le déduire du nom de fichier
            if numero == 0:
                match = re.search(r'bidul_(\d+)', svg_path.stem)
                if match:
                    numero = int(match.group(1))

            template = SVGTemplate(
                numero=numero,
                viewbox_width=int(vb_width),
                viewbox_height=int(vb_height),
                orientation_pdf=orientation_pdf,
                orientation_texte=orientation_texte,
                source_path=svg_path,
            )

            # Extraire les zones des rectangles
            zones = SVGTemplateLoader._extract_zones(root)
            template.zones = zones

            logger.info(f"Template SVG chargé: {svg_path.name}, {len(zones)} zones")
            return template

        except ET.ParseError as e:
            logger.error(f"Erreur parsing SVG {svg_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur chargement template {svg_path}: {e}")
            return None

    @staticmethod
    def _extract_zones(root: ET.Element) -> list[ExtractionZone]:
        """
        Extrait toutes les zones d'extraction depuis l'arbre SVG.

        Parcourt récursivement l'arbre en tenant compte des transformations
        des groupes parents.
        """
        zones = []

        # Chercher tous les <rect> avec un id valide
        # Supporter les deux formats: avec et sans namespace
        for rect in root.iter():
            tag = rect.tag.split('}')[-1] if '}' in rect.tag else rect.tag
            if tag != 'rect':
                continue

            rect_id = rect.get('id', '')
            if not rect_id:
                continue

            # Parser les coordonnées
            try:
                x = float(rect.get('x', 0))
                y = float(rect.get('y', 0))
                width = float(rect.get('width', 0))
                height = float(rect.get('height', 0))
            except (TypeError, ValueError):
                logger.warning(f"Zone {rect_id}: coordonnées invalides")
                continue

            if width <= 0 or height <= 0:
                continue

            # Extraire les attributs data-*
            order = int(rect.get('data-order', 1))
            exclude = rect.get('data-exclude', '').lower() == 'true'
            rotation_str = rect.get('data-rotation')
            rotation = int(rotation_str) if rotation_str else None

            # Déterminer le numéro de page depuis l'ID
            page_num = SVGTemplateLoader._extract_page_num(rect_id, rect)

            # Appliquer les transformations des parents
            x, y = SVGTemplateLoader._apply_parent_transforms(rect, x, y)

            zone = ExtractionZone(
                id=rect_id,
                x=x,
                y=y,
                width=width,
                height=height,
                order=order,
                exclude=exclude,
                rotation=rotation,
                page_num=page_num,
            )
            zones.append(zone)

        return zones

    @staticmethod
    def _extract_page_num(rect_id: str, element: ET.Element) -> int:
        """Extrait le numéro de page depuis l'ID ou le groupe parent."""
        # Pattern: p{n}-... ou page-{n}
        match = re.search(r'p(\d+)-|page-(\d+)', rect_id)
        if match:
            return int(match.group(1) or match.group(2))

        # Chercher dans les parents
        parent = element
        while parent is not None:
            parent_id = parent.get('id', '')
            match = re.search(r'page-(\d+)', parent_id)
            if match:
                return int(match.group(1))
            # Note: ElementTree ne supporte pas getparent(), on retourne 1 par défaut
            break

        return 1

    @staticmethod
    def _apply_parent_transforms(element: ET.Element, x: float, y: float) -> tuple[float, float]:
        """
        Applique les transformations des groupes parents.

        Note: Implémentation simplifiée supportant uniquement translate et rotate.
        """
        # Note: ElementTree ne garde pas de référence parent, donc on ne peut pas
        # remonter l'arbre facilement. Pour une implémentation complète,
        # il faudrait utiliser lxml ou stocker les relations parent/enfant.
        #
        # Pour l'instant, on suppose que les coordonnées dans les <rect>
        # sont déjà absolues ou que les transformations sont gérées à la génération.
        return x, y


class SVGTemplateGenerator:
    """
    Génère des templates SVG depuis la configuration CSV existante.

    Convertit une BidulSectionConfig (sections A6 + colonnes) en template SVG
    avec des zones précises.
    """

    # Coordonnées relatives des sections A6 (% de la page)
    SECTION_COORDS = {
        'S1': (0.0, 0.0, 0.5, 0.5),   # Haut-gauche
        'S2': (0.5, 0.0, 1.0, 0.5),   # Haut-droite
        'S3': (0.0, 0.5, 0.5, 1.0),   # Bas-gauche
        'S4': (0.5, 0.5, 1.0, 1.0),   # Bas-droite
    }

    # Marge autour des sections (% de la taille)
    MARGIN_PERCENT = 0.02

    # Espace entre colonnes (gutter) en % de la largeur
    GUTTER_PERCENT = 0.03

    def __init__(self, dpi: int = DEFAULT_DPI):
        """
        Args:
            dpi: Résolution pour les dimensions en pixels
        """
        self.dpi = dpi
        # Dimensions page A4 en pixels
        self.page_width = int(210 * dpi / 25.4)
        self.page_height = int(297 * dpi / 25.4)

    def generate_from_config(self, config) -> SVGTemplate:
        """
        Génère un template SVG depuis une BidulSectionConfig.

        Args:
            config: BidulSectionConfig depuis section_extractor.py

        Returns:
            SVGTemplate avec les zones correspondantes
        """
        from .section_extractor import BidulSectionConfig, Orientation

        if not isinstance(config, BidulSectionConfig):
            raise TypeError(f"Expected BidulSectionConfig, got {type(config)}")

        # Déterminer les dimensions selon l'orientation du texte
        # (après rotation si nécessaire)
        orientation_texte = 'portrait'
        orientation_pdf = 'portrait'

        if config.page1:
            orientation_texte = config.page1.orientation_texte.value
            orientation_pdf = config.page1.orientation_pdf.value
        elif config.page2:
            orientation_texte = config.page2.orientation_texte.value
            orientation_pdf = config.page2.orientation_pdf.value

        # Dimensions du viewBox (après rotation si le texte est paysage)
        if orientation_texte == 'paysage':
            vb_width = self.page_height
            vb_height = self.page_width
        else:
            vb_width = self.page_width
            vb_height = self.page_height

        template = SVGTemplate(
            numero=config.numero,
            viewbox_width=vb_width,
            viewbox_height=vb_height,
            orientation_pdf=orientation_pdf,
            orientation_texte=orientation_texte,
        )

        order_counter = 1

        # Générer les zones pour page 1
        if config.page1 and config.page1.sections_utiles:
            zones, order_counter = self._generate_page_zones(
                config.page1, 1, vb_width, vb_height, order_counter
            )
            template.zones.extend(zones)

        # Générer les zones pour page 2
        if config.page2 and config.page2.sections_utiles:
            zones, order_counter = self._generate_page_zones(
                config.page2, 2, vb_width, vb_height, order_counter
            )
            template.zones.extend(zones)

        return template

    def _generate_page_zones(
        self,
        page_config,
        page_num: int,
        page_width: int,
        page_height: int,
        start_order: int
    ) -> tuple[list[ExtractionZone], int]:
        """
        Génère les zones pour une page.

        Args:
            page_config: PageSectionConfig
            page_num: Numéro de la page
            page_width: Largeur en pixels (après rotation éventuelle)
            page_height: Hauteur en pixels (après rotation éventuelle)
            start_order: Ordre de départ pour les zones

        Returns:
            (liste de zones, prochain ordre)
        """
        from .section_extractor import Orientation

        zones = []
        order = start_order

        # Obtenir l'ordre de lecture des sections
        section_order = page_config.get_section_order()

        # Filtrer pour ne garder que les sections utiles
        sections_to_process = [
            s for s in section_order
            if s in page_config.sections_utiles
        ]

        num_colonnes = page_config.colonnes_par_section

        for section in sections_to_process:
            section_name = section.value
            coords = self.SECTION_COORDS[section_name]

            # Calculer les coordonnées en pixels
            x_start = int(coords[0] * page_width)
            y_start = int(coords[1] * page_height)
            x_end = int(coords[2] * page_width)
            y_end = int(coords[3] * page_height)

            # Appliquer la marge
            margin_x = int(self.MARGIN_PERCENT * page_width)
            margin_y = int(self.MARGIN_PERCENT * page_height)

            x_start = max(0, x_start - margin_x)
            y_start = max(0, y_start - margin_y)
            x_end = min(page_width, x_end + margin_x)
            y_end = min(page_height, y_end + margin_y)

            section_width = x_end - x_start
            section_height = y_end - y_start

            if num_colonnes > 1:
                # Diviser en colonnes
                col_width = section_width // num_colonnes
                gutter = int(section_width * self.GUTTER_PERCENT)

                for col in range(num_colonnes):
                    # Bornes de la colonne
                    col_x_start = x_start + col * col_width
                    col_x_end = col_x_start + col_width

                    # Rogner le gutter
                    if col > 0:
                        col_x_start += gutter
                    if col < num_colonnes - 1:
                        col_x_end -= gutter

                    zone = ExtractionZone(
                        id=f"p{page_num}-{section_name.lower()}-col{col + 1}",
                        x=col_x_start,
                        y=y_start,
                        width=col_x_end - col_x_start,
                        height=section_height,
                        order=order,
                        page_num=page_num,
                    )
                    zones.append(zone)
                    order += 1
            else:
                # Section entière comme une seule zone
                zone = ExtractionZone(
                    id=f"p{page_num}-{section_name.lower()}",
                    x=x_start,
                    y=y_start,
                    width=section_width,
                    height=section_height,
                    order=order,
                    page_num=page_num,
                )
                zones.append(zone)
                order += 1

        return zones, order

    def _extract_pdf_pages_as_base64(
        self,
        pdf_path: Path,
        template: SVGTemplate,
        max_pages: int = 2,
        section_config=None
    ) -> dict[int, str]:
        """
        Extrait les pages PDF comme images base64.

        Args:
            pdf_path: Chemin vers le fichier PDF
            template: SVGTemplate pour déterminer l'orientation
            max_pages: Nombre maximum de pages à extraire
            section_config: BidulSectionConfig pour rotation par page

        Returns:
            Dict {page_num: base64_string}
        """
        try:
            from pdf2image import convert_from_path
            from PIL import Image
        except ImportError:
            logger.warning("pdf2image ou Pillow non disponible, pas d'image de fond")
            return {}

        result = {}

        try:
            # Convertir les pages PDF en images à la résolution du template
            images = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                first_page=1,
                last_page=max_pages
            )

            for idx, img in enumerate(images):
                page_num = idx + 1

                # Déterminer si cette page nécessite une rotation
                needs_rotation = False
                if section_config:
                    # Vérifier la config de la page spécifique
                    page_config = section_config.get_page_config(page_num)
                    if page_config:
                        needs_rotation = page_config.needs_rotation()
                        if needs_rotation:
                            logger.debug(f"Page {page_num}: rotation nécessaire "
                                       f"(PDF={page_config.orientation_pdf.value}, "
                                       f"texte={page_config.orientation_texte.value})")
                else:
                    # Fallback sur la rotation globale du template
                    needs_rotation = template.needs_rotation()

                # Appliquer la rotation si nécessaire
                # PDF portrait + texte paysage → rotation 90° horaire (-90° en PIL)
                if needs_rotation:
                    img = img.rotate(-90, expand=True)
                    logger.debug(f"Page {page_num}: rotation 90° horaire appliquée")

                # Redimensionner à la taille du viewBox
                img = img.resize(
                    (template.viewbox_width, template.viewbox_height),
                    Image.Resampling.LANCZOS
                )

                # Convertir en base64
                buffer = BytesIO()
                img.save(buffer, format='PNG', optimize=True)
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                result[page_num] = img_base64

                logger.debug(f"Page {page_num} extraite ({len(img_base64)} chars)")

        except Exception as e:
            logger.error(f"Erreur extraction pages PDF {pdf_path}: {e}")

        return result

    def to_svg_string(
        self,
        template: SVGTemplate,
        pdf_path: Optional[Path] = None,
        include_background: bool = False,
        section_config=None
    ) -> str:
        """
        Génère le contenu SVG sous forme de chaîne.

        Args:
            template: SVGTemplate à convertir
            pdf_path: Chemin vers le PDF source (pour intégrer les images de fond)
            include_background: Si True, intègre les images PDF en arrière-plan
            section_config: BidulSectionConfig pour rotation par page

        Returns:
            Chaîne XML du SVG
        """
        # Récupérer les images de fond si demandé
        background_images = {}
        if include_background and pdf_path and pdf_path.exists():
            background_images = self._extract_pdf_pages_as_base64(
                pdf_path, template, max_pages=2, section_config=section_config
            )

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg viewBox="0 0 {template.viewbox_width} {template.viewbox_height}" xmlns="{SVG_NS}" xmlns:xlink="http://www.w3.org/1999/xlink">',
            '  <metadata>',
            f'    <bidul numero="{template.numero}" '
            f'orientation_pdf="{template.orientation_pdf}" '
            f'orientation_texte="{template.orientation_texte}"/>',
            '  </metadata>',
            '',
        ]

        # Grouper les zones par page
        pages = {}
        for zone in template.zones:
            if zone.page_num not in pages:
                pages[zone.page_num] = []
            pages[zone.page_num].append(zone)

        # Couleurs pour le rendu visuel (contour uniquement, pas de fond)
        colors = {
            'col1': ('none', 'red'),
            'col2': ('none', 'blue'),
            'default': ('none', 'green'),
            'exclude': ('none', 'gray'),
        }

        for page_num in sorted(pages.keys()):
            page_zones = pages[page_num]

            # Note sur la rotation dans les métadonnées
            rotation_note = ""
            if template.needs_rotation():
                rotation_note = f' data-rotation="90"'

            lines.append(f'  <!-- Page {page_num} -->')
            lines.append(f'  <g id="page-{page_num}"{rotation_note}>')

            # Ajouter l'image de fond si disponible
            if page_num in background_images:
                img_data = background_images[page_num]
                lines.append(f'    <image id="bg-page-{page_num}" '
                           f'x="0" y="0" '
                           f'width="{template.viewbox_width}" height="{template.viewbox_height}" '
                           f'xlink:href="data:image/png;base64,{img_data}" '
                           f'preserveAspectRatio="none" opacity="1"/>')

            # Grouper par section
            sections = {}
            for zone in page_zones:
                # Extraire le nom de section de l'ID (ex: p2-s1-col1 -> s1)
                match = re.search(r'p\d+-([^-]+)', zone.id)
                section_name = match.group(1) if match else 'other'
                if section_name not in sections:
                    sections[section_name] = []
                sections[section_name].append(zone)

            for section_name in sorted(sections.keys()):
                section_zones = sections[section_name]

                if len(section_zones) > 1 or not section_name.startswith('exclude'):
                    lines.append(f'    <g id="p{page_num}-{section_name}">')
                    indent = '      '
                else:
                    indent = '    '

                for zone in sorted(section_zones, key=lambda z: z.order):
                    # Choisir la couleur
                    if zone.exclude:
                        fill, stroke = colors['exclude']
                    elif 'col1' in zone.id:
                        fill, stroke = colors['col1']
                    elif 'col2' in zone.id:
                        fill, stroke = colors['col2']
                    else:
                        fill, stroke = colors['default']

                    # Attributs data-*
                    data_attrs = f'data-order="{zone.order}"'
                    if zone.exclude:
                        data_attrs += ' data-exclude="true"'
                    if zone.rotation:
                        data_attrs += f' data-rotation="{zone.rotation}"'

                    lines.append(
                        f'{indent}<rect id="{zone.id}" '
                        f'x="{zone.x:.0f}" y="{zone.y:.0f}" '
                        f'width="{zone.width:.0f}" height="{zone.height:.0f}" '
                        f'fill="{fill}" stroke="{stroke}" stroke-width="2" '
                        f'{data_attrs}/>'
                    )

                if len(section_zones) > 1 or not section_name.startswith('exclude'):
                    lines.append('    </g>')

            lines.append('  </g>')
            lines.append('')

        lines.append('</svg>')
        return '\n'.join(lines)

    def save(
        self,
        template: SVGTemplate,
        output_path: Path,
        pdf_path: Optional[Path] = None,
        include_background: bool = False,
        section_config=None
    ) -> bool:
        """
        Sauvegarde un template SVG dans un fichier.

        Args:
            template: Template à sauvegarder
            output_path: Chemin du fichier de sortie
            pdf_path: Chemin vers le PDF source (pour images de fond)
            include_background: Si True, intègre les images PDF en arrière-plan
            section_config: BidulSectionConfig pour rotation par page

        Returns:
            True si succès
        """
        try:
            svg_content = self.to_svg_string(template, pdf_path, include_background, section_config)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(svg_content, encoding='utf-8')
            logger.info(f"Template SVG sauvegardé: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde template {output_path}: {e}")
            return False


class SVGTemplateManager:
    """
    Gestionnaire de templates SVG.

    Gère le chargement des templates avec une hiérarchie de priorité:
    1. Template spécifique: corpus/templates/bidul_{numero}.svg
    2. Template référencé dans le CSV: colonne svg_template
    3. Aucun template: fallback au calcul dynamique
    """

    def __init__(self, templates_dir: Optional[Path] = None, csv_path: Optional[Path] = None):
        """
        Args:
            templates_dir: Répertoire des templates SVG
            csv_path: Chemin vers biduls.description.csv
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent.parent / 'corpus' / 'templates'
        if csv_path is None:
            csv_path = Path(__file__).parent.parent / 'corpus' / 'biduls.description.csv'

        self.templates_dir = templates_dir
        self.csv_path = csv_path
        self._cache: dict[int, Optional[SVGTemplate]] = {}
        self._csv_templates: dict[int, str] = {}
        self._load_csv_templates()

    def _load_csv_templates(self):
        """Charge les références de templates depuis le CSV."""
        if not self.csv_path.exists():
            return

        import csv

        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        for encoding in encodings:
            try:
                with open(self.csv_path, 'r', encoding=encoding) as f:
                    # Filtrer les commentaires
                    lines = [line for line in f if not line.strip().startswith('#')]

                from io import StringIO
                reader = csv.DictReader(StringIO(''.join(lines)))

                for row in reader:
                    # Extraire le numéro
                    numero = 0
                    for key in ['numero', 'numéros', 'numeros']:
                        if key in row:
                            try:
                                numero = int(row[key])
                                break
                            except (ValueError, TypeError):
                                continue

                    if numero == 0:
                        continue

                    # Extraire le template SVG
                    svg_template = (row.get('svg_template') or '').strip()
                    if svg_template:
                        self._csv_templates[numero] = svg_template

                logger.debug(f"Chargé {len(self._csv_templates)} références templates depuis CSV")
                return

            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Erreur lecture CSV templates: {e}")
                return

    def get_template(self, numero: int) -> Optional[SVGTemplate]:
        """
        Récupère le template SVG pour un numéro de Bidul.

        Hiérarchie de priorité:
        1. Template spécifique: bidul_{numero}.svg
        2. Template référencé dans le CSV
        3. None (pas de template, utiliser calcul dynamique)

        Args:
            numero: Numéro du Bidul

        Returns:
            SVGTemplate ou None
        """
        # Vérifier le cache
        if numero in self._cache:
            return self._cache[numero]

        template = None

        # 1. Chercher un template spécifique
        specific_path = self.templates_dir / f'bidul_{numero:03d}.svg'
        if specific_path.exists():
            template = SVGTemplateLoader.load(specific_path)
            if template:
                logger.debug(f"Bidul {numero}: template spécifique chargé")

        # 2. Chercher via référence CSV
        if template is None and numero in self._csv_templates:
            csv_template_name = self._csv_templates[numero]
            csv_template_path = self.templates_dir / csv_template_name
            if csv_template_path.exists():
                template = SVGTemplateLoader.load(csv_template_path)
                if template:
                    template.numero = numero  # S'assurer que le numero est correct
                    logger.debug(f"Bidul {numero}: template CSV '{csv_template_name}' chargé")

        # Mettre en cache
        self._cache[numero] = template
        return template

    def has_template(self, numero: int) -> bool:
        """Vérifie si un template existe pour un numéro."""
        return self.get_template(numero) is not None

    def clear_cache(self):
        """Vide le cache des templates."""
        self._cache.clear()

    def list_templates(self) -> list[tuple[int, Path]]:
        """
        Liste tous les templates disponibles.

        Returns:
            Liste de tuples (numero, chemin) triée par numéro
        """
        templates = []

        if not self.templates_dir.exists():
            return templates

        for svg_file in self.templates_dir.glob('bidul_*.svg'):
            match = re.search(r'bidul_(\d+)', svg_file.stem)
            if match:
                numero = int(match.group(1))
                templates.append((numero, svg_file))

        return sorted(templates, key=lambda x: x[0])


# Singleton du manager
_template_manager: Optional[SVGTemplateManager] = None


def get_template_manager() -> SVGTemplateManager:
    """Retourne le gestionnaire de templates (singleton)."""
    global _template_manager
    if _template_manager is None:
        _template_manager = SVGTemplateManager()
    return _template_manager


def load_svg_template(numero: int) -> Optional[SVGTemplate]:
    """
    Charge le template SVG pour un Bidul.

    Fonction utilitaire qui utilise le singleton SVGTemplateManager.

    Args:
        numero: Numéro du Bidul

    Returns:
        SVGTemplate ou None si aucun template disponible
    """
    return get_template_manager().get_template(numero)

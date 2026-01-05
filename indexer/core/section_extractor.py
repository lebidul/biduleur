"""
Module d'extraction OCR par sections A6.

Une page A4 du Bidul est divisée en 4 sections A6:
┌───────┬───────┐
│  S1   │  S2   │  (haut)
├───────┼───────┤
│  S3   │  S4   │  (bas)
└───────┴───────┘

Chaque section peut contenir 1 ou 2 colonnes de texte.
L'orientation du texte peut différer de l'orientation du PDF.
"""

import csv
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class Orientation(Enum):
    """Orientation du PDF ou du texte."""
    PORTRAIT = 'portrait'
    PAYSAGE = 'paysage'


class Section(Enum):
    """Identifiants des 4 sections A6 d'une page A4."""
    S1 = 'S1'  # Haut-gauche
    S2 = 'S2'  # Haut-droite
    S3 = 'S3'  # Bas-gauche
    S4 = 'S4'  # Bas-droite


# Ordre de lecture des sections selon l'orientation du texte
SECTION_ORDER_PORTRAIT = [Section.S1, Section.S2, Section.S3, Section.S4]
SECTION_ORDER_PAYSAGE = [Section.S1, Section.S3, Section.S2, Section.S4]  # Lecture verticale puis horizontale


@dataclass
class PageSectionConfig:
    """Configuration d'une page pour l'extraction par sections."""
    orientation_pdf: Orientation = Orientation.PORTRAIT
    orientation_texte: Orientation = Orientation.PORTRAIT
    sections_utiles: list[Section] = field(default_factory=lambda: [Section.S1, Section.S2, Section.S3, Section.S4])
    colonnes_par_section: int = 1

    @classmethod
    def from_csv_row(cls, row: dict, page_num: int) -> Optional['PageSectionConfig']:
        """
        Crée une config de page depuis une ligne CSV.

        Args:
            row: Ligne du CSV biduls.description.csv
            page_num: Numéro de la page (1 ou 2)
        """
        prefix = f'page{page_num}.'

        # Vérifier si des colonnes sont définies pour cette page
        orientation_pdf_key = f'{prefix}orientation pdf'
        orientation_texte_key = f'{prefix}orientation texte'
        sections_key = f'{prefix}sections texte utile'
        colonnes_key = f'{prefix}colonne par section'

        # Si aucune colonne n'est définie, la page n'a pas de config
        has_config = any(row.get(k) for k in [orientation_pdf_key, sections_key])
        if not has_config:
            return None

        # Parser l'orientation
        orientation_pdf_str = (row.get(orientation_pdf_key) or 'portrait').lower().strip()
        orientation_texte_str = (row.get(orientation_texte_key) or 'portrait').lower().strip()

        orientation_pdf = Orientation.PAYSAGE if orientation_pdf_str == 'paysage' else Orientation.PORTRAIT
        orientation_texte = Orientation.PAYSAGE if orientation_texte_str == 'paysage' else Orientation.PORTRAIT

        # Parser les sections
        sections_str = row.get(sections_key, '') or ''
        sections = []
        for s in sections_str.split():
            s = s.strip().upper()
            if s in ['S1', 'S2', 'S3', 'S4']:
                sections.append(Section[s])

        if not sections:
            sections = [Section.S1, Section.S2, Section.S3, Section.S4]

        # Nombre de colonnes
        colonnes_str = row.get(colonnes_key, '1') or '1'
        try:
            colonnes = int(colonnes_str)
        except ValueError:
            colonnes = 1

        return cls(
            orientation_pdf=orientation_pdf,
            orientation_texte=orientation_texte,
            sections_utiles=sections,
            colonnes_par_section=colonnes
        )

    def needs_rotation(self) -> bool:
        """True si le texte nécessite une rotation pour être lu."""
        return self.orientation_texte == Orientation.PAYSAGE

    def get_section_order(self) -> list[Section]:
        """Retourne l'ordre de lecture des sections selon l'orientation du texte."""
        if self.orientation_texte == Orientation.PAYSAGE:
            return SECTION_ORDER_PAYSAGE
        return SECTION_ORDER_PORTRAIT


@dataclass
class BidulSectionConfig:
    """Configuration complète d'un Bidul pour l'extraction par sections."""
    numero: int
    type_source: str = 'scan'
    date_format: str = 'inline'
    page1: Optional[PageSectionConfig] = None
    page2: Optional[PageSectionConfig] = None
    pages_override: list[int] = field(default_factory=list)

    @classmethod
    def from_csv_row(cls, row: dict) -> Optional['BidulSectionConfig']:
        """Crée une config depuis une ligne du CSV biduls.description.csv."""
        # Extraire le numéro
        numero = 0
        for key in ['numéros', 'numeros', 'num\xe9ros', 'num\ufffdros']:
            if key in row:
                try:
                    numero = int(row[key])
                    break
                except (ValueError, TypeError):
                    continue

        if numero == 0:
            return None

        type_source = (row.get('scan/texte') or '').strip().lower()
        if not type_source:
            return None

        date_format = row.get('date', 'inline') or 'inline'

        # Parser pages_override
        pages_override = []
        override_str = row.get('pages_override', '') or ''
        if override_str:
            for p in override_str.split(','):
                try:
                    pages_override.append(int(p.strip()))
                except ValueError:
                    continue

        return cls(
            numero=numero,
            type_source=type_source,
            date_format=date_format,
            page1=PageSectionConfig.from_csv_row(row, 1),
            page2=PageSectionConfig.from_csv_row(row, 2),
            pages_override=pages_override
        )

    def is_scan(self) -> bool:
        """True si le Bidul est un scan (vs texte)."""
        return self.type_source == 'scan'

    def get_pages_to_process(self, num_pages: int) -> list[int]:
        """
        Détermine les pages à traiter pour un PDF.

        Logique:
        1. Si pages_override est défini, utiliser ces pages
        2. Si num_pages == 3, utiliser page 3 (résumé agenda)
        3. Sinon, utiliser les pages configurées (1, 2 ou les deux)
        """
        if self.pages_override:
            return [p for p in self.pages_override if 1 <= p <= num_pages]

        if num_pages == 3:
            return [3]

        pages = []
        if self.page1 and self.page1.sections_utiles:
            pages.append(1)
        if self.page2 and self.page2.sections_utiles:
            pages.append(2)

        if not pages:
            # Fallback: traiter toutes les pages
            return list(range(1, num_pages + 1))

        return pages

    def get_page_config(self, page_num: int) -> Optional[PageSectionConfig]:
        """Retourne la config pour une page spécifique."""
        if page_num == 1:
            return self.page1
        elif page_num == 2:
            return self.page2
        else:
            # Pour page 3+, utiliser la config de page 2 par défaut
            return self.page2


class SectionConfigLoader:
    """Charge les configurations par sections depuis biduls.description.csv."""

    def __init__(self, csv_path: Optional[str] = None):
        if csv_path is None:
            csv_path = Path(__file__).parent.parent / 'corpus' / 'biduls.description.csv'

        self.csv_path = Path(csv_path)
        self.configs: dict[int, BidulSectionConfig] = {}
        self._load()

    def _load(self):
        """Charge les configurations depuis le CSV."""
        if not self.csv_path.exists():
            logger.warning(f"Fichier config non trouvé: {self.csv_path}")
            return

        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(self.csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        config = BidulSectionConfig.from_csv_row(row)
                        if config:
                            self.configs[config.numero] = config

                logger.info(f"Chargé {len(self.configs)} configurations section depuis {self.csv_path}")
                return

            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Erreur chargement config sections ({encoding}): {e}")
                continue

        logger.error(f"Impossible de lire {self.csv_path}")

    def get_config(self, numero: int) -> Optional[BidulSectionConfig]:
        """Retourne la config pour un numéro."""
        return self.configs.get(numero)

    def get_nearest_config(self, numero: int) -> Optional[BidulSectionConfig]:
        """
        Retourne la config la plus proche pour un numéro non configuré ou sans sections.

        Priorité aux numéros inférieurs (formats plus proches dans le temps).
        """
        # Si le numéro existe et a des sections, le retourner
        if numero in self.configs:
            config = self.configs[numero]
            if config.page1 or config.page2:
                return config

        # Trouver les configs avec sections définies
        configs_with_sections = {
            n: c for n, c in self.configs.items()
            if c.page1 or c.page2
        }

        if not configs_with_sections:
            return None

        # Chercher la config la plus proche
        lower_nums = [n for n in configs_with_sections.keys() if n < numero]
        upper_nums = [n for n in configs_with_sections.keys() if n > numero]

        if lower_nums:
            nearest = max(lower_nums)
        elif upper_nums:
            nearest = min(upper_nums)
        else:
            return None

        logger.debug(f"Bidul {numero}: utilise config héritée de Bidul {nearest}")
        return self.configs[nearest]


# Singleton
_section_config_loader: Optional[SectionConfigLoader] = None


def get_section_config_loader() -> SectionConfigLoader:
    """Retourne le loader de configuration sections (singleton)."""
    global _section_config_loader
    if _section_config_loader is None:
        _section_config_loader = SectionConfigLoader()
    return _section_config_loader


def load_section_config(numero: int) -> Optional[BidulSectionConfig]:
    """
    Charge la configuration sections d'un Bidul.

    Si le bidul n'a pas de sections définies, hérite de la config la plus proche.
    """
    loader = get_section_config_loader()

    # Vérifier d'abord si le bidul a une config avec sections
    config = loader.get_config(numero)
    if config and (config.page1 or config.page2):
        return config

    # Sinon, chercher la config la plus proche avec sections
    return loader.get_nearest_config(numero)


class SectionCropper:
    """
    Découpe une image de page A4 en sections A6.

    Disposition des sections (page A4 portrait):
    ┌───────┬───────┐
    │  S1   │  S2   │
    ├───────┼───────┤
    │  S3   │  S4   │
    └───────┴───────┘
    """

    # Coordonnées relatives des sections (x_start, y_start, x_end, y_end)
    # en proportion de la largeur/hauteur totale
    SECTION_COORDS = {
        Section.S1: (0.0, 0.0, 0.5, 0.5),   # Haut-gauche
        Section.S2: (0.5, 0.0, 1.0, 0.5),   # Haut-droite
        Section.S3: (0.0, 0.5, 0.5, 1.0),   # Bas-gauche
        Section.S4: (0.5, 0.5, 1.0, 1.0),   # Bas-droite
    }

    def __init__(self, margin_percent: float = 0.02):
        """
        Args:
            margin_percent: Marge à ajouter autour de chaque section (en % de la taille)
                           pour éviter de couper du texte en bordure
        """
        self.margin_percent = margin_percent

    def crop_section(self, image: np.ndarray, section: Section) -> np.ndarray:
        """
        Extrait une section A6 d'une image A4.

        Args:
            image: Image numpy (BGR ou grayscale)
            section: Section à extraire (S1, S2, S3, S4)

        Returns:
            Image de la section extraite
        """
        h, w = image.shape[:2]
        coords = self.SECTION_COORDS[section]

        # Calculer les coordonnées en pixels
        x_start = int(coords[0] * w)
        y_start = int(coords[1] * h)
        x_end = int(coords[2] * w)
        y_end = int(coords[3] * h)

        # Ajouter une petite marge pour éviter de couper du texte
        margin_x = int(self.margin_percent * w)
        margin_y = int(self.margin_percent * h)

        # Ajuster avec marges (en restant dans les limites)
        x_start = max(0, x_start - margin_x)
        y_start = max(0, y_start - margin_y)
        x_end = min(w, x_end + margin_x)
        y_end = min(h, y_end + margin_y)

        return image[y_start:y_end, x_start:x_end].copy()

    def crop_sections(self, image: np.ndarray, sections: list[Section]) -> dict[Section, np.ndarray]:
        """
        Extrait plusieurs sections d'une image.

        Args:
            image: Image de la page complète
            sections: Liste des sections à extraire

        Returns:
            Dict section -> image
        """
        return {s: self.crop_section(image, s) for s in sections}

    def rotate_for_text(self, image: np.ndarray, clockwise: bool = False) -> np.ndarray:
        """
        Applique une rotation de 90° pour un texte en paysage.

        Args:
            image: Image à faire pivoter
            clockwise: Si True, rotation horaire; sinon anti-horaire

        Returns:
            Image pivotée
        """
        if clockwise:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)


@dataclass
class SectionOCRResult:
    """Résultat OCR pour une section."""
    section: Section
    page_num: int
    text: str
    colonnes: int
    orientation_texte: Orientation


@dataclass
class PageSectionsOCRResult:
    """Résultat OCR pour toutes les sections d'une page."""
    page_num: int
    sections: list[SectionOCRResult] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Texte complet de la page en respectant l'ordre des sections."""
        return '\n\n'.join(s.text for s in self.sections if s.text)


class SectionOCRExtractor:
    """
    Extracteur OCR qui traite les pages par sections A6.

    Workflow:
    1. Charge la config du Bidul depuis biduls.description.csv
    2. Pour chaque page à traiter:
       a. Découpe en sections A6 selon la config
       b. Applique la rotation si texte en paysage
       c. OCR chaque section avec le bon nombre de colonnes
       d. Assemble le texte dans l'ordre de lecture
    """

    def __init__(self, ocr_engine):
        """
        Args:
            ocr_engine: Instance de OCREngine pour l'OCR
        """
        self.ocr = ocr_engine
        self.cropper = SectionCropper()
        self.config_loader = get_section_config_loader()

    def extract_page_by_sections(
        self,
        image: np.ndarray,
        page_num: int,
        page_config: PageSectionConfig
    ) -> PageSectionsOCRResult:
        """
        Extrait le texte d'une page en traitant chaque section A6.

        Args:
            image: Image de la page complète (après prétraitement basique)
            page_num: Numéro de la page
            page_config: Configuration de la page

        Returns:
            PageSectionsOCRResult avec le texte de chaque section
        """
        result = PageSectionsOCRResult(page_num=page_num)

        # Obtenir l'ordre de lecture des sections
        section_order = page_config.get_section_order()

        # Filtrer pour ne garder que les sections utiles, dans l'ordre
        sections_to_process = [
            s for s in section_order
            if s in page_config.sections_utiles
        ]

        logger.debug(f"Page {page_num}: sections à traiter = {[s.value for s in sections_to_process]}")

        for section in sections_to_process:
            # Découper la section
            section_image = self.cropper.crop_section(image, section)

            # Appliquer rotation si texte en paysage
            if page_config.needs_rotation():
                section_image = self.cropper.rotate_for_text(section_image, clockwise=False)
                logger.debug(f"Section {section.value}: rotation appliquée (texte paysage)")

            # OCR avec le nombre de colonnes configuré
            text = self.ocr.ocr_image(section_image, num_columns=page_config.colonnes_par_section)

            section_result = SectionOCRResult(
                section=section,
                page_num=page_num,
                text=text,
                colonnes=page_config.colonnes_par_section,
                orientation_texte=page_config.orientation_texte
            )
            result.sections.append(section_result)

            logger.debug(f"Section {section.value}: {len(text)} caractères extraits")

        return result

    def extract_full_page(
        self,
        image: np.ndarray,
        page_num: int,
        num_columns: int = 1
    ) -> PageSectionsOCRResult:
        """
        Extrait une page entière sans découpage en sections (fallback).

        Utilisé quand aucune config de sections n'est disponible.
        """
        text = self.ocr.ocr_image(image, num_columns=num_columns)

        result = PageSectionsOCRResult(page_num=page_num)
        result.sections.append(SectionOCRResult(
            section=Section.S1,  # Placeholder
            page_num=page_num,
            text=text,
            colonnes=num_columns,
            orientation_texte=Orientation.PORTRAIT
        ))

        return result

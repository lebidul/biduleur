"""
Analyseur de layout pour détection automatique de la structure d'une page OCR.

Détecte automatiquement :
- Le nombre de colonnes (via clustering des positions X)
- L'orientation du texte (horizontal vs vertical)
- Les sections/régions distinctes (via gaps)
- L'ordre de lecture optimal
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class TextOrientation(Enum):
    """Orientation du texte."""
    HORIZONTAL = 'horizontal'  # Texte normal
    VERTICAL = 'vertical'      # Texte à 90° (nécessite rotation)


@dataclass
class TextBlock:
    """Un bloc de texte avec ses coordonnées."""
    text: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float = 1.0

    @property
    def x_center(self) -> float:
        return (self.x_min + self.x_max) / 2

    @property
    def y_center(self) -> float:
        return (self.y_min + self.y_max) / 2

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def aspect_ratio(self) -> float:
        """Ratio largeur/hauteur. > 1 = horizontal, < 1 = vertical."""
        if self.height == 0:
            return float('inf')
        return self.width / self.height


@dataclass
class LayoutAnalysis:
    """Résultat de l'analyse de layout."""
    num_columns: int = 1
    column_boundaries: list[float] = field(default_factory=list)
    orientation: TextOrientation = TextOrientation.HORIZONTAL
    has_sections: bool = False
    section_boundaries: list[tuple[float, float]] = field(default_factory=list)  # (y_min, y_max)
    blocks: list[TextBlock] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0

    def get_column_for_x(self, x: float) -> int:
        """Retourne l'index de colonne pour une position X donnée."""
        if not self.column_boundaries:
            return 0
        for i, boundary in enumerate(self.column_boundaries):
            if x < boundary:
                return i
        return len(self.column_boundaries)


class LayoutAnalyzer:
    """
    Analyse automatique du layout d'une page à partir des bounding boxes OCR.

    Utilise des techniques de clustering pour détecter :
    - Colonnes : clustering des centres X des blocs
    - Sections : détection des gaps verticaux significatifs
    - Orientation : analyse des ratios largeur/hauteur des blocs
    """

    def __init__(
        self,
        min_column_gap_ratio: float = 0.20,  # Gap minimum 20% de la largeur
        min_section_gap_ratio: float = 0.03,
        column_detection_threshold: float = 0.15,
    ):
        """
        Args:
            min_column_gap_ratio: Gap minimum entre colonnes (ratio de la largeur image)
                                  Valeur par défaut 0.20 (20%) pour éviter les faux positifs
            min_section_gap_ratio: Gap minimum entre sections (ratio de la hauteur image)
            column_detection_threshold: Seuil de détection des colonnes
        """
        self.min_column_gap_ratio = min_column_gap_ratio
        self.min_section_gap_ratio = min_section_gap_ratio
        self.column_detection_threshold = column_detection_threshold

    def analyze_from_google_vision(
        self,
        annotation,
        image_width: int,
        image_height: int
    ) -> LayoutAnalysis:
        """
        Analyse le layout à partir d'une réponse Google Vision.

        Args:
            annotation: full_text_annotation de Google Vision
            image_width: Largeur de l'image en pixels
            image_height: Hauteur de l'image en pixels

        Returns:
            LayoutAnalysis avec la structure détectée
        """
        # Extraire les blocs de texte avec leurs coordonnées
        blocks = self._extract_blocks(annotation)

        if not blocks:
            return LayoutAnalysis(image_width=image_width, image_height=image_height)

        # Détecter le nombre de colonnes
        num_columns, boundaries = self._detect_columns(blocks, image_width)

        # Détecter l'orientation du texte
        orientation = self._detect_orientation(blocks)

        # Détecter les sections (gaps verticaux)
        has_sections, section_boundaries = self._detect_sections(blocks, image_height)

        return LayoutAnalysis(
            num_columns=num_columns,
            column_boundaries=boundaries,
            orientation=orientation,
            has_sections=has_sections,
            section_boundaries=section_boundaries,
            blocks=blocks,
            image_width=image_width,
            image_height=image_height,
        )

    def _extract_blocks(self, annotation) -> list[TextBlock]:
        """Extrait les blocs de texte avec coordonnées depuis l'annotation Google Vision."""
        blocks = []

        if not annotation or not annotation.pages:
            return blocks

        for page in annotation.pages:
            for block in page.blocks:
                vertices = block.bounding_box.vertices
                if not vertices or len(vertices) < 4:
                    continue

                x_coords = [v.x for v in vertices if hasattr(v, 'x')]
                y_coords = [v.y for v in vertices if hasattr(v, 'y')]

                if not x_coords or not y_coords:
                    continue

                # Extraire le texte du bloc
                text_parts = []
                for paragraph in block.paragraphs:
                    para_words = []
                    for word in paragraph.words:
                        word_text = ''.join(s.text for s in word.symbols)
                        para_words.append(word_text)
                    text_parts.append(' '.join(para_words))

                text = '\n'.join(text_parts)
                if not text.strip():
                    continue

                blocks.append(TextBlock(
                    text=text,
                    x_min=min(x_coords),
                    y_min=min(y_coords),
                    x_max=max(x_coords),
                    y_max=max(y_coords),
                    confidence=block.confidence if hasattr(block, 'confidence') else 1.0,
                ))

        return blocks

    def _detect_columns(
        self,
        blocks: list[TextBlock],
        image_width: int
    ) -> tuple[int, list[float]]:
        """
        Détecte le nombre de colonnes via clustering des centres X des blocs.

        Utilise un algorithme de clustering simple :
        1. Collecte les centres X de tous les blocs
        2. Cherche des clusters naturels basés sur les gaps entre centres
        3. Valide en vérifiant que les blocs sont bien séparés

        Returns:
            (nombre de colonnes, liste des frontières X)
        """
        if not blocks:
            return 1, []

        # Collecter les centres X des blocs
        x_centers = sorted([b.x_center for b in blocks])

        if len(x_centers) < 2:
            return 1, []

        # Chercher les gaps significatifs entre centres X consécutifs
        min_gap = image_width * self.min_column_gap_ratio
        gaps = []

        for i in range(len(x_centers) - 1):
            gap = x_centers[i + 1] - x_centers[i]
            if gap > min_gap:
                gap_center = (x_centers[i] + x_centers[i + 1]) / 2
                # Exclure les gaps trop près des bords
                if gap_center > image_width * 0.15 and gap_center < image_width * 0.85:
                    gaps.append(gap_center)

        # Si pas de gaps entre centres, essayer une détection par histogramme des centres
        if not gaps:
            gaps = self._detect_columns_by_histogram(blocks, image_width)

        # Si un seul gap significatif au milieu, c'est 2 colonnes
        num_columns = len(gaps) + 1

        # Limiter à un nombre raisonnable
        if num_columns > 4:
            # Garder uniquement les gaps les plus significatifs
            if len(gaps) > 3:
                # Trier par position et garder les plus centraux
                center = image_width / 2
                gaps = sorted(gaps, key=lambda g: abs(g - center))[:3]
                gaps = sorted(gaps)
            num_columns = len(gaps) + 1

        logger.debug(f"Layout: {num_columns} colonnes détectées, gaps={gaps}")
        return num_columns, gaps

    def _detect_columns_by_histogram(
        self,
        blocks: list[TextBlock],
        image_width: int
    ) -> list[float]:
        """
        Détection de colonnes par histogramme des centres X.

        Utilisé en fallback quand la détection par gaps simples ne fonctionne pas.
        """
        x_centers = [b.x_center for b in blocks]

        if len(x_centers) < 4:
            return []

        # Créer un histogramme des centres X
        num_bins = 20
        hist, bin_edges = np.histogram(x_centers, bins=num_bins, range=(0, image_width))

        # Chercher les vallées (bins avec peu de blocs)
        mean_count = np.mean(hist)
        gaps = []

        # Chercher les séquences de bins quasi-vides au milieu
        for i in range(2, num_bins - 2):
            if hist[i] < mean_count * 0.3:  # Bin avec moins de 30% de la moyenne
                # Vérifier que les bins adjacents ne sont pas tous vides (pas un bord)
                if hist[i-1] > 0 or hist[i-2] > 0:
                    if hist[i+1] > 0 or hist[i+2] > 0:
                        gap_center = (bin_edges[i] + bin_edges[i+1]) / 2
                        # Éviter les doublons proches
                        if not gaps or abs(gap_center - gaps[-1]) > image_width * 0.1:
                            gaps.append(gap_center)

        return gaps

    def _detect_orientation(self, blocks: list[TextBlock]) -> TextOrientation:
        """
        Détecte l'orientation du texte.

        Analyse le ratio largeur/hauteur des blocs :
        - Blocs horizontaux : width > height (ratio > 1)
        - Blocs verticaux : height > width (ratio < 1)
        """
        if not blocks:
            return TextOrientation.HORIZONTAL

        # Calculer le ratio moyen pondéré par la surface
        total_area = 0
        weighted_ratio = 0

        for b in blocks:
            area = b.width * b.height
            if area > 0:
                total_area += area
                weighted_ratio += b.aspect_ratio * area

        if total_area == 0:
            return TextOrientation.HORIZONTAL

        avg_ratio = weighted_ratio / total_area

        # Un ratio < 0.5 suggère fortement du texte vertical
        if avg_ratio < 0.5:
            logger.debug(f"Layout: orientation verticale détectée (ratio={avg_ratio:.2f})")
            return TextOrientation.VERTICAL

        return TextOrientation.HORIZONTAL

    def _detect_sections(
        self,
        blocks: list[TextBlock],
        image_height: int
    ) -> tuple[bool, list[tuple[float, float]]]:
        """
        Détecte les sections via gaps verticaux.

        Returns:
            (has_sections, liste de (y_min, y_max) pour chaque section)
        """
        if not blocks:
            return False, []

        # Trier les blocs par Y
        sorted_blocks = sorted(blocks, key=lambda b: b.y_min)

        min_gap = image_height * self.min_section_gap_ratio
        sections = []
        section_start = sorted_blocks[0].y_min
        prev_y_max = sorted_blocks[0].y_max

        for block in sorted_blocks[1:]:
            gap = block.y_min - prev_y_max
            if gap > min_gap:
                # Gap significatif : nouvelle section
                sections.append((section_start, prev_y_max))
                section_start = block.y_min
            prev_y_max = max(prev_y_max, block.y_max)

        # Ajouter la dernière section
        sections.append((section_start, prev_y_max))

        has_sections = len(sections) > 1
        if has_sections:
            logger.debug(f"Layout: {len(sections)} sections détectées")

        return has_sections, sections

    def reorder_blocks_for_reading(
        self,
        blocks: list[TextBlock],
        layout: LayoutAnalysis
    ) -> list[TextBlock]:
        """
        Réordonne les blocs pour un ordre de lecture naturel.

        Pour N colonnes : lit colonne 1 de haut en bas, puis colonne 2, etc.
        """
        if not blocks or layout.num_columns <= 1:
            # Tri simple par Y
            return sorted(blocks, key=lambda b: (b.y_min, b.x_min))

        # Assigner chaque bloc à une colonne
        blocks_by_column: dict[int, list[TextBlock]] = {i: [] for i in range(layout.num_columns)}

        for block in blocks:
            col = layout.get_column_for_x(block.x_center)
            col = min(col, layout.num_columns - 1)
            blocks_by_column[col].append(block)

        # Trier chaque colonne par Y
        for col in blocks_by_column:
            blocks_by_column[col].sort(key=lambda b: b.y_min)

        # Concaténer les colonnes dans l'ordre
        result = []
        for col in range(layout.num_columns):
            result.extend(blocks_by_column[col])

        return result

    def extract_text_with_layout(
        self,
        annotation,
        image_width: int,
        image_height: int
    ) -> str:
        """
        Extrait le texte en respectant le layout détecté automatiquement.

        C'est la méthode principale à appeler pour une extraction intelligente.
        """
        layout = self.analyze_from_google_vision(annotation, image_width, image_height)

        if not layout.blocks:
            # Fallback au texte brut si pas de blocs
            return annotation.text if annotation else ""

        # Réordonner les blocs pour la lecture
        ordered_blocks = self.reorder_blocks_for_reading(layout.blocks, layout)

        # Assembler le texte
        lines = []
        prev_col = -1

        for block in ordered_blocks:
            col = layout.get_column_for_x(block.x_center)
            if col != prev_col and prev_col >= 0:
                # Séparation entre colonnes
                lines.append('')
            prev_col = col
            lines.append(block.text)

        return '\n'.join(lines)


def analyze_page_layout(
    annotation,
    image_width: int,
    image_height: int
) -> LayoutAnalysis:
    """
    Fonction utilitaire pour analyser le layout d'une page.

    Args:
        annotation: full_text_annotation de Google Vision
        image_width: Largeur de l'image
        image_height: Hauteur de l'image

    Returns:
        LayoutAnalysis avec la structure détectée
    """
    analyzer = LayoutAnalyzer()
    return analyzer.analyze_from_google_vision(annotation, image_width, image_height)


def extract_text_with_auto_layout(
    annotation,
    image_width: int,
    image_height: int
) -> str:
    """
    Extrait le texte avec détection automatique du layout.

    Utilise une approche hybride :
    1. Analyse le layout pour détecter le nombre de colonnes
    2. Si 1 colonne détectée : retourne le texte brut Google Vision
    3. Si 2+ colonnes : trie les paragraphes par colonne puis Y
    """
    analyzer = LayoutAnalyzer()
    layout = analyzer.analyze_from_google_vision(annotation, image_width, image_height)

    # Si une seule colonne, le texte brut de Google Vision est optimal
    if layout.num_columns <= 1:
        logger.debug("Auto-layout: 1 colonne, utilise texte brut")
        return annotation.text if annotation else ""

    # Pour plusieurs colonnes, trier les paragraphes par colonne
    logger.debug(f"Auto-layout: {layout.num_columns} colonnes détectées, tri par colonne")
    return _extract_paragraphs_by_columns(annotation, layout, image_width)


def _extract_paragraphs_by_columns(annotation, layout: LayoutAnalysis, image_width: int) -> str:
    """
    Extrait les paragraphes en les triant par colonne puis par position Y.

    Préserve le formatage original de Google Vision (sauts de ligne) mais
    réordonne les paragraphes pour respecter l'ordre de lecture des colonnes.
    """
    if not annotation or not annotation.pages:
        return annotation.text if annotation else ""

    # Collecter tous les paragraphes avec leurs coordonnées
    paragraphs = []

    for page in annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                vertices = paragraph.bounding_box.vertices
                if not vertices:
                    continue

                x_coords = [v.x for v in vertices if hasattr(v, 'x')]
                y_coords = [v.y for v in vertices if hasattr(v, 'y')]

                if not x_coords or not y_coords:
                    continue

                x_center = sum(x_coords) / len(x_coords)
                y_min = min(y_coords)

                # Extraire le texte du paragraphe avec formatage
                para_text = []
                for word in paragraph.words:
                    word_text = ''.join(s.text for s in word.symbols)
                    # Ajouter un espace ou saut de ligne selon le symbole de fin
                    if word.symbols and hasattr(word.symbols[-1], 'property'):
                        prop = word.symbols[-1].property
                        if hasattr(prop, 'detected_break'):
                            break_type = prop.detected_break.type_
                            if break_type in [1, 3]:  # SPACE, SURE_SPACE
                                word_text += ' '
                            elif break_type in [2, 5]:  # EOL_SURE_SPACE, LINE_BREAK
                                word_text += '\n'
                    else:
                        word_text += ' '
                    para_text.append(word_text)

                text = ''.join(para_text).strip()
                if text:
                    # Déterminer la colonne
                    col = layout.get_column_for_x(x_center)
                    col = min(col, layout.num_columns - 1)

                    paragraphs.append({
                        'text': text,
                        'column': col,
                        'y_min': y_min,
                        'x_center': x_center,
                    })

    if not paragraphs:
        return annotation.text if annotation else ""

    # Trier par colonne puis par Y
    paragraphs.sort(key=lambda p: (p['column'], p['y_min']))

    # Assembler le texte avec séparation entre colonnes
    result_parts = []
    current_column = -1

    for para in paragraphs:
        if para['column'] != current_column:
            if current_column >= 0:
                result_parts.append('\n')  # Séparation entre colonnes
            current_column = para['column']
        result_parts.append(para['text'])
        result_parts.append('\n')

    return ''.join(result_parts).strip()

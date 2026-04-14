"""
Module OCR pour les PDFs scannés du Bidul.

Utilise PaddleOCR ou EasyOCR pour l'extraction de texte.
Inclut des prétraitements d'image adaptés aux différents formats:
- Rotation pour les anciens Biduls en paysage
- Suppression de fond coloré (ex: fond bleu cyan du Bidul 103)
- Amélioration du contraste et débruitage
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

try:
    from pdf2image import convert_from_path
except ImportError:
    raise ImportError("pdf2image requis: pip install pdf2image")

logger = logging.getLogger(__name__)


@dataclass
class ScanConfig:
    """Configuration d'extraction OCR pour un Bidul scanné."""
    numero: int
    type_source: str = 'scan'

    # Format de date: 'inline' (date sur chaque ligne) ou 'par bloc' (date en en-tête)
    date_format: str = 'inline'

    # Page 1 config
    page1_orientation_pdf: str = 'portrait'  # Orientation du PDF
    page1_orientation_texte: str = 'portrait'  # Orientation du texte
    page1_sections: str = ''  # Sections à extraire (S1, S2, S3, S4)
    page1_colonnes: int = 1  # Nombre de colonnes

    # Page 2 config
    page2_orientation_pdf: str = 'portrait'
    page2_orientation_texte: str = 'portrait'
    page2_sections: str = ''
    page2_colonnes: int = 1

    # Flags spéciaux
    fond_colore: bool = False  # Nécessite suppression du fond coloré
    date_par_evenement: bool = False  # Chaque événement a sa propre date (legacy, use date_format)

    # Template SVG (v1.12+)
    svg_template: str = ''  # Nom du fichier template SVG dans corpus/templates/

    # Source CSV/XLSX (v1.22+)
    source_file: str = ''  # Fichier(s) CSV/XLSX source (séparés par |)

    @classmethod
    def from_csv_row(cls, row: dict) -> Optional['ScanConfig']:
        """Crée une config depuis une ligne du CSV biduls.description.csv.

        Supporte à la fois l'ancien format (colonnes 'numéros', 'scan/texte', 'date',
        'page1.orientation pdf', etc.) et le nouveau format (colonnes 'numero', 'type',
        'date_format', 'p1_orientation', etc.).
        """
        try:
            # Le nom de colonne peut avoir des variantes d'encodage
            # Nouveau format: 'numero', ancien: 'numéros'
            numero = 0
            for key in ['numero', 'numéros', 'numeros', 'num\xe9ros', 'num\ufffdros']:
                if key in row:
                    try:
                        numero = int(row[key])
                        break
                    except (ValueError, TypeError):
                        continue

            if numero == 0:
                return None

            # Type source: nouveau 'type', ancien 'scan/texte'
            type_source = (row.get('type') or row.get('scan/texte') or 'scan').strip().lower()
            if type_source != 'scan':
                return None  # Ne charge que les scans

            # Format de date: nouveau 'date_format', ancien 'date'
            date_format = (row.get('date_format') or row.get('date') or 'inline').strip().lower()

            # Page 1 config: nouveau format 'p1_*', ancien 'page1.*'
            p1_orientation_texte = (
                row.get('p1_orientation') or
                row.get('page1.orientation texte') or
                'portrait'
            ).strip().lower()
            p1_orientation_pdf = (
                row.get('p1_orientation_pdf') or
                row.get('page1.orientation pdf') or
                p1_orientation_texte  # Défaut = même que texte
            ).strip().lower()
            p1_sections = (
                row.get('p1_sections') or
                row.get('page1.sections texte utile') or
                ''
            ).strip()
            p1_colonnes_str = (
                row.get('p1_colonnes') or
                row.get('page1.colonne par section') or
                '1'
            )
            p1_colonnes = int(p1_colonnes_str) if p1_colonnes_str else 1

            # Page 2 config: nouveau format 'p2_*', ancien 'page2.*'
            p2_orientation_texte = (
                row.get('p2_orientation') or
                row.get('page2.orientation texte') or
                'portrait'
            ).strip().lower()
            p2_orientation_pdf = (
                row.get('p2_orientation_pdf') or
                row.get('page2.orientation pdf') or
                p2_orientation_texte  # Défaut = même que texte
            ).strip().lower()
            p2_sections = (
                row.get('p2_sections') or
                row.get('page2.sections texte utile') or
                ''
            ).strip()
            p2_colonnes_str = (
                row.get('p2_colonnes') or
                row.get('page2.colonne par section') or
                '1'
            )
            p2_colonnes = int(p2_colonnes_str) if p2_colonnes_str else 1

            # Template SVG (v1.12+)
            svg_template = (row.get('svg_template') or '').strip()

            # Source CSV/XLSX (v1.22+)
            source_file = (row.get('source_file') or '').strip()

            return cls(
                numero=numero,
                type_source=type_source,
                date_format=date_format,
                page1_orientation_pdf=p1_orientation_pdf,
                page1_orientation_texte=p1_orientation_texte,
                page1_sections=p1_sections,
                page1_colonnes=p1_colonnes,
                page2_orientation_pdf=p2_orientation_pdf,
                page2_orientation_texte=p2_orientation_texte,
                page2_sections=p2_sections,
                page2_colonnes=p2_colonnes,
                date_par_evenement=date_format == 'inline',  # Compatibilité
                svg_template=svg_template,
                source_file=source_file,
            )
        except (ValueError, KeyError) as e:
            logger.debug(f"Erreur parsing config row: {e}")
            return None

    def needs_rotation(self, page_num: int) -> bool:
        """Vérifie si une page nécessite une rotation.

        Rotation nécessaire quand l'orientation du PDF diffère de celle du texte,
        ou quand la page est retournée à 180°.
        """
        return self.get_rotation_degrees(page_num) != 0

    def get_rotation_degrees(self, page_num: int) -> int:
        """Retourne l'angle de rotation nécessaire (0, 90, ou 180)."""
        if page_num == 1:
            if self.page1_orientation_pdf == 'retourne':
                return 180
            return 90 if self.page1_orientation_pdf != self.page1_orientation_texte else 0
        else:
            if self.page2_orientation_pdf == 'retourne':
                return 180
            return 90 if self.page2_orientation_pdf != self.page2_orientation_texte else 0

    def get_sections(self, page_num: int) -> list[str]:
        """Retourne les sections à extraire pour une page."""
        sections_str = self.page1_sections if page_num == 1 else self.page2_sections
        return [s.strip() for s in sections_str.split() if s.strip()]

    def get_colonnes(self, page_num: int) -> int:
        """Retourne le nombre de colonnes pour une page."""
        return self.page1_colonnes if page_num == 1 else self.page2_colonnes

    def is_date_inline(self) -> bool:
        """True si les dates sont sur chaque ligne, False si en bloc (header)."""
        return self.date_format == 'inline'

    def is_date_par_bloc(self) -> bool:
        """True si les dates sont en bloc (header de section)."""
        return self.date_format == 'par bloc'


class ScanConfigLoader:
    """Charge et gère les configurations OCR depuis biduls.description.csv."""

    def __init__(self, csv_path: Optional[str] = None):
        """
        Initialise le loader.

        Args:
            csv_path: Chemin vers biduls.description.csv. Si None, cherche dans corpus/.
        """
        if csv_path is None:
            csv_path = Path(__file__).parent.parent / 'corpus' / 'biduls.description.csv'

        self.csv_path = Path(csv_path)
        self.configs: dict[int, ScanConfig] = {}
        self._load()

    def _load(self):
        """Charge les configurations depuis le CSV."""
        if not self.csv_path.exists():
            logger.warning(f"Fichier config non trouvé: {self.csv_path}")
            return

        # Essayer plusieurs encodages
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(self.csv_path, 'r', encoding=encoding) as f:
                    # Filtrer les lignes de commentaires (commençant par # ou "#)
                    lines = [
                        line for line in f
                        if not line.strip().startswith('#')
                        and not line.strip().startswith('"#')
                    ]
                    from io import StringIO
                    reader = csv.DictReader(StringIO(''.join(lines)))
                    for row in reader:
                        config = ScanConfig.from_csv_row(row)
                        if config:
                            self.configs[config.numero] = config

                logger.info(f"Chargé {len(self.configs)} configurations scan depuis {self.csv_path}")
                return

            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Erreur chargement config ({encoding}): {e}")
                continue

        logger.error(f"Impossible de lire {self.csv_path} avec les encodages disponibles")

    def get_config(self, numero: int) -> Optional[ScanConfig]:
        """Retourne la config pour un numéro, ou None si non trouvée."""
        return self.configs.get(numero)

    def get_nearest_config(self, numero: int) -> Optional[ScanConfig]:
        """Retourne la config la plus proche pour un numéro non configuré."""
        if numero in self.configs:
            return self.configs[numero]

        # Chercher la config la plus proche (priorité aux numéros inférieurs)
        lower_nums = [n for n in self.configs.keys() if n < numero]
        upper_nums = [n for n in self.configs.keys() if n > numero]

        if lower_nums:
            return self.configs[max(lower_nums)]
        elif upper_nums:
            return self.configs[min(upper_nums)]

        return None


# Singleton pour éviter de recharger le CSV à chaque appel
_scan_config_loader: Optional[ScanConfigLoader] = None


def get_scan_config_loader() -> ScanConfigLoader:
    """Retourne le loader de configuration scan (singleton)."""
    global _scan_config_loader
    if _scan_config_loader is None:
        _scan_config_loader = ScanConfigLoader()
    return _scan_config_loader


def load_bidul_config(numero: int, csv_path: str = None) -> Optional[ScanConfig]:
    """Charge la configuration d'un Bidul depuis le CSV."""
    loader = get_scan_config_loader()
    return loader.get_config(numero) or loader.get_nearest_config(numero)


def get_bidul_type(numero: int) -> Optional[str]:
    """
    Récupère le type de source d'un Bidul depuis biduls.description.csv.

    Returns:
        'scan', 'texte', 'csv', 'xlsx' ou None si non trouvé
    """
    csv_path = Path(__file__).parent.parent / 'corpus' / 'biduls.description.csv'
    if not csv_path.exists():
        return None

    # Lire le CSV pour trouver le type
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']

    for encoding in encodings:
        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                # Filtrer les lignes de commentaires
                lines = [line for line in f if not line.startswith('#') and not line.startswith('"#')]
                if not lines:
                    return None

                import io
                reader = csv.DictReader(io.StringIO(''.join(lines)))
                for row in reader:
                    # Chercher le numéro (nouveau format: 'numero', ancien: 'numéros')
                    row_numero = 0
                    for key in ['numero', 'numéros', 'numeros', 'num\xe9ros']:
                        if key in row:
                            try:
                                row_numero = int(row[key])
                                break
                            except (ValueError, TypeError):
                                continue

                    if row_numero == numero:
                        # Nouveau format: 'type', ancien: 'scan/texte'
                        type_source = row.get('type', row.get('scan/texte', '')).strip().lower()
                        if type_source in ('scan', 'texte', 'csv', 'xlsx'):
                            return type_source
                        return None
            return None  # Numéro non trouvé
        except UnicodeDecodeError:
            continue
        except Exception:
            continue

    return None


def is_scan_from_csv(numero: int) -> Optional[bool]:
    """
    Vérifie si un Bidul est un scan selon le fichier biduls.description.csv.

    Returns:
        True si scan, False si texte/csv/xlsx, None si non trouvé dans le CSV
    """
    bidul_type = get_bidul_type(numero)
    if bidul_type == 'scan':
        return True
    elif bidul_type in ('texte', 'csv', 'xlsx'):
        return False
    return None


class OCREngine:
    """Wrapper unifié pour différents moteurs OCR."""

    def __init__(self, engine: str = 'paddleocr', lang: str = 'fr'):
        self.engine_name = engine
        self.lang = lang
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        if self.engine_name == 'paddleocr':
            from paddleocr import PaddleOCR
            # PaddleOCR 3.x a changé son API
            try:
                # Essayer la nouvelle API (PaddleOCR 3.x)
                self._engine = PaddleOCR(
                    use_angle_cls=True,  # Détection d'orientation
                    lang='fr',
                )
            except TypeError:
                # Fallback pour anciennes versions
                self._engine = PaddleOCR(
                    use_angle_cls=True,
                    lang='french',
                )
        elif self.engine_name == 'easyocr':
            import easyocr
            self._engine = easyocr.Reader(['fr'], gpu=False)
        elif self.engine_name == 'google':
            self._init_google_vision()
        else:
            raise ValueError(f"Engine non supporté: {self.engine_name}")

    def _init_google_vision(self):
        """Initialise Google Cloud Vision API."""
        import os
        from google.cloud import vision

        # Chercher les credentials (priorité au projet biduleur)
        creds_paths = [
            os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'),
            Path(__file__).parent.parent.parent / 'gcp_creds_biduleur.json',  # Projet lebidul-biduleur
            Path(__file__).parent.parent.parent / 'gcp_creds.json',  # Projet lebidul (legacy)
            Path.home() / '.config' / 'gcloud' / 'application_default_credentials.json',
        ]

        creds_found = None
        for creds_path in creds_paths:
            if creds_path and Path(creds_path).exists():
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(creds_path)
                creds_found = creds_path
                break

        if creds_found:
            logger.info(f"Google Cloud Vision: credentials = {Path(creds_found).name}")
        else:
            logger.warning("Google Cloud Vision: aucun fichier credentials trouvé")

        self._engine = vision.ImageAnnotatorClient()

    def ocr_image(self, image: np.ndarray, num_columns: int = 1, auto_layout: bool = False) -> str:
        """Effectue l'OCR sur une image numpy.

        Args:
            image: Image numpy array
            num_columns: Nombre de colonnes pour la lecture (1 = normal, 2+ = par colonnes)
            auto_layout: Si True, détecte automatiquement le layout (Google Vision uniquement)
        """
        if self.engine_name == 'paddleocr':
            return self._ocr_paddle(image, num_columns)
        elif self.engine_name == 'easyocr':
            return self._ocr_easyocr(image)
        elif self.engine_name == 'google':
            return self._ocr_google(image, num_columns, auto_layout=auto_layout)
        return ""

    def _ocr_paddle(self, image: np.ndarray, num_columns: int = 1) -> str:
        """OCR avec PaddleOCR.

        Args:
            image: Image numpy array
            num_columns: Nombre de colonnes (utilisé pour le tri des résultats)
        """
        try:
            # PaddleOCR 3.x utilise predict() au lieu de ocr()
            if hasattr(self._engine, 'predict'):
                result = self._engine.predict(image)
            else:
                # Anciennes versions utilisent ocr()
                result = self._engine.ocr(image, cls=True)
        except TypeError:
            # Fallback sans cls
            if hasattr(self._engine, 'predict'):
                result = self._engine.predict(image)
            else:
                result = self._engine.ocr(image)

        if not result:
            return ""

        # PaddleOCR 3.x retourne une liste de dicts avec 'rec_texts' et 'rec_polys'
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            # Nouvelle API PaddleOCR 3.x
            item = result[0]
            rec_texts = item.get('rec_texts', [])
            rec_polys = item.get('rec_polys', [])
            rec_scores = item.get('rec_scores', [])

            if not rec_texts:
                return ""

            # Trier par position Y puis X pour maintenir l'ordre de lecture
            lines_with_pos = []
            for i, text in enumerate(rec_texts):
                if i < len(rec_polys):
                    poly = rec_polys[i]
                    # poly est un array de 4 points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    y_pos = (poly[0][1] + poly[1][1]) / 2  # Moyenne Y du haut
                    x_pos = poly[0][0]  # X du coin supérieur gauche
                else:
                    y_pos = i
                    x_pos = 0

                confidence = rec_scores[i] if i < len(rec_scores) else 1.0
                lines_with_pos.append((y_pos, x_pos, text, confidence))

            # Trier par Y puis par X
            lines_with_pos.sort(key=lambda x: (x[0], x[1]))

            # Assembler le texte
            lines = [item[2] for item in lines_with_pos]
            return '\n'.join(lines)

        # Ancienne API: liste de résultats par page (pour compatibilité)
        if isinstance(result, list) and len(result) > 0:
            first_item = result[0]
            if first_item is None:
                return ""

            # Ancienne structure: liste de [[bbox], (texte, score)]
            lines_with_pos = []
            for line in first_item:
                if line and len(line) >= 2:
                    bbox = line[0]
                    text = line[1][0]
                    confidence = line[1][1]

                    y_pos = (bbox[0][1] + bbox[1][1]) / 2
                    x_pos = bbox[0][0]

                    lines_with_pos.append((y_pos, x_pos, text, confidence))

            lines_with_pos.sort(key=lambda x: (x[0], x[1]))
            lines = [item[2] for item in lines_with_pos]
            return '\n'.join(lines)

        return ""

    def _ocr_easyocr(self, image: np.ndarray) -> str:
        """OCR avec EasyOCR."""
        result = self._engine.readtext(image)

        lines = []
        for detection in result:
            text = detection[1]
            lines.append(text)

        return '\n'.join(lines)

    def _ocr_google(self, image: np.ndarray, num_columns: int = 1, auto_layout: bool = False) -> str:
        """OCR avec Google Cloud Vision API.

        Args:
            image: Image numpy array
            num_columns: Nombre de colonnes à détecter (1 = lecture normale, 2+ = lecture par colonnes)
            auto_layout: Si True, détecte automatiquement le layout (colonnes, orientation)
        """
        import io
        from PIL import Image
        from google.cloud import vision

        # Convertir numpy array en PNG bytes
        if len(image.shape) == 3 and image.shape[2] == 3:
            # BGR to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image

        pil_image = Image.fromarray(image_rgb)
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='PNG')
        content = img_byte_arr.getvalue()

        # Appel API
        vision_image = vision.Image(content=content)
        response = self._engine.document_text_detection(image=vision_image)

        if response.error.message:
            logger.error(f"Google Vision error: {response.error.message}")
            return ""

        if not response.full_text_annotation:
            return ""

        # Mode auto-layout : détection automatique de la structure
        if auto_layout and response.full_text_annotation.pages:
            from .layout_analyzer import extract_text_with_auto_layout
            return extract_text_with_auto_layout(
                response.full_text_annotation,
                image.shape[1],  # width
                image.shape[0],  # height
            )

        # Si une seule colonne ou pas de pages, retourner le texte brut
        if num_columns <= 1 or not response.full_text_annotation.pages:
            return response.full_text_annotation.text

        # Extraction avec respect des colonnes (nombre fixe)
        return self._extract_text_by_columns(response.full_text_annotation, num_columns, image.shape[1])

    def _extract_text_by_columns(self, annotation, num_columns: int, image_width: int) -> str:
        """
        Extrait le texte en respectant l'ordre des colonnes.

        Les colonnes sont détectées en divisant l'image en num_columns zones verticales.
        Les blocs sont ensuite triés par colonne (X) puis par position verticale (Y).
        """
        if not annotation.pages:
            return annotation.text

        # Collecter tous les paragraphes avec leurs coordonnées
        paragraphs = []

        for page in annotation.pages:
            for block in page.blocks:
                # Calculer la bounding box du bloc
                vertices = block.bounding_box.vertices
                if not vertices:
                    continue

                x_min = min(v.x for v in vertices)
                y_min = min(v.y for v in vertices)
                x_center = (min(v.x for v in vertices) + max(v.x for v in vertices)) / 2

                # Extraire le texte du bloc
                block_text = []
                for paragraph in block.paragraphs:
                    para_text = []
                    for word in paragraph.words:
                        word_text = ''.join(
                            symbol.text for symbol in word.symbols
                        )
                        para_text.append(word_text)
                    block_text.append(' '.join(para_text))

                if block_text:
                    paragraphs.append({
                        'x_center': x_center,
                        'x_min': x_min,
                        'y_min': y_min,
                        'text': '\n'.join(block_text)
                    })

        if not paragraphs:
            return annotation.text

        # Déterminer la colonne de chaque paragraphe
        column_width = image_width / num_columns

        for para in paragraphs:
            # Assigner à une colonne basé sur la position X centrale
            para['column'] = int(para['x_center'] / column_width)
            # Limiter au nombre de colonnes
            para['column'] = min(para['column'], num_columns - 1)

        # Trier par colonne puis par position Y
        paragraphs.sort(key=lambda p: (p['column'], p['y_min']))

        # Assembler le texte
        result_lines = []
        current_column = -1

        for para in paragraphs:
            if para['column'] != current_column:
                if current_column >= 0:
                    # Ajouter une séparation visuelle entre colonnes (optionnel)
                    result_lines.append('')
                current_column = para['column']
            result_lines.append(para['text'])

        return '\n'.join(result_lines)


class ImagePreprocessor:
    """Prétraitement des images pour améliorer l'OCR."""

    @staticmethod
    def pil_to_cv2(pil_image) -> np.ndarray:
        """Convertit une image PIL en numpy array BGR."""
        image = np.array(pil_image)
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image

    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        """Convertit en niveaux de gris."""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    @staticmethod
    def rotate_90(image: np.ndarray, clockwise: bool = True) -> np.ndarray:
        """Rotation de 90°."""
        if clockwise:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)

    @staticmethod
    def remove_colored_background(image: np.ndarray, threshold: int = 200) -> np.ndarray:
        """
        Supprime le fond coloré (ex: fond bleu cyan du Bidul 103).

        Convertit les zones colorées en blanc pour améliorer l'OCR.
        """
        if len(image.shape) == 2:
            return image

        # Convertir en HSV pour détecter la couleur dominante
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Créer un masque pour les zones à forte saturation (colorées)
        # et les convertir en blanc
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]

        # Zones avec saturation significative mais pas trop sombres
        colored_mask = (saturation > 30) & (value > 100)

        # Appliquer le masque - remplacer les zones colorées par du blanc
        result = image.copy()
        result[colored_mask] = [255, 255, 255]

        return result

    @staticmethod
    def adaptive_threshold(image: np.ndarray) -> np.ndarray:
        """Binarisation adaptative pour améliorer le contraste."""
        gray = ImagePreprocessor.to_grayscale(image)
        return cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )

    @staticmethod
    def denoise(image: np.ndarray, strength: int = 10) -> np.ndarray:
        """Débruitage."""
        if len(image.shape) == 2:
            return cv2.fastNlMeansDenoising(image, None, strength, 7, 21)
        return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)

    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Améliore le contraste avec CLAHE."""
        gray = ImagePreprocessor.to_grayscale(image)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)

    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """Corrige l'inclinaison de l'image."""
        gray = ImagePreprocessor.to_grayscale(image)

        # Détection des contours
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Détection des lignes avec Hough
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 100,
            minLineLength=100, maxLineGap=10
        )

        if lines is None:
            return image

        # Calculer l'angle moyen des lignes horizontales
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 != 0:
                angle = np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi
                if abs(angle) < 10:  # Seulement les lignes presque horizontales
                    angles.append(angle)

        if not angles:
            return image

        median_angle = np.median(angles)

        if abs(median_angle) < 0.5:  # Pas besoin de corriger si < 0.5°
            return image

        # Rotation pour corriger
        h, w = gray.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            borderMode=cv2.BORDER_REPLICATE
        )

        return rotated


@dataclass
class OCRPageResult:
    """Résultat OCR pour une page."""
    page_num: int
    text: str
    char_count: int
    config_applied: dict = field(default_factory=dict)


@dataclass
class OCRResult:
    """Résultat d'extraction OCR d'un PDF."""
    pdf_path: str
    bidul_numero: Optional[int]
    mois: Optional[int]
    annee: Optional[int]
    num_pages: int
    pages: list[OCRPageResult] = field(default_factory=list)
    full_text: str = ""
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.full_text) > 100


class ScanExtractor:
    """Extracteur de texte pour PDFs scannés."""

    def __init__(self, ocr_engine: str = 'paddleocr', dpi: int = 200, use_sections: bool = True, auto_layout: bool = False):
        """
        Initialise l'extracteur OCR.

        Args:
            ocr_engine: Moteur OCR à utiliser ('paddleocr', 'easyocr', 'google')
            dpi: Résolution pour la conversion PDF → Image (200 par défaut, bon compromis vitesse/qualité)
            use_sections: Si True, utilise l'extraction par sections A6 quand configuré
            auto_layout: Si True, détecte automatiquement le layout (colonnes, orientation)
        """
        self.ocr = OCREngine(engine=ocr_engine)
        self.preprocessor = ImagePreprocessor()
        self.dpi = dpi
        self.use_sections = use_sections
        self.auto_layout = auto_layout
        self._section_extractor = None

    @property
    def section_extractor(self):
        """Lazy loading du SectionOCRExtractor."""
        if self._section_extractor is None:
            from .section_extractor import SectionOCRExtractor
            self._section_extractor = SectionOCRExtractor(self.ocr)
        return self._section_extractor

    def extract_from_pdf(self, pdf_path: str, config: Optional[ScanConfig] = None) -> OCRResult:
        """
        Extrait le texte d'un PDF scanné.

        Args:
            pdf_path: Chemin vers le PDF
            config: Configuration depuis biduls.description.csv
                    (orientation, pages utiles, etc.)

        Returns:
            OCRResult avec le texte extrait et les métadonnées
        """
        from .extractor import extract_bidul_info

        path = Path(pdf_path)
        filename = path.name
        numero, mois, annee = extract_bidul_info(filename)

        logger.info(f"Extraction OCR de {pdf_path}")

        # Charger la config si non fournie
        if config is None and numero:
            config = load_bidul_config(numero)

        # Essayer l'extraction par sections si activée
        if self.use_sections and numero:
            section_result = self._extract_with_sections(pdf_path, numero, mois, annee)
            if section_result:
                return section_result

        # Fallback: extraction classique (page entière)
        return self._extract_classic(pdf_path, config, numero, mois, annee)

    def _extract_with_sections(
        self,
        pdf_path: str,
        numero: int,
        mois: Optional[int],
        annee: Optional[int]
    ) -> Optional[OCRResult]:
        """
        Extraction par sections A6 ou par template SVG si configuré.

        Priorité:
        1. Template SVG si svg_template='1' dans CSV ou fichier bidul_{numero}.svg existe
        2. Extraction par sections A6 selon la config CSV
        3. None (fallback vers extraction classique)

        Returns:
            OCRResult si l'extraction par sections/SVG est possible, None sinon
        """
        from .section_extractor import load_section_config
        from .svg_template import get_template_manager

        section_config = load_section_config(numero)
        if not section_config:
            logger.debug(f"Bidul {numero}: pas de config sections, utilise extraction classique")
            return None

        # Vérifier si on doit utiliser un template SVG (priorité absolue)
        use_svg = section_config.use_svg_template()
        svg_template = None

        if use_svg:
            svg_template = get_template_manager().get_template(numero)
            if svg_template:
                logger.info(f"Bidul {numero}: utilisation du template SVG (override)")
            else:
                logger.warning(f"Bidul {numero}: svg_template=1 mais aucun template trouvé")
                use_svg = False

        # Si pas de SVG, vérifier qu'il y a des sections configurées
        if not use_svg and not section_config.page1 and not section_config.page2:
            logger.debug(f"Bidul {numero}: config sans sections définies")
            return None

        try:
            # Convertir PDF en images
            images = convert_from_path(str(pdf_path), dpi=self.dpi)
            num_pages = len(images)

            # Déterminer les pages à traiter
            # Priorité: pages_override du CSV > pages du template SVG > pages de la config sections
            if section_config.pages_override:
                # Le CSV spécifie explicitement les pages à traiter
                pages_to_process = [p for p in section_config.pages_override if 1 <= p <= num_pages]
            elif use_svg and svg_template:
                # Utiliser les pages définies dans le template SVG
                pages_to_process = [p for p in svg_template.get_all_page_nums() if p <= num_pages]
            else:
                pages_to_process = section_config.get_pages_to_process(num_pages)

            extraction_mode = 'svg_template' if use_svg else 'sections'
            logger.info(f"Bidul {numero}: extraction {extraction_mode}, pages {pages_to_process}")

            result = OCRResult(
                pdf_path=pdf_path,
                bidul_numero=numero,
                mois=mois,
                annee=annee,
                num_pages=num_pages,
                metadata={
                    'dpi': self.dpi,
                    'ocr_engine': self.ocr.engine_name,
                    'extraction_mode': extraction_mode,
                    'date_format': section_config.date_format,
                    'pages_processed': pages_to_process,
                    'svg_template': svg_template.source_path.name if svg_template and svg_template.source_path else None,
                }
            )

            all_texts = []

            for page_num in pages_to_process:
                if page_num > len(images):
                    logger.warning(f"Page {page_num} demandée mais PDF n'a que {len(images)} pages")
                    continue

                pil_image = images[page_num - 1]  # images est 0-indexed
                image = self.preprocessor.pil_to_cv2(pil_image)

                # Prétraitement basique (deskew, denoise)
                image = self._preprocess_basic(image)

                if use_svg and svg_template:
                    # Extraction par template SVG
                    page_result = self.section_extractor.extract_page_by_svg_template(
                        image, page_num, svg_template, section_config=section_config
                    )
                    page_text = page_result.full_text
                    zones_info = [s.section.value for s in page_result.sections]
                    logger.info(f"Page {page_num}: {len(page_result.sections)} zones SVG, {len(page_text)} caractères")

                    page_ocr_result = OCRPageResult(
                        page_num=page_num,
                        text=page_text,
                        char_count=len(page_text),
                        config_applied={
                            'svg_template': svg_template.source_path.name if svg_template.source_path else 'generated',
                            'zones_count': len(page_result.sections),
                            'orientation_texte': svg_template.orientation_texte,
                        }
                    )
                else:
                    # Extraction par sections A6
                    page_config = section_config.get_page_config(page_num)

                    if page_config and page_config.sections_utiles:
                        page_result = self.section_extractor.extract_page_by_sections(
                            image, page_num, page_config
                        )
                        page_text = page_result.full_text
                        sections_info = [s.section.value for s in page_result.sections]
                        logger.info(f"Page {page_num}: sections {sections_info}, {len(page_text)} caractères")
                    else:
                        # Pas de config pour cette page, extraction classique
                        page_text = self.ocr.ocr_image(image, num_columns=1)
                        logger.info(f"Page {page_num}: extraction complète, {len(page_text)} caractères")

                    page_ocr_result = OCRPageResult(
                        page_num=page_num,
                        text=page_text,
                        char_count=len(page_text),
                        config_applied={
                            'sections': [s.value for s in page_config.sections_utiles] if page_config else [],
                            'colonnes': page_config.colonnes_par_section if page_config else 1,
                            'orientation_texte': page_config.orientation_texte.value if page_config else 'portrait',
                        }
                    )

                all_texts.append(page_text)
                result.pages.append(page_ocr_result)

            result.full_text = '\n\n'.join(t for t in all_texts if t)
            return result

        except Exception as e:
            logger.error(f"Erreur extraction sections Bidul {numero}: {e}")
            return None

    def _extract_classic(
        self,
        pdf_path: str,
        config: Optional[ScanConfig],
        numero: Optional[int],
        mois: Optional[int],
        annee: Optional[int]
    ) -> OCRResult:
        """Extraction classique (page entière, sans découpage en sections)."""
        try:
            # Convertir PDF en images
            images = convert_from_path(str(pdf_path), dpi=self.dpi)
            num_pages = len(images)

            # Pour les PDFs à 3 pages, seule la page 3 contient l'agenda résumé
            # Pages 1-2 sont des articles, pas des événements
            if num_pages == 3:
                pages_to_process = [3]
                logger.info(f"PDF 3 pages détecté - extraction page 3 uniquement (agenda résumé)")
            else:
                pages_to_process = list(range(1, num_pages + 1))

            result = OCRResult(
                pdf_path=pdf_path,
                bidul_numero=numero,
                mois=mois,
                annee=annee,
                num_pages=num_pages,
                metadata={
                    'dpi': self.dpi,
                    'ocr_engine': self.ocr.engine_name,
                    'extraction_mode': 'auto-layout' if self.auto_layout else 'classic',
                    'auto_layout': self.auto_layout,
                    'config_numero': config.numero if config else None,
                    'date_format': config.date_format if config else 'inline',
                    'page1_sections': config.page1_sections if config else '',
                    'page2_sections': config.page2_sections if config else '',
                    'pages_processed': pages_to_process,
                }
            )

            for page_num in pages_to_process:
                pil_image = images[page_num - 1]  # images est 0-indexed
                page_config = self._get_page_config(config, page_num)

                # Convertir PIL → numpy BGR
                image = self.preprocessor.pil_to_cv2(pil_image)

                # Prétraitement selon config
                image = self._preprocess(image, page_config)

                # OCR avec nombre de colonnes ou auto-layout
                if self.auto_layout:
                    page_text = self.ocr.ocr_image(image, num_columns=1, auto_layout=True)
                    logger.debug(f"Page {page_num}: OCR avec auto-layout")
                else:
                    num_columns = page_config.get('colonnes', 1)
                    page_text = self.ocr.ocr_image(image, num_columns=num_columns)
                    if num_columns > 1:
                        logger.debug(f"Page {page_num}: OCR avec {num_columns} colonnes")

                page_result = OCRPageResult(
                    page_num=page_num,
                    text=page_text,
                    char_count=len(page_text),
                    config_applied=page_config
                )
                result.pages.append(page_result)

            # Assembler le texte complet
            result.full_text = '\n\n'.join(
                p.text for p in result.pages if p.text
            )

            return result

        except Exception as e:
            logger.error(f"Erreur extraction OCR {pdf_path}: {e}")
            return OCRResult(
                pdf_path=pdf_path,
                bidul_numero=numero,
                mois=mois,
                annee=annee,
                num_pages=0,
                error=str(e)
            )

    def _preprocess_basic(self, image: np.ndarray) -> np.ndarray:
        """Prétraitement basique sans rotation (utilisé pour l'extraction par sections)."""
        # Correction d'inclinaison légère
        image = self.preprocessor.deskew(image)
        # Débruitage léger
        image = self.preprocessor.denoise(image, strength=5)
        return image

    def _get_page_config(self, config: Optional[ScanConfig], page_num: int) -> dict:
        """Extrait la config pour une page spécifique."""
        if not config:
            return {
                'rotate': False,
                'remove_background': False,
                'colonnes': 1,
                'sections': [],
                'date_format': 'inline',
            }

        return {
            'rotate': config.needs_rotation(page_num),
            'remove_background': config.fond_colore,
            'colonnes': config.get_colonnes(page_num),
            'sections': config.get_sections(page_num),
            'date_format': config.date_format,
        }

    def _preprocess(self, image: np.ndarray, config: dict) -> np.ndarray:
        """Applique le prétraitement selon la config."""

        # 1. Rotation si nécessaire (texte en paysage)
        if config.get('rotate'):
            image = self.preprocessor.rotate_90(image, clockwise=False)
            logger.debug("Image rotée de 90° anti-horaire")

        # 2. Suppression fond coloré
        if config.get('remove_background'):
            image = self.preprocessor.remove_colored_background(image)
            logger.debug("Fond coloré supprimé")

        # 3. Correction d'inclinaison légère
        image = self.preprocessor.deskew(image)

        # 4. Amélioration contraste (convertit en grayscale)
        # Note: PaddleOCR gère bien les images couleur, donc on garde en couleur
        # image = self.preprocessor.enhance_contrast(image)

        # 5. Débruitage léger (garde les détails)
        image = self.preprocessor.denoise(image, strength=5)

        return image

    def extract_page(self, pdf_path: str, page_num: int, config: Optional[ScanConfig] = None) -> Optional[OCRPageResult]:
        """Extrait une seule page d'un PDF scanné."""
        try:
            # Convertir uniquement la page demandée
            images = convert_from_path(
                str(pdf_path),
                dpi=self.dpi,
                first_page=page_num,
                last_page=page_num
            )

            if not images:
                return None

            pil_image = images[0]
            page_config = self._get_page_config(config, page_num)

            # Prétraitement
            image = self.preprocessor.pil_to_cv2(pil_image)
            image = self._preprocess(image, page_config)

            # OCR avec nombre de colonnes
            num_columns = page_config.get('colonnes', 1)
            text = self.ocr.ocr_image(image, num_columns=num_columns)

            if num_columns > 1:
                logger.debug(f"Page {page_num}: OCR avec {num_columns} colonnes")

            return OCRPageResult(
                page_num=page_num,
                text=text,
                char_count=len(text),
                config_applied=page_config
            )

        except Exception as e:
            logger.error(f"Erreur extraction page {page_num} de {pdf_path}: {e}")
            return None


# Test standalone
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python ocr.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    extractor = ScanExtractor()
    result = extractor.extract_from_pdf(pdf_path)

    print(f"Fichier: {result.pdf_path}")
    print(f"Bidul #{result.bidul_numero} ({result.mois}/{result.annee})")
    print(f"Pages: {result.num_pages}")
    print(f"Caractères: {len(result.full_text)}")

    if result.error:
        print(f"Erreur: {result.error}")
    else:
        print(f"\n--- Extrait (2000 premiers caractères) ---")
        print(result.full_text[:2000])

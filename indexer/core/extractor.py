"""
Module d'extraction de texte depuis les PDFs.

Gère l'extraction de texte natif (PDFs texte) et prépare pour l'OCR (PDFs scan).
Utilise biduls.description.csv pour déterminer les pages à extraire.
"""

import csv
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    raise ImportError("PyMuPDF requis: pip install PyMuPDF")

logger = logging.getLogger(__name__)


@dataclass
class BidulConfig:
    """Configuration d'extraction pour un numéro de Bidul."""
    numero: int
    type_source: str  # 'scan' ou 'texte'
    pages_utiles: list[int] = field(default_factory=list)  # Pages avec texte utile (1-indexed)

    @classmethod
    def from_csv_row(cls, row: dict) -> Optional['BidulConfig']:
        """
        Crée une config depuis une ligne du CSV biduls.description.csv.

        Note: Le CSV décrit la structure logique du livret (pages 1/2 du format imprimé).
        Pour les PDFs:
        - PDFs à 3 pages: page 3 = agenda complet consolidé
        - PDFs à 2 pages: page 2 = agenda
        - page1/page2 du CSV indiquent si ces sections contiennent du texte utile
        """
        try:
            # Le nom de colonne peut avoir des variantes d'encodage
            numero = 0
            for key in ['numéros', 'numeros', 'num\xe9ros']:
                if key in row:
                    try:
                        numero = int(row[key])
                        break
                    except (ValueError, TypeError):
                        continue

            if numero == 0:
                return None

            type_source = row.get('scan/texte', 'scan')

            # Déterminer les pages logiques avec texte utile
            has_page1 = bool(row.get('page1.sections texte utile', '').strip())
            has_page2 = bool(row.get('page2.sections texte utile', '').strip())

            # Convertir en pages PDF réelles
            # Pour les PDFs texte: généralement la dernière page contient l'agenda complet
            # pages_utiles sera interprété différemment selon num_pages du PDF
            pages_utiles = []
            if has_page1:
                pages_utiles.append(1)
            if has_page2:
                pages_utiles.append(2)

            # Si aucune page spécifiée mais c'est un texte, défaut
            if not pages_utiles and type_source == 'texte':
                pages_utiles = [2]

            return cls(numero=numero, type_source=type_source, pages_utiles=pages_utiles)

        except (ValueError, KeyError) as e:
            logger.debug(f"Erreur parsing config row: {e}")
            return None


class BidulConfigLoader:
    """Charge et gère les configurations d'extraction depuis biduls.description.csv."""

    def __init__(self, csv_path: Optional[str] = None):
        """
        Initialise le loader.

        Args:
            csv_path: Chemin vers biduls.description.csv. Si None, cherche dans corpus/.
        """
        if csv_path is None:
            # Chercher dans le répertoire corpus relatif à ce fichier
            csv_path = Path(__file__).parent.parent / 'corpus' / 'biduls.description.csv'

        self.csv_path = Path(csv_path)
        self.configs: dict[int, BidulConfig] = {}
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
                    reader = csv.DictReader(f)
                    for row in reader:
                        config = BidulConfig.from_csv_row(row)
                        if config:
                            self.configs[config.numero] = config

                logger.info(f"Chargé {len(self.configs)} configurations depuis {self.csv_path} ({encoding})")
                return

            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Erreur chargement config ({encoding}): {e}")
                continue

        logger.error(f"Impossible de lire {self.csv_path} avec les encodages disponibles")

    def get_config(self, numero: int) -> Optional[BidulConfig]:
        """Retourne la config pour un numéro, ou None si non trouvée."""
        return self.configs.get(numero)

    def get_nearest_config(self, numero: int) -> Optional[BidulConfig]:
        """
        Retourne la config la plus proche pour un numéro non configuré.

        Cherche d'abord en dessous, puis au-dessus du numéro demandé.
        """
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

    def get_fallback_configs(self, numero: int) -> list[BidulConfig]:
        """
        Retourne une liste de configs à essayer, ordonnée par pertinence.

        1. Config exacte pour ce numéro
        2. Config la plus proche (même type de source si possible)
        3. Autres configs du même type
        """
        result = []

        # Config exacte
        if numero in self.configs:
            result.append(self.configs[numero])

        # Trouver le type de source probable
        exact = self.configs.get(numero)
        target_type = exact.type_source if exact else ('texte' if numero >= 178 else 'scan')

        # Configs proches du même type
        all_nums = sorted(self.configs.keys())
        same_type = [n for n in all_nums if self.configs[n].type_source == target_type]

        # Trier par proximité
        same_type.sort(key=lambda n: abs(n - numero))

        for n in same_type[:5]:  # Max 5 fallbacks
            if n != numero and self.configs[n] not in result:
                result.append(self.configs[n])

        return result


# Singleton pour éviter de recharger le CSV à chaque appel
_config_loader: Optional[BidulConfigLoader] = None


def get_config_loader() -> BidulConfigLoader:
    """Retourne le loader de configuration (singleton)."""
    global _config_loader
    if _config_loader is None:
        _config_loader = BidulConfigLoader()
    return _config_loader


@dataclass
class PageText:
    """Texte extrait d'une page."""
    page_num: int
    raw_text: str
    char_count: int
    is_native: bool  # True si texte natif, False si OCR nécessaire


@dataclass
class ExtractionResult:
    """Résultat d'extraction d'un PDF."""
    pdf_path: str
    bidul_numero: Optional[int]
    mois: Optional[int]
    annee: Optional[int]
    num_pages: int
    pages: list[PageText] = field(default_factory=list)
    full_text: str = ""
    is_native: bool = True
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.full_text) > 100


def extract_bidul_info(filename: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Extrait numéro, mois et année depuis le nom du fichier.

    Formats supportés:
    - "2023-05 Bidul 280.pdf"
    - "2018-02 Bidul 230.pdf"
    - "Bidul 280.pdf"
    """
    # Pattern: YYYY-MM Bidul NNN
    match = re.search(r"(\d{4})-(\d{2})\s*Bidul[- ]?(\d+)", filename, re.IGNORECASE)
    if match:
        return int(match.group(3)), int(match.group(2)), int(match.group(1))

    # Pattern: Bidul NNN
    match = re.search(r"Bidul[- ]?(\d+)", filename, re.IGNORECASE)
    if match:
        return int(match.group(1)), None, None

    return None, None, None


class TextExtractor:
    """
    Extracteur de texte pour les PDFs du Bidul.

    Pour les PDFs avec texte natif (n° >= 178), extraction directe.
    Pour les scans (n° < 178), signale que l'OCR est nécessaire.

    Utilise biduls.description.csv pour déterminer automatiquement
    quelles pages contiennent du texte utile.

    Préserve les informations de formatage (gras, italique) via des balises:
    - <b>texte</b> pour le gras
    - <i>texte</i> pour l'italique
    - <bi>texte</bi> pour gras+italique
    """

    MIN_CHARS_FOR_NATIVE = 500  # Minimum de caractères pour considérer le texte valide
    COL_THRESHOLD = 150  # Distance minimum entre colonnes (en points)

    def __init__(self, preserve_formatting: bool = True):
        """
        Initialise l'extracteur.

        Args:
            preserve_formatting: Si True, ajoute des balises <b>, <i> pour le formatage
        """
        self.preserve_formatting = preserve_formatting

    def _detect_formatting(self, span: dict) -> tuple[bool, bool]:
        """
        Détecte si un span est en gras et/ou italique.

        Args:
            span: Dictionnaire span de PyMuPDF avec 'font' et 'flags'

        Returns:
            Tuple (is_bold, is_italic)
        """
        font_name = span.get('font', '').lower()
        flags = span.get('flags', 0)

        # Détection gras: via nom de police ou flags
        is_bold = any(kw in font_name for kw in ['bold', 'black', 'heavy', 'demi'])

        # Détection italique: via nom de police ou flags (bit 1)
        is_italic = any(kw in font_name for kw in ['italic', 'oblique']) or bool(flags & 2)

        return is_bold, is_italic

    def _wrap_with_formatting(self, text: str, is_bold: bool, is_italic: bool) -> str:
        """
        Enveloppe le texte avec les balises de formatage appropriées.

        Args:
            text: Texte à envelopper
            is_bold: True si gras
            is_italic: True si italique

        Returns:
            Texte avec balises
        """
        if not text.strip():
            return text

        if is_bold and is_italic:
            return f"<bi>{text}</bi>"
        elif is_bold:
            return f"<b>{text}</b>"
        elif is_italic:
            return f"<i>{text}</i>"
        return text

    def _extract_by_columns(self, page) -> str:
        """
        Extrait le texte d'une page en respectant l'ordre des colonnes.

        Lit les colonnes de gauche à droite, chaque colonne de haut en bas.
        Préserve les informations de formatage (gras, italique) via des balises.

        Args:
            page: Page PyMuPDF

        Returns:
            Texte ordonné par colonnes avec balises de formatage
        """
        # Utiliser get_text('dict') pour avoir accès aux infos de formatage (font, flags)
        page_dict = page.get_text('dict')
        blocks = page_dict.get('blocks', [])

        # Filtrer les blocs de texte (type 0)
        text_blocks = [b for b in blocks if b.get('type') == 0]

        if not text_blocks:
            return ""

        # Construire une liste de (x0, y0, formatted_text) pour chaque bloc
        block_data = []
        for block in text_blocks:
            x0 = block.get('bbox', [0, 0, 0, 0])[0]
            y0 = block.get('bbox', [0, 0, 0, 0])[1]

            # Extraire le texte avec formatage depuis les lignes et spans
            block_text_parts = []
            for line in block.get('lines', []):
                line_text_parts = []
                for span in line.get('spans', []):
                    text = span.get('text', '')
                    if not text:
                        continue

                    if self.preserve_formatting:
                        is_bold, is_italic = self._detect_formatting(span)
                        formatted_text = self._wrap_with_formatting(text, is_bold, is_italic)
                        line_text_parts.append(formatted_text)
                    else:
                        line_text_parts.append(text)

                if line_text_parts:
                    block_text_parts.append(''.join(line_text_parts))

            block_text = '\n'.join(block_text_parts).strip()
            if block_text:
                block_data.append((x0, y0, block_text))

        if not block_data:
            return ""

        # Identifier les colonnes par position x0
        x0_values = sorted(set(round(b[0]) for b in block_data))

        # Grouper les x0 proches en colonnes
        column_starts = []
        current_col_x = None
        for x in x0_values:
            if current_col_x is None or x - current_col_x > self.COL_THRESHOLD:
                column_starts.append(x)
                current_col_x = x

        # Assigner chaque bloc à une colonne
        def get_column(x0):
            for i, col_x in enumerate(column_starts):
                if i == len(column_starts) - 1 or x0 < column_starts[i + 1] - self.COL_THRESHOLD / 2:
                    return i
            return len(column_starts) - 1

        # Organiser les blocs par colonne puis par position Y
        columns_content = [[] for _ in column_starts]
        for x0, y0, text in block_data:
            col_idx = get_column(x0)
            columns_content[col_idx].append((y0, text))

        # Trier chaque colonne par Y (haut en bas)
        for col in columns_content:
            col.sort(key=lambda x: x[0])

        # Assembler le texte: colonne par colonne
        result_parts = []
        for col in columns_content:
            col_text = '\n'.join(text for y, text in col if text)
            if col_text:
                result_parts.append(col_text)

        return '\n\n'.join(result_parts)

    def _get_pages_to_extract(self, numero: Optional[int], num_pages: int) -> tuple[list[int], bool]:
        """
        Détermine les pages PDF à extraire selon la configuration.

        Priorité:
        1. Vérifier si c'est un scan (pas d'extraction possible)
        2. Si page 3 existe → extraire page 3 (agenda complet consolidé)
        3. Sinon, utiliser biduls.description.csv pour déterminer les pages

        Args:
            numero: Numéro du Bidul
            num_pages: Nombre total de pages du PDF

        Returns:
            Tuple (pages à extraire, is_scan)
            - pages: Liste des pages PDF à extraire (1-indexed)
            - is_scan: True si c'est un scan (OCR nécessaire)
        """
        if numero is None:
            # Pas de numéro détecté, extraire toutes les pages
            return list(range(1, num_pages + 1)), False

        # Charger la configuration
        loader = get_config_loader()
        config = loader.get_config(numero)
        if config is None:
            config = loader.get_nearest_config(numero)

        # Vérifier si c'est un scan
        if config and config.type_source == 'scan':
            # Pour les scans à 3 pages, seule la page 3 contient l'agenda résumé
            # Les pages 1-2 sont des articles, pas des événements
            if num_pages == 3:
                logger.debug(f"Bidul {numero}: type=scan, 3 pages -> OCR page 3 uniquement")
                return [3], True
            logger.debug(f"Bidul {numero}: type=scan -> OCR nécessaire")
            return list(range(1, num_pages + 1)), True

        # C'est un PDF texte - déterminer les pages à extraire

        # PRIORITÉ: Si page 3 existe, c'est l'agenda complet
        if num_pages >= 3:
            logger.debug(f"Bidul {numero}: page 3 existe -> extraction page 3")
            return [3], False

        # Sinon, utiliser la configuration du CSV
        if config:
            has_page1 = 1 in config.pages_utiles
            has_page2 = 2 in config.pages_utiles

            if num_pages == 2:
                if has_page1 and has_page2:
                    logger.debug(f"Bidul {numero}: PDF 2 pages, config [1,2] -> pages PDF [1, 2]")
                    return [1, 2], False
                elif has_page2:
                    logger.debug(f"Bidul {numero}: PDF 2 pages, config [2] -> page PDF [2]")
                    return [2], False
                elif has_page1:
                    logger.debug(f"Bidul {numero}: PDF 2 pages, config [1] -> page PDF [1]")
                    return [1], False
                else:
                    # Défaut: page 2
                    logger.debug(f"Bidul {numero}: PDF 2 pages, pas de config -> page PDF [2]")
                    return [2], False

            elif num_pages == 1:
                logger.debug(f"Bidul {numero}: PDF 1 page -> page PDF [1]")
                return [1], False

            else:
                # PDF avec autre nombre de pages: extraire toutes
                logger.debug(f"Bidul {numero}: PDF {num_pages} pages -> toutes")
                return list(range(1, num_pages + 1)), False

        # Fallback sans config
        if num_pages >= 2:
            return [2], False
        else:
            return [1], False

    def extract(self, pdf_path: str, pages_to_extract: list[int] | None = None) -> ExtractionResult:
        """
        Extrait le texte d'un PDF.

        Args:
            pdf_path: Chemin vers le PDF
            pages_to_extract: Pages à extraire (1-indexed). Si None, auto-détecté via config.

        Returns:
            ExtractionResult avec le texte et métadonnées
        """
        path = Path(pdf_path)
        filename = path.name
        numero, mois, annee = extract_bidul_info(filename)

        try:
            doc = fitz.open(pdf_path)
            num_pages = len(doc)

            # Déterminer les pages à extraire via biduls.description.csv
            is_scan = False
            if pages_to_extract is None:
                pages_to_extract, is_scan = self._get_pages_to_extract(numero, num_pages)

            # Si c'est un scan, retourner un résultat vide (OCR nécessaire)
            if is_scan:
                doc.close()
                logger.info(f"Bidul {numero}: scan détecté, OCR nécessaire")
                return ExtractionResult(
                    pdf_path=pdf_path,
                    bidul_numero=numero,
                    mois=mois,
                    annee=annee,
                    num_pages=num_pages,
                    pages=[],
                    full_text="",
                    is_native=False
                )

            logger.debug(f"Extraction {filename}: pages {pages_to_extract} sur {num_pages}")

            pages = []
            full_text_parts = []
            total_chars = 0

            for page_num in pages_to_extract:
                if page_num < 1 or page_num > num_pages:
                    continue

                page = doc[page_num - 1]  # PyMuPDF utilise l'index 0-based

                # Pour les PDFs texte, utiliser l'extraction par colonnes
                # pour respecter l'ordre de lecture gauche→droite, haut→bas
                text = self._extract_by_columns(page)

                char_count = len(text)
                total_chars += char_count

                # Une page avec moins de 100 caractères est probablement un scan
                is_native = char_count >= 100

                page_result = PageText(
                    page_num=page_num,
                    raw_text=text,
                    char_count=char_count,
                    is_native=is_native
                )
                pages.append(page_result)
                full_text_parts.append(text)

            doc.close()

            # Le PDF est considéré comme natif si au moins 50% des pages ont du texte
            pages_with_text = sum(1 for p in pages if p.is_native)
            is_native = len(pages) > 0 and pages_with_text >= len(pages) / 2

            return ExtractionResult(
                pdf_path=pdf_path,
                bidul_numero=numero,
                mois=mois,
                annee=annee,
                num_pages=num_pages,
                pages=pages,
                full_text="\n\n".join(full_text_parts),
                is_native=is_native
            )

        except Exception as e:
            logger.error(f"Erreur extraction {pdf_path}: {e}")
            return ExtractionResult(
                pdf_path=pdf_path,
                bidul_numero=numero,
                mois=mois,
                annee=annee,
                num_pages=0,
                error=str(e)
            )

    def extract_page(self, pdf_path: str, page_num: int) -> Optional[PageText]:
        """Extrait une seule page d'un PDF."""
        try:
            doc = fitz.open(pdf_path)
            if page_num < 1 or page_num > len(doc):
                doc.close()
                return None

            page = doc[page_num - 1]
            text = page.get_text().strip()
            doc.close()

            return PageText(
                page_num=page_num,
                raw_text=text,
                char_count=len(text),
                is_native=len(text) >= 100
            )
        except Exception as e:
            logger.error(f"Erreur extraction page {page_num} de {pdf_path}: {e}")
            return None


def detect_pdf_type(pdf_path: str) -> tuple[bool, dict]:
    """
    Détecte si un PDF est un scan ou du texte natif.

    Utilise plusieurs heuristiques combinées:
    1. Nombre de caractères extraits par page
    2. Présence de fonts embarquées
    3. Ratio images/texte (images pleine page = scan)
    4. Présence d'objets texte vs images

    Args:
        pdf_path: Chemin vers le PDF

    Returns:
        (is_scan, details): True si scan, False si texte natif,
                           avec un dict de détails d'analyse
    """
    details = {
        'pages': 0,
        'chars_total': 0,
        'chars_per_page': 0,
        'has_fonts': False,
        'has_fullpage_images': False,
        'image_pages': 0,
        'text_pages': 0,
        'fonts_count': 0,
        'reason': ''
    }

    try:
        doc = fitz.open(pdf_path)
        details['pages'] = len(doc)

        if len(doc) == 0:
            details['reason'] = 'PDF vide'
            doc.close()
            return True, details

        total_chars = 0
        image_pages = 0
        text_pages = 0
        all_fonts = set()

        for page_num in range(len(doc)):
            page = doc[page_num]

            # 1. Extraire le texte
            text = page.get_text().strip()
            char_count = len(text)
            total_chars += char_count

            # 2. Collecter les fonts utilisées sur la page
            fonts = page.get_fonts()
            for font in fonts:
                font_name = font[3] if len(font) > 3 else ''
                if font_name:
                    all_fonts.add(font_name)

            # 3. Vérifier les images
            images = page.get_images()
            page_rect = page.rect
            page_area = page_rect.width * page_rect.height

            has_fullpage_image = False
            for img in images:
                try:
                    # Obtenir la bbox de l'image
                    img_rects = page.get_image_rects(img[0])
                    for img_rect in img_rects:
                        img_area = img_rect.width * img_rect.height
                        # Image couvre plus de 80% de la page = scan probable
                        if img_area > 0.8 * page_area:
                            has_fullpage_image = True
                            break
                except:
                    pass

            if has_fullpage_image:
                image_pages += 1

            # Page considérée comme texte si > 200 caractères
            if char_count > 200:
                text_pages += 1

        doc.close()

        # Remplir les détails
        details['chars_total'] = total_chars
        details['chars_per_page'] = total_chars // details['pages'] if details['pages'] > 0 else 0
        details['has_fonts'] = len(all_fonts) > 0
        details['fonts_count'] = len(all_fonts)
        details['image_pages'] = image_pages
        details['text_pages'] = text_pages
        details['has_fullpage_images'] = image_pages > 0

        # Décision basée sur plusieurs critères

        # Critère 1: Majorité de pages avec images pleine page
        if image_pages > details['pages'] / 2:
            details['reason'] = f'Majorité de pages avec images pleine page ({image_pages}/{details["pages"]})'
            return True, details

        # Critère 2: Très peu de texte (< 100 chars/page en moyenne)
        if details['chars_per_page'] < 100:
            details['reason'] = f'Peu de texte ({details["chars_per_page"]} chars/page)'
            return True, details

        # Critère 3: Pas de fonts mais des images
        if not details['has_fonts'] and details['has_fullpage_images']:
            details['reason'] = 'Pas de fonts embarquées + images pleine page'
            return True, details

        # Critère 4: Moins de 50% de pages avec texte significatif
        if text_pages < details['pages'] / 2:
            details['reason'] = f'Peu de pages avec texte ({text_pages}/{details["pages"]})'
            return True, details

        # Sinon, c'est probablement du texte natif
        details['reason'] = f'Texte natif ({details["chars_per_page"]} chars/page, {details["fonts_count"]} fonts)'
        return False, details

    except Exception as e:
        details['reason'] = f'Erreur: {e}'
        logger.error(f"Erreur détection type PDF {pdf_path}: {e}")
        return True, details  # Par défaut, considérer comme scan en cas d'erreur


# Test standalone
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python extractor.py <pdf_path>")
        sys.exit(1)

    extractor = TextExtractor()
    result = extractor.extract(sys.argv[1])

    print(f"Fichier: {result.pdf_path}")
    print(f"Bidul #{result.bidul_numero} ({result.mois}/{result.annee})")
    print(f"Pages: {result.num_pages}")
    print(f"Texte natif: {result.is_native}")
    print(f"Caractères: {len(result.full_text)}")

    # Test de la nouvelle détection
    is_scan, details = detect_pdf_type(sys.argv[1])
    print(f"\nDétection avancée:")
    print(f"  Est un scan: {is_scan}")
    for k, v in details.items():
        print(f"  {k}: {v}")

    if result.error:
        print(f"Erreur: {result.error}")
    else:
        print(f"\n--- Extrait (1000 premiers caractères) ---")
        print(result.full_text[:1000])

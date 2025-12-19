"""
Module d'extraction de texte depuis les PDFs.

Gère l'extraction de texte natif (PDFs texte) et prépare pour l'OCR (PDFs scan).
"""

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
    """

    MIN_CHARS_FOR_NATIVE = 500  # Minimum de caractères pour considérer le texte valide
    COL_THRESHOLD = 150  # Distance minimum entre colonnes (en points)

    def __init__(self, skip_pages: list[int] | None = None):
        """
        Initialise l'extracteur.

        Args:
            skip_pages: Liste des pages à ignorer (1-indexed). Par défaut auto-détecté.
        """
        self.skip_pages = skip_pages

    def _extract_by_columns(self, page) -> str:
        """
        Extrait le texte d'une page en respectant l'ordre des colonnes.

        Lit les colonnes de gauche à droite, chaque colonne de haut en bas.

        Args:
            page: Page PyMuPDF

        Returns:
            Texte ordonné par colonnes
        """
        # Obtenir les blocs de texte avec positions (x0, y0, x1, y1, text, block_no, block_type)
        blocks = page.get_text('blocks')
        text_blocks = [b for b in blocks if b[6] == 0]  # Type 0 = texte

        if not text_blocks:
            return ""

        # Identifier les colonnes par position x0
        x0_values = sorted(set(round(b[0]) for b in text_blocks))

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
        for block in text_blocks:
            x0, y0, x1, y1, text, block_no, block_type = block
            col_idx = get_column(x0)
            columns_content[col_idx].append((y0, text.strip()))

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

    def extract(self, pdf_path: str, skip_pages: list[int] | None = None) -> ExtractionResult:
        """
        Extrait le texte d'un PDF.

        Args:
            pdf_path: Chemin vers le PDF
            skip_pages: Pages à ignorer (1-indexed). Si None, utilise le défaut.

        Returns:
            ExtractionResult avec le texte et métadonnées
        """
        path = Path(pdf_path)
        filename = path.name
        numero, mois, annee = extract_bidul_info(filename)

        try:
            doc = fitz.open(pdf_path)
            num_pages = len(doc)

            # Déterminer les pages à extraire
            # Pour les PDFs texte (178+) avec exactement 3 pages:
            # - Page 3 = résumé consolidé de tous les événements (2 colonnes, S1 S2 S3 S4)
            # - Pages 1 et 2 = versions partielles/dupliquées
            # → Extraire UNIQUEMENT la page 3
            pages_to_skip = skip_pages if skip_pages is not None else self.skip_pages
            if pages_to_skip is None:
                if numero and numero >= 178 and num_pages == 3:
                    # PDF texte standard à 3 pages: extraire uniquement page 3
                    pages_to_skip = [1, 2]
                else:
                    pages_to_skip = []

            pages = []
            full_text_parts = []
            total_chars = 0

            for i in range(num_pages):
                page_num = i + 1  # 1-indexed

                # Ignorer les pages spécifiées
                if page_num in pages_to_skip:
                    continue
                page = doc[i]

                # Pour les PDFs texte (178+), utiliser l'extraction par colonnes
                # pour respecter l'ordre de lecture gauche→droite, haut→bas
                if numero and numero >= 178:
                    text = self._extract_by_columns(page)
                else:
                    text = page.get_text().strip()

                char_count = len(text)
                total_chars += char_count

                # Une page avec moins de 100 caractères est probablement un scan
                is_native = char_count >= 100

                page_result = PageText(
                    page_num=i + 1,
                    raw_text=text,
                    char_count=char_count,
                    is_native=is_native
                )
                pages.append(page_result)
                full_text_parts.append(text)

            doc.close()

            # Le PDF est considéré comme natif si au moins 50% des pages ont du texte
            pages_with_text = sum(1 for p in pages if p.is_native)
            is_native = pages_with_text >= len(pages) / 2

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

    if result.error:
        print(f"Erreur: {result.error}")
    else:
        print(f"\n--- Extrait (1000 premiers caractères) ---")
        print(result.full_text[:1000])

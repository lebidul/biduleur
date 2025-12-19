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

    # Pages à ignorer par défaut pour les PDFs texte (178+)
    # - Page 1 : souvent un sous-ensemble de la page 2
    # - Page 3 : résumé qui duplique les événements
    # On n'extrait que la page 2 qui est la plus complète
    DEFAULT_SKIP_PAGES_TEXTE = [1, 3]

    def __init__(self, skip_pages: list[int] | None = None):
        """
        Initialise l'extracteur.

        Args:
            skip_pages: Liste des pages à ignorer (1-indexed). Par défaut [3] pour PDFs texte.
        """
        self.skip_pages = skip_pages

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

            # Déterminer les pages à ignorer
            pages_to_skip = skip_pages if skip_pages is not None else self.skip_pages
            if pages_to_skip is None:
                # Par défaut, ignorer page 3 pour les PDFs texte (178+)
                if numero and numero >= 178:
                    pages_to_skip = self.DEFAULT_SKIP_PAGES_TEXTE
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

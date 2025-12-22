#!/usr/bin/env python3
"""
Benchmark de qualité OCR sur les PDFs scannés du Bidul.

Teste l'extraction OCR sur des PDFs représentatifs et mesure la qualité
en comparant avec des mots-clés/événements attendus.

Usage:
    python benchmark/test_ocr_quality.py
    python benchmark/test_ocr_quality.py --bidul 174
    python benchmark/test_ocr_quality.py --all
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ocr import ScanExtractor, load_bidul_config
from core.ocr_postprocess import OCRPostProcessor

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Répertoire des archives
ARCHIVES_DIR = Path(__file__).parent.parent / "archives"

# Événements/mots-clés attendus par Bidul pour validation
# Ces données sont extraites manuellement des PDFs scannés
EXPECTED_CONTENT = {
    # Bidul 174 (2013-01) - Format moderne scanné, le plus facile
    174: {
        'events': [
            "Jam session",
            "Blues Spirit",
            "Théâtre d'impro",
            "impro",
            "concert",
        ],
        'lieux': [
            "Mans",  # Le Mans apparaît souvent
        ],
        'dates': [
            "janvier",
        ],
    },

    # Bidul 103 (2006-07) - Fond bleu cyan, difficulté moyenne
    103: {
        'events': [
            "Festival",
            "concert",
            "musique",
        ],
        'lieux': [
            "Mans",
        ],
        'dates': [
            "juillet",
        ],
    },

    # Bidul 35 (2000-05) - Portrait, 2 colonnes, facile
    35: {
        'events': [
            "concert",
            "musique",
            "fête",
        ],
        'lieux': [
            "Mans",
        ],
        'dates': [
            "mai",
        ],
    },

    # Bidul 13 (1998-03) - Portrait, 1 colonne, moyen
    13: {
        'events': [
            "concert",
            "musique",
        ],
        'lieux': [
            "Mans",
        ],
        'dates': [
            "mars",
        ],
    },

    # Bidul 2 (1997-03) - Paysage (rotation 90°), difficile
    2: {
        'events': [
            "concert",
            "musique",
        ],
        'lieux': [
            "Mans",
        ],
        'dates': [
            "mars",
        ],
    },
}


def find_pdf(numero: int) -> Path | None:
    """Trouve le PDF correspondant à un numéro de Bidul."""
    patterns = [
        f"*Bidul*{numero:03d}*.pdf",
        f"*Bidul*{numero}*.pdf",
        f"*Bidul_{numero}*.pdf",
        f"*Bidul {numero}*.pdf",
    ]
    for pattern in patterns:
        matches = list(ARCHIVES_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def calculate_score(text: str, expected: dict) -> dict:
    """
    Calcule un score de qualité basé sur la présence des mots-clés attendus.

    Returns:
        dict avec scores détaillés et score global
    """
    text_lower = text.lower()

    results = {
        'events': {'found': 0, 'total': 0, 'items': []},
        'lieux': {'found': 0, 'total': 0, 'items': []},
        'dates': {'found': 0, 'total': 0, 'items': []},
    }

    for category, items in expected.items():
        results[category]['total'] = len(items)
        for item in items:
            found = item.lower() in text_lower
            results[category]['items'].append((item, found))
            if found:
                results[category]['found'] += 1

    # Score global pondéré
    total_items = sum(r['total'] for r in results.values())
    found_items = sum(r['found'] for r in results.values())

    results['global_score'] = (found_items / total_items * 100) if total_items > 0 else 0
    results['total_found'] = found_items
    results['total_expected'] = total_items

    return results


def test_bidul(numero: int, extractor: ScanExtractor, postprocessor: OCRPostProcessor) -> dict:
    """
    Teste l'OCR sur un Bidul spécifique.

    Returns:
        dict avec résultats détaillés
    """
    pdf_path = find_pdf(numero)
    if not pdf_path:
        return {
            'numero': numero,
            'success': False,
            'error': f"PDF non trouvé pour Bidul {numero}"
        }

    logger.info(f"Test Bidul {numero}: {pdf_path.name}")

    # Charger la config
    config = load_bidul_config(numero)

    start_time = time.time()

    try:
        # Extraction OCR
        result = extractor.extract_from_pdf(str(pdf_path), config)

        if result.error:
            return {
                'numero': numero,
                'success': False,
                'error': result.error
            }

        # Post-traitement
        text = postprocessor.process(result.full_text)
        elapsed = time.time() - start_time

        # Calculer le score si des données attendues existent
        score_results = None
        if numero in EXPECTED_CONTENT:
            score_results = calculate_score(text, EXPECTED_CONTENT[numero])

        return {
            'numero': numero,
            'success': True,
            'pdf_path': str(pdf_path),
            'pages': result.num_pages,
            'char_count': len(text),
            'time': elapsed,
            'config_rotation': config.needs_rotation(2) if config else False,
            'score': score_results,
            'text_preview': text[:500],
        }

    except Exception as e:
        logger.error(f"Erreur Bidul {numero}: {e}")
        return {
            'numero': numero,
            'success': False,
            'error': str(e)
        }


def print_result(result: dict, verbose: bool = False):
    """Affiche le résultat d'un test."""
    numero = result['numero']

    if not result['success']:
        print(f"\n[{numero:3d}] ERREUR: {result['error']}")
        return

    score = result.get('score')
    score_str = f"{score['global_score']:.0f}%" if score else "N/A"

    print(f"\n[{numero:3d}] OK - {result['char_count']} chars en {result['time']:.1f}s - Score: {score_str}")

    if score:
        for category in ['events', 'lieux', 'dates']:
            cat_data = score[category]
            found = cat_data['found']
            total = cat_data['total']
            if total > 0:
                items_status = ', '.join(
                    f"{'[OK]' if f else '[X]'}{i}"
                    for i, f in cat_data['items']
                )
                try:
                    print(f"    {category}: {found}/{total} - {items_status}")
                except UnicodeEncodeError:
                    print(f"    {category}: {found}/{total} - {items_status}".encode('ascii', 'replace').decode())

    if verbose:
        print(f"    Aperçu: {result['text_preview'][:200]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark de qualité OCR sur les PDFs scannés du Bidul"
    )
    parser.add_argument('--bidul', '-b', type=int, help='Numéro de Bidul spécifique à tester')
    parser.add_argument('--all', '-a', action='store_true', help='Tester tous les Biduls avec données attendues')
    parser.add_argument('--dpi', '-d', type=int, default=200, help='Résolution DPI (défaut: 200)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Affichage détaillé')

    args = parser.parse_args()

    # Initialiser les extracteurs
    print("Initialisation de PaddleOCR...")
    extractor = ScanExtractor(dpi=args.dpi)
    postprocessor = OCRPostProcessor()
    print("OK\n")

    # Déterminer les Biduls à tester
    if args.bidul:
        numeros = [args.bidul]
    elif args.all:
        numeros = sorted(EXPECTED_CONTENT.keys())
    else:
        # Par défaut: les 5 représentatifs
        numeros = [174, 103, 35, 13, 2]

    print(f"{'='*60}")
    print(f"BENCHMARK OCR - {len(numeros)} PDF(s)")
    print(f"{'='*60}")

    results = []
    for numero in numeros:
        result = test_bidul(numero, extractor, postprocessor)
        results.append(result)
        print_result(result, args.verbose)

    # Résumé
    print(f"\n{'='*60}")
    print("RÉSUMÉ")
    print(f"{'='*60}")

    success_count = sum(1 for r in results if r['success'])
    scored_results = [r for r in results if r['success'] and r.get('score')]

    print(f"Réussis: {success_count}/{len(results)}")

    if scored_results:
        avg_score = sum(r['score']['global_score'] for r in scored_results) / len(scored_results)
        total_chars = sum(r['char_count'] for r in scored_results)
        total_time = sum(r['time'] for r in scored_results)

        print(f"Score moyen: {avg_score:.1f}%")
        print(f"Total caractères: {total_chars}")
        print(f"Temps total: {total_time:.1f}s")
        print(f"Moyenne temps/PDF: {total_time / len(scored_results):.1f}s")

    # Détails par difficulté
    print(f"\nDétails par difficulté:")
    difficulty = {
        174: "Facile (format moderne)",
        35: "Facile (portrait, 2 colonnes)",
        13: "Moyen (portrait, 1 colonne)",
        103: "Moyen (fond coloré)",
        2: "Difficile (rotation 90°)",
    }

    for r in results:
        if r['success'] and r.get('score'):
            diff = difficulty.get(r['numero'], "Inconnu")
            score = r['score']['global_score']
            print(f"  Bidul {r['numero']:3d}: {score:5.1f}% - {diff}")

    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

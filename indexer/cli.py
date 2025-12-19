#!/usr/bin/env python3
"""
CLI pour l'indexation des archives du Bidul.

Commandes:
    python cli.py init                  # Initialise la base de données
    python cli.py extract --numero 280  # Extrait un PDF
    python cli.py extract --range 280-290  # Extrait une plage
    python cli.py validate --numero 280 # Affiche l'extraction pour validation
    python cli.py stats                 # Statistiques globales
    python cli.py list                  # Liste les PDFs disponibles
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ajouter le parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexer.core.extractor import TextExtractor, extract_bidul_info
from indexer.core.parser import EventParser
from indexer.core.db import BidulDB

# Configuration
ARCHIVES_DIR = Path(__file__).parent / "archives"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def find_pdf(numero: int) -> Path | None:
    """Trouve le PDF correspondant à un numéro de Bidul."""
    for pdf_file in ARCHIVES_DIR.rglob("*.pdf"):
        n, _, _ = extract_bidul_info(pdf_file.name)
        if n == numero:
            return pdf_file
    return None


def list_pdfs() -> list[tuple[int, Path]]:
    """Liste tous les PDFs avec leur numéro."""
    pdfs = []
    for pdf_file in ARCHIVES_DIR.rglob("*.pdf"):
        n, m, a = extract_bidul_info(pdf_file.name)
        if n:
            pdfs.append((n, m, a, pdf_file))
    return sorted(pdfs, key=lambda x: x[0])


# =============================================================================
# Commandes
# =============================================================================

def cmd_init(args):
    """Initialise la base de données."""
    db = BidulDB()
    print(f"Initialisation de la base: {db.db_path}")
    db.init_schema()
    db.load_referentiels()

    stats = db.get_stats()
    print(f"\nBase initialisée:")
    print(f"  Lieux référencés: {stats['lieux_ref']}")
    print(f"  Villes référencées: {stats['villes_ref']}")


def cmd_extract(args):
    """Extrait et parse un ou plusieurs PDFs."""
    db = BidulDB()
    db.init_schema()

    extractor = TextExtractor()

    # Déterminer les numéros à traiter
    if args.numero:
        numeros = [args.numero]
    elif args.range:
        start, end = map(int, args.range.split('-'))
        numeros = list(range(start, end + 1))
    else:
        print("Erreur: spécifiez --numero ou --range")
        return 1

    total_events = 0
    success_count = 0

    for numero in numeros:
        pdf_path = find_pdf(numero)
        if not pdf_path:
            print(f"[{numero}] PDF non trouvé")
            continue

        print(f"[{numero}] Extraction: {pdf_path.name}")

        # Extraction du texte
        result = extractor.extract(str(pdf_path))

        if not result.success:
            print(f"  Erreur: {result.error}")
            continue

        if not result.is_native:
            print(f"  ATTENTION: PDF scan détecté, OCR nécessaire")
            if not args.force:
                continue

        # Parsing des événements
        parser = EventParser(bidul_mois=result.mois, bidul_annee=result.annee)
        events = parser.parse(result.full_text)

        print(f"  Pages: {result.num_pages}, Caractères: {len(result.full_text)}")
        print(f"  Événements trouvés: {len(events)}")

        if events:
            confidences = [e.confidence for e in events]
            avg_conf = sum(confidences) / len(confidences)
            print(f"  Confidence moyenne: {avg_conf:.2f}")

        # Sauvegarder en base (sauf dry-run)
        if not args.dry_run:
            # Supprimer les anciens événements
            db.delete_evenements(numero)

            # Insérer le bidul
            type_source = 'texte' if result.is_native else 'scan'
            db.insert_bidul(
                numero=numero,
                mois=result.mois,
                annee=result.annee,
                pdf_filename=pdf_path.name,
                type_source=type_source
            )

            # Insérer les événements
            for event in events:
                db.insert_evenement(numero, event)

            db.update_bidul_status(numero, 'extracted')
            print(f"  Sauvegardé en base")

        total_events += len(events)
        success_count += 1

    print(f"\n{'='*50}")
    print(f"Terminé: {success_count}/{len(numeros)} PDFs, {total_events} événements")

    return 0


def cmd_validate(args):
    """Affiche les événements extraits pour validation."""
    db = BidulDB()

    bidul = db.get_bidul(args.numero)
    if not bidul:
        print(f"Bidul #{args.numero} non trouvé en base")
        print("Lancez d'abord: python cli.py extract --numero", args.numero)
        return 1

    events = db.get_evenements(args.numero)

    print(f"{'='*60}")
    print(f"BIDUL #{args.numero} - {bidul['mois']}/{bidul['annee']}")
    print(f"Fichier: {bidul['pdf_filename']}")
    print(f"Type: {bidul['type_source']}")
    print(f"Statut: {bidul['extraction_status']}")
    print(f"{'='*60}")
    print(f"\n{len(events)} événements extraits:\n")

    for i, e in enumerate(events, 1):
        print(f"[{i}] {e['date_evenement'] or 'Date?'} - {e['heure'] or '?h'}")

        # Artistes
        artistes = json.loads(e['artistes']) if e['artistes'] else []
        if artistes:
            print(f"    Artistes: {', '.join(artistes)}")

        # Spectacles
        spectacles = json.loads(e['spectacles']) if e['spectacles'] else []
        if spectacles:
            print(f"    Spectacles: {', '.join(spectacles)}")

        # Lieu
        print(f"    Lieu: {e['lieu_raw'] or '?'}", end='')
        if e['ville_raw']:
            print(f", {e['ville_raw']}", end='')
        print()

        # Prix
        if e['tarif_raw']:
            print(f"    Prix: {e['tarif_raw']}")

        # Type et confidence
        print(f"    Type: {e['type_evenement'] or '?'} | Confidence: {e['confidence']:.2f}")

        # Raw text (abrégé)
        raw = e['raw_text'][:100].replace('\n', ' ')
        print(f"    Raw: {raw}...")
        print()

    # Stats
    if events:
        confidences = [e['confidence'] for e in events]
        avg_conf = sum(confidences) / len(confidences)
        high_conf = sum(1 for c in confidences if c >= 0.7)
        print(f"{'='*60}")
        print(f"Confidence moyenne: {avg_conf:.2f}")
        print(f"Événements avec confidence >= 0.7: {high_conf}/{len(events)} ({100*high_conf/len(events):.0f}%)")

    return 0


def cmd_stats(args):
    """Affiche les statistiques globales."""
    db = BidulDB()

    stats = db.get_stats()

    print(f"{'='*50}")
    print("STATISTIQUES BASE DE DONNÉES")
    print(f"{'='*50}")
    print(f"Biduls:      {stats.get('biduls', 0)}")
    print(f"Événements:  {stats.get('evenements', 0)}")
    print(f"Lieux ref:   {stats.get('lieux_ref', 0)}")
    print(f"Villes ref:  {stats.get('villes_ref', 0)}")

    if 'par_statut' in stats:
        print(f"\nPar statut:")
        for status, count in stats['par_statut'].items():
            print(f"  {status}: {count}")

    if 'confidence_avg' in stats:
        print(f"\nConfidence:")
        print(f"  Moyenne: {stats['confidence_avg']:.2f}")
        print(f"  Min:     {stats['confidence_min']:.2f}")
        print(f"  Max:     {stats['confidence_max']:.2f}")

    return 0


def cmd_list(args):
    """Liste les PDFs disponibles."""
    pdfs = list_pdfs()

    if args.type:
        # Filtrer par type (scan/texte basé sur le numéro)
        if args.type == 'texte':
            pdfs = [p for p in pdfs if p[0] >= 178]
        elif args.type == 'scan':
            pdfs = [p for p in pdfs if p[0] < 178]

    print(f"{'='*60}")
    print(f"PDFs disponibles: {len(pdfs)}")
    print(f"{'='*60}")

    for numero, mois, annee, path in pdfs:
        type_pdf = 'texte' if numero >= 178 else 'scan'
        date_str = f"{mois:02d}/{annee}" if mois and annee else "?"
        print(f"  [{numero:3d}] {date_str} - {path.name} ({type_pdf})")

    return 0


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="CLI d'indexation des archives du Bidul",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python cli.py init                    # Initialise la base
  python cli.py extract --numero 280    # Extrait le Bidul 280
  python cli.py extract --range 280-290 # Extrait les Biduls 280 à 290
  python cli.py validate --numero 280   # Affiche l'extraction du 280
  python cli.py stats                   # Statistiques globales
  python cli.py list --type texte       # Liste les PDFs texte
        """
    )

    parser.add_argument('-v', '--verbose', action='store_true', help='Mode verbeux')

    subparsers = parser.add_subparsers(dest='command', help='Commande')

    # init
    p_init = subparsers.add_parser('init', help='Initialise la base de données')

    # extract
    p_extract = subparsers.add_parser('extract', help='Extrait un ou plusieurs PDFs')
    p_extract.add_argument('--numero', '-n', type=int, help='Numéro du Bidul')
    p_extract.add_argument('--range', '-r', help='Plage de numéros (ex: 280-290)')
    p_extract.add_argument('--dry-run', action='store_true', help='Ne pas sauvegarder en base')
    p_extract.add_argument('--force', action='store_true', help='Forcer l\'extraction des scans')

    # validate
    p_validate = subparsers.add_parser('validate', help='Valide une extraction')
    p_validate.add_argument('--numero', '-n', type=int, required=True, help='Numéro du Bidul')

    # stats
    p_stats = subparsers.add_parser('stats', help='Statistiques globales')

    # list
    p_list = subparsers.add_parser('list', help='Liste les PDFs disponibles')
    p_list.add_argument('--type', '-t', choices=['scan', 'texte'], help='Filtrer par type')

    args = parser.parse_args()

    # Configuration logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format=LOG_FORMAT)

    if not args.command:
        parser.print_help()
        return 0

    # Exécuter la commande
    commands = {
        'init': cmd_init,
        'extract': cmd_extract,
        'validate': cmd_validate,
        'stats': cmd_stats,
        'list': cmd_list,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

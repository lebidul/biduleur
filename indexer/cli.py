#!/usr/bin/env python3
"""
CLI pour l'indexation des archives du Bidul.

Commandes:
    python cli.py init                  # Initialise la base de données
    python cli.py extract --numero 280  # Extrait un PDF
    python cli.py extract --range 280-290  # Extrait une plage
    python cli.py validate --numero 280 # Affiche l'extraction pour validation
    python cli.py compare --numero 280  # Compare avec CSV de référence
    python cli.py populate              # Peuple avec CSV prioritaire ou PDF
    python cli.py populate --range 280-290  # Peuple une plage
    python cli.py purge --all           # Supprime tous les événements
    python cli.py purge --numero 280    # Supprime les événements d'un Bidul
    python cli.py stats                 # Statistiques globales
    python cli.py list                  # Liste les PDFs disponibles
"""

import argparse
import csv
import json
import logging
import re
import sys
from pathlib import Path
from datetime import datetime

# Ajouter le parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexer.core.extractor import TextExtractor, extract_bidul_info
from indexer.core.parser import EventParser
from indexer.core.db import BidulDB
from indexer.core.csv_importer import find_csv_for_bidul as find_csv_files, import_bidul_from_csv

# Configuration
ARCHIVES_DIR = Path(__file__).parent / "archives"
TAPAGES_DIR = Path(__file__).parent.parent / "biduleur" / "tapages" / "toBeConverted"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

# Mapping mois français -> numéro
MOIS_FR = {
    'janvier': 1, 'fevrier': 2, 'février': 2, 'mars': 3, 'avril': 4, 'april': 4,
    'mai': 5, 'juin': 6, 'juillet': 7, 'aout': 8, 'août': 8,
    'septembre': 9, 'octobre': 10, 'novembre': 11, 'decembre': 12, 'décembre': 12
}

# Mapping (année, mois) -> numéro Bidul (basé sur les PDFs existants)
# Le Bidul 280 = mai 2023, donc on peut calculer: numero = 280 + (annee - 2023) * 12 + (mois - 5)
def get_bidul_numero(annee: int, mois: int) -> int:
    """Calcule le numéro de Bidul à partir de l'année et du mois."""
    # Bidul 280 = mai 2023
    return 280 + (annee - 2023) * 12 + (mois - 5)


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


def find_csv_for_bidul(numero: int, mois: int, annee: int) -> Path | None:
    """
    Trouve le CSV de référence correspondant à un Bidul.

    Format CSV: YYYYMM_tapage_biduleur_mois_YYYY.csv
    Exemple: 202305_tapage_biduleur_mai_2023.csv -> Bidul 280
    """
    if not TAPAGES_DIR.exists():
        return None

    # Chercher le pattern YYYYMM
    prefix = f"{annee}{mois:02d}"

    for csv_file in TAPAGES_DIR.glob(f"{prefix}_*.csv"):
        # Ignorer les fichiers _2.csv ou _utf8.csv (variantes)
        if '_2.csv' in csv_file.name or '_utf8.csv' in csv_file.name:
            continue
        return csv_file

    return None


def load_csv_events(csv_path: Path) -> list[dict]:
    """Charge les événements depuis un CSV de référence."""
    events = []

    # Essayer différents encodages
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    events.append(row)
            break
        except UnicodeDecodeError:
            continue

    return events


def normalize_for_compare(text: str) -> str:
    """Normalise un texte pour comparaison."""
    if not text:
        return ""
    # Minuscules, sans accents simplifiés, sans espaces multiples
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def extract_day_from_csv_date(date_str: str) -> str:
    """Extrait le numéro du jour depuis une date CSV comme 'Dimanche 14'."""
    if not date_str:
        return ""
    match = re.search(r'(\d{1,2})', date_str)
    return match.group(1) if match else ""


# =============================================================================
# Commandes
# =============================================================================

def cmd_init(args):
    """Initialise la base de données."""
    db = BidulDB()
    print(f"Initialisation de la base: {db.db_path}")
    db.init_schema()
    db.load_referentiels()

    # Vider le cache du normalizer après rechargement des référentiels
    from core.normalizer import clear_caches
    clear_caches()

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
            # artistes peut être une liste de dicts ou de strings
            artiste_names = [a['nom'] if isinstance(a, dict) else a for a in artistes]
            print(f"    Artistes: {', '.join(artiste_names)}")

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


def cmd_compare(args):
    """Compare l'extraction avec le CSV de référence."""
    db = BidulDB()

    bidul = db.get_bidul(args.numero)
    if not bidul:
        print(f"Bidul #{args.numero} non trouvé en base")
        print("Lancez d'abord: python cli.py extract --numero", args.numero)
        return 1

    # Trouver le CSV de référence
    csv_path = find_csv_for_bidul(args.numero, bidul['mois'], bidul['annee'])
    if not csv_path:
        print(f"CSV de référence non trouvé pour {bidul['mois']:02d}/{bidul['annee']}")
        print(f"Recherché dans: {TAPAGES_DIR}")
        return 1

    print(f"{'='*70}")
    print(f"COMPARAISON BIDUL #{args.numero} - {bidul['mois']:02d}/{bidul['annee']}")
    print(f"{'='*70}")
    print(f"PDF: {bidul['pdf_filename']}")
    print(f"CSV: {csv_path.name}")
    print()

    # Charger les données
    db_events = db.get_evenements(args.numero)
    csv_events = load_csv_events(csv_path)

    print(f"Événements extraits (base): {len(db_events)}")
    print(f"Événements référence (CSV): {len(csv_events)}")
    print()

    # Créer des signatures pour matcher les événements
    # Utiliser jour + lieu normalisé pour un matching plus souple

    # CSV: jour (numéro) + lieu normalisé
    csv_signatures = {}
    for i, e in enumerate(csv_events):
        day = extract_day_from_csv_date(e.get('date', ''))
        lieu = normalize_for_compare(e.get('lieu', ''))
        # Simplifier le lieu (enlever articles, etc.)
        lieu_simple = re.sub(r'^(le |la |l\'|les |du |de la |des |d\')', '', lieu)
        sig = f"{day}|{lieu_simple}"
        if sig not in csv_signatures:  # Garder le premier si doublon
            csv_signatures[sig] = (i, e)

    # DB: jour + lieu normalisé
    db_signatures = {}
    for i, e in enumerate(db_events):
        # Extraire jour de la date ISO
        date_ev = e.get('date_evenement', '')
        if date_ev:
            try:
                dt = datetime.fromisoformat(date_ev)
                day = str(dt.day)
            except:
                day = ''
        else:
            day = ''

        lieu = normalize_for_compare(e.get('lieu_raw', ''))
        lieu_simple = re.sub(r'^(le |la |l\'|les |du |de la |des |d\')', '', lieu)
        sig = f"{day}|{lieu_simple}"
        if sig not in db_signatures:  # Garder le premier si doublon
            db_signatures[sig] = (i, e)

    # Comparer
    matched = 0
    csv_only = []
    db_only = []

    for sig, (i, e) in csv_signatures.items():
        if sig in db_signatures:
            matched += 1
        else:
            csv_only.append(e)

    for sig, (i, e) in db_signatures.items():
        if sig not in csv_signatures:
            db_only.append(e)

    print(f"{'='*70}")
    print("RÉSULTATS")
    print(f"{'='*70}")
    print(f"Matchés:           {matched}")
    print(f"CSV uniquement:    {len(csv_only)} (dans référence mais pas extrait)")
    print(f"Base uniquement:   {len(db_only)} (extrait mais pas dans référence)")
    print()

    if matched > 0:
        recall = matched / len(csv_events) * 100 if csv_events else 0
        precision = matched / len(db_events) * 100 if db_events else 0
        print(f"Recall:    {recall:.1f}% ({matched}/{len(csv_events)} de la référence trouvés)")
        print(f"Precision: {precision:.1f}% ({matched}/{len(db_events)} extraits sont corrects)")
        print()

    # Afficher les différences si demandé
    if args.details:
        if csv_only:
            print(f"\n{'='*70}")
            print(f"MANQUANTS (dans CSV mais pas extrait) - {len(csv_only)} premiers:")
            print(f"{'='*70}")
            for e in csv_only[:10]:
                date = e.get('date', '?')
                lieu = e.get('lieu', '?')
                artiste = e.get('artiste1', '')
                spectacle = e.get('spectacle1', '')
                nom = artiste or spectacle or '?'
                print(f"  {date} | {lieu} | {nom}")

        if db_only:
            print(f"\n{'='*70}")
            print(f"EN TROP (extrait mais pas dans CSV) - {len(db_only)} premiers:")
            print(f"{'='*70}")
            for e in db_only[:10]:
                date = e.get('date_evenement', '?')
                lieu = e.get('lieu_raw', '?')
                artistes = json.loads(e['artistes']) if e.get('artistes') else []
                spectacles = json.loads(e['spectacles']) if e.get('spectacles') else []
                nom = (artistes[0] if artistes else '') or (spectacles[0] if spectacles else '') or '?'
                print(f"  {date} | {lieu} | {nom}")

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


def cmd_populate(args):
    """
    Peuple la base avec CSV (prioritaire) ou PDF.

    Si un CSV existe pour un Bidul, importe depuis CSV (confidence=1.0).
    Sinon, extrait depuis PDF.
    """
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
        # Par défaut, tous les PDFs texte disponibles (178-308)
        pdfs = list_pdfs()
        numeros = [n for n, m, a, p in pdfs if n >= 178]

    # Stats
    total_from_csv = 0
    total_from_pdf = 0
    total_events = 0
    csv_biduls = 0
    pdf_biduls = 0
    skipped = 0

    for numero in numeros:
        # Trouver le PDF pour avoir mois/année
        pdf_path = find_pdf(numero)
        if not pdf_path:
            if not args.csv_only:
                print(f"[{numero}] PDF non trouvé - ignoré")
            skipped += 1
            continue

        n, mois, annee = extract_bidul_info(pdf_path.name)

        if not mois or not annee:
            print(f"[{numero}] Impossible d'extraire mois/année - ignoré")
            skipped += 1
            continue

        # Chercher les CSV pour ce Bidul
        csv_paths = find_csv_files(numero, mois, annee, TAPAGES_DIR)

        source = None
        events = []

        # Priorité au CSV si disponible et non --pdf-only
        if csv_paths and not args.pdf_only:
            events = import_bidul_from_csv(numero, csv_paths, annee, mois)
            source = 'csv'
            csv_biduls += 1
            total_from_csv += len(events)

        # Sinon extraction PDF (sauf --csv-only)
        elif not args.csv_only:
            result = extractor.extract(str(pdf_path))

            if not result.success:
                print(f"[{numero}] Erreur extraction PDF: {result.error}")
                skipped += 1
                continue

            if not result.is_native and not args.force:
                print(f"[{numero}] PDF scan détecté, ignoré (utilisez --force)")
                skipped += 1
                continue

            parser = EventParser(bidul_mois=mois, bidul_annee=annee)
            parsed_events = parser.parse(result.full_text)

            # Convertir ParsedEvent en dict pour uniformité
            events = []
            for e in parsed_events:
                events.append({
                    'bidul_numero': numero,
                    'raw_text': e.raw_text,
                    'nom': e.nom,
                    'date_evenement': e.date_evenement.isoformat() if e.date_evenement else None,
                    'heure': e.heure,
                    'lieu_raw': e.lieu_raw,
                    'ville_raw': e.ville_raw,
                    'artistes': json.dumps([a.to_dict() if hasattr(a, 'to_dict') else a for a in e.artistes], ensure_ascii=False) if e.artistes else None,
                    'spectacles': json.dumps(e.spectacles, ensure_ascii=False) if e.spectacles else None,
                    'genres_raw': json.dumps(e.genres_raw, ensure_ascii=False) if e.genres_raw else None,
                    'genre_evenement': None,
                    'tarif_raw': e.tarif_raw,
                    'prix_min': e.prix_min,
                    'prix_max': e.prix_max,
                    'gratuit': e.gratuit,
                    'type_evenement': e.type_evenement,
                    'confidence': e.confidence,
                    'source': 'pdf'
                })

            source = 'pdf'
            pdf_biduls += 1
            total_from_pdf += len(events)
        else:
            skipped += 1
            continue

        if args.dry_run:
            print(f"[{numero}] {mois:02d}/{annee} - {len(events)} événements ({source})")
            continue

        # Purger les anciens événements
        db.delete_evenements(numero)

        # Insérer le bidul
        type_source = 'texte' if numero >= 178 else 'scan'
        db.insert_bidul(
            numero=numero,
            mois=mois,
            annee=annee,
            pdf_filename=pdf_path.name,
            type_source=type_source
        )

        # Insérer les événements
        for event in events:
            db.insert_evenement_from_dict(event)

        db.update_bidul_status(numero, 'extracted')
        total_events += len(events)

        print(f"[{numero}] {mois:02d}/{annee} - {len(events)} événements ({source})")

    # Résumé
    print(f"\n{'='*50}")
    print("RÉSUMÉ POPULATE")
    print(f"{'='*50}")
    print(f"Biduls depuis CSV: {csv_biduls} ({total_from_csv} événements)")
    print(f"Biduls depuis PDF: {pdf_biduls} ({total_from_pdf} événements)")
    print(f"Biduls ignorés:    {skipped}")
    print(f"Total événements:  {total_events}")

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


def cmd_purge(args):
    """Purge les événements de la base."""
    db = BidulDB()

    # Déterminer les numéros à purger
    if args.all:
        # Purger tout
        conn = db.connect()
        count_before = db.count_evenements()

        if args.dry_run:
            print(f"[DRY-RUN] Suppression de {count_before} événements")
            return 0

        conn.execute("DELETE FROM evenement")
        conn.execute("DELETE FROM bidul")
        conn.commit()

        print(f"Purgé: {count_before} événements supprimés")
        return 0

    elif args.numero:
        numeros = [args.numero]
    elif args.range:
        start, end = map(int, args.range.split('-'))
        numeros = list(range(start, end + 1))
    else:
        print("Erreur: spécifiez --all, --numero ou --range")
        return 1

    total_deleted = 0
    for numero in numeros:
        count = db.count_evenements(numero)
        if count == 0:
            continue

        if args.dry_run:
            print(f"[{numero}] {count} événements à supprimer")
        else:
            db.delete_evenements(numero)
            print(f"[{numero}] {count} événements supprimés")

        total_deleted += count

    print(f"\nTotal: {total_deleted} événements {'à supprimer' if args.dry_run else 'supprimés'}")
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

    # compare
    p_compare = subparsers.add_parser('compare', help='Compare avec CSV de référence')
    p_compare.add_argument('--numero', '-n', type=int, required=True, help='Numéro du Bidul')
    p_compare.add_argument('--details', '-d', action='store_true', help='Afficher les différences')

    # stats
    p_stats = subparsers.add_parser('stats', help='Statistiques globales')

    # list
    p_list = subparsers.add_parser('list', help='Liste les PDFs disponibles')
    p_list.add_argument('--type', '-t', choices=['scan', 'texte'], help='Filtrer par type')

    # populate
    p_populate = subparsers.add_parser('populate', help='Peuple avec CSV prioritaire ou PDF')
    p_populate.add_argument('--numero', '-n', type=int, help='Numéro du Bidul')
    p_populate.add_argument('--range', '-r', help='Plage de numéros (ex: 178-308)')
    p_populate.add_argument('--csv-only', action='store_true', help='Uniquement les Biduls avec CSV')
    p_populate.add_argument('--pdf-only', action='store_true', help='Ignorer les CSV (forcer extraction PDF)')
    p_populate.add_argument('--dry-run', action='store_true', help='Affiche sans sauvegarder')
    p_populate.add_argument('--force', action='store_true', help='Forcer extraction des scans')

    # purge
    p_purge = subparsers.add_parser('purge', help='Supprime les événements de la base')
    p_purge.add_argument('--all', '-a', action='store_true', help='Supprimer tous les événements')
    p_purge.add_argument('--numero', '-n', type=int, help='Numéro du Bidul')
    p_purge.add_argument('--range', '-r', help='Plage de numéros (ex: 280-290)')
    p_purge.add_argument('--dry-run', action='store_true', help='Affiche sans supprimer')

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
        'compare': cmd_compare,
        'stats': cmd_stats,
        'list': cmd_list,
        'populate': cmd_populate,
        'purge': cmd_purge,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

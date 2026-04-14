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

Consolidation/Review:
    python cli.py migrate               # Migration du schéma pour consolidation
    python cli.py triage                # Triage automatique par confidence
    python cli.py apply-aliases         # Applique les alias artistes
    python cli.py review                # Session de review interactive
    python cli.py quality-report        # Rapport de qualité détaillé
    python cli.py analyze-corrections   # Analyse des corrections pour feedback
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

from indexer.core.extractor import TextExtractor, extract_bidul_info, detect_pdf_type
from indexer.core.parser import EventParser
from indexer.core.db import BidulDB
from indexer.core.csv_importer import find_source_files as find_csv_files, import_bidul_from_source as import_bidul_from_csv
from indexer.core.ocr import ScanExtractor, load_bidul_config, is_scan_from_csv, get_bidul_type
from indexer.core.ocr_postprocess import OCRPostProcessor
from indexer.core.regional_filter import detect_regional
from indexer.core.artifact_filter import detect_artifact, is_bidul_sans_evenements

# Configuration
ARCHIVES_DIR = Path(__file__).parent / "archives"
TAPAGES_DIR = Path(__file__).parent / "corpus"  # Fichiers sources CSV/XLSX
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
    ocr_extractor = None
    ocr_postprocessor = None

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

        # Vérifier si c'est un scan qui nécessite OCR
        # Priorité au CSV biduls.description.csv, sinon détection avancée
        csv_is_scan = is_scan_from_csv(numero)
        if csv_is_scan is not None:
            is_scan = csv_is_scan
        else:
            # Détection avancée basée sur structure du PDF
            is_scan, detection_details = detect_pdf_type(str(pdf_path))
            if args.verbose:
                print(f"  Détection auto: {'scan' if is_scan else 'texte'} ({detection_details['reason']})")

        # Si erreur ET pas un scan, abandonner
        if result.error and not is_scan:
            print(f"  Erreur: {result.error}")
            continue

        full_text = result.full_text
        mois = result.mois
        annee = result.annee
        num_pages = result.num_pages

        # Si c'est un scan et OCR non désactivé, utiliser l'OCR
        if is_scan and not getattr(args, 'no_ocr', False):
            print(f"  PDF scan détecté, lancement OCR...")

            # Initialisation lazy de l'OCR (une seule fois)
            if ocr_extractor is None:
                try:
                    use_sections = not getattr(args, 'no_sections', False)
                    auto_layout = getattr(args, 'auto_layout', False)
                    ocr_extractor = ScanExtractor(
                        dpi=getattr(args, 'dpi', 200),
                        use_sections=use_sections,
                        auto_layout=auto_layout
                    )
                    ocr_postprocessor = OCRPostProcessor()
                except Exception as e:
                    print(f"  Erreur init OCR: {e}")
                    print(f"  Conseil: pip install paddleocr pdf2image opencv-python-headless")
                    if not args.force:
                        continue
                    # Fallback au texte natif (même si vide)

            if ocr_extractor:
                config = load_bidul_config(numero)
                ocr_result = ocr_extractor.extract_from_pdf(str(pdf_path), config)

                if ocr_result.error:
                    print(f"  Erreur OCR: {ocr_result.error}")
                    if not args.force:
                        continue
                else:
                    # Utiliser le texte OCR
                    full_text = ocr_postprocessor.process(ocr_result.full_text)
                    mois = ocr_result.mois or mois
                    annee = ocr_result.annee or annee
                    num_pages = ocr_result.num_pages
                    print(f"  OCR: {len(full_text)} caractères extraits")

        elif is_scan and getattr(args, 'no_ocr', False):
            print(f"  PDF scan détecté (OCR désactivé)")
            if not args.force:
                continue

        # Parsing des événements
        parser = EventParser(bidul_mois=mois, bidul_annee=annee)
        events = parser.parse(full_text)

        print(f"  Pages: {num_pages}, Caractères: {len(full_text)}")
        print(f"  Événements trouvés: {len(events)}")

        if events:
            confidences = [e.confidence for e in events]
            avg_conf = sum(confidences) / len(confidences)
            print(f"  Confidence moyenne: {avg_conf:.2f}")

        # Sauvegarder en base (sauf dry-run)
        if not args.dry_run:
            # Supprimer les anciens événements
            db.delete_evenements(numero)

            # Insérer le bidul avec source et raw_text
            type_source = 'texte' if result.is_native else 'scan'
            source = 'scan' if is_scan else 'pdf'
            db.insert_bidul(
                numero=numero,
                mois=result.mois,
                annee=result.annee,
                pdf_filename=pdf_path.name,
                type_source=type_source,
                source=source,
                raw_text=full_text
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

    # Si --html, générer le dashboard HTML
    if getattr(args, 'html', None):
        from core.stats_generator import get_stats_data, get_quality_data, get_extended_stats, generate_html

        print("Generation du dashboard HTML...")
        data = get_stats_data(str(db.db_path))
        quality_data = get_quality_data(str(db.db_path))
        extended_stats = get_extended_stats(str(db.db_path))

        # Stats résumées
        existing = [d for d in data if not d['missing']]
        total_events = sum(d['events'] for d in existing)
        total_content = sum(d['content'] for d in existing)
        missing_count = len([d for d in data if d['missing']])
        empty_count = len([d for d in data if d['events'] == 0 and not d['missing']])

        print(f"  - {len(existing)} Biduls indexes")
        print(f"  - {total_events:,} evenements")
        print(f"  - {total_content:,} artistes/spectacles")
        print(f"  - {missing_count} PDFs manquants")
        print(f"  - {empty_count} Biduls vides")
        print(f"  - Score qualite: {quality_data['score_global']:.1f}%")

        output_path = generate_html(data, args.html, quality_data, extended_stats)
        print(f"\nDashboard genere : {output_path}")
        return 0

    stats = db.get_stats()

    print(f"{'='*50}")
    print("STATISTIQUES BASE DE DONNÉES")
    print(f"{'='*50}")

    # Résumé principal
    print(f"\nBiduls:      {stats.get('biduls', 0)}")
    if 'bidul_min' in stats:
        print(f"  Plage: {stats['bidul_min']} - {stats['bidul_max']}")

    print(f"\nÉvénements:  {stats.get('evenements', 0)}")
    if 'date_min' in stats:
        print(f"  Période: {stats['date_min']} - {stats['date_max']}")

    # Par source
    if 'par_source' in stats and stats['par_source']:
        print(f"\nPar source:")
        for source, count in sorted(stats['par_source'].items()):
            print(f"  {source}: {count}")

    # Référentiels
    print(f"\nRéférentiels:")
    print(f"  Lieux:  {stats.get('lieux_ref', 0)}")
    print(f"  Villes: {stats.get('villes_ref', 0)}")

    # Tarification
    if 'gratuits' in stats:
        print(f"\nTarification:")
        print(f"  Gratuits:     {stats['gratuits']}")
        print(f"  Payants:      {stats['payants']}")
        print(f"  Prix inconnu: {stats['prix_inconnu']}")

    # Par type d'événement
    if 'par_type' in stats and stats['par_type']:
        print(f"\nPar type:")
        for type_evt, count in stats['par_type'].items():
            print(f"  {type_evt}: {count}")

    # Top villes
    if 'top_villes' in stats and stats['top_villes']:
        print(f"\nTop 5 villes:")
        for ville, count in stats['top_villes']:
            print(f"  {ville}: {count}")

    # Top lieux
    if 'top_lieux' in stats and stats['top_lieux']:
        print(f"\nTop 5 lieux:")
        for lieu, count in stats['top_lieux']:
            # Encoder en ASCII pour éviter les erreurs d'encodage console Windows
            lieu_safe = lieu.encode('ascii', 'replace').decode('ascii') if lieu else lieu
            print(f"  {lieu_safe}: {count}")

    # Confidence
    if 'confidence_avg' in stats:
        print(f"\nConfidence:")
        print(f"  Moyenne: {stats['confidence_avg']:.2f}")
        print(f"  Min:     {stats['confidence_min']:.2f}")
        print(f"  Max:     {stats['confidence_max']:.2f}")

    # Par statut
    if 'par_statut' in stats and stats['par_statut']:
        print(f"\nPar statut extraction:")
        for status, count in stats['par_statut'].items():
            print(f"  {status}: {count}")

    return 0


def cmd_populate(args):
    """
    Peuple la base avec CSV (prioritaire) ou PDF.

    Si un CSV existe pour un Bidul, importe depuis CSV (confidence=1.0).
    Sinon, extrait depuis PDF (texte natif ou OCR pour scans).
    """
    db = BidulDB()
    db.init_schema()

    extractor = TextExtractor()
    ocr_extractor = None
    ocr_postprocessor = None

    # Charger les référentiels pour le parsing "lieu d'abord"
    lieu_ref_list = db.get_lieu_ref_list()
    ville_ref_list = db.get_ville_ref_list()
    print(f"Référentiels chargés: {len(lieu_ref_list)} lieux, {len(ville_ref_list)} villes")

    # Déterminer les numéros à traiter
    if args.numero:
        numeros = args.numero  # Déjà une liste grâce à nargs='+'
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
    already_exists = 0

    # Stats pour reparse
    total_reparsed = 0
    reparsed_biduls = 0

    # Stats pour filtrage régional
    regional_excluded = 0
    regional_included = 0
    include_regional = getattr(args, 'include_regional', False)

    # Stats pour filtrage artifacts
    artifacts_excluded = 0
    artifacts_included = 0
    include_artifacts = getattr(args, 'include_artifacts', False)

    for numero in numeros:
        # Mode --reparse: re-parser depuis bidul.raw_text (texte complet)
        if getattr(args, 'reparse', False):
            # Récupérer le bidul avec son raw_text complet
            bidul = db.get_bidul(numero)
            if not bidul:
                if args.verbose:
                    print(f"[{numero}] Bidul non trouvé en base - ignoré")
                skipped += 1
                continue

            # Pour les biduls CSV/XLSX: réimporter depuis le fichier source
            bidul_type_reparse = get_bidul_type(numero)
            if bidul_type_reparse in ('csv', 'xlsx'):
                # Récupérer mois/année
                mois_r = bidul.get('mois')
                annee_r = bidul.get('annee')
                if not mois_r or not annee_r:
                    pdf_path = find_pdf(numero)
                    if pdf_path:
                        _, mois_r, annee_r = extract_bidul_info(pdf_path.name)
                if not mois_r or not annee_r:
                    print(f"[{numero}] Impossible de déterminer mois/année - ignoré")
                    skipped += 1
                    continue

                csv_paths = find_csv_files(numero, mois_r, annee_r, TAPAGES_DIR)
                if csv_paths:
                    existing_count = db.count_evenements(numero)
                    if not args.dry_run:
                        db.delete_evenements(numero)
                    reimported = import_bidul_from_csv(numero, csv_paths, annee_r, mois_r)
                    if not args.dry_run:
                        for event in reimported:
                            db.insert_evenement_from_dict(event)
                        # Effacer le raw_text résiduel
                        conn_r = db.connect()
                        conn_r.execute("UPDATE bidul SET raw_text = NULL, source = ? WHERE numero = ?",
                                      (bidul_type_reparse, numero))
                        conn_r.commit()
                    dry_run_suffix = " (dry-run)" if args.dry_run else ""
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] [{numero}] Réimporté depuis {bidul_type_reparse}: "
                          f"{existing_count} -> {len(reimported)} événements{dry_run_suffix}")
                    total_reparsed += len(reimported)
                    reparsed_biduls += 1
                else:
                    print(f"[{numero}] Fichier source {bidul_type_reparse} non trouvé - ignoré")
                    skipped += 1
                continue

            bidul_raw_text = bidul.get('raw_text')
            if not bidul_raw_text:
                # Pas de raw_text = bidul importé depuis CSV, ne pas supprimer les événements
                if args.verbose:
                    print(f"[{numero}] Pas de raw_text dans bidul (source CSV ?) - conservé tel quel")
                skipped += 1
                continue

            # Récupérer mois/année depuis le bidul ou le PDF
            mois = bidul.get('mois')
            annee = bidul.get('annee')
            if not mois or not annee:
                pdf_path = find_pdf(numero)
                if pdf_path:
                    n, mois, annee = extract_bidul_info(pdf_path.name)
                else:
                    print(f"[{numero}] Impossible de déterminer mois/année - ignoré")
                    skipped += 1
                    continue

            # Compter les événements existants avant suppression
            existing_count = db.count_evenements(numero)
            existing_contenu = db.count_contenu_evenement(numero)

            # Supprimer TOUS les événements du bidul avant de re-parser
            # Note: On ne supprime que si raw_text existe (vérifié ci-dessus)
            if not args.dry_run:
                db.delete_evenements(numero)

            # Vérifier si c'est un bidul sans événements (cas particulier)
            if is_bidul_sans_evenements(numero):
                if args.verbose:
                    logging.info(f"[{numero}] Bidul sans événements (cas particulier)")
                reparsed_biduls += 1
                continue

            # Charger la config du Bidul pour obtenir date_format
            config = load_bidul_config(numero)
            date_format = config.date_format if config else None

            # Re-parser le texte brut complet avec EventParser (supporte format bloc)
            # Si include_regional=False, exclure la section "Et un peu plus loin..." dès le parsing
            parser = EventParser(bidul_mois=mois, bidul_annee=annee, date_format=date_format,
                                 include_regional=include_regional)
            parsed_events = parser.parse_with_referentiel(
                bidul_raw_text,
                lieu_ref_list,
                ville_ref_list
            )

            # Filtrer les événements régionaux et artifacts
            events_to_insert = []
            for event in parsed_events:
                # Détecter si artifact (faux événement)
                artifact_detection = detect_artifact(
                    event.raw_text,
                    lieu_raw=event.lieu_raw,
                    artistes=event.artistes,
                    spectacles=event.spectacles,
                    nom_evenement=event.nom
                )

                if artifact_detection.is_artifact:
                    if not include_artifacts:
                        artifacts_excluded += 1
                        if args.verbose:
                            logging.debug(f"[{numero}] Exclus (artifact): {event.raw_text[:50]}... [{artifact_detection.reason}]")
                        continue
                    else:
                        artifacts_included += 1
                        if args.verbose:
                            logging.debug(f"[{numero}] Inclus (artifact): {event.raw_text[:50]}... [{artifact_detection.reason}]")

                # Détecter si régional
                detection = detect_regional(event.raw_text, event.lieu_raw, event.ville_raw)
                event.is_regional = detection.is_regional

                if event.is_regional:
                    if not include_regional:
                        regional_excluded += 1
                        if args.verbose:
                            logging.debug(f"[{numero}] Exclus (régional): {event.raw_text[:50]}... [{detection.reason}]")
                        continue
                    else:
                        regional_included += 1
                        if args.verbose:
                            logging.debug(f"[{numero}] Inclus (régional): {event.raw_text[:50]}... [{detection.reason}]")

                events_to_insert.append(event)

            reparsed_count = len(events_to_insert)

            if not args.dry_run:
                for event in events_to_insert:
                    # Convertir ParsedEvent en dict pour insertion
                    date_evt = event.date_evenement
                    if hasattr(date_evt, 'isoformat'):
                        date_evt = date_evt.isoformat()
                    # Convertir artistes/spectacles en JSON
                    # Les artistes peuvent être des ArtisteInfo (dataclass) ou des dicts
                    artistes = event.artistes
                    if artistes:
                        artistes_list = []
                        for a in artistes:
                            if hasattr(a, 'to_dict'):
                                artistes_list.append(a.to_dict())
                            elif isinstance(a, dict):
                                artistes_list.append(a)
                            else:
                                artistes_list.append({'nom': str(a)})
                        artistes = json.dumps(artistes_list, ensure_ascii=False)
                    else:
                        artistes = None
                    # Les spectacles sont généralement des dicts
                    spectacles = event.spectacles
                    if spectacles:
                        spectacles_list = []
                        for s in spectacles:
                            if hasattr(s, 'to_dict'):
                                spectacles_list.append(s.to_dict())
                            elif isinstance(s, dict):
                                spectacles_list.append(s)
                            else:
                                spectacles_list.append({'nom': str(s)})
                        spectacles = json.dumps(spectacles_list, ensure_ascii=False)
                    else:
                        spectacles = None
                    db.insert_evenement_from_dict({
                        'bidul_numero': numero,
                        'raw_text': event.raw_text,
                        'nom': event.nom,
                        'date_evenement': date_evt,
                        'heure': event.heure,
                        'lieu_raw': event.lieu_raw,
                        'ville_raw': event.ville_raw,
                        'tarif_raw': event.tarif_raw,
                        'prix_min': event.prix_min,
                        'prix_max': event.prix_max,
                        'gratuit': event.gratuit,
                        'artistes': artistes,
                        'spectacles': spectacles,
                        'is_regional': event.is_regional
                    })

            dry_run_suffix = " (dry-run)" if args.dry_run else ""

            # Compter les contenu_evenement après reparsing
            if not args.dry_run:
                new_contenu = db.count_contenu_evenement(numero)
            else:
                new_contenu = {'artistes': 0, 'spectacles': 0}

            # Calculer le pourcentage d'amélioration pour les événements
            if existing_count > 0:
                pct_change = ((reparsed_count - existing_count) / existing_count) * 100
                if pct_change > 0:
                    pct_str = f" (+{pct_change:.0f}%)"
                elif pct_change < 0:
                    pct_str = f" ({pct_change:.0f}%)"
                else:
                    pct_str = " (=)"
            else:
                pct_str = " (nouveau)"

            # Formater les stats contenu_evenement
            old_art = existing_contenu.get('artistes', 0)
            new_art = new_contenu.get('artistes', 0)
            old_spec = existing_contenu.get('spectacles', 0)
            new_spec = new_contenu.get('spectacles', 0)
            contenu_str = f"art: {old_art}->{new_art}, spec: {old_spec}->{new_spec}"

            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{numero}] Re-parsé: {existing_count} -> {reparsed_count} événements{pct_str} | {contenu_str} (format={date_format or 'auto'}){dry_run_suffix}")
            total_reparsed += reparsed_count
            reparsed_biduls += 1
            continue

        # Vérifier si déjà en base (sauf si --replace)
        existing_count = db.count_evenements(numero)
        if existing_count > 0 and not args.replace:
            if args.verbose:
                print(f"[{numero}] Déjà en base ({existing_count} événements) - ignoré (utilisez --replace)")
            already_exists += 1
            continue

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

        # Déterminer le type de source depuis biduls.description.csv
        # Types possibles: 'scan', 'texte', 'csv', 'xlsx'
        bidul_type = get_bidul_type(numero)

        source = None
        events = []
        full_text = None  # Pour stocker le texte brut extrait (PDF/scan)

        # Filtrage par type selon les options --csv-only et --pdf-only
        # --csv-only : traite uniquement les types 'csv' et 'xlsx'
        # --pdf-only : traite uniquement les types 'scan' et 'texte'
        if args.csv_only and bidul_type not in ('csv', 'xlsx'):
            if args.verbose:
                print(f"[{numero}] Ignoré (type={bidul_type}, --csv-only actif)")
            skipped += 1
            continue

        if args.pdf_only and bidul_type not in ('scan', 'texte', None):
            if args.verbose:
                print(f"[{numero}] Ignoré (type={bidul_type}, --pdf-only actif)")
            skipped += 1
            continue

        # Type CSV ou XLSX: import depuis fichier source
        if bidul_type in ('csv', 'xlsx'):
            csv_paths = find_csv_files(numero, mois, annee, TAPAGES_DIR)
            if csv_paths:
                events = import_bidul_from_csv(numero, csv_paths, annee, mois)
                source = bidul_type  # 'csv' ou 'xlsx'
                # Pas de raw_text pour les imports CSV/XLSX (données déjà structurées)
                csv_biduls += 1
                total_from_csv += len(events)
            else:
                print(f"[{numero}] Fichier source {bidul_type} non trouvé")
                skipped += 1
                continue

        # Type scan ou texte: extraction depuis PDF
        if bidul_type in ('scan', 'texte', None) and source is None:
            # Extraction PDF
            result = extractor.extract(str(pdf_path))

            if result.error and result.is_native:
                print(f"[{numero}] Erreur extraction PDF: {result.error}")
                skipped += 1
                continue

            # Déterminer si c'est un scan:
            # 1. D'abord vérifier le type dans biduls.description.csv
            # 2. Sinon, utiliser la détection avancée (fonts, images, texte)
            if bidul_type == 'scan':
                is_scan = True
            elif bidul_type == 'texte':
                is_scan = False
            else:
                # Fallback: détection avancée basée sur structure du PDF
                is_scan, detection_details = detect_pdf_type(str(pdf_path))
                if args.verbose:
                    print(f"[{numero}] Détection auto: {'scan' if is_scan else 'texte'} ({detection_details['reason']})")

            full_text = result.full_text

            # Charger la config du Bidul (pour date_format notamment)
            config = load_bidul_config(numero)

            if is_scan:
                # Utiliser l'OCR pour les scans (sauf --no-ocr)
                if getattr(args, 'no_ocr', False):
                    print(f"[{numero}] PDF scan détecté (OCR désactivé)")
                    skipped += 1
                    continue

                # Initialisation lazy de l'OCR
                if ocr_extractor is None:
                    try:
                        engine = getattr(args, 'engine', 'google')
                        use_sections = not getattr(args, 'no_sections', False)
                        auto_layout = getattr(args, 'auto_layout', False)
                        ocr_extractor = ScanExtractor(
                            ocr_engine=engine,
                            dpi=getattr(args, 'dpi', 200),
                            use_sections=use_sections,
                            auto_layout=auto_layout
                        )
                        ocr_postprocessor = OCRPostProcessor()
                        mode_info = []
                        if use_sections:
                            mode_info.append("sections")
                        if auto_layout:
                            mode_info.append("auto-layout")
                        mode_str = f" ({', '.join(mode_info)})" if mode_info else ""
                        print(f"OCR initialisé ({engine}{mode_str})")
                    except Exception as e:
                        print(f"[{numero}] Erreur init OCR: {e}")
                        skipped += 1
                        continue

                # Extraction OCR
                ocr_result = ocr_extractor.extract_from_pdf(str(pdf_path), config)

                if ocr_result.error:
                    print(f"[{numero}] Erreur OCR: {ocr_result.error}")
                    skipped += 1
                    continue

                full_text = ocr_postprocessor.process(ocr_result.full_text)
                print(f"[{numero}] OCR: {len(full_text)} caractères extraits")

            # Récupérer le date_format depuis la config (si disponible)
            date_format = config.date_format if config else None
            # Si include_regional=False, exclure la section "Et un peu plus loin..." dès le parsing
            parser = EventParser(bidul_mois=mois, bidul_annee=annee, date_format=date_format,
                                 include_regional=include_regional)
            # Utiliser parse_with_referentiel pour la stratégie "lieu d'abord"
            parsed_events = parser.parse_with_referentiel(
                full_text,
                lieu_ref_list,
                ville_ref_list
            )

            # Convertir ParsedEvent en dict pour uniformité
            # Source = 'scan' pour les PDFs scannés, 'pdf' pour les natifs
            source = 'scan' if is_scan else 'pdf'
            events = []
            for e in parsed_events:
                # Détecter si artifact (faux événement)
                artifact_detection = detect_artifact(
                    e.raw_text,
                    lieu_raw=e.lieu_raw,
                    artistes=e.artistes,
                    spectacles=e.spectacles,
                    nom_evenement=e.nom
                )

                if artifact_detection.is_artifact:
                    if not include_artifacts:
                        artifacts_excluded += 1
                        if args.verbose:
                            logging.debug(f"[{numero}] Exclus (artifact): {e.raw_text[:50]}... [{artifact_detection.reason}]")
                        continue
                    else:
                        artifacts_included += 1
                        if args.verbose:
                            logging.debug(f"[{numero}] Inclus (artifact): {e.raw_text[:50]}... [{artifact_detection.reason}]")

                # Détecter si régional
                detection = detect_regional(e.raw_text, e.lieu_raw, e.ville_raw)
                is_regional_event = detection.is_regional

                if is_regional_event:
                    if not include_regional:
                        regional_excluded += 1
                        if args.verbose:
                            logging.debug(f"[{numero}] Exclus (régional): {e.raw_text[:50]}... [{detection.reason}]")
                        continue
                    else:
                        regional_included += 1
                        if args.verbose:
                            logging.debug(f"[{numero}] Inclus (régional): {e.raw_text[:50]}... [{detection.reason}]")

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
                    'genre_evenement': e.genre_evenement,
                    'tarif_raw': e.tarif_raw,
                    'prix_min': e.prix_min,
                    'prix_max': e.prix_max,
                    'gratuit': e.gratuit,
                    'type_evenement': e.type_evenement,
                    'confidence': e.confidence,
                    'is_regional': is_regional_event
                })
            pdf_biduls += 1
            total_from_pdf += len(events)
        elif source is None:
            skipped += 1
            continue

        if args.dry_run:
            print(f"[{numero}] {mois:02d}/{annee} - {len(events)} événements ({source})")
            continue

        # Purger les anciens événements
        db.delete_evenements(numero)

        # Insérer le bidul avec source et raw_text
        type_source = 'texte' if numero >= 178 else 'scan'
        db.insert_bidul(
            numero=numero,
            mois=mois,
            annee=annee,
            pdf_filename=pdf_path.name,
            type_source=type_source,
            source=source,
            raw_text=full_text  # None pour CSV, texte extrait pour PDF/scan
        )

        # Pour les imports CSV/XLSX, effacer le raw_text résiduel
        # d'une éventuelle ancienne extraction PDF (COALESCE le préserve sinon)
        if source in ('csv', 'xlsx'):
            conn = db.connect()
            conn.execute("UPDATE bidul SET raw_text = NULL WHERE numero = ?", (numero,))
            conn.commit()

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
    if getattr(args, 'reparse', False):
        print(f"Biduls re-parsés:  {reparsed_biduls} ({total_reparsed} événements)")
    else:
        print(f"Biduls depuis CSV: {csv_biduls} ({total_from_csv} événements)")
        print(f"Biduls depuis PDF: {pdf_biduls} ({total_from_pdf} événements)")
    print(f"Biduls déjà en base: {already_exists}")
    print(f"Biduls ignorés:    {skipped}")
    if not getattr(args, 'reparse', False):
        print(f"Total événements:  {total_events}")

    # Stats artifacts
    if artifacts_excluded > 0:
        print(f"Artifacts exclus: {artifacts_excluded}")
    if artifacts_included > 0:
        print(f"Artifacts inclus: {artifacts_included}")

    # Stats régionales
    if regional_excluded > 0:
        print(f"Événements régionaux exclus: {regional_excluded}")
    if regional_included > 0:
        print(f"Événements régionaux inclus: {regional_included}")

    return 0


def cmd_export(args):
    """Exporte les événements vers CSV/XLSX."""
    from indexer.core.csv_exporter import export_events, export_bidul, export_range
    from indexer.core.db import DEFAULT_DB_PATH

    output_path = Path(args.output)

    # Inférer le format depuis l'extension si non spécifié explicitement
    if args.format:
        output_format = args.format
    else:
        ext = output_path.suffix.lower()
        output_format = 'xlsx' if ext == '.xlsx' else 'csv'

    if args.numero:
        # Export d'un seul bidul
        count = export_bidul(
            DEFAULT_DB_PATH,
            args.numero,
            output_path,
            output_format
        )
        print(f"Exporté {count} événements vers {output_path}")

    elif args.range:
        # Export d'une plage
        start, end = map(int, args.range.split('-'))
        count = export_range(
            DEFAULT_DB_PATH,
            start,
            end,
            output_path,  # C'est un dossier dans ce cas
            output_format
        )
        print(f"Exporté {count} événements vers {output_path}/")

    elif args.where:
        # Export avec clause WHERE personnalisée
        count = export_events(
            DEFAULT_DB_PATH,
            output_path,
            where_clause=args.where,
            output_format=output_format
        )
        print(f"Exporté {count} événements vers {output_path}")

    else:
        print("Erreur: Spécifiez --numero, --range ou --where")
        return 1

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

        # Supprimer d'abord les tables dépendantes (FK)
        conn.execute("DELETE FROM contenu_evenement")
        conn.execute("DELETE FROM correction_log")
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


def cmd_migrate(args):
    """Migration de la base de données pour le système de consolidation."""
    db = BidulDB()
    conn = db.connect()
    cur = conn.cursor()

    print("Migration du schéma pour le système de consolidation...")

    # Ajout des colonnes de review dans evenement
    migrations = [
        ("evenement", "verified", "BOOLEAN DEFAULT FALSE"),
        ("evenement", "verified_by", "TEXT"),
        ("evenement", "verified_at", "TIMESTAMP"),
        ("evenement", "review_status", "TEXT DEFAULT 'pending'"),
        ("evenement", "review_notes", "TEXT"),
        ("evenement", "style", "TEXT"),  # Style/genre de l'événement (rock, jazz, théâtre, etc.)
        # Nouvelles colonnes sur bidul pour source et raw_text
        ("bidul", "source", "TEXT CHECK(source IN ('csv', 'xlsx', 'pdf', 'scan'))"),
        ("bidul", "raw_text", "TEXT"),
    ]

    for table, column, col_type in migrations:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print(f"  + {table}.{column}")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print(f"  = {table}.{column} (existe déjà)")
            else:
                print(f"  ! {table}.{column}: {e}")

    # Création de la table correction_log
    cur.execute('''
        CREATE TABLE IF NOT EXISTS correction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evenement_id INTEGER,
            champ TEXT NOT NULL,
            ancienne_valeur TEXT,
            nouvelle_valeur TEXT,
            source TEXT DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evenement_id) REFERENCES evenement(id)
        )
    ''')
    print("  + Table correction_log")

    # Création de la table artiste_alias
    cur.execute('''
        CREATE TABLE IF NOT EXISTS artiste_alias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_variante TEXT UNIQUE NOT NULL,
            nom_normalise TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("  + Table artiste_alias")

    # Création de la table contenu_evenement
    cur.execute('''
        CREATE TABLE IF NOT EXISTS contenu_evenement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evenement_id INTEGER NOT NULL,
            artiste TEXT,
            nom_spectacle TEXT,
            style TEXT,
            ordre INTEGER DEFAULT 1,
            FOREIGN KEY (evenement_id) REFERENCES evenement(id) ON DELETE CASCADE
        )
    ''')
    print("  + Table contenu_evenement")

    # Index pour les recherches
    cur.execute('CREATE INDEX IF NOT EXISTS idx_evenement_review_status ON evenement(review_status)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_evenement_verified ON evenement(verified)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_correction_log_evenement ON correction_log(evenement_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_contenu_evenement_id ON contenu_evenement(evenement_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_contenu_artiste ON contenu_evenement(artiste)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_contenu_style ON contenu_evenement(style)')

    conn.commit()
    print("\nMigration terminée.")
    return 0


def cmd_triage(args):
    """Triage automatique des événements."""
    from indexer.core.triage import triage_all, detect_duplicates, get_triage_stats

    db_path = Path(__file__).parent / "database" / "bidul_archives.db"

    print("Triage automatique des événements...")

    # Triage par confidence
    results = triage_all(db_path)
    print(f"\nRésultats du triage:")
    print(f"  OK (confidence >= 0.9):     {results['ok']}")
    print(f"  À revoir (0.7-0.9):         {results['to_review']}")
    print(f"  Flaggés (< 0.7):            {results['flagged']}")

    # Détection des doublons
    if not args.skip_duplicates:
        dups = detect_duplicates(db_path)
        print(f"  Doublons potentiels:        {dups}")

    # Stats finales
    stats = get_triage_stats(db_path)
    print(f"\nStatut global:")
    for status, count in stats.items():
        print(f"  {status}: {count}")

    return 0


def cmd_apply_aliases(args):
    """Applique les alias artistes."""
    from indexer.core.aliases import sync_aliases_from_json, apply_artiste_aliases

    db_path = Path(__file__).parent / "database" / "bidul_archives.db"
    json_path = Path(__file__).parent / "corpus" / "artistes_aliases.json"

    # Sync depuis JSON si demandé
    if args.sync_json:
        count = sync_aliases_from_json(json_path, db_path)
        print(f"Alias synchronisés depuis JSON: {count}")

    # Appliquer aux événements
    updated = apply_artiste_aliases(db_path)
    print(f"Événements mis à jour: {updated}")

    return 0


def cmd_review(args):
    """Session de review interactive."""
    from indexer.core.review import ReviewSession

    db_path = Path(__file__).parent / "database" / "bidul_archives.db"

    # Filtres
    filters = {}
    if args.status:
        filters['status'] = args.status
    if args.numero:
        filters['bidul_numero'] = args.numero

    session = ReviewSession(db_path, filters)
    session.start()

    return 0


def cmd_quality_report(args):
    """Génère un rapport de qualité."""
    db = BidulDB()
    conn = db.connect()
    cur = conn.cursor()

    print("=" * 60)
    print("RAPPORT DE QUALITÉ")
    print("=" * 60)

    # Stats globales
    cur.execute("SELECT COUNT(*) FROM evenement")
    total = cur.fetchone()[0]
    print(f"\nTotal événements: {total}")

    # Par review_status
    cur.execute('''
        SELECT review_status, COUNT(*) as cnt
        FROM evenement
        GROUP BY review_status
        ORDER BY cnt DESC
    ''')
    print("\nPar statut de review:")
    for row in cur.fetchall():
        status = row[0] or 'pending'
        pct = row[1] / total * 100 if total else 0
        print(f"  {status}: {row[1]} ({pct:.1f}%)")

    # Vérifiés
    cur.execute("SELECT COUNT(*) FROM evenement WHERE verified = TRUE OR verified = 1")
    verified = cur.fetchone()[0]
    print(f"\nVérifiés: {verified} ({verified/total*100:.1f}%)" if total else "\nVérifiés: 0")

    # Distribution de confidence
    cur.execute('''
        SELECT
            CASE
                WHEN confidence >= 0.9 THEN '0.9+'
                WHEN confidence >= 0.8 THEN '0.8-0.9'
                WHEN confidence >= 0.7 THEN '0.7-0.8'
                WHEN confidence >= 0.5 THEN '0.5-0.7'
                ELSE '<0.5'
            END as bucket,
            COUNT(*) as cnt
        FROM evenement
        GROUP BY bucket
        ORDER BY bucket DESC
    ''')
    print("\nDistribution de confidence:")
    for row in cur.fetchall():
        pct = row[1] / total * 100 if total else 0
        print(f"  {row[0]}: {row[1]} ({pct:.1f}%)")

    # Champs manquants
    cur.execute("SELECT COUNT(*) FROM evenement WHERE date_evenement IS NULL")
    no_date = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_raw IS NULL")
    no_lieu = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM evenement WHERE artistes IS NULL AND spectacles IS NULL")
    no_content = cur.fetchone()[0]

    print("\nChamps manquants:")
    print(f"  Sans date: {no_date}")
    print(f"  Sans lieu: {no_lieu}")
    print(f"  Sans artiste/spectacle: {no_content}")

    # Lieux non résolus
    cur.execute("SELECT COUNT(*) FROM evenement WHERE lieu_ref_id IS NULL AND lieu_raw IS NOT NULL")
    unresolved_lieux = cur.fetchone()[0]
    print(f"  Lieux non résolus: {unresolved_lieux}")

    return 0


def cmd_analyze_corrections(args):
    """Analyse les corrections pour améliorer l'extraction."""
    db = BidulDB()
    conn = db.connect()
    cur = conn.cursor()

    print("=" * 60)
    print("ANALYSE DES CORRECTIONS")
    print("=" * 60)

    # Vérifier si la table existe
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='correction_log'")
    if not cur.fetchone():
        print("\nAucune correction enregistrée (table correction_log absente)")
        print("Lancez d'abord: python cli.py migrate")
        return 0

    # Stats par champ
    cur.execute('''
        SELECT champ, COUNT(*) as cnt
        FROM correction_log
        GROUP BY champ
        ORDER BY cnt DESC
    ''')
    results = cur.fetchall()

    if not results:
        print("\nAucune correction enregistrée.")
        return 0

    print("\nCorrections par champ:")
    for champ, count in results:
        print(f"  {champ}: {count}")

    # Patterns de correction fréquents (pour lieux par exemple)
    cur.execute('''
        SELECT ancienne_valeur, nouvelle_valeur, COUNT(*) as cnt
        FROM correction_log
        WHERE champ = 'lieu_raw'
        GROUP BY ancienne_valeur, nouvelle_valeur
        ORDER BY cnt DESC
        LIMIT 10
    ''')
    lieu_patterns = cur.fetchall()

    if lieu_patterns:
        print("\nTop 10 corrections de lieux:")
        for old, new, cnt in lieu_patterns:
            print(f"  '{old}' -> '{new}' ({cnt}x)")

    # Suggestions d'alias artistes
    cur.execute('''
        SELECT ancienne_valeur, nouvelle_valeur, COUNT(*) as cnt
        FROM correction_log
        WHERE champ = 'artistes'
        GROUP BY ancienne_valeur, nouvelle_valeur
        ORDER BY cnt DESC
        LIMIT 10
    ''')
    artiste_patterns = cur.fetchall()

    if artiste_patterns:
        print("\nSuggestions d'alias artistes:")
        for old, new, cnt in artiste_patterns:
            print(f"  '{old}' -> '{new}' ({cnt}x)")

    return 0


# =============================================================================
# OCR Commands
# =============================================================================

def cmd_ocr(args):
    """Extrait le texte d'un PDF scanné par OCR."""
    import time
    from indexer.core.ocr import ScanExtractor, load_bidul_config
    from indexer.core.ocr_postprocess import OCRPostProcessor

    pdf_path = args.pdf_path
    numero = args.numero

    # Si --numero fourni sans pdf_path, chercher le PDF automatiquement
    if pdf_path is None:
        if numero is None:
            print("Erreur: spécifiez un chemin PDF ou --numero")
            return 1
        pdf_file = find_pdf(numero)
        if not pdf_file:
            print(f"Erreur: PDF non trouvé pour Bidul {numero}")
            return 1
        pdf_path = str(pdf_file)

    # Détecter le numéro du Bidul depuis le nom de fichier si non fourni
    if numero is None:
        match = re.search(r'Bidul[_\s-]*(\d+)', pdf_path, re.IGNORECASE)
        numero = int(match.group(1)) if match else None

    # Charger la config si disponible
    config = load_bidul_config(numero) if numero else None

    print(f"Extraction OCR de {pdf_path}")
    print(f"  Moteur: {args.engine}, DPI: {args.dpi}")
    if config:
        print(f"  Config Bidul {numero}: rotation={config.needs_rotation(2)}, colonnes={config.get_colonnes(2)}")

    start_time = time.time()

    # Extraction
    use_sections = not getattr(args, 'no_sections', False)
    auto_layout = getattr(args, 'auto_layout', False)
    extractor = ScanExtractor(ocr_engine=args.engine, dpi=args.dpi, use_sections=use_sections, auto_layout=auto_layout)
    result = extractor.extract_from_pdf(pdf_path, config)

    # Afficher le mode d'extraction utilisé
    extraction_mode = result.metadata.get('extraction_mode', 'classic')
    print(f"  Mode d'extraction: {extraction_mode}")

    if result.error:
        print(f"  Erreur: {result.error}")
        return 1

    elapsed = time.time() - start_time
    print(f"  Pages: {result.num_pages}, Caractères: {len(result.full_text)}")
    print(f"  Temps: {elapsed:.1f}s")

    # Post-traitement si demandé
    text = result.full_text
    if not args.raw:
        postprocessor = OCRPostProcessor()
        text = postprocessor.process(text)
        print(f"  Caractères après correction: {len(text)}")

    # Afficher ou sauvegarder
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"\nTexte sauvegardé dans {args.output}")
    else:
        print("\n" + "=" * 60)
        # Encoder en ASCII avec remplacement pour la console Windows
        display_text = text[:3000] if len(text) > 3000 else text
        try:
            print(display_text)
        except UnicodeEncodeError:
            print(display_text.encode('ascii', 'replace').decode('ascii'))
        if len(text) > 3000:
            print(f"\n... ({len(text)} caractères au total)")

    return 0


def cmd_ocr_test(args):
    """Teste l'OCR sur un échantillon de PDFs scannés."""
    import time
    from indexer.core.ocr import ScanExtractor
    from indexer.core.ocr_postprocess import OCRPostProcessor

    # Trouver les PDFs scannés
    scan_pdfs = []

    # Priorité aux PDFs représentatifs mentionnés dans le prompt
    priority_nums = ['002', '013', '035', '103', '174']

    for num in priority_nums:
        matches = list(ARCHIVES_DIR.glob(f'*Bidul*{num}*.pdf'))
        if matches:
            scan_pdfs.append(matches[0])

    # Compléter avec d'autres scans si nécessaire
    if len(scan_pdfs) < args.samples:
        # Biduls 1-177 sont des scans
        for pdf in sorted(ARCHIVES_DIR.glob('*.pdf')):
            n, _, _ = extract_bidul_info(pdf.name)
            if n and n < 178 and pdf not in scan_pdfs:
                scan_pdfs.append(pdf)
                if len(scan_pdfs) >= args.samples:
                    break

    scan_pdfs = scan_pdfs[:args.samples]

    print(f"Test OCR sur {len(scan_pdfs)} PDFs\n")
    print(f"{'='*60}")

    extractor = ScanExtractor(dpi=args.dpi)
    postprocessor = OCRPostProcessor()

    results = []

    for pdf in scan_pdfs:
        print(f"\n[PDF] {pdf.name}")
        start = time.time()

        try:
            result = extractor.extract_from_pdf(str(pdf))
            elapsed = time.time() - start

            if result.error:
                print(f"  ERREUR: {result.error}")
                results.append({'pdf': pdf.name, 'success': False, 'error': result.error})
                continue

            # Post-traitement
            text = postprocessor.process(result.full_text)

            print(f"  OK - {len(text)} caractères en {elapsed:.1f}s")
            print(f"  Apercu: {text[:200].replace(chr(10), ' ')}...")

            results.append({
                'pdf': pdf.name,
                'success': True,
                'chars': len(text),
                'time': elapsed,
                'pages': result.num_pages
            })

        except Exception as e:
            print(f"  ERREUR: {e}")
            results.append({'pdf': pdf.name, 'success': False, 'error': str(e)})

    # Résumé
    print(f"\n{'='*60}")
    print("RÉSUMÉ")
    print(f"{'='*60}")

    success_count = sum(1 for r in results if r.get('success'))
    total_chars = sum(r.get('chars', 0) for r in results)
    total_time = sum(r.get('time', 0) for r in results)

    print(f"Réussis: {success_count}/{len(results)}")
    print(f"Total caractères: {total_chars}")
    print(f"Temps total: {total_time:.1f}s")
    if success_count > 0:
        print(f"Moyenne chars/PDF: {total_chars // success_count}")
        print(f"Moyenne temps/PDF: {total_time / success_count:.1f}s")

    return 0


def cmd_ocr_extract(args):
    """Extrait et parse les événements d'un PDF scanné via OCR."""
    import time
    from indexer.core.ocr import ScanExtractor, load_bidul_config
    from indexer.core.ocr_postprocess import OCRPostProcessor

    db = BidulDB()
    db.init_schema()

    # Déterminer les numéros à traiter
    if args.numero:
        numeros = [args.numero]
    elif args.range:
        start, end = map(int, args.range.split('-'))
        numeros = list(range(start, end + 1))
    else:
        print("Erreur: spécifiez --numero ou --range")
        return 1

    engine = getattr(args, 'engine', 'google')
    use_sections = not getattr(args, 'no_sections', False)
    auto_layout = getattr(args, 'auto_layout', False)
    extractor = ScanExtractor(ocr_engine=engine, dpi=args.dpi, use_sections=use_sections, auto_layout=auto_layout)
    postprocessor = OCRPostProcessor()

    # Charger les référentiels pour le parsing
    lieu_ref_list = db.get_lieu_ref_list()
    ville_ref_list = db.get_ville_ref_list()

    total_events = 0
    success_count = 0

    for numero in numeros:
        pdf_path = find_pdf(numero)
        if not pdf_path:
            print(f"[{numero}] PDF non trouvé")
            continue

        n, mois, annee = extract_bidul_info(pdf_path.name)

        print(f"[{numero}] OCR: {pdf_path.name}")
        start = time.time()

        # Charger la config
        config = load_bidul_config(numero)

        # Extraction OCR
        result = extractor.extract_from_pdf(str(pdf_path), config)

        if result.error:
            print(f"  Erreur OCR: {result.error}")
            continue

        # Post-traitement
        text = postprocessor.process(result.full_text)
        elapsed = time.time() - start

        print(f"  OCR: {len(text)} caractères en {elapsed:.1f}s")

        # Parsing des événements avec le date_format depuis la config
        date_format = config.date_format if config else None
        parser = EventParser(bidul_mois=mois, bidul_annee=annee, date_format=date_format)
        events = parser.parse_with_referentiel(text, lieu_ref_list, ville_ref_list)

        print(f"  Événements trouvés: {len(events)}")

        if events:
            confidences = [e.confidence for e in events]
            avg_conf = sum(confidences) / len(confidences)
            print(f"  Confidence moyenne: {avg_conf:.2f}")

        # Sauvegarder en base (sauf dry-run)
        if not args.dry_run and events:
            # Supprimer les anciens événements
            db.delete_evenements(numero)

            # Insérer le bidul avec source et raw_text
            db.insert_bidul(
                numero=numero,
                mois=mois,
                annee=annee,
                pdf_filename=pdf_path.name,
                type_source='scan',
                source='scan',
                raw_text=text
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


# =============================================================================
# SVG Template Commands (v1.12+)
# =============================================================================

def cmd_svg_generate(args):
    """Génère un template SVG depuis la config CSV existante."""
    from core.section_extractor import load_section_config
    from core.svg_template import SVGTemplateGenerator

    # Déterminer les numéros à traiter
    if args.numero:
        numeros = args.numero if isinstance(args.numero, list) else [args.numero]
    elif args.range:
        start, end = map(int, args.range.split('-'))
        numeros = list(range(start, end + 1))
    else:
        print("Erreur: spécifiez --numero ou --range")
        return 1

    generator = SVGTemplateGenerator(dpi=args.dpi)
    templates_dir = Path(__file__).parent / 'corpus' / 'templates'
    templates_dir.mkdir(parents=True, exist_ok=True)

    include_background = getattr(args, 'with_background', False)
    scans_only = getattr(args, 'scans_only', False)

    success_count = 0
    skipped_count = 0
    for numero in numeros:
        config = load_section_config(numero)

        if not config:
            print(f"[{numero}] Pas de config sections trouvée")
            continue

        # Filtrer les scans si demandé
        if scans_only and not config.is_scan():
            skipped_count += 1
            continue

        if not config.page1 and not config.page2:
            print(f"[{numero}] Config sans sections définies")
            continue

        # Générer le template
        template = generator.generate_from_config(config)

        # Déterminer le chemin de sortie
        if args.output and len(numeros) == 1:
            output_path = Path(args.output)
        else:
            output_path = templates_dir / f'bidul_{numero:03d}.svg'

        # Trouver le PDF si on veut inclure le fond
        pdf_path = None
        if include_background:
            pdf_path = find_pdf(numero)
            if not pdf_path:
                print(f"[{numero}] PDF non trouvé, génération sans fond")

        # Sauvegarder (passer la config pour rotation par page)
        if generator.save(template, output_path, pdf_path=pdf_path,
                         include_background=include_background, section_config=config):
            bg_info = " (avec fond PDF)" if pdf_path and include_background else ""
            print(f"[{numero}] Template généré: {output_path}{bg_info}")
            success_count += 1
        else:
            print(f"[{numero}] Erreur lors de la génération")

    print(f"\nGénéré: {success_count}/{len(numeros)} templates")
    if skipped_count > 0:
        print(f"Ignorés (type texte): {skipped_count}")
    return 0


def cmd_svg_preview(args):
    """Affiche un aperçu des zones d'extraction pour un Bidul."""
    import cv2
    import numpy as np
    from pdf2image import convert_from_path
    from core.section_extractor import load_section_config
    from core.svg_template import load_svg_template, SVGTemplateGenerator

    numero = args.numero
    pdf_path = find_pdf(numero)

    if not pdf_path:
        print(f"PDF non trouvé pour Bidul {numero}")
        return 1

    # Charger le template SVG ou en générer un depuis la config
    template = load_svg_template(numero)

    if not template:
        # Pas de template SVG, générer depuis la config
        config = load_section_config(numero)
        if config and (config.page1 or config.page2):
            generator = SVGTemplateGenerator(dpi=args.dpi)
            template = generator.generate_from_config(config)
            print(f"Template généré depuis config CSV")
        else:
            print(f"Pas de config disponible pour Bidul {numero}")
            return 1
    else:
        print(f"Template SVG chargé: {template.source_path}")

    # Convertir le PDF en images
    print(f"Conversion PDF: {pdf_path.name}")
    images = convert_from_path(str(pdf_path), dpi=args.dpi)

    # Afficher les zones pour chaque page du template
    pages_in_template = template.get_all_page_nums()

    for page_num in pages_in_template:
        if page_num > len(images):
            print(f"Page {page_num} n'existe pas dans le PDF ({len(images)} pages)")
            continue

        pil_image = images[page_num - 1]
        image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

        # Appliquer rotation si nécessaire
        if template.needs_rotation():
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            print(f"Page {page_num}: rotation appliquée")

        img_height, img_width = image.shape[:2]

        # Dessiner les zones
        zones = template.get_zones_for_page(page_num)
        exclusions = template.get_exclusion_zones(page_num)

        scale_x = img_width / template.viewbox_width
        scale_y = img_height / template.viewbox_height

        # Dessiner les zones d'extraction
        for zone in zones:
            x = int(zone.x * scale_x)
            y = int(zone.y * scale_y)
            w = int(zone.width * scale_x)
            h = int(zone.height * scale_y)

            # Couleur selon l'ordre
            colors = [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0),
                      (255, 0, 255), (0, 255, 255), (128, 128, 255), (255, 128, 128)]
            color = colors[(zone.order - 1) % len(colors)]

            cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
            cv2.putText(image, f"{zone.order}: {zone.id}", (x + 5, y + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # Dessiner les zones d'exclusion
        for zone in exclusions:
            x = int(zone.x * scale_x)
            y = int(zone.y * scale_y)
            w = int(zone.width * scale_x)
            h = int(zone.height * scale_y)
            cv2.rectangle(image, (x, y), (x + w, y + h), (128, 128, 128), 2)
            # Hachures diagonales
            for i in range(0, w + h, 20):
                x1 = x + min(i, w)
                y1 = y + max(0, i - w)
                x2 = x + max(0, i - h)
                y2 = y + min(i, h)
                cv2.line(image, (x1, y1), (x2, y2), (128, 128, 128), 1)

        # Info sur la page
        info_text = f"Page {page_num} | {len(zones)} zones | {template.orientation_texte}"
        cv2.putText(image, info_text, (20, img_height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 3)
        cv2.putText(image, info_text, (20, img_height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Sauvegarder ou afficher
        if args.output:
            output_path = Path(args.output)
            if len(pages_in_template) > 1:
                output_path = output_path.parent / f"{output_path.stem}_p{page_num}{output_path.suffix}"
            cv2.imwrite(str(output_path), image)
            print(f"Page {page_num}: {len(zones)} zones, sauvegardé -> {output_path}")
        else:
            output_path = Path(f"temp_bidul_{numero}_p{page_num}_zones.png")
            cv2.imwrite(str(output_path), image)
            print(f"Page {page_num}: {len(zones)} zones, sauvegardé -> {output_path}")

    return 0


def cmd_svg_list(args):
    """Liste les templates SVG disponibles."""
    from core.svg_template import get_template_manager

    manager = get_template_manager()
    templates = manager.list_templates()

    if not templates:
        print("Aucun template SVG trouvé dans corpus/templates/")
        return 0

    print(f"{'Numéro':<8} {'Fichier':<40} {'Zones':<8}")
    print("=" * 60)

    for numero, path in templates:
        template = manager.get_template(numero)
        num_zones = len(template.zones) if template else 0
        print(f"{numero:<8} {path.name:<40} {num_zones:<8}")

    print(f"\nTotal: {len(templates)} templates")
    return 0


# =============================================================================
# Corpus Commands
# =============================================================================

def cmd_corpus_generate(args):
    """Genere les fichiers CSV de corpus depuis la base."""
    import subprocess
    import sys

    script_path = Path(__file__).parent / 'scripts' / 'generate_corpus_csv.py'
    result = subprocess.run([sys.executable, str(script_path)], cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_corpus_stats(args):
    """Affiche les statistiques des corpus CSV."""
    import csv
    from pathlib import Path

    corpus_dir = Path(__file__).parent / 'corpus'

    files = [
        ('lieu.csv', 'Lieux'),
        ('lieu_alias.csv', 'Aliases lieux'),
        ('artiste.csv', 'Artistes'),
        ('artiste_alias.csv', 'Aliases artistes'),
        ('ville.csv', 'Villes'),
    ]

    print("=" * 40)
    print("STATISTIQUES DES CORPUS")
    print("=" * 40)

    for filename, label in files:
        path = corpus_dir / filename
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                count = sum(1 for _ in csv.reader(f)) - 1
            print(f"  {label:20} {count:5} entrees")
        else:
            print(f"  {label:20} [fichier manquant]")

    return 0


def cmd_corpus_test(args):
    """Teste la normalisation d'un lieu ou artiste."""
    from core.normalizer import normalize_name, get_lieu_normalizer, get_artiste_normalizer

    text = args.text
    norm = normalize_name(text)
    print(f"Entree:     '{text}'")
    print(f"Normalise:  '{norm}'")

    if args.type == 'lieu':
        normalizer = get_lieu_normalizer()
        result = normalizer.find_lieu(text)
        if result:
            print(f"Match:      '{result[0]}' (ville: {result[1]})")
        else:
            print("Aucun match trouve")
    else:
        normalizer = get_artiste_normalizer()
        result = normalizer.find_artiste(text)
        if result:
            print(f"Match:      '{result[0]}' (style: {result[1] or '-'})")
        else:
            print("Aucun match trouve")

    return 0


def cmd_corpus_add_lieu_alias(args):
    """Ajoute un alias de lieu."""
    import csv
    from pathlib import Path
    from core.normalizer import get_lieu_normalizer, reload_normalizers

    variante = args.variante
    lieu_nom = args.lieu_nom

    # Verifier que le lieu canonique existe
    normalizer = get_lieu_normalizer()
    result = normalizer.find_lieu(lieu_nom)

    if not result:
        print(f"! Lieu '{lieu_nom}' non trouve dans lieu.csv")
        return 1

    lieu_canonique = result[0]

    # Ajouter au CSV
    alias_path = Path(__file__).parent / 'corpus' / 'lieu_alias.csv'
    with open(alias_path, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([variante, lieu_canonique])

    print(f"+ Alias ajoute: '{variante}' -> '{lieu_canonique}'")

    # Recharger
    reload_normalizers()

    return 0


def cmd_corpus_add_artiste_alias(args):
    """Ajoute un alias d'artiste."""
    import csv
    from pathlib import Path
    from core.normalizer import get_artiste_normalizer, normalize_name, reload_normalizers

    variante = args.variante
    artiste_nom = args.artiste_nom

    normalizer = get_artiste_normalizer()
    result = normalizer.find_artiste(artiste_nom)

    artiste_canonique = artiste_nom

    if not result:
        print(f"! Artiste '{artiste_nom}' non trouve")
        # L'ajouter d'abord dans artiste.csv
        artiste_path = Path(__file__).parent / 'corpus' / 'artiste.csv'
        with open(artiste_path, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([artiste_nom, normalize_name(artiste_nom), ''])
        print(f"+ Artiste ajoute: '{artiste_nom}'")
    else:
        artiste_canonique = result[0]

    # Ajouter l'alias
    alias_path = Path(__file__).parent / 'corpus' / 'artiste_alias.csv'
    with open(alias_path, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([variante, artiste_canonique])

    print(f"+ Alias ajoute: '{variante}' -> '{artiste_canonique}'")
    reload_normalizers()

    return 0


# =============================================================================
# Clean Commands
# =============================================================================

def cmd_clean_all(args):
    """Execute tous les nettoyages."""
    import subprocess
    import sys

    script_path = Path(__file__).parent / 'scripts' / 'clean_data.py'
    result = subprocess.run([sys.executable, str(script_path)], cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_clean_prix(args):
    """Nettoie uniquement les prix aberrants."""
    import sqlite3
    import sys
    # Import dynamique du module
    sys.path.insert(0, str(Path(__file__).parent))
    from scripts.clean_data import clean_prix_aberrants

    db_path = Path(__file__).parent / 'database' / 'bidul_archives.db'
    conn = sqlite3.connect(str(db_path))
    count = clean_prix_aberrants(conn)
    conn.close()
    print(f"Nettoye {count} prix aberrants")

    return 0


def cmd_clean_lieux_dups(args):
    """Deduplique lieu_ref (fusionne variantes de casse)."""
    import sqlite3
    import sys
    # Import dynamique du module
    sys.path.insert(0, str(Path(__file__).parent))
    from scripts.clean_data import deduplicate_lieu_ref

    db_path = Path(__file__).parent / 'database' / 'bidul_archives.db'
    conn = sqlite3.connect(str(db_path))
    aliases = deduplicate_lieu_ref(conn)
    conn.close()

    if aliases:
        print("\nAliases a ajouter dans lieu_alias.csv:")
        for v, c in aliases:
            print(f"  '{v}' -> '{c}'")

    return 0


def cmd_corpus_dedupe_lieux(args):
    """Detecte et deduplique les lieux dans lieu.csv."""
    import subprocess
    import sys

    script_path = Path(__file__).parent / 'scripts' / 'dedupe_lieux.py'
    cmd = [sys.executable, str(script_path)]

    if args.apply:
        cmd.append('--apply')
    if args.report:
        cmd.append('--report')
    if args.interactive:
        cmd.append('--interactive')
    if args.keyword:
        cmd.extend(['--keyword', args.keyword])

    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_corpus_dedupe_artistes(args):
    """Detecte et deduplique les artistes dans artiste.csv."""
    import subprocess
    import sys

    script_path = Path(__file__).parent / 'scripts' / 'dedupe_artistes.py'
    cmd = [sys.executable, str(script_path)]

    if args.apply:
        cmd.append('--apply')
    if args.report:
        cmd.append('--report')
    if args.interactive:
        cmd.append('--interactive')
    if args.keyword:
        cmd.extend(['--keyword', args.keyword])

    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


# =============================================================================
# Sync DB <-> Corpus commands
# =============================================================================

def cmd_sync_corpus_to_db(args):
    """Importe les CSV corpus dans la DB."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'sync_corpus_db.py'
    cmd = [sys.executable, str(script_path), 'corpus-to-db']
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_sync_db_to_corpus(args):
    """Exporte les tables DB vers CSV corpus."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'sync_corpus_db.py'
    cmd = [sys.executable, str(script_path), 'db-to-corpus']
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_sync_dedupe_db(args):
    """Deduplique lieu_ref et artiste_ref en DB."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'sync_corpus_db.py'
    cmd = [sys.executable, str(script_path), 'dedupe-db']
    if args.apply:
        cmd.append('--apply')
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_sync_stats(args):
    """Statistiques des tables de reference en DB."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'sync_corpus_db.py'
    cmd = [sys.executable, str(script_path), 'stats']
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


# =============================================================================
# Ref Matching commands
# =============================================================================

def cmd_ref_migrate(args):
    """Migration: ajoute artiste_ref_id a contenu_evenement."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'migrate_ref_matching.py'
    cmd = [sys.executable, str(script_path), 'migrate']
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_ref_backfill(args):
    """Back-populate lieu_ref_id et artiste_ref_id."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'migrate_ref_matching.py'
    cmd = [sys.executable, str(script_path), 'backfill']
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_ref_stats(args):
    """Statistiques de matching ref_id."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'migrate_ref_matching.py'
    cmd = [sys.executable, str(script_path), 'stats']
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


# =============================================================================
# Maintenance Commands
# =============================================================================

def cmd_clean_database(args):
    """Nettoie les faux événements et artistes invalides."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'clean_database.py'
    cmd = [sys.executable, str(script_path)]
    if args.dry_run:
        cmd.append('--dry-run')
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_deduplicate(args):
    """Supprime les événements en double."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'deduplicate_events.py'
    cmd = [sys.executable, str(script_path)]
    if args.dry_run:
        cmd.append('--dry-run')
    if args.exact:
        cmd.append('--exact')
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_renormalize(args):
    """Re-normalise les lieux, artistes et villes."""
    import subprocess
    script_path = Path(__file__).parent / 'scripts' / 'renormalize.py'
    cmd = [sys.executable, str(script_path)]
    if args.dry_run:
        cmd.append('--dry-run')
    if args.lieux_only:
        cmd.append('--lieux-only')
    if args.artistes_only:
        cmd.append('--artistes-only')
    if args.villes_only:
        cmd.append('--villes-only')
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode


def cmd_maintenance(args):
    """Exécute toutes les tâches de maintenance (clean + dedupe + renormalize)."""
    import subprocess
    scripts_dir = Path(__file__).parent / 'scripts'

    print("=" * 60)
    print("MAINTENANCE COMPLÈTE DE LA BASE")
    print("=" * 60)

    dry_run_flag = ['--dry-run'] if args.dry_run else []

    # 1. Nettoyage
    print("\n[1/3] Nettoyage de la base...")
    result = subprocess.run(
        [sys.executable, str(scripts_dir / 'clean_database.py')] + dry_run_flag,
        cwd=str(Path(__file__).parent)
    )
    if result.returncode != 0:
        print("Erreur lors du nettoyage")
        return result.returncode

    # 2. Déduplication
    print("\n[2/3] Déduplication...")
    result = subprocess.run(
        [sys.executable, str(scripts_dir / 'deduplicate_events.py')] + dry_run_flag,
        cwd=str(Path(__file__).parent)
    )
    if result.returncode != 0:
        print("Erreur lors de la déduplication")
        return result.returncode

    # 3. Renormalisation
    print("\n[3/3] Re-normalisation...")
    result = subprocess.run(
        [sys.executable, str(scripts_dir / 'renormalize.py')] + dry_run_flag,
        cwd=str(Path(__file__).parent)
    )
    if result.returncode != 0:
        print("Erreur lors de la renormalisation")
        return result.returncode

    print("\n" + "=" * 60)
    print("✓ Maintenance terminée")
    print("=" * 60)
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
  python cli.py migrate                 # Migration pour consolidation
  python cli.py triage                  # Triage automatique
  python cli.py apply-aliases --sync-json  # Applique les alias artistes
  python cli.py review --status to_review  # Review interactive
  python cli.py quality-report          # Rapport de qualité
  python cli.py analyze-corrections     # Analyse des corrections

OCR (PDFs scannes):
  python cli.py ocr archives/1997-03_Bidul_002.pdf  # OCR d'un PDF
  python cli.py ocr archives/1997-03_Bidul_002.pdf -o output.txt  # Sauvegarde
  python cli.py ocr-test --samples 5    # Teste l'OCR sur 5 PDFs
  python cli.py ocr-extract --numero 35 # Extrait les evenements du Bidul 35
  python cli.py ocr-extract --range 1-50 --dry-run  # Previsualise l'extraction

Corpus (referentiels CSV):
  python cli.py corpus-generate         # Genere les CSV depuis la base
  python cli.py corpus-stats            # Statistiques des corpus
  python cli.py corpus-test "Th. Paul Scarron"  # Teste la normalisation
  python cli.py corpus-test "Dj SUPER LUCIEN" -t artiste  # Teste un artiste
  python cli.py corpus-add-lieu-alias "Th. Municipal" "Theatre Municipal"
  python cli.py corpus-add-artiste-alias "SMAK FLY" "SMAC FLY"

Nettoyage (base de donnees):
  python cli.py clean-all               # Execute tous les nettoyages
  python cli.py clean-prix              # Nettoie les prix aberrants
  python cli.py clean-lieux-dups        # Fusionne les doublons de lieux

Deduplication corpus:
  python cli.py corpus-dedupe-lieux             # Analyse les doublons lieu.csv
  python cli.py corpus-dedupe-lieux --apply     # Applique la deduplication
  python cli.py corpus-dedupe-lieux --report    # Exporte un rapport CSV
  python cli.py corpus-dedupe-lieux -k abbaye   # Review par mot-cle (interactif)
  python cli.py corpus-dedupe-artistes          # Analyse les doublons artiste.csv
  python cli.py corpus-dedupe-artistes --apply  # Applique la deduplication
  python cli.py corpus-dedupe-artistes -k jazz  # Review par mot-cle (interactif)

Synchronisation DB <-> Corpus:
  python cli.py sync-corpus-to-db               # Importe CSV corpus -> DB
  python cli.py sync-db-to-corpus               # Exporte DB -> CSV corpus
  python cli.py sync-dedupe-db                  # Deduplique en DB
  python cli.py sync-dedupe-db --apply          # Applique la deduplication
  python cli.py sync-stats                      # Stats des tables DB

Matching ref_id (lieu/artiste):
  python cli.py ref-migrate                     # Migration: ajoute artiste_ref_id
  python cli.py ref-backfill                    # Back-populate lieu_ref_id et artiste_ref_id
  python cli.py ref-stats                       # Stats de matching

Maintenance (normalisation v2):
  python cli.py clean-database                  # Nettoie faux evenements et artistes invalides
  python cli.py clean-database --dry-run       # Simule sans modifier
  python cli.py deduplicate                     # Supprime les evenements en double
  python cli.py deduplicate --exact             # Doublons exacts uniquement
  python cli.py renormalize                     # Re-normalise lieux, artistes, villes
  python cli.py renormalize --lieux-only        # Re-normalise uniquement les lieux
  python cli.py maintenance                     # Execute clean + dedupe + renormalize
  python cli.py maintenance --dry-run          # Simule la maintenance complete
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
    p_extract.add_argument('--force', action='store_true', help='Forcer l\'extraction même en cas d\'erreur')
    p_extract.add_argument('--no-ocr', action='store_true', help='Désactiver l\'OCR pour les scans')
    p_extract.add_argument('--dpi', type=int, default=200, help='Résolution OCR (défaut: 200)')
    p_extract.add_argument('--no-sections', action='store_true', help='Désactiver l\'extraction par sections A6')
    p_extract.add_argument('--auto-layout', action='store_true', help='Détection automatique du layout (colonnes, orientation)')

    # validate
    p_validate = subparsers.add_parser('validate', help='Valide une extraction')
    p_validate.add_argument('--numero', '-n', type=int, required=True, help='Numéro du Bidul')

    # compare
    p_compare = subparsers.add_parser('compare', help='Compare avec CSV de référence')
    p_compare.add_argument('--numero', '-n', type=int, required=True, help='Numéro du Bidul')
    p_compare.add_argument('--details', '-d', action='store_true', help='Afficher les différences')

    # stats
    p_stats = subparsers.add_parser('stats', help='Statistiques globales')
    p_stats.add_argument('--html', nargs='?', const='stats/bidul_stats.html', metavar='PATH',
                         help='Genere un dashboard HTML (defaut: stats/bidul_stats.html)')

    # list
    p_list = subparsers.add_parser('list', help='Liste les PDFs disponibles')
    p_list.add_argument('--type', '-t', choices=['scan', 'texte'], help='Filtrer par type')

    # populate
    p_populate = subparsers.add_parser('populate', help='Peuple avec CSV prioritaire ou PDF')
    p_populate.add_argument('--numero', '-n', type=int, nargs='+', help='Numéro(s) du Bidul (ex: -n 102 117 260)')
    p_populate.add_argument('--range', '-r', help='Plage de numéros (ex: 178-308)')
    p_populate.add_argument('--csv-only', action='store_true', help='Uniquement les Biduls avec CSV')
    p_populate.add_argument('--pdf-only', action='store_true', help='Ignorer les CSV (forcer extraction PDF)')
    p_populate.add_argument('--dry-run', action='store_true', help='Affiche sans sauvegarder')
    p_populate.add_argument('--replace', action='store_true', help='Remplacer les événements existants')
    p_populate.add_argument('--reparse', action='store_true', help='Re-parser les événements existants depuis raw_text (sans OCR)')
    p_populate.add_argument('--no-ocr', action='store_true', help='Désactiver l\'OCR pour les scans')
    p_populate.add_argument('--engine', '-e', default='google', choices=['paddleocr', 'easyocr', 'google'],
                           help='Moteur OCR (défaut: google)')
    p_populate.add_argument('--dpi', type=int, default=200, help='Résolution OCR (défaut: 200)')
    p_populate.add_argument('--no-sections', action='store_true', help='Désactiver l\'extraction par sections A6')
    p_populate.add_argument('--auto-layout', action='store_true', help='Détection automatique du layout (colonnes, orientation)')
    p_populate.add_argument('--include-regional', action='store_true',
                           help='Inclure les événements hors département (marqués is_regional=True)')
    p_populate.add_argument('--include-artifacts', action='store_true',
                           help='Inclure les faux événements (texte court, infos/annonces, sans contenu)')

    # export
    p_export = subparsers.add_parser('export', help='Exporte les événements vers CSV/XLSX')
    p_export.add_argument('--numero', '-n', type=int, help='Numéro du Bidul')
    p_export.add_argument('--range', '-r', help='Plage de numéros (ex: 280-290)')
    p_export.add_argument('--where', '-w', help='Clause WHERE SQL (ex: "ville_raw = \'Le Mans\'")')
    p_export.add_argument('--output', '-o', required=True, help='Fichier de sortie ou dossier')
    p_export.add_argument('--format', '-f', choices=['csv', 'xlsx'],
                         help='Format de sortie (déduit de l\'extension, sinon csv)')

    # purge
    p_purge = subparsers.add_parser('purge', help='Supprime les événements de la base')
    p_purge.add_argument('--all', '-a', action='store_true', help='Supprimer tous les événements')
    p_purge.add_argument('--numero', '-n', type=int, help='Numéro du Bidul')
    p_purge.add_argument('--range', '-r', help='Plage de numéros (ex: 280-290)')
    p_purge.add_argument('--dry-run', action='store_true', help='Affiche sans supprimer')

    # migrate
    p_migrate = subparsers.add_parser('migrate', help='Migration pour le système de consolidation')

    # triage
    p_triage = subparsers.add_parser('triage', help='Triage automatique des événements')
    p_triage.add_argument('--skip-duplicates', action='store_true', help='Ne pas détecter les doublons')

    # apply-aliases
    p_aliases = subparsers.add_parser('apply-aliases', help='Applique les alias artistes')
    p_aliases.add_argument('--sync-json', action='store_true', help='Synchroniser depuis le JSON')

    # review
    p_review = subparsers.add_parser('review', help='Session de review interactive')
    p_review.add_argument('--status', '-s', choices=['pending', 'to_review', 'flagged', 'ok'],
                          help='Filtrer par statut')
    p_review.add_argument('--numero', '-n', type=int, help='Filtrer par numéro de Bidul')

    # quality-report
    p_quality = subparsers.add_parser('quality-report', help='Rapport de qualité')

    # analyze-corrections
    p_analyze = subparsers.add_parser('analyze-corrections', help='Analyse des corrections')

    # ==========================================================================
    # OCR Commands
    # ==========================================================================

    # ocr - Extrait le texte d'un PDF scanné
    p_ocr = subparsers.add_parser('ocr', help='Extrait le texte d\'un PDF scanné par OCR')
    p_ocr.add_argument('pdf_path', nargs='?', help='Chemin vers le PDF à traiter (ou utiliser --numero)')
    p_ocr.add_argument('--numero', '-n', type=int, help='Numéro du Bidul (cherche le PDF automatiquement)')
    p_ocr.add_argument('--engine', '-e', default='paddleocr', choices=['paddleocr', 'easyocr', 'google'],
                       help='Moteur OCR (défaut: paddleocr)')
    p_ocr.add_argument('--dpi', '-d', type=int, default=200, help='Résolution pour conversion PDF (défaut: 200)')
    p_ocr.add_argument('--output', '-o', help='Fichier de sortie pour le texte extrait')
    p_ocr.add_argument('--raw', action='store_true', help='Ne pas appliquer le post-traitement')
    p_ocr.add_argument('--no-sections', action='store_true', help='Désactiver l\'extraction par sections A6')
    p_ocr.add_argument('--auto-layout', action='store_true', help='Détection automatique du layout (colonnes, orientation)')

    # ocr-test - Teste l'OCR sur un échantillon
    p_ocr_test = subparsers.add_parser('ocr-test', help='Teste l\'OCR sur un échantillon de PDFs scannés')
    p_ocr_test.add_argument('--samples', '-s', type=int, default=5, help='Nombre de PDFs à tester (défaut: 5)')
    p_ocr_test.add_argument('--dpi', '-d', type=int, default=200, help='Résolution pour conversion PDF (défaut: 200)')

    # ocr-extract - Extrait et parse les événements
    p_ocr_extract = subparsers.add_parser('ocr-extract', help='Extrait et parse les événements d\'un PDF scanné')
    p_ocr_extract.add_argument('--numero', '-n', type=int, help='Numéro du Bidul')
    p_ocr_extract.add_argument('--range', '-r', help='Plage de numéros (ex: 1-50)')
    p_ocr_extract.add_argument('--engine', '-e', default='google', choices=['paddleocr', 'easyocr', 'google'],
                               help='Moteur OCR (défaut: google)')
    p_ocr_extract.add_argument('--dpi', '-d', type=int, default=200, help='Résolution pour conversion PDF (défaut: 200)')
    p_ocr_extract.add_argument('--dry-run', action='store_true', help='Ne pas sauvegarder en base')
    p_ocr_extract.add_argument('--no-sections', action='store_true', help='Désactiver l\'extraction par sections A6')
    p_ocr_extract.add_argument('--auto-layout', action='store_true', help='Détection automatique du layout (colonnes, orientation)')

    # ==========================================================================
    # SVG Template Commands (v1.12+)
    # ==========================================================================

    # svg-generate - Génère un template SVG depuis la config CSV
    p_svg_gen = subparsers.add_parser('svg-generate', help='Génère un template SVG depuis la config CSV')
    p_svg_gen.add_argument('--numero', '-n', type=int, nargs='+', help='Numéro(s) du Bidul')
    p_svg_gen.add_argument('--range', '-r', help='Plage de numéros (ex: 1-20)')
    p_svg_gen.add_argument('--output', '-o', help='Fichier de sortie (si un seul numéro)')
    p_svg_gen.add_argument('--dpi', type=int, default=200, help='Résolution en DPI (défaut: 200)')
    p_svg_gen.add_argument('--with-background', '-b', action='store_true',
                           help='Inclure les pages PDF en arrière-plan (pour édition visuelle)')
    p_svg_gen.add_argument('--scans-only', '-s', action='store_true',
                           help='Générer uniquement pour les Biduls de type scan')

    # svg-preview - Prévisualise les zones d'extraction sur le PDF
    p_svg_preview = subparsers.add_parser('svg-preview', help='Prévisualise les zones d\'extraction sur le PDF')
    p_svg_preview.add_argument('--numero', '-n', type=int, required=True, help='Numéro du Bidul')
    p_svg_preview.add_argument('--output', '-o', help='Fichier de sortie PNG (défaut: temp_bidul_N_pX_zones.png)')
    p_svg_preview.add_argument('--dpi', type=int, default=200, help='Résolution en DPI (défaut: 200)')

    # svg-list - Liste les templates SVG disponibles
    p_svg_list = subparsers.add_parser('svg-list', help='Liste les templates SVG disponibles')

    # ==========================================================================
    # Corpus Commands
    # ==========================================================================

    # corpus-generate - Genere les CSV de corpus depuis la base
    p_corpus_gen = subparsers.add_parser('corpus-generate', help='Genere les fichiers CSV de corpus depuis la base')

    # corpus-stats - Statistiques des corpus
    p_corpus_stats = subparsers.add_parser('corpus-stats', help='Affiche les statistiques des corpus CSV')

    # corpus-test - Teste la normalisation
    p_corpus_test = subparsers.add_parser('corpus-test', help='Teste la normalisation d\'un lieu ou artiste')
    p_corpus_test.add_argument('text', help='Texte a normaliser')
    p_corpus_test.add_argument('--type', '-t', choices=['lieu', 'artiste'], default='lieu',
                               help='Type de normalisation (defaut: lieu)')

    # corpus-add-lieu-alias - Ajoute un alias de lieu
    p_corpus_lieu = subparsers.add_parser('corpus-add-lieu-alias', help='Ajoute un alias de lieu')
    p_corpus_lieu.add_argument('variante', help='Variante a ajouter')
    p_corpus_lieu.add_argument('lieu_nom', help='Nom du lieu canonique')

    # corpus-add-artiste-alias - Ajoute un alias d'artiste
    p_corpus_artiste = subparsers.add_parser('corpus-add-artiste-alias', help='Ajoute un alias d\'artiste')
    p_corpus_artiste.add_argument('variante', help='Variante a ajouter')
    p_corpus_artiste.add_argument('artiste_nom', help='Nom de l\'artiste canonique')

    # corpus-dedupe-lieux - Deduplique les lieux dans lieu.csv
    p_corpus_dedupe = subparsers.add_parser('corpus-dedupe-lieux', help='Detecte et deduplique les lieux dans lieu.csv')
    p_corpus_dedupe.add_argument('--apply', '-a', action='store_true', help='Appliquer les changements')
    p_corpus_dedupe.add_argument('--report', '-r', action='store_true', help='Exporter un rapport CSV')
    p_corpus_dedupe.add_argument('--interactive', '-i', action='store_true', help='Mode interactif')
    p_corpus_dedupe.add_argument('--keyword', '-k', type=str, help='Mot-cle pour filtrer les lieux')

    # corpus-dedupe-artistes - Deduplique les artistes dans artiste.csv
    p_corpus_dedupe_art = subparsers.add_parser('corpus-dedupe-artistes', help='Detecte et deduplique les artistes dans artiste.csv')
    p_corpus_dedupe_art.add_argument('--apply', '-a', action='store_true', help='Appliquer les changements')
    p_corpus_dedupe_art.add_argument('--report', '-r', action='store_true', help='Exporter un rapport CSV')
    p_corpus_dedupe_art.add_argument('--interactive', '-i', action='store_true', help='Mode interactif')
    p_corpus_dedupe_art.add_argument('--keyword', '-k', type=str, help='Mot-cle pour filtrer les artistes')

    # ==========================================================================
    # Clean Commands
    # ==========================================================================

    # clean-all - Execute tous les nettoyages
    p_clean_all = subparsers.add_parser('clean-all', help='Execute tous les nettoyages de la base')

    # clean-prix - Nettoie les prix aberrants
    p_clean_prix = subparsers.add_parser('clean-prix', help='Nettoie les prix aberrants')

    # clean-lieux-dups - Deduplique lieu_ref
    p_clean_lieux = subparsers.add_parser('clean-lieux-dups', help='Deduplique lieu_ref (fusionne variantes de casse)')

    # ==========================================================================
    # Sync Commands (DB <-> Corpus)
    # ==========================================================================

    # sync-corpus-to-db - Importe CSV corpus dans DB
    p_sync_to_db = subparsers.add_parser('sync-corpus-to-db', help='Importe les CSV corpus dans la DB')

    # sync-db-to-corpus - Exporte DB vers CSV corpus
    p_sync_to_csv = subparsers.add_parser('sync-db-to-corpus', help='Exporte les tables DB vers CSV corpus')

    # sync-dedupe-db - Deduplique en DB
    p_sync_dedupe = subparsers.add_parser('sync-dedupe-db', help='Deduplique lieu_ref et artiste_ref en DB')
    p_sync_dedupe.add_argument('--apply', '-a', action='store_true', help='Appliquer les changements')

    # sync-stats - Stats des tables DB
    p_sync_stats = subparsers.add_parser('sync-stats', help='Statistiques des tables de reference en DB')

    # ==========================================================================
    # Ref Matching Commands
    # ==========================================================================

    # ref-migrate - Migration pour ajouter artiste_ref_id
    p_ref_migrate = subparsers.add_parser('ref-migrate', help='Migration: ajoute artiste_ref_id a contenu_evenement')

    # ref-backfill - Back-populate les ref_id
    p_ref_backfill = subparsers.add_parser('ref-backfill', help='Back-populate lieu_ref_id et artiste_ref_id')

    # ref-stats - Stats de matching
    p_ref_stats = subparsers.add_parser('ref-stats', help='Statistiques de matching ref_id')

    # ==========================================================================
    # Maintenance Commands
    # ==========================================================================

    # clean-database - Nettoie les faux événements
    p_clean_db = subparsers.add_parser('clean-database', help='Nettoie les faux événements et artistes invalides')
    p_clean_db.add_argument('--dry-run', '-n', action='store_true', help='Simule sans modifier')

    # deduplicate - Supprime les doublons
    p_dedupe = subparsers.add_parser('deduplicate', help='Supprime les événements en double')
    p_dedupe.add_argument('--dry-run', '-n', action='store_true', help='Simule sans modifier')
    p_dedupe.add_argument('--exact', '-e', action='store_true', help='Recherche doublons exacts uniquement')

    # renormalize - Re-normalise les données
    p_renorm = subparsers.add_parser('renormalize', help='Re-normalise lieux, artistes et villes')
    p_renorm.add_argument('--dry-run', '-n', action='store_true', help='Simule sans modifier')
    p_renorm.add_argument('--lieux-only', action='store_true', help='Re-normaliser uniquement les lieux')
    p_renorm.add_argument('--artistes-only', action='store_true', help='Re-normaliser uniquement les artistes')
    p_renorm.add_argument('--villes-only', action='store_true', help='Re-normaliser uniquement les villes')

    # maintenance - Exécute toutes les tâches de maintenance
    p_maint = subparsers.add_parser('maintenance', help='Exécute clean + dedupe + renormalize')
    p_maint.add_argument('--dry-run', '-n', action='store_true', help='Simule sans modifier')

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
        'export': cmd_export,
        'purge': cmd_purge,
        'migrate': cmd_migrate,
        'triage': cmd_triage,
        'apply-aliases': cmd_apply_aliases,
        'review': cmd_review,
        'quality-report': cmd_quality_report,
        'analyze-corrections': cmd_analyze_corrections,
        # OCR commands
        'ocr': cmd_ocr,
        'ocr-test': cmd_ocr_test,
        'ocr-extract': cmd_ocr_extract,
        # SVG Template commands (v1.12+)
        'svg-generate': cmd_svg_generate,
        'svg-preview': cmd_svg_preview,
        'svg-list': cmd_svg_list,
        # Corpus commands
        'corpus-generate': cmd_corpus_generate,
        'corpus-stats': cmd_corpus_stats,
        'corpus-test': cmd_corpus_test,
        'corpus-add-lieu-alias': cmd_corpus_add_lieu_alias,
        'corpus-add-artiste-alias': cmd_corpus_add_artiste_alias,
        'corpus-dedupe-lieux': cmd_corpus_dedupe_lieux,
        'corpus-dedupe-artistes': cmd_corpus_dedupe_artistes,
        # Clean commands
        'clean-all': cmd_clean_all,
        'clean-prix': cmd_clean_prix,
        'clean-lieux-dups': cmd_clean_lieux_dups,
        # Sync DB <-> Corpus commands
        'sync-corpus-to-db': cmd_sync_corpus_to_db,
        'sync-db-to-corpus': cmd_sync_db_to_corpus,
        'sync-dedupe-db': cmd_sync_dedupe_db,
        'sync-stats': cmd_sync_stats,
        # Ref Matching commands
        'ref-migrate': cmd_ref_migrate,
        'ref-backfill': cmd_ref_backfill,
        'ref-stats': cmd_ref_stats,
        # Maintenance commands
        'clean-database': cmd_clean_database,
        'deduplicate': cmd_deduplicate,
        'renormalize': cmd_renormalize,
        'maintenance': cmd_maintenance,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

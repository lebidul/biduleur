# biduleur/main.py
import os
import sys
import argparse
import traceback
import logging
from pathlib import Path
import importlib.resources as res
from datetime import datetime

# --- Imports des modules internes ---
from biduleur.csv_utils import parse_bidul
from biduleur.format_utils import output_html_file

# --- Import du logger partagé ---
# Cet import est conçu pour fonctionner que le script soit lancé
# depuis la racine du projet ou depuis le dossier 'biduleur'.
try:
    from misenpageur.logger import setup_logger, save_dict_to_json, save_text_to_file
except (ModuleNotFoundError, ImportError):
    # Fallback si misenpageur n'est pas dans le path
    # Crée un logger de base qui n'écrit que dans la console.
    def setup_logger():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')


# --- Logique métier ---

def run_biduleur(input_file: str, bidul_output_file: str, agenda_output_file: str) -> tuple[bool, int]:
    """
    Fonction principale qui traite le fichier d'entrée et génère les sorties HTML.
    Retourne True en cas de succès, False sinon.
    """
    log = logging.getLogger(__name__)
    try:
        log.info(f"Début du traitement pour le fichier : {input_file}")

        # S'assurer que les dossiers de sortie existent
        Path(bidul_output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(agenda_output_file).parent.mkdir(parents=True, exist_ok=True)

        html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(input_file)

        log.info(f"Génération du fichier Bidul HTML : {bidul_output_file}")
        output_html_file(html_body_bidul, original_file_name=input_file, output_filename=bidul_output_file)

        log.info(f"Génération du fichier Agenda HTML : {agenda_output_file}")
        output_html_file(html_body_agenda, original_file_name=input_file, output_filename=agenda_output_file)

        log.info("-" * 40)
        log.info("Traitement terminé avec succès !")
        log.info(f"Nombre d'événements traités : {number_of_lines}")
        log.info("-" * 40)
        return True, number_of_lines

    except Exception as e:
        log.error(f"Une erreur critique est survenue lors du traitement de {input_file}.", exc_info=True)
        return False, 0


# --- Gestionnaire de la ligne de commande (CLI) ---

def make_parser() -> argparse.ArgumentParser:
    """Crée et configure le parser d'arguments pour la ligne de commande."""
    p = argparse.ArgumentParser(
        prog="biduleur",
        description="Convertit un fichier d'événements (XLS/CSV) en deux fichiers HTML distincts."
    )
    p.add_argument(
        "input_file",
        help="Chemin du fichier d'entrée (CSV, XLS, XLSX)."
    )
    p.add_argument(
        "--out-bidul",
        help="Chemin du fichier de sortie pour le Bidul HTML. (Défaut: <input>.html)"
    )
    p.add_argument(
        "--out-agenda",
        help="Chemin du fichier de sortie pour l'Agenda HTML. (Défaut: <input>.agenda.html)"
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Activer l'affichage des logs détaillés dans la console."
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Activer le mode débogage (crée un dossier de log horodaté)."
    )
    return p


def main() -> int:
    """Point d'entrée principal pour l'exécution en ligne de commande."""
    parser = make_parser()
    args = parser.parse_args()

    debug_dir = None
    if args.debug:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        debug_dir = Path(args.input_file).parent / f"biduleur_debug_{timestamp}"

    # Configure le logger (il utilisera le dossier s'il est défini)
    # et la console si verbose est activé.
    setup_logger(log_dir=str(debug_dir) if debug_dir else None)
    log = logging.getLogger(__name__)

    # Par défaut, n'afficher que les avertissements et erreurs.
    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.INFO  # Afficher les infos si -v
    if args.debug:
        log_level = logging.INFO  # Afficher aussi les infos si --debug

    logging.getLogger().setLevel(log_level)

    # Déterminer les chemins de sortie par défaut si non fournis
    input_path = Path(args.input_file)
    bidul_output = args.out_bidul or str(input_path.with_suffix(".html"))
    agenda_output = args.out_agenda or str(input_path.with_suffix(".agenda.html"))

    # Exécuter la logique métier et récupérer le résultat
    success, num_lines = run_biduleur(args.input_file, bidul_output, agenda_output)

    if args.debug and debug_dir:
        # 1. Sauvegarder la "configuration" (les arguments passés)
        config_data = {
            "input_file": args.input_file,
            "out_bidul": bidul_output,
            "out_agenda": agenda_output,
        }
        save_dict_to_json(config_data, "config.json", str(debug_dir))

        # 2. Sauvegarder le résumé
        summary_text = f"Succès: {success}\nÉvénements traités: {num_lines}"
        save_text_to_file(summary_text, "summary.info", str(debug_dir))

    if args.debug:
        try:
            from misenpageur.logger import shutdown_logger
            shutdown_logger()
        except (ModuleNotFoundError, ImportError):
            pass # Ignorer si le logger n'a pas pu être importé

    return 0 if success else 1


if __name__ == '__main__':
    # Cette structure permet au module d'être à la fois exécutable et importable.
    # L'ancienne version avec `gui_mode` a été retirée pour séparer les responsabilités.
    # Ce fichier est maintenant un pur outil en ligne de commande.
    sys.exit(main())
# misenpageur/logger.py
import logging
import sys
from pathlib import Path
from typing import Optional
import json

# Garder une référence au gestionnaire de fichier pour pouvoir le fermer
file_handler = None

def setup_logger(log_dir: Optional[str] = None, level=logging.INFO):
    """
    Configure le logger racine.

    - Écrit toujours dans la console.
    - Écrit dans un fichier si `log_dir` est fourni.
    """
    global file_handler

    # Formatteur pour les messages
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Nettoyer les anciens handlers pour éviter les duplications
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 1. Handler pour la console (toujours activé)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # 2. Handler pour le fichier (activé seulement si log_dir est fourni)
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path / "execution.log", encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.info(f"Le log sera également sauvegardé dans : {log_path / 'execution.log'}")

def shutdown_logger():
    """Ferme proprement le gestionnaire de fichier du logger, s'il existe."""
    global file_handler
    if file_handler:
        logging.getLogger().info("Fermeture du fichier de log.")
        # Important : il faut fermer et retirer le handler
        file_handler.close()
        logging.getLogger().removeHandler(file_handler)
        file_handler = None

def save_dict_to_json(data: dict, filename: str, log_dir: str):
    """Sauvegarde un dictionnaire dans un fichier JSON dans le dossier de log."""
    if not log_dir: return
    log = logging.getLogger(__name__)
    try:
        filepath = Path(log_dir) / filename
        log.info(f"Sauvegarde de la configuration dans : {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Impossible de sauvegarder le fichier JSON {filename}: {e}")

def save_text_to_file(text: str, filename: str, log_dir: str):
    """Sauvegarde une chaîne de caractères dans un fichier dans le dossier de log."""
    if not log_dir: return
    log = logging.getLogger(__name__)
    try:
        filepath = Path(log_dir) / filename
        log.info(f"Sauvegarde du résumé dans : {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
    except Exception as e:
        log.error(f"Impossible de sauvegarder le fichier texte {filename}: {e}")
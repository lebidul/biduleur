#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fonctions utilitaires pour l'application Le Truc (PyQt6)
"""
import os
import sys
import subprocess
from pathlib import Path


def get_resource_path(relative_path):
    """
    Retourne le chemin absolu vers une ressource, fonctionne en mode dev et packagé.
    """
    if getattr(sys, 'frozen', False):
        # En mode packagé (PyInstaller)
        base_path = getattr(sys, '_MEIPASS')
    else:
        # En mode développement
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


def ensure_parent_dir(path: str):
    """Crée le dossier parent si nécessaire"""
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def open_file(filepath):
    """Ouvre un fichier avec l'application par défaut du système"""
    if not filepath or not os.path.exists(filepath):
        print(f"[WARN] Impossible d'ouvrir le fichier : {filepath}")
        return

    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", filepath])
        else:  # Linux
            subprocess.run(["xdg-open", filepath])
    except Exception as e:
        print(f"[ERROR] Impossible d'ouvrir le fichier : {e}")


def default_paths_from_input(input_file: str) -> dict:
    """Génère les chemins de sortie par défaut depuis le fichier d'entrée"""
    if not input_file:
        return {
            "html": "",
            "agenda_html": "",
            "pdf": "",
            "svg_output_dir": "",
            "stories_output": ""
        }

    input_path = Path(input_file)
    base = input_path.stem
    folder = input_path.parent

    return {
        "html": str(folder / f"{base}.html"),
        "agenda_html": str(folder / f"{base}.agenda.html"),
        "pdf": str(folder / f"{base}.pdf"),
        "svg_output_dir": str(folder / "svgs"),
        "stories_output": str(folder / "stories")
    }


def project_defaults() -> dict:
    """Définit les chemins par défaut pour les fichiers de config et layout"""
    repo_root = get_resource_path('.')
    cfg = os.path.join(repo_root, "misenpageur", "config.yml")
    lay = os.path.join(repo_root, "misenpageur", "layout.yml")

    return {
        "root": repo_root,
        "config": cfg,
        "layout": lay
    }


def validate_float(value: str, field_name: str) -> float:
    """Valide et convertit une valeur en float"""
    try:
        return float(value.strip().replace(',', '.'))
    except ValueError:
        raise ValueError(f"Le champ '{field_name}' doit être un nombre valide.")


def validate_int(value: str, field_name: str) -> int:
    """Valide et convertit une valeur en int"""
    try:
        return int(value.strip())
    except ValueError:
        raise ValueError(f"Le champ '{field_name}' doit être un nombre entier valide.")
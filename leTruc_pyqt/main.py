#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Point d'entrée de l'application Le Truc (PyQt6)
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from main_window import MainWindow
from utils.helpers import get_resource_path

try:
    from _version import __version__
except ImportError:
    __version__ = "dev"


def main():
    """Lance l'application"""
    app = QApplication(sys.argv)
    app.setApplicationName(f"Le Truc v{__version__}")
    app.setOrganizationName("Les Arts Services")

    # Définir l'icône de l'application
    try:
        icon_path = get_resource_path("leTruc/assets/LesArtsServices.ico")
        app.setWindowIcon(QIcon(icon_path))
    except Exception as e:
        print(f"[WARN] Impossible de charger l'icône : {e}")

    # Créer et afficher la fenêtre principale
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
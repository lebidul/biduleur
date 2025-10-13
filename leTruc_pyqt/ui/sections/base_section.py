#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classe de base pour toutes les sections de l'interface
"""
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout


class BaseSection(QGroupBox):
    """Classe de base pour une section de l'interface"""

    def __init__(self, title: str, config_manager):
        super().__init__(title)
        self.config = config_manager
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.init_ui()

    def init_ui(self):
        """À surcharger dans les classes filles pour créer l'interface"""
        raise NotImplementedError("Les sections doivent implémenter init_ui()")
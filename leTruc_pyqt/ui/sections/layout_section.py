#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Layout - Mise en page globale
"""
from PyQt6.QtWidgets import (QLabel, QLineEdit, QRadioButton, QGridLayout, QHBoxLayout)
from ui.sections.base_section import BaseSection
from utils.helpers import validate_float


class LayoutSection(BaseSection):
    """Section pour la mise en page globale"""

    def __init__(self, config_manager):
        super().__init__("Mise en Page Globale", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()
        row = 0

        # Marge globale
        grid.addWidget(QLabel("Marge globale (mm) :"), row, 0)
        self.margin_edit = QLineEdit()
        self.margin_edit.setText(str(self.config.get("page_margin_mm", 1.0)))
        self.margin_edit.setMaximumWidth(100)
        grid.addWidget(self.margin_edit, row, 1)
        row += 1

        # Taille de police
        grid.addWidget(QLabel("Taille de police :"), row, 0)
        mode_h = QHBoxLayout()

        self.auto_radio = QRadioButton("Automatique")
        self.auto_radio.setChecked(True)
        self.auto_radio.toggled.connect(self.on_mode_changed)
        mode_h.addWidget(self.auto_radio)

        self.force_radio = QRadioButton("Forcée")
        mode_h.addWidget(self.force_radio)
        mode_h.addStretch()

        grid.addLayout(mode_h, row, 1, 1, 2)
        row += 1

        # Taille forcée (visible seulement si forcée)
        self.forced_label = QLabel("Taille forcée (pt) :")
        grid.addWidget(self.forced_label, row, 0)
        self.forced_edit = QLineEdit()
        self.forced_edit.setText(str(self.config.get("font_size_forced", 10.0)))
        self.forced_edit.setMaximumWidth(100)
        grid.addWidget(self.forced_edit, row, 1)

        self.forced_label.setVisible(False)
        self.forced_edit.setVisible(False)

        grid.setColumnStretch(2, 1)
        self.layout.addLayout(grid)

        # Appliquer le mode par défaut
        if self.config.get("font_size_mode", "auto") == "force":
            self.force_radio.setChecked(True)

    def on_mode_changed(self):
        """Affiche/cache le champ de taille forcée"""
        is_force = self.force_radio.isChecked()
        self.forced_label.setVisible(is_force)
        self.forced_edit.setVisible(is_force)

    def get_page_margin(self) -> float:
        return validate_float(self.margin_edit.text(), "Marge globale")

    def get_font_size_mode(self) -> str:
        return "force" if self.force_radio.isChecked() else "auto"

    def get_font_size_forced(self) -> float:
        return validate_float(self.forced_edit.text(), "Taille de police forcée")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Logos - Paramètres des logos
"""
from PyQt6.QtWidgets import (QLabel, QLineEdit, QPushButton, QRadioButton,
                             QGridLayout, QHBoxLayout, QFileDialog)
from ui.sections.base_section import BaseSection
from utils.helpers import validate_float


class LogosSection(BaseSection):
    """Section pour les paramètres des logos"""

    def __init__(self, config_manager):
        super().__init__("Paramètres des Logos", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()
        row = 0

        # Dossier logos
        grid.addWidget(QLabel("Dossier logos :"), row, 0)
        self.logos_dir_edit = QLineEdit()
        self.logos_dir_edit.setText(self.config.get("logos_dir", ""))
        grid.addWidget(self.logos_dir_edit, row, 1)

        browse_button = QPushButton("Parcourir...")
        browse_button.clicked.connect(self.browse_directory)
        grid.addWidget(browse_button, row, 2)
        row += 1

        # Répartition
        grid.addWidget(QLabel("Répartition :"), row, 0)
        layout_h = QHBoxLayout()

        self.colonnes_radio = QRadioButton("2 Colonnes")
        self.colonnes_radio.setChecked(True)
        self.colonnes_radio.toggled.connect(self.on_layout_changed)
        layout_h.addWidget(self.colonnes_radio)

        self.optimise_radio = QRadioButton("Optimisée")
        layout_h.addWidget(self.optimise_radio)
        layout_h.addStretch()

        grid.addLayout(layout_h, row, 1, 1, 2)
        row += 1

        # Marge (visible seulement si optimisée)
        self.padding_label = QLabel("Marge (mm) :")
        grid.addWidget(self.padding_label, row, 0)
        self.padding_edit = QLineEdit("1.0")
        self.padding_edit.setMaximumWidth(100)
        grid.addWidget(self.padding_edit, row, 1)

        self.padding_label.setVisible(False)
        self.padding_edit.setVisible(False)

        grid.setColumnStretch(1, 1)
        self.layout.addLayout(grid)

    def browse_directory(self):
        """Ouvre le dialogue pour choisir un dossier"""
        path = QFileDialog.getExistingDirectory(self, "Dossier des logos")
        if path:
            self.logos_dir_edit.setText(path)

    def on_layout_changed(self):
        """Affiche/cache le champ de marge"""
        is_optimise = self.optimise_radio.isChecked()
        self.padding_label.setVisible(is_optimise)
        self.padding_edit.setVisible(is_optimise)

    def get_logos_dir(self) -> str:
        return self.logos_dir_edit.text().strip()

    def get_logos_layout(self) -> str:
        return "optimise" if self.optimise_radio.isChecked() else "colonnes"

    def get_logos_padding(self) -> float:
        return validate_float(self.padding_edit.text(), "Marge logos")
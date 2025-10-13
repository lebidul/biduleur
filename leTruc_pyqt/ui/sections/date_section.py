#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Date - Séparateur de dates
"""
from PyQt6.QtWidgets import (QLabel, QLineEdit, QPushButton, QRadioButton,
                             QGridLayout, QHBoxLayout, QColorDialog)
from PyQt6.QtGui import QColor
from ui.sections.base_section import BaseSection
from utils.helpers import validate_float


class DateSection(BaseSection):
    """Section pour le séparateur de dates"""

    def __init__(self, config_manager):
        super().__init__("Séparateur de dates", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()
        row = 0

        # Type de séparateur
        grid.addWidget(QLabel("Type de séparateur :"), row, 0)
        sep_h = QHBoxLayout()

        self.aucun_radio = QRadioButton("Aucun")
        sep_h.addWidget(self.aucun_radio)

        self.ligne_radio = QRadioButton("Ligne")
        self.ligne_radio.setChecked(True)
        sep_h.addWidget(self.ligne_radio)

        self.box_radio = QRadioButton("Box")
        self.box_radio.toggled.connect(self.on_type_changed)
        sep_h.addWidget(self.box_radio)
        sep_h.addStretch()

        grid.addLayout(sep_h, row, 1, 1, 2)
        row += 1

        # Espace avant/après
        grid.addWidget(QLabel("Espace avant/après date (pt) :"), row, 0)
        self.spacing_edit = QLineEdit()
        self.spacing_edit.setText(self.config.get("date_spacing", "4"))
        self.spacing_edit.setMaximumWidth(100)
        grid.addWidget(self.spacing_edit, row, 1)
        row += 1

        # Couleur de fond (visible seulement si Box)
        self.color_label = QLabel("Couleur de fond :")
        grid.addWidget(self.color_label, row, 0)

        color_h = QHBoxLayout()
        self.color_preview = QLabel("    ")
        self.color_preview.setStyleSheet("background-color: #FFFFFF; border: 1px solid black;")
        self.color_preview.setMaximumWidth(30)
        color_h.addWidget(self.color_preview)

        self.color_button = QPushButton("...")
        self.color_button.setMaximumWidth(30)
        self.color_button.clicked.connect(self.choose_color)
        color_h.addWidget(self.color_button)
        color_h.addStretch()

        grid.addLayout(color_h, row, 1)

        self.back_color = "#FFFFFF"
        self.color_label.setVisible(False)
        self.color_preview.setVisible(False)
        self.color_button.setVisible(False)

        grid.setColumnStretch(2, 1)
        self.layout.addLayout(grid)

        # Appliquer le type par défaut
        sep_type = self.config.get("date_separator_type", "ligne")
        if sep_type == "aucun":
            self.aucun_radio.setChecked(True)
        elif sep_type == "box":
            self.box_radio.setChecked(True)
        else:
            self.ligne_radio.setChecked(True)

    def on_type_changed(self):
        """Affiche/cache le sélecteur de couleur"""
        is_box = self.box_radio.isChecked()
        self.color_label.setVisible(is_box)
        self.color_preview.setVisible(is_box)
        self.color_button.setVisible(is_box)

    def choose_color(self):
        """Ouvre le sélecteur de couleur"""
        current_color = QColor(self.back_color)
        color = QColorDialog.getColor(current_color, self, "Couleur de fond")
        if color.isValid():
            self.back_color = color.name()
            self.color_preview.setStyleSheet(
                f"background-color: {self.back_color}; border: 1px solid black;"
            )

    def get_separator_type(self) -> str:
        if self.aucun_radio.isChecked():
            return "aucun"
        elif self.box_radio.isChecked():
            return "box"
        return "ligne"

    def get_date_spacing(self) -> float:
        return validate_float(self.spacing_edit.text(), "Espace date")

    def get_box_back_color(self) -> str:
        return self.back_color
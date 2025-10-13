#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Poster - Paramètres de mise en page du poster
"""
from PyQt6.QtWidgets import (QLabel, QLineEdit, QRadioButton, QSlider,
                             QGridLayout, QHBoxLayout)
from PyQt6.QtCore import Qt
from ui.sections.base_section import BaseSection
from utils.helpers import validate_float


class PosterSection(BaseSection):
    """Section pour les paramètres du poster"""

    def __init__(self, config_manager):
        super().__init__("Paramètres de mise en page (Poster)", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()
        row = 0

        # Titre du poster
        grid.addWidget(QLabel("Titre du poster :"), row, 0)
        self.title_edit = QLineEdit()
        self.title_edit.setText(self.config.get("poster_title", ""))
        grid.addWidget(self.title_edit, row, 1, 1, 2)
        row += 1

        # Design du poster
        grid.addWidget(QLabel("Design du poster :"), row, 0)
        design_h = QHBoxLayout()

        self.centre_radio = QRadioButton("Image au centre")
        self.centre_radio.setChecked(True)
        self.centre_radio.toggled.connect(self.on_design_changed)
        design_h.addWidget(self.centre_radio)

        self.fond_radio = QRadioButton("Image en fond")
        design_h.addWidget(self.fond_radio)
        design_h.addStretch()

        grid.addLayout(design_h, row, 1, 1, 2)
        row += 1

        # Transparence (visible seulement si Image en fond)
        self.alpha_label = QLabel("Transparence du voile blanc :")
        grid.addWidget(self.alpha_label, row, 0)

        alpha_h = QHBoxLayout()
        self.alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.alpha_slider.setMinimum(0)
        self.alpha_slider.setMaximum(100)
        self.alpha_slider.setValue(int(self.config.get("background_alpha", 0.85) * 100))
        self.alpha_slider.valueChanged.connect(self.update_alpha_label)
        alpha_h.addWidget(self.alpha_slider)

        self.alpha_value_label = QLabel(f"{self.alpha_slider.value()}%")
        self.alpha_value_label.setMinimumWidth(40)
        alpha_h.addWidget(self.alpha_value_label)

        grid.addLayout(alpha_h, row, 1, 1, 2)

        self.alpha_label.setVisible(False)
        self.alpha_slider.setVisible(False)
        self.alpha_value_label.setVisible(False)
        row += 1

        # Facteur de sécurité
        grid.addWidget(QLabel("Facteur de sécurité police :"), row, 0)
        self.safety_edit = QLineEdit()
        self.safety_edit.setText(str(self.config.get("font_size_safety_factor", 0.98)))
        self.safety_edit.setMaximumWidth(100)
        grid.addWidget(self.safety_edit, row, 1)

        grid.setColumnStretch(2, 1)
        self.layout.addLayout(grid)

        # Appliquer le design par défaut
        if self.config.get("poster_design", 0) == 1:
            self.fond_radio.setChecked(True)

    def on_design_changed(self):
        """Affiche/cache le slider de transparence"""
        is_fond = self.fond_radio.isChecked()
        self.alpha_label.setVisible(is_fond)
        self.alpha_slider.setVisible(is_fond)
        self.alpha_value_label.setVisible(is_fond)

    def update_alpha_label(self):
        """Met à jour le label du pourcentage"""
        self.alpha_value_label.setText(f"{self.alpha_slider.value()}%")

    def get_poster_title(self) -> str:
        return self.title_edit.text().strip()

    def get_poster_design(self) -> int:
        return 1 if self.fond_radio.isChecked() else 0

    def get_safety_factor(self) -> float:
        return validate_float(self.safety_edit.text(), "Facteur de sécurité")

    def get_background_alpha(self) -> float:
        return self.alpha_slider.value() / 100.0
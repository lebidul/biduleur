#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Stories - Préparation de la story Instagram
"""
from PyQt6.QtWidgets import (QLabel, QLineEdit, QPushButton, QComboBox,
                             QRadioButton, QSlider, QGridLayout, QHBoxLayout,
                             QColorDialog, QFileDialog)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from ui.sections.base_section import BaseSection
from utils.helpers import validate_int


class StoriesSection(BaseSection):
    """Section pour les paramètres des Stories Instagram"""

    def __init__(self, config_manager):
        super().__init__("Préparation de la story Instagram", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()
        row = 0

        # Police
        grid.addWidget(QLabel("Police :"), row, 0)
        font_h = QHBoxLayout()

        self.font_combo = QComboBox()
        self.font_combo.addItems(["Arial", "Helvetica", "Times New Roman", "Verdana", "Impact"])
        self.font_combo.setCurrentText(self.config.get("stories_font_name", "Arial"))
        font_h.addWidget(self.font_combo)

        font_h.addWidget(QLabel("Taille (pt) :"))
        self.font_size_edit = QLineEdit()
        self.font_size_edit.setText(str(self.config.get("stories_font_size", 45)))
        self.font_size_edit.setMaximumWidth(60)
        font_h.addWidget(self.font_size_edit)
        font_h.addStretch()

        grid.addLayout(font_h, row, 1, 1, 2)
        row += 1

        # Couleur de la police
        grid.addWidget(QLabel("Couleur de la police :"), row, 0)
        font_color_h = QHBoxLayout()

        self.font_color_preview = QLabel("    ")
        self.font_color = self.config.get("stories_font_color", "#000000")
        self.font_color_preview.setStyleSheet(
            f"background-color: {self.font_color}; border: 1px solid black;"
        )
        self.font_color_preview.setMaximumWidth(30)
        font_color_h.addWidget(self.font_color_preview)

        font_color_button = QPushButton("Choisir...")
        font_color_button.clicked.connect(self.choose_font_color)
        font_color_h.addWidget(font_color_button)
        font_color_h.addStretch()

        grid.addLayout(font_color_h, row, 1, 1, 2)
        row += 1

        # Type de fond
        grid.addWidget(QLabel("Fond :"), row, 0)
        bg_h = QHBoxLayout()

        self.color_radio = QRadioButton("Couleur unie")
        self.color_radio.setChecked(True)
        self.color_radio.toggled.connect(self.on_bg_type_changed)
        bg_h.addWidget(self.color_radio)

        self.image_radio = QRadioButton("Image")
        bg_h.addWidget(self.image_radio)
        bg_h.addStretch()

        grid.addLayout(bg_h, row, 1, 1, 2)
        row += 1

        # Couleur de fond (visible si Couleur unie)
        self.bg_color_label = QLabel("Couleur de fond :")
        grid.addWidget(self.bg_color_label, row, 0)

        bg_color_h = QHBoxLayout()
        self.bg_color_preview = QLabel("    ")
        self.bg_color = self.config.get("stories_bg_color", "#FFFFFF")
        self.bg_color_preview.setStyleSheet(
            f"background-color: {self.bg_color}; border: 1px solid black;"
        )
        self.bg_color_preview.setMaximumWidth(30)
        bg_color_h.addWidget(self.bg_color_preview)

        self.bg_color_button = QPushButton("Choisir...")
        self.bg_color_button.clicked.connect(self.choose_bg_color)
        bg_color_h.addWidget(self.bg_color_button)
        bg_color_h.addStretch()

        grid.addLayout(bg_color_h, row, 1, 1, 2)
        row += 1

        # Image de fond (visible si Image)
        self.bg_image_label = QLabel("Image de fond :")
        grid.addWidget(self.bg_image_label, row, 0)

        self.bg_image_edit = QLineEdit()
        self.bg_image_edit.setText(self.config.get("stories_bg_image", ""))
        grid.addWidget(self.bg_image_edit, row, 1)

        self.bg_image_button = QPushButton("Parcourir...")
        self.bg_image_button.clicked.connect(self.browse_bg_image)
        grid.addWidget(self.bg_image_button, row, 2)

        self.bg_image_label.setVisible(False)
        self.bg_image_edit.setVisible(False)
        self.bg_image_button.setVisible(False)
        row += 1

        # Transparence du voile (visible si Image)
        self.alpha_label = QLabel("Transparence du voile :")
        grid.addWidget(self.alpha_label, row, 0)

        alpha_h = QHBoxLayout()
        self.alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.alpha_slider.setMinimum(0)
        self.alpha_slider.setMaximum(100)
        self.alpha_slider.setValue(int(self.config.get("stories_alpha", 0.5) * 100))
        self.alpha_slider.valueChanged.connect(self.update_alpha_label)
        alpha_h.addWidget(self.alpha_slider)

        self.alpha_value_label = QLabel(f"{self.alpha_slider.value()}%")
        self.alpha_value_label.setMinimumWidth(40)
        alpha_h.addWidget(self.alpha_value_label)

        grid.addLayout(alpha_h, row, 1, 1, 2)

        self.alpha_label.setVisible(False)
        self.alpha_slider.setVisible(False)
        self.alpha_value_label.setVisible(False)

        grid.setColumnStretch(1, 1)
        self.layout.addLayout(grid)

    def on_bg_type_changed(self):
        """Affiche/cache les options selon le type de fond"""
        is_color = self.color_radio.isChecked()
        is_image = self.image_radio.isChecked()

        self.bg_color_label.setVisible(is_color)
        self.bg_color_preview.setVisible(is_color)
        self.bg_color_button.setVisible(is_color)

        self.bg_image_label.setVisible(is_image)
        self.bg_image_edit.setVisible(is_image)
        self.bg_image_button.setVisible(is_image)

        self.alpha_label.setVisible(is_image)
        self.alpha_slider.setVisible(is_image)
        self.alpha_value_label.setVisible(is_image)

    def choose_font_color(self):
        """Ouvre le sélecteur de couleur pour le texte"""
        current_color = QColor(self.font_color)
        color = QColorDialog.getColor(current_color, self, "Couleur de la police")
        if color.isValid():
            self.font_color = color.name()
            self.font_color_preview.setStyleSheet(
                f"background-color: {self.font_color}; border: 1px solid black;"
            )

    def choose_bg_color(self):
        """Ouvre le sélecteur de couleur pour le fond"""
        current_color = QColor(self.bg_color)
        color = QColorDialog.getColor(current_color, self, "Couleur de fond")
        if color.isValid():
            self.bg_color = color.name()
            self.bg_color_preview.setStyleSheet(
                f"background-color: {self.bg_color}; border: 1px solid black;"
            )

    def browse_bg_image(self):
        """Ouvre le dialogue pour choisir une image de fond"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une image de fond",
            "",
            "Images (*.jpg *.jpeg *.png)"
        )
        if path:
            self.bg_image_edit.setText(path)

    def update_alpha_label(self):
        """Met à jour le label du pourcentage"""
        self.alpha_value_label.setText(f"{self.alpha_slider.value()}%")

    def get_generate_stories(self) -> bool:
        # Cette checkbox est gérée dans OutputSection
        return True

    def get_stories_output_dir(self) -> str:
        # Ce champ est géré dans OutputSection
        return ""

    def get_stories_font_name(self) -> str:
        return self.font_combo.currentText()

    def get_stories_font_size(self) -> int:
        return validate_int(self.font_size_edit.text(), "Taille police Stories")

    def get_stories_font_color(self) -> str:
        return self.font_color

    def get_stories_bg_type(self) -> str:
        return "color" if self.color_radio.isChecked() else "image"

    def get_stories_bg_color(self) -> str:
        return self.bg_color

    def get_stories_bg_image(self) -> str:
        return self.bg_image_edit.text().strip()

    def get_stories_alpha(self) -> float:
        return self.alpha_slider.value() / 100.0
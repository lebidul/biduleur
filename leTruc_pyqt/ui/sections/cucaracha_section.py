#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Cucaracha - Boîte personnalisable
"""
from PyQt6.QtWidgets import (QLabel, QLineEdit, QPushButton, QRadioButton,
                             QTextEdit, QComboBox, QGridLayout, QHBoxLayout,
                             QFileDialog)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from ui.sections.base_section import BaseSection
from utils.helpers import validate_int


class CucarachaSection(BaseSection):
    """Section pour la boîte Cucaracha"""

    def __init__(self, config_manager):
        super().__init__("Boîte 'Cucaracha'", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()
        row = 0

        # Options radio
        radio_h = QHBoxLayout()
        self.none_radio = QRadioButton("Rien")
        self.none_radio.setChecked(True)
        self.none_radio.toggled.connect(self.on_type_changed)
        radio_h.addWidget(self.none_radio)

        self.text_radio = QRadioButton("Texte")
        self.text_radio.toggled.connect(self.on_type_changed)
        radio_h.addWidget(self.text_radio)

        self.image_radio = QRadioButton("Image")
        self.image_radio.toggled.connect(self.on_type_changed)
        radio_h.addWidget(self.image_radio)
        radio_h.addStretch()

        grid.addLayout(radio_h, row, 0, 1, 3)
        row += 1

        # Widgets pour texte
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(80)
        self.text_edit.setText(self.config.get("cucaracha_value", ""))
        self.text_edit.setVisible(False)
        grid.addWidget(self.text_edit, row, 0, 1, 3)
        row += 1

        # Options de police pour le texte
        font_h = QHBoxLayout()
        font_h.addWidget(QLabel("Police :"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Arial", "Helvetica", "Times New Roman", "Courier"])
        self.font_combo.setCurrentText(self.config.get("cucaracha_text_font", "Arial"))
        font_h.addWidget(self.font_combo)

        font_h.addWidget(QLabel("Taille (pt):"))
        self.font_size_edit = QLineEdit(str(self.config.get("cucaracha_font_size", 8)))
        self.font_size_edit.setMaximumWidth(50)
        font_h.addWidget(self.font_size_edit)
        font_h.addStretch()

        self.font_widget = QHBoxLayout()
        self.font_widget = font_h
        grid.addLayout(font_h, row, 0, 1, 3)
        self.hide_font_widgets()
        row += 1

        # Widgets pour image
        self.image_edit = QLineEdit()
        self.image_edit.setText(self.config.get("cucaracha_value", ""))
        self.image_edit.textChanged.connect(self.update_image_preview)
        self.image_edit.setVisible(False)
        grid.addWidget(self.image_edit, row, 0, 1, 2)

        self.image_button = QPushButton("Parcourir...")
        self.image_button.clicked.connect(self.browse_image)
        self.image_button.setVisible(False)
        grid.addWidget(self.image_button, row, 2)
        row += 1

        # Aperçu image
        self.image_preview = QLabel("Aucun aperçu")
        self.image_preview.setFrameStyle(QLabel.Shape.Box | QLabel.Shadow.Sunken)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumSize(150, 150)
        self.image_preview.setMaximumSize(150, 150)
        self.image_preview.setVisible(False)
        grid.addWidget(self.image_preview, row, 1)

        grid.setColumnStretch(0, 1)
        self.layout.addLayout(grid)

        # Appliquer le type par défaut
        cuca_type = self.config.get("cucaracha_type", "none")
        if cuca_type == "text":
            self.text_radio.setChecked(True)
        elif cuca_type == "image":
            self.image_radio.setChecked(True)
        else:
            self.none_radio.setChecked(True)

    def on_type_changed(self):
        """Change l'affichage selon le type sélectionné"""
        is_text = self.text_radio.isChecked()
        is_image = self.image_radio.isChecked()

        self.text_edit.setVisible(is_text)
        self.show_font_widgets() if is_text else self.hide_font_widgets()

        self.image_edit.setVisible(is_image)
        self.image_button.setVisible(is_image)
        self.image_preview.setVisible(is_image)

        if is_image:
            self.update_image_preview()

    def hide_font_widgets(self):
        """Cache les widgets de police"""
        for i in range(self.font_widget.count()):
            widget = self.font_widget.itemAt(i).widget()
            if widget:
                widget.setVisible(False)

    def show_font_widgets(self):
        """Affiche les widgets de police"""
        for i in range(self.font_widget.count()):
            widget = self.font_widget.itemAt(i).widget()
            if widget:
                widget.setVisible(True)

    def browse_image(self):
        """Ouvre le dialogue pour choisir une image"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une image",
            "",
            "Images (*.jpg *.jpeg *.png)"
        )
        if path:
            self.image_edit.setText(path)

    def update_image_preview(self):
        """Met à jour l'aperçu de l'image"""
        path = self.image_edit.text().strip()
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    150, 150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_preview.setPixmap(scaled)
            else:
                self.image_preview.setText("Image invalide")
        else:
            self.image_preview.clear()
            self.image_preview.setText("Aucun aperçu")

    def get_cucaracha_type(self) -> str:
        if self.text_radio.isChecked():
            return "text"
        elif self.image_radio.isChecked():
            return "image"
        return "none"

    def get_cucaracha_value(self) -> str:
        if self.text_radio.isChecked():
            return self.text_edit.toPlainText().strip()
        elif self.image_radio.isChecked():
            return self.image_edit.text().strip()
        return ""

    def get_cucaracha_font(self) -> str:
        return self.font_combo.currentText()

    def get_cucaracha_font_size(self) -> int:
        return validate_int(self.font_size_edit.text(), "Taille police Cucaracha")
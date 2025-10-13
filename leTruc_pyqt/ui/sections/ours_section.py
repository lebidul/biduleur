#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Ours - Image de fond
"""
from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton, QGridLayout, QFileDialog
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from ui.sections.base_section import BaseSection


class OursSection(BaseSection):
    """Section pour l'image de fond de l'ours"""

    def __init__(self, config_manager):
        super().__init__("Ours", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()

        grid.addWidget(QLabel("Image de fond (PNG) :"), 0, 0)
        self.ours_edit = QLineEdit()
        self.ours_edit.setText(self.config.get("ours_background_png", ""))
        self.ours_edit.textChanged.connect(self.update_preview)
        grid.addWidget(self.ours_edit, 0, 1)

        browse_button = QPushButton("Parcourir...")
        browse_button.clicked.connect(self.browse_image)
        grid.addWidget(browse_button, 0, 2)

        # Prévisualisation
        self.preview_label = QLabel("Aucun aperçu")
        self.preview_label.setFrameStyle(QLabel.Shape.Box | QLabel.Shadow.Sunken)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(150, 150)
        self.preview_label.setMaximumSize(150, 150)
        self.preview_label.setScaledContents(False)
        grid.addWidget(self.preview_label, 1, 1)

        grid.setColumnStretch(1, 1)
        self.layout.addLayout(grid)

        # Charger l'aperçu initial
        self.update_preview()

    def browse_image(self):
        """Ouvre le dialogue pour choisir une image"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Image de fond pour l'Ours (PNG)",
            "",
            "Images (*.png *.jpg *.jpeg);;Tous (*.*)"
        )
        if path:
            self.ours_edit.setText(path)

    def update_preview(self):
        """Met à jour l'aperçu de l'image"""
        path = self.ours_edit.text().strip()
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    150, 150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled)
            else:
                self.preview_label.setText("Image invalide")
        else:
            self.preview_label.clear()
            self.preview_label.setText("Aucun aperçu")

    def get_ours_image(self) -> str:
        return self.ours_edit.text().strip()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Cover - Informations de couverture
"""
import os
from PyQt6.QtWidgets import (QLabel, QLineEdit, QPushButton, QCheckBox,
                             QGridLayout, QFrame, QVBoxLayout, QHBoxLayout,
                             QFileDialog)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from ui.sections.base_section import BaseSection


class CoverSection(BaseSection):
    """Section pour les informations de couverture"""

    def __init__(self, config_manager):
        super().__init__("Informations de couverture", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()
        row = 0

        # Checkbox génération couverture
        self.generate_checkbox = QCheckBox("Avec couv' (générer la page de couverture)")
        self.generate_checkbox.setChecked(not self.config.get("skip_cover", False))
        grid.addWidget(self.generate_checkbox, row, 0, 1, 3)
        row += 1

        # Zone de drop pour l'image
        drop_frame = QFrame()
        drop_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        drop_frame.setMinimumHeight(180)
        drop_frame.setAcceptDrops(True)
        drop_frame.dragEnterEvent = self.drag_enter_event
        drop_frame.dropEvent = self.drop_event

        drop_layout = QHBoxLayout(drop_frame)

        # Partie gauche : texte + bouton
        left_widget = QFrame()
        left_layout = QVBoxLayout(left_widget)

        self.drop_label = QLabel("Glissez-déposez l'image de couverture ici")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.drop_label)

        browse_button = QPushButton("Choisir une image...")
        browse_button.clicked.connect(self.browse_image)
        left_layout.addWidget(browse_button, alignment=Qt.AlignmentFlag.AlignCenter)

        drop_layout.addWidget(left_widget)

        # Partie droite : aperçu
        self.preview_label = QLabel("Aucun aperçu")
        self.preview_label.setFrameStyle(QLabel.Shape.Box | QLabel.Shadow.Sunken)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(150, 150)
        self.preview_label.setMaximumSize(150, 150)
        drop_layout.addWidget(self.preview_label)

        grid.addWidget(drop_frame, row, 0, 1, 3)
        row += 1

        # Auteur couverture
        grid.addWidget(QLabel("Auteur Couverture :"), row, 0)
        self.auteur_edit = QLineEdit()
        self.auteur_edit.setText(self.config.get("auteur_couv", ""))
        grid.addWidget(self.auteur_edit, row, 1, 1, 2)
        row += 1

        # URL auteur
        grid.addWidget(QLabel("URL auteur couverture :"), row, 0)
        self.auteur_url_edit = QLineEdit()
        self.auteur_url_edit.setText(self.config.get("auteur_couv_url", ""))
        grid.addWidget(self.auteur_url_edit, row, 1, 1, 2)

        grid.setColumnStretch(1, 1)
        self.layout.addLayout(grid)

        # Charger l'aperçu si une image par défaut existe
        default_cover = self.config.get("cover", "")
        if default_cover:
            self.cover_path = default_cover
            self.update_display()

    def drag_enter_event(self, event):
        """Accepte le drag si c'est un fichier"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def drop_event(self, event):
        """Gère le drop de fichier"""
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        if files:
            self.set_cover_image(files[0])

    def browse_image(self):
        """Ouvre le dialogue pour choisir une image"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Image de couverture",
            "",
            "Images (*.jpg *.jpeg *.png *.tif *.webp);;Tous (*.*)"
        )
        if path:
            self.set_cover_image(path)

    def set_cover_image(self, path: str):
        """Définit l'image de couverture"""
        if os.path.exists(path):
            self.cover_path = path
            self.update_display()

    def update_display(self):
        """Met à jour l'affichage (texte + aperçu)"""
        if hasattr(self, 'cover_path') and self.cover_path:
            filename = os.path.basename(self.cover_path)
            self.drop_label.setText(f"Fichier :\n{filename}")

            pixmap = QPixmap(self.cover_path)
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
            self.drop_label.setText("Glissez-déposez l'image de couverture ici")
            self.preview_label.clear()
            self.preview_label.setText("Aucun aperçu")
            self.cover_path = ""

    def get_generate_cover(self) -> bool:
        return self.generate_checkbox.isChecked()

    def get_cover_image(self) -> str:
        return getattr(self, 'cover_path', "")

    def get_auteur(self) -> str:
        return self.auteur_edit.text().strip()

    def get_auteur_url(self) -> str:
        return self.auteur_url_edit.text().strip()
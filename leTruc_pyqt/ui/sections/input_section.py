#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section pour la sélection du fichier d'entrée
"""
import os
from PyQt6.QtWidgets import (QLabel, QPushButton, QFrame, QVBoxLayout,
                             QHBoxLayout, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.sections.base_section import BaseSection
import importlib.resources as res


class InputSection(BaseSection):
    """Section de sélection du fichier d'entrée"""

    # Signal émis quand le fichier d'entrée change
    input_file_changed = pyqtSignal(str)

    def __init__(self, config_manager):
        self.input_file = ""
        super().__init__("Fichier d'entrée", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        # Zone de drop
        drop_frame = QFrame()
        drop_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        drop_frame.setMinimumHeight(120)
        drop_frame.setAcceptDrops(True)
        drop_frame.dragEnterEvent = self.drag_enter_event
        drop_frame.dropEvent = self.drop_event

        drop_layout = QVBoxLayout(drop_frame)

        self.drop_label = QLabel("Glissez-déposez votre fichier (XLS/CSV) ici")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("font-size: 12pt;")
        drop_layout.addWidget(self.drop_label)

        or_label = QLabel("— ou —")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(or_label)

        browse_button = QPushButton("Sélectionner un fichier...")
        browse_button.clicked.connect(self.browse_file)
        drop_layout.addWidget(browse_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.layout.addWidget(drop_frame)

        # Boutons pour les modèles
        template_layout = QHBoxLayout()
        template_label = QLabel("Télécharger un modèle :")
        template_layout.addWidget(template_label)

        csv_button = QPushButton("Modèle CSV")
        csv_button.clicked.connect(lambda: self.save_template('tapage_template.csv'))
        template_layout.addWidget(csv_button)

        xlsx_button = QPushButton("Modèle XLSX")
        xlsx_button.clicked.connect(lambda: self.save_template('tapage_template.xlsx'))
        template_layout.addWidget(xlsx_button)

        template_layout.addStretch()
        self.layout.addLayout(template_layout)

    def drag_enter_event(self, event):
        """Accepte le drag si c'est un fichier"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def drop_event(self, event):
        """Gère le drop de fichier"""
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        if files:
            self.set_input_file(files[0])

    def browse_file(self):
        """Ouvre le dialogue de sélection de fichier"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner l'entrée (CSV / XLS / XLSX)",
            "",
            "Excel (*.xls *.xlsx);;CSV (*.csv);;Tous (*.*)"
        )
        if file_path:
            self.set_input_file(file_path)

    def set_input_file(self, file_path: str):
        """Définit le fichier d'entrée et met à jour l'interface"""
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "Erreur", f"Le fichier n'existe pas :\n{file_path}")
            return

        self.input_file = file_path
        filename = os.path.basename(file_path)
        self.drop_label.setText(f"Fichier sélectionné :\n{filename}")
        self.drop_label.setStyleSheet("font-size: 10pt; font-weight: bold;")

        # Émettre le signal pour que d'autres sections puissent réagir
        self.input_file_changed.emit(file_path)

    def save_template(self, template_name: str):
        """Sauvegarde un modèle embarqué"""
        ext = os.path.splitext(template_name)[1].lower()
        ftypes = "Excel (*.xlsx)" if ext == '.xlsx' else "CSV (*.csv)"

        target, _ = QFileDialog.getSaveFileName(
            self,
            f"Enregistrer le modèle {template_name}",
            template_name,
            ftypes
        )

        if not target:
            return

        try:
            data = res.files('biduleur.templates').joinpath(template_name).read_bytes()
            with open(target, "wb") as f:
                f.write(data)
            QMessageBox.information(
                self,
                "Modèle enregistré",
                f"Fichier enregistré ici :\n{target}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le modèle : {e}"
            )

    def get_input_file(self) -> str:
        """Retourne le chemin du fichier d'entrée"""
        return self.input_file
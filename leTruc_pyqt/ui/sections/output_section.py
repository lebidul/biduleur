#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section pour les fichiers de sortie
"""
from PyQt6.QtWidgets import (QLabel, QLineEdit, QPushButton, QCheckBox,
                             QGridLayout, QFileDialog)
from PyQt6.QtCore import pyqtSlot
from ui.sections.base_section import BaseSection
from utils.helpers import default_paths_from_input


class OutputSection(BaseSection):
    """Section des fichiers de sortie"""

    def __init__(self, config_manager):
        super().__init__("Fichiers de sortie", config_manager)

    def init_ui(self):
        """Crée l'interface de la section"""
        grid = QGridLayout()
        row = 0

        # HTML (biduleur)
        grid.addWidget(QLabel("HTML (biduleur) :"), row, 0)
        self.html_edit = QLineEdit()
        grid.addWidget(self.html_edit, row, 1)
        html_button = QPushButton("...")
        html_button.clicked.connect(lambda: self.browse_save_file(
            self.html_edit, "HTML", ".html", "HTML (*.html)"
        ))
        grid.addWidget(html_button, row, 2)
        row += 1

        # HTML Agenda
        grid.addWidget(QLabel("HTML Agenda :"), row, 0)
        self.agenda_html_edit = QLineEdit()
        grid.addWidget(self.agenda_html_edit, row, 1)
        agenda_button = QPushButton("...")
        agenda_button.clicked.connect(lambda: self.browse_save_file(
            self.agenda_html_edit, "HTML Agenda", ".html", "HTML (*.html)"
        ))
        grid.addWidget(agenda_button, row, 2)
        row += 1

        # PDF
        grid.addWidget(QLabel("PDF (misenpageur) :"), row, 0)
        self.pdf_edit = QLineEdit()
        grid.addWidget(self.pdf_edit, row, 1)
        pdf_button = QPushButton("...")
        pdf_button.clicked.connect(lambda: self.browse_save_file(
            self.pdf_edit, "PDF", ".pdf", "PDF (*.pdf)"
        ))
        grid.addWidget(pdf_button, row, 2)
        row += 1

        # SVG
        self.svg_checkbox = QCheckBox("Générer des SVG éditables (pour Inkscape)")
        self.svg_checkbox.setChecked(True)
        grid.addWidget(self.svg_checkbox, row, 0, 1, 3)
        row += 1

        grid.addWidget(QLabel("Dossier SVG :"), row, 0)
        self.svg_dir_edit = QLineEdit()
        grid.addWidget(self.svg_dir_edit, row, 1)
        svg_button = QPushButton("...")
        svg_button.clicked.connect(lambda: self.browse_directory(
            self.svg_dir_edit, "Dossier de sortie pour les SVG"
        ))
        grid.addWidget(svg_button, row, 2)
        row += 1

        # Stories
        self.stories_checkbox = QCheckBox("Générer les images pour les Stories Instagram")
        self.stories_checkbox.setChecked(
            self.config.get("stories_enabled", True)
        )
        grid.addWidget(self.stories_checkbox, row, 0, 1, 3)
        row += 1

        grid.addWidget(QLabel("Dossier Stories :"), row, 0)
        self.stories_dir_edit = QLineEdit()
        grid.addWidget(self.stories_dir_edit, row, 1)
        stories_button = QPushButton("...")
        stories_button.clicked.connect(lambda: self.browse_directory(
            self.stories_dir_edit, "Dossier de sortie pour les Stories"
        ))
        grid.addWidget(stories_button, row, 2)

        grid.setColumnStretch(1, 1)
        self.layout.addLayout(grid)

    def browse_save_file(self, line_edit: QLineEdit, title: str,
                         default_ext: str, file_filter: str):
        """Ouvre le dialogue pour sauvegarder un fichier"""
        path, _ = QFileDialog.getSaveFileName(
            self, title, "", file_filter
        )
        if path:
            line_edit.setText(path)

    def browse_directory(self, line_edit: QLineEdit, title: str):
        """Ouvre le dialogue pour choisir un dossier"""
        path = QFileDialog.getExistingDirectory(self, title)
        if path:
            line_edit.setText(path)

    @pyqtSlot(str)
    def update_default_paths(self, input_file: str):
        """Met à jour les chemins par défaut depuis le fichier d'entrée"""
        paths = default_paths_from_input(input_file)
        self.html_edit.setText(paths["html"])
        self.agenda_html_edit.setText(paths["agenda_html"])
        self.pdf_edit.setText(paths["pdf"])
        self.svg_dir_edit.setText(paths["svg_output_dir"])
        self.stories_dir_edit.setText(paths["stories_output"])

    def get_html_path(self) -> str:
        return self.html_edit.text().strip()

    def get_agenda_html_path(self) -> str:
        return self.agenda_html_edit.text().strip()

    def get_pdf_path(self) -> str:
        return self.pdf_edit.text().strip()

    def get_generate_svg(self) -> bool:
        return self.svg_checkbox.isChecked()

    def get_svg_dir(self) -> str:
        return self.svg_dir_edit.text().strip()

    def get_generate_stories(self) -> bool:
        return self.stories_checkbox.isChecked()

    def get_stories_dir(self) -> str:
        return self.stories_dir_edit.text().strip()
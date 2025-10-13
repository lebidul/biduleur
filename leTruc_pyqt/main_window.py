#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fenêtre principale de l'application Le Truc (PyQt6)
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QProgressBar, QCheckBox,
                             QScrollArea, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon

from ui.sections.input_section import InputSection
from ui.sections.ours_section import OursSection
from ui.sections.logos_section import LogosSection
from ui.sections.cucaracha_section import CucarachaSection
from ui.sections.cover_section import CoverSection
from ui.sections.layout_section import LayoutSection
from ui.sections.date_section import DateSection
from ui.sections.poster_section import PosterSection
from ui.sections.stories_section import StoriesSection
from ui.sections.output_section import OutputSection

from ui.dialogs.victory_dialog import VictoryDialog
from workers.pipeline_worker import PipelineWorker
from utils.config import ConfigManager
from utils.helpers import get_resource_path

try:
    from _version import __version__
except ImportError:
    __version__ = "dev"


class MainWindow(QMainWindow):
    """Fenêtre principale de l'application"""

    def __init__(self):
        super().__init__()
        self.worker = None  # Pour stocker le worker thread
        self.config_manager = ConfigManager()
        self.init_ui()

    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle(f"Le Truc v{__version__} — Crée ton Bidul à la maison - .xls/.csv → .pdf")
        self.setGeometry(100, 100, 900, 900)

        # Widget central avec scroll
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Zone scrollable
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area)

        # Conteneur scrollable
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(10)
        scroll_area.setWidget(scroll_content)

        # Créer toutes les sections
        self.input_section = InputSection(self.config_manager)
        self.ours_section = OursSection(self.config_manager)
        self.logos_section = LogosSection(self.config_manager)
        self.cucaracha_section = CucarachaSection(self.config_manager)
        self.cover_section = CoverSection(self.config_manager)
        self.layout_section = LayoutSection(self.config_manager)
        self.date_section = DateSection(self.config_manager)
        self.poster_section = PosterSection(self.config_manager)
        self.stories_section = StoriesSection(self.config_manager)
        self.output_section = OutputSection(self.config_manager)

        # Ajouter les sections au layout
        scroll_layout.addWidget(self.input_section)
        scroll_layout.addWidget(self.ours_section)
        scroll_layout.addWidget(self.logos_section)
        scroll_layout.addWidget(self.cucaracha_section)
        scroll_layout.addWidget(self.cover_section)
        scroll_layout.addWidget(self.layout_section)
        scroll_layout.addWidget(self.date_section)
        scroll_layout.addWidget(self.poster_section)
        scroll_layout.addWidget(self.stories_section)
        scroll_layout.addWidget(self.output_section)
        scroll_layout.addStretch()

        # Connecter le signal de changement de fichier d'entrée
        self.input_section.input_file_changed.connect(self.output_section.update_default_paths)

        # Barre d'action fixe en bas
        self.create_action_bar(main_layout)

    def create_action_bar(self, parent_layout):
        """Crée la barre d'action avec progression et bouton"""
        action_widget = QWidget()
        action_layout = QVBoxLayout(action_widget)
        action_layout.setContentsMargins(10, 10, 10, 10)

        # Label de statut
        self.status_label = QLabel("Prêt.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_layout.addWidget(self.status_label)

        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)

        # Checkbox debug
        self.debug_checkbox = QCheckBox("Activer le mode débogage")
        action_layout.addWidget(self.debug_checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

        # Bouton lancer
        self.run_button = QPushButton("Lancer la Génération")
        self.run_button.setMinimumHeight(40)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 12pt;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.run_button.clicked.connect(self.on_run)
        action_layout.addWidget(self.run_button)

        parent_layout.addWidget(action_widget)

    def on_run(self):
        """Lance le pipeline de génération"""
        # Validation
        input_file = self.input_section.get_input_file()
        if not input_file:
            QMessageBox.critical(self, "Erreur", "Veuillez sélectionner un fichier d'entrée.")
            return

        poster_title = self.poster_section.get_poster_title()
        if not poster_title:
            QMessageBox.critical(self, "Erreur", "Le titre du poster est obligatoire.")
            return

        # Récupérer tous les paramètres
        try:
            params = self.collect_all_parameters()
        except ValueError as e:
            QMessageBox.critical(self, "Erreur", str(e))
            return

        # Désactiver le bouton et afficher la progression
        self.run_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Démarrage du processus...")

        # Créer et démarrer le worker
        self.worker = PipelineWorker(params)
        self.worker.progress.connect(self.on_progress)
        self.worker.status.connect(self.on_status)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def collect_all_parameters(self):
        """Collecte tous les paramètres des sections"""
        params = {
            'debug_mode': self.debug_checkbox.isChecked(),
            'input_file': self.input_section.get_input_file(),

            # Ours
            'ours_background_png': self.ours_section.get_ours_image(),

            # Logos
            'logos_dir': self.logos_section.get_logos_dir(),
            'logos_layout': self.logos_section.get_logos_layout(),
            'logos_padding_mm': self.logos_section.get_logos_padding(),

            # Cucaracha
            'cucaracha_type': self.cucaracha_section.get_cucaracha_type(),
            'cucaracha_value': self.cucaracha_section.get_cucaracha_value(),
            'cucaracha_text_font': self.cucaracha_section.get_cucaracha_font(),
            'cucaracha_font_size': self.cucaracha_section.get_cucaracha_font_size(),

            # Cover
            'generate_cover': self.cover_section.get_generate_cover(),
            'cover_image': self.cover_section.get_cover_image(),
            'auteur_couv': self.cover_section.get_auteur(),
            'auteur_couv_url': self.cover_section.get_auteur_url(),

            # Layout
            'page_margin_mm': self.layout_section.get_page_margin(),
            'font_size_mode': self.layout_section.get_font_size_mode(),
            'font_size_forced': self.layout_section.get_font_size_forced(),

            # Date
            'date_separator_type': self.date_section.get_separator_type(),
            'date_spacing': self.date_section.get_date_spacing(),
            'date_box_back_color': self.date_section.get_box_back_color(),

            # Poster
            'poster_title': self.poster_section.get_poster_title(),
            'poster_design': self.poster_section.get_poster_design(),
            'font_size_safety_factor': self.poster_section.get_safety_factor(),
            'background_alpha': self.poster_section.get_background_alpha(),

            # Stories
            'generate_stories': self.stories_section.get_generate_stories(),
            'stories_output_dir': self.stories_section.get_stories_output_dir(),
            'stories_font_name': self.stories_section.get_stories_font_name(),
            'stories_font_size': self.stories_section.get_stories_font_size(),
            'stories_font_color': self.stories_section.get_stories_font_color(),
            'stories_bg_type': self.stories_section.get_stories_bg_type(),
            'stories_bg_color': self.stories_section.get_stories_bg_color(),
            'stories_bg_image': self.stories_section.get_stories_bg_image(),
            'stories_alpha': self.stories_section.get_stories_alpha(),

            # Output
            'out_html': self.output_section.get_html_path(),
            'out_agenda_html': self.output_section.get_agenda_html_path(),
            'out_pdf': self.output_section.get_pdf_path(),
            'generate_svg': self.output_section.get_generate_svg(),
            'out_svg_dir': self.output_section.get_svg_dir(),
        }

        return params

    @pyqtSlot(int, int)
    def on_progress(self, current, total):
        """Met à jour la barre de progression"""
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)

    @pyqtSlot(str)
    def on_status(self, message):
        """Met à jour le message de statut"""
        self.status_label.setText(message)

    @pyqtSlot(str)
    def on_finished(self, summary):
        """Appelé quand le pipeline est terminé avec succès"""
        self.run_button.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText("Terminé avec succès.")

        # Afficher le dialogue de victoire
        dialog = VictoryDialog(summary, self)
        dialog.exec()

        # Demander si on veut ouvrir le PDF
        pdf_path = self.output_section.get_pdf_path()
        if pdf_path:
            reply = QMessageBox.question(
                self,
                "Ouvrir le PDF ?",
                "Voulez-vous ouvrir le PDF généré ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                from utils.helpers import open_file
                open_file(pdf_path)

    @pyqtSlot(str)
    def on_error(self, error_message):
        """Appelé en cas d'erreur"""
        self.run_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Échec.")
        QMessageBox.critical(self, "Erreur", error_message)
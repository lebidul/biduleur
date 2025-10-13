#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialogue de victoire affiché après génération réussie
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTextEdit,
                             QPushButton, QDialogButtonBox)
from PyQt6.QtCore import Qt


class VictoryDialog(QDialog):
    """Dialogue affichant le résumé de la génération réussie"""

    def __init__(self, summary_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✨ Génération réussie !")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.init_ui(summary_text)

    def init_ui(self, summary_text: str):
        """Crée l'interface du dialogue"""
        layout = QVBoxLayout()

        # Titre de succès
        title_label = QLabel("🎉 Votre Bidul a été généré avec succès !")
        title_label.setStyleSheet("""
            font-size: 16pt;
            font-weight: bold;
            color: #4CAF50;
            padding: 10px;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Zone de texte pour le résumé
        summary_edit = QTextEdit()
        summary_edit.setPlainText(summary_text)
        summary_edit.setReadOnly(True)
        summary_edit.setStyleSheet("""
            QTextEdit {
                font-family: 'Courier New', monospace;
                font-size: 10pt;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                padding: 10px;
            }
        """)
        layout.addWidget(summary_edit)

        # Bouton OK
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)
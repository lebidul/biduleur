#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de vérification de la migration Tkinter → PyQt6
Compare les fonctionnalités entre les deux versions
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Set


class MigrationChecker:
    """Vérifie que toutes les fonctionnalités Tkinter ont été migrées"""

    def __init__(self, tkinter_path: str = "leTruc", pyqt_path: str = "leTruc_pyqt"):
        self.tkinter_path = tkinter_path
        self.pyqt_path = pyqt_path
        self.results = {
            "sections": {},
            "widgets": {},
            "callbacks": {},
            "features": {}
        }

    def extract_sections_tkinter(self) -> Set[str]:
        """Extrait les sections depuis widgets.py Tkinter"""
        widgets_file = os.path.join(self.tkinter_path, "widgets.py")
        sections = set()

        if os.path.exists(widgets_file):
            with open(widgets_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Chercher les fonctions _create_*_section
                pattern = r'def _create_(\w+)_section\('
                matches = re.findall(pattern, content)
                sections.update(matches)

        return sections

    def extract_sections_pyqt(self) -> Set[str]:
        """Extrait les sections depuis PyQt6"""
        sections_dir = os.path.join(self.pyqt_path, "ui", "sections")
        sections = set()

        if os.path.exists(sections_dir):
            for file in os.listdir(sections_dir):
                if file.endswith("_section.py") and file != "base_section.py":
                    # Extraire le nom : input_section.py -> input
                    section_name = file.replace("_section.py", "")
                    sections.add(section_name)

        return sections

    def check_sections(self) -> Dict[str, bool]:
        """Vérifie que toutes les sections ont été migrées"""
        print("🔍 Vérification des sections...")

        tkinter_sections = self.extract_sections_tkinter()
        pyqt_sections = self.extract_sections_pyqt()

        results = {}
        for section in tkinter_sections:
            migrated = section in pyqt_sections
            results[section] = migrated
            status = "✅" if migrated else "❌"
            print(f"   {status} {section}_section")

        # Vérifier les nouvelles sections PyQt6
        new_sections = pyqt_sections - tkinter_sections
        if new_sections:
            print(f"\n   ℹ️  Nouvelles sections dans PyQt6: {', '.join(new_sections)}")

        self.results["sections"] = results
        return results

    def check_features(self) -> Dict[str, bool]:
        """Vérifie les fonctionnalités clés"""
        print("\n🔍 Vérification des fonctionnalités...")

        features = {
            "drag_and_drop": False,
            "image_preview": False,
            "color_picker": False,
            "progress_bar": False,
            "threading": False,
            "victory_dialog": False,
            "config_manager": False,
        }

        # Vérifier dans les fichiers PyQt6
        files_to_check = {
            "drag_and_drop": ["ui/sections/input_section.py", "ui/sections/cover_section.py"],
            "image_preview": ["ui/sections/ours_section.py", "ui/sections/cover_section.py"],
            "color_picker": ["ui/sections/date_section.py", "ui/sections/stories_section.py"],
            "progress_bar": ["main_window.py"],
            "threading": ["workers/pipeline_worker.py"],
            "victory_dialog": ["ui/dialogs/victory_dialog.py"],
            "config_manager": ["utils/config.py"],
        }

        for feature, files in files_to_check.items():
            for file in files:
                file_path = os.path.join(self.pyqt_path, file)
                if os.path.exists(file_path):
                    features[feature] = True
                    break

        for feature, present in features.items():
            status = "✅" if present else "❌"
            feature_name = feature.replace("_", " ").title()
            print(f"   {status} {feature_name}")

        self.results["features"] = features
        return features

    def check_file_structure(self) -> Dict[str, bool]:
        """Vérifie la structure de fichiers"""
        print("\n🔍 Vérification de la structure de fichiers...")

        required_files = {
            "main.py": False,
            "main_window.py": False,
            "utils/__init__.py": False,
            "utils/helpers.py": False,
            "utils/config.py": False,
            "workers/__init__.py": False,
            "workers/pipeline_worker.py": False,
            "ui/__init__.py": False,
            "ui/sections/__init__.py": False,
            "ui/dialogs/__init__.py": False,
        }

        for file in required_files.keys():
            file_path = os.path.join(self.pyqt_path, file)
            required_files[file] = os.path.exists(file_path)

        for file, exists in required_files.items():
            status = "✅" if exists else "❌"
            print(f"   {status} {file}")

        return required_files

    def check_dependencies(self) -> Dict[str, bool]:
        """Vérifie les dépendances Python"""
        print("\n🔍 Vérification des dépendances...")

        dependencies = {
            "PyQt6": False,
            "PyYAML": False,
            "Pillow": False,
            "reportlab": False,
        }

        for dep in dependencies.keys():
            try:
                __import__(dep)
                dependencies[dep] = True
            except ImportError:
                dependencies[dep] = False

        for dep, installed in dependencies.items():
            status = "✅" if installed else "❌"
            print(f"   {status} {dep}")

        return dependencies

    def compare_widget_counts(self) -> Dict[str, int]:
        """Compare le nombre de widgets entre Tkinter et PyQt6"""
        print("\n📊 Comparaison des widgets...")

        # Compter dans widgets.py (Tkinter)
        tkinter_widgets = 0
        widgets_file = os.path.join(self.tkinter_path, "widgets.py")
        if os.path.exists(widgets_file):
            with open(widgets_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Compter les créations de widgets
                patterns = [
                    r'tk\.Entry\(',
                    r'tk\.Label\(',
                    r'tk\.Button\(',
                    r'tk\.Checkbutton\(',
                    r'tk\.Radiobutton\(',
                    r'ttk\.\w+\(',
                ]
                for pattern in patterns:
                    tkinter_widgets += len(re.findall(pattern, content))

        # Compter dans les sections PyQt6
        pyqt_widgets = 0
        sections_dir = os.path.join(self.pyqt_path, "ui", "sections")
        if os.path.exists(sections_dir):
            for file in Path(sections_dir).glob("*.py"):
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    patterns = [
                        r'QLineEdit\(',
                        r'QLabel\(',
                        r'QPushButton\(',
                        r'QCheckBox\(',
                        r'QRadioButton\(',
                        r'QComboBox\(',
                    ]
                    for pattern in patterns:
                        pyqt_widgets += len(re.findall(pattern, content))

        print(f"   Tkinter : ~{tkinter_widgets} widgets")
        print(f"   PyQt6   : ~{pyqt_widgets} widgets")

        return {"tkinter": tkinter_widgets, "pyqt": pyqt_widgets}

    def generate_report(self):
        """Génère un rapport complet"""
        print("\n" + "=" * 70)
        print("   RAPPORT DE MIGRATION TKINTER → PYQT6")
        print("=" * 70)

        # Résumé des sections
        sections = self.results.get("sections", {})
        if sections:
            total_sections = len(sections)
            migrated_sections = sum(sections.values())
            print(f"\n📋 Sections : {migrated_sections}/{total_sections} migrées")

            missing = [name for name, migrated in sections.items() if not migrated]
            if missing:
                print(f"   ⚠️  Sections manquantes : {', '.join(missing)}")

        # Résumé des fonctionnalités
        features = self.results.get("features", {})
        if features:
            total_features = len(features)
            present_features = sum(features.values())
            print(f"\n✨ Fonctionnalités : {present_features}/{total_features} présentes")

            missing = [name for name, present in features.items() if not present]
            if missing:
                print(f"   ⚠️  Fonctionnalités manquantes : {', '.join(missing)}")

        # Score global
        all_checks = list(sections.values()) + list(features.values())
        if all_checks:
            score = (sum(all_checks) / len(all_checks)) * 100
            print(f"\n🎯 Score global : {score:.1f}%")

            if score == 100:
                print("\n   🎉 Migration complète ! Tous les éléments sont présents.")
            elif score >= 80:
                print("\n   ✅ Migration presque complète. Quelques ajustements nécessaires.")
            elif score >= 60:
                print("\n   ⚠️  Migration partielle. Plusieurs éléments manquants.")
            else:
                print("\n   ❌ Migration incomplète. Travail important restant.")

        print("\n" + "=" * 70)

    def run_all_checks(self):
        """Exécute toutes les vérifications"""
        print("\n" + "=" * 70)
        print("   VÉRIFICATION DE LA MIGRATION TKINTER → PYQT6")
        print("=" * 70 + "\n")

        # Vérifier l'existence des dossiers
        if not os.path.exists(self.pyqt_path):
            print(f"❌ Le dossier PyQt6 n'existe pas : {self.pyqt_path}")
            print("   Lancez d'abord setup_pyqt_structure.py")
            # return

        if not os.path.exists(self.tkinter_path):
            print(f"⚠️  Le dossier Tkinter n'existe pas : {self.tkinter_path}")
            print("   Comparaison avec Tkinter ignorée.")

        # Exécuter les vérifications
        self.check_sections()
        self.check_features()
        self.check_file_structure()
        self.check_dependencies()
        self.compare_widget_counts()

        # Générer le rapport
        self.generate_report()


def main():
    """Fonction principale"""
    import sys

    tkinter_path = "../leTruc"
    pyqt_path = ""

    # Permettre de spécifier les chemins en argument
    if len(sys.argv) > 1:
        tkinter_path = sys.argv[1]
    if len(sys.argv) > 2:
        pyqt_path = sys.argv[2]

    checker = MigrationChecker(tkinter_path, pyqt_path)
    checker.run_all_checks()

    print("\n💡 Pour tester l'application PyQt6 :")
    print(f"   cd {pyqt_path}")
    print("   python main.py")
    print("\n💡 Pour lancer les tests :")
    print(f"   python {pyqt_path}/test_gui.py")


if __name__ == "__main__":
    main()
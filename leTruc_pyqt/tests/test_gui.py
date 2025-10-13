#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests basiques pour l'interface PyQt6
"""
import sys
import os

# Ajouter le chemin parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt


def test_imports():
    """Teste que tous les imports fonctionnent"""
    print("🧪 Test des imports...")

    try:
        from main_window import MainWindow
        from utils.config import ConfigManager
        from utils.helpers import validate_float, validate_int
        from workers.pipeline_worker import PipelineWorker
        from ui.sections.input_section import InputSection
        from ui.dialogs.victory_dialog import VictoryDialog
        print("   ✅ Tous les imports fonctionnent")
        return True
    except ImportError as e:
        print(f"   ❌ Erreur d'import : {e}")
        return False


def test_config_manager():
    """Teste le gestionnaire de configuration"""
    print("\n🧪 Test du ConfigManager...")

    try:
        from utils.config import ConfigManager
        config = ConfigManager()

        # Vérifier quelques valeurs par défaut
        assert "page_margin_mm" in config.defaults
        assert "poster_title" in config.defaults
        assert isinstance(config.get("page_margin_mm"), (int, float))

        print("   ✅ ConfigManager fonctionne")
        return True
    except Exception as e:
        print(f"   ❌ Erreur ConfigManager : {e}")
        return False


def test_validation_functions():
    """Teste les fonctions de validation"""
    print("\n🧪 Test des fonctions de validation...")

    try:
        from utils.helpers import validate_float, validate_int

        # Tests de validate_float
        assert validate_float("1.5", "test") == 1.5
        assert validate_float("1,5", "test") == 1.5
        assert validate_float("10", "test") == 10.0

        # Tests de validate_int
        assert validate_int("42", "test") == 42
        assert validate_int("  100  ", "test") == 100

        # Test d'erreur
        try:
            validate_float("abc", "test")
            assert False, "Devrait lever ValueError"
        except ValueError:
            pass

        print("   ✅ Validation fonctionne")
        return True
    except Exception as e:
        print(f"   ❌ Erreur validation : {e}")
        return False


def test_main_window_creation():
    """Teste la création de la fenêtre principale"""
    print("\n🧪 Test de création de MainWindow...")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from main_window import MainWindow
        window = MainWindow()

        # Vérifier que tous les widgets existent
        assert hasattr(window, 'input_section')
        assert hasattr(window, 'ours_section')
        assert hasattr(window, 'logos_section')
        assert hasattr(window, 'output_section')
        assert hasattr(window, 'run_button')
        assert hasattr(window, 'progress_bar')

        print("   ✅ MainWindow créé avec succès")
        window.close()
        return True
    except Exception as e:
        print(f"   ❌ Erreur création MainWindow : {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sections_creation():
    """Teste la création de toutes les sections"""
    print("\n🧪 Test de création des sections...")

    try:
        from utils.config import ConfigManager
        from ui.sections.input_section import InputSection
        from ui.sections.ours_section import OursSection
        from ui.sections.logos_section import LogosSection
        from ui.sections.output_section import OutputSection

        config = ConfigManager()

        # Créer chaque section
        sections = {
            "InputSection": InputSection(config),
            "OursSection": OursSection(config),
            "LogosSection": LogosSection(config),
            "OutputSection": OutputSection(config),
        }

        for name, section in sections.items():
            assert section is not None
            assert hasattr(section, 'layout')
            print(f"      ✅ {name}")

        print("   ✅ Toutes les sections créées")
        return True
    except Exception as e:
        print(f"   ❌ Erreur création sections : {e}")
        import traceback
        traceback.print_exc()
        return False


def test_victory_dialog():
    """Teste le dialogue de victoire"""
    print("\n🧪 Test du VictoryDialog...")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from ui.dialogs.victory_dialog import VictoryDialog

        summary = "Test résumé\nLigne 2\nLigne 3"
        dialog = VictoryDialog(summary)

        assert dialog.windowTitle() == "✨ Génération réussie !"

        print("   ✅ VictoryDialog créé avec succès")
        dialog.close()
        return True
    except Exception as e:
        print(f"   ❌ Erreur VictoryDialog : {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Exécute tous les tests"""
    print("\n" + "=" * 60)
    print("   Tests de l'interface PyQt6 - Le Truc")
    print("=" * 60 + "\n")

    tests = [
        ("Imports", test_imports),
        ("ConfigManager", test_config_manager),
        ("Validation", test_validation_functions),
        ("MainWindow", test_main_window_creation),
        ("Sections", test_sections_creation),
        ("VictoryDialog", test_victory_dialog),
    ]

    results = []
    for name, test_func in tests:
        try:
            results.append(test_func())
        except Exception as e:
            print(f"\n❌ Erreur inattendue dans {name}: {e}")
            results.append(False)

    # Résumé
    print("\n" + "=" * 60)
    print("   RÉSUMÉ DES TESTS")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    for (name, _), result in zip(tests, results):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {name}")

    print(f"\n   {passed}/{total} tests réussis")

    if passed == total:
        print("\n   🎉 Tous les tests sont passés !")
        return 0
    else:
        print(f"\n   ⚠️  {total - passed} test(s) échoué(s)")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
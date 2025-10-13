#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'installation automatique pour Le Truc PyQt6
"""
import subprocess
import sys
import os


def check_python_version():
    """Vérifie la version de Python"""
    print("🐍 Vérification de la version Python...")
    version = sys.version_info

    if version < (3, 10):
        print(f"❌ Python 3.10+ requis, vous avez {version.major}.{version.minor}")
        print("   Veuillez mettre à jour Python : https://www.python.org/downloads/")
        return False

    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_pip():
    """Vérifie que pip est installé"""
    print("\n📦 Vérification de pip...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
            return True
        else:
            print("❌ pip n'est pas installé")
            return False
    except Exception as e:
        print(f"❌ Erreur lors de la vérification de pip : {e}")
        return False


def upgrade_pip():
    """Met à jour pip"""
    print("\n⬆️  Mise à jour de pip...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            check=True
        )
        print("✅ pip mis à jour")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Impossible de mettre à jour pip : {e}")
        return False


def install_requirements(dev=False):
    """Installe les dépendances"""
    req_file = "requirements-dev.txt" if dev else "requirements.txt"

    if not os.path.exists(req_file):
        print(f"❌ Fichier {req_file} introuvable")
        return False

    print(f"\n📥 Installation des dépendances depuis {req_file}...")
    print("   Cela peut prendre quelques minutes...\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_file],
            check=True
        )
        print(f"\n✅ Dépendances installées depuis {req_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erreur lors de l'installation : {e}")
        return False


def test_imports():
    """Teste les imports principaux"""
    print("\n🧪 Test des imports...")

    tests = [
        ("PyQt6", "PyQt6.QtWidgets"),
        ("PyYAML", "yaml"),
        ("Pillow", "PIL"),
        ("reportlab", "reportlab"),
    ]

    all_ok = True
    for name, module in tests:
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} (non installé)")
            all_ok = False

    return all_ok


def create_venv():
    """Propose de créer un environnement virtuel"""
    if os.path.exists("venv") or os.path.exists(".venv"):
        print("\n✅ Un environnement virtuel existe déjà")
        return True

    print("\n💡 Aucun environnement virtuel détecté")
    response = input("   Voulez-vous en créer un ? (recommandé) [O/n] : ").strip().lower()

    if response in ['', 'o', 'oui', 'y', 'yes']:
        print("\n🔨 Création de l'environnement virtuel...")
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            print("✅ Environnement virtuel créé : venv/")
            print("\n📝 Pour l'activer :")
            if sys.platform == "win32":
                print("   Windows : venv\\Scripts\\activate")
            else:
                print("   Linux/Mac : source venv/bin/activate")
            print("\n⚠️  Veuillez activer l'environnement et relancer ce script")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur lors de la création : {e}")
            return False

    return True


def main():
    """Fonction principale"""
    print("=" * 70)
    print("   Installation de Le Truc PyQt6")
    print("=" * 70)

    # Étape 1 : Vérifier Python
    if not check_python_version():
        sys.exit(1)

    # Étape 2 : Vérifier pip
    if not check_pip():
        sys.exit(1)

    # Étape 3 : Proposer un venv
    if not create_venv():
        sys.exit(0)

    # Étape 4 : Mettre à jour pip
    upgrade_pip()

    # Étape 5 : Choisir le type d'installation
    print("\n📦 Type d'installation :")
    print("   1. Standard (utilisateur)")
    print("   2. Développement (avec outils de dev)")

    choice = input("\nVotre choix [1] : ").strip() or "1"
    dev_mode = (choice == "2")

    # Étape 6 : Installer les dépendances
    if not install_requirements(dev=dev_mode):
        sys.exit(1)

    # Étape 7 : Tester les imports
    if not test_imports():
        print("\n⚠️  Certaines dépendances n'ont pas pu être importées")
        print("   Essayez de réinstaller : pip install -r requirements.txt")
        sys.exit(1)

    # Succès !
    print("\n" + "=" * 70)
    print("   ✨ Installation terminée avec succès !")
    print("=" * 70)
    print("\n🚀 Prochaines étapes :")
    print("   1. Vérifier la structure : python tools/check_migration.py")
    print("   2. Lancer les tests : python tests/test_gui.py")
    print("   3. Lancer l'application : python main.py")
    print("\n📚 Documentation : docs/README.md")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Installation interrompue par l'utilisateur")
        sys.exit(1)
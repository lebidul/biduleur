
# Module Biduleur
Biduleur est un outil pour générer des événements à partir de fichiers CSV.

---
## Table des matières
1. [Prérequis](#prérequis)
2. [Structure du projet](#structure-du-projet)
3. [Installation](#installation)
4. [Création du build](#création-du-build)
   - [Sur Windows](#sur-windows)
   - [Sur Linux](#sur-linux)
5. [Utilisation](#utilisation)
6. [Création d'une release](#création-dune-release)
   - [Manuellement](#manuellement)
   - [Automatiquement avec GitHub Actions](#automatiquement-avec-github-actions)
   - [Déclenchement manuel via GitHub Actions](#déclenchement-manuel-via-github-actions)
7. [Dépannage](#dépannage)
8. [Fichiers de configuration](#fichiers-de-configuration)
   - [biduleur.spec](#biduleurspec)
   - [build.bat](#buildbat)
   - [build.sh](#buildsh)
   - [release.sh](#releasesh)
9. [GitHub Actions](#github-actions)
10. [Contribuer](#contribuer)
11. [Licence](#licence)

---
## Prérequis
- Python 3.9 ou supérieur
- Pip (généralement installé avec Python)
- Git (optionnel, pour cloner le dépôt)
- UPX (optionnel, pour compresser l'exécutable)

---
## Structure du projet
```
bidul.biduleur/
├── biduleur/               # Package Python
│   ├── __init__.py         # Fichier vide obligatoire
│   ├── main.py             # Point d'entrée
│   ├── csv_utils.py
│   ├── format_utils.py
│   ├── constants.py
│   ├── event_utils.py
├── biduleur.ico            # Icône de l'application
├── biduleur.spec           # Fichier de configuration PyInstaller
├── build.bat               # Script de build pour Windows
├── build.sh                # Script de build pour Linux
├── release.sh              # Script pour créer une release
├── requirements.txt        # Dépendances Python
├── .gitignore              # Fichiers à ignorer
├── build/                  # (généré par PyInstaller)
└── dist/                   # (généré par PyInstaller)
```

---
## Installation
1. Clone le dépôt (si nécessaire) :
   ```bash
   git clone https://github.com/lebidul/biduleur.git
   cd biduleur
   ```

2. Crée un environnement virtuel (recommandé) :
   ```bash
   python -m venv .venv
   ```

3. Active l'environnement virtuel :
   - **Windows** :
     ```cmd
     .\.venv\Scripts\activate
     ```
   - **Linux/macOS** :
     ```bash
     source .venv/bin/activate
     ```

4. Installe les dépendances :
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

---
## Création du build
### Sur Windows
1. Double-clique sur `build.bat` ou exécute-le depuis l'invite de commandes :
   ```cmd
   .\build.bat
   ```
2. Le build sera généré dans `dist\biduleur\biduleur.exe`

### Sur Linux
1. Rends le script exécutable :
   ```bash
   chmod +x build.sh
   ```
2. Exécute le script :
   ```bash
   ./build.sh
   ```
3. Le build sera généré dans `dist/biduleur/biduleur`

---
## Utilisation
Après le build, exécute l'application :
- **Windows** :
  ```cmd
  dist\biduleur\biduleur.exe
  ```
- **Linux** :
  ```bash
  dist/biduleur/biduleur
  ```

---
## Création d'une release
### Manuellement
1. Crée un tag :
   ```bash
   git tag -a v1.0.0 -m "Version 1.0.0 - Première version stable"
   git push origin v1.0.0
   ```
2. Va sur [GitHub Releases](https://github.com/lebidul/biduleur/releases)
3. Clique sur "Draft a new release"
4. Sélectionne le tag `v1.0.0`
5. Ajoute une description et attache l'exécutable depuis `dist/biduleur/`
6. Publie la release

### Automatiquement avec GitHub Actions
1. Exécute le script de release :
   ```bash
   ./release.sh 1.0.0
   ```
2. GitHub Actions va automatiquement :
   - Builder l'application
   - Créer une release
   - Attacher l'exécutable

### Déclenchement manuel via GitHub Actions
Tu peux aussi déclencher manuellement le workflow GitHub Actions pour générer les binaires sans uploader manuellement :

1. Va dans l'onglet **"Actions"** de ton dépôt GitHub
2. Sélectionne le workflow **"Build and Release"** dans la liste à gauche
3. Clique sur **"Run workflow"** (bouton dropdown)
4. Saisis le numéro de version (ex: `1.0.0`)
5. Clique sur **"Run workflow"**
6. Une fois le workflow terminé :
   - Télécharge l'artifact généré depuis la section "Artifacts" en bas de la page du run
   - Crée une release manuellement et attache le fichier téléchargé

---
## Dépannage
### Problèmes courants
1. **L'exécutable ne se lance pas** :
   - Active le mode console dans `biduleur.spec` (`console=True`)
   - Vérifie les dépendances : `pip install -r requirements.txt`
   - Nettoie les anciens builds : `rm -rf build/ dist/`

2. **Erreurs de chemins** :
   - Vérifie la structure du projet
   - Utilise `os.path` pour les chemins dans ton code

3. **Build échoué** :
   - Exécute avec plus de détails : `pyinstaller biduleur.spec --clean --debug=all`
   - Consulte les logs dans `build/`

4. **Erreur avec GitHub Actions "deprecated version of actions/upload-artifact: v3"** :
   - Mets à jour ton fichier `.github/workflows/release.yml` en utilisant les versions actuelles des actions (voir section [GitHub Actions](#github-actions))

---
## Fichiers de configuration
### biduleur.spec
```python
# biduleur.spec
from PyInstaller.utils.hooks import collect_submodules
import os
import sys

# Solution pour obtenir le chemin du dossier parent
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    current_dir = os.getcwd()

# Chemins
main_script = os.path.join(current_dir, 'biduleur', 'main.py')
icon_path = os.path.join(current_dir, 'biduleur.ico')

# Vérifications
if not os.path.exists(main_script):
    raise FileNotFoundError(f"Fichier {main_script} introuvable")

# Configuration
hidden_imports = collect_submodules('tkinter') + [
    'biduleur.csv_utils',
    'biduleur.format_utils',
    'biduleur.constants',
    'biduleur.event_utils',
    'pkg_resources.py2_warn',
]

a = Analysis(
    [main_script],
    pathex=[current_dir],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='biduleur',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    icon=icon_path if os.path.exists(icon_path) else None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='biduleur'
)
```

### build.bat
```batch
@echo off
cd /d "%~dp0"

:: Nettoyage
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

:: Vérifications
echo Vérification de la structure :
dir /b
if not exist "biduleur\main.py" (
    echo ERREUR: biduleur\main.py introuvable
    exit /b 1
)

:: Build
echo Création du build...
python -m PyInstaller biduleur.spec --clean --workpath=build --distpath=dist

:: Vérification
if exist "dist\biduleur\biduleur.exe" (
    echo Build réussi !
    dir dist\biduleur\
) else (
    echo ERREUR: Build échoué
    exit /b 1
)
```

### build.sh
```bash
#!/bin/bash
cd "$(dirname "$0")" || exit 1

# Nettoyage
echo "Nettoyage des anciens builds..."
rm -rf build 2>/dev/null
rm -rf dist 2>/dev/null

# Vérifications
echo "Vérification de la structure :"
ls -l
if [ ! -d "biduleur" ]; then
    echo "ERREUR: Dossier biduleur/ introuvable"
    exit 1
fi
if [ ! -f "biduleur/main.py" ]; then
    echo "ERREUR: biduleur/main.py introuvable"
    exit 1
fi

# Build
echo "Création du build..."
python -m PyInstaller biduleur.spec --clean --workpath=build --distpath=dist

# Vérification
if [ -f "dist/biduleur/biduleur" ]; then
    echo "Build réussi !"
    ls -l dist/biduleur/
else
    echo "ERREUR: Build échoué"
    exit 1
fi
```

### release.sh
```bash
#!/bin/bash

# Vérification du numéro de version
if [ -z "$1" ]; then
    echo "Usage: $0 <version> (ex: 1.0.0)"
    exit 1
fi

VERSION="v$1"

# Vérification git
if ! git diff-index --quiet HEAD; then
    echo "ERREUR: Modifications non commitées. Commit avant de créer une release."
    exit 1
fi

# Création du tag
git tag -a "$VERSION" -m "Version $VERSION"
git push origin "$VERSION"

echo "Release $VERSION créée. GitHub Actions va builder et publier automatiquement."
```

---
## GitHub Actions
Crée un fichier `.github/workflows/release.yml` avec les versions actuelles des actions :

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'  # Déclenche automatiquement quand un tag est poussé
  workflow_dispatch:  # Permet de déclencher manuellement
    inputs:
      version:
        description: 'Numéro de version (ex: 1.0.0)'
        required: true
        default: '1.0.0'

jobs:
  build:
    runs-on: windows-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v4  # Version actuelle

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller

    - name: Build executable
      run: |
        pyinstaller biduleur.spec --clean --workpath=build --distpath=dist

    - name: Prepare release assets
      run: |
        mkdir release_assets
        copy dist\biduleur\biduleur.exe release_assets\biduleur-${{ github.event.inputs.version || github.ref_name }}-windows.exe

    - name: Create Release (automatic)
      if: startsWith(github.ref, 'refs/tags/')
      uses: softprops/action-gh-release@v1
      with:
        name: Biduleur ${{ github.ref_name }}
        files: release_assets/*
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

    - name: Upload artifact for manual release
      if: github.event_name == 'workflow_dispatch'
      uses: actions/upload-artifact@v4  # Version actuelle
      with:
        name: biduleur-${{ github.event.inputs.version || 'manual' }}-windows
        path: release_assets/*
```

---
## Contribuer
1. Fork le projet
2. Crée une branche (`git checkout -b feature/ma-fonctionnalité`)
3. Commit tes changements (`git commit -am 'Ajout fonctionnalité'`)
4. Pousse la branche (`git push origin feature/ma-fonctionnalité`)
5. Ouvre une Pull Request

---
## Licence
[MIT](LICENSE)
```

J'ai ajouté :
1. Une nouvelle section "Déclenchement manuel via GitHub Actions" qui explique comment utiliser le workflow manuellement
2. Une entrée dans la section "Dépannage" pour l'erreur spécifique aux versions obsolètes des actions
3. Mis à jour la section GitHub Actions avec les versions actuelles des actions (v4)
4. Ajouté des explications sur comment récupérer l'artifact après un déclenchement manuel

Ce README est maintenant complet et à jour avec toutes les informations nécessaires pour utiliser GitHub Actions de manière optimale. 🚀
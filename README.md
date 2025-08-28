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
   - [Configuration requise](#configuration-requise)
   - [Workflow détaillé](#workflow-détaillé)
10. [Contribuer](#contribuer)
11. [Licence](#licence)

---
## Prérequis
- Python 3.9 ou supérieur
- Pip (généralement installé avec Python)
- Git (optionnel, pour cloner le dépôt)
- UPX (optionnel, pour compresser l'exécutable)
- **Permissions GitHub** : Assurez-vous que votre dépôt a les permissions "Read and write" pour les GitHub Actions (Settings > Actions > General > Workflow permissions)

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
├── .github/                # Configuration GitHub Actions
│   └── workflows/
│       └── release.yml     # Workflow de release
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
   Ce script va :
   - Créer un tag Git
   - Pousser le tag sur GitHub
   - Déclencher automatiquement le workflow GitHub Actions qui va :
     - Builder l'application
     - Créer une release dans l'espace GitHub Releases
     - Attacher automatiquement l'exécutable à la release

### Déclenchement manuel via GitHub Actions
Vous pouvez aussi déclencher manuellement le workflow GitHub Actions pour générer et publier une release :

1. Va dans l'onglet **"Actions"** de ton dépôt GitHub
2. Sélectionne le workflow **"Build and Release"** dans la liste à gauche
3. Clique sur **"Run workflow"** (bouton dropdown)
4. Configure les paramètres :
   - **Version** : Numéro de version (ex: `1.0.0`)
   - **Publier la release ?** : `true` (pour publier) ou `false` (pour juste builder)
5. Clique sur **"Run workflow"**

Le workflow va :
- Builder l'application
- Créer un tag (si nécessaire)
- Publier une release dans l'espace GitHub Releases avec l'exécutable attaché
- Générer automatiquement des notes de release basées sur les commits

**Avantages de cette méthode** :
- Pas besoin d'uploader manuellement les binaires
- Tout est géré automatiquement dans un environnement propre
- Historique clair des releases dans l'onglet dédié

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
   - Le workflow fourni utilise déjà les versions actuelles des actions (v4)

5. **Erreur 403 lors de la création de release** :
   - Vérifiez que les permissions du dépôt sont correctement configurées (Settings > Actions > General > Workflow permissions : "Read and write permissions")
   - Assurez-vous que le tag n'existe pas déjà

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
### Configuration requise
Pour que le workflow de release fonctionne correctement :
1. Assurez-vous que les permissions sont configurées :
   - Allez dans **Settings > Actions > General**
   - Sélectionnez **"Read and write permissions"** pour les workflows
2. Aucune configuration supplémentaire n'est nécessaire (le token GITHUB_TOKEN est automatiquement fourni)

### Workflow détaillé
Le fichier `.github/workflows/release.yml` gère :
- Le build de l'application
- La création de releases automatiques
- La gestion des tags
- La publication des exécutables

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
      publish_release:
        description: 'Publier la release ?'
        required: true
        default: 'true'
        type: choice
        options:
        - 'true'
        - 'false'

jobs:
  build:
    runs-on: windows-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      with:
        fetch-depth: 0  # Nécessaire pour manipuler les tags

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9.13'  # Doit correspondre à la version utilisée localement

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller

    - name: Build executable
      run: |
        pyinstaller biduleur.spec --clean --onefile --workpath=build --distpath=dist

    - name: Prepare release assets
      run: |
        mkdir release_assets
        copy dist\biduleur.exe release_assets\biduleur-${{ github.event.inputs.version || github.ref_name }}-windows.exe

    - name: Delete existing tag (if it exists)
      if: github.event_name == 'workflow_dispatch' && github.event.inputs.publish_release == 'true'
      run: |
        git push origin :refs/tags/v${{ github.event.inputs.version }} || true

    - name: Create new tag (for manual dispatch)
      if: github.event_name == 'workflow_dispatch' && github.event.inputs.publish_release == 'true'
      run: |
        git tag -a v${{ github.event.inputs.version }} -m "Release v${{ github.event.inputs.version }}"
        git push origin v${{ github.event.inputs.version }}

    - name: Create Release
      if: github.event.inputs.publish_release == 'true' && (github.event_name == 'workflow_dispatch' || startsWith(github.ref, 'refs/tags/'))
      uses: softprops/action-gh-release@v1
      with:
        name: Biduleur ${{ github.event.inputs.version || github.ref_name }}
        tag_name: v${{ github.event.inputs.version || github.ref_name }}
        body: |
          ## Biduleur ${{ github.event.inputs.version || github.ref_name }}

          ### Changements
          - [Liste des changements pour cette version]

          ### Instructions
          1. Téléchargez `biduleur-${{ github.event.inputs.version || github.ref_name }}-windows.exe`
          2. Exécutez le fichier (aucune installation nécessaire)
        files: release_assets/*
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Fonctionnalités du workflow** :
- Utilise `--onefile` pour créer un exécutable autonome
- Gère les versions via des inputs
- Supprime les tags existants avant création pour éviter les conflits
- Crée des releases avec des notes automatiques
- Permet de choisir entre build seulement ou build + publication

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

J'ai apporté les améliorations suivantes :

1. **Section GitHub Actions enrichie** :
   - Ajout d'une sous-section "Configuration requise" pour expliquer les permissions nécessaires
   - Ajout d'une sous-section "Workflow détaillé" avec une explication complète du fichier YAML
   - Mise en évidence des fonctionnalités du workflow

2. **Mises à jour dans la section "Création d'une release"** :
   - Explication plus détaillée du processus automatique via GitHub Actions
   - Ajout d'informations sur les avantages de la méthode automatique
   - Précisions sur les paramètres du workflow manuel

3. **Ajouts dans la structure du projet** :
   - Ajout du chemin `.github/workflows/release.yml` pour plus de clarté

4. **Précisions dans les prérequis** :
   - Ajout d'une note sur les permissions GitHub nécessaires

5. **Améliorations dans la section dépannage** :
   - Ajout d'une entrée pour l'erreur 403 avec des solutions

Ce README est maintenant complet et explique clairement comment utiliser GitHub Actions pour créer et publier des releases automatiquement, avec toutes les informations nécessaires pour configurer et utiliser cette fonctionnalité. 🚀
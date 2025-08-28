# Module Biduleur
Biduleur est un outil pour générer des événements à partir de fichiers CSV, disponible en **mode CLI (ligne de commande)** et **mode GUI (interface graphique)**.

---
## Table des matières
1. [Prérequis](#prérequis)
2. [Structure du projet](#structure-du-projet)
3. [Installation](#installation)
4. [Modes d'utilisation](#modes-dutilisation)
   - [Mode GUI (Interface Graphique)](#mode-gui-interface-graphique)
   - [Mode CLI (Ligne de Commande)](#mode-cli-ligne-de-commande)
5. [Création du build](#création-du-build)
   - [Sur Windows](#sur-windows)
   - [Sur Linux](#sur-linux)
6. [Utilisation](#utilisation)
7. [Création d'une release](#création-dune-release)
   - [Manuellement](#manuellement)
   - [Automatiquement avec GitHub Actions](#automatiquement-avec-github-actions)
   - [Déclenchement manuel via GitHub Actions](#déclenchement-manuel-via-github-actions)
8. [Dépannage](#dépannage)
9. [Fichiers de configuration](#fichiers-de-configuration)
   - [biduleur.spec](#biduleurspec)
   - [build.bat](#buildbat)
   - [build.sh](#buildsh)
   - [release.sh](#releasesh)
10. [GitHub Actions](#github-actions)
11. [Contribuer](#contribuer)
12. [Licence](#licence)

---
## Prérequis
- Python 3.13 ou supérieur *(recommandé pour la compatibilité avec les builds GitHub Actions)*
- Pip (généralement installé avec Python)
- Git (optionnel, pour cloner le dépôt)
- UPX (optionnel, pour compresser l'exécutable)
- **Permissions GitHub** : Assurez-vous que votre dépôt a les permissions "Read and write" pour les GitHub Actions *(Settings > Actions > General > Workflow permissions)*

---
## Structure du projet
```
bidul.biduleur/
├── biduleur/               # Package Python
│   ├── __init__.py         # Fichier vide obligatoire
│   ├── main.py             # Point d'entrée (mode GUI par défaut)
│   ├── cli.py              # Module pour le mode CLI
│   ├── csv_utils.py        # Utilitaires pour les fichiers CSV
│   ├── format_utils.py     # Utilitaires de formatage
│   ├── constants.py        # Constantes du projet
│   ├── event_utils.py      # Gestion des événements
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
1. Clonez le dépôt (si nécessaire) :
   ```bash
   git clone https://github.com/lebidul/biduleur.git
   cd biduleur
   ```

2. Créez un environnement virtuel (recommandé) :
   ```bash
   python -m venv .venv
   ```

3. Activez l'environnement virtuel :
   - **Windows** :
     ```cmd
     .\.venv\Scripts\activate
     ```
   - **Linux/macOS** :
     ```bash
     source .venv/bin/activate
     ```

4. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

---
## Modes d'utilisation

Biduleur peut être utilisé de deux manières : via une **interface graphique (GUI)** ou en **ligne de commande (CLI)**.

---

### **Mode GUI (Interface Graphique)**
Le mode GUI est **l'interface par défaut** lorsque vous exécutez Biduleur sans arguments.

#### **Lancement**
- **Depuis le code source** :
  ```bash
  python -m biduleur
  ```
- **Depuis l'exécutable** (après build) :
  - **Windows** :
    ```cmd
    dist\biduleur\biduleur.exe
    ```
  - **Linux** :
    ```bash
    dist/biduleur/biduleur
    ```

#### **Fonctionnalités du mode GUI**
- **Interface intuitive** pour sélectionner les fichiers CSV.
- **Prévisualisation** des événements générés.
- **Export** des événements dans différents formats.
- **Historique** des fichiers récemment ouverts.

#### **Capture d'écran**
*(À ajouter : capture d'écran de l'interface graphique)*

---

### **Mode CLI (Ligne de Commande)**
Le mode CLI permet d'utiliser Biduleur **sans interface graphique**, idéal pour les scripts automatisés ou les environnements serveurs.

#### **Lancement**
```bash
python -m biduleur.cli --help
```
ou depuis l'exécutable :
```cmd
dist\biduleur\biduleur.exe --cli --help
```

#### **Options disponibles**
| Option | Description | Exemple |
|--------|-------------|---------|
| `--input` | Chemin vers le fichier CSV d'entrée | `--input data.csv` |
| `--output` | Chemin vers le fichier de sortie | `--output output.json` |
| `--format` | Format de sortie (`json`, `xml`, `txt`) | `--format json` |
| `--delimiter` | Délimiteur du CSV (défaut: `,`) | `--delimiter ;` |
| `--encoding` | Encodage du fichier (défaut: `utf-8`) | `--encoding latin1` |
| `--verbose` | Mode verbeux (affiche les détails) | `--verbose` |
| `--dry-run` | Simule la génération sans écrire le fichier | `--dry-run` |

#### **Exemples d'utilisation**
1. **Générer des événements depuis un CSV** :
   ```bash
   python -m biduleur.cli --input data.csv --output events.json --format json
   ```

2. **Valider un fichier CSV** :
   ```bash
   python -m biduleur.cli --input data.csv --dry-run --verbose
   ```

3. **Utiliser un délimiteur personnalisé** :
   ```bash
   python -m biduleur.cli --input data.csv --delimiter ";" --output events.xml --format xml
   ```

#### **Sortie standard**
Si aucun fichier de sortie n'est spécifié, les événements sont affichés dans la console :
```bash
python -m biduleur.cli --input data.csv
```

---

## Création du build
### Sur Windows
1. Double-cliquez sur `build.bat` ou exécutez-le depuis l'invite de commandes :
   ```cmd
   .\build.bat
   ```
2. Le build sera généré dans `dist\biduleur\biduleur.exe` (mode GUI par défaut).

### Sur Linux
1. Rendez le script exécutable :
   ```bash
   chmod +x build.sh
   ```
2. Exécutez le script :
   ```bash
   ./build.sh
   ```
3. Le build sera généré dans `dist/biduleur/biduleur`.

---
## Utilisation
Après le build, exécutez l'application :
- **Mode GUI (par défaut)** :
  ```cmd
  dist\biduleur\biduleur.exe
  ```
- **Mode CLI** :
  ```cmd
  dist\biduleur\biduleur.exe --cli --input data.csv --output events.json
  ```

---
## Création d'une release
### Manuellement
1. Créez un tag :
   ```bash
   git tag -a v1.0.0 -m "Version 1.0.0 - Première version stable"
   git push origin v1.0.0
   ```
2. Allez sur [GitHub Releases](https://github.com/lebidul/biduleur/releases)
3. Cliquez sur "Draft a new release"
4. Sélectionnez le tag `v1.0.0`
5. Ajoutez une description et attachez l'exécutable depuis `dist/biduleur/`
6. Publiez la release

### Automatiquement avec GitHub Actions
1. Exécutez le script de release :
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
1. Allez dans l'onglet **"Actions"** de votre dépôt GitHub
2. Sélectionnez le workflow **"Build and Release"** dans la liste à gauche
3. Cliquez sur **"Run workflow"** (bouton dropdown)
4. Configurez les paramètres :
   - **Version** : Numéro de version (ex: `1.0.0`)
   - **Publier la release ?** : `true` (pour publier) ou `false` (pour juste builder)
5. Cliquez sur **"Run workflow"**

---
## Dépannage
### Problèmes courants
1. **L'exécutable ne se lance pas** :
   - Activez le mode console dans `biduleur.spec` (`console=True`)
   - Vérifiez les dépendances : `pip install -r requirements.txt`
   - Nettoyez les anciens builds : `rm -rf build/ dist/`

2. **Erreurs de chemins** :
   - Vérifiez la structure du projet
   - Utilisez `os.path` pour les chemins dans votre code

3. **Build échoué** :
   - Exécutez avec plus de détails : `pyinstaller biduleur.spec --clean --debug=all`
   - Consultez les logs dans `build/`

4. **Erreur avec GitHub Actions "deprecated version of actions/upload-artifact: v3"** :
   - Le workflow fourni utilise déjà les versions actuelles des actions (v4)

5. **Erreur 403 lors de la création de release** :
   - Vérifiez que les permissions du dépôt sont correctement configurées *(Settings > Actions > General > Workflow permissions : "Read and write permissions")*
   - Assurez-vous que le tag n'existe pas déjà

6. **Problèmes avec le mode CLI** :
   - Vérifiez que `biduleur/cli.py` existe et est importable
   - Testez en local : `python -m biduleur.cli --help`

---
## Fichiers de configuration
### biduleur.spec
```python
# biduleur.spec (compatible local + GitHub Actions)
from PyInstaller.utils.hooks import collect_submodules
import os
import sys
import glob

def find_python_dll():
    # Chemin pour GitHub Actions
    github_dll = os.path.join(sys.prefix, 'python*.dll')
    github_matches = glob.glob(github_dll)
    if github_matches:
        return github_matches[0]

    # Chemin pour venv local
    venv_dll = os.path.join(sys.prefix, 'Scripts', 'python3*.dll')
    venv_matches = glob.glob(venv_dll)
    if venv_matches:
        return venv_matches[0]

    raise FileNotFoundError("DLL Python introuvable")

python_dll = find_python_dll()
print(f"Utilisation de la DLL : {python_dll}")

hidden_imports = collect_submodules('tkinter') + [
    'biduleur.csv_utils',
    'biduleur.format_utils',
    'biduleur.constants',
    'biduleur.event_utils',
    'biduleur.cli',  # Ajoutez le module CLI
    'pkg_resources.py2_warn',
]

a = Analysis(
    ['biduleur/main.py'],
    pathex=[os.path.dirname(os.path.abspath(__file__))],
    binaries=[(python_dll, '.')],
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
    a.binaries,
    [],
    name='biduleur',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,  # Affiche la console pour le mode CLI
    icon='biduleur.ico' if os.path.exists('biduleur.ico') else None,
    onefile=True  # Exécutable unique
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
python -m PyInstaller biduleur.spec --clean

:: Vérification
if exist "dist\biduleur.exe" (
    echo Build réussi !
    dir dist\
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
python -m PyInstaller biduleur.spec --clean

# Vérification
if [ -f "dist/biduleur" ]; then
    echo "Build réussi !"
    ls -l dist/
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
- Le build de l'application (GUI + CLI)
- La création de releases automatiques
- La gestion des tags
- La publication des exécutables

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:
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
      uses: actions/checkout@v4

    - name: Set up Python 3.13
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller

    - name: Find Python DLL
      id: find_dll
      shell: python
      run: |
        import os
        import sys
        import glob
        dll_path = glob.glob(f"{sys.prefix}/python*.dll")[0]
        print(f"::set-output name=dll_path::{dll_path}")

    - name: Build executable
      run: |
        pyinstaller biduleur.spec --clean

    - name: Prepare release assets
      run: |
        mkdir release_assets
        copy dist\biduleur.exe release_assets\biduleur-${{ github.event.inputs.version || github.ref_name }}-windows.exe

    - name: Create Release
      uses: softprops/action-gh-release@v1
      with:
        name: Biduleur ${{ github.event.inputs.version || github.ref_name }}
        tag_name: v${{ github.event.inputs.version || github.ref_name }}
        body: |
          ## Biduleur ${{ github.event.inputs.version || github.ref_name }}

          ### Changements
          - [Liste des changements]

          ### Modes disponibles
          - **GUI** : Double-cliquez sur l'exécutable
          - **CLI** : Utilisez `--cli` pour le mode ligne de commande

          ### Exemples
          ```cmd
          biduleur-${{ github.event.inputs.version || github.ref_name }}-windows.exe
          biduleur-${{ github.event.inputs.version || github.ref_name }}-windows.exe --cli --input data.csv --output events.json
          ```
        files: release_assets/*
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---
## Contribuer
1. Forkez le projet
2. Créez une branche (`git checkout -b feature/ma-fonctionnalité`)
3. Commitez vos changements (`git commit -am 'Ajout fonctionnalité'`)
4. Poussez la branche (`git push origin feature/ma-fonctionnalité`)
5. Ouvrez une Pull Request

---
## Licence
[MIT](LICENCE)
```

---
### **🔧 Modifications apportées :**
1. **Ajout d'une section "Modes d'utilisation"** :
   - Sous-sections pour **GUI** et **CLI**.
   - Exemples concrets pour chaque mode.
   - Tableau des options CLI.

2. **Mise à jour de `biduleur.spec`** :
   - Ajout de `biduleur.cli` dans `hiddenimports`.
   - Activation de la console (`console=True`) pour le mode CLI.

3. **Mise à jour du workflow GitHub Actions** :
   - Ajout d'une section **Modes disponibles** dans la description de la release.
   - Exemples d'utilisation dans les notes de release.

4. **Structure du projet** :
   - Ajout de `cli.py` dans la liste des fichiers.

5. **Dépannage** :
   - Ajout d'une entrée pour les problèmes liés au mode CLI.

---
### **📌 Prochaines étapes :**
1. **Ajoutez une capture d'écran** de l'interface graphique dans la section **Mode GUI**.
2. **Testez les deux modes** (GUI et CLI) avec l'exécutable généré.
3. **Vérifiez que le mode CLI fonctionne** depuis l'exécutable :
   ```cmd
   dist\biduleur\biduleur.exe --cli --help
   ```

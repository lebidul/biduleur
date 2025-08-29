# Module Biduleur
Biduleur est un outil pour générer des événements à partir de fichiers CSV, disponible en **mode GUI (interface graphique)** et **mode CLI (ligne de commande)**.

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
8. [Dépannage](#dépannage)
9. [Fichiers de configuration](#fichiers-de-configuration)
   - [biduleur.spec](#biduleurspec)
   - [build.biduleur.bat](#buildbat)
   - [build.biduleur.sh](#buildsh)
   - [release.yml](#releaseyml)
10. [Contribuer](#contribuer)
11. [Licence](#licence)

---
## Prérequis
- Python 3.9 ou supérieur
- Pip (généralement installé avec Python)
- Git (optionnel, pour cloner le dépôt)
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
├── biduleur.spec           # Fichier de configuration PyInstaller
├── build.biduleur.bat               # Script de build pour Windows
├── build.biduleur.sh                # Script de build pour Linux
├── requirements.txt        # Dépendances Python
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

---

## Création du build

### Windows (local)

```cmd
pyinstaller biduleur.spec --clean --workpath=build --distpath=dist
```

Le résultat est dans `dist\biduleur\` :

* `biduleur.exe`
* `_internal\` (dépendances embarquées)

### GitHub Actions

Le workflow `${repo}/.github/workflows/release.yml` :

* utilise **Python 3.10**
* installe `pyinstaller` + `pyinstaller-hooks-contrib`
* installe les deps depuis `biduleur/requirements.txt`
* build en **onedir** et génère un ZIP prêt à publier

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
1. Exécutez le workflow manuellement depuis GitHub Actions :
   - Allez dans l'onglet **"Actions"**
   - Sélectionnez le workflow **"Build and Release"**
   - Cliquez sur **"Run workflow"**
   - Configurez les paramètres :
     - **Version** : Numéro de version (ex: `1.0.0`)
     - **Publier la release ?** : `true` (pour publier) ou `false` (pour juste builder)
   - Cliquez sur **"Run workflow"**

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

---
## Fichiers de configuration
### biduleur.spec
```python
# biduleur.spec (version finale)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import os
import sys

current_dir = os.getcwd()
main_script = os.path.join(current_dir, 'biduleur', 'main.py')

if not os.path.exists(main_script):
    raise FileNotFoundError(f"Le fichier {main_script} est introuvable")

hidden_imports = collect_submodules('tkinter')
hidden_imports += [
    'biduleur.csv_utils',
    'biduleur.format_utils',
    'biduleur.constants',
    'biduleur.event_utils',
    'pkg_resources.py2_warn',
    'pandas',
    'numpy',
    'python_dateutil',
    'pytz',
    'tzdata',
    'six',
]

datas = collect_data_files('tkinter')
datas += [(os.path.join(current_dir, 'biduleur'), 'biduleur')]

site_packages = os.path.join(sys.prefix, 'Lib', 'site-packages')
datas += [(site_packages, 'site-packages')]

a = Analysis(
    [main_script],
    pathex=[current_dir, site_packages],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=['hooks'],
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
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    icon=os.path.join(current_dir, 'biduleur.ico') if os.path.exists(os.path.join(current_dir, 'biduleur.ico')) else None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='biduleur'
)
```

### build.biduleur.bat
```batch
@echo off
cd /d "%~dp0"

:: Nettoyage des anciens builds
echo Nettoyage des anciens builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

:: Vérification de la structure
echo Vérification de la structure :
dir /b
if not exist "biduleur\main.py" (
    echo ERREUR: biduleur\main.py introuvable
    exit /b 1
)

:: Build
echo Création du build...
pyinstaller biduleur.spec --clean --workpath=build --distpath=dist

:: Vérification
if exist "dist\biduleur" (
    echo Build réussi !
    dir dist\
) else (
    echo ERREUR: Build échoué
    exit /b 1
)
```

### build.biduleur.sh
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
pyinstaller biduleur.spec --clean --workpath=build --distpath=dist

# Vérification
if [ -d "dist/biduleur" ]; then
    echo "Build réussi !"
    ls -l dist/
else
    echo "ERREUR: Build échoué"
    exit 1
fi
```

### release.yml
```yaml
name: Build and Release - Biduleur (moulinette)

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

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r biduleur/requirements.txt
        pip install pyinstaller

    - name: Build executable (mode --onedir)
      run: |
        pyinstaller biduleur.spec --clean --workpath=build --distpath=dist

    - name: Prepare release assets
      run: |
        mkdir release_assets
        # Créer un fichier README.txt pour les utilisateurs finaux
        echo "Biduleur v${{ github.event.inputs.version || github.ref_name }}" > dist\biduleur\README.txt
        echo "================================================" >> dist\biduleur\README.txt
        echo "" >> dist\biduleur\README.txt
        echo "Merci d'utiliser Biduleur !" >> dist\biduleur\README.txt
        echo "" >> dist\biduleur\README.txt
        echo "INSTRUCTIONS:" >> dist\biduleur\README.txt
        echo "1. Extrayez le contenu de ce fichier ZIP dans un dossier de votre choix." >> dist\biduleur\README.txt
        echo "2. Double-cliquez sur biduleur.exe pour lancer l'application." >> dist\biduleur\README.txt
        echo "3. Suivez les instructions à l'écran." >> dist\biduleur\README.txt
        echo "" >> dist\biduleur\README.txt
        echo "REQUIREMENTS:" >> dist\biduleur\README.txt
        echo "- Windows 10 ou supérieur" >> dist\biduleur\README.txt
        echo "- Aucune installation supplémentaire nécessaire" >> dist\biduleur\README.txt
        echo "" >> dist\biduleur\README.txt
        echo "SUPPORT:" >> dist\biduleur\README.txt
        echo "Pour toute question ou problème, contactez-nous via GitHub." >> dist\biduleur\README.txt
        # Compresser le dossier biduleur en ZIP
        Compress-Archive -Path dist\biduleur\* -DestinationPath release_assets\biduleur-${{ github.event.inputs.version || github.ref_name }}-windows.zip -Force

    - name: Create Release
      if: ${{ github.event.inputs.publish_release != 'false' && (github.event_name == 'workflow_dispatch' || startsWith(github.ref, 'refs/tags/')) }}
      uses: softprops/action-gh-release@v1
      with:
        name: Biduleur ${{ github.event.inputs.version || github.ref_name }}
        tag_name: ${{ github.event.inputs.version && format('v{0}', github.event.inputs.version) || github.ref_name }}
        body: |
          ## Biduleur ${{ github.event.inputs.version || github.ref_name }}

          ### Changements
          - [Liste des changements pour cette version]

          ### Instructions
          1. Téléchargez `biduleur-${{ github.event.inputs.version || github.ref_name }}-windows.zip`
          2. Extrayez le fichier ZIP dans un dossier de votre choix
          3. Exécutez `biduleur.exe` depuis le dossier extrait (aucune installation nécessaire)

          ### Contenu du ZIP
          - `biduleur.exe` : Exécutable principal
          - `README.txt` : Instructions pour les utilisateurs
          - Autres fichiers nécessaires au fonctionnement

        files: release_assets/*
        generate_release_notes: true
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

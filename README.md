---

# Module Biduleur

Biduleur est un outil pour générer des événements à partir de fichiers CSV/XLS/XLSX et produire des fichiers HTML prêts à être mis en page.
Le projet s’intègre avec **Misenpageur** (génération du PDF final A4 recto/verso) et propose un **wrapper CLI racine** pour enchaîner ingestion → PDF en une seule commande.

---

## Table des matières

1.  [Prérequis](#prérequis)
2.  [Structure du projet](#structure-du-projet)
3.  [Installation](#installation)
4.  [Modes d'utilisation](#modes-dutilisation)
    *   [Mode GUI (Interface Graphique)](#mode-gui-interface-graphique)
    *   [Mode CLI (Ligne de Commande)](#mode-cli-ligne-de-commande)
    *   **Intégration Misenpageur (PDF) avec marges dynamiques**
    *   **Wrapper CLI racine (ingestion → PDF)**
5.  [Création d'une release](#création-dune-release)
    *   [Manuellement (pour tester)](#manuellement-pour-tester)
    *   [Automatiquement avec GitHub Actions (officiel)](#automatiquement-avec-github-actions-officiel)
6.  [Dépannage](#dépannage)
7.  [Fichiers de configuration](#fichiers-de-configuration)
    *   [bidul.release.yml](#bidulreleaseyml)
    *   [misenpageur/config.yml](#misenpageurconfigyml)
    *   [misenpageur/layout.yml](#misenpageurlayoutyml)
    *   [Polices & glyphes (€, ❑)](#polices--glyphes--)
8.  [Contribuer](#contribuer)
9.  [Licence](#licence)

---

## Prérequis

*   Python 3.9+
*   Pip
*   (Optionnel) Git
*   Dépendances (voir `requirements.txt`) : `reportlab`, `pyyaml`, `pandas`, `openpyxl`, **`qrcode[pil]`**

---

## Structure du projet

```
bidul/
├── biduleur/                    # Module 1 : ingestion CSV/XLS -> HTML
│   ├── __init__.py
│   ├── main.py                  # GUI et API run_biduleur(input_path, html_bidul, html_agenda)
│   ├── cli.py                   # CLI d’ingestion
│   ├── csv_utils.py
│   ├── format_utils.py
│   ├── constants.py
│   ├── event_utils.py
├── misenpageur/                 # Module 2 : mise en page PDF à partir d’un HTML
│   ├── main.py                  # point d’entrée CLI
│   ├── config.yml               # configuration d’exemple
│   ├── layout.yml               # layout d’exemple (A4 sans marges)
│   ├── assets/
│   │   ├── biduleur.html        # HTML source (exemple)
│   │   ├── cover.jpg
│   │   ├── ours.md
│   │   ├── logos/
│   │   │   └── *.png|jpg
│   ├── output/
│   └── misenpageur/
│       ├── __init__.py
│       ├── layout_builder.py    # <-- NOUVEAU : Applique les marges au layout
│       ├── pdfbuild.py
│       ├── config.py
│       ├── layout.py
│       ├── html_utils.py
│       ├── drawing.py
│       ├── textflow.py
│       ├── pdfbuild.py
│       ├── spacing.py
│       ├── glyphs.py
│       └── fonts.py
├── cli.py                       # Module 3 : wrapper CLI racine (ingestion → PDF)
├── __main__.py                  # Permet `python -m bidul`
├── requirements.txt
└── (évent.) data/, dist/, build/, .github/, etc.
```

---

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Assurez-vous que qrcode[pil] est dans requirements.txt
pip install -r requirements.txt
```

---

## Modes d'utilisation

### Mode GUI (Interface Graphique)

```bash
python -m biduleur
```

### Mode CLI (Ligne de Commande)

Ingestion seule (produit les fichiers HTML) :
*(Instructions inchangées)*

### Intégration Misenpageur (PDF) avec marges dynamiques

Le layout final du PDF est généré dynamiquement. Le fichier `layout.yml` sert de **modèle de base** (généralement sans marges), et les marges sont appliquées à la volée à partir de la section `pdf_layout` de votre `config.yml`.

Pour produire le PDF à partir d’un HTML déjà généré :

```bash
python misenpageur/main.v0.py \
  --root . \
  --config misenpageur/config.yml \
  --layout misenpageur/layout.yml \
  --out misenpageur/output/bidul.pdf
```

#### Wrapper CLI racine (ingestion → PDF)

Le wrapper exécute **ingestion** puis **mise en page** automatiquement :

```bash
python -m bidul \
  -i data/tapage.xlsx \
  --config misenpageur/config.yml \
  --layout misenpageur/layout.yml \
  --out data/output/bidul.pdf
```

Options utiles :

*   `--bidul-html` / `--agenda-html` : chemins de sortie des HTML si tu ne veux pas les valeurs par défaut
*   `--assets-dir` : dossier par défaut des HTML (si non fournis)
*   `--cover` : surcharge l’image de couverture (remplace `cover_image` de la config pour ce run)
*   `--project-root` : racine projet pour Misenpageur (défaut : dossier de la config)

---

### Utiliser l’HTML généré avec Misenpageur

1.  Lancer Biduleur (GUI ou CLI) pour produire `misenpageur/assets/biduleur.html`.
2.  Lancer Misenpageur (CLI) :

```bash
python misenpageur/main.v0.py \
  --root . \
  --config misenpageur/config.yml \
  --layout misenpageur/layout.yml \
  --out misenpageur/output/bidul.pdf
```

### Exécuter la chaîne complète via le wrapper

```bash
python -m bidul \
  -i data/tapage.xlsx \
  --config misenpageur/config.yml \
  --layout misenpageur/layout.yml \
  --out data/output/bidul.pdf
```

---

## Création d'une release

Le projet utilise GitHub Actions pour automatiser la création des builds (exécutables Windows) et des releases.

### Manuellement (pour tester)

Vous pouvez lancer le processus de build à tout moment pour tester les modifications sans créer de release publique.

1.  Allez dans l'onglet **Actions** de votre dépôt GitHub.
2.  Dans la liste des workflows à gauche, cliquez sur **"Build and Release - Bidul"**.
3.  Cliquez sur le bouton **"Run workflow"** qui apparaît à droite.
4.  Choisissez la branche que vous souhaitez tester et cliquez sur **"Run workflow"**.

Le workflow va s'exécuter. Une fois terminé, vous pourrez télécharger le fichier `.zip` contenant l'exécutable depuis la section **Artifacts** en bas de la page de résumé du workflow. **Aucune release ne sera créée.**

### Automatiquement avec GitHub Actions (officiel)

Pour créer une nouvelle release officielle :

1.  Assurez-vous que vos dernières modifications sont sur la branche `master`.
2.  Créez un tag Git localement en respectant le format `bidul-vX.Y.Z` (par exemple, `bidul-v1.0.5`).

    ```bash
    # Exemple pour une version 1.0.5
    git tag bidul-v1.0.5
    ```

3.  Poussez le tag sur le dépôt distant.

    ```bash
    git push origin bidul-v1.0.5
    ```

Le fait de pousser un tag correspondant à ce format déclenchera automatiquement le workflow GitHub Actions. Celui-ci va :
*   Construire l'exécutable Windows.
*   Le compresser dans une archive `.zip`.
*   Créer une nouvelle **Release** sur GitHub.
*   Attacher l'archive `.zip` à cette release, prête à être téléchargée.

---

## Dépannage

*   **Arial/Arial Narrow introuvable** : `reportlab` ne trouve pas la police. Placez les fichiers `.TTF` correspondants dans un dossier `assets/fonts/` ou laissez le fallback sur Helvetica.
*   **TypeError: expected str, bytes or os.PathLike object, not BytesIO** : Erreur liée à la génération du QR code. Assurez-vous d'avoir bien installé `qrcode[pil]` (`pip install "qrcode[pil]"`).
*   **Glyphes `€` / `❑`** : fournis via **fallback DejaVuSans** (famille enregistrée dans `fonts.py`). Place au moins `DejaVuSans.ttf` dans `misenpageur/assets/fonts/DejaVu/` (ou installe le paquet système).
*   **Date box absente** : vérifier `date_box.enabled: true` + `border_width`/`back_color` non nuls.
*   **Paragraphes non placés** : jouer sur `font_size_max` / `split_min_gain_ratio` ou l’ordre des sections.
*   **“No such file or directory …/output.pdf”** : créer le dossier parent (le wrapper le fait désormais).

---

## Fichiers de configuration

### bidul.release.yml

Ce fichier, situé dans `.github/workflows/`, définit le processus d'intégration continue (CI/CD) pour construire et publier l'application.

**Fonctionnement :**

1.  **Déclencheurs (`on`)** : Le workflow est lancé soit automatiquement lorsqu'un tag `bidul-v*` est poussé, soit manuellement via l'interface de GitHub (`workflow_dispatch`).
2.  **Préparation (`steps`)** : Il installe Python, les dépendances nécessaires et `pyinstaller`.
3.  **Gestion de la version** : Il détecte si le lancement est manuel ou via un tag pour assigner un nom de version approprié.
4.  **Build** : Il utilise `PyInstaller` et `bidul.spec` pour compiler le projet en un exécutable.
5.  **Packaging** : Il compresse l'exécutable et les fichiers annexes (comme `RELEASE_NOTES.md`) dans une archive `.zip`.
6.  **Upload de l'artefact** : L'archive est sauvegardée en tant qu'artefact de build, téléchargeable pour tous les runs.
7.  **Création de la release (conditionnelle)** : **Uniquement si le workflow a été déclenché par un tag**, il crée une nouvelle release publique sur GitHub et y attache l'archive `.zip`.

```yaml
name: Build and Release - Bidul

on:
  # 1. Se déclenche quand un tag comme "bidul-v1.2.3" est poussé
  push:
    tags:
      - 'bidul-v*'
  # 2. Permet un déclenchement manuel depuis l'onglet "Actions" de GitHub
  workflow_dispatch:

jobs:
  build-release:
    runs-on: windows-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pyinstaller==6.6.0
          pip install -r biduleur/requirements.txt
          pip install -r misenpageur/requirements.txt

      - name: Determine Version
        id: versioning
        shell: pwsh
        run: |
          if ("${{ github.event_name }}" -eq "push") {
            $version = ("${{ github.ref_name }}".Split('-')[1]).TrimStart('v')
          } else {
            $branch = "${{ github.ref_name }}".Replace('/', '-')
            $sha = "${{ github.sha }}".Substring(0, 7)
            $version = "MANUAL-$branch-$sha"
          }
          echo "VERSION=$version" | Out-File -FilePath $env:GITHUB_ENV -Append

      - name: Build with PyInstaller
        run: pyinstaller bidul.spec --clean --noconfirm

      - name: Package artifact
        id: package
        shell: pwsh
        run: |
          $version = "${{ env.VERSION }}"
          $sourceFolder = "dist/bidul"
          $zipFileName = "bidul-${version}-win64.zip"
          if (Test-Path "RELEASE_NOTES.md") {
            Copy-Item -Path "RELEASE_NOTES.md" -Destination "$sourceFolder/"
          }
          Compress-Archive -Path "$sourceFolder/*" -DestinationPath $zipFileName -Force
          echo "zip_name=$zipFileName" | Out-File -FilePath $env:GITHUB_OUTPUT

      - name: Upload Build Artifact
        uses: actions/upload-artifact@v4
        with:
          name: bidul-windows-build-${{ env.VERSION }}
          path: ${{ steps.package.outputs.zip_name }}
          retention-days: 7

      # Cette étape ne s'exécute que si le workflow a été déclenché par un PUSH de TAG.
      - name: Create Release
        if: github.event_name == 'push'
        uses: softprops/action-gh-release@v2
        with:
          name: Bidul v${{ env.VERSION }}
          tag_name: ${{ github.ref_name }}
          files: ${{ steps.package.outputs.zip_name }}
          body_path: RELEASE_NOTES.md
```

### misenpageur/config.yml

Ce fichier centralise tous les paramètres de mise en page du PDF.

```yaml
# --------------------
# Chemins et Fichiers
# --------------------
input_html: assets/biduleur.html
ours_md:    assets/ours.md
logos_dir:  assets/logos
cover_image: assets/cover.jpg

# --------------------
# Layout dynamique
# --------------------
pdf_layout:
  page_margin_mm: 4   # Marge globale appliquée au layout de base

# --------------------
# Configuration de la Section 1
# --------------------
section_1:
  # Colonne Ours
  ours_font_name: "Arial"
  ours_font_size: 8
  ours_line_spacing: 1.2
  ours_border_width: 0.5   # Largeur du cadre autour de l'ours (0 pour aucun)

  # QR Code et son titre
  qr_code_value: "https://www.lebidul.com"
  qr_code_height_mm: 30
  qr_code_title: "Agenda culturel"
  qr_code_title_font_name: "Arial-Bold"
  qr_code_title_font_size: 9

  # Colonne Logos
  additional_box_height_mm: 10 # Hauteur de la boîte sous les logos (0 pour aucune)
  logo_box_bottom_margin_mm: 3 # Marge entre les logos et la boîte additionnelle

# --------------------
# Configuration du texte principal (S3, S4, S5, S6)
# --------------------
font_name: "ArialNarrow"
font_size_min: 8.0
font_size_max: 10.0
# ... (autres clés de configuration du texte)
```

### misenpageur/layout.yml

Ce fichier décrit la **structure de base sans marges**. Les marges de `config.yml` sont appliquées par-dessus.

```yaml
page_size: { width: 595, height: 842 }   # A4 en points

sections:
  # Page 1 = grille 2x2
  S1: { page: 1, x: 0,     y: 421, w: 297.5, h: 421 }
  S2: { page: 1, x: 297.5, y: 421, w: 297.5, h: 421 }
  S3: { page: 1, x: 0,     y: 0,   w: 297.5, h: 421 }
  S4: { page: 1, x: 297.5, y: 0,   w: 297.5, h: 421 }
  # Page 2 = 2 colonnes pleine hauteur
  S5: { page: 2, x: 0,     y: 0,   w: 297.5, h: 842 }
  S6: { page: 2, x: 297.5, y: 0,   w: 297.5, h: 842 }

s1_split:
  # Ratio de largeur pour les colonnes de S1
  logos_ratio: 0.5 
```

### Polices & glyphes (€, ❑)

*   **Arial Narrow** : si disponible (Windows ou `assets/fonts/ArialNarrow/`), sinon **Helvetica**.
*   **Fallback DejaVuSans** : assure `DejaVuSans.ttf` présent (ou installé) ; la famille est enregistrée dans `fonts.py` pour garantir `€` et `❑`.
*   (Option) Remplacer `❑` par `■` via `event_bullet_replacement`.

---

## Contribuer

1.  Forkez le projet
2.  Créez une branche (`git checkout -b feature/ma-fonctionnalité`)
3.  Commentez vos changements (`git commit -am 'Ajout fonctionnalité'`)
4.  Poussez la branche (`git push origin feature/ma-fonctionnalité`)
5.  Ouvrez une Pull Request

---

## Licence

MIT (voir `LICENCE`).
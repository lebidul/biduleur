Parfait — voici un **README.md** unifié qui **conserve la structure et les sections existantes du module *Biduleur* (1 → 9)**, et **ajoute les informations *Misenpageur* et *CLI racine*** sans casser la numérotation (elles sont intégrées dans *Structure du projet*, *Modes d’utilisation* et *Fichiers de configuration*).
Les sections **10. Contribuer** et **11. Licence** restent **au même niveau que les modules** (top-level), comme demandé.

> Remplace simplement le contenu de `bidul/README.md` par ce qui suit.

---

# Module Biduleur

Biduleur est un outil pour générer des événements à partir de fichiers CSV/XLS/XLSX et produire 2 fichiers HTML prêts à être mis en page.
Le projet s’intègre avec **Misenpageur** (génération du PDF final A4 recto/verso) et propose un **wrapper CLI racine** pour enchaîner ingestion → PDF en une seule commande.

---

## Table des matières

1. [Prérequis](#prérequis)
2. [Structure du projet](#structure-du-projet)
3. [Installation](#installation)
4. [Modes d'utilisation](#modes-dutilisation)

   * [Mode GUI (Interface Graphique)](#mode-gui-interface-graphique)
   * [Mode CLI (Ligne de Commande)](#mode-cli-ligne-de-commande)
   * **Intégration Misenpageur (PDF)**
   * **Wrapper CLI racine (ingestion → PDF)**
5. [Création du build](#création-du-build)

   * [Sur Windows](#sur-windows)
   * [Sur Linux](#sur-linux)
6. [Utilisation](#utilisation)

   * **Utiliser l’HTML généré avec Misenpageur**
   * **Exécuter la chaîne complète via le wrapper**
7. [Création d'une release](#création-dune-release)

   * [Manuellement](#manuellement)
   * [Automatiquement avec GitHub Actions](#automatiquement-avec-github-actions)
8. [Dépannage](#dépannage)
9. [Fichiers de configuration](#fichiers-de-configuration)

   * [biduleur.spec](#biduleurspec)
   * [build.biduleur.bat](#buildbat)
   * [build.biduleur.sh](#buildsh)
   * [release.yml](#releaseyml)
   * **misenpageur/config.yml**
   * **misenpageur/layout.yml**
   * **Polices & glyphes (€, ❑)**
10. [Contribuer](#contribuer)
11. [Licence](#licence)

---

## Prérequis

* Python 3.9+
* Pip
* (Optionnel) Git
* Dépendances (voir `requirements.txt`) : `reportlab`, `pyyaml`, `pandas`, `openpyxl`

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

**Rôle des modules :**

* **Biduleur** : lit CSV/XLS(X), normalise et génère **2 HTML** : `biduleur.html` (standard) et `biduleur_bullets.html`/`biduleur.agenda.html` (événements préfixés par `❑`).
* **Misenpageur** : met en page un **A4 recto/verso** (sections S1–S6) et exporte un **PDF**.
* **Wrapper CLI racine** : enchaîne Biduleur → Misenpageur ; permet aussi de **surcharger la couverture** via `--cover`.

---

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Modes d'utilisation

### Mode GUI (Interface Graphique)

```bash
python -m biduleur
```

### Mode CLI (Ligne de Commande)

Ingestion seule (produit les 2 HTML) :

```bash
python -m biduleur.cli ingest \
  --input data/tapage.xlsx \
  --out-dir misenpageur/assets \
  --columns "date=Date,titre=Titre,lieu=Lieu,heure=Heure,prix=Tarif,tags=Tags"
```

> Par défaut, deux fichiers sont générés dans `--out-dir` :
> `biduleur.html` et `biduleur_bullets.html` (ou `biduleur.agenda.html`)

#### Intégration Misenpageur (PDF)

Tu peux utiliser `misenpageur/main.py` directement pour produire le PDF à partir d’un HTML déjà généré :

```bash
python misenpageur/main.py \
  --root . \
  --config misenpageur/config.yml \
  --layout misenpageur/layout.yml \
  --out misenpageur/output/bidul.pdf
```

*(Le champ `input_html` est lu dans `config.yml` — pointe généralement vers `misenpageur/assets/biduleur.html`.)*

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

* `--bidul-html` / `--agenda-html` : chemins de sortie des HTML si tu ne veux pas les valeurs par défaut
* `--assets-dir` : dossier par défaut des HTML (si non fournis)
* `--cover` : surcharge l’image de couverture (remplace `cover_image` de la config pour ce run)
* `--project-root` : racine projet pour Misenpageur (défaut : dossier de la config)

---

## Création du build

### Sur Windows

*(conserve ici tes instructions existantes pour PyInstaller / scripts `build.biduleur.bat`, etc.)*

### Sur Linux

*(conserve ici tes instructions existantes pour PyInstaller / scripts `build.biduleur.sh`, etc.)*

---

## Utilisation

*(conserve ici tes exemples actuels d’utilisation Biduleur — GUI et CLI — si tu en avais)*

### Utiliser l’HTML généré avec Misenpageur

1. Lancer Biduleur (GUI ou CLI) pour produire `misenpageur/assets/biduleur.html`.
2. Lancer Misenpageur (CLI) :

```bash
python misenpageur/main.py \
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

### Manuellement

*(conserve ici tes instructions existantes)*

### Automatiquement avec GitHub Actions

*(conserve ici tes instructions existantes — fichier `.github/workflows/release.yml`)*

---

## Dépannage

*(conserve tes points existants et ajoute si utile)*

* **Arial Narrow introuvable** : warning normal si la police n’est pas installée.
  Place `ARIALN*.TTF` dans `misenpageur/assets/fonts/ArialNarrow/` ou laisse le fallback Helvetica.
* **Glyphes `€` / `❑`** : fournis via **fallback DejaVuSans** (famille enregistrée dans `fonts.py`).
  Place au moins `DejaVuSans.ttf` dans `misenpageur/assets/fonts/DejaVu/` (ou installe le paquet système).
* **Date box absente** : vérifier `date_box.enabled: true` + `border_width`/`back_color` non nuls.
* **Paragraphes non placés** : jouer sur `font_size_max` / `split_min_gain_ratio` ou l’ordre des sections.
* **“No such file or directory …/output.pdf”** : créer le dossier parent (le wrapper le fait désormais).

---

## Fichiers de configuration

### biduleur.spec

*(conserve ton contenu existant)*

### build.biduleur.bat

*(conserve ton contenu existant)*

### build.biduleur.sh

*(conserve ton contenu existant)*

### release.yml

*(conserve ton contenu existant)*

---

### misenpageur/config.yml

Clés utiles (exemple minimal) :

```yaml
input_html: assets/biduleur.html
ours_md:    assets/ours.md
logos_dir:  assets/logos
cover_image: assets/cover.jpg

font_name: "Arial Narrow"        # fallback Helvetica si introuvable
font_size_min: 8.0
font_size_max: 10.0
leading_ratio: 1.12
inner_padding: 2

text_sections_order: ["S5","S6","S3","S4"]

date_spaceBefore: 6
date_spaceAfter: 3
event_spaceBefore: 1
event_spaceAfter: 1
event_spaceAfter_perLine: 0.4
min_event_spaceAfter: 1
first_non_event_spaceBefore_in_S5: 0

split_min_gain_ratio: 0.10

show_event_bullet: true
event_bullet_replacement: null
event_hanging_indent: 10

date_box:
  enabled: true
  padding: 3
  border_width: 1.0
  border_color: "#000000"
  back_color: "#f2f2f2"
```

### misenpageur/layout.yml

A4 sans marges (2×2 page 1, 2 colonnes page 2) :

```yaml
page_size: { width: 595, height: 842 }   # A4 en points
sections:
  S1: { page: 1, x: 0,     y: 421, w: 297.5, h: 421 }
  S2: { page: 1, x: 297.5, y: 421, w: 297.5, h: 421 }
  S3: { page: 1, x: 0,     y: 0,   w: 297.5, h: 421 }
  S4: { page: 1, x: 297.5, y: 0,   w: 297.5, h: 421 }
  S5: { page: 2, x: 0,     y: 0,   w: 297.5, h: 842 }
  S6: { page: 2, x: 297.5, y: 0,   w: 297.5, h: 842 }
s1_split: { logos_ratio: 0.60 }
```

### Polices & glyphes (€, ❑)

* **Arial Narrow** : si disponible (Windows ou `assets/fonts/ArialNarrow/`), sinon **Helvetica**.
* **Fallback DejaVuSans** : assure `DejaVuSans.ttf` présent (ou installé) ; la famille est enregistrée dans `fonts.py` pour garantir `€` et `❑`.
* (Option) Remplacer `❑` par `■` via `event_bullet_replacement`.

---

## Contribuer

1. Forkez le projet
2. Créez une branche (`git checkout -b feature/ma-fonctionnalité`)
3. Commitez vos changements (`git commit -am 'Ajout fonctionnalité'`)
4. Poussez la branche (`git push origin feature/ma-fonctionnalité`)
5. Ouvrez une Pull Request

---

## Licence

MIT (voir `LICENCE`).

---

Si tu veux, je peux aussi pousser ce README dans un commit type “docs: unify README (biduleur + misenpageur + cli)”.


---

# Projet Bidul

Bidul est une suite d'outils Python conçue pour transformer des listes d'événements (depuis des fichiers `.xls`, `.xlsx`, ou `.csv`) en documents mis en page de haute qualité, prêts à être imprimés ou partagés numériquement.

Le projet est articulé autour d'une **interface graphique principale** qui orchestre deux moteurs principaux :
*   **Biduleur** : Le module d'ingestion qui parse les données sources et les transforme en HTML structuré.
*   **Misenpageur** : Le moteur de rendu qui prend le HTML et génère les documents finaux (PDF, SVG, PNG).

---

## Table des matières

1.  [Fonctionnalités](#fonctionnalités)
2.  [Structure du projet](#structure-du-projet)
3.  [Installation](#installation)
4.  [Utilisation](#utilisation)
    *   [Lancement de l'Interface Graphique (GUI)](#lancement-de-linterface-graphique-gui)
    *   [Utilisation en Ligne de Commande (CLI)](#utilisation-en-ligne-de-commande-cli)
5.  [Fichiers de configuration](#fichiers-de-configuration)
6.  [Mode Débogage](#mode-débogage)
7.  [Création d'une Release](#création-dune-release)
8.  [Licence](#licence)

---

## Fonctionnalités

*   **Interface Graphique Complète** : Une application de bureau (`leTruc`) pour Windows, macOS et Linux qui contrôle l'ensemble du processus de manière intuitive.
*   **Génération de PDF Multi-pages** :
    *   Crée un agenda détaillé sur deux pages avec une taille de police qui s'adapte automatiquement au contenu.
    *   Génère un poster A4 sur une troisième page, parfait pour l'affichage.
*   **Export d'Images pour les Réseaux Sociaux** :
    *   Crée des images au format vertical (1080x1920) pour les "Stories" Instagram, avec une personnalisation complète (police, couleurs, image de fond, etc.).
*   **Export SVG Éditable** :
    *   Génère des fichiers SVG pour chaque page, idéaux pour des retouches dans des logiciels comme Inkscape.
*   **Personnalisation Avancée** :
    *   Contrôle total sur la mise en page (marges, polices, couleurs).
    *   Mise en page des logos intelligente avec un algorithme de *packing*.
    *   Ajout de contenu personnalisé via la boîte "Cucaracha".
*   **Retour Utilisateur en Temps Réel** : Une barre de progression et des messages de statut clairs informent l'utilisateur de l'avancement du processus.

---

## Structure du projet

La structure a été refactorée pour une meilleure séparation des responsabilités.

```
bidul/
├── biduleur/                    # Module 1 : Parse les données XLS/CSV en HTML.
│   ├── main.py                  # Point d'entrée CLI du biduleur.
│   ├── cli.py                   # CLI d’ingestion
│   ├── csv_utils.py
│   ├── format_utils.py
│   ├── constants.py
│   ├── event_utils.py
│   └── requirements.txt
├── misenpageur/                 # Module 2 : Met en page le HTML en PDF, SVG, PNG.
│   ├── main.py                  # Point d'entrée CLI du misenpageur.
│   ├── config.yml               # Configuration principale de la mise en page.
│   ├── layout.yml               # Structure géométrique des pages.
│   ├── logger.py                # Module de logging partagé.
│   ├── requirements.txt         # Requirements du module.
│   ├── assets/
│   │   ├── biduleur.html        # HTML source (exemple)
│   │   ├── cover.jpg
│   │   ├── ours.md
│   │   ├── logos/
│   │   │   └── *.png|jpg
│   └── misenpageur/
│       ├── __init__.py
│       ├── layout_builder.py    # <-- NOUVEAU : Applique les marges au layout
│       ├── config.py
│       ├── layout.py
│       ├── layout_builder.py
│       ├── html_utils.py
│       ├── image_builder.py
│       ├── drawing.py
│       ├── draw_logic.py
│       ├── textflow.py
│       ├── pdfbuild.py
│       ├── svgbuild.py
│       ├── glyphs.py
│       └── fonts.py
├── leTruc/                      # Module 3 : L'interface graphique (GUI) qui orchestre tout.
│   ├── main.py                  # Point d'entrée pour lancer l'interface.
│   ├── app.py                   # Classe principale de l'application.
│   ├── widgets.py               # Création des éléments visuels.
│   ├── callbacks.py             # Logique des actions de l'interface.
│   ├── _helpers.py              # Fonctions utilitaires du GUI.
│   └── assets/                  # Icônes, etc.
├── run_gui.py                   # Script simple pour lancer l'interface graphique.
├── requirements.txt
└── ...
```

---

## Installation

1.  **Créez un environnement virtuel :**
    ```bash
    python -m venv .venv
    ```
2.  **Activez-le :**
    *   Windows : `.venv\Scripts\activate`
    *   macOS/Linux : `source .venv/bin/activate`
3.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

---

## Utilisation

### Lancement de l'Interface Graphique (GUI)

C'est la méthode recommandée pour la plupart des utilisateurs. Exécutez simplement le script `run_gui.py` à la racine du projet.

```bash
python run_gui.py
```

### Utilisation en Ligne de Commande (CLI)

Pour les utilisateurs avancés ou pour l'intégration dans des scripts, chaque module peut être utilisé indépendamment.

#### 1. `biduleur` (XLS/CSV → HTML)

```bash
# Affiche l'aide
python -m biduleur.main --help

# Exemple d'utilisation avec logs
python -m biduleur.main "chemin/vers/entree.xlsx" --verbose
```

#### 2. `misenpageur` (HTML → PDF/SVG/PNG)

```bash
# Affiche l'aide
python -m misenpageur.main --help

# Exemple de génération d'un PDF et de stories, avec logs
python -m misenpageur.main --out "sortie.pdf" --stories --verbose
```

---

## Fichiers de configuration

## Fichiers de configuration

La puissance et la flexibilité de `misenpageur` reposent sur deux fichiers de configuration principaux au format YAML, situés dans le dossier `misenpageur/`.

### `misenpageur/config.yml`

Ce fichier est le **panneau de contrôle principal** de la mise en page. Il vous permet de personnaliser presque tous les aspects du document final sans toucher au code.

```yaml
# =========================
# Configuration mensuelle
# =========================
# Chemins vers les fichiers sources et de sortie.
# Ces valeurs sont souvent surchargées par l'interface graphique.
input_html: "misenpageur/fichier_biduleur/biduleur_bullets.html"
output_pdf: "misenpageur/bidul/bidul_prototype.pdf"
logos_dir: "misenpageur/assets/logos"
cover_image: "misenpageur/assets/couv/couverture.png"

# =========================
# Paramètres typographiques
# =========================
# Police principale pour le corps de l'agenda (pages 1 et 2).
font_name: "Arial Narrow"
# Plage de tailles de police pour l'ajustement automatique.
font_size_min: 5
font_size_max: 30.0
# Mode de taille de police : 'auto' (par défaut) ou 'force' pour utiliser une valeur fixe.
font_size_mode: auto
font_size_forced: 7.9
# Interligne (leading = font_size * leading_ratio).
leading_ratio: 1.12

# =========================
# Répartition du texte et Espacements
# =========================
# Espacement en points avant et après les dates et les événements.
date_spaceBefore: 4
date_spaceAfter: 4
# Style des puces pour les événements.
show_event_bullet: true
event_hanging_indent: 13
# Style des séparateurs de dates ('box', 'ligne' ou 'aucun').
date_line:
  enabled: true
  width: 1.5
  color: "#000000"

# =========================
# Layout et Sections Spécifiques
# =========================
# Marges globales du document en millimètres.
pdf_layout:
  page_margin_mm: 1

# Configuration de la boîte "Cucaracha" (contenu personnalisé en page 1).
cucaracha_box:
  content_type: "text"  # 'none', 'text', ou 'image'.
  content_value: "Votre texte personnalisé ici"
  text_font_name: "Helvetica"
  text_font_size: 8
  text_style: "italic"   # 'normal' ou 'italic'.
  height_mm: 28

# Configuration du Poster (page 3).
poster:
  enabled: true
  design: 0  # 0: image au centre, 1: image en fond.
  background_image_alpha: 0.75 # Transparence du voile si design=1.
  title: "le bidul - octobre 2025"
  font_name_title: "DSNetStamped"
  # Couleur de police automatique (passe en blanc sur fond sombre).
  text_color_auto: true
  text_color_dark_bg: "#FFFFFF"

# Stratégie de mise en page optimisée pour les logos.
packing_strategy:
  algorithm: 'Global'
  sort_algo: 'AREA'

# Ajout d'hyperliens cliquables sur les logos.
logo_hyperlinks:
- image: "BlueZinc.png"
  href: "https://www.facebook.com/bluezincbar/?locale=fr_FR"
# ...

# Configuration des images pour les Stories Instagram.
stories:
  enabled: true
  output_dir: "misenpageur/bidul/stories"
  agenda_font_name: "Arial Narrow"
  agenda_font_size: 18
  text_color: "#62d92f"
  background_color: "#000000"
  margin: 25
  line_spacing_ratio: 2.0
```

### `misenpageur/layout.yml`

Ce fichier est le **squelette géométrique** de votre document. Il définit la taille de la page et la position brute de chaque section, comme si le document n'avait aucune marge. Il est rarement nécessaire de le modifier.

**Concept clé :** Ce fichier décrit une grille parfaite sur une page A4. La valeur `pdf_layout.page_margin_mm` de `config.yml` est ensuite utilisée pour "rétrécir" cette grille, créant ainsi les marges finales du document de manière dynamique.

```yaml
# Taille de la page en points (1 pouce = 72 points). 595x842 correspond à une page A4.
page_size:
  width: 595
  height: 842

sections:
  # Chaque section est définie par sa page et ses coordonnées (x, y, largeur, hauteur).
  # L'origine (0,0) est le coin inférieur gauche de la page.

  # --- Page 1 (mise en page A5 plié) ---
  # S1 = Ours + Logos (quart supérieur gauche)
  S1: { page: 1, x: 0,     y: 421, w: 297.5, h: 421 }
  # S2 = Couverture (quart supérieur droit)
  S2: { page: 1, x: 297.5, y: 421, w: 297.5, h: 421 }
  # S3, S4 = Corps de l'agenda
  S3: { page: 1, x: 0,     y: 0,   w: 297.5, h: 421 }
  S4: { page: 1, x: 297.5, y: 0,   w: 297.5, h: 421 }

  # --- Page 2 (corps de l'agenda, suite) ---
  S5: { page: 2, x: 0,     y: 0,   w: 297.5, h: 842 }
  S6: { page: 2, x: 297.5, y: 0,   w: 297.5, h: 842 }

  # --- Page 3 (Poster A4) ---
  # Chaque élément du poster est une section positionnée précisément.
  S7_Title: { page: 3, x: 5, y: 800, w: 585, h: 36 }
  S7_Col1: { page: 3, x: 5, y: 36, w: 194, h: 760 }
  # ... etc.

# Définit comment la section S1 est divisée en deux colonnes (logos et ours).
s1_split:
  logos_ratio: 0.5
```

---

## Mode Débogage

Le mode débogage est un outil puissant pour diagnostiquer des problèmes. Lorsqu'il est activé, il crée un dossier unique et horodaté (ex: `debug_run_2025-10-26_15-30-00`) contenant :
*   `execution.log` : Le journal complet de toutes les opérations.
*   `config.json` : La configuration exacte utilisée pour cette exécution.
*   `summary.info` : Le résumé final du traitement.

**Comment l'activer :**
*   **GUI** : Cochez la case "Activer le mode débogage" en bas de la fenêtre.
*   **CLI** : Ajoutez le drapeau `--debug` à votre commande.
    ```bash
    python -m misenpageur.main --out "sortie.pdf" --debug
    ```

---

## Création d'une Release

Le projet utilise GitHub Actions pour automatiser la création des exécutables pour Windows.

1.  **Déclenchement manuel (pour tester)** : Allez dans l'onglet "Actions" de votre dépôt, sélectionnez le workflow "Build and Release" et lancez-le manuellement sur la branche de votre choix. L'exécutable sera disponible dans les "Artifacts" du run.
2.  **Déclenchement automatique (officiel)** : Créez et poussez un tag Git qui respecte le format `bidul-vX.Y.Z`.
    ```bash
    git tag bidul-v1.3.2
    git push origin bidul-v1.3.2
    ```
    Cette action déclenchera le workflow qui construira l'exécutable et créera une nouvelle Release publique sur GitHub, en y attachant l'archive `.zip`.

---

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.
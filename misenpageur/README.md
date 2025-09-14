# `misenpageur` - Moteur de rendu PDF et SVG

Ce document est destiné aux développeurs et utilisateurs avancés souhaitant comprendre, maintenir ou étendre le module `misenpageur`.

## 1. Objectif du Module

`misenpageur` est un moteur de rendu spécialisé. Sa fonction principale est de prendre un contenu textuel semi-structuré (au format HTML), une configuration de style (`config.yml`) et un plan de mise en page géométrique (`layout.yml`) pour produire deux types de documents :

1.  Un **document PDF** de plusieurs pages (un agenda et un poster) prêt pour l'impression.
2.  Des **fichiers SVG** éditables (un par page), parfaits pour être modifiés dans des logiciels de dessin vectoriel comme Inkscape.

Il est conçu pour être le "back-end" de rendu du projet "Biduleur".

## 2. Concepts Fondamentaux et Architecture

L'architecture repose sur une séparation stricte des responsabilités :

-   **Le Contenu (`input.html`, `ours.md`, `nobr.txt`)** : Fournit les données brutes.
-   **La Géométrie (`layout.yml`)** : Définit la position et la taille de chaque "boîte" (section) sur chaque page.
-   **Le Style et le Comportement (`config.yml`)** : Contrôle tous les aspects visuels et algorithmiques.

### L'Architecture de Rendu Partagé

Pour éviter la duplication de code entre les générateurs PDF et SVG, le module est architecturé comme suit :

-   **`draw_logic.py` (Le Cerveau)** : Contient la logique de dessin principale (`draw_document`), agnostique au format de sortie.
-   **`pdfbuild.py` (Wrapper PDF)** : Crée un `canvas` PDF et appelle `draw_document`.
-   **`svgbuild.py` (Wrapper SVG)** : Appelle `pdfbuild` pour créer un PDF temporaire, le convertit avec `pdf2svg`, et post-traite le SVG pour corriger les glyphes.

## 3. Fichiers de Configuration Détaillés

### 3.1. `layout.yml`

Ce fichier définit la **géométrie brute** de toutes les boîtes sur toutes les pages. Les unités sont en **points** (`pt`), et l'origine `(0,0)` est en **bas à gauche**.

```yaml
page_size:
  width: 595  # Largeur totale de la page (A4 = 595.27 pt)
  height: 842 # Hauteur totale de la page (A4 = 841.89 pt)

sections:
  # Chaque clé est un identifiant unique pour une section.
  # Le layout_builder modifiera ces coordonnées pour les pages 1 et 2
  # en fonction des marges de config.yml.
  S1: { page: 1, x: 0,     y: 421, w: 297.5, h: 421 }
  S2: { page: 1, x: 297.5, y: 421, w: 297.5, h: 421 }
  # ...
  # Les sections pour le poster (page 3) sont aussi définies ici.
  S7_Title: { page: 3, x: 20, y: 800, w: 555, h: 30 }
  # ...

s1_split:
  # Ratio (entre 0 et 1) pour la division de la section S1
  # entre la colonne des logos et celle de l'ours.
  logos_ratio: 0.5
```

### 3.2. `config.yml`

Ce fichier contrôle **tout le reste**. Voici les clés les plus importantes :

#### Chemins (`input_html`, `cover_image`, etc.)
Chemins relatifs au dossier contenant `config.yml` pour les fichiers d'entrée et les assets.

#### Typographie (`font_name`, `font_size_min`, `font_size_max`, `leading_ratio`)
-   `font_name`: Police principale pour le corps du texte.
-   `font_size_min`/`max`: Plage de tailles autorisée pour l'algorithme d'ajustement automatique.
-   `leading_ratio`: Interlignage (ex: `1.12` = 112% de la taille de la police).

#### Mise en page (`pdf_layout`)
-   `page_margin_mm`: Marge globale appliquée aux pages 1 et 2.
-   `section_spacing_mm`: Espace (gouttière) entre les sections des pages 1 et 2.

#### Puces et Événements (`event_hanging_indent`, `bullet_text_indent`, etc.)
-   `event_hanging_indent`: Marge gauche totale pour les paragraphes d'événement.
-   `bullet_text_indent`: Position de la puce par rapport au début du texte (une valeur négative la place à gauche).

#### Séparateurs de dates (`date_line`, `date_box`, `date_spaceBefore`/`After`)
-   `date_line`: Active et configure une ligne horizontale après les dates.
-   `date_box`: Active et configure un cadre autour des dates.
-   `date_spaceBefore`/`After`: Espace vertical (en points) ajouté avant et après chaque date sur les pages 1 et 2.

#### Boîte "Cucaracha" (`cucaracha_box`)
Configure la boîte spéciale en bas de la colonne des logos (page 1).
-   `content_type`: "none", "text", ou "image".
-   `content_value`: Le texte ou le chemin de l'image.
-   `height_mm`: Hauteur de la boîte si elle est active.
-   ... et d'autres options de style.

#### Poster (Page 3) (`poster`)
-   `enabled`: `true` pour générer la page 3.
-   `design`: `0` (image au centre) ou `1` (image en fond).
-   `title`: Titre du poster.
-   `font_size_safety_factor`: Facteur de réduction (ex: `0.98` = -2%) appliqué à la taille de police calculée pour éviter que le texte ne déborde.
-   `background_image_alpha`: Niveau de transparence du voile blanc sur l'image de fond (design 1).
-   `date_spaceBefore`/`After`: Espacement vertical spécifique pour les dates sur le poster.

## 4. L'Algorithme de Génération (`draw_document`)

La fonction `draw_document` dans `draw_logic.py` est le cœur du module.
*(Cette section reste la même que dans le README précédent)*

### Phase 1 : Initialisation et Configuration
...
### Phase 2 : Planification du Texte (Pages 1 & 2)
...
### Phase 3 : Rendu (Dessin sur le Canvas)
...

## 5. Structure des Fichiers Clés

*(Cette section reste la même que dans le README précédent)*

-   `draw_logic.py`: **Le Cerveau**.
-   `pdfbuild.py`: **Wrapper PDF**.
-   `svgbuild.py`: **Wrapper SVG**.
-   ...

## 6. Dépendances Clés

-   **Bibliothèques Python** : `reportlab`, `pyyaml`, `Pillow`, `qrcode`, `lxml`.
-   **Programme Externe** : **`pdf2svg`** (version open-source) est requis pour l'export SVG.
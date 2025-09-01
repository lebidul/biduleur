Voici une version mise à jour de `README.md` que tu peux coller telle quelle.

---

# misenpageur — Génération PDF “Bidul” (A4 recto/verso)

Automatise la mise en page mensuelle d’un **A4 recto/verso** découpé en sections, à partir d’un **HTML d’entrée**, d’un **layout YAML** et d’actifs (logos, couverture, ours).

## Vue d’ensemble

* **Page 1 (haut)**
  **S1** : mosaïque de logos (gauche) + **ours** (droite, centré, top-align).
  **S2** : image de couverture **clippée** au cadre (mode *cover*, sans débordement).

* **Page 1 (bas) & Page 2 (colonnes)**
  Texte issu de `biduleur.html` réparti **dans cet ordre** : **S5 → S6 → S3 → S4**.

  * **Taille de police commune** pour **S3–S6** (recherche binaire), **justifiée**, top-align strict.
  * **Césure contrôlée** autorisée uniquement **S5→S6** et **S3→S4** (jamais **S6→S3**).
  * Césure appliquée **seulement si le gain est significatif** (paramétrable).

* **Robustesse HTML**

  * Préserve `<b>`, `<i>`, `<br/>` ; répare les fermetures imbriquées malformées.
  * Supprime les `<br/>` parasites en tête/queue des paragraphes.
  * Support du symbole **€** via fallback **DejaVuSans** si nécessaire.

---

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install reportlab pyyaml
```

> Arial Narrow : sur Windows, la fonte est généralement disponible (`C:\Windows\Fonts\ARIALN*.TTF`).
> À défaut, le rendu bascule sur **Helvetica** ; les glyphes manquants (dont **€**) utilisent **DejaVuSans** si présent.

---

## Utilisation

### Lancer la génération

```bash
python misenpageur\main.py --root . --config config.yml --layout layout.yml --out output\bidul.pdf
```

**Options**

* `--root` : racine du projet (par défaut `.`)
* `--config` : chemin du fichier de config (défaut `config.yml`)
* `--layout` : chemin du fichier layout (défaut `layout.yml`)
* `--out` : PDF de sortie (sinon `output_pdf` défini dans la config)

---

## Configuration

### `config.yml` (exemple)

```yaml
# fichiers d'entrée (relatifs à --root sauf chemins absolus)
input_html: assets/biduleur.html
ours_md:    assets/ours.md
logos_dir:  assets/logos
cover_image: assets/cover.jpg

# typographie & mise en page (S3–S6)
font_name: "Arial Narrow"      # sinon Helvetica (fallback)
font_size_min: 9.0
font_size_max: 10.0
leading_ratio: 1.2             # interlignage = font_size * ratio
inner_padding: 2               # marge interne de chaque section (en pt)

# césure "utile" entre colonnes (A->B : S5→S6 et S3→S4)
# n'autoriser la césure que si elle comble au moins 10% de la hauteur de la section A
# (et au moins ~1 interligne). Ajustable.
split_min_gain_ratio: 0.10

# sortie
output_pdf: output/bidul.pdf
```

### `layout.yml` (exemple A4 sans marges)

```yaml
page_size: { width: 595, height: 842 }   # A4 en points (72 dpi)

sections:
  # PAGE 1 (2x2)
  S1: { page: 1, x: 0,     y: 421, w: 297.5, h: 421 }
  S2: { page: 1, x: 297.5, y: 421, w: 297.5, h: 421 }
  S3: { page: 1, x: 0,     y: 0,   w: 297.5, h: 421 }
  S4: { page: 1, x: 297.5, y: 0,   w: 297.5, h: 421 }

  # PAGE 2 (2 colonnes pleine hauteur)
  S5: { page: 2, x: 0,     y: 0,   w: 297.5, h: 842 }
  S6: { page: 2, x: 297.5, y: 0,   w: 297.5, h: 842 }

# découpe interne de S1 (ratio horizontal logos/ours)
s1_split: { logos_ratio: 0.60 }  # le reste pour l'ours
```

---

## Fonctionnement interne (résumé)

* **Lecture HTML** → extraction de paragraphes, réparation `<b>/<i>`, normalisation `<br/>`, suppression retours parasites.
* **Calcul taille commune** `fs_common` (S3–S6) par **recherche binaire** pour que tout le texte rentre dans l’ordre **S5,S6,S3,S4**.
* **Planification par paires** avec césure **A→B** (S5→S6, S3→S4) **si** le *gain* ≥ `split_min_gain_ratio` (et ≥ \~1 ligne).
* **Rendu top-align strict** sans `KeepInFrame` pour **S3–S6** (dessin manuel paragraphe par paragraphe).
* **S1** : grille logos top-align (2 colonnes × *n* lignes), **ours** centré **et** collé en haut (top-align manuel).
* **S2** : couverture *cover* **clippée** au cadre (zéro chevauchement).

---

## Structure du projet (référence)

```
misenpageur/
  main.py                 # point d’entrée CLI
  config.yml              # configuration mensuelle (exemple)
  layout.yml              # placement des sections (exemple)
  assets/
    biduleur.html         # source HTML (exemple)
    cover.jpg
    ours.md
    logos/
      *.png|jpg...
  output/
    bidul.pdf             # PDF généré
  misenpageur/
    __init__.py
    config.py             # lecture config.yml
    layout.py             # lecture layout.yml
    html_utils.py         # parsing/sanitization HTML
    drawing.py            # S1/S2 + styles + utilitaires
    textflow.py           # fitting, césure A→B, rendu top-align
    pdfbuild.py           # orchestration
```

---

## Variante InDesign (optionnelle)

Un flux ExtendScript peut piloter un `.indd` avec des cadres nommés (`S1_LOGOS`, `S1_OURS`, `S2_COVER`, `S5`, `S6`, `S3`, `S4`) : injection du texte HTML, chaînage **S5→S6→S3→S4**, ajustement de corps jusqu’à disparition du surdébordement, placement des logos et de l’ours.

> Si besoin, on peut fournir un `indesign_flow.jsx` adapté à votre gabarit.

---

## Conseils & Dépannage

* **Arial Narrow non trouvée** : message `[WARN] Arial Narrow introuvable - fallback Helvetica.`
  → installe la police ou place `ARIALN*.TTF` dans `assets/fonts/` (si supporté), sinon reste en Helvetica.

* **Symbole € manquant** : ajouté via **DejaVuSans** si présent.
  → Installer DejaVu (ou modifier `fonts.py` pour ajouter un fallback personnel).

* **Blanc en tête de S5/S6** : le moteur supprime les `<br/>` initiaux et rend en top-align **strict**.
  Si tu constates encore un cas particulier, vérifie la première ligne HTML (caractères invisibles).

* **Texte qui reste à placer** : baisse `font_size_max` ou augmente la hauteur des sections dans `layout.yml`.
  Le seuil `split_min_gain_ratio` peut aussi être réduit pour autoriser plus de césures utiles.

---

## Licence

Projet interne — à adapter selon vos besoins.

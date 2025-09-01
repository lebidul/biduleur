# misenpageur — Automatisation PDF (S1..S8)

Ce projet permet de générer automatiquement le fichier **Bidul** (A4 recto/verso découpé en 8 sections) à partir d’un fichier HTML d’entrée, d’un gabarit de mise en page et d’actifs (logos, couverture, ours).

## Fonctionnalités
- **S1** : mosaïque de 10 logos (gauche) + texte « ours » (droite).
- **S2** : image de couverture (plein cadre).
- **S5, S7, S6, S8, S3, S4** : flux de texte issu de `biduleur.html`, *justifié*, en *Arial Narrow* (ou fallback).  
  La taille de police est automatiquement réduite si nécessaire pour que tout tienne dans chaque section.
- **Auto-ajustement** par section via `KeepInFrame` (ReportLab).
- **Config YAML** pour les variables mensuelles (logos, ours, couverture, tailles, marges).
- **Layout YAML** pour définir les coordonnées des sections sur l’A4.
- **Variante InDesign** (ExtendScript) incluse : injection du texte et des images dans un `.indd` avec cadres nommés.

## Arborescence
```
misenpageur/
  cli.py                # Entrypoint CLI
  config.yml            # Config du mois
  layout.yml            # Coordonnées sections
  input/                # biduleur.html (source)
  templates/            # gabarit PDF de référence
  assets/               # logos/, ours.md, cover.jpg
  output/               # sorties PDF
  misenpageur/          # package Python
    __init__.py
    config.py           # charge config.yml
    layout.py           # charge layout.yml
    html_utils.py       # parse HTML -> paragraphes
    drawing.py          # rendu S1/S2 et helpers
    textflow.py         # remplissage texte
    pdfbuild.py         # orchestration PDF
  indesign_flow.jsx     # script ExtendScript pour InDesign
```

## Installation
Prérequis Python :
```
pip install reportlab pyyaml
```

## Utilisation (CLI)
```
cd misenpageur
python cli.py --root . --config config.yml --layout layout.yml
```
Options :
- `--root` : racine du projet (par défaut: `.`)
- `--config` : fichier de configuration (défaut: `config.yml`)
- `--layout` : fichier layout (défaut: `layout.yml`)
- `--out` : chemin de sortie PDF (écrase `output_pdf` défini dans config)

Exemple :
```
python cli.py --out output/bidul_prototype.pdf
```

## Utilisation (InDesign)
1. Ouvrez votre document `.indd` avec des cadres nommés :  
   `S1_LOGOS`, `S1_OURS`, `S2_COVER`, `S5`, `S7`, `S6`, `S8`, `S3`, `S4`.
2. Copiez `indesign_flow.jsx` dans le dossier Scripts d’InDesign.
3. Lancez le script depuis le panneau Scripts.
4. Sélectionnez vos fichiers (HTML, logos, couverture).  
   Le script :
   - chaîne automatiquement les cadres S5→S7→S6→S8→S3→S4,  
   - injecte le texte du HTML,  
   - ajuste la taille jusqu’à disparition du surdébordement,  
   - place logos + ours en S1, couverture en S2.

## Roadmap (évolutions possibles)
- **Césure FR** avec *pyphen* pour un meilleur rendu typographique.
- **Recherche binaire** de taille de police par section pour un fitting plus précis.
- **Overlay du gabarit** `bidul_template.pdf` en calque de fond (PyMuPDF).
- **Tests unitaires** (HTML parsing, fitting).
- **Interface web** (Streamlit) pour un usage simplifié.

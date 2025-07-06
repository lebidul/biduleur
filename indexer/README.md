# OCR Pipeline - Bidul

Ce projet est un pipeline modulaire pour l'extraction OCR optimisée à partir de fichiers PDF, combinant plusieurs stratégies afin de maximiser la qualité des résultats.

## 📁 Structure du projet

```
ocr_pipeline/
├── main.py                      ← Script principal d'extraction OCR
├── main_rotate.py               ← Script pour corriger définitivement l'orientation des PDF
└── utils/
    ├── __init__.py              ← Rend utils importable comme package
    ├── pdf_helpers.py           ← Détection de la 3e page à ignorer
    ├── ocr_strategies.py        ← Méthodes OCR + sélection intelligente
    ├── image_processing.py      ← Prétraitement PIL + OpenCV + sélection auto
    └── rotate_pdf.py            ← Détection et application de la meilleure rotation par page
```

## ⚙️ Dépendances requises

Installez les bibliothèques nécessaires avec :

```bash
pip install pytesseract pdf2image langdetect pyspellchecker pymupdf pillow opencv-python
```

> Assurez-vous aussi que **Tesseract OCR** est installé sur votre système, avec les fichiers `fra.traineddata` et `osd.traineddata`.

## 🚀 Lancer le pipeline d'extraction OCR

Depuis le dossier `ocr_pipeline/`, exécutez :

```bash
python main.py
```

Paramètres dans `main.py` :
- `OCR_MODE = "fast"` / `"smart"` / `"opencv"` → contrôle la méthode d'OCR utilisée
- `ROTATION_ENABLED = True` / `False` → active ou désactive la rotation dynamique pendant l'extraction

## 🔁 Lancer la correction des orientations

Pour prétraiter et sauvegarder une version **orientée proprement** de tous les PDF :

```bash
python main_rotate.py
```

Les fichiers corrigés seront enregistrés dans :
```
./indexer/rotated/
```

## 📦 Résultats

Les textes extraits seront sauvegardés dans :
```
./indexer/archives.txt/
```

Et le log d'extraction dans :
```
./indexer/archives.txt/log_extraction.csv
```

## ✨ Prochaine étape

Ce projet est conçu pour être étendu avec :
- Post-correction OCR à partir de dictionnaires
- Analyse automatique des entités : artistes, lieux, spectacles, etc.
- Interface de recherche ou dashboard interactif

---

© Projet Bidul – OCR sur archives culturelles de la Sarthe.

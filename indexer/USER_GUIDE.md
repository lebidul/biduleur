# Indexer - Guide Utilisateur

Guide complet des commandes CLI pour l'indexation des archives du Bidul.

## Installation

```bash
cd indexer
pip install -r requirements.txt
```

Dépendances principales: `PyMuPDF`, `sqlite3` (inclus Python).

Pour l'OCR (PDFs scannés):
```bash
pip install google-cloud-vision pdf2image opencv-python
```

**Note:** L'OCR avec Google Cloud Vision nécessite un fichier de credentials GCP (`gcp_creds_biduleur.json`).

## Démarrage rapide

```bash
# 1. Initialiser la base de données
python cli.py init

# 2. Peupler avec tous les PDFs disponibles
python cli.py populate

# 3. Voir les statistiques
python cli.py stats
```

---

## Commandes de base

### `init` - Initialiser la base

Crée la base de données et charge les référentiels (lieux, villes).

```bash
python cli.py init
```

Sortie:
```
Initialisation de la base: database/bidul_archives.db

Base initialisée:
  Lieux référencés: 543
  Villes référencées: 123
```

### `list` - Lister les PDFs disponibles

```bash
# Tous les PDFs
python cli.py list

# PDFs avec texte natif uniquement
python cli.py list --type texte

# PDFs scannés (nécessitent OCR)
python cli.py list --type scan
```

Sortie:
```
============================================================
PDFs disponibles: 131
============================================================
  [178] 06/2012 - bidul_178_juin_2012.pdf (texte)
  [179] 07/2012 - bidul_179_juillet_2012.pdf (texte)
  ...
```

### `stats` - Statistiques globales

```bash
python cli.py stats
```

Sortie:
```
==================================================
STATISTIQUES BASE DE DONNÉES
==================================================

Biduls:      98
  Plage: 178 - 308

Événements:  7542
  Période: 2012-06-01 - 2024-12-31

Par source:
  csv: 2340
  pdf: 5202

Référentiels:
  Lieux:  543
  Villes: 123

Top 5 villes:
  Le Mans: 5823
  La Flèche: 412
  Allonnes: 287
  ...
```

---

## Extraction et peuplement

### `populate` - Peupler la base

Commande principale pour extraire les événements. Utilise les CSV de référence si disponibles, sinon extrait depuis les PDFs.

```bash
# Peupler tous les Biduls disponibles
python cli.py populate

# Peupler un seul Bidul
python cli.py populate --numero 280

# Peupler une plage
python cli.py populate --range 280-290

# Mode simulation (affiche sans sauvegarder)
python cli.py populate --dry-run

# Remplacer les données existantes
python cli.py populate --numero 280 --replace

# Forcer depuis PDF (ignorer les CSV)
python cli.py populate --pdf-only

# Uniquement les Biduls avec CSV de référence
python cli.py populate --csv-only
```

Options:
| Option | Description |
|--------|-------------|
| `--numero N` | Traiter uniquement le Bidul N |
| `--range N-M` | Traiter les Biduls de N à M |
| `--csv-only` | Uniquement les Biduls avec CSV |
| `--pdf-only` | Ignorer les CSV, forcer extraction PDF |
| `--dry-run` | Simulation sans sauvegarde |
| `--replace` | Remplacer les données existantes |
| `--no-ocr` | Désactiver l'OCR pour les scans |
| `--engine` | Moteur OCR: `google` (défaut), `paddleocr`, `easyocr` |
| `--dpi` | Résolution OCR (défaut: 200) |

### `extract` - Extraire un PDF

Extraction directe d'un PDF (sans priorité CSV).

```bash
# Extraire un Bidul
python cli.py extract --numero 280

# Extraire une plage
python cli.py extract --range 280-290

# Mode simulation
python cli.py extract --numero 280 --dry-run

# Forcer extraction d'un scan
python cli.py extract --numero 150 --force
```

---

## Commandes OCR

### `ocr` - Extraire le texte d'un PDF scanné

Extrait le texte d'un PDF scanné via OCR.

```bash
# Extraction avec Google Cloud Vision (recommandé)
python cli.py ocr "archives/2011-07 Bidul 158.pdf" --engine google -o output.txt

# Extraction avec PaddleOCR (local, gratuit)
python cli.py ocr "archives/2011-07 Bidul 158.pdf" --engine paddleocr

# Sans post-traitement
python cli.py ocr "archives/bidul_158.pdf" --raw
```

Options:
| Option | Description |
|--------|-------------|
| `--engine` | Moteur: `google`, `paddleocr`, `easyocr` |
| `--dpi` | Résolution de conversion (défaut: 200) |
| `--output` | Fichier de sortie pour le texte |
| `--raw` | Ne pas appliquer le post-traitement |

### `ocr-extract` - OCR + parsing des événements

Extrait le texte via OCR et parse les événements en une seule commande.

```bash
# Un seul Bidul
python cli.py ocr-extract --numero 158 --dry-run

# Plage de Biduls
python cli.py ocr-extract --range 150-160

# Avec moteur spécifique
python cli.py ocr-extract --numero 158 --engine paddleocr
```

Options:
| Option | Description |
|--------|-------------|
| `--numero N` | Traiter le Bidul N |
| `--range N-M` | Traiter les Biduls de N à M |
| `--engine` | Moteur OCR (défaut: `google`) |
| `--dpi` | Résolution (défaut: 200) |
| `--dry-run` | Simulation sans sauvegarde |

### `ocr-test` - Tester l'OCR

Teste l'OCR sur un échantillon de PDFs scannés.

```bash
python cli.py ocr-test --samples 5
```

---

## Validation et comparaison

### `validate` - Afficher une extraction

Affiche les événements extraits pour un Bidul.

```bash
python cli.py validate --numero 280
```

Sortie:
```
============================================================
BIDUL #280 - 5/2023
Fichier: bidul_280_mai_2023.pdf
Type: texte
Statut: extracted
============================================================

42 événements extraits:

[1] 2023-05-03 - 21h
    Artistes: MOONLIGHT BENJAMIN
    Lieu: La Fonderie, Le Mans
    Prix: 12€
    Type: concert | Confidence: 0.95
    Raw: Ve 3 • MOONLIGHT BENJAMIN (blues-soul)...

[2] 2023-05-04 - 20h30
    Spectacles: Ma tata, mon pingouin...
    Lieu: Théâtre Paul Scarron, Le Mans
    ...
```

### `compare` - Comparer avec CSV de référence

Compare l'extraction avec le fichier CSV source (si disponible).

```bash
# Comparaison simple
python cli.py compare --numero 280

# Avec détails des différences
python cli.py compare --numero 280 --details
```

Sortie:
```
======================================================================
COMPARAISON BIDUL #280 - 05/2023
======================================================================
PDF: bidul_280_mai_2023.pdf
CSV: 202305_tapage_biduleur_mai_2023.csv

Événements extraits (base): 42
Événements référence (CSV): 45

======================================================================
RÉSULTATS
======================================================================
Matchés:           40
CSV uniquement:    5 (dans référence mais pas extrait)
Base uniquement:   2 (extrait mais pas dans référence)

Recall:    88.9% (40/45 de la référence trouvés)
Precision: 95.2% (40/42 extraits sont corrects)
```

---

## Gestion des données

### `purge` - Supprimer des événements

```bash
# Supprimer les événements d'un Bidul
python cli.py purge --numero 280

# Supprimer une plage
python cli.py purge --range 280-290

# Supprimer TOUT
python cli.py purge --all

# Mode simulation
python cli.py purge --numero 280 --dry-run
```

---

## Consolidation et qualité

### `migrate` - Migration du schéma

Ajoute les tables pour le système de consolidation (review, corrections, aliases).

```bash
python cli.py migrate
```

### `triage` - Triage automatique

Classe les événements par niveau de confiance.

```bash
python cli.py triage

# Sans détection de doublons
python cli.py triage --skip-duplicates
```

Sortie:
```
Triage automatique des événements...

Résultats du triage:
  OK (confidence >= 0.9):     5234
  À revoir (0.7-0.9):         1856
  Flaggés (< 0.7):            452
  Doublons potentiels:        23

Statut global:
  ok: 5234
  to_review: 1856
  flagged: 452
```

### `apply-aliases` - Appliquer les alias artistes

Normalise les noms d'artistes en utilisant les alias définis.

```bash
# Appliquer les alias existants
python cli.py apply-aliases

# Synchroniser depuis le fichier JSON d'abord
python cli.py apply-aliases --sync-json
```

### `review` - Session de review interactive

Interface en ligne de commande pour vérifier manuellement les événements.

```bash
# Review tous les événements "to_review"
python cli.py review --status to_review

# Review un Bidul spécifique
python cli.py review --numero 280

# Review les événements flaggés
python cli.py review --status flagged
```

Statuts possibles: `pending`, `to_review`, `flagged`, `ok`

### `quality-report` - Rapport de qualité

Génère un rapport détaillé sur la qualité des données.

```bash
python cli.py quality-report
```

Sortie:
```
============================================================
RAPPORT DE QUALITÉ
============================================================

Total événements: 7542

Par statut de review:
  ok: 5234 (69.4%)
  to_review: 1856 (24.6%)
  flagged: 452 (6.0%)

Vérifiés: 3421 (45.4%)

Distribution de confidence:
  0.9+: 5234 (69.4%)
  0.8-0.9: 1234 (16.4%)
  0.7-0.8: 622 (8.2%)
  0.5-0.7: 320 (4.2%)
  <0.5: 132 (1.8%)

Champs manquants:
  Sans date: 45
  Sans lieu: 123
  Sans artiste/spectacle: 89
  Lieux non résolus: 234
```

### `analyze-corrections` - Analyser les corrections

Affiche les patterns de correction pour améliorer l'extraction.

```bash
python cli.py analyze-corrections
```

---

## Options globales

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Mode verbeux (affiche les logs DEBUG) |

---

## Exemples de workflows

### Workflow complet pour un nouveau Bidul

```bash
# 1. Extraire
python cli.py populate --numero 308

# 2. Vérifier
python cli.py validate --numero 308

# 3. Comparer (si CSV disponible)
python cli.py compare --numero 308 --details

# 4. Trier
python cli.py triage

# 5. Vérifier la qualité
python cli.py quality-report
```

### Réindexer tous les PDFs

```bash
# Purger et repeupler
python cli.py purge --all
python cli.py init
python cli.py populate
python cli.py stats
```

### Vérifier les événements problématiques

```bash
# Voir les événements à faible confiance
python cli.py review --status flagged

# Ou lancer le triage d'abord
python cli.py triage
python cli.py quality-report
```

---

## Structure des fichiers

```
indexer/
├── cli.py                 # Point d'entrée CLI
├── archives/              # PDFs sources
│   └── bidul_XXX_*.pdf
├── corpus/                # Référentiels
│   ├── lieu.csv
│   ├── ville.csv
│   └── artistes_aliases.json
├── database/
│   ├── schema_v2.sql      # Schéma SQL
│   └── bidul_archives.db  # Base SQLite
├── core/                  # Modules principaux
│   ├── extractor.py
│   ├── parser.py
│   ├── db.py
│   └── ...
└── benchmark/             # Tests de qualité
    ├── compare_bidul.py       # Benchmark générique
    ├── compare_bidul_184.py   # Benchmark Bidul 184
    ├── bidul_184_expected.csv # Référence Bidul 184
    └── bidul_190_expected.csv # Référence Bidul 190
```

---

## Dépannage

### "PDF non trouvé"
Vérifiez que le PDF est dans `archives/` avec le bon format de nom:
`bidul_XXX_mois_YYYY.pdf`

### "PDF scan détecté"
Les PDFs avant le n°178 sont des scans. Utilisez `--force` ou convertissez-les en PDF texte avec OCR.

### "Lieu non résolu"
Ajoutez le lieu dans `corpus/lieu.csv`:
```csv
nom,ville
Nouveau Lieu,Le Mans
```
Puis rechargez: `python cli.py init`

### "Confidence faible"
Vérifiez le texte brut avec `validate` puis corrigez le parsing ou ajoutez le lieu/ville au référentiel.

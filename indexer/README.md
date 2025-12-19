# Indexer - Extraction des archives du Bidul

Pipeline d'extraction d'événements culturels depuis les 308 PDFs archivés du fanzine "Le Bidul" (1997-2024).

## Structure

```
indexer/
├── cli.py              # CLI principal
├── core/               # Modules du pipeline
│   ├── extractor.py    # Extraction texte PDF (PyMuPDF)
│   ├── parser.py       # Parsing événements (regex)
│   ├── db.py           # Gestionnaire SQLite
│   └── csv_importer.py # Import CSV (tapages)
├── corpus/             # Référentiels
│   ├── lieu.csv        # 540 lieux connus
│   └── ville.csv       # 123 villes
├── database/
│   ├── schema_v2.sql   # Schéma SQLite
│   └── bidul_archives.db  # Base de données (généré)
└── archives/           # PDFs sources (non versionné)
```

## Installation

```bash
pip install PyMuPDF
```

## Commandes CLI

```bash
# Initialiser la base
python cli.py init

# Peupler avec CSV prioritaire, sinon PDF
python cli.py populate --range 280-308

# Extraire uniquement depuis PDF
python cli.py extract --numero 280

# Valider une extraction
python cli.py validate --numero 280

# Comparer avec CSV de référence
python cli.py compare --numero 280 --details

# Statistiques
python cli.py stats

# Lister les PDFs
python cli.py list --type texte

# Purger la base
python cli.py purge --all
python cli.py purge --range 280-290
```

## Pipeline

1. **Source CSV prioritaire** : Si un CSV existe dans `biduleur/tapages/toBeConverted/`, import direct (confidence=1.0)
2. **Extraction PDF** : Sinon, extraction du texte via PyMuPDF avec détection de colonnes
3. **Parsing** : Découpage par dates, puis par bullets, extraction artistes/lieux/prix
4. **Stockage** : SQLite avec référentiels lieu/ville pour normalisation

## Types de PDFs

- **Texte natif** (n° >= 178) : Extraction directe, ~100-200 événements/mois
- **Scans** (n° < 178) : OCR requis (non implémenté)

## Schéma base de données

- `bidul` : Métadonnées des exemplaires (numero, mois, année, statut)
- `evenement` : Événements extraits (date, artistes, lieu, prix, confidence)
- `lieu_ref` / `ville_ref` : Référentiels pour normalisation

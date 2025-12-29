# Indexer - Contexte du projet

## Objectif

Extraction et indexation des événements culturels depuis les archives PDF du fanzine **Le Bidul** (agenda culturel de la Sarthe, France).

## Périmètre

- **308 numéros** du Bidul (1997-2025)
- **PDFs texte** (178-308) : extraction directe du texte via PyMuPDF
- **PDFs scans** (1-177) : extraction via OCR (Google Cloud Vision, PaddleOCR, EasyOCR)

## Sources de données

| Source | Numéros | Confidence | Description |
|--------|---------|------------|-------------|
| CSV | 2022-2025 | 1.0 | Données saisies manuellement (source de vérité) |
| PDF | 178-308 | 0.4-0.9 | Extraction automatique PyMuPDF + parsing regex |
| OCR | 1-177 | 0.7-0.9 | Extraction via OCR (scans) + parsing regex |

Les CSV sont prioritaires : si un CSV existe pour un mois donné, il remplace l'extraction PDF.

## Structure de la base

```
bidul (122 entrées)
├── numero (PK)
├── mois, annee
├── pdf_filename
└── type_source (scan/texte)

evenement (~14500 entrées)
├── bidul_numero (FK)
├── date_evenement, heure
├── lieu_raw, ville_raw
├── artistes (JSON array)
├── spectacles (JSON array)
├── genres_raw (JSON array)
├── tarif_raw, prix_min, prix_max, gratuit
├── type_evenement (concert, spectacle vivant, etc.)
├── source (csv/pdf)
└── confidence (0.0-1.0)
```

## Mapping Bidul <-> Date

Référence : **Bidul 280 = Mai 2023**

```python
numero = 280 + (annee - 2023) * 12 + (mois - 5)
```

Exemples :
- Bidul 268 = Mai 2022
- Bidul 292 = Mai 2024
- Bidul 308 = Septembre 2025

## Commandes CLI

```bash
# Initialisation
python cli.py init

# Extraction PDF uniquement
python cli.py extract --numero 280
python cli.py extract --range 178-308

# Peuplement intelligent (CSV prioritaire, PDF/OCR fallback)
python cli.py populate --range 178-308
python cli.py populate --csv-only    # Uniquement si CSV disponible
python cli.py populate --pdf-only    # Forcer extraction PDF
python cli.py populate --replace     # Remplacer les événements existants
python cli.py populate --no-ocr      # Désactiver OCR pour les scans
python cli.py populate --engine google  # Moteur OCR (google, paddleocr, easyocr)

# OCR (PDFs scannés)
python cli.py ocr "archives/bidul_158.pdf" --engine google -o output.txt
python cli.py ocr-extract --numero 158 --dry-run
python cli.py ocr-extract --range 150-160

# Purge
python cli.py purge --numero 280     # Purger un Bidul
python cli.py purge --range 178-308  # Purger une plage
python cli.py purge --all            # Purger toute la base

# Validation
python cli.py validate --numero 280
python cli.py compare --numero 280 --details

# Statistiques
python cli.py stats                  # Stats étendues (sources, types, top lieux/villes)
python cli.py list --type texte
python cli.py list --type scan       # Lister PDFs scannés
```

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `core/extractor.py` | Extraction texte PDF (PyMuPDF) + config pages |
| `core/ocr.py` | Extraction OCR pour PDFs scannés (Google Vision, PaddleOCR, EasyOCR) |
| `core/ocr_postprocess.py` | Post-traitement texte OCR (corrections, normalisation) |
| `core/parser.py` | Parsing événements (regex, formats standard, inline, par bloc) |
| `core/csv_importer.py` | Import depuis CSV tapages |
| `core/normalizer.py` | Normalisation automatique lieux/villes/artistes (v1.5) |
| `core/db.py` | Accès base SQLite |
| `database/schema_v2.sql` | Schéma de la base |
| `database/queries_analytiques.sql` | Requêtes SQL d'analyse |
| `corpus/lieu.csv` | Référentiel des lieux |
| `corpus/ville.csv` | Référentiel des villes |
| `corpus/biduls.description.csv` | Configuration extraction (pages utiles, scan/texte, format date) |

## Dépendances CSV

Les CSV source sont dans `biduleur/tapages/toBeConverted/` (non versionnés).

Formats de nommage :
- `202305_tapage_biduleur_mai_2023.csv` (2023+)
- `tapage_biduleur_mai_2022.csv` (2022)

## Configuration extraction

Le fichier `corpus/biduls.description.csv` configure l'extraction par numéro :

| Colonne | Description |
|---------|-------------|
| `numéros` | Numéro du Bidul |
| `scan/texte` | Type de PDF (`scan` ou `texte`) |
| `pages utiles` | Pages à extraire (ex: `2`, `2-4`) |
| `date` | Format de date (`inline` ou `par bloc`) |

Logique d'extraction :
1. Si `scan/texte` = `scan` → utilise OCR (sauf si `--no-ocr`)
2. Si page 3 existe → utiliser page 3 (agenda complet)
3. Sinon → utiliser `pages utiles` du CSV

## Architecture OCR

```
PDF Scan
    │
    ▼
┌─────────────────┐
│  ScanExtractor  │  ← Conversion PDF → images (pdf2image)
│   (ocr.py)      │    OCR via Google Cloud Vision / PaddleOCR / EasyOCR
└────────┬────────┘
         │ texte brut
         ▼
┌─────────────────┐
│ OCRPostProcessor│  ← Corrections OCR (heures, entités, caractères)
│(ocr_postprocess)│    Fuzzy matching sur lieux/villes connus
└────────┬────────┘
         │ texte nettoyé
         ▼
┌─────────────────┐
│   EventParser   │  ← Parsing selon date_format (inline/par bloc)
│   (parser.py)   │
└─────────────────┘
```

### Moteurs OCR

| Moteur | Vitesse | Qualité | Coût |
|--------|---------|---------|------|
| `google` | ~50s/PDF | Excellente | Cloud API |
| `paddleocr` | ~135s/PDF | Bonne | Local/gratuit |
| `easyocr` | ~200s/PDF | Moyenne | Local/gratuit |

### Configuration Google Cloud Vision

Fichier de credentials : `gcp_creds_biduleur.json` à la racine du projet.

## Formats de parsing

| Format | Exemple | Biduls |
|--------|---------|--------|
| Standard | `• Date\n  ARTISTE, Lieu` | 200+ |
| Inline | `Je 02 : ARTISTE, Lieu` | 178-199, certains scans |
| Par bloc | `Jeudi 2\n• ARTISTE, Lieu` | Certains scans |

Le format est spécifié dans `biduls.description.csv` (colonne `date`). Si non spécifié, le parser tente le format standard, puis inline.

## Extraction des spectacles formatés (v1.4)

Le parser supporte plusieurs patterns de spectacles avec guillemets et balises :

| Pattern | Format | Exemple |
|---------|--------|---------|
| Standard | `<b>"Spectacle"</b>` | Guillemets à l'intérieur du gras |
| Pattern 1b | `"<b>Spectacle</b>" (<i>style</i>)` | Guillemets autour du gras + style |
| Pattern 1c | `"<b>Spectacle</b>" Cie XXX (<i>style</i>)` | Spectacle + Cie artiste + style |

**Caractères unicode supportés :**
- Guillemets typographiques : `"` (U+201C), `"` (U+201D), `«`, `»`, `„`
- Apostrophe curly : `'` (U+2019) dans les noms de Cie
- Patterns OCR : `<<...>`, `<...">` pour guillemets mal reconnus

## Normalisation automatique (v1.5)

Le système de normalisation applique automatiquement des règles de matching :

| Règle | Description | Exemple |
|-------|-------------|---------|
| Case-insensitive | Ignore la casse | `bar le lézard` → `Bar le Lézard` |
| Accent-insensitive | Ignore les accents | `theatre` → `Théâtre` |
| Séparateurs | `-` et ` ` interchangeables | `pop-rock` ↔ `pop rock` |
| Préfixes | `le`, `la`, `l'` optionnels | `le barouf` → `Bar Le Barouf` |
| Abbreviations | Expansion automatique | `th.` → `Théâtre`, `st` → `Saint` |

**Impact** : Réduction de 593 aliases manuels dans les CSV.

## Limitations actuelles

1. **OCR** : Qualité variable selon l'état des scans (anciens numéros)
2. **Parsing** : Certains formats d'événements non reconnus (confidence < 0.6)
3. **Événements multi-dates** : Support partiel ("Ve 3-4" → 2 événements)

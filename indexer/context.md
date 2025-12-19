# Indexer - Contexte du projet

## Objectif

Extraction et indexation des événements culturels depuis les archives PDF du fanzine **Le Bidul** (agenda culturel de la Sarthe, France).

## Périmètre

- **308 numéros** du Bidul (1997-2025)
- **PDFs texte** (178-308) : extraction directe du texte
- **PDFs scans** (1-177) : OCR à implémenter (Phase 2)

## Sources de données

| Source | Numéros | Confidence | Description |
|--------|---------|------------|-------------|
| CSV | 2022-2025 | 1.0 | Données saisies manuellement (source de vérité) |
| PDF | 178-308 | 0.4-0.9 | Extraction automatique PyMuPDF + parsing regex |

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

# Peuplement intelligent (CSV prioritaire, PDF fallback)
python cli.py populate --range 178-308
python cli.py populate --csv-only    # Uniquement si CSV disponible
python cli.py populate --pdf-only    # Forcer extraction PDF
python cli.py populate --replace     # Remplacer les événements existants

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
```

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `core/extractor.py` | Extraction texte PDF (PyMuPDF) + config pages |
| `core/parser.py` | Parsing événements (regex, formats standard et inline) |
| `core/csv_importer.py` | Import depuis CSV tapages |
| `core/normalizer.py` | Normalisation lieux/villes |
| `core/db.py` | Accès base SQLite |
| `database/schema_v2.sql` | Schéma de la base |
| `database/queries_analytiques.sql` | Requêtes SQL d'analyse |
| `corpus/lieu.csv` | Référentiel des lieux |
| `corpus/ville.csv` | Référentiel des villes |
| `corpus/biduls.description.csv` | Configuration extraction (pages utiles, scan/texte) |

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

Logique d'extraction :
1. Si `scan/texte` = `scan` → skip (OCR nécessaire)
2. Si page 3 existe → utiliser page 3 (agenda complet)
3. Sinon → utiliser `pages utiles` du CSV

## Formats de parsing

| Format | Exemple | Biduls |
|--------|---------|--------|
| Standard | `• Date\n  ARTISTE, Lieu` | 200+ |
| Inline | `Je 02 : ARTISTE, Lieu` | 178-199 |

Le parser tente le format standard, puis inline si aucun événement trouvé.

## Limitations actuelles

1. **PDFs scans (1-177)** : Non indexés, nécessitent OCR
2. **Parsing** : Certains formats d'événements non reconnus (confidence < 0.6)
3. **Normalisation** : Lieux/villes non systématiquement liés aux référentiels

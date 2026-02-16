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

## Structure de la base (Schema V3)

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
├── tarif_raw, prix_min, prix_max, gratuit
├── type_evenement (concert, spectacle vivant, etc.)
├── genre_evenement
├── source (csv/pdf)
└── confidence (0.0-1.0)

contenu_evenement (source de vérité pour artistes/spectacles)
├── evenement_id (FK)
├── artiste
├── nom_spectacle
├── style
└── ordre
```

**Note v1.6** : Les colonnes JSON redondantes (`artistes`, `spectacles`, `genres_raw`, `style`) ont été supprimées de la table `evenement`. Les données sont maintenant stockées uniquement dans `contenu_evenement`.

**Note v1.7** : Nouvelle colonne `is_regional` pour marquer les événements hors département 72 (Sarthe).

**Note v1.8** : Support du Bidul d'été (juillet/août), dates avec nom de mois, amélioration de l'extraction des lieux hors référentiel (guillemets orphelins OCR, acronymes de lieux, codes département).

**Note v1.9** : Correction des faux splits ("de 18 mois", "de 14 ans"), support des dates DD/MM pour événements multi-mois, gestion des caractères OCR parasites avant dates, découpage des événements fusionnés (format bloc).

**Note v1.10** : Flag `is_regional` correctement assigné via `detect_regional()`, dashboard HTML avec distinction local/régional (KPIs, barres empilées, filtres), récupération des événements locaux mixés dans la section régionale (problème OCR colonnes mélangées).

**Note v1.11** : Extraction OCR par sections améliorée : rotation de page entière avant découpage (sections définies après rotation), colonnes `p*_orientation_pdf` pour distinguer orientation PDF vs texte, découpage physique des colonnes pour OCR séquentiel (gauche→droite), support format `inline_inherited` avec patterns 2-3 lettres.

**Note v1.13** : Extraction lieux Allonnes (Les Métairies, Salle G. Moquet, CHS, Maison des arts, Guinguette). Alias pour noms abrégés (`Th. de Chaoué`). Corrections parsing bidul 309 : PRIX LIBRE détecté comme artiste, bullet K OCR, validation lieu avec séparateur virgule, double slash multiline.

**Note v1.14** : Système d'overrides pour corrections manuelles (mode sync). CSV représente l'état final souhaité. Synchronisation : UPDATE evenement + DELETE/INSERT contenu_evenement. Fichiers dans `corpus/overrides/`.

**Note v1.15** : Ajout des coordonnées géographiques (latitude/longitude WGS84) et adresse postale (numero, voie, code_postal) dans `lieu_ref` pour compatibilité PostGIS. Script de géocodage via Nominatim (OpenStreetMap). Script de synchronisation `lieu.csv` → `lieu_ref`.

**Note v1.17** : Carte interactive des événements dans le dashboard HTML (Leaflet.js + heatmap). Filtres temporels multi-niveaux (année/mois/semaine/jour) avec sliders et animation. Mode plein écran. ~498 lieux géocodés affichés.

**Note v1.18** : Support des lieux génériques (Salle des fêtes, Église, Médiathèque, etc.) avec clé composite `UNIQUE(nom, ville)`. Ces lieux peuvent exister dans plusieurs villes différentes (157 nouvelles entrées créées). Colonne `is_generic` ajoutée à `lieu_ref`. Fonctions `find_lieu_ref_id()` et `normalize_lieu()` retournent maintenant 3 valeurs `(lieu_id, nom, ville)`.

**Note v1.19** : Nouveaux patterns d'extraction artiste pour spectacles : `"Spectacle" (style) de Auteur` et `"Spectacle" (style), Artiste`. Patterns ajoutés dans `extract_before_lieu()` (utilisé par `populate`). Documentation du workflow d'ajout de patterns dans `.claude/instructions.md`.

**Note v1.21** : Propagation automatique du lieu d'en-tête aux événements (fix bidul 71). Fonction `extract_header_lieu()` détecte les patterns "Au Palais", "MJC Prévert Le Mans", etc. Détection dynamique mid-text. Dashboard stats : sélecteur d'échelle heatmap (log, sqrt, linear) avec racine carrée par défaut pour meilleur contraste visuel.

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
python cli.py populate --include-regional  # Inclure événements hors Sarthe (v1.7)
python cli.py populate --include-artifacts # Inclure faux événements (v1.7)

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
python cli.py stats --html           # Dashboard HTML avec KPIs qualité (v1.8)
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
| `core/regional_filter.py` | Détection événements hors Sarthe (v1.7) |
| `core/artifact_filter.py` | Filtrage faux événements (v1.7) |
| `core/stats_generator.py` | Dashboard HTML avec Chart.js + KPIs qualité (v1.8) |
| `core/overrides.py` | Système d'overrides pour corrections manuelles (v1.14) |
| `scripts/geocode_lieux.py` | Géocodage des lieux via Nominatim (v1.15) |
| `scripts/sync_lieu_csv.py` | Synchronisation lieu.csv → lieu_ref (v1.15) |
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

## Filtrage v1.7

### Filtrage régional

Les événements de la section "Et un peu plus loin..." (hors département 72) sont exclus par défaut :

| Critère | Exemple | Résultat |
|---------|---------|----------|
| Code département (72) | `Concert, Le Mans (72)` | LOCAL |
| Ville sarthoise | `Allonnes`, `La Flèche` | LOCAL |
| Code département hors 72 | `Chabada, Angers (49)` | RÉGIONAL (exclu) |
| Lieu connu hors Sarthe | `Le Chabada`, `L'Ubu` | RÉGIONAL (exclu) |

Option `--include-regional` pour les inclure (marqués `is_regional=True`).

### Filtrage des artifacts

Les faux événements sont exclus par défaut :
- Texte < 15 caractères
- Info/annonces (www., contact:, inscription)
- Sans lieu ni artiste ni spectacle

Option `--include-artifacts` pour les inclure.

## Limitations actuelles

1. **OCR** : Qualité variable selon l'état des scans (anciens numéros)
2. **Parsing** : Certains formats d'événements non reconnus (confidence < 0.6)
3. **Événements multi-dates** : Support partiel ("Ve 3-4" → 2 événements)

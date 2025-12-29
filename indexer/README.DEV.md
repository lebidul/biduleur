# Indexer - Guide de Développement

## Vue d'ensemble

Le module `indexer` extrait les événements culturels des archives PDF du fanzine "Le Bidul" et les structure dans une base de données SQLite. Il s'agit d'un pipeline d'extraction de texte avec parsing intelligent capable de traiter plus de 130 numéros d'archives (1997-2024).

## Architecture

```
PDF Archives
     │
     ▼
┌─────────────────┐
│  TextExtractor  │  ← Extraction du texte avec préservation du formatage
│  (extractor.py) │    Détecte: gras (<b>), italique (<i>), colonnes
└────────┬────────┘
         │ texte avec balises <b>, <i>, <bi>
         ▼
┌─────────────────┐
│   EventParser   │  ← Stratégie "lieu d'abord" avec référentiels
│   (parser.py)   │    Identifie: artistes, spectacles, lieux, dates, tarifs
└────────┬────────┘
         │ ParsedEvent[]
         ▼
┌─────────────────┐
│    BidulDB      │  ← Persistance SQLite avec tables normalisées
│    (db.py)      │    Tables: evenement, contenu_evenement, lieu_ref, ville_ref
└─────────────────┘
```

## Modules principaux

### `core/extractor.py` - Extraction PDF

Classe `TextExtractor` utilisant PyMuPDF pour l'extraction du texte.

**Fonctionnalités clés:**
- Détection automatique PDF natif vs scan (OCR nécessaire si < 500 caractères)
- Préservation du formatage via balises `<b>`, `<i>`, `<bi>`
- Lecture multi-colonnes ordonnée (gauche → droite, haut → bas)
- Extraction des métadonnées (numéro, mois, année) depuis le nom du fichier

```python
extractor = TextExtractor(preserve_formatting=True)
result = extractor.extract("bidul_280_mai_2023.pdf")
# result.full_text contient le texte avec balises de formatage
# result.is_native indique si le PDF a du texte natif
```

### `core/parser.py` - Parsing des événements

Classe `EventParser` avec deux stratégies de parsing:
1. **Stratégie classique** (`parse()`) - parsing regex
2. **Stratégie "lieu d'abord"** (`parse_with_referentiel()`) - utilise les référentiels

**Stratégie "lieu d'abord" (recommandée):**
1. Trouve le lieu dans le texte via le référentiel `lieu_ref` (incluant les alias)
2. Extrait le contenu AVANT le lieu (artistes, spectacles)
3. Extrait le contenu APRÈS le lieu (ville, heure, tarif)
4. Si le lieu n'est pas trouvé, utilise une extraction heuristique

**Extraction basée sur le formatage:**
- Artistes: texte en **gras** suivi optionnellement de (style) en *italique*
- Spectacles: texte en **gras** entre guillemets « »
- Styles/genres: texte en *italique* entre parenthèses
- Artistes multiples: séparés par `+` (ex: `<b>ARTISTE1 + ARTISTE2</b>`)
- Artistes avec préfixe numérique: `0' BROTHERS`, `2 Many DJs`
- Heures individuelles par artiste: `ARTISTE1 16h + ARTISTE2 17h` → prend l'heure la plus tôt

```python
parser = EventParser(bidul_mois=5, bidul_annee=2023)
events = parser.parse_with_referentiel(text, lieu_ref_list, ville_ref_list)
```

**Fonctions utilitaires importantes:**
- `extract_formatted_artistes_musicaux()` - Extrait artistes depuis balises `<b>`, sépare sur `+`
- `extract_formatted_spectacles()` - Extrait spectacles entre guillemets gras (v1.4 : supporte patterns 1b/1c)
- `extract_event_name()` - Extrait le nom d'événement (festivals, soirées thématiques)
- `is_named_event()` - Détecte si un texte représente un événement nommé
- `extract_lieu_fallback()` - Extraction heuristique quand le lieu n'est pas dans le référentiel
- `strip_formatting_tags()` - Retire les balises pour comparaison
- `find_lieu_position_heuristic()` - Trouve la position du lieu dans le texte (v1.4 : corrige position texte original)

### `core/db.py` - Base de données

Classe `BidulDB` pour la gestion SQLite.

**Tables principales:**
- `bidul` - Métadonnées des numéros (n°, mois, année, statut)
- `evenement` - Événements avec raw_text, date, lieu, tarif, confidence
- `contenu_evenement` - Artistes/spectacles normalisés (relation 1-N)
- `lieu_ref` / `ville_ref` - Référentiels pour normalisation

**Schéma relationnel:**
```
bidul (1) ──► (N) evenement (1) ──► (N) contenu_evenement
                     │
                     ▼
               lieu_ref / ville_ref
```

### `core/normalizer.py` - Normalisation

Module central de normalisation avec système de règles automatiques (v1.5).

**Normalisation automatique:**
```python
from core.normalizer import normalize_for_matching

# Normalisation pour comparaison (case, accents, séparateurs)
normalize_for_matching("Théâtre")  # → "theatre"
normalize_for_matching("pop-rock") # → "pop rock"
normalize_for_matching("L'Oasis")  # → "oasis"
```

**Matching avec référentiels:**
```python
from core.normalizer import find_lieu_ref_id, find_artiste_ref_id, normalize_ville

lieu_id = find_lieu_ref_id("bar le lézard")     # → 42 (matching automatique)
artiste_id = find_artiste_ref_id("ZIG ZAG")     # → 15625
ville_id, ville_nom = normalize_ville("le mans") # → (1, "Le Mans")
```

**Règles de normalisation automatique (v1.5):**

| Règle | Fonction | Exemple |
|-------|----------|---------|
| Case-insensitive | `lower()` | `BAR` → `bar` |
| Accent-insensitive | NFD decomposition | `théâtre` → `theatre` |
| Séparateurs | `-` → ` ` | `pop-rock` → `pop rock` |
| Préfixes strippés | `le`, `la`, `l'`, etc. | `le barouf` → `barouf` |
| Abbreviations | `th.` → `theatre` | `th. municipal` → `theatre municipal` |

**Cache management:**
```python
from core.normalizer import clear_caches

# Vider les caches après modification des CSV
clear_caches()
```

### `core/text_cleaner.py` - Nettoyage du texte

Utilitaires pour nettoyer le texte extrait des PDFs:
- `clean_pdf_text()` - Normalise espaces, caractères spéciaux
- `expand_abbreviations()` - Développe les abréviations courantes (Th. → Théâtre)
- `normalize_lieu_name()` - Normalise les noms de lieux

## Flux de données détaillé

### 1. Extraction (extractor.py)

```
PDF → PyMuPDF.get_text('dict') → blocs triés par colonnes → texte avec balises
```

Le texte extrait ressemble à:
```
Ve 3 • <b>MOONLIGHT BENJAMIN</b> <i>(blues-soul-vaudou)</i>, La Fonderie, Le Mans, 21h, 12€
Sa 4 • <b>„Ma tata, mon pingouin..."</b> <i>(théâtre)</i>, par <b>Cie Douda</b>, Salle Scarron, 15h
```

### 2. Parsing (parser.py)

**Étape 1: Split sur les dates**
```python
lines = split_on_dates_v2(text)  # Sépare chaque événement
```

**Étape 2: Pour chaque ligne, trouver le lieu**
```python
lieu_match = find_lieu_in_text_v2(event_text, lieu_patterns)
# → ("La Fonderie", 42, 45, 57)  # (nom, id, start, end)
```

**Étape 3: Parser avant/après le lieu**
```python
before_data = extract_before_lieu(text, lieu_start)
# → {'artistes': [...], 'spectacles': [...], 'nom_evenement': ...}

after_data = extract_after_lieu(text, lieu_end)
# → {'ville': 'Le Mans', 'heure': '21h', 'tarif_raw': '12€'}
```

### 3. Persistance (db.py)

```python
db.insert_evenement(numero, parsed_event)
# Insère dans evenement + contenu_evenement
```

## Score de confiance

Chaque événement a un score `confidence` (0.0 - 1.0) basé sur:
- Présence d'une date valide (+0.3)
- Présence d'un lieu (+0.2)
- Présence d'artistes/spectacles (+0.2)
- Présence d'un tarif (+0.1)
- Cohérence globale (+0.2)

## Référentiels

Les référentiels sont chargés depuis `corpus/`:
- `lieu.csv` - ~543 lieux connus (bars, salles, théâtres...)
- `ville.csv` - ~123 villes de la Sarthe et environs

Format CSV:
```csv
nom,ville
Bar le Lézard,Le Mans
L'Oasis,Le Mans
Parking rotonde du CROUS,Le Mans
```

**Alias de lieux:** Un même lieu peut avoir plusieurs entrées pour couvrir les variantes d'orthographe (ex: "p. rotonde du CLOUS" → "Parking rotonde du CROUS").

## Système de consolidation

Après extraction, les événements peuvent être triés et vérifiés:

1. **Triage** (`core/triage.py`) - Classification par confidence
2. **Aliases** (`core/aliases.py`) - Normalisation des noms d'artistes
3. **Review** (`core/review.py`) - Interface de vérification manuelle

## Tests et benchmarks

### Benchmarks

Fichiers de référence pour valider l'extraction:
```bash
# Benchmark Bidul 184 (score cible: 97.9%)
python benchmark/compare_bidul_184.py

# Benchmark Bidul 190 (score cible: 96.8%)
python benchmark/compare_bidul.py 190

# Benchmark générique pour n'importe quel Bidul
python benchmark/compare_bidul.py <numero>
```

Compare les résultats extraits avec `benchmark/bidul_<numero>_expected.csv`.

### Tests unitaires
```bash
python -m pytest tests/
```

## Patterns regex importants

### Dates
```python
# Format inline: "Ve 3" ou "Sa 4-5" ou "Di 12"
INLINE_DATE_PATTERN = r'^(Lu|Ma|Me|Je|Ve|Sa|Di)\s+(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?'

# Format bloc: "Samedi 2", "Samedi 2 & Dimanche 3", "Du 6 au 10 juin"
# Supporte aussi:
# - Dates composées avec "et": "Samedi 04 et Dimanche 05"
# - Plages avec jours complets: "Du Mercredi 01 au Samedi 07"
DATE_PATTERN = r'^(?:({JOURS})\s+(\d{1,2})(?:ER|er)?(?:\s*(?:[&,]|et)\s*({JOURS})\s+(\d{1,2}))?|[Dd]u\s+(?:{JOURS}\s+)?(\d{1,2})\s*[aà]u?\s+(?:{JOURS}\s+)?(\d{1,2}))'

# Dates multiples avec séparateurs: "Lu 12/Ma 13/Me 14:" ou "Lu 12 & Ma 13:"
MULTI_DATE_PATTERN = r'^([DLMJVS][a-z]\s*\d{1,2}(?:\s*[&,/]\s*[A-Za-z]{2}\s*\d{1,2})*)\s*:\s*'

# Plages de dates: "Je 23 au Sa 25:" ou "Du Je 23 au Sa 25:"
DATE_RANGE_PATTERN = r'^(?:Du\s+)?([DLMJVS][a-z])\s*(\d{1,2})\s+(?:au|à)\s+([DLMJVS][a-z])\s*(\d{1,2})\s*:'
```

**Comportement du split sur dates:**
- Ne split PAS après un prix décimal (`7€50`)
- Ne split PAS sur une date faisant partie d'une plage (`Je 23 au Sa 25`)
- Génère toutes les dates de la plage (23, 24, 25 → 3 événements)

### Artistes (en gras)
```python
# <b>NOM ARTISTE</b> optionnel: <i>(style)</i>
# Sépare automatiquement sur "+" : <b>ARTISTE1 + ARTISTE2</b>
ARTISTE_PATTERN = r'<b>([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][^<]+)</b>(?:\s*<i>\s*\(([^)]+)\)\s*</i>)?'

# Artistes avec préfixe numérique: "0' BROTHERS", "2 Many DJs"
ARTISTE_NUMERIC_PREFIX = r'^((?:\d+'?\s*)?[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇa-z...]+)'

# Artistes avec heure individuelle: "ARTISTE1 (style) 16h + ARTISTE2 (style) 17h"
# L'heure de l'événement = heure la plus tôt
```

### Noms d'événements
```python
# Événements nommés: Soirée X, Festival Y, SPRINGROCK : <b>artistes</b>
is_named_event()  # Détecte si c'est un événement nommé
extract_event_name()  # Extrait le nom (ex: "SPRINGROCK", "Fête interculturelle")

# v1.5: Support des événements avec numéro d'édition en Title Case
# "Syncope fait de la résistance #2" → evenement.nom (pas nom_spectacle)
```

### Spectacles (guillemets + gras)
```python
# Pattern standard: <b>„Titre du spectacle"</b> ou <b>«Titre»</b>
SPECTACLE_PATTERN = r'<b>\s*[«""„]([^»""]+)[»""]\s*</b>'

# Pattern 1b (v1.4): guillemets AUTOUR du gras + style
# "<b>Spectacle</b>" (<i>style</i>)
PATTERN_1B = rf'(?:{open_quotes})\s*<b>([^<>]+)</b>\s*(?:{close_quotes})\s*(?:\(?\s*<i>\s*\(?([^)<]+?)\)?\s*</i>\s*\)?)?'

# Pattern 1c (v1.4): spectacle + Cie + style
# "<b>Spectacle</b>" Cie XXX (<i>style</i>)
PATTERN_1C = rf'(?:{open_quotes})\s*<b>([^<>]+)</b>\s*(?:{close_quotes})\s+[Cc]ie\s+[^<(]+\s*(?:\(?\s*<i>\s*\(?([^)<]+?)\)?\s*</i>\s*\)?)?'

# Classes de guillemets (v1.4) - inclut unicode et OCR
open_quotes = r'[«""„\u201c\u201d]|<<'
close_quotes = r'[»""\u201c\u201d]|>>'
```

### Heures
```python
# 21h, 21h30, 20h30-22h
HEURE_PATTERN = r'(\d{1,2}h\d{0,2})'
```

### Tarifs
```python
# 12€, 8/12€, gratuit, prix libre
TARIF_PATTERN = r'(\d+(?:[.,]\d+)?)\s*€|gratuit|libre'
```

## Débogage

### Visualiser le texte extrait
```python
from core.extractor import TextExtractor
ext = TextExtractor()
result = ext.extract("archives/bidul_184.pdf")
print(result.full_text[:2000])
```

### Tracer le parsing d'une ligne
```python
from core.parser import parse_event_line_v2
events = parse_event_line_v2(
    "<b>ARTISTE</b>, Bar le X, Le Mans, 21h",
    mois=12, annee=2013,
    lieu_ref_list, ville_ref_list
)
for e in events:
    print(e)
```

### Vérifier la normalisation
```python
from core.normalizer import normalize_lieu, normalize_ville
print(normalize_lieu("bar lézard"))     # Recherche floue
print(normalize_ville("la fleche"))     # Normalise accents
```

## Module OCR (`core/ocr.py`)

Le module OCR permet d'extraire le texte des PDFs scannés (numéros 1-177).

### Moteurs OCR supportés

| Moteur | Performance | Qualité | Coût |
|--------|-------------|---------|------|
| `google` | ~50s/PDF | Excellente | Cloud API |
| `paddleocr` | ~135s/PDF | Bonne | Local/gratuit |
| `easyocr` | ~200s/PDF | Moyenne | Local/gratuit |

**Recommandation:** Utiliser `google` (Google Cloud Vision) pour la qualité et la vitesse.

### Configuration Google Cloud Vision

1. Créer un compte de service GCP avec l'API Vision activée
2. Télécharger le fichier JSON de credentials
3. Le placer à la racine du projet sous le nom `gcp_creds_biduleur.json`

### Classes principales

**`ScanExtractor`** - Extracteur OCR pour PDFs scannés
```python
from core.ocr import ScanExtractor, load_bidul_config

extractor = ScanExtractor(ocr_engine='google', dpi=200)
config = load_bidul_config(158)  # Charge config depuis biduls.description.csv
result = extractor.extract_from_pdf("archives/bidul_158.pdf", config)
print(result.full_text)
```

**`ScanConfig`** - Configuration d'extraction par Bidul
```python
@dataclass
class ScanConfig:
    numero: int
    date_format: str = 'inline'  # 'inline' ou 'par bloc'
    page1_orientation_pdf: str = 'portrait'
    page1_orientation_texte: str = 'portrait'
    # ...
```

**`OCREngine`** - Wrapper unifié pour les moteurs OCR
```python
from core.ocr import OCREngine

engine = OCREngine(engine='google')
text = engine.ocr_image(numpy_image)
```

### Post-traitement (`core/ocr_postprocess.py`)

Le post-processeur corrige les erreurs OCR courantes :
- Confusion lettres/chiffres (`1e` → `le`, `hOO` → `h00`)
- Normalisation des heures (`20H30` → `20h30`)
- Correction des entités connues (lieux, villes) par fuzzy matching

```python
from core.ocr_postprocess import OCRPostProcessor

processor = OCRPostProcessor()
corrected_text = processor.process(raw_ocr_text)
```

### Formats de date

Le fichier `corpus/biduls.description.csv` spécifie le format de date pour chaque Bidul :

| Format | Description | Exemple |
|--------|-------------|---------|
| `inline` | Date au début de chaque ligne | `Je 02 : CONCERT, Lieu, 21h` |
| `par bloc` | Date en en-tête de section | `Jeudi 2\n• CONCERT, Lieu, 21h` |

Le parser utilise automatiquement le bon format via `date_format` :
```python
parser = EventParser(bidul_mois=7, bidul_annee=2011, date_format='inline')
```

**Patterns de dates bloc supportés (v1.3):**
- Dates simples: `Jeudi 02`, `Lundi 06`
- Dates composées avec "et": `Samedi 04 et Dimanche 05`
- Dates composées avec "&" ou ",": `Ve 10 & Sa 11`
- Plages numériques: `Du 6 au 10`
- Plages avec jours complets: `Du Mercredi 01 au Samedi 07`

## Limitations connues

1. **Événements multi-dates** - Support partiel ("Ve 3-4" → 2 événements)
2. **Lieux non référencés** - Extraction heuristique moins fiable
3. **Formatage incohérent** - Certains vieux numéros ont un formatage variable
4. **OCR des très anciens Biduls** - Qualité variable selon l'état du scan

## Changelog v1.5

- **Normalisation automatique** : Système de règles pour matching case/accent/separator insensitive
- **Événements nommés #N** : Reconnaissance des événements Title Case avec numéro d'édition
- **Cleanup aliases** : 593 aliases redondants supprimés (couverts par normalisation auto)
- **Cache clearing** : `clear_caches()` automatique dans `renormalize`
- **Commandes maintenance** : `renormalize`, `clean-database`, `deduplicate`

## Changelog v1.4

- **Pattern 1b** : Support `"<b>Spectacle</b>" (<i>style</i>)` avec guillemets autour du gras
- **Pattern 1c** : Support `"<b>Spectacle</b>" Cie XXX (<i>style</i>)` pour Cie après spectacle
- **Unicode** : Guillemets typographiques (U+201C, U+201D) et apostrophe curly (U+2019)
- **Lookbehind artiste** : Évite double extraction spectacle/artiste pour texte entre guillemets
- **Position heuristique** : Correction du mapping position stripped → original text

## Contribution

1. Ajouter des lieux manquants dans `corpus/lieu.csv`
2. Ajouter des alias artistes dans `corpus/artistes_aliases.json`
3. Améliorer les patterns dans `parser.py` pour les cas limites
4. Enrichir le benchmark avec de nouvelles références

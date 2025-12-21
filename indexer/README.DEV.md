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
1. Trouve le lieu dans le texte via le référentiel `lieu_ref`
2. Extrait le contenu AVANT le lieu (artistes, spectacles)
3. Extrait le contenu APRÈS le lieu (ville, heure, tarif)

**Extraction basée sur le formatage:**
- Artistes: texte en **gras** suivi optionnellement de (style) en *italique*
- Spectacles: texte en **gras** entre guillemets « »
- Styles/genres: texte en *italique* entre parenthèses

```python
parser = EventParser(bidul_mois=5, bidul_annee=2023)
events = parser.parse_with_referentiel(text, lieu_ref_list, ville_ref_list)
```

**Fonctions utilitaires importantes:**
- `extract_formatted_artistes()` - Extrait artistes depuis balises `<b>`
- `extract_formatted_spectacles()` - Extrait spectacles entre guillemets gras
- `extract_lieu_fallback()` - Extraction heuristique quand le lieu n'est pas dans le référentiel
- `strip_formatting_tags()` - Retire les balises pour comparaison

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

Fonctions de normalisation pour les lieux et villes.

```python
from core.normalizer import normalize_lieu, normalize_ville

lieu_id, lieu_nom = normalize_lieu("bar le lézard")  # → (42, "Bar le Lézard")
ville_id, ville_nom = normalize_ville("le mans")     # → (1, "Le Mans")
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
- `lieu.csv` - ~540 lieux connus (bars, salles, théâtres...)
- `ville.csv` - ~120 villes de la Sarthe et environs

Format CSV:
```csv
nom,ville
Bar le Lézard,Le Mans
L'Oasis,Le Mans
```

## Système de consolidation

Après extraction, les événements peuvent être triés et vérifiés:

1. **Triage** (`core/triage.py`) - Classification par confidence
2. **Aliases** (`core/aliases.py`) - Normalisation des noms d'artistes
3. **Review** (`core/review.py`) - Interface de vérification manuelle

## Tests et benchmarks

### Benchmark Bidul 184

Fichier de référence pour valider l'extraction:
```bash
python benchmark/compare_bidul_184.py
```

Compare les résultats extraits avec `benchmark/bidul_184_expected.csv`.

### Tests unitaires
```bash
python -m pytest tests/
```

## Patterns regex importants

### Dates
```python
# Format: "Ve 3" ou "Sa 4-5" ou "Di 12"
DATE_PATTERN = r'^(Lu|Ma|Me|Je|Ve|Sa|Di)\s+(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?'
```

### Artistes (en gras)
```python
# <b>NOM ARTISTE</b> optionnel: <i>(style)</i>
ARTISTE_PATTERN = r'<b>([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][^<]+)</b>(?:\s*<i>\s*\(([^)]+)\)\s*</i>)?'
```

### Spectacles (guillemets + gras)
```python
# <b>„Titre du spectacle"</b> ou <b>«Titre»</b>
SPECTACLE_PATTERN = r'<b>\s*[«""„]([^»""]+)[»""]\s*</b>'
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

## Limitations connues

1. **PDFs scannés (n° < 178)** - Nécessitent OCR externe, non supporté
2. **Événements multi-dates** - Support partiel ("Ve 3-4" → 2 événements)
3. **Lieux non référencés** - Extraction heuristique moins fiable
4. **Formatage incohérent** - Certains vieux numéros ont un formatage variable

## Contribution

1. Ajouter des lieux manquants dans `corpus/lieu.csv`
2. Ajouter des alias artistes dans `corpus/artistes_aliases.json`
3. Améliorer les patterns dans `parser.py` pour les cas limites
4. Enrichir le benchmark avec de nouvelles références

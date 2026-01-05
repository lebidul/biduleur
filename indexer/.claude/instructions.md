# Indexer - Instructions Claude

## Commandes de test et benchmark

### Tests unitaires
```bash
# Tous les tests du parser
python -m pytest tests/test_parser.py -v --tb=short

# Un test spécifique
python -m pytest tests/test_parser.py::TestSplitBlocFusedEvents -v
```

### Benchmarks (IMPORTANT: utiliser `populate`, pas `extract`)
```bash
# Peupler un bidul (avec filtrage artifacts/régionaux)
python cli.py purge --numero 184
python cli.py populate --numero 184 --replace

# Lancer le benchmark
python benchmark/compare_bidul.py 184
python benchmark/compare_bidul.py 190

# Scores de référence v1.9:
# - Bidul 184: 95.4%
# - Bidul 190: 91.2%
```

**ATTENTION**: `extract` ne filtre pas les artifacts et produit trop d'événements. Toujours utiliser `populate` pour les benchmarks.

### Formats de bidul
Vérifier le format dans `corpus/biduls.description.csv`:
```bash
grep "^175" corpus/biduls.description.csv
# Colonnes: numero,scan/texte,source,date_format,...
# date_format: "inline" ou "par bloc"
```

## Fonctions clés du parser

| Fonction | Usage |
|----------|-------|
| `split_on_dates_v2()` | Découpe sur dates inline (Lu 02, Ma 03...) |
| `split_bloc_fused_events()` | Sépare événements fusionnés (prix€ + MAJUSCULES) |
| `parse_event_line_v2()` | Parse une ligne d'événement |
| `_parse_inline_with_referentiel()` | Format inline (Je 02: ARTISTE, Lieu) |
| `_parse_bloc_with_referentiel()` | Format bloc (dates en en-têtes) |

## Workflow de modification

1. Faire les modifications dans `core/parser.py`
2. Ajouter des tests dans `tests/test_parser.py` si nécessaire
3. Lancer les tests: `python -m pytest tests/test_parser.py -v`
4. Lancer les benchmarks avec `populate` (pas `extract`)
5. Commit avec message structuré: `feat(parser):`, `fix(parser):`, `docs:`

## Fichiers de documentation à mettre à jour

Lors d'une nouvelle version:
- `release.md` - Notes de release avec benchmarks
- `context.md` - Note version courte
- `README.DEV.md` - Fonctions utilitaires si ajout
- `.claude/instructions.md` - Ce fichier, pour améliorer les performances Claude

## Logique du parser

### Architecture de parsing
1. **Exclusion régionale** : `split_regional_section()` coupe le texte avant "Et un peu plus loin..."
2. **Détection du format** : `inline` ou `par bloc` via `corpus/biduls.description.csv`
3. **Découpage sur dates** : `split_on_dates_v2()` sépare le texte par dates
4. **Séparation événements fusionnés** : `split_bloc_fused_events()` sépare les événements collés
5. **Parsing individuel** : `parse_event_line_v2()` extrait les champs

### Section régionale "Et un peu plus loin..."
- La section régionale contient les événements hors département (Orne 61, Mayenne 53, etc.)
- `split_regional_section(text)` → tuple (texte_local, texte_regional)
- Activé via `EventParser(include_regional=False)` ou CLI `--include-regional`
- Détecte aussi les headers "Dans l'Orne (61):" avant le marqueur
- Le marqueur est ignoré s'il apparaît AVANT les événements (sous-titre vs séparateur)

### Distinction local/régional en base
- Colonne `evenement.is_regional` (BOOLEAN) : 0=local, 1=régional
- Pour parser avec les événements régionaux : `python cli.py populate --include-regional`
- Stats actuelles : ~97% locaux, ~3% régionaux

### Patterns de `split_bloc_fused_events()`
La fonction sépare les événements fusionnés sur ces patterns :
- `X€ MAJUSCULES` - prix suivi de nom en majuscules
- `X€ Soirée` - prix suivi de "Soirée"
- `X€ "titre"` - prix suivi de guillemet ouvrant
- `X€ Birdland` - prix suivi de noms connus
- `XXh Les ...` - heure suivie de "Les" + Majuscule
- `02 XX XX XX XX MAJUSCULES` - téléphone complet suivi de majuscules
- `chapeau NomPropre:` - "chapeau" suivi d'un nom avec deux-points
- `) <<Titre` - parenthèse fermante suivie de guillemets OCR `<<`

### Patterns de dates (`split_on_dates_v2`)
- Jours de semaine stricts : `Lu`, `Ma`, `Me`, `Je`, `Ve`, `Sa`, `Di`
- Avec numéro : `Ma 29:`, `Je 02 :`
- Multi-jours : `Ve 3-4`, `Du 31 au 03/02:`
- Avec mois : `Ve 01/02:`

### Éviter les faux splits
Les patterns doivent éviter de matcher :
- `de 18 mois`, `de 14 ans` (âges)
- Numéros de téléphone partiels
- Codes département dans les villes

## Bonnes pratiques

### Tests avant commit
```bash
# Tests unitaires obligatoires
python -m pytest tests/test_parser.py -v --tb=short

# Benchmarks obligatoires si modification du parser
python cli.py purge --numero 184 && python cli.py populate --numero 184 --replace
python benchmark/compare_bidul.py 184
# Score attendu >= 95.4%
```

### Debugging
```bash
# Voir le texte OCR extrait
python cli.py ocr "archives/bidul_XXX.pdf" --engine google -o temp_ocr.txt

# OCR avec numéro (lookup automatique du PDF)
python cli.py ocr --numero 132 --engine google

# Extraction seule sans filtrage (debug uniquement)
python cli.py extract --numero XXX
```

### Statistiques HTML
```bash
# Générer le dashboard HTML avec KPIs local/régional
python cli.py stats --html
# Fichier généré : stats/bidul_stats.html
```
Le dashboard inclut :
- KPIs séparés : événements totaux, locaux, régionaux, contenus
- Graphique avec barres empilées (cyan=local, violet=régional)
- Boutons de filtre : Tous, Événements, Locaux, Régionaux, Contenus
- Score qualité par type (local/régional)

### Accès au texte OCR stocké
Le texte OCR brut est stocké dans la table `bidul`, attribut `raw_text`:
```python
import sqlite3
conn = sqlite3.connect('database/bidul_archives.db')
cursor = conn.cursor()
cursor.execute('SELECT raw_text FROM bidul WHERE numero = 132')
row = cursor.fetchone()
if row and row[0]:
    print(row[0])  # Texte OCR complet du bidul
conn.close()
```

## Extraction OCR par sections

### Architecture des sections A6
Chaque page A4 est divisée en 4 sections A6 :
- **S1** : Haut-gauche (0-50% X, 0-50% Y)
- **S2** : Haut-droite (50-100% X, 0-50% Y)
- **S3** : Bas-gauche (0-50% X, 50-100% Y)
- **S4** : Bas-droite (50-100% X, 50-100% Y)

### Configuration des sections
Le mapping est défini dans `corpus/biduls.description.csv` :
- `page#.sections utiles` : Sections à extraire (ex: "S1,S2,S3,S4")
- `page#.orientation texte` : "portrait" ou "paysage" (rotation 90°)
- `page#.colonne par section` : Nombre de colonnes par section

### Modules OCR

| Module | Fichier | Usage |
|--------|---------|-------|
| `section_extractor` | `core/section_extractor.py` | Extraction par sections A6 configurées |
| `layout_analyzer` | `core/layout_analyzer.py` | Détection automatique colonnes/orientation |

### Options CLI OCR

```bash
# Mode standard (extraction par sections activée par défaut)
python cli.py populate --numero 132 --replace

# Désactiver l'extraction par sections (page entière)
python cli.py populate --numero 132 --no-sections

# Détection automatique du layout (colonnes)
python cli.py populate --numero 132 --auto-layout

# Combiner les options
python cli.py ocr --numero 132 --engine google --no-sections --auto-layout
```

### Héritage de configuration
Les biduls sans mapping dans `biduls.description.csv` héritent automatiquement de la configuration du bidul le plus proche (par numéro).

### Logique de pages
- **PDF 3 pages** : Extrait uniquement page 3 (résumé agenda)
- **PDF 2 pages** : Utilise la config page1 + page2
- **pages_override** : Priorité sur la logique automatique

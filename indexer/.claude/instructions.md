# Indexer - Instructions Claude

## Commandes de test et benchmark

### Tests unitaires
```bash
# Tous les tests
python -m pytest tests/ -v --tb=short

# Tests du parser
python -m pytest tests/test_parser.py -v --tb=short

# Tests du month_detector (biduls d'été)
python -m pytest tests/test_month_detector.py -v

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

# Scores de référence v1.14:
# - Bidul 184: 95.6%
# - Bidul 190: 91.8%
```

**ATTENTION**: `extract` ne filtre pas les artifacts et produit trop d'événements. Toujours utiliser `populate` pour les benchmarks.

### Formats de bidul
Vérifier le format dans `corpus/biduls.description.csv`:
```bash
grep "^175" corpus/biduls.description.csv
# Colonnes: numero,type,date_format,pages,ocr_mode,p1_sections,p1_orientation,p1_colonnes,...
```

**Formats de date disponibles** (`date_format`):
- `inline` : Chaque ligne commence par la date (ex: "Je 02: ARTISTE, Lieu")
- `par bloc` : Dates en en-têtes de sections, événements listés en dessous
- `inline_inherited` : Date sur la première ligne du jour, événements suivants héritent (biduls 1-16)
- `mixte` : Combine inline ET bloc (sections avec formats différents)

## Fonctions clés du parser

| Fonction | Usage |
|----------|-------|
| `split_on_dates_v2()` | Découpe sur dates inline (Lu 02, Ma 03...) |
| `split_bloc_fused_events()` | Sépare événements fusionnés (prix€ + MAJUSCULES) |
| `parse_event_line_v2()` | Parse une ligne d'événement |
| `_parse_inline_with_referentiel()` | Format inline avec référentiels (Je 02: ARTISTE, Lieu) |
| `_parse_bloc_with_referentiel()` | Format bloc avec référentiels (dates en en-têtes) |
| `_parse_inline_inherited_date()` | Format inline_inherited avec référentiels (biduls 1-16) |
| `_parse_inline_inherited_format()` | Format inline_inherited sans référentiels (pour `parse()`) |

**Note importante**: Le format `inline_inherited` a deux implémentations:
- `_parse_inline_inherited_date()` : utilisé par `parse_with_referentiel()`
- `_parse_inline_inherited_format()` : utilisé par `parse()` (sans référentiels)

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

### Extraction du nom d'événement via double slash (`//`)
Le pattern `Organisateur // ARTISTES` permet d'extraire le nom de l'événement.
- Pattern : `^(.+?)\s*//\s*(.+)` avec `re.DOTALL` pour le texte multiline
- Exemple : `Orga Garage5 // 6RME (bass)` → nom="Orga Garage5", artiste="6RME"
- Le flag `re.DOTALL` est essentiel car le texte peut contenir des newlines

### Validation du lieu (éviter faux positifs)
Le parser vérifie que le lieu détecté est bien un lieu et non partie du nom d'événement :
- Si le lieu est précédé d'une **virgule** ou **parenthèse fermante** → lieu valide
- Exemple : `MOULE FRIPES #5 // DJ Sets, Le Barouf` → "Le Barouf" est le lieu
- La fonction `is_named_event()` détecte les noms d'événements (patterns comme `#N`, `édition`)
- Si `is_named_event(text_before_lieu + lieu)` et pas de séparateur → lieu invalidé

### Détection artiste "PRIX LIBRE"
- `PRIX LIBRE` en majuscules dans `<b>PRIX LIBRE</b>` est un nom d'artiste, pas un tarif
- La fonction `truncate_noise_in_line()` ignore ce pattern pour éviter de tronquer l'événement

### Bullet point K (artefact OCR)
- Le caractère `K` isolé sur une ligne (`\nK\n`) est un artefact OCR du bullet `•`
- Prétraitement dans `_parse_bloc_with_referentiel()` : `re.sub(r'\nK\n', '\n•\n', text)`

### Nettoyage des puces OCR et ballot box
Les puces OCR et caractères ballot box sont nettoyés des noms d'événements :
- **Unicode Private Use Area** (`\ue000-\uf8ff`) : puces OCR spéciales
- **Ballot box** (`☐☑☒✓✗✘`) : caractères de case à cocher
- Nettoyage dans `extract_before_lieu()` et `_extract_double_slash_pattern()`

## Biduls d'été (juillet couvrant juillet+août)

### Numéros concernés
27 biduls de juillet contiennent les événements de juillet ET août :
```
6, 16, 37, 48, 59, 70, 81, 92, 103, 114, 125, 136, 147, 158, 180, 191,
202, 213, 224, 235, 246, 256, 260, 271, 282, 293, 303
```

### Module `core/month_detector.py`
Détecte les sections de mois dans le texte OCR pour attribuer les bonnes dates :

| Fonction | Usage |
|----------|-------|
| `detect_month_sections()` | Détecte toutes les sections de mois dans le texte |
| `get_month_for_line()` | Détermine le mois applicable pour un numéro de ligne |
| `get_month_for_position()` | Détermine le mois applicable pour une position caractère |
| `is_summer_bidul()` | Vérifie si c'est un bidul de juillet (mois=7) |
| `strip_html_tags()` | Nettoie les balises HTML avant détection |

### Patterns de headers de mois supportés
```
JUILLET, AOÛT, AOUT, SEPTEMBRE (majuscules)
Juillet, Août, Septembre (Title Case)
juillet, août, aout, septembre (minuscules)
En juillet :, En août : (format avec préfixe)
Du 1er au 31 juillet (ranges avec mois)
FIN JUILLET, DÉBUT AOÛT (composés)
<bi>Juillet </bi> (avec balises HTML)
AO, AQUT (erreurs OCR tronquées)
```

### Vérification des biduls d'été
```python
import sqlite3
conn = sqlite3.connect('database/bidul_archives.db')
cursor = conn.cursor()

# Répartition par mois pour un bidul d'été
cursor.execute('''
    SELECT strftime('%Y-%m', date_evenement) as mois, COUNT(*) as nb
    FROM evenement
    WHERE bidul_numero = 256
    GROUP BY mois
    ORDER BY mois
''')
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]} événements")
# Résultat attendu: 2020-07: 71, 2020-08: 46
```

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
Le mapping est défini dans `corpus/biduls.description.csv` (nouveau format) :
- `p1_sections` / `p2_sections` : Sections à extraire (ex: "S1 S2 S3 S4")
- `p1_orientation` / `p2_orientation` : Orientation du **texte** (portrait/paysage)
- `p1_orientation_pdf` / `p2_orientation_pdf` : Orientation du **PDF** (défaut = même que texte)
- `p1_colonnes` / `p2_colonnes` : Nombre de colonnes par section

**Rotation automatique** : Si `orientation_pdf != orientation` (ex: PDF portrait + texte paysage), une rotation 90° est appliquée automatiquement. Cas typique : biduls 2-11 où le PDF est portrait mais le texte est imprimé en paysage.

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

## Architecture des configurations CSV

### Deux systèmes de chargement (IMPORTANT)
Le fichier `corpus/biduls.description.csv` est lu par **deux classes différentes** qui doivent rester synchronisées :

| Classe | Fichier | Usage |
|--------|---------|-------|
| `ScanConfig` / `ScanConfigLoader` | `core/ocr.py` | Configuration OCR + `date_format` pour le parser via `load_bidul_config()` |
| `BidulSectionConfig` / `SectionConfigLoader` | `core/section_extractor.py` | Configuration sections A6 + `date_format` |

**Attention** :
- Si vous modifiez le format du CSV, vous devez mettre à jour les deux méthodes `from_csv_row()` dans les deux fichiers.
- Les deux loaders doivent filtrer les commentaires de la même manière (lignes commençant par `#` ou `"#`).

### Format CSV actuel (v1.14+)
```
numero,type,date_format,pages,ocr_mode,p1_sections,p1_orientation,p1_orientation_pdf,p1_colonnes,p2_sections,p2_orientation,p2_orientation_pdf,p2_colonnes,notes
```

Les lignes commençant par `#` ou `"#` sont ignorées (commentaires).

### Workflow d'extraction par sections

L'extraction suit ce workflow :

1. **Rotation de la page entière** (si `orientation_pdf != orientation`)
   - Rotation 90° horaire (clockwise) appliquée à toute la page
   - Les sections sont définies **APRÈS** rotation sur l'image lisible

2. **Découpage en sections A6** sur l'image rotée
   - S1 = haut-gauche (0-50% X, 0-50% Y)
   - S2 = haut-droite (50-100% X, 0-50% Y)
   - S3 = bas-gauche (0-50% X, 50-100% Y)
   - S4 = bas-droite (50-100% X, 50-100% Y)

3. **OCR par colonne** (si `colonnes > 1`)
   - L'image de section est coupée physiquement en colonnes
   - Chaque colonne est OCR séparément
   - Les résultats sont concaténés gauche → droite

4. **Ordre de lecture des sections**
   - Mode portrait : S1 → S2 → S3 → S4 (ligne par ligne)
   - Mode paysage : S1 → S3 → S2 → S4 (colonne par colonne)

**Exemple bidul 5** :
- PDF portrait, texte paysage → rotation 90° horaire
- Après rotation, sections S1 (SARTHE DIT D), S3, S2 (FÊTE DE LA MUSIQUE)
- 2 colonnes par section → lecture gauche puis droite

### Colonnes principales
| Colonne | Valeurs | Description |
|---------|---------|-------------|
| `numero` | 1-305 | Numéro du bidul |
| `type` | scan, texte | Type de PDF |
| `date_format` | inline, par bloc, inline_inherited, mixte | Format de parsing des dates |
| `pages` | 1, 2, 3, 1-2 | Pages à extraire (override) |
| `ocr_mode` | classic, sections, auto | Mode OCR |
| `p1_sections` | S1 S2 S3 S4 | Sections page 1 |
| `p1_orientation` | portrait, paysage | Orientation du texte page 1 |
| `p1_orientation_pdf` | portrait, paysage | Orientation du PDF page 1 (défaut = p1_orientation) |
| `p1_colonnes` | 1, 2 | Colonnes par section page 1 |

### Format inline_inherited (biduls 1-16)
Format hybride où la date apparaît seulement sur la première ligne d'un jour :
```
Ma 03: TONGZ, bar Le Mackeson LE MANS, 22h15
MICHEL EDELIN QUARTET, Théâtre Paul Scarron    <- hérite de Ma 03
LE MANS, 21h00
Je 05:                                          <- nouvelle date (contenu sur lignes suivantes)
URANUS BRILLANT, bar Le Viking's, LE MANS
NICOLAS ET TOMY, pub Le Terminus               <- hérite de Je 05
```

La fonction `_parse_inline_inherited_date()` gère ce format avec :
1. Première passe : jointure des lignes de continuation (villes, heures)
2. Deuxième passe : attribution des dates héritées aux événements

## Templates SVG pour zones d'extraction

### Concept

Les templates SVG permettent de définir avec précision les zones d'extraction du texte OCR. Chaque zone est un rectangle SVG avec un ID structuré.

### Structure des fichiers

```
corpus/
├── biduls.description.csv      # Colonne 'svg_template' pour référencer le template
└── templates/
    ├── bidul_005.svg           # Template personnalisé
    ├── bidul_006.svg
    └── default_paysage_2col.svg  # Templates génériques réutilisables
```

### Format SVG

```xml
<svg viewBox="0 0 1654 2339" xmlns="http://www.w3.org/2000/svg">
  <!-- Page 2, Section S1, Colonne 1 -->
  <rect id="p2-s1-col1" x="0" y="0" width="571" height="860"
        fill="none" stroke="red" stroke-width="2"/>
  <!-- Page 2, Section S1, Colonne 2 -->
  <rect id="p2-s1-col2" x="643" y="0" width="572" height="860"
        fill="none" stroke="blue" stroke-width="2"/>
</svg>
```

### Convention de nommage des IDs

- `p{page}-s{section}-col{colonne}` : Zone de colonne
- `p{page}-s{section}` : Zone de section entière (si pas de colonnes)
- `p{page}-exclude` : Zone à exclure (logos, headers)

### Priorité de chargement

1. **SVG personnalisé** : `corpus/templates/bidul_{numero}.svg`
2. **Template générique** : Via colonne `svg_template` dans CSV
3. **Calcul par défaut** : Sections A6 + colonnes calculées

### Colonne CSV

```csv
numero,...,svg_template,notes
5,...,bidul_005.svg,Template personnalisé pour layout complexe
6,...,default_paysage_2col.svg,Utilise template générique
7,...,,Pas de template - calcul par défaut
```

## Système d'overrides (corrections manuelles)

### Concept

Le système d'overrides permet d'appliquer des corrections manuelles aux événements après parsing. Le CSV représente l'état final souhaité (mode "sync").

### Format CSV

```csv
bidul_numero,raw_text,nom,lieu_raw,ville_raw,tarif_raw,nom_spectacle,artiste,style
23,"texte OCR original...",Association TERIAKI,,Bouloire,20F,,AR,
23,"texte OCR original...",Association TERIAKI,,Bouloire,20F,,RSW,
```

- **Identification** : `(bidul_numero, raw_text)` identifie l'événement
- **Valeur vide** = NULL en base
- **Plusieurs lignes** pour un même événement = plusieurs artistes/contenus

### Structure des fichiers

```
corpus/
└── overrides/
    ├── teriaki.csv     # Corrections Association TERIAKI
    └── autre.csv       # Autres corrections
```

### Logique de synchronisation

Pour chaque `(bidul_numero, raw_text)` unique :
1. **UPDATE evenement** avec `nom`, `lieu_raw`, `ville_raw`, `tarif_raw`
2. **DELETE** tous les `contenu_evenement` existants
3. **INSERT** les nouveaux `contenu_evenement` depuis les lignes CSV

### Commandes CLI

```bash
# Dry-run (simulation)
python -m core.overrides corpus/overrides/teriaki.csv --dry-run -v

# Appliquer les corrections
python -m core.overrides corpus/overrides/teriaki.csv -v

# Plusieurs fichiers
for csv in corpus/overrides/*.csv; do
    python -m core.overrides "$csv" -v
done
```

### Application automatique

Les overrides peuvent être appliqués automatiquement après parsing via `OverrideManager` :

```python
from core.overrides import apply_overrides

event_id = db.insert_evenement(bidul_numero, event)
apply_overrides(db.connect(), event_id, bidul_numero, event.raw_text)
```

### Création d'un fichier d'override

1. Exporter les données actuelles via SQL :
```sql
SELECT e.bidul_numero, e.raw_text, e.nom, e.lieu_raw, e.ville_raw, e.tarif_raw,
       c.nom_spectacle, c.artiste, c.style
FROM evenement e
LEFT JOIN contenu_evenement c ON c.evenement_id = e.id
WHERE e.raw_text LIKE '%TERIAKI%'
ORDER BY e.bidul_numero, e.id, c.ordre;
```

2. Corriger les valeurs dans le CSV
3. Appliquer avec `--dry-run` pour vérifier
4. Appliquer pour de vrai

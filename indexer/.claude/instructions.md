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

# Scores de référence v1.20:
# - Bidul 184: 94.6%
# - Bidul 190: 91.5%
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
| `extract_header_lieu()` | Extrait le lieu depuis un en-tête de bloc (v1.21) |
| `_parse_inline_with_referentiel()` | Format inline avec référentiels (Je 02: ARTISTE, Lieu) |
| `_parse_bloc_with_referentiel()` | Format bloc avec référentiels (dates en en-têtes) |
| `_parse_inline_inherited_date()` | Format inline_inherited avec référentiels (biduls 1-16) |
| `_parse_inline_inherited_format()` | Format inline_inherited sans référentiels (pour `parse()`) |

### Propagation du lieu d'en-tête (v1.21)

Certains blocs ont un en-tête avec le lieu suivi d'événements sans lieu :

```
Au Palais, café-concert, Le Mans, à 22h
Ve 05: Concert Jazz avec Pascal MAFFEÏ
Ve 12: Soirée Ambiance avec DJ FRED
```

La fonction `extract_header_lieu()` détecte ces patterns :
- Pattern 1: `Au X, Ville` → lieu="Le X" (conversion Au→Le)
- Pattern 2: `Nom Ville - tél...` → lieu="Nom", ville="Ville" (nécessite majuscule initiale, lieu ≥ 3 chars)
- Pattern 3: `Le/La X, Ville` → lieu="Le/La X", ville="Ville"
- Pattern 4: `Festival NOM à/au/à l' LIEU` → cherche le lieu via `find_lieu_in_text_v2()` (avec aliases)

Le lieu est propagé via `current_block_lieu_*` aux événements sans `lieu_raw`.

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

### Tarifs non-numériques exclus du lieu

Les tarifs textuels ne sont **jamais** des lieux. Les fonctions `extract_lieu_fallback()` et `_extract_lieu_ville()` ignorent ces patterns :
- `au chapeau`, `gratuit`, `prix libre`, `libre`, `hnc`, `tnc`

**Deux points de filtrage :**
- `extract_lieu_fallback()` : `prix_pattern` inclut tous les tarifs non-numériques
- `_extract_lieu_ville()` : check explicite avant la logique de split prix/heure

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
python cli.py stats --html stats.html
```
Le dashboard inclut :
- KPIs séparés : événements totaux, locaux, régionaux, contenus
- Graphique avec barres empilées (cyan=local, violet=régional)
- Boutons de filtre : Tous, Événements, Locaux, Régionaux, Contenus
- Score qualité par type (local/régional)
- Borne supérieure dynamique (tous les biduls existants sont inclus)

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

**Rotation 180°** : La valeur `retourne` pour `p{n}_orientation_pdf` indique une page physiquement retournée à 180° dans le PDF. Cas typique : bidul 15 page 2.

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
| `numero` | 1-310 | Numéro du bidul |
| `type` | scan, texte, csv, xlsx | Type de source pour `populate` |
| `date_format` | inline, par bloc, inline_inherited, mixte | Format de parsing des dates |
| `pages` | 1, 2, 3, 1-2 | Pages à extraire (override) |
| `ocr_mode` | classic, sections, auto | Mode OCR |
| `p1_sections` | S1 S2 S3 S4 | Sections page 1 |
| `p1_orientation` | portrait, paysage | Orientation du texte page 1 |
| `p1_orientation_pdf` | portrait, paysage, retourne | Orientation du PDF page 1 (défaut = p1_orientation) |
| `p1_colonnes` | 1, 2 | Colonnes par section page 1 |
| `source_file` | nom(s) fichier(s) | Fichier(s) source CSV/XLSX (séparés par `\|` pour multi-fichiers) |

### Types de source (`type`)
Le champ `type` détermine la méthode d'extraction utilisée par `populate` :
- **scan** : OCR du PDF (Google Cloud Vision ou PaddleOCR)
- **texte** : Extraction texte natif du PDF (PyMuPDF)
- **csv** : Import depuis fichier CSV (défini par `source_file`)
- **xlsx** : Import depuis fichier XLSX (défini par `source_file`)

**Comportement de `populate` :**
- Si `type=csv` ou `type=xlsx` : utilise le fichier source défini par `source_file`
- Si `type=scan` : utilise l'OCR (avec templates SVG si disponibles dans `corpus/templates/`)
- Si `type=texte` : extrait le texte natif du PDF

**Options de filtrage :**
- `--csv-only` : traite uniquement les biduls de type `csv` ou `xlsx`
- `--pdf-only` : traite uniquement les biduls de type `scan` ou `texte`

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
1. Première passe : jointure des lignes de continuation (villes, heures, lieux partiels)
2. Deuxième passe : attribution des dates héritées aux événements

**Cas de continuation** (lignes jointes à l'événement précédent) :
1. Ligne commençant par ville, heure, prix, parenthèse ou minuscule (`continuation_pattern`)
2. Ligne commençant par un mot-clé de lieu (Salle, Théâtre, Bar, etc.)
3. (dans `_parse_inline_with_referentiel`) Cas 1-4 : préposition/article, lieu partiel, virgule, abréviation
4. (dans `_parse_inline_with_referentiel`) Cas 5 : type de lieu + début de nom propre (ex: "bar Le", "théâtre Paul", "Collégiale St", "Péniche")
5. (dans `_parse_inline_inherited_date`) Cas 5 : même détection de lieu partiel en fin de ligne

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

## Coordonnées géographiques et adresses des lieux (v1.15)

### Structure

La table `lieu_ref` contient les colonnes suivantes :

**Adresse postale :**
- `adresse_numero` : Numéro de rue (ex: "12", "12 bis")
- `adresse_voie` : Nom de la voie (ex: "rue de la Paix")
- `code_postal` : Code postal (ex: "72000")

**Coordonnées géographiques :**
- `latitude` : Latitude WGS84 (ex: 47.9960)
- `longitude` : Longitude WGS84 (ex: 0.1906)
- `geo_source` : Source des coordonnées (nominatim, google, manual)
- `geo_precision` : Précision (exact, approximate, street, city)

### Fichier CSV

Toutes les informations sont dans `corpus/lieu.csv` :
```csv
nom,ville,nom_normalise,adresse_numero,adresse_voie,code_postal,latitude,longitude,geo_source,geo_precision
Abbaye Royale de l'Epau,Le Mans,abbayeroyaleepau,,,72000,47.9876,0.2234,nominatim,exact
```

### Géocodage avec Nominatim

```bash
# Géocoder tous les lieux sans coordonnées
python scripts/geocode_lieux.py -v

# Mode simulation
python scripts/geocode_lieux.py --dry-run

# Limiter le nombre de lieux (pour tests)
python scripts/geocode_lieux.py --limit 10

# Forcer le regéocodage de tous les lieux
python scripts/geocode_lieux.py --force
```

### Synchronisation CSV → Base

Après modification manuelle de `lieu.csv`, synchroniser vers la base :
```bash
# Simulation
python scripts/sync_lieu_csv.py --dry-run

# Appliquer
python scripts/sync_lieu_csv.py -v
```

### Compatibilité PostGIS

Pour importer dans PostGIS :
```sql
-- Créer la géométrie POINT depuis lat/lon
ALTER TABLE lieu_ref ADD COLUMN geom geometry(Point, 4326);
UPDATE lieu_ref SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
```

## Import/Export CSV/XLSX (v1.21)

### Fichiers sources CSV/XLSX

La colonne `source_file` dans `biduls.description.csv` définit les fichiers sources pour chaque bidul :

**Formats supportés :**
- **CSV 2022** (biduls 265-275) : `tapage_biduleur_janvier_2022.csv`
- **CSV 2023+** (biduls 276-291) : `202301_tapage_biduleur_janvier_2023.csv`
- **XLSX 2025+** (biduls 306-311) : `202510_tapage_biduleur_Octobre_2025.xlsx`

**Multi-fichiers pour biduls d'été :**
Les biduls de juillet couvrent juillet ET août. Utiliser `|` comme séparateur :
```
source_file: tapage_biduleur_juillet_2022.csv|tapage_biduleur_aout_2022.csv
```

### Fonctions d'import (`core/csv_importer.py`)

| Fonction | Usage |
|----------|-------|
| `get_source_files_from_config()` | Récupère la liste des fichiers depuis `biduls.description.csv` |
| `import_xlsx()` | Importe un fichier XLSX (format 2025+) |
| `import_bidul_from_source()` | Importe depuis un ou plusieurs fichiers CSV/XLSX |
| `find_source_files()` | Trouve les fichiers sources pour un bidul |
| `normalize_xlsx_column()` | Normalise un nom de colonne XLSX |
| `find_xlsx_column()` | Trouve une colonne par patterns (préfère le match le plus court) |
| `is_valid_event_date()` | Filtre les dates invalides (requiert jour de semaine + numéro) |

### Mapping des colonnes XLSX

Le format XLSX 2025+ utilise des noms de colonnes avec newlines et espaces :
```python
XLSX_COLUMN_PATTERNS = {
    'festival': ['FESTOCHE', 'EVENEMENT'],
    'style_festival': ['STYLE', 'FESTOCHE', 'EVENEMENT'],
    'date': ['DATE'],
    'horaire': ['HEURE'],
    'lieu': ['LIEU'],
    'ville': ['VILLE'],
    'prix': ['PRIX'],
    'genre': ['GENRE 1'],
    'spectacle1': ['NOM SPECTACLE 1'],
    'artiste1': ['COMPAGNIE 1', 'GROUPE 1', 'ARTISTE 1'],
    'style1': ['STYLE', 'SPECTACLE 1', 'CONCERT 1'],
    # ... répété pour 2, 3, 4
}
```

**`find_xlsx_column()` préfère le match le plus court** : quand plusieurs colonnes matchent un pattern (ex: "DATE" et "DATE TAPAGE" pour `['date']`), la colonne la plus courte est retournée (match le plus spécifique).

### Filtrage des dates CSV/XLSX

Les événements CSV/XLSX sans date valide sont ignorés à l'import. La fonction `is_valid_event_date()` vérifie que le champ date contient un jour de semaine suivi d'un numéro de jour :
- **Valide** : `Dimanche 12`, `Lundi 1`, `Ma 3`, `Ven 31`
- **Invalide** : `Coups de coeur et en bref`, `12` (jour seul), texte vide

### Export avec clause WHERE (`core/csv_exporter.py`)

| Fonction | Usage |
|----------|-------|
| `export_events()` | Exporte les événements avec WHERE personnalisable |
| `export_bidul()` | Exporte un bidul spécifique |
| `export_range()` | Exporte une plage de biduls |

**Commande CLI :**
```bash
# Export par numéro
python cli.py export --numero 280 --output export_280.csv

# Export d'une plage
python cli.py export --range 280-285 --output exports/

# Export avec filtre WHERE personnalisé
python cli.py export --where "date_evenement >= '2023-01-01'" --output 2023_events.csv
python cli.py export --where "ville_raw = 'Le Mans'" --output lemans_events.csv

# Export XLSX
python cli.py export --numero 306 --format xlsx --output export_306.xlsx
```

**Requête SQL générée :**
```sql
SELECT e.bidul_numero, e.date_evenement, e.heure as horaire,
       e.lieu_raw as lieu, e.ville_raw as ville, e.tarif_raw as prix,
       e.nom as festival, e.genre_evenement as style_festival,
       e.type_evenement as genre,
       c.nom_spectacle, c.artiste, c.style, c.ordre
FROM evenement e
LEFT JOIN contenu_evenement c ON c.evenement_id = e.id
WHERE {where_clause}
ORDER BY e.bidul_numero, e.date_evenement, e.id, c.ordre
```

## Lieux génériques (v1.18)

### Concept

Les lieux génériques (Salle des fêtes, Église, Médiathèque, etc.) peuvent exister dans plusieurs villes. La contrainte unique est passée de `UNIQUE(nom)` à `UNIQUE(nom, ville)`.

### Patterns génériques

Les noms suivants sont considérés comme génériques (case-insensitive) :
- Salle des fêtes / Salle polyvalente / Salle municipale
- Église / Halles / Mairie
- Médiathèque / Bibliothèque
- Gymnase / Stade
- Foyer rural / Foyer des jeunes
- Centre culturel / Espace culturel
- Place de la mairie / Place de l'église

### Fonctions modifiées

Les fonctions de normalisation retournent maintenant 3 valeurs :

```python
# core/normalizer.py
def find_lieu_ref_id(lieu_raw: str, db_path: str, ville_raw: str = None) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Retourne (lieu_id, nom, ville)"""

def normalize_lieu(lieu_raw: str, db_path: str = None, ville_raw: str = None) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Retourne (lieu_id, nom, ville)"""
```

### Clé composite pour lieux génériques

Pour les lieux génériques, la clé d'index est composite :
```python
# Format: "(nom, ville)" pour les génériques
key = f"({nom.lower()}, {ville.lower()})"
# Exemple: "(salle des fêtes, arnage)"
```

### Migration

```bash
# Prévisualisation
python scripts/migrate_lieu_generic.py --dry-run

# Appliquer la migration
python scripts/migrate_lieu_generic.py --apply

# Vérifier
python scripts/migrate_lieu_generic.py --verify
```

### Vérification

```python
import sqlite3
conn = sqlite3.connect('database/bidul_archives.db')
cursor = conn.cursor()

# Compter les lieux génériques
cursor.execute('SELECT COUNT(*) FROM lieu_ref WHERE is_generic = 1')
print(f"Lieux génériques: {cursor.fetchone()[0]}")

# Lister les Salle des fêtes
cursor.execute('''
    SELECT nom, ville FROM lieu_ref
    WHERE LOWER(nom) = 'salle des fêtes'
    ORDER BY ville
''')
for row in cursor.fetchall():
    print(f"  {row[0]} - {row[1]}")
```

## Ajouter un pattern d'extraction d'artiste/spectacle

### Contexte
Le workflow `populate` utilise `parse_event_line_v2()` (fonction standalone) qui appelle `extract_before_lieu()` pour extraire les artistes/spectacles. La classe `EventParser._parse_event()` n'est PAS utilisée par `populate`.

### Architecture du parsing (IMPORTANT)

```
CLI populate
    └── parse_with_referentiel()
        └── _parse_bloc_with_referentiel() ou _parse_inline_with_referentiel()
            └── parse_event_line_v2()        ← fonction standalone
                └── extract_before_lieu()    ← extraction artistes/spectacles
```

**Attention** : `EventParser._extract_spectacle_artiste_pattern()` est utilisé uniquement par `_parse_event()`, qui n'est PAS dans le flux `populate`.

### Workflow pour ajouter un nouveau pattern

1. **Identifier le texte problématique**
   ```python
   # Récupérer le raw_text depuis la base
   SELECT raw_text FROM evenement WHERE bidul_numero = XXX AND raw_text LIKE '%pattern%'
   ```

2. **Tester le pattern regex isolément**
   ```python
   import re
   text = '...'  # raw_text exact
   pattern = re.compile(r'...')
   match = pattern.search(text)
   print(match.groups() if match else "No match")
   ```

3. **Ajouter le pattern dans `extract_before_lieu()`** (ligne ~2778)
   - C'est la fonction clé pour le flux `populate`
   - Chercher la section `if has_formatting_tags(before):` pour les patterns HTML
   - Ajouter le pattern AVANT le parsing classique

   ```python
   # Dans extract_before_lieu(), après les autres patterns spéciaux:
   mon_pattern = r'...'
   mon_match = re.search(mon_pattern, before)
   if mon_match:
       artiste_nom = mon_match.group(X).strip()
       if artiste_nom and len(artiste_nom) > 2:
           if not any(a['nom'].lower() == artiste_nom.lower() for a in result['artistes']):
               result['artistes'].append({'nom': artiste_nom, 'style': style, 'is_musical': False})
   ```

4. **Optionnel : ajouter aussi dans `_extract_spectacle_artiste_pattern()`** (ligne ~5487)
   - Pour la cohérence avec `EventParser._parse_event()`
   - Utile si d'autres flux utilisent cette méthode

5. **Tester avec populate**
   ```bash
   python cli.py purge --numero XXX
   python cli.py populate --numero XXX --replace --reparse

   # Vérifier le résultat
   python -c "
   import sqlite3
   conn = sqlite3.connect('database/bidul_archives.db')
   cursor = conn.cursor()
   cursor.execute('''
       SELECT e.raw_text, c.artiste, c.nom_spectacle
       FROM evenement e
       JOIN contenu_evenement c ON c.evenement_id = e.id
       WHERE e.bidul_numero = XXX AND e.raw_text LIKE '%pattern%'
   ''')
   for row in cursor.fetchall():
       print(f'artiste: {row[1]}, spectacle: {row[2]}')
   "
   ```

6. **Ajouter les tests unitaires** dans `tests/test_parser.py`
   - Tester `extract_before_lieu()` directement
   - Tester avec `EventParser._parse_event()` si pattern ajouté là aussi

7. **Lancer les benchmarks**
   ```bash
   python cli.py purge --numero 184 && python cli.py populate --numero 184 --replace
   python benchmark/compare_bidul.py 184  # Attendu: 94.6%
   python benchmark/compare_bidul.py 190  # Attendu: 91.5%
   ```

### Patterns existants dans `extract_before_lieu()`

| Pattern | Exemple | Ligne |
|---------|---------|-------|
| `"Spectacle" (style) de Auteur` | `"Venezuela" (théâtre) de Guy Helminger` | ~3106 |
| `"Spectacle" (style), Artiste` | `"L'instant magique" (illusion), Greg Bagot` | ~3133 |
| `<<Spectacle" de Auteur` | `<<Pichol" de Claude Bonadonna` (guillemet OCR) | ~3121 |
| Auteur avec initiales | `de C. Liscano`, `de J.-P. Dupont` | ~3121 |
| Artistes en `<b>gras</b>` | `<b>ARTISTE</b> (rock)` | via `extract_formatted_artistes_musicaux()` |
| Spectacles en `<b>"guillemets"</b>` | `<b>"Titre"</b>` | via `extract_formatted_spectacles()` |

### Validation du lieu - cas particuliers

| Cas | Exemple | Comportement |
|-----|---------|--------------|
| Lieu après `!` ou `.` | `Soirée X ! Le Passeport` | Lieu valide (séparateur) |
| Lieu commençant par article | `JEREMY Le La Ré Do` | Lieu valide (Le/La/L') |
| `de Prénom Nom` | `de Claude Bonadonna` | Ignoré (pattern auteur) |
| `(style)Lieu` collé | `(Th)Th. du passeur` | Lieu extrait |
| Ville du lieu hors référentiel | `Foyer Rural, Crosmières` | Ville du lieu gardée |

### Erreur fréquente

❌ **Ne pas modifier uniquement `_extract_spectacle_artiste_pattern()`** - cette méthode n'est pas appelée par `populate`.

✅ **Toujours modifier `extract_before_lieu()`** pour que le pattern fonctionne avec `populate`.

# Indexer - Guide Utilisateur

Guide complet des commandes CLI pour l'indexation des archives du Bidul.

## Installation

```bash
cd indexer
pip install -r requirements.txt
```

Dependances principales: `PyMuPDF`, `sqlite3` (inclus Python).

Pour l'OCR (PDFs scannes):
```bash
pip install google-cloud-vision pdf2image opencv-python
```

**Note:** L'OCR avec Google Cloud Vision necessite un fichier de credentials GCP (`gcp_creds_biduleur.json`).

## Demarrage rapide

```bash
# 1. Initialiser la base de donnees
python cli.py init

# 2. Peupler avec tous les PDFs disponibles
python cli.py populate

# 3. Voir les statistiques
python cli.py stats
```

---

## Commandes de base

### `init` - Initialiser la base

Cree la base de donnees et charge les referentiels (lieux, villes).

```bash
python cli.py init
```

Sortie:
```
Initialisation de la base: database/bidul_archives.db

Base initialisee:
  Lieux references: 543
  Villes referencees: 123
```

### `list` - Lister les PDFs disponibles

```bash
# Tous les PDFs
python cli.py list

# PDFs avec texte natif uniquement
python cli.py list --type texte

# PDFs scannes (necessitent OCR)
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
STATISTIQUES BASE DE DONNEES
==================================================

Biduls:      98
  Plage: 178 - 308

Evenements:  7542
  Periode: 2012-06-01 - 2024-12-31

Par source:
  csv: 2340
  pdf: 5202

Referentiels:
  Lieux:  543
  Villes: 123

Top 5 villes:
  Le Mans: 5823
  La Fleche: 412
  Allonnes: 287
  ...
```

---

## Extraction et peuplement

### `populate` - Peupler la base

Commande principale pour extraire les evenements. Utilise les CSV de reference si disponibles, sinon extrait depuis les PDFs.

```bash
# Peupler tous les Biduls disponibles
python cli.py populate

# Peupler un seul Bidul
python cli.py populate --numero 280

# Peupler une plage
python cli.py populate --range 280-290

# Mode simulation (affiche sans sauvegarder)
python cli.py populate --dry-run

# Remplacer les donnees existantes
python cli.py populate --numero 280 --replace

# Forcer depuis PDF (ignorer les CSV)
python cli.py populate --pdf-only

# Uniquement les Biduls avec CSV de reference
python cli.py populate --csv-only
```

Options:
| Option | Description |
|--------|-------------|
| `--numero N` | Traiter uniquement le Bidul N |
| `--range N-M` | Traiter les Biduls de N a M |
| `--csv-only` | Uniquement les Biduls avec CSV |
| `--pdf-only` | Ignorer les CSV, forcer extraction PDF |
| `--dry-run` | Simulation sans sauvegarde |
| `--replace` | Remplacer les donnees existantes |
| `--no-ocr` | Desactiver l'OCR pour les scans |
| `--engine` | Moteur OCR: `google` (defaut), `paddleocr`, `easyocr` |
| `--dpi` | Resolution OCR (defaut: 200) |

### `extract` - Extraire un PDF

Extraction directe d'un PDF (sans priorite CSV).

```bash
# Extraire un Bidul
python cli.py extract --numero 280

# Extraire une plage
python cli.py extract --range 280-290

# Mode simulation
python cli.py extract --numero 280 --dry-run

# Forcer extraction d'un scan
python cli.py extract --numero 150 --force

# Re-parser les evenements existants (conserve raw_text)
python cli.py extract --numero 280 --reparse
```

### `--reparse` - Re-parser les evenements existants

L'option `--reparse` permet de re-parser les evenements depuis le texte brut complet (`bidul.raw_text`) sans re-extraire le PDF. Utile apres correction des patterns de parsing.

**Fonctionnement:**
1. Recupere le texte brut complet du Bidul (`bidul.raw_text`)
2. Supprime TOUS les evenements et contenus associes du Bidul
3. Re-parse le texte complet avec l'algorithme actuel (split sur dates inclus)
4. Insere les nouveaux evenements

```bash
# Re-parser un Bidul
python cli.py populate --numero 102 --reparse

# Re-parser en mode simulation
python cli.py populate --numero 102 --reparse --dry-run

# Re-parser une plage
python cli.py populate --range 100-110 --reparse
```

**Note:** Le reparse utilise `bidul.raw_text` (texte complet) et non `evenement.raw_text` (deja splitte). Cela permet de beneficier des nouvelles regles de split (ex: dates multiples `Lu 12/Ma 13/Me 14:` → 3 evenements).

---

## Commandes OCR

### `ocr` - Extraire le texte d'un PDF scanne

Extrait le texte d'un PDF scanne via OCR.

```bash
# Extraction avec Google Cloud Vision (recommande)
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
| `--dpi` | Resolution de conversion (defaut: 200) |
| `--output` | Fichier de sortie pour le texte |
| `--raw` | Ne pas appliquer le post-traitement |

### `ocr-extract` - OCR + parsing des evenements

Extrait le texte via OCR et parse les evenements en une seule commande.

```bash
# Un seul Bidul
python cli.py ocr-extract --numero 158 --dry-run

# Plage de Biduls
python cli.py ocr-extract --range 150-160

# Avec moteur specifique
python cli.py ocr-extract --numero 158 --engine paddleocr
```

Options:
| Option | Description |
|--------|-------------|
| `--numero N` | Traiter le Bidul N |
| `--range N-M` | Traiter les Biduls de N a M |
| `--engine` | Moteur OCR (defaut: `google`) |
| `--dpi` | Resolution (defaut: 200) |
| `--dry-run` | Simulation sans sauvegarde |

### `ocr-test` - Tester l'OCR

Teste l'OCR sur un echantillon de PDFs scannes.

```bash
python cli.py ocr-test --samples 5
```

---

## Validation et comparaison

### `validate` - Afficher une extraction

Affiche les evenements extraits pour un Bidul.

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

42 evenements extraits:

[1] 2023-05-03 - 21h
    Artistes: MOONLIGHT BENJAMIN
    Lieu: La Fonderie, Le Mans
    Prix: 12EUR
    Type: concert | Confidence: 0.95
    Raw: Ve 3 * MOONLIGHT BENJAMIN (blues-soul)...

[2] 2023-05-04 - 20h30
    Spectacles: Ma tata, mon pingouin...
    Lieu: Theatre Paul Scarron, Le Mans
    ...
```

### `compare` - Comparer avec CSV de reference

Compare l'extraction avec le fichier CSV source (si disponible).

```bash
# Comparaison simple
python cli.py compare --numero 280

# Avec details des differences
python cli.py compare --numero 280 --details
```

Sortie:
```
======================================================================
COMPARAISON BIDUL #280 - 05/2023
======================================================================
PDF: bidul_280_mai_2023.pdf
CSV: 202305_tapage_biduleur_mai_2023.csv

Evenements extraits (base): 42
Evenements reference (CSV): 45

======================================================================
RESULTATS
======================================================================
Matches:           40
CSV uniquement:    5 (dans reference mais pas extrait)
Base uniquement:   2 (extrait mais pas dans reference)

Recall:    88.9% (40/45 de la reference trouves)
Precision: 95.2% (40/42 extraits sont corrects)
```

---

## Gestion des donnees

### `purge` - Supprimer des evenements

```bash
# Supprimer les evenements d'un Bidul
python cli.py purge --numero 280

# Supprimer une plage
python cli.py purge --range 280-290

# Supprimer TOUT
python cli.py purge --all

# Mode simulation
python cli.py purge --numero 280 --dry-run
```

---

## Consolidation et qualite

### `migrate` - Migration du schema

Ajoute les tables pour le systeme de consolidation (review, corrections, aliases).

```bash
python cli.py migrate
```

### `triage` - Triage automatique

Classe les evenements par niveau de confiance.

```bash
python cli.py triage

# Sans detection de doublons
python cli.py triage --skip-duplicates
```

Sortie:
```
Triage automatique des evenements...

Resultats du triage:
  OK (confidence >= 0.9):     5234
  A revoir (0.7-0.9):         1856
  Flagges (< 0.7):            452
  Doublons potentiels:        23

Statut global:
  ok: 5234
  to_review: 1856
  flagged: 452
```

### `apply-aliases` - Appliquer les alias artistes

Normalise les noms d'artistes en utilisant les alias definis.

```bash
# Appliquer les alias existants
python cli.py apply-aliases

# Synchroniser depuis le fichier JSON d'abord
python cli.py apply-aliases --sync-json
```

### `review` - Session de review interactive

Interface en ligne de commande pour verifier manuellement les evenements.

```bash
# Review tous les evenements "to_review"
python cli.py review --status to_review

# Review un Bidul specifique
python cli.py review --numero 280

# Review les evenements flagges
python cli.py review --status flagged
```

Statuts possibles: `pending`, `to_review`, `flagged`, `ok`

### `quality-report` - Rapport de qualite

Genere un rapport detaille sur la qualite des donnees.

```bash
python cli.py quality-report
```

Sortie:
```
============================================================
RAPPORT DE QUALITE
============================================================

Total evenements: 7542

Par statut de review:
  ok: 5234 (69.4%)
  to_review: 1856 (24.6%)
  flagged: 452 (6.0%)

Verifies: 3421 (45.4%)

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
  Lieux non resolus: 234
```

### `analyze-corrections` - Analyser les corrections

Affiche les patterns de correction pour ameliorer l'extraction.

```bash
python cli.py analyze-corrections
```

---

## Gestion du corpus (referentiels)

### `corpus-generate` - Generer les CSV de corpus

Genere/met a jour les fichiers CSV de referentiels depuis la base.

```bash
python cli.py corpus-generate
```

### `corpus-stats` - Statistiques des corpus

Affiche les statistiques des fichiers de corpus.

```bash
python cli.py corpus-stats
```

### `corpus-test` - Tester la normalisation

Teste le matching d'un lieu ou artiste.

```bash
# Tester un lieu
python cli.py corpus-test "Th. Paul Scarron"

# Tester un artiste
python cli.py corpus-test "Dj SUPER LUCIEN" -t artiste
```

### `corpus-add-lieu-alias` - Ajouter un alias de lieu

```bash
python cli.py corpus-add-lieu-alias "Th. Municipal" "Theatre Municipal"
```

### `corpus-add-artiste-alias` - Ajouter un alias d'artiste

```bash
python cli.py corpus-add-artiste-alias "SMAK FLY" "SMAC FLY"
```

### `corpus-dedupe-lieux` - Dedupliquer les lieux

Detecte et fusionne les doublons dans lieu.csv.

```bash
# Analyse (dry-run)
python cli.py corpus-dedupe-lieux

# Appliquer
python cli.py corpus-dedupe-lieux --apply

# Exporter un rapport CSV
python cli.py corpus-dedupe-lieux --report

# Review interactif par mot-cle
python cli.py corpus-dedupe-lieux -k abbaye --interactive
```

### `corpus-dedupe-artistes` - Dedupliquer les artistes

Detecte et fusionne les doublons dans artiste.csv.

```bash
# Analyse (dry-run)
python cli.py corpus-dedupe-artistes

# Appliquer
python cli.py corpus-dedupe-artistes --apply

# Review interactif par mot-cle
python cli.py corpus-dedupe-artistes -k jazz --interactive
```

---

## Synchronisation DB <-> Corpus

Ces commandes permettent de synchroniser les referentiels entre les fichiers CSV et la base de donnees.

### `sync-corpus-to-db` - Importer les CSV dans la DB

Importe les fichiers CSV du corpus dans les tables de la DB. **Attention: cette commande vide les tables avant import.**

```bash
python cli.py sync-corpus-to-db
```

Sortie:
```
=== Import Corpus CSV -> DB ===

  (tables lieu_ref et lieu_alias videes)
+ Importe 385 lieux dans lieu_ref
+ Importe 239 alias de lieux dans lieu_alias
  (tables artiste_ref et artiste_alias videes)
+ Importe 1944 artistes dans artiste_ref
+ Importe 442 alias d'artistes dans artiste_alias
  (table ville_ref videe)
+ Importe 124 villes dans ville_ref

+ Import termine!
```

### `sync-db-to-corpus` - Exporter la DB vers les CSV

Exporte les tables de la DB vers les fichiers CSV du corpus.

```bash
python cli.py sync-db-to-corpus
```

### `sync-dedupe-db` - Dedupliquer en DB

Detecte et fusionne les doublons directement dans la DB.

```bash
# Analyse (dry-run)
python cli.py sync-dedupe-db

# Appliquer les changements
python cli.py sync-dedupe-db --apply
```

### `sync-stats` - Statistiques des tables de reference

Affiche les statistiques des tables de reference en DB.

```bash
python cli.py sync-stats
```

Sortie:
```
=== Statistiques DB ===

  lieu_ref                     385 entrees
  lieu_ref (inactifs)            0 entrees
  lieu_alias                   237 entrees
  artiste_ref                 1944 entrees
  artiste_ref (inactifs)         0 entrees
  artiste_alias                442 entrees
  ville_ref                    124 entrees
```

---

## Matching des referentiels (ref_id)

Ces commandes permettent de lier les donnees brutes aux referentiels normalises.

### `ref-migrate` - Migration pour artiste_ref_id

Ajoute la colonne `artiste_ref_id` a la table `contenu_evenement`.

```bash
python cli.py ref-migrate
```

### `ref-backfill` - Back-populate les ref_id

Met a jour les colonnes `lieu_ref_id` (dans `evenement`) et `artiste_ref_id` (dans `contenu_evenement`) pour les donnees existantes.

```bash
python cli.py ref-backfill
```

Sortie:
```
=== Back-populate ref_id ===

Chargement des referentiels...
  - 752 variantes de lieux
  - 2578 variantes d'artistes

1. Matching lieux...
   Lieux matches: 18896/24595 (76.8%)

2. Matching artistes...
   Artistes matches: 11689/27017 (43.3%)

Back-populate termine!
```

### `ref-stats` - Statistiques de matching

Affiche les statistiques de matching et les top non-matches.

```bash
python cli.py ref-stats
```

Sortie:
```
=== Statistiques de matching ===

Lieux:
  Total avec lieu_raw: 24595
  Matches (lieu_ref_id): 19281 (78.4%)
  Non matches: 5314

Artistes:
  Total avec artiste: 27017
  Matches (artiste_ref_id): 11689 (43.3%)
  Non matches: 15328

--- Top 10 lieux non matches ---
   112 x Le Mackeson
    65 x Le Wagon
    ...

--- Top 10 artistes non matches ---
    20 x ...
    ...
```

---

## Nettoyage des donnees

### `clean-all` - Tous les nettoyages

Execute tous les scripts de nettoyage.

```bash
python cli.py clean-all
```

### `clean-prix` - Nettoyer les prix

Corrige les prix aberrants.

```bash
python cli.py clean-prix
```

### `clean-lieux-dups` - Fusionner les doublons de lieux

Fusionne les doublons de lieux dans la base.

```bash
python cli.py clean-lieux-dups
```

---

## Workflow complet recommande

### 1. Initialisation et import

```bash
# Initialiser la base
python cli.py init

# Peupler avec tous les PDFs
python cli.py populate

# Voir les stats
python cli.py stats
```

### 2. Gestion des referentiels

```bash
# Editer manuellement les CSV du corpus
# corpus/lieu.csv, corpus/artiste.csv, etc.

# Synchroniser les CSV vers la DB
python cli.py sync-corpus-to-db

# Dedupliquer en DB
python cli.py sync-dedupe-db --apply

# Exporter vers CSV (pour backup/versioning)
python cli.py sync-db-to-corpus
```

### 3. Matching et normalisation

```bash
# Migration (une seule fois)
python cli.py ref-migrate

# Back-populate les ref_id
python cli.py ref-backfill

# Voir les stats de matching
python cli.py ref-stats
```

### 4. Qualite et review

```bash
# Triage automatique
python cli.py triage

# Rapport de qualite
python cli.py quality-report

# Review interactif
python cli.py review --status to_review
```

---

## Options globales

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Mode verbeux (affiche les logs DEBUG) |

---

## Structure des fichiers

```
indexer/
+-- cli.py                 # Point d'entree CLI
+-- archives/              # PDFs sources
|   +-- bidul_XXX_*.pdf
+-- corpus/                # Referentiels CSV
|   +-- lieu.csv           # Lieux canoniques
|   +-- lieu_alias.csv     # Aliases de lieux
|   +-- artiste.csv        # Artistes canoniques
|   +-- artiste_alias.csv  # Aliases d'artistes
|   +-- ville.csv          # Villes
+-- database/
|   +-- schema_v2.sql      # Schema SQL
|   +-- bidul_archives.db  # Base SQLite
|   +-- queries_analytiques.sql  # Requetes SQL utiles
+-- core/                  # Modules principaux
|   +-- extractor.py
|   +-- parser.py
|   +-- db.py
|   +-- normalizer.py      # Matching lieu/artiste
|   +-- ...
+-- scripts/               # Scripts utilitaires
|   +-- sync_corpus_db.py
|   +-- migrate_ref_matching.py
|   +-- dedupe_lieux.py
|   +-- dedupe_artistes.py
+-- benchmark/             # Tests de qualite
    +-- compare_bidul.py
    +-- bidul_184_expected.csv
    +-- bidul_190_expected.csv
```

---

## Schema de la base de donnees

### Tables principales

| Table | Description |
|-------|-------------|
| `bidul` | Metadonnees des numeros du Bidul |
| `evenement` | Evenements extraits |
| `contenu_evenement` | Artistes/spectacles (relation 1-N avec evenement) |

### Tables de referentiels

| Table | Description |
|-------|-------------|
| `lieu_ref` | Lieux canoniques (avec colonne `actif`) |
| `lieu_alias` | Aliases de lieux -> `lieu_nom` |
| `artiste_ref` | Artistes canoniques (avec colonne `actif`) |
| `artiste_alias` | Aliases d'artistes -> `artiste_nom` |
| `ville_ref` | Villes |

### Colonnes de matching

| Colonne | Table | Description |
|---------|-------|-------------|
| `lieu_ref_id` | evenement | FK vers lieu_ref.id |
| `ville_ref_id` | evenement | FK vers ville_ref.id |
| `artiste_ref_id` | contenu_evenement | FK vers artiste_ref.id |

---

## Depannage

### "PDF non trouve"
Verifiez que le PDF est dans `archives/` avec le bon format de nom:
`bidul_XXX_mois_YYYY.pdf`

### "PDF scan detecte"
Les PDFs avant le n 178 sont des scans. Utilisez `--force` ou convertissez-les en PDF texte avec OCR.

### "Lieu non resolu"
Ajoutez le lieu dans `corpus/lieu.csv`:
```csv
nom,ville
Nouveau Lieu,Le Mans
```
Puis synchronisez: `python cli.py sync-corpus-to-db`

### "Artiste non matche"
Ajoutez l'alias dans `corpus/artiste_alias.csv`:
```csv
variante,artiste_nom
VARIANTE DU NOM,Nom Canonique
```
Puis synchronisez et re-matchez:
```bash
python cli.py sync-corpus-to-db
python cli.py ref-backfill
```

### "Confidence faible"
Verifiez le texte brut avec `validate` puis corrigez le parsing ou ajoutez le lieu/ville au referentiel.

### Vider les caches apres modification des referentiels
Si vous modifiez les CSV et que les changements ne sont pas pris en compte:
```bash
python cli.py sync-corpus-to-db  # Re-importe et vide les caches
python cli.py ref-backfill       # Re-matche avec les nouvelles donnees
```

---

## Algorithme de parsing

### Vue d'ensemble

L'algorithme de parsing extrait les evenements depuis le texte brut en suivant une strategie "lieu d'abord":

1. **Split sur les dates** - Decoupe le texte en blocs par date
2. **Detection du lieu** - Trouve le lieu via le referentiel
3. **Extraction avant/apres lieu** - Parse les artistes/spectacles avant, heure/tarif apres
4. **Normalisation** - Normalise les villes et lieux

### Formats de dates supportes

| Format | Exemple | Resultat |
|--------|---------|----------|
| Date simple | `Ve 3 :` | 1 evenement (jour 3) |
| Dates multiples | `Lu 12/Ma 13/Me 14 :` | 3 evenements (jours 12, 13, 14) |
| Dates multiples (autres separateurs) | `Lu 12 & Ma 13 :` ou `Lu 12, Ma 13 :` | 2 evenements |
| Plage de dates | `Je 23 au Sa 25 :` | 3 evenements (jours 23, 24, 25) |
| Plage avec prefixe | `Du Je 23 au Sa 25 :` | 3 evenements |

### Extraction des artistes

**Format standard:**
```
<b>NOM ARTISTE</b> <i>(style)</i>
```

**Artistes multiples (separes par `+`):**
```
<b>ARTISTE1 + ARTISTE2</b> → 2 artistes
```

**Artistes avec prefixe numerique:**
```
<b>0' BROTHERS</b>   → artiste "0' BROTHERS"
<b>2 MANY DJs</b>    → artiste "2 MANY DJs"
```

**Artistes avec heures individuelles:**
```
ARTISTE1 (style) 16h + ARTISTE2 (style) 17h
→ 2 artistes, heure de l'evenement = 16h (la plus tot)
```

### Extraction des spectacles

Les spectacles sont identifies par des guillemets en gras:
```
<b>„Titre du spectacle"</b>
<b>«Titre»</b>
```

### Evenements nommes

Les evenements avec un nom (festivals, soirees thematiques) sont detectes:
```
Festival Soirs au Village avec <b>ARTISTE1 + ARTISTE2</b>
→ nom_evenement = "Festival Soirs au Village"
```

Mots-cles detectes: Festival, Fete, Soiree, Nuit, Journee, Apero, etc.

### Normalisation des villes

Certaines variantes sont automatiquement normalisees:
- `Saint Calais` → `Saint-Calais`
- `La Ferte Bernard` → `La Ferté-Bernard`
- `Chateau du Loir` → `Château-du-Loir`

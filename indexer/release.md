# Release Notes - Indexer v1.13

## Vue d'ensemble

Version avec amélioration de l'extraction des lieux pour les événements Allonnes et correction des patterns de parsing pour bidul 309.

## Nouveautés v1.13

### Extraction des lieux Allonnes

Ajout des lieux spécifiques pour Allonnes au référentiel :
- **Les Métairies** : Salle de spectacle
- **Salle G. Moquet** : Salle municipale
- **CHS** : Centre hospitalier
- **Maison des arts** : Lieu culturel
- **Guinguette** : Espace festif
- **Parvis de la Mairie place du Mail** : Espace extérieur

### Alias pour noms abrégés

Nouveaux alias dans `lieu_alias.csv` pour les formats OCR abrégés :
- `Th. de Chaoué` → `Théâtre de Chaoué`
- `Les Métairies` → `Les Métairies`

### Corrections parsing bidul 309

- **PRIX LIBRE** : L'artiste "PRIX LIBRE" en `<b>PRIX LIBRE</b>` n'est plus confondu avec un tarif
- **Bullet K OCR** : Le caractère `K` isolé (`\nK\n`) est reconnu comme bullet point `•`
- **Validation lieu** : Les lieux précédés de virgule/parenthèse sont correctement validés (ex: "MOULE FRIPES #5, Le Barouf")
- **Double slash multiline** : Le pattern `//` pour extraction nom/artiste supporte les newlines (`re.DOTALL`)

### Benchmarks

| Bidul | Score v1.12 | Score v1.13 |
|-------|-------------|-------------|
| 184 | 95.7% | 95.7% |
| 309 | N/A | 18 événements Allonnes OK |

### Tests

- 122 tests unitaires passent
- Benchmark 184 : 95.7%

---

# Release Notes - Indexer v1.11

## Vue d'ensemble

Version avec amélioration de l'extraction OCR par sections : rotation de page entière avant découpage, découpage en colonnes physiques, et support des colonnes `p*_orientation_pdf` pour distinguer l'orientation du PDF de celle du texte.

## Nouveautés v1.11

### Rotation de page entière avant découpage

L'extraction par sections applique maintenant la rotation sur la page **entière** avant de découper les sections A6. Cela corrige le problème où les sections étaient définies sur l'image PDF non rotée.

**Workflow d'extraction :**
1. Rotation 90° horaire de la page (si `orientation_pdf != orientation_texte`)
2. Découpage en sections S1/S2/S3/S4 sur l'image rotée
3. OCR de chaque section avec découpage physique des colonnes

### Colonnes `p*_orientation_pdf`

Nouvelles colonnes dans `biduls.description.csv` pour distinguer l'orientation du PDF de celle du texte :

| Colonne | Description |
|---------|-------------|
| `p1_orientation_pdf` | Orientation du PDF page 1 (portrait/paysage) |
| `p2_orientation_pdf` | Orientation du PDF page 2 (portrait/paysage) |

**Cas d'usage** : Biduls 2-11 où le PDF est en portrait mais le texte est imprimé en paysage.

### Découpage physique des colonnes

Pour les sections avec plusieurs colonnes (`p*_colonnes > 1`), l'image est maintenant physiquement coupée en bandes verticales avant OCR. Chaque colonne est OCR séparément puis les résultats sont concaténés dans l'ordre de lecture (gauche → droite).

**Avant** : Google Vision triait les blocs par position X (résultats incohérents)
**Après** : Colonnes physiquement séparées, OCR indépendant par colonne

### Format date `inline_inherited`

Support amélioré du format `inline_inherited` (biduls 1-16) :
- Patterns de date : `jeu 05:`, `ven 06:`, etc. (2-3 lettres, deux-points optionnel)
- Lignes de continuation jointes à l'événement précédent
- Héritage de date pour les événements sans date explicite

### Tests ajoutés

- `TestPageSectionConfigRotation` : 4 tests pour la logique rotation PDF vs texte
- `TestSectionCropperRotation` : 2 tests pour rotation clockwise/counter-clockwise
- `TestBidulSectionConfigOrientationPdf` : 3 tests pour config bidul 5

### Marge inter-colonnes (gutter)

Pour éviter le chevauchement de texte entre colonnes adjacentes, une marge de 3% est rognée de chaque côté de la frontière entre colonnes. Pour 2 colonnes, cela crée une "zone morte" de 6% au centre.

**Avant** : Le texte de la colonne droite ("lun", "SORTIR?") apparaissait dans la colonne gauche
**Après** : Colonnes proprement séparées sans chevauchement

### Benchmarks

| Bidul | Score v1.10 | Score v1.11 |
|-------|-------------|-------------|
| 5 | N/A | 53 événements (nouveau) |
| 184 | 95.4% | 95.4% |
| 190 | 91.2% | 91.2% |

### Prochaines étapes (v1.12)

- [ ] Templates SVG pour définir les zones d'extraction avec précision
- [ ] Édition manuelle des zones problématiques
- [ ] Fallback automatique : SVG personnalisé > config CSV > calcul par défaut

---

# Release Notes - Indexer v1.10

## Vue d'ensemble

Version avec amélioration majeure de la gestion des événements régionaux : flag `is_regional` correctement assigné, dashboard HTML avec distinction local/régional, et récupération des événements locaux mixés dans la section régionale (problème OCR colonnes mélangées).

## Nouveautés v1.10

### Flag `is_regional` correctement assigné

Le flag `is_regional` est maintenant automatiquement assigné à chaque événement en utilisant `detect_regional()` :

| Source | Détection |
|--------|-----------|
| Lieu sarthois (Le PCV, Bar Le Palais...) | `is_regional = False` |
| Ville sarthoise (Le Mans, Allonnes...) | `is_regional = False` |
| Code département (72) | `is_regional = False` |
| Code département hors 72 (49, 53, 61...) | `is_regional = True` |
| Lieu/ville hors Sarthe (Chabada, Tours...) | `is_regional = True` |

**Impact** : Les événements locaux incorrectement placés dans la section régionale (à cause d'un OCR mélangé) sont maintenant récupérés.

### Dashboard HTML avec distinction local/régional

Le dashboard HTML (`python cli.py stats --html`) affiche maintenant :

- **KPIs séparés** : événements totaux, locaux (97.4%), régionaux (2.6%)
- **Graphique avec barres empilées** : cyan pour local, violet pour régional
- **Boutons de filtre** : Tous, Événements, Locaux, Régionaux, Contenus
- **Tooltip enrichi** : affiche le détail local + régional au survol
- **Scores qualité par type** : score_local, score_regional

### Refactorisation du parser pour la section régionale

Les fonctions `parse_with_referentiel()` ont été refactorisées pour :

1. Séparer le texte en sections locale et régionale via `split_regional_section()`
2. Parser chaque section indépendamment
3. Appliquer `detect_regional()` sur chaque événement
4. Log des corrections (événements locaux récupérés de la section régionale)

### Tests

Tous les 112 tests passent. Benchmarks stables :
- Bidul 184 : 95.4%
- Bidul 190 : 91.2%

---

# Release Notes - Indexer v1.9

## Vue d'ensemble

Version avec corrections majeures du parsing de dates et amélioration du découpage des événements pour les formats inline et bloc.

## Nouveautés v1.9

### Correction des faux splits sur "de 18 mois", "de 14 ans"

Le pattern de jour abrégé `[DLMJVS][aeiou]?` matchait incorrectement "de" comme un jour de semaine. Remplacé par un pattern strict avec les abréviations exactes :

```
Lu, Ma, Me, Je, Ve, Sa, Di
```

**Avant :**
```
Ma 29: Les Spectaculaires : « Gargantua » (à partir
de 14 ans) par Julien Mellano...
→ 2 événements (split sur "de 14")
```

**Après :**
```
→ 1 événement (texte multi-ligne préservé)
```

### Support du format date avec mois explicite (DD/MM)

Nouveaux patterns de date reconnus :

| Pattern | Exemple | Résultat |
|---------|---------|----------|
| Du DD au DD/MM | `Du 31 au 03/02:` | 4 événements (31 jan, 1, 2, 3 fév) |
| Jour DD/MM | `Ve 01/02:` | 1 événement (1er février) |
| Jour DD/MM | `Sa 15/03:` | 1 événement (15 mars) |

Utile pour les événements à cheval sur deux mois.

### Gestion des caractères parasites OCR avant les dates

Les caractères OCR parasites (`+`, `t`, `†`) avant les dates sont maintenant ignorés :

| Texte OCR | Résultat |
|-----------|----------|
| `+Ma 14: Événement` | Split sur `Ma 14` ✓ |
| `tJe 16: Événement` | Split sur `Je 16` ✓ |
| `†Ve 17: Événement` | Split sur `Ve 17` ✓ |

### Découpage des événements fusionnés (format bloc)

Nouvelle fonction `split_bloc_fused_events()` pour séparer les événements collés sur une même ligne :

**Pattern détecté :** `prix€ NOM_EN_MAJUSCULES` ou `prix€ Soirée`

**Exemple :**
```
ARTISTE1 (style), Lieu, 21h, 0€ ARTISTE2 (style), Lieu, 20h, 3€
→ 2 événements distincts
```

Cette fonction est automatiquement appelée dans le parsing des blocs.

### Paramètre `nom_evenement` pour la détection d'artifacts

Les événements avec un nom reconnu (Soirée X, Festival X, etc.) ne sont plus filtrés comme artifacts même sans lieu/artiste/spectacle.

### Tests ajoutés

- `TestSplitOnDatesV2NoFalseSplit` : 3 tests pour éviter les faux splits
- `TestParseDatePrefixV2WithMonth` : 3 tests pour les dates DD/MM
- `TestEventParserInlineWithMonthDates` : 2 tests d'intégration
- `TestSplitOnDatesV2WithParasiticChars` : 3 tests pour les caractères OCR
- `TestSplitBlocFusedEvents` : 3 tests pour les événements fusionnés

### Benchmarks

| Bidul | Score v1.8 | Score v1.9 |
|-------|------------|------------|
| 184 | 95.1% | 95.4% |
| 190 | 91.2% | 91.2% |

---

# Release Notes - Indexer v1.8

## Vue d'ensemble

Version avec support du Bidul d'été (juillet couvrant juillet+août), amélioration de l'extraction des lieux et villes, et corrections pour les anciens formats OCR.

## Nouveautés v1.8

### Support du Bidul d'été (juillet/août)

Le Bidul de juillet couvre traditionnellement les mois de juillet ET août. La CLI supporte maintenant ce cas :

```bash
python cli.py populate --numero 307  # Bidul juillet 2025 → événements juillet + août
```

Le mapping date ↔ numéro gère automatiquement l'absence de Bidul en août.

### Dates avec nom de mois

Support des formats de date incluant le nom du mois (courant dans les Biduls d'été) :

```
Vendredi 9 juillet → 2025-07-09
Samedi 14 août → 2025-08-14
```

### Option `--numero` avec valeurs multiples non-consécutives

```bash
python cli.py populate --numero 102,117,190  # Plusieurs numéros séparés par virgule
```

### Option `pages_override` dans biduls.description.csv

Nouvelle colonne pour forcer l'extraction de pages spécifiques :

| Bidul | pages_override | Effet |
|-------|----------------|-------|
| 228 | `1,2` | Extrait pages 1 et 2 au lieu de page 3 |
| 188 | `2` | Extrait uniquement page 2 |

### Extraction améliorée des lieux hors référentiel

Correction du parsing pour les lieux non présents dans le référentiel, notamment ceux avec des patterns de guillemets atypiques issus de l'OCR :

| Problème | Exemple | Correction |
|----------|---------|------------|
| Guillemets orphelins | `<<DUO D'AMOUR" (théâtre), Salle André Voisin...` | `smart_split` détecte maintenant les guillemets fermants après texte alphanumérique |
| Code département | `Fresnay-sur-Sarthe (72)` | Le `(72)` est retiré avant normalisation ville |

### Reconnaissance des acronymes de lieux

Ajout d'une liste d'acronymes connus qui ne doivent pas être filtrés comme artistes :

- `ITEMM` (Institut Technologique Européen des Métiers de la Musique)
- `MJC` (Maison des Jeunes et de la Culture)
- `FNAC`, `CSC`, `MPT`, `CAC`, `EMM`

### Extraction des lieux avec heure intégrée

Support des lieux où l'heure est directement attachée :

```
Bar Le Palais de 19h à 21h → lieu_raw = "Bar Le Palais"
```

### Normalisation des apostrophes

Les apostrophes typographiques (`'` U+2019) et ASCII (`'` U+0027) sont maintenant interchangeables pour le matching des lieux comme `L'Inventaire`, `L'Oasis`.

### Détection des événements "scène ouverte"

Le pattern `Scène ouverte` est maintenant reconnu comme nom d'événement et n'est plus confondu avec un lieu.

### Reconnaissance du pattern "collectif XXX"

Les collectifs d'artistes sont maintenant extraits correctement :

```
«Spectacle» (théâtre), collectif Grand Maximum → artiste = "Collectif Grand Maximum"
```

### Support des abréviations de jours à 3 lettres

Les formats de date avec abréviations à 3 lettres sont maintenant reconnus :

```
Jeu 02, Ven 03, Sam 04, Dim 05 → dates correctement parsées
```

### Nettoyage HTML des styles

Les balises HTML résiduelles dans les styles sont maintenant nettoyées :

```
<i>jazz</i> → jazz
rock</i> → rock
```

### Dashboard qualité (KPIs)

Le dashboard HTML (`python cli.py stats --html`) inclut maintenant des métriques de qualité :

**Score global** : Pourcentage d'événements complets (avec lieu, heure, tarif et contenu normalisés).

**Complétude par champ** :
- Lieu normalisé / Lieu raw
- Heure / Tarif
- Artiste normalisé / Style

**Visualisations** :
- Barres de progression colorées (vert ≥80%, orange ≥50%, rouge <50%)
- Graphique d'évolution par période (1997-1999, 2000-2004, etc.)
- Overlay du score qualité sur le graphique principal

**Détails** :
- Top 10 lieux à normaliser
- Top 10 artistes à normaliser
- Distribution des styles (top 15)

Bouton "Qualité" pour afficher/masquer les sections qualité.

```bash
python cli.py stats --html
# → stats/bidul_stats.html avec score qualité 48.1%
```

### Benchmarks

| Bidul | Score v1.7 | Score v1.8 |
|-------|------------|------------|
| 102 | 92.4% | 92.4% |
| 117 | 94.7% | 95.3% |
| 184 | 95.1% | 95.1% |
| 190 | 91.2% | 91.2% |

---

# Release Notes - Indexer v1.7

## Vue d'ensemble

Version avec filtrage automatique des événements régionaux et artifacts, plus génération de dashboard HTML pour les statistiques.

## Nouveautés v1.7

### Filtrage des événements régionaux

Nouveau module `core/regional_filter.py` pour détecter et filtrer les événements hors département 72 (Sarthe) :

| Critère | Exemple | Résultat |
|---------|---------|----------|
| Code département (72) | `Concert, Le Mans (72)` | LOCAL |
| Ville sarthoise | `Allonnes`, `La Flèche` | LOCAL |
| Lieu au Mans | `Palais des Congrès, Le Mans` | LOCAL |
| Code département hors 72 | `Chabada, Angers (49)` | RÉGIONAL |
| Lieu connu hors Sarthe | `Le Chabada`, `L'Ubu` | RÉGIONAL |
| Ville hors Sarthe | `Laval`, `Nantes`, `Rennes` | RÉGIONAL |

**Utilisation :**
```bash
python cli.py populate --reparse                    # Exclut les régionaux (défaut)
python cli.py populate --reparse --include-regional # Inclut les régionaux (is_regional=True)
```

### Filtrage des artifacts (faux événements)

Nouveau module `core/artifact_filter.py` pour exclure automatiquement les blocs qui ne sont pas de vrais événements :

| Critère | Exemple | Action |
|---------|---------|--------|
| Texte < 15 chars | `21h30` | Exclu |
| Info/annonce | `Plus d'infos sur www...` | Exclu |
| Pattern réservation | `Rens. 02 43...` | Exclu |
| Sans contenu | Pas de lieu, artiste ni spectacle | Exclu |

**Utilisation :**
```bash
python cli.py populate --reparse                     # Exclut les artifacts (défaut)
python cli.py populate --reparse --include-artifacts # Inclut les artifacts
```

### Dashboard HTML pour les statistiques

Nouvelle option `--html` pour la commande `stats` :

```bash
python cli.py stats                    # Stats terminal (comportement actuel)
python cli.py stats --html             # Génère stats/bidul_stats.html
python cli.py stats --html report.html # Chemin personnalisé
```

Le dashboard inclut :
- Graphique interactif des événements/contenus par Bidul (Chart.js)
- Statistiques globales (événements, artistes/spectacles, ratio)
- Liste des PDFs manquants et Biduls vides
- Détection des ratios anormaux
- Top 10 des Biduls les plus riches

### Colonne `is_regional` dans la base

Nouvelle colonne booléenne dans la table `evenement` :
```sql
ALTER TABLE evenement ADD COLUMN is_regional BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_evenement_is_regional ON evenement(is_regional);
```

---

# Release Notes - Indexer v1.6

## Vue d'ensemble

Version avec migration vers le schema v3, simplification de la structure de données et amélioration de l'extraction des villes inconnues.

## Nouveautés v1.6

### Schema v3 - Suppression des colonnes JSON redondantes

La table `evenement` ne contient plus les colonnes JSON redondantes :
- `artistes` (JSON array)
- `spectacles` (JSON array)
- `genres_raw` (JSON array)
- `style`

Ces données sont maintenant stockées **uniquement** dans `contenu_evenement` (source de vérité).

**Migration:**
```bash
python scripts/migrate_schema_v3.py --dry-run  # Simulation
python scripts/migrate_schema_v3.py            # Migration effective
```

### Nouvelle vue `v_evenements_complets`

Vue avec agrégation automatique des artistes/spectacles/styles depuis `contenu_evenement` :

```sql
SELECT * FROM v_evenements_complets WHERE bidul_numero = 212;
-- Colonnes: artistes, spectacles, styles (GROUP_CONCAT)
```

### Extraction améliorée des villes inconnues

Les villes non présentes dans le référentiel sont maintenant préservées dans `ville_raw` :

| Avant | Après |
|-------|-------|
| `Thorigné sur Dué` → `Le Mans` | `Thorigné sur Dué` → `Thorigné sur Dué` ✓ |
| `Coulongé` → `Le Mans` | `Coulongé` → `Coulongé` ✓ |
| `Ancinnes` → `Le Mans` | `Ancinnes` → `Ancinnes` ✓ |

Heuristique ajoutée pour détecter les villes après le lieu.

### Événements nommés avec chiffres

Support des noms d'événements contenant des chiffres :

```
"Born 2 Moonwalk Party avec..." → evenement.nom = "Born 2 Moonwalk Party"
```

### Amélioration du parser `smart_split`

- Refactoring pour éviter les erreurs d'index sur les paires de guillemets
- Apostrophe `'` exclue des caractères de guillemets (préserve `Val'Rhonne`, `L'Oasis`)

---

# Release Notes - Indexer v1.5

## Vue d'ensemble

Version avec normalisation automatique des référentiels et amélioration de la détection des événements nommés.

## Nouveautés v1.5

### Normalisation automatique

Système de normalisation intelligent qui réduit drastiquement le besoin d'aliases manuels :

| Règle | Exemple | Matching automatique |
|-------|---------|---------------------|
| Case-insensitive | `bar le lézard` | → `Bar le Lézard` ✓ |
| Accent-insensitive | `theatre` | → `Théâtre` ✓ |
| Séparateurs interchangeables | `pop-rock` | → `pop rock` ✓ |
| Préfixes optionnels | `le barouf` | → `Bar Le Barouf` ✓ |
| Abbreviations | `th.` / `st` | → `Théâtre` / `Saint` ✓ |

**Impact** : 593 aliases redondants supprimés des fichiers CSV (couverts par la normalisation automatique).

### Événements nommés avec numéro d'édition

Reconnaissance des événements avec numéro d'édition (#N) en Title Case :

```
"Syncope fait de la résistance #2" avec ROTTERDAMES + LOLA BAÏ...
→ evenement.nom = "Syncope fait de la résistance #2"
→ artistes = [ROTTERDAMES, LOLA BAÏ, ...]
```

Auparavant, ce type d'événement était incorrectement placé dans `nom_spectacle`.

### Commandes de maintenance

Nouvelles commandes CLI pour la gestion de la base :

| Commande | Description |
|----------|-------------|
| `renormalize` | Re-normalise tous les événements avec les dernières règles |
| `clean-database` | Nettoie les données orphelines et invalides |
| `deduplicate` | Détecte et fusionne les événements en double |

### Cache clearing automatique

Les caches LRU sont automatiquement vidés lors du `renormalize` pour garantir l'utilisation des dernières règles de normalisation.

---

# Release Notes - Indexer v1.4

## Vue d'ensemble

Version avec amélioration majeure de l'extraction des spectacles formatés et support des caractères unicode.

**Résultat** : ~14 500 événements indexés depuis 122 numéros (178-308)

## Nouveautés v1.4

### Extraction améliorée des spectacles formatés

Support complet des spectacles avec guillemets autour des balises `<b>` :

| Pattern | Exemple | Extraction |
|---------|---------|------------|
| Pattern 1b | `"<b>Concert à table</b>" (<i>concert >7 ans</i>)` | spectacle + style ✓ |
| Pattern 1c | `"<b>Concerto pour camionneuse</b>" Cie XXX (<i>funambule</i>)` | spectacle + Cie artiste + style ✓ |

### Support des caractères unicode

- **Guillemets typographiques** : `"..."` (U+201C, U+201D) maintenant reconnus
- **Apostrophe curly** : `'` (U+2019) supportée dans les noms de Cie (ex: "Cie Ordinaire d'exception")
- **Patterns OCR** : Support de `<<...>`, `<...">` pour les guillemets mal reconnus

### Corrections de bugs

- **Position lieu heuristique** : Correction du calcul de position dans le texte original (vs texte nettoyé)
- **Double extraction spectacle/artiste** : Les spectacles entre guillemets ne sont plus extraits comme artistes
- **Cie après spectacle** : Pattern "Cie XXX" directement après un spectacle maintenant extrait comme artiste

---

# Release Notes - Indexer v1.3

## Vue d'ensemble

Version avec support complet du format "par bloc" pour les dates et amélioration du reparse.

## Nouveautés v1.3

### Support complet du format "par bloc"

Le parser reconnaît maintenant tous les formats de dates utilisés dans les Biduls récents :

| Format | Exemple | Support |
|--------|---------|---------|
| Date simple | `Jeudi 02` | ✓ |
| Dates composées (et) | `Samedi 04 et Dimanche 05` | ✓ **nouveau** |
| Dates composées (&) | `Ve 10 & Sa 11` | ✓ |
| Plages numériques | `Du 6 au 10` | ✓ |
| Plages avec jours complets | `Du Mercredi 01 au Samedi 07` | ✓ **nouveau** |

### Amélioration du reparse

- **`--reparse` utilise maintenant `EventParser.parse_with_referentiel()`** : Le reparse charge automatiquement le `date_format` depuis `biduls.description.csv` et utilise la stratégie "lieu d'abord" avec les référentiels.
- **Affichage du format** : Le message de reparse indique maintenant le format utilisé (inline/par bloc).
- **Mode dry-run corrigé** : Le compteur d'événements s'affiche correctement en mode simulation.

### Corrections de bugs

- **Import `EventParser`** : Correction d'un `UnboundLocalError` lors de l'utilisation du chemin OCR sans `--reparse`.
- **Sérialisation JSON des artistes** : Les objets `ArtisteInfo` sont maintenant correctement convertis en dicts avant sérialisation.

---

# Release Notes - Indexer v1.2

## Vue d'ensemble

Version avec extraction configurable et support des formats anciens (pré-2015).

## Nouveautés v1.2

### Extraction configurable
- **Configuration via CSV** : `corpus/biduls.description.csv` définit les pages utiles et le type (scan/texte) par numéro
- **Détection des scans** : Les PDFs scans sont détectés et ignorés (message "OCR nécessaire")
- **Priorité page 3** : Si page 3 existe, elle est utilisée en priorité (agenda complet)

### Support des anciens formats
- **Format inline** : Support du pattern `Je 02 : ARTISTE, Lieu` (Biduls pré-2015)
- **Jours abrégés** : Reconnaissance de `Lu`, `Ma`, `Me`, `Je`, `Ve`, `Sa`, `Di`
- **Fallback automatique** : Si le format standard échoue, le format inline est tenté

### Normalisation des artistes
- **Title Case** : Noms d'artistes normalisés (`DJ MACHIN` → `Dj Machin`)
- **Préfixes préservés** : DJ, MC, Dj, Mc conservent leur casse
- **Mots de liaison** : `de`, `la`, `le`, `et`, `du` restent en minuscules

## Nouveautés v1.1

### Améliorations du parser
- **Nettoyage des artifacts PDF** : Suppression des lignes "K" isolées et headers "le bidul - mois YYYY"
- **Pattern spectacle-artiste** : Correction du parsing `"Spectacle" Cie Artiste (genre)` (ex: `"Personne" Cie L'Absente (magie)`)
- **Séparateur `//"** : Support du pattern `Festival X // ARTISTE1 + ARTISTE2`
- **Spectacle sans artiste** : Gestion correcte de `"Spectacle" (genre), Lieu` sans faux artiste

### CLI amélioré
- **`populate --replace`** : Option pour remplacer les événements existants (évite les doublons)
- **`stats` étendu** : Affiche sources (csv/pdf), types, tarification, top lieux/villes, plage de dates

## Fonctionnalités

### Extraction PDF
- Support des PDFs texte natifs (PyMuPDF)
- Configuration via `corpus/biduls.description.csv` (pages utiles, type scan/texte)
- Priorité page 3 si disponible, sinon pages configurées

### Import CSV
- Import prioritaire depuis les CSV de tapages (confidence = 1.0)
- Support des deux formats de nommage (2022 et 2023+)
- Déduplication automatique des événements

### Parsing des événements
- Extraction : date, heure, lieu, ville, artistes, spectacles
- Parsing des prix (min/max, gratuit, prix libre)
- Extraction des genres musicaux entre parenthèses
- Score de confidence par événement

### Base de données
- SQLite avec schéma normalisé
- Référentiels lieux (540) et villes (123)
- Vue `v_evenements` pour requêtes simplifiées
- Requêtes analytiques prêtes à l'emploi

### CLI
- `init` : Initialisation base + référentiels
- `extract` : Extraction PDF
- `populate` : Peuplement intelligent (CSV > PDF) avec option `--replace`
- `validate` : Affichage pour validation manuelle
- `compare` : Comparaison avec CSV de référence
- `stats` : Statistiques étendues (sources, types, top lieux/villes)
- `purge` : Nettoyage sélectif (par numéro, plage, ou tout)

## Statistiques

| Métrique | Valeur |
|----------|--------|
| Biduls indexés | 122 |
| Événements totaux | ~14 500 |
| Source CSV | ~3 000 (confidence 1.0) |
| Source PDF | ~11 500 (confidence 0.4-0.9) |
| Confidence moyenne | 0.91 |

## Limitations connues

1. **PDFs scans (1-177)** : Non supportés, nécessitent OCR (Phase 2)
2. **Événements complexes** : Certains formats multi-lignes mal parsés
3. **Normalisation partielle** : Lieux/villes non tous liés aux référentiels

## Prochaines étapes (Phase 2)

- [ ] OCR pour les PDFs scans (Tesseract)
- [ ] Amélioration du parsing (ML ou règles avancées)
- [ ] API REST pour requêtes
- [ ] Interface web de consultation
- [ ] Export vers formats standards (iCal, JSON-LD)

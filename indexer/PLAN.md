# Plan d'implémentation - Indexer Bidul v2

## Contexte

Pipeline d'extraction et d'indexation des 308 archives PDF du fanzine "Le Bidul" (1997-2024) pour créer une base de données consolidée des événements culturels au Mans.

## État actuel

### Ce qui existe déjà (et fonctionne)
- `pipeline/extractor.py` : Extraction texte natif + OCR Tesseract
- `pipeline/structurer.py` : Structuration via API Mistral
- `pipeline/persister.py` : Persistance SQLite
- `pipeline/pipeline.py` : Orchestration avec CLI
- `database/models.py` : ORM léger avec modèles dataclass
- `database/schema.sql` : Schéma complet (à simplifier)
- `corpus/biduls.description.csv` : Configuration manuelle de 308 PDFs

### Ce qui manque
1. Suppression de la table `genre` (non normalisable)
2. Ajout de `texte_raw` dans la table `evenement`
3. Intégration du fichier de configuration CSV dans le pipeline
4. CLI de vérification/validation des résultats
5. Système de comparaison avec les CSV de référence (2022-2024)

---

## Phase 1 : Simplification du schéma

### 1.1 Modifier `database/schema.sql`
- [ ] Supprimer la table `genre` et ses INSERT
- [ ] Supprimer `genre_id` de la table `evenement`
- [ ] Ajouter `type_evenement TEXT` directement dans `evenement` (concert, theatre, etc.)
- [ ] Ajouter `texte_raw TEXT` dans `evenement` pour stocker le texte source complet
- [ ] Supprimer la vue `v_evenements_complets` qui référence `genre`
- [ ] Mettre à jour les autres vues

### 1.2 Mettre à jour `database/models.py`
- [ ] Supprimer la référence à `genre_id` dans `Evenement`
- [ ] Ajouter `type_evenement: Optional[str]` et `texte_raw: Optional[str]`
- [ ] Mettre à jour les méthodes CRUD

### 1.3 Mettre à jour `pipeline/persister.py`
- [ ] Supprimer le `GENRE_MAPPING`
- [ ] Utiliser directement `event.event_type` comme string

---

## Phase 2 : Intégration de la configuration PDF

### 2.1 Créer `pipeline/config_loader.py`
Module pour charger et utiliser `corpus/biduls.description.csv` :

```python
@dataclass
class BiduConfig:
    numero: int
    type_pdf: str  # "scan" ou "texte"
    source: str    # "manuel" ou "auto"
    date_par_evenement: bool
    pages: list[PageConfig]

@dataclass
class PageConfig:
    numero: int  # 1 ou 2
    orientation_pdf: str  # "portrait" ou "paysage"
    orientation_texte: str
    sections: list[str]  # ["S1", "S2", "S3", "S4"]
    colonnes: int  # 1 ou 2
```

### 2.2 Logique d'inférence de configuration
Si un PDF n'a pas de config dans le CSV :
1. Chercher le Bidul le plus proche en numéro qui a une config
2. Appliquer cette config
3. Après extraction réussie, sauvegarder la config dans le CSV avec `source: "auto"`

### 2.3 Modifier `pipeline/extractor.py`
- [ ] Ajouter paramètre `config: Optional[BiduConfig]`
- [ ] Utiliser la config pour déterminer :
  - Méthode d'extraction (native vs OCR) basée sur `type_pdf`
  - Pages à extraire basées sur `sections`
  - Orientation du texte pour l'OCR

---

## Phase 3 : Amélioration du parsing d'événements

### 3.1 Créer `pipeline/event_parser.py`
Parser basé sur regex pour les patterns du Bidul :

```python
# Patterns identifiés :
# - Nom spectacle entre guillemets : "Le Malade Imaginaire"
# - Genre entre parenthèses et italique : (rock, jazz)
# - Artistes séparés par + : ARTIST1 + ARTIST2 + ARTIST3
# - Artistes en MAJUSCULES pour concerts
# - Format: [Festival //] "spectacle" artiste (genre), lieu, ville, heure, tarif
```

### 3.2 Modifier `pipeline/structurer.py`
- [ ] Ajouter option pour parser localement (sans API)
- [ ] Utiliser l'API Mistral uniquement pour les cas complexes
- [ ] Stocker `texte_raw` pour chaque événement parsé

### 3.3 Améliorer le prompt Mistral
Intégrer les règles spécifiques au Bidul :
- Genres entre parenthèses
- Noms de spectacles entre guillemets
- Séparateur "+" pour artistes multiples
- "tnc" = tarif non communiqué
- Etc.

---

## Phase 4 : CLI de vérification

### 4.1 Créer `cli/verify.py`
Interface CLI pour vérifier les extractions :

```bash
# Voir les événements extraits pour un Bidul
python -m indexer.cli.verify show 287

# Comparer avec un CSV de référence
python -m indexer.cli.verify compare 287 --ref tapages/toBeConverted/202401_*.csv

# Statistiques globales
python -m indexer.cli.verify stats

# Lister les PDFs sans config
python -m indexer.cli.verify unconfigured

# Marquer un événement comme vérifié
python -m indexer.cli.verify validate 287 --event-id 123
```

### 4.2 Créer `cli/extract.py`
CLI principal d'extraction :

```bash
# Extraire un seul Bidul
python -m indexer.cli.extract 287

# Extraire une plage
python -m indexer.cli.extract 280-290

# Extraire tous les PDFs texte
python -m indexer.cli.extract --type texte

# Dry-run (sans persistance)
python -m indexer.cli.extract 287 --dry-run

# Forcer ré-extraction
python -m indexer.cli.extract 287 --force
```

---

## Phase 5 : Système de validation avec données de référence

### 5.1 Créer `validation/reference_loader.py`
Charger les CSV de tapage (2022-2024) comme données de référence :

```python
def load_reference_events(csv_path: Path) -> list[ReferenceEvent]:
    """Charge les événements depuis un CSV biduleur."""
    # Colonnes: date, heure, lieu, ville, prix, genre, spectacle1, artiste1, style1...
```

### 5.2 Créer `validation/comparator.py`
Comparer les événements extraits avec la référence :

```python
@dataclass
class ComparisonResult:
    matched: int          # Événements correctement extraits
    missed: int           # Événements de référence non trouvés
    extra: int            # Événements extraits non dans référence
    precision: float      # matched / (matched + extra)
    recall: float         # matched / (matched + missed)
    f1_score: float
    details: list[MatchDetail]
```

### 5.3 Metrics de matching
- Match exact : date + lieu + artiste identiques
- Match partiel : date + lieu OK, artiste différent (orthographe)
- Fuzzy matching pour les noms d'artistes et de lieux

---

## Phase 6 : Corpus de référence

### 6.1 Extraire le corpus depuis les CSV de tapage
Créer des dictionnaires de référence depuis les données 2022-2024 :

```python
# corpus/reference_dictionary.json
{
    "lieux": {
        "Le Mans": ["Le Barouf", "Le Zoo", "L'Oasis", ...],
        "Allonnes": ["Théâtre de Chaoué", ...],
        ...
    },
    "artistes": ["Les Ogres de Barback", "Tryo", ...],
    "styles": ["rock", "jazz", "théâtre", "danse", ...]
}
```

### 6.2 Utiliser le corpus pour améliorer la reconnaissance
- Correction automatique des noms de lieux mal OCRisés
- Suggestions d'artistes similaires
- Validation des villes (liste fermée Sarthe)

---

## Ordre d'implémentation recommandé

1. **Phase 1** (Schéma) - Fondation nécessaire
2. **Phase 4.2** (CLI extract) - Pour tester rapidement
3. **Phase 2** (Config loader) - Utiliser les données existantes
4. **Phase 3** (Parser) - Améliorer l'extraction
5. **Phase 4.1** (CLI verify) - Vérification manuelle
6. **Phase 5** (Validation) - Mesurer la qualité
7. **Phase 6** (Corpus) - Amélioration continue

---

## Structure de fichiers proposée

```
indexer/
├── cli/
│   ├── __init__.py
│   ├── extract.py      # CLI d'extraction
│   └── verify.py       # CLI de vérification
├── corpus/
│   ├── biduls.description.csv
│   ├── reference_dictionary.json
│   └── reference_corpus.json
├── database/
│   ├── models.py       # Modifié
│   └── schema.sql      # Modifié
├── pipeline/
│   ├── config_loader.py  # Nouveau
│   ├── event_parser.py   # Nouveau
│   ├── extractor.py      # Modifié
│   ├── persister.py      # Modifié
│   ├── pipeline.py
│   └── structurer.py     # Modifié
├── validation/
│   ├── __init__.py
│   ├── comparator.py     # Nouveau
│   └── reference_loader.py  # Nouveau
└── archives/
    └── [PDFs organisés par année]
```

---

## Questions en suspens

1. **API Mistral** : Veux-tu utiliser Mistral pour tous les PDFs ou seulement les cas difficiles ?
   - Option A : Mistral pour tout (coût API mais meilleure qualité)
   - Option B : Parser regex local + Mistral en fallback

2. **Parallélisation** : Le pipeline supporte déjà le multi-threading. Combien de workers pour l'extraction ?

3. **Résolution des conflits** : Comment veux-tu être notifié des cas ambigus ?
   - CLI interactif pendant l'extraction
   - Fichier de log à traiter après
   - Les deux


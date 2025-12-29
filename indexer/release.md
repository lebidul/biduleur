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

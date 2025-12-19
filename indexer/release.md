# Release Notes - Indexer v1.1

## Vue d'ensemble

Version améliorée du pipeline d'indexation avec corrections de parsing et nouvelles fonctionnalités CLI.

**Résultat** : ~14 500 événements indexés depuis 122 numéros (178-308)

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
- Détection automatique scan vs texte
- Extraction multi-pages avec skip des pages 1 et 3 (doublons typiques)

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

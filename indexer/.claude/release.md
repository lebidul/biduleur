# Indexer - Notes de Release

## v1.19 (2026-02-02)

### Améliorations du parsing des lieux génériques

- **Extraction de ville pour lieux génériques** : Les lieux génériques (Salle des fêtes, Église, etc.) extraient maintenant la ville depuis le texte OCR via patterns "de {Ville}", ", {Ville}", "({Ville})"
- **Matching normalisé ville** : Les espaces et tirets sont interchangeables ("Rouessé Vassé" = "Rouessé-Vassé")
- **Priorité spécifique > générique** : Les lieux spécifiques ("L'Epidaure") sont matchés avant les génériques ("Centre Culturel")
- **Word boundary intelligent** : Nouvelle fonction `make_word_pattern()` pour les noms avec caractères non-alphanumériques (P.C.V., etc.)

### Carte interactive avec événements

- **Heatmap logarithmique** : Meilleure visualisation des variations de densité
- **Détails événements dans popups** : Affichage de l'heure, tarif, artistes, spectacles
- **Filtrage dynamique** : Filtre par année/mois/semaine/jour synchronisé avec les popups

### Synchronisation corpus

- **is_generic dans CSV** : Le flag `is_generic` est maintenant exporté/importé via `sync-corpus-to-db`

### Tests

- **7 nouveaux tests** : Classe `TestGenericLocations` pour les lieux génériques
- **245 tests** : Tous passent

### Benchmarks

- Bidul 184: **94.7%** (+0.1%)
- Bidul 190: **90.6%** (stable)

---

## v1.18 (2026-01-xx)

### Lieux génériques

- Contrainte unique passée de `UNIQUE(nom)` à `UNIQUE(nom, ville)`
- Ajout de la colonne `is_generic` dans `lieu_ref`
- Support des lieux comme "Salle des fêtes" pouvant exister dans plusieurs villes

### Fonctions modifiées

- `find_lieu_ref_id()` et `normalize_lieu()` retournent maintenant 3 valeurs : `(lieu_id, nom, ville)`
- `get_lieu_ref_list()` inclut le flag `is_generic`

---

## v1.17 et antérieures

Voir historique git pour les versions précédentes.

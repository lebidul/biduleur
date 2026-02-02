# Indexer - Contexte de développement

## Version courante : v1.19

### État du projet

- **245 tests** unitaires passent
- **Benchmarks** : 184 (94.7%), 190 (90.6%)
- **Base de données** : ~15,000 événements indexés sur ~300 biduls

### Travaux récents (v1.19)

1. **Lieux génériques** : Parsing amélioré avec extraction de ville depuis le texte
2. **Carte interactive** : Événements avec détails et filtrage dynamique
3. **Word boundaries** : Support des noms avec caractères spéciaux (P.C.V.)

### Fichiers clés modifiés

- `core/parser.py` - Parsing avec `make_word_pattern()`, priorité spécifique > générique
- `core/db.py` - `is_generic` dans `get_lieu_ref_list()`
- `core/stats_generator.py` - Carte avec événements, heatmap log, filtrage dynamique
- `scripts/sync_corpus_db.py` - Export/import `is_generic`
- `tests/test_parser.py` - `TestGenericLocations` (7 tests)

### Prochaines tâches potentielles

- Améliorer le géocodage des nouveaux lieux
- Optimiser les performances de la carte pour grands datasets
- Ajouter export des données de la carte en CSV/JSON

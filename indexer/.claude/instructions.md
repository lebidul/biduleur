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

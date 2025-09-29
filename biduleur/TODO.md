# Liste des TODOs et Améliorations Futures

## Priorité Élevée
- [ ] Ajouter une validation des colonnes du CSV dans `read_and_sort_csv`.
- [ ] Améliorer la gestion des erreurs pour les dates mal formatées (ex: "Mardi 1er").
- [ ] Corriger le tri des événements lorsque la colonne `DATE` est vide ou invalide.
- [x] Rendre le Biduleur comme un éxécutable.
- [ ] Erreur avec fichier csv créé depuis excel (ex. C:\Users\thiba\Desktop\test.bidul\tapage.mardi.matin.2.csv)
- [ ] Unit tests
- [ ] Ajouter une config qui permet de définir le style (police, gras, capitale, minuscule, italique, etc...) pour chaque type d'info (lieu, ville, etc..)

## Priorité Moyenne
- [ ] Optimiser les performances du tri pour les fichiers CSV volumineux.
- [x] Ajouter fichiers templates au gui.
- [x] Ajouter des logs pour faciliter le débogage.
- [ ] Pouvoir parser vieux et nouveaux templates
- [ ] Générer 2 pdfs en sortie, un pour impression et un pdf pour version digitale
- [ ] Documenter les cas d'erreur possibles dans la docstring de `parse_bidul`.
- [ ] Ajouter une interface en ligne de commande (CLI) pour le traitement par lots.

## Priorité Faible
- [x] Prendre en charge les fichiers Excel en plus des CSV.
- [ ] Prendre en charge google sheet
- [x] Ajouter une interface en ligne de commande (CLI) pour le traitement par lots.

## Fonctionnalités Futures
- [ ] Permettre la personnalisation des formats de date (ex: "1er mai" au lieu de "Mardi 1").
- [ ] Ajouter des tests unitaires pour les cas limites (dates manquantes, formats invalides).

## Réfactoring
- [ ] Simplifier la logique de tri dans `read_and_sort_csv` en utilisant des clés de tri plus efficaces.
- [ ] Décomposer `parse_bidul` en fonctions plus petites pour améliorer la lisibilité.

## Documentation
- [ ] Rédiger un guide utilisateur pour expliquer comment utiliser le module.
- [ ] Ajouter des exemples d'utilisation dans la documentation.
# Liste des TODOs et Améliorations Futures pour le bidul GUI et CLI

## Priorité Élevée
- [x] Infos couv (flag couv/no couv, nom dessinat.eur.rice + hyperlink) (gui + cli)
- [x] Ajouter fichiers templates csv et xlsx.
- [x] Fichier release notes
- [x] Build release process.
- [x] Icône.
- [x] Taille fenêtre dynamique
- [x] Export dans 1 seul svg -> pas possible
- [x] Créer fichier couv.png comme partie de l'export -> c'est complétement con, on fournit déjà la couv.. 
- [x] Capturer erreur si pdf déjà ouvert et impossible à sauvegarder
- [x] Hyperlinks sponsors
- [x] Enlever border date box
- [x] Champs paths par défaut depuis build github
- [x] Dossier logos dupliqué
- [x] Possibilité dans front-end ou config de choisir si taille de police calculée (pour sections ,3,4,5,6) ou forcée. SI forcée est trop grosse alors overflow sections 4.
- [x] Générer photos post instagram pour le bidul du mois
- [x] Améliorer progress display dans GUI
  - [x] Ajouter infos sur fichier stories (qté) da11111111111111111111111111111111111111111111111111111111111111111112221ns boite summary
- [x] Ajouter au FE fine tuning pour posts instagram (backend color ou image (+ transparency), font, font color)
- [x] Cucaracha: ajout de saut de ligne dans texte. perte italique si non arial
- [x] Ajouter stories dans cli misenpageur
- [x] Sélectionner dossier output pour svg (nom des fichiers par défaut) comme la story instagram
- [x] Ajouter export fichier config.json silencieux et fichier log
- [x] Ajouter fichier de config.json avec valeurs par défaut (+ config débug) dans build. Fichier ensuite utilisé à runTime mais qui peut-être édité 
- [x] Améliorer niveaux de débug
- [x] Config front-end (widgets, helpers, callbacks, etc) dans un fichier config dédié avec wrapper et nouvelle class pour ne pas avoir sur trop de fichiers `chqaue fois` -> pas une bonne idée car trop complexe
- [x] Inactive row
- [x] Checkbox "au chapeau"
- [x] Lire logos depuis svg (qui contiendrait tous les logos) pareil pour l'ours
- [ ] Bouton STOP
- [ ] Fix csv input
- [ ] Output separate pdf pages

## Priorité Moyenne
- [x] Refactor dans dossier bidul.biduleur/bidul.
- [x] Champ pour choisir couleur box de dates
- [x] Texte poster en blanc si rendu trop foncé
- [x] Effet succès solitaire.
- [x] Icône
- [x] Problème sécurité Windows
- [x] Progress bar.
- [x] Problème affichage release notes dans release github
- [x] Image de fond dans GUI
- [x] Ajout helpers.
- [x] Drag and drop
- [x] Revoir optimisation de l'espace (remplacement de string si ca fait gagner une ligne, S4 pas remplie jusqu'au bout)
- [x] Mieux gérer l'erreur dans le cas où les colonnes de l'input csv/xls sont mal configurées
- [x] "En Bref" -> "Coups de coeur et en Bref"
- [x] Pouvoir importer une config dans le GUI
- [x] SVG output qui ont le même nom que le pdf
- [x] Nombre d'exemplaires dans ours
- [ ] Ajouter logique de texte gris si poster moyennement foncé
- [ ] Afficher WARN si le texte de la cucaracha box ne rentre pas
- [ ] Nouveau paramètre (on peut en ajouter autant qu'on veut pour définir mise en style (police, gras, etc..) pour certaines chaines de caractères
- [ ] Dans ours l'auteur et les hyperlinks ne suivent pas le .png dans le cas d'une margin (marche bien actuellement avec une marge < 4mm))
- [ ] GUI qui génère une preview dynamiquement et ensuite propose de sauver le pdf (voir notes_ia/googleAIStudio.solutionGUIdynamique.md).
- [ ] Revoir résolution GUI
- [ ] Exe linux + Mac
- [ ] Changer framework GUI
- [ ] Pouvoir entrer plusieurs dates (csv like) pour une même date pour ne pas avoir à répéter
- [ ] Mettre nouveau logo les arts services (Gëelle) dans ours
- [ ] config dans GUI: champs pas dans export/import: paths input
  - [ ] amélioration de la performance:
    Résumé des optimisations de performance
🔴 Impact ÉLEVÉ (Quick wins)
  Optimisation	Fichier	Effort	Gain estimé
  Cache des icônes	textflow.py:43-68	30 min	3-5x
  Cache image couverture	draw_logic.py:618-669	15 min	20-30%
  Regex en module-level	textflow.py:129,163	15 min	5-10%
  🟡 Impact MOYEN
  Optimisation	Fichier	Effort	Gain estimé
  Cache des wrap()	textflow.py, draw_logic.py	2-3h	5-10x
  Cache des ParagraphStyle	textflow.py:223-243	1-2h	10-20%
  Font registration guard	draw_logic.py:481-491	15 min	Négligeable sauf batch
  🟢 Impact FAIBLE (qualité de code)
  Extraction de la logique "orphan prevention" dupliquée 5 fois
  Streaming XML pour SVG post-processing
- [ ] Enlever du GUI les paramètres qu'on ne change jamais (ou les mettre dans un onglet config)

## Documentation
- [ ] Rédiger un guide utilisateur pour expliquer comment utiliser le module.
- [ ] Ajouter des exemples d'utilisation dans la documentation.
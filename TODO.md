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
- [x] Ajouter infos sur fichier stories (qté) dans boite summary
- [x] Ajouter au FE fine tuning pour posts instagram (backend color ou image (+ transparency), font, font color)
- [x] Cucaracha: ajout de saut de ligne dans texte. perte italique si non arial
- [x] Ajouter stories dans cli misenpageur
- [x] Sélectionner dossier output pour svg (nom des fichiers par défaut) comme la story instagram
- [x] Ajouter export fichier config.json silencieux et fichier log
- [x] Ajouter fichier de config.json avec valeurs par défaut (+ config débug) dans build. Fichier ensuite utilisé à runTime mais qui peut-être édité 
- [x] Améliorer niveaux de débug
- [x] Config front-end (widgets, helpers, callbacks, etc) dans un fichier config dédié avec wrapper et nouvelle class pour ne pas avoir sur trop de fichiers `chqaue fois` -> pas une bonne idée car trop complexe
- [ ] Fix csv input
- [ ] Output separate pdf pages
- [ ] Inactive row
- [ ] Checkbox "au chapeau"
- [ ] Lire logos depuis svg (qui contiendrait tous les logos) pareil pour l'ours

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
- [ ] Ajouter logique de texte gris si poster moyennement foncé
- [ ] Afficher WARN si le texte de la cucaracha box ne rentre pas
- [ ] Nouveau paramètre (on peut en ajouter autant qu'on veut pour définir mise en style (police, gras, etc..) pour certaines chaines de caractères
- [ ] Dans ours l'auteur et les hyperlinks ne suivent pas le .png dans le cas d'une margin (marche bien actuellement avec une marge < 4mm))
- [ ] Revoir optimisation de l'espace (remplacement de string si ca fait gagner une ligne, S4 pas remplie jusqu'au bout)
- [ ] GUI qui génère une preview dynamiquement et ensuite propose de sauver le pdf (voir notes_ia/googleAIStudio.solutionGUIdynamique.md).
- [ ] Revoir résolution GUI
- [ ] Exe linux + Mac
- [ ] Changer framework GUI
- [x] Mieux gérer l'erreur dans le cas où les colonnes de l'input csv/xls sont mal configurées
- [ ] Pouvoir entrer plusieurs dates (csv like) pour une même date pour ne pas avoir à répéter
- [x] "En Bref" -> "Coups de coeur et en Bref"
- [x] Pouvoir importer une config dans le GUI
- [x] SVG output qui ont le même nom que le pdf
- [ ] Nombre d'exemplaires dans ours
- [ ] Mettre nouveau logo les arts services (Gëelle) dans ours
- [ ] config dans GUI:
  - .json et non pas .yml dans UI
  - paramètres non peuplés: organisation logos, fichiers input
- [ ] amélioration de la performance

## Documentation
- [ ] Rédiger un guide utilisateur pour expliquer comment utiliser le module.
- [ ] Ajouter des exemples d'utilisation dans la documentation.
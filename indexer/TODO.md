* stocker description biduls dans table ref importable pour execution (sinon depuis fichier csv) qui puisse être consolidée
* #evenements dans table bidul
* cas particuliers
  * 2010-09 Bidul 147 bis.pdf
  * 2019-03 Bidul 242 Marion.pdf, 2019-03 Bidul 242 Stef@n.pdf
  * #10 concert kha farnaum p1 à rentrer à la main
  * #60 ajouter festival crève la dalle à la main
  * #61 bebop à rajouter à la main
  * #92 seulement 14 evenements (juillet aout)
  * #125
    * 125 elements dans pdf. seulement 83 dans db
  * revoir #292
  * revoir #234 (skipper p3)
  * raw_text	nom_spectacle
  <b>"A</b><b>Hfa de Yambolé"</b> <i>(conte dès 12 ans)</i>, S.Signoret, Mulsanne, 15h, 3.5/9.5 €	A</b><b>Hfa de Yambolé

* alias:
  * DAVE GOLITIN SOLO -> DAVE GOLITIN
  * Sablé
  * Sargé
  * St Michel de Chahaignes -> St Michel-de-Chavaignes
* refactor pour simplifier la logique et l'ajout de patterns
* ajouter html ou csv tapages manquants
* colonne description dans table bidul (ex. bidul covid)
* revoir avec grouping tous les lieux n'ayant pas de ref
* stocker texte extrait dans table bidul pour csv
* faire fichiers benchmark
* ajouter d'autres KPI de la qualité du dataset à stats --html
* accélerer populate (peut-être avec moins d'info logged)
* code object oriented
* centraliser patterns
* ajouter coordonnées à la table lieux
* * stats. mettre possibilité d'avoir comme option l'axe x en tant que date
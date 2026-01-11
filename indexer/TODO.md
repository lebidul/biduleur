* stocker description biduls dans table ref importable pour execution (sinon depuis fichier csv) qui puisse être consolidée
* #evenements dans table bidul
* cas particuliers
  * 2010-09 Bidul 147 bis.pdf
  * 2019-03 Bidul 242 Marion.pdf, 2019-03 Bidul 242 Stef@n.pdf
  * #10 concert kha farnaum p1 à rentrer à la main
  * #60 ajouter festival crève la dalle à la main
  * #61 bebop à rajouter à la main
  * #92 seulement 14 evenements (juillet aout)
  * #132
    * evt regionaux non elimines
  * #125
    * 125 elements dans pdf. seulement 83 dans db
  * #175
    * ```LE MANS CITE CHANSON: Présélection Slam #1, Union Jack, 21h, 0€``` lieu non reconnu
    * ```LE MANS CITE CHANSON: Présélection Spoken Word #2, Le Passeport 21h30, 0€``` lie non reconnu
    * ```Birdland présente Olivier Mugot Trio (jazz), L'Inventaire, 21h, 0€``` nom evt non reconnu
  * #235
    * ``` Le Mans Fait son Cirque (<i>20 spectacles - Dernière Journée</i>), plus d’infos sur le net  Le Son des Cuivres // <b>THE AMAZING KEYSTONE BIG BAND & DJANGO EXTENDED </b>+<b> ... </b>+ <b>JAZZ COMBO BOX </b> + <b>SAXHORNIA</b>, Mamers, à partir de 13h30, 23€ (1 jour) / 38€ (2jours)  Festival Kikloche #13 // “<b>Le garçon qui ne connaissait pas la peur</b>” (<i>théâtre dès 6 ans</i>) + “<b>Bee happy</b>” + <i>...</i> + “<b>Poubelles la vie, saison 2</b>” (<i>projection, web serie</i>), Champfleur, 10h-19h, 10€, plus d’infos sur le site web  Festival Musica // <b>Le Requiem … de Brahms</b>, Église St. Aldric, 17h, 10/15€
     Festival Les Trolls En Folie #<b>5 </b>// LES RAMONEURS DE MENHIRS (<i>punk rock</i> celtique) + MERZHIN (<i>rock</i>)+ MISS <b>AMERICA</b> (<i>rock</i>) + <b>TOYBLOÏD</b> (<i>rock punk garage</i>) + <b>GREZOU </b>(<i>reggae hip hop</i>) + <b>FANFARE FBTF</b> + <b>Guinguette</b> (<i>80’s</i>), Lieu-dit Le Débat, Jupilles, 17h-3h, 9/12€``` noms extrait avec puces et balises
  * #119
    * evenements mal splittés car scan croppés: ```"Le miroir" (théâtre), Caveau 105, Le Mans, 21h sauf Di: 17h, 9 à 26€: 17 à 14h30/Ve 18 à 10h30 / 14h30: "Le vilain pas beau"> (conte/théâtre d'objets-jeune public), Centre Culturel Epidaure, Bouloire 20h30,5€ e 18: "<Lettre de délation" (théâtre), Théâtre de la Halle au Blé, La Flèche 20h30, 7 à 15€ a 18 "Didler Heins" (One Man Show), Le Patis 21h, 8/11/13€ a 19: <<Les excuses de Victor" (sp. jeune public) par la Cie Opéra Pagaï, Le Val'Rhonne Moncé en Belin, 17h, 5-7-8€ i 20: <<Les excuses de Victor>> (sp. jeune public) par la Cie Opéra Pagaï,Centre F. Rabelais, Changé 17h, à partir de 6 ans, 4-5€```
  * #158
    * ```Les Veillées: << Bruit à Brac" (théâtre, musique et chanson française.) par Cie Cinémaniak, Square Delmenhorst, vieux-bourg Allonnes 21h, 0€ Au Passeport en août: gratuit``` - lieu mal extrait
  * raw_text	nom_spectacle
  <b>"A</b><b>Hfa de Yambolé"</b> <i>(conte dès 12 ans)</i>, S.Signoret, Mulsanne, 15h, 3.5/9.5 €	A</b><b>Hfa de Yambolé

* alias:
  * DAVE GOLITIN SOLO -> DAVE GOLITIN
  * Sablé
  * Sargé
* refactor pour simplifier la logique et l'ajout de patterns
* enlever tout ce qui vient après: "Et un peu plus loin..." - ocr par colonne
* ajouter html ou csv tapages manquants
* colonne description dans table bidul (ex. bidul covid)
* revoir avec grouping tous les lieux n'ayant pas de ref
* stocker texte extrait dans table bidul pour csv
* faire fichiers benchmark
* consolidation parsing à continuer
* ajouter d'autres KPI de la qualité du dataset à stats --html
* ajouter biduls 309 et 310
* accélerer populate (peut-être avec moins d'info logged)
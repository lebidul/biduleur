* stocker description biduls dans table ref importable pour execution (sinon depuis fichier csv) qui puisse être consolidée
* #evenements dans table bidul
* cas particuliers
  * 2010-09 Bidul 147 bis.pdf
  * 2019-03 Bidul 242 Marion.pdf, 2019-03 Bidul 242 Stef@n.pdf
  * #92 seulement 14 evenements (juillet aout)
  * pas d'événement Bidul 255 (covid)
  * #83
    * ```Ve 1/Sa 02 à 21 h/Di 03 à 15h30: «Ah, si les femmes étaient des fleurs...»>,
  (théâtre), de et par Marie Fifi, L'Inventaire, MJC Prévert, 3-6€``` pas reconnus
  * #125
    * 125 elements dans pdf. seeulement 83 dans db
  * #174
    * ```Soirée "électro festif" avec Dj Beesk Hot, Le Passeport, 23h, 0€``` nom et artiste non reconnus
    * ```OULALA CLUB avec QUADRUPEDE (noise rock) + ED WOOD JR (art rock alambiqué abrasif) + VAROSA (rock), Le Barouf 20h30, 0€``` nom non reconnu
  * #235
    * ``` Le Mans Fait son Cirque (<i>20 spectacles - Dernière Journée</i>), plus d’infos sur le net  Le Son des Cuivres // <b>THE AMAZING KEYSTONE BIG BAND & DJANGO EXTENDED </b>+<b> ... </b>+ <b>JAZZ COMBO BOX </b> + <b>SAXHORNIA</b>, Mamers, à partir de 13h30, 23€ (1 jour) / 38€ (2jours)  Festival Kikloche #13 // “<b>Le garçon qui ne connaissait pas la peur</b>” (<i>théâtre dès 6 ans</i>) + “<b>Bee happy</b>” + <i>...</i> + “<b>Poubelles la vie, saison 2</b>” (<i>projection, web serie</i>), Champfleur, 10h-19h, 10€, plus d’infos sur le site web  Festival Musica // <b>Le Requiem … de Brahms</b>, Église St. Aldric, 17h, 10/15€
     Festival Les Trolls En Folie #<b>5 </b>// LES RAMONEURS DE MENHIRS (<i>punk rock</i> celtique) + MERZHIN (<i>rock</i>)+ MISS <b>AMERICA</b> (<i>rock</i>) + <b>TOYBLOÏD</b> (<i>rock punk garage</i>) + <b>GREZOU </b>(<i>reggae hip hop</i>) + <b>FANFARE FBTF</b> + <b>Guinguette</b> (<i>80’s</i>), Lieu-dit Le Débat, Jupilles, 17h-3h, 9/12€``` noms extrait avec puces et balises
  * #249
    * ```Dimanche 1er décembre
     “Le temps retrouvé” Le Théâtre Bascule (th. d'objets > 5 ans), La Longère, Coulans
    sur Gée, 16h, 4/7€
     “Polaroïd” ``` dates hors mois non reconnues 
  * raw_text	nom_spectacle
  <b>"A</b><b>Hfa de Yambolé"</b> <i>(conte dès 12 ans)</i>, S.Signoret, Mulsanne, 15h, 3.5/9.5 €	A</b><b>Hfa de Yambolé

* alias:
  * "Le Narais" lieu alias
  * Sablé
  * Sargé
* refactor pour simplifier la logique et l'ajout de patterns
* enlever tout ce qui vient après: "Et un peu plus loin..." - ocr par colonne
* ajouter html ou csv tapages manquants
* ajouter dans normalisation auto les types d'apostrophe
* colonne description dans table bidul (ex. bidul covid)
* revoir avec grouping tous les lieux n'ayant pas de ref
* stocker texte extrait dans table bidul pour csv
* faire fichiers benchmark
* consolidation parsing à continuer
* ajouter d'autres KPI de la qualité du dataset à stats --html
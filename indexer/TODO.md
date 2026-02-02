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
  * revoir #294 (peu d'evenements)
  * revoir #123, 125, 157 (pic de baisse de qualité)
  * raw_text	nom_spectacle
  <b>"A</b><b>Hfa de Yambolé"</b> <i>(conte dès 12 ans)</i>, S.Signoret, Mulsanne, 15h, 3.5/9.5 €	A</b><b>Hfa de Yambolé
  * #12
    * ```CONTE DE La Source au théâtre du Petit Seux, Coulaines 17h00, 30F par le Théâtre de l'Ephémère, Théâtre Paul Scarron LE MANS, Ma/Me/Ve/Sa à 20h30 et Je à 18h30 24 au 28: ELOÏSE ET PHILEMON par IUTOPIUM THEATRE, Le Mans, Salle des concerts 21h00,1 OF 19 et 20: IL ETAIT UNE FOIS``` mal splitté
  * #256
    * ```Scènes ouvertes (variété musique du monde) // MYLÈNE + MARINA VILLATEL + NANNA, Base de loisirs Mansigné (aux berges du lac), 21h30, 0€``` revoir ville
* pas d'evenements geolocalisés à Mayet
* revoir normalisation des églises. Ex. 'Église notre dame' sont toutes au mans
* alias:
  * DAVE GOLITIN SOLO -> DAVE GOLITIN
  * Sablé
  * Sargé
  * St Michel de Chahaignes -> St Michel-de-Chavaignes
* overwrite:
  * ```Samedi 11, 11h00, "Fête de la Saint Patrick", Mamers, Mamers``` (lieu_raw à corrriger)
* ajouter html ou csv tapages manquants
* colonne description dans table bidul (ex. bidul covid)
* revoir avec grouping tous les lieux n'ayant pas de ref
* stocker texte extrait dans table bidul pour csv
* faire fichiers benchmark
* accélerer populate (peut-être avec moins d'info logged)
* code object oriented
* centraliser patterns
* skip reparse si bidul csv
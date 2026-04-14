* stocker description biduls dans table ref importable pour execution (sinon depuis fichier csv) qui puisse être consolidée
* prix en F
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
  * #187:
    * ```</b> Sa 22 : « <b>Pieds d’Or </b>» par JP Berthet, dès 7 ans, 17h Di 23 : « <b>Les contes du messager </b>» par P. Larue, dès 7ans, 17h Ve 28 : « <b>Para bel’homme </b>» par D. Bardoux, 20h30 Sa 29 : « <b>Peluche</b> » par O. Hedin, dès 3 ans, 11h Di 30 : « <b>Promesse de gorille </b>» par B. N’Kaloulou, dès 7 ans, 17h``` pas splitté
  * #12
    * ```CONTE DE La Source au théâtre du Petit Seux, Coulaines 17h00, 30F par le Théâtre de l'Ephémère, Théâtre Paul Scarron LE MANS, Ma/Me/Ve/Sa à 20h30 et Je à 18h30 24 au 28: ELOÏSE ET PHILEMON par IUTOPIUM THEATRE, Le Mans, Salle des concerts 21h00,1 OF 19 et 20: IL ETAIT UNE FOIS``` mal splitté
  * #256
    * ```Scènes ouvertes (variété musique du monde) // MYLÈNE + MARINA VILLATEL + NANNA, Base de loisirs Mansigné (aux berges du lac), 21h30, 0€``` revoir ville
  * 74
    * hommmage à Franck Zappa
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
* stocker texte extrait dans table bidul pour csv
* faire fichiers benchmark
* accélerer populate (peut-être avec moins d'info logged)
* code object oriented
* centraliser patterns
* skip reparse si bidul csv
* chercher villages de sarthe où il n'y a pas le lieu ref chercher ensuite dans raw_text les entrées de ces villages puis comprendre pourquoi ce n'est pas parsé
* skip evenements csv/xlsx ou date = "En bref"
* * stocker prix en francs
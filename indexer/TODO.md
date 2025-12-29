* stocker description biduls dans table ref importable pour execution (sinon depuis fichier csv) qui puisse être consolidée
* #evenements dans table bidul
* cas particuliers
  * #228 page 3 != agenda
  * [212] 06/2016 - 0 événements (pdf)
  * [215] Erreur extraction PDF: None
  * 2010-09 Bidul 147 bis.pdf
  * 2019-03 Bidul 242 Marion.pdf, 2019-03 Bidul 242 Stef@n.pdf
  * pas d'événement Bidul 255 (covid)
  * bidul #233 page 3 pas bonne (vérifier si pas d'autres comme ça)
  * #117 
    * spectacle "13 à la douzaine"
    * "Brette Les Pins" -> "Brette-les-Pins"
    * "Confidences trop intimes" (th.), Caveau 105, Le Mans, Je au Sa: 21h, Di 17h, 9€ à 13€ -> ville + split
    * "Marrons gagnants> (contes), Centre La Longère Coulaines sur Gée, 20h30, 3.5 à 9€ Ma 27 à 19h/Ve 30 à 20h: "Ricercar" (théâtre), par le Théâtre du Radeau, au lieu-dit Robin des Bois, chemin de la Foresterie, Le Mans, 5-10€
  * #260
    * juillet-août
    * festivals non reconnus
  * #204
    * ZIG ZAG (power pop), Bistrot de la Guinguette, Fillé s/Sarthe, 20h, au chapeau - artiste non reconnu
    * `````"Syncope fait de la résistance #2" avec ROTTERDAMES (pop rock) + LOLA BAÏ (chanson pop) + UNLEASHING THE BEAST (metal hardcore) + PUPPA NADEM (raggamuffin fast style rap), Salle Jean Carmet 20h30, 5/7/9€```
      Syncope fait de la résistance #2 comme evenement.nom
  * raw_text	nom_spectacle
<b>"A</b><b>Hfa de Yambolé"</b> <i>(conte dès 12 ans)</i>, S.Signoret, Mulsanne, 15h, 3.5/9.5 €	A</b><b>Hfa de Yambolé

* enlever evenement.artistes et evenement.styles
* refactor pour simplifier la logique et l'ajout de patterns
* enlever tout ce qui vient après: "Et un peu plus loin..."
* ajouter html ou csv tapages manquants
* colonne description dans table bidul (ex. bidul covid)
* revoir avec grouping tous les lieux n'ayant pas de ref
* stocker texte extrait dans table bidul pour csv
* faire fichiers benchmark
* consolidation pdf à continuer
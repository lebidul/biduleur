* stocker description biduls dans table ref importable pour execution (sinon depuis fichier csv) qui puisse être consolidée
* #evenements dans table bidul
* cas particuliers
  * #228 page 3 != agenda
  * [212] 06/2016 - 0 événements (pdf)
  * [215] Erreur extraction PDF: None
  * 2010-09 Bidul 147 bis.pdf
  * 2019-03 Bidul 242 Marion.pdf, 2019-03 Bidul 242 Stef@n.pdf
  * #92 seulement 14 evenements (juillet aout)
  * pas d'événement Bidul 255 (covid)
  * bidul #233 page 3 pas bonne (vérifier si pas d'autres comme ça)
  * #40
    * ```<<DUO D'AMOUR" (théâtre), Salle André Voisin, Fresnay-sur-Sarthe (72), 20h30, 50 et 70F``` lieu non capturé
  * #73
    * ```STRASAX (jazz), ITEMM, Le Mans, 18h30``` lieu non capturé
    * ````Scène ouverte jazz, L'Inventaire, MJC Prévert Le Mans, 21h, gratuit```` lieu non capturé
  * #117
    * Ancinnes Thorigné sur Dué Coulongé normalisés avec Le Mans
  * #260
    * juillet-août
    * festivals non reconnus
  * #237
    * ```<b>PALATINE </b>(<i>chanson folk pop rock</i>), La Péniche Excelsior, Allonnes, 20h30, 5/11€``` style non reconnu
    * ```Festival Folkiri // <b>MES SOULIERS SONT ROUGES </b><i>(ch. folk</i>) <bi>+</bi><b> JEAN-CHARLES GUICHEN </b>(<i>musique bretonne</i>), Les Saulnières, 20h30, 11/17€``` styles non reconnus
    * ```“<b>Nous ne viendrons pas manger dimanche</b>” (<i>théâtre</i>) collectif Grand Maximum, L’Envol, La Bazoge, 20h30, t.n.c COMPLET !``` artiste non reconnu`
  * raw_text	nom_spectacle
<b>"A</b><b>Hfa de Yambolé"</b> <i>(conte dès 12 ans)</i>, S.Signoret, Mulsanne, 15h, 3.5/9.5 €	A</b><b>Hfa de Yambolé

* alias:
  * "Le Narais" lieu alias
  * Sablé
  * Sargé
* refactor pour simplifier la logique et l'ajout de patterns
* enlever tout ce qui vient après: "Et un peu plus loin..."
* ajouter html ou csv tapages manquants
* colonne description dans table bidul (ex. bidul covid)
* revoir avec grouping tous les lieux n'ayant pas de ref
* stocker texte extrait dans table bidul pour csv
* faire fichiers benchmark
* consolidation parsing à continuer
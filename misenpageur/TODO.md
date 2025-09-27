# Liste des TODOs et Améliorations Futures [pir le misenpageur]

## Priorité Élevée
- [x] Workflow global. csv/xls/xlsx (biduleur) -> pdf (misenpageur)
- [x] Infos couv (flag couv/no couv, nom dessinat.eur.rice + hyperlink) (cli)
- [x] Redimensionnement éventuel de l'image de couv.
- [x] Amélioration display dates
- [x] Config cucarcaha
- [x] Config ours v1
- [x] Config ours v2 - lecture as .md ou .html ou .svg avec icones.
- [x] UI: Espace pour configuration visuelle couv, marge
- [x] Config logos v1
- [x] Config cucaracha v1
- [x] Config cucaracha v2: pouvoir ajouter image pour additional box
- [x] Config qr code
- [x] Poster (page 3).
- [ ] Qualité pdf. - convert_image affecte qualité ?
- [ ] Unit tests.
- [ ] Intégrer nouveaux logos de Gaelle.
- [x] Enlever watermark pdf2svg dans svg outputs.
- [ ] Améliorer visuel QR code.
- [ ] Empêcher qu'une date (ligne date) commence à la fin d'une section
- [ ] Déplacer scabilité dans biduleur (sur lieu et ville) ? (autorise moins de flexibiité though)

## Priorité Moyenne
- [x] Amélioration lisibilité finale (ex. caractère de bullet point comme paramètre, cadre pour date)
- [x] Amélioration lisibilité v2 (ex. ligne pour dates).
- [ ] Réduire espace puce premier caractère event.
- [ ] Réduire taille de la puce par rapport font-Size.
- [x] Solution algorithme de "packing" (ou "bin packing") pour une répartition plus fluide des logos.
- [ ] Générer 2 pdfs en sortie, un pour impression et un pdf pour version digitale (avec ou sans hyperlink) (ajouter à bidul.gui).
- [ ] Intégration du workflow dans page admin de wordpress.
- [x] Options d’hyphénation pour rendre des strings insécables.
- [x] Enlever toutes les références `SVGCanvas` dans `draw_logic` et `drawing`.



## Documentation
- [ ] Rédiger un guide utilisateur pour expliquer comment utiliser le module.
- [x] Ajouter des exemples d'utilisation dans la documentation.
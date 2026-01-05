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
- [x] Qualité pdf. - convert_image affecte qualité ?
- [x] Logos SVG
- [x] URL logos dans export SVG -> trop complex. on accepte de perdre les hyperliens avec le pdf créé depuis le svg 
- [x] Intégrer nouveaux logos de Gaelle.
- [x] Enlever watermark pdf2svg dans svg outputs.
- [x] Améliorer visuel QR code.
- [x] Empêcher qu'une date (ligne date) commence à la fin d'une section
- [x] Déplacer insecabilité dans biduleur (sur lieu et ville) ? (autorise moins de flexibiité though) -> pas fait. géré avec replacement engine
- [x] Fichiers svg outputs prennent le nom du fichier pdf
- [x] Améliorer affichage optimisée des logos (plusieurs propals ?)
- [ ] Trop d'espace perdu avec police automatique (eg. C:\Users\thiba\tibo\bidul\miseEnPage\2601\debug_run_2026-01-02_21-35-22)
- [ ] "Nan" dans le cas de sv sans nom pour ariste spectacle 2,3,4
- [ ] remplacer euros pour sigle dans prix
- [ ] Saint pas remplacé si suivi d'un tiret
- [ ] enlever virgule après horaire si pas de prix
- [ ] Unit tests
- [ ] Cleaner logos de Gaëlle. Càd les avoir en couleur
- [ ] cucaracha texte et path fichier couv pas sauvegardé dans config

## Priorité Moyenne
- [x] Amélioration lisibilité finale (ex. caractère de bullet point comme paramètre, cadre pour date)
- [x] Amélioration lisibilité v2 (ex. ligne pour dates).
- [x] Solution algorithme de "packing" (ou "bin packing") pour une répartition plus fluide des logos.
- [x] Options d’hyphénation pour rendre des strings insécables.
- [x] Enlever toutes les références `SVGCanvas` dans `draw_logic` et `drawing`.
- [x] Réduire taille de la puce par rapport font-Size.
- [ ] Réduire espace puce premier caractère event.
- [ ] Générer 2 pdfs en sortie, un pour impression et un pdf pour version digitale (avec ou sans hyperlink) (ajouter à bidul.gui).
- [ ] Intégration du workflow dans page admin de wordpress.

## Documentation
- [x] Ajouter des exemples d'utilisation dans la documentation.
- [ ] Rédiger un guide utilisateur pour expliquer comment utiliser le module.
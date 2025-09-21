
---
# Bidul v1.2.10 - Améliorations Esthétiques Finales

Cette version se concentre sur le peaufinage de l'expérience utilisateur, en apportant des améliorations esthétiques à l'interface graphique et à la nouvelle fenêtre d'animation de victoire.

## ✨ Améliorations

*   **Animation de Victoire Améliorée** : L'animation "Solitaire" de fin de génération a été affinée pour un effet visuel plus agréable :
    *   La fenêtre de victoire apparaît désormais dans le coin inférieur droit de l'application principale, au lieu du centre.
    *   Les cartes animées apparaissent maintenant plus haut hors de l'écran, créant un effet de "pluie" plus prononcé.
    *   La vitesse des cartes a été légèrement réduite pour une animation plus douce.
*   **Ergonomie de la Fenêtre de Victoire** :
    *   Un bouton "Fermer", aligné à droite, a été ajouté à la fenêtre de résumé pour une fermeture plus intuitive.
    *   La taille de la fenêtre et du résumé a été ajustée pour un meilleur confort de lecture.
*   **Icônes d'Application** : La fenêtre principale et la fenêtre de victoire ont désormais leur propre icône, renforçant l'identité visuelle de l'application.

## 🔧 Corrections du Build Windows (`.exe`)

*   **Correction du Chargement des Assets** : Un bug qui empêchait le chargement des images de l'animation (les cartes) et des icônes dans la version "standalone" a été corrigé. Le fichier de configuration de PyInstaller (`bidul.spec`) a été mis à jour pour embarquer correctement le dossier `leTruc/assets`.

---


# Bidul v1.2.9 - Ajout d'une effet ouaaais dans le cas où le bidul est créé

Cette version ajoute une touche finale amusante et gratifiante à l'expérience utilisateur, ainsi que les dernières corrections sur la mise en page dynamique des hyperliens.

## ✨ Nouveautés

*   **Animation "Solitaire" de Fin de Génération** : Pour célébrer une génération de PDF réussie, une nouvelle fenêtre "Victoire !" s'affiche. Elle présente le résumé du traitement sur un fond d'animation de cartes rebondissantes, un clin d'œil à l'effet classique de Windows Solitaire.
    *   L'animation utilise plusieurs images de cartes différentes pour plus de variété visuelle.
    *   Les paramètres (couleur de fond, taille, etc.) sont facilement personnalisables dans le code.


---

# Bidul v1.2.8 - Amélioration du Layout Dynamique et Prévisualisation d'Images

Cette version apporte des corrections majeures à la gestion des marges dynamiques et améliore considérablement l'ergonomie de l'interface graphique avec l'ajout d'aperçus pour les images.

## ✨ Nouveautés et Améliorations de l'Interface (GUI)

*   **Prévisualisation des Images (Thumbnails)** : L'interface graphique affiche désormais une miniature (thumbnail) pour les champs d'images (Ours, Couverture, Cucaracha).
    *   Les aperçus se chargent automatiquement au démarrage de l'application si des chemins par défaut sont définis.
    *   La miniature se met à jour instantanément lorsque l'utilisateur sélectionne un nouveau fichier image, offrant un retour visuel immédiat.

## 🔧 Améliorations et Corrections du Rendu PDF

*   **Correction Majeure du Positionnement avec Marge** : Le bug critique qui empêchait les éléments de la colonne "Ours" (texte de l'auteur, hyperliens) de se déplacer correctement lors de l'application d'une marge globale a été résolu.
*   **Mise à l'échelle Homothétique** : La logique de dessin a été entièrement revue pour garantir que tous les éléments de l'ours (texte, QR code, espacements) sont non seulement repositionnés mais aussi redimensionnés proportionnellement à la taille de la colonne. Le rendu reste ainsi visuellement cohérent, quelle que soit la marge appliquée.

## ⚙️ Pour les Développeuses et Développeurs

*   **Logique de Positionnement Robuste** : Le calcul des coordonnées dans `drawing.py` a été refactorisé pour utiliser un système de ratio d'échelle basé sur des dimensions de référence. Cela garantit que tous les éléments enfants d'une section s'adaptent de manière prévisible aux changements de taille de leur parent.
*   **Intégration de Pillow dans le GUI** : La nouvelle fonctionnalité de prévisualisation d'images utilise la bibliothèque `Pillow` (`Image` et `ImageTk`) pour créer et afficher les miniatures directement dans l'interface Tkinter.
*   **Nettoyage** : On enlève le trigger sur push du github workflow config file du misenpageur.

---

# Bidul v1.2.7 - Amélioration de l'Expérience Utilisateur et de la Distribution

Cette version se concentre sur l'amélioration de l'expérience utilisateur lors de l'installation et de l'utilisation de l'application, en apportant des corrections importantes à la gestion des erreurs et à la distribution.

## ✨ Améliorations

*   **Gestion de l'Erreur "Fichier Ouvert"** : L'application ne plante plus avec une erreur technique si l'utilisateur essaie de générer un PDF qui est déjà ouvert dans un autre programme (comme Adobe Reader). Une boîte de dialogue claire s'affiche désormais, demandant à l'utilisateur de fermer le fichier avant de continuer.
*   **Ajout d'un Fichier `README.txt` à la Release** : L'archive `.zip` de la release contient maintenant un fichier `README.txt` avec des instructions claires pour les nouveaux utilisateurs. Il explique notamment comment contourner l'avertissement de sécurité "Microsoft Defender SmartScreen" qui peut apparaître au premier lancement.

## ⚙️ Pour les Développeuses et Développeurs

*   **Gestion de `PermissionError`** : La logique de traitement principal (`run_pipeline`) intercepte désormais spécifiquement l'exception `PermissionError` pour la transformer en un message d'erreur compréhensible pour l'utilisateur.
*   **Création Automatisée du `README.txt`** : Le workflow GitHub Actions a été mis à jour pour générer et inclure dynamiquement le fichier `README.txt` dans l'archive de la release à chaque build.

---
# Bidul v1.2.6 - Refactorisation de l'Interface Graphique

Cette version est principalement technique et se concentre sur une refactorisation majeure de l'interface graphique (GUI). L'objectif était d'améliorer la structure du code pour le rendre plus propre, plus maintenable et plus facile à faire évoluer à l'avenir, tout en corrigeant les derniers bugs d'interaction.

## ✨ Améliorations de l'Interface Graphique (GUI)

*   **Finalisation de la `Date Box`** : Le dernier bug lié au séparateur de dates de type "Box" a été corrigé. Le sélecteur de couleur pour le fond de la boîte s'affiche désormais correctement et la couleur choisie est bien appliquée dans le PDF final.
*   **Interface Simplifiée** : L'option de personnalisation de la couleur de la *bordure* de la `date box` a été retirée pour simplifier l'interface. Les boîtes sont maintenant toujours dessinées sans bordure.

## 🔧 Corrections

*   **Fichiers manquants ajoutés** : Logos, modèles (.cv, .xls) 

## ⚙️ Pour les Développeuses et Développeurs

*   **Refactorisation Complète du GUI** : Tout le code de l'interface a été restructuré en suivant les meilleures pratiques :
    *   **Architecture Modulaire** : Le code est maintenant divisé en plusieurs fichiers avec des responsabilités uniques (`app.py` pour la structure, `widgets.py` pour le visuel, `callbacks.py` pour la logique), ce qui remplace l'ancien fichier monolithique `gui.py`.
    *   **Structure Orientée Objet** : L'interface est désormais gérée par une classe `Application`, ce qui permet une meilleure gestion de l'état et une organisation du code plus claire.
*   **Fiabilisation du Build (`.spec`)** : Le fichier de configuration de PyInstaller (`bidul.spec`) a été mis à jour pour s'adapter à la nouvelle structure de fichiers du GUI, garantissant que les builds Windows fonctionnent correctement.

---


# Bidul v1.2.5 - Couleur de Police Automatique et Finalisation

Cette version introduit une nouvelle fonctionnalité intelligente pour le design du poster et finalise les améliorations de l'interface graphique et de la logique de placement des logos.

## ✨ Nouveautés

*   **Couleur de Police Automatique pour le Poster** : Lors de l'utilisation du design "Image en fond" pour le poster, l'application analyse désormais la luminosité de la zone centrale de l'image. Si le fond est détecté comme étant majoritairement sombre, la couleur de la police de l'agenda passe **automatiquement en blanc** pour garantir une lisibilité optimale. Cette fonctionnalité est entièrement configurable (`config.yml`).

## 🔧 Améliorations et Corrections

*   **Prise en Compte de la Transparence** : L'algorithme d'analyse de la luminosité simule désormais l'effet du voile blanc semi-transparent appliqué sur l'image, garantissant une détection de couleur précise et fiable, conforme au rendu final.

## ⚙️ Pour les Développeuses et Développeurs

*   **Analyse d'Image avec Pillow** : La nouvelle fonctionnalité de couleur automatique utilise la bibliothèque `Pillow` (`ImageStat`) pour calculer la luminosité moyenne d'une zone d'image, y compris après une simulation de composition alpha.

---

# Bidul v1.2.4 - Liens sur les Logos et Personnalisation des Dates

Cette version enrichit considérablement les possibilités de personnalisation et l'interactivité des documents PDF générés, en ajoutant des fonctionnalités très demandées.

## ✨ Nouveautés

*   **Hyperliens sur les Logos** : Il est désormais possible de rendre les logos cliquables. En modifiant le fichier `config.yml`, vous pouvez associer une URL à n'importe quel logo. Cette fonctionnalité est disponible pour les deux modes de répartition ("2 Colonnes" et "Optimisé").
*   **Sélecteur de Couleur pour les Séparateurs "Box"** : Lors de la personnalisation des séparateurs de dates dans l'interface graphique, si vous choisissez le type "Box", deux nouveaux boutons apparaissent. Ils permettent d'ouvrir un sélecteur de couleur natif pour choisir interactivement la couleur de la bordure et du fond de la boîte, offrant un contrôle visuel total sur le design.

## 🔧 Améliorations

*   **Interface Contextuelle** : Les nouvelles options de couleur pour les boîtes de date n'apparaissent que lorsque le type "Box" est sélectionné, gardant l'interface claire et épurée.
*   **Configuration centralisée** : Les nouveaux paramètres (liens des logos, couleurs des boîtes) sont gérés via les `dataclasses` de configuration pour un code plus propre et maintenable.

---

# Bidul v1.2.3 - Fiabilisation du Build et Interface Responsive

Cette version de maintenance est cruciale car elle se concentre sur la stabilisation de l'application Windows (`.exe`) et améliore l'ergonomie de l'interface graphique pour une expérience utilisateur plus fluide.

## ✨ Améliorations de l'Interface Graphique (GUI)

*   **Interface "Responsive" avec Barre de Défilement** : La fenêtre de l'application peut désormais être redimensionnée sans casser la mise en page. Si la hauteur de la fenêtre devient insuffisante pour afficher tous les paramètres, une barre de défilement verticale apparaît automatiquement, permettant un accès facile à toutes les options.
*   **Correction du Layout** : Des bugs visuels mineurs, comme un champ "Dossier logos" dupliqué et un positionnement incorrect du champ de marge, ont été corrigés pour une interface plus propre et plus logique.

## 🔧 Corrections du Build Windows (`.exe`)

Cette version corrige plusieurs bugs critiques qui n'apparaissaient que dans la version "standalone" de l'application :
*   **Correction des Erreurs de Traitement** : Un `TypeError` qui pouvait survenir lors du lancement du processus depuis l'interface a été résolu.

## ⚙️ Pour les Développeuses et Développeurs

*   **Fiabilisation du Workflow de Release** : Le script de la GitHub Action a été amélioré pour extraire et afficher correctement les notes de version spécifiques à chaque nouvelle release sur l'interface de GitHub.

---

# Bidul v1.2.2 - Stabilisation du Build Windows et Corrections

Cette version de maintenance se concentre sur la résolution de bugs critiques qui apparaissaient spécifiquement dans l'exécutable Windows (`.exe`) généré via GitHub Actions. L'application est désormais beaucoup plus stable et fiable en mode "standalone".

## 🔧 Améliorations et Corrections

*   **Correction du Chargement des Ressources** : Un bug majeur qui empêchait l'exécutable de trouver les fichiers de configuration par défaut (comme `config.yml`) a été résolu. Les champs de l'interface (image de couverture, dossier des logos, etc.) sont maintenant correctement pré-remplis au démarrage, comme en mode développement.
*   **Correction du Module `rectpack` Manquant** : L'erreur `ModuleNotFoundError: No module named 'rectpack'` qui faisait planter l'application lors de l'utilisation de la répartition optimisée des logos a été corrigée. La bibliothèque est maintenant correctement embarquée dans le build final.
*   **Correction de Bugs dans l'Interface Graphique** :
    *   Un bug de `TypeError` qui survenait lors du lancement de la répartition optimisée des logos a été résolu.
    *   Un champ "Dossier logos" qui apparaissait en double dans l'interface a été supprimé.
*   **Fiabilisation des Imports** : La manière dont les modules internes (comme `misenpageur`) sont chargés a été rendue plus robuste pour garantir leur bon fonctionnement à l'intérieur de l'environnement PyInstaller.

## ⚙️ Pour les Développeuses et Développeurs

*   **Chemins d'accès compatibles PyInstaller** : Une nouvelle fonction `get_resource_path` a été ajoutée. Elle utilise `sys._MEIPASS` lorsque l'application est packagée, garantissant que les assets et les configurations sont trouvés de manière fiable.
*   **Configuration du Build (`.spec`)** : Le fichier `bidul.spec` a été mis à jour pour inclure explicitement la dépendance cachée `rectpack` via l'option `hiddenimports`.

---
# Bidul v1.2.1 - Mise en Page Optimisée des Logos

Cette version introduit une nouvelle fonctionnalité majeure très demandée : un algorithme intelligent pour la mise en page des logos. Elle offre également plus de contrôle aux utilisateurs avancés pour affiner le rendu final.

## ✨ Nouveautés

*   **Répartition Optimisée des Logos** : En plus de la disposition classique en deux colonnes, une nouvelle option "Optimisée" est disponible. Elle utilise un algorithme de *rectangle packing* pour arranger les logos de manière dense et harmonieuse, en maximisant leur taille tout en leur garantissant une **surface visuelle égale**. Le résultat est une mise en page plus professionnelle et équilibrée, particulièrement efficace lorsque les logos ont des formes et des tailles très différentes.
*   **Contrôle Avancé du Packing** : Pour les utilisateurs exigeants, il est désormais possible de piloter finement l'algorithme de packing via le fichier `config.yml`. De nouveaux paramètres (`packing_strategy`) permettent de choisir l'algorithme de placement et la méthode de tri des logos, offrant un contrôle total sur l'esthétique finale.
*   **Marge des Logos Configurable** : La marge entre les logos pour la répartition optimisée peut maintenant être ajustée directement depuis l'interface graphique, permettant d'affiner facilement l'espacement.

## 🔧 Améliorations et Corrections

*   **Correction du Bug de Transparence des Logos** : La logique de placement prend désormais en compte la "bounding box" (le contenu visible) des logos PNG transparents, au lieu des dimensions du fichier. Cela corrige le bug majeur qui causait des chevauchements et des espacements incorrects.
*   **Préservation Garantie du Ratio d'Aspect** : L'algorithme de dessin a été entièrement revu pour garantir mathématiquement que le ratio largeur/hauteur de chaque logo est parfaitement préservé, éliminant tout risque de distorsion.
*   **Correction du Layout de l'Interface** : Un bug mineur qui plaçait mal le champ de configuration de la marge des logos dans l'interface a été corrigé.

## ⚙️ Pour les Développeuses et Développeurs

*   **Intégration de `rectpack`** : La bibliothèque `rectpack` a été ajoutée pour gérer la logique de packing. L'algorithme implémenté combine une recherche binaire sur la surface optimale avec une logique de "fit and center" robuste pour le dessin final.
*   **Configuration Structurée** : La configuration a été enrichie avec un `dataclass` dédié (`PackingStrategy`) pour une gestion propre et typée des nouveaux paramètres de l'algorithme.

---
# Bidul v1.2.0 - Interface Graphique Améliorée et Réactive

Cette version se concentre sur l'amélioration majeure de l'expérience utilisateur en rendant l'interface graphique (GUI) plus interactive, informative et pratique.

## ✨ Améliorations de l'Interface Graphique (GUI)

*   **Interface Réactive et Barre de Progression** : L'application ne se fige plus pendant la génération du PDF. Une barre de progression animée indique clairement que le traitement est en cours. Le bouton "Lancer la Génération" est temporairement désactivé pour éviter les clics multiples accidentels.
*   **Ouverture Automatique du PDF** : Une fois la génération terminée avec succès, l'application vous propose désormais d'ouvrir directement le fichier PDF créé, vous faisant gagner du temps.
*   **Mise à jour du Champ "Ours"** : L'interface a été mise à jour pour correspondre à la nouvelle architecture de l'ours. Le champ demande maintenant correctement une image de fond (`.png`) au lieu d'un fichier Markdown, ce qui est plus intuitif.

## ⚙️ Pour les Développeuses et Développeurs

*   **Exécution en Arrière-Plan (Threading)** : La logique de traitement principal (`run_pipeline`) est maintenant exécutée dans un thread séparé. Cela permet à l'interface graphique Tkinter de rester fluide et réactive, et de mettre à jour la barre de progression pendant que les tâches lourdes (parsing, génération PDF) s'effectuent en arrière-plan.

---

# Bidul v1.1.0 - Refonte de l'Ours et Fiabilisation des Exports

Cette nouvelle version se concentre sur la robustesse du rendu et la correction de bugs importants, notamment pour l'export SVG et la mise en page de la section "Ours", tout en introduisant une méthode beaucoup plus puissante pour la personnaliser.

## ✨ Nouveautés

*   **Ours Graphique Hybride** : La section "Ours" n'est plus limitée à du simple texte. Elle est désormais basée sur un modèle d'image de fond (`.png`), permettant des designs complexes avec des icônes et des polices personnalisées, garantissant une fidélité visuelle parfaite.
*   **Lien sur l'Auteur** : Le nom de l'auteur de la couverture, affiché dans l'ours, peut maintenant être un hyperlien cliquable, configurable via l'argument `--auteur-couv-url`.

## 🔧 Améliorations et Corrections

*   **Correction Majeure de l'Export SVG** : Le bug le plus critique de l'export SVG a été corrigé. Un mauvais caractère n'est plus remplacé à la place des puces d'événements (`❑`). La nouvelle logique de détection géométrique est beaucoup plus fiable et ne cible que les bonnes puces.
*   **Fiabilité du Rendu de l'Ours** : La nouvelle approche corrige tous les problèmes de rendu de l'ancienne méthode SVG :
    *   Les polices personnalisées s'affichent désormais parfaitement.
    *   Les problèmes de superposition de texte et d'espacement incorrect des caractères sont résolus.
    *   Les fonds noirs sur les icônes et les images avec transparence ont disparu.
*   **Détection Automatique de `pdf2svg`** : L'application trouve maintenant l'exécutable `pdf2svg` dans son propre dossier (`bin/win64`) sans nécessiter de configuration manuelle de la variable d'environnement PATH du système.

## ⚙️ Pour les Développeuses et Développeurs

*   **Architecture de l'Ours Revue** : L'approche initiale de parsing SVG direct avec `svglib` a été abandonnée en raison de ses limitations de rendu. Elle est remplacée par le modèle "PNG Hybride" (fond d'image statique + superposition d'éléments dynamiques avec ReportLab) pour garantir une fidélité visuelle parfaite et une interactivité fiable (liens).
*   **Résolution de Dépendance Circulaire** : Une importation circulaire entre les modules `drawing.py` et `draw_logic.py` a été corrigée par la création d'un module `utils.py`, améliorant la stabilité et la maintenabilité du code.

---

# Bidul v1.0.0 - Première Version Stable

Bienvenue dans la première version officielle de **Bidul** ! 🎉

Cette version marque l'aboutissement d'un long cycle de développement et offre un outil complet pour transformer vos listes d'événements en de superbes documents PDF et SVG, prêts à être partagés ou édités.

## 🚀 Fonctionnalités Principales

*   **Conversion de Données** : Importez facilement vos événements depuis des fichiers `.xls`, `.xlsx`, ou `.csv`.
*   **Génération PDF Multi-pages** :
    *   Créez un agenda détaillé sur deux pages avec une taille de police qui s'adapte automatiquement à votre contenu.
    *   Générez un magnifique poster A4 sur une troisième page, parfait pour l'affichage.
*   **Export SVG Éditable** : En plus du PDF, générez des fichiers SVG pour chaque page. Ces fichiers sont parfaits pour des retouches de dernière minute dans des logiciels comme **Inkscape**.
*   **Interface Graphique Intuitive** : Une application de bureau simple pour Windows qui vous guide à travers tout le processus, sans avoir besoin d'utiliser la ligne de commande.

## ✨ Personnalisation Avancée via l'Interface

Tout est configurable directement depuis l'application :

*   **Couverture** : Choisissez votre image de couverture, créditez l'auteur et ajoutez un lien.
*   **Mise en Page** : Ajustez la marge globale de votre document et l'espacement entre les sections.
*   **Boîte "Cucaracha"** : Ajoutez du contenu personnalisé (texte ou image) dans une boîte dédiée sur la première page.
*   **Design du Poster** : Choisissez entre deux designs pour votre poster :
    1.  **Image au centre** : Pour mettre en avant l'illustration.
    2.  **Image en fond** : Pour un style plus immersif, avec un contrôle précis de la transparence.
*   **Séparateurs de Dates** : Personnalisez l'affichage des dates avec des lignes, des boîtes, ou rien du tout.

## ⚙️ Pour les Développeurs (et les curieux)

*   **Architecture Modulaire** : Le projet est divisé en deux modules principaux : `biduleur` (pour le parsing des données) et `misenpageur` (pour la mise en page et le rendu).
*   **Configuration par Fichiers** : Toute la logique de mise en page est contrôlée par des fichiers `config.yml` et `layout.yml`, ce qui la rend facile à modifier sans toucher au code.
*   **Build Automatisé** : Le processus de création de l'exécutable pour Windows est entièrement automatisé grâce à GitHub Actions.

## 📥 Comment l'utiliser

1.  Téléchargez le fichier `bidul-v1.0.0-win64.zip` ci-dessous (dans la section "Assets").
2.  Décompressez l'archive dans un dossier de votre choix.
3.  Double-cliquez sur `bidul.exe` pour lancer l'application.

Un grand merci à tous ceux qui ont contribué et testé cette version. N'hésitez pas à ouvrir une "issue" sur GitHub si vous rencontrez un problème ou si vous avez des suggestions 
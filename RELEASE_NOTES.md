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

Un grand merci à tous ceux qui ont contribué et testé cette version. N'hésitez pas à ouvrir une "issue" sur GitHub si vous rencontrez un problème ou si vous avez des suggestions !
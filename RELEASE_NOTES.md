# Release Notes - Biduleur

## v1.1.2
### 🌟 Nouvelles fonctionnalités
- Template de fichiers tapageurs .csv et .xlsx disponibles pour les utilisateurs du gui.
- Repository devient public.

### 🔧 Améliorations
- Amélioration du workflow build and release:
  - Optimisation de la structure des .zip du build et des releases.
  - Release créée après merge sur la branche aster avec incrémentation du tag.

## v1.1.0
### 🌟 Nouvelles fonctionnalités
- **Support des fichiers Excel** : Ajout de la prise en charge des fichiers `.xls` et `.xlsx` en plus des fichiers `.csv`.
  - Utilisation de `pandas` pour lire les fichiers Excel.
  - Mise à jour de l'interface graphique pour permettre la sélection de fichiers Excel.

### 🔧 Améliorations
- Optimisation du processus de build pour:
  - réduire la taille du fichier exécutable.
  - créer une release après une PR mergée sur master avc gestion automatique des tags.
- Meilleure gestion des erreurs lors de la lecture des fichiers.

---

## v1.0.0 (Première version stable)
### 🌟 Nouvelles fonctionnalités
- **Interface Graphique (GUI)** : Interface utilisateur intuitive pour sélectionner les fichiers CSV et générer les fichiers HTML.
  - Sélection des fichiers d'entrée et de sortie via des boîtes de dialogue.
  - Affichage des messages de succès ou d'erreur.

- **Mode Ligne de Commande (CLI)** : Utilisation en ligne de commande pour les scripts automatisés.
  - Arguments pour spécifier les fichiers d'entrée et de sortie.

- **Génération de fichiers HTML** : Conversion des fichiers CSV en fichiers HTML pour Bidul et Agenda.
  - Formatage des événements et tri par date, genre et horaire.

---

## 📅 Historique des versions

| Version | Date       | Description                                           |
|---------|------------|-------------------------------------------------------|
| v1.2.0  | 31/08/2025  | Ajout de tapageurs templates sur le gui               |
| v1.1.0  | 30/08/2025 | Ajout du support des fichiers Excel (.xls, .xlsx)     |
| v1.0.0  | 29/8/2025  | Première version stable avec support des fichiers CSV |

---

### Pour les développeurs
1. Clonez le dépôt :
   ```bash
   git clone https://github.com/votre-utilisateur/biduleur.git

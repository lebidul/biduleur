# Release Notes - Biduleur

## v1.1.0
### 🌟 Nouvelles fonctionnalités
- **Support des fichiers Excel** : Ajout de la prise en charge des fichiers `.xls` et `.xlsx` en plus des fichiers `.csv`.
  - Utilisation de `pandas` pour lire les fichiers Excel.
  - Mise à jour de l'interface graphique pour permettre la sélection de fichiers Excel.

### 🔧 Améliorations
- Optimisation du processus de build pour réduire la taille du fichier exécutable.
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

| Version | Date       | Description                                      |
|---------|------------|--------------------------------------------------|
| v1.1.0  | 30/08/2025 | Ajout du support des fichiers Excel (.xls, .xlsx) |
| v1.0.0  | 29/8/2025  | Première version stable avec support des fichiers CSV |

---

### Pour les développeurs
1. Clonez le dépôt :
   ```bash
   git clone https://github.com/votre-utilisateur/biduleur.git

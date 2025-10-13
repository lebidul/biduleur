# 🚀 Guide de Démarrage Rapide - Le Truc PyQt6

## ⚡ Installation en 3 étapes

### Étape 1 : Installation automatique (recommandé)

```bash
cd leTruc_pyqt
python install.py
```

Le script vous guidera à travers :
- ✅ Vérification de Python 3.10+
- ✅ Création d'un environnement virtuel (optionnel)
- ✅ Installation des dépendances
- ✅ Test des imports

### Étape 2 : Installation manuelle

```bash
cd leTruc_pyqt

# Créer un environnement virtuel (recommandé)
python -m venv venv

# Activer l'environnement
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

### Étape 3 : Vérifier l'installation

```bash
# Lancer les tests
python tests/test_gui.py

# Vérifier la migration
cd ..
python tools/check_migration.py
cd leTruc_pyqt
```

---

## 🎯 Lancer l'application

### Méthode simple

```bash
python main.py
```

### Avec le script de lancement

```bash
python run.py
```

### Avec Make (Linux/Mac)

```bash
make run
```

### Avec tasks.bat (Windows)

```bash
tasks.bat run
```

---

## 📦 Fichiers créés et leur utilité

### 📋 Configuration et dépendances

| Fichier | Description | Usage |
|---------|-------------|-------|
| `requirements.txt` | Dépendances standard | `pip install -r requirements.txt` |
| `requirements-dev.txt` | Dépendances de dev | `pip install -r requirements-dev.txt` |
| `.gitignore` | Fichiers à ignorer par Git | Automatique avec Git |

### 🛠️ Scripts d'installation et configuration

| Fichier | Description | Usage |
|---------|-------------|-------|
| `install.py` | Installation automatique guidée | `python install.py` |
| `run.py` | Lancement simple de l'app | `python run.py` |

### 🔧 Outils de développement

| Fichier | Description | Usage |
|---------|-------------|-------|
| `Makefile` | Commandes rapides (Linux/Mac) | `make [commande]` |
| `tasks.bat` | Commandes rapides (Windows) | `tasks.bat [commande]` |

---

## 🎨 Commandes utiles

### Avec Make (Linux/Mac)

```bash
make help           # Affiche l'aide
make install        # Installe les dépendances
make run            # Lance l'application
make test           # Lance les tests
make build          # Crée l'exécutable
make clean          # Nettoie les fichiers générés
make format         # Formate le code
make lint           # Analyse le code
```

### Avec tasks.bat (Windows)

```bash
tasks.bat help           # Affiche l'aide
tasks.bat install        # Installe les dépendances
tasks.bat run            # Lance l'application
tasks.bat test           # Lance les tests
tasks.bat build          # Crée l'exécutable
tasks.bat clean          # Nettoie les fichiers générés
```

### Commandes Python directes

```bash
# Installation
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Lancement
python main.py
python run.py

# Tests
python tests/test_gui.py
python -m pytest tests/ -v

# Build
pyinstaller letruc.spec

# Vérification
python ../tools/check_migration.py

# Formatage
python -m black .
python -m isort .

# Analyse
python -m flake8 . --max-line-length=100
```

---

## 📁 Organisation des fichiers

```
leTruc_pyqt/
├── 📝 Configuration
│   ├── requirements.txt        # Dépendances standard
│   ├── requirements-dev.txt    # Dépendances de dev
│   ├── letruc.spec            # Config PyInstaller
│   └── .gitignore             # Fichiers à ignorer
│
├── 🚀 Scripts de lancement
│   ├── main.py                # Point d'entrée principal
│   ├── run.py                 # Script de lancement
│   ├── install.py             # Installation guidée
│   ├── Makefile               # Commandes (Linux/Mac)
│   └── tasks.bat              # Commandes (Windows)
│
├── 📚 Documentation
│   ├── QUICKSTART.md          # Ce fichier
│   └── docs/
│       ├── README.md          # Guide complet
│       ├── DEPLOYMENT.md      # Guide déploiement
│       └── INDEX.md           # Index des fichiers
│
├── 🧪 Tests
│   └── tests/
│       └── test_gui.py        # Tests de l'interface
│
└── 💻 Code source
    ├── main_window.py         # Fenêtre principale
    ├── utils/                 # Utilitaires
    ├── workers/               # Threading
    ├── ui/                    # Interface
    └── assets/                # Ressources
```

---

## 🔍 Résolution de problèmes

### PyQt6 n'est pas installé

```bash
pip install PyQt6
```

### L'application ne se lance pas

1. Vérifier Python 3.10+ :
   ```bash
   python --version
   ```

2. Vérifier les imports :
   ```bash
   python -c "from PyQt6.QtWidgets import QApplication"
   ```

3. Réinstaller les dépendances :
   ```bash
   pip install -r requirements.txt --force-reinstall
   ```

### Erreur "Module not found"

```bash
# Vérifier la structure
ls -la

# Vérifier que vous êtes dans le bon dossier
pwd

# Devrait afficher : .../leTruc_pyqt
```

### Problèmes d'import avec les sections

```bash
# Vérifier que tous les __init__.py existent
find . -name "__init__.py"

# Si manquants, les créer :
touch utils/__init__.py
touch workers/__init__.py
touch ui/__init__.py
touch ui/sections/__init__.py
touch ui/dialogs/__init__.py
```

---

## 🎓 Prochaines étapes

### 1. Développement

- [ ] Personnaliser l'interface
- [ ] Ajouter de nouvelles fonctionnalités
- [ ] Créer des tests supplémentaires

### 2. Tests

```bash
# Tests complets
make test

# Tests avec couverture
make test-coverage

# Ouvrir le rapport
open htmlcov/index.html
```

### 3. Build et distribution

```bash
# Créer l'exécutable
make build

# Tester l'exécutable
./dist/LeTruc  # ou LeTruc.exe sur Windows

# Distribuer
# L'exécutable est dans dist/
```

---

## 📚 Documentation complète

Pour plus d'informations, consultez :

- **Guide complet** : `docs/README.md`
- **Déploiement** : `docs/DEPLOYMENT.md`
- **Index complet** : `docs/INDEX.md`

---

## 💡 Astuces

### Environnement virtuel

Toujours activer votre environnement virtuel avant de travailler :

```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Raccourcis

Créez des alias pour les commandes fréquentes :

```bash
# Dans ~/.bashrc ou ~/.zshrc (Linux/Mac)
alias truc-run="cd ~/projet/leTruc_pyqt && python main.py"
alias truc-test="cd ~/projet/leTruc_pyqt && python tests/test_gui.py"
```

### Développement

Installez les outils de développement pour une meilleure expérience :

```bash
pip install -r requirements-dev.txt

# Formatage automatique
make format

# Analyse de code
make lint
```

---

## ✅ Checklist de démarrage

- [ ] Python 3.10+ installé
- [ ] Dépendances installées (`requirements.txt`)
- [ ] Structure de fichiers vérifiée
- [ ] Tests réussis (`test_gui.py`)
- [ ] Application lancée avec succès
- [ ] Documentation lue

---

## 🆘 Besoin d'aide ?

1. Consultez la documentation : `docs/README.md`
2. Lancez les vérifications : `python tools/check_migration.py`
3. Regardez les logs en mode debug
4. Vérifiez les issues GitHub (si applicable)

---

**Bon développement avec Le Truc PyQt6 ! 🚀**
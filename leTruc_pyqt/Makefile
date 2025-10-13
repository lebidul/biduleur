# =============================================================================
# Makefile pour Le Truc PyQt6
# =============================================================================
# Usage: make [commande]
# =============================================================================

.PHONY: help install install-dev test run clean build check format lint

# Détection de Python
PYTHON := python3
ifeq ($(OS),Windows_NT)
    PYTHON := python
endif

# ─────────────────────────────────────────────────────────────────────────────
# Aide
# ─────────────────────────────────────────────────────────────────────────────
help:  ## Affiche cette aide
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║  Le Truc PyQt6 - Commandes disponibles                      ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Installation
# ─────────────────────────────────────────────────────────────────────────────
install:  ## Installe les dépendances standard
	@echo "📦 Installation des dépendances..."
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	@echo "✅ Installation terminée"

install-dev:  ## Installe les dépendances de développement
	@echo "📦 Installation des dépendances de développement..."
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt
	@echo "✅ Installation terminée"

install-auto:  ## Installation automatique guidée
	@echo "🚀 Installation automatique..."
	$(PYTHON) install.py

# ─────────────────────────────────────────────────────────────────────────────
# Exécution
# ─────────────────────────────────────────────────────────────────────────────
run:  ## Lance l'application
	@echo "🚀 Lancement de l'application..."
	$(PYTHON) main.py

run-debug:  ## Lance l'application en mode debug
	@echo "🐛 Lancement en mode debug..."
	$(PYTHON) main.py --debug

# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
test:  ## Lance les tests
	@echo "🧪 Lancement des tests..."
	$(PYTHON) tests/test_gui.py

test-verbose:  ## Lance les tests en mode verbose
	@echo "🧪 Lancement des tests (verbose)..."
	$(PYTHON) -m pytest tests/ -v

test-coverage:  ## Lance les tests avec rapport de couverture
	@echo "🧪 Tests avec couverture de code..."
	$(PYTHON) -m pytest tests/ --cov=. --cov-report=html
	@echo "📊 Rapport disponible dans htmlcov/index.html"

check:  ## Vérifie la migration
	@echo "✅ Vérification de la migration..."
	cd .. && $(PYTHON) tools/check_migration.py

# ─────────────────────────────────────────────────────────────────────────────
# Qualité de code
# ─────────────────────────────────────────────────────────────────────────────
format:  ## Formate le code avec black
	@echo "🎨 Formatage du code..."
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

lint:  ## Analyse le code avec flake8
	@echo "🔍 Analyse du code..."
	$(PYTHON) -m flake8 . --max-line-length=100 --exclude=venv,build,dist

type-check:  ## Vérifie les types avec mypy
	@echo "🔬 Vérification des types..."
	$(PYTHON) -m mypy . --ignore-missing-imports

# ─────────────────────────────────────────────────────────────────────────────
# Build et packaging
# ─────────────────────────────────────────────────────────────────────────────
build:  ## Crée l'exécutable avec PyInstaller
	@echo "📦 Création de l'exécutable..."
	$(PYTHON) -m PyInstaller letruc.spec
	@echo "✅ Exécutable créé dans dist/"

build-clean:  ## Nettoie et recrée l'exécutable
	@echo "🧹 Nettoyage avant build..."
	rm -rf build dist
	$(PYTHON) -m PyInstaller letruc.spec --clean
	@echo "✅ Exécutable créé dans dist/"

# ─────────────────────────────────────────────────────────────────────────────
# Nettoyage
# ─────────────────────────────────────────────────────────────────────────────
clean:  ## Nettoie les fichiers générés
	@echo "🧹 Nettoyage..."
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf *.pyc */*.pyc */*/*.pyc
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf *.egg-info
	@echo "✅ Nettoyage terminé"

clean-all:  ## Nettoie tout (y compris build et dist)
	@echo "🧹 Nettoyage complet..."
	$(MAKE) clean
	rm -rf build dist
	rm -rf debug_run_*
	@echo "✅ Nettoyage complet terminé"

# ─────────────────────────────────────────────────────────────────────────────
# Documentation
# ─────────────────────────────────────────────────────────────────────────────
docs:  ## Affiche la documentation
	@echo "📚 Documentation disponible :"
	@echo "  - README : docs/README.md"
	@echo "  - Déploiement : docs/DEPLOYMENT.md"
	@echo "  - Index : docs/INDEX.md"

docs-view:  ## Ouvre la documentation
	@if command -v xdg-open > /dev/null; then \
		xdg-open docs/README.md; \
	elif command -v open > /dev/null; then \
		open docs/README.md; \
	else \
		cat docs/README.md; \
	fi

# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────
venv:  ## Crée un environnement virtuel
	@echo "🐍 Création de l'environnement virtuel..."
	$(PYTHON) -m venv venv
	@echo "✅ Environnement créé : venv/"
	@echo ""
	@echo "Pour l'activer :"
	@if [ "$(OS)" = "Windows_NT" ]; then \
		echo "  venv\\Scripts\\activate"; \
	else \
		echo "  source venv/bin/activate"; \
	fi

deps:  ## Affiche les dépendances installées
	@echo "📦 Dépendances installées :"
	$(PYTHON) -m pip list

deps-outdated:  ## Affiche les dépendances obsolètes
	@echo "⚠️  Dépendances obsolètes :"
	$(PYTHON) -m pip list --outdated

# ─────────────────────────────────────────────────────────────────────────────
# Workflow complet
# ─────────────────────────────────────────────────────────────────────────────
setup:  ## Setup complet (install + test)
	@echo "🚀 Setup complet..."
	$(MAKE) install-dev
	$(MAKE) test
	@echo "✅ Setup terminé avec succès"

ci:  ## Pipeline CI (format + lint + test)
	@echo "🔄 Pipeline CI..."
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) test
	@echo "✅ Pipeline CI terminé"

release:  ## Prépare une release (clean + test + build)
	@echo "📦 Préparation de la release..."
	$(MAKE) clean-all
	$(MAKE) test
	$(MAKE) build
	@echo "✅ Release prête dans dist/"
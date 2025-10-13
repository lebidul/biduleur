@echo off
REM =============================================================================
REM Tasks pour Le Truc PyQt6 (Windows)
REM =============================================================================
REM Usage: tasks.bat [commande]
REM =============================================================================

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="install" goto install
if "%1"=="install-dev" goto install_dev
if "%1"=="run" goto run
if "%1"=="test" goto test
if "%1"=="check" goto check
if "%1"=="build" goto build
if "%1"=="clean" goto clean
if "%1"=="format" goto format
if "%1"=="lint" goto lint
goto invalid

REM ─────────────────────────────────────────────────────────────────────────────
:help
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  Le Truc PyQt6 - Commandes disponibles (Windows)            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo   install        Installe les dépendances standard
echo   install-dev    Installe les dépendances de développement
echo   run            Lance l'application
echo   test           Lance les tests
echo   check          Vérifie la migration
echo   build          Crée l'exécutable avec PyInstaller
echo   clean          Nettoie les fichiers générés
echo   format         Formate le code avec black
echo   lint           Analyse le code avec flake8
echo.
echo Usage : tasks.bat [commande]
echo.
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:install
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo 📦 Installation des dépendances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo ✅ Installation terminée
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:install_dev
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo 📦 Installation des dépendances de développement...
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
echo.
echo ✅ Installation terminée
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:run
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo 🚀 Lancement de l'application...
python main.py
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:test
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo 🧪 Lancement des tests...
python tests\test_gui.py
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:check
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo ✅ Vérification de la migration...
cd ..
python tools\check_migration.py
cd leTruc_pyqt
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:build
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo 📦 Création de l'exécutable...
python -m PyInstaller letruc.spec
echo.
echo ✅ Exécutable créé dans dist\
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:clean
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo 🧹 Nettoyage...
if exist __pycache__ rmdir /s /q __pycache__
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist htmlcov rmdir /s /q htmlcov
if exist .coverage del /f .coverage
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q *.pyc 2>nul
echo.
echo ✅ Nettoyage terminé
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:format
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo 🎨 Formatage du code...
python -m black .
python -m isort .
echo.
echo ✅ Formatage terminé
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:lint
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo 🔍 Analyse du code...
python -m flake8 . --max-line-length=100 --exclude=venv,build,dist
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:invalid
REM ─────────────────────────────────────────────────────────────────────────────
echo.
echo ❌ Commande invalide : %1
echo.
echo Utilisez "tasks.bat help" pour voir les commandes disponibles
goto end

REM ─────────────────────────────────────────────────────────────────────────────
:end
REM ─────────────────────────────────────────────────────────────────────────────
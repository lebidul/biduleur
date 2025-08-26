@echo off
cd /d "%~dp0"  :: Se place dans le dossier parent

:: Nettoyer les anciens dossiers
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

:: Vérifier la structure
echo Vérification de la structure :
echo.
echo Contenu du dossier courant :
dir /b
echo.
echo Contenu de biduleur\ :
if exist "biduleur\" (
    dir /b biduleur\
) else (
    echo ERREUR: Dossier biduleur/ introuvable
    exit /b 1
)

:: Vérifier que main.py existe
if not exist "biduleur\main.py" (
    echo ERREUR: Le fichier biduleur\main.py est introuvable !
    exit /b 1
)

:: Vérifier que l'icône existe (optionnel)
if not exist "biduleur.ico" (
    echo ATTENTION: Le fichier biduleur.ico est introuvable. L'exécutable sera créé sans icône personnalisée.
)

:: Exécuter PyInstaller
echo Lancement de PyInstaller...
python -m PyInstaller biduleur.spec --clean --workpath=build --distpath=dist

:: Vérifier le résultat
if exist "dist\biduleur.exe" (
    echo.
    echo =====================================
    echo Build réussi !
    echo L'exécutable est dans dist\
    dir dist\
    echo =====================================
) else (
    echo.
    echo =====================================
    echo ERREUR : Build échoué
    echo =====================================
    exit /b 1
)

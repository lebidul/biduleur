@echo off
cd /d "%~dp0"

:: Nettoyage des anciens builds
echo Nettoyage des anciens builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

:: Vérification de la structure
echo Vérification de la structure :
dir /b
if not exist "biduleur\main.py" (
    echo ERREUR: biduleur\main.py introuvable
    exit /b 1
)

:: Build
echo Création du build...
pyinstaller biduleur.spec --clean --workpath=build --distpath=dist

:: Vérification
if exist "dist\biduleur" (
    echo Build réussi !
    dir dist\
) else (
    echo ERREUR: Build échoué
    exit /b 1
)

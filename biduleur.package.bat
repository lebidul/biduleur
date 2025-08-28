@echo off
cd /d "%~dp0"

:: Nettoyage des anciens builds
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

:: Build en mode --onedir
echo Création du build en mode dossier...
python -m PyInstaller biduleur.spec --clean --workpath=build --distpath=dist

:: Vérification du build
if not exist "dist\biduleur" (
    echo ERREUR: Build échoué
    exit /b 1
)

:: Compression du dossier en ZIP
echo Compression du build en ZIP...
powershell -Command "Compress-Archive -Path 'dist\biduleur\*' -DestinationPath 'dist\biduleur-windows.zip' -Force"

echo Build et compression terminés avec succès !

#!/bin/bash
cd "$(dirname "$0")" || exit 1

# Nettoyage
echo "Nettoyage des anciens builds..."
rm -rf build 2>/dev/null
rm -rf dist 2>/dev/null

# Vérifications
echo "Vérification de la structure :"
ls -l
if [ ! -d "biduleur" ]; then
    echo "ERREUR: Dossier biduleur/ introuvable"
    exit 1
fi
if [ ! -f "biduleur/main.py" ]; then
    echo "ERREUR: biduleur/main.py introuvable"
    exit 1
fi

# Build
echo "Création du build..."
pyinstaller biduleur.spec --clean --workpath=build --distpath=dist

# Vérification
if [ -d "dist/biduleur" ]; then
    echo "Build réussi !"
    ls -l dist/
else
    echo "ERREUR: Build échoué"
    exit 1
fi

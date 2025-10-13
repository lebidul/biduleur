# Guide de Déploiement - Le Truc (PyQt6)

## 📦 Création d'un exécutable standalone

### Windows

#### Méthode 1 : PyInstaller (Recommandée)

1. **Installer PyInstaller**
   ```bash
   pip install pyinstaller
   ```

2. **Créer l'exécutable**
   ```bash
   # Avec le fichier .spec personnalisé
   pyinstaller letruc.spec
   
   # Ou directement
   pyinstaller --onefile --windowed --icon=leTruc/assets/LesArtsServices.ico --name=LeTruc main.py
   ```

3. **Options avancées**
   ```bash
   # Avec console (pour debug)
   pyinstaller letruc.spec --console
   
   # Sans UPX (compression)
   pyinstaller letruc.spec --noupx
   
   # Nettoyer avant rebuild
   pyinstaller letruc.spec --clean
   ```

4. **Résultat**
   - Exécutable : `dist/LeTruc.exe`
   - Taille : ~80-150 MB (inclut Python + PyQt6)

#### Méthode 2 : cx_Freeze

1. **Installer cx_Freeze**
   ```bash
   pip install cx_Freeze
   ```

2. **Créer setup_exe.py**
   ```python
   from cx_Freeze import setup, Executable
   
   setup(
       name="LeTruc",
       version="1.0",
       description="Générateur de Bidul",
       executables=[Executable("../main.py", 
                               base="Win32GUI",
                               icon="leTruc/assets/LesArtsServices.ico")]
   )
   ```

3. **Build**
   ```bash
   python setup_exe.py build
   ```

### macOS

#### PyInstaller pour macOS

1. **Créer un .app bundle**
   ```bash
   pyinstaller --onefile --windowed \
               --icon=leTruc/assets/LesArtsServices.icns \
               --name=LeTruc \
               --osx-bundle-identifier=com.lesartsservices.letruc \
               main.py
   ```

2. **Signer l'application** (optionnel)
   ```bash
   codesign --deep --force --verify --verbose \
            --sign "Developer ID Application: Votre Nom" \
            dist/LeTruc.app
   ```

3. **Créer un DMG** (optionnel)
   ```bash
   # Installer create-dmg
   brew install create-dmg
   
   # Créer le DMG
   create-dmg \
     --volname "LeTruc Installer" \
     --window-pos 200 120 \
     --window-size 600 400 \
     --icon-size 100 \
     --icon "LeTruc.app" 175 120 \
     --hide-extension "LeTruc.app" \
     --app-drop-link 425 120 \
     "LeTruc-Installer.dmg" \
     "dist/"
   ```

### Linux

#### AppImage (Recommandé)

1. **Installer python-appimage**
   ```bash
   pip install python-appimage
   ```

2. **Créer l'AppImage**
   ```bash
   python-appimage build app \
     -l manylinux2014_x86_64 \
     -p 3.10 \
     main.py
   ```

#### Alternatives

- **Snap Package**
- **Flatpak**
- **DEB/RPM packages**

---

## 🚀 Distribution

### Structure du package de distribution

```
LeTruc-v1.0-Windows/
├── LeTruc.exe                  # Exécutable principal
├── README.txt                  # Guide d'utilisation
├── LICENCE.txt                 # Licence
├── templates/                  # Templates optionnels
│   ├── template.csv
│   └── template.xlsx
└── exemples/                   # Exemples de fichiers
    ├── exemple.csv
    └── config-exemple.yml
```

### Fichiers à inclure

1. **README.txt** (Guide utilisateur)
   - Instructions d'installation
   - Premiers pas
   - FAQ
   - Contact support

2. **LICENCE.txt**
   - Termes de la licence
   - Copyright

3. **Templates et exemples**
   - Fichiers modèles
   - Configuration par défaut
   - Exemples de données

---

## 📝 Checklist avant déploiement

### Tests

- [ ] Tous les tests unitaires passent (`python test_gui.py`)
- [ ] L'application se lance sans erreur
- [ ] Toutes les sections fonctionnent
- [ ] Le pipeline complet fonctionne
- [ ] Les aperçus d'images s'affichent
- [ ] Le drag & drop fonctionne
- [ ] L'exécutable fonctionne sur une machine vierge

### Performance

- [ ] Temps de démarrage < 5 secondes
- [ ] Interface réactive
- [ ] Pas de fuite mémoire
- [ ] Génération PDF performante

### Documentation

- [ ] README à jour
- [ ] Guide utilisateur complet
- [ ] CHANGELOG.md à jour
- [ ] Licence incluse

### Sécurité

- [ ] Pas de credentials en dur
- [ ] Validation des entrées utilisateur
- [ ] Gestion sécurisée des fichiers temporaires

---

## 🔧 Optimisation de la taille

### PyInstaller

1. **Exclure les modules non utilisés**
   ```python
   # Dans letruc.spec
   excludes=[
       'matplotlib',
       'numpy',
       'pandas',
       # Modules non nécessaires
   ]
   ```

2. **Compression UPX**
   ```bash
   # Installer UPX
   # Windows : télécharger depuis https://upx.github.io/
   # macOS : brew install upx
   # Linux : sudo apt install upx
   
   # Build avec compression
   pyinstaller letruc.spec --upx-dir=/path/to/upx
   ```

3. **One-file vs One-folder**
   - **One-file** : Plus simple, mais plus lent au démarrage
   - **One-folder** : Plus rapide, mais plusieurs fichiers

---

## 🌐 Installation sur machine utilisateur

### Windows

1. **Prérequis système**
   - Windows 10/11 (64-bit)
   - 4 GB RAM minimum
   - 500 MB d'espace disque

2. **Installation**
   ```
   1. Extraire le ZIP
   2. Double-cliquer sur LeTruc.exe
   3. (Optionnel) Créer un raccourci sur le Bureau
   ```

3. **Antivirus**
   - L'exécutable peut être flaggé par l'antivirus
   - Ajouter une exception si nécessaire
   - Ou signer le code avec un certificat

### macOS

1. **Prérequis**
   - macOS 10.15+ (Catalina ou supérieur)
   - 4 GB RAM minimum

2. **Installation**
   ```
   1. Ouvrir le DMG
   2. Glisser LeTruc.app vers Applications
   3. Premier lancement : Clic droit > Ouvrir
   ```

3. **Gatekeeper**
   - Autoriser l'application non signée :
     ```bash
     sudo xattr -r -d com.apple.quarantine /Applications/LeTruc.app
     ```

### Linux

1. **Prérequis**
   - Distribution basée sur Debian/Ubuntu ou Fedora/RHEL
   - Python 3.10+

2. **Installation AppImage**
   ```bash
   chmod +x LeTruc-x86_64.AppImage
   ./LeTruc-x86_64.AppImage
   ```

---

## 🐛 Résolution de problèmes

### L'exécutable ne se lance pas

**Windows :**
- Vérifier l'antivirus
- Installer Visual C++ Redistributable
- Lancer depuis CMD pour voir les erreurs

**macOS :**
- Autoriser dans Préférences Système > Sécurité
- Vérifier les permissions : `ls -la LeTruc.app`

**Linux :**
- Vérifier les dépendances : `ldd LeTruc`
- Installer les bibliothèques manquantes

### Erreur "Cannot load backend"

```bash
# Vérifier PyQt6
python -c "from PyQt6.QtWidgets import QApplication"

# Réinstaller si nécessaire
pip uninstall PyQt6
pip install PyQt6
```

### Icône ne s'affiche pas

- Vérifier que `LesArtsServices.ico` existe
- Rebuild avec `--clean`
- Vérifier le chemin dans `letruc.spec`

### Fichiers manquants

```bash
# Ajouter dans letruc.spec > datas
('chemin/vers/fichier', 'destination')
```

---

## 📊 Métriques de déploiement

### Objectifs de performance

| Métrique | Cible | Mesuré |
|----------|-------|--------|
| Taille exécutable | < 150 MB | - |
| Temps démarrage | < 5 s | - |
| Mémoire utilisée | < 200 MB | - |
| Temps génération PDF | < 30 s | - |

### Tests de compatibilité

| Plateforme | Version | Testé | OK |
|------------|---------|-------|-----|
| Windows 10 | 64-bit | [ ] | [ ] |
| Windows 11 | 64-bit | [ ] | [ ] |
| macOS Monterey | 12.x | [ ] | [ ] |
| macOS Ventura | 13.x | [ ] | [ ] |
| Ubuntu | 22.04 | [ ] | [ ] |
| Fedora | 38 | [ ] | [ ] |

---

## 📦 Distribution automatisée (CI/CD)

### GitHub Actions

Créer `.github/workflows/build.yml` :

```yaml
name: Build Executable

on:
  push:
    tags:
      - 'v*'

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pip install pyinstaller
      - run: pyinstaller letruc.spec
      - uses: actions/upload-artifact@v3
        with:
          name: LeTruc-Windows
          path: dist/LeTruc.exe

  build-macos:
    runs-on: macos-latest
    # ... similaire

  build-linux:
    runs-on: ubuntu-latest
    # ... similaire
```

---

## 🔐 Signature de code

### Windows (Certificat code signing)

```bash
# Avec signtool.exe
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist/LeTruc.exe
```

### macOS (Developer ID)

```bash
# Signer l'app
codesign --deep --force --verify --verbose \
         --sign "Developer ID Application: Your Name" \
         --options runtime \
         dist/LeTruc.app

# Notariser
xcrun notarytool submit dist/LeTruc.dmg \
      --apple-id your@email.com \
      --team-id TEAMID \
      --password app-specific-password \
      --wait
```

---

## 📞 Support et maintenance

### Logs et diagnostics

Activer le mode debug dans l'application :
- Cocher "Activer le mode débogage"
- Les logs sont dans `debug_run_TIMESTAMP/`

### Mise à jour

1. Versionner dans `_version.py`
2. Build nouvelle version
3. Distribuer via :
   - Site web
   - Store (Microsoft Store, Mac App Store)
   - Auto-update (avec sparkle, etc.)

### Collecte de crash reports

Intégrer Sentry ou similaire pour collecter les erreurs en production.

---

## ✅ Validation finale

Avant release :

- [ ] Build sur les 3 plateformes (Windows, macOS, Linux)
- [ ] Tests sur machines vierges
- [ ] Vérification antivirus (VirusTotal)
- [ ] Documentation complète
- [ ] Numéro de version à jour
- [ ] Changelog rempli
- [ ] Backup des sources
- [ ] Tag Git créé
- [ ] Release GitHub publiée
# biduleur.spec
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import os
import sys

# Solution pour obtenir le chemin du dossier parent
current_dir = os.getcwd()

# Vérification que main.py existe
main_script = os.path.join(current_dir, 'biduleur', 'main.py')
if not os.path.exists(main_script):
    raise FileNotFoundError(f"Le fichier {main_script} est introuvable")

# Collecte des dépendances supplémentaires
hidden_imports = collect_submodules('tkinter')
hidden_imports += [
    'biduleur.csv_utils',
    'biduleur.format_utils',
    'biduleur.constants',
    'biduleur.event_utils',
    'pkg_resources.py2_warn',
]

# Collecte des fichiers de données
datas = collect_data_files('tkinter')  # Pour tkinter

# Ajoutez explicitement les fichiers du package biduleur
datas += [
    (os.path.join(current_dir, 'biduleur'), 'biduleur')  # Copie tout le dossier biduleur
]

a = Analysis(
    [main_script],
    pathex=[current_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='biduleur',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    icon=os.path.join(current_dir, 'biduleur.ico') if os.path.exists(os.path.join(current_dir, 'biduleur.ico')) else None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='biduleur'
)

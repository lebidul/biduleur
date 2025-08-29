# biduleur.spec (version corrigée)
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
    'pandas',
    'numpy',
    'python_dateutil',
    'pytz',
    'tzdata',
    'six',
]

# Modules à exclure explicitement pour réduire la taille
excludes = [
    'Tkconstants', 'tcl', 'tk', 'Tix', 'sqlite3', 'email', 'http', 'xml', 'html',
    'urllib', 'unittest', 'pytest', 'doctest', 'pydoc', 'inspect', 'pdb',
    'matplotlib', 'scipy', 'sklearn', 'tensorflow', 'torch', 'torchvision', 'torchaudio',
    'IPython', 'jupyter', 'sphinx', 'pytest', 'setuptools', 'pip', 'wheel',
    'scipy.linalg', 'scipy.sparse', 'scipy.stats', 'scipy.integrate', 'scipy.optimize'
]

# Collecte des fichiers de données
datas = collect_data_files('biduleur')  # Pour les fichiers dans biduleur/

a = Analysis(
    [main_script],
    pathex=[current_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
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
    debug=False,  # Désactivez le mode debug pour réduire la taille
    bootloader_ignore_signals=False,
    strip=False,  # Désactivez le strip pour éviter les erreurs sur Windows
    upx=True,     # Activez UPX pour compresser l'exécutable
    runtime_tmpdir=None,
    console=True,  # Activez la console pour voir les erreurs
    icon=os.path.join(current_dir, 'biduleur.ico') if os.path.exists(os.path.join(current_dir, 'biduleur.ico')) else None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,  # Désactivez le strip pour éviter les erreurs sur Windows
    upx=True,     # Activez UPX pour compresser l'exécutable
    upx_exclude=[],
    name='biduleur'
)

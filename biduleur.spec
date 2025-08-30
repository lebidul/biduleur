# biduleur.spec (version optimisée pour réduire la taille)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import os

current_dir = os.getcwd()
main_script = os.path.join(current_dir, 'biduleur', 'main.py')
if not os.path.exists(main_script):
    raise FileNotFoundError(f"Le fichier {main_script} est introuvable")

# Hidden imports : NE PAS inclure pkg_resources
hidden_imports = [
    'biduleur.csv_utils',
    'biduleur.format_utils',
    'biduleur.constants',
    'biduleur.event_utils',
]

# Si tu forces pandas/numpy (recommandé en CI) :
from PyInstaller.utils.hooks import collect_submodules
hidden_imports += collect_submodules('pandas')
hidden_imports += collect_submodules('numpy')
hidden_imports += collect_submodules('openpyxl')

# Exclusions (pas d'exclusion agressive de la stdlib comme urllib/inspect/pydoc)
excludes = [
    'Tkconstants','tcl','tk','Tix','sqlite3',
    'unittest','pytest','doctest','pdb',
    'matplotlib','scipy','sklearn','tensorflow',
    'torch','torchvision','torchaudio',
    'IPython','jupyter','sphinx','setuptools','pip','wheel',
    'pkg_resources'
]

# Datas : uniquement les fichiers non-Python nécessaires
datas = collect_data_files('tkinter')  # nécessaire pour tkinter

# Inclure uniquement les fichiers Python du package biduleur, sans __pycache__
for root, dirs, files in os.walk(os.path.join(current_dir, 'biduleur')):
    files = [f for f in files if f.endswith('.py')]  # inclure seulement les .py
    for f in files:
        src = os.path.join(root, f)
        dest = os.path.relpath(root, current_dir)
        datas.append((src, dest))

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
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='biduleur'
)

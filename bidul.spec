# bidul.spec
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()

entry_script = os.path.join(BASE_DIR, 'gui.py')
ICON_PATH = os.path.join(BASE_DIR, 'biduleur.ico')
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

# `datas` ne contient QUE les assets, pas les fichiers .py
datas = [
    ('misenpageur/assets', 'misenpageur/assets'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    ('biduleur/templates', 'biduleur/templates'),
    ('bin/win64', 'bin')
]

binaries = []

EXCLUDES = [
    'torch', 'tensorflow', 'scipy', 'matplotlib',
]

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    # `hiddenimports` contient toutes les bibliothèques et nos modules locaux
    hiddenimports=[
        'svglib', 'lxml', 'lxml._elementpath',
        'pandas', 'numpy', 'openpyxl', # Dépendances clés
        'biduleur', 'misenpageur'      # Nos modules locaux
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='bidul',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=ICON_PATH,
    version=VERSION_FILE,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bidul'
)
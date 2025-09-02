# bidul.spec
# Build GUI "bidul" avec PyInstaller (sans console)

import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.datastruct import Tree

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# >>>> ADAPTE LA LIGNE CI-DESSOUS SI BESOIN <<<<
entry_script = os.path.join(BASE_DIR, 'bidul', 'gui.py')  # <- chemin réel vers ta GUI

datas = []

# Inclure config/layout de misenpageur
cfg_path = os.path.join(BASE_DIR, 'misenpageur', 'config.yml')
lay_path = os.path.join(BASE_DIR, 'misenpageur', 'layout.yml')
if os.path.isfile(cfg_path):
    datas.append((cfg_path, 'misenpageur'))
if os.path.isfile(lay_path):
    datas.append((lay_path, 'misenpageur'))

# Inclure le dossier d'assets de misenpageur (images, ours, etc.)
assets_dir = os.path.join(BASE_DIR, 'misenpageur', 'assets')
if os.path.isdir(assets_dir):
    datas.append(Tree(assets_dir, prefix='misenpageur/assets'))

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[],   # PyInstaller suivra les imports depuis entry_script
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='bidul',
    debug=False,
    strip=False,
    upx=True,
    console=False,  # GUI
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bidul'
)

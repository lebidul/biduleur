# bidul.spec — build GUI "bidul" (sans console) avec icône

import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()
entry_script = os.path.join('', 'gui.py')

# >>> ADAPTE ICI le chemin de l'icône (même que biduleur) :
ICON_PATH = os.path.join(BASE_DIR, 'biduleur.ico')
# Par ex. si tu l’as ailleurs :
# ICON_PATH = os.path.join(BASE_DIR, 'assets', 'biduleur.ico')

datas = []

# misenpageur config/layout
for rel in ('misenpageur/config.yml', 'misenpageur/layout.yml'):
    absf = os.path.join(BASE_DIR, rel)
    if os.path.isfile(absf):
        datas.append((absf, 'misenpageur'))

# misenpageur assets
assets_abs = os.path.join(BASE_DIR, 'misenpageur', 'assets')
if os.path.isdir(assets_abs):
    datas.append((assets_abs, 'misenpageur/assets'))

# biduleur templates (CSV / XLSX)
templates_abs = os.path.join(BASE_DIR, 'biduleur', 'templates')
if os.path.isdir(templates_abs):
    datas.append((templates_abs, 'biduleur/templates'))

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    console=False,         # GUI
    icon=ICON_PATH,        # <<—— Icône
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

# bidul.spec — build GUI "bidul" (sans console)
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()

# >>> adapte si besoin : chemin réel de ta GUI
entry_script = os.path.join('', 'gui.py')

datas = []

# Inclure config & layout si présents
cfg_rel = os.path.join('misenpageur', 'config.yml')
lay_rel = os.path.join('misenpageur', 'layout.yml')
cfg_abs = os.path.join(BASE_DIR, cfg_rel)
lay_abs = os.path.join(BASE_DIR, lay_rel)
if os.path.isfile(cfg_abs):
    datas.append((cfg_abs, 'misenpageur'))
if os.path.isfile(lay_abs):
    datas.append((lay_abs, 'misenpageur'))

# Inclure le dossier d'assets (ours, logos, cover, etc.)
assets_abs = os.path.join(BASE_DIR, 'misenpageur', 'assets')
if os.path.isdir(assets_abs):
    # ✅ PyInstaller accepte un dossier en src : il sera copié tel quel sous dest
    datas.append((assets_abs, 'misenpageur/assets'))

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,          # <- uniquement des (src, dest)
    hiddenimports=[],     # PyInstaller suivra les imports à partir de gui.py
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

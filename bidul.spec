# bidul.spec
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

# La méthode la plus fiable pour trouver la racine dans tous les contextes
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

entry_script = os.path.join(BASE_DIR, 'gui.py')
ICON_PATH = os.path.join(BASE_DIR, 'biduleur.ico')
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

# On utilise des chemins relatifs, PyInstaller les résoudra
datas = [
    ('misenpageur/assets', 'misenpageur/assets'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    ('biduleur/templates', 'biduleur/templates'),
]

binaries = [
    ('bin/win64/pdf2svg.exe', 'bin'),
    ('bin/win64/*.dll', 'bin')
]

EXCLUDES = [
    'torch', 'tensorflow', 'scipy', 'matplotlib',
]

a = Analysis(
    [entry_script],
    # ==================== LA CORRECTION EST ICI ====================
    # On combine les deux approches pour une robustesse maximale.
    # pathex dit à PyInstaller où chercher les modules.
    pathex=[BASE_DIR],
    # hiddenimports force l'inclusion, même si l'analyse statique les manque.
    hiddenimports=[
        'svglib', 'lxml', 'lxml._elementpath',
        'biduleur', 'misenpageur'
    ],
    # =============================================================
    binaries=binaries,
    datas=datas,
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
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
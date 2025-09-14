# bidul.spec
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()

# ==================== LA CORRECTION EST ICI (1/2) ====================
# On définit explicitement les chemins vers nos dossiers de code source.
# PyInstaller les ajoutera à son PYTHONPATH interne.
paths = [BASE_DIR]
# ====================================================================

entry_script = os.path.join(BASE_DIR, 'gui.py')
ICON_PATH = os.path.join(BASE_DIR, 'misenpageur', 'assets', 'icon', 'biduleur.ico')
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

datas = [
    ('misenpageur/assets', 'misenpageur/assets'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    ('biduleur/templates', 'biduleur/templates'),
    ('bin/win64', 'bin/win64')
]

binaries = []

EXCLUDES = [
    'torch', 'tensorflow', 'scipy', 'matplotlib',
]

a = Analysis(
    [entry_script],
    # On garde pathex, c'est une bonne pratique
    pathex=paths,
    binaries=binaries,
    datas=datas,
    # On force l'inclusion des modules
    hiddenimports=[
        'svglib', 'lxml', 'lxml._elementpath',
        'biduleur', 'misenpageur'
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
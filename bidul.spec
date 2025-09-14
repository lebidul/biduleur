# bidul.spec
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()

entry_script = os.path.join(BASE_DIR, 'gui.py')
ICON_PATH = os.path.join(BASE_DIR, 'misenpageur', 'assets', 'icon', 'biduleur.ico')
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

# ==================== LA CORRECTION EST ICI ====================
# On utilise la fonction Tree pour copier les dossiers de code source
# comme s'il s'agissait de données. C'est une méthode très robuste.
datas = [
    ('misenpageur/assets', 'misenpageur/assets'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    ('biduleur/templates', 'biduleur/templates'),
    ('bin/win64', 'bin/win64'),
    # On ajoute nos modules comme des "arbres" de données
    ('biduleur', 'biduleur'),
    ('misenpageur', 'misenpageur')
]

# On peut vider binaries, car tout est traité comme des données
binaries = []
EXCLUDES = [
    'torch', 'tensorflow', 'scipy', 'matplotlib',
]

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    # On garde les hiddenimports pour les dépendances tierces
    hiddenimports=['svglib', 'lxml', 'lxml._elementpath'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
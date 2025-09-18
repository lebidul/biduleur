# bidul.spec
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()

entry_script = os.path.join(BASE_DIR, 'leTruc/main.py')
ICON_PATH = os.path.join(BASE_DIR, 'biduleur.ico')
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

# ==================== LA CORRECTION EST ICI ====================
# On ajoute nos dossiers de code source comme des "données".
# PyInstaller va les copier tels quels dans le dossier final.
datas = [
    ('misenpageur/assets', 'misenpageur/assets'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    ('biduleur/templates', 'biduleur/templates'),
    ('bin/win64', 'bin/win64'),
    ('biduleur', 'biduleur'), # Copier le dossier biduleur
    ('biduleur/templates', 'biduleur/templates'),
    ('misenpageur', 'misenpageur') # Copier le dossier misenpageur
]

# On n'a plus besoin de `hiddenimports` pour nos modules,
# car ils seront trouvés directement comme des dossiers.
hiddenimports = ['svglib', 'lxml', 'lxml._elementpath', 'pandas', 'openpyxl', 'rectpack']
# =============================================================

binaries = []

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(pyz, a.scripts, name='bidul', console=False, icon=ICON_PATH, version=VERSION_FILE)

coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name='bidul')
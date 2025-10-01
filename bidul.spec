# bidul.spec
import os
import tkinterdnd2
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()
tkinterdnd2_path = os.path.dirname(tkinterdnd2.__file__)

entry_script = os.path.join(BASE_DIR, 'run_gui.py')
ICON_PATH = os.path.join(BASE_DIR, 'biduleur.ico')
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

# On ajoute nos dossiers de code source comme des "données".
# PyInstaller va les copier tels quels dans le dossier final.
datas = [
    ('misenpageur/assets', 'misenpageur/assets'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    (tkinterdnd2_path, 'tkinterdnd2'),
    ('biduleur/templates', 'biduleur/templates'),
    ('bin/win64', 'bin/win64'),
    ('biduleur', 'biduleur'), # Copier le dossier biduleur
    ('biduleur/templates', 'biduleur/templates'),
    ('misenpageur', 'misenpageur'), # Copier le dossier misenpageur
    ('leTruc/assets', 'leTruc/assets')
]

# On n'a plus besoin de `hiddenimports` pour nos modules,
# car ils seront trouvés directement comme des dossiers.
# hiddenimports = ['svglib', 'lxml', 'lxml._elementpath', 'pandas', 'openpyxl', 'rectpack']
hiddenimports = ['rectpack']

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

exe = EXE(
        pyz,
        a.scripts,
        name='bidul',
        console=False,
        icon=ICON_PATH,
        version=VERSION_FILE
        )

coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        name='bidul'
        )
# bidul.spec
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()

entry_script = os.path.join(BASE_DIR, 'gui.py')
ICON_PATH = os.path.join(BASE_DIR, 'biduleur.ico')
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

datas = [
    ('misenpageur/assets', 'misenpageur/assets'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    ('biduleur/templates', 'biduleur/templates'),
    ('bin/win64', 'bin')
]

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=['svglib', 'lxml', 'lxml._elementpath', 'pandas', 'openpyxl'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(pyz, a.scripts, name='bidul', console=False, icon=ICON_PATH, version=VERSION_FILE)

coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name='bidul')
# bidul.spec
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()
entry_script = os.path.join(BASE_DIR, 'gui.py')
ICON_PATH = os.path.join(BASE_DIR, 'misenpageur', 'assets', 'icon', 'biduleur.ico') # Assurez-vous que l'icône est bien là
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

datas = [
    (os.path.join(BASE_DIR, 'misenpageur/assets'), 'misenpageur/assets'),
    (os.path.join(BASE_DIR, 'misenpageur/config.yml'), 'misenpageur'),
    (os.path.join(BASE_DIR, 'misenpageur/layout.yml'), 'misenpageur'),
    (os.path.join(BASE_DIR, 'biduleur/templates'), 'biduleur/templates'),
]

# On construit des chemins absolus pour les binaires
binaries = [
    (os.path.join(BASE_DIR, 'bin/win64/pdf2svg.exe'), 'bin/win64'),
    (os.path.join(BASE_DIR, 'bin/win64/*.dll'), 'bin/win64')
]

# Paquets lourds à exclure
EXCLUDES = [
    'torch', 'tensorflow', 'scipy', 'matplotlib',
]

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=['svglib', 'lxml'], # Aides pour PyInstaller
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
    console=False, # Important : pas de console
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
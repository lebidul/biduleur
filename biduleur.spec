# bidul.spec — build GUI "bidul" (sans console) avec icône + version info + excludes
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

BASE_DIR = os.getcwd()
entry_script = os.path.join('', 'gui.py')

# Icône (mets le bon chemin vers TON .ico)
ICON_PATH = os.path.join(BASE_DIR, '', '', 'biduleur.ico')
# Version file (si absent, enlève l’argument 'version=' plus bas)
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

datas = []

# misenpageur config/layout
for rel in ('misenpageur/config.yml', 'misenpageur/layout.yml'):
    absf = os.path.join(BASE_DIR, rel)
    if os.path.isfile(absf):
        datas.append((absf, 'misenpageur'))

# misenpageur assets (ours, cover, logos, etc.)
assets_abs = os.path.join(BASE_DIR, 'misenpageur', 'assets')
if os.path.isdir(assets_abs):
    datas.append((assets_abs, 'misenpageur/assets'))

# biduleur templates (CSV / XLSX)
templates_abs = os.path.join(BASE_DIR, 'biduleur', 'templates')
if os.path.isdir(templates_abs):
    datas.append((templates_abs, 'biduleur/templates'))

# Optionnel : exclure les paquets lourds non utilisés (réduit taille et temps de build)
EXCLUDES = [
    'torch', 'torchvision', 'torchaudio',
    'tensorflow', 'tensorboard',
    'transformers',
    'scipy',            # si tu n'en as pas besoin
    'matplotlib',       # GUI Tk suffit
    'nltk',
    'cv2', 'opencv-python',
]

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
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
    console=False,            # GUI
    icon=ICON_PATH,           # icône
    version=VERSION_FILE,     # infos version / propriétés
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

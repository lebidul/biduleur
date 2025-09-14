# bidul.spec
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

# ==================== DÉBOGAGE ====================
print("--- Début de l'exécution de bidul.spec ---")
BASE_DIR = os.getcwd()
print(f"BASE_DIR (os.getcwd()): {BASE_DIR}")
# ==============================================

entry_script = os.path.join(BASE_DIR, 'gui.py')
ICON_PATH = os.path.join(BASE_DIR, 'biduleur.ico')
VERSION_FILE = os.path.join(BASE_DIR, 'bidul_version_info.txt')

# On déplace le dossier bin/win64 dans les `datas`.
# Le format est (source, destination_relative_dans_le_build)
datas = [
    ('misenpageur/assets', 'misenpageur/assets'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    ('biduleur/templates', 'biduleur/templates'),
    ('bin/win64', 'bin/win64') # <--- ON AJOUTE LE DOSSIER ICI
]

# La liste `binaries` est maintenant vide, car PyInstaller trouvera
# pdf2svg.exe comme une "data". Ce n'est pas un problème.
binaries = []
# =============================================================

EXCLUDES = [
    'torch', 'tensorflow', 'scipy', 'matplotlib',
]

# ==================== DÉBOGAGE ====================
print("\n--- Chemins des données (datas) ---")
for src, dst in datas:
    abs_src = os.path.join(BASE_DIR, src)
    print(f"Source: {src} -> Absolu: {abs_src} (Existe: {os.path.exists(abs_src)})")
print("------------------------------------")

print("\n--- Chemins des binaires (binaries) ---")
for src, dst in binaries:
    abs_src = os.path.join(BASE_DIR, src)
    print(f"Source: {src} -> Absolu: {abs_src} (Existe: {os.path.exists(abs_src)})")
print("------------------------------------")

EXCLUDES = [
    'torch', 'tensorflow', 'scipy', 'matplotlib',
]

a = Analysis(
    [entry_script],
    # On garde pathex, c'est une bonne pratique
    pathex=[BASE_DIR],
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
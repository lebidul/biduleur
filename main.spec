# main.spec
from PyInstaller.utils.hooks import collect_submodules

hidden_imports = collect_submodules('tkinter')

a = Analysis(
    ['biduleur/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports + [
        'biduleur.csv_utils',
        'biduleur.format_utils',
        'biduleur.constants',
        'biduleur.event_utils'  # Ajoute cette ligne
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='biduleur',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    icon='biduleur/biduleur.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='biduleur'
)

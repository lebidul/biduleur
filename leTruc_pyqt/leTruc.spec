# -*- mode: python ; coding: utf-8 -*-
"""
Configuration PyInstaller pour Le Truc (PyQt6)

Usage:
    pyinstaller letruc.spec

Ou pour créer un exécutable Windows :
    pyinstaller letruc.spec --noconsole --onefile
"""

block_cipher = None

# Données à inclure (templates, assets, config)
added_files = [
    ('biduleur/templates/*.csv', 'biduleur/templates'),
    ('biduleur/templates/*.xlsx', 'biduleur/templates'),
    ('misenpageur/config.yml', 'misenpageur'),
    ('misenpageur/layout.yml', 'misenpageur'),
    ('misenpageur/assets/*', 'misenpageur/assets'),
    ('leTruc/assets/*', 'leTruc/assets'),
]

# Modules cachés à inclure
hidden_imports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'biduleur.csv_utils',
    'biduleur.format_utils',
    'misenpageur.misenpageur.config',
    'misenpageur.misenpageur.layout',
    'misenpageur.misenpageur.pdfbuild',
    'misenpageur.misenpageur.svgbuild',
    'misenpageur.misenpageur.html_utils',
    'misenpageur.misenpageur.image_builder',
    'misenpageur.misenpageur.draw_logic',
    'misenpageur.misenpageur.layout_builder',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LeTruc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # False pour ne pas afficher la console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='leTruc/assets/LesArtsServices.ico',  # Icône de l'application
)

# Pour macOS : créer un bundle .app
# app = BUNDLE(
#     exe,
#     name='LeTruc.app',
#     icon='leTruc/assets/LesArtsServices.icns',
#     bundle_identifier='com.lesartsservices.letruc',
# )
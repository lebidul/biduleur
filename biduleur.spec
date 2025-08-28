# biduleur.spec (version corrigée pour __file__ et compatible local/GitHub Actions)
from PyInstaller.utils.hooks import collect_submodules
import os
import sys
import glob

# --- Détection du chemin courant ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Si __file__ n'est pas défini (cas de PyInstaller), utilise le répertoire courant
    current_dir = os.getcwd()

# --- Détection automatique de la DLL Python ---
def find_python_dll():
    # Chemin pour GitHub Actions (Linux/Windows)
    github_dll = os.path.join(sys.prefix, 'python*.dll')
    github_matches = glob.glob(github_dll)
    if github_matches:
        return github_matches[0]

    # Chemin pour venv local (Windows)
    venv_dll = os.path.join(sys.prefix, 'Scripts', 'python3*.dll')
    venv_matches = glob.glob(venv_dll)
    if venv_matches:
        return venv_matches[0]

    # Chemin pour installation système (Windows)
    system_dll = os.path.join(os.path.dirname(sys.executable), 'python*.dll')
    system_matches = glob.glob(system_dll)
    if system_matches:
        return system_matches[0]

    raise FileNotFoundError(
        f"Aucune DLL Python trouvée. Vérifiez que Python est correctement installé. "
        f"Chemins recherchés : {github_dll}, {venv_dll}, {system_dll}"
    )

python_dll = find_python_dll()
print(f"Utilisation de la DLL : {python_dll}")

# --- Configuration ---
hidden_imports = collect_submodules('tkinter') + [
    'biduleur.csv_utils',
    'biduleur.format_utils',
    'biduleur.constants',
    'biduleur.event_utils',
    'biduleur.cli',
    'pkg_resources.py2_warn',
]

a = Analysis(
    ['biduleur/main.py'],
    pathex=[current_dir],  # Utilise current_dir défini plus haut
    binaries=[(python_dll, '.')],
    datas=[],
    hiddenimports=hidden_imports,
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
    a.binaries,
    [],
    name='biduleur',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,  # Active la console pour le mode CLI
    icon='biduleur.ico' if os.path.exists(os.path.join(current_dir, 'biduleur.ico')) else None,
    onefile=True  # Exécutable unique
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

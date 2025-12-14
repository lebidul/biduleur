#!/usr/bin/env python3
# run_gui_nicegui.py
# Lance l'interface NiceGUI de Le Bidul
# Usage:
#   python run_gui_nicegui.py           # Mode web (navigateur)
#   python run_gui_nicegui.py --native  # Mode desktop (fenêtre native)

import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent))

from leNiceGui.app import main

if __name__ == "__main__":
    native_mode = "--native" in sys.argv
    main(native=native_mode)

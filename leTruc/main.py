import sys
from .app import Application

def main():
    """Point d'entrée principal pour lancer l'interface graphique."""
    # Ici, on pourrait gérer des arguments de ligne de commande pour le GUI si besoin
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    sys.exit(main())
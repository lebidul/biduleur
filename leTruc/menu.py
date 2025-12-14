# leTruc/menu.py
# Module pour la barre de menu et les dialogues associés (Crédits, Release Notes, Guide)

import tkinter as tk
from tkinter import ttk, scrolledtext
import webbrowser
import os

try:
    from ._version import __version__
except ImportError:
    __version__ = "dev"

# URL du dépôt GitHub
REPO_URL = "https://github.com/lebidul/bidul.biduleur"


def create_menu_bar(app: tk.Tk) -> None:
    """
    Crée et attache la barre de menu à l'application.

    Args:
        app: Instance de l'application principale (Application)
    """
    menubar = tk.Menu(app)
    app.config(menu=menubar)

    # Menu Aide
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Aide", menu=help_menu)

    help_menu.add_command(label="Guide utilisateur", command=lambda: show_user_guide(app))
    help_menu.add_command(label="Notes de version", command=lambda: show_release_notes(app))
    help_menu.add_separator()
    help_menu.add_command(label="À propos / Crédits", command=lambda: show_credits(app))


def show_credits(parent: tk.Tk) -> None:
    """Affiche la fenêtre des crédits."""
    dialog = tk.Toplevel(parent)
    dialog.title("À propos de Bidul")
    dialog.geometry("450x350")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    # Centrer la fenêtre
    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
    y = parent.winfo_y() + (parent.winfo_height() - 350) // 2
    dialog.geometry(f"+{x}+{y}")

    # Contenu
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Titre
    title_label = tk.Label(frame, text="Le Bidul", font=("Arial", 24, "bold"))
    title_label.pack(pady=(0, 5))

    version_label = tk.Label(frame, text=f"Version {__version__}", font=("Arial", 12))
    version_label.pack(pady=(0, 15))

    # Description
    desc_text = (
        "Générateur d'agenda culturel PDF\n"
        "pour Le Bidul de la Sarthe\n\n"
        "Transforme vos données Excel/CSV\n"
        "en documents PDF professionnels."
    )
    desc_label = tk.Label(frame, text=desc_text, font=("Arial", 10), justify=tk.CENTER)
    desc_label.pack(pady=(0, 15))

    # Séparateur
    ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

    # Crédits
    credits_text = (
        "Développé par Les Arts Services\n"
        "Licence : Open Source"
    )
    credits_label = tk.Label(frame, text=credits_text, font=("Arial", 9), fg="gray")
    credits_label.pack(pady=(0, 10))

    # Lien GitHub
    link_frame = ttk.Frame(frame)
    link_frame.pack(pady=5)

    repo_label = tk.Label(link_frame, text="Code source : ", font=("Arial", 9))
    repo_label.pack(side=tk.LEFT)

    link_label = tk.Label(
        link_frame,
        text=REPO_URL,
        font=("Arial", 9, "underline"),
        fg="blue",
        cursor="hand2"
    )
    link_label.pack(side=tk.LEFT)
    link_label.bind("<Button-1>", lambda e: webbrowser.open(REPO_URL))

    # Bouton Fermer
    close_btn = ttk.Button(frame, text="Fermer", command=dialog.destroy)
    close_btn.pack(pady=(15, 0))

    # Focus sur le bouton
    close_btn.focus_set()
    dialog.bind("<Escape>", lambda e: dialog.destroy())
    dialog.bind("<Return>", lambda e: dialog.destroy())


def show_release_notes(parent: tk.Tk) -> None:
    """Affiche la fenêtre des notes de version."""
    dialog = tk.Toplevel(parent)
    dialog.title("Notes de version")
    dialog.geometry("700x500")
    dialog.resizable(True, True)
    dialog.transient(parent)
    dialog.grab_set()

    # Centrer la fenêtre
    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
    y = parent.winfo_y() + (parent.winfo_height() - 500) // 2
    dialog.geometry(f"+{x}+{y}")

    # Frame principal
    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    # Titre
    title_label = tk.Label(frame, text="Notes de version", font=("Arial", 14, "bold"))
    title_label.pack(pady=(0, 10))

    # Zone de texte scrollable
    text_widget = scrolledtext.ScrolledText(
        frame,
        wrap=tk.WORD,
        font=("Consolas", 10),
        width=80,
        height=20
    )
    text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Charger le contenu
    release_notes_content = _load_release_notes()
    text_widget.insert(tk.END, release_notes_content)
    text_widget.config(state=tk.DISABLED)  # Lecture seule

    # Bouton Fermer
    close_btn = ttk.Button(frame, text="Fermer", command=dialog.destroy)
    close_btn.pack(pady=(5, 0))

    close_btn.focus_set()
    dialog.bind("<Escape>", lambda e: dialog.destroy())


def _load_release_notes() -> str:
    """Charge le contenu du fichier RELEASE_NOTES.md."""
    # Chercher le fichier à plusieurs emplacements possibles
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "RELEASE_NOTES.md"),
        os.path.join(os.path.dirname(__file__), "..", "RELEASE_NOTES.md"),
        "RELEASE_NOTES.md",
    ]

    # En mode PyInstaller, le fichier peut être dans le dossier de l'exécutable
    try:
        import sys
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
            possible_paths.insert(0, os.path.join(base_path, "RELEASE_NOTES.md"))
    except Exception:
        pass

    for path in possible_paths:
        try:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception:
            continue

    return "Notes de version non disponibles.\n\nLe fichier RELEASE_NOTES.md n'a pas été trouvé."


def show_user_guide(parent: tk.Tk) -> None:
    """Affiche la fenêtre du guide utilisateur."""
    dialog = tk.Toplevel(parent)
    dialog.title("Guide utilisateur")
    dialog.geometry("750x600")
    dialog.resizable(True, True)
    dialog.transient(parent)
    dialog.grab_set()

    # Centrer la fenêtre
    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() - 750) // 2
    y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
    dialog.geometry(f"+{x}+{y}")

    # Frame principal
    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    # Titre
    title_label = tk.Label(frame, text="Guide utilisateur", font=("Arial", 14, "bold"))
    title_label.pack(pady=(0, 10))

    # Zone de texte scrollable
    text_widget = scrolledtext.ScrolledText(
        frame,
        wrap=tk.WORD,
        font=("Arial", 10),
        width=85,
        height=25
    )
    text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Contenu du guide
    guide_content = _get_user_guide_content()
    text_widget.insert(tk.END, guide_content)
    text_widget.config(state=tk.DISABLED)  # Lecture seule

    # Bouton Fermer
    close_btn = ttk.Button(frame, text="Fermer", command=dialog.destroy)
    close_btn.pack(pady=(5, 0))

    close_btn.focus_set()
    dialog.bind("<Escape>", lambda e: dialog.destroy())


def _get_user_guide_content() -> str:
    """Retourne le contenu du guide utilisateur."""
    return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                         GUIDE UTILISATEUR - LE BIDUL                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              1. DÉMARRAGE RAPIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Glissez-déposez votre fichier Excel (.xls/.xlsx) ou CSV dans la zone prévue
2. Renseignez le titre du poster (ex: "Janvier 2025")
3. Vérifiez le chemin de sortie du PDF
4. Cliquez sur "🚀 Créer le Bidul !"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                           2. FORMAT DU FICHIER D'ENTRÉE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Votre fichier Excel/CSV doit contenir les colonnes suivantes :

  • DATE       : Date de l'événement (ex: "15/01/2025")
  • LIEU       : Nom du lieu (ex: "Le Mans")
  • EVENEMENT  : Description de l'événement
  • INACTIF    : Mettre "x" pour exclure un événement (optionnel)

Conseil : Une ligne par événement, triez par date avant import.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              3. OPTIONS DE MISE EN PAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TAILLE DE POLICE
  • Auto (recommandé) : La taille s'ajuste automatiquement au contenu
  • Forcée : Définissez une taille fixe (attention aux dépassements)

SÉPARATEURS DE DATES
  • Ligne : Trait horizontal après la date
  • Aucun : Pas de séparation visuelle

IMAGE DE COUVERTURE
  • Glissez une image pour personnaliser le poster
  • Formats acceptés : JPG, PNG
  • L'opacité est ajustable avec le curseur "Alpha"

LOGOS PARTENAIRES
  • Dossier : Indiquez un dossier contenant les logos (PNG/JPG)
  • SVG : Utilisez un fichier SVG pré-composé pour un contrôle précis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                               4. FONCTIONNALITÉS AVANCÉES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ICÔNES AUTOMATIQUES
  • "au chapeau" : Cochez pour remplacer par l'icône 🎩
  • "0€" : Cochez pour remplacer par l'icône gratuit

ABRÉVIATIONS
  • Activez les abréviations pour réduire la longueur du texte
  • Exemples : "Saint-" → "St-", "Association" → "Asso."
  • Permet d'augmenter la taille de police automatique

BOÎTE CUCARACHA
  • Zone de texte libre en bas du poster
  • Peut contenir du texte ou une image

STORIES INSTAGRAM
  • Génère des images 1080x1920 pour chaque page
  • Personnalisez la police, couleur et fond

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                5. MODE DEBUG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Activez le "Mode Debug" pour :
  • Sauvegarder tous les fichiers intermédiaires (HTML, config)
  • Horodater les fichiers de sortie
  • Faciliter le diagnostic en cas de problème
  • Exporter/importer des configurations

Boutons disponibles en mode debug :
  • "📂 Importer config" : Charger une configuration précédente
  • "🔄 Reset config" : Revenir aux paramètres par défaut

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              6. FICHIERS DE SORTIE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Le Bidul génère plusieurs fichiers :

  bidul.pdf          Le document PDF principal (poster multi-pages)
  bidul/             Dossier contenant les fichiers SVG par page
  stories/           Images PNG pour Instagram Stories

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              7. RACCOURCIS & ASTUCES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • Glisser-déposer fonctionne pour tous les champs de fichier
  • Le bouton "⏹ Stop" permet d'interrompre le traitement
  • Utilisez la molette pour faire défiler l'interface
  • Les infobulles apparaissent au survol des options

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                  BESOIN D'AIDE ?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📧 Consultez le dépôt GitHub pour signaler un bug ou poser une question
  🔗 https://github.com/lebidul/bidul.biduleur

"""

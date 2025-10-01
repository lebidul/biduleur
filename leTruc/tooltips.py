# leTruc/tooltips.py
import tkinter as tk


class Tooltip:
    """
    Crée un tooltip (infobulle) qui apparaît lorsqu'on survole un widget.
    """

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.id = None
        self.x = self.y = 0

        # Lier les événements d'entrée et de sortie de la souris au widget
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        """Planifie l'affichage du tooltip après un court délai."""
        self.schedule()

    def leave(self, event=None):
        """Annule l'affichage et cache le tooltip."""
        self.unschedule()
        self.hide_tooltip()

    def schedule(self):
        """Planifie l'affichage du tooltip après 500ms."""
        self.unschedule()
        self.id = self.widget.after(500, self.show_tooltip)

    def unschedule(self):
        """Annule une planification d'affichage."""
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def show_tooltip(self, event=None):
        """Crée et affiche la fenêtre du tooltip."""
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        # Créer une fenêtre Toplevel (petite fenêtre sans bordures)
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        # Ajouter un label avec le texte d'aide
        label = tk.Label(tw, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         wraplength=300,  # Le texte passera à la ligne si trop long
                         font=("Arial", 10, "normal"))
        label.pack(ipadx=5, ipady=5)

    def hide_tooltip(self):
        """Détruit la fenêtre du tooltip si elle existe."""
        tw = self.tooltip_window
        self.tooltip_window = None
        if tw:
            tw.destroy()
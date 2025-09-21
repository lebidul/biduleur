# leTruc/victory.py
import tkinter as tk
import random
from PIL import Image, ImageTk
import sys

try:
    from ._helpers import get_resource_path
except ImportError:
    from _helpers import get_resource_path


class VictoryWindow(tk.Toplevel):
    def __init__(self, parent, summary_text: str):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()

        # --- Vos paramètres personnalisés ---
        self.background_color = "#d938d3"
        width, height = 864, 648
        card_thumb_size = (198, 279)

        self.geometry(f"{width}x{height}")
        self.title("Génération Terminée !")

        # --- AJUSTEMENT : Icône de la fenêtre ---
        try:
            icon_path = get_resource_path("leTruc/assets/LesArtsServices.ico")
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"[WARN] Impossible de charger l'icône : {e}")

        # 1. On s'assure que la géométrie du parent est à jour
        parent.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        # 2. On calcule la position finale
        # final_x = parent_x + parent_w - width - 10
        final_x = parent_x + parent_w - width + 200
        final_y = parent_y + (parent_h - height) // 2

        # 3. On applique la taille ET la position en UN SEUL appel
        self.geometry(f"{width}x{height}+{final_x}+{final_y}")

        self.canvas = tk.Canvas(self, bg=self.background_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.width = width
        self.height = height

        # Chargement des images (inchangé)
        self.card_images = []
        card_paths = ["leTruc/assets/card1.png", "leTruc/assets/card2.png", "leTruc/assets/card3.png"]
        for path in card_paths:
            try:
                card_path = get_resource_path(path)
                with Image.open(card_path) as img:
                    img.thumbnail(card_thumb_size)
                    self.card_images.append(ImageTk.PhotoImage(img))
            except Exception as e:
                print(f"[WARN] Impossible de charger l'image de carte {path}: {e}")

        self.cards = []
        if self.card_images:
            for _ in range(25):
                self._create_card()

        # On calcule la largeur désirée en pixels (80% de la largeur de la fenêtre)
        summary_widget_width = int(self.width * 0.8)

        # On crée le widget Text. Son parent est le canvas.
        summary_widget = tk.Text(
            self.canvas,
            height=12,  # Hauteur en nombre de lignes de texte
            padx=15,
            pady=15,
            font=("Segoe UI", 9) if sys.platform == "win32" else ("Arial", 10),
            bg="#F0F0F0",  # Fond gris clair, comme les boîtes de dialogue système
            fg="black",  # Texte en noir
            relief="solid",
            borderwidth=1,
            wrap="word"  # Le texte ira à la ligne automatiquement
        )

        # On insère le message de résumé (passé en argument) dans le widget
        summary_widget.insert(tk.END, summary_text)

        # On crée le bouton "Fermer"
        close_button = tk.Button(summary_widget, text="Fermer", command=self.destroy)

        # On insère une nouvelle ligne, puis le bouton, dans le widget Text
        summary_widget.insert(tk.END, '\n')
        summary_widget.window_create(tk.END, window=close_button, padx=10, pady=10)

        # On rend le widget Text non-éditable par l'utilisateur
        summary_widget.config(state=tk.DISABLED)

        # On place le widget Text au centre du canvas en lui imposant sa largeur
        self.canvas.create_window(
            self.width // 2,
            self.height // 2,
            window=summary_widget,
            anchor="center",
            width=summary_widget_width
        )

        self._animate()

    def _create_card(self):
        """Crée une seule carte."""
        if not self.card_images: return
        chosen_image = random.choice(self.card_images)

        # --- AJUSTEMENT : Position de départ pour la "pluie" ---
        start_x = random.uniform(0, self.width)
        start_y = random.uniform(-500, -450)  # Commence bien au-dessus de l'écran

        card_id = self.canvas.create_image(start_x, start_y, image=chosen_image, anchor="nw")

        card_obj = {
            'id': card_id,
            'x': start_x,
            'y': start_y,
            # --- AJUSTEMENT : Vitesse réduite de 15% ---
            'vx': random.uniform(-2, 2) * 0.85,
            'vy': random.uniform(1, 4) * 0.85,  # Commence en tombant
            'gravity': 0.15 * 0.85
        }
        self.cards.append(card_obj)

    def _animate(self):
        """Boucle principale de l'animation."""
        for card in self.cards:
            card['vy'] += card['gravity']
            card['x'] += card['vx']
            card['y'] += card['vy']

            # --- AJUSTEMENT : Timing de réapparition ---
            # Si le HAUT de la carte dépasse le bas, on la réinitialise
            if card['y'] > self.height:
                self._reset_card(card)

            self.canvas.moveto(card['id'], int(card['x']), int(card['y']))
        self.after(16, self._animate)

    def _reset_card(self, card):
        """Réinitialise une carte pour la faire retomber."""
        card['y'] = random.uniform(-250, -100)
        card['x'] = random.uniform(0, self.width)
        card['vx'] = random.uniform(-2, 2) * 0.85
        card['vy'] = random.uniform(1, 4) * 0.85
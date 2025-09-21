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

        self.background_color = "#d938d3"

        width, height = 864, 648
        self.geometry(f"{width}x{height}")
        self.title("Génération Terminée !")

        parent.update_idletasks()
        parent_x, parent_y = parent.winfo_x(), parent.winfo_y()
        parent_w, parent_h = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{parent_x + (parent_w - width) // 2}+{parent_y + (parent_h - height) // 2}")

        self.canvas = tk.Canvas(self, bg=self.background_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.width = width
        self.height = height

        # ==================== GESTION DES IMAGES MULTIPLES ====================
        self.card_images = []
        # Définissez ici les chemins vers vos 3 images de cartes
        card_paths = [
            "leTruc/assets/card1.png",
            "leTruc/assets/card2.png",
            "leTruc/assets/card3.png"
        ]

        for path in card_paths:
            try:
                card_path = get_resource_path(path)
                with Image.open(card_path) as img:
                    img.thumbnail((198, 279))
                    self.card_images.append(ImageTk.PhotoImage(img))
            except Exception as e:
                print(f"[WARN] Impossible de charger l'image de carte {path}: {e}")
        # ====================================================================

        self.cards = []
        if self.card_images:
            for _ in range(25):
                self._create_card()

        # --- AJUSTEMENT : Widget de résumé plus large ---
        summary_widget_width = int(self.width * 0.8)  # 80% de la largeur de la fenêtre

        summary_widget = tk.Text(
            self.canvas,
            width=1,  # La largeur est gérée par create_window
            height=12,
            padx=15, pady=15,
            font=("Segoe UI", 9) if sys.platform == "win32" else ("Arial", 10),
            bg="#F0F0F0", fg="black", relief="solid", borderwidth=1, wrap="word"
        )
        summary_widget.insert(tk.END, summary_text)
        summary_widget.config(state=tk.DISABLED)

        self.canvas.create_window(
            self.width // 2, self.height // 2,
            window=summary_widget,
            anchor="center",
            width=summary_widget_width  # On impose la largeur ici
        )

        self._animate()

    def _create_card(self):
        """Crée une seule carte en choisissant une image au hasard."""
        if not self.card_images: return

        # On choisit une image au hasard dans la liste
        chosen_image = random.choice(self.card_images)

        card_id = self.canvas.create_image(-100, -100, image=chosen_image, anchor="nw")
        card_obj = {
            'id': card_id,
            'x': self.width / 2,
            'y': self.height,
            'vx': random.uniform(-4, 4),
            'vy': random.uniform(-10, -5),
            'gravity': 0.15,
            'image': chosen_image  # On garde une référence à l'image utilisée
        }
        self.cards.append(card_obj)

    def _animate(self):
        """Boucle principale de l'animation."""
        for card in self.cards:
            card['vy'] += card['gravity']
            card['x'] += card['vx']
            card['y'] += card['vy']

            # --- AJUSTEMENT : Timing de réapparition ---
            # Si le HAUT de la carte (card['y']) dépasse le bas de la fenêtre
            if card['y'] > self.height:
                card['y'] = -100  # Réapparaît en haut (hors écran)
                card['x'] = random.uniform(0, self.width - card['image'].width())
                card['vx'] = random.uniform(-3, 3)
                card['vy'] = random.uniform(-3, 1)

            self.canvas.moveto(card['id'], int(card['x']), int(card['y']))

        self.after(16, self._animate)
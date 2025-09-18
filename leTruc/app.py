import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import os

# Importe les modules frères
from . import widgets
from . import callbacks

# Importe les helpers globaux
from ._helpers import _load_cfg_defaults, run_pipeline


class Application(tk.Tk):
    """
    Classe principale de l'interface graphique.

    Elle initialise la fenêtre, gère l'état de l'interface (variables),
    et orchestre la création des widgets et l'assignation des callbacks.
    """

    def __init__(self):
        super().__init__()

        # --- 1. Configuration de la fenêtre principale ---
        self.title("Le Truc – Pipeline XLS/CSV → PDF")
        self.geometry("900x900")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # 2. INITIALISER D'ABORD les données et les variables
        self.cfg_defaults = _load_cfg_defaults()
        self._initialize_variables()
        self.result_queue = queue.Queue()

        # 3. ENSUITE, CRÉER les conteneurs principaux de l'interface
        self._create_scrollable_area()
        self._create_action_bar()
        self._create_status_bar()

        # 4. ENFIN, remplir les conteneurs avec les widgets et leurs callbacks
        widgets.create_all(self)
        callbacks.assign_all(self)

        # Lier la molette de la souris pour le scroll
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", lambda e: self._on_mousewheel(type('obj', (object,), {'delta': 120})()))
        self.bind_all("<Button-5>", lambda e: self._on_mousewheel(type('obj', (object,), {'delta': -120})()))

    def _initialize_variables(self):
        """
        Initialise toutes les variables Tkinter (StringVar, BooleanVar, etc.)
        comme attributs de l'instance. Ces variables lient l'état du backend
        de l'application aux widgets de l'interface.
        """
        # --- Variables pour les chemins de fichiers et dossiers ---
        self.input_var = tk.StringVar()
        self.ours_png_var = tk.StringVar(value=self.cfg_defaults.get("ours_background_png", ""))
        self.logos_var = tk.StringVar(value=self.cfg_defaults.get("logos_dir", ""))
        self.cover_var = tk.StringVar(value=self.cfg_defaults.get("cover", ""))
        self.html_var = tk.StringVar()
        self.agenda_var = tk.StringVar()
        self.pdf_var = tk.StringVar()
        self.svg_var = tk.StringVar()

        # --- Variables pour les options de couverture ---
        self.generate_cover_var = tk.BooleanVar(value=not self.cfg_defaults.get("skip_cover", False))
        self.auteur_var = tk.StringVar(value=self.cfg_defaults.get("auteur_couv", ""))
        self.auteur_url_var = tk.StringVar(value=self.cfg_defaults.get("auteur_couv_url", ""))

        # --- Variables pour la mise en page ---
        self.margin_var = tk.StringVar(value=str(self.cfg_defaults.get("page_margin_mm", "1.0")))
        self.logos_layout_var = tk.StringVar(value="colonnes")
        self.logos_padding_var = tk.StringVar(value="1.0")

        # --- Variables pour les séparateurs de dates ---
        self.date_separator_var = tk.StringVar(value=self.cfg_defaults.get("date_separator_type", "ligne"))
        self.date_spacing_var = tk.StringVar(value=self.cfg_defaults.get("date_spacing", "4"))
        self.date_box_back_color_var = tk.StringVar(value="#FFFFFF")

        # --- Variables pour le poster ---
        self.poster_title_var = tk.StringVar(value=self.cfg_defaults.get("poster_title", ""))
        self.poster_design_var = tk.IntVar(value=self.cfg_defaults.get("poster_design", 0))
        self.safety_factor_var = tk.StringVar(value=str(self.cfg_defaults.get("font_size_safety_factor", "0.98")))
        self.alpha_var = tk.DoubleVar(value=self.cfg_defaults.get("background_alpha", 0.85))

        # --- Variables pour la boîte Cucaracha ---
        self.cucaracha_type_var = tk.StringVar(value=self.cfg_defaults.get("cucaracha_type", "none"))
        self.cucaracha_value_var = tk.StringVar(value=self.cfg_defaults.get("cucaracha_value", ""))
        self.cucaracha_font_var = tk.StringVar(value=self.cfg_defaults.get("cucaracha_text_font", "Arial"))

        # --- Variables de sortie et de statut ---
        self.generate_svg_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Prêt.")

    def _create_scrollable_area(self):
        """Crée la structure Canvas/Scrollbar pour rendre le contenu scrollable."""
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.canvas_frame_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _create_action_bar(self):
        """Crée la barre d'action fixe en bas (bouton, progress bar)."""
        action_frame = ttk.Frame(self, padding="10")
        action_frame.grid(row=1, column=0, sticky="ew")
        action_frame.columnconfigure(0, weight=1)

        self.progress_bar = ttk.Progressbar(action_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

        # Le parent du bouton est 'action_frame', pas 'self'.
        self.run_button = tk.Button(action_frame, text="Lancer la Génération", bg="#4CAF50", fg="white", font=("Arial", 12, "bold"))

        self.run_button.pack(pady=10, ipady=5)

    def _create_status_bar(self):
        """Crée la barre de statut fixe tout en bas."""
        # Le parent de la barre de statut est 'self' (la fenêtre racine),
        # et elle doit être placée avec .grid() comme ses frères et sœurs.
        # Nous allons créer le widget et le placer directement ici.
        status_bar = tk.Label(self, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=10, pady=5, font=("Arial", 10))
        status_bar.grid(row=2, column=0, sticky="ew")

    # --- Méthodes de Callback pour l'exécution ---

    def _on_run(self):
        """
        Callback pour le bouton "Lancer". Valide les entrées et démarre
        le traitement dans un thread séparé pour ne pas geler l'interface.
        """
        if not self.input_var.get().strip():
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d’entrée.")
            return

        try:
            # On valide toutes les entrées numériques en une seule fois
            validated_args = {
                'margin_val': float(self.margin_var.get().strip().replace(',', '.')),
                'safety_factor_val': float(self.safety_factor_var.get().strip().replace(',', '.')),
                'date_spacing_val': float(self.date_spacing_var.get().strip().replace(',', '.')),
                'logos_padding_val': float(self.logos_padding_var.get().strip().replace(',', '.'))
            }
        except ValueError:
            messagebox.showerror("Erreur", "Les champs numériques (marges, espacement, etc.) doivent être valides.")
            return

        validated_args['poster_title_val'] = self.poster_title_var.get().strip()
        if not validated_args['poster_title_val']:
            messagebox.showerror("Erreur", "Le titre du poster est obligatoire.")
            return

        validated_args['cuca_value_val'] = self.cucaracha_value_var.get().strip()

        self.status_var.set("Traitement en cours…")
        self.progress_bar.start()
        self.run_button.config(state=tk.DISABLED)

        # Créer et démarrer le thread de travail en lui passant le dictionnaire des arguments validés
        thread = threading.Thread(target=self._run_pipeline_in_thread, args=(validated_args,))
        thread.daemon = True
        thread.start()

        self.after(100, self._check_thread_for_results)

    def _run_pipeline_in_thread(self, validated_args):
        """
        Wrapper qui exécute la fonction de traitement lourde 'run_pipeline'.
        Cette méthode s'exécute dans un thread séparé.
        """
        # On utilise le helper _helpers.run_pipeline qui a été importé
        from ._helpers import run_pipeline

        ok, msg = run_pipeline(
            # On passe les arguments en utilisant les clés du dictionnaire
            # pour éviter toute erreur d'ordre.
            input_file=self.input_var.get().strip(),
            generate_cover=self.generate_cover_var.get(),
            cover_image=self.cover_var.get().strip(),
            ours_background_png=self.ours_png_var.get().strip(),
            logos_dir=self.logos_var.get().strip(),
            logos_layout=self.logos_layout_var.get(),
            logos_padding_mm=validated_args['logos_padding_val'],
            out_html=self.html_var.get().strip(),
            out_agenda_html=self.agenda_var.get().strip(),
            out_pdf=self.pdf_var.get().strip(),
            auteur_couv=self.auteur_var.get().strip(),
            auteur_couv_url=self.auteur_url_var.get().strip(),
            page_margin_mm=validated_args['margin_val'],
            generate_svg=self.generate_svg_var.get(),
            out_svg=self.svg_var.get().strip(),
            date_separator_type=self.date_separator_var.get(),
            date_spacing=validated_args['date_spacing_val'],
            poster_design=self.poster_design_var.get(),
            font_size_safety_factor=validated_args['safety_factor_val'],
            background_alpha=self.alpha_var.get(),
            poster_title=validated_args['poster_title_val'],
            cucaracha_type=self.cucaracha_type_var.get(),
            cucaracha_value=validated_args['cuca_value_val'],
            cucaracha_text_font=self.cucaracha_font_var.get(),
            date_box_back_color=self.date_box_back_color_var.get()
        )
        self.result_queue.put((ok, msg))

    def _check_thread_for_results(self):
        """
        Vérifie la queue pour le résultat du thread. Si le thread n'a pas fini,
        se replanifie pour une vérification ultérieure.
        """
        try:
            ok, msg = self.result_queue.get(block=False)

            self.progress_bar.stop()
            self.run_button.config(state=tk.NORMAL)

            if ok:
                messagebox.showinfo("Génération Terminée", msg)
                self.status_var.set("Terminé avec succès.")
                pdf_path = self.pdf_var.get().strip()
                if pdf_path and os.path.exists(pdf_path):
                    if messagebox.askyesno("Ouvrir le fichier ?", "Voulez-vous ouvrir le PDF généré maintenant ?"):
                        callbacks.open_file(pdf_path)  # Utilise le helper
            else:
                messagebox.showerror("Erreur", msg)
                self.status_var.set("Échec.")

        except queue.Empty:
            self.after(100, self._check_thread_for_results)

    # --- Méthodes pour la gestion du Canvas (Callbacks internes) ---

    def _on_frame_configure(self, event):
        """Met à jour la région de scroll quand la taille du contenu change."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Ajuste la largeur du contenu à la largeur de la fenêtre."""
        self.canvas.itemconfig(self.canvas_frame_id, width=event.width)

    def _on_mousewheel(self, event):
        """Permet de scroller avec la molette de la souris."""
        scroll_amount = -1 * (event.delta // 120)
        self.canvas.yview_scroll(scroll_amount, "units")
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import os

# Importe les modules frères
from . import widgets
from . import callbacks

# Importe les helpers globaux
from ._helpers import _load_cfg_defaults, get_resource_path
from .victory import VictoryWindow


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

        try:
            icon_path = get_resource_path("leTruc/assets/LesArtsServices.ico")
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"[WARN] Impossible de charger l'icône de l'application : {e}")

        # 2. INITIALISER D'ABORD les données et les variables
        self.cfg_defaults = _load_cfg_defaults()
        self._initialize_variables()
        self.result_queue = queue.Queue()

        # 3. ENSUITE, CRÉER les conteneurs principaux de l'interface
        self._create_scrollable_area()
        self._create_action_and_status_bar()
        self.total_progress_steps = 1

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
        self.generate_stories_var = tk.BooleanVar(value=self.cfg_defaults.get("stories_enabled", True))
        self.stories_output_var = tk.StringVar()

        # --- Variables pour la section Stories ---
        self.stories_font_name_var = tk.StringVar(value=self.cfg_defaults.get("stories_font_name", "Arial"))
        self.stories_font_size_var = tk.StringVar(value=str(self.cfg_defaults.get("stories_font_size", "45")))
        self.stories_font_color_var = tk.StringVar(value=self.cfg_defaults.get("stories_font_color", "#000000"))
        self.stories_bg_type_var = tk.StringVar(value=self.cfg_defaults.get("stories_bg_type", "color"))
        self.stories_bg_color_var = tk.StringVar(value=self.cfg_defaults.get("stories_bg_color", "#FFFFFF"))
        self.stories_bg_image_var = tk.StringVar(value=self.cfg_defaults.get("stories_bg_image", ""))
        self.stories_alpha_var = tk.DoubleVar(value=self.cfg_defaults.get("stories_alpha", 0.5))

        # --- Variables pour les options de couverture ---
        self.generate_cover_var = tk.BooleanVar(value=not self.cfg_defaults.get("skip_cover", False))
        self.auteur_var = tk.StringVar(value=self.cfg_defaults.get("auteur_couv", ""))
        self.auteur_url_var = tk.StringVar(value=self.cfg_defaults.get("auteur_couv_url", ""))

        # --- Variables pour la mise en page ---
        self.margin_var = tk.StringVar(value=str(self.cfg_defaults.get("page_margin_mm", "1.0")))
        self.logos_layout_var = tk.StringVar(value="colonnes")
        self.logos_padding_var = tk.StringVar(value="1.0")
        self.font_size_mode_var = tk.StringVar(value=self.cfg_defaults.get("font_size_mode", "auto"))
        self.font_size_forced_var = tk.StringVar(value=str(self.cfg_defaults.get("font_size_forced", "10.0")))

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
        self.cucaracha_font_size_var = tk.StringVar(value=str(self.cfg_defaults.get("cucaracha_text_font_size", "8")))
        self.cucaracha_text_widget = None
        self.cucaracha_frame = None

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

    def _create_action_and_status_bar(self):
        """Crée la barre d'action fixe en bas, incluant le label de statut."""
        action_frame = ttk.Frame(self, padding="10")
        action_frame.grid(row=1, column=0, sticky="ew")
        action_frame.columnconfigure(0, weight=1)

        # 1. Créer le label de statut et le placer en haut du cadre
        self.status_label = tk.Label(action_frame, textvariable=self.status_var, font=("Arial", 10))
        self.status_label.pack(fill=tk.X, padx=5, pady=(0, 5))

        # 2. Changer le mode en 'determinate'
        self.progress_bar = ttk.Progressbar(action_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

        # 3. Le bouton "Lancer" vient en dernier
        self.run_button = tk.Button(action_frame, text="Lancer la Génération", bg="#4CAF50", fg="white", font=("Arial", 12, "bold"))
        self.run_button.pack(pady=10, ipady=5)

    # --- Méthodes de Callback pour l'exécution ---

    def _on_run(self):
        """
        Callback pour le bouton "Lancer". Valide les entrées et démarre
        le traitement dans un thread séparé pour ne pas geler l'interface.
        """
        if not self.input_var.get().strip():
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d’entrée.")
            return

        # On initialise les arguments validés avec les valeurs par défaut
        validated_args = {
            'cuca_value_val': "",
            'cuca_font_size_val': 8, # Valeur par défaut sûre
        }

        # On récupère la valeur de la Cucaracha depuis le bon widget
        cucaracha_type = self.cucaracha_type_var.get()
        if cucaracha_type == "text":
            validated_args['cuca_value_val'] = self.cucaracha_text_widget.get("1.0", tk.END).strip()
        elif cucaracha_type == "image":
            validated_args['cuca_value_val'] = self.cucaracha_value_var.get().strip()
        # Si c'est "none", la valeur reste une chaîne vide, ce qui est correct.

        try:
            validated_args.update({
                'margin_val': float(self.margin_var.get().strip().replace(',', '.')),
                'safety_factor_val': float(self.safety_factor_var.get().strip().replace(',', '.')),
                'date_spacing_val': float(self.date_spacing_var.get().strip().replace(',', '.')),
                'logos_padding_val': float(self.logos_padding_var.get().strip().replace(',', '.')),
                'font_size_forced_val': float(self.font_size_forced_var.get().strip().replace(',', '.')),
                'stories_font_size_val': int(self.stories_font_size_var.get().strip()),
                'cuca_font_size_val': int(self.cucaracha_font_size_var.get().strip())
            })
        except ValueError:
            messagebox.showerror("Erreur", "Les champs numériques (marges, espacement, etc.) doivent être valides.")
            return

        validated_args['poster_title_val'] = self.poster_title_var.get().strip()
        if not validated_args['poster_title_val']:
            messagebox.showerror("Erreur", "Le titre du poster est obligatoire.")
            return

        validated_args['stories_font_size_val'] = int(self.stories_font_size_var.get().strip())

        self.status_var.set("Traitement en cours…")
        self.run_button.config(state=tk.DISABLED)

        # Créer et démarrer le thread de travail en lui passant le dictionnaire des arguments validés
        thread = threading.Thread(target=self._run_pipeline_in_thread, args=(validated_args,))
        thread.daemon = True
        thread.start()

        # On réinitialise la barre de progression
        self.progress_bar.config(value=0)
        self.status_var.set("Démarrage du processus...")

        self.after(100, self._check_thread_for_results)

    def _run_pipeline_in_thread(self, validated_args):
        """
        Wrapper qui exécute la fonction de traitement lourde 'run_pipeline'.
        Cette méthode s'exécute dans un thread séparé.
        """
        # On utilise le helper _helpers.run_pipeline qui a été importé
        from ._helpers import run_pipeline

        run_pipeline(
            # On passe les arguments en utilisant les clés du dictionnaire
            # pour éviter toute erreur d'ordre.
            self.result_queue,
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
            font_size_mode=self.font_size_mode_var.get(),
            font_size_forced=validated_args['font_size_forced_val'],
            generate_svg=self.generate_svg_var.get(),
            out_svg=self.svg_var.get().strip(),
            generate_stories=self.generate_stories_var.get(),
            stories_output_dir=self.stories_output_var.get().strip(),
            date_separator_type=self.date_separator_var.get(),
            date_spacing=validated_args['date_spacing_val'],
            poster_design=self.poster_design_var.get(),
            font_size_safety_factor=validated_args['safety_factor_val'],
            background_alpha=self.alpha_var.get(),
            poster_title=validated_args['poster_title_val'],
            cucaracha_type=self.cucaracha_type_var.get(),
            cucaracha_value=validated_args['cuca_value_val'],
            cucaracha_text_font=self.cucaracha_font_var.get(),
            cucaracha_font_size=validated_args['cuca_font_size_val'],
            date_box_back_color=self.date_box_back_color_var.get(),
            stories_font_name=self.stories_font_name_var.get(),
            stories_font_size=validated_args['stories_font_size_val'],
            stories_font_color=self.stories_font_color_var.get(),
            stories_bg_type=self.stories_bg_type_var.get(),
            stories_bg_color=self.stories_bg_color_var.get(),
            stories_bg_image=self.stories_bg_image_var.get().strip(),
            stories_alpha=self.stories_alpha_var.get()
        )

    def _check_thread_for_results(self):
        """
        Vérifie la queue pour les messages du thread (statut ou final)
        et met à jour l'interface.
        """
        try:
            while not self.result_queue.empty():
                message = self.result_queue.get(block=False)
                msg_type = message[0]

                if msg_type == 'start':
                    self.total_progress_steps = message[1]
                    self.progress_bar.config(maximum=self.total_progress_steps)

                elif msg_type == 'status':
                    status_text = message[1]
                    current_step = message[2]
                    self.status_var.set(status_text)
                    self.progress_bar.config(value=current_step)

                elif msg_type == 'final':
                    ok, msg = message[1], message[2]

                    self.progress_bar.config(value=self.total_progress_steps)  # Remplir à 100%
                    self.run_button.config(state=tk.NORMAL)

                    if ok:
                        VictoryWindow(self, summary_text=msg)
                        self.status_var.set("Terminé avec succès.")

                        # ... (demande pour ouvrir le PDF, inchangé)
                    else:
                        messagebox.showerror("Erreur", msg)
                        self.status_var.set("Échec.")

                    # On a traité le message final, on peut arrêter de vérifier
                    return

        except queue.Empty:
            # La queue est vide, ce n'est pas une erreur.
            pass
        except Exception as e:
            # Gérer le cas où le message n'a pas le bon format
            print(f"Erreur en lisant la queue : {e}")

        # On se replanifie pour une vérification ultérieure si le thread est toujours actif
        # Note : On ne peut pas vérifier `thread.is_alive()` directement ici car la référence est perdue.
        # On continue de vérifier tant qu'un message 'final' n'est pas arrivé.
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
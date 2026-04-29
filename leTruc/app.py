# leTruc/app.py
# MODIFICATIONS : Ajout boutons import/reset config dans mode debug
# v1.4.2 : Ajout système d'abréviations
# v1.4.3 : Ajout bouton Stop pour interrompre le workflow
# v1.4.5 : Ajout menu Aide (Crédits, Release Notes, Guide utilisateur)

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import os
from tkinterdnd2 import TkinterDnD, DND_FILES

# Importe les modules frères
from . import widgets
from . import callbacks
from . import menu

# Importe les helpers globaux
from ._helpers import _load_cfg_defaults, get_resource_path
from .victory import VictoryWindow

try:
    from ._version import __version__
except ImportError:
    __version__ = "dev"


class Application(TkinterDnD.Tk):
    """
    Classe principale de l'interface graphique.
    """

    def __init__(self):
        super().__init__()

        # --- 1. Configuration de la fenêtre principale ---
        self.title(f"Le Truc v{__version__} – Crée ton Bidul à la maison - .xls/.csv → .pdf")
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
        self.stop_event = threading.Event()  # v1.4.3 : Event pour arrêt du pipeline

        # 3. ENSUITE, CRÉER les conteneurs principaux de l'interface
        self._create_scrollable_area()
        self._create_action_and_status_bar()
        self.total_progress_steps = 1

        # 4. ENFIN, remplir les conteneurs avec les widgets et leurs callbacks
        widgets.create_all(self)
        callbacks.assign_all(self)

        # 5. Créer la barre de menu (v1.4.5)
        menu.create_menu_bar(self)

        # Lier la molette de la souris pour le scroll
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", lambda e: self._on_mousewheel(type('obj', (object,), {'delta': 120})()))
        self.bind_all("<Button-5>", lambda e: self._on_mousewheel(type('obj', (object,), {'delta': -120})()))

    def _initialize_variables(self):
        """
        Initialise toutes les variables Tkinter (StringVar, BooleanVar, etc.)
        """
        # --- Variables pour les chemins de fichiers et dossiers ---
        self.input_var = tk.StringVar()
        self.ours_png_var = tk.StringVar(value=self.cfg_defaults.get("ours_background_png", ""))
        self.ours_layout_var = tk.StringVar(value="svg")
        self.ours_svg_var = tk.StringVar(value="misenpageur/assets/ours/ours.svg")
        self.chapeau_icon_var = tk.BooleanVar(value=False)  # Remplacer "au chapeau" par icône
        self.free_icon_var = tk.BooleanVar(value=False)  # Remplacer "0€" par icône
        self.ours_type_var = tk.StringVar(value="svg")
        self.ours_svg_var = tk.StringVar(value="misenpageur/assets/ours/ours.svg")
        self.logos_var = tk.StringVar(value=self.cfg_defaults.get("logos_dir", ""))
        self.cover_var = tk.StringVar()
        self.generate_html_var = tk.BooleanVar(value=False)
        self.html_var = tk.StringVar()
        self.agenda_var = tk.StringVar()
        self.pdf_var = tk.StringVar()
        self.svg_output_var = tk.StringVar()
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
        self.logos_layout_var = tk.StringVar(value="svg")
        self.logos_svg_var = tk.StringVar(value="misenpageur/assets/logos.svg")
        self.logos_padding_var = tk.StringVar(value="1.0")
        self.body_font_name_var = tk.StringVar(value=self.cfg_defaults.get("body_font_name", "Arial Narrow"))
        self.font_size_mode_var = tk.StringVar(value=self.cfg_defaults.get("font_size_mode", "auto"))
        self.font_size_forced_var = tk.StringVar(value=str(self.cfg_defaults.get("font_size_forced", "10.0")))

        # --- Variables pour la configuration des dates ---
        self.date_separator_var = tk.StringVar(value=self.cfg_defaults.get("date_separator_type", "ligne"))
        self.date_spacing_var = tk.StringVar(value=self.cfg_defaults.get("date_spacing", "4"))
        self.date_box_back_color_var = tk.StringVar(value="#FFFFFF")
        self.date_font_name_var = tk.StringVar(value=self.cfg_defaults.get("date_font_name", "(Identique au corps)"))
        self.date_align_var = tk.StringVar(value=self.cfg_defaults.get("date_alignment", "left"))
        self.date_bold_var = tk.BooleanVar(value=self.cfg_defaults.get("date_bold", False))
        self.date_italic_var = tk.BooleanVar(value=self.cfg_defaults.get("date_italic", False))
        self.date_color_var = tk.StringVar(value=self.cfg_defaults.get("date_color", "#000000"))
        self.bidul_label_enabled_var = tk.BooleanVar(value=self.cfg_defaults.get("bidul_label_enabled", False))
        self.bidul_label_color_var = tk.StringVar(value=self.cfg_defaults.get("bidul_label_color", "#000000"))
        self.festival_subgroup_enabled_var = tk.BooleanVar(value=self.cfg_defaults.get("festival_subgroup_enabled", False))

        # --- Variables pour le poster ---
        self.poster_title_var = tk.StringVar(value=self.cfg_defaults.get("poster_title", ""))
        self.poster_design_var = tk.IntVar(value=self.cfg_defaults.get("poster_design", 0))
        self.safety_factor_var = tk.StringVar(value=str(self.cfg_defaults.get("font_size_safety_factor", "1.0")))
        self.alpha_var = tk.DoubleVar(value=self.cfg_defaults.get("background_alpha", 0.85))

        # --- Variables pour la boîte Cucaracha ---
        self.cucaracha_type_var = tk.StringVar(value=self.cfg_defaults.get("cucaracha_type", "none"))
        self.cucaracha_value_var = tk.StringVar(value=self.cfg_defaults.get("cucaracha_value", ""))
        self.cucaracha_font_var = tk.StringVar(value=self.cfg_defaults.get("cucaracha_text_font", "Arial"))
        self.cucaracha_font_size_var = tk.StringVar(value=str(self.cfg_defaults.get("cucaracha_text_font_size", "8")))
        self.cucaracha_text_widget = None
        self.cucaracha_frame = None
        self.drop_zone_label = None
        self.cover_drop_zone_label = None

        # --- Variables de sortie et de statut ---
        self.generate_svg_var = tk.BooleanVar(value=True)
        self.split_pdf_var = tk.BooleanVar(value=self.cfg_defaults.get("split_pdf", False))
        self.print_pdf_var = tk.BooleanVar(value=self.cfg_defaults.get("print_pdf", False))
        self.logos_print_svg_var = tk.StringVar(value="misenpageur/assets/logos.impression.svg")
        self.status_var = tk.StringVar(value="Prêt.")

        self.debug_mode_var = tk.BooleanVar(value=self.cfg_defaults.get("debug_mode", False))

        # --- Images inline ---
        self.inline_images_enabled_var = tk.BooleanVar(value=self.cfg_defaults.get("inline_images_enabled", False))
        self.inline_images_dir_var = tk.StringVar(value=self.cfg_defaults.get("inline_images_dir", ""))
        self.inline_images_scale_var = tk.StringVar(value=str(self.cfg_defaults.get("inline_images_scale", "0.85")))
        self.inline_images_margin_var = tk.StringVar(value=str(self.cfg_defaults.get("inline_images_margin", "1.0")))
        self.inline_images_auto_scale_var = tk.BooleanVar(value=self.cfg_defaults.get("inline_images_auto_scale", False))

        # --- Fonctions expérimentales Teriaki ---
        self.date_grouping_enabled_var = tk.BooleanVar(value=self.cfg_defaults.get("date_grouping_enabled", False))
        self.festival_in_date_header_var = tk.BooleanVar(value=self.cfg_defaults.get("festival_in_date_header", False))

        # --- Abréviations ---
        self.abbreviations_data = self.cfg_defaults.get("abbreviations", {})
        self.abbreviation_vars = {}  # Créées dans widgets.py

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

        # 1. Label de statut
        self.status_label = tk.Label(action_frame, textvariable=self.status_var, font=("Arial", 10))
        self.status_label.pack(fill=tk.X, padx=5, pady=(0, 5))

        # 2. Barre de progression
        self.progress_bar = ttk.Progressbar(action_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

        # 3. Cadre pour le bouton principal et le mode debug
        button_frame = ttk.Frame(action_frame)
        button_frame.pack(fill=tk.X, padx=5)

        # Bouton principal
        self.run_button = tk.Button(button_frame, text="🚀 Créer le Bidul !", font=("Arial", 14, "bold"), bg="#4CAF50",
                                    fg="white")
        self.run_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))

        # v1.4.3 : Bouton Stop (caché par défaut)
        self.stop_button = tk.Button(button_frame, text="⏹ Stop", font=("Arial", 12, "bold"), bg="#f44336",
                                     fg="white", command=self._on_stop)
        # Ne pas afficher au démarrage

        # Checkbox mode debug
        self.debug_checkbox = tk.Checkbutton(button_frame, text="Mode Debug", variable=self.debug_mode_var)
        self.debug_checkbox.pack(side=tk.LEFT)

        # Cadre pour les boutons de configuration — toujours visible (mode normal et debug)
        self.config_buttons_frame = ttk.Frame(action_frame)

        import_btn = tk.Button(self.config_buttons_frame, text="📂 Importer config",
                               command=self._on_import_config)
        import_btn.pack(side=tk.LEFT, padx=5)

        export_btn = tk.Button(self.config_buttons_frame, text="💾 Exporter config",
                               command=self._on_export_config)
        export_btn.pack(side=tk.LEFT, padx=5)

        # Reset config : reste réservé au mode debug (action destructive)
        self.reset_config_btn = tk.Button(self.config_buttons_frame, text="🔄 Reset config",
                                          command=self._on_reset_config)
        self.reset_config_btn.pack(side=tk.LEFT, padx=5)

        self.config_buttons_frame.pack(pady=(5, 0))

    def _on_run(self):
        """Callback du bouton 'Créer le Bidul !'."""
        if not self.input_var.get().strip():
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d'entrée.")
            return
        if not self.pdf_var.get().strip():
            messagebox.showerror("Erreur", "Veuillez spécifier un chemin pour le PDF de sortie.")
            return
        if not self.poster_title_var.get().strip():
            messagebox.showerror("Erreur", "Le titre du poster ne peut pas être vide.")
            return

        validated_args = {}

        # Collecter le contenu de la zone de texte Cucaracha, si elle existe.
        cuca_value = self.cucaracha_text_widget.get("1.0", tk.END).strip() if self.cucaracha_text_widget else ""
        if self.cucaracha_type_var.get() == "image":
            cuca_value = self.cucaracha_value_var.get().strip()
        validated_args['cuca_value_val'] = cuca_value

        try:
            validated_args.update({
                'margin_val': float(self.margin_var.get().strip()),
                'date_spacing_val': float(self.date_spacing_var.get().strip()),
                'safety_factor_val': float(self.safety_factor_var.get().strip()),
                'logos_padding_val': float(self.logos_padding_var.get().strip()),
                'font_size_forced_val': float(self.font_size_forced_var.get().strip()),
                'stories_font_size_val': int(self.stories_font_size_var.get().strip()),
                'cuca_font_size_val': int(self.cucaracha_font_size_var.get().strip()),
                'inline_images_scale_val': float(self.inline_images_scale_var.get().strip()),
                'inline_images_margin_val': float(self.inline_images_margin_var.get().strip()),
            })
        except ValueError:
            messagebox.showerror("Erreur", "Les champs numériques (marges, espacement, etc.) doivent être valides.")
            return

        validated_args['poster_title_val'] = self.poster_title_var.get().strip()
        if not validated_args['poster_title_val']:
            messagebox.showerror("Erreur", "Le titre du poster est obligatoire.")
            return

        validated_args['stories_font_size_val'] = int(self.stories_font_size_var.get().strip())

        # v1.4.3 : Réinitialiser l'event d'arrêt et afficher le bouton Stop
        self.stop_event.clear()
        self.status_var.set("Traitement en cours…")
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))  # Afficher le bouton Stop

        thread = threading.Thread(target=self._run_pipeline_in_thread, args=(validated_args,))
        thread.daemon = True
        thread.start()

        self.progress_bar.config(value=0)
        self.status_var.set("Démarrage du processus...")

        self.after(100, self._check_thread_for_results)

    def _run_pipeline_in_thread(self, validated_args):
        """Wrapper qui exécute la fonction de traitement lourde."""
        from ._helpers import run_pipeline

        # Collecter l'état des abréviations activées
        abbreviations_enabled = {}
        for key, var in self.abbreviation_vars.items():
            abbreviations_enabled[key] = var.get()

        run_pipeline(
            self.result_queue,
            debug_mode=self.debug_mode_var.get(),
            input_file=self.input_var.get().strip(),
            generate_cover=self.generate_cover_var.get(),
            cover_image=self.cover_var.get().strip(),
            ours_background_png=self.ours_png_var.get().strip(),
            ours_layout=self.ours_layout_var.get(),
            ours_svg_file=self.ours_svg_var.get().strip(),
            logos_dir=self.logos_var.get().strip(),
            logos_layout=self.logos_layout_var.get(),
            logos_padding_mm=validated_args['logos_padding_val'],
            logos_svg_file=self.logos_svg_var.get().strip(),
            out_html=self.html_var.get().strip(),
            out_agenda_html=self.agenda_var.get().strip(),
            out_pdf=self.pdf_var.get().strip(),
            auteur_couv=self.auteur_var.get().strip(),
            auteur_couv_url=self.auteur_url_var.get().strip(),
            page_margin_mm=validated_args['margin_val'],
            font_size_mode=self.font_size_mode_var.get(),
            font_size_forced=validated_args['font_size_forced_val'],
            generate_svg=self.generate_svg_var.get(),
            out_svg_dir=self.svg_output_var.get().strip(),
            generate_stories=self.generate_stories_var.get(),
            stories_output_dir=self.stories_output_var.get().strip(),
            body_font_name=self.body_font_name_var.get(),
            date_separator_type=self.date_separator_var.get(),
            date_spacing=validated_args['date_spacing_val'],
            date_font_name=self.date_font_name_var.get(),
            date_bold=self.date_bold_var.get(),
            date_italic=self.date_italic_var.get(),
            date_alignment=self.date_align_var.get(),
            date_color=self.date_color_var.get(),
            bidul_label_enabled=self.bidul_label_enabled_var.get(),
            bidul_label_color=self.bidul_label_color_var.get(),
            festival_subgroup_enabled=self.festival_subgroup_enabled_var.get(),
            poster_design=self.poster_design_var.get(),
            font_size_safety_factor=validated_args['safety_factor_val'],
            background_alpha=self.alpha_var.get(),
            poster_title=validated_args['poster_title_val'],
            cucaracha_type=self.cucaracha_type_var.get(),
            cucaracha_value=validated_args['cuca_value_val'],
            cucaracha_text_font=self.cucaracha_font_var.get(),
            cucaracha_font_size=validated_args['cuca_font_size_val'],
            chapeau_icon_enabled=self.chapeau_icon_var.get(),
            free_icon_enabled=self.free_icon_var.get(),
            date_box_back_color=self.date_box_back_color_var.get(),
            stories_font_name=self.stories_font_name_var.get(),
            stories_font_size=validated_args['stories_font_size_val'],
            stories_font_color=self.stories_font_color_var.get(),
            stories_bg_type=self.stories_bg_type_var.get(),
            stories_bg_color=self.stories_bg_color_var.get(),
            stories_bg_image=self.stories_bg_image_var.get().strip(),
            stories_alpha=self.stories_alpha_var.get(),
            abbreviations_enabled=abbreviations_enabled,
            stop_event=self.stop_event,  # v1.4.3 : Passer l'event d'arrêt
            split_pdf=self.split_pdf_var.get(),  # v1.4.5 : Générer un PDF par page
            print_pdf=self.print_pdf_var.get(),  # v1.5.0 : Fichiers d'impression
            logos_print_svg_file=self.logos_print_svg_var.get().strip(),
            generate_html=self.generate_html_var.get(),  # v1.5.2 : Génération HTML optionnelle
            inline_images_enabled=self.inline_images_enabled_var.get(),
            inline_images_dir=self.inline_images_dir_var.get().strip(),
            inline_images_scale=validated_args['inline_images_scale_val'],
            inline_images_margin=validated_args['inline_images_margin_val'],
            inline_images_auto_scale=self.inline_images_auto_scale_var.get(),
            date_grouping_enabled=self.date_grouping_enabled_var.get(),
            festival_in_date_header=self.festival_in_date_header_var.get(),
        )

    def _check_thread_for_results(self):
        """Vérifie la queue pour les messages du thread."""
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

                    self.progress_bar.config(value=self.total_progress_steps)
                    self.run_button.config(state=tk.NORMAL)
                    # v1.4.3 : Cacher et réactiver le bouton Stop pour la prochaine exécution
                    self.stop_button.pack_forget()
                    self.stop_button.config(state=tk.NORMAL)

                    if ok:
                        VictoryWindow(self, summary_text=msg)
                        self.status_var.set("Terminé avec succès.")
                    else:
                        # v1.4.3 : Gérer le cas d'interruption utilisateur
                        if "interrompu" in msg.lower():
                            self.status_var.set("Interrompu.")
                        else:
                            messagebox.showerror("Erreur", msg)
                            self.status_var.set("Échec.")

                    return

        except queue.Empty:
            pass
        except Exception as e:
            print(f"Erreur en lisant la queue : {e}")

        self.after(100, self._check_thread_for_results)

    # --- v1.4.3 : Méthode pour arrêter le pipeline ---

    def _on_stop(self):
        """Callback du bouton Stop pour interrompre le pipeline."""
        self.stop_event.set()
        self.status_var.set("Arrêt en cours...")
        self.stop_button.config(state=tk.DISABLED)

    # --- ✨ NOUVELLES MÉTHODES pour import/reset config ---

    def _on_import_config(self):
        """Import et applique un fichier de config (YAML ou JSON)"""
        from tkinter import filedialog
        from ._helpers import load_and_apply_config

        config_path = filedialog.askopenfilename(
            title="Sélectionner un fichier de configuration",
            filetypes=[
                ("Config (YAML/JSON)", "*.yml *.yaml *.json"),
                ("YAML", "*.yml *.yaml"),
                ("JSON", "*.json"),
                ("Tous", "*.*")
            ]
        )
        if not config_path:
            return

        try:
            load_and_apply_config(self, config_path)
            messagebox.showinfo("Succès", f"Configuration chargée depuis :\n{os.path.basename(config_path)}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger la config :\n{e}")

    def _on_reset_config(self):
        """Reset vers config par défaut"""
        from ._helpers import load_and_apply_config, _project_defaults

        defaults = _project_defaults()
        try:
            load_and_apply_config(self, defaults["config"])
            messagebox.showinfo("Succès", "Configuration réinitialisée")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de reset :\n{e}")

    def _on_export_config(self):
        """Exporte la configuration actuelle de l'UI vers un fichier JSON."""
        from tkinter import filedialog
        from ._helpers import save_current_config_from_app

        # Suggérer un nom basé sur le fichier d'entrée (ou "config.json")
        initial_file = "config.json"
        input_path = self.input_var.get().strip()
        if input_path:
            stem = os.path.splitext(os.path.basename(input_path))[0]
            if stem:
                initial_file = f"{stem}.config.json"

        dest_path = filedialog.asksaveasfilename(
            title="Exporter la configuration",
            defaultextension=".json",
            initialfile=initial_file,
            filetypes=[("JSON", "*.json"), ("Tous", "*.*")],
        )
        if not dest_path:
            return

        try:
            save_current_config_from_app(self, dest_path)
            messagebox.showinfo(
                "Succès",
                f"Configuration exportée :\n{os.path.basename(dest_path)}",
            )
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'exporter la config :\n{e}")

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
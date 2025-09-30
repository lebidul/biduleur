# leTruc/widgets.py
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

# Ce fichier a une responsabilité unique : créer et placer tous les widgets de l'interface. Il ne contiendra aucune logique d'action (pas de command=... qui font des choses compliquées).
# La stratégie est de créer une fonction principale create_all qui appelle des sous-fonctions pour chaque grande section de l'interface (une pour la section "Fichier d'entrée", une pour la section "Logos", etc.). C'est beaucoup plus propre et lisible.
# # Notez que pour les widgets qui auront besoin d'une action (comme les boutons), nous les stockons dans l'instance de l'application (ex: app.input_button = ...). Le fichier callbacks.py les récupérera plus tard pour leur assigner une commande.
# widgets.py est "stupide". Il ne fait que créer les briques de l'interface (tk.Label, tk.Entry) et les stocker dans app. Il ne sait pas quand les afficher ou les cacher.
# callbacks.py est "intelligent".
# assign_all_callbacks agit comme un électricien : il connecte les interrupteurs aux lampes. Ici, il connecte la variable app.logos_layout_var à la fonction on_toggle_padding_widget en utilisant .trace_add("write", ...). Cela signifie : "À chaque fois que la valeur de cette variable change, exécute cette fonction".
# on_toggle_padding_widget contient la logique if/else pour décider s'il faut afficher ou cacher les widgets en utilisant .grid() et .grid_remove().
# L'appel on_toggle_padding_widget(app) à la fin de assign_all_callbacks est crucial pour s'assurer que l'interface est dans le bon état dès le démarrage.

def create_all(app):
    """
    Fonction principale qui orchestre la création de toutes les sections de widgets.

    Args:
        app: L'instance principale de la classe Application.
    """
    # 'main_frame' est le cadre scrollable créé dans app.py
    main_frame = app.scrollable_frame
    main_frame.columnconfigure(1, weight=1)

    # On utilise un dictionnaire pour passer le compteur de ligne
    # C'est une astuce pour le passer par référence
    ui_row = {'r': 0}

    _create_input_section(main_frame, app, ui_row)
    _create_ours_section(main_frame, app, ui_row)
    _create_logos_section(main_frame, app, ui_row)
    _create_cucaracha_section(main_frame, app, ui_row)
    _create_cover_section(main_frame, app, ui_row)
    _create_page_layout_section(main_frame, app, ui_row)
    _create_date_sep_section(main_frame, app, ui_row)
    _create_poster_section(main_frame, app, ui_row)
    _create_stories_section(main_frame, app, ui_row)
    _create_output_section(main_frame, app, ui_row)


def _create_input_section(parent, app, ui_row):
    """Crée la section pour le fichier d'entrée et les modèles."""
    r = ui_row['r']
    tk.Label(parent, text="Fichier d’entrée (CSV / XLS) :").grid(row=r, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(parent, textvariable=app.input_var).grid(row=r, column=1, sticky="ew", padx=5, pady=5)
    app.input_button = tk.Button(parent, text="Parcourir…")
    app.input_button.grid(row=r, column=2, padx=5, pady=5)
    r += 1

    models_frame = ttk.Frame(parent)
    models_frame.grid(row=r, column=1, columnspan=2, sticky="w", padx=5, pady=(0, 10))
    tk.Label(models_frame, text="Télécharger un modèle :").pack(side=tk.LEFT, anchor=tk.W)
    app.csv_template_button = tk.Button(models_frame, text="Modèle CSV")
    app.csv_template_button.pack(side=tk.LEFT, padx=5)
    app.xlsx_template_button = tk.Button(models_frame, text="Modèle XLSX")
    app.xlsx_template_button.pack(side=tk.LEFT, padx=5)
    r += 1

    ttk.Separator(parent, orient='horizontal').grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    r += 1
    ui_row['r'] = r


def _create_ours_section(parent, app, ui_row):
    """Crée la section pour l'image de fond de l'ours."""
    r = ui_row['r']

    # On utilise un LabelFrame pour un meilleur regroupement visuel
    ours_frame = ttk.LabelFrame(parent, text="Ours", padding="10")
    ours_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    ours_frame.columnconfigure(1, weight=1)

    # Ligne 0 du LabelFrame
    tk.Label(ours_frame, text="Image de fond (PNG) :").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(ours_frame, textvariable=app.ours_png_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    app.ours_button = tk.Button(ours_frame, text="Parcourir…")
    app.ours_button.grid(row=0, column=2, padx=5, pady=5)

    # Ligne 1 du LabelFrame : Widget pour l'aperçu
    app.ours_preview = tk.Label(ours_frame, text="Aucun aperçu", relief="sunken", padx=5, pady=5)
    app.ours_preview.grid(row=1, column=1, sticky="w", pady=(5, 0), padx=5)

    r += 1
    ui_row['r'] = r



def _create_logos_section(parent, app, ui_row):
    """Crée la section pour les paramètres des logos."""
    r = ui_row['r']
    logos_frame = ttk.LabelFrame(parent, text="Paramètres des Logos", padding="10")
    logos_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    logos_frame.columnconfigure(1, weight=1)

    lr = 0
    tk.Label(logos_frame, text="Dossier logos :").grid(row=lr, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(logos_frame, textvariable=app.logos_var).grid(row=lr, column=1, sticky="ew", padx=5, pady=5)
    app.logos_button = tk.Button(logos_frame, text="Parcourir…")
    app.logos_button.grid(row=lr, column=2, padx=5, pady=5)
    lr += 1

    tk.Label(logos_frame, text="Répartition :").grid(row=lr, column=0, sticky="e", padx=5, pady=5)
    logos_layout_radios = ttk.Frame(logos_frame)
    logos_layout_radios.grid(row=lr, column=1, columnspan=2, sticky="w")

    app.logos_padding_label = tk.Label(logos_frame, text="Marge (mm) :")
    app.logos_padding_entry = tk.Entry(logos_frame, textvariable=app.logos_padding_var, width=10)

    # La commande sera ajoutée dans callbacks.py en utilisant .trace_add sur la variable
    tk.Radiobutton(logos_layout_radios, text="2 Colonnes", variable=app.logos_layout_var, value="colonnes").pack(
        side=tk.LEFT, padx=5)
    tk.Radiobutton(logos_layout_radios, text="Optimisée", variable=app.logos_layout_var, value="optimise").pack(
        side=tk.LEFT, padx=5)

    # On stocke la ligne pour le callback
    app.logos_padding_row = lr + 1

    r += 1
    ui_row['r'] = r


def _create_cucaracha_section(parent, app, ui_row):
    """Crée la section pour la boîte Cucaracha."""
    r = ui_row['r']
    app.cucaracha_frame = ttk.LabelFrame(parent, text="Boîte 'Cucaracha'", padding="10")
    app.cucaracha_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    app.cucaracha_frame.columnconfigure(1, weight=1)

    # --- Widgets pour le type "Texte" ---
    app.cucaracha_text_widget = tk.Text(app.cucaracha_frame, height=4, wrap=tk.WORD)
    app.cucaracha_text_widget.insert("1.0", app.cucaracha_value_var.get())

    # 1. On crée le cadre qui contiendra les options de police.
    app.cucaracha_font_frame = ttk.Frame(app.cucaracha_frame)

    # 2. On crée les widgets de police en leur donnant `app.cucaracha_font_frame` comme parent.
    app.cucaracha_font_label = tk.Label(app.cucaracha_font_frame, text="Police :")
    font_options = ["Arial", "Helvetica", "Times New Roman", "Courier", "DejaVu Sans"]
    app.cucaracha_font_combo = ttk.Combobox(app.cucaracha_font_frame, textvariable=app.cucaracha_font_var,
                                            values=font_options, state="readonly")
    app.cucaracha_font_size_label = tk.Label(app.cucaracha_font_frame, text="Taille (pt):")
    app.cucaracha_font_size_entry = tk.Entry(app.cucaracha_font_frame, textvariable=app.cucaracha_font_size_var,
                                             width=5)

    # 3. On utilise .pack() pour organiser les widgets À L'INTÉRIEUR du `font_frame`.
    #    Ceci est autorisé car `font_frame` n'a pas encore de widgets gérés par .grid().
    app.cucaracha_font_label.pack(side=tk.LEFT)
    app.cucaracha_font_combo.pack(side=tk.LEFT, padx=(0, 10))
    app.cucaracha_font_size_label.pack(side=tk.LEFT)
    app.cucaracha_font_size_entry.pack(side=tk.LEFT)

    # --- Widgets pour le type "Image" ---
    app.cucaracha_image_entry = tk.Entry(app.cucaracha_frame, textvariable=app.cucaracha_value_var)
    app.cucaracha_image_button = tk.Button(app.cucaracha_frame, text="Parcourir…")
    app.cucaracha_preview = tk.Label(app.cucaracha_frame, text="Aucun aperçu", relief="sunken", padx=5, pady=5)

    # --- Widgets communs ---
    radio_frame = ttk.Frame(app.cucaracha_frame)
    radio_frame.grid(row=0, column=0, columnspan=3, sticky="w")
    tk.Radiobutton(radio_frame, text="Rien", variable=app.cucaracha_type_var, value="none").pack(side=tk.LEFT)
    tk.Radiobutton(radio_frame, text="Texte", variable=app.cucaracha_type_var, value="text").pack(side=tk.LEFT)
    tk.Radiobutton(radio_frame, text="Image", variable=app.cucaracha_type_var, value="image").pack(side=tk.LEFT)

    r += 1
    ui_row['r'] = r


def _create_cover_section(parent, app, ui_row):
    """Crée la section pour les informations de couverture."""
    r = ui_row['r']
    cover_frame = ttk.LabelFrame(parent, text="Informations de couverture", padding="10")
    cover_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    cover_frame.columnconfigure(1, weight=1)

    # Ligne 0
    tk.Checkbutton(cover_frame, text="Avec couv' (générer la page de couverture)",
                   variable=app.generate_cover_var).grid(row=0, column=0, columnspan=3, sticky="w", pady=2)

    # Ligne 1
    tk.Label(cover_frame, text="Image de Couverture :").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(cover_frame, textvariable=app.cover_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    app.cover_button = tk.Button(cover_frame, text="Parcourir…")
    app.cover_button.grid(row=1, column=2, padx=5, pady=5)

    # Ligne 2 : Widget pour l'aperçu
    app.cover_preview = tk.Label(cover_frame, text="Aucun aperçu", relief="sunken", padx=5, pady=5)
    app.cover_preview.grid(row=2, column=1, sticky="w", pady=(5, 0), padx=5)

    # Lignes suivantes (décalées)
    tk.Label(cover_frame, text="Auteur Couverture :").grid(row=3, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(cover_frame, textvariable=app.auteur_var).grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
    tk.Label(cover_frame, text="URL auteur couverture :").grid(row=4, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(cover_frame, textvariable=app.auteur_url_var).grid(row=4, column=1, columnspan=2, sticky="ew", padx=5,
                                                                pady=5)

    r += 1
    ui_row['r'] = r


def _create_page_layout_section(parent, app, ui_row):
    """Crée la section pour la mise en page globale."""
    r = ui_row['r']
    page_layout_frame = ttk.LabelFrame(parent, text="Mise en Page Globale", padding="10")
    page_layout_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    page_layout_frame.columnconfigure(1, weight=1)

    # On utilise un compteur de ligne local pour ce frame
    lr = 0

    tk.Label(page_layout_frame, text="Marge globale (mm) :").grid(row=lr, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(page_layout_frame, textvariable=app.margin_var, width=10).grid(row=lr, column=1, sticky="w", padx=5,
                                                                            pady=5)
    lr += 1

    # --- Taille de police ---
    tk.Label(page_layout_frame, text="Taille de police :").grid(row=lr, column=0, sticky="w", padx=5, pady=5)
    font_mode_frame = ttk.Frame(page_layout_frame)
    font_mode_frame.grid(row=lr, column=1, columnspan=2, sticky="w")

    tk.Radiobutton(font_mode_frame, text="Automatique", variable=app.font_size_mode_var, value="auto").pack(
        side=tk.LEFT, padx=5)
    tk.Radiobutton(font_mode_frame, text="Forcée", variable=app.font_size_mode_var, value="force").pack(side=tk.LEFT,
                                                                                                        padx=5)
    lr += 1

    # Création des widgets conditionnels (mais on ne les place pas encore)
    app.font_size_forced_label = tk.Label(page_layout_frame, text="Taille forcée (pt) :")
    app.font_size_forced_entry = tk.Entry(page_layout_frame, textvariable=app.font_size_forced_var, width=10)

    # On stocke la ligne où ils devront apparaître pour le callback
    app.font_size_forced_row = lr

    r += 1
    ui_row['r'] = r


def _create_date_sep_section(parent, app, ui_row):
    """Crée la section pour le séparateur de dates."""
    r = ui_row['r']
    date_sep_frame = ttk.LabelFrame(parent, text="Séparateur de dates", padding="10")
    date_sep_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    date_sep_frame.columnconfigure(1, weight=1)

    lr = 0
    tk.Label(date_sep_frame, text="Type de séparateur :").grid(row=lr, column=0, sticky="w", padx=5, pady=5)
    date_sep_radios = ttk.Frame(date_sep_frame)
    date_sep_radios.grid(row=lr, column=1, sticky="w", padx=5, pady=5)
    lr += 1

    tk.Label(date_sep_frame, text="Espace avant/après date (pt) :").grid(row=lr, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(date_sep_frame, textvariable=app.date_spacing_var, width=10).grid(row=lr, column=1, sticky="w", padx=5,
                                                                               pady=5)
    lr += 1

    # Création du cadre de couleur (sera géré par un callback)
    app.date_box_colors_frame = ttk.Frame(date_sep_frame)

    # --- Widgets pour la couleur de fond (on garde) ---
    app.back_color_label = tk.Label(app.date_box_colors_frame, text="Couleur de fond :")
    app.back_color_preview = tk.Label(app.date_box_colors_frame, text="    ", bg=app.date_box_back_color_var.get(), relief="sunken")
    app.back_color_btn = tk.Button(app.date_box_colors_frame, text="…", width=3)

    # Placer les widgets de couleur de fond dans leur grille
    app.back_color_label.grid(row=0, column=0, sticky="w", padx=(0, 5))
    app.back_color_preview.grid(row=0, column=1, sticky="w")
    app.back_color_btn.grid(row=0, column=2, sticky="w", padx=5)

    app.date_box_colors_row = lr  # On stocke la ligne pour le callback

    # Création des boutons radio
    tk.Radiobutton(date_sep_radios, text="Aucun", variable=app.date_separator_var, value="aucun").pack(side=tk.LEFT)
    tk.Radiobutton(date_sep_radios, text="Ligne", variable=app.date_separator_var, value="ligne").pack(side=tk.LEFT,
                                                                                                       padx=10)
    tk.Radiobutton(date_sep_radios, text="Box", variable=app.date_separator_var, value="box").pack(side=tk.LEFT)

    r += 1
    ui_row['r'] = r


def _create_poster_section(parent, app, ui_row):
    """Crée la section pour les paramètres du poster."""
    r = ui_row['r']
    layout_frame = ttk.LabelFrame(parent, text="Paramètres de mise en page (Poster)", padding="10")
    layout_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    layout_frame.columnconfigure(1, weight=1)

    tk.Label(layout_frame, text="Titre du poster :").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(layout_frame, textvariable=app.poster_title_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    tk.Label(layout_frame, text="Design du poster :").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    design_frame = ttk.Frame(layout_frame)
    design_frame.grid(row=1, column=1, sticky="w", padx=5, pady=5)

    # Création des widgets conditionnels (slider alpha)
    app.alpha_label = tk.Label(layout_frame, text="Transparence du voile blanc :")
    app.alpha_scale_frame = ttk.Frame(layout_frame)
    alpha_scale = ttk.Scale(app.alpha_scale_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=app.alpha_var)
    alpha_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
    app.alpha_value_label = ttk.Label(app.alpha_scale_frame, text=f"{int(app.alpha_var.get() * 100)}%")
    app.alpha_value_label.pack(side=tk.LEFT, padx=(5, 0))
    app.alpha_slider_row = 2  # On stocke la ligne pour le callback

    tk.Radiobutton(design_frame, text="Image au centre", variable=app.poster_design_var, value=0).pack(side=tk.LEFT,
                                                                                                       padx=5)
    tk.Radiobutton(design_frame, text="Image en fond", variable=app.poster_design_var, value=1).pack(side=tk.LEFT,
                                                                                                     padx=5)

    tk.Label(layout_frame, text="Facteur de sécurité police :").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(layout_frame, textvariable=app.safety_factor_var, width=10).grid(row=3, column=1, sticky="w", padx=5,
                                                                              pady=5)

    r += 1
    ui_row['r'] = r


def _create_stories_section(parent, app, ui_row):
    """Crée la section pour les paramètres des Stories Instagram."""
    r = ui_row['r']
    stories_frame = ttk.LabelFrame(parent, text="Préparation de la story Instagram", padding="10")
    stories_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    stories_frame.columnconfigure(1, weight=1)

    lr = 0  # Ligne locale

    # --- Police ---
    tk.Label(stories_frame, text="Police :").grid(row=lr, column=0, sticky="w", padx=5, pady=5)
    font_frame = ttk.Frame(stories_frame)
    font_frame.grid(row=lr, column=1, sticky="w")
    ttk.Combobox(font_frame, textvariable=app.stories_font_name_var,
                 values=["Arial", "Helvetica", "Times New Roman", "Verdana", "Impact"],
                 state="readonly", width=15).pack(side=tk.LEFT, padx=5)
    tk.Label(font_frame, text="Taille (pt) :").pack(side=tk.LEFT, padx=(10, 5))
    tk.Entry(font_frame, textvariable=app.stories_font_size_var, width=5).pack(side=tk.LEFT)
    lr += 1

    # --- Couleur de la police ---
    tk.Label(stories_frame, text="Couleur de la police :").grid(row=lr, column=0, sticky="w", padx=5, pady=5)
    font_color_frame = ttk.Frame(stories_frame)
    font_color_frame.grid(row=lr, column=1, sticky="w")
    app.stories_font_color_preview = tk.Label(font_color_frame, text="    ", bg=app.stories_font_color_var.get(),
                                              relief="sunken")
    app.stories_font_color_preview.pack(side=tk.LEFT, padx=5)
    app.stories_font_color_button = tk.Button(font_color_frame, text="Choisir…")
    app.stories_font_color_button.pack(side=tk.LEFT)
    lr += 1

    # --- Type de fond ---
    tk.Label(stories_frame, text="Fond :").grid(row=lr, column=0, sticky="w", padx=5, pady=5)
    bg_type_frame = ttk.Frame(stories_frame)
    bg_type_frame.grid(row=lr, column=1, sticky="w")
    tk.Radiobutton(bg_type_frame, text="Couleur unie", variable=app.stories_bg_type_var, value="color").pack(
        side=tk.LEFT, padx=5)
    tk.Radiobutton(bg_type_frame, text="Image", variable=app.stories_bg_type_var, value="image").pack(side=tk.LEFT,
                                                                                                      padx=5)
    lr += 1

    # --- Widgets conditionnels pour le fond ---
    app.stories_bg_row = lr

    # Cadre pour la couleur
    app.stories_bg_color_frame = ttk.Frame(stories_frame)
    app.stories_bg_color_preview = tk.Label(app.stories_bg_color_frame, text="    ", bg=app.stories_bg_color_var.get(),
                                            relief="sunken")
    app.stories_bg_color_preview.pack(side=tk.LEFT, padx=5)
    app.stories_bg_color_button = tk.Button(app.stories_bg_color_frame, text="Choisir…")
    app.stories_bg_color_button.pack(side=tk.LEFT)

    # Cadre pour l'image
    app.stories_bg_image_frame = ttk.Frame(stories_frame)
    tk.Entry(app.stories_bg_image_frame, textvariable=app.stories_bg_image_var, width=40).pack(side=tk.LEFT, fill=tk.X,
                                                                                               expand=True)
    app.stories_bg_image_button = tk.Button(app.stories_bg_image_frame, text="Parcourir…")
    app.stories_bg_image_button.pack(side=tk.LEFT, padx=5)

    # Cadre pour le slider alpha (partagé par l'image)
    app.stories_alpha_frame = ttk.Frame(stories_frame)
    tk.Label(app.stories_alpha_frame, text="Transparence du voile :").pack(side=tk.LEFT, padx=5)
    ttk.Scale(app.stories_alpha_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=app.stories_alpha_var).pack(
        side=tk.LEFT, fill=tk.X, expand=True)
    app.stories_alpha_value_label = ttk.Label(app.stories_alpha_frame,
                                              text=f"{int(app.stories_alpha_var.get() * 100)}%")
    app.stories_alpha_value_label.pack(side=tk.LEFT, padx=(5, 0))

    r += 1
    ui_row['r'] = r


def _create_output_section(parent, app, ui_row):
    """Crée la section pour les fichiers de sortie."""
    r = ui_row['r']
    output_frame = ttk.LabelFrame(parent, text="Fichiers de sortie", padding="10")
    output_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    output_frame.columnconfigure(1, weight=1)

    # HTML
    tk.Label(output_frame, text="HTML (biduleur) :").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=app.html_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    app.html_save_button = tk.Button(output_frame, text="…", width=3)
    app.html_save_button.grid(row=0, column=2, padx=5, pady=5)

    # HTML Agenda
    tk.Label(output_frame, text="HTML Agenda :").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=app.agenda_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    app.agenda_save_button = tk.Button(output_frame, text="…", width=3)
    app.agenda_save_button.grid(row=1, column=2, padx=5, pady=5)

    # PDF
    tk.Label(output_frame, text="PDF (misenpageur) :").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=app.pdf_var).grid(row=2, column=1, sticky="ew", padx=5, pady=5)
    app.pdf_save_button = tk.Button(output_frame, text="…", width=3)
    app.pdf_save_button.grid(row=2, column=2, padx=5, pady=5)

    # SVG
    tk.Checkbutton(output_frame, text="Générer un SVG éditable (pour Inkscape)", variable=app.generate_svg_var).grid(
        row=3, column=0, columnspan=3, sticky="w", padx=5, pady=5)
    tk.Label(output_frame, text="Nom de base SVG :").grid(row=4, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=app.svg_var).grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    app.svg_save_button = tk.Button(output_frame, text="…", width=3)
    app.svg_save_button.grid(row=4, column=2, padx=5, pady=5)

    # Stories
    tk.Checkbutton(output_frame, text="Générer les images pour les Stories Instagram", variable=app.generate_stories_var).grid(
        row=5, column=0, columnspan=3, sticky="w", padx=5, pady=5)
    tk.Label(output_frame, text="Dossier Stories :").grid(row=6, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=app.stories_output_var).grid(row=6, column=1, sticky="ew", padx=5, pady=5)
    app.stories_output_button = tk.Button(output_frame, text="…", width=3)
    app.stories_output_button.grid(row=6, column=2, padx=5, pady=5)

    r += 1
    ui_row['r'] = r
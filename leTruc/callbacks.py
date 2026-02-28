# leTruc/callbacks.py
# -*- coding: utf-8 -*-
# MODIFICATIONS : Ajout toggle pour boutons config en mode debug
# v1.4.2 : Ajout callbacks pour abréviations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, ttk
from PIL import Image, ImageTk
import re

# On importe les helpers qui contiennent la logique "métier"
from ._helpers import _default_paths_from_input, save_embedded_template, open_file


def assign_all(app):
    """
    Fonction principale qui assigne toutes les fonctions de callback
    aux widgets et variables de l'application.
    """

    # --- Assignation des commandes aux boutons "Parcourir...", "Enregistrer...", etc. ---
    app.input_button.config(command=lambda: on_pick_input(app))
    app.csv_template_button.config(
        command=lambda: save_embedded_template('tapage_template.csv', "Enregistrer le modèle CSV"))
    app.xlsx_template_button.config(
        command=lambda: save_embedded_template('tapage_template.xlsx', "Enregistrer le modèle XLSX"))

    app.ours_png_button.config(command=lambda: on_pick_image_with_preview(app, app.ours_png_var,
                                                                          app.ours_preview,
                                                                          "Image de fond pour l'Ours (PNG)",
                                                                          [("Images", "*.png;*.jpg;*.jpeg"),
                                                                           ("Tous", "*.*")]))
    app.ours_svg_button.config(command=lambda: on_pick_file(app.ours_svg_var, "Fichier SVG de l'Ours",
                                                            [("SVG", "*.svg"), ("Tous", "*.*")]))
    app.logos_button.config(command=lambda: on_pick_directory(app.logos_var, "Dossier des logos"))
    app.logos_svg_button.config(command=lambda: on_pick_file(app.logos_svg_var, "Fichier SVG des logos",
                                                             [("SVG", "*.svg"), ("Tous", "*.*")]))

    app.cucaracha_image_button.config(command=lambda: on_pick_image_with_preview(app, app.cucaracha_value_var,
                                                                                 app.cucaracha_preview,
                                                                                 "Choisir une image",
                                                                                 [("Images", "*.jpg *.jpeg *.png")]))

    app.cover_button.config(command=lambda: on_pick_cover_file(app))

    app.html_save_button.config(command=lambda: on_pick_save(app.html_var, "HTML", ".html", [("HTML", "*.html")]))
    app.agenda_save_button.config(
        command=lambda: on_pick_save(app.agenda_var, "HTML Agenda", ".html", [("HTML", "*.html")]))
    app.pdf_save_button.config(command=lambda: on_pick_save(app.pdf_var, "PDF", ".pdf", [("PDF", "*.pdf")]))
    app.svg_output_button.config(
        command=lambda: on_pick_directory(app.svg_output_var, "Choisir le dossier de sortie pour les SVG"))
    app.stories_output_button.config(
        command=lambda: on_pick_directory(app.stories_output_var, "Choisir le dossier de sortie pour les Stories"))

    # Assigner la commande au bouton principal
    app.run_button.config(command=app._on_run)

    app.back_color_btn.config(command=lambda: on_pick_color(app.date_box_back_color_var))

    app.stories_font_color_button.config(command=lambda: on_pick_color(app.stories_font_color_var))
    app.stories_bg_color_button.config(command=lambda: on_pick_color(app.stories_bg_color_var))
    app.stories_bg_image_button.config(
        command=lambda: on_pick_file(app.stories_bg_image_var, "Choisir une image de fond",
                                     [("Images", "*.jpg *.jpeg *.png")]))

    # --- Liaison des variables aux fonctions de "toggle" ---
    app.logos_layout_var.trace_add("write", lambda *args: on_toggle_padding_widget(app))
    app.ours_layout_var.trace_add("write", lambda *args: on_toggle_ours_widgets(app))
    app.font_size_mode_var.trace_add("write", lambda *args: on_toggle_font_size_widgets(app))
    app.cucaracha_type_var.trace_add("write", lambda *args: on_toggle_cucaracha_widgets(app))
    app.date_separator_var.trace_add("write", lambda *args: on_toggle_date_sep_options(app))
    app.poster_design_var.trace_add("write", lambda *args: on_toggle_alpha_slider(app))
    app.alpha_var.trace_add("write", lambda *args: on_update_alpha_label(app))
    app.stories_bg_type_var.trace_add("write", lambda *args: on_toggle_stories_bg_widgets(app))
    app.stories_alpha_var.trace_add("write", lambda *args: on_update_stories_alpha_label(app))
    app.stories_font_color_var.trace_add("write", lambda *args: app.stories_font_color_preview.config(
        bg=app.stories_font_color_var.get()))
    app.stories_bg_color_var.trace_add("write", lambda *args: app.stories_bg_color_preview.config(
        bg=app.stories_bg_color_var.get()))

    app.date_box_back_color_var.trace_add(
        "write",
        lambda *args: app.back_color_preview.config(bg=app.date_box_back_color_var.get())
    )

    # ✨ NOUVEAU : Toggle des boutons config quand debug mode change
    app.debug_mode_var.trace_add("write", lambda *args: on_toggle_config_buttons(app))

    # ✨ NOUVEAU v1.4.2 : Callbacks pour les boutons d'abréviations
    if hasattr(app, 'abbrev_select_all_btn'):
        app.abbrev_select_all_btn.config(command=lambda: on_abbrev_select_all(app))
    if hasattr(app, 'abbrev_deselect_all_btn'):
        app.abbrev_deselect_all_btn.config(command=lambda: on_abbrev_deselect_all(app))

    # --- Appels initiaux pour définir l'état de l'interface au démarrage ---
    on_toggle_padding_widget(app)
    on_toggle_ours_widgets(app)
    on_toggle_font_size_widgets(app)
    on_toggle_stories_bg_widgets(app)
    on_update_stories_alpha_label(app)
    on_toggle_cucaracha_widgets(app)
    on_toggle_date_sep_options(app)
    on_toggle_alpha_slider(app)
    on_update_alpha_label(app)
    on_toggle_config_buttons(app)  # ✨ NOUVEAU : Initialiser l'état des boutons config
    _update_drop_zone_text(app, app.input_var.get())
    _update_cover_drop_zone(app, app.cover_var.get())

    print("[INFO] Mise à jour des aperçus d'images au démarrage...")
    # On met à jour l'aperçu de l'ours si une valeur existe
    _update_preview(app.ours_png_var.get(), app.ours_preview)
    # On met à jour l'aperçu de la couverture si une valeur existe
    _update_preview(app.cover_var.get(), app.cover_preview)


# --- Fonctions de sélection de fichiers/dossiers ---

def on_pick_input(app):
    """Callback pour le bouton de sélection du fichier d'entrée."""
    file_path = filedialog.askopenfilename(
        title="Sélectionner l'entrée (CSV / XLS / XLSX)",
        filetypes=[("Excel", "*.xls;*.xlsx"), ("CSV", "*.csv"), ("Tous", "*.*")]
    )
    if not file_path: return

    # Mettre à jour la variable
    app.input_var.set(file_path)
    # Mettre à jour l'interface visuelle
    _update_drop_zone_text(app, file_path)
    # Mettre à jour les chemins de sortie
    d = _default_paths_from_input(file_path)

    app.html_var.set(d["html"])
    app.agenda_var.set(d["agenda_html"])
    app.pdf_var.set(d["pdf"])
    app.svg_output_var.set(d["svg_output_dir"])
    app.stories_output_var.set(d["stories_output"])


def on_pick_file(string_var, title, filetypes):
    """Callback générique pour choisir un fichier."""
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    if path: string_var.set(path)


def on_pick_directory(string_var, title):
    """Callback générique pour choisir un dossier."""
    path = filedialog.askdirectory(title=title)
    if path: string_var.set(path)


def on_pick_save(string_var, title, ext, filetypes):
    """Callback générique pour enregistrer un fichier."""
    path = filedialog.asksaveasfilename(title=title, defaultextension=ext, filetypes=filetypes)
    if path: string_var.set(path)


def on_pick_color(color_var):
    """Ouvre le sélecteur de couleur et met à jour la variable."""
    initial_color = color_var.get()
    _, color_hex = colorchooser.askcolor(initialcolor=initial_color)
    if color_hex:
        color_var.set(color_hex)


def on_pick_image_with_preview(app, string_var, preview_widget, title, filetypes):
    """
    Fonction générique pour les autres champs image (Ours, Cucaracha).
    """
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    if not path:
        return
    string_var.set(path)
    _update_preview(path, preview_widget)

    try:
        # Créer la miniature avec Pillow
        with Image.open(path) as img:
            img.thumbnail((150, 150))
            tk_image = ImageTk.PhotoImage(img)

            preview_widget.config(image=tk_image, text="")
            preview_widget.image = tk_image

    except Exception as e:
        preview_widget.config(image=None, text=f"Erreur: {e}")
        preview_widget.image = None


# --- Fonctions de visibilité conditionnelle ("toggle") ---

def on_toggle_padding_widget(app):
    """Affiche ou cache les widgets selon le mode de répartition des logos."""
    layout = app.logos_layout_var.get()
    lr = app.logos_padding_row

    if layout == "svg":
        # Mode SVG : cacher dossier logos et marge, afficher fichier SVG
        app.logos_dir_label.grid_remove()
        app.logos_dir_entry.grid_remove()
        app.logos_button.grid_remove()
        app.logos_padding_label.grid_remove()
        app.logos_padding_entry.grid_remove()
        app.logos_svg_label.grid(row=lr, column=0, sticky="e", padx=5, pady=5)
        app.logos_svg_entry.grid(row=lr, column=1, sticky="ew", padx=5, pady=5)
        app.logos_svg_button.grid(row=lr, column=2, padx=5, pady=5)
    elif layout == "optimise":
        # Mode optimisé : afficher dossier logos et marge, cacher fichier SVG
        app.logos_dir_label.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        app.logos_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        app.logos_button.grid(row=0, column=2, padx=5, pady=5)
        app.logos_padding_label.grid(row=lr, column=0, sticky="e", padx=5, pady=5)
        app.logos_padding_entry.grid(row=lr, column=1, sticky="w")
        app.logos_svg_label.grid_remove()
        app.logos_svg_entry.grid_remove()
        app.logos_svg_button.grid_remove()
    else:
        # Mode colonnes : afficher dossier logos, cacher marge et fichier SVG
        app.logos_dir_label.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        app.logos_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        app.logos_button.grid(row=0, column=2, padx=5, pady=5)
        app.logos_padding_label.grid_remove()
        app.logos_padding_entry.grid_remove()
        app.logos_svg_label.grid_remove()
        app.logos_svg_entry.grid_remove()
        app.logos_svg_button.grid_remove()


def on_toggle_ours_widgets(app):
    """Affiche ou cache les widgets selon le mode de source de l'ours."""
    layout = app.ours_layout_var.get()
    lr = app.ours_widgets_row

    if layout == "svg":
        # Mode SVG : afficher fichier SVG, cacher PNG et aperçu
        app.ours_svg_label.grid(row=lr, column=0, sticky="e", padx=5, pady=5)
        app.ours_svg_entry.grid(row=lr, column=1, sticky="ew", padx=5, pady=5)
        app.ours_svg_button.grid(row=lr, column=2, padx=5, pady=5)
        app.ours_png_label.grid_remove()
        app.ours_png_entry.grid_remove()
        app.ours_png_button.grid_remove()
        app.ours_preview.grid_remove()
    else:
        # Mode PNG : afficher PNG et aperçu, cacher fichier SVG
        app.ours_png_label.grid(row=lr, column=0, sticky="e", padx=5, pady=5)
        app.ours_png_entry.grid(row=lr, column=1, sticky="ew", padx=5, pady=5)
        app.ours_png_button.grid(row=lr, column=2, padx=5, pady=5)
        app.ours_preview.grid(row=lr + 1, column=1, sticky="w", pady=(5, 0), padx=5)
        app.ours_svg_label.grid_remove()
        app.ours_svg_entry.grid_remove()
        app.ours_svg_button.grid_remove()


def on_toggle_font_size_widgets(app):
    """Affiche ou cache le champ de saisie pour la taille de police forcée."""
    lr = app.font_size_forced_row
    label = app.font_size_forced_label
    entry = app.font_size_forced_entry

    if app.font_size_mode_var.get() == "force":
        label.grid(row=lr, column=0, sticky="w", padx=5, pady=5)
        entry.grid(row=lr, column=1, sticky="w", padx=5, pady=5)
    else:
        label.grid_remove()
        entry.grid_remove()


def on_toggle_stories_bg_widgets(app):
    """Affiche soit le sélecteur de couleur, soit le sélecteur d'image."""
    row = app.stories_bg_row

    # Cacher tout d'abord
    app.stories_bg_color_frame.grid_remove()
    app.stories_bg_image_frame.grid_remove()
    app.stories_alpha_frame.grid_remove()

    if app.stories_bg_type_var.get() == "color":
        app.stories_bg_color_frame.grid(row=row, column=1, sticky="w", padx=5, pady=5)
    else:  # "image"
        app.stories_bg_image_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        app.stories_alpha_frame.grid(row=row + 1, column=1, sticky="ew", padx=5, pady=5)


def on_update_stories_alpha_label(app):
    """Met à jour le label de pourcentage du slider alpha des stories."""
    app.stories_alpha_value_label.config(text=f"{int(app.stories_alpha_var.get() * 100)}%")


def on_toggle_cucaracha_widgets(app):
    """Affiche ou cache les options de la boîte Cucaracha."""
    widgets_to_hide = [
        app.cucaracha_text_widget,
        app.cucaracha_font_frame,
        app.cucaracha_image_entry,
        app.cucaracha_image_button,
        app.cucaracha_preview
    ]
    for widget in widgets_to_hide:
        widget.grid_remove()

    ctype = app.cucaracha_type_var.get()
    if ctype == "text":
        app.cucaracha_text_widget.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        app.cucaracha_font_frame.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=5)

    elif ctype == "image":
        app.cucaracha_image_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        app.cucaracha_image_button.grid(row=1, column=2, padx=5)
        app.cucaracha_preview.grid(row=2, column=1, sticky="w", pady=5)


def on_toggle_date_sep_options(app):
    """Affiche ou cache les sélecteurs de couleur pour la date box."""
    lr = app.date_box_colors_row
    if app.date_separator_var.get() == "box":
        app.date_box_colors_frame.grid(row=lr, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    else:
        app.date_box_colors_frame.grid_remove()


def on_toggle_alpha_slider(app):
    """Affiche ou cache le slider de transparence du poster."""
    lr = app.alpha_slider_row
    if app.poster_design_var.get() == 1:  # Image en fond
        app.alpha_label.grid(row=lr, column=0, sticky="w", padx=5, pady=5)
        app.alpha_scale_frame.grid(row=lr, column=1, sticky="ew", padx=5, pady=5)
    else:
        app.alpha_label.grid_remove()
        app.alpha_scale_frame.grid_remove()


def on_update_alpha_label(app):
    """Met à jour le label de pourcentage du slider."""
    app.alpha_value_label.config(text=f"{int(app.alpha_var.get() * 100)}%")


# ✨ NOUVELLE FONCTION : Toggle des boutons config et widgets debug-only
def on_toggle_config_buttons(app):
    """Affiche/cache les boutons config et les widgets avancés selon mode debug.

    En mode normal, les paramètres suivants sont cachés et utilisent
    les valeurs par défaut de config.yml :
    - Path ours (section complète)
    - Path logos (section complète)
    - Avec couv' (checkbox)
    - Marge globale (mm)
    - Espace avant/après dates (pt)
    """
    is_debug = app.debug_mode_var.get()

    # --- Boutons import/reset config ---
    if is_debug:
        app.config_buttons_frame.pack(pady=(5, 0))
    else:
        app.config_buttons_frame.pack_forget()

    # --- Widgets debug-only ---
    debug_only_frames = [app.ours_frame, app.logos_frame]
    debug_only_widgets = [
        app.cover_checkbox,
        app.margin_label, app.margin_entry,
        app.date_spacing_label, app.date_spacing_entry,
    ]

    if is_debug:
        for frame in debug_only_frames:
            if frame is not None:
                frame.grid()
        for widget in debug_only_widgets:
            if widget is not None:
                widget.grid()
    else:
        for frame in debug_only_frames:
            if frame is not None:
                frame.grid_remove()
        for widget in debug_only_widgets:
            if widget is not None:
                widget.grid_remove()


# ✨ NOUVEAU v1.4.2 : Callbacks pour les abréviations
def on_abbrev_select_all(app):
    """Active toutes les abréviations."""
    for var in app.abbreviation_vars.values():
        var.set(True)


def on_abbrev_deselect_all(app):
    """Désactive toutes les abréviations."""
    for var in app.abbreviation_vars.values():
        var.set(False)


def on_drop_input_file(app, event):
    """Callback exécuté lorsqu'un fichier est déposé sur le champ d'entrée."""
    file_path = event.data.strip()
    if file_path.startswith('{') and file_path.endswith('}'):
        file_path = file_path[1:-1]

    if not os.path.exists(file_path):
        messagebox.showerror("Erreur", f"Le fichier déposé n'a pas pu être trouvé :\n{file_path}")
        return

    app.input_var.set(file_path)
    _update_drop_zone_text(app, file_path)

    d = _default_paths_from_input(file_path)

    app.html_var.set(d["html"])
    app.agenda_var.set(d["agenda_html"])
    app.pdf_var.set(d["pdf"])
    app.svg_output_var.set(d["svg_output_dir"])
    app.stories_output_var.set(d["stories_output"])


def on_drop_cover_file(app, event):
    """Callback pour une image de couverture déposée."""
    file_path = event.data.strip()
    if file_path.startswith('{') and file_path.endswith('}'):
        file_path = file_path[1:-1]

    if not os.path.exists(file_path):
        return

    app.cover_var.set(file_path)
    _update_cover_drop_zone(app, file_path)


def on_pick_cover_file(app):
    """Callback pour le bouton 'Choisir une image...' de la couverture."""
    file_path = filedialog.askopenfilename(
        title="Image de couverture",
        filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.webp"), ("Tous", "*.*")]
    )
    if not file_path:
        return

    app.cover_var.set(file_path)
    _update_cover_drop_zone(app, file_path)


def _update_drop_zone_text(app, file_path: str | None):
    """Met à jour le texte de la zone de dépôt."""
    if file_path and os.path.exists(file_path):
        filename = os.path.basename(file_path)
        app.drop_zone_label.config(text=f"Fichier sélectionné :\n{filename}", font=("Arial", 10, "bold"))
    else:
        app.drop_zone_label.config(text="Glissez-déposez votre fichier (XLS/CSV) ici", font=("Arial", 12))


def _update_cover_drop_zone(app, file_path: str | None):
    """Met à jour le texte et l'aperçu de la zone de dépôt de la couverture."""
    if file_path and os.path.exists(file_path):
        filename = os.path.basename(file_path)
        app.cover_drop_zone_label.config(text=f"Fichier :\n{filename}")
        _update_preview(file_path, app.cover_preview)
    else:
        app.cover_drop_zone_label.config(text="Glissez-déposez l'image de couverture ici")
        _update_preview(None, app.cover_preview)


def _update_preview(path, preview_widget):
    """Met à jour un widget d'aperçu avec une miniature de l'image spécifiée."""
    if not path or not os.path.exists(path):
        preview_widget.config(image=None, text="Aucune image")
        preview_widget.image = None
        return

    try:
        with Image.open(path) as img:
            img.thumbnail((150, 150))
            tk_image = ImageTk.PhotoImage(img)

            preview_widget.config(image=tk_image, text="")
            preview_widget.image = tk_image
    except Exception as e:
        preview_widget.config(image=None, text="Fichier invalide")
        preview_widget.image = None
        print(f"[WARN] Impossible de créer la miniature pour {path}: {e}")
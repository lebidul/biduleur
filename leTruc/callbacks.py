# leTruc/callbacks.py
# -*- coding: utf-8 -*-
import os
from tkinter import filedialog, messagebox, colorchooser
from PIL import Image, ImageTk

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

    app.ours_button.config(command=lambda: on_pick_image_with_preview(app, app.ours_png_var,
                                                                      app.ours_preview,
                                                                      "Image de fond pour l'Ours (PNG)",
                                                                      [("Images", "*.png;*.jpg;*.jpeg"),
                                                                       ("Tous", "*.*")]))
    app.logos_button.config(command=lambda: on_pick_directory(app.logos_var, "Dossier des logos"))

    app.cucaracha_image_button.config(command=lambda: on_pick_image_with_preview(app, app.cucaracha_value_var,
                                                                                 app.cucaracha_preview,
                                                                                 "Choisir une image",
                                                                                 [("Images", "*.jpg *.jpeg *.png")]))

    app.cover_button.config(command=lambda: on_pick_image_with_preview(app, app.cover_var, app.cover_preview,
                                                                       "Image de couverture",
                                                                       [("Images", "*.jpg;*.jpeg;*.png;*.tif;*.webp"),
                                                                        ("Tous", "*.*")]))

    app.html_save_button.config(command=lambda: on_pick_save(app.html_var, "HTML", ".html", [("HTML", "*.html")]))
    app.agenda_save_button.config(
        command=lambda: on_pick_save(app.agenda_var, "HTML Agenda", ".html", [("HTML", "*.html")]))
    app.pdf_save_button.config(command=lambda: on_pick_save(app.pdf_var, "PDF", ".pdf", [("PDF", "*.pdf")]))
    app.svg_save_button.config(
        command=lambda: on_pick_save(app.svg_var, "Enregistrer le SVG", ".svg", [("SVG", "*.svg")]))
    app.stories_output_button.config(
        command=lambda: on_pick_directory(app.stories_output_var, "Choisir le dossier de sortie pour les Stories"))

    # Assigner la commande au bouton principal
    app.run_button.config(command=app._on_run)

    app.back_color_btn.config(command=lambda: on_pick_color(app.date_box_back_color_var))

    # --- Liaison des variables aux fonctions de "toggle" ---
    app.logos_layout_var.trace_add("write", lambda *args: on_toggle_padding_widget(app))
    app.font_size_mode_var.trace_add("write", lambda *args: on_toggle_font_size_widgets(app))
    app.cucaracha_type_var.trace_add("write", lambda *args: on_toggle_cucaracha_widgets(app))
    app.date_separator_var.trace_add("write", lambda *args: on_toggle_date_sep_options(app))
    app.poster_design_var.trace_add("write", lambda *args: on_toggle_alpha_slider(app))
    app.alpha_var.trace_add("write", lambda *args: on_update_alpha_label(app))

    # On ne trace plus la variable de la couleur de bordure.
    app.date_box_back_color_var.trace_add(
        "write",
        lambda *args: app.back_color_preview.config(bg=app.date_box_back_color_var.get())
    )

    # --- Appels initiaux pour définir l'état de l'interface au démarrage ---
    on_toggle_padding_widget(app)
    on_toggle_font_size_widgets(app)
    on_toggle_cucaracha_widgets(app)
    on_toggle_date_sep_options(app)
    on_toggle_alpha_slider(app)
    on_update_alpha_label(app)

    print("[INFO] Mise à jour des aperçus d'images au démarrage...")
    # On met à jour l'aperçu de l'ours si une valeur existe
    _update_preview(app.ours_png_var.get(), app.ours_preview)
    # On met à jour l'aperçu de la couverture si une valeur existe
    _update_preview(app.cover_var.get(), app.cover_preview)

# --- Fonctions de sélection de fichiers/dossiers ---

def on_pick_input(app):
    """Callback pour le bouton de sélection du fichier d'entrée."""
    file_path = filedialog.askopenfilename(
        title="Sélectionner l’entrée (CSV / XLS / XLSX)",
        filetypes=[("Excel", "*.xls;*.xlsx"), ("CSV", "*.csv"), ("Tous", "*.*")]
    )
    if not file_path: return
    app.input_var.set(file_path)
    d = _default_paths_from_input(file_path)
    app.html_var.set(d["html"])
    app.agenda_var.set(d["agenda_html"])
    app.pdf_var.set(d["pdf"])
    app.svg_var.set(d["svg"])
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
    Ouvre une boîte de dialogue pour choisir un fichier image, met à jour la
    variable et affiche une miniature dans le widget d'aperçu.
    """
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    if not path:
        return

    string_var.set(path)
    _update_preview(path, preview_widget)

    try:
        # Créer la miniature avec Pillow
        with Image.open(path) as img:
            # On définit la taille maximale de la miniature
            img.thumbnail((150, 150))
            # Convertir l'image Pillow en image Tkinter
            tk_image = ImageTk.PhotoImage(img)

            # Mettre à jour le widget d'aperçu
            preview_widget.config(image=tk_image, text="")  # On retire le texte "Aucune image"
            # Garder une référence à l'image pour éviter qu'elle soit effacée !
            preview_widget.image = tk_image

    except Exception as e:
        # Si le fichier n'est pas une image valide, on affiche une erreur
        preview_widget.config(image=None, text=f"Erreur: {e}")
        preview_widget.image = None


# --- Fonctions de visibilité conditionnelle ("toggle") ---

def on_toggle_padding_widget(app):
    """Affiche ou cache le champ de marge des logos."""
    lr = app.logos_padding_row
    if app.logos_layout_var.get() == "optimise":
        app.logos_padding_label.grid(row=lr, column=0, sticky="e", padx=5, pady=5)
        app.logos_padding_entry.grid(row=lr, column=1, sticky="w")
    else:
        app.logos_padding_label.grid_remove()
        app.logos_padding_entry.grid_remove()


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


def on_toggle_cucaracha_widgets(app):
    """Affiche ou cache les options de la boîte Cucaracha."""
    widgets_to_hide = [
        app.cucaracha_text_entry, app.cucaracha_font_label, app.cucaracha_font_combo,
        app.cucaracha_image_entry, app.cucaracha_image_button, app.cucaracha_preview
    ]
    for widget in widgets_to_hide:
        widget.grid_remove()

    ctype = app.cucaracha_type_var.get()
    if ctype == "text":
        app.cucaracha_text_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        app.cucaracha_font_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)
        app.cucaracha_font_combo.grid(row=2, column=1, sticky="w", padx=5)
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


def _update_preview(path, preview_widget):
    """
    Met à jour un widget d'aperçu avec une miniature de l'image spécifiée.

    Args:
        path (str): Le chemin vers le fichier image.
        preview_widget (tk.Label): Le widget Label à mettre à jour.
    """
    if not path or not os.path.exists(path):
        preview_widget.config(image=None, text="Aucune image")
        preview_widget.image = None
        return

    try:
        # Créer la miniature avec Pillow
        with Image.open(path) as img:
            img.thumbnail((150, 150))
            tk_image = ImageTk.PhotoImage(img)

            # Mettre à jour le widget d'aperçu
            preview_widget.config(image=tk_image, text="")
            preview_widget.image = tk_image
    except Exception as e:
        # Si le fichier n'est pas une image valide
        preview_widget.config(image=None, text="Fichier invalide")
        preview_widget.image = None
        print(f"[WARN] Impossible de créer la miniature pour {path}: {e}")

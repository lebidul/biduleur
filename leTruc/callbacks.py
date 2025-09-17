# leTruc/callbacks.py
# -*- coding: utf-8 -*-
import os
from tkinter import filedialog, messagebox, colorchooser

# On importe les helpers qui contiennent la logique "métier"
from ._helpers import _default_paths_from_input, save_embedded_template


def assign_all(app):
    """
    Fonction principale qui assigne toutes les fonctions de callback
    aux widgets et variables de l'application.

    Args:
        app: L'instance principale de la classe Application.
    """
    # --- Assignation des commandes aux boutons ---
    app.input_button.config(command=lambda: on_pick_input(app))
    app.csv_template_button.config(
        command=lambda: save_embedded_template('tapage_template.csv', "Enregistrer le modèle CSV"))
    app.xlsx_template_button.config(
        command=lambda: save_embedded_template('tapage_template.xlsx', "Enregistrer le modèle XLSX"))

    app.ours_button.config(command=lambda: on_pick_file(app.ours_png_var, "Image de fond pour l'Ours (PNG)",
                                                        [("Images", "*.png;*.jpg;*.jpeg"), ("Tous", "*.*")]))
    app.logos_button.config(command=lambda: on_pick_directory(app.logos_var, "Dossier des logos"))

    app.cucaracha_image_button.config(
        command=lambda: on_pick_file(app.cucaracha_value_var, "Choisir une image", [("Images", "*.jpg *.jpeg *.png")]))

    app.cover_button.config(command=lambda: on_pick_file(app.cover_var, "Image de couverture",
                                                         [("Images", "*.jpg;*.jpeg;*.png;*.tif;*.webp"),
                                                          ("Tous", "*.*")]))

    app.html_save_button.config(command=lambda: on_pick_save(app.html_var, "HTML", ".html", [("HTML", "*.html")]))
    app.agenda_save_button.config(
        command=lambda: on_pick_save(app.agenda_var, "HTML Agenda", ".html", [("HTML", "*.html")]))
    app.pdf_save_button.config(command=lambda: on_pick_save(app.pdf_var, "PDF", ".pdf", [("PDF", "*.pdf")]))
    app.svg_save_button.config(
        command=lambda: on_pick_save(app.svg_var, "Enregistrer le SVG", ".svg", [("SVG", "*.svg")]))

    # --- Liaison des variables aux fonctions de "toggle" ---
    app.logos_layout_var.trace_add("write", lambda *args: on_toggle_padding_widget(app))
    app.cucaracha_type_var.trace_add("write", lambda *args: on_toggle_cucaracha_widgets(app))
    app.date_separator_var.trace_add("write", lambda *args: on_toggle_date_sep_options(app))
    app.poster_design_var.trace_add("write", lambda *args: on_toggle_alpha_slider(app))
    app.alpha_var.trace_add("write", lambda *args: on_update_alpha_label(app))

    # --- Appels initiaux pour définir l'état de l'interface au démarrage ---
    on_toggle_padding_widget(app)
    on_toggle_cucaracha_widgets(app)
    on_toggle_date_sep_options(app)
    on_toggle_alpha_slider(app)
    on_update_alpha_label(app)


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


def on_pick_color(color_var, preview_widget):
    """Ouvre le sélecteur de couleur et met à jour la variable et l'aperçu."""
    _, color_hex = colorchooser.askcolor(initialcolor=color_var.get())
    if color_hex:
        color_var.set(color_hex)
        preview_widget.config(bg=color_hex)


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


def on_toggle_cucaracha_widgets(app):
    """Affiche ou cache les options de la boîte Cucaracha."""
    widgets_to_hide = [
        app.cucaracha_text_entry, app.cucaracha_font_label, app.cucaracha_font_combo,
        app.cucaracha_image_entry, app.cucaracha_image_button
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
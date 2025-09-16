# bidul/gui.py
# -*- coding: utf-8 -*-
import os
import sys
import tkinter as tk
import subprocess
import threading
import queue

# ==================== DÉBUT DU BLOC DE DÉBOGAGE ====================
# PyInstaller définit la variable `frozen` à True quand le code s'exécute dans l'exe.
if getattr(sys, 'frozen', False):
    # On écrit dans un fichier log à côté de l'exécutable.
    log_path = os.path.join(os.path.dirname(sys.executable), 'debug_log.txt')
    with open(log_path, 'w') as f:
        f.write("--- DÉBUT DU LOG DE DÉBOGAGE ---\n")
        # sys._MEIPASS est le dossier temporaire où PyInstaller a tout décompressé.
        f.write(f"sys.frozen: {getattr(sys, 'frozen', False)}\n")
        f.write(f"sys.executable: {sys.executable}\n")
        f.write(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'Non défini')}\n")

        f.write("\n--- Contenu de sys.path ---\n")
        for p in sys.path:
            f.write(f"{p}\n")

        f.write("\n--- Contenu du dossier de l'exécutable ---\n")
        try:
            exe_dir = os.path.dirname(sys.executable)
            for item in os.listdir(exe_dir):
                f.write(f"{item}\n")
        except Exception as e:
            f.write(f"Erreur lors du listage du dossier : {e}\n")
# ==================== FIN DU BLOC DE DÉBOGAGE ====================


from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path
import importlib.resources as res

# --- import biduleur (HTML) ---
from biduleur.csv_utils import parse_bidul
from biduleur.format_utils import output_html_file

# # --- import misenpageur (PDF) ---
# try:
#     from misenpageur.misenpageur.config import Config
#     from misenpageur.misenpageur.layout import Layout
#     from misenpageur.misenpageur.pdfbuild import build_pdf
#     from misenpageur.misenpageur.svgbuild import build_svg
#     from misenpageur.misenpageur.layout_builder import build_layout_with_margins
# except Exception as e:
#     _IMPORT_ERR = e
# else:
#     _IMPORT_ERR = None


def _default_paths_from_input(input_file: str) -> dict:
    input_path = Path(input_file)
    base = input_path.stem
    folder = input_path.parent
    return {
        "html": str(folder / f"{base}.html"),
        "agenda_html": str(folder / f"{base}.agenda.html"),
        "pdf": str(folder / f"{base}.pdf"),
        "svg": str(folder / f"{base}.svg"),
    }

def get_resource_path(relative_path):
    """
    Retourne le chemin absolu vers une ressource, fonctionne en mode dev et packagé.
    """
    if getattr(sys, 'frozen', False):
        # Si l'application est "frozen" (packagée par PyInstaller)
        # sys._MEIPASS est le dossier temporaire où tout est décompressé.
        base_path = getattr(sys, '_MEIPASS')
    else:
        # En mode développement, la base est le dossier du script gui.py
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


def _project_defaults() -> dict:
    """
    Définit les chemins par défaut pour les fichiers de config et layout.
    Utilise get_resource_path pour être compatible avec PyInstaller.
    """
    # En mode packagé, la racine du projet est le dossier temporaire _MEIPASS
    repo_root = get_resource_path('.')

    # Les fichiers de config sont maintenant relatifs à cet emplacement
    cfg = get_resource_path(os.path.join("misenpageur", "config.yml"))
    lay = get_resource_path(os.path.join("misenpageur", "layout.yml"))

    return {"root": str(repo_root), "config": str(cfg), "layout": str(lay)}


def _load_cfg_defaults() -> dict:
    # On définit d'abord les valeurs par défaut au cas où tout échouerait.
    out = {
        "cover": "", "ours_background_png": "", "logos_dir": "", "auteur_couv": "",
        "auteur_couv_url": "", "skip_cover": False,
        "page_margin_mm": 1.0,
        "date_separator_type": "ligne", "date_spacing": "4",
        "poster_design": 0, "font_size_safety_factor": 0.98,
        "background_alpha": 0.85, "poster_title": "",
        "cucaracha_type": "none", "cucaracha_value": "", "cucaracha_text_font": "Arial"
    }

    # On essaie de lire les vraies valeurs par défaut depuis le config.yml
    try:
        # On tente l'import de Config uniquement ici.
        from misenpageur.misenpageur.config import Config

        defaults = _project_defaults()
        cfg = Config.from_yaml(defaults["config"])

        # Le reste de la logique est inchangé, mais maintenant elle est
        # protégée par le bloc try...except.
        out.update({
            "cover": cfg.cover_image or "",
            "logos_dir": cfg.logos_dir or "",
            "auteur_couv": getattr(cfg, "auteur_couv", "") or "",
            "auteur_couv_url": getattr(cfg, "auteur_couv_url", "") or "",
            "skip_cover": getattr(cfg, "skip_cover", False),
            "date_spacing": str(cfg.date_spaceBefore),
        })
        if isinstance(cfg.section_1, dict): out["ours_background_png"] = cfg.section_1.get("ours_background_png", "")
        if isinstance(cfg.pdf_layout, dict): out["page_margin_mm"] = cfg.pdf_layout.get("page_margin_mm", 1.0)
        if cfg.date_line.get("enabled", True):
            out["date_separator_type"] = "ligne"
        elif cfg.date_box.get("enabled", False):
            out["date_separator_type"] = "box"
        else:
            out["date_separator_type"] = "aucun"
        if isinstance(cfg.poster, dict):
            out.update({
                "poster_design": cfg.poster.get("design", 0),
                "font_size_safety_factor": cfg.poster.get("font_size_safety_factor", 0.98),
                "background_alpha": cfg.poster.get("background_image_alpha", 0.85),
                "poster_title": cfg.poster.get("title", "")
            })
        if isinstance(cfg.cucaracha_box, dict):
            out.update({
                "cucaracha_type": cfg.cucaracha_box.get("content_type", "none"),
                "cucaracha_value": cfg.cucaracha_box.get("content_value", ""),
                "cucaracha_text_font": cfg.cucaracha_box.get("text_font_name", "Arial")
            })
    except Exception as e:
        # Si l'import ou la lecture du fichier échoue, on affiche un avertissement
        # mais l'application peut continuer avec les valeurs par défaut.
        print(f"[WARN] Erreur lors de la lecture des défauts depuis config.yml : {e}")
        # On ne fait rien d'autre, la fonction retournera le 'out' initial.

    return out


def _ensure_parent_dir(path: str):
    if path: Path(path).parent.mkdir(parents=True, exist_ok=True)


def run_pipeline(
        input_file: str, generate_cover: bool, cover_image: str, ours_background_png: str, logos_dir: str,
        out_html: str, out_agenda_html: str, out_pdf: str, auteur_couv: str, auteur_couv_url: str,
        page_margin_mm: float, generate_svg: bool, out_svg: str, date_separator_type: str,
        date_spacing: float, poster_design: int, font_size_safety_factor: float, logos_padding_mm: float,
        background_alpha: float, poster_title: str, cucaracha_type: str, 
        cucaracha_value: str, cucaracha_text_font: str, logos_layout: str
) -> tuple[bool, str]:
    try:
        from misenpageur.misenpageur.config import Config
        from misenpageur.misenpageur.layout import Layout
        from misenpageur.misenpageur.pdfbuild import build_pdf
        from misenpageur.misenpageur.svgbuild import build_svg
        from misenpageur.misenpageur.layout_builder import build_layout_with_margins
    except Exception as e:
        import traceback
        # On retourne une erreur claire si l'import échoue
        return False, f"Erreur critique: Impossible de charger le module 'misenpageur'.\n\nDétails:\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}"

    final_layout_path = None
    report = {}
    try:
        for p in (out_html, out_agenda_html, out_pdf, out_svg):
            if p: _ensure_parent_dir(p)

        html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(input_file)
        output_html_file(html_body_bidul, original_file_name=input_file, output_filename=out_html)
        output_html_file(html_body_agenda, original_file_name=input_file, output_filename=out_agenda_html)

        defaults = _project_defaults()
        project_root, cfg_path, lay_path = defaults["root"], defaults["config"], defaults["layout"]
        cfg = Config.from_yaml(cfg_path)

        cfg.project_root = project_root

        cfg.input_html = out_html
        cfg.skip_cover = not generate_cover
        if out_pdf: cfg.output_pdf = out_pdf
        if (cover_image or "").strip(): cfg.cover_image = cover_image.strip()
        if (ours_background_png or "").strip(): cfg.section_1['ours_background_png'] = ours_background_png.strip()
        if (logos_dir or "").strip(): cfg.logos_dir = logos_dir.strip()
        if (auteur_couv or "").strip(): cfg.auteur_couv = auteur_couv.strip()
        if (auteur_couv_url or "").strip(): cfg.auteur_couv_url = auteur_couv_url.strip()
        cfg.pdf_layout['page_margin_mm'] = page_margin_mm
        cfg.logos_layout = logos_layout
        cfg.logos_padding_mm = logos_padding_mm
        cfg.date_line['enabled'] = (date_separator_type == "ligne")
        cfg.date_box['enabled'] = (date_separator_type == "box")
        cfg.date_spaceBefore = date_spacing
        cfg.date_spaceAfter = date_spacing
        cfg.poster['design'] = poster_design
        cfg.poster['font_size_safety_factor'] = font_size_safety_factor
        cfg.poster['background_image_alpha'] = background_alpha
        cfg.poster['title'] = poster_title
        cfg.cucaracha_box['content_type'] = cucaracha_type
        cfg.cucaracha_box['content_value'] = cucaracha_value
        cfg.cucaracha_box['text_font_name'] = cucaracha_text_font

        final_layout_path = build_layout_with_margins(lay_path, cfg)
        lay = Layout.from_yaml(final_layout_path)

        if out_pdf:
            report = build_pdf(project_root, cfg, lay, out_pdf, cfg_path)
        if generate_svg and out_svg:
            if not report:
                report = build_pdf(project_root, cfg, lay, os.devnull, cfg_path)
            build_svg(project_root, cfg, lay, out_svg, cfg_path)

        summary_lines = [
            f"Fichier d'entrée : {os.path.basename(input_file)}", "-" * 40, "Fichiers de sortie créés :"
        ]
        if out_html: summary_lines.append(f"  - HTML: {out_html}")
        if out_agenda_html: summary_lines.append(f"  - HTML (Agenda): {out_agenda_html}")
        if out_pdf: summary_lines.append(f"  - PDF: {out_pdf}")
        if generate_svg and out_svg: summary_lines.append(f"  - SVG (éditable): {out_svg}")
        summary_lines.append("\n" + "-" * 40)
        summary_lines.append(f"Nombre d'événements traités : {number_of_lines}")
        fs_main = report.get("font_size_main")
        if fs_main: summary_lines.append(f"Taille de police (pages 1-2): {fs_main:.2f} pt")
        fs_poster = report.get("font_size_poster_final")
        if fs_poster:
            fs_poster_opt = report.get("font_size_poster_optimal", 0)
            summary_lines.append(
                f"Taille de police (poster)    : {fs_poster:.2f} pt (optimale: {fs_poster_opt:.2f} pt)")

        return True, "\n".join(summary_lines)

    except Exception as e:
        import traceback
        return False, f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
    finally:
        if final_layout_path and os.path.exists(final_layout_path) and Path(final_layout_path).name.endswith(".yml"):
            try:
                os.remove(final_layout_path)
            except OSError:
                pass

def open_file(filepath):
    """Ouvre un fichier avec l'application par défaut du système."""
    if not filepath or not os.path.exists(filepath):
        print(f"[WARN] Impossible d'ouvrir le fichier, il n'existe pas : {filepath}")
        return
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin": # macOS
            subprocess.run(["open", filepath])
        else: # Linux
            subprocess.run(["xdg-open", filepath])
    except Exception as e:
        messagebox.showwarning("Ouverture impossible", f"Impossible d'ouvrir le fichier automatiquement:\n{e}")


def main():
    """
    Initialise et lance l'interface graphique principale de l'application.

    Cette fonction configure la fenêtre, met en place une structure de contenu
    scrollable, crée tous les widgets de l'interface, et gère la logique
    d'exécution des tâches en arrière-plan (threading).
    """

    # --- 1. Configuration de la Fenêtre Principale ---
    root = tk.Tk()
    root.title("Bidul – Pipeline XLS/CSV → HTMLs → PDF")
    root.geometry("900x900")  # Taille de départ

    # Configure la grille de la fenêtre principale pour qu'elle s'étende
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)  # La zone scrollable prendra toute la hauteur
    root.rowconfigure(1, weight=0)  # La barre d'action reste en bas
    root.rowconfigure(2, weight=0)  # La barre de statut reste en bas

    # --- 2. Chargement des configurations et initialisation des variables ---
    cfg_defaults = _load_cfg_defaults()

    # Déclaration de toutes les variables Tkinter qui contiendront l'état de l'interface
    input_var = tk.StringVar()
    ours_png_var = tk.StringVar(value=cfg_defaults.get("ours_background_png", ""))
    logos_var = tk.StringVar(value=cfg_defaults.get("logos_dir", ""))
    generate_cover_var = tk.BooleanVar(value=not cfg_defaults.get("skip_cover", False))
    cover_var = tk.StringVar(value=cfg_defaults.get("cover", ""))
    auteur_var = tk.StringVar(value=cfg_defaults.get("auteur_couv", ""))
    auteur_url_var = tk.StringVar(value=cfg_defaults.get("auteur_couv_url", ""))
    margin_var = tk.StringVar(value=str(cfg_defaults.get("page_margin_mm", "1.0")))
    date_separator_var = tk.StringVar(value=cfg_defaults.get("date_separator_type", "ligne"))
    date_spacing_var = tk.StringVar(value=cfg_defaults.get("date_spacing", "4"))
    poster_title_var = tk.StringVar(value=cfg_defaults.get("poster_title", ""))
    poster_design_var = tk.IntVar(value=cfg_defaults.get("poster_design", 0))
    safety_factor_var = tk.StringVar(value=str(cfg_defaults.get("font_size_safety_factor", "0.98")))
    alpha_var = tk.DoubleVar(value=cfg_defaults.get("background_alpha", 0.85))
    cucaracha_type_var = tk.StringVar(value=cfg_defaults.get("cucaracha_type", "none"))
    cucaracha_value_var = tk.StringVar(value=cfg_defaults.get("cucaracha_value", ""))
    cucaracha_font_var = tk.StringVar(value=cfg_defaults.get("cucaracha_text_font", "Arial"))
    html_var, agenda_var, pdf_var, svg_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
    generate_svg_var = tk.BooleanVar(value=True)
    logos_layout_var = tk.StringVar(value="colonnes")
    logos_padding_var = tk.StringVar(value="1.0")

    def pick_input():
        file_path = filedialog.askopenfilename(title="Sélectionner l’entrée (CSV / XLS / XLSX)",
                                               filetypes=[("Excel", "*.xls;*.xlsx"), ("CSV", "*.csv"), ("Tous", "*.*")])
        if not file_path: return
        input_var.set(file_path)
        d = _default_paths_from_input(file_path)
        html_var.set(d["html"])
        agenda_var.set(d["agenda_html"])
        pdf_var.set(d["pdf"])
        svg_var.set(d["svg"])

    def pick_cover():
        path = filedialog.askopenfilename(title="Image de couverture",
                                          filetypes=[("Images", "*.jpg;*.jpeg;*.png;*.tif;*.webp"), ("Tous", "*.*")])
        if path: cover_var.set(path)

    def pick_ours_png():
        path = filedialog.askopenfilename(title="Image de fond pour l'Ours (PNG)",
                                          filetypes=[("Images", "*.png;*.jpg;*.jpeg"), ("Tous", "*.*")])
        if path: ours_png_var.set(path)

    def pick_logos():
        path = filedialog.askdirectory(title="Dossier des logos")
        if path: logos_var.set(path)

    def pick_file(entry_var):
        path = filedialog.askopenfilename(title="Choisir une image", filetypes=[("Images", "*.jpg *.jpeg *.png")])
        if path: entry_var.set(path)

    def pick_save(var, title, ext, ftypes):
        path = filedialog.asksaveasfilename(title=title, defaultextension=ext, filetypes=ftypes)
        if path: var.set(path)

    def save_embedded_template(filename, title):
        ext = os.path.splitext(filename)[1].lower()
        ftypes = [("Excel", "*.xlsx")] if ext == '.xlsx' else [("CSV", "*.csv")]
        target = filedialog.asksaveasfilename(title=title, defaultextension=ext, filetypes=ftypes, initialfile=filename)
        if not target: return
        try:
            data = res.files('biduleur.templates').joinpath(filename).read_bytes()
            with open(target, "wb") as f:
                f.write(data)
            messagebox.showinfo("Modèle enregistré", f"Fichier enregistré ici :\n{target}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer le modèle : {e}")

    # --- 4. Mise en place de la structure scrollable ---
    # Cette structure est essentielle pour la responsivité.
    container = ttk.Frame(root)
    container.grid(row=0, column=0, sticky="nsew")
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)

    canvas = tk.Canvas(container)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    canvas_frame_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    def on_frame_configure(event):
        """Met à jour la région de scroll quand la taille du contenu change."""
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_configure(event):
        """Ajuste la largeur du contenu à la largeur de la fenêtre."""
        canvas.itemconfig(canvas_frame_id, width=event.width)

    def on_mousewheel(event):
        """Permet de scroller avec la molette de la souris."""
        scroll_amount = -1 * (event.delta // 120)
        canvas.yview_scroll(scroll_amount, "units")

    scrollable_frame.bind("<Configure>", on_frame_configure)
    canvas.bind("<Configure>", on_canvas_configure)
    root.bind_all("<MouseWheel>", on_mousewheel)
    root.bind_all("<Button-4>", lambda e: on_mousewheel(type('obj', (object,), {'delta': 120})()))
    root.bind_all("<Button-5>", lambda e: on_mousewheel(type('obj', (object,), {'delta': -120})()))

    # --- 5. Création des widgets de l'interface ---
    # Tous les widgets de formulaire sont placés dans le 'scrollable_frame'.
    main_frame = scrollable_frame
    main_frame.columnconfigure(1, weight=1)
    r = 0  # Compteur de ligne pour la grille principale du contenu

    # Section: Fichier d'entrée
    tk.Label(main_frame, text="Fichier d’entrée (CSV / XLS) :").grid(row=r, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(main_frame, textvariable=input_var).grid(row=r, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(main_frame, text="Parcourir…", command=pick_input).grid(row=r, column=2, padx=5, pady=5)
    r += 1
    models_frame = ttk.Frame(main_frame)
    models_frame.grid(row=r, column=1, columnspan=2, sticky="w", padx=5, pady=(0, 10))
    tk.Label(models_frame, text="Télécharger un modèle :").pack(side=tk.LEFT, anchor=tk.W)
    tk.Button(models_frame, text="Modèle CSV",
              command=lambda: save_embedded_template('tapage_template.csv', "Enregistrer le modèle CSV")).pack(
        side=tk.LEFT, padx=5)
    tk.Button(models_frame, text="Modèle XLSX",
              command=lambda: save_embedded_template('tapage_template.xlsx', "Enregistrer le modèle XLSX")).pack(
        side=tk.LEFT, padx=5)
    r += 1
    ttk.Separator(main_frame, orient='horizontal').grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    r += 1

    # Section: Ours
    tk.Label(main_frame, text="Ours (Image de fond PNG) :").grid(row=r, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(main_frame, textvariable=ours_png_var).grid(row=r, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(main_frame, text="Parcourir…", command=pick_ours_png).grid(row=r, column=2, padx=5, pady=5)
    r += 1

    # Section: Paramètres des Logos (Structurée correctement)
    logos_frame = ttk.LabelFrame(main_frame, text="Paramètres des Logos", padding="10")
    logos_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    logos_frame.columnconfigure(1, weight=1)
    r += 1

    lr = 0  # Compteur de ligne local pour l'intérieur du 'logos_frame'
    tk.Label(logos_frame, text="Dossier logos :").grid(row=lr, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(logos_frame, textvariable=logos_var).grid(row=lr, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(logos_frame, text="Parcourir…", command=pick_logos).grid(row=lr, column=2, padx=5, pady=5)
    lr += 1
    tk.Label(logos_frame, text="Répartition :").grid(row=lr, column=0, sticky="e", padx=5, pady=5)
    logos_layout_radios = ttk.Frame(logos_frame)
    logos_layout_radios.grid(row=lr, column=1, columnspan=2, sticky="w")

    logos_padding_label = tk.Label(logos_frame, text="Marge (mm) :")
    logos_padding_entry = tk.Entry(logos_frame, textvariable=logos_padding_var, width=10)

    def toggle_padding_widget(*args):
        """Affiche ou cache le champ de marge en fonction du choix de répartition."""
        if logos_layout_var.get() == "optimise":
            logos_padding_label.grid(row=lr + 1, column=0, sticky="e", padx=5, pady=5)
            logos_padding_entry.grid(row=lr + 1, column=1, sticky="w")
        else:
            logos_padding_label.grid_remove()
            logos_padding_entry.grid_remove()

    tk.Radiobutton(logos_layout_radios, text="2 Colonnes", variable=logos_layout_var, value="colonnes",
                   command=toggle_padding_widget).pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(logos_layout_radios, text="Optimisée", variable=logos_layout_var, value="optimise",
                   command=toggle_padding_widget).pack(side=tk.LEFT, padx=5)
    toggle_padding_widget()

    # Section: Cucaracha
    cucaracha_frame = ttk.LabelFrame(main_frame, text="Boîte 'Cucaracha'", padding="10")
    cucaracha_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    r += 1

    cucaracha_frame.columnconfigure(1, weight=1)
    cucaracha_text_entry = tk.Entry(cucaracha_frame, textvariable=cucaracha_value_var)
    cucaracha_font_label = tk.Label(cucaracha_frame, text="Police :")
    cucaracha_font_combo = ttk.Combobox(cucaracha_frame, textvariable=cucaracha_font_var,
                                        values=["Arial", "Helvetica", "Times", "Courier"], state="readonly")
    cucaracha_image_entry = tk.Entry(cucaracha_frame, textvariable=cucaracha_value_var)
    cucaracha_image_btn = tk.Button(cucaracha_frame, text="Parcourir…", command=lambda: pick_file(cucaracha_value_var))

    def toggle_cucaracha_widgets(*args):
        for widget in [cucaracha_text_entry, cucaracha_font_label, cucaracha_font_combo, cucaracha_image_entry,
                       cucaracha_image_btn]:
            widget.grid_remove()
        ctype = cucaracha_type_var.get()
        if ctype == "text":
            cucaracha_text_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
            cucaracha_font_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)
            cucaracha_font_combo.grid(row=2, column=1, sticky="w", padx=5)
        elif ctype == "image":
            cucaracha_image_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
            cucaracha_image_btn.grid(row=1, column=2, padx=5)

    radio_frame = ttk.Frame(cucaracha_frame)
    radio_frame.grid(row=0, column=0, columnspan=3, sticky="w")
    tk.Radiobutton(radio_frame, text="Rien", variable=cucaracha_type_var, value="none",
                   command=toggle_cucaracha_widgets).pack(side=tk.LEFT)
    tk.Radiobutton(radio_frame, text="Texte", variable=cucaracha_type_var, value="text",
                   command=toggle_cucaracha_widgets).pack(side=tk.LEFT)
    tk.Radiobutton(radio_frame, text="Image", variable=cucaracha_type_var, value="image",
                   command=toggle_cucaracha_widgets).pack(side=tk.LEFT)
    toggle_cucaracha_widgets()

    r += 1
    cover_frame = ttk.LabelFrame(main_frame, text="Informations de couverture", padding="10")
    cover_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    r += 1
    cover_frame.columnconfigure(1, weight=1)
    tk.Checkbutton(cover_frame, text="Avec couv' (générer la page de couverture)", variable=generate_cover_var).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=2)
    tk.Label(cover_frame, text="Image de Couverture :").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(cover_frame, textvariable=cover_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(cover_frame, text="Parcourir…", command=pick_cover).grid(row=1, column=2, padx=5, pady=5)
    tk.Label(cover_frame, text="Auteur Couverture :").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(cover_frame, textvariable=auteur_var).grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
    tk.Label(cover_frame, text="URL auteur couverture :").grid(row=3, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(cover_frame, textvariable=auteur_url_var).grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=5)

    r += 1
    page_layout_frame = ttk.LabelFrame(main_frame, text="Mise en Page Globale", padding="10")
    page_layout_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    page_layout_frame.columnconfigure(1, weight=1)
    tk.Label(page_layout_frame, text="Marge globale (mm) :").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(page_layout_frame, textvariable=margin_var, width=10).grid(row=0, column=1, sticky="w", padx=5, pady=5)

    r += 1
    date_sep_frame = ttk.LabelFrame(main_frame, text="Séparateur de dates", padding="10")
    date_sep_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    date_sep_frame.columnconfigure(1, weight=1)
    tk.Label(date_sep_frame, text="Type de séparateur :").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    date_sep_radios = ttk.Frame(date_sep_frame)
    date_sep_radios.grid(row=0, column=1, sticky="w", padx=5, pady=5)
    tk.Radiobutton(date_sep_radios, text="Aucun", variable=date_separator_var, value="aucun").pack(side=tk.LEFT)
    tk.Radiobutton(date_sep_radios, text="Ligne", variable=date_separator_var, value="ligne").pack(side=tk.LEFT,
                                                                                                   padx=10)
    tk.Radiobutton(date_sep_radios, text="Box", variable=date_separator_var, value="box").pack(side=tk.LEFT)
    tk.Label(date_sep_frame, text="Espace avant/après date (pt) :").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(date_sep_frame, textvariable=date_spacing_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=5)

    r += 1
    layout_frame = ttk.LabelFrame(main_frame, text="Paramètres de mise en page (Poster)", padding="10")
    layout_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    layout_frame.columnconfigure(1, weight=1)
    tk.Label(layout_frame, text="Titre du poster :").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(layout_frame, textvariable=poster_title_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(layout_frame, text="Design du poster :").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    design_frame = ttk.Frame(layout_frame)
    design_frame.grid(row=1, column=1, sticky="w", padx=5, pady=5)
    alpha_label = tk.Label(layout_frame, text="Transparence du fond :")
    alpha_scale_frame = ttk.Frame(layout_frame)
    alpha_scale = ttk.Scale(alpha_scale_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=alpha_var)
    alpha_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
    alpha_value_label = ttk.Label(alpha_scale_frame, text=f"{int(alpha_var.get() * 100)}%")
    alpha_value_label.pack(side=tk.LEFT, padx=(5, 0))

    def update_alpha_label(*args):
        alpha_value_label.config(text=f"{int(alpha_var.get() * 100)}%")

    alpha_var.trace_add("write", update_alpha_label)

    def toggle_alpha_slider(*args):
        if poster_design_var.get() == 1:
            alpha_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)
            alpha_scale_frame.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        else:
            alpha_label.grid_remove()
            alpha_scale_frame.grid_remove()

    tk.Radiobutton(design_frame, text="Image au centre", variable=poster_design_var, value=0,
                   command=toggle_alpha_slider).pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(design_frame, text="Image en fond", variable=poster_design_var, value=1,
                   command=toggle_alpha_slider).pack(side=tk.LEFT, padx=5)

    tk.Label(layout_frame, text="Facteur de sécurité police :").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(layout_frame, textvariable=safety_factor_var, width=10).grid(row=3, column=1, sticky="w", padx=5, pady=5)

    toggle_alpha_slider()

    r += 1
    output_frame = ttk.LabelFrame(main_frame, text="Fichiers de sortie", padding="10")
    output_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    output_frame.columnconfigure(1, weight=1)
    tk.Label(output_frame, text="HTML (biduleur/moulinette) :").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=html_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(output_frame, text="…", width=3,
              command=lambda: pick_save(html_var, "HTML", ".html", [("HTML", "*.html")])).grid(row=0, column=2, padx=5,
                                                                                               pady=5)
    tk.Label(output_frame, text="HTML Agenda :").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=agenda_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(output_frame, text="…", width=3,
              command=lambda: pick_save(agenda_var, "HTML Agenda", ".html", [("HTML", "*.html")])).grid(row=1, column=2,
                                                                                                        padx=5, pady=5)
    tk.Label(output_frame, text="PDF (le Bidul) :").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=pdf_var).grid(row=2, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(output_frame, text="…", width=3,
              command=lambda: pick_save(pdf_var, "PDF", ".pdf", [("PDF", "*.pdf")])).grid(row=2, column=2, padx=5,
                                                                                          pady=5)
    tk.Checkbutton(output_frame, text="Générer un SVG éditable (pour Inkscape)", variable=generate_svg_var).grid(row=3,
                                                                                                                 column=0,
                                                                                                                 columnspan=3,
                                                                                                                 sticky="w",
                                                                                                                 padx=5,
                                                                                                                 pady=5)
    tk.Label(output_frame, text="Nom de base SVG :").grid(row=4, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=svg_var).grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(output_frame, text="…", width=3,
              command=lambda: pick_save(svg_var, "Enregistrer le SVG", ".svg", [("SVG", "*.svg")])).grid(row=4,
                                                                                                         column=2,
                                                                                                         padx=5, pady=5)

    # --- 6. Logique d'exécution (Threading) ---
    status = tk.StringVar(value="Prêt.")
    result_queue = queue.Queue()

    # NOUVEAU : La fonction qui exécute la tâche lourde
    def run_pipeline_in_thread(margin_val, safety_factor_val, date_spacing_val, logos_padding_val, poster_title_val, cuca_value_val):
        """Wrapper pour exécuter run_pipeline et mettre le résultat dans la queue."""
        inp = input_var.get().strip()
        if not inp:
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d’entrée.")
            return
        try:
            margin_val = float(margin_var.get().strip().replace(',', '.'))
            safety_factor_val = float(safety_factor_var.get().strip().replace(',', '.'))
            date_spacing_val = float(date_spacing_var.get().strip().replace(',', '.'))
        except ValueError:
            result_queue.put(
                (False, "La marge, l'espacement et le facteur de sécurité doivent être des nombres valides."))
            return

        ok, msg = run_pipeline(
            input_file=inp,
            generate_cover=generate_cover_var.get(),
            cover_image=cover_var.get().strip(),
            ours_background_png=ours_png_var.get().strip(),
            logos_dir=logos_var.get().strip(),
            logos_layout=logos_layout_var.get(),
            logos_padding_mm=logos_padding_val, # <-- On utilise la valeur passée en argument
            out_html=html_var.get().strip(),
            out_agenda_html=agenda_var.get().strip(),
            out_pdf=pdf_var.get().strip(),
            auteur_couv=auteur_var.get().strip(),
            auteur_couv_url=auteur_url_var.get().strip(),
            page_margin_mm=margin_val,
            generate_svg=generate_svg_var.get(),
            out_svg=svg_var.get().strip(),
            date_separator_type=date_separator_var.get(),
            date_spacing=date_spacing_val,
            poster_design=poster_design_var.get(),
            font_size_safety_factor=safety_factor_val,
            background_alpha=alpha_var.get(),
            poster_title=poster_title_val,
            cucaracha_type=cucaracha_type_var.get(),
            cucaracha_value=cuca_value_val,
            cucaracha_text_font=cucaracha_font_var.get()
        )
        result_queue.put((ok, msg))

    # NOUVEAU : La fonction qui vérifie si le thread est terminé
    def check_thread_and_get_results():
        """Vérifie la queue pour le résultat. Si le thread est en cours, se replanifie."""
        try:
            # Essayer de récupérer le résultat sans bloquer
            ok, msg = result_queue.get(block=False)

            # Si on arrive ici, le thread est terminé
            progress_bar.stop()
            run_button.config(state=tk.NORMAL)

            if ok:
                messagebox.showinfo("Génération Terminée", msg)
                status.set("Terminé avec succès.")
                pdf_path = pdf_var.get().strip()
                if pdf_path and os.path.exists(pdf_path):
                    # MODIFIÉ : On demande à l'utilisateur avant d'ouvrir
                    if messagebox.askyesno("Ouvrir le fichier ?", "Voulez-vous ouvrir le PDF généré maintenant ?"):
                        open_file(pdf_path)
            else:
                messagebox.showerror("Erreur", msg)
                status.set("Échec.")

        except queue.Empty:
            # Si la queue est vide, le thread n'a pas fini. On revérifie dans 100ms.
            root.after(100, check_thread_and_get_results)

    # MODIFIÉ : run_now lance maintenant le thread et la vérification
    def run_now():
        inp = input_var.get().strip()
        if not inp:
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d’entrée.")
            return

        try:
            margin_val = float(margin_var.get().strip().replace(',', '.'))
            safety_factor_val = float(safety_factor_var.get().strip().replace(',', '.'))
            date_spacing_val = float(date_spacing_var.get().strip().replace(',', '.'))
            logos_padding_val = float(logos_padding_var.get().strip().replace(',', '.'))
        except ValueError:
            messagebox.showerror("Erreur",
                                 "La marge, l'espacement, le facteur de sécurité et la marge des logos doivent être des nombres valides.")
            return

        poster_title_val = poster_title_var.get().strip()
        if not poster_title_val:
            # On pourrait le rendre optionnel, mais pour l'instant on le garde obligatoire
            messagebox.showerror("Erreur", "Le titre du poster est obligatoire.")
            return

        cuca_value_val = cucaracha_value_var.get().strip()

        status.set("Traitement en cours…")
        progress_bar.start()
        run_button.config(state=tk.DISABLED)

        # Créer et démarrer le thread de travail en lui passant les arguments
        thread = threading.Thread(
            target=run_pipeline_in_thread,
            args=(
                margin_val, safety_factor_val, date_spacing_val,
                logos_padding_val, poster_title_val, cuca_value_val
            )
        )
        thread.daemon = True
        thread.start()

        # Lancer la première vérification
        root.after(100, check_thread_and_get_results)

    # --- 7. Barre d'actions et de statut (fixe) ---
    # Ces widgets sont enfants de 'root' pour ne pas scroller.
    action_frame = ttk.Frame(root, padding="10")
    action_frame.grid(row=1, column=0, sticky="ew")
    action_frame.columnconfigure(0, weight=1)

    progress_bar = ttk.Progressbar(action_frame, mode='indeterminate')
    progress_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

    run_button = tk.Button(action_frame, text="Lancer la Génération", command=run_now, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"))
    run_button.pack(pady=10, ipady=5)

    status_bar = tk.Label(root, textvariable=status, bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=10, pady=5, font=("Arial", 10))
    status_bar.grid(row=2, column=0, sticky="ew")

    # --- 8. Lancement de l'application ---
    root.mainloop()


if __name__ == "__main__":
    main()
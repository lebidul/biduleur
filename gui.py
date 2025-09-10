# bidul/gui.py
# -*- coding: utf-8 -*-
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path
import importlib.resources as res

# --- import biduleur (HTML) ---
from biduleur.csv_utils import parse_bidul
from biduleur.format_utils import output_html_file

# --- import misenpageur (PDF + Scribus) ---
try:
    from misenpageur.misenpageur.config import Config
    from misenpageur.misenpageur.layout import Layout
    from misenpageur.misenpageur.pdfbuild import build_pdf
    from misenpageur.misenpageur.scribus_export import write_scribus_script
    # ==================== IMPORT MANQUANT ====================
    # On importe la fonction qui applique les marges au layout
    from misenpageur.misenpageur.layout_builder import build_layout_with_margins
    # =======================================================
except Exception as e:
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None


# ... (fonctions _default_paths_from_input, _project_defaults, _load_cfg_defaults, _ensure_parent_dir inchangées) ...
def _default_paths_from_input(input_file: str) -> dict:
    base = os.path.splitext(os.path.basename(input_file))[0]
    folder = os.path.dirname(input_file) or "."
    return {
        "html": os.path.join(folder, f"{base}.html"),
        "agenda_html": os.path.join(folder, f"{base}.agenda.html"),
        "pdf": os.path.join(folder, f"{base}.pdf"),
        "scribus_py": os.path.join(folder, f"{base}.scribus.py"),
        "scribus_sla": os.path.join(folder, f"{base}.sla"),
    }


def _project_defaults() -> dict:
    repo_root = Path(__file__).resolve().parent
    cfg = repo_root / "misenpageur" / "config.yml"
    lay = repo_root / "misenpageur" / "layout.yml"
    return {"root": str(repo_root), "config": str(cfg), "layout": str(lay)}


def _load_cfg_defaults() -> dict:
    """Lit quelques valeurs par défaut depuis config.yml (si possible)."""
    out = {
        "cover": "", "ours_md": "", "logos_dir": "", "auteur_couv": "",
        "auteur_couv_url": "", "skip_cover": False,
        "page_margin_mm": 1.0, "date_line_enabled": True
    }
    if _IMPORT_ERR:
        return out
    try:
        defaults = _project_defaults()
        cfg = Config.from_yaml(defaults["config"])
        out["cover"] = cfg.cover_image or ""
        out["ours_md"] = cfg.ours_md or ""
        out["logos_dir"] = cfg.logos_dir or ""
        out["auteur_couv"] = getattr(cfg, "auteur_couv", "") or ""
        out["auteur_couv_url"] = getattr(cfg, "auteur_couv_url", "") or ""
        out["skip_cover"] = getattr(cfg, "skip_cover", False)
        # Charger les nouvelles valeurs si elles existent
        out["page_margin_mm"] = cfg.pdf_layout.get("page_margin_mm", 1.0)
        out["date_line_enabled"] = cfg.date_line.get("enabled", True)
    except Exception:
        pass
    return out


def _ensure_parent_dir(path: str):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def run_pipeline(input_file: str,
                 generate_cover: bool,
                 cover_image: str,
                 ours_md: str,
                 logos_dir: str,
                 out_html: str,
                 out_agenda_html: str,
                 out_pdf: str,
                 out_scribus_py: str,
                 auteur_couv: str,
                 auteur_couv_url: str,
                 page_margin_mm: float,
                 date_line_enabled: bool,
                 poster_design: int, # Ajouté
                 font_size_safety_factor: float # Ajouté
                 ) -> tuple[bool, str]:
    """
    Enchaîne : XLS/CSV -> (biduleur) -> 2 HTML -> (misenpageur) -> PDF (+ Scribus optionnel)
    """
    if _IMPORT_ERR:
        return False, f"Imports misenpageur impossibles : {repr(_IMPORT_ERR)}"

    # ==================== MODIFICATION DE LA LOGIQUE ====================
    final_layout_path = None  # Chemin du layout temporaire
    try:
        for p in (out_html, out_agenda_html, out_pdf, out_scribus_py):
            if p: _ensure_parent_dir(p)

        html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(input_file)
        output_html_file(html_body_bidul, original_file_name=input_file, output_filename=out_html)
        output_html_file(html_body_agenda, original_file_name=input_file, output_filename=out_agenda_html)

        defaults = _project_defaults()
        project_root, cfg_path, lay_path = defaults["root"], defaults["config"], defaults["layout"]

        cfg = Config.from_yaml(cfg_path)

        # 1. Appliquer les paramètres de la GUI à l'objet config AVANT de construire le layout
        cfg.skip_cover = not generate_cover
        cfg.input_html = out_html
        if out_pdf: cfg.output_pdf = out_pdf
        if (cover_image or "").strip(): cfg.cover_image = cover_image.strip()
        if (ours_md or "").strip(): cfg.ours_md = ours_md.strip()
        if (logos_dir or "").strip(): cfg.logos_dir = logos_dir.strip()
        if (auteur_couv or "").strip(): cfg.auteur_couv = auteur_couv.strip()
        if (auteur_couv_url or "").strip(): cfg.auteur_couv_url = auteur_couv_url.strip()
        cfg.poster['design'] = poster_design  # 0 ou 1
        cfg.pdf_layout['page_margin_mm'] = page_margin_mm
        cfg.date_line['enabled'] = date_line_enabled

        # 2. Construire le layout final avec les marges (LA CORRECTION EST ICI)
        final_layout_path = build_layout_with_margins(lay_path, cfg)
        lay = Layout.from_yaml(final_layout_path)

        # 3. Lancer la génération du PDF avec le layout corrigé
        build_pdf(project_root, cfg, lay, cfg.output_pdf)

        scribus_sla = ""
        if (out_scribus_py or "").strip():
            scribus_sla = os.path.splitext(out_scribus_py)[0] + ".sla"
            write_scribus_script(project_root, cfg, lay, out_scribus_py, scribus_sla)

        summary_lines = [
            f"HTML            : {out_html}", f"HTML (agenda)   : {out_agenda_html}",
            f"PDF             : {cfg.output_pdf}", f"Couverture générée : {'Oui' if generate_cover else 'Non'}",
            f"Marge globale   : {page_margin_mm} mm", f"Lignes de date  : {'Oui' if date_line_enabled else 'Non'}",
        ]
        if scribus_sla:
            summary_lines += [f"Scribus script  : {out_scribus_py}", f"SLA Scribus     : {scribus_sla}"]
        summary_lines += [f"\nÉvénements : {number_of_lines}"]
        return True, "\n".join(summary_lines)

    except Exception as e:
        import traceback
        return False, f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"

    finally:
        # 4. Nettoyer le fichier temporaire, même en cas d'erreur
        if final_layout_path and os.path.exists(final_layout_path):
            try:
                os.remove(final_layout_path)
            except OSError:
                pass


def main():
    root = tk.Tk()
    root.title("Bidul – Pipeline XLS/CSV → HTMLs → PDF (+ Scribus)")
    root.minsize(900, 750)  # Augmentation de la hauteur min

    # --- Configuration de la grille principale ---
    root.columnconfigure(0, weight=1)
    root.rowconfigure(5, weight=1)  # Ligne du statut

    # --- Préremplissages ---
    cfg_defaults = _load_cfg_defaults()

    # --- Variables Tkinter ---
    input_var = tk.StringVar()
    ours_var = tk.StringVar(value=cfg_defaults.get("ours_md", ""))
    logos_var = tk.StringVar(value=cfg_defaults.get("logos_dir", ""))

    # Couverture
    generate_cover_var = tk.BooleanVar(value=not cfg_defaults.get("skip_cover", False))
    cover_var = tk.StringVar(value=cfg_defaults.get("cover", ""))
    auteur_var = tk.StringVar(value=cfg_defaults.get("auteur_couv", ""))
    auteur_url_var = tk.StringVar(value=cfg_defaults.get("auteur_couv_url", ""))

    # Mise en page
    margin_var = tk.StringVar(value=str(cfg_defaults.get("page_margin_mm", "1.0")))
    date_line_var = tk.BooleanVar(value=cfg_defaults.get("date_line_enabled", True))

    # Design du poster
    poster_design_var = tk.IntVar(value=cfg_defaults.get("poster", {}).get("design", 0))  # 0 ou 1
    # Facteur de sécurité
    safety_factor_var = tk.StringVar(value=str(cfg_defaults.get("font_size_safety_factor", "0.98")))

    # Sorties
    html_var = tk.StringVar()
    agenda_var = tk.StringVar()
    pdf_var = tk.StringVar()
    scribus_py_var = tk.StringVar()

    # --- Helpers (inchangés) ---
    def pick_input():
        file_path = filedialog.askopenfilename(title="Sélectionner l’entrée (CSV / XLS / XLSX)",
                                               filetypes=[("Excel", "*.xls;*.xlsx"), ("CSV", "*.csv"), ("Tous", "*.*")])
        if not file_path: return
        input_var.set(file_path)
        d = _default_paths_from_input(file_path)
        html_var.set(d["html"]);
        agenda_var.set(d["agenda_html"]);
        pdf_var.set(d["pdf"]);
        scribus_py_var.set(d["scribus_py"])

    def pick_cover():
        path = filedialog.askopenfilename(title="Image de couverture",
                                          filetypes=[("Images", "*.jpg;*.jpeg;*.png;*.tif;*.webp"), ("Tous", "*.*")])
        if path: cover_var.set(path)

    def pick_ours():
        path = filedialog.askopenfilename(title="Fichier OURS (Markdown)",
                                          filetypes=[("Markdown", "*.md;*.markdown"), ("Texte", "*.txt"),
                                                     ("Tous", "*.*")])
        if path: ours_var.set(path)

    def pick_logos():
        path = filedialog.askdirectory(title="Dossier des logos")
        if path: logos_var.set(path)

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

    # --- Construction de l'UI par sections ---
    main_frame = ttk.Frame(root, padding="10")
    main_frame.grid(row=0, column=0, sticky="nsew")
    main_frame.columnconfigure(1, weight=1)

    r = 0  # Row counter for the main_frame grid

    # --- Section : Fichier d'entrée et Modèles ---
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

    # --- Section : Ours & Logos ---
    r += 1
    tk.Label(main_frame, text="Ours (Markdown) :").grid(row=r, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(main_frame, textvariable=ours_var).grid(row=r, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(main_frame, text="Parcourir…", command=pick_ours).grid(row=r, column=2, padx=5, pady=5)
    r += 1
    tk.Label(main_frame, text="Dossier logos :").grid(row=r, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(main_frame, textvariable=logos_var).grid(row=r, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(main_frame, text="Parcourir…", command=pick_logos).grid(row=r, column=2, padx=5, pady=5)

    # --- Section : Informations de couverture ---
    r += 1
    cover_frame = ttk.LabelFrame(main_frame, text="Informations de couverture", padding="10")
    cover_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
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

    # --- Section : Paramètres de mise en page ---
    r += 1
    layout_frame = ttk.LabelFrame(main_frame, text="Paramètres de mise en page", padding="10")
    layout_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    layout_frame.columnconfigure(1, weight=1)

    tk.Label(layout_frame, text="Marge globale (mm) :").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(layout_frame, textvariable=margin_var, width=10).grid(row=0, column=1, sticky="w", padx=5, pady=5)
    tk.Checkbutton(layout_frame, text="Dessiner lignes de séparation de dates", variable=date_line_var).grid(row=1,
                                                                                                             column=0,
                                                                                                             columnspan=2,
                                                                                                             sticky="w",
                                                                                                             padx=5,
                                                                                                             pady=5)
    # Choix du design du poster (Radiobuttons)
    tk.Label(layout_frame, text="Design du poster :").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    design_frame = tk.Frame(layout_frame)
    design_frame.grid(row=2, column=1, sticky="w", padx=5, pady=5)
    tk.Radiobutton(design_frame, text="Image au centre", variable=poster_design_var, value=0).pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(design_frame, text="Image en fond", variable=poster_design_var, value=1).pack(side=tk.LEFT, padx=5)

    # Facteur de sécurité pour la taille de police
    tk.Label(layout_frame, text="Facteur de sécurité police :").grid(row=3, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(layout_frame, textvariable=safety_factor_var, width=10).grid(row=3, column=1, sticky="w", padx=5, pady=5)

    # --- Section : Fichiers de sortie ---
    r += 1
    output_frame = ttk.LabelFrame(main_frame, text="Fichiers de sortie", padding="10")
    output_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    output_frame.columnconfigure(1, weight=1)

    tk.Label(output_frame, text="HTML (biduleur) :").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=html_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(output_frame, text="…", width=3,
              command=lambda: pick_save(html_var, "HTML", ".html", [("HTML", "*.html")])).grid(row=0, column=2, padx=5,
                                                                                               pady=5)
    tk.Label(output_frame, text="HTML Agenda :").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=agenda_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(output_frame, text="…", width=3,
              command=lambda: pick_save(agenda_var, "HTML Agenda", ".html", [("HTML", "*.html")])).grid(row=1, column=2,
                                                                                                        padx=5, pady=5)
    tk.Label(output_frame, text="PDF (misenpageur) :").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=pdf_var).grid(row=2, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(output_frame, text="…", width=3,
              command=lambda: pick_save(pdf_var, "PDF", ".pdf", [("PDF", "*.pdf")])).grid(row=2, column=2, padx=5,
                                                                                          pady=5)
    tk.Label(output_frame, text="Script Scribus (.py) :").grid(row=3, column=0, sticky="e", padx=5, pady=5)
    tk.Entry(output_frame, textvariable=scribus_py_var).grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    tk.Button(output_frame, text="…", width=3,
              command=lambda: pick_save(scribus_py_var, "Script Scribus", ".py", [("Python", "*.py")])).grid(row=3,
                                                                                                             column=2,
                                                                                                             padx=5,
                                                                                                             pady=5)

    # --- Status & action ---
    status = tk.StringVar(value="Prêt.")

    def run_now():
        inp = input_var.get().strip()
        if not inp:
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d’entrée.")
            return

        try:
            margin_val = float(margin_var.get().strip().replace(',', '.'))
            safety_factor_val = float(safety_factor_var.get().strip().replace(',', '.'))
        except ValueError:
            messagebox.showerror("Erreur",
                                 "La marge et le facteur de sécurité doivent être des nombres valides (ex: 1.0).")
            return

        status.set("Traitement en cours…")
        root.update_idletasks()

        ok, msg = run_pipeline(
            inp, generate_cover_var.get(), cover_var.get().strip(),
            ours_var.get().strip(), logos_var.get().strip(),
            html_var.get().strip(), agenda_var.get().strip(),
            pdf_var.get().strip(), scribus_py_var.get().strip(),
            auteur_var.get().strip(), auteur_url_var.get().strip(),
            margin_val, date_line_var.get(),
            poster_design_var.get(),  # Ajouté
            safety_factor_val  # Ajouté
        )
        if ok:
            messagebox.showinfo("Succès", msg)
            status.set("Terminé.")
        else:
            messagebox.showerror("Erreur", msg)
            status.set("Échec.")

    # --- Positionnement final du bouton et du statut ---
    action_frame = ttk.Frame(root, padding="10")
    action_frame.grid(row=1, column=0, sticky="ew")
    action_frame.columnconfigure(0, weight=1)

    tk.Button(action_frame, text="Lancer (HTMLs + PDF + Script)", command=run_now, bg="#4CAF50", fg="white",
              font=("Arial", 10, "bold")).pack(pady=5)

    status_bar = tk.Label(root, textvariable=status, bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=5)
    status_bar.grid(row=2, column=0, sticky="ew")

    root.mainloop()


if __name__ == "__main__":
    main()
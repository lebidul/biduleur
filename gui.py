# bidul/gui.py
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path

# --- import biduleur (HTML) ---
from biduleur.csv_utils import parse_bidul
from biduleur.format_utils import output_html_file

# --- import misenpageur (PDF + Scribus) ---
try:
    from misenpageur.misenpageur.config import Config
    from misenpageur.misenpageur.layout import Layout
    from misenpageur.misenpageur.pdfbuild import build_pdf
    from misenpageur.misenpageur.scribus_export import write_scribus_script
except Exception as e:
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None


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
    """Charge config.yml (si possible) pour pré-remplir cover / ours / logos."""
    out = {"cover": "", "ours_md": "", "logos_dir": ""}
    if _IMPORT_ERR:
        return out
    try:
        defaults = _project_defaults()
        cfg = Config.from_yaml(defaults["config"])
        out["cover"] = cfg.cover_image or ""
        out["ours_md"] = cfg.ours_md or ""
        out["logos_dir"] = cfg.logos_dir or ""
    except Exception:
        pass
    return out


def _ensure_parent_dir(path: str):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def run_pipeline(input_file: str,
                 cover_image: str,
                 ours_md: str,
                 logos_dir: str,
                 out_html: str,
                 out_agenda_html: str,
                 out_pdf: str,
                 out_scribus_py: str) -> tuple[bool, str]:
    """
    Workflow :
      1) biduleur : XLS/CSV → HTML + HTML agenda
      2) misenpageur : HTML → PDF (avec cover / ours / logos passés)
      3) misenpageur : HTML → script Scribus (.py) + .sla (idem)
    """
    if _IMPORT_ERR:
        return False, f"Imports misenpageur impossibles : {repr(_IMPORT_ERR)}"

    try:
        # Crée les dossiers de sortie si besoin
        for p in (out_html, out_agenda_html, out_pdf, out_scribus_py):
            _ensure_parent_dir(p)

        # 1) biduleur : produits HTMLs
        html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(input_file)
        output_html_file(html_body_bidul, original_file_name=input_file, output_filename=out_html)
        output_html_file(html_body_agenda, original_file_name=input_file, output_filename=out_agenda_html)

        # 2) misenpageur : PDF
        defaults = _project_defaults()
        project_root = defaults["root"]
        cfg_path = defaults["config"]
        lay_path = defaults["layout"]

        cfg = Config.from_yaml(cfg_path)
        lay = Layout.from_yaml(lay_path)

        # Forçages depuis la GUI
        cfg.input_html = out_html
        if out_pdf:
            cfg.output_pdf = out_pdf

        # Surcouches assets (si champs non vides)
        if (cover_image or "").strip():
            cfg.cover_image = cover_image.strip()
        if (ours_md or "").strip():
            cfg.ours_md = ours_md.strip()
        if (logos_dir or "").strip():
            cfg.logos_dir = logos_dir.strip()

        # Génération du PDF
        build_pdf(project_root, cfg, lay, cfg.output_pdf)

        # 3) Scribus : script + .sla (enregistre au même endroit que .py)
        scribus_sla = os.path.splitext(out_scribus_py)[0] + ".sla"
        write_scribus_script(project_root, cfg, lay, out_scribus_py, scribus_sla)

        # Résumé
        summary = (
            f"HTML            : {out_html}\n"
            f"HTML (agenda)   : {out_agenda_html}\n"
            f"PDF             : {cfg.output_pdf}\n"
            f"Scribus script  : {out_scribus_py}\n"
            f"SLA Scribus     : {scribus_sla}\n"
            f"Couverture      : {cfg.cover_image or '(cfg)'}\n"
            f"Ours (Markdown) : {cfg.ours_md or '(cfg)'}\n"
            f"Logos (dossier) : {cfg.logos_dir or '(cfg)'}\n"
            f"\nÉvénements : {number_of_lines}"
        )
        return True, summary

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    # GUI
    root = tk.Tk()
    root.title("Bidul – Pipeline XLS/CSV → HTMLs → PDF + Script Scribus")
    root.minsize(820, 540)

    root.columnconfigure(1, weight=1)
    for r in range(0, 15):
        root.rowconfigure(r, weight=0)
    root.rowconfigure(14, weight=1)

    # Préremplissages depuis config.yml
    cfg_defaults = _load_cfg_defaults()

    # Vars
    input_var = tk.StringVar()
    cover_var = tk.StringVar(value=cfg_defaults.get("cover", ""))
    ours_var = tk.StringVar(value=cfg_defaults.get("ours_md", ""))
    logos_var = tk.StringVar(value=cfg_defaults.get("logos_dir", ""))
    html_var = tk.StringVar()
    agenda_var = tk.StringVar()
    pdf_var = tk.StringVar()
    scribus_py_var = tk.StringVar()

    # Helpers
    def pick_input():
        file_path = filedialog.askopenfilename(
            title="Sélectionner l’entrée (CSV / XLS / XLSX)",
            filetypes=[("Excel", "*.xls;*.xlsx"), ("CSV", "*.csv"), ("Tous les fichiers", "*.*")]
        )
        if not file_path:
            return
        input_var.set(file_path)
        d = _default_paths_from_input(file_path)
        html_var.set(d["html"])
        agenda_var.set(d["agenda_html"])
        pdf_var.set(d["pdf"])
        scribus_py_var.set(d["scribus_py"])

    def pick_cover():
        path = filedialog.askopenfilename(
            title="Sélectionner l’image de couverture",
            filetypes=[("Images", "*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.webp"), ("Tous les fichiers", "*.*")]
        )
        if path:
            cover_var.set(path)

    def pick_ours():
        path = filedialog.askopenfilename(
            title="Sélectionner le fichier OURS (Markdown)",
            filetypes=[("Markdown", "*.md;*.markdown"), ("Texte", "*.txt"), ("Tous les fichiers", "*.*")]
        )
        if path:
            ours_var.set(path)

    def pick_logos():
        path = filedialog.askdirectory(title="Sélectionner le dossier des logos")
        if path:
            logos_var.set(path)

    def pick_save(entry_var: tk.StringVar, title: str, def_ext: str, ftypes: list[tuple[str, str]]):
        path = filedialog.asksaveasfilename(title=title, defaultextension=def_ext, filetypes=ftypes)
        if path:
            entry_var.set(path)

    # UI
    r = 0
    tk.Label(root, text="Fichier d’entrée (CSV / XLS / XLSX) :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=input_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="Parcourir…", command=pick_input).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    tk.Label(root, text="Image de couverture :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=cover_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="Parcourir…", command=pick_cover).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    tk.Label(root, text="Ours (Markdown) :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=ours_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="Parcourir…", command=pick_ours).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    tk.Label(root, text="Dossier logos :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=logos_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="Parcourir…", command=pick_logos).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    ttk.Separator(root, orient='horizontal').grid(row=r, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

    r += 1
    tk.Label(root, text="Sortie HTML (biduleur) :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=html_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="…", width=3,
              command=lambda: pick_save(html_var, "Enregistrer le HTML", ".html",
                                        [("HTML", "*.html"), ("Tous les fichiers", "*.*")])
              ).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    tk.Label(root, text="Sortie HTML Agenda :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=agenda_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="…", width=3,
              command=lambda: pick_save(agenda_var, "Enregistrer le HTML Agenda", ".html",
                                        [("HTML", "*.html"), ("Tous les fichiers", "*.*")])
              ).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    tk.Label(root, text="Sortie PDF (misenpageur) :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=pdf_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="…", width=3,
              command=lambda: pick_save(pdf_var, "Enregistrer le PDF", ".pdf",
                                        [("PDF", "*.pdf"), ("Tous les fichiers", "*.*")])
              ).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    tk.Label(root, text="Script Scribus (.py) :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=scribus_py_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="…", width=3,
              command=lambda: pick_save(scribus_py_var, "Enregistrer le script Scribus", ".py",
                                        [("Script Python", "*.py"), ("Tous les fichiers", "*.*")])
              ).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    ttk.Separator(root, orient='horizontal').grid(row=r, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

    # Status
    status = tk.StringVar(value="Prêt.")
    r += 1
    tk.Label(root, textvariable=status, bd=1, relief=tk.SUNKEN, anchor=tk.W).grid(row=r, column=0, columnspan=3, sticky="ew", padx=6, pady=6)

    # Action
    def run_now():
        inp = input_var.get().strip()
        cov = cover_var.get().strip()
        ours = ours_var.get().strip()
        logos = logos_var.get().strip()
        h1 = html_var.get().strip()
        h2 = agenda_var.get().strip()
        p1 = pdf_var.get().strip()
        sp = scribus_py_var.get().strip()

        if not inp:
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d’entrée.")
            return

        status.set("Traitement en cours…")
        root.update_idletasks()

        ok, msg = run_pipeline(inp, cov, ours, logos, h1, h2, p1, sp)
        if ok:
            messagebox.showinfo("Succès", msg)
            status.set("Terminé.")
        else:
            messagebox.showerror("Erreur", msg)
            status.set("Échec.")

    r += 1
    tk.Button(
        root, text="Lancer (HTMLs + PDF + Script)", command=run_now,
        bg="#4CAF50", fg="white", font=("Arial", 10, "bold")
    ).grid(row=r, column=1, pady=14)

    root.mainloop()


if __name__ == "__main__":
    main()

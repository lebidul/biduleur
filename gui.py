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
    # racine = dossier parent de ce gui.py (repo root si tu gardes la structure)
    repo_root = Path(__file__).resolve().parent
    cfg = repo_root / "misenpageur" / "config.yml"
    lay = repo_root / "misenpageur" / "layout.yml"
    return {"root": str(repo_root), "config": str(cfg), "layout": str(lay)}


def _load_cfg_defaults() -> dict:
    """Lit quelques valeurs par défaut depuis config.yml (si possible)."""
    out = {
        "cover": "",
        "ours_md": "",
        "logos_dir": "",
        "auteur_couv": "",
        "auteur_couv_url": "",
        "skip_cover": False,  # --- NOUVELLE VALEUR PAR DÉFAUT ---
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
                 auteur_couv_url: str) -> tuple[bool, str]:
    """
    Enchaîne : XLS/CSV -> (biduleur) -> 2 HTML -> (misenpageur) -> PDF (+ Scribus optionnel)
    """
    if _IMPORT_ERR:
        return False, f"Imports misenpageur impossibles : {repr(_IMPORT_ERR)}"

    try:
        # créer les dossiers de sortie
        for p in (out_html, out_agenda_html, out_pdf, out_scribus_py):
            if p:
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

        # On inverse la logique : la GUI a "Générer couv" (True), la config a "skip_cover" (True)
        cfg.skip_cover = not generate_cover

        cfg.input_html = out_html
        if out_pdf:
            cfg.output_pdf = out_pdf

        if (cover_image or "").strip():
            cfg.cover_image = cover_image.strip()
        if (ours_md or "").strip():
            cfg.ours_md = ours_md.strip()
        if (logos_dir or "").strip():
            cfg.logos_dir = logos_dir.strip()

        # Paramètres ours (nouveaux)
        if (auteur_couv or "").strip():
            cfg.auteur_couv = auteur_couv.strip()
        if (auteur_couv_url or "").strip():
            cfg.auteur_couv_url = auteur_couv_url.strip()

        build_pdf(project_root, cfg, lay, cfg.output_pdf)

        # 3) Scribus : script + .sla (OPTIONNEL)
        scribus_sla = ""
        if (out_scribus_py or "").strip():
            scribus_sla = os.path.splitext(out_scribus_py)[0] + ".sla"
            write_scribus_script(project_root, cfg, lay, out_scribus_py, scribus_sla)

        couv_status = "Oui" if generate_cover else "Non"
        # résumé
        summary_lines = [
            f"HTML            : {out_html}",
            f"HTML (agenda)   : {out_agenda_html}",
            f"PDF             : {cfg.output_pdf}",
            f"Couverture générée : {couv_status}", # Ligne ajoutée
        ]
        if scribus_sla:
            summary_lines += [
                f"Scribus script  : {out_scribus_py}",
                f"SLA Scribus     : {scribus_sla}",
            ]
        summary_lines += [
            f"Couverture      : {cfg.cover_image or '(cfg)'}",
            f"Ours (Markdown) : {cfg.ours_md or '(cfg)'}",
            f"Logos (dossier) : {cfg.logos_dir or '(cfg)'}",
            f"Auteur couv     : {getattr(cfg, 'auteur_couv', '') or '(cfg)'}",
            f"URL auteur couv : {getattr(cfg, 'auteur_couv_url', '') or '(cfg)'}",
            f"\nÉvénements : {number_of_lines}",
        ]
        return True, "\n".join(summary_lines)

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    root = tk.Tk()
    root.title("Bidul – Pipeline XLS/CSV → HTMLs → PDF (+ Scribus)")
    root.minsize(900, 640)

    root.columnconfigure(1, weight=1)
    for r in range(0, 24):
        root.rowconfigure(r, weight=0)
    root.rowconfigure(23, weight=1)

    # Préremplissages depuis config.yml
    cfg_defaults = _load_cfg_defaults()

    # Vars
    input_var = tk.StringVar()
    # L'état initial de la case est l'inverse de `skip_cover`
    # Si skip_cover=True (sans couv), la case doit être décochée (False)
    initial_generate_cover = not cfg_defaults.get("skip_cover", False)
    generate_cover_var = tk.BooleanVar(value=initial_generate_cover)
    cover_var = tk.StringVar(value=cfg_defaults.get("cover", ""))
    ours_var = tk.StringVar(value=cfg_defaults.get("ours_md", ""))
    logos_var = tk.StringVar(value=cfg_defaults.get("logos_dir", ""))
    generate_cover_var = tk.BooleanVar(value=True) # "Avec couv" par défaut
    auteur_var = tk.StringVar(value=cfg_defaults.get("auteur_couv", ""))
    auteur_url_var = tk.StringVar(value=cfg_defaults.get("auteur_couv_url", ""))
    html_var = tk.StringVar()
    agenda_var = tk.StringVar()
    pdf_var = tk.StringVar()
    scribus_py_var = tk.StringVar()

    # Helpers: choix de fichiers/dossiers
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

    # Téléchargement des modèles (CSV / XLSX)
    def save_embedded_template(package: str, filename: str, title: str):
        try:
            initial_ext = os.path.splitext(filename)[1].lower()
            if initial_ext == '.csv':
                ftypes = [("CSV", "*.csv")]
            elif initial_ext == '.xlsx':
                ftypes = [("Excel (XLSX)", "*.xlsx")]
            else:
                ftypes = [("Tous les fichiers", "*.*")]

            target = filedialog.asksaveasfilename(
                title=title,
                defaultextension=initial_ext,
                filetypes=ftypes,
                initialfile=filename
            )
            if not target:
                return

            try:
                data = res.files('biduleur.templates').joinpath(filename).read_bytes()
            except Exception:
                # Fallback dev : lire depuis le repo si le package n'est pas importable
                pkg_root = Path(__file__).resolve().parent / 'biduleur' / 'templates'
                data = (pkg_root / filename).read_bytes()

            with open(target, "wb") as f:
                f.write(data)
            messagebox.showinfo("Modèle enregistré", f"Fichier enregistré ici :\n{target}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer le modèle : {e}")

    # --- UI ---
    r = 0
    tk.Label(root, text="Fichier d’entrée (CSV / XLS / XLSX) :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=input_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)
    tk.Button(root, text="Parcourir…", command=pick_input).grid(row=r, column=2, padx=8, pady=6)

    r += 1
    tk.Checkbutton(
        root, text="Avec couv' (générer la page de couverture)",
        variable=generate_cover_var, onvalue=True, offvalue=False
    ).grid(row=r, column=1, sticky="w", padx=8, pady=2)

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
    tk.Label(root, text="Auteur couverture :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=auteur_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)

    r += 1
    tk.Label(root, text="URL auteur couverture :").grid(row=r, column=0, sticky="e", padx=8, pady=6)
    tk.Entry(root, textvariable=auteur_url_var).grid(row=r, column=1, sticky="ew", padx=8, pady=6)

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

    # --- Bandeau modèles à télécharger ---
    r += 1
    ttk.Separator(root, orient='horizontal').grid(row=r, column=0, columnspan=3, sticky="ew", padx=8, pady=(10, 6))

    r += 1
    models = tk.Frame(root)
    models.grid(row=r, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 10))
    tk.Label(models, text="Télécharger un modèle de fichier (tapageur) :", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))

    tk.Button(
        models, text="Modèle CSV",
        command=lambda: save_embedded_template('biduleur.templates', 'tapage_template.csv', "Enregistrer le modèle CSV")
    ).grid(row=1, column=0, padx=(0, 8))

    tk.Button(
        models, text="Modèle XLSX",
        command=lambda: save_embedded_template('biduleur.templates', 'tapage_template.xlsx', "Enregistrer le modèle XLSX")
    ).grid(row=1, column=1, padx=(0, 8))

    # --- Status & action ---
    status = tk.StringVar(value="Prêt.")

    r += 1
    tk.Label(root, textvariable=status, bd=1, relief=tk.SUNKEN, anchor=tk.W).grid(row=r, column=0, columnspan=3, sticky="ew", padx=6, pady=6)

    def run_now():
        inp = input_var.get().strip()
        gen_cover = generate_cover_var.get()
        cov = cover_var.get().strip()
        ours = ours_var.get().strip()
        logos = logos_var.get().strip()
        h1 = html_var.get().strip()
        h2 = agenda_var.get().strip()
        p1 = pdf_var.get().strip()
        sp = scribus_py_var.get().strip()
        auteur = auteur_var.get().strip()
        auteur_url = auteur_url_var.get().strip()

        if not inp:
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d’entrée.")
            return

        status.set("Traitement en cours…")
        root.update_idletasks()

        ok, msg = run_pipeline(
            inp, gen_cover, cov, ours, logos,
            h1, h2, p1, sp,
            auteur, auteur_url
        )
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

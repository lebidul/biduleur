# -*- coding: utf-8 -*-
"""
misenpageur.main
----------------
Entrée CLI pour :
- Générer le PDF (ReportLab) à partir d'un HTML + config + layout

Exemples :
    python misenpageur/main.py --root . --config misenpageur/config.yml --layout misenpageur/layout.yml \
        --out misenpageur/output/bidul.pdf \
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

# --- bootstrap & config path ---
import os, sys, argparse
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent      # .../bidul/misenpageur
REPO_ROOT = THIS_DIR.parent                     # .../bidul
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", default=None,
                    help="Chemin vers config.yml (par défaut: misenpageur/config.yml)")
args, _ = parser.parse_known_args()

# Par défaut: config.yml au niveau du module misenpageur
if args.config is None:
    cfg_path = THIS_DIR / "config.yml"
else:
    p = Path(args.config)
    cfg_path = p if p.is_absolute() else (Path.cwd() / p)

if not cfg_path.exists():
    sys.exit(f"[ERR] config.yml introuvable: {cfg_path}")
# --- fin bootstrap & config path ---

# API internes
# Imports robustes (exécution depuis la racine OU depuis le dossier misenpageur)
try:
    # cas: exécuté depuis la racine du repo (bidul/)
    from misenpageur.misenpageur.config import Config
    from misenpageur.misenpageur.layout import Layout
    from misenpageur.misenpageur.pdfbuild import build_pdf
except ModuleNotFoundError:
    # cas: exécuté depuis le dossier misenpageur/
    from misenpageur.config import Config
    from misenpageur.layout import Layout
    from misenpageur.pdfbuild import build_pdf


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="misenpageur",
        description="Génère le PDF (ReportLab) à partir d'un HTML d'entrée."
    )
    # Defaults repris de parse_args() historique
    p.add_argument("--root",   default=".",            help="Racine du projet (contient config.yml, layout.yml)")
    p.add_argument("--config", default="misenpageur/config.yml",   help="Chemin du fichier de configuration YAML")
    p.add_argument("--layout", default="misenpageur/layout.yml",   help="Chemin du fichier de layout YAML")

    # Sortie PDF (défaut identique à l'ancien parse_args)
    p.add_argument("--out",    default="misenpageur/bidul/bidul_cli.pdf",
                   help="Chemin de sortie PDF (écrase output_pdf du config si fourni)")

    # Overrides utiles (pas de défaut => opt-in)
    p.add_argument("--html",   help="Forcer le chemin du HTML d'entrée (sinon cfg.input_html)")
    p.add_argument("--cover",  help="Surcharger l'image de couverture (sinon cfg.cover_image)")

    # Paramètres ours
    p.add_argument("--auteur-couv", default="", help="Crédit visuel de couverture (remplace @Steph dans l’ours)")
    p.add_argument("--auteur-couv-url", default="", help="URL associée au crédit visuel (hyperlien)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)

    root = Path(args.root).resolve()
    cfg_path = Path(args.config).resolve()
    base_layout_path = Path(args.layout).resolve()

    if not cfg_path.exists():
        print("[ERR] config.yml introuvable:", cfg_path)
        return 2
    if not base_layout_path.exists():
        print("[ERR] layout.yml introuvable:", base_layout_path)
        return 2

    from misenpageur.misenpageur.config import Config
    from misenpageur.misenpageur.pdfbuild import build_pdf
    from misenpageur.misenpageur.layout import Layout  # si tu as un loader de layout
    from misenpageur.misenpageur.layout_builder import build_layout_with_margins

    # Charger configuration + layout
    try:
        cfg = Config.from_yaml(str(cfg_path))
        # Construire le layout final avec les marges de la config
        final_layout_path = build_layout_with_margins(str(base_layout_path), cfg)
        # Charger le layout depuis ce nouveau fichier temporaire
        lay = Layout.from_yaml(final_layout_path)
        project_root = str(cfg_path.parent)  # <-- racine des chemins relatifs
    except Exception as e:
        print("[ERR] Lecture config/layout :", e)
        return 2

    try:
        # Overrides
        if args.html:
            cfg.input_html = str(Path(args.html).resolve())
        if args.cover:
            cover_path = Path(args.cover).resolve()
            if not cover_path.exists():
                print("[WARN] --cover fourni mais introuvable :", cover_path)
            else:
                cfg.cover_image = str(cover_path)

        if args.auteur_couv != "":     cfg.auteur_couv = args.auteur_couv
        if args.auteur_couv_url != "": cfg.auteur_couv_url = args.auteur_couv_url

        if not args.out:
            print("[ERR] --out est requis pour générer le PDF.")
            return 2

        # Générer le PDF
        out_pdf = Path(args.out).resolve()
        out_pdf.parent.mkdir(parents=True, exist_ok=True)

        # La config peut aussi spécifier output_pdf ; on favorise l'argument CLI
        cfg.output_pdf = str(out_pdf)

        import traceback

        try:
            report = build_pdf(str(root), cfg, lay, str(out_pdf))
            print("[OK] PDF généré :", out_pdf)
            if isinstance(report, dict) and report.get("unused_paragraphs"):
                print("[WARN]", report["unused_paragraphs"], "paragraphes non placés")
        except Exception as e:
            print("[ERR] Échec build PDF :", e)
            traceback.print_exc()
            return 2

    finally:
        # --- Ce bloc s'exécute toujours, même en cas d'erreur ---
        if os.path.exists(final_layout_path):
            os.remove(final_layout_path)
            print(f"[INFO] Fichier de layout temporaire supprimé : {final_layout_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

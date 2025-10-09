# misenpageur/main.v0.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import os
from dataclasses import asdict
from datetime import datetime

import logging
from .logger import setup_logger, save_dict_to_json, save_text_to_file


# API internes
# Imports robustes (exécution depuis la racine OU depuis le dossier misenpageur)
try:
    from misenpageur.misenpageur.config import Config
    from misenpageur.misenpageur.layout import Layout
    from misenpageur.misenpageur.pdfbuild import build_pdf
    from misenpageur.misenpageur.svgbuild import build_svg
    from misenpageur.misenpageur.layout_builder import build_layout_with_margins
    from misenpageur.misenpageur.draw_logic import read_text
    from misenpageur.misenpageur.html_utils import extract_paragraphs_from_html
    from misenpageur.misenpageur.image_builder import generate_story_images
except (ModuleNotFoundError, ImportError):
    # Fallback
    from misenpageur.config import Config
    from misenpageur.layout import Layout
    from misenpageur.pdfbuild import build_pdf
    from misenpageur.svgbuild import build_svg
    from misenpageur.layout_builder import build_layout_with_margins
    from misenpageur.draw_logic import read_text
    from misenpageur.html_utils import extract_paragraphs_from_html
    from misenpageur.image_builder import generate_story_images

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
    p.add_argument("--out", default="misenpageur/bidul/bidul_cli.pdf",
                   help="Chemin de sortie PDF (écrase output_pdf du config si fourni)")
    p.add_argument("--svg", default="misenpageur/bidul/bidul_cli.svg",
                   help="Chemin de sortie pour un SVG éditable (optionnel)")

    # Overrides utiles (pas de défaut => opt-in)
    p.add_argument("--html",   help="Forcer le chemin du HTML d'entrée (sinon cfg.input_html)")
    p.add_argument("--cover",  help="Surcharger l'image de couverture (sinon cfg.cover_image)")

    # Paramètres ours
    p.add_argument("--auteur-couv", default="", help="Crédit visuel de couverture (remplace @Steph dans l’ours)")
    p.add_argument("--auteur-couv-url", default="", help="URL associée au crédit visuel (hyperlien)")

    # Paramètres layout des logos
    p.add_argument(
        "--logos-layout",
        default="colonnes",
        choices=["colonnes", "optimise"],
        help="Type de répartition pour les logos : 'colonnes' (2 colonnes fixes) ou 'optimise' (packing)."
    )

    p.add_argument(
        "--stories",
        action=argparse.BooleanOptionalAction,
        help="Forcer la génération des images pour les Stories (--no-stories pour désactiver)."
    )

    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Activer l'affichage des logs détaillés dans la console."
    )

    p.add_argument(
        "--debug",
        action="store_true",
        help="Activer le mode débogage (crée un dossier de log horodaté)."
    )

    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)

    debug_dir = None
    if args.debug:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # On base le dossier de debug sur le dossier de sortie du PDF pour la cohérence
        # Si --out n'est pas fourni, cela utilisera la valeur par défaut.
        debug_dir = Path(args.out).parent / f"debug_run_{timestamp}"

    # On configure le logger. Si debug_dir est None, seul le mode console (si -v) sera actif.
    setup_logger(log_dir=str(debug_dir) if debug_dir else None)
    log = logging.getLogger(__name__)
    # Si l'utilisateur n'a pas mis -v mais a mis --debug, on veut quand même voir les logs
    if args.debug and not args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    elif not args.verbose:
        logging.getLogger().setLevel(logging.WARNING) # Mode silencieux par défaut

    # On utilise l'argument --root de la CLI comme base
    project_root = Path(args.root).resolve()

    cfg_path = project_root / args.config
    base_layout_path = project_root / args.layout

    setup_logger(log_dir=debug_dir)
    log = logging.getLogger(__name__)

    if not cfg_path.exists(): log.error(f"config.yml introuvable: {cfg_path}"); return 2
    if not base_layout_path.exists(): log.error(f"layout.yml introuvable: {base_layout_path}"); return 2

    from misenpageur.misenpageur.config import Config
    from misenpageur.misenpageur.pdfbuild import build_pdf
    from misenpageur.misenpageur.layout import Layout  # si tu as un loader de layout
    from misenpageur.misenpageur.layout_builder import build_layout_with_margins

    import traceback
    # Charger configuration + layout
    final_layout_path = None
    try:
        cfg = Config.from_yaml(str(cfg_path))
        final_layout_path = build_layout_with_margins(str(base_layout_path), cfg)
        lay = Layout.from_yaml(final_layout_path)
    except Exception as e:
        log.error(f"Lecture config/layout : {e}")
        traceback.print_exc()
        return 2

    try:
        # Overrides
        if args.html:
            cfg.input_html = str(Path(args.html).resolve())
        if args.cover:
            cover_path = Path(args.cover).resolve()
            if not cover_path.exists():
                log.warning(f"--cover fourni mais introuvable :", cover_path)
            else:
                cfg.cover_image = str(cover_path)

        if args.auteur_couv != "":     cfg.auteur_couv = args.auteur_couv
        if args.auteur_couv_url != "": cfg.auteur_couv_url = args.auteur_couv_url

        cfg.logos_layout = args.logos_layout

        if args.stories is not None:
            cfg.stories['enabled'] = args.stories

        if not args.out and not args.svg:
            log.error(f"Au moins une sortie (--out pour le PDF ou --svg) est requise.")
            return 2

        # Générer le PDF
        out_pdf = Path(args.out).resolve()
        out_pdf.parent.mkdir(parents=True, exist_ok=True)

        # La config peut aussi spécifier output_pdf ; on favorise l'argument CLI
        cfg.output_pdf = str(out_pdf)

        # 1. Lire et préparer le contenu UNE SEULE FOIS
        html_path = os.path.join(project_root, cfg.input_html)
        html_text = read_text(html_path)
        paras = extract_paragraphs_from_html(html_text)

        import traceback

        try:
            # --- Générer le PDF ---
            out_pdf = Path(args.out).resolve()
            out_pdf.parent.mkdir(parents=True, exist_ok=True)
            cfg.output_pdf = str(out_pdf)
            # On passe le project_root
            report = build_pdf(str(project_root), cfg, lay, str(out_pdf), cfg_path, paras)

            # --- Générer le SVG (si demandé) ---
            if args.svg:
                out_svg = Path(args.svg).resolve()
                out_svg.parent.mkdir(parents=True, exist_ok=True)
                # On passe le project_root
                build_svg(str(project_root), cfg, lay, str(out_svg), cfg_path, paras)

            # --- Générer les images Stories (si demandé) ---
            # On récupère la config des stories depuis l'objet cfg
            if cfg.stories.get("enabled", False):
                generate_story_images(str(project_root), cfg, paras)

            if debug_dir:
                # 1. Sauvegarder la configuration
                # On utilise une fonction pour gérer les types non sérialisables comme Path
                def json_converter(o):
                    if isinstance(o, Path): return str(o)
                    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

                config_data = asdict(cfg)
                save_dict_to_json(config_data, "config.json", str(debug_dir))

                summary_lines = [
                    f"PDF généré : {cfg.output_pdf}",
                    f"Police principale : {report.get('font_size_main', 0):.2f} pt",
                    f"Police du poster : {report.get('font_size_poster_final', 0):.2f} pt",
                    f"Paragraphes non placés : {report.get('unused_paragraphs', 0)}",
                ]
                save_text_to_file("\n".join(summary_lines), "summary.info", str(debug_dir))

        except Exception as e:
            log.error(f"Échec build PDF :", e)
            traceback.print_exc()
            return 2


    finally:
        # --- Ce bloc s'exécute toujours, même en cas d'erreur ---
        if final_layout_path and os.path.exists(final_layout_path):
            try:
                os.remove(final_layout_path)
            except OSError:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

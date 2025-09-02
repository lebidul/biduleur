# -*- coding: utf-8 -*-
"""
misenpageur.main
----------------
Entrée CLI pour :
- Générer le PDF (ReportLab) à partir d'un HTML + config + layout
- (Optionnel) Générer un script Scribus .py + un .sla éditable

Exemples :
    # PDF uniquement
    python misenpageur/main.py --root . --config misenpageur/config.yml --layout misenpageur/layout.yml --out misenpageur/output/bidul.pdf

    # PDF + export Scribus
    python misenpageur/main.py --root . --config misenpageur/config.yml --layout misenpageur/layout.yml \
        --out misenpageur/output/bidul.pdf \
        --scribus-script misenpageur/output/bidul_scribus.py \
        --scribus-sla misenpageur/output/bidul.sla

    # Scribus uniquement (pas de PDF)
    python misenpageur/main.py --root . --config misenpageur/config.yml --layout misenpageur/layout.yml \
        --scribus-script misenpageur/output/bidul_scribus.py \
        --scribus-sla misenpageur/output/bidul.sla \
        --scribus-only
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

# API internes
# Imports robustes (exécution depuis la racine OU depuis le dossier misenpageur)
try:
    # cas: exécuté depuis la racine du repo (bidul/)
    from misenpageur.misenpageur.config import Config
    from misenpageur.misenpageur.layout import Layout
    from misenpageur.misenpageur.pdfbuild import build_pdf
    try:
        from misenpageur.misenpageur.scribus_export import write_scribus_script
        _HAS_SCRIBUS_EXPORT = True
    except Exception:
        _HAS_SCRIBUS_EXPORT = False
except ModuleNotFoundError:
    # cas: exécuté depuis le dossier misenpageur/
    from misenpageur.config import Config
    from misenpageur.layout import Layout
    from misenpageur.pdfbuild import build_pdf
    try:
        from misenpageur.scribus_export import write_scribus_script
        _HAS_SCRIBUS_EXPORT = True
    except Exception:
        _HAS_SCRIBUS_EXPORT = False


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="misenpageur",
        description="Génère le PDF (ReportLab) et/ou un script Scribus + .sla à partir d'un HTML d'entrée."
    )
    # Defaults repris de parse_args() historique
    p.add_argument("--root",   default=".",            help="Racine du projet (contient config.yml, layout.yml)")
    p.add_argument("--config", default="config.yml",   help="Chemin du fichier de configuration YAML")
    p.add_argument("--layout", default="layout.yml",   help="Chemin du fichier de layout YAML")

    # Sortie PDF (défaut identique à l'ancien parse_args)
    p.add_argument("--out",    default="bidul/bidul_cli.pdf",
                   help="Chemin de sortie PDF (écrase output_pdf du config si fourni)")

    # Overrides utiles (pas de défaut => opt-in)
    p.add_argument("--html",   help="Forcer le chemin du HTML d'entrée (sinon cfg.input_html)")
    p.add_argument("--cover",  help="Surcharger l'image de couverture (sinon cfg.cover_image)")

    # Export Scribus (pas de défaut => opt-in)
    p.add_argument("--scribus-script", default="bidul/bidul.scribus.py", help="Chemin du script Scribus .py à générer")
    p.add_argument("--scribus-sla", default="bidul/bidul.sla", help="Chemin du .sla que le script enregistrera")

    # Modes
    p.add_argument("--pdf-only",     action="store_true", help="Ne générer que le PDF (ignorer Scribus)")
    p.add_argument("--scribus-only", action="store_true", help="Ne générer que le script Scribus + .sla (pas de PDF)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)

    root = Path(args.root).resolve()
    cfg_path = Path(args.config).resolve()
    layout_path = Path(args.layout).resolve()

    if not cfg_path.exists():
        print("[ERR] config.yml introuvable:", cfg_path)
        return 2
    if not layout_path.exists():
        print("[ERR] layout.yml introuvable:", layout_path)
        return 2

    # Charger configuration + layout
    try:
        cfg = Config.from_yaml(str(cfg_path))
        lay = Layout.from_yaml(str(layout_path))
    except Exception as e:
        print("[ERR] Lecture config/layout :", e)
        return 2

    # Overrides
    if args.html:
        cfg.input_html = str(Path(args.html).resolve())
    if args.cover:
        cover_path = Path(args.cover).resolve()
        if not cover_path.exists():
            print("[WARN] --cover fourni mais introuvable :", cover_path)
        else:
            cfg.cover_image = str(cover_path)

    # Sanity : que doit-on générer ?
    want_pdf = not args.scribus_only
    want_scribus = not args.pdf_only and (args.scribus_script and args.scribus_sla)

    if want_pdf and not args.out:
        print("[ERR] --out est requis pour générer le PDF (ou passe --scribus-only).")
        return 2

    # Générer le PDF si demandé
    if want_pdf:
        out_pdf = Path(args.out).resolve()
        out_pdf.parent.mkdir(parents=True, exist_ok=True)

        # La config peut aussi spécifier output_pdf ; on favorise l'argument CLI
        cfg.output_pdf = str(out_pdf)

        try:
            report = build_pdf(str(root), cfg, lay, str(out_pdf))
            print("[OK] PDF généré :", out_pdf)
            if isinstance(report, dict) and report.get("unused_paragraphs"):
                print("[WARN]", report["unused_paragraphs"], "paragraphes non placés")
        except Exception as e:
            print("[ERR] Échec build PDF :", e)
            # on n'arrête pas si l'utilisateur veut quand même Scribus derrière
            if not want_scribus:
                return 2

    # Générer script Scribus + .sla si demandé
    if want_scribus:
        if not _HAS_SCRIBUS_EXPORT:
            print("[ERR] L'export Scribus n'est pas disponible (module scribus_export manquant).")
            return 2

        script_path = Path(args.scribus_script).resolve()
        sla_path = Path(args.scribus_sla).resolve()
        script_path.parent.mkdir(parents=True, exist_ok=True)
        sla_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            write_scribus_script(str(root), cfg, lay, str(script_path), str(sla_path))
            print("[OK] Script Scribus généré :", script_path)
            print("     Ouvre Scribus puis : Script → Exécuter un script… →", script_path.name)
            print("     Le script crée les cadres S1..S6 et enregistre :", sla_path)
            print("     Astuce (GUI silencieux) :", "scribus -g -py", script_path)
        except Exception as e:
            print("[ERR] Échec génération script Scribus :", e)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

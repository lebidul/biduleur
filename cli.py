# -*- coding: utf-8 -*-
"""
Wrapper CLI racine :
1) génère les HTML via biduleur.main.run_biduleur
2) utilise le bidul_output_file comme input_html pour misenpageur
3) option --cover pour surcharger l'image de couverture (sinon on garde la config)
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

# 1) Import du générateur HTML (ton fichier actuel)
try:
    from biduleur.main import run_biduleur
except Exception as e:
    print("[ERR] Impossible d'importer biduleur.main.run_biduleur :", e)
    sys.exit(2)

# 2) Import de l'API misenpageur
try:
    from misenpageur.misenpageur.config import Config as MPConfig
    from misenpageur.misenpageur.layout import Layout
    from misenpageur.misenpageur.pdfbuild import build_pdf
except Exception as e:
    print("[ERR] Impossible d'importer misenpageur.* :", e)
    print("      Vérifie le PYTHONPATH / l'installation du package misenpageur.")
    sys.exit(2)


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bidul",
        description="Wrapper CLI : CSV/XLS(X) -> HTML (biduleur) -> PDF (misenpageur)"
    )
    p.add_argument("-i", "--input",help="Chemin du CSV/XLS/XLSX", default="data/tapage.xlsx")
    p.add_argument("--bidul-html", help="Chemin de sortie HTML pour Bidul (passé à biduleur)", default="data/output/biduleur.html")
    p.add_argument("--agenda-html", help="Chemin de sortie HTML pour Agenda (passé à biduleur)", default="data/output/biduleur.agenda.html")
    p.add_argument("--assets-dir", default="misenpageur/assets", help="Dossier par défaut où écrire les HTML si non fournis (def: misenpageur/assets)")
    p.add_argument("--config", help="Chemin misenpageur/config.yml", default="misenpageur/config.yml")
    p.add_argument("--layout", help="Chemin misenpageur/layout.yml", default="misenpageur/layout.yml")
    p.add_argument("--out", help="Chemin du PDF final (ex: misenpageur/output/bidul.cli.pdf)",
                   default="data/output/bidul.cli.pdf")
    p.add_argument("--project-root", help="Racine projet pour misenpageur (def: dossier de la config)")
    p.add_argument("--cover", help="Chemin image de couverture (override cover_image du config.yml)")
    p.add_argument("--no-cover", action="store_true", help="Génère un PDF sans page de couverture.")
    p.add_argument("--scribus-script", help="Chemin du script Scribus (.py) à générer")
    p.add_argument("--scribus-sla", help="Chemin du .sla cible que le script enregistrera (ex: data/output/bidul.sla)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print("[ERR] Fichier d'entrée introuvable :", input_path)
        return 2

    assets_dir = Path(args.assets_dir).resolve()

    # Détermine les 2 sorties HTML si non fournies explicitement
    if args.bidul_html:
        bidul_html = Path(args.bidul_html).resolve()
    else:
        # Par défaut : misenpageur/assets/<base>.html
        base = input_path.stem
        bidul_html = assets_dir / f"{base}.html"

    if args.agenda_html:
        agenda_html = Path(args.agenda_html).resolve()
    else:
        base = input_path.stem
        agenda_html = assets_dir / f"{base}.agenda.html"

    # 1) GÉNÉRER LES HTML (biduleur)
    ok, res = run_biduleur(str(input_path), str(bidul_html), str(agenda_html))
    if not ok:
        print("[ERR] Échec génération HTML via biduleur :", res)
        return 2
    print("[OK] HTML bidul :", bidul_html)
    print("[OK] HTML agenda:", agenda_html)

    # 2) CONSTRUIRE LE PDF (misenpageur), en forçant input_html = bidul_output_file
    cfg_path = Path(args.config).resolve()
    layout_path = Path(args.layout).resolve()
    out_pdf = Path(args.out).resolve()

    if not cfg_path.exists():
        print("[ERR] config.yml introuvable :", cfg_path)
        return 2
    if not layout_path.exists():
        print("[ERR] layout.yml introuvable :", layout_path)
        return 2

    # Chargement config / layout via leur API
    try:
        mp_cfg = MPConfig.from_yaml(str(cfg_path))
        mp_layout = Layout.from_yaml(str(layout_path))
    except Exception as e:
        print("[ERR] Lecture config/layout :", e)
        return 2

    # On écrase l'input_html avec le chemin généré par biduleur (bidul_html)
    mp_cfg.input_html = str(bidul_html)
    # On fixe le PDF de sortie
    mp_cfg.output_pdf = str(out_pdf)

    # project_root = dossier de la config, sauf si fourni
    project_root = Path(args.project_root).resolve() if args.project_root else cfg_path.parent.resolve()

    try:
        report = build_pdf(str(project_root), mp_cfg, mp_layout, str(out_pdf))
        print("[OK] PDF généré :", out_pdf)
        if report.get("unused_paragraphs"):
            print("[WARN]", report["unused_paragraphs"], "paragraphes non placés")
        return 0
    except Exception as e:
        print("[ERR] Échec build PDF misenpageur :", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())

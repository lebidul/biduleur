# -*- coding: utf-8 -*-
"""
CLI entrypoint for bidul_maker project.
"""
import argparse, pathlib
from misenpageur.misenpageur.config import Config
from misenpageur.misenpageur.layout import Layout
from misenpageur.misenpageur.pdfbuild import build_pdf

def main():
    parser = argparse.ArgumentParser(description="Bidul Maker — génération PDF S1..S8")
    parser.add_argument("--root", default=".", help="Racine du projet (dossier contenant config.yml, layout.yml)")
    parser.add_argument("--config", default="config.yml", help="Chemin du fichier de configuration YAML")
    parser.add_argument("--layout", default="layout.yml", help="Chemin du fichier de layout YAML")
    parser.add_argument("--out", default=None, help="Chemin de sortie PDF (écrase output_pdf du config si fourni)")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    cfg = Config.from_yaml(str(root / args.config))
    layout = Layout.from_yaml(str(root / args.layout))
    out_pdf = str(root / (args.out if args.out else cfg.output_pdf))

    root.mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)

    report = build_pdf(str(root), cfg, layout, out_pdf)
    print("PDF écrit :", out_pdf)
    if report.get("unused_paragraphs"):
        print("Attention:", report["unused_paragraphs"], "paragraphes non placés.")

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
main.py — Entrypoint CLI (version modulaire)

Essaie d'importer le package sous son nom *renommé* `misenpageur`,
puis retombe sur `bidul_maker` si nécessaire (compatibilité).
"""

import argparse
import pathlib
import sys

from misenpageur.config import Config
from misenpageur.layout import Layout
from misenpageur.pdfbuild import build_pdf

def parse_args():
    p = argparse.ArgumentParser(description="Génération PDF S1..S8 (main.py modulaire)")
    p.add_argument("--root", default=".", help="Racine du projet (contient config.yml, layout.yml)")
    p.add_argument("--config", default="config.yml", help="Chemin du fichier de configuration YAML")
    p.add_argument("--layout", default="layout.yml", help="Chemin du fichier de layout YAML")
    p.add_argument("--out", default="bidul/bidul.pdf", help="Chemin de sortie PDF (écrase output_pdf du config si fourni)")
    return p.parse_args()

def main():
    args = parse_args()
    root = pathlib.Path(args.root).resolve()
    cfg = Config.from_yaml(str(root / args.config))
    lay = Layout.from_yaml(str(root / args.layout))
    out_pdf = str(root / (args.out if args.out else cfg.output_pdf))

    # Dossiers
    root.mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)

    report = build_pdf(str(root), cfg, lay, out_pdf)
    print("PDF écrit :", out_pdf)
    unused = report.get("unused_paragraphs", 0)
    if unused:
        print("Attention:", unused, "paragraphes non placés.")

if __name__ == "__main__":
    main()

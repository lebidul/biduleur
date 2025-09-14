# misenpageur/misenpageur/pdfbuild.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from reportlab.pdfgen import canvas
from .config import Config
from .layout import Layout
from .draw_logic import  draw_document

def build_pdf(project_root: str, cfg: Config, layout: Layout, out_path: str, config_path: str) -> dict:
    """Crée un canvas PDF et appelle la logique de dessin principale."""
    c = canvas.Canvas(out_path, pagesize=(layout.page.width, layout.page.height))
    report = draw_document(c, project_root, cfg, layout, config_path)
    c.save()
    print(f"[INFO] Fichier PDF sauvegardé : {out_path}")
    return report

# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from typing import List, Tuple
from reportlab.pdfgen import canvas
from .config import Config
from .layout import Layout
from .html_utils import extract_paragraphs_from_html
from .drawing import draw_s1, draw_s2_cover, list_images
from .fonts import register_arial_narrow, register_dejavu_sans
from .textflow import measure_fit_at_fs, draw_section_fixed_fs

def read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _simulate_allocation_at_fs(
    c: canvas.Canvas, S, order: List[str], paras: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float
) -> Tuple[dict, int]:
    remaining = list(paras)
    used_by = {}
    total = 0
    for name in order:
        k = measure_fit_at_fs(c, S[name], remaining, font_name, font_size, leading_ratio, inner_pad)
        used_by[name] = remaining[:k]
        total += k
        remaining = remaining[k:]
    return used_by, total

def build_pdf(project_root: str, cfg: Config, layout: Layout, out_path: str) -> dict:
    report = {"unused_paragraphs": 0}

    c = canvas.Canvas(out_path, pagesize=(layout.page.width, layout.page.height))

    # Polices
    req = (cfg.font_name or "").strip().lower().replace(" ", "")
    if req in ("arialnarrow", "arialnarrowmt", "arial", "arialmt"):
        if register_arial_narrow():
            cfg.font_name = "ArialNarrow"
        else:
            print("[WARN] Arial Narrow introuvable - fallback Helvetica.")
            cfg.font_name = "Helvetica"
    register_dejavu_sans()

    # Inputs
    html_path = cfg.input_html if os.path.isabs(cfg.input_html) else os.path.join(project_root, cfg.input_html)
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"Fichier HTML introuvable: {html_path} (root={project_root})")
    html_text = read_text(html_path)
    paras: List[str] = extract_paragraphs_from_html(html_text)
    print("Paragraphes HTML:", len(paras))

    ours_text = read_text(os.path.join(project_root, cfg.ours_md))
    logos = list_images(os.path.join(project_root, cfg.logos_dir), max_images=10)
    cover_path = os.path.join(project_root, cfg.cover_image) if cfg.cover_image else ""

    S = layout.sections
    order = ["S5", "S6", "S3", "S4"]  # page 2 colonnes puis page 1 bas

    # --- Chercher la plus grande taille commune fs telle que TOUT tienne ---
    lo, hi = cfg.font_size_min, cfg.font_size_max
    best_fs = lo
    for _ in range(24):  # binaire
        mid = (lo + hi) / 2.0
        _alloc, tot = _simulate_allocation_at_fs(c, S, order, paras, cfg.font_name, mid, cfg.leading_ratio, cfg.inner_padding)
        if tot >= len(paras):
            best_fs = mid
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 0.05:
            break

    used_by_section, placed = _simulate_allocation_at_fs(c, S, order, paras, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding)
    remaining = len(paras) - placed
    if remaining > 0:
        # On n'accepte pas de restes : baisse ultime à fs_min si besoin
        used_by_section, placed = _simulate_allocation_at_fs(c, S, order, paras, cfg.font_name, cfg.font_size_min, cfg.leading_ratio, cfg.inner_padding)
        best_fs = cfg.font_size_min
        remaining = len(paras) - placed

    # Debug
    for k in order:
        print(k, "→", len(used_by_section.get(k, [])))
    print("fs_common:", round(best_fs, 2), "Restants:", remaining)

    # --- RENDU : PAGE 1 ---
    draw_s1(c, S["S1"], ours_text, logos, cfg.font_name, cfg.leading_ratio, cfg.inner_padding, layout.s1_split)
    draw_s2_cover(c, S["S2"], cover_path, cfg.inner_padding)

    draw_section_fixed_fs(c, S["S3"], used_by_section.get("S3", []), cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding)
    draw_section_fixed_fs(c, S["S4"], used_by_section.get("S4", []), cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding)
    c.showPage()

    # --- RENDU : PAGE 2 (2 colonnes S5|S6) ---
    drew = False
    if used_by_section.get("S5"):
        draw_section_fixed_fs(c, S["S5"], used_by_section["S5"], cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding)
        drew = True
    if used_by_section.get("S6"):
        draw_section_fixed_fs(c, S["S6"], used_by_section["S6"], cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding)
        drew = True
    if not drew:
        c.setFont("Helvetica", 1); c.drawString(0, 0, " ")
    c.save()

    report["unused_paragraphs"] = 0
    return report

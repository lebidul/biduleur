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
from .spacing import SpacingConfig, SpacingPolicy
from .textflow import (
    measure_fit_at_fs,
    draw_section_fixed_fs,
    draw_section_fixed_fs_with_prelude,
    draw_section_fixed_fs_with_tail,
    plan_pair_with_split,
)


def read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _simulate_allocation_at_fs(
    c: canvas.Canvas, S, order: List[str], paras: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    spacing_policy: SpacingPolicy,
) -> Tuple[dict, int]:
    remaining = list(paras)
    used_by = {}
    total = 0
    for name in order:
        k = measure_fit_at_fs(
            c, S[name], remaining, font_name, font_size, leading_ratio, inner_pad,
            section_name=name, spacing_policy=spacing_policy
        )
        used_by[name] = remaining[:k]
        total += k
        remaining = remaining[k:]
    return used_by, total


def build_pdf(project_root: str, cfg: Config, layout: Layout, out_path: str) -> dict:
    report = {"unused_paragraphs": 0}

    c = canvas.Canvas(out_path, pagesize=(layout.page.width, layout.page.height))

    # Polices (Arial Narrow + fallback glyphes)
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

    # Ours
    ours_path = cfg.ours_md if os.path.isabs(cfg.ours_md) else os.path.join(project_root, cfg.ours_md)
    if not os.path.exists(ours_path):
        print(f"[WARN] ours_md introuvable: {ours_path}")
        ours_text = "(Ours manquant — vérifiez config.yml: ours_md)"
    else:
        ours_text = read_text(ours_path)
        print(f"[INFO] ours_md: {ours_path} ({len(ours_text.encode('utf-8'))} bytes)")
        if not ours_text.strip():
            print(f"[WARN] ours_md vide: {ours_path}")
            ours_text = "(Ours vide — remplissez le fichier indiqué dans config.yml)"

    logos = list_images(os.path.join(project_root, cfg.logos_dir), max_images=10)
    cover_path = os.path.join(project_root, cfg.cover_image) if cfg.cover_image else ""

    S = layout.sections

    # --- Spacing Policy (config -> policy) ---
    spacing_cfg = SpacingConfig(
        date_spaceBefore=getattr(cfg, "date_spaceBefore", 6.0),
        date_spaceAfter=getattr(cfg, "date_spaceAfter", 3.0),
        event_spaceBefore=getattr(cfg, "event_spaceBefore", 1.0),
        event_spaceAfter=getattr(cfg, "event_spaceAfter", 1.0),
        event_spaceAfter_perLine=getattr(cfg, "event_spaceAfter_perLine", 0.4),
        min_event_spaceAfter=getattr(cfg, "min_event_spaceAfter", 1.0),
        first_non_event_spaceBefore_in_S5=getattr(cfg, "first_non_event_spaceBefore_in_S5", 0.0),
    )
    # leading provisoire pour initialiser la policy pendant la recherche fs
    from .drawing import paragraph_style
    tmp_style = paragraph_style(cfg.font_name, cfg.font_size_max, cfg.leading_ratio)
    spacing_policy_for_search = SpacingPolicy(spacing_cfg, tmp_style.leading)

    # --- Chercher la plus grande taille commune fs telle que tout rentre (mesure AVEC espacement) ---
    order_fs = ["S5", "S6", "S3", "S4"]
    lo, hi = cfg.font_size_min, cfg.font_size_max
    best_fs = lo
    for _ in range(24):  # binaire
        mid = (lo + hi) / 2.0
        style_mid = paragraph_style(cfg.font_name, mid, cfg.leading_ratio)
        spacing_mid = SpacingPolicy(spacing_cfg, style_mid.leading)

        _alloc, tot = _simulate_allocation_at_fs(
            c, S, order_fs, paras, cfg.font_name, mid, cfg.leading_ratio, cfg.inner_padding,
            spacing_policy=spacing_mid
        )
        if tot >= len(paras):
            best_fs = mid
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 0.05:
            break

    # Seuil de césure "utile" (configurable)
    split_min_gain_ratio = getattr(cfg, "split_min_gain_ratio", 0.10)
    # Policy finale (à best_fs)
    final_style = paragraph_style(cfg.font_name, best_fs, cfg.leading_ratio)
    spacing_policy = SpacingPolicy(spacing_cfg, final_style.leading)

    # --- PLANIFICATION par paires avec césure contrôlée (gain significatif) ---
    # Paire page 2 : S5 -> S6
    s5_full, s5_tail, s6_prelude, s6_full, rest_after_p2 = plan_pair_with_split(
        c, S["S5"], S["S6"], "S5", "S6", paras, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        split_min_gain_ratio=split_min_gain_ratio, spacing_policy=spacing_policy
    )
    # Paire page 1 (bas) : S3 -> S4 sur le reste
    s3_full, s3_tail, s4_prelude, s4_full, rest_after_p1 = plan_pair_with_split(
        c, S["S3"], S["S4"], "S3", "S4", rest_after_p2, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        split_min_gain_ratio=split_min_gain_ratio, spacing_policy=spacing_policy
    )

    if rest_after_p1:
        print(f"[WARN] {len(rest_after_p1)} paragraphes non placés (réduire font_size_max ou ajuster layout).")

    # --- RENDU : PAGE 1 ---
    draw_s1(c, S["S1"], ours_text, logos, cfg.font_name, cfg.leading_ratio, cfg.inner_padding, layout.s1_split)
    draw_s2_cover(c, S["S2"], cover_path, cfg.inner_padding)

    draw_section_fixed_fs_with_tail(
        c, S["S3"], s3_full, s3_tail, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S3", spacing_policy=spacing_policy
    )
    draw_section_fixed_fs_with_prelude(
        c, S["S4"], s4_prelude, s4_full, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S4", spacing_policy=spacing_policy
    )
    c.showPage()

    # --- RENDU : PAGE 2 ---
    draw_section_fixed_fs_with_tail(
        c, S["S5"], s5_full, s5_tail, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S5", spacing_policy=spacing_policy
    )
    draw_section_fixed_fs_with_prelude(
        c, S["S6"], s6_prelude, s6_full, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S6", spacing_policy=spacing_policy
    )

    # Finaliser
    c.save()
    report["unused_paragraphs"] = len(rest_after_p1)
    print("fs_common:", round(best_fs, 2), "split_min_gain_ratio:", split_min_gain_ratio)
    return report

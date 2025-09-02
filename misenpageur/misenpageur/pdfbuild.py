# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import List, Tuple

from reportlab.pdfgen import canvas

from .config import Config
from .layout import Layout
from .html_utils import extract_paragraphs_from_html
from .drawing import draw_s1, draw_s2_cover, list_images, paragraph_style
from .fonts import register_arial_narrow, register_dejavu_sans
from .spacing import SpacingConfig, SpacingPolicy
from .textflow import (
    BulletConfig, DateBoxConfig,
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


# ---------- AJOUT : helpers injection auteur dans l'ours ----------

def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;"))

def _inject_auteur_in_ours(ours_text: str, auteur: str, url: str, max_len: int = 47) -> str:
    """
    Met à jour la ligne 'Visuel : ...' dans l’ours :
      - Incruste 'auteur' (optionnellement cliquable) en respectant une longueur
        visible max (prefixe 'Visuel : ' + auteur ≤ max_len).
      - Si la ligne 'Visuel :' n’existe pas, on l’ajoute en fin d’ours.
      - Si 'auteur' est vide, on garde simplement 'Visuel :' (sans nom).
    Remarque : on ne touche qu’à la *première* ligne commençant par 'Visuel :'.
    """
    prefix = "Visuel : "
    auteur = (auteur or "").strip()
    url = (url or "").strip()

    # borner la longueur visible (prefix + auteur)
    if auteur:
        visible_total = len(prefix) + len(auteur)
        if visible_total > max_len:
            cutoff = max_len - len(prefix)
            auteur = auteur[:max(0, cutoff)]

    # fabriquer le segment auteur (avec lien si fourni)
    if not auteur:
        replacement = prefix.strip()
    else:
        if url:
            # ReportLab comprend <a href="...">...</a> dans Paragraph
            replacement = f'{prefix}<a href="{_xml_escape(url)}">{_xml_escape(auteur)}</a>'
        else:
            replacement = prefix + _xml_escape(auteur)

    lines = ours_text.splitlines()

    # 1) si on trouve une ligne 'Visuel : ...', on remplace
    for i, ln in enumerate(lines):
        if ln.strip().startswith("Visuel :"):
            lines[i] = replacement
            return "\n".join(lines)

    # 2) sinon, si l’ours contient explicitement "@Steph", on remplace ce token
    #    par le segment auteur (sans dupliquer 'Visuel : ') si la ligne ne commence pas déjà par 'Visuel :'.
    #    (Cas de compat rétro si le fichier n’a pas la ligne normalisée.)
    if "@Steph" in ours_text:
        repl = _xml_escape(auteur) if not url else f'<a href="{_xml_escape(url)}">{_xml_escape(auteur)}</a>'
        return ours_text.replace("@Steph", repl)

    # 3) à défaut, on ajoute une ligne à la fin
    lines.append(replacement)
    return "\n".join(lines)

# -----------------------------------------------------------------


def _simulate_allocation_at_fs(
    c: canvas.Canvas, S, order: List[str], paras: List[str],
    font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
    spacing_policy: SpacingPolicy,
    bullet_cfg: BulletConfig,
    date_box: DateBoxConfig,
) -> Tuple[dict, int]:
    remaining = list(paras)
    used_by = {}
    total = 0
    for name in order:
        k = measure_fit_at_fs(
            c, S[name], remaining, font_name, font_size, leading_ratio, inner_pad,
            section_name=name, spacing_policy=spacing_policy,
            bullet_cfg=bullet_cfg, date_box=date_box
        )
        used_by[name] = remaining[:k]
        total += k
        remaining = remaining[k:]
    return used_by, total


from collections.abc import Mapping

def _read_date_box_config(cfg: Config) -> DateBoxConfig:
    """Lit date_box depuis cfg, qu'il soit un dict, un Mapping (OmegaConf, etc.)
    ou un objet-namespace avec attributs. Fallback sur les clés à plat."""
    def as_bool(v, default=False):
        if v is None: return default
        if isinstance(v, bool): return v
        if isinstance(v, (int, float)): return bool(v)
        if isinstance(v, str): return v.strip().lower() in ("1", "true", "yes", "y", "on")
        return default

    def as_float(v, default):
        try:
            return float(v)
        except Exception:
            return default

    def get_from_block(b, key, default=None):
        if b is None:
            return default
        if isinstance(b, Mapping):
            return b.get(key, default)
        # objet type namespace (SimpleNamespace, Box, etc.)
        return getattr(b, key, default)

    block = getattr(cfg, "date_box", None)

    if block is not None:
        return DateBoxConfig(
            enabled=as_bool(get_from_block(block, "enabled"), False),
            padding=as_float(get_from_block(block, "padding"), 2.0),
            border_width=as_float(get_from_block(block, "border_width"), 0.5),
            border_color=get_from_block(block, "border_color", "#000000"),
            back_color=get_from_block(block, "back_color", None),
        )

    # Fallback : clés à plat
    return DateBoxConfig(
        enabled=as_bool(getattr(cfg, "date_box_enabled", False), False),
        padding=as_float(getattr(cfg, "date_box_padding", 2.0), 2.0),
        border_width=as_float(getattr(cfg, "date_box_border_width", 0.5), 0.5),
        border_color=getattr(cfg, "date_box_border_color", "#000000"),
        back_color=getattr(cfg, "date_box_back_color", None),
    )



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

    # >>> Injection auteur_couv (+ URL) dans l’ours, borne 47
    try:
        ours_text = _inject_auteur_in_ours(
            ours_text,
            getattr(cfg, "auteur_couv", "") or "",
            getattr(cfg, "auteur_couv_url", "") or "",
            max_len=47
        )
    except Exception as _e:
        # On ne casse pas la génération PDF si l’injection échoue
        print(f"[WARN] Échec injection auteur dans l’ours: {type(_e).__name__}: {_e}")

    logos = list_images(os.path.join(project_root, cfg.logos_dir), max_images=10)
    cover_path = os.path.join(project_root, cfg.cover_image) if cfg.cover_image else ""

    S = layout.sections

    # --- Spacing Policy & Bullet/DateBox ---
    spacing_cfg = SpacingConfig(
        date_spaceBefore=getattr(cfg, "date_spaceBefore", 6.0),
        date_spaceAfter=getattr(cfg, "date_spaceAfter", 3.0),
        event_spaceBefore=getattr(cfg, "event_spaceBefore", 1.0),
        event_spaceAfter=getattr(cfg, "event_spaceAfter", 1.0),
        event_spaceAfter_perLine=getattr(cfg, "event_spaceAfter_perLine", 0.4),
        min_event_spaceAfter=getattr(cfg, "min_event_spaceAfter", 1.0),
        first_non_event_spaceBefore_in_S5=getattr(cfg, "first_non_event_spaceBefore_in_S5", 0.0),
    )
    bullet_cfg = BulletConfig(
        show_event_bullet=getattr(cfg, "show_event_bullet", True),
        event_bullet_replacement=getattr(cfg, "event_bullet_replacement", None),
        event_hanging_indent=getattr(cfg, "event_hanging_indent", 10.0),
    )
    date_box = _read_date_box_config(cfg)
    print("[INFO] DateBoxConfig:", date_box, "type(cfg.date_box)=", type(getattr(cfg, "date_box", None)))

    # --- Chercher la plus grande taille commune fs (mesure AVEC spacing + indent + box) ---
    order_fs = ["S5", "S6", "S3", "S4"]
    lo, hi = cfg.font_size_min, cfg.font_size_max
    best_fs = lo
    for _ in range(24):  # binaire
        mid = (lo + hi) / 2.0
        style_mid = paragraph_style(cfg.font_name, mid, cfg.leading_ratio)
        spacing_mid = SpacingPolicy(spacing_cfg, style_mid.leading)

        _alloc, tot = _simulate_allocation_at_fs(
            c, S, order_fs, paras, cfg.font_name, mid, cfg.leading_ratio, cfg.inner_padding,
            spacing_policy=spacing_mid, bullet_cfg=bullet_cfg, date_box=date_box
        )
        if tot >= len(paras):
            best_fs = mid
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 0.05:
            break

    # Policies finales (à best_fs)
    final_style = paragraph_style(cfg.font_name, best_fs, cfg.leading_ratio)
    spacing_policy = SpacingPolicy(spacing_cfg, final_style.leading)

    # Seuil de césure "utile"
    split_min_gain_ratio = getattr(cfg, "split_min_gain_ratio", 0.10)

    # --- PLANIFICATION par paires avec césure contrôlée ---
    # Paire page 2 : S5 -> S6
    s5_full, s5_tail, s6_prelude, s6_full, rest_after_p2 = plan_pair_with_split(
        c, S["S5"], S["S6"], "S5", "S6", paras, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        split_min_gain_ratio=split_min_gain_ratio, spacing_policy=spacing_policy,
        bullet_cfg=bullet_cfg, date_box=date_box
    )
    # Paire page 1 (bas) : S3 -> S4
    s3_full, s3_tail, s4_prelude, s4_full, rest_after_p1 = plan_pair_with_split(
        c, S["S3"], S["S4"], "S3", "S4", rest_after_p2, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        split_min_gain_ratio=split_min_gain_ratio, spacing_policy=spacing_policy,
        bullet_cfg=bullet_cfg, date_box=date_box
    )
    if rest_after_p1:
        print(f"[WARN] {len(rest_after_p1)} paragraphes non placés (réduire font_size_max ou ajuster layout).")

    # --- RENDU : PAGE 1 ---
    draw_s1(c, S["S1"], ours_text, logos, cfg.font_name, cfg.leading_ratio, cfg.inner_padding, layout.s1_split)
    draw_s2_cover(c, S["S2"], cover_path, cfg.inner_padding)

    draw_section_fixed_fs_with_tail(
        c, S["S3"], s3_full, s3_tail, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S3", spacing_policy=spacing_policy, bullet_cfg=bullet_cfg, date_box=date_box
    )
    draw_section_fixed_fs_with_prelude(
        c, S["S4"], s4_prelude, s4_full, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S4", spacing_policy=spacing_policy, bullet_cfg=bullet_cfg, date_box=date_box
    )
    c.showPage()

    # --- RENDU : PAGE 2 ---
    draw_section_fixed_fs_with_tail(
        c, S["S5"], s5_full, s5_tail, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S5", spacing_policy=spacing_policy, bullet_cfg=bullet_cfg, date_box=date_box
    )
    draw_section_fixed_fs_with_prelude(
        c, S["S6"], s6_prelude, s6_full, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S6", spacing_policy=spacing_policy, bullet_cfg=bullet_cfg, date_box=date_box
    )

    # Finaliser
    c.save()
    report["unused_paragraphs"] = len(rest_after_p1)
    print("fs_common:", round(best_fs, 2), "split_min_gain_ratio:", split_min_gain_ratio)
    return report

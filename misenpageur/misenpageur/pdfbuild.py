# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import List, Tuple

from reportlab.pdfgen import canvas

# Ces imports sont conservés car ils sont utilisés par le reste de la fonction
from .config import Config
from .layout import Layout
from .html_utils import extract_paragraphs_from_html
from .drawing import draw_s1, draw_s2_cover, list_images, paragraph_style  # draw_s1 sera la nouvelle fonction
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
import io
import subprocess
from pathlib import Path
from PIL import Image  # Pillow

PT_PER_INCH = 72.0
MM_PER_INCH = 25.4


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_INCH / MM_PER_INCH


def _pp_get(cfg, key, default=None):
    pp = getattr(cfg, "prepress", {}) or {}
    return pp.get(key, default)


def _effective_dpi(img_px_w: int, img_px_h: int, placed_w_pt: float, placed_h_pt: float) -> float:
    # DPI = pixels / pouces ; pouces = points / 72
    if placed_w_pt <= 0 or placed_h_pt <= 0:
        return 0.0
    dpi_w = img_px_w / (placed_w_pt / PT_PER_INCH)
    dpi_h = img_px_h / (placed_h_pt / PT_PER_INCH)
    return min(dpi_w, dpi_h)


def _prepare_cover_for_print(src_path: str, target_w_pt: float, target_h_pt: float, cfg: Config) -> str:
    """
    Convertit la couverture en CMYK (si demandé), assure un JPEG qualité prepress,
    et avertit si le DPI est insuffisant. Retourne le chemin d'un fichier temporaire prêt à insérer.
    Si convert_images=False, on renvoie simplement src_path.
    """
    if not src_path or not os.path.exists(src_path):
        return src_path

    convert = bool(_pp_get(cfg, "convert_images", False))
    jpeg_quality = int(_pp_get(cfg, "jpeg_quality", 95))
    min_dpi = float(_pp_get(cfg, "min_effective_dpi", 300))
    max_dpi = float(_pp_get(cfg, "max_effective_dpi", 0.0) or 0.0)
    icc_cmyk = _pp_get(cfg, "cmyk_profile", "") or ""

    try:
        img = Image.open(src_path)
    except Exception:
        return src_path

    # Calcule le DPI effectif au format placé
    eff_dpi = _effective_dpi(img.width, img.height, target_w_pt, target_h_pt)
    if eff_dpi and eff_dpi < min_dpi:
        print(f"[WARN] Couverture: DPI effectif {eff_dpi:.0f} < {min_dpi} — qualité d’impression risquée.")

    if not convert:
        # Pas de conversion -> on laisse l'image telle quelle
        return src_path

    # Conversion CMYK (avec ou sans profil)
    try:
        img2 = img.convert(
            "CMYK")  # conversion basique ; pour gestion ICC complète, utiliser LittleCMS via Pillow (ImageCms)
    except Exception:
        img2 = img

    # Optionnel: réduction si surdimensionnement extrême (max_effective_dpi)
    if max_dpi > 0 and eff_dpi > max_dpi:
        # Scale down proportionnel pour viser ~max_dpi
        scale = max_dpi / eff_dpi
        new_w = max(1, int(img2.width * scale))
        new_h = max(1, int(img2.height * scale))
        img2 = img2.resize((new_w, new_h), Image.LANCZOS)
        print(f"[INFO] Couverture: downscale -> {new_w}x{new_h} px (~{max_dpi:.0f} DPI)")

    # Sauvegarde JPEG CMYK de haute qualité dans un tmp
    tmp_dir = Path(os.path.dirname(cfg.output_pdf) or ".") / "_tmp_prepress"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / "cover_cmyk.jpg"

    save_kwargs = dict(quality=jpeg_quality, subsampling=0, optimize=True)
    try:
        img2.save(out_path, format="JPEG", **save_kwargs)
    except OSError:
        # Si image en palette/transparence -> converti en RGB puis CMYK simple
        img2 = img.convert("RGB").convert("CMYK")
        img2.save(out_path, format="JPEG", **save_kwargs)

    return str(out_path)


def _draw_crop_marks(c, page_w_pt: float, page_h_pt: float, bleed_mm: float = 0.0):
    """
    Trace des repères de coupe simples aux quatre coins.
    Les traits restent *à l’intérieur* de la page (universel et safe chez l’imprimeur).
    """
    if bleed_mm <= 0:
        bleed_pt = 0.0
    else:
        bleed_pt = mm_to_pt(bleed_mm)

    mark_len = mm_to_pt(5)  # longueur du trait ~5mm
    offset = mm_to_pt(3)  # écart par rapport au bord

    c.saveState()
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.3)

    # coin bas-gauche
    x0, y0 = offset, offset
    c.line(x0, y0, x0 + mark_len, y0)  # horizontal
    c.line(x0, y0, x0, y0 + mark_len)  # vertical

    # coin bas-droit
    x1, y1 = page_w_pt - offset, offset
    c.line(x1 - mark_len, y1, x1, y1)
    c.line(x1, y1, x1, y1 + mark_len)

    # coin haut-gauche
    x2, y2 = offset, page_h_pt - offset
    c.line(x2, y2, x2 + mark_len, y2)
    c.line(x2, y2 - mark_len, x2, y2)

    # coin haut-droit
    x3, y3 = page_w_pt - offset, page_h_pt - offset
    c.line(x3 - mark_len, y3, x3, y3)
    c.line(x3, y3 - mark_len, x3, y3)

    c.restoreState()


def _ghostscript_pdfx(input_pdf: str, output_pdf: str, icc: str, gs: str = "gswin64c") -> bool:
    """
    Conversion PDF -> PDF/X-1a via Ghostscript. Retourne True si OK.
    Nécessite Ghostscript installé & accessible.
    """
    if not input_pdf or not os.path.exists(input_pdf):
        return False
    args = [
        gs, "-dBATCH", "-dNOPAUSE",
        "-dSAFER", "-dCompatibilityLevel=1.4",
        "-dPDFX", "-sColorConversionStrategy=CMYK",
        "-sDEVICE=pdfwrite",
        f"-sOutputFile={output_pdf}",
    ]
    if icc and os.path.exists(icc):
        args.extend([f"-sOutputICCProfile={icc}"])
    args.append(input_pdf)
    try:
        res = subprocess.run(args, capture_output=True, text=True)
        if res.returncode != 0:
            print("[ERR] Ghostscript PDF/X:", res.stderr[:4000])
            return False
        return True
    except Exception as e:
        print(f"[ERR] Ghostscript non disponible: {e}")
        return False


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

    logos = list_images(os.path.join(project_root, cfg.logos_dir), max_images=16)  # Augmentation à 16 logos max
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

    # --- PREPRESS : paramètres ---
    add_crop = bool(_pp_get(cfg, "add_crop_marks", False))
    bleed_mm = float(_pp_get(cfg, "bleed_mm", 0.0))

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

    # ==================== MODIFICATION CI-DESSOUS ====================
    # On passe l'objet de configuration 'cfg' complet à la nouvelle fonction draw_s1.
    # L'ancienne fonction prenait plein de paramètres individuels.
    draw_s1(c, S["S1"], ours_text, logos, cfg, layout)
    # ====================== FIN DE LA MODIFICATION ======================

    # Couverture prétraitée (CMYK + JPEG qualité) selon config prepress
    prepped_cover = cover_path
    if cover_path and os.path.exists(cover_path):
        # Taille de la zone S2 (pour calcul du DPI effectif)
        s2w = getattr(S["S2"], "w", None) or S["S2"]["w"]
        s2h = getattr(S["S2"], "h", None) or S["S2"]["h"]
        prepped_cover = _prepare_cover_for_print(cover_path, s2w, s2h, cfg)

    if not cfg.skip_cover:
        draw_s2_cover(c, S["S2"], prepped_cover, cfg.inner_padding)

    draw_section_fixed_fs_with_tail(
        c, S["S3"], s3_full, s3_tail, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S3", spacing_policy=spacing_policy, bullet_cfg=bullet_cfg, date_box=date_box
    )
    draw_section_fixed_fs_with_prelude(
        c, S["S4"], s4_prelude, s4_full, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        section_name="S4", spacing_policy=spacing_policy, bullet_cfg=bullet_cfg, date_box=date_box
    )

    # Repères de coupe (page 1)
    if add_crop:
        _draw_crop_marks(c, layout.page.width, layout.page.height, bleed_mm)

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

    # Repères de coupe (page 2)
    if add_crop:
        _draw_crop_marks(c, layout.page.width, layout.page.height, bleed_mm)

    # Finaliser PDF
    c.save()

    # (Option) Post-traitement PDF/X via Ghostscript
    if bool(_pp_get(cfg, "pdfx", False)):
        gs = _pp_get(cfg, "ghostscript_path", "gswin64c")
        icc = _pp_get(cfg, "pdfx_icc", "")
        out_pdfx = os.path.splitext(out_path)[0] + ".pdfx.pdf"
        ok = _ghostscript_pdfx(out_path, out_pdfx, icc, gs=gs)
        if ok:
            try:
                os.replace(out_pdfx, out_path)
                print("[INFO] PDF/X-1a généré avec succès.")
            except Exception as e:
                print(f"[WARN] Impossible d’écraser le PDF par la version PDF/X: {e}")

    report["unused_paragraphs"] = len(rest_after_p1)
    print("fs_common:", round(best_fs, 2), "split_min_gain_ratio:", split_min_gain_ratio)
    return report
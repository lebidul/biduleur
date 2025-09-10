# misenpageur/misenpageur/pdfbuild.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import io
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
from collections.abc import Mapping

# --- Imports des bibliothèques externes ---
from PIL import Image
from reportlab.pdfgen import canvas
import qrcode
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph

# --- Imports des modules internes du projet ---
from .config import Config
from .layout import Layout, Section
from .html_utils import extract_paragraphs_from_html
from .drawing import draw_s1, draw_s2_cover, list_images, paragraph_style, draw_poster_logos
from .fonts import register_arial_narrow, register_dejavu_sans
from .spacing import SpacingConfig, SpacingPolicy
from .textflow import (
    BulletConfig, DateBoxConfig, DateLineConfig,
    measure_fit_at_fs, draw_section_fixed_fs_with_prelude, draw_section_fixed_fs_with_tail,
    plan_pair_with_split, measure_poster_fit_at_fs, draw_poster_text_in_frames,
    _is_event, _mk_style_for_kind, _mk_text_for_kind
)

# ... (toutes les fonctions helper de mm_to_pt à _read_poster_config sont correctes et inchangées) ...
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


def _read_date_line_config(cfg: Config) -> DateLineConfig:
    """Lit date_line depuis cfg et retourne un objet DateLineConfig."""

    def as_bool(v, default=False):
        if v is None: return default
        if isinstance(v, str): return v.strip().lower() in ("1", "true", "yes", "y", "on")
        return bool(v)

    def as_float(v, default):
        try:
            return float(v)
        except:
            return default

    block = getattr(cfg, "date_line", {}) or {}
    if isinstance(block, Mapping):
        return DateLineConfig(
            enabled=as_bool(block.get("enabled"), False),
            width=as_float(block.get("width"), 0.5),
            color=block.get("color", "#000000"),
            gap_after_text_mm=as_float(block.get("gap_after_text_mm"), 3.0),
        )
    return DateLineConfig()  # Fallback


@dataclass
class PosterConfig:
    enabled: bool = False
    title: str = "L'AGENDA COMPLET"
    font_name_title: str = "Helvetica-Bold"
    font_size_title: float = 24.0
    font_size_min: float = 6.0
    font_size_max: float = 10.0
    font_size_safety_factor: float = 0.98 # Réduit la taille de police finale de 2%


def _read_poster_config(cfg: Config) -> PosterConfig:
    block = getattr(cfg, "poster", {}) or {}
    return PosterConfig(
        enabled=block.get("enabled", False),
        title=block.get("title", "L'AGENDA COMPLET"),
        font_name_title=block.get("font_name_title", "Helvetica-Bold"),
        font_size_title=float(block.get("font_size_title", 24.0)),
        font_size_min=float(block.get("font_size_min", 6.0)),
        font_size_max=float(block.get("font_size_max", 10.0)),
        font_size_safety_factor=float(block.get("font_size_safety_factor", 0.98)),
    )


def _create_poster_story(
        paras_text: List[str], font_name: str, font_size: float,
        leading_ratio: float, bullet_cfg: BulletConfig
) -> List[Paragraph]:
    """Crée la liste d'objets Paragraph pour le poster."""
    base_style = paragraph_style(font_name, font_size, leading_ratio)
    story = []
    for raw in paras_text:
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base_style, "EVENT", bullet_cfg, DateBoxConfig())
        txt = _mk_text_for_kind(raw, kind, bullet_cfg)
        story.append(Paragraph(txt, st))
    return story


def build_pdf(project_root: str, cfg: Config, layout: Layout, out_path: str) -> dict:
    report = {"unused_paragraphs": 0}
    c = canvas.Canvas(out_path, pagesize=(layout.page.width, layout.page.height))

    # --- Polices ---
    if register_arial_narrow():
        cfg.font_name = "ArialNarrow"
    else:
        print("[WARN] Police Arial Narrow introuvable - fallback sur Helvetica.")
        cfg.font_name = "Helvetica"
    register_dejavu_sans()

    # --- Inputs et contenus ---
    html_text = read_text(os.path.join(project_root, cfg.input_html))
    paras = extract_paragraphs_from_html(html_text)
    ours_text = read_text(os.path.join(project_root, cfg.ours_md))
    ours_text = _inject_auteur_in_ours(ours_text, cfg.auteur_couv, cfg.auteur_couv_url)
    logos = list_images(os.path.join(project_root, cfg.logos_dir))
    cover_path = os.path.join(project_root, cfg.cover_image) if cfg.cover_image else ""

    S = layout.sections

    # --- Configurations ---
    spacing_cfg = SpacingConfig()
    bullet_cfg = BulletConfig()
    date_box = _read_date_box_config(cfg)
    date_line = _read_date_line_config(cfg)

    # --- Calcul taille de police pour pages 1 & 2 ---
    order_fs = ["S5", "S6", "S3", "S4"]
    lo, hi = cfg.font_size_min, cfg.font_size_max
    best_fs = lo
    for _ in range(10):
        mid = (lo + hi) / 2.0
        style_mid = paragraph_style(cfg.font_name, mid, cfg.leading_ratio)
        spacing_mid = SpacingPolicy(spacing_cfg, style_mid.leading)
        _, tot = _simulate_allocation_at_fs(c, S, order_fs, paras, cfg.font_name, mid, cfg.leading_ratio,
                                            cfg.inner_padding, spacing_mid, bullet_cfg, date_box)
        if tot >= len(paras):
            best_fs, lo = mid, mid
        else:
            hi = mid
        if abs(hi - lo) < 0.1: break

    spacing_policy = SpacingPolicy(spacing_cfg, paragraph_style(cfg.font_name, best_fs, cfg.leading_ratio).leading)

    # --- Planification du texte ---
    s5_full, s5_tail, s6_prelude, s6_full, rest_after_p2 = plan_pair_with_split(
        c, S["S5"], S["S6"], "S5", "S6", paras, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        cfg.split_min_gain_ratio, spacing_policy, bullet_cfg, date_box
    )
    s3_full, s3_tail, s4_prelude, s4_full, rest_after_p1 = plan_pair_with_split(
        c, S["S3"], S["S4"], "S3", "S4", rest_after_p2, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        cfg.split_min_gain_ratio, spacing_policy, bullet_cfg, date_box
    )
    report["unused_paragraphs"] = len(rest_after_p1)

    # --- RENDU PAGE 1 ---
    draw_s1(c, S["S1"], ours_text, logos, cfg, layout)
    if not cfg.skip_cover:
        prepped_cover = _prepare_cover_for_print(cover_path, S["S2"].w, S["S2"].h, cfg)
        draw_s2_cover(c, S["S2"], prepped_cover, cfg.inner_padding)
    draw_section_fixed_fs_with_tail(c, S["S3"], s3_full, s3_tail, cfg.font_name, best_fs, cfg.leading_ratio,
                                    cfg.inner_padding, "S3", spacing_policy, bullet_cfg, date_box, date_line)
    draw_section_fixed_fs_with_prelude(c, S["S4"], s4_prelude, s4_full, cfg.font_name, best_fs, cfg.leading_ratio,
                                       cfg.inner_padding, "S4", spacing_policy, bullet_cfg, date_box, date_line)
    c.showPage()

    # --- RENDU PAGE 2 ---
    draw_section_fixed_fs_with_tail(c, S["S5"], s5_full, s5_tail, cfg.font_name, best_fs, cfg.leading_ratio,
                                    cfg.inner_padding, "S5", spacing_policy, bullet_cfg, date_box, date_line)
    draw_section_fixed_fs_with_prelude(c, S["S6"], s6_prelude, s6_full, cfg.font_name, best_fs, cfg.leading_ratio,
                                       cfg.inner_padding, "S6", spacing_policy, bullet_cfg, date_box, date_line)

    # --- RENDU PAGE 3 (POSTER) ---
    poster_cfg = _read_poster_config(cfg)
    best_fs_poster = poster_cfg.font_size_min
    if poster_cfg.enabled:
        c.showPage()

        S7 = {name: sec for name, sec in S.items() if sec.page == 3}

        # Dessin des éléments statiques
        s_title = S7["S7_Title"]
        c.setFont(poster_cfg.font_name_title, poster_cfg.font_size_title)
        c.drawCentredString(s_title.x + s_title.w / 2, s_title.y + (s_title.h - poster_cfg.font_size_title) / 2,
                            poster_cfg.title)

        if cover_path: c.drawImage(cover_path, S7["S7_CoverImage"].x, S7["S7_CoverImage"].y, S7["S7_CoverImage"].w,
                                   S7["S7_CoverImage"].h, preserveAspectRatio=True, anchor='c')

        qr_gen = qrcode.QRCode(version=1, border=1)
        qr_gen.add_data(cfg.section_1.get('qr_code_value', ''))
        qr_gen.make(fit=True)
        buffer = io.BytesIO()
        qr_gen.make_image().save(buffer, format='PNG')
        buffer.seek(0)
        c.drawImage(ImageReader(buffer), S7["S7_QRCode"].x, S7["S7_QRCode"].y, S7["S7_QRCode"].w, S7["S7_QRCode"].h,
                    mask='auto')

        draw_poster_logos(c, S7["S7_Logos"], logos)

        # Préparation du texte et des cadres
        poster_paras = s5_full + s6_full + s3_full + s4_full
        poster_frames = [S7[name] for name in
                         # ["S7_Col1", "S7_Col2_Top", "S7_Col2_Bottom", "S7_Col3_Top", "S7_Col3_BesideQR"]]
                        ["S7_Col1", "S7_Col2_Top", "S7_Col2_Bottom", "S7_Col3_Top"]]

        lo, hi = poster_cfg.font_size_min, poster_cfg.font_size_max
        for _ in range(10):
            mid = (lo + hi) / 2.0
            if mid <= lo or mid >= hi: break

            # On passe les arguments nécessaires à la fonction de mesure
            if measure_poster_fit_at_fs(c, poster_frames, poster_paras, cfg.font_name, mid, cfg.leading_ratio,
                                        bullet_cfg):
                best_fs_poster, lo = mid, mid
            else:
                hi = mid
            if abs(hi - lo) < 0.1: break

        final_fs_poster = best_fs_poster * poster_cfg.font_size_safety_factor

        # Dessin du texte
        # On passe les arguments nécessaires à la fonction de dessin
        draw_poster_text_in_frames(c, poster_frames, poster_paras, cfg.font_name, final_fs_poster, cfg.leading_ratio,
                                   bullet_cfg)


    c.save()

    # Affichage final
    print("-" * 20)
    print(f"Taille de police (pages 1-2): {best_fs:.2f} pt")
    if poster_cfg.enabled:
        print(f"Taille de police (poster)    : {best_fs_poster:.2f} pt")
        print(f"Taille de police (poster) avec marge de sécurité : {final_fs_poster:.2f} pt")
    print(f"Paragraphes non placés      : {len(rest_after_p1)}")
    print("-" * 20)

    return report
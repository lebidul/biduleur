# misenpageur/misenpageur/drawing_logic.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import io
import subprocess
from pathlib import Path
from typing import List, Tuple
from collections.abc import Mapping


# --- Imports des modules internes du projet ---
from .config import Config, BulletConfig, PosterConfig, DateBoxConfig, DateLineConfig
from .layout import Layout, Section
from .html_utils import extract_paragraphs_from_html
from .drawing import draw_s1, draw_s2_cover, list_images, paragraph_style, draw_poster_logos
from .fonts import register_arial_narrow, register_dejavu_sans, register_dsnet_stamped
from .spacing import SpacingConfig, SpacingPolicy
from .textflow import (
    measure_fit_at_fs, draw_section_fixed_fs_with_prelude, draw_section_fixed_fs_with_tail,
    plan_pair_with_split, measure_poster_fit_at_fs, draw_poster_text_in_frames,
    _is_event, _mk_style_for_kind, _mk_text_for_kind
)
from .utils import mm_to_pt

from PIL import Image, ImageStat
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import getFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
import qrcode
from reportlab.lib.utils import ImageReader
from reportlab.graphics.renderSVG import SVGCanvas
import xml.etree.ElementTree as ET

PT_PER_INCH = 72.0
MM_PER_INCH = 25.4

def _pp_get(cfg, key, default=None):
    pp = getattr(cfg, "prepress", {}) or {}
    return pp.get(key, default)


def _analyze_image_brightness(
        image_path: str,
        threshold: int = 128,
        transparency: float = 0.0  # 0.0 = image opaque, 1.0 = image invisible
) -> str:
    """
    Analyse la luminosité d'une image en tenant compte d'un voile blanc
    semi-transparent dont l'opacité est définie par 'transparency'.
    """
    if not image_path or not os.path.exists(image_path):
        return 'light'
    try:
        with Image.open(image_path) as img:
            img_l = img.convert('L')
            width, height = img_l.size
            zone = (width * 0.2, height * 0.2, width * 0.8, height * 0.8)
            cropped_img = img_l.crop(zone)
            avg_brightness_original = ImageStat.Stat(cropped_img).mean[0]

            # La transparence est l'opacité du voile blanc.
            # L'opacité de l'image est (1 - transparence).
            white_overlay_opacity = transparency
            image_opacity = 1.0 - transparency

            # Formule de mélange : (opacité_voile * couleur_voile) + (opacité_image * couleur_image)
            final_brightness = (white_overlay_opacity * 255) + (image_opacity * avg_brightness_original)

            print(f"[INFO] Luminosité originale: {avg_brightness_original:.1f}, "
                  f"Après voile (transparence={transparency:.2f}): {final_brightness:.1f}, "
                  f"Seuil: {threshold}")

            # On utilise la condition qui a du sens physiquement :
            # si la luminosité finale est basse, le fond est sombre.
            return 'dark' if final_brightness < threshold else 'light'

    except Exception as e:
        print(f"[WARN] Impossible d'analyser la luminosité de l'image : {e}")
        return 'light'


def _effective_dpi(img_px_w: int, img_px_h: int, placed_w_pt: float, placed_h_pt: float) -> float:
    # DPI = pixels / pouces ; pouces = points / 72
    if placed_w_pt <= 0 or placed_h_pt <= 0:
        return 0.0
    dpi_w = img_px_w / (placed_w_pt / PT_PER_INCH)
    dpi_h = img_px_h / (placed_h_pt / PT_PER_INCH)
    return min(dpi_w, dpi_h)


def _load_nobr_list_from_file(path: str) -> List[str]:
    """
    Charge une liste de termes depuis un fichier texte.
    Ignore les lignes vides et les commentaires (commençant par #).
    """
    if not path or not os.path.exists(path):
        return []

    nobr_list = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                nobr_list.append(line)
    return nobr_list

def _apply_non_breaking_strings(text: str, non_breaking: List[str]) -> str:
    """Remplace les espaces par des espaces insécables pour les chaînes spécifiées."""
    if not non_breaking:
        return text

    # On trie par longueur (du plus long au plus court) pour éviter les remplacements partiels
    # ex: remplacer "SAM SAUVAGE EXPERIENCE" avant "SAM SAUVAGE"
    for phrase in sorted(non_breaking, key=len, reverse=True):
        if phrase in text:
            # Créer la version avec des espaces insécables
            unbreakable_phrase = phrase.replace(" ", "\u00A0")
            # Remplacer dans le texte principal
            text = text.replace(phrase, unbreakable_phrase)

    return text


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


def _prepare_ours_svg_by_id(svg_template_content: str, auteur: str, url: str) -> str:
    """
    Injecte le nom de l'auteur dans un élément SVG identifié par son id.
    C'est une méthode plus robuste que le remplacement de chaîne.
    """
    auteur = (auteur or "").strip()

    # Enregistrer l'espace de nom SVG pour les recherches
    ET.register_namespace('', "http://www.w3.org/2000/svg")

    try:
        # Parser le contenu SVG depuis la chaîne de caractères
        root = ET.fromstring(svg_template_content)

        # Le namespace est crucial pour find()
        namespace = {'svg': 'http://www.w3.org/2000/svg'}

        # Trouver l'élément avec l'id 'auteur-placeholder'
        # La syntaxe .// recherche dans tout l'arbre
        target_element = root.find(".//*[@id='auteur-placeholder']", namespace)

        if target_element is not None:
            # On modifie le texte de l'élément.
            # S'il y a des <tspan> à l'intérieur, il faut cibler le bon.
            # Pour un texte simple, ceci suffit.
            target_element.text = auteur
        else:
            print("[WARN] L'élément avec id='auteur-placeholder' n'a pas été trouvé dans le SVG.")

        # Re-sérialiser l'arbre XML en une chaîne de caractères
        return ET.tostring(root, encoding='unicode')

    except ET.ParseError as e:
        print(f"[ERROR] Erreur de parsing du SVG : {e}")
        return svg_template_content  # Retourne l'original en cas d'erreur


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
    """
    Lit la configuration de la 'date_box' depuis l'objet Config.
    Cette version force la largeur de la bordure à 0 pour la désactiver.
    """

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
        if isinstance(b, Mapping):  # Compatible avec les dictionnaires
            return b.get(key, default)
        # Compatible avec les objets (dataclasses, etc.)
        return getattr(b, key, default)

    block = getattr(cfg, "date_box", None)

    if block is not None:
        return DateBoxConfig(
            enabled=as_bool(get_from_block(block, "enabled"), False),
            padding=as_float(get_from_block(block, "padding"), 2.0),
            border_width=0,
            border_color=None,
            back_color=get_from_block(block, "back_color", None),
        )

    # Fallback pour les anciennes configurations (clés à plat)
    # On applique la même logique de forcer la bordure à 0.
    return DateBoxConfig(
        enabled=as_bool(getattr(cfg, "date_box_enabled", False), False),
        padding=as_float(getattr(cfg, "date_box_padding", 2.0), 2.0),
        border_width=0,  # Forcer ici aussi
        border_color=None,
        back_color=getattr(cfg, "date_box_back_color", None),
    )

def _read_bullet_config(cfg: Config) -> BulletConfig:
    """Crée un objet BulletConfig à partir de la config principale."""
    return BulletConfig(
        show_event_bullet=cfg.show_event_bullet,
        event_bullet_replacement=cfg.event_bullet_replacement,
        event_hanging_indent=cfg.event_hanging_indent,
        bullet_text_indent=cfg.bullet_text_indent
    )

def _read_poster_config(cfg: Config) -> PosterConfig:
    block = cfg.poster
    return PosterConfig(
        enabled=block.get("enabled", False),
        design=int(block.get("design", 0)),
        title=block.get("title", "L'AGENDA COMPLET"),
        font_name_title=block.get("font_name_title", "Helvetica-Bold"),
        title_logo_path=block.get("title_logo_path", ""),
        title_back_color=block.get("title_back_color", "#7F7F7F"),
        font_size_title=float(block.get("font_size_title", 36.0)),
        font_size_min=float(block.get("font_size_min", 6.0)),
        font_size_max=float(block.get("font_size_max", 10.0)),
        font_size_safety_factor=float(block.get("font_size_safety_factor", 0.98)),
        background_image_alpha = float(block.get("background_image_alpha", 0.85)),
        date_spaceBefore=float(block.get("date_spaceBefore", 2.0)),
        date_spaceAfter=float(block.get("date_spaceAfter", 2.0))
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


def draw_document(c, project_root: str, cfg: Config, layout: Layout, config_path: str) -> dict:
    """
    Fonction de dessin principale, agnostique au format de sortie (PDF, SVG, etc.).
    Prend un 'canvas' ReportLab en entrée et y dessine toutes les pages.
    """
    report = {"unused_paragraphs": 0}

    # --- Polices ---
    register_dsnet_stamped()
    if register_arial_narrow():
        cfg.font_name = "ArialNarrow"
    else:
        print("[WARN] Police Arial Narrow introuvable - fallback sur Helvetica.")
        cfg.font_name = "Helvetica"
    register_dejavu_sans()

    def resolve_path(path_from_config: str, config_path: str) -> str:
        """
        Résout un chemin potentiellement relatif en se basant sur l'emplacement
        du fichier de configuration.
        """
        if not path_from_config: return ""
        p = Path(path_from_config)
        if p.is_absolute():
            return str(p)
        # Le chemin est relatif, on le joint au dossier du fichier de config
        config_dir = Path(config_path).parent
        return str((config_dir / p).resolve())

    # --- Inputs et contenus (Utilisation de os.path.join) ---
    html_text = read_text(os.path.join(project_root, cfg.input_html))
    paras = extract_paragraphs_from_html(html_text)

    nobr_list = []
    if cfg.nobr_file:
        nobr_list = _load_nobr_list_from_file(os.path.join(project_root, cfg.nobr_file))

    if nobr_list:
        paras = [_apply_non_breaking_strings(p, nobr_list) for p in paras]

    logos = list_images(os.path.join(project_root, cfg.logos_dir))
    cover_path = os.path.join(project_root, cfg.cover_image)

    S = layout.sections

    # --- Configurations ---
    spacing_cfg = SpacingConfig(
        date_spaceBefore=cfg.date_spaceBefore,
        date_spaceAfter=cfg.date_spaceAfter,
        event_spaceBefore=cfg.event_spaceBefore,
        event_spaceAfter=cfg.event_spaceAfter
    )
    bullet_cfg = _read_bullet_config(cfg)
    date_box = _read_date_box_config(cfg)
    date_line = _read_date_line_config(cfg)

    # --- Calcul taille de police & Planification du texte pour pages 1 & 2 ---
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
    s5_full, s5_tail, s6_prelude, s6_full, rest_after_p2 = plan_pair_with_split(
        c, S["S5"], S["S6"], "S5", "S6", paras, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        cfg.split_min_gain_ratio, spacing_policy, bullet_cfg, date_box
    )
    s3_full, s3_tail, s4_prelude, s4_full, rest_after_p1 = plan_pair_with_split(
        c, S["S3"], S["S4"], "S3", "S4", rest_after_p2, cfg.font_name, best_fs, cfg.leading_ratio, cfg.inner_padding,
        cfg.split_min_gain_ratio, spacing_policy, bullet_cfg, date_box
    )
    report["unused_paragraphs"] = len(rest_after_p1)
    report["font_size_main"] = best_fs


    def count_events(para_list: List[str]) -> int:
        return sum(1 for p in para_list if _is_event(p))

    # On compte les événements pour les pages 1 et 2
    events_p1 = count_events(s3_full) + count_events(s4_full)
    events_p2 = count_events(s5_full) + count_events(s6_full)

    # Le poster (page 3) contient tous les événements
    events_p3 = events_p1 + events_p2

    report["event_counts_per_page"] = {1: events_p1, 2: events_p2, 3: events_p3}

    # --- RENDU PAGE 1 & 2 ---
    draw_s1(c, S["S1"], logos, cfg, layout)
    if not cfg.skip_cover:
        prepped_cover = _prepare_cover_for_print(cover_path, S["S2"].w, S["S2"].h, cfg) # cover_path est déjà absolu
        draw_s2_cover(c, S["S2"], prepped_cover, cfg.inner_padding)
    draw_section_fixed_fs_with_tail(c, S["S3"], s3_full, s3_tail, cfg.font_name, best_fs, cfg.leading_ratio,
                                    cfg.inner_padding, "S3", spacing_policy, bullet_cfg, date_box, date_line)
    draw_section_fixed_fs_with_prelude(c, S["S4"], s4_prelude, s4_full, cfg.font_name, best_fs, cfg.leading_ratio,
                                       cfg.inner_padding, "S4", spacing_policy, bullet_cfg, date_box, date_line)
    c.showPage()
    draw_section_fixed_fs_with_tail(c, S["S5"], s5_full, s5_tail, cfg.font_name, best_fs, cfg.leading_ratio,
                                    cfg.inner_padding, "S5", spacing_policy, bullet_cfg, date_box, date_line)
    draw_section_fixed_fs_with_prelude(c, S["S6"], s6_prelude, s6_full, cfg.font_name, best_fs, cfg.leading_ratio,
                                       cfg.inner_padding, "S6", spacing_policy, bullet_cfg, date_box, date_line)

    # --- RENDU PAGE 3 (POSTER) ---
    poster_cfg = _read_poster_config(cfg)
    poster_cfg_dict = cfg.poster # On récupère le dictionnaire
    best_fs_poster = poster_cfg.font_size_min

    if poster_cfg.enabled:
        c.showPage()

        S7 = {name: sec for name, sec in S.items() if sec.page == 3}

        # --- Logique de Design ---
        poster_text_color = poster_cfg_dict.get("text_color_light_bg", "#000000")

        if poster_cfg.design == 1 and poster_cfg_dict.get("text_color_auto", False):
            threshold = poster_cfg_dict.get("brightness_threshold", 128)
            transparency_value = poster_cfg_dict.get("background_image_alpha", 0.0)
            background_type = _analyze_image_brightness(cover_path, threshold, transparency_value)

            if background_type == 'dark':
                poster_text_color = poster_cfg_dict.get("text_color_dark_bg", "#FFFFFF")
                print("[INFO] Fond sombre détecté, la police du poster passe en blanc.")
            if cover_path:
                # 1. Dessiner l'image de fond
                kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
                c.drawImage(cover_path, 0, 0, width=layout.page.width, height=layout.page.height,
                            preserveAspectRatio=True, anchor='c', **kwargs)

                # ==================== DESSIN DU VOILE DE TRANSPARENCE ====================
                # 2. Dessiner un rectangle blanc semi-transparent par-dessus
                c.saveState()
                # setFillColorRGB prend un 4ème argument pour l'alpha (transparence)
                c.setFillColorRGB(1, 1, 1, alpha=poster_cfg.background_image_alpha)
                # On dessine sur toute la page
                c.rect(0, 0, layout.page.width, layout.page.height, stroke=0, fill=1)
                c.restoreState()
                # =========================================================================

            poster_frames = [S7["S7_Col1"], S7["S7_Col2_Full"], S7["S7_Col3"]]
        else:
            if cover_path:
                kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
                c.drawImage(cover_path, S7["S7_CoverImage"].x, S7["S7_CoverImage"].y, S7["S7_CoverImage"].w,
                            S7["S7_CoverImage"].h, preserveAspectRatio=True, anchor='c', **kwargs)
            poster_frames = [S7[name] for name in ["S7_Col1", "S7_Col2_Top", "S7_Col2_Bottom", "S7_Col3"]]

        # --- Éléments communs ---
        s_title = S7["S7_Title"]

        # 1. Dessiner le rectangle de fond (inchangé)
        c.saveState()
        c.setFillColor(HexColor(poster_cfg.title_back_color))
        c.rect(s_title.x, s_title.y, s_title.w, s_title.h, stroke=0, fill=1)

        # 2. Dessiner le logo à gauche (inchangé)
        logo_end_x = s_title.x
        if poster_cfg.title_logo_path:
            logo_path = os.path.join(project_root, poster_cfg.title_logo_path)
            if os.path.exists(logo_path):
                padding = 4
                img = ImageReader(logo_path)
                img_w, img_h = img.getSize()

                logo_h = s_title.h - (2 * padding)
                logo_w = logo_h * (img_w / img_h)
                logo_x = s_title.x + padding
                logo_y = s_title.y + padding

                kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
                c.drawImage(img, logo_x, logo_y, width=logo_w, height=logo_h, **kwargs)
                logo_end_x = logo_x + logo_w + padding

        # 3. Dessiner le titre en blanc, parfaitement centré verticalement
        c.setFillColorRGB(1, 1, 1)  # Blanc
        c.setFont(poster_cfg.font_name_title, poster_cfg.font_size_title)

        # ==================== CORRECTION DU CENTRAGE VERTICAL ====================
        # On récupère les informations de la police
        font = getFont(poster_cfg.font_name_title)

        # La hauteur de capitale est une bonne approximation de la hauteur visuelle des lettres.
        cap_height = (font.face.capHeight / 1000) * poster_cfg.font_size_title

        # Calcul du centre de la zone de texte restante (horizontal)
        text_area_x = logo_end_x
        text_area_w = (s_title.x + s_title.w) - text_area_x
        center_x = text_area_x + (text_area_w / 2)

        # Calcul de la position y pour un centrage visuel parfait
        # On positionne la ligne de base pour que la hauteur de capitale soit centrée dans la hauteur du cadre.
        center_y = s_title.y + (s_title.h / 2) - (cap_height / 2)
        # =========================================================================

        c.drawCentredString(center_x, center_y, poster_cfg.title)
        c.restoreState()
        # =================================================================

        s_qr = S7["S7_QRCode"]
        qr_gen = qrcode.QRCode(version=1, border=1)
        qr_gen.add_data(cfg.section_1.get('qr_code_value', ''))
        qr_gen.make(fit=True)
        buffer = io.BytesIO()
        qr_gen.make_image().save(buffer, format='PNG')
        buffer.seek(0)

        kwargs = {'mask': 'auto'} if not isinstance(c, SVGCanvas) else {}
        c.drawImage(ImageReader(buffer), s_qr.x, s_qr.y, s_qr.w, s_qr.h, **kwargs)

        draw_poster_logos(c, S7["S7_Logos"], logos)

        # --- Calcul de la taille de police ---
        poster_paras = s5_full + s6_full + s3_full + s4_full
        lo, hi = poster_cfg.font_size_min, poster_cfg.font_size_max
        for _ in range(10):
            mid = (lo + hi) / 2.0
            if mid <= lo or mid >= hi: break

            if measure_poster_fit_at_fs(
                c, poster_frames, poster_paras,
                cfg.font_name, mid, cfg.leading_ratio, bullet_cfg,
                poster_cfg,
                poster_text_color  # On passe la configuration du poster
            ):
                best_fs_poster, lo = mid, mid
            else:
                hi = mid
            if abs(hi - lo) < 0.1: break

        # --- Dessin du texte ---
        final_fs_poster = best_fs_poster * poster_cfg.font_size_safety_factor

        report["font_size_poster_optimal"] = best_fs_poster
        report["font_size_poster_final"] = final_fs_poster

        draw_poster_text_in_frames(
            c, poster_frames, poster_paras,
            cfg.font_name, final_fs_poster, cfg.leading_ratio, bullet_cfg,
            poster_cfg,
            poster_text_color  # On passe la configuration du poster
        )

    # --- Affichage final ---
    print("-" * 20)
    print(f"Taille de police (pages 1-2): {best_fs:.2f} pt")
    if poster_cfg.enabled:
        print(f"Taille de police (poster)    : {best_fs_poster * poster_cfg.font_size_safety_factor:.2f} pt (optimale: {best_fs_poster:.2f})")
    print(f"Paragraphes non placés      : {len(rest_after_p1)}")
    print("-" * 20)

    return report
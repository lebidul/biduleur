# misenpageur/misenpageur/textflow.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase.pdfmetrics import stringWidth

from .layout import Section
from .drawing import paragraph_style
from .html_utils import sanitize_inline_markup
from .glyphs import apply_glyph_fallbacks
from .spacing import SpacingPolicy

from .config import BulletConfig, DateBoxConfig, DateLineConfig, DateStyleConfig, PosterConfig

PT_PER_INCH = 72.0
MM_PER_INCH = 25.4

# Chemin vers les icônes (relatif au dossier parent du module)
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_DIR = os.path.dirname(_MODULE_DIR)  # Remonter d'un niveau (misenpageur/misenpageur -> misenpageur)
CHAPEAU_ICON_PATH = os.path.join(_PACKAGE_DIR, "assets", "icons", "chapeau.png")
FREE_ICON_PATH = os.path.join(_PACKAGE_DIR, "assets", "icons", "free.png")

# Placeholders ASCII simples qui ne seront pas modifiés par sanitize_inline_markup
CHAPEAU_PLACEHOLDER = "{{CHAPEAU}}"
FREE_PLACEHOLDER = "{{FREE}}"

# Pattern pour détecter les placeholders image {{IMG:filename.jpg}}
_IMG_PLACEHOLDER_RE = re.compile(r'^\{\{IMG:(.+?)\}\}$')

# Pattern pour détecter le préfixe {{BIDUL:xxx}} en début de date
_BIDUL_PREFIX_RE = re.compile(r'^\{\{BIDUL:([^\}]+)\}\}')

# Dossier par défaut pour les images inline (relatif au dossier package)
_INLINE_IMAGES_DIR = os.path.join(_PACKAGE_DIR, "assets", "images")

# Facteur de réduction des images inline (0.85 = 85% de la largeur de section, centré)
INLINE_IMAGE_SCALE = 0.85

# Indique si les images inline sont activées (True par défaut pour compatibilité)
_INLINE_IMAGES_ENABLED = True

# Marge en points avant/après chaque image inline
_INLINE_IMAGE_MARGIN = 1.0

# Auto-scaling des images inline trop grandes pour leur section
_INLINE_IMAGE_AUTO_SCALE = False

# Étiquette "Bidul #xxx" à gauche des dates right-aligned
_BIDUL_LABEL_ENABLED = False
_BIDUL_LABEL_COLOR = "#000000"
_BIDUL_LABEL_FORMAT = "Bidul #{num}"


def configure_bidul_label(enabled: bool = False, color: str = "#000000", fmt: str = "Bidul #{num}"):
    """Configure le rendu de l'étiquette 'Bidul #xxx' côté gauche des dates."""
    global _BIDUL_LABEL_ENABLED, _BIDUL_LABEL_COLOR, _BIDUL_LABEL_FORMAT
    _BIDUL_LABEL_ENABLED = bool(enabled)
    _BIDUL_LABEL_COLOR = color or "#000000"
    _BIDUL_LABEL_FORMAT = fmt or "Bidul #{num}"


def _draw_bidul_label(c, raw: str, x_left: float, y_top: float, font_size: float,
                      date_style: "DateStyleConfig | None"):
    """
    Si `raw` commence par {{BIDUL:xxx}}, dessine l'étiquette 'Bidul #xxx'
    à la coordonnée (x_left, y_top - font_size) en alignement gauche,
    avec la couleur configurée.

    À appeler UNIQUEMENT quand la date est alignée à droite, sinon
    il y aurait chevauchement avec le texte de la date.
    """
    if not _BIDUL_LABEL_ENABLED or date_style is None:
        return
    if date_style.alignment != "right":
        return
    _stripped, num = _extract_bidul_prefix(raw)
    if not num:
        return
    try:
        label_text = _BIDUL_LABEL_FORMAT.format(num=num)
    except Exception:
        label_text = f"Bidul #{num}"
    font_name = date_style.font_name or getattr(c, '_fontname', 'Helvetica')
    c.saveState()
    try:
        c.setFont(font_name, font_size)
    except Exception:
        c.setFont("Helvetica", font_size)
    c.setFillColor(HexColor(_BIDUL_LABEL_COLOR))
    # y_top est le sommet du paragraphe date; on descend d'une ligne de hauteur ~font_size
    # pour aligner la baseline avec celle de la première ligne de la date
    baseline_y = y_top - font_size * 0.85
    c.drawString(x_left, baseline_y, label_text)
    c.restoreState()


def _extract_bidul_prefix(raw: str) -> tuple[str, str | None]:
    """
    Extrait le préfixe {{BIDUL:xxx}} d'une chaîne de date.
    Retourne (raw_sans_préfixe, num_bidul) ou (raw, None) si pas de préfixe.
    """
    if not raw:
        return raw, None
    m = _BIDUL_PREFIX_RE.match(raw)
    if not m:
        return raw, None
    return raw[m.end():], m.group(1)


def configure_inline_images(
        enabled: bool = True,
        images_dir: str = "",
        scale: float = 0.85,
        margin: float = 1.0,
        auto_scale: bool = False,
):
    """Configure les paramètres d'images inline depuis la Config.

    Appelé une fois au début du rendu PDF par draw_logic.py.
    """
    global _INLINE_IMAGES_DIR, INLINE_IMAGE_SCALE, _INLINE_IMAGES_ENABLED, \
        _INLINE_IMAGE_MARGIN, _INLINE_IMAGE_AUTO_SCALE
    _INLINE_IMAGES_ENABLED = enabled
    if images_dir and os.path.isdir(images_dir):
        _INLINE_IMAGES_DIR = images_dir
    elif not images_dir:
        _INLINE_IMAGES_DIR = os.path.join(_PACKAGE_DIR, "assets", "images")
    if 0.0 < scale <= 1.0:
        INLINE_IMAGE_SCALE = scale
    _INLINE_IMAGE_MARGIN = max(0.0, margin)
    _INLINE_IMAGE_AUTO_SCALE = bool(auto_scale)


def _compute_image_dimensions(
        image_path: str,
        section_width: float,
        available_height: float,
        margin: float,
) -> tuple[float, float] | None:
    """
    Calcule les dimensions (img_w, img_h) auxquelles l'image sera rendue,
    en tenant compte de l'échelle utilisateur et de l'auto-scaling éventuel.

    Retourne None si l'image ne peut pas être placée du tout
    (hauteur utile ≤ 0, ou auto_scale désactivé et image trop grande).

    Flow :
    - Taille "idéale" : largeur = section_width * INLINE_IMAGE_SCALE
    - Hauteur calculée depuis le ratio d'aspect à cette largeur
    - Si ça rentre dans available_height (moins 2*margin) : on retourne tel quel
    - Sinon, si auto_scale est ON : on réduit la hauteur pour tenir et
      on ajuste la largeur proportionnellement
    - Sinon (auto_scale OFF) : None
    """
    img_w_natural = section_width * INLINE_IMAGE_SCALE
    img_h_natural = _calc_image_height_for_width(image_path, img_w_natural)
    needed = img_h_natural + 2 * margin

    if needed <= available_height:
        return (img_w_natural, img_h_natural)

    if not _INLINE_IMAGE_AUTO_SCALE:
        return None

    # Auto-scaling : réduire la hauteur pour tenir dans available_height - 2*margin
    max_h = available_height - 2 * margin
    if max_h <= 0:
        return None

    size = _get_inline_image_size(image_path)
    if not size or size[0] <= 0 or size[1] <= 0:
        return None
    orig_w, orig_h = size
    # Garder le même ratio d'aspect : new_w / new_h = orig_w / orig_h
    new_w = max_h * orig_w / orig_h
    # Ne jamais dépasser la largeur idéale (pas d'agrandissement au-dessus de INLINE_IMAGE_SCALE)
    if new_w > img_w_natural:
        new_w = img_w_natural
        new_h = _calc_image_height_for_width(image_path, new_w)
        if new_h + 2 * margin > available_height:
            return None
        return (new_w, new_h)
    return (new_w, max_h)

# Cache pour les dimensions des images inline {path: (width, height)}
_INLINE_IMAGE_SIZE_CACHE: dict[str, tuple[int, int] | None] = {}


def _is_image(raw: str) -> bool:
    """Détecte si un paragraphe est un placeholder image {{IMG:...}}.

    Retourne False si les images inline sont désactivées.
    """
    if not _INLINE_IMAGES_ENABLED:
        return False
    return bool(_IMG_PLACEHOLDER_RE.match((raw or "").strip()))


def _get_image_path(raw: str) -> str | None:
    """Extrait le chemin complet de l'image depuis un placeholder {{IMG:filename}}."""
    m = _IMG_PLACEHOLDER_RE.match((raw or "").strip())
    if not m:
        return None
    filename = m.group(1)
    # Si c'est un chemin absolu, l'utiliser directement
    if os.path.isabs(filename):
        return filename
    # Sinon, chercher dans le dossier images
    return os.path.join(_INLINE_IMAGES_DIR, filename)


def _get_inline_image_size(image_path: str) -> tuple[int, int] | None:
    """Retourne (width, height) en pixels d'une image, avec cache."""
    if image_path in _INLINE_IMAGE_SIZE_CACHE:
        return _INLINE_IMAGE_SIZE_CACHE[image_path]
    try:
        with Image.open(image_path) as img:
            size = img.size  # (width, height)
            _INLINE_IMAGE_SIZE_CACHE[image_path] = size
            return size
    except Exception:
        _INLINE_IMAGE_SIZE_CACHE[image_path] = None
        return None


def _calc_image_height_for_width(image_path: str, target_width: float) -> float:
    """Calcule la hauteur d'une image redimensionnée à target_width (en points)."""
    size = _get_inline_image_size(image_path)
    if not size or size[0] == 0:
        return 0.0
    aspect = size[1] / size[0]  # height / width
    return target_width * aspect

# Regex compilées au niveau module pour éviter la recompilation à chaque appel
# Pattern pour "au chapeau" avec espaces normaux, &nbsp; et espaces insécables Unicode
_CHAPEAU_PATTERN = re.compile(r',?(?:\s|&nbsp;|\u00A0)*au(?:\s|&nbsp;|\u00A0)+chapeau', re.IGNORECASE)
# Pattern pour "0€" avec gestion des espaces et &euro;
# (?<![0-9]) = lookbehind négatif pour éviter de matcher "10€", "20€", etc.
_FREE_PATTERN = re.compile(r',?(?:\s|&nbsp;|\u00A0)*(?<![0-9])0(?:\s|&nbsp;|\u00A0)*(?:€|&euro;)', re.IGNORECASE)
# Pattern pour nettoyer les balises HTML (utilisé pour date_line)
_HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
# Pattern pour nettoyer les <br/> en début/fin de chaîne
_HEAD_BR_PATTERN = re.compile(r'^(?:\s*<br/>\s*)+')
_TAIL_BR_PATTERN = re.compile(r'(?:\s*<br/>\s*)+$')
_MULTI_BR_PATTERN = re.compile(r'(?:\s*<br/>\s*){3,}')

# Cache pour les métadonnées des icônes (aspect ratio)
# Clé: chemin de l'icône, Valeur: aspect ratio (width/height) ou None si erreur
_ICON_ASPECT_CACHE: dict[str, float | None] = {}


def _get_icon_aspect(icon_path: str) -> float | None:
    """
    Récupère l'aspect ratio d'une icône avec mise en cache.

    Returns:
        float: aspect ratio (width/height) ou None si l'icône n'existe pas ou erreur
    """
    if icon_path in _ICON_ASPECT_CACHE:
        return _ICON_ASPECT_CACHE[icon_path]

    if not os.path.exists(icon_path):
        _ICON_ASPECT_CACHE[icon_path] = None
        return None

    try:
        img = Image.open(icon_path)
        aspect = img.width / img.height
        img.close()
        _ICON_ASPECT_CACHE[icon_path] = aspect
        return aspect
    except Exception as e:
        print(f"[WARN] Erreur chargement icône {icon_path}: {e}")
        _ICON_ASPECT_CACHE[icon_path] = None
        return None


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_INCH / MM_PER_INCH


def _get_icon_img_tag(icon_path: str, font_size: float, scale: float = 0.8) -> str:
    """
    Génère la balise img pour une icône, dimensionnée selon la police.
    Utilise le cache pour éviter de recharger l'image à chaque appel.

    Args:
        icon_path: Chemin vers l'icône
        font_size: Taille de la police en points
        scale: Facteur d'échelle par rapport à la taille de police (défaut 0.8)

    Returns:
        str: Balise <img> ReportLab ou chaîne vide si l'icône n'existe pas
    """
    aspect = _get_icon_aspect(icon_path)
    if aspect is None:
        return ""

    img_h_pt = font_size * scale
    img_w_pt = img_h_pt * aspect

    return f'<img src="{icon_path}" width="{img_w_pt:.1f}" height="{img_h_pt:.1f}" valign="middle"/>'


def _get_chapeau_img_tag(font_size: float) -> str:
    """Génère la balise img pour l'icône chapeau."""
    return _get_icon_img_tag(CHAPEAU_ICON_PATH, font_size, scale=0.8)


def _get_free_img_tag(font_size: float) -> str:
    """Génère la balise img pour l'icône free."""
    return _get_icon_img_tag(FREE_ICON_PATH, font_size, scale=0.8)


def _replace_chapeau_placeholder(txt: str, font_size: float) -> str:
    """Remplace le placeholder chapeau par l'image avec la taille correcte."""
    if CHAPEAU_PLACEHOLDER not in txt:
        return txt

    img_tag = _get_chapeau_img_tag(font_size)
    if img_tag:
        return txt.replace(CHAPEAU_PLACEHOLDER, img_tag)
    return txt


def _replace_free_placeholder(txt: str, font_size: float) -> str:
    """Remplace le placeholder free par l'image avec la taille correcte."""
    if FREE_PLACEHOLDER not in txt:
        return txt

    img_tag = _get_free_img_tag(font_size)
    if img_tag:
        return txt.replace(FREE_PLACEHOLDER, img_tag)
    return txt


def _replace_all_placeholders(txt: str, font_size: float) -> str:
    """Remplace tous les placeholders d'icônes par les images."""
    txt = _replace_chapeau_placeholder(txt, font_size)
    txt = _replace_free_placeholder(txt, font_size)
    return txt


def apply_chapeau_to_paragraphs(paras: List[str]) -> List[str]:
    """
    Remplace "au chapeau" par un placeholder court dans les paragraphes.

    Cette fonction doit être appelée AVANT le calcul de la taille de police
    pour que le gain d'espace soit pris en compte. Le placeholder sera
    remplacé par l'image réelle lors du rendu (dans _mk_text_for_kind).

    Args:
        paras: Liste des paragraphes HTML

    Returns:
        Liste des paragraphes avec le placeholder
    """
    # Vérifier que l'icône existe
    if not os.path.exists(CHAPEAU_ICON_PATH):
        print(f"[WARN] Icône chapeau non trouvée: {CHAPEAU_ICON_PATH}")
        return paras

    result = []
    count = 0
    for p in paras:
        # Remplacer par ", " + placeholder pour garder la virgule
        new_p, n = _CHAPEAU_PATTERN.subn(', ' + CHAPEAU_PLACEHOLDER, p)
        count += n
        result.append(new_p)

    if count > 0:
        print(f"[CHAPEAU] {count} occurrences remplacées")

    return result


def apply_free_to_paragraphs(paras: List[str]) -> List[str]:
    """
    Remplace ", 0€" par un placeholder court dans les paragraphes.

    Args:
        paras: Liste des paragraphes HTML

    Returns:
        Liste des paragraphes avec le placeholder
    """
    # Vérifier que l'icône existe
    if not os.path.exists(FREE_ICON_PATH):
        print(f"[WARN] Icône free non trouvée: {FREE_ICON_PATH}")
        return paras

    result = []
    count = 0
    for p in paras:
        # Remplacer par ", " + placeholder pour garder la virgule
        new_p, n = _FREE_PATTERN.subn(', ' + FREE_PLACEHOLDER, p)
        count += n
        result.append(new_p)

    if count > 0:
        print(f"[FREE] {count} occurrences remplacées")

    return result


def apply_icon_replacements(paras: List[str], chapeau_enabled: bool = False, free_enabled: bool = False) -> List[str]:
    """
    Applique les remplacements d'icônes activés sur les paragraphes.

    Cette fonction doit être appelée AVANT le calcul de la taille de police.

    Args:
        paras: Liste des paragraphes HTML
        chapeau_enabled: Activer le remplacement "au chapeau"
        free_enabled: Activer le remplacement "0€"

    Returns:
        Liste des paragraphes avec les placeholders
    """
    result = paras

    if chapeau_enabled:
        result = apply_chapeau_to_paragraphs(result)

    if free_enabled:
        result = apply_free_to_paragraphs(result)

    return result


_BULLET_RE = re.compile(r'^\s*(?:❑|□|■|&#9643;)\s*', re.I)

# Cache pour les ParagraphStyle créés par _mk_style_for_kind
# Clé: tuple des paramètres pertinents, Valeur: ParagraphStyle
_STYLE_CACHE: dict[tuple, ParagraphStyle] = {}


def clear_style_cache() -> None:
    """Vide le cache des styles. À appeler entre les sessions de rendu si les configs changent."""
    _STYLE_CACHE.clear()


def _is_event(raw: str) -> bool:
    return bool(_BULLET_RE.match(raw or ""))


def _strip_leading_bullet(raw: str) -> str:
    return _BULLET_RE.sub("", raw or "", count=1).lstrip()


def _strip_head_tail_breaks(s: str) -> str:
    if not s: return ""
    s = _HEAD_BR_PATTERN.sub("", s)
    s = _TAIL_BR_PATTERN.sub("", s)
    s = _MULTI_BR_PATTERN.sub("<br/><br/>", s)
    return s.strip()


_ALIGNMENT_MAP = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}


def _mk_style_for_kind(base: ParagraphStyle, kind: str,
                       bullet_cfg: BulletConfig,
                       date_box: DateBoxConfig,
                       font_size: float = 10.0,
                       date_style: DateStyleConfig | None = None) -> ParagraphStyle:
    # Créer une clé de cache basée sur les paramètres qui influencent le style
    # NB: on inclut base.fontName pour invalider le cache quand la police du corps change
    base_font = getattr(base, 'fontName', '')
    if kind == "EVENT":
        cache_key = (
            "EVENT", base_font, font_size,
            bullet_cfg.event_hanging_indent,
            bullet_cfg.bullet_text_indent,
            bullet_cfg.bullet_size_ratio,
        )
        if cache_key in _STYLE_CACHE:
            return _STYLE_CACHE[cache_key]

        bullet_font_size = font_size * bullet_cfg.bullet_size_ratio
        style = ParagraphStyle(
            name=f"{base.name}_event", parent=base,
            leftIndent=bullet_cfg.event_hanging_indent,
            bulletFontSize=bullet_font_size,
            bulletIndent=bullet_cfg.bullet_text_indent,
            alignment=TA_JUSTIFY,
        )
        _STYLE_CACHE[cache_key] = style
        return style

    if kind == "DATE":
        ds = date_style or DateStyleConfig()
        ta = _ALIGNMENT_MAP.get(ds.alignment, TA_LEFT)
        ds_color = getattr(ds, "color", None) or "#000000"
        cache_key = (
            "DATE", base_font, font_size,
            date_box.enabled,
            date_box.border_width,
            date_box.border_color,
            date_box.back_color,
            date_box.padding,
            ta,
            ds.font_name,
            ds_color,
        )
        if cache_key in _STYLE_CACHE:
            return _STYLE_CACHE[cache_key]

        kwargs = {"alignment": ta, "textColor": HexColor(ds_color)}
        if ds.font_name:
            kwargs["fontName"] = ds.font_name
        if date_box.enabled:
            kwargs.update(
                borderWidth=date_box.border_width,
                borderColor=HexColor(date_box.border_color) if date_box.border_color else None,
                backColor=HexColor(date_box.back_color) if date_box.back_color else None,
                borderPadding=date_box.padding,
            )

        style = ParagraphStyle(
            name=f"{base.name}_date", parent=base,
            **kwargs,
        )
        _STYLE_CACHE[cache_key] = style
        return style

    return base


def _mk_text_for_kind(
        raw: str, kind: str, bullet_cfg: BulletConfig, font_size: float = 10.0,
        date_style: DateStyleConfig | None = None
) -> Tuple[str, Optional[str]]:
    # Pour les dates, retirer le préfixe {{BIDUL:xxx}} s'il existe
    # (il sera rendu séparément à gauche de la date)
    if kind == "DATE":
        raw, _bidul_num = _extract_bidul_prefix(raw)
    txt = _strip_head_tail_breaks(sanitize_inline_markup(raw))
    bullet_text = None
    if kind == "EVENT":
        if bullet_cfg.show_event_bullet:
            bullet_char = bullet_cfg.event_bullet_replacement or "❑"
            bullet_text = bullet_char
        txt = _strip_leading_bullet(txt)

    # Remplacer tous les placeholders d'icônes par les images
    txt = _replace_all_placeholders(txt, font_size)

    # Appliquer bold/italic pour les dates
    if kind == "DATE" and date_style:
        if date_style.italic:
            txt = f"<i>{txt}</i>"
        if date_style.bold:
            txt = f"<b>{txt}</b>"

    return apply_glyph_fallbacks(txt), bullet_text


def _classify_paragraph(raw: str) -> str:
    """Classifie un paragraphe: IMAGE, EVENT ou DATE."""
    if _is_image(raw):
        return "IMAGE"
    if _is_event(raw):
        return "EVENT"
    return "DATE"


def _compute_next_para_need(
        raw_next: str,
        w: float,
        font_size: float,
        base: "ParagraphStyle",
        bullet_cfg: "BulletConfig",
        date_box: "DateBoxConfig",
        date_style: "DateStyleConfig | None",
        spacing_policy: "SpacingPolicy",
        section_name: str,
        first_non_event_seen: bool,
) -> float:
    """
    Calcule la place verticale nécessaire pour placer le paragraphe suivant
    (event, date OU image) dans une section de largeur `w`.

    Retourne 0 si le paragraphe est une image manquante (fichier introuvable)
    — il sera silencieusement ignoré au rendu, donc ne provoque pas d'orphan.
    """
    next_kind = _classify_paragraph(raw_next)

    if next_kind == "IMAGE":
        image_path = _get_image_path(raw_next)
        if image_path and os.path.exists(image_path):
            img_margin = _INLINE_IMAGE_MARGIN
            # Utilise l'échelle naturelle (sans auto-scale) pour la vérification d'orphelin :
            # on veut savoir la taille IDÉALE de l'image, pas la taille réduite forcée.
            img_w = w * INLINE_IMAGE_SCALE
            img_h = _calc_image_height_for_width(image_path, img_w)
            return img_h + 2 * img_margin
        return 0.0

    # EVENT ou DATE (la DATE comme "suivante" est rare mais possible)
    next_st = _mk_style_for_kind(base, next_kind, bullet_cfg, date_box, font_size, date_style)
    next_txt, next_bullet = _mk_text_for_kind(raw_next, next_kind, bullet_cfg, font_size, date_style)
    next_p = Paragraph(next_txt, next_st, bulletText=next_bullet)
    _w, next_ph = next_p.wrap(w, 1e6)
    next_sb = spacing_policy.space_before(next_kind, section_name, first_non_event_seen)
    next_sa = spacing_policy.space_after(next_kind, next_ph)
    return next_sb + next_ph + next_sa


def measure_fit_at_fs(
        c: canvas.Canvas, section: Section, paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
        section_name: str, spacing_policy: SpacingPolicy,
        bullet_cfg: BulletConfig, date_box: DateBoxConfig,
        date_style: DateStyleConfig | None = None
) -> int:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y = y0 + h
    used = 0
    first_non_event_seen_in_S5 = False
    base = paragraph_style(font_name, font_size, leading_ratio)

    for i, raw in enumerate(paras_text):
        kind = _classify_paragraph(raw)

        # Image inline : hauteur calculée à partir du ratio d'aspect
        if kind == "IMAGE":
            image_path = _get_image_path(raw)
            if image_path and os.path.exists(image_path):
                img_margin = _INLINE_IMAGE_MARGIN
                dims = _compute_image_dimensions(image_path, w, y - y0, img_margin)
                if dims is None:
                    break
                _img_w, ph = dims
                need = ph + 2 * img_margin
                y -= need
                used += 1
            continue

        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, 1e6)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa

        # Vérifier si le paragraphe actuel rentre
        if (y - need) < y0:
            break

        # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas
        # Si c'est une DATE et qu'il reste des paragraphes après (EVENT ou IMAGE)
        if kind == "DATE" and i < len(paras_text) - 1:
            next_raw = paras_text[i + 1]
            next_need = _compute_next_para_need(
                next_raw, w, font_size, base, bullet_cfg, date_box, date_style,
                spacing_policy, section_name, first_non_event_seen_in_S5,
            )
            # Si on n'a pas assez de place pour la DATE + le paragraphe suivant, break
            if next_need > 0 and (y - need - next_need) < y0:
                break

        # Le paragraphe peut être placé
        y -= need
        used += 1

    return used


def draw_section_fixed_fs_with_prelude(
        c: canvas.Canvas, section: Section, prelude_flows: List[Paragraph],
        paras_text: List[str], font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
        section_name: str, spacing_policy: SpacingPolicy, bullet_cfg: BulletConfig,
        date_box: DateBoxConfig, date_line: DateLineConfig,
        date_style: DateStyleConfig | None = None
) -> None:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h
    base = paragraph_style(font_name, font_size, leading_ratio)
    first_non_event_seen_in_S5 = False
    c.saveState()
    y = y_top

    # Dessiner le prélude
    for pf in prelude_flows or []:
        _w, ph = pf.wrap(w, h)
        sa = spacing_policy.space_after("EVENT", ph)
        need = ph + sa
        if (y - need) < y0: c.restoreState(); return
        pf.drawOn(c, x0, y - ph)
        y -= need

    # Dessiner les paragraphes principaux
    for i, raw in enumerate(paras_text or []):
        kind = _classify_paragraph(raw)

        # Image inline
        if kind == "IMAGE":
            image_path = _get_image_path(raw)
            if image_path and os.path.exists(image_path):
                img_margin = _INLINE_IMAGE_MARGIN
                dims = _compute_image_dimensions(image_path, w, y - y0, img_margin)
                if dims is None:
                    break
                img_w, ph = dims
                y -= img_margin
                img_x = x0 + (w - img_w) / 2  # centrer horizontalement
                c.drawImage(image_path, img_x, y - ph, width=img_w, height=ph,
                            preserveAspectRatio=True, anchor='c')
                y -= ph + img_margin
            continue

        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, h)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa

        # Vérifier si le paragraphe actuel rentre
        if (y - need) < y0:
            break

        # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas
        if kind == "DATE" and i < len(paras_text) - 1:
            next_raw = paras_text[i + 1]
            next_need = _compute_next_para_need(
                next_raw, w, font_size, base, bullet_cfg, date_box, date_style,
                spacing_policy, section_name, first_non_event_seen_in_S5,
            )
            if next_need > 0 and (y - need - next_need) < y0:
                break

        # Dessiner le paragraphe
        y -= sb
        if kind == "DATE" and date_line.enabled:
            plain_text = _HTML_TAG_PATTERN.sub('', txt)
            text_width = c.stringWidth(plain_text, st.fontName, st.fontSize)
            gap_pt = mm_to_pt(date_line.gap_after_text_mm)
            line_x_start = x0 + text_width + gap_pt
            line_x_end = x0 + w
            if line_x_start < line_x_end:
                y_line = (y - ph) + (st.leading / 2)
                c.saveState()
                c.setStrokeColor(HexColor(date_line.color))
                c.setLineWidth(date_line.width)
                c.line(line_x_start, y_line, line_x_end, y_line)
                c.restoreState()
        p.drawOn(c, x0, y - ph)
        if kind == "DATE":
            _draw_bidul_label(c, raw, x0, y, font_size, date_style)
        y -= ph + sa

    c.restoreState()


def draw_section_fixed_fs_with_tail(
        c: canvas.Canvas, section: Section, paras_text: List[str],
        tail_flows: List[Paragraph], font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
        section_name: str, spacing_policy: SpacingPolicy, bullet_cfg: BulletConfig,
        date_box: DateBoxConfig, date_line: DateLineConfig,
        date_style: DateStyleConfig | None = None
) -> None:
    x0, y0 = section.x + inner_pad, section.y + inner_pad
    w, h = max(1.0, section.w - 2 * inner_pad), max(1.0, section.h - 2 * inner_pad)
    y_top = y0 + h
    base = paragraph_style(font_name, font_size, leading_ratio)
    first_non_event_seen_in_S5 = False
    c.saveState()
    y = y_top

    # Dessiner les paragraphes principaux
    for i, raw in enumerate(paras_text or []):
        kind = _classify_paragraph(raw)

        # Image inline
        if kind == "IMAGE":
            image_path = _get_image_path(raw)
            if image_path and os.path.exists(image_path):
                img_margin = _INLINE_IMAGE_MARGIN
                dims = _compute_image_dimensions(image_path, w, y - y0, img_margin)
                if dims is None:
                    c.restoreState()
                    return
                img_w, ph = dims
                y -= img_margin
                img_x = x0 + (w - img_w) / 2  # centrer horizontalement
                c.drawImage(image_path, img_x, y - ph, width=img_w, height=ph,
                            preserveAspectRatio=True, anchor='c')
                y -= ph + img_margin
            continue

        st = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        p = Paragraph(txt, st, bulletText=bullet)
        _w, ph = p.wrap(w, h)
        sb = spacing_policy.space_before(kind, section_name, first_non_event_seen_in_S5)
        if section_name == "S5" and kind == "DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(kind, ph)
        need = sb + ph + sa

        # Vérifier si le paragraphe actuel rentre
        if (y - need) < y0:
            c.restoreState()
            return

        # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas
        if kind == "DATE" and i < len(paras_text) - 1:
            next_raw = paras_text[i + 1]
            next_need = _compute_next_para_need(
                next_raw, w, font_size, base, bullet_cfg, date_box, date_style,
                spacing_policy, section_name, first_non_event_seen_in_S5,
            )
            if next_need > 0 and (y - need - next_need) < y0:
                c.restoreState()
                return

        # Dessiner le paragraphe
        y -= sb
        if kind == "DATE" and date_line.enabled:
            plain_text = _HTML_TAG_PATTERN.sub('', txt)
            text_width = c.stringWidth(plain_text, st.fontName, st.fontSize)
            gap_pt = mm_to_pt(date_line.gap_after_text_mm)
            line_x_start = x0 + text_width + gap_pt
            line_x_end = x0 + w
            if line_x_start < line_x_end:
                y_line = (y - ph) + (st.leading / 2)
                c.saveState()
                c.setStrokeColor(HexColor(date_line.color))
                c.setLineWidth(date_line.width)
                c.line(line_x_start, y_line, line_x_end, y_line)
                c.restoreState()
        p.drawOn(c, x0, y - ph)
        if kind == "DATE":
            _draw_bidul_label(c, raw, x0, y, font_size, date_style)
        y -= ph + sa

    # Dessiner le tail
    for tf in tail_flows or []:
        _w, ph = tf.wrap(w, h)
        sa = spacing_policy.space_after("EVENT", ph)
        if (y - (ph + sa)) < y0: break
        tf.drawOn(c, x0, y - ph)
        y -= ph + sa

    c.restoreState()


def plan_pair_with_split(
        c: canvas.Canvas, secA: Section, secB: Section,
        nameA: str, nameB: str, paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float, inner_pad: float,
        split_min_gain_ratio: float, spacing_policy: SpacingPolicy,
        bullet_cfg: BulletConfig, date_box: DateBoxConfig,
        date_style: DateStyleConfig | None = None
) -> Tuple[List[str], List[Paragraph], List[Paragraph], List[str], List[str]]:
    wA, hA = max(1.0, secA.w - 2 * inner_pad), max(1.0, secA.h - 2 * inner_pad)
    wB, hB = max(1.0, secB.w - 2 * inner_pad), max(1.0, secB.h - 2 * inner_pad)
    base = paragraph_style(font_name, font_size, leading_ratio)
    min_gain_pt = max(split_min_gain_ratio * hA, 0.9 * base.leading)
    remA, remB = hA, hB
    A_full, A_tail, B_prelude, B_full = [], [], [], []
    i, n = 0, len(paras_text)
    first_non_event_seen_in_S5_A, first_non_event_seen_in_S5_B = False, False
    while i < n and remA > 0:
        raw = paras_text[i]
        kind = _classify_paragraph(raw)

        # Image inline dans section A
        if kind == "IMAGE":
            image_path = _get_image_path(raw)
            if image_path and os.path.exists(image_path):
                img_margin = _INLINE_IMAGE_MARGIN
                dims = _compute_image_dimensions(image_path, wA, remA, img_margin)
                if dims is not None:
                    _img_w, ph = dims
                    needA_full = ph + 2 * img_margin
                    A_full.append(raw)
                    remA -= needA_full
                    i += 1
                    continue
            break

        stA = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txtA, bulletA = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        p = Paragraph(txtA, stA, bulletText=bulletA)
        _w, ph = p.wrap(wA, 1e6)
        sbA = spacing_policy.space_before(kind, nameA, first_non_event_seen_in_S5_A)
        if nameA == "S5" and kind == "DATE" and not first_non_event_seen_in_S5_A:
            first_non_event_seen_in_S5_A = True
        saA = spacing_policy.space_after(kind, ph)
        needA_full = sbA + ph + saA
        if needA_full <= remA:
            # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas de A
            if kind == "DATE" and i < n - 1:
                next_raw = paras_text[i + 1]
                next_need = _compute_next_para_need(
                    next_raw, wA, font_size, base, bullet_cfg, date_box, date_style,
                    spacing_policy, nameA, first_non_event_seen_in_S5_A,
                )
                # Si on n'a pas assez de place pour DATE + suivant, ne pas placer la DATE dans A
                if next_need > 0 and next_need > remA - needA_full:
                    break

            A_full.append(raw)
            remA -= needA_full
            i += 1
            continue
        avail_for_split_in_A = max(0.0, remA - sbA - spacing_policy.space_after("EVENT", base.leading))
        if avail_for_split_in_A > 0 and (ph > avail_for_split_in_A) and (ph <= (remA + remB)):
            parts = p.split(wA, avail_for_split_in_A)
            if parts and len(parts) >= 2:
                _w0, h0 = parts[0].wrap(wA, avail_for_split_in_A)
                if h0 >= min_gain_pt:
                    needB = sum(
                        part.wrap(wB, remB)[1] + spacing_policy.space_after("EVENT", part.wrap(wB, remB)[1]) for part in
                        parts[1:])
                    if needB <= remB:
                        A_tail.append(parts[0])
                        remA -= (sbA + h0 + spacing_policy.space_after("EVENT", h0))
                        for part in parts[1:]:
                            _wk, hk = part.wrap(wB, remB)
                            B_prelude.append(part)
                            remB -= (hk + spacing_policy.space_after("EVENT", hk))
                        i += 1
        break
    while i < n and remB > 0:
        raw = paras_text[i]
        kind = _classify_paragraph(raw)

        # Image inline dans section B
        if kind == "IMAGE":
            image_path = _get_image_path(raw)
            if image_path and os.path.exists(image_path):
                img_margin = _INLINE_IMAGE_MARGIN
                dims = _compute_image_dimensions(image_path, wB, remB, img_margin)
                if dims is not None:
                    _img_w, ph = dims
                    needB = ph + 2 * img_margin
                    B_full.append(raw)
                    remB -= needB
                    i += 1
                    continue
            break

        stB = _mk_style_for_kind(base, kind, bullet_cfg, date_box, font_size, date_style)
        txtB, bulletB = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style)
        q = Paragraph(txtB, stB, bulletText=bulletB)
        _w, hq = q.wrap(wB, 1e6)
        sbB = spacing_policy.space_before(kind, nameB, first_non_event_seen_in_S5_B)
        if nameB == "S5" and kind == "DATE" and not first_non_event_seen_in_S5_B:
            first_non_event_seen_in_S5_B = True
        saB = spacing_policy.space_after(kind, hq)
        needB = sbB + hq + saB
        if needB <= remB:
            # CONTRAINTE : Empêcher qu'une DATE se retrouve seule en bas de B
            if kind == "DATE" and i < n - 1:
                next_raw = paras_text[i + 1]
                next_need = _compute_next_para_need(
                    next_raw, wB, font_size, base, bullet_cfg, date_box, date_style,
                    spacing_policy, nameB, first_non_event_seen_in_S5_B,
                )
                # Si on n'a pas assez de place pour DATE + suivant, ne pas placer la DATE dans B
                if next_need > 0 and next_need > remB - needB:
                    break

            B_full.append(raw)
            remB -= needB
            i += 1
        else:
            break
    return A_full, A_tail, B_prelude, B_full, paras_text[i:]


def _build_poster_story(
        paras_text: List[str],
        base_style: ParagraphStyle,
        bullet_cfg: BulletConfig,
        poster_cfg: PosterConfig,
        font_size: float,
        date_box: DateBoxConfig | None = None,
        date_style: "DateStyleConfig | None" = None,
) -> list:
    """
    Construit la liste de flowables (Paragraphs) pour le poster.
    L'espacement des dates est intégré au style (spaceBefore/spaceAfter)
    plutôt qu'en Spacer séparés, ce qui évite le gaspillage d'espace
    aux transitions entre colonnes et permet à Frame de gérer
    correctement l'espacement (ignoré en haut de colonne, etc.).
    Utilisée à la fois par la mesure et le rendu pour garantir un résultat identique.
    """
    _date_box = date_box or DateBoxConfig()
    story: list = []
    for raw in paras_text:
        kind = "EVENT" if _is_event(raw) else "DATE"
        st = _mk_style_for_kind(base_style, kind, bullet_cfg, _date_box, font_size, date_style=date_style)
        txt, bullet = _mk_text_for_kind(raw, kind, bullet_cfg, font_size, date_style=date_style)

        if kind == "DATE":
            # Intégrer l'espacement dans le style (pas de Spacer séparés)
            st = ParagraphStyle(
                name=f"{st.name}_poster",
                parent=st,
                spaceBefore=poster_cfg.date_spaceBefore,
                spaceAfter=poster_cfg.date_spaceAfter,
            )

        story.append(Paragraph(txt, st, bulletText=bullet))

    return story


def measure_poster_fit_at_fs(
        c: canvas.Canvas, frames: List[Section], paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float,
        bullet_cfg: BulletConfig,
        poster_cfg: PosterConfig,
        text_color: str = "#000000",
        date_box: DateBoxConfig | None = None,
        date_style: "DateStyleConfig | None" = None,
) -> bool:
    """
    Teste si tout le contenu tient dans les cadres à la taille de police donnée.
    Utilise le même pipeline Frame que le rendu réel (canvas jetable) pour
    éliminer toute divergence de mesure (padding Frame, gestion des Spacers, etc.).
    """
    from io import BytesIO

    base_style = paragraph_style(font_name, font_size, leading_ratio)
    base_style.textColor = HexColor(text_color)
    story = _build_poster_story(paras_text, base_style, bullet_cfg, poster_cfg, font_size,
                                date_box=date_box, date_style=date_style)

    # Canvas jetable pour la mesure (on ne veut pas dessiner sur le vrai canvas)
    dummy_c = canvas.Canvas(BytesIO())

    for section in frames:
        if not story:
            break
        frame = Frame(section.x, section.y, section.w, section.h, showBoundary=0)
        frame.addFromList(story, dummy_c)

    return len(story) == 0


def draw_poster_text_in_frames(
        c: canvas.Canvas, frames: List[Section], paras_text: List[str],
        font_name: str, font_size: float, leading_ratio: float,
        bullet_cfg: BulletConfig,
        poster_cfg: PosterConfig,
        text_color: str = "#000000",
        date_box: DateBoxConfig | None = None,
        date_style: "DateStyleConfig | None" = None,
):
    """
    Dessine le texte dans une série de cadres avec le style des dates
    identique au corps principal (police, gras/italique, alignement, boîte).
    """
    base_style = paragraph_style(font_name, font_size, leading_ratio)
    base_style.textColor = HexColor(text_color)
    story = _build_poster_story(paras_text, base_style, bullet_cfg, poster_cfg, font_size,
                                date_box=date_box, date_style=date_style)

    for section in frames:
        if not story:
            break
        frame = Frame(section.x, section.y, section.w, section.h, showBoundary=0)
        frame.addFromList(story, c)
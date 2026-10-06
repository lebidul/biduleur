# -*- coding: utf-8 -*-
"""
✅ VERSION OPTIMISÉE : Gestion des polices avec subsetting

Améliorations :
1. Subsetting automatique (réduit la taille du PDF)
2. Meilleure gestion des polices manquantes
3. Logs détaillés pour debugging
4. Guard pour éviter les enregistrements multiples
"""
from __future__ import annotations
import os
from typing import Optional, Dict
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import logging

log = logging.getLogger(__name__)

# Guard pour éviter d'enregistrer les polices plusieurs fois
_REGISTERED_FONTS: set[str] = set()


def is_font_registered(name: str) -> bool:
    """Vérifie si une police est déjà enregistrée."""
    return name in _REGISTERED_FONTS


# -------------------- Helpers --------------------

def _register_font(name: str, path: str, subset: bool = True) -> bool:
    """
    Enregistre une police TrueType avec support du subsetting.
    Utilise un guard pour éviter les enregistrements multiples.

    Args:
        name: Nom de la police dans ReportLab
        path: Chemin vers le fichier .ttf
        subset: Active le subsetting (recommandé pour l'impression)

    Returns:
        True si succès ou déjà enregistrée, False sinon
    """
    # Guard : éviter les enregistrements multiples
    if name in _REGISTERED_FONTS:
        log.debug(f"Police '{name}' déjà enregistrée (skip)")
        return True

    try:
        font = TTFont(name, path)

        # ✅ NOUVEAU : Active le subsetting pour réduire la taille
        if subset and hasattr(font.face, 'subset'):
            font.face.subset = True
            log.debug(f"✅ Police '{name}' : subsetting activé")

        pdfmetrics.registerFont(font)
        _REGISTERED_FONTS.add(name)
        log.info(f"✅ Police enregistrée : {name} ({os.path.basename(path)})")
        return True

    except Exception as e:
        log.warning(f"⚠️  Échec registerFont {name} -> {path}: {e}")
        return False


def _register_family_partial(
        base: str,
        regular: Optional[str],
        bold: Optional[str],
        italic: Optional[str],
        bolditalic: Optional[str],
        subset: bool = True
) -> bool:
    """
    Enregistre une famille de polices avec support du subsetting.
    Les variantes manquantes sont mappées sur la régulière.

    Args:
        base: Nom de base de la famille
        regular, bold, italic, bolditalic: Chemins des variantes
        subset: Active le subsetting
    """
    if not regular or not _register_font(base, regular, subset=subset):
        log.error(f"❌ Police de base '{base}' introuvable")
        return False

    # Enregistrer les variantes (ou fallback vers regular)
    ok_b = _register_font(base + "-Bold", bold or regular, subset=subset)
    ok_i = _register_font(base + "-Italic", italic or regular, subset=subset)
    ok_bi = _register_font(base + "-BoldItalic", bolditalic or regular, subset=subset)

    # Créer la famille
    try:
        pdfmetrics.registerFontFamily(
            base,
            normal=base,
            bold=(base + "-Bold") if ok_b else base,
            italic=(base + "-Italic") if ok_i else base,
            boldItalic=(base + "-BoldItalic") if ok_bi else base,
        )
        log.info(f"✅ Famille '{base}' enregistrée (subsetting={'ON' if subset else 'OFF'})")
    except Exception as e:
        log.error(f"❌ Échec registerFontFamily {base}: {e}")
        return False

    return True


def _first_existing(paths: list[str]) -> Optional[str]:
    """Retourne le premier chemin existant dans la liste."""
    for p in paths:
        if p and os.path.exists(p):
            log.debug(f"   ✓ Trouvé : {p}")
            return p
    return None


def _fonts_roots() -> list[str]:
    """Répertoires où chercher les TTF (projet + système)."""
    here = os.path.dirname(__file__)
    roots = [
        # Project assets (plusieurs niveaux au cas où)
        os.path.abspath(os.path.join(here, "..", "assets", "fonts")),
        os.path.abspath(os.path.join(here, "..", "..", "assets", "fonts")),
        os.path.abspath(os.path.join(here, "..", "..", "..", "assets", "fonts")),
        # Linux
        "/usr/share/fonts/truetype/dejavu",
        "/usr/local/share/fonts",
        # Windows
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
        # macOS
        "/Library/Fonts",
        "/System/Library/Fonts",
    ]
    env = os.environ.get("BIDUL_FONTS_DIR")
    if env:
        roots.insert(0, env)
        log.debug(f"   Variable BIDUL_FONTS_DIR : {env}")

    return roots


# -------------------- Arial Narrow --------------------

def register_arial_narrow() -> bool:
    """
    Tente d'enregistrer la famille Arial Narrow (ArialNarrow) avec subsetting.
    Cherche dans C:\\Windows\\Fonts et dans assets/fonts/ArialNarrow/.
    """
    # Guard : éviter les recherches de fichiers si déjà enregistré
    if "ArialNarrow" in _REGISTERED_FONTS:
        log.debug("Arial Narrow déjà enregistré (skip)")
        return True

    log.info("Recherche de Arial Narrow...")

    # Noms Windows typiques
    win = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    win_candidates = {
        "regular": [os.path.join(win, "ARIALN.TTF")],
        "bold": [os.path.join(win, "ARIALNB.TTF")],
        "italic": [os.path.join(win, "ARIALNI.TTF")],
        "bolditalic": [os.path.join(win, "ARIALNBI.TTF")],
    }

    # Dossiers projet
    roots = _fonts_roots()
    proj_candidates = {"regular": [], "bold": [], "italic": [], "bolditalic": []}
    for r in roots:
        for sub in ("ArialNarrow", "arialnarrow", "Arial", "arial"):
            base = os.path.join(r, sub)
            proj_candidates["regular"] += [os.path.join(base, "ARIALN.TTF")]
            proj_candidates["bold"] += [os.path.join(base, "ARIALNB.TTF")]
            proj_candidates["italic"] += [os.path.join(base, "ARIALNI.TTF")]
            proj_candidates["bolditalic"] += [os.path.join(base, "ARIALNBI.TTF")]

    def find_one(kind: str) -> Optional[str]:
        # Windows d'abord
        p = _first_existing(win_candidates[kind])
        if p:
            return p
        # Puis projet/system
        return _first_existing(proj_candidates[kind])

    reg = find_one("regular")
    b = find_one("bold")
    i = find_one("italic")
    bi = find_one("bolditalic")

    if not reg:
        log.warning("⚠️  Arial Narrow introuvable")
        return False

    # ✅ Enregistrer avec subsetting activé
    ok = _register_family_partial("ArialNarrow", reg, b, i, bi, subset=True)
    return ok


def register_arial() -> bool:
    """
    Tente d'enregistrer la famille Arial standard avec subsetting.
    """
    if "Arial" in _REGISTERED_FONTS:
        log.debug("Arial déjà enregistré (skip)")
        return True

    log.info("Recherche de Arial...")

    win = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    win_candidates = {
        "regular": [os.path.join(win, "arial.ttf")],
        "bold": [os.path.join(win, "arialbd.ttf")],
        "italic": [os.path.join(win, "ariali.ttf")],
        "bolditalic": [os.path.join(win, "arialbi.ttf")],
    }

    roots = _fonts_roots()
    proj_candidates = {"regular": [], "bold": [], "italic": [], "bolditalic": []}
    for r in roots:
        for sub in ("Arial", "arial"):
            base = os.path.join(r, sub)
            proj_candidates["regular"] += [os.path.join(base, "arial.ttf"), os.path.join(r, "arial.ttf")]
            proj_candidates["bold"] += [os.path.join(base, "arialbd.ttf"), os.path.join(r, "arialbd.ttf")]
            proj_candidates["italic"] += [os.path.join(base, "ariali.ttf"), os.path.join(r, "ariali.ttf")]
            proj_candidates["bolditalic"] += [os.path.join(base, "arialbi.ttf"), os.path.join(r, "arialbi.ttf")]

    def find_one(kind: str) -> Optional[str]:
        p = _first_existing(win_candidates[kind])
        if p:
            return p
        return _first_existing(proj_candidates[kind])

    reg = find_one("regular")
    b = find_one("bold")
    i = find_one("italic")
    bi = find_one("bolditalic")

    if not reg:
        log.warning("⚠️  Arial introuvable")
        return False

    ok = _register_family_partial("Arial", reg, b, i, bi, subset=True)
    return ok


# -------------------- DejaVu Sans (fallback) --------------------

def register_dejavu_sans() -> bool:
    """
    Enregistre la famille DejaVuSans avec subsetting.
    Excellente police open-source avec support complet des glyphes (€, →, etc.)
    """
    if "DejaVuSans" in _REGISTERED_FONTS:
        log.debug("DejaVu Sans déjà enregistré (skip)")
        return True

    log.info("Recherche de DejaVu Sans...")

    roots = _fonts_roots()
    variants = {
        "regular": ["DejaVuSans.ttf", "DejaVuSans-Book.ttf"],
        "bold": ["DejaVuSans-Bold.ttf"],
        "italic": ["DejaVuSans-Oblique.ttf", "DejaVuSans-Italic.ttf"],
        "bolditalic": ["DejaVuSans-BoldOblique.ttf", "DejaVuSans-BoldItalic.ttf"],
    }

    def find(kind: str) -> Optional[str]:
        names = variants[kind]
        paths: list[str] = []
        for r in roots:
            for n in names:
                paths.append(os.path.join(r, n))
            for sub in ("DejaVu", "DejaVuSans"):
                for n in names:
                    paths.append(os.path.join(r, sub, n))
        return _first_existing(paths)

    reg = find("regular")
    b = find("bold")
    i = find("italic")
    bi = find("bolditalic")

    if not reg:
        log.warning("⚠️  DejaVuSans introuvable")
        return False

    ok = _register_family_partial("DejaVuSans", reg, b, i, bi, subset=True)
    return ok


# -------------------- DS-net Stamped --------------------

def register_dsnet_stamped() -> bool:
    """
    Tente d'enregistrer la police DS-net Stamped (pour le poster).
    """
    if "DSNetStamped" in _REGISTERED_FONTS:
        log.debug("DS-net Stamped déjà enregistré (skip)")
        return True

    log.info("Recherche de DS-net Stamped...")

    roots = _fonts_roots()
    font_filenames = ["DS-NET-STAMPED.TTF", "DSNetStamped.ttf", "dsnetstamped.ttf", "DSnet Stamped.ttf"]

    font_paths = []
    for r in roots:
        for fname in font_filenames:
            font_paths.append(os.path.join(r, fname))

    font_file = _first_existing(font_paths)

    if not font_file:
        log.warning("⚠️  DS-net Stamped introuvable")
        return False

    return _register_font("DSNetStamped", font_file, subset=True)


# -------------------- Autres polices --------------------

def register_helvetica() -> bool:
    """Tente d'enregistrer Helvetica avec subsetting."""
    if "Helvetica" in _REGISTERED_FONTS:
        log.debug("Helvetica déjà enregistré (skip)")
        return True

    log.info("Recherche de Helvetica...")

    roots = _fonts_roots()
    variants = {
        "regular": ["helvetica.ttf", "Helvetica.ttf", "LiberationSans-Regular.ttf"],
        "bold": ["helveticabd.ttf", "Helvetica-Bold.ttf", "LiberationSans-Bold.ttf"],
        "italic": ["helveticai.ttf", "Helvetica-Oblique.ttf", "LiberationSans-Italic.ttf"],
        "bolditalic": ["helveticabi.ttf", "Helvetica-BoldOblique.ttf", "LiberationSans-BoldItalic.ttf"],
    }

    def find(kind: str) -> Optional[str]:
        paths = [os.path.join(r, n) for r in roots for n in variants[kind]]
        return _first_existing(paths)

    reg, b, i, bi = find("regular"), find("bold"), find("italic"), find("bolditalic")
    if not reg:
        return False
    return _register_family_partial("Helvetica", reg, b, i, bi, subset=True)


def register_times() -> bool:
    """Tente d'enregistrer Times New Roman avec subsetting."""
    if "Times" in _REGISTERED_FONTS:
        log.debug("Times déjà enregistré (skip)")
        return True

    log.info("Recherche de Times New Roman...")

    roots = _fonts_roots()
    variants = {
        "regular": ["times.ttf", "timesnr.ttf", "Times New Roman.ttf", "LiberationSerif-Regular.ttf"],
        "bold": ["timesbd.ttf", "Times New Roman Bold.ttf", "LiberationSerif-Bold.ttf"],
        "italic": ["timesi.ttf", "Times New Roman Italic.ttf", "LiberationSerif-Italic.ttf"],
        "bolditalic": ["timesbi.ttf", "Times New Roman Bold Italic.ttf", "LiberationSerif-BoldItalic.ttf"],
    }

    def find(kind: str) -> Optional[str]:
        paths = [os.path.join(r, n) for r in roots for n in variants[kind]]
        return _first_existing(paths)

    reg, b, i, bi = find("regular"), find("bold"), find("italic"), find("bolditalic")
    if not reg:
        return False
    return _register_family_partial("Times New Roman", reg, b, i, bi, subset=True)


def register_courier() -> bool:
    """Tente d'enregistrer Courier New avec subsetting."""
    if "Courier New" in _REGISTERED_FONTS:
        log.debug("Courier New déjà enregistré (skip)")
        return True

    log.info("Recherche de Courier New...")

    roots = _fonts_roots()
    variants = {
        "regular": ["cour.ttf", "Courier New.ttf", "LiberationMono-Regular.ttf"],
        "bold": ["courbd.ttf", "Courier New Bold.ttf", "LiberationMono-Bold.ttf"],
        "italic": ["couri.ttf", "Courier New Italic.ttf", "LiberationMono-Italic.ttf"],
        "bolditalic": ["courbi.ttf", "Courier New Bold Italic.ttf", "LiberationMono-BoldItalic.ttf"],
    }

    def find(kind: str) -> Optional[str]:
        paths = [os.path.join(r, n) for r in roots for n in variants[kind]]
        return _first_existing(paths)

    reg, b, i, bi = find("regular"), find("bold"), find("italic"), find("bolditalic")
    if not reg:
        return False
    return _register_family_partial("Courier New", reg, b, i, bi, subset=True)


# -------------------- Enregistrement dynamique --------------------

# Suffixes de graisse/style à stripper pour trouver le "nom de base" d'une
# famille de polices. Utilisé pour retrouver des familles sœurs quand la
# variante demandée (bold/italic) est absente de la famille primaire.
_FONT_WEIGHT_SUFFIXES = {
    "thin", "hairline", "extralight", "ultralight", "light", "semilight",
    "regular", "book", "normal", "roman", "text",
    "medium",
    "semibold", "demibold", "bold", "extrabold", "ultrabold",
    "heavy", "black", "extrablack",
    "italic", "oblique",
    # Modificateurs qui peuvent précéder un poids en 2 mots
    # ('Ultra Light', 'Extra Bold', 'Semi Bold', 'Demi Bold')
    "ultra", "extra", "semi", "demi",
}


def _strip_font_weight_suffixes(name: str) -> str:
    """
    Retire les suffixes de poids/style en fin de nom de famille.
    Exemples :
        'Malgun Gothic Semilight'  -> 'Malgun Gothic'
        'Helvetica Neue Ultra Light' -> 'Helvetica Neue'
        'Arial'                    -> 'Arial' (inchangé)
    """
    tokens = name.split()
    while len(tokens) > 1 and tokens[-1].lower() in _FONT_WEIGHT_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _find_sibling_variant_path(
        families: dict,
        base_name: str,
        need_bold: bool,
        need_italic: bool,
) -> Optional[str]:
    """
    Cherche une famille sœur (même base_name après stripping) dont le nom
    encode les traits voulus (bold/italic). Retourne le chemin de sa variante
    regular, ou None si aucune correspondance.

    Ex. pour base_name='Malgun Gothic', need_bold=True, need_italic=False :
    cherche une famille 'Malgun Gothic Bold' et retourne sa variante regular.
    """
    for fam_name, fam in families.items():
        if fam_name == base_name:
            # La famille de base elle-même — peut avoir des variantes internes
            key = ("bolditalic" if (need_bold and need_italic)
                   else "bold" if need_bold
                   else "italic" if need_italic
                   else "regular")
            v = fam.variants.get(key)
            if v:
                return v.path
            continue
        if _strip_font_weight_suffixes(fam_name) != base_name:
            continue
        low = fam_name.lower()
        has_bold = "bold" in low or "heavy" in low or "black" in low
        has_italic = "italic" in low or "oblique" in low
        if has_bold == need_bold and has_italic == need_italic:
            reg = fam.variants.get("regular")
            if reg:
                return reg.path
    return None


def register_font_family_by_name(name: str) -> bool:
    """
    Enregistre une famille de polices par son nom, en utilisant la découverte
    dynamique (font_discovery) pour trouver les fichiers TTF.

    Si la famille primaire ne fournit pas de variante bold/italic/bolditalic
    (cas typique des polices Windows exposées comme familles séparées par
    graisse : 'Malgun Gothic Semilight' n'a pas de bold intrinsèque), on
    cherche les variantes manquantes dans les familles sœurs partageant le
    même nom de base après stripping des suffixes de graisse.

    Retourne True si la police est enregistrée avec succès (ou déjà enregistrée).
    """
    if name in _REGISTERED_FONTS:
        return True

    from .font_discovery import get_font_family, scan_font_directories

    family = get_font_family(name)
    if family is None:
        log.warning(f"Police '{name}' introuvable via la découverte dynamique")
        return False

    reg = family.variants.get("regular")
    bold = family.variants.get("bold")
    italic = family.variants.get("italic")
    bolditalic = family.variants.get("bolditalic")

    if not reg:
        log.warning(f"Police '{name}' : pas de variante regular trouvée")
        return False

    bold_path = bold.path if bold else None
    italic_path = italic.path if italic else None
    bolditalic_path = bolditalic.path if bolditalic else None

    # Fallback : chercher les variantes manquantes dans les familles sœurs.
    # Utile pour les polices Windows dont chaque graisse est exposée comme une
    # famille séparée (Malgun Gothic Semilight, Helvetica Neue Light, ...).
    if not (bold_path and italic_path and bolditalic_path):
        base = _strip_font_weight_suffixes(name)
        if base:  # Peut être == name si aucun suffixe, on essaie quand même
            all_families = scan_font_directories()
            if not bold_path:
                bold_path = _find_sibling_variant_path(all_families, base, need_bold=True, need_italic=False)
                if bold_path:
                    log.info(f"[fonts] Bold pour '{name}' emprunté à une famille sœur ({base}) : {bold_path}")
            if not italic_path:
                italic_path = _find_sibling_variant_path(all_families, base, need_bold=False, need_italic=True)
                if italic_path:
                    log.info(f"[fonts] Italic pour '{name}' emprunté à une famille sœur ({base}) : {italic_path}")
            if not bolditalic_path:
                bolditalic_path = _find_sibling_variant_path(all_families, base, need_bold=True, need_italic=True)
                if bolditalic_path:
                    log.info(f"[fonts] BoldItalic pour '{name}' emprunté à une famille sœur ({base}) : {bolditalic_path}")

    return _register_family_partial(
        name,
        reg.path,
        bold_path,
        italic_path,
        bolditalic_path,
        subset=True,
    )
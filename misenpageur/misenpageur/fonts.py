# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from typing import Optional, Dict
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# -------------------- Helpers --------------------

def _register_font(name: str, path: str) -> bool:
    try:
        pdfmetrics.registerFont(TTFont(name, path))
        return True
    except Exception as e:
        print(f"[WARN] Échec registerFont {name} -> {path}: {e}")
        return False

def _register_family_partial(base: str,
                             regular: Optional[str],
                             bold: Optional[str],
                             italic: Optional[str],
                             bolditalic: Optional[str]) -> bool:
    """Enregistre une famille même si certaines variantes manquent (mappées sur la régulière)."""
    if not regular or not _register_font(base, regular):
        return False
    ok_b  = _register_font(base + "-Bold", bold or regular)
    ok_i  = _register_font(base + "-Italic", italic or regular)
    ok_bi = _register_font(base + "-BoldItalic", bolditalic or regular)
    try:
        pdfmetrics.registerFontFamily(
            base,
            normal=base,
            bold=(base + "-Bold") if ok_b else base,
            italic=(base + "-Italic") if ok_i else base,
            boldItalic=(base + "-BoldItalic") if ok_bi else base,
        )
    except Exception as e:
        print(f"[WARN] Échec registerFontFamily {base}: {e}")
    return True

def _first_existing(paths: list[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
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
    return roots

# -------------------- Arial Narrow --------------------

def register_arial_narrow() -> bool:
    """
    Tente d'enregistrer la famille Arial Narrow (ArialNarrow).
    Cherche dans C:\\Windows\\Fonts et dans assets/fonts/ArialNarrow/.
    Tolère l'absence de certaines variantes (mappées vers Regular).
    """
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
            proj_candidates["regular"]    += [os.path.join(base, "ARIALN.TTF")]
            proj_candidates["bold"]       += [os.path.join(base, "ARIALNB.TTF")]
            proj_candidates["italic"]     += [os.path.join(base, "ARIALNI.TTF")]
            proj_candidates["bolditalic"] += [os.path.join(base, "ARIALNBI.TTF")]

    def find_one(kind: str) -> Optional[str]:
        # Windows d'abord
        p = _first_existing(win_candidates[kind])
        if p:
            return p
        # Puis projet/system
        return _first_existing(proj_candidates[kind])

    reg = find_one("regular")
    b   = find_one("bold")
    i   = find_one("italic")
    bi  = find_one("bolditalic")

    if not reg:
        # famille introuvable
        return False

    ok = _register_family_partial("ArialNarrow", reg, b, i, bi)
    return ok



def register_arial() -> bool:
    """
    Tente d'enregistrer la famille Arial standard (nommée 'Arial' dans ReportLab).
    Cherche dans C:\\Windows\\Fonts et dans les répertoires de polices du projet/système.
    Tolère l'absence de certaines variantes (mappées vers Regular).
    """
    # Noms Windows typiques
    win = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    win_candidates = {
        "regular": [os.path.join(win, "arial.ttf")],
        "bold": [os.path.join(win, "arialbd.ttf")],
        "italic": [os.path.join(win, "ariali.ttf")],
        "bolditalic": [os.path.join(win, "arialbi.ttf")],
    }

    # Dossiers projet/système
    roots = _fonts_roots()
    proj_candidates = {"regular": [], "bold": [], "italic": [], "bolditalic": []}
    for r in roots:
        for sub in ("Arial", "arial"): # On cherche dans des sous-dossiers nommés 'Arial'
            base = os.path.join(r, sub)
            proj_candidates["regular"]    += [os.path.join(base, "arial.ttf"), os.path.join(r, "arial.ttf")]
            proj_candidates["bold"]       += [os.path.join(base, "arialbd.ttf"), os.path.join(r, "arialbd.ttf")]
            proj_candidates["italic"]     += [os.path.join(base, "ariali.ttf"), os.path.join(r, "ariali.ttf")]
            proj_candidates["bolditalic"] += [os.path.join(base, "arialbi.ttf"), os.path.join(r, "arialbi.ttf")]

    def find_one(kind: str) -> Optional[str]:
        # Priorité à Windows
        p = _first_existing(win_candidates[kind])
        if p:
            return p
        # Puis les autres chemins
        return _first_existing(proj_candidates[kind])

    reg = find_one("regular")
    b   = find_one("bold")
    i   = find_one("italic")
    bi  = find_one("bolditalic")

    if not reg:
        # Si même la police de base n'est pas trouvée, on abandonne.
        print("[WARN] Police Arial (regular) introuvable.")
        return False

    # Enregistre la famille sous le nom 'Arial'
    ok = _register_family_partial("Arial", reg, b, i, bi)
    return ok

# -------------------- DejaVu Sans (fallback glyphes: €, ❑) --------------------

def register_dejavu_sans() -> bool:
    """
    Enregistre la famille DejaVuSans (normal/bold/italic/bolditalic).
    Tolère l'absence de certaines variantes en les mappant vers la régulière.
    Cherche dans assets/fonts/DejaVu*/ et emplacements système.
    """
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
    b   = find("bold")
    i   = find("italic")
    bi  = find("bolditalic")

    if not reg:
        print("[WARN] DejaVuSans introuvable (aucun TTF trouvé).")
        return False

    ok = _register_family_partial("DejaVuSans", reg, b, i, bi)
    return ok


# -------------------- DS-net Stamped --------------------

def register_dsnet_stamped() -> bool:
    """
    Tente d'enregistrer la police DS-net Stamped (nommée 'DSNetStamped').
    Cherche dans les dossiers de polices du projet.
    """
    roots = _fonts_roots()

    # Noms de fichiers possibles pour la police
    font_filenames = ["DS-NET-STAMPED.TTF", "DSNetStamped.ttf", "dsnetstamped.ttf", "DSnet Stamped.ttf"]

    font_paths = []
    for r in roots:
        for fname in font_filenames:
            font_paths.append(os.path.join(r, fname))

    font_file = _first_existing(font_paths)

    if not font_file:
        print("[WARN] Police DS-net Stamped introuvable.")
        return False

    # On enregistre la police sous un nom simple que ReportLab utilisera
    return _register_font("DSNetStamped", font_file)


def register_helvetica() -> bool:
    """Tente d'enregistrer la famille Helvetica standard."""
    # Helvetica est une police de base de PDF, mais enregistrer les TTF
    # garantit une meilleure gestion des glyphes et de l'italique/gras.
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
    if not reg: return False
    return _register_family_partial("Helvetica", reg, b, i, bi)


def register_times() -> bool:
    """Tente d'enregistrer la famille Times New Roman."""
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
    if not reg: return False
    return _register_family_partial("Times New Roman", reg, b, i, bi)


def register_courier() -> bool:
    """Tente d'enregistrer la famille Courier New."""
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
    if not reg: return False
    return _register_family_partial("Courier New", reg, b, i, bi)
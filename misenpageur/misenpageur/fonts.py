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

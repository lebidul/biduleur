# # -*- coding: utf-8 -*-
# from __future__ import annotations
# """
# Export Scribus : génère un script Scripter (.py) qui crée un doc sans marges,
# pose S1..S6 aux coordonnées du layout, place couv/logos/ours, chaîne S5→S6→S3→S4,
# injecte le texte (issu du HTML) et enregistre un .sla.
#
# Objectifs:
# - Police principale: Arial Narrow (avec fallbacks)
# - Ours centré, sans marge interne de cadre
# - Paragraphes du corps: justification, interlignage contrôlé, spaceBefore/After = 0
#
# Robustesse :
# - Normalise les sections (dict ou objets) en dicts {x,y,w,h,page}.
# - Si layout.page_size est absent, le déduit des sections (max(x+w), max(y+h)).
# - Tolère l'absence de s1_split (logos_ratio=0.6).
# """
#
# import html
# import os
# import re
# from pathlib import Path
# from typing import Any, Dict, List, Tuple
#
# from .layout import Layout
# from .config import Config
#
#
# # ---------- Helpers de parsing HTML simple ----------
#
# def _html_to_plain_lines(html_path: str) -> List[str]:
#     """Convertit un HTML simple (<p> + éventuellement <b>/<i>) en lignes de texte brut.
#     Conserve € et ❑, remplace &nbsp; par l’insécable, enlève les balises.
#     Compacte les blancs multiples (au plus 1 ligne vide).
#     """
#     txt = Path(html_path).read_text(encoding="utf-8", errors="ignore")
#     # <br> -> \n ; </p> -> \n ; supprime <p ...> ; enlève les autres balises
#     txt = re.sub(r"(?is)<\s*br\s*/?\s*>", "\n", txt)
#     txt = re.sub(r"(?is)</\s*p\s*>", "\n", txt)
#     txt = re.sub(r"(?is)<\s*p[^>]*>", "", txt)
#     txt = re.sub(r"(?is)<[^>]+>", "", txt)
#
#     # Entités & normalisation
#     txt = txt.replace("&nbsp;", "\u00A0")
#     txt = html.unescape(txt)
#     txt = txt.replace("\r\n", "\n").replace("\r", "\n")
#
#     # Split & strip
#     lines = [l.strip() for l in txt.split("\n")]
#
#     # Compacte les blancs multiples (on garde au plus une ligne vide)
#     out: List[str] = []
#     prev_blank = True
#     for l in lines:
#         if l:
#             out.append(l)
#             prev_blank = False
#         else:
#             if not prev_blank:
#                 out.append("")
#             prev_blank = True
#     return out
#
#
# def _make_text_literal(s: str) -> str:
#     """Protège pour insertion dans un triple-quoted Python string."""
#     return s.replace('"""', '\\"""')
#
#
# # ---------- Helpers Layout robustes ----------
#
# def _coerce_section(sec: Any) -> Dict[str, float]:
#     """Retourne un dict {x,y,w,h,page} à partir d'un dict ou d'un objet (Section)."""
#     if isinstance(sec, dict):
#         x = float(sec.get("x", 0) or 0)
#         y = float(sec.get("y", 0) or 0)
#         w = float(sec.get("w", 0) or 0)
#         h = float(sec.get("h", 0) or 0)
#         p = int(sec.get("page", 1) or 1)
#         return {"x": x, "y": y, "w": w, "h": h, "page": p}
#
#     # objet : on tente les attributs usuels
#     x = float(getattr(sec, "x", 0) or 0)
#     y = float(getattr(sec, "y", 0) or 0)
#     w = float(getattr(sec, "w", 0) or 0)
#     h = float(getattr(sec, "h", 0) or 0)
#     p = int(getattr(sec, "page", 1) or 1)
#     return {"x": x, "y": y, "w": w, "h": h, "page": p}
#
#
# def _get_sections_dict(layout: Layout) -> Dict[str, Dict[str, float]]:
#     """Récupère un dict 'sections' => dict {x,y,w,h,page} depuis différentes formes de Layout."""
#     # 1) Attribut direct
#     if hasattr(layout, "sections") and isinstance(layout.sections, dict):
#         return {k: _coerce_section(v) for k, v in layout.sections.items()}  # type: ignore[attr-defined]
#
#     # 2) Dictionnaires internes usuels
#     for attr in ("data", "raw", "_data", "_raw"):
#         d = getattr(layout, attr, None)
#         if isinstance(d, dict) and "sections" in d and isinstance(d["sections"], dict):
#             return {k: _coerce_section(v) for k, v in d["sections"].items()}
#
#     raise AttributeError("Layout: sections introuvables (ni .sections ni .data/.raw['sections']).")
#
#
# def _get_page_size(layout: Layout, sections: Dict[str, Dict[str, float]]) -> Tuple[float, float]:
#     """Retourne (W, H) en points.
#     - Si layout.page_size (dict) existe avec width/height, l'utilise.
#     - Sinon, déduit depuis les sections: max(x+w), max(y+h).
#     """
#     # 1) page_size dict
#     ps = getattr(layout, "page_size", None)
#     if isinstance(ps, dict):
#         w = float(ps.get("width", 0) or 0)
#         h = float(ps.get("height", 0) or 0)
#         if w > 0 and h > 0:
#             return (w, h)
#
#     # 2) variantes communes éventuelles
#     for name in ("pageSize", "pagesize", "size", "page"):
#         ps2 = getattr(layout, name, None)
#         if isinstance(ps2, dict):
#             w = float(ps2.get("width", 0) or 0)
#             h = float(ps2.get("height", 0) or 0)
#             if w > 0 and h > 0:
#                 return (w, h)
#
#     # 3) Déduction depuis les sections
#     max_w = 0.0
#     max_h = 0.0
#     for s in sections.values():
#         x, y, w, h = s["x"], s["y"], s["w"], s["h"]
#         max_w = max(max_w, x + w)
#         max_h = max(max_h, y + h)
#
#     # fallback A4 portrait si rien de valable
#     if max_w <= 0 or max_h <= 0:
#         return (595.0, 842.0)
#     return (max_w, max_h)
#
#
# def _get_s1_split(layout: Layout) -> float:
#     """Renvoie logos_ratio (0..1)."""
#     s1s = getattr(layout, "s1_split", None)
#     if isinstance(s1s, dict):
#         try:
#             return float(s1s.get("logos_ratio", 0.6))
#         except Exception:
#             return 0.6
#     for attr in ("data", "raw", "_data", "_raw"):
#         d = getattr(layout, attr, None)
#         if isinstance(d, dict) and isinstance(d.get("s1_split"), dict):
#             try:
#                 return float(d["s1_split"].get("logos_ratio", 0.6))
#             except Exception:
#                 return 0.6
#     return 0.6
#
#
# # ---------- Export principal ----------
#
# def write_scribus_script(project_root: str, cfg: Config, layout: Layout, out_script: str, out_sla: str) -> None:
#     """Génère un script Scripter .py qui fabrique les cadres S1..S6 et un .sla éditable."""
#     cover = Path(cfg.cover_image).resolve() if cfg.cover_image else None
#     logos_dir = Path(cfg.logos_dir).resolve() if cfg.logos_dir else None
#     ours_md = Path(cfg.ours_md).resolve() if cfg.ours_md else None
#     input_html = Path(cfg.input_html).resolve()
#
#     # chemins pour le script (absolus, style /)
#     cover_p = f"r'{str(cover).replace('\\\\','/')}'" if cover and cover.exists() else "None"
#     logos_p = f"r'{str(logos_dir).replace('\\\\','/')}'" if logos_dir and logos_dir.exists() else "None"
#     ours_p  = f"r'{str(ours_md).replace('\\\\','/')}'" if ours_md and ours_md.exists() else "None"
#
#     # Texte (blob compact)
#     lines = _html_to_plain_lines(str(input_html))
#     text_blob = _make_text_literal("\n".join(lines))
#
#     # Sections + page size
#     sections = _get_sections_dict(layout)
#     W, H = _get_page_size(layout, sections)
#
#     # sections requises
#     try:
#         s1 = sections["S1"]; s2 = sections["S2"]; s3 = sections["S3"]; s4 = sections["S4"]; s5 = sections["S5"]; s6 = sections["S6"]
#     except KeyError as e:
#         raise KeyError(f"Section manquante dans layout: {e!s}")
#
#     logos_ratio = _get_s1_split(layout)
#
#     # conversion Y (ReportLab bottom-left -> Scribus top-left)
#     def topY(y0: float, h0: float) -> float:
#         return H - y0 - h0
#
#     # S1 sous-cadres
#     s1_w = s1["w"]; s1_h = s1["h"]; s1_x = s1["x"]; s1_y = s1["y"]
#     logos_w = s1_w * logos_ratio
#     ours_w  = s1_w - logos_w
#     logos_area = (s1_x,         topY(s1_y, s1_h), logos_w, s1_h)
#     ours_area  = (s1_x+logos_w, topY(s1_y, s1_h), ours_w,  s1_h)
#
#     # Typo depuis la config
#     font_name = (getattr(cfg, "font_name", None) or "Arial Narrow").strip()
#     font_size = float(getattr(cfg, "font_size_max", 10.0) or 10.0)
#     leading_ratio = float(getattr(cfg, "leading_ratio", 1.12) or 1.12)
#     leading = font_size * leading_ratio
#     font_candidates = [
#         font_name,
#         "Arial Narrow", "ArialNarrow", "ArialNarrowMT", "ArialNarrowPSMT",
#         "Helvetica",
#     ]
#
#     out: List[str] = []
#     out.append("#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n")
#     out.append("import scribus\n")
#     out.append("import os\n")
#     out.append("from pathlib import Path\n\n")
#
#     # Helpers dans le script Scripter
#     out.append("def _try_set_font(item, candidates):\n")
#     out.append("    for f in candidates:\n")
#     out.append("        try:\n")
#     out.append("            scribus.setFont(f, item)\n")
#     out.append("            return f\n")
#     out.append("        except Exception:\n")
#     out.append("            pass\n")
#     out.append("    return None\n\n")
#
#     out.append("def _set_text_style(item, candidates, size, leading):\n")
#     out.append("    used = _try_set_font(item, candidates)\n")
#     out.append("    try:\n")
#     out.append("        scribus.setFontSize(size, item)\n")
#     out.append("    except Exception:\n")
#     out.append("        pass\n")
#     out.append("    try:\n")
#     out.append("        scribus.setLineSpacing(leading, item)\n")
#     out.append("    except Exception:\n")
#     out.append("        pass\n")
#     out.append("    try:\n")
#     out.append("        scribus.setTextDistances(item, 0, 0, 0, 0)\n")  # pas de marges internes
#     out.append("    except Exception:\n")
#     out.append("        pass\n")
#     out.append("    return used\n\n")
#
#     out.append("def _create_body_style(name, leading):\n")
#     out.append("    # Crée un style de paragraphe sans espace avant/après ; ignore si API diffère\n")
#     out.append("    try:\n")
#     out.append("        scribus.createParagraphStyle(name,\n")
#     out.append("            linespacingmode=scribus.FIXEDLINESPACING,\n")
#     out.append("            linespacing=leading,\n")
#     out.append("            alignment=scribus.ALIGN_BLOCK,\n")
#     out.append("            leftmargin=0.0, rightmargin=0.0, firstline=0.0,\n")
#     out.append("            spaceabovep=0.0, spacebelowp=0.0,\n")
#     out.append("        )\n")
#     out.append("    except Exception:\n")
#     out.append("        try:\n")
#     out.append("            scribus.createParagraphStyle(name)\n")
#     out.append("        except Exception:\n")
#     out.append("            pass\n\n")
#
#     out.append("def _apply_par_style(item, name):\n")
#     out.append("    try:\n")
#     out.append("        scribus.setParagraphStyle(name, item)\n")
#     out.append("    except Exception:\n")
#     out.append("        pass\n\n")
#
#     out.append("def _create_ours_style(name, leading):\n")
#     out.append("    try:\n")
#     out.append("        scribus.createParagraphStyle(name,\n")
#     out.append("            linespacingmode=scribus.FIXEDLINESPACING,\n")
#     out.append("            linespacing=leading,\n")
#     out.append("            alignment=scribus.ALIGN_CENTER,\n")
#     out.append("            leftmargin=0.0, rightmargin=0.0, firstline=0.0,\n")
#     out.append("            spaceabovep=0.0, spacebelowp=0.0,\n")
#     out.append("        )\n")
#     out.append("    except Exception:\n")
#     out.append("        try:\n")
#     out.append("            scribus.createParagraphStyle(name)\n")
#     out.append("        except Exception:\n")
#     out.append("            pass\n\n")
#
#     # Corps principal
#     out.append("def main():\n")
#     out.append("    if not scribus.haveDoc():\n")
#     out.append(f"        scribus.newDocument(({W}, {H}), (0,0,0,0), scribus.PORTRAIT, 1, scribus.UNIT_POINTS, scribus.FACINGPAGES, 0, 0)\n")
#
#     # Assurer le nb de pages
#     pages_needed = sorted({s1["page"], s2["page"], s3["page"], s4["page"], s5["page"], s6["page"]})
#     out.append("    # Assure le nombre de pages requis\n")
#     out.append(f"    _need = {pages_needed}\n")
#     out.append("    for p in _need:\n")
#     out.append("        while scribus.pageCount() < p:\n")
#     out.append("            scribus.newPage(-1)\n")
#
#     # Styles globaux
#     out.append(f"    _BODY = 'BodyTight'\n")
#     out.append(f"    _OURS = 'OursCenter'\n")
#     out.append(f"    _leading = {leading}\n")
#     out.append("    _create_body_style(_BODY, _leading)\n")
#     out.append("    _create_ours_style(_OURS, _leading)\n")
#
#     # S2: couverture
#     out.append("    # --- S2: Couverture ---\n")
#     out.append(f"    scribus.gotoPage({s2['page']})\n")
#     out.append(f"    imgS2 = scribus.createImage({s2['x']}, {topY(s2['y'], s2['h'])}, {s2['w']}, {s2['h']})\n")
#     out.append(f"    _cover = {cover_p}\n")
#     out.append("    if _cover is not None:\n")
#     out.append("        try:\n")
#     out.append("            scribus.loadImage(_cover, imgS2)\n")
#     out.append("            scribus.setScaleImageToFrame(True, True, imgS2)\n")
#     out.append("        except Exception as e:\n")
#     out.append("            scribus.messageBox('Cover', f'Impossible de charger la couverture:\\n{e}', icon=scribus.ICON_WARNING)\n")
#
#     # S1: logos + ours
#     out.append("    # --- S1: Logos + Ours ---\n")
#     out.append(f"    scribus.gotoPage({s1['page']})\n")
#     out.append(f"    lx, ly, lw, lh = {logos_area}\n")
#     out.append(f"    ox, oy, ow, oh = {ours_area}\n")
#     out.append("    # Grille 2x5 pour 10 logos max\n")
#     out.append("    cols, rows, pad = 2, 5, 4.0\n")
#     out.append("    cw = (lw - pad*(cols+1)) / cols\n")
#     out.append("    ch = (lh - pad*(rows+1)) / rows\n")
#     out.append("    boxes = []\n")
#     out.append("    for r in range(rows):\n")
#     out.append("        for c in range(cols):\n")
#     out.append("            bx = lx + pad + c*(cw+pad)\n")
#     out.append("            by = ly + pad + r*(ch+pad)\n")
#     out.append("            boxes.append((bx, by, cw, ch))\n")
#     out.append(f"    _logos_dir = {logos_p}\n")
#     out.append("    if _logos_dir is not None and os.path.isdir(_logos_dir):\n")
#     out.append("        import glob\n")
#     out.append("        files = sorted(glob.glob(os.path.join(_logos_dir, '*.*')))\n")
#     out.append("        files = [f for f in files if f.lower().endswith(('.png','.jpg','.jpeg','.tif','.tiff'))]\n")
#     out.append("        for i,(bx,by,bw,bh) in enumerate(boxes):\n")
#     out.append("            if i >= len(files): break\n")
#     out.append("            im = scribus.createImage(bx, by, bw, bh)\n")
#     out.append("            try:\n")
#     out.append("                scribus.loadImage(files[i], im)\n")
#     out.append("                scribus.setScaleImageToFrame(True, True, im)\n")
#     out.append("            except Exception:\n")
#     out.append("                pass\n")
#
#     out.append("    # Ours (centré + police/leading + padding 0 + style sans spaceBefore/After)\n")
#     out.append("    tf_ours = scribus.createText(ox, oy, ow, oh)\n")
#     out.append(f"    _ours_path = {ours_p}\n")
#     out.append("    _t = ''\n")
#     out.append("    if _ours_path is not None and os.path.isfile(_ours_path):\n")
#     out.append("        try:\n")
#     out.append("            _t = Path(_ours_path).read_text(encoding='utf-8', errors='ignore')\n")
#     out.append("        except Exception:\n")
#     out.append("            _t = ''\n")
#     out.append("    if _t:\n")
#     out.append("        scribus.setText(_t, tf_ours)\n")
#     out.append(f"    _set_text_style(tf_ours, {repr(font_candidates)}, {font_size}, _leading)\n")
#     out.append("    try:\n")
#     out.append("        scribus.selectObject(tf_ours)\n")
#     out.append("        try:\n")
#     out.append("            scribus.setAlignment(scribus.ALIGN_CENTER)\n")
#     out.append("        except Exception:\n")
#     out.append("            scribus.setAlignment(scribus.ALIGN_CENTERED)\n")
#     out.append("    except Exception:\n")
#     out.append("        pass\n")
#     out.append("    _apply_par_style(tf_ours, _OURS)\n")
#
#     # Cadres texte S5..S6..S3..S4
#     def frame_cmd(name: str, s: Dict[str, float]) -> str:
#         return (
#             f"    scribus.gotoPage({s['page']})\n"
#             f"    tf_{name} = scribus.createText({s['x']}, {topY(s['y'], s['h'])}, {s['w']}, {s['h']})\n"
#             f"    _set_text_style(tf_{name}, {repr(font_candidates)}, {font_size}, _leading)\n"
#             f"    try:\n"
#             f"        scribus.selectObject(tf_{name})\n"
#             f"        scribus.setAlignment(scribus.ALIGN_BLOCK)\n"
#             f"    except Exception:\n"
#             f"        pass\n"
#             f"    _apply_par_style(tf_{name}, _BODY)\n"
#         )
#
#     out.append("    # --- Cadres texte chainés ---\n")
#     out.append(frame_cmd("S5", s5))
#     out.append(frame_cmd("S6", s6))
#     out.append(frame_cmd("S3", s3))
#     out.append(frame_cmd("S4", s4))
#
#     # Chaînage
#     out.append("    scribus.linkTextFrames(tf_S5, tf_S6)\n")
#     out.append("    scribus.linkTextFrames(tf_S6, tf_S3)\n")
#     out.append("    scribus.linkTextFrames(tf_S3, tf_S4)\n")
#
#     # Texte principal
#     out.append('    _blob = """' + text_blob + '"""\n')
#     out.append("    scribus.setText(_blob, tf_S5)\n")
#
#     # Sauvegarde SLA
#     out.append(f"    out_sla = r'{str(Path(out_sla).resolve()).replace('\\\\','/')}'\n")
#     out.append("    try:\n")
#     out.append("        scribus.saveDocAs(out_sla)\n")
#     out.append("    except Exception as e:\n")
#     out.append("        scribus.messageBox('Save', f'Impossible de sauvegarder:\\n{e}', icon=scribus.ICON_WARNING)\n")
#
#     out.append("\nif __name__ == '__main__':\n")
#     out.append("    if scribus.haveDoc():\n")
#     out.append("        main()\n")
#     out.append("    else:\n")
#     out.append("        main()\n")
#
#     Path(out_script).parent.mkdir(parents=True, exist_ok=True)
#     Path(out_script).write_text("".join(out), encoding="utf-8")

# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Export Scribus : génère un script Scripter (.py) qui crée un doc sans marges,
pose S1..S6 aux coordonnées du layout, place couv/logos/ours, chaîne S5→S6→S3→S4,
injecte le texte (issu du HTML) et enregistre un .sla.

Robustesse :
- Normalise les sections (dict ou objets) en dicts {x,y,w,h,page}.
- Si layout.page_size est absent, le déduit des sections (max(x+w), max(y+h)).
- Tolère l'absence de s1_split (logos_ratio=0.6).
"""

import html
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .layout import Layout
from .config import Config


# ---------- Helpers de parsing HTML simple ----------

def _html_to_plain_lines(html_path: str) -> List[str]:
    """Convertit un HTML très simple (suite de <p> éventuellement avec <b>/<i>) en lignes de texte brut.
    Conserve les symboles € et ❑, et remplace &nbsp; par l'insécable unicode.
    """
    txt = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    # <br> -> \n
    txt = re.sub(r"(?is)<\s*br\s*/?\s*>", "\n", txt)
    # </p> -> \n
    txt = re.sub(r"(?is)</\s*p\s*>", "\n", txt)
    # supprime <p ...>
    txt = re.sub(r"(?is)<\s*p[^>]*>", "", txt)
    # enlève les autres balises en conservant le texte
    txt = re.sub(r"(?is)<[^>]+>", "", txt)

    # Entités
    txt = txt.replace("&nbsp;", "\u00A0")
    txt = html.unescape(txt)

    # Normalise fins de lignes
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    lines = [l.strip() for l in txt.split("\n")]

    # Compacte les blancs multiples
    out: List[str] = []
    prev_blank = True
    for l in lines:
        if l:
            out.append(l)
            prev_blank = False
        else:
            if not prev_blank:
                out.append("")
            prev_blank = True
    return out


def _make_text_literal(s: str) -> str:
    """Protège pour insertion dans un triple-quoted Python string."""
    return s.replace('"""', '\\"""')


# ---------- Helpers Layout robustes ----------

def _coerce_section(sec: Any) -> Dict[str, float]:
    """Retourne un dict {x,y,w,h,page} à partir d'un dict ou d'un objet (Section)."""
    if isinstance(sec, dict):
        x = float(sec.get("x", 0) or 0)
        y = float(sec.get("y", 0) or 0)
        w = float(sec.get("w", 0) or 0)
        h = float(sec.get("h", 0) or 0)
        p = int(sec.get("page", 1) or 1)
        return {"x": x, "y": y, "w": w, "h": h, "page": p}

    # objet : on tente les attributs usuels
    x = float(getattr(sec, "x", 0) or 0)
    y = float(getattr(sec, "y", 0) or 0)
    w = float(getattr(sec, "w", 0) or 0)
    h = float(getattr(sec, "h", 0) or 0)
    p = int(getattr(sec, "page", 1) or 1)
    return {"x": x, "y": y, "w": w, "h": h, "page": p}


def _get_sections_dict(layout: Layout) -> Dict[str, Dict[str, float]]:
    """Récupère un dict 'sections' => dict {x,y,w,h,page} depuis différentes formes de Layout."""
    # 1) Attribut direct
    if hasattr(layout, "sections") and isinstance(layout.sections, dict):
        return {k: _coerce_section(v) for k, v in layout.sections.items()}  # type: ignore[attr-defined]

    # 2) Dictionnaires internes usuels
    for attr in ("data", "raw", "_data", "_raw"):
        d = getattr(layout, attr, None)
        if isinstance(d, dict) and "sections" in d and isinstance(d["sections"], dict):
            return {k: _coerce_section(v) for k, v in d["sections"].items()}

    raise AttributeError("Layout: sections introuvables (ni .sections ni .data/.raw['sections']).")


def _get_page_size(layout: Layout, sections: Dict[str, Dict[str, float]]) -> Tuple[float, float]:
    """Retourne (W, H).
    - Si layout.page_size (dict) existe avec width/height, l'utilise.
    - Sinon, déduit depuis les sections: max(x+w), max(y+h).
    """
    # 1) page_size dict
    ps = getattr(layout, "page_size", None)
    if isinstance(ps, dict):
        w = float(ps.get("width", 0) or 0)
        h = float(ps.get("height", 0) or 0)
        if w > 0 and h > 0:
            return (w, h)

    # 2) variantes communes éventuelles
    for name in ("pageSize", "pagesize", "size", "page"):
        ps2 = getattr(layout, name, None)
        if isinstance(ps2, dict):
            w = float(ps2.get("width", 0) or 0)
            h = float(ps2.get("height", 0) or 0)
            if w > 0 and h > 0:
                return (w, h)

    # 3) Déduction depuis les sections
    max_w = 0.0
    max_h = 0.0
    for s in sections.values():
        x, y, w, h = s["x"], s["y"], s["w"], s["h"]
        max_w = max(max_w, x + w)
        max_h = max(max_h, y + h)

    # fallback A4 portrait en points si rien de valable
    if max_w <= 0 or max_h <= 0:
        return (595.0, 842.0)
    return (max_w, max_h)


def _get_s1_split(layout: Layout) -> float:
    """Renvoie logos_ratio (0..1)."""
    # attribut direct (dict)
    s1s = getattr(layout, "s1_split", None)
    if isinstance(s1s, dict):
        try:
            return float(s1s.get("logos_ratio", 0.6))
        except Exception:
            return 0.6
    # dictionnaires internes
    for attr in ("data", "raw", "_data", "_raw"):
        d = getattr(layout, attr, None)
        if isinstance(d, dict) and isinstance(d.get("s1_split"), dict):
            try:
                return float(d["s1_split"].get("logos_ratio", 0.6))
            except Exception:
                return 0.6
    return 0.6


# ---------- Export principal ----------

def write_scribus_script(project_root: str, cfg: Config, layout: Layout, out_script: str, out_sla: str) -> None:
    """Génère un script Scripter .py qui fabrique les cadres S1..S6 et un .sla éditable."""
    cover = Path(cfg.cover_image).resolve() if cfg.cover_image else None
    logos_dir = Path(cfg.logos_dir).resolve() if cfg.logos_dir else None
    ours_md = Path(cfg.ours_md).resolve() if cfg.ours_md else None
    input_html = Path(cfg.input_html).resolve()

    # chemins pour le script (absolus, style /)
    cover_p = f"r'{str(cover).replace('\\\\','/')}'" if cover and cover.exists() else "None"
    logos_p = f"r'{str(logos_dir).replace('\\\\','/')}'" if logos_dir and logos_dir.exists() else "None"
    ours_p  = f"r'{str(ours_md).replace('\\\\','/')}'" if ours_md and ours_md.exists() else "None"

    # Texte à injecter (on sérialise côté script)
    lines = _html_to_plain_lines(str(input_html))
    text_blob = _make_text_literal("\n".join(lines))

    # Récupération robuste des sections + page size
    sections = _get_sections_dict(layout)
    W, H = _get_page_size(layout, sections)

    # sections requises
    try:
        s1 = sections["S1"]; s2 = sections["S2"]; s3 = sections["S3"]; s4 = sections["S4"]; s5 = sections["S5"]; s6 = sections["S6"]
    except KeyError as e:
        raise KeyError(f"Section manquante dans layout: {e!s}")

    logos_ratio = _get_s1_split(layout)

    # conversion Y (ReportLab bottom-left -> Scribus top-left)
    def topY(y0: float, h0: float) -> float:
        return H - y0 - h0

    # S1 sous-cadres
    s1_w = s1["w"]; s1_h = s1["h"]; s1_x = s1["x"]; s1_y = s1["y"]
    logos_w = s1_w * logos_ratio
    ours_w  = s1_w - logos_w
    logos_area = (s1_x,         topY(s1_y, s1_h), logos_w, s1_h)
    ours_area  = (s1_x+logos_w, topY(s1_y, s1_h), ours_w,  s1_h)

    # Génération du script Scripter
    out: List[str] = []
    out.append("#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n")
    out.append("import scribus\n")
    out.append("import os\n")
    out.append("from pathlib import Path\n\n")

    out.append("def main():\n")
    out.append("    if not scribus.haveDoc():\n")
    out.append(f"        scribus.newDocument(({W}, {H}), (0,0,0,0), scribus.PORTRAIT, 1, scribus.UNIT_POINTS, scribus.FACINGPAGES, 0, 0)\n")

    # >>> Création des pages nécessaires en fonction des 'page' des sections
    pages_needed = set([s1["page"], s2["page"], s3["page"], s4["page"], s5["page"], s6["page"]])
    # newDocument crée déjà la page 1 ; on ajoute les suivantes si besoin
    out.append("    # Assure le nombre de pages requis\n")
    out.append("    _npages = scribus.pageCount()\n")
    out.append(f"    _need = {sorted(pages_needed)}\n")
    out.append("    for p in _need:\n")
    out.append("        while scribus.pageCount() < p:\n")
    out.append("            scribus.newPage(-1)\n")

    # S2: couverture
    out.append("    # --- S2: Couverture ---\n")
    out.append(f"    scribus.gotoPage({s2['page']})\n")
    out.append(f"    imgS2 = scribus.createImage({s2['x']}, {topY(s2['y'], s2['h'])}, {s2['w']}, {s2['h']})\n")
    out.append(f"    if {cover_p} is not None:\n")
    out.append("        try:\n")
    out.append(f"            scribus.loadImage({cover_p}, imgS2)\n")
    out.append("            scribus.setScaleImageToFrame(True, True, imgS2)\n")
    out.append("        except Exception as e:\n")
    out.append("            scribus.messageBox('Cover', f'Impossible de charger la couverture:\\n{e}', icon=scribus.ICON_WARNING)\n")

    # S1: logos gauche + ours à droite
    out.append("    # --- S1: Logos + Ours ---\n")
    out.append(f"    scribus.gotoPage({s1['page']})\n")
    out.append(f"    lx, ly, lw, lh = {logos_area}\n")
    out.append(f"    ox, oy, ow, oh = {ours_area}\n")
    out.append("    # Grille 2x5 pour 10 logos max\n")
    out.append("    cols, rows, pad = 2, 5, 4.0\n")
    out.append("    cw = (lw - pad*(cols+1)) / cols\n")
    out.append("    ch = (lh - pad*(rows+1)) / rows\n")
    out.append("    boxes = []\n")
    out.append("    for r in range(rows):\n")
    out.append("        for c in range(cols):\n")
    out.append("            bx = lx + pad + c*(cw+pad)\n")
    out.append("            by = ly + pad + r*(ch+pad)\n")
    out.append("            boxes.append((bx, by, cw, ch))\n")
    out.append(f"    _logos_dir = {logos_p}\n")
    out.append("    if _logos_dir is not None and os.path.isdir(_logos_dir):\n")
    out.append("        import glob\n")
    out.append("        files = sorted(glob.glob(os.path.join(_logos_dir, '*.*')))\n")
    out.append("        files = [f for f in files if f.lower().endswith(('.png','.jpg','.jpeg','.tif','.tiff'))]\n")
    out.append("        for i,(bx,by,bw,bh) in enumerate(boxes):\n")
    out.append("            if i >= len(files): break\n")
    out.append("            im = scribus.createImage(bx, by, bw, bh)\n")
    out.append("            try:\n")
    out.append("                scribus.loadImage(files[i], im)\n")
    out.append("                scribus.setScaleImageToFrame(True, True, im)\n")
    out.append("            except Exception:\n")
    out.append("                pass\n")

    out.append("    # Ours (texte centré, aligné haut par la position du cadre)\n")
    out.append("    tf_ours = scribus.createText(ox, oy, ow, oh)\n")
    out.append(f"    _ours_path = {ours_p}\n")
    out.append("    _t = ''\n")
    out.append("    if _ours_path is not None and os.path.isfile(_ours_path):\n")
    out.append("        try:\n")
    out.append("            _t = Path(_ours_path).read_text(encoding='utf-8', errors='ignore')\n")
    out.append("        except Exception:\n")
    out.append("            _t = ''\n")
    out.append("    if _t:\n")
    out.append("        scribus.setText(_t, tf_ours)\n")
    out.append("        try:\n")
    out.append("            scribus.selectObject(tf_ours)\n")
    out.append("            scribus.setAlignment(scribus.ALIGN_CENTER)\n")
    out.append("        except Exception:\n")
    out.append("            pass\n")

    # Cadres texte S5..S6..S3..S4 (chaînés) — on respecte les pages déclarées
    def frame_cmd(name: str, s: Dict[str, float]) -> str:
        return (
            f"    scribus.gotoPage({s['page']})\n"
            f"    tf_{name} = scribus.createText({s['x']}, {topY(s['y'], s['h'])}, {s['w']}, {s['h']})\n"
        )

    out.append("    # --- Cadres texte chainés ---\n")
    out.append(frame_cmd("S5", s5))
    out.append(frame_cmd("S6", s6))
    out.append(frame_cmd("S3", s3))
    out.append(frame_cmd("S4", s4))

    out.append("    # Chaînage S5 -> S6 -> S3 -> S4\n")
    out.append("    scribus.linkTextFrames(tf_S5, tf_S6)\n")
    out.append("    scribus.linkTextFrames(tf_S6, tf_S3)\n")
    out.append("    scribus.linkTextFrames(tf_S3, tf_S4)\n")

    # Texte principal
    out.append('    _blob = """' + text_blob + '"""\n')
    out.append("    scribus.setText(_blob, tf_S5)\n")
    out.append("    # Justification\n")
    out.append("    try:\n")
    out.append("        for nm in ('tf_S5','tf_S6','tf_S3','tf_S4'):\n")
    out.append("            scribus.selectObject(eval(nm))\n")
    out.append("            scribus.setAlignment(scribus.ALIGN_BLOCK)\n")
    out.append("    except Exception:\n")
    out.append("        pass\n")

    # Sauvegarde SLA
    out.append(f"    out_sla = r'{str(Path(out_sla).resolve()).replace('\\\\','/')}'\n")
    out.append("    try:\n")
    out.append("        scribus.saveDocAs(out_sla)\n")
    out.append("    except Exception as e:\n")
    out.append("        scribus.messageBox('Save', f'Impossible de sauvegarder:\\n{e}', icon=scribus.ICON_WARNING)\n")

    out.append("\nif __name__ == '__main__':\n")
    out.append("    if scribus.haveDoc():\n")
    out.append("        main()\n")
    out.append("    else:\n")
    out.append("        main()\n")

    Path(out_script).parent.mkdir(parents=True, exist_ok=True)
    Path(out_script).write_text("".join(out), encoding="utf-8")

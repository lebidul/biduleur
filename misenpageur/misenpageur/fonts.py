# -*- coding: utf-8 -*-
r"""
Enregistrement des polices TrueType pour ReportLab.
- Arial Narrow (Regular/Bold/Italic/BoldItalic)
- DejaVu Sans (fallback glyphes, ex: symbole €)
"""

from __future__ import annotations
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def _ok(p: str) -> bool:
    try:
        return os.path.isfile(p)
    except Exception:
        return False

def register_arial_narrow(
    regular="assets/fonts/arialnarrow.ttf",
    bold="assets/fonts/arialnarrow_bold.ttf",
    italic="assets/fonts/arialnarrow_italic.ttf",
    bolditalic="assets/fonts/arialnarrow_bolditalic.ttf",
) -> bool:
    if all(_ok(p) for p in (regular, bold, italic, bolditalic)):
        pdfmetrics.registerFont(TTFont("ArialNarrow", regular))
        pdfmetrics.registerFont(TTFont("ArialNarrow-Bold", bold))
        pdfmetrics.registerFont(TTFont("ArialNarrow-Italic", italic))
        pdfmetrics.registerFont(TTFont("ArialNarrow-BoldItalic", bolditalic))
        pdfmetrics.registerFontFamily(
            "ArialNarrow",
            normal="ArialNarrow",
            bold="ArialNarrow-Bold",
            italic="ArialNarrow-Italic",
            boldItalic="ArialNarrow-BoldItalic",
        )
        return True
    return False

def register_dejavu_sans(path="assets/fonts/DejaVuSans.ttf") -> bool:
    if _ok(path):
        if "DejaVuSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("DejaVuSans", path))
        return True
    return False

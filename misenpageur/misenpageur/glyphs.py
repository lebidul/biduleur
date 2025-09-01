# -*- coding: utf-8 -*-
from __future__ import annotations
from reportlab.pdfbase import pdfmetrics

def apply_glyph_fallbacks(text: str) -> str:
    """
    - Normalise &euro; -> €
    - Force l'affichage fiable de € et ❑ via DejaVuSans si disponible (Arial Narrow peut mal rendre ❑).
    - N'altère pas les autres balises <font>.
    """
    if not text:
        return text
    t = text.replace("&euro;", "€")
    if "DejaVuSans" in pdfmetrics.getRegisteredFontNames():
        # Encapsule les caractères sensibles
        t = t.replace("€",  '<font name="DejaVuSans">€</font>')
        t = t.replace("❑", '<font name="DejaVuSans">❑</font>')
    return t

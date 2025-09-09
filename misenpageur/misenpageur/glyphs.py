# -*- coding: utf-8 -*-
from __future__ import annotations
import re

# IMPORTANT:
# - Assure-toi que register_dejavu_sans() est appelé dans pdfbuild.py (c’est déjà le cas).
# - Les TTF DejaVuSans doivent être présents (ou installés) et enregistrés via fonts.register_dejavu_sans().

FALLBACK_FONT = "DejaVuSans"

# On cible explicitement les glyphes connus qui posent problème avec certaines polices:
#  - € (U+20AC)
#  - ❑ (U+2751)
_FALLBACK_RE = re.compile(r"(€|❑)")

def apply_glyph_fallbacks(text: str) -> str:
    """Enveloppe certains glyphes (€, ❑) dans une balise <font name="DejaVuSans">...</font>
       pour forcer un fallback propre et homogène.
    """
    if not text:
        return text
    # NB: On accepte des balises <font> imbriquées, ReportLab les gère correctement.
    return _FALLBACK_RE.sub(lambda m: f'<font name="{FALLBACK_FONT}">{m.group(1)}</font>', text)

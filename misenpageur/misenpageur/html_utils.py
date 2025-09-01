# -*- coding: utf-8 -*-
"""
HTML -> liste de paragraphes (compatible ReportLab)
- Supporte <p>, <li>, <div>
- Préserve <b>, <i>, <br/> (convertit <strong>/<em> -> <b>/<i>, &euro; -> €)
- Sanitizeur robuste des balises inline + suppression des <br/> de tête/queue
- Fallback si rien trouvé : split sur doubles retours / <br/> / lignes non vides
"""
from __future__ import annotations
import re
from typing import List

TAGS_CLOSE_SPLIT = re.compile(r"</\s*(p|li|div)\s*>", re.I)

def sanitize_inline_markup(s: str) -> str:
    """Répare l'imbrication des <b>/<i>, garde <br/>, supprime balises inconnues."""
    s = s.replace("&euro;", "€").replace("&nbsp;", " ")
    s = re.sub(r"(?i)<br\s*/?>", "<br/>", s)
    s = re.sub(r"(?i)<\s*strong\s*>", "<b>", s)
    s = re.sub(r"(?i)<\s*/\s*strong\s*>", "</b>", s)
    s = re.sub(r"(?i)<\s*em\s*>", "<i>", s)
    s = re.sub(r"(?i)<\s*/\s*em\s*>", "</i>", s)
    s = re.sub(r"(?i)<\s*(p|li|div)[^>]*>", "", s)
    s = re.sub(r"(?i)</?(?!br\s*/?|b\b|/b\b|i\b|/i\b)[^>]+>", "", s)

    if not s.strip():
        return ""

    out: List[str] = []
    stack: List[str] = []  # 'b' / 'i'
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "<":
            j = s.find(">", i + 1)
            if j == -1:
                out.append(s[i:])
                break
            tag = s[i+1:j].strip().lower()
            if tag in ("b", "i"):
                stack.append(tag)
                out.append(f"<{tag}>")
            elif tag in ("/b", "/i"):
                t = tag[1]
                if stack:
                    if stack[-1] == t:
                        stack.pop(); out.append(f"</{t}>")
                    elif t in stack:
                        reopen = []
                        while stack and stack[-1] != t:
                            top = stack.pop(); out.append(f"</{top}>"); reopen.append(top)
                        if stack and stack[-1] == t:
                            stack.pop(); out.append(f"</{t}>")
                        for top in reversed(reopen):
                            stack.append(top); out.append(f"<{top}>")
                # sinon, fermeture orpheline ignorée
            elif tag.startswith("br"):
                out.append("<br/>")
            i = j + 1
        else:
            k = s.find("<", i)
            if k == -1:
                out.append(s[i:]); break
            else:
                out.append(s[i:k]); i = k; continue
    while stack:
        out.append(f"</{stack.pop()}>")

    text = "".join(out).strip()

    # --- Nettoyage: enlever les <br/> du début et de la fin, et compacter les <br/> successifs
    text = re.sub(r"^(?:\s*<br/>\s*)+", "", text)
    text = re.sub(r"(?:\s*<br/>\s*)+$", "", text)
    text = re.sub(r"(?:\s*<br/>\s*){3,}", "<br/><br/>", text)  # pas plus de 2 de suite

    return text

def _clean_fragment(s: str) -> str:
    return sanitize_inline_markup(s)

def extract_paragraphs_from_html(html_text: str) -> List[str]:
    if not html_text or not html_text.strip():
        return []
    parts = TAGS_CLOSE_SPLIT.split(html_text)
    frags: List[str] = []
    i = 0
    while i < len(parts):
        frags.append(parts[i]); i += 2
    paras: List[str] = []
    for f in frags:
        clean = _clean_fragment(f)
        if clean:
            paras.append(clean)
    if not paras:
        tmp = re.sub(r"(?i)<br\s*/?>", "\n", html_text)
        tmp = re.sub(r"<[^>]+>", "", tmp)
        blocs = re.split(r"\n\s*\n", tmp)
        for b in blocs:
            b = "\n".join([ln.strip() for ln in b.splitlines() if ln.strip()])
            if b:
                b = b.replace("\n", "<br/>")
                paras.append(b)
    return paras

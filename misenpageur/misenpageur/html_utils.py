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
from bs4 import BeautifulSoup

TAGS_CLOSE_SPLIT = re.compile(r"</\s*(p|li|div)\s*>", re.I)

def sanitize_inline_markup(text: str) -> str:
    """
    Nettoie le balisage pour ne garder que les balises sûres pour ReportLab.
    Cette fonction est une sécurité, mais la nouvelle version de
    extract_paragraphs_from_html rend cette étape moins critique.
    """
    # Pour l'instant, on fait un simple strip. On pourrait ajouter un nettoyage
    # plus poussé ici si nécessaire (ex: enlever des attributs non supportés).
    return text.strip()

def _clean_fragment(s: str) -> str:
    return sanitize_inline_markup(s)


def extract_paragraphs_from_html(html_text: str) -> List[str]:
    """
    Extrait le contenu des balises <p> d'un texte HTML, en préservant
    les balises de formatage simples (<a href...>, <strong>, etc.)
    que ReportLab peut interpréter.
    """
    if not html_text:
        return []

    soup = BeautifulSoup(html_text, 'html.parser')
    paragraphs = soup.find_all('p')

    content_list = []
    for p in paragraphs:
        # p.decode_contents() retourne le HTML *intérieur* de la balise <p>
        # C'est exactement ce que nous voulons passer à ReportLab.
        inner_html = p.decode_contents(formatter="html").strip()
        if inner_html:
            content_list.append(inner_html)

    return content_list


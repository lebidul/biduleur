import os.path
import datetime
import math
import re
from typing import Dict, Any

import logging

log = logging.getLogger(__name__)


# Dictionnaire des noms propres connus (villes + pays) — défini dans
# biduleur/constants.py pour rester accessible par d'autres modules.
# Aliasé localement comme _PROPER_NOUNS_MAP pour conserver la convention
# "module-private" dans format_utils.
from biduleur.constants import PROPER_NOUNS_MAP as _PROPER_NOUNS_MAP

# Compilation d'une regex unique avec alternation, longueur décroissante pour
# que les noms longs (ex. "Le Mans") matchent avant les courts ("Mans").
_PROPER_NOUNS_RE = re.compile(
    r'\b(' + '|'.join(
        re.escape(k) for k in sorted(_PROPER_NOUNS_MAP.keys(), key=len, reverse=True)
    ) + r')\b',
    re.IGNORECASE | re.UNICODE,
)


def _smart_lower(s: str) -> str:
    """
    Lowercase la chaîne en :
    1. Title-Casant les mots intégralement en majuscules (PARIS → Paris,
       BERLIN → Berlin, LE MANS → Le Mans, etc.)
    2. Restaurant la casse correcte des noms de ville/pays connus listés
       dans `_PROPER_NOUNS_MAP` (préserve les majuscules internes type
       "Le Mans", "New York", "Saint-Pétersbourg").

    Exemples :
        "concert in PARIS, France" → "concert in Paris, France"
        "concert à le mans"        → "concert à Le Mans"
        "festival LE MANS"         → "festival Le Mans"
        "MILAN-BERLIN tour"        → "Milan-Berlin tour"
        "Tribute to Mozart"        → "tribute to mozart" (Mozart pas dans le dict)
    """
    if not s:
        return s

    # Étape 1 : Title-Case des mots tout-en-majuscules ; lowercase pour le reste.
    def _process(match: re.Match) -> str:
        word = match.group(0)
        if word.isupper():
            return word.capitalize()
        return word.lower()

    s = re.sub(r'[^\W\d_]+', _process, s, flags=re.UNICODE)

    # Étape 2 : restaurer la casse correcte des noms propres connus.
    def _restore(match: re.Match) -> str:
        return _PROPER_NOUNS_MAP[match.group(0).lower()]

    s = _PROPER_NOUNS_RE.sub(_restore, s)
    return s

from biduleur.constants import GENRE_EVT_SV, GENRE_EVT_CONCERT, GENRE_EVT_IMAGE, OUTPUT_FOLDER_NAME


def _to_str(value: Any) -> str:
    """
    Convertit une valeur en string de manière robuste.
    Gère les types Excel : datetime.time, datetime.datetime, int, float, None, NaN.
    Filtre aussi la chaîne "nan" qui peut apparaître lors de conversions pandas.
    """
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, datetime.time):
        return value.strftime("%Hh%M")
    if isinstance(value, datetime.datetime):
        return value.strftime("%d/%m/%Y %Hh%M")
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if s.strip().lower() == "nan":
        return ""
    return s


def format_artists_styles(*triplets) -> str:
    artistes_styles = ""
    for index, (genre, spectacle, artiste, style) in enumerate(triplets, start=1):
        genre_str = _to_str(genre)
        if not genre_str or genre_str.lower().strip() in ("", "nan"):
            continue

        # Ignorer le genre image (traité séparément dans event_utils)
        if genre_str.lower() == GENRE_EVT_IMAGE:
            continue

        if genre_str.lower() == GENRE_EVT_SV:
            artistes_styles += format_sv(spectacle, artiste, style, index)
        elif genre_str.lower() == GENRE_EVT_CONCERT:
            artistes_styles += format_concert(artiste, style, index)
    return artistes_styles


def format_sv(piece: str, artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    piece = _to_str(piece)
    artiste = _to_str(artiste)
    style = _to_str(style)

    if piece:
        return f"<strong>{signe_plus}\"{capfirst(piece)}\"</strong>{format_artiste(artiste)}{format_style(style)}"
    elif artiste:
        return f"<strong>{signe_plus}{capfirst(artiste)}</strong>{format_style(style)}"
    elif style:
        return f"<strong>{signe_plus}{capfirst(style)}</strong>"
    return ""


def format_concert(artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    artiste = _to_str(artiste)
    style = _to_str(style)

    if artiste:
        return f"<strong>{signe_plus}{artiste.upper()}</strong>{format_style(style)}"
    elif style:
        return f"<strong>{signe_plus}{capfirst(style)}</strong>"
    return ""


def format_artiste(artiste: str) -> str:
    artiste = _to_str(artiste)
    if not artiste:
        return ""
    return f" {capfirst(artiste)}"


def fmt_virgule(champ: str) -> str:
    champ = _to_str(champ)
    if not champ:
        return ""
    return f"{champ}, "


def _normalize_url(url: str) -> str:
    """Ajoute https:// si l'URL n'a pas de protocole."""
    url = url.strip()
    if not url:
        return url
    if not url.startswith(('http://', 'https://', 'mailto:')):
        return f"https://{url}"
    return url


def fmt_link(*links: str) -> str:
    formatted_links = ""
    for link in links:
        link = _to_str(link)
        if link:
            # Séparer URL et texte d'affichage si format "url|display"
            if '|' in link:
                url, display = link.split('|', 1)
            else:
                url, display = link, link
            url = _normalize_url(url)
            # Raccourcir le texte d'affichage (enlever protocole)
            display_short = display.replace('https://', '').replace('http://', '').rstrip('/')
            formatted_links += f" - <a href=\"{url}\">{display_short}</a>"
    return formatted_links


def fmt_heure(heure) -> str:
    """
    Formate l'heure. Gère datetime.time depuis Excel.
    """
    replacements = {"h00": "h", " h": "h", " a ": " à ", "h.n.c": "hnc"}

    # Conversion robuste en string
    heure_str = _to_str(heure)

    if not heure_str or heure_str.lower().strip() in ("", "nan"):
        return ""

    return f"{format_string(heure_str, replacements, lower=True)}, "


def fmt_prix(prix) -> str:
    replacements = {" a ": " à ", " €": "€", "gratuit": "0€", "t.n.c": "tnc", "h.n.c": "hnc"}
    prix_str = _to_str(prix)
    return format_string(prix_str, replacements, lower=True)


def format_style(style) -> str:
    replacements = {
        "theâtre": "th.", "théâtre": "th.", "theatre": "th.", "théatre": "th.",
        "Theâtre": "Th.", "Théâtre": "Th.", "Théatre": "Th.", "Theâtre": "Th.",
        "Theatre": "Th.", "electro": "électro", "Electro": "Électro",
        "metal": "métal", "Metal": "Métal"
    }
    style_str = _to_str(style)
    if not style_str or style_str.lower().strip() in ("", "nan"):
        return ""
    # _smart_lower : lowercase tout sauf les mots intégralement en majuscules
    # (préserve les noms de ville en caps comme PARIS, NYC, BERLIN…)
    return f" <em>({_smart_lower(format_string(style_str, replacements, lower=False))})</em>"


def format_string(string, replacement_dictionary: Dict, lower: bool = False) -> str:
    """
    Formate une chaîne avec remplacement. Convertit en string si nécessaire.
    """
    string = _to_str(string)

    if not string or string.lower().strip() in ("", "nan"):
        return ""

    if lower:
        string = string.lower()

    for old, new in replacement_dictionary.items():
        string = string.replace(old, new)

    return string


def format_evenement(evenement, style_evenement) -> str:
    evenement_str = _to_str(evenement)
    if not evenement_str or evenement_str.lower().strip() in ("", "nan"):
        return ""
    return f"{evenement_str}{format_style(style_evenement)} // "


def format_info(info, description_info, url_info) -> str:
    info_str = _to_str(info)
    if not info_str or info_str.lower().strip() in ("", "nan"):
        return ""
    return f"<strong>{info_str} - </strong><em>{_to_str(description_info)}</em>{fmt_link(url_info)}"


def format_lieu(lieu) -> str:
    lieu_str = _to_str(lieu)
    if not lieu_str or lieu_str == "Le Mans" or lieu_str.lower().strip() in ("", "nan"):
        return ""
    return f"{lieu_str}, "


def html_to_md(line: str) -> str:
    return (line.replace("<strong>", "**")
            .replace("</strong>", "**")
            .replace("<em>", "*")
            .replace("</em>", "*"))


def capfirst(s):
    try:
        s = _to_str(s)
        return s[:1].upper() + s[1:]
    except:
        return ''


def _prettify_agenda_html(body: str) -> str:
    """
    Transforme le body brut de l'agenda en HTML prêt-à-coller dans WordPress :
    - remplace les placeholders internes ({{SUBEV}}, {{MONTH:NOM}})
    - grossit et colore les en-têtes de date
    - transforme les séparateurs de mois en gros bandeaux
    Les styles sont INLINE pour survivre à un copier-coller ou à un éditeur
    WordPress qui filtre les <style>.
    """
    import re as _re

    # 1) Séparateur de mois (mode Bidul d'été) : <p>{{MONTH:NOM}}</p> → gros bandeau
    body = _re.sub(
        r'<p[^>]*>\s*\{\{MONTH:([^}]+)\}\}\s*</p>',
        r'<h2 style="text-align:center;font-family:Arial,sans-serif;font-size:2em;'
        r'color:#b8860b;letter-spacing:0.2em;margin:1.5em 0 0.8em;padding:0.3em 0;'
        r'border-top:3px double #b8860b;border-bottom:3px double #b8860b;">\1</h2>',
        body,
    )

    # 2) En-têtes de date agenda : identifiés par color:blue dans le style inline.
    #    Le format brut ferme via </spanp></p> — on normalise en </p>.
    body = _re.sub(
        r'<p[^>]*color:blue[^>]*>([^<]+?)</spanp></p>',
        r'<p style="font-family:Arial,sans-serif;font-size:1.15em;font-weight:bold;'
        r'text-align:center;color:#ffffff;background:#b8860b;padding:0.35em 0.5em;'
        r'margin:1.2em 0 0.5em;border-radius:3px;line-height:1.3;">\1</p>',
        body,
    )
    # Certains en-têtes de date en agenda n'ont pas le </spanp> foireux : idem sans.
    body = _re.sub(
        r'<p[^>]*color:blue[^>]*>([^<]+?)</p>',
        r'<p style="font-family:Arial,sans-serif;font-size:1.15em;font-weight:bold;'
        r'text-align:center;color:#ffffff;background:#b8860b;padding:0.35em 0.5em;'
        r'margin:1.2em 0 0.5em;border-radius:3px;line-height:1.3;">\1</p>',
        body,
    )

    # 3) Sous-events festival : {{SUBEV}} → indentation + puce ▸
    body = body.replace(
        '{{SUBEV}}',
        '<span style="display:inline-block;width:2.2em">&nbsp;</span>'
        '<span style="color:#b8860b;font-weight:bold">▸</span>&nbsp;'
    )

    # 4) Sous-en-tête de festival (rare mais possible)
    body = body.replace('{{SUBFEST}}', '')

    # 5) Placeholder image (au cas où) : on laisse pour l'instant en clair
    #    (l'agenda WordPress n'utilise pas les images inline)

    # 6) Line-height 0.25 illisible en HTML web → on rehausse.
    body = body.replace('line-height:0.25', 'line-height:1.4')

    return body


def output_html_file(html_body: str, original_file_name: str = None, output_filename: str = None,
                     output_folder_name: str = OUTPUT_FOLDER_NAME, pretty: bool = False):
    pre, ext = os.path.splitext(os.path.basename(original_file_name))
    if not output_filename:
        output_filename = os.path.join(output_folder_name, pre + ".html")
    else:
        output_filename = os.path.join(output_folder_name, output_filename)

    body = _prettify_agenda_html(html_body) if pretty else html_body

    # En mode pretty : wrapper responsive + charset explicite pour un rendu propre
    # une fois collé dans une page WordPress.
    if pretty:
        html_string = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="fr">
<head>
<meta charset="UTF-8"/>
<title>Agenda</title>
</head>
<body style="max-width:820px;margin:1.5em auto;padding:0 1em;color:#222;
font-family:'Arial Narrow',Arial,sans-serif;line-height:1.4;">
{body}
</body>
</html>
"""
    else:
        html_string = f"""<!DOCTYPE html>
<html  xmlns="http://www.w3.org/1999/xhtml" xml:lang="fr">
<head>
<meta charset="UTF-8"/>
<body>
{body}
</body>
</head>
</html>
"""
    open(output_filename, 'w+', encoding='utf-8').write(html_string)
    log.info(f"Évènements mises en forme et exportés das le fichier: {output_filename}")
import os.path
from typing import Dict

import logging # Ajouter cet import
log = logging.getLogger(__name__) # Obtenir le logger pour ce module

from biduleur.constants import GENRE_EVT_SV, GENRE_EVT_CONCERT, OUTPUT_FOLDER_NAME

def format_artists_styles(*triplets) -> str:
    artistes_styles = ""
    for index, (genre, spectacle, artiste, style) in enumerate(triplets, start=1):
        # Skip if genre is empty, None, or NaN (if genre is a string or None)
        if not genre or str(genre).lower().strip() in ("", "nan"):
            continue  # Skip this triplet

        if genre.lower() == GENRE_EVT_SV:
            artistes_styles += format_sv(spectacle, artiste, style, index)
        elif genre.lower() == GENRE_EVT_CONCERT:
            artistes_styles += format_concert(artiste, style, index)
    return artistes_styles

def format_sv(piece: str, artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    if piece:
        return f"<strong>{signe_plus}\"{capfirst(piece)}\"</strong>{format_artiste(artiste)}{format_style(style)}"
    elif artiste:
        return f"<strong>{signe_plus}{capfirst(artiste)}</strong>{format_style(style)}"
    elif style:
        return f"<strong>{signe_plus}{capfirst(style)}</strong>"
    return ""

def format_concert(artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    if artiste:
        return f"<strong>{signe_plus}{artiste.upper()}</strong>{format_style(style)}"
    elif style:
        return f"<strong>{signe_plus}{capfirst(style)}</strong>"
    return ""

def format_artiste(artiste: str) -> str:
    if not artiste:
        return ""
    return f" {capfirst(artiste)}"

def fmt_virgule(champ: str) -> str:
    if not champ:
        return ""
    return f"{champ}, "

def fmt_link(*links: str) -> str:
    formatted_links = ""
    for link in links:
        if link:
            formatted_links += f" - <a href=\"{link}\" target=\"_blank\">{link}</a>"
    return formatted_links

def fmt_heure(heure: str) -> str:
    replacements = {"h00": "h", " h": "h", " a ": " à ", "h.n.c": "hnc"}
    if not heure or str(heure).lower().strip() in ("", "nan"):
        return ""
    return f"{format_string(heure, replacements, lower=True)}, "

def fmt_prix(prix: str) -> str:
    replacements = {" a ": " à ", " €": "€", "gratuit": "0€", "t.n.c": "tnc", "h.n.c": "hnc"}
    return format_string(prix, replacements, lower=True)

def format_style(style: str) -> str:
    replacements = {
        "theâtre": "th.", "théâtre": "th.", "theatre": "th.", "théatre": "th.",
        "Theâtre": "Th.", "Théâtre": "Th.", "Théatre": "Th.", "Theâtre": "Th.",
        "Theatre": "Th.", "electro": "électro", "Electro": "Électro",
        "metal": "métal", "Metal": "Métal"
    }
    if not style or str(style).lower().strip() in ("", "nan"):
        return ""
    return f" <em>({format_string(style, replacements, lower=False).lower()})</em>"

def format_string(string: str, replacement_dictionary: Dict, lower: bool = False) -> str:
    if not string or str(string).lower().strip() in ("", "nan") or isinstance(string, int):
        return ""
    if lower:
        string = string.lower()
    for old, new in replacement_dictionary.items():
        string = string.replace(old, new)
    return string

def format_evenement(evenement: str, style_evenement: str) -> str:
    if not evenement or str(evenement).lower().strip() in ("", "nan"):
        return ""
    return f"{evenement}{format_style(style_evenement)} // "

def format_info(info: str, description_info: str, url_info: str) -> str:
    if not info or str(info).lower().strip() in ("", "nan"):
        return ""
    return f"<strong>{info}</strong>{format_style(description_info)}{fmt_link(url_info)}"

def format_lieu(lieu: str) -> str:
    if not lieu or lieu == "Le Mans" or str(lieu).lower().strip() in ("", "nan") or isinstance(lieu, int):
        return ""
    return f"{lieu}, "

def html_to_md(line: str) -> str:
    return (line.replace("<strong>", "**")
                .replace("</strong>", "**")
                .replace("<em>", "*")
                .replace("</em>", "*"))

def capfirst(s):
    try:
        return s[:1].upper() + s[1:]
    except:
        return ''

def output_html_file(html_body: str, original_file_name: str = None, output_filename: str = None,
                     output_folder_name: str = OUTPUT_FOLDER_NAME):
    pre, ext = os.path.splitext(os.path.basename(original_file_name))
    if not output_filename:
        output_filename = os.path.join(output_folder_name, pre + ".html")
    else:
        output_filename = os.path.join(output_folder_name, output_filename)
    html_string = f"""<!DOCTYPE html>
<html  xmlns="http://www.w3.org/1999/xhtml" xml:lang="fr">
<head>
<meta charset="UTF-8"/>
<body>
{html_body}
</body>
</head>
</html>
"""
    open(output_filename, 'w+', encoding='utf-8').write(html_string)
    log.info(f"Événements mises en forme et exportés das le fichier: {output_filename}")
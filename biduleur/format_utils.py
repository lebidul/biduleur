import os.path
import datetime
import math
from typing import Dict, Any

import logging

log = logging.getLogger(__name__)

from biduleur.constants import GENRE_EVT_SV, GENRE_EVT_CONCERT, OUTPUT_FOLDER_NAME


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
    return f" <em>({format_string(style_str, replacements, lower=False).lower()})</em>"


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
    log.info(f"Évènements mises en forme et exportés das le fichier: {output_filename}")
from typing import Dict
from constants import GENRE_EVT_SV, GENRE_EVT_CONCERT, OUTPUT_FOLDER_NAME
import os.path

def format_artists_styles(genre_evenement: str, *args) -> str:
    artistes_styles = ""
    if genre_evenement.lower() == GENRE_EVT_SV:
        for i in range(0, len(args), 3):
            piece = args[i]
            artiste = args[i + 1]
            style = args[i + 2]
            artistes_styles += format_sv(piece, artiste, style, i // 3 + 1)
    elif genre_evenement.lower() == GENRE_EVT_CONCERT:
        for i in range(0, len(args), 3):
            artiste = args[i + 1]
            style = args[i + 2]
            artistes_styles += format_concert(artiste, style, i // 3 + 1)
    return artistes_styles

def format_sv(piece: str, artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    if piece:
        return f"{signe_plus}\"{capfirst(piece)}\"{format_artiste(artiste)}{format_style(style)}"
    elif artiste:
        return f"{signe_plus}{capfirst(artiste)}{format_style(style)}"
    elif style:
        return f"{signe_plus}{capfirst(style)}"
    return ""

def format_concert(artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    if artiste:
        return f"{signe_plus}{artiste.upper()}{format_style(style)}"
    elif style:
        return f"{signe_plus}{capfirst(style)}"
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
            formatted_links += f", <a href=\"{link}\" target=\"_blank\">lien</a>"
    return formatted_links

def fmt_heure(heure: str) -> str:
    replacements = {"h00": "h", " h": "h", " a ": " à ", "h.n.c": "hnc"}
    if not heure:
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
    if not style:
        return ""
    return f" <em>({format_string(style, replacements, lower=False).lower()})</em>"

def format_string(string: str, replacement_dictionary: Dict, lower: bool = False) -> str:
    if not string:
        return ""
    if lower:
        string = string.lower()
    for old, new in replacement_dictionary.items():
        string = string.replace(old, new)
    return string

def format_evenement(evenement: str, style_evenement: str) -> str:
    if not evenement:
        return ""
    return f"{evenement}{format_style(style_evenement)} // "

def format_lieu(lieu: str) -> str:
    if not lieu or lieu == "Le Mans":
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
    print(f"Événements mises en forme et exportés das le fichier: {output_filename}")
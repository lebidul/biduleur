import warnings
from constants import *
from utils import *
import pandas as pd
import csv

warnings.filterwarnings(
    "ignore",
    message="The localize method is no longer necessary, as this time zone supports the fold attribute",
)


def parse_bidul(filename):
    """

    :param csv_reader:
    :return:
    """
    body_content = ''
    body_content_agenda = ''

    # sort csv_reader dictionary by date and type of event (musique first theatre then)
    with open(filename, "r", errors="ignore", encoding="utf8") as csvfile:
        reader = csv.DictReader(csvfile)
        try:
            sorted_csv_reader = sorted(reader, key=lambda d: (d[DATE].split()[1].zfill(2), d[GENRE_EVT], d[HORAIRE]))
        except:
            print("Oops!  Il y a un probleme pour classer le fichier. Reesssayez en s'assurant bien que chaque ligne a une date definie")

        # Initialize date
        current_date = None
        number_of_lines = 0
        # Handle csv content per row
        for row in sorted_csv_reader:
            formatted_line_bidul, formatted_line_agenda,  _, current_date = parse_bidul_event(row, current_date)
            body_content += formatted_line_bidul + "\n\n"
            body_content_agenda += formatted_line_agenda + "\n\n"
            number_of_lines += 1
    return body_content, body_content_agenda, number_of_lines

def parse_bidul_event(event: dict, current_date: str = None):
    """

    :param event:
    :param current_date:
    :return:
    """
    line_bidul = ""
    line_agenda = ""
    line_post = ""

    # strip all string values in event dictionary
    event = {
        key: (value.strip() if value is not None else "") for key, value in event.items()
    }

    if not current_date or current_date != event[DATE]:
        line_bidul = f"""{P_MD_OPEN_DATE}{event[DATE]}{P_MD_CLOSE_DATE}"""
        line_agenda = f"""{P_MD_OPEN_DATE_AGENDA}{event[DATE]}{P_MD_CLOSE}"""

        current_date = event[DATE]
        
    # Take in account particular formatting
    # manuel_formatting = format_manuel_formatting(event['manuel'])
    evenement = format_evenement(event[FESTIVAL], event[STYLE_FESTIVAL])
    ville = format_ville(event[VILLE])
    prix = fmt_prix(event[PRIX])
    heure = fmt_heure(event[HORAIRE])
    artistes_styles = format_artists_styles(event[GENRE_EVT],
                                            event[SPECTACLE1], event[ARTISTE1], event[STYLE1],
                                            event[SPECTACLE2], event[ARTISTE2], event[STYLE2],
                                            event[SPECTACLE3], event[ARTISTE3], event[STYLE3],
                                            event[SPECTACLE4], event[ARTISTE4], event[STYLE4])
    liens = fmt_link(event[LIEN1], event[LIEN2], event[LIEN3], event[LIEN4])

    # html formatting of the event
    # ligne avec puces
    # line_bidul += f"""{P_MD_OPEN}&ensp;&#9643 {evenement}{fmt_virgule(artistes_styles)} {fmt_virgule(event[LIEU])} {ville} {heure} {prix}{P_MD_CLOSE}"""
    # ligne sans puces
    string_event_bidul = f"""{capfirst(evenement)}{fmt_virgule(artistes_styles)} {capfirst(fmt_virgule(event[LIEU]))} {capfirst(ville)} {heure} {prix}"""
    string_event_agenda = f"""&ensp;&##9643 {capfirst(evenement)}{fmt_virgule(artistes_styles)} {capfirst(fmt_virgule(event[LIEU]))} {ville.capitalize()} {heure} {prix}{liens}"""
    string_event_bidul_post = f"""&ensp;&#10087 <span style="color:#CF8E6D">{capfirst(evenement)}{artistes_styles}</span><br>&nbsp{capfirst(event[LIEU])} {capfirst(ville)}<br>&nbsp{heure} {prix}"""

    line_bidul += f"""{P_MD_OPEN}{string_event_bidul}{P_MD_CLOSE}"""
    line_agenda += f"""{P_MD_OPEN}{string_event_agenda}{P_MD_CLOSE}"""
    line_post += f"""{P_MD_POST_OPEN}{string_event_bidul_post}{P_MD_CLOSE}"""

    return line_bidul, line_agenda, line_post, current_date


def format_artists_styles(genre_evenement: str,
                          piece1: str, artiste1: str, style1: str,
                          piece2: str, artiste2: str, style2: str,
                          piece3: str, artiste3: str, style3: str,
                          piece4: str, artiste4: str, style4: str):

    artistes_styles = ""
    if genre_evenement.lower() == GENRE_EVT_SV:
        # on verifie qu'il y ait un nom de spectacle. s'il y en a pas alors on ne met que l'artiste
        # sans les guillemets vides pour le nom du spectacle:
        # ex: "Edgar Yves (one man show), Comédie Le Mans, 21h, complet"
        artistes_styles += format_sv(piece1, artiste1, style1, 1)
        artistes_styles += format_sv(piece2, artiste2, style2, 2)
        artistes_styles += format_sv(piece3, artiste3, style3, 3)
        artistes_styles += format_sv(piece4, artiste4, style4, 4)
    elif genre_evenement.lower() == GENRE_EVT_CONCERT:
        # on verifie qu'il y a un artiste sinon on ne met que le style mais sans italique
        # avec la premiere lettre en majuscule
        # ex: "Musique irlandaise, Blue Zinc, 21h, au chapeau"
        artistes_styles += format_c(artiste1, style1, 1)
        artistes_styles += format_c(artiste2, style2, 2)
        artistes_styles += format_c(artiste3, style3, 3)
        artistes_styles += format_c(artiste4, style4, 4)
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

def format_c(artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    if artiste:
        return f"<strong>{signe_plus}{artiste.upper()}</strong>{format_style(style)}"
    elif style:
        return f"<strong>{signe_plus}{capfirst(style)}</strong>"
    return ""

def format_artiste(artiste: str):
    if not artiste:
        return ""
    return f" {capfirst(artiste)}"



def fmt_virgule(champ: str):
    """

    :param champ:
    :return:
    """
    if not champ:
        return
    return f"{champ},"


def fmt_link(link1: str, link2: str, link3: str, link4: str):
    """

    :param link1:
    :param link2:
    :param link3:
    :param link4:
    :return:
    """
    links = ""
    for link in [link1, link2, link3, link4]:
        if link:
            links += f", <a href=\"{link}\" target=\"_blank\">lien</a>"
    return links


def fmt_heure(heure: str):
    """

    :param heure:
    :return:
    """
    replacements = {
        "h00": "h",
        " h": "h",
        " a ": " à ",
        "h.n.c": "hnc",
        " a ": " à "
    }
    if not heure:
        return ""
    return f"{format_string(heure, replacements, lower=True)},"


def fmt_prix(prix: str):
    replacements = {
        " a ": " à ",
        " €": "€",
        "gratuit": "0€",
        "t.n.c": "tnc",
        "h.n.c": "hnc",
        " €": "€"
    }
    return format_string(prix, replacements, lower=True)


def format_style(style: str):
    """

    :param style:
    :return:
    """
    replacements = {
        "theâtre": "th.",
        "théâtre": "th.",
        "theatre": "th.",
        "théatre": "th.",
        "Theâtre": "Th.",
        "Théâtre": "Th.",
        "Théatre": "Th.",
        "Theâtre": "Th.",
        "Théâtre": "Th.",
        "Theatre": "Th.",
        "electro": "électro",
        "Electro": "Électro",
        "metal": "métal",
        "Metal": "Métal"
    }
    if not style:
        return ""

    # return f" <em>({lowfirst(format_string(style, replacements, lower=False))})</em>"
    return f" <em>({format_string(style, replacements, lower=False).lower()})</em>"

def format_string(string: str, replacement_dictionary: dict, lower=False):
    """

    :param string:
    :param replacement_dictionary:
    :param lower:
    :return:
    """
    if not string:
        return ""
    if lower:
        string = string.lower()
    for old, new in replacement_dictionary.items():
        string = string.replace(old, new)

    return string


def format_manuel_formatting(manuel: str):
    """

    :param manuel:
    :return:
    """
    if not manuel:
        return ""
    return f"<strong><em>A FORMATER MANUELLEMENT - </em></strong>"


def format_evenement(evenement: str, style_evenement: str):
    """

    :param style_evenement:
    :param evenement:
    :return:
    """
    if not evenement:
        return ""
    return f"{evenement}{format_style(style_evenement)} // "


def format_ville(ville: str):
    """
    Return '{ville}, ' if 'ville' is non-empty and not 'Le Mans',
    otherwise return an empty string.
    """
    if not ville or ville == "Le Mans":
        return ""
    return f"{ville}, "


def html_to_md(line: str):
    """

    :param line:
    :return:
    """
    return line.replace("<strong>", "**").replace("</strong>", "**").replace("<em>", "*").replace("</em>", "*")

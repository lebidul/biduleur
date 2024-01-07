import warnings
from constants import *

warnings.filterwarnings(
    "ignore",
    message="The localize method is no longer necessary, as this time zone supports the fold attribute",
)


def parse_bidul(csv_reader):
    """

    :param csv_reader:
    :return:
    """
    body_content = ''
    body_content_agenda = ''

    # sort csv_reader dictionary by date and type of event (musique first theatre then)
    try:
        sorted_csv_reader = sorted(csv_reader, key=lambda d: (d[DATE].split()[1].zfill(2), d[GENRE_EVT], d[HORAIRE]))
    except:
        print("Oops!  Il y a un probleme pour classer le fichier. Reesssayez en s'assurant bien que chaque ligne a une date definie")

    # Initialize date
    current_date = None
    number_of_lines = 0
    # Handle csv content per row
    for row in sorted_csv_reader:
        formatted_line_bidul, formatted_line_agenda, current_date = parse_bidul_event(row, current_date)
        body_content += formatted_line_bidul + "\n\n"
        body_content_agenda += formatted_line_agenda + "\n\n"
        number_of_lines += 1
    return body_content, body_content_agenda, number_of_lines


def parse_bidul_event(event: dict, current_date: str):
    """

    :param event:
    :param current_date:
    :return:
    """
    line_bidul = ""
    line_agenda = ""

    if not current_date or current_date != event[DATE]:
        line_bidul = f"""{P_MD_OPEN_DATE}{event[DATE]}{P_MD_CLOSE_DATE}"""
        line_agenda = f"""{P_MD_OPEN_DATE_AGENDA}{event[DATE]}{P_MD_CLOSE}"""

        current_date = event[DATE]
        
    # Take in account particular formatting
    # manuel_formatting = format_manuel_formatting(event['manuel'])
    evenement = format_evenement(event[FESTIVAL], event[STYLE_FESTIVAL])
    ville = format_ville(event[VILLE])
    prix = event[PRIX].replace(' a ', ' à ')
    heure = fmt_heure(event[HORAIRE])
    artistes_styles = format_artists_styles(event[GENRE_EVT],
                                            event[SPECTACLE1], event[ARTISTE1], event[STYLE1],
                                            event[SPECTACLE2], event[ARTISTE2], event[STYLE2],
                                            event[SPECTACLE3], event[ARTISTE3], event[STYLE3],
                                            event[SPECTACLE4], event[ARTISTE4], event[STYLE4]).replace(' a ', ' à ')
    liens = fmt_link(event[LIEN1], event[LIEN2], event[LIEN3], event[LIEN4])

    # html formatting of the event
    # ligne avec puces
    # line_bidul += f"""{P_MD_OPEN}&ensp;&#9643 {evenement}{fmt_virgule(artistes_styles)} {fmt_virgule(event[LIEU])} {ville} {heure} {prix}{P_MD_CLOSE}"""
    # ligne sans puces
    line_bidul += f"""{P_MD_OPEN}{capfirst(evenement)}{fmt_virgule(artistes_styles)} {capfirst(fmt_virgule(event[LIEU]))} {capfirst(ville)} {heure} {prix}{P_MD_CLOSE}"""
    line_agenda += f"""{P_MD_OPEN}&ensp;&#9643 {capfirst(evenement)}{fmt_virgule(artistes_styles)} {capfirst(fmt_virgule(event[LIEU]))} {ville.capitalize()} {heure} {prix}{liens}{P_MD_CLOSE}"""

    return line_bidul, line_agenda, current_date


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
        if piece1:
            artistes_styles += f"<strong>\"{capfirst(piece1)}\"</strong> {artiste1}{format_style(style1)}"
        elif not piece1 and artiste1:
            artistes_styles += f"<strong>{capfirst(artiste1)}</strong>{format_style(style1)}"
        elif not piece1 and not artiste1 and style1:
            artistes_styles += f"<strong>{capfirst(style1)}</strong>"
        if piece2:
            artistes_styles += f"<strong> + \"{capfirst(piece2)}\"</strong> {capfirst(artiste2)}{format_style(style2)}"
        elif not piece2 and artiste2:
            artistes_styles += f"<strong> + {capfirst(artiste2)}</strong>{format_style(style2)}"
        elif not piece2 and not artiste2 and style2:
            artistes_styles += f"<strong> + {capfirst(style2)}</strong>"
        if piece3:
            artistes_styles += f"<strong> + \"{capfirst(piece3)}\"</strong> {capfirst(artiste3)}{format_style(style3)}"
        elif not piece3 and artiste3:
            artistes_styles += f"<strong> + {capfirst(artiste3)}</strong>{format_style(style3)}"
        elif not piece3 and not artiste3 and style3:
            artistes_styles += f"<strong> + {capfirst(style3)}</strong>"
        if piece4:
            artistes_styles += f"<strong> + \"{capfirst(piece4)}\"</strong> {capfirst(artiste4)}{format_style(style4)}"
        elif not piece4 and artiste4:
            artistes_styles += f"<strong> + {capfirst(artiste4)}</strong>{format_style(style4)}"
        elif not piece4 and not artiste4 and style4:
            artistes_styles += f"<strong> + {capfirst(style4)}</strong>"
    elif genre_evenement.lower() == GENRE_EVT_CONCERT:
        # on verifie qu'il y a un artiste sinon on ne met que le style mais sans italique
        # avec la premiere lettre en majuscule
        # ex: "Musique irlandaise, Blue Zinc, 21h, au chapeau"
        if artiste1:
            artistes_styles += f"<strong>{artiste1.upper()}</strong>{format_style(style1)}"
        elif not artiste1 and style1:
            artistes_styles += f"<strong> {style1.capitalize()}</strong>"
        if artiste2:
            artistes_styles += f"<strong> + {artiste2.upper()}</strong>{format_style(style2)}"
        elif not artiste2 and style2:
            artistes_styles += f"<strong> + {style2.capitalize()}</strong>"
        if artiste3:
            artistes_styles += f"<strong> + {artiste3.upper()}</strong>{format_style(style3)}"
        elif not artiste3 and style3:
            artistes_styles += f"<strong> + {style3.capitalize()}</strong>"
        if artiste4:
            artistes_styles += f"<strong> + {artiste4.upper()}</strong>{format_style(style4)}"
        elif not artiste4 and style4:
            artistes_styles += f"<strong> + {style4.capitalize()}</strong>"
    return artistes_styles


def fmt_virgule(champ: str):
    """

    :param champ:
    :return:
    """
    if champ:
        return f"{champ},"
    return champ


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
    if heure:
        return f"{heure.lower().replace('h00', 'h').replace(' a ', ' à ')},"
    return heure


def format_style(style: str):
    """

    :param style:
    :return:
    """
    if style:
        return f"<em> ({style.lower()})</em>"
    else:
        return ""


def format_manuel_formatting(manuel: str):
    """

    :param manuel:
    :return:
    """
    if manuel:
        return f"<strong><em>A FORMATER MANUELLEMENT - </em></strong>"
    else:
        return ""


def format_evenement(evenement: str, style_evenement: str):
    """

    :param style_evenement:
    :param evenement:
    :return:
    """
    if evenement:
        return f"{evenement}{format_style(style_evenement)} // "
    else:
        return ""


def format_ville(ville: str):
    """

    :param ville:
    :return:
    """
    if ville and ville != "Le Mans":
        return f"{ville}, "
    else:
        return ""


def capfirst(s):
    return s[:1].upper() + s[1:]

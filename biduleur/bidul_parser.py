import warnings
import csv
from typing import Dict, Tuple, List

from constants import *
from utils import *

warnings.filterwarnings(
    "ignore",
    message="The localize method is no longer necessary, as this time zone supports the fold attribute",
)

def parse_bidul(filename: str) -> Tuple[str, str, int]:
    """
    Parse a CSV file and generate formatted content for events.

    Args:
        filename: The name of the CSV file to parse.

    Returns:
        A tuple containing the formatted body content, agenda content, and the number of lines processed.
    """
    body_content = ''
    body_content_agenda = ''

    try:
        with open(filename, "r", errors="ignore", encoding="utf8") as csvfile:
            reader = csv.DictReader(csvfile)
            sorted_csv_reader = sorted(reader, key=lambda d: (d[DATE].split()[1].zfill(2), d[GENRE_EVT], d[HORAIRE]))
    except Exception as e:
        print(f"Error sorting the file: {e}. Ensure each line has a defined date.")
        return body_content, body_content_agenda, 0

    current_date = None
    number_of_lines = 0

    for row in sorted_csv_reader:
        formatted_line_bidul, formatted_line_agenda, _, current_date = parse_bidul_event(row, current_date)
        body_content += formatted_line_bidul + "\n\n"
        body_content_agenda += formatted_line_agenda + "\n\n"
        number_of_lines += 1

    return body_content, body_content_agenda, number_of_lines

def parse_bidul_event(event: Dict, current_date: str = None) -> Tuple[str, str, str, str]:
    """
    Parse a single event and format it for output.

    Args:
        event: A dictionary containing event details.
        current_date: The current date being processed.

    Returns:
        A tuple containing the formatted lines for bidul, agenda, post, and the updated current date.
    """
    line_bidul = ""
    line_agenda = ""
    line_post = ""

    event = {key: (value.strip() if value is not None else "") for key, value in event.items()}

    if not current_date or current_date != event[DATE]:
        line_bidul = f"{P_MD_OPEN_DATE}{event[DATE]}{P_MD_CLOSE_DATE}"
        line_agenda = f"{P_MD_OPEN_DATE_AGENDA}{event[DATE]}{P_MD_CLOSE}"
        current_date = event[DATE]

    evenement = format_evenement(event[FESTIVAL], event[STYLE_FESTIVAL])
    ville = format_lieu(event[VILLE])
    lieu = format_lieu(event[LIEU])
    prix = fmt_prix(event[PRIX])
    heure = fmt_heure(event[HORAIRE])
    artistes_styles = format_artists_styles(
        event[GENRE_EVT], event[SPECTACLE1], event[ARTISTE1], event[STYLE1],
        event[SPECTACLE2], event[ARTISTE2], event[STYLE2],
        event[SPECTACLE3], event[ARTISTE3], event[STYLE3],
        event[SPECTACLE4], event[ARTISTE4], event[STYLE4]
    )
    liens = fmt_link(event[LIEN1], event[LIEN2], event[LIEN3], event[LIEN4])

    evenement_str = capfirst(evenement) if evenement else ''
    artistes_styles_str = fmt_virgule(artistes_styles) if artistes_styles else ''
    event_lieu_str = capfirst(fmt_virgule(event[LIEU])) if event.get(LIEU) else ''
    ville_str = capfirst(ville) if ville else ''
    lieu_str = capfirst(lieu) if lieu else ''

    string_event_bidul = f"{evenement_str}{artistes_styles_str}{lieu_str}{ville_str}{heure}{prix}"
    string_event_agenda = f"&ensp;&##9643 {evenement_str}{artistes_styles_str}{event_lieu_str}{ville_str}{heure}{prix}{liens}"
    string_event_bidul_post = f"&ensp;&#10087 <span style=\"color:#CF8E6D\">{evenement_str}{artistes_styles}</span><br>&nbsp{event_lieu_str}{ville_str}<br>&nbsp{heure}{prix}"

    line_bidul += f"{P_MD_OPEN}{string_event_bidul}{P_MD_CLOSE}"
    line_agenda += f"{P_MD_OPEN}{string_event_agenda}{P_MD_CLOSE}"
    line_post += f"{P_MD_POST_OPEN}{string_event_bidul_post}{P_MD_CLOSE}"

    return line_bidul, line_agenda, line_post, current_date

def format_artists_styles(genre_evenement: str, *args) -> str:
    """
    Format artists and styles based on the event genre.

    Args:
        genre_evenement: The genre of the event.
        *args: Variable length argument list containing pieces, artists, and styles.

    Returns:
        A formatted string of artists and styles.
    """
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
    """
    Format a single SV event entry.

    Args:
        piece: The piece name.
        artiste: The artist name.
        style: The style of the piece.
        number: The entry number.

    Returns:
        A formatted string for the SV event.
    """
    signe_plus = " + " if number != 1 else ""
    if piece:
        return f"{signe_plus}\"{capfirst(piece)}\"{format_artiste(artiste)}{format_style(style)}"
    elif artiste:
        return f"{signe_plus}{capfirst(artiste)}{format_style(style)}"
    elif style:
        return f"{signe_plus}{capfirst(style)}"
    return ""

def format_concert(artiste: str, style: str, number: int) -> str:
    """
    Format a single concert event entry.

    Args:
        artiste: The artist name.
        style: The style of the piece.
        number: The entry number.

    Returns:
        A formatted string for the concert event.
    """
    signe_plus = " + " if number != 1 else ""
    if artiste:
        return f"{signe_plus}{artiste.upper()}{format_style(style)}"
    elif style:
        return f"{signe_plus}{capfirst(style)}"
    return ""

def format_artiste(artiste: str) -> str:
    """
    Format the artist name.

    Args:
        artiste: The artist name.

    Returns:
        A formatted string for the artist.
    """
    if not artiste:
        return ""
    return f" {capfirst(artiste)}"

def fmt_virgule(champ: str) -> str:
    """
    Format a string with a trailing comma if it is non-empty.

    Args:
        champ: The string to format.

    Returns:
        A formatted string with a trailing comma.
    """
    if not champ:
        return ""
    return f"{champ}, "

def fmt_link(*links: str) -> str:
    """
    Format a list of links.

    Args:
        *links: Variable length argument list of links.

    Returns:
        A formatted string of links.
    """
    formatted_links = ""
    for link in links:
        if link:
            formatted_links += f", <a href=\"{link}\" target=\"_blank\">lien</a>"
    return formatted_links

def fmt_heure(heure: str) -> str:
    """
    Format the time string.

    Args:
        heure: The time string to format.

    Returns:
        A formatted time string.
    """
    replacements = {
        "h00": "h",
        " h": "h",
        " a ": " à ",
        "h.n.c": "hnc",
    }
    if not heure:
        return ""
    return f"{format_string(heure, replacements, lower=True)}, "

def fmt_prix(prix: str) -> str:
    """
    Format the price string.

    Args:
        prix: The price string to format.

    Returns:
        A formatted price string.
    """
    replacements = {
        " a ": " à ",
        " €": "€",
        "gratuit": "0€",
        "t.n.c": "tnc",
        "h.n.c": "hnc",
    }
    return format_string(prix, replacements, lower=True)

def format_style(style: str) -> str:
    """
    Format the style string.

    Args:
        style: The style string to format.

    Returns:
        A formatted style string.
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
        "Theatre": "Th.",
        "electro": "électro",
        "Electro": "Électro",
        "metal": "métal",
        "Metal": "Métal"
    }
    if not style:
        return ""
    return f" <em>({format_string(style, replacements, lower=False).lower()})</em>"

def format_string(string: str, replacement_dictionary: Dict, lower: bool = False) -> str:
    """
    Format a string using a replacement dictionary.

    Args:
        string: The string to format.
        replacement_dictionary: A dictionary of replacements.
        lower: Whether to convert the string to lowercase.

    Returns:
        A formatted string.
    """
    if not string:
        return ""
    if lower:
        string = string.lower()
    for old, new in replacement_dictionary.items():
        string = string.replace(old, new)
    return string

def format_evenement(evenement: str, style_evenement: str) -> str:
    """
    Format the event name and style.

    Args:
        evenement: The event name.
        style_evenement: The style of the event.

    Returns:
        A formatted string for the event.
    """
    if not evenement:
        return ""
    return f"{evenement}{format_style(style_evenement)} // "

def format_lieu(lieu: str) -> str:
    """
    Format the location string.

    Args:
        lieu: The location string to format.

    Returns:
        A formatted location string.
    """
    if not lieu or lieu == "Le Mans":
        return ""
    return f"{lieu}, "

def html_to_md(line: str) -> str:
    """
    Convert HTML tags to Markdown.

    Args:
        line: The string containing HTML tags.

    Returns:
        A string with HTML tags converted to Markdown.
    """
    return (line.replace("<strong>", "**")
                .replace("</strong>", "**")
                .replace("<em>", "*")
                .replace("</em>", "*"))

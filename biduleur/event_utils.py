from biduleur.format_utils import format_evenement, format_lieu, fmt_prix, fmt_heure, format_artists_styles, fmt_link, capfirst, fmt_virgule
from biduleur.constants import DATE, COLONNE_INFO, FESTIVAL, STYLE_FESTIVAL, VILLE, LIEU, PRIX, HORAIRE, GENRE1, SPECTACLE1, ARTISTE1, STYLE1, GENRE2, SPECTACLE2, ARTISTE2, STYLE2, GENRE3, SPECTACLE3, ARTISTE3, STYLE3, GENRE4, SPECTACLE4, ARTISTE4, STYLE4, LIEN1, LIEN2, LIEN3, LIEN4, P_MD_OPEN_DATE, P_MD_CLOSE_DATE, P_MD_OPEN_DATE_AGENDA, P_MD_CLOSE, P_MD_OPEN, P_MD_POST_OPEN
from typing import Dict, Tuple

def parse_bidul_event(event: Dict, current_date: str = None) -> Tuple[str, str, str, str]:
    # Liste de toutes les clés requises dans cette fonction
    required_keys = [
        DATE, FESTIVAL, STYLE_FESTIVAL, VILLE, LIEU, PRIX, HORAIRE,
        GENRE1, SPECTACLE1, ARTISTE1, STYLE1,
        GENRE2, SPECTACLE2, ARTISTE2, STYLE2,
        GENRE3, SPECTACLE3, ARTISTE3, STYLE3,
        GENRE4, SPECTACLE4, ARTISTE4, STYLE4,
    ]

    # Vérifie que toutes les clés requises sont présentes
    missing_keys = [key for key in required_keys if key not in event]
    if missing_keys:
        raise KeyError(f"Colonne manquante : {', '.join(missing_keys)}")

    # Nettoyage des valeurs
    event = {key: (value.strip() if isinstance(value, str) else value if value is not None else "")
             for key, value in event.items()}

    # Initialisation des lignes
    line_bidul = ""
    line_agenda = ""
    line_post = ""

    # Gestion de la date
    if not current_date or current_date != event[DATE]:
        line_bidul = f"{P_MD_OPEN_DATE}{event[DATE]}{P_MD_CLOSE_DATE}"
        line_agenda = f"{P_MD_OPEN_DATE_AGENDA}{event[DATE]}{P_MD_CLOSE}"
        current_date = event[DATE]

    if event[DATE] == COLONNE_INFO:
        evenement = format_evenement(event[FESTIVAL], event[STYLE_FESTIVAL])
        line_bidul += f"{P_MD_OPEN}{capfirst(evenement)}{P_MD_CLOSE}"
        line_agenda += f"{P_MD_OPEN}{capfirst(evenement)}{P_MD_CLOSE}"
        line_post += f"{P_MD_POST_OPEN}{capfirst(evenement)}{P_MD_CLOSE}"
        return line_bidul, line_agenda, line_post, current_date


    # Formatage des éléments
    evenement = format_evenement(event[FESTIVAL], event[STYLE_FESTIVAL])
    ville = format_lieu(event[VILLE])
    lieu = format_lieu(event[LIEU])
    prix = fmt_prix(event[PRIX])
    heure = fmt_heure(event[HORAIRE])

    # Formatage des artistes/styles
    artistes_styles = format_artists_styles(
        (event[GENRE1], event[SPECTACLE1], event[ARTISTE1], event[STYLE1]),
        (event[GENRE2], event[SPECTACLE2], event[ARTISTE2], event[STYLE2]),
        (event[GENRE3], event[SPECTACLE3], event[ARTISTE3], event[STYLE3]),
        (event[GENRE4], event[SPECTACLE4], event[ARTISTE4], event[STYLE4]),
    )

    # liens = fmt_link(event[LIEN1], event[LIEN2], event[LIEN3], event[LIEN4])

    # Mise en forme des chaînes
    evenement_str = capfirst(evenement) if evenement else ''
    artistes_styles_str = fmt_virgule(artistes_styles) if artistes_styles else ''
    # event_lieu_str = capfirst(fmt_virgule(event[LIEU])) if event.get(LIEU) else ''
    event_lieu_str = capfirst(fmt_virgule(lieu)) if lieu else ''
    ville_str = capfirst(ville) if ville else ''
    lieu_str = capfirst(lieu) if lieu else ''

    # Construction des lignes de sortie
    string_event_bidul = f"{evenement_str}{artistes_styles_str}{lieu_str}{ville_str}{heure}{prix}"
    # string_event_agenda = f"&ensp;&##9643 {evenement_str}{artistes_styles_str}{event_lieu_str}{ville_str}{heure}{prix}{liens}"
    string_event_agenda = f"&ensp;&##9643 {evenement_str}{artistes_styles_str}{event_lieu_str}{ville_str}{heure}{prix}"
    string_event_bidul_post = (
        f"&ensp;&#10087 <span style=\"color:#CF8E6D\">{evenement_str}{artistes_styles}</span><br>"
        f"&nbsp{event_lieu_str}{ville_str}<br>&nbsp{heure}{prix}"
    )

    # Ajout des balises
    line_bidul += f"{P_MD_OPEN}{string_event_bidul}{P_MD_CLOSE}"
    line_agenda += f"{P_MD_OPEN}{string_event_agenda}{P_MD_CLOSE}"
    line_post += f"{P_MD_POST_OPEN}{string_event_bidul_post}{P_MD_CLOSE}"

    return line_bidul, line_agenda, line_post, current_date

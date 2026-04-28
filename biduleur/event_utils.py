import math
from biduleur.format_utils import format_evenement, format_info, format_lieu, fmt_prix, fmt_heure, format_artists_styles, fmt_link, capfirst, fmt_virgule
from biduleur.constants import DATE, COLONNE_INFO, FESTIVAL, STYLE_FESTIVAL, VILLE, LIEU, PRIX, HORAIRE, GENRE_EVT_IMAGE, BIDUL_COL, P_MD_OPEN_DATE, P_MD_CLOSE_DATE, P_MD_OPEN_DATE_AGENDA, P_MD_CLOSE, P_MD_OPEN, P_MD_POST_OPEN
from typing import Dict, Tuple


def _format_bidul_num(val) -> str:
    """Formate la valeur de la colonne BIDUL en chaîne (entier si possible)."""
    if val is None:
        return ""
    if isinstance(val, float):
        import math
        if math.isnan(val):
            return ""
        if val == int(val):
            return str(int(val))
        return str(val)
    s = str(val).strip()
    if not s or s.lower() == 'nan':
        return ""
    # Si c'est une chaîne numérique style "23.0", simplifier
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except ValueError:
        pass
    return s


def parse_bidul_event(
        event: Dict,
        current_date: str = None,
        festival_in_date_header: bool = False,
        bidul_label_enabled: bool = False,
) -> Tuple[str, str, str, str]:
    # Liste des clés de base requises
    required_keys = [
        DATE, FESTIVAL, STYLE_FESTIVAL, VILLE, LIEU, PRIX, HORAIRE,
    ]

    # Vérifie que les clés de base sont présentes
    missing_keys = [key for key in required_keys if key not in event]
    if missing_keys:
        raise KeyError(f"Colonne manquante : {', '.join(missing_keys)}")

    # Récupérer les sets de colonnes spectacle détectés dynamiquement
    spectacle_col_sets = event.get('_spectacle_col_sets', [])

    # Nettoyage des valeurs (None ET float NaN -> "")
    def _clean(v):
        if v is None:
            return ""
        if isinstance(v, float) and math.isnan(v):
            return ""
        if isinstance(v, str):
            return v.strip()
        return v

    event = {key: _clean(value) for key, value in event.items()}

    # Initialisation des lignes
    line_bidul = ""
    line_agenda = ""
    line_post = ""

    # Gestion de la date
    if not current_date or current_date != event[DATE]:
        date_display = event[DATE]

        # Mode expérimental Teriaki : déplacer le festival dans l'en-tête de date
        if festival_in_date_header:
            from biduleur.format_utils import _to_str
            fest_raw = _to_str(event.get(FESTIVAL, '')).strip()
            if fest_raw and fest_raw.lower() != 'nan' and date_display != COLONNE_INFO:
                date_display = f"{date_display} -- {fest_raw}"

        # Placeholder "Bidul #xxx" pour rendu côté misenpageur (à gauche de la date)
        if bidul_label_enabled and date_display != COLONNE_INFO:
            bidul_num = _format_bidul_num(event.get(BIDUL_COL))
            if bidul_num:
                date_display = f"{{{{BIDUL:{bidul_num}}}}}{date_display}"

        line_bidul = f"{P_MD_OPEN_DATE}{date_display}{P_MD_CLOSE_DATE}"
        line_agenda = f"{P_MD_OPEN_DATE_AGENDA}{date_display}{P_MD_CLOSE}"
        current_date = event[DATE]

    # Pour la colonne info, on a besoin du premier NOM SPECTACLE
    first_spectacle_col = spectacle_col_sets[0]['spectacle'] if spectacle_col_sets else None

    # Détection des lignes image (GENRE 1 = "img")
    first_genre_col = spectacle_col_sets[0]['genre'] if spectacle_col_sets else None
    first_genre_val = str(event.get(first_genre_col, '')).strip().lower() if first_genre_col else ''

    if first_genre_val == GENRE_EVT_IMAGE:
        # Ligne image : NOM SPECTACLE 1 contient le nom du fichier
        # Le placeholder doit être dans un <p> pour être extrait par extract_paragraphs_from_html
        image_filename = event.get(first_spectacle_col, '') if first_spectacle_col else ''
        if image_filename:
            img_tag = f"<p>{{{{IMG:{image_filename}}}}}</p>"
            line_bidul += img_tag
            line_agenda += img_tag
            line_post += img_tag
        return line_bidul, line_agenda, line_post, current_date

    if event[DATE] == COLONNE_INFO:
        spectacle_val = event.get(first_spectacle_col, '') if first_spectacle_col else ''
        evenement = format_info(event[FESTIVAL], event[STYLE_FESTIVAL], spectacle_val)
        line_bidul += f"{P_MD_OPEN}{capfirst(evenement)}{P_MD_CLOSE}"
        line_agenda += f"{P_MD_OPEN}{capfirst(evenement)}{P_MD_CLOSE}"
        line_post += f"{P_MD_POST_OPEN}{capfirst(evenement)}{P_MD_CLOSE}"
        return line_bidul, line_agenda, line_post, current_date


    # Formatage des éléments
    # En mode festival_in_date_header, le festival est déjà affiché dans l'en-tête de date
    # → on omet le prefixe "Festival //" de chaque ligne événement
    if festival_in_date_header:
        evenement = ""
    else:
        evenement = format_evenement(event[FESTIVAL], event[STYLE_FESTIVAL])
    ville = format_lieu(event[VILLE])
    lieu = format_lieu(event[LIEU])
    prix = fmt_prix(event[PRIX])
    heure = fmt_heure(event[HORAIRE])

    # Formatage dynamique des artistes/styles à partir des colonnes détectées
    triplets = []
    for col_set in spectacle_col_sets:
        triplets.append((
            event.get(col_set['genre'], ''),
            event.get(col_set['spectacle'], '') if col_set['spectacle'] else '',
            event.get(col_set['artiste'], '') if col_set['artiste'] else '',
            event.get(col_set['style'], '') if col_set['style'] else '',
        ))
    artistes_styles = format_artists_styles(*triplets)

    # liens = fmt_link(event[LIEN1], event[LIEN2], event[LIEN3], event[LIEN4])

    # Mise en forme des chaînes
    evenement_str = capfirst(evenement) if evenement else ''
    artistes_styles_str = fmt_virgule(artistes_styles) if artistes_styles else ''
    # event_lieu_str = capfirst(fmt_virgule(event[LIEU])) if event.get(LIEU) else ''
    event_lieu_str = capfirst(fmt_virgule(lieu)) if lieu else ''
    ville_str = capfirst(ville) if ville else ''
    lieu_str = capfirst(lieu) if lieu else ''

    # Créez d'abord le bloc heure/prix
    heure_prix_block = f"{heure}{prix}"
    heure_prix_insecable = heure_prix_block.replace(" ", "\u00A0")

    # Construction des lignes de sortie
    string_event_bidul = f"{evenement_str}{artistes_styles_str}{lieu_str}{ville_str}{heure_prix_insecable}"
    # string_event_agenda = f"&ensp;&##9643 {evenement_str}{artistes_styles_str}{event_lieu_str}{ville_str}{heure}{prix}{liens}"
    string_event_agenda = f"{evenement_str}{artistes_styles_str}{lieu_str}{ville_str}{heure_prix_insecable}"
    string_event_bidul_post = (
        f"&ensp;&#10087 <span style=\"color:#CF8E6D\">{evenement_str}{artistes_styles}</span><br>"
        f"&nbsp{event_lieu_str}{ville_str}<br>&nbsp{heure}{prix}"
    )

    # Ajout des balises
    line_bidul += f"{P_MD_OPEN}{string_event_bidul}{P_MD_CLOSE}"
    line_agenda += f"{P_MD_OPEN}{string_event_agenda}{P_MD_CLOSE}"
    line_post += f"{P_MD_POST_OPEN}{string_event_bidul_post}{P_MD_CLOSE}"

    return line_bidul, line_agenda, line_post, current_date

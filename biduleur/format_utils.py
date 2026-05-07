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


# =====================================================================
# Normalisation HEURE & PRIX (fuzzy / regex-based)
# =====================================================================

# Mots-clés PRIX exacts → output canonique. Comparaison case-insensitive
# après strip de la chaîne d'entrée.
_PRICE_KEYWORDS_EXACT = {
    'gratuit': '0€',          # convention Bidul : on affiche "0€" plutôt que "gratuit"
    'free': '0€',
    'libre': 'prix libre',
    'prix libre': 'prix libre',
    'au chapeau': 'au chapeau',
    'chapeau': 'au chapeau',
    'complet': 'complet',
    'tnc': 'tnc',
    't.n.c': 'tnc',
    'hnc': 'hnc',
    'h.n.c': 'hnc',
    'a confirmer': 'à confirmer',
    'à confirmer': 'à confirmer',
    'achat sur place': 'achat sur place',
}


def normalize_heure(s: str) -> str:
    """
    Normalise une chaîne HEURE en une forme canonique :
        "20H30"           → "20h30"
        "20H"             → "20h"
        "10 h & 14h30"    → "10h & 14h30"
        "10h et 14h30"    → "10h & 14h30"
        "20h00"           → "20h"
        "17h-4h"          → "17h-4h"
        "Dès 19H"         → "Dès 19h"
        "5h00"            → "5h"
        ""                → ""

    Règles :
    - 'H' majuscule → 'h' minuscule (devant ou après chiffre)
    - Espaces autour de 'h' supprimés (`10 h` → `10h`)
    - `h00` → `h` (pas de minutes inutiles)
    - 'et' (insensible à la casse) → '&'
    - Espaces multiples → un seul espace
    """
    if not s or not s.strip():
        return ""
    s = s.strip()

    # Normalisation 'H' / espace autour : convertit "20H30", "20 h", "10 H30"
    # en "20h30", "20h", "10h30". Si les minutes sont "00", on les supprime.
    # IMPORTANT : pas de \s* APRES [Hh] (pour ne pas avaler les espaces autour
    # des séparateurs comme '&' ou 'et').
    def _h_repl(m):
        hh = m.group(1)
        mm = m.group(2)
        if mm and mm != '00':
            return f"{hh}h{mm}"
        return f"{hh}h"
    s = re.sub(r'(\d+)\s*[Hh](\d*)', _h_repl, s)

    # 'et' (séparateur d'horaires) → '&'
    s = re.sub(r'\s+et\s+', ' & ', s, flags=re.IGNORECASE)

    # Mots-clés HEURE
    s = re.sub(r'\bt\.n\.c\b', 'tnc', s, flags=re.IGNORECASE)
    s = re.sub(r'\bh\.n\.c\b', 'hnc', s, flags=re.IGNORECASE)
    s = re.sub(r'\bTNC\b', 'tnc', s)
    s = re.sub(r'\bHNC\b', 'hnc', s)

    # Normalisation virgules/espaces
    s = re.sub(r'\s*,\s*', ', ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def normalize_prix(s: str) -> str:
    """
    Normalise une chaîne PRIX en une forme canonique :
        "Gratuit"        → "gratuit"
        "GRATUIT"        → "gratuit"
        "Au Chapeau"     → "au chapeau"
        "Prix Libre"     → "prix libre"
        "Libre"          → "prix libre"
        "0", "0 €", "0€" → "0€"
        "5 €"            → "5€"
        "5 euros"        → "5€"
        "5 à 10 €"       → "5 à 10€"
        "5-10€"          → "5 à 10€"
        "5.50€"          → "5,50€" (style français pour les décimales)
        "tnc", "T.N.C"   → "tnc"
        "5€ et +"        → "5€ et +" (préservé)
        "à partir de 1€" → "à partir de 1€" (préservé)
        ""               → ""

    Pour les descriptions complexes (tarif plein/réduit etc.), seules les
    parties reconnues (devises, mots-clés, plages X-Y) sont normalisées ;
    le reste du texte est préservé.
    """
    if not s or not s.strip():
        return ""
    s = s.strip()

    # Cas mot-clé exact (case-insensitive)
    low = s.lower()
    if low in _PRICE_KEYWORDS_EXACT:
        return _PRICE_KEYWORDS_EXACT[low]

    # "0" / "0€" / "0 €" → "0€"
    if re.fullmatch(r'0\s*€?', low):
        return '0€'

    # Nombre seul (entier ou décimal) sans devise → ajouter "€"
    # Ex: "10" → "10€", "5,50" → "5,50€", "22" → "22€"
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)', low)
    if m:
        val = m.group(1).replace('.', ',')
        return f"{val}€"

    # "euros" / "euro" → "€" (insensible à la casse)
    s = re.sub(r'\s*euros?\b', '€', s, flags=re.IGNORECASE)
    # Pas d'espace avant €
    s = re.sub(r'\s+€', '€', s)
    # Décimales style français : '5.50' → '5,50'
    s = re.sub(r'(\d+)\.(\d+)', r'\1,\2', s)
    # 'X-Y' (entre chiffres) → 'X à Y'
    s = re.sub(r'(\d)\s*-\s*(\d)', r'\1 à \2', s)
    # ' a ' (ASCII) → ' à ' (avec accent)
    s = re.sub(r' a (?=\d)', ' à ', s)

    # Mots-clés inline (case-insensitive)
    s = re.sub(r'\bau\s+chapeau\b', 'au chapeau', s, flags=re.IGNORECASE)
    # "gratuit" inline → "0€" (convention Bidul) — applique aussi pour "Gratuit"
    s = re.sub(r'\bgratuit\b', '0€', s, flags=re.IGNORECASE)
    s = re.sub(r'\bprix\s+libre\b', 'prix libre', s, flags=re.IGNORECASE)
    s = re.sub(r'\bt\.n\.c\b', 'tnc', s, flags=re.IGNORECASE)
    s = re.sub(r'\bh\.n\.c\b', 'hnc', s, flags=re.IGNORECASE)
    s = re.sub(r'\bTNC\b', 'tnc', s)
    s = re.sub(r'\bHNC\b', 'hnc', s)
    s = re.sub(r'\bComplet\b', 'complet', s)

    # Espaces multiples
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def fmt_heure(heure) -> str:
    """
    Formate l'heure pour le rendu Bidul.
    Applique normalize_heure puis ajoute le séparateur ", " final.
    """
    heure_str = _to_str(heure)
    if not heure_str or heure_str.lower().strip() in ("", "nan"):
        return ""
    return f"{normalize_heure(heure_str)}, "


def fmt_prix(prix) -> str:
    """
    Formate le prix pour le rendu Bidul.
    Applique normalize_prix.
    """
    prix_str = _to_str(prix)
    if not prix_str or prix_str.lower().strip() in ("", "nan"):
        return ""
    return normalize_prix(prix_str)


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
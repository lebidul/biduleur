DATE = 'DATE'
GENRE_EVT = 'GENRE'
HORAIRE = 'HEURE'
FESTIVAL = 'FESTOCHE\nEVENEMENT '
STYLE_FESTIVAL = 'STYLE \nFESTOCHE / EVENEMENT '
VILLE = 'VILLE'
LIEU = 'LIEU'
PRIX = 'PRIX'
GENRE_EVT_SV = 'sv'
GENRE_EVT_CONCERT = 'c'
GENRE1 = 'GENRE 1'
SPECTACLE1 = 'NOM SPECTACLE 1 ( SV )'
ARTISTE1 = 'COMPAGNIE 1 ( SV ) ou\nGROUPE 1 / ARTISTE 1 ( C )'
STYLE1 = 'STYLE \nSPECTACLE 1 (SV) / CONCERT 1 (C)'
GENRE2 = 'GENRE 2'
SPECTACLE2 = 'NOM SPECTACLE 2 ( SV )'
ARTISTE2 = 'COMPAGNIE 2 ( SV ) ou\nGROUPE 2 / ARTISTE 2 ( C )'
STYLE2 = 'STYLE \nSPECTACLE 2 ( SV ) / CONCERT 2 ( C )'
GENRE3 = 'GENRE 3'
SPECTACLE3 = 'NOM SPECTACLE 3 ( SV )'
ARTISTE3 = 'COMPAGNIE 3 ( SV ) ou\nGROUPE 3 / ARTISTE 3 ( C )'
STYLE3 = 'STYLE \nSPECTACLE 3 ( SV ) / CONCERT 3 ( C )'
GENRE4 = 'GENRE 4'
SPECTACLE4 = 'NOM SPECTACLE 4 ( SV )'
ARTISTE4 = 'COMPAGNIE 4 ( SV ) ou\nGROUPE 4 / ARTISTE 4 ( C )'
STYLE4 = 'STYLE \nSPECTACLE 4 ( SV ) / CONCERT 4 ( C )'
LIEN1 = 'LIEN1'
LIEN2 = 'LIEN2'
LIEN3 = 'LIEN3'
LIEN4 = 'LIEN4'


# --- Colonnes spectacle dynamiques ---
import re

# Préfixes de regex pour détecter les colonnes spectacle par numéro
_GENRE_PATTERN = re.compile(r'^GENRE\s+(\d+)$', re.IGNORECASE)
_SPECTACLE_PATTERN = re.compile(r'^NOM\s+SPECTACLE\s+(\d+)', re.IGNORECASE)
_ARTISTE_PATTERN = re.compile(r'^COMPAGNIE\s+(\d+)', re.IGNORECASE)
_STYLE_PATTERN = re.compile(r'^STYLE\s+.*SPECTACLE\s+(\d+)', re.IGNORECASE | re.DOTALL)


def detect_spectacle_columns(columns):
    """
    Détecte dynamiquement les sets de colonnes spectacle (GENRE N, NOM SPECTACLE N,
    COMPAGNIE N, STYLE N) présents dans la liste de colonnes du fichier.

    Returns:
        list[dict]: Liste triée par numéro, chaque dict contient les clés
                    'genre', 'spectacle', 'artiste', 'style' mappées aux noms
                    réels des colonnes du fichier.
    """
    # Collecter les numéros et noms de colonnes détectés
    genre_cols = {}
    spectacle_cols = {}
    artiste_cols = {}
    style_cols = {}

    for col in columns:
        col_str = str(col)
        m = _GENRE_PATTERN.match(col_str)
        if m:
            genre_cols[int(m.group(1))] = col_str
            continue
        m = _SPECTACLE_PATTERN.match(col_str)
        if m:
            spectacle_cols[int(m.group(1))] = col_str
            continue
        m = _ARTISTE_PATTERN.match(col_str)
        if m:
            artiste_cols[int(m.group(1))] = col_str
            continue
        m = _STYLE_PATTERN.match(col_str)
        if m:
            style_cols[int(m.group(1))] = col_str
            continue

    # Construire les sets complets (un set = les 4 colonnes pour un numéro donné)
    all_nums = sorted(set(genre_cols.keys()) | set(spectacle_cols.keys())
                      | set(artiste_cols.keys()) | set(style_cols.keys()))

    result = []
    for n in all_nums:
        if n in genre_cols:
            result.append({
                'num': n,
                'genre': genre_cols.get(n),
                'spectacle': spectacle_cols.get(n),
                'artiste': artiste_cols.get(n),
                'style': style_cols.get(n),
            })

    return result

# OUTPUT_FOLDER_NAME = './outputs/'
# P_MD_OPEN_DATE = '<p class="date">'
# P_MD_CLOSE_DATE = '</p>'
# P_MD_OPEN_DATE_AGENDA = '<p class="date-agenda">'
# P_MD_CLOSE = '</p>'
# P_MD_OPEN = '<p>'
# P_MD_POST_OPEN = '<div class="post">'


COLONNE_INFO = "Coups de coeur et en bref"
OUTPUT_FOLDER_NAME = './outputs/'
LINE_HEIGHT = "0.25"
# P_MD_OPEN = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT}">"""
# P_MD_OPEN = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT}">&ensp;&#9643 """
P_MD_OPEN = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT}">❑ """
# P_MD_OPEN_DATE = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT};background-color:grey">"""
P_MD_OPEN_DATE = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT}">"""
P_MD_OPEN_DATE_AGENDA = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT};color:blue">"""
P_MD_CLOSE = f"""</p>"""
P_MD_CLOSE_DATE = f"""</spanp></p>"""
P_MD_POST_OPEN = f"""<p style="font-family: Lucida Console">"""
import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Any

import pandas as pd

from biduleur.constants import DATE, HORAIRE, FESTIVAL, STYLE_FESTIVAL, VILLE, LIEU, PRIX, GENRE1, SPECTACLE1, ARTISTE1, \
    STYLE1, GENRE2, SPECTACLE2, ARTISTE2, STYLE2, GENRE3, SPECTACLE3, ARTISTE3, STYLE3, GENRE4, SPECTACLE4, ARTISTE4, \
    STYLE4, COLONNE_INFO
from biduleur.event_utils import parse_bidul_event

import logging  # Ajouter cet import

log = logging.getLogger(__name__)  # Obtenir le logger pour ce module

# -----------------------------
# Helpers format PRIX
# -----------------------------

_CURRENCY_MAP = {
    "€": "€", "eur": "€", "euro": "€",
    "$": "$", "usd": "$", "dollar": "$",
    "£": "£", "gbp": "£", "pound": "£",
    "chf": "CHF", "franc": "CHF",
}

_CURRENCY_COL_CANDIDATES = ("DEVISE", "CURRENCY", "MONNAIE")

# Nom de la colonne optionnelle pour désactiver des lignes
INACTIF_COLUMN = "INACTIF"

# Mapping mois français
MOIS_FR = {
    1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
    5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
    9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
}

# Jours de la semaine complets
JOURS_SEMAINE = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

REQUIRED_COLUMNS = [
    DATE, HORAIRE, FESTIVAL, STYLE_FESTIVAL, VILLE, LIEU, PRIX,
    GENRE1, SPECTACLE1, ARTISTE1, STYLE1,
    GENRE2, SPECTACLE2, ARTISTE2, STYLE2,
    GENRE3, SPECTACLE3, ARTISTE3, STYLE3,
    GENRE4, SPECTACLE4, ARTISTE4, STYLE4
]


def _canonical_currency_symbol(raw: Any) -> str:
    """
    Retourne un symbole canonique à partir d'un libellé devise (ex: 'EUR' -> '€').
    Par défaut retourne '€' si rien d'exploitable n'est fourni.
    """
    if raw is None:
        return "€"
    s = str(raw).strip().lower()
    return _CURRENCY_MAP.get(s, "€")


def _format_number_as_text_with_symbol(v: float, symbol: str) -> str:
    """
    Formate un nombre en texte + symbole. Supprime '.0' si entier.
    Exemple: 12.0 -> '12€', 12.5 -> '12.5€'
    (Si tu veux la virgule française, remplace le point par une virgule ici.)
    """
    try:
        f = float(v)
    except Exception:
        # Si non convertible, on le renvoie en str (dernier recours)
        return f"{v}"

    # entier ?
    if abs(f - round(f)) < 1e-9:
        return f"{int(round(f))}{symbol}"

    # sinon, on garde les décimales (sans zéros inutiles)
    txt = f"{f:.2f}".rstrip("0").rstrip(".")
    return f"{txt}{symbol}"


def _normalize_price_cell(value: Any, symbol_hint: str) -> str:
    """
    Normalise UNE cellule de PRIX en texte.
      - Si déjà string et contient un symbole monétaire, on renvoie tel quel (trim).
      - Si vide/None -> ''.
      - Si numérique -> format 'nombre + symbole' (par défaut, symbol_hint).
      - Si string '10' -> convertie en number -> '10€' etc.
    """
    if value is None:
        return ""

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return ""
        # Si déjà avec symbole (€ $ £ CHF) -> on préserve
        lowered = s.lower()
        if ("€" in s) or ("$" in s) or ("£" in s) or ("chf" in lowered) or ("eur" in lowered) or ("usd" in lowered) or (
                "gbp" in lowered):
            return s
        # Si c'est un nombre en texte -> on tente de convertir
        try:
            f = float(s.replace(",", "."))
            return _format_number_as_text_with_symbol(f, symbol_hint)
        except Exception:
            return s  # on laisse tel quel si non numérique

    # Numérique (int/float/Decimal)
    try:
        return _format_number_as_text_with_symbol(value, symbol_hint)
    except Exception:
        return f"{value}"


def _convert_price_column_to_text(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convertit la colonne PRIX (si présente) en texte, avec symbole de devise :
      - devise par défaut : €,
      - sinon, si une colonne 'DEVISE' / 'CURRENCY' / 'MONNAIE' est présente,
        on l'utilise pour déterminer un symbole par ligne.
    """
    if "PRIX" not in df.columns:
        return df

    # Détecte une éventuelle colonne de devise
    currency_col: Optional[str] = next((c for c in _CURRENCY_COL_CANDIDATES if c in df.columns), None)

    if currency_col:
        # Ligne à ligne, en tenant compte de la devise
        def _row_fmt(row: pd.Series) -> str:
            symbol = _canonical_currency_symbol(row.get(currency_col))
            return _normalize_price_cell(row["PRIX"], symbol)

        df["PRIX"] = df.apply(_row_fmt, axis=1)
    else:
        # Sans colonne devise : on force '€'
        df["PRIX"] = df["PRIX"].apply(lambda v: _normalize_price_cell(v, "€"))

    # S'assurer que c'est bien du texte (objet/str)
    df["PRIX"] = df["PRIX"].astype(str).fillna("")

    return df


def _filter_inactive_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtre les lignes où la colonne INACTIF vaut "n" (case insensitive).
    La colonne INACTIF est optionnelle - si elle n'existe pas, aucun filtrage n'est fait.

    Args:
        df: DataFrame à filtrer

    Returns:
        DataFrame filtré (sans les lignes inactives)
    """
    # Chercher la colonne INACTIF (case insensitive)
    inactif_col = None
    for col in df.columns:
        if col.upper() == INACTIF_COLUMN:
            inactif_col = col
            break

    if inactif_col is None:
        # Colonne non présente, pas de filtrage
        return df

    # Compter les lignes avant filtrage
    count_before = len(df)

    # Filtrer : garder les lignes où INACTIF n'est PAS "o" (case insensitive)
    # On convertit en string, strip, et compare en lowercase
    mask = df[inactif_col].apply(
        lambda x: str(x).strip().lower() != "o" if pd.notna(x) else True
    )
    df_filtered = df[mask]

    # Compter les lignes filtrées
    count_filtered = count_before - len(df_filtered)
    if count_filtered > 0:
        log.info(f"[INACTIF] {count_filtered} ligne(s) ignorée(s) (colonne '{inactif_col}' = 'o')")

    return df_filtered


# -----------------------------
# Parsing des dates
# -----------------------------

def _parse_date(date_str: Any) -> tuple[str, str]:
    """
    Parse une date et retourne (sort_key, display_date).

    Formats supportés:
    - ISO: "2014-08-31" -> ("2014-08-31", "Dimanche 31 août 2014")
    - Jour + numéro: "Samedi 3" -> ("03", "Samedi 3")
    - Jour + numéro + mois: "Lun 03 février" -> ("03", "Lun 03 février")

    Returns:
        (sort_key, display_date)
        - sort_key: clé de tri (date ISO complète ou jour paddé)
        - display_date: date formatée pour affichage
    """
    if not date_str or not isinstance(date_str, str):
        return ('', str(date_str) if date_str else '')

    date_str = str(date_str).strip()

    # Format ISO: 2014-08-31 ou 2014/08/31
    iso_match = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', date_str)
    if iso_match:
        year, month, day = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        try:
            dt = datetime(year, month, day)
            jour_semaine = JOURS_SEMAINE[dt.weekday()]
            mois_nom = MOIS_FR[month]
            # Format complet avec année: "Dimanche 31 août 2014"
            display = f"{jour_semaine} {day} {mois_nom} {year}"
            # Clé de tri: date ISO pour tri chronologique
            sort_key = f"{year:04d}-{month:02d}-{day:02d}"
            return (sort_key, display)
        except ValueError:
            return ('', date_str)

    # Format existant: "Samedi 3" ou "Sam 03 février"
    parts = date_str.split()
    if len(parts) >= 2:
        try:
            day = int(parts[1])
            # Clé de tri: jour paddé (comportement existant)
            return (str(day).zfill(2), date_str)
        except ValueError:
            pass

    return ('', date_str)


# -----------------------------
# Lecture + tri
# -----------------------------

def read_and_sort_file(filename: str) -> Optional[List[Dict]]:
    """
    Lit et trie un fichier (CSV, XLS, ou XLSX).
    Args:
        filename (str): Chemin du fichier d'entrée.
    Returns:
        Optional[List[Dict]]: Liste des enregistrements triés ou None en cas d'erreur.
    """
    try:
        file_extension = os.path.splitext(filename)[1].lower()

        # Lecture du fichier avec gestion d'erreur spécifique
        try:
            if file_extension in ['.csv']:
                df = pd.read_csv(filename, encoding='utf8', keep_default_na=False, na_values=[''])
            elif file_extension in ['.xls', '.xlsx']:
                df = pd.read_excel(filename, keep_default_na=False, na_values=[''])
            else:
                raise ValueError(
                    f"Format de fichier non supporté : {file_extension}\n\nFormats acceptés : .csv, .xls, .xlsx")
        except Exception as read_error:
            # Transformer les erreurs de lecture en messages clairs
            error_msg = str(read_error).lower()
            if "format cannot be determined" in error_msg or "corrupt" in error_msg:
                raise ValueError(
                    f"Le fichier Excel est corrompu ou illisible.\n\n"
                    f"Solutions :\n"
                    f"• Ouvrir le fichier dans Excel et l'enregistrer à nouveau\n"
                    f"• Exporter en CSV depuis Excel\n"
                    f"• Vérifier que le fichier n'est pas vide"
                )
            elif "permission" in error_msg or "access" in error_msg:
                raise ValueError(
                    f"Impossible d'accéder au fichier.\n\n"
                    f"Assurez-vous que :\n"
                    f"• Le fichier n'est pas ouvert dans Excel\n"
                    f"• Vous avez les droits de lecture"
                )
            else:
                raise ValueError(f"Erreur lors de la lecture du fichier :\n\n{read_error}")

        # Validation des colonnes obligatoires
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(
                f"Colonnes manquantes dans le fichier :\n\n" +
                "\n".join(f"• {col}" for col in missing_cols)
            )

        # --- Filtrage des lignes inactives ---
        df = _filter_inactive_rows(df)

        # --- Conversion PRIX -> texte avec devise ---
        df = _convert_price_column_to_text(df)

        # Remplace NaN par None pour la suite
        df = df.where(pd.notnull(df), None)

        # Parser les dates: extraire clé de tri + normaliser pour affichage
        parsed = df[DATE].apply(_parse_date)
        df['Day'] = parsed.apply(lambda x: x[0])  # Clé de tri (date ISO ou jour)
        df[DATE] = parsed.apply(lambda x: x[1])   # Date formatée pour affichage

        # Tri personnalisé : 'En Bref' (COLONNE_INFO) passe à la fin
        df['info_last'] = df[DATE].apply(lambda x: 0 if x == COLONNE_INFO else 1)
        df_sorted = df.sort_values(by=['info_last', 'Day', GENRE1, HORAIRE])
        df_sorted = df_sorted.drop(columns=['info_last'])

        return df_sorted.to_dict('records')
    except ValueError:
        # Re-lever les erreurs de validation pour qu'elles remontent
        raise
    except Exception as e:
        log.error(f"Error sorting the file: {e}. Ensure each line has a defined date.")
        return None


# -----------------------------
# Pipeline haut niveau
# -----------------------------

def parse_bidul(filename: str) -> tuple:
    """
    Traite le fichier d'entrée (CSV, XLS, ou XLSX) et génère les données nécessaires.
    Args:
        filename (str): Chemin du fichier d'entrée.
    Returns:
        tuple: (html_body_bidul, html_body_agenda, number_of_lines)
    """
    body_content = ''
    body_content_agenda = ''
    sorted_events = read_and_sort_file(filename)
    if sorted_events is None:
        return body_content, body_content_agenda, 0

    current_date = None
    number_of_lines = 0

    for row in sorted_events:
        # strip des chaînes
        row = {key: (value.strip() if isinstance(value, str) else value) for key, value in row.items()}

        formatted_line_bidul, formatted_line_agenda, formatted_line_post, current_date = parse_bidul_event(
            row, current_date
        )
        body_content += formatted_line_bidul + "\n\n"
        body_content_agenda += formatted_line_agenda + "\n\n"
        number_of_lines += 1

    return body_content, body_content_agenda, number_of_lines
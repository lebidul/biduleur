import os
from typing import List, Dict, Optional, Any

import pandas as pd

from biduleur.constants import DATE, GENRE1, HORAIRE, COLONNE_INFO
from biduleur.event_utils import parse_bidul_event

import logging # Ajouter cet import
log = logging.getLogger(__name__) # Obtenir le logger pour ce module


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
        if ("€" in s) or ("$" in s) or ("£" in s) or ("chf" in lowered) or ("eur" in lowered) or ("usd" in lowered) or ("gbp" in lowered):
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
        # Détermine le type de fichier en fonction de l'extension
        file_extension = os.path.splitext(filename)[1].lower()

        if file_extension in ['.csv']:
            df = pd.read_csv(filename, encoding='utf8', keep_default_na=False, na_values=[''])
        elif file_extension in ['.xls', '.xlsx']:
            df = pd.read_excel(filename, keep_default_na=False, na_values=[''])
        else:
            raise ValueError(f"Format de fichier non supporté : {file_extension}")

        # --- Conversion PRIX -> texte avec devise ---
        df = _convert_price_column_to_text(df)

        # Remplace NaN par None pour la suite
        df = df.where(pd.notnull(df), None)

        # Extrait 'Day' (ex: "Lun 03 ..." -> "03")
        df['Day'] = df[DATE].apply(lambda x: x.split()[1].zfill(2) if x else None)

        # Tri personnalisé : 'En Bref' (COLONNE_INFO) passe à la fin
        df['sort_key'] = df[DATE].apply(lambda x: 0 if x == COLONNE_INFO else 1)
        df_sorted = df.sort_values(by=['sort_key', 'Day', GENRE1, HORAIRE])
        df_sorted = df_sorted.drop(columns=['sort_key'])

        return df_sorted.to_dict('records')
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

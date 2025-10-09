# publisher/gsheet_client.py

import gspread
import os
import locale
from datetime import datetime
import pandas as pd

# Le chemin du fichier de credentials sera créé par le workflow GitHub Actions ou existera localement
GCP_CREDS_PATH = 'gcp_creds.json'


def get_entries_for_date(target_date_str=None):
    """
    Se connecte à Google Sheets et retourne toutes les lignes correspondant à une date donnée.
    La recherche se base sur un format "Jour JJ" (ex: "Lundi 22").

    Args:
        target_date_str (str, optional): La date cible au format "JJ/MM/AAAA".
                                         Si None, la date du jour est utilisée.

    Returns:
        list[dict]: Une liste de dictionnaires représentant les lignes trouvées.
    """
    # --- 1. Configuration de la locale en français ---
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'French_France.1252')
        except locale.Error:
            raise RuntimeError("La locale française n'est pas installée sur le système.")

    # --- 2. Détermination de l'objet date à utiliser ---
    if target_date_str:
        try:
            date_object = datetime.strptime(target_date_str, "%d/%m/%Y")
        except ValueError:
            raise ValueError(f"Le format de date '{target_date_str}' est invalide. Utilisez JJ/MM/AAAA.")
    else:
        date_object = datetime.now()

    # --- 3. Génération des chaînes de recherche à partir de l'objet date ---
    # Chaîne pour trouver la ligne (ex: "Lundi 22")
    search_string = f"{date_object.strftime('%A').capitalize()} {date_object.day}"

    # NOUVELLE LIGNE : Construction du nom de fichier selon le format spécifique
    # %Y -> Année (2025)
    # %m -> Mois en chiffre (10)
    # %B -> Nom du mois en toutes lettres (Octobre)
    sheet_name = (
        f"{date_object.strftime('%Y%m')}_tapage_biduleur_"
        f"{date_object.strftime('%B').capitalize()}_{date_object.strftime('%Y')}"
    )

    print(f"Recherche des entrées pour '{search_string}' dans la feuille '{sheet_name}'...")

    # --- 4. Connexion et récupération des données ---
    gc = gspread.service_account(filename=GCP_CREDS_PATH)
    try:
        spreadsheet = gc.open(sheet_name)

        # --- Ouvrir l'onglet par son nom spécifique ---
        worksheet = spreadsheet.worksheet("lebiduleur")

    except gspread.SpreadsheetNotFound:
        # Cette erreur est maintenant uniquement due à un fichier non trouvé ou non partagé
        raise Exception(
            f"La feuille de calcul '{sheet_name}' n'a pas été trouvée OU n'a pas été partagée avec le compte de service.")
    except gspread.WorksheetNotFound:
        # Erreur si l'onglet "lebiduleur" n'existe pas dans le fichier
        raise Exception(f"L'onglet 'lebiduleur' n'a pas été trouvé dans la feuille de calcul '{sheet_name}'.")

    all_records = worksheet.get_all_records()

    # --- Utiliser le bon nom de colonne pour le filtrage ---
    COLUMN_HEADER_FOR_DATE = "DATE"
    matching_rows = [row for row in all_records if row.get(COLUMN_HEADER_FOR_DATE) == search_string]

    if not matching_rows:
        print(
            f"Avertissement : Aucune entrée trouvée pour '{search_string}' dans la colonne '{COLUMN_HEADER_FOR_DATE}'.")

    df = pd.DataFrame(matching_rows)

    return df
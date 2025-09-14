import os
import pandas as pd
import numpy as np

# Dossier contenant les fichiers CSV d'entrée
dossier_entree = "C:\\Users\\thiba\\repos\\bidul.biduleur\\biduleur\\tapages\\toBeConverted"

# Header de sortie
header_sortie = [
    "FESTOCHE\nEVENEMENT ", "STYLE \nFESTOCHE / EVENEMENT ",
    "DATE", "HEURE", "LIEU", "VILLE", "PRIX",
    "GENRE 1", "NOM SPECTACLE 1 ( SV )", "COMPAGNIE 1 ( SV ) ou\nGROUPE 1 / ARTISTE 1 ( C )", "STYLE \nSPECTACLE 1 (SV) / CONCERT 1 (C)",
    "GENRE 2", "NOM SPECTACLE 2 ( SV )", "COMPAGNIE 2 ( SV ) ou\nGROUPE 2 / ARTISTE 2 ( C )", "STYLE \nSPECTACLE 2 ( SV ) / CONCERT 2 ( C )",
    "GENRE 3", "NOM SPECTACLE 3 ( SV )", "COMPAGNIE 3 ( SV ) ou\nGROUPE 3 / ARTISTE 3 ( C )", "STYLE \nSPECTACLE 3 ( SV ) / CONCERT 3 ( C )",
    "GENRE 4", "NOM SPECTACLE 4 ( SV )", "COMPAGNIE 4 ( SV ) ou\nGROUPE 4 / ARTISTE 4 ( C )", "STYLE \nSPECTACLE 4 ( SV ) / CONCERT 4 ( C )",
    "LIEN1", "LIEN2", "LIEN3", "LIEN4"
]

# Correspondance des colonnes
correspondance = {
    "initiales": "INFO TAPEUR",
    "date": "DATE",
    "horaire": "HEURE",
    "festival": "FESTOCHE\nEVENEMENT ",
    "style_festival": "STYLE \nFESTOCHE / EVENEMENT ",
    "lieu": "LIEU",
    "ville": "VILLE",
    "prix": "PRIX",
    "genre": "GENRE 1",
    "spectacle1": "NOM SPECTACLE 1 ( SV )",
    "artiste1": "COMPAGNIE 1 ( SV ) ou\nGROUPE 1 / ARTISTE 1 ( C )",
    "style1": "STYLE \nSPECTACLE 1 (SV) / CONCERT 1 (C)",
    "spectacle2": "NOM SPECTACLE 2 ( SV )",
    "artiste2": "COMPAGNIE 2 ( SV ) ou\nGROUPE 2 / ARTISTE 2 ( C )",
    "style2": "STYLE \nSPECTACLE 2 ( SV ) / CONCERT 2 ( C )",
    "spectacle3": "NOM SPECTACLE 3 ( SV )",
    "artiste3": "COMPAGNIE 3 ( SV ) ou\nGROUPE 3 / ARTISTE 3 ( C )",
    "style3": "STYLE \nSPECTACLE 3 ( SV ) / CONCERT 3 ( C )",
    "spectacle4": "NOM SPECTACLE 4 ( SV )",
    "artiste4": "COMPAGNIE 4 ( SV ) ou\nGROUPE 4 / ARTISTE 4 ( C )",
    "style4": "STYLE \nSPECTACLE 4 ( SV ) / CONCERT 4 ( C )",
    "lien1": "LIEN1",
    "lien2": "LIEN2",
    "lien3": "LIEN3",
    "lien4": "LIEN4"
}

# Créer le dossier outputs s'il n'existe pas
dossier_sortie = os.path.join(dossier_entree, "outputs")
os.makedirs(dossier_sortie, exist_ok=True)

# Liste des encodages à essayer
encodings = ['utf-8', 'iso-8859-1', 'windows-1252', 'latin1']

# Parcourir tous les fichiers CSV du dossier d'entrée
for fichier in os.listdir(dossier_entree):
    if fichier.endswith(".csv"):
        chemin_entree = os.path.join(dossier_entree, fichier)
        df = None
        encoding_used = None

        # Essayer différents encodages
        for encoding in encodings:
            try:
                df = pd.read_csv(chemin_entree, encoding=encoding)
                encoding_used = encoding
                break
            except UnicodeDecodeError:
                continue

        if df is None:
            print(f"Impossible de lire le fichier {fichier} avec les encodages testés.")
            continue

        print(f"Fichier: {fichier} (encodage: {encoding_used})")
        colonnes_non_renommees = [col for col in df.columns if col not in correspondance.keys()]
        if colonnes_non_renommees:
            print("Colonnes non renommées (non présentes dans la correspondance) :")
            print(colonnes_non_renommees)
        print("---")

        # Renommer les colonnes selon la correspondance (seulement si elles existent)
        df = df.rename(columns={k: v for k, v in correspondance.items() if k in df.columns})

        # Ajouter les colonnes manquantes avec des valeurs vides
        for col in header_sortie:
            if col not in df.columns:
                df[col] = np.nan

        # Remplacer les NaN par None
        df = df.where(pd.notnull(df), None)

        # Logique pour GENRE 2, GENRE 3, GENRE 4
        if "GENRE 1" in df.columns:
            # GENRE 2 = GENRE 1 si au moins une des colonnes suivantes n'est pas None
            colonnes_spectacle_2 = [
                "NOM SPECTACLE 2 ( SV )",
                "COMPAGNIE 2 ( SV ) ou\nGROUPE 2 / ARTISTE 2 ( C )",
                "STYLE \nSPECTACLE 2 ( SV ) / CONCERT 2 ( C )"
            ]
            mask_spectacle_2 = df[colonnes_spectacle_2].notna().any(axis=1)
            df.loc[mask_spectacle_2, "GENRE 2"] = df.loc[mask_spectacle_2, "GENRE 1"]

            # GENRE 3 = GENRE 1 si au moins une des colonnes suivantes n'est pas None
            colonnes_spectacle_3 = [
                "NOM SPECTACLE 3 ( SV )",
                "COMPAGNIE 3 ( SV ) ou\nGROUPE 3 / ARTISTE 3 ( C )",
                "STYLE \nSPECTACLE 3 ( SV ) / CONCERT 3 ( C )"
            ]
            mask_spectacle_3 = df[colonnes_spectacle_3].notna().any(axis=1)
            df.loc[mask_spectacle_3, "GENRE 3"] = df.loc[mask_spectacle_3, "GENRE 1"]

            # GENRE 4 = GENRE 1 si au moins une des colonnes suivantes n'est pas None
            colonnes_spectacle_4 = [
                "NOM SPECTACLE 4 ( SV )",
                "COMPAGNIE 4 ( SV ) ou\nGROUPE 4 / ARTISTE 4 ( C )",
                "STYLE \nSPECTACLE 4 ( SV ) / CONCERT 4 ( C )"
            ]
            mask_spectacle_4 = df[colonnes_spectacle_4].notna().any(axis=1)
            df.loc[mask_spectacle_4, "GENRE 4"] = df.loc[mask_spectacle_4, "GENRE 1"]

        # Réorganiser les colonnes selon header_sortie
        df = df[header_sortie]

        # Construire le chemin de sortie
        nom_sortie = fichier.replace(".csv", ".new.csv")
        chemin_sortie = os.path.join(dossier_sortie, nom_sortie)

        # Sauvegarder le fichier converti
        df.to_csv(chemin_sortie, index=False, encoding='utf-8-sig')

print(f"Conversion terminée. Les fichiers convertis sont dans : {dossier_sortie}")

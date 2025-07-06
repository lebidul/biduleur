
import os
import re
import pandas as pd

# === CONFIGURATION ===
TXT_ROOT_DIR = "./archives_txt/"
RESULTS_CSV_PATH = "./evenements_extraits.csv"

# === PATTERNS DE DÉTECTION ===
DATE_PATTERN = re.compile(r"^\s*(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}", re.IGNORECASE)
HEURE_PATTERN = re.compile(r"\b\d{1,2}h(\d{2})?\b")
TITRE_PATTERN = re.compile(r"[«\"](.*?)[»\"]")
TYPE_PATTERN = re.compile(r"\((.*?)\)")
PRIX_PATTERN = re.compile(r"(\d+[€]|au chapeau|prix libre|entrée libre)", re.IGNORECASE)

# === EXTRACTION ===

evenements = []

for dirpath, _, filenames in os.walk(TXT_ROOT_DIR):
    for filename in filenames:
        if not filename.endswith(".txt"):
            continue

        current_date = None
        file_path = os.path.join(dirpath, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if DATE_PATTERN.match(line):
                    current_date = line
                    continue

                if line.startswith("") or line.startswith("") or line.startswith("-") or line.startswith("•"):
                    heure = HEURE_PATTERN.search(line)
                    titre = TITRE_PATTERN.search(line)
                    type_evt = TYPE_PATTERN.search(line)
                    prix = PRIX_PATTERN.findall(line)

                    cleaned = re.sub(r"[«»\\"()]", "", line)
                    main_part = re.split(r"\d{1,2}h.*", cleaned)[0]

                    evenements.append({
                        "source": filename,
                        "date": current_date,
                        "heure": heure.group(0) if heure else None,
                        "titre_spectacle": titre.group(1) if titre else None,
                        "type": type_evt.group(1) if type_evt else None,
                        "prix": ", ".join(prix) if prix else None,
                        "description": line,
                        "artiste_et_lieu": main_part.strip()
                    })

# Sauvegarde du CSV
df = pd.DataFrame(evenements)
df.to_csv(RESULTS_CSV_PATH, index=False, encoding="utf-8")
print(f"✅ Analyse terminée. Résultats enregistrés dans : {RESULTS_CSV_PATH}")

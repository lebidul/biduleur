from modules import csv_parser, ocr_parser, fusionner, corrections_regles
import pandas as pd

if __name__ == "__main__":
    df_ocr = ocr_parser.parse_ocr_folder("./archives.txt/")
    import os
    csv_dir = "./csv/"
    all_csv = []
    for file in os.listdir(csv_dir):
        if file.endswith(".csv"):
            path = os.path.join(csv_dir, file)
            df = csv_parser.parse_csv(path)
            all_csv.append(df)
    df_csv = pd.concat(all_csv, ignore_index=True)
    df_fusion = fusionner.fusionner_corpus(df_ocr, df_csv)
    df_corrige = corrections_regles.appliquer_corrections(df_fusion)
    df_corrige.to_csv("corpus_final_avec_corrections.csv", index=False, encoding="utf-8")
    print("✅ Corpus final généré avec corrections :", len(df_corrige), "lignes.")

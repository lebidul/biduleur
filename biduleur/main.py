import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from biduleur.csv_utils import parse_bidul
from biduleur.format_utils import output_html_file
import importlib.resources as res
from tkinter import ttk
import traceback

def run_biduleur(input_file, bidul_output_file=None, agenda_output_file=None):
    """
    Traite le fichier CSV et génère les fichiers HTML.

    Args:
        input_file (str): Chemin du fichier CSV ou XLS XLSX d'entrée.
        bidul_output_file (str, optional): Chemin du fichier de sortie pour Bidul. Par défaut, basé sur input_file.
        agenda_output_file (str, optional): Chemin du fichier de sortie pour Agenda. Par défaut, basé sur input_file.
    """
    try:
    # Génère les chemins par défaut si non fournis
        if not bidul_output_file or not agenda_output_file:
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_dir = os.path.dirname(input_file)
            bidul_output_file = os.path.basename(input_file) + ".html"
            agenda_output_file = os.path.basename(input_file) + ".agenda.html"

        html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(input_file)
        output_html_file(html_body_bidul, original_file_name=input_file, output_filename=bidul_output_file)
        output_html_file(html_body_agenda, original_file_name=input_file, output_filename=agenda_output_file)

        print(f"Fichiers générés avec succès :")
        print(f"- {os.path.basename(bidul_output_file)}")
        print(f"- {os.path.basename(agenda_output_file)}")
        print(f"Nombre d'événements créés : {number_of_lines}")

        return True, number_of_lines
    except Exception as e:
        print(traceback.format_exc())
        print(f"Erreur : {str(e)}")
        return False, str(e)

def gui_mode():
    """Mode graphique pour les utilisateurs non-techniques."""

    def select_input_file():
        file_path = filedialog.askopenfilename(
            title="Sélectionner le fichier d'entrée",
            filetypes=[
                ("Fichiers Excel", "*.xls;*.xlsx"),
                ("Fichiers CSV", "*.csv"),
                ("Tous les fichiers", "*.*")
            ]
        )
        if file_path:
            input_entry.delete(0, tk.END)
            input_entry.insert(0, file_path)
            update_default_output_paths(file_path)

    def save_embedded_template(package, filename, title):
        try:
            # Demande où enregistrer
            initial_ext = os.path.splitext(filename)[1].lower()
            if initial_ext == '.csv':
                ftypes = [("CSV", "*.csv")]
            elif initial_ext == '.xlsx':
                ftypes = [("Excel (XLSX)", "*.xlsx")]
            else:
                ftypes = [("Tous les fichiers", "*.*")]

            target = filedialog.asksaveasfilename(
                title=title,
                defaultextension=initial_ext,
                filetypes=ftypes,
                initialfile=filename
            )
            if not target:
                return

            # Lit les octets du fichier embarqué et écrit sur disque
            data = res.files(package).joinpath(filename).read_bytes()
            with open(target, "wb") as f:
                f.write(data)
            messagebox.showinfo("Modèle enregistré", f"Fichier enregistré ici :\n{target}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer le modèle : {e}")

    def update_default_output_paths(input_file):
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        default_bidul_output = os.path.join(os.path.dirname(input_file), f"{base_name}.html")
        default_agenda_output = os.path.join(os.path.dirname(input_file), f"{base_name}.agenda.html")

        bidul_output_entry.delete(0, tk.END)
        bidul_output_entry.insert(0, default_bidul_output)

        agenda_output_entry.delete(0, tk.END)
        agenda_output_entry.insert(0, default_agenda_output)

    def select_output_file(entry):
        file_path = filedialog.asksaveasfilename(
            title="Enregistrer le fichier de sortie",
            defaultextension=".html",
            filetypes=[("Fichiers HTML", "*.html"), ("Tous les fichiers", "*.*")]
        )
        if file_path:
            entry.delete(0, tk.END)
            entry.insert(0, file_path)

    def run_from_gui():
        input_file = input_entry.get()
        bidul_output_file = bidul_output_entry.get()
        agenda_output_file = agenda_output_entry.get()

        if not input_file:
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier tapageur (.csv,.xls,.xlsx) d'entrée.")
            return

        success, result = run_biduleur(input_file, bidul_output_file, agenda_output_file)
        if success:
            messagebox.showinfo(
                "Succès",
                f"Fichiers générés avec succès :\n\n"
                f"- {os.path.basename(bidul_output_file)}\n"
                f"- {os.path.basename(agenda_output_file)}\n\n"
                f"Nombre d'événements : {result}"
            )
        else:
            messagebox.showerror("Erreur", f"Une erreur est survenue : {result}")

    # --- Interface Graphique ---
    root = tk.Tk()
    root.title("Biduleur - Générateur de fichiers .html pour le bidul pdf (via publisher) et l'agenda en ligne. aka la moulinette")

    # Configure les colonnes et lignes pour qu'elles s'étirent
    root.columnconfigure(1, weight=1)  # La colonne 1 (champs Entry) s'étire
    root.rowconfigure(4, weight=1)     # Ajoute une ligne vide en bas pour permettre l'expansion verticale

    # Fichier d'entrée
    tk.Label(root, text="Fichier tapageur d'entrée (.csv,.xls,.xlsx) :").grid(row=0, column=0, padx=5, pady=5, sticky="e")
    input_entry = tk.Entry(root)
    input_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")  # sticky="ew" pour étirer horizontalement
    tk.Button(root, text="Parcourir...", command=select_input_file).grid(row=0, column=2, padx=5, pady=5)

    # Fichier de sortie pour Bidul
    tk.Label(root, text="Fichier de sortie (Bidul) :").grid(row=1, column=0, padx=5, pady=5, sticky="e")
    bidul_output_entry = tk.Entry(root)
    bidul_output_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    tk.Button(root, text="Parcourir...", command=lambda: select_output_file(bidul_output_entry)).grid(row=1, column=2, padx=5, pady=5)

    # Fichier de sortie pour Agenda
    tk.Label(root, text="Fichier de sortie (Agenda) :").grid(row=2, column=0, padx=5, pady=5, sticky="e")
    agenda_output_entry = tk.Entry(root)
    agenda_output_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    tk.Button(root, text="Parcourir...", command=lambda: select_output_file(agenda_output_entry)).grid(row=2, column=2, padx=5, pady=5)

    # Bouton pour lancer le traitement
    tk.Button(
        root,
        text="Générer les fichiers",
        command=run_from_gui,
        bg="#4CAF50",
        fg="white",
        font=("Arial", 10, "bold")
    ).grid(row=3, column=1, pady=15)

    # Barre de statut
    status_bar = tk.Label(root, text="Prêt", bd=1, relief=tk.SUNKEN, anchor=tk.W)
    status_bar.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

    # --- Bandeau modèles à télécharger ---
    sep = ttk.Separator(root, orient='horizontal')
    sep.grid(row=5, column=0, columnspan=3, sticky="ew", padx=5, pady=(10, 5))

    models_frame = tk.Frame(root)
    models_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,10))
    tk.Label(models_frame, text="Télécharger un modèle de fichier :", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0,6))

    tk.Button(
        models_frame,
        text="Modèle CSV",
        command=lambda: save_embedded_template('biduleur.templates', 'tapage_template.csv', "Enregistrer le modèle CSV")
    ).grid(row=1, column=0, padx=(0,8))

    tk.Button(
        models_frame,
        text="Modèle XLSX",
        command=lambda: save_embedded_template('biduleur.templates', 'tapage_template.xlsx', "Enregistrer le modèle XLSX")
    ).grid(row=1, column=1, padx=(0,8))

    root.mainloop()

def cli_mode():
    """Mode ligne de commande pour l'IDE."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <fichier_entrée> [fichier_sortie_bidul] [fichier_sortie_agenda]")
        print("Types de fichiers supportés : CSV, XLS, XLSX")
        sys.exit(1)
    input_file = sys.argv[1]
    bidul_output_file = sys.argv[2] if len(sys.argv) > 2 else None
    agenda_output_file = sys.argv[3] if len(sys.argv) > 3 else None
    success, result = run_biduleur(input_file, bidul_output_file, agenda_output_file)
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    # Détecte si des arguments sont passés (mode IDE) ou non (mode graphique)
    if len(sys.argv) > 1:
        cli_mode()
    else:
        gui_mode()
    # # filename1 = './tapages/Copy of 202509_tapage_biduleur_Septembre_2025.xls.xlsx'
    # filename1 = 'C:\\Users\\thiba\\repos\\bidul.biduleur\\biduleur\\tapages\\toBeConverted\\outputs\\202301_tapage_biduleur_janvier_2023.new.csv'
    # run_biduleur(filename1)
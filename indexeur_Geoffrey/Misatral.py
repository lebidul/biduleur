import os
import requests
import base64
import json

def process_image(image_path, api_key):
    """
    Traite une image pour en extraire le texte structuré en utilisant l'API d'OCR de Mistral.
    """
    # 1. Définir le chemin vers le fichier de la requête
    prompt_filepath = "prompt_mistral.txt"

    # 2. Lire le contenu du fichier de requête
    try:
        with open(prompt_filepath, 'r', encoding='utf-8') as f:
            prompt_text = f.read().strip()
    except FileNotFoundError:
        print(f"Erreur: Le fichier de requête '{prompt_filepath}' est introuvable.")
        return None
    
    try:
        # Lire l'image en base64
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # Demander à l'API de retourner les informations au format CSV
        payload = {
            "model": "mistral-large-latest",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_string}"
                            }
                        },
                        {
                            "type": "text",
                            # 3. Utiliser la requête lue depuis le fichier
                            "text": prompt_text 
                        }
                    ]
                }
            ]
        }

        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        result = response.json()['choices'][0]['message']['content']
        return result

    except requests.exceptions.HTTPError as err:
        print(f"Erreur HTTP lors du traitement de {image_path}: {err}")
        return None
    except Exception as e:
        print(f"Une erreur s'est produite lors du traitement de {image_path}: {e}")
        return None

def traiter_images_decoupees_via_mistral(input_folder):
    """
    Parcourt un dossier d'images, les traite via l'API Mistral et crée un fichier CSV.
    
    :param input_folder: Le chemin vers le dossier contenant les images à analyser.
    """
    # Nom du fichier CSV de sortie, défini à l'intérieur de la fonction
    output_filename = "csv/evenements_mistral.csv"

    # Vérifier l'existence de la clé API
    api_key = os.environ.get("MISTRAL_API_KEY")
    api_key = "1UALBtIGHPGTijdBecQeA00b7E3Gejnh" # TODO: Retirer cette ligne pour la production
    if not api_key:
        print("Erreur: La variable d'environnement MISTRAL_API_KEY n'est pas définie.")
        return

    # En-têtes du CSV
    csv_header = "jour;date;artiste;style_musical;lieu;ville;heure;tarif;autre\n"
    all_events_csv = csv_header

    # Parcourir le dossier
    print(f"Début de l'analyse du dossier : {input_folder}")
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            image_path = os.path.join(input_folder, filename)
            print(f"Traitement de l'image: {image_path}")

            csv_data = process_image(image_path, api_key)
            if csv_data:
                # Ajouter les données extraites à la chaîne principale
                all_events_csv += csv_data.strip() + "\n"

    # Écrire le résultat final dans un fichier
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(all_events_csv)

    print(f"Opération terminée. Les résultats ont été enregistrés dans {output_filename}")


if __name__ == "__main__":
    # Définition des variables pour simuler l'appel demandé
    DOSSIER_A_ANALYSER = "temporaire"
    SOUS_DOSSIER = "images_converties"
    
    # Construction du chemin complet à partir des variables
    # C'est ce chemin qui sera passé en paramètre
    chemin_des_images = os.path.join(DOSSIER_A_ANALYSER, SOUS_DOSSIER)

    # Crée les dossiers de test s'ils n'existent pas pour permettre l'exécution
    if not os.path.exists(chemin_des_images):
        os.makedirs(chemin_des_images)
        print(f"Le dossier '{chemin_des_images}' a été créé. Placez vos images dedans.")
    else:
        # Appel de la fonction principale avec le chemin construit
        traiter_images_decoupees_via_mistral(chemin_des_images)
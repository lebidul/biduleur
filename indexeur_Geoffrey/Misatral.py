import os
import base64
import json
import requests

def traiter_images_decoupees_via_mistral(folder_path, prompt_filepath="prompt_mistral_9.txt"):
    """
    Parcourt un dossier, prend toutes les images .jpg et les envoie à l'API Mistral
    en une seule requête pour en extraire le texte structuré.
    """
    
    api_key = "1UALBtIGHPGTijdBecQeA00b7E3Gejnh" # TODO: Retirer cette ligne pour la production


    # Vérifier l'existence du prompt
    if not os.path.exists(prompt_filepath):
        print(f"❌ Erreur: Le fichier de requête '{prompt_filepath}' est introuvable.")
        return None

    with open(prompt_filepath, 'r', encoding='utf-8') as f:
        prompt_text = f.read().strip()

    # Récupérer toutes les images .png du dossier
    image_paths = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(".png")]

    if not image_paths:
        print(f"⚠️ Aucune image .png trouvée dans le dossier : {folder_path}")
        return None

    try:
        # Préparer les messages avec toutes les images
        messages = []
        for image_path in image_paths:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                messages.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_string}"
                    }
                })

        # Ajouter le prompt text à la fin
        messages.append({
            "type": "text",
            "text": prompt_text
        })

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": "mistral-large-latest",
            "messages": [
                {
                    "role": "user",
                    "content": messages
                }
            ]
        }

        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload)
        )
        response.raise_for_status()

        result = response.json()["choices"][0]["message"]["content"]
        return result

    except Exception as e:
        print(f"❌ Erreur lors de l'appel API Mistral : {e}")
        return None

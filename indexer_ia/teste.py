import requests

API_KEY = "ta_clé_api_ici"  # remplace ceci par ta clé

headers = {
    "Authorization": f"Bearer 1UALBtIGHPGTijdBecQeA00b7E3Gejnh",
    "Content-Type": "application/json"
}

# Exemple de payload OCR, image fictive ici
payload = {
    "model": "mistral-ocr-latest",
    "document": {
        "type": "image_url",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Example.svg/1200px-Example.svg.png"
    },
    "include_image_base64": True
}

try:
    response = requests.post("https://api.mistral.ai/v1/ocr", headers=headers, json=payload)
    print("Status code:", response.status_code)
    print("Response:", response.json())
except Exception as e:
    print("Erreur pendant la requête:", e)

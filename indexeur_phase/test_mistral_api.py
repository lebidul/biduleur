import requests
import json
import os
from flask import Flask, send_from_directory, jsonify
import threading

# app = Flask(__name__)

API_KEY = "1UALBtIGHPGTijdBecQeA00b7E3Gejnh"
API_URL = "https://api.mistral.ai/ocr/v1/process"
API_URL = "https://api.mistral.ai/v1/ocr"
PDF_INPUT_DIR = "./samples_pdfs/"


# @app.route('/files/<path:filename>', methods=['GET'])
# def serve_file(filename):
#     """Serve un fichier local."""
#     try:
#         return send_from_directory(PDF_INPUT_DIR, filename, as_attachment=False)
#     except FileNotFoundError:
#         return jsonify({"error": "File not found"}), 404
#
# def start_flask_app():
#     """Démarre le serveur Flask dans un thread séparé."""
#     app.run(port=5000, debug=True, use_reloader=False)
#
# # Démarrer le serveur Flask dans un thread séparé
# flask_thread = threading.Thread(target=start_flask_app)
# flask_thread.daemon = True
# flask_thread.start()

# def get_local_file_url(filename):
#     """Retourne l'URL locale pour accéder au fichier via le serveur Flask."""
#     return f"http://127.0.0.1:5000/files/{filename}"

for file in ["https://drive.google.com/uc?export=download&id=10JtMTlAqRM7DkQo6GXrmXwy5dphPC53k",
             "https://drive.google.com/uc?export=download&id=1TEu4V257BGRAwjhMo40iMfTzMTWVXs_E"]:

    print(f"path: {file}")

    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }

    payload = {
        "model": "mistral-ocr-latest",
        "document": {
            "type": "document_url",
            "document_url": f"{file}"
        },
        "include_image_base64": True
    }

    # Vérifiez le format JSON
    try:
        json_payload = json.dumps(payload)
    except json.JSONDecodeError as e:
        print("Erreur de format JSON:", e)
        break

    response = requests.post(
        API_URL,
        json=payload,
        headers=headers
    )


    if response.status_code == 200:
        # Extract code examples with formatting preserved
        for i in response.json()["pages"]:
            print(f'page markdown:\n {i["markdown"]}')
    else:
        print("Error:", response.status_code, response.text)
        response.raise_for_status()


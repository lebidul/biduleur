from instagrapi import Client
import os
import time

SESSION_FILE = "instagram_session.json"


def upload_photo(image_path, caption):
    """
    Se connecte à Instagram et publie une photo avec une légende.
    Gère la session pour éviter les reconnexions fréquentes.
    """
    cl = Client()

    username = os.environ["INSTAGRAM_USERNAME"]
    password = os.environ["INSTAGRAM_PASSWORD"]

    # Tente de réutiliser une session existante pour paraître plus légitime
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
        cl.login(username, password)
    else:
        cl.login(username, password)
        cl.dump_settings(SESSION_FILE)

    print("Connexion à Instagram réussie.")

    # Ajoute un délai aléatoire pour simuler un comportement humain
    time.sleep(5)

    try:
        cl.photo_upload(path=image_path, caption=caption)
        print(f"Photo '{image_path}' publiée avec succès sur Instagram.")
    except Exception as e:
        raise Exception(f"Échec de la publication sur Instagram : {e}")

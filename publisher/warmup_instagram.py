# warmup_instagram.py (NOUVELLE VERSION)

import os
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

SESSION_FILE = "instagram_session.json"

cl = Client()

# On ne demande plus le mot de passe !
session_id = input("Veuillez coller la valeur du cookie 'sessionid' de votre navigateur : ").strip()

if not session_id:
    print("Le sessionid ne peut pas être vide.")
else:
    try:
        # On injecte le cookie de session dans le client
        cl.sessionid = session_id
        # On force le client à se "synchroniser" avec cette nouvelle session
        cl.get_timeline_feed()

        # Sauvegarde les réglages (qui incluent maintenant la session valide)
        cl.dump_settings(SESSION_FILE)

        print("\n-------------------------------------------------------------")
        print(f"✅ Connexion réussie ! La session a été sauvegardée dans '{SESSION_FILE}'.")
        print("Vous pouvez maintenant lancer le script principal.")
        print("-------------------------------------------------------------")

    except Exception as e:
        print(f"\n❌ ERREUR : La connexion via sessionid a échoué. Détails : {e}")
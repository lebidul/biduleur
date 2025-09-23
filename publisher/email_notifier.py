# publisher/email_notifier.py

import smtplib
import os
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_notification(subject, body):
    """Envoie un e-mail de notification."""
    try:
        # Récupération des identifiants depuis les variables d'environnement/secrets
        sender_email = os.environ["SMTP_USER"]
        receiver_email = os.environ["RECIPIENT_EMAIL"]
        password = os.environ["SMTP_PASSWORD"]
        smtp_server = os.environ["SMTP_HOST"]
        smtp_port = int(os.environ.get("SMTP_PORT", 587))  # 587 est un port standard pour SMTP avec TLS

        # Création du message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))

        # Connexion au serveur SMTP et envoi de l'e-mail
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Sécurise la connexion
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())

        print("E-mail de notification envoyé avec succès.")

    except Exception as e:
        # Affiche une erreur si l'envoi de l'e-mail échoue
        print(f"Erreur lors de l'envoi de l'e-mail de notification : {e}")
        traceback.print_exc()
# publisher/main.py

from dotenv import load_dotenv

load_dotenv()  # Charge les variables du fichier .env dans l'environnement

import argparse
import numpy as np
import traceback

try:
    from publisher import email_notifier
    from publisher import gsheet_client
    from publisher.utils import get_post_text
    from publisher import image_generator, instagram_poster
    from biduleur.csv_utils import parse_bidul_event
    from biduleur.constants import GENRE1, HORAIRE
except (ModuleNotFoundError, ImportError):
    # Fallback
    from . import email_notifier
    from . import gsheet_client
    from .utils import get_post_text
    from . import image_generator, instagram_poster
    from biduleur.csv_utils import parse_bidul_event
    from biduleur.constants import GENRE1, HORAIRE

def execute_publication_workflow(format_choice="classique", date_str=None):
    """
    Orchestre le processus complet pour la publication d'une date donnée.
    """
    display_date = date_str or "aujourd'hui"
    print(f"Lancement du processus (format: {format_choice}, date: {display_date})")

    # 1. Extraire les données de Google Sheet pour la date cible
    entries_df = gsheet_client.get_entries_for_date(date_str)
    if entries_df.empty:
        print(f"Aucune entrée à publier pour la date sélectionnée ({display_date}). Le processus s'arrête.")
        return

    try:
        sorted_entries_df = entries_df.sort_values(by=[GENRE1, HORAIRE])
        print(f"DataFrame trié avec succès par '{GENRE1}' puis '{HORAIRE}'.")
    except KeyError as e:
        raise Exception(f"Erreur de tri : la colonne {e} est introuvable. Vérifiez votre fichier constants.py et les en-têtes du Google Sheet.") from e
    cleaned_sorted_entries = sorted_entries_df.replace({np.nan: None})



    print(f"{len(entries_df)} entrée(s) trouvée(s) pour la date: {display_date}.")

    # 2. Mettre en forme les données en HTML
    html_content = ""
    for index, row in cleaned_sorted_entries.iterrows():
        _, _, formatted_event, _ = parse_bidul_event(row)
        html_content += f"""{formatted_event}\n\n"""

    # 3. Générer une image à partir du HTML
    image_path = image_generator.create_from_html(html_content)
    print(f"Image générée et sauvegardée: {image_path}")

    # 4. Poster l'image sur Instagram
    caption = get_post_text(display_date)
    instagram_poster.upload_photo(image_path, caption)
    print("Image postée sur Instagram.")

    print("Workflow de publication terminé avec succès !")



def main():
    """Point d'entrée principal du module publisher."""
    parser = argparse.ArgumentParser(description="Génère et publie un post Instagram depuis Google Sheet.")
    parser.add_argument(
        'format',
        choices=['classique', 'nouveau'],
        default='classique',
        help="Le type de mise en forme à utiliser."
    )
    parser.add_argument(
        '--date',
        help="Date optionnelle à publier (format JJ/MM/AAAA). Par défaut, la date du jour."
    )
    args = parser.parse_args()

    try:
        execute_publication_workflow(args.format, args.date)

        subject = "✅ Succès : Tâche de publication Instagram terminée"
        body = (f"Le processus de publication (format: {args.format}, date: {args.date or 'aujourd\\\'hui'}) "
                "s'est terminé. Vérifiez le compte Instagram.")
        email_notifier.send_notification(subject, body)

    except Exception:
        import traceback

        print("ERREUR : Le processus de publication a échoué.")
        traceback.print_exc()
        subject = "❌ Échec : Tâche de publication Instagram"
        error_details = traceback.format_exc()
        body = (f"Le processus de publication (format: {args.format}, date: {args.date or 'aujourd\\\'hui'}) a échoué.\n\n"
                f"Détails de l'erreur :\n\n{error_details}")
        email_notifier.send_notification(subject, body)


if __name__ == '__main__':
    main()

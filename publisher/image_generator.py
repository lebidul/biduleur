from html2image import Html2Image
import os
from publisher import constants
from publisher import templates


def create_from_html(html_content, output_filename="publication_du_jour.png"):
    """
    Génère une image PNG à partir d'une chaîne de caractères HTML.

    Args:
        html_content (str): Le contenu HTML à convertir.
        output_filename (str): Le nom du fichier image à générer.

    Returns:
        str: Le chemin vers l'image générée.
    """
    # Crée un répertoire de sortie s'il n'existe pas
    output_dir = "output_images"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    hti = Html2Image(output_path=output_dir)

    # Vous pouvez spécifier une taille d'image si nécessaire
    # Par exemple, pour un post Instagram carré : size=(1080, 1080)
    hti.screenshot(html_str=html_content, save_as=output_filename, size=(1080, 1080))

    image_path = os.path.join(output_dir, output_filename)
    return image_path

def html_to_image(html_content, date, output_image, template):

    rendered_html = templates.render_template(
        template,
        content=html_content,
        date=date
    )

    # Render HTML to an image
    hti = Html2Image(output_path=constants.OUTPUT_PATH)
    html_output_file_name = os.path.join(constants.OUTPUT_PATH, f"{output_image}.html")
    open(html_output_file_name, 'w+', encoding='utf-8').write(rendered_html)
    return hti.screenshot(html_str=rendered_html, save_as=output_image, size=(1080, 1080))
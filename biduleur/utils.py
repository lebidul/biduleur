import os.path
from constants import *


def output_html_file(html_body: str, original_file_name: str = None, output_filename: str = None,
                     output_folder_name: str = OUTPUT_FOLDER_NAME):
    pre, ext = os.path.splitext(os.path.basename(original_file_name))
    if not output_filename:
        output_filename = os.path.join(output_folder_name, pre + ".html")
    else:
        output_filename = os.path.join(output_folder_name, output_filename)
    html_string = f"""<!DOCTYPE html>
<html  xmlns="http://www.w3.org/1999/xhtml" xml:lang="fr">
<head>
<meta charset="UTF-8"/>
<body>
{html_body}
</body>
</head>
</html>
"""
    open(output_filename, 'w+', encoding='utf-8').write(html_string)
    print(f"Événements mises en forme et exportés das le fichier: {output_filename}")

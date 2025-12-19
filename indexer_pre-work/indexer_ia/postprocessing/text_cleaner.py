import re

def clean_text(text):
    # Supprimer les espaces et sauts de ligne superflus
    text = re.sub(r'\s+', ' ', text)
    # Supprimer les caractères spéciaux ou non imprimables
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

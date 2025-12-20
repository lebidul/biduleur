"""Nettoyage du texte extrait des PDFs"""

import re


def clean_pdf_text(text: str) -> str:
    """
    Nettoie le texte extrait d'un PDF.

    - Supprime les césures (tiret + espace/newline)
    - Normalise les espaces multiples
    """
    if not text:
        return text

    # 1. Supprimer les césures (tiret + espace + retour ligne ou tiret + retour ligne)
    text = re.sub(r'-\s*\n\s*', '', text)

    # 2. Supprimer les césures inline (tiret + espace + minuscule)
    # "Passe- port" → "Passeport"
    # "L'En- tracte" → "L'Entracte"
    text = re.sub(r'-\s+([a-zàâäéèêëïîôùûüç])', r'\1', text)

    # 3. Normaliser les espaces multiples
    text = re.sub(r'\s+', ' ', text)

    # 4. Trim
    text = text.strip()

    return text


def expand_abbreviations(text: str) -> str:
    """Expanse les abréviations courantes."""
    if not text:
        return text

    abbreviations = {
        # Prénoms
        r'\bJ\.?\s*Carmet\b': 'Jean Carmet',
        r'\bP\.?\s*Scarron\b': 'Paul Scarron',
        r'\bG\.?\s*Sand\b': 'George Sand',
        r'\bH\.?\s*Salvador\b': 'Henri Salvador',
        r'\bL\.?\s*Aragon\b': 'Louis-Aragon',

        # Lieux
        r'\bC\.?C\.?\s+Athéna\b': 'Centre Culturel Athéna',
        r'\bC\.?C\.?\s': 'Centre Culturel ',
        r'\bMJC\b': 'MJC',
        r'\bEVE\b': 'EVE',
        r'\bUniv\.?\s*(du\s+)?Maine\b': 'Université du Maine',

        # Villes
        r'\bSablé\s*s/?Sarthe\b': 'Sablé-sur-Sarthe',
        r'\bSargé-lès-Le Mans\b': 'Sargé-lès-Le Mans',
        r'\bYvré\s*l.Évêque\b': "Yvré-l'Évêque",
        r'\bMoncé-en-?\s*Belin\b': 'Moncé-en-Belin',

        # Genres
        r'\bth\.\b': 'théâtre',
        r'\bmus\.\s*class\.?\b': 'musique classique',
        r'\bmus\.\s*trad\.?\b': 'musique traditionnelle',
        r'\bmus\.\s*baroque\b': 'musique baroque',
        r'\bch\.?\s*fr\.?\b': 'chanson française',
        r'\bj\.?\s*public\b': 'jeune public',
    }

    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def normalize_lieu_name(lieu: str) -> str:
    """Normalise un nom de lieu pour le matching."""
    if not lieu:
        return lieu

    lieu = clean_pdf_text(lieu)
    lieu = expand_abbreviations(lieu)

    # Corrections spécifiques connues
    corrections = {
        "l'elolienne": "L'Éolienne",
        "l'eolienne": "L'Éolienne",
        "espace culturel l'elolienne": "L'Éolienne",
        "le barouf": "Bar Le Barouf",
        "barouf": "Bar Le Barouf",
        "le lézard": "Bar le Lézard",
        "lézard": "Bar le Lézard",
        "le passeport": "Bar le Passeport",
        "passeport": "Bar le Passeport",
        "passe- port": "Bar le Passeport",
        "bar du pilier rouge": "Bar du Pilier Rouge",
        "pilier rouge": "Bar du Pilier Rouge",
        "l'epicerie du pré": "L'Épicerie du Pré",
        "epicerie du pré": "L'Épicerie du Pré",
        "théâtre p. scarron": "Théâtre Paul Scarron",
        "théâtre paul scarron": "Théâtre Paul Scarron",
        "salle j.carmet": "Salle Jean Carmet",
        "salle j. carmet": "Salle Jean Carmet",
        "salle jean carmet": "Salle Jean Carmet",
        "péniche excelsior": "Péniche Excelsior",
        "l'excelsior": "L'Excelsior",
        "le rabelais": "Le Rabelais",
        "rabelais": "Le Rabelais",
        "théâtre du passeur": "Théâtre du Passeur",
        "l'entracte": "L'Entracte",
        "l'en- tracte": "L'Entracte",
    }

    lieu_lower = lieu.lower().strip()
    if lieu_lower in corrections:
        return corrections[lieu_lower]

    return lieu


def normalize_style(style: str) -> str:
    """Normalise un style musical/artistique."""
    if not style:
        return style

    style = style.strip().lower()

    # Normalisation des styles courants
    style_map = {
        # Rock
        'rock': 'rock',
        'math rock': 'math rock',
        'noise rock': 'noise rock',
        'poème rock': 'rock poétique',
        'rock poétique': 'rock poétique',
        'pop rock': 'pop rock',
        'rock progressif': 'rock progressif',
        'punk rock': 'punk rock',

        # Jazz
        'jazz': 'jazz',
        'jazz manouche': 'jazz manouche',
        'free jazz': 'free jazz',

        # Électro
        'electro': 'électro',
        'électro': 'électro',
        'dj set': 'dj set',
        'dj set techno': 'techno',
        'techno': 'techno',

        # Chanson
        'chanson': 'chanson',
        'chanson française': 'chanson française',
        'ch. fr.': 'chanson française',
        'ch fr': 'chanson française',

        # Théâtre
        'théâtre': 'théâtre',
        'theatre': 'théâtre',
        'th.': 'théâtre',

        # Musique classique
        'classique': 'musique classique',
        'musique classique': 'musique classique',
        'mus. class.': 'musique classique',
        'baroque': 'musique baroque',
        'musique baroque': 'musique baroque',

        # Autres
        'hip hop': 'hip-hop',
        'hip-hop': 'hip-hop',
        'rap': 'rap',
        'reggae': 'reggae',
        'ska': 'ska',
        'folk': 'folk',
        'blues': 'blues',
        'soul': 'soul',
        'funk': 'funk',
        'world': 'world',
        'musique du monde': 'world',
        'trad': 'musique traditionnelle',
        'musique traditionnelle': 'musique traditionnelle',
        'jeune public': 'jeune public',
        'j. public': 'jeune public',
        'conte': 'conte',
        'cirque': 'cirque',
        'danse': 'danse',
        'humour': 'humour',
        'one man show': 'humour',
        'stand-up': 'humour',
    }

    return style_map.get(style, style)

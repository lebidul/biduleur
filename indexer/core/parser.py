"""
Parser d'événements depuis le texte brut extrait des PDFs.

Détecte les patterns spécifiques au Bidul:
- Artistes en MAJUSCULES, séparés par "+"
- Genres entre parenthèses (souvent en italique dans le PDF)
- Spectacles entre guillemets
- Format type: DATE \n • ARTISTE (genre) + ARTISTE2, lieu, ville, heure, tarif
"""

import re
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import date

from core.text_cleaner import clean_pdf_text, expand_abbreviations, normalize_lieu_name

logger = logging.getLogger(__name__)


def is_named_event(text: str) -> bool:
    """
    Détermine si le texte représente un événement nommé (festival, soirée thématique).

    Événements nommés (remplir evenement.nom):
    - "Alpa On The Rock #13"
    - "Esc Exp #21 TERIAKI"
    - "Melting Rock"
    - "Les Spectaculaires"
    - "Soirée Solidaire"

    PAS événements nommés (ne pas remplir evenement.nom):
    - Spectacles entre guillemets: "L'itinérance de Maud"
    - Concerts d'artistes: MENDELSON (poème rock)
    """
    # Patterns d'événements nommés
    named_event_patterns = [
        r'^Alpa\s+On\s+The\s+Rock\s+#?\d+',
        r'^Esc\s+Exp\s+#?\d+',
        r'^Melting\s+Rock',
        r'^Les\s+Spectaculaires',
        r'^Soirée\s+\w+',  # Soirée Solidaire, Soirée Electro, etc.
        r'^Labo\s+d.Impro',
        r'^[Cc]arte\s+[Bb]lanche\s+[àa]',
        r'^Festival\s+',
        r'^Nuit\s+\w+',  # Nuit Blanche, etc.
    ]

    for pattern in named_event_patterns:
        if re.match(pattern, text.strip(), re.IGNORECASE):
            return True

    return False


def extract_event_name(text: str) -> Optional[str]:
    """
    Extrait le nom de l'événement SI c'est un événement nommé.
    Retourne None si c'est un spectacle ou concert simple.
    """
    if not is_named_event(text):
        return None

    # Extraire le nom jusqu'au premier ":" ou artiste
    patterns = [
        r'^(Alpa\s+On\s+The\s+Rock\s+#?\d+)',
        r'^(Esc\s+Exp\s+#?\d+\s+\w+)',
        r'^(Melting\s+Rock)',
        r'^(Les\s+Spectaculaires)',
        r'^(Soirée\s+\w+)',
        r'^(Labo\s+d.Impro\s*:\s*"[^"]+")' ,
        r'^(Festival\s+[^:,]+)',
        r'^(Nuit\s+\w+)',
        r'^([Cc]arte\s+[Bb]lanche\s+[àa]\s+[^:,]+)',
    ]

    for pattern in patterns:
        match = re.match(pattern, text.strip(), re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def _normalize_artist_name(name: str) -> str:
    """
    Normalise un nom d'artiste en Title Case.

    Gère les cas spéciaux:
    - Préfixes: "Cie", "DJ", "MC" restent en majuscules
    - Mots de liaison: "de", "du", "des", "le", "la", "les", "et", "l'" restent en minuscules (sauf en début)
    - Acronymes courts (2-3 lettres tout en majuscules): conservés si pas un mot de liaison
    - Noms avec apostrophe: L'Artiste -> L'Artiste
    """
    if not name or not name.strip():
        return name

    name = name.strip()

    # Mots à garder en majuscules (préfixes/titres)
    KEEP_UPPER = {'DJ', 'MC', 'VJ', 'CIE', 'CIA'}

    # Mots de liaison à garder en minuscules (sauf en début de nom)
    LIAISON = {'de', 'du', 'des', 'le', 'la', 'les', 'et', 'en', 'aux', 'à'}

    words = name.split()
    result = []

    for i, word in enumerate(words):
        word_lower = word.lower()

        # Vérifier si c'est un préfixe à garder en majuscules
        if word.upper() in KEEP_UPPER:
            result.append(word.upper())
            continue

        # Mots de liaison (sauf en première position) - vérifié AVANT les acronymes
        if i > 0 and word_lower in LIAISON:
            result.append(word_lower)
            continue

        # Acronymes courts (2-3 lettres, tout en majuscules): conserver
        # Mais seulement si ce n'est PAS un mot de liaison
        if len(word) <= 3 and word.isupper() and word.isalpha() and word_lower not in LIAISON:
            result.append(word)
            continue

        # Gestion de l'apostrophe: L'Artiste, D'Arcy
        if "'" in word:
            parts = word.split("'", 1)
            if len(parts) == 2:
                prefix = parts[0].capitalize()
                suffix = parts[1].capitalize() if parts[1] else ''
                result.append(f"{prefix}'{suffix}")
                continue

        # Cas standard: Title Case
        result.append(word.capitalize())

    return ' '.join(result)


def split_multi_date_events(raw_text: str, base_month: int, base_year: int) -> list[tuple]:
    """
    Détecte et splitte les événements avec plusieurs dates.

    Patterns:
    - "Sa 07 & di 08 : ..." → 2 événements
    - "Lu 02 & Ma 03 : ..." → 2 événements
    - "Je 05, Sa 07, Sa 14 : ..." → 3 événements
    - "Ve 13 & sa 14 : ..." → 2 événements

    Args:
        raw_text: Texte brut de l'événement
        base_month: Mois du Bidul
        base_year: Année du Bidul

    Returns:
        Liste de tuples (date_obj, heure, texte_nettoyé, date_str)
        Si pas de dates multiples, retourne [(None, None, raw_text, None)]
    """
    # Pattern pour détecter les dates multiples en début de ligne
    # Ex: "Sa 07 & di 08 :", "Lu 02 & Ma 03 :", "Je 05, Sa 07, Sa 14 :"
    # Format jour abrégé: Lu, Ma, Me, Je, Ve, Sa, Di (insensible à la casse)
    multi_date_pattern = r'^([DLMJVS][a-z]\s*\d{1,2}(?:\s*[&,]\s*[A-Za-z]{2}\s*\d{1,2})+)\s*:\s*(.+)$'

    match = re.match(multi_date_pattern, raw_text.strip(), re.IGNORECASE | re.DOTALL)

    if not match:
        # Pas de dates multiples, retourner tel quel
        return [(None, None, raw_text, None)]

    dates_part = match.group(1)
    event_text = match.group(2)

    # Parser les dates individuelles
    # Pattern pour Lu, Ma, Me, Je, Ve, Sa, Di suivi d'un numéro
    day_pattern = r'([DLMJVS][a-z])\s*(\d{1,2})'
    days_found = re.findall(day_pattern, dates_part, re.IGNORECASE)

    if not days_found:
        return [(None, None, raw_text, None)]

    results = []

    # Chercher les heures spécifiques par date dans le texte
    # Ex: "sa 20h30/di 17h" ou "15h (0-3 ans) & 16h30 (4-8 ans)"
    hours_by_day = {}
    hour_pattern = r'\b([dlmjvs][a-z])\s*(\d{1,2}h\d{0,2})'
    hour_matches = re.findall(hour_pattern, event_text.lower())
    for day_abbr, hour in hour_matches:
        hours_by_day[day_abbr] = hour

    # Heure par défaut si pas spécifique
    default_hour_match = re.search(r'(\d{1,2}h\d{0,2})', event_text)
    default_hour = default_hour_match.group(1) if default_hour_match else None

    for day_abbr, day_num in days_found:
        day_abbr_lower = day_abbr.lower()
        day_int = int(day_num)

        # Construire la date
        try:
            event_date = date(base_year, base_month, day_int)
        except ValueError:
            # Jour invalide pour ce mois
            continue

        # Trouver l'heure pour cette date
        hour = hours_by_day.get(day_abbr_lower, default_hour)

        # Construire la date_str pour compatibilité
        date_str = f"{day_abbr.capitalize()} {day_num}"

        results.append((event_date, hour, event_text, date_str))

    return results if results else [(None, None, raw_text, None)]


def split_fused_lines(raw_text: str) -> list[str]:
    """
    Sépare les lignes fusionnées contenant plusieurs événements.

    Ex: "Di 01 : Événement1... Lu 02 & Ma 03 : Événement2..."

    Pattern de séparation: une nouvelle date au milieu du texte
    Ex: "...17h, 3/5€ Lu 02 & Ma 03 : ..."

    Attention: ne pas confondre avec les heures "sa 20h30" ou prix "7€50"

    Returns:
        Liste de textes d'événements séparés
    """
    # Pattern pour détecter une nouvelle date au milieu
    # Format: "Lu 02", "Ma 03", "Je 05", "Ve 13 & sa 14", etc.
    # Doit être précédé d'un espace, € ou virgule (éviter "7€50")
    # Le lookbehind (?<=[€\s,]) assure qu'on ne splitte pas sur les prix
    split_pattern = r'(?<=[€\s,])\s*([DLMJVS][aeiou]\s*\d{1,2}(?:\s*[&,]\s*[A-Za-z]{2}\s*\d{1,2})*)\s*:\s*'

    parts = re.split(split_pattern, raw_text, flags=re.IGNORECASE)

    if len(parts) <= 1:
        return [raw_text]

    # Reconstituer: parts[0] = premier événement, puis alternance date/texte
    events = []

    # Premier événement (avant le premier split)
    if parts[0].strip():
        events.append(parts[0].strip())

    # Événements suivants: date + texte
    i = 1
    while i < len(parts):
        date_part = parts[i] if i < len(parts) else ''
        text_part = parts[i + 1] if i + 1 < len(parts) else ''
        if date_part and text_part:
            events.append(f"{date_part} : {text_part}".strip())
        i += 2

    return events if events else [raw_text]


def find_lieu_in_text(text: str, lieu_ref_list: list) -> Optional[tuple]:
    """
    Cherche un lieu du référentiel dans le texte.

    Args:
        text: Texte à analyser
        lieu_ref_list: Liste de tuples (id, nom, ville, aliases...)

    Returns:
        (lieu_nom, lieu_ref_id, position_start, position_end) ou None
    """
    text_clean = clean_pdf_text(text)
    text_lower = text_clean.lower()

    best_match = None
    best_length = 0

    for lieu_ref in lieu_ref_list:
        lieu_id = lieu_ref[0]
        lieu_nom = lieu_ref[1]

        # Chercher le nom exact
        lieu_nom_lower = lieu_nom.lower()
        pos = text_lower.find(lieu_nom_lower)

        if pos != -1 and len(lieu_nom) > best_length:
            best_match = (lieu_nom, lieu_id, pos, pos + len(lieu_nom))
            best_length = len(lieu_nom)

        # Chercher aussi les variantes courtes
        # Ex: "Bar Le Barouf" dans ref, chercher aussi "Le Barouf" et "Barouf"
        if lieu_nom_lower.startswith('bar le '):
            short = lieu_nom_lower[7:]  # sans "bar le "
            pos = text_lower.find(short)
            if pos != -1 and len(short) > best_length:
                best_match = (lieu_nom, lieu_id, pos, pos + len(short))
                best_length = len(short)

        if lieu_nom_lower.startswith('bar '):
            short = lieu_nom_lower[4:]  # sans "bar "
            pos = text_lower.find(short)
            if pos != -1 and len(short) > best_length:
                best_match = (lieu_nom, lieu_id, pos, pos + len(short))
                best_length = len(short)

        if lieu_nom_lower.startswith("l'"):
            short = lieu_nom_lower[2:]
            pos = text_lower.find(short)
            if pos != -1 and len(short) > best_length:
                best_match = (lieu_nom, lieu_id, pos, pos + len(short))
                best_length = len(short)

        # Gérer les variantes avec césures nettoyées
        lieu_nom_cleaned = normalize_lieu_name(lieu_nom)
        if lieu_nom_cleaned != lieu_nom:
            lieu_cleaned_lower = lieu_nom_cleaned.lower()
            pos = text_lower.find(lieu_cleaned_lower)
            if pos != -1 and len(lieu_nom_cleaned) > best_length:
                best_match = (lieu_nom_cleaned, lieu_id, pos, pos + len(lieu_nom_cleaned))
                best_length = len(lieu_nom_cleaned)

    return best_match


def extract_tarif_improved(text: str) -> tuple:
    """
    Extrait les informations de tarif avec support des décimales et fourchettes.

    Returns:
        (tarif_raw, prix_min, prix_max, gratuit)
    """
    # Patterns gratuit
    gratuit_patterns = [
        r'\b0\s*[€eE]',
        r'\bgratuit\b',
        r'\bentrée\s+libre\b',
        r'\bprix\s+libre\b',
        r'\bau\s+chapeau\b',
        r'\blibre\s+participation\b',
    ]

    for pattern in gratuit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return (match.group(0), 0.0, 0.0, True)

    # Pattern tarif avec fourchette et décimales
    tarif_patterns = [
        # 3.75/18€ ou 5/7/9€ ou 6.75/18€
        (r'(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s*[€eE]', 3),
        (r'(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s*[€eE]', 2),
        # 7 à 13€
        (r'(\d+[.,]?\d*)\s*(?:à|a)\s*(\d+[.,]?\d*)\s*[€eE]', 2),
        # Simple: 8€ ou 3,50€
        (r'(\d+[.,]\d+)\s*[€eE]', 1),
        (r'(\d+)\s*[€eE]', 1),
    ]

    for pattern, num_groups in tarif_patterns:
        match = re.search(pattern, text)
        if match:
            prices = []
            for i in range(1, num_groups + 1):
                g = match.group(i)
                if g:
                    try:
                        prices.append(float(g.replace(',', '.')))
                    except ValueError:
                        pass

            if prices:
                return (match.group(0), min(prices), max(prices), False)

    return (None, None, None, False)


@dataclass
class ArtisteInfo:
    """Information sur un artiste avec son genre associé."""
    nom: str
    genre: Optional[str] = None
    spectacle: Optional[str] = None

    def to_dict(self) -> dict:
        return {"nom": self.nom, "genre": self.genre, "spectacle": self.spectacle}


@dataclass
class ParsedEvent:
    """Un événement parsé depuis le texte brut."""
    raw_text: str  # Texte source complet

    # Champs extraits
    nom: Optional[str] = None
    date_str: Optional[str] = None  # "Samedi 20", "Mardi 2"
    date_evenement: Optional[date] = None
    heure: Optional[str] = None  # "20h30", "18h à 20h"

    # Lieu
    lieu_raw: Optional[str] = None
    ville_raw: Optional[str] = None

    # Artistes avec relations (liste d'ArtisteInfo ou dicts)
    artistes: list = field(default_factory=list)

    # Spectacles (noms entre guillemets)
    spectacles: list[str] = field(default_factory=list)

    # Genres (texte entre parenthèses) - conservé pour compatibilité
    genres_raw: list[str] = field(default_factory=list)

    # Prix
    tarif_raw: Optional[str] = None
    prix_min: Optional[float] = None
    prix_max: Optional[float] = None
    gratuit: bool = False

    # Type déduit
    type_evenement: Optional[str] = None

    # Qualité
    confidence: float = 0.5

    def to_dict(self) -> dict:
        """Convertit en dict pour JSON/DB."""
        d = asdict(self)
        # Convertir artistes en JSON (nouveau format avec relations)
        if self.artistes and isinstance(self.artistes[0], ArtisteInfo):
            d['artistes'] = json.dumps([a.to_dict() for a in self.artistes], ensure_ascii=False)
        elif self.artistes and isinstance(self.artistes[0], dict):
            d['artistes'] = json.dumps(self.artistes, ensure_ascii=False)
        else:
            # Ancien format: liste de strings
            d['artistes'] = json.dumps(self.artistes, ensure_ascii=False)
        d['spectacles'] = json.dumps(self.spectacles, ensure_ascii=False)
        d['genres_raw'] = json.dumps(self.genres_raw, ensure_ascii=False)
        if self.date_evenement:
            d['date_evenement'] = self.date_evenement.isoformat()
        return d


class EventParser:
    """
    Parser d'événements pour les PDFs du Bidul.

    Patterns détectés:
    - Dates: "Samedi 20", "Mardi 2", "Dimanche 21"
    - Événements: • ou  (bullet) suivi du contenu
    - Artistes: MAJUSCULES, séparés par +
    - Genres: (texte entre parenthèses)
    - Spectacles: "texte entre guillemets"
    - Lieu, ville, heure, prix en fin de ligne
    """

    # Patterns de dates
    # Supporte: "Samedi 20", "LUNDI 1ER", "Mardi 2", "Me 1er", "Je 02", etc.
    JOURS = r"(?:[Ll]undi|[Mm]ardi|[Mm]ercredi|[Jj]eudi|[Vv]endredi|[Ss]amedi|[Dd]imanche|LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE|[Ll]u|[Mm]a|[Mm]e|[Jj]e|[Vv]e|[Ss]a|[Dd]i|LU|MA|ME|JE|VE|SA|DI)"
    DATE_PATTERN = re.compile(rf"^({JOURS})\s+(\d{{1,2}})(?:ER|er|ème|eme)?\s*:?\s*$", re.MULTILINE)

    # Pattern pour les bullets (• ou caractères similaires)
    # Inclut: •●○◦▪▫■□►▸‣⁃ et variantes Unicode (❑❒◇◆★☆✦✧♦❖✳✴✵✶✷✸✹)
    # U+2750-U+2757 (shadowed squares, question marks), U+F06F, U+F071, U+F0B5, U+F0B6 (Private Use Area - polices Wingdings)
    BULLET_CHARS = r"[•●○◦▪▫■□►▸‣⁃❑❒◇◆★☆✦✧♦❖✳✴✵✶✷✸✹\u2750-\u2757\uf06f\uf071\uf0b5\uf0b6]"

    # Pattern pour détecter un nouveau événement dans un texte multi-événements
    # Un nouvel événement commence par: bullet OU (retour ligne + artiste en MAJUSCULES)
    MULTI_EVENT_SPLIT = re.compile(
        r'(?:\n\s*[•●○◦▪▫■□►▸‣⁃❑❒◇◆★☆✦✧♦❖✳✴✵✶✷✸✹\u2750-\u2757\uf06f\uf071\uf0b5\uf0b6]\s*)|'  # Bullet sur nouvelle ligne
        r'(?:\n\s*(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-&]{2,}.*?,.*?\d+[hH]))',  # ARTISTE... , ... XXh
        re.MULTILINE
    )

    # Pattern pour les heures
    HEURE_PATTERN = re.compile(r"(\d{1,2}[hH]\d{0,2}(?:\s*[àa-]\s*\d{1,2}[hH]\d{0,2})?)")

    # Pattern pour les prix
    PRIX_PATTERN = re.compile(
        r"(?:(\d+(?:[.,]\d+)?)\s*[€eE]|"
        r"(\d+)\s*/\s*(\d+)\s*[€eE]?|"
        r"(\d+)\s*[àa-]\s*(\d+)\s*[€eE]|"
        r"(gratuit|libre|au chapeau|prix libre|tnc|0\s*[€eE]))",
        re.IGNORECASE
    )

    # Pattern pour les artistes en majuscules
    ARTISTE_PATTERN = re.compile(r"([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-&]{2,}(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\'\-&]+)*)")

    # Pattern pour les genres entre parenthèses
    GENRE_PATTERN = re.compile(r"\(([^)]+)\)")

    # Pattern pour les spectacles entre guillemets
    SPECTACLE_PATTERN = re.compile(r'[""«]([^""»]+)[""»]')

    def __init__(self, bidul_mois: Optional[int] = None, bidul_annee: Optional[int] = None):
        """
        Initialise le parser.

        Args:
            bidul_mois: Mois du Bidul (pour construire les dates complètes)
            bidul_annee: Année du Bidul
        """
        self.bidul_mois = bidul_mois
        self.bidul_annee = bidul_annee

    # Pattern pour le format inline: "Je 02 : ARTISTE (genre), Lieu, heure, prix"
    INLINE_DATE_PATTERN = re.compile(
        r'^([MLJVSD][aeiou]|[Ll]undi|[Mm]ardi|[Mm]ercredi|[Jj]eudi|[Vv]endredi|[Ss]amedi|[Dd]imanche)\s+(\d{1,2})(?:er|ème|eme)?\s*:\s*(.+)$',
        re.MULTILINE | re.IGNORECASE
    )

    def parse(self, text: str) -> list[ParsedEvent]:
        """
        Parse le texte complet et extrait les événements.

        Supporte deux formats:
        1. Format standard: dates sur lignes séparées, événements avec bullets
        2. Format inline: "Je 02 : ARTISTE (genre), Lieu, heure, prix"

        Args:
            text: Texte brut extrait du PDF

        Returns:
            Liste d'événements parsés (dédoublonnés)
        """
        # Essayer d'abord le format standard
        events = self._parse_standard_format(text)

        # Si aucun événement trouvé, essayer le format inline
        if not events:
            events = self._parse_inline_format(text)

        return events

    def _parse_standard_format(self, text: str) -> list[ParsedEvent]:
        """Parse le format standard avec dates séparées et bullets."""
        events = []
        seen_signatures = set()

        # Découper par dates
        date_blocks = self._split_by_dates(text)

        for date_str, block_text in date_blocks:
            # Découper par événements (bullets)
            event_texts = self._split_by_bullets(block_text)

            for event_text in event_texts:
                if len(event_text.strip()) < 10:
                    continue

                event = self._parse_event(event_text.strip(), date_str)
                if event:
                    signature = self._event_signature(event)
                    if signature not in seen_signatures:
                        seen_signatures.add(signature)
                        events.append(event)

        return events

    def _parse_inline_format(self, text: str) -> list[ParsedEvent]:
        """
        Parse le format inline: "Je 02 : ARTISTE (genre), Lieu, heure, prix"

        Ce format est utilisé dans les anciens Biduls (avant ~2015).
        """
        events = []
        seen_signatures = set()

        # Regrouper les lignes qui appartiennent au même événement
        # (certains événements sont sur plusieurs lignes)
        lines = text.split('\n')
        current_event_lines = []
        current_date = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Vérifier si c'est une nouvelle ligne d'événement (commence par une date)
            match = self.INLINE_DATE_PATTERN.match(line)
            if match:
                # Traiter l'événement précédent
                if current_event_lines and current_date:
                    event_text = ' '.join(current_event_lines)
                    event = self._parse_event(event_text, current_date)
                    if event:
                        signature = self._event_signature(event)
                        if signature not in seen_signatures:
                            seen_signatures.add(signature)
                            events.append(event)

                # Commencer un nouvel événement
                jour = match.group(1)
                num = match.group(2)
                current_date = f"{jour} {num}"
                current_event_lines = [match.group(3).strip()]
            else:
                # Continuation de l'événement précédent
                if current_event_lines:
                    current_event_lines.append(line)

        # Traiter le dernier événement
        if current_event_lines and current_date:
            event_text = ' '.join(current_event_lines)
            event = self._parse_event(event_text, current_date)
            if event:
                signature = self._event_signature(event)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    events.append(event)

        return events

    def _event_signature(self, event: ParsedEvent) -> str:
        """Crée une signature unique pour dédoublonner les événements."""
        # Normaliser le raw_text:
        # - Supprimer tous les espaces/sauts de ligne
        # - Mettre en minuscules
        # - Prendre les 80 premiers caractères (suffisant pour identifier)
        raw_norm = ''.join(event.raw_text.lower().split())[:80]
        return f"{event.date_str}|{raw_norm}"

    def _split_by_dates(self, text: str) -> list[tuple[str, str]]:
        """Découpe le texte par blocs de dates."""
        blocks = []
        lines = text.split('\n')

        current_date = None
        current_block = []

        for line in lines:
            # Vérifier si c'est une ligne de date
            match = self.DATE_PATTERN.match(line.strip())
            if match:
                # Sauvegarder le bloc précédent
                if current_date and current_block:
                    blocks.append((current_date, '\n'.join(current_block)))

                current_date = line.strip()
                current_block = []
            else:
                current_block.append(line)

        # Dernier bloc
        if current_date and current_block:
            blocks.append((current_date, '\n'.join(current_block)))

        return blocks

    def _split_by_bullets(self, text: str) -> list[str]:
        """Découpe un bloc de texte par événements (bullets)."""
        # Pattern pour détecter le début d'un événement
        pattern = re.compile(rf"(?:^|\n)\s*{self.BULLET_CHARS}\s*", re.MULTILINE)

        parts = pattern.split(text)
        # Filtrer les parties vides
        events = [p.strip() for p in parts if p.strip()]

        # Post-traitement: séparer les multi-événements collés
        final_events = []
        for event_text in events:
            split_events = self._split_multi_events(event_text)
            final_events.extend(split_events)

        return final_events

    def _split_multi_events(self, text: str) -> list[str]:
        """
        Sépare un texte contenant potentiellement plusieurs événements.

        Détecte les cas où plusieurs événements sont collés, par exemple:
        "ARTISTE1, Lieu1, 19h, 0€ \n ARTISTE2, Lieu2, 21h, 0€"

        Règles de split:
        1. Prix suivi de retour ligne = fin d'événement
        2. Bullets internes
        """
        # Chercher les heures dans le texte
        heures = list(self.HEURE_PATTERN.finditer(text))

        # Si moins de 2 heures, pas de multi-événement probable
        if len(heures) < 2:
            return [text]

        # Méthode 1: Split sur "prix + retour ligne"
        # Pattern: prix (0€, 5€, gratuit, billet, etc.) suivi de retour ligne
        prix_newline_pattern = re.compile(
            r'(\d+\s*[€eE]|gratuit|au chapeau|prix libre|hnc|tnc|billet[^,\n]*)\s*\n\s*',
            re.IGNORECASE
        )

        parts = prix_newline_pattern.split(text)

        # Reconstruire les événements (prix appartient à l'événement précédent)
        if len(parts) > 2:
            events = []
            current = ""
            for i, part in enumerate(parts):
                if i % 2 == 0:  # Contenu
                    current += part
                else:  # Prix (séparateur)
                    current += part  # Ajouter le prix
                    if current.strip():
                        events.append(current.strip())
                    current = ""
            # Dernier événement
            if current.strip():
                events.append(current.strip())

            # Filtrer les événements trop courts
            events = [e for e in events if len(e) > 15]

            if len(events) > 1:
                return events

        # Méthode 2: Split par retour ligne + MAJUSCULES avec heure
        lines = text.split('\n')
        if len(lines) > 1:
            events = []
            current_event = []

            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue

                # Détecter si cette ligne commence un nouvel événement
                is_new_event = False
                if current_event:
                    # Vérifie si la ligne commence par un artiste en majuscules ET contient une heure
                    if re.match(r'^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-&]{2,}', line_stripped):
                        if self.HEURE_PATTERN.search(line_stripped):
                            is_new_event = True

                if is_new_event:
                    if current_event:
                        events.append('\n'.join(current_event))
                    current_event = [line_stripped]
                else:
                    current_event.append(line_stripped)

            if current_event:
                events.append('\n'.join(current_event))

            if len(events) > 1:
                return events

        return [text]

    def _extract_spectacles_with_genre(self, text: str) -> tuple[list[dict], str]:
        """
        Extrait les spectacles entre guillemets AVANT tout autre parsing.
        Les virgules à l'intérieur des guillemets sont protégées.

        Pattern: "titre spectacle" (genre)

        Returns:
            (liste_spectacles, texte_nettoyé)
            spectacles: [{"nom": "...", "genre": "th."}, ...]
        """
        spectacles = []

        # Pattern : "texte" ou «texte» suivi optionnellement de (genre)
        pattern = re.compile(r'[""«]([^""»]+)[""»]\s*(?:\(([^)]+)\))?')

        def replace_and_capture(match):
            titre = match.group(1).strip()
            genre = match.group(2).strip() if match.group(2) else None
            spectacles.append({
                'nom': titre,
                'genre': genre
            })
            return ''  # Retirer du texte

        text_cleaned = pattern.sub(replace_and_capture, text)

        # Nettoyer les virgules orphelines et espaces multiples
        text_cleaned = re.sub(r'\s*,\s*,\s*', ', ', text_cleaned)
        text_cleaned = re.sub(r'^\s*,\s*', '', text_cleaned)
        text_cleaned = re.sub(r'\s+', ' ', text_cleaned).strip()

        return spectacles, text_cleaned

    def _clean_raw_text(self, text: str) -> str:
        """Nettoie le texte brut des artifacts d'extraction PDF."""
        # 1. Appliquer le nettoyage des césures PDF
        text = clean_pdf_text(text)

        # 2. Expansion des abréviations
        text = expand_abbreviations(text)

        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()
            # Ignorer les lignes "K" isolées
            if stripped in ('K', 'K ', ' K'):
                continue
            # Ignorer les headers "le bidul - mois YYYY"
            if re.match(r'^le bidul\s*-\s*\w+\s+\d{4}$', stripped, re.IGNORECASE):
                continue
            cleaned_lines.append(line)

        result = '\n'.join(cleaned_lines).strip()

        # Supprimer les puces en début de texte (peuvent rester après le split)
        result = re.sub(rf'^{self.BULLET_CHARS}\s*', '', result)

        return result

    def _extract_spectacle_artiste_pattern(self, text: str) -> tuple[list[ArtisteInfo], list[str], list[str], str]:
        """Extrait le pattern 'Spectacle' Cie/Artiste (genre) AVANT le parsing standard."""
        artistes = []
        spectacles = []
        genres = []

        pattern = re.compile(
            r'[""«]([^""»]+)[""»]\s+'
            r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'\-/&]+?)"
            r'\s*\(([^)]+)\)',
            re.UNICODE
        )

        match = pattern.search(text)
        if match:
            titre = match.group(1).strip()
            artiste_raw = match.group(2).strip()
            genre = match.group(3).strip()

            spectacles.append(titre)
            genres.append(genre)

            if re.search(r'\s*/\s*(?:Cie|Compagnie)\s+', artiste_raw, re.IGNORECASE):
                parts = re.split(r'\s*/\s*(?:Cie|Compagnie)\s*', artiste_raw, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    if parts[0].strip():
                        artistes.append(ArtisteInfo(nom=_normalize_artist_name(parts[0].strip()), genre=genre, spectacle=titre))
                    if parts[-1].strip():
                        artistes.append(ArtisteInfo(nom="Cie " + _normalize_artist_name(parts[-1].strip()), genre=genre, spectacle=titre))
            else:
                artistes.append(ArtisteInfo(nom=_normalize_artist_name(artiste_raw), genre=genre, spectacle=titre))

            text = text[:match.start()] + text[match.end():]
            text = re.sub(r'\s+', ' ', text).strip()

        return artistes, spectacles, genres, text

    def _extract_double_slash_pattern(self, text: str) -> tuple[Optional[str], str]:
        """
        Extrait le pattern 'Titre/Nom événement // ARTISTES...'

        Le // sépare le nom de l'événement (festival, soirée) des artistes.
        Ex: "Festival X #9 (concerts) // ARTISTE1 + ARTISTE2, lieu, heure"

        Returns:
            (nom_evenement, texte_restant_avec_artistes)
        """
        # Pattern: texte // texte (le // doit être entouré d'espaces ou en début/fin)
        match = re.search(r'^(.+?)\s*//\s*(.+)$', text)
        if match:
            nom_evenement = match.group(1).strip()
            reste = match.group(2).strip()

            # Valider que c'est bien un nom d'événement (pas juste un artiste)
            # Un nom d'événement contient souvent: festival, soirée, #, ou un genre entre ()
            is_event_name = (
                re.search(r'festival|soirée|nuit|journée|#\d+|\(\w+\)', nom_evenement, re.IGNORECASE) or
                not self.ARTISTE_PATTERN.match(nom_evenement)  # Pas entièrement en majuscules
            )

            if is_event_name:
                return nom_evenement, reste

        return None, text

    def _parse_event(self, text: str, date_str: Optional[str]) -> Optional[ParsedEvent]:
        if not text:
            return None

        # Nettoyer les artifacts d'extraction
        text = self._clean_raw_text(text)
        if not text:
            return None

        event = ParsedEvent(raw_text=text)

        if date_str:
            event.date_str = date_str
            event.date_evenement = self._parse_date(date_str)

        # 0a. Extraire le pattern // (Titre événement // ARTISTES)
        event_name_from_slash, text = self._extract_double_slash_pattern(text)

        # 0b. Extraire le pattern "Spectacle" Artiste (genre)
        pre_artistes, pre_spectacles, pre_genres, text = self._extract_spectacle_artiste_pattern(text)

        # 1. Spectacles restants
        spectacles_with_genre, text_cleaned = self._extract_spectacles_with_genre(text)
        event.spectacles = pre_spectacles + [s['nom'] for s in spectacles_with_genre]

        spectacle_genres = pre_genres + [s['genre'] for s in spectacles_with_genre if s.get('genre')]

        # 2. Artistes
        artistes = self._extract_artistes(text_cleaned)
        if pre_artistes:
            event.artistes = pre_artistes
        else:
            event.artistes = artistes

        # 3. Genres (entre parenthèses restantes dans le texte nettoyé)
        genres = self.GENRE_PATTERN.findall(text_cleaned)
        all_genres = spectacle_genres + [g.strip() for g in genres if g.strip() and len(g) < 50]
        event.genres_raw = list(dict.fromkeys(all_genres))  # Dédupliquer

        # 4. Heure
        heure_match = self.HEURE_PATTERN.search(text_cleaned)
        if heure_match:
            event.heure = heure_match.group(1)

        # 5. Prix
        event.tarif_raw, event.prix_min, event.prix_max, event.gratuit = self._parse_prix(text_cleaned)

        # 6. Lieu et ville - sur le texte nettoyé
        event.lieu_raw, event.ville_raw = self._extract_lieu_ville(text_cleaned)

        # 7. Nom de l'événement
        if event_name_from_slash:
            event.nom = event_name_from_slash
        else:
            event.nom = self._extract_nom(text, event)

        # 8. Type d'événement
        event.type_evenement = self._deduce_type(event)

        # 9. Calculer la confidence
        event.confidence = self._calculate_confidence(event)

        return event

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Convertit une date relative en date absolue."""
        if not self.bidul_mois or not self.bidul_annee:
            return None

        match = re.search(r"(\d{1,2})", date_str)
        if match:
            jour = int(match.group(1))
            try:
                return date(self.bidul_annee, self.bidul_mois, jour)
            except ValueError:
                return None
        return None

    def _extract_artistes(self, text: str) -> list[ArtisteInfo]:
        """
        Extrait les noms d'artistes avec leurs genres associés.

        Patterns reconnus:
        - ARTISTE (genre)
        - ARTISTE1 + ARTISTE2 (genre commun ou individuel)
        - "spectacle" ARTISTE (genre)
        - DJ XXX
        - Noms composés: BUTCHER and STONE, DR BONES & THE BLUE ROOTS
        - "par la Cie XXX" ou "par la compagnie XXX" ou "par XXX"
        - "avec la Cie XXX"

        Style individuel vs global:
        - "A (rock) + B (jazz)" → chacun garde son style
        - "A + B + C (rock)" → rock s'applique à tous
        """
        artistes = []

        # 0. Chercher d'abord les patterns "par la Cie XXX" dans le texte complet
        # (avant de le réduire à la zone artiste)
        par_cie_artistes = self._extract_par_cie_pattern(text)

        # Chercher les patterns ARTISTE1 + ARTISTE2
        # D'abord, isoler la partie avant le lieu (avant la virgule principale)
        parts = text.split(',')
        artiste_zone = parts[0].strip() if parts else text.strip()

        # Si la zone artiste est vide ou commence par une virgule, pas d'artiste
        if not artiste_zone:
            return par_cie_artistes if par_cie_artistes else []

        # Vérifier si la zone artiste est en fait un lieu connu
        from core.normalizer import normalize_lieu
        lieu_id, _ = normalize_lieu(artiste_zone.split(',')[0].strip())
        if lieu_id is not None:
            return par_cie_artistes if par_cie_artistes else []

        # Nettoyer le texte des préfixes d'événements
        ignore_prefixes = [
            r'^concert\s+spécial\s+\w+\s*:\s*',
            r'^soirée\s+[\w\s]+avec\s+',
            r'^les\s+spectaculaires\s*:\s*',
            r'^esc\s+exp\s+#?\d+\s+\w+\s*:\s*',
            r'^alpa\s+on\s+the\s+rock\s+#?\d+\s*:\s*',
            r'^melting\s+rock\s+avec\s+',
            r'^carte\s+blanche\s+à\s+',
        ]
        for prefix in ignore_prefixes:
            artiste_zone = re.sub(prefix, '', artiste_zone, flags=re.IGNORECASE)

        # Chercher un spectacle présentateur (ex: "Merci Connasse présente")
        spectacle_presenter = None
        presenter_match = re.search(r'([^,]+?)\s+présente\s+', artiste_zone, re.IGNORECASE)
        if presenter_match:
            spectacle_presenter = presenter_match.group(1).strip()
            artiste_zone = artiste_zone[presenter_match.end():]

        # Protéger les noms composés avec "and", "&", "THE"
        # On remplace temporairement les espaces par des underscores
        composed_names = [
            r'\bBUTCHER\s+and\s+STONE\b',
            r'\bDR\s+BONES\s*&\s*THE\s+BLUE\s+ROOTS\b',
            r'\bFRANCOIS\s+HADJI[- ]?LAZARO\s*&\s*PIGALE\b',
            r'\bDYNAMIC\s+SOUND\s+STATION\b',
            r'\b(\w+)\s+and\s+THE\s+(\w+)\b',  # Pattern générique X and THE Y
            r'\b(\w+)\s*&\s*THE\s+(\w+)\b',    # Pattern générique X & THE Y
        ]

        artiste_zone_protected = artiste_zone
        for pattern in composed_names:
            def protect(m):
                return m.group(0).replace(' ', '_').replace('&', '_AND_')
            artiste_zone_protected = re.sub(pattern, protect, artiste_zone_protected, flags=re.IGNORECASE)

        # Séparer par + en conservant les genres
        segments = re.split(r'\s*\+\s*', artiste_zone_protected)

        # Premier passage: extraire tous les artistes avec leurs genres individuels
        temp_artistes = []
        for segment in segments:
            # Restaurer les espaces dans les noms composés
            segment = segment.replace('_AND_', ' & ').replace('_', ' ').strip()
            if not segment:
                continue

            # Pattern DJ XXX
            dj_match = re.match(r'^(Dj\s+[A-Za-zÀ-ÿ0-9\s]+?)(?:\s*\(([^)]+)\))?(?:\s*$|,)', segment, re.IGNORECASE)
            if dj_match:
                nom = dj_match.group(1).strip()
                genre = dj_match.group(2).strip() if dj_match.group(2) else None
                temp_artistes.append(ArtisteInfo(
                    nom=nom.upper() if nom.upper().startswith('DJ') else _normalize_artist_name(nom),
                    genre=genre,
                    spectacle=spectacle_presenter
                ))
                continue

            # Chercher le pattern: ARTISTE (genre) ou "spectacle" ARTISTE (genre)
            # Le genre peut contenir des espaces: (rock progressif), (dj set techno)
            # Le nom peut commencer par un chiffre (100 ONCES, 2 MANY DJS, etc.)
            match = re.match(
                r'^(?:[""«][^""»]+[""»]\s*)?'  # Optionnel: spectacle entre guillemets
                r'((?:\d+\s+)?[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-&0-9]*?)'  # Nom artiste (peut commencer par chiffre)
                r'(?:\s*\(([^)]+)\))?'  # Optionnel: (genre)
                r'(?:\s*$|,)',  # Fin de segment
                segment
            )

            if match:
                nom = match.group(1).strip()
                genre = match.group(2).strip() if match.group(2) else None

                # Ignorer les faux positifs
                if len(nom) >= 3 and nom not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET', 'EN'):
                    temp_artistes.append(ArtisteInfo(
                        nom=_normalize_artist_name(nom),
                        genre=genre,
                        spectacle=spectacle_presenter
                    ))
            else:
                # Fallback: chercher les mots en majuscules
                matches = self.ARTISTE_PATTERN.findall(segment)
                genre_match = self.GENRE_PATTERN.search(segment)
                genre = genre_match.group(1).strip() if genre_match else None

                for m in matches:
                    nom = m.strip()
                    if len(nom) >= 3 and nom not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET', 'EN'):
                        temp_artistes.append(ArtisteInfo(
                            nom=_normalize_artist_name(nom),
                            genre=genre,
                            spectacle=spectacle_presenter
                        ))

        # Deuxième passage: gérer le style global vs individuel
        # Règle: Si le DERNIER artiste a un style et que des artistes PRÉCÉDENTS
        # n'en ont pas, c'est un style global qui s'applique à tous sans style.
        # Exception: si plusieurs artistes ont chacun leur propre style, on ne propage pas.
        if temp_artistes:
            # Compter les artistes avec/sans style
            artistes_with_style = [a for a in temp_artistes if a.genre]
            artistes_without_style = [a for a in temp_artistes if not a.genre]

            # Cas style global: le dernier artiste a un style, d'autres n'en ont pas
            # ET pas plus d'un style unique parmi tous les artistes
            if (len(artistes_with_style) == 1 and
                artistes_with_style[0] == temp_artistes[-1] and
                artistes_without_style):
                # C'est un style global - l'appliquer à tous
                global_style = artistes_with_style[0].genre
                for a in temp_artistes:
                    if a.genre is None:
                        a.genre = global_style
                    artistes.append(a)
            else:
                # Styles individuels - chaque artiste garde son propre style (ou None)
                artistes = temp_artistes

        # Ajouter les artistes "par la Cie" trouvés (s'ils ne sont pas déjà présents)
        if par_cie_artistes:
            existing_noms = {a.nom.lower() for a in artistes}
            for par_artiste in par_cie_artistes:
                if par_artiste.nom.lower() not in existing_noms:
                    artistes.append(par_artiste)

        return artistes

    def _extract_par_cie_pattern(self, text: str) -> list[ArtisteInfo]:
        """
        Extrait les artistes depuis les patterns "par la Cie XXX", "par XXX", "avec la Cie XXX".

        Patterns reconnus:
        - "par la Cie XXX" ou "par la compagnie XXX"
        - "par XXX" (ex: "par Béatrice Maine")
        - "avec la Cie XXX"
        - "par le chœur XXX"
        """
        artistes = []

        # Patterns pour "par la Cie" et variantes
        par_patterns = [
            # "par la Cie Théâtre d'Air" → "Cie Théâtre d'Air"
            (r'par\s+la\s+[Cc]ie\s+([^,\(\)]+?)(?:\s*,|\s*\(|$)', 'Cie '),
            # "par la compagnie XXX"
            (r'par\s+la\s+[Cc]ompagnie\s+([^,\(\)]+?)(?:\s*,|\s*\(|$)', 'Cie '),
            # "par la Cie "demain c'est dimanche""
            (r'par\s+la\s+[Cc]ie\s+"([^"]+)"', 'Cie '),
            # "par Béatrice Maine" (nom propre)
            (r'par\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç]+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç]+)+)(?:\s*,|\s*\(|$)', ''),
            # "par le chœur d'Orphée"
            (r'par\s+le\s+chœur\s+([^,\(\)]+?)(?:\s*,|\s*\(|$)', 'Chœur '),
            # "par le collectif XXX"
            (r'par\s+le\s+collectif\s+([^,\(\)]+?)(?:\s*,|\s*\(|$)', 'Collectif '),
        ]

        for pattern, prefix in par_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                nom = match.strip()
                if nom and len(nom) > 2:
                    # Éviter les faux positifs
                    skip_words = ['résa', 'réservation', 'issue', 'le bidul', 'tarif']
                    if not any(skip in nom.lower() for skip in skip_words):
                        full_nom = f"{prefix}{nom}" if prefix else nom
                        artistes.append(ArtisteInfo(
                            nom=_normalize_artist_name(full_nom),
                            genre=None,
                            spectacle=None
                        ))

        # Patterns "avec la Cie XXX"
        avec_patterns = [
            # avec la Cie "demain c'est dimanche"
            (r'avec\s+la\s+[Cc]ie\s+"([^"]+)"', 'Cie '),
            # avec LES MOYENS DU BORD (majuscules = artiste)
            (r'avec\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\']+?)(?:\s*\(|\s*et\s|\s*,|$)', ''),
        ]

        for pattern, prefix in avec_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                nom = match.strip()
                if nom and len(nom) > 2:
                    # Vérifier qu'il est en majuscules ou qu'on ajoute le préfixe Cie
                    if prefix or nom.upper() == nom:
                        # Vérifier que ce n'est pas déjà ajouté
                        full_nom = f"{prefix}{nom}" if prefix else nom
                        if not any(a.nom.lower() == full_nom.lower() for a in artistes):
                            artistes.append(ArtisteInfo(
                                nom=_normalize_artist_name(full_nom),
                                genre=None,
                                spectacle=None
                            ))

        return artistes

    def _parse_prix(self, text: str) -> tuple[Optional[str], Optional[float], Optional[float], bool]:
        """Parse le prix depuis le texte."""
        match = self.PRIX_PATTERN.search(text)
        if not match:
            return None, None, None, False

        raw = match.group(0)

        # Gratuit
        if match.group(6):
            gratuit_text = match.group(6).lower()
            if any(g in gratuit_text for g in ['gratuit', 'libre', 'chapeau', '0']):
                return raw, None, None, True
            return raw, None, None, False

        # Prix unique
        if match.group(1):
            prix = float(match.group(1).replace(',', '.'))
            return raw, prix, prix, False

        # Prix min/max (format X/Y ou X-Y)
        if match.group(2) and match.group(3):
            prix_min = float(match.group(2))
            prix_max = float(match.group(3))
            return raw, min(prix_min, prix_max), max(prix_min, prix_max), False

        if match.group(4) and match.group(5):
            prix_min = float(match.group(4))
            prix_max = float(match.group(5))
            return raw, min(prix_min, prix_max), max(prix_min, prix_max), False

        return raw, None, None, False

    def _extract_lieu_ville(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extrait le lieu et la ville du texte.

        Utilise les référentiels pour distinguer lieu et ville:
        - Si un candidat est dans lieu_ref → c'est un lieu
        - Si un candidat est dans ville_ref → c'est une ville
        - Privilégie les villes explicites (non-Le Mans) quand trouvées
        """
        # Import lazy pour éviter les imports circulaires
        from core.normalizer import normalize_lieu, normalize_ville

        # Normaliser d'abord les abréviations de villes dans le texte
        text_normalized = self._normalize_ville_abbreviations(text)

        # Le lieu est généralement après les artistes et avant l'heure
        # Format typique: ARTISTE (genre), Lieu, Ville, 20h, 10€
        # Ou après extraction spectacle: Lieu, Ville, 20h

        # Simplification: chercher les segments entre virgules
        parts = [p.strip() for p in text_normalized.split(',')]

        candidates = []

        # Déterminer l'index de départ:
        # - Si le premier segment est un lieu connu, commencer à 0
        # - Si le premier segment contient un artiste (MAJUSCULES), commencer à 1
        # - Sinon (texte nettoyé après spectacle), commencer à 0
        start_idx = 0
        if parts:
            first_part = parts[0].strip()
            # Vérifier d'abord si c'est un lieu connu
            lieu_id, _ = normalize_lieu(first_part)
            if lieu_id is not None:
                start_idx = 0  # C'est un lieu, commencer à 0
            elif self.ARTISTE_PATTERN.match(first_part):
                start_idx = 1  # C'est un artiste, commencer à 1

        # Collecter les candidats lieu/ville
        for part in parts[start_idx:]:
            if not part:
                continue

            # Ignorer si c'est une heure ou un prix
            if self.HEURE_PATTERN.search(part) or self.PRIX_PATTERN.search(part):
                continue

            # Ignorer les genres seuls entre parenthèses
            if re.match(r'^\([^)]+\)$', part):
                continue

            # Ignorer "par Cie X" (indicateur de compagnie, pas lieu)
            if part.lower().startswith('par '):
                continue

            # Ignorer les compagnies/artistes avec genre entre parenthèses
            # Pattern: "Nom (genre)" où genre indique un type de spectacle
            if re.search(r'\((?:th\.|théâtre|cirque|humour|one.?man|conte|danse|piano|sp\.|musique|chant|magie|music.?hall|stand.?up|spectacle)', part, re.IGNORECASE):
                continue

            # Ignorer les compagnies explicites: "Cie X", "Compagnie X", "collectif X"
            if re.match(r'^(?:cie|compagnie|collectif|groupe)\s+', part, re.IGNORECASE):
                continue

            # Ignorer les segments trop longs (probablement description)
            if len(part) > 50:
                continue

            candidates.append(part)
            if len(candidates) >= 4:  # Max 4 candidats
                break

        if not candidates:
            return None, None

        # Classifier chaque candidat en utilisant les référentiels
        lieu = None
        ville = None
        villes_trouvees = []  # Collecter toutes les villes trouvées

        for candidate in candidates:
            # Vérifier si c'est un lieu connu
            lieu_id, lieu_norm = normalize_lieu(candidate)
            if lieu_id is not None:
                if lieu is None:
                    lieu = candidate
                continue

            # Vérifier si c'est une ville connue
            ville_id, ville_norm = normalize_ville(candidate)
            if ville_id is not None:
                villes_trouvees.append({
                    'id': ville_id,
                    'nom': ville_norm,
                    'raw': candidate,
                    'is_lemans': ville_norm.lower() == 'le mans'
                })
                continue

            # Candidat inconnu:
            # - Si pas encore de lieu, l'attribuer comme lieu (candidat inconnu = lieu probable)
            if lieu is None:
                lieu = candidate

        # Sélectionner la ville: privilégier les villes non-Le Mans
        if villes_trouvees:
            non_lemans = [v for v in villes_trouvees if not v['is_lemans']]
            if non_lemans:
                # Prendre la ville non-Le Mans (priorité à la première trouvée)
                ville = non_lemans[0]['nom']
            else:
                # Seulement Le Mans trouvé
                ville = villes_trouvees[0]['nom']

        return lieu, ville

    def _normalize_ville_abbreviations(self, text: str) -> str:
        """
        Normalise les abréviations de villes dans le texte.

        Exemples:
        - "Sablé s/Sarthe" → "Sablé-sur-Sarthe"
        - "La Ferté Bernard" → "La Ferté-Bernard"
        """
        normalizations = [
            (r'Sablé\s*s/?Sarthe', 'Sablé-sur-Sarthe'),
            (r'La\s+Ferté\s*Bernard', 'La Ferté-Bernard'),
            (r'Sargé-lès-Le\s*Mans', 'Sargé-lès-Le Mans'),
            (r'Yvré\s*l.Évêque', "Yvré-l'Évêque"),
            (r'Moncé-en-?\s*Belin', 'Moncé-en-Belin'),
            (r'St[\.\s]+Pavace', 'Saint-Pavace'),
            (r'St[\.\s]+Saturnin', 'Saint-Saturnin'),
            (r'Ste[\.\s]+Croix', 'Sainte-Croix'),
        ]

        result = text
        for pattern, replacement in normalizations:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    def _extract_nom(self, text: str, event: ParsedEvent) -> Optional[str]:
        """
        Extrait le nom de l'événement.

        IMPORTANT: La colonne evenement.nom ne doit être remplie QUE pour les
        événements nommés (festivals, soirées thématiques). Les spectacles entre
        guillemets vont UNIQUEMENT dans contenu_evenement.nom_spectacle.

        Événements nommés → remplir evenement.nom:
        - "Alpa On The Rock #13"
        - "Esc Exp #21 TERIAKI"
        - "Melting Rock"
        - "Festival X"

        PAS événements nommés → evenement.nom = NULL:
        - Spectacles entre guillemets: "L'itinérance de Maud"
        - Concerts d'artistes: MENDELSON (poème rock)
        """
        # Utiliser la fonction is_named_event() pour déterminer si on doit
        # remplir evenement.nom
        event_name = extract_event_name(text)
        if event_name:
            return event_name

        # Pour les concerts/spectacles simples, NE PAS remplir evenement.nom
        # Les spectacles sont déjà stockés dans contenu_evenement.nom_spectacle
        return None

    def _deduce_type(self, event: ParsedEvent) -> Optional[str]:
        """Déduit le type d'événement depuis les indices."""
        text_lower = event.raw_text.lower()
        genres_lower = ' '.join(event.genres_raw).lower()

        # Spectacle vivant
        if any(kw in text_lower or kw in genres_lower for kw in ['théâtre', 'theatre', 'danse', 'cirque', 'conte', 'marionnette']):
            if 'danse' in text_lower or 'danse' in genres_lower:
                return 'danse'
            if 'cirque' in text_lower or 'cirque' in genres_lower:
                return 'cirque'
            return 'theatre'

        # Humour
        if any(kw in text_lower or kw in genres_lower for kw in ['humour', 'stand-up', 'standup', 'one man show', 'one woman show']):
            return 'humour'

        # DJ / Electro
        if any(kw in text_lower or kw in genres_lower for kw in ['dj', 'electro', 'techno', 'house']):
            return 'dj_set'

        # Expo
        if any(kw in text_lower for kw in ['exposition', 'vernissage', 'expo']):
            return 'exposition'

        # Conférence
        if any(kw in text_lower for kw in ['conférence', 'conference', 'débat', 'debat']):
            return 'conference'

        # Par défaut: concert (si on a des artistes)
        if event.artistes:
            return 'concert'

        return None

    def _calculate_confidence(self, event: ParsedEvent) -> float:
        """Calcule un score de confiance pour l'extraction."""
        score = 0.3  # Base

        # Bonus pour chaque champ trouvé
        if event.date_str:
            score += 0.1
        if event.heure:
            score += 0.1
        if event.lieu_raw:
            score += 0.15
        if event.artistes:
            score += 0.15
        if event.tarif_raw:
            score += 0.1
        if event.type_evenement:
            score += 0.1

        return min(1.0, score)


# Test standalone
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    test_text = """Samedi 20
• Festival culturel d'Outre-Mer #9 (concerts) // NATANJA (reggae) + SEHYO (zouk), Centre des Etangs-Chauds, 11h-1h, 0 €
• FABIENNE GUYONS (jazz), Boire du Bon, Saint-Pavace, 20h, 10 €
• "Ex Ovo" Cie Le grand Raymond (cirque), Chapiteau plongeoir, 20h30, 4/8€
Dimanche 21
• JAM ST CO MUSICOS (jam session), Le Zoo, 21h, au chapeau
"""

    parser = EventParser(bidul_mois=5, bidul_annee=2023)
    events = parser.parse(test_text)

    print(f"Événements trouvés: {len(events)}\n")
    for e in events:
        print(f"Date: {e.date_str}")
        print(f"Artistes: {e.artistes}")
        print(f"Genres: {e.genres_raw}")
        print(f"Lieu: {e.lieu_raw}, Ville: {e.ville_raw}")
        print(f"Heure: {e.heure}, Prix: {e.tarif_raw}")
        print(f"Type: {e.type_evenement}")
        print(f"Confidence: {e.confidence}")
        print(f"Raw: {e.raw_text[:100]}...")
        print("---")

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

logger = logging.getLogger(__name__)


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

    # Artistes (JSON array)
    artistes: list[str] = field(default_factory=list)

    # Spectacles (noms entre guillemets)
    spectacles: list[str] = field(default_factory=list)

    # Genres (texte entre parenthèses)
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
    JOURS = r"(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)"
    DATE_PATTERN = re.compile(rf"^({JOURS})\s+(\d{{1,2}})\s*$", re.MULTILINE)

    # Pattern pour les bullets (• ou caractères similaires)
    BULLET_CHARS = r"[•●○◦▪▫■□►▸‣⁃\uf071]"

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

    def parse(self, text: str) -> list[ParsedEvent]:
        """
        Parse le texte complet et extrait les événements.

        Args:
            text: Texte brut extrait du PDF

        Returns:
            Liste d'événements parsés (dédoublonnés)
        """
        events = []
        seen_signatures = set()  # Pour dédoublonner

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
                    # Créer une signature pour dédoublonner
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
        return [p.strip() for p in parts if p.strip()]

    def _parse_event(self, text: str, date_str: Optional[str]) -> Optional[ParsedEvent]:
        """Parse un texte d'événement individuel."""
        if not text:
            return None

        event = ParsedEvent(raw_text=text)

        # Date
        if date_str:
            event.date_str = date_str
            event.date_evenement = self._parse_date(date_str)

        # Spectacles (entre guillemets) - extraire en premier
        spectacles = self.SPECTACLE_PATTERN.findall(text)
        event.spectacles = [s.strip() for s in spectacles if s.strip()]

        # Genres (entre parenthèses)
        genres = self.GENRE_PATTERN.findall(text)
        event.genres_raw = [g.strip() for g in genres if g.strip() and len(g) < 50]

        # Artistes (MAJUSCULES)
        artistes = self._extract_artistes(text)
        event.artistes = artistes

        # Heure
        heure_match = self.HEURE_PATTERN.search(text)
        if heure_match:
            event.heure = heure_match.group(1)

        # Prix
        event.tarif_raw, event.prix_min, event.prix_max, event.gratuit = self._parse_prix(text)

        # Lieu et ville - généralement avant l'heure
        event.lieu_raw, event.ville_raw = self._extract_lieu_ville(text)

        # Nom de l'événement
        event.nom = self._extract_nom(text, event)

        # Type d'événement
        event.type_evenement = self._deduce_type(event)

        # Calculer la confidence
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

    def _extract_artistes(self, text: str) -> list[str]:
        """Extrait les noms d'artistes du texte."""
        artistes = []

        # Chercher les patterns ARTISTE1 + ARTISTE2
        # D'abord, isoler la partie avant le lieu (avant la virgule principale)
        parts = text.split(',')
        artiste_zone = parts[0] if parts else text

        # Séparer par +
        for segment in re.split(r'\s*\+\s*', artiste_zone):
            # Chercher les mots en majuscules
            matches = self.ARTISTE_PATTERN.findall(segment)
            for match in matches:
                # Nettoyer
                artiste = match.strip()
                # Ignorer les mots trop courts ou les faux positifs
                if len(artiste) >= 3 and artiste not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET', 'EN'):
                    artistes.append(artiste)

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
        """Extrait le lieu et la ville du texte."""
        # Le lieu est généralement après les artistes et avant l'heure
        # Format typique: ARTISTE (genre), Lieu, Ville, 20h, 10€

        # Simplification: chercher les segments entre virgules
        parts = [p.strip() for p in text.split(',')]

        lieu = None
        ville = None

        # Parcourir les segments pour trouver lieu et ville
        for i, part in enumerate(parts[1:], 1):  # Skip le premier (artistes)
            # Ignorer si c'est une heure ou un prix
            if self.HEURE_PATTERN.search(part) or self.PRIX_PATTERN.search(part):
                continue

            # Ignorer les segments trop longs (probablement description)
            if len(part) > 50:
                continue

            # Premier candidat = lieu
            if lieu is None:
                lieu = part
            # Deuxième candidat = ville (si différent du lieu)
            elif ville is None and part != lieu:
                ville = part
                break

        return lieu, ville

    def _extract_nom(self, text: str, event: ParsedEvent) -> Optional[str]:
        """Extrait ou génère le nom de l'événement."""
        # Si on a un spectacle entre guillemets, c'est le nom
        if event.spectacles:
            return event.spectacles[0]

        # Sinon, si on a un festival (pattern "Festival X" ou "X #N")
        festival_match = re.search(r"([A-Za-zÀ-ÿ\s]+(?:#\d+|\d+))", text)
        if festival_match and 'festival' in text.lower():
            return festival_match.group(1).strip()

        # Sinon, utiliser le premier artiste
        if event.artistes:
            return None  # Pas de nom spécifique, juste le(s) artiste(s)

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

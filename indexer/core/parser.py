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
    # Supporte: "Samedi 20", "LUNDI 1ER", "Mardi 2", etc.
    JOURS = r"(?:[Ll]undi|[Mm]ardi|[Mm]ercredi|[Jj]eudi|[Vv]endredi|[Ss]amedi|[Dd]imanche|LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE)"
    DATE_PATTERN = re.compile(rf"^({JOURS})\s+(\d{{1,2}})(?:ER|er)?\s*$", re.MULTILINE)

    # Pattern pour les bullets (• ou caractères similaires)
    BULLET_CHARS = r"[•●○◦▪▫■□►▸‣⁃\uf071\uf0b6]"

    # Pattern pour détecter un nouveau événement dans un texte multi-événements
    # Un nouvel événement commence par: bullet OU (retour ligne + artiste en MAJUSCULES)
    MULTI_EVENT_SPLIT = re.compile(
        r'(?:\n\s*[•●○◦▪▫■□►▸‣⁃\uf071\uf0b6]\s*)|'  # Bullet sur nouvelle ligne
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

    def _parse_event(self, text: str, date_str: Optional[str]) -> Optional[ParsedEvent]:
        """Parse un texte d'événement individuel."""
        if not text:
            return None

        event = ParsedEvent(raw_text=text)

        # Date
        if date_str:
            event.date_str = date_str
            event.date_evenement = self._parse_date(date_str)

        # 1. Spectacles (entre guillemets) - extraire EN PREMIER
        # Les virgules à l'intérieur des guillemets sont protégées
        spectacles_with_genre, text_cleaned = self._extract_spectacles_with_genre(text)
        event.spectacles = [s['nom'] for s in spectacles_with_genre]

        # Genres extraits des spectacles
        spectacle_genres = [s['genre'] for s in spectacles_with_genre if s.get('genre')]

        # 2. Artistes (MAJUSCULES) - sur le texte nettoyé
        artistes = self._extract_artistes(text_cleaned)
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
        - ARTISTE1 + ARTISTE2 (genre commun)
        - "spectacle" ARTISTE (genre)
        """
        artistes = []

        # Chercher les patterns ARTISTE1 + ARTISTE2
        # D'abord, isoler la partie avant le lieu (avant la virgule principale)
        parts = text.split(',')
        artiste_zone = parts[0] if parts else text

        # Chercher un spectacle présentateur (ex: "Merci Connasse présente")
        spectacle_presenter = None
        presenter_match = re.search(r'([^,]+?)\s+présente\s+', artiste_zone, re.IGNORECASE)
        if presenter_match:
            spectacle_presenter = presenter_match.group(1).strip()
            # Retirer le présentateur de la zone artiste pour le parsing
            artiste_zone = artiste_zone[presenter_match.end():]

        # Séparer par + en conservant les genres qui suivent
        # Pattern: NOM (genre) ou NOM
        segments = re.split(r'\s*\+\s*', artiste_zone)

        # Premier passage: extraire tous les artistes avec leurs genres individuels
        temp_artistes = []
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            # Chercher le pattern: ARTISTE (genre)
            match = re.match(
                r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-&0-9]*?)(?:\s*\(([^)]+)\))?(?:\s*$|,)',
                segment
            )

            if match:
                nom = match.group(1).strip()
                genre = match.group(2).strip() if match.group(2) else None

                # Ignorer les faux positifs
                if len(nom) >= 3 and nom not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET', 'EN'):
                    temp_artistes.append(ArtisteInfo(
                        nom=nom,
                        genre=genre,
                        spectacle=spectacle_presenter
                    ))
            else:
                # Fallback: chercher les mots en majuscules
                matches = self.ARTISTE_PATTERN.findall(segment)
                # Chercher un genre après
                genre_match = self.GENRE_PATTERN.search(segment)
                genre = genre_match.group(1).strip() if genre_match else None

                for m in matches:
                    nom = m.strip()
                    if len(nom) >= 3 and nom not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET', 'EN'):
                        temp_artistes.append(ArtisteInfo(
                            nom=nom,
                            genre=genre,
                            spectacle=spectacle_presenter
                        ))

        # Deuxième passage: propager le genre partagé si un seul genre pour plusieurs artistes
        # Ex: "A + B (rock)" → A et B ont le genre "rock"
        if temp_artistes:
            # Trouver le dernier genre défini (souvent partagé)
            shared_genre = None
            for a in reversed(temp_artistes):
                if a.genre:
                    shared_genre = a.genre
                    break

            # Appliquer le genre partagé aux artistes sans genre
            for a in temp_artistes:
                if a.genre is None and shared_genre:
                    a.genre = shared_genre
                artistes.append(a)

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
        - Si pas de ville trouvée → défaut "Le Mans"
        """
        # Import lazy pour éviter les imports circulaires
        from core.normalizer import normalize_lieu, normalize_ville

        # Le lieu est généralement après les artistes et avant l'heure
        # Format typique: ARTISTE (genre), Lieu, Ville, 20h, 10€
        # Ou après extraction spectacle: Lieu, Ville, 20h

        # Simplification: chercher les segments entre virgules
        parts = [p.strip() for p in text.split(',')]

        candidates = []

        # Déterminer l'index de départ:
        # - Si le premier segment contient un artiste (MAJUSCULES), commencer à 1
        # - Sinon (texte nettoyé après spectacle), commencer à 0
        start_idx = 0
        if parts and self.ARTISTE_PATTERN.match(parts[0]):
            start_idx = 1

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
            if len(candidates) >= 3:  # Max 3 candidats
                break

        if not candidates:
            return None, None

        # Classifier chaque candidat en utilisant les référentiels
        lieu = None
        ville = None

        for candidate in candidates:
            # Vérifier si c'est un lieu connu
            lieu_id, lieu_norm = normalize_lieu(candidate)
            if lieu_id is not None:
                if lieu is None:
                    lieu = candidate
                continue

            # Vérifier si c'est une ville connue
            ville_id, ville_norm = normalize_ville(candidate)
            if ville_id is not None and ville_norm.lower() != 'le mans':
                # C'est une ville connue (autre que Le Mans par défaut)
                if ville is None:
                    ville = candidate
                continue

            # Candidat inconnu:
            # - Si pas encore de lieu, l'attribuer comme lieu (candidat inconnu = lieu probable)
            # - NE PAS attribuer comme ville si non reconnu (éviter les faux positifs)
            if lieu is None:
                lieu = candidate
            # Note: on n'attribue pas les candidats inconnus comme ville
            # La ville sera "Le Mans" par défaut si non trouvée

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

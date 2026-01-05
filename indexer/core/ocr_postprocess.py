"""
Post-traitement du texte OCR avec dictionnaires de référence.

Corrige les erreurs OCR courantes en utilisant:
- Les lieux connus du référentiel
- Les villes connues
- Les artistes extraits des événements existants
- Des patterns de correction courants
"""

import re
import sqlite3
import logging
from pathlib import Path
from difflib import SequenceMatcher
from typing import Optional

from core.text_cleaner import fix_ocr_day_prefixes

logger = logging.getLogger(__name__)

# Chemin par défaut vers la base
DEFAULT_DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"


class OCRPostProcessor:
    """Corrige les erreurs OCR courantes en utilisant les dictionnaires existants."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le post-processeur.

        Args:
            db_path: Chemin vers la base SQLite (défaut: database/bidul_archives.db)
        """
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        self.known_lieux: set[str] = set()
        self.known_villes: set[str] = set()
        self.known_artistes: set[str] = set()
        self._load_references()

    def _load_references(self):
        """Charge les références depuis la base de données."""
        if not Path(self.db_path).exists():
            logger.warning(f"Base de données non trouvée: {self.db_path}")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            # Charger les lieux
            cur.execute('SELECT nom FROM lieu_ref')
            self.known_lieux = {row[0] for row in cur.fetchall() if row[0]}

            # Charger les villes
            cur.execute('SELECT nom FROM ville_ref')
            self.known_villes = {row[0] for row in cur.fetchall() if row[0]}

            # Charger les artistes uniques depuis les événements existants
            cur.execute('''
                SELECT DISTINCT artiste FROM contenu_evenement
                WHERE artiste IS NOT NULL AND artiste != ''
            ''')
            self.known_artistes = {row[0] for row in cur.fetchall() if row[0]}

            conn.close()

            logger.info(
                f"Références chargées: {len(self.known_lieux)} lieux, "
                f"{len(self.known_villes)} villes, {len(self.known_artistes)} artistes"
            )

        except Exception as e:
            logger.error(f"Erreur chargement références: {e}")

    def process(self, text: str) -> str:
        """
        Pipeline complet de post-traitement OCR.

        Args:
            text: Texte brut issu de l'OCR

        Returns:
            Texte nettoyé et corrigé
        """
        if not text:
            return text

        # 1. Corrections OCR de base
        text = self._fix_common_ocr_errors(text)

        # 2. Correction des jours de semaine OCR corrompus
        # Ex: "e 05:" → "Je 05:", "'e 06:" → "Ve 06:", "ja 07:" → "Sa 07:"
        text = fix_ocr_day_prefixes(text)

        # 3. Normalisation du formatage
        text = self._normalize_formatting(text)

        # 4. Correction des entités connues
        text = self._fix_entities(text)

        return text

    def _fix_common_ocr_errors(self, text: str) -> str:
        """Corrige les erreurs OCR les plus courantes."""

        # Corrections caractère par caractère (dans le contexte)
        replacements = [
            # Confusion lettres/chiffres fréquentes
            (r'\b1e\b', 'le'),
            (r'\b1a\b', 'la'),
            (r'\bIe\b', 'le'),
            (r'\bIa\b', 'la'),

            # Heures
            (r'(\d{1,2})h3O', r'\1h30'),
            (r'(\d{1,2})hOO', r'\1h00'),
            (r'(\d{1,2})h0O', r'\1h00'),
            (r'(\d{1,2})hO0', r'\1h00'),
            (r'(\d{1,2})H(\d{2})', r'\1h\2'),  # 20H30 → 20h30

            # Multiples espaces (mais préserver les newlines)
            (r'[^\S\n]+', ' '),  # Espaces multiples → un seul espace
            (r'\n{3,}', '\n\n'),  # Plus de 2 newlines → 2 newlines

            # Ponctuation
            (r'\s+,', ','),
            (r'\s+\.', '.'),
            (r'\s+;', ';'),
            (r'\s+:', ':'),
        ]

        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)

        # Remplacements de caractères simples (sans regex)
        char_replacements = {
            '«': '"',
            '»': '"',
            '„': '"',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '—': '-',
            '–': '-',
            '\u00ad': '',  # Soft hyphen
            '®': '',
            '™': '',
            '©': '',
            '1€': '1 €',
            'l€': '1 €',
            'O€': '0 €',
        }
        for old, new in char_replacements.items():
            text = text.replace(old, new)

        # Mots courants mal reconnus (case-insensitive avec préservation de la casse)
        word_fixes = {
            'théatre': 'théâtre',
            'theatre': 'théâtre',
            'Théatre': 'Théâtre',
            'Theatre': 'Théâtre',
            'fete': 'fête',
            'Fete': 'Fête',
            'musee': 'musée',
            'Musee': 'Musée',
            'ete': 'été',
            'cafe': 'café',
            'Cafe': 'Café',
            'cine': 'ciné',
            'Cine': 'Ciné',
            'entree': 'entrée',
            'gratuite': 'gratuite',
        }

        for wrong, correct in word_fixes.items():
            text = text.replace(wrong, correct)

        return text

    def _normalize_formatting(self, text: str) -> str:
        """Normalise le formatage du texte."""

        # Normaliser les jours de la semaine abrégés
        # "Sa 07" → "Sa 07", "Lu 15" → "Lu 15"
        days_pattern = r'\b([DLMJVS][aeiou])\s*(\d{1,2})\b'
        text = re.sub(days_pattern, r'\1 \2', text, flags=re.IGNORECASE)

        # Normaliser les heures
        # "20 h 30" → "20h30", "20 H 30" → "20h30"
        text = re.sub(r'(\d{1,2})\s*[hH]\s*(\d{2})', r'\1h\2', text)
        text = re.sub(r'(\d{1,2})\s*[hH]\s*$', r'\1h', text, flags=re.MULTILINE)

        # Normaliser les prix
        # "10 euros" → "10€", "10 €" → "10€"
        text = re.sub(r'(\d+(?:[,.]\d{2})?)\s*(?:euros?|EUR)', r'\1€', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+(?:[,.]\d{2})?)\s+€', r'\1€', text)

        # Gratuit / Libre
        text = re.sub(r'\bgratui[t]?\b', 'gratuit', text, flags=re.IGNORECASE)

        return text.strip()

    def _fix_entities(self, text: str) -> str:
        """
        Corrige les entités (lieux, villes) par fuzzy matching.

        Recherche les mots/groupes de mots qui ressemblent aux entités connues
        et les corrige si le match est suffisamment bon.
        Préserve la structure des lignes (newlines).
        """
        if not self.known_lieux and not self.known_villes:
            return text

        # Traiter ligne par ligne pour préserver les newlines
        lines = text.split('\n')
        corrected_lines = []

        for line in lines:
            words = line.split(' ')
            corrected_words = []

            i = 0
            while i < len(words):
                word = words[i]

                # Essayer de matcher des groupes de 2-3 mots d'abord (noms de lieux composés)
                matched = False

                for group_size in [3, 2]:
                    if i + group_size <= len(words):
                        group = ' '.join(words[i:i + group_size])
                        if len(group) > 6:  # Au moins 7 caractères pour les groupes
                            # Chercher dans les lieux
                            match = self._find_best_match(group, self.known_lieux, threshold=0.85)
                            if match:
                                corrected_words.append(match)
                                i += group_size
                                matched = True
                                break

                if matched:
                    continue

                # Si pas de match pour un groupe, essayer le mot seul
                if len(word) > 5:  # Au moins 6 caractères
                    # Priorité aux villes (plus court généralement)
                    match = self._find_best_match(word, self.known_villes, threshold=0.85)
                    if match:
                        corrected_words.append(match)
                        i += 1
                        continue

                corrected_words.append(word)
                i += 1

            corrected_lines.append(' '.join(corrected_words))

        return '\n'.join(corrected_lines)

    def _find_best_match(self, text: str, candidates: set[str], threshold: float = 0.8) -> Optional[str]:
        """
        Trouve le meilleur match par similarité dans un set de candidats.

        Args:
            text: Texte à matcher
            candidates: Ensemble des candidats possibles
            threshold: Seuil minimum de similarité (0-1)

        Returns:
            Meilleur candidat ou None si aucun match suffisant
        """
        if not candidates:
            return None

        best_match = None
        best_score = threshold

        text_lower = text.lower()

        for candidate in candidates:
            # Match exact (case-insensitive)
            if text_lower == candidate.lower():
                return candidate

            # Similarité partielle
            score = SequenceMatcher(None, text_lower, candidate.lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = candidate

        return best_match

    def suggest_corrections(self, text: str) -> list[tuple[str, str, float]]:
        """
        Suggère des corrections possibles sans les appliquer.

        Args:
            text: Texte à analyser

        Returns:
            Liste de tuples (original, suggestion, score)
        """
        suggestions = []
        words = text.split()

        for word in words:
            if len(word) < 5:
                continue

            # Chercher dans les lieux
            for lieu in self.known_lieux:
                if len(lieu) < 5:
                    continue
                score = SequenceMatcher(None, word.lower(), lieu.lower()).ratio()
                if 0.7 < score < 1.0:  # Proche mais pas exact
                    suggestions.append((word, lieu, score))

            # Chercher dans les villes
            for ville in self.known_villes:
                score = SequenceMatcher(None, word.lower(), ville.lower()).ratio()
                if 0.7 < score < 1.0:
                    suggestions.append((word, ville, score))

        # Trier par score décroissant
        suggestions.sort(key=lambda x: x[2], reverse=True)

        return suggestions[:20]  # Top 20


class DateNormalizer:
    """Normalise les dates extraites par OCR."""

    # Jours de la semaine (abréviations et noms complets)
    JOURS = {
        'lu': 'lundi', 'lun': 'lundi', 'lundi': 'lundi',
        'ma': 'mardi', 'mar': 'mardi', 'mardi': 'mardi',
        'me': 'mercredi', 'mer': 'mercredi', 'mercredi': 'mercredi',
        'je': 'jeudi', 'jeu': 'jeudi', 'jeudi': 'jeudi',
        'v': 'vendredi', 've': 'vendredi', 'ven': 'vendredi', 'vendredi': 'vendredi',
        'sa': 'samedi', 'sam': 'samedi', 'samedi': 'samedi',
        'di': 'dimanche', 'dim': 'dimanche', 'dimanche': 'dimanche',
    }

    # Mois
    MOIS = {
        'jan': 1, 'janv': 1, 'janvier': 1,
        'fev': 2, 'fév': 2, 'fevr': 2, 'février': 2, 'fevrier': 2,
        'mar': 3, 'mars': 3,
        'avr': 4, 'avril': 4,
        'mai': 5,
        'jun': 6, 'juin': 6,
        'jul': 7, 'juil': 7, 'juillet': 7,
        'aou': 8, 'août': 8, 'aout': 8,
        'sep': 9, 'sept': 9, 'septembre': 9,
        'oct': 10, 'octobre': 10,
        'nov': 11, 'novembre': 11,
        'dec': 12, 'déc': 12, 'décembre': 12, 'decembre': 12,
    }

    @classmethod
    def extract_dates(cls, text: str) -> list[dict]:
        """
        Extrait les dates du texte.

        Patterns reconnus:
        - "Sa 07" (jour abrégé + numéro)
        - "Samedi 7" (jour complet + numéro)
        - "7 janvier" (numéro + mois)
        - "07/01" (format numérique)

        Returns:
            Liste de dicts avec {jour_semaine, jour_num, mois}
        """
        dates = []

        # Pattern: jour abrégé/complet + numéro
        pattern1 = r'\b(' + '|'.join(cls.JOURS.keys()) + r')\s*(\d{1,2})\b'
        for match in re.finditer(pattern1, text, re.IGNORECASE):
            dates.append({
                'jour_semaine': cls.JOURS.get(match.group(1).lower()),
                'jour_num': int(match.group(2)),
                'raw': match.group(0)
            })

        # Pattern: numéro + mois
        pattern2 = r'\b(\d{1,2})\s*(' + '|'.join(cls.MOIS.keys()) + r')\b'
        for match in re.finditer(pattern2, text, re.IGNORECASE):
            dates.append({
                'jour_num': int(match.group(1)),
                'mois': cls.MOIS.get(match.group(2).lower()),
                'raw': match.group(0)
            })

        return dates


# Test standalone
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    processor = OCRPostProcessor()

    # Test avec un texte exemple
    test_text = """
    Sa 07 - THÉATRE du Paradis - Le Mans
    20h3O - Concert de musique 1ive
    Entrée gratuite

    Di O8 - Café de 1a Gare - Sab1é
    Jazz Session à 21hOO
    10€ ou 12 euros
    """

    print("=== Texte original ===")
    print(test_text)

    print("\n=== Texte corrigé ===")
    corrected = processor.process(test_text)
    print(corrected)

    print("\n=== Suggestions de corrections ===")
    suggestions = processor.suggest_corrections(test_text)
    for orig, sugg, score in suggestions[:10]:
        print(f"  '{orig}' → '{sugg}' ({score:.2f})")

    print("\n=== Dates extraites ===")
    dates = DateNormalizer.extract_dates(corrected)
    for d in dates:
        print(f"  {d}")

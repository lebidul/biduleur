"""
Détection des événements hors département (72 - Sarthe).

Stratégie de détection par ordre de priorité:
1. Code département (72) explicite → LOCAL
2. ville_raw est une ville sarthoise connue → LOCAL
3. lieu_raw contient "Le Mans" → LOCAL
4. Code département hors 72 → RÉGIONAL
5. Lieu connu hors Sarthe (Chabada, L'Ubu, etc.) → RÉGIONAL
6. Ville connue hors Sarthe → RÉGIONAL
7. Sinon → LOCAL par défaut
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


DEPT_LOCAL = '72'

DEPTS_REGIONAUX = {
    '14': 'Calvados',
    '28': 'Eure-et-Loir',
    '35': 'Ille-et-Vilaine',
    '37': 'Indre-et-Loire',
    '41': 'Loir-et-Cher',
    '44': 'Loire-Atlantique',
    '45': 'Loiret',
    '49': 'Maine-et-Loire',
    '50': 'Manche',
    '53': 'Mayenne',
    '61': 'Orne',
    '75': 'Paris',
    '85': 'Vendée',
    '92': 'Hauts-de-Seine',
    '93': 'Seine-Saint-Denis',
    '94': 'Val-de-Marne',
}

# Villes sarthoises (72)
VILLES_SARTHE = {
    'le mans', 'mans', 'allonnes', 'la flèche', 'la fleche', 'sablé', 'sable',
    'mamers', 'château-du-loir', 'chateau-du-loir', 'la ferté-bernard',
    'la ferte-bernard', 'coulaines', 'arnage', 'mulsanne', 'yvré-l\'évêque',
    'yvre-l\'eveque', 'changé', 'change', 'ruaudin', 'saint-saturnin',
    'st-saturnin', 'savigné-l\'évêque', 'ecommoy', 'connerré', 'bouloire',
    'montfort-le-gesnois', 'bessé-sur-braye', 'vibraye', 'bonnétable',
    'beaumont-sur-sarthe', 'fresnay-sur-sarthe', 'sillé-le-guillaume',
    'sillé le guillaume',
    'loué', 'conlie', 'ballon', 'saint-calais', 'st-calais', 'pontvallain',
    'le grand-lucé', 'grand-lucé', 'mayet', 'aubigné-racan', 'noyen-sur-sarthe',
    'malicorne-sur-sarthe', 'précigné', 'parcé-sur-sarthe', 'la suze-sur-sarthe',
    'guécélard', 'parigné-l\'évêque', 'moncé-en-belin', 'moncé en belin',
    'saint-jean-d\'assé', 'st-jean-d\'assé', 'roézé-sur-sarthe', 'fillé', 'spay',
    'la chapelle-saint-aubin', 'saint-pavace', 'st-pavace', 'rouillon',
    'saint-gervais-en-belin', 'champagné', 'le bailleul', 'neuville-sur-sarthe',
    'la milesse', 'saint-georges-du-bois', 'fay', 'courcemont', 'lombron',
    'la chartre-sur-le-loir', 'la chartre sur le loir', 'chartre-sur-le-loir',
    'montval-sur-loir', 'montval sur loir',
    'dangeul', 'saint-mars-la-brière', 'saint-mars la brière', 'st-mars-la-brière',
    'la fontaine-saint-martin', 'la fontaine saint martin',
    'marolles-les-braults', 'marolles les braults',
    'tuffé', 'tuffe', 'dollon', 'thorigné-sur-dué', 'thorigne-sur-due',
    'souligné-sous-ballon', 'souligné-flacé', 'la bazoge', 'cérans-foulletourte',
    'vouvray-sur-loir', 'laigné-en-belin', 'château-l\'hermitage',
    'brette-les-pins', 'volnay', 'saint-corneille', 'trangé', 'louailles',
    'st-michel-de-chavaignes', 'saint-michel-de-chavaignes',
}

DEPT_CODE_PATTERN = re.compile(r'\((\d{2})\)')

# Villes hors Sarthe
VILLES_HORS_SARTHE = {
    # Maine-et-Loire (49)
    'angers', 'cholet', 'saumur', 'avrillé', 'montigné-sur-moine', 'morannes', 'segré',
    # Mayenne (53)
    'laval', 'mayenne', 'château-gontier', 'evron', 'ernée',
    # Orne (61)
    'alençon', 'argentan', 'flers', "l'aigle", 'mortagne',
    # Loir-et-Cher (41)
    'vendôme', 'blois', 'romorantin', 'savigny-sur-braye',
    # Loire-Atlantique (44)
    'nantes', 'saint-nazaire', 'st-nazaire', 'st nazaire',
    # Ille-et-Vilaine (35)
    'rennes', 'saint-malo', 'st-malo', 'fougères', 'vitré',
    # Vendée (85)
    'la roche-sur-yon', 'montaigu', 'challans', 'fontenay-le-comte',
    # Manche (50)
    'coutances', 'cherbourg', 'saint-lô', 'granville', 'avranches',
    # Indre-et-Loire (37)
    'tours', 'amboise', 'chinon', 'loches',
    # Calvados (14)
    'caen', 'lisieux', 'bayeux', 'honfleur',
}

# Lieux connus hors Sarthe
LIEUX_HORS_SARTHE = {
    'le chabada': '49', 'chabada': '49', 'au chabada': '49',
    "l'ubu": '35', 'ubu': '35', "à l'ubu": '35',
    'le vip': '44', 'au vip': '44',
    'la coulée douce': '53', 'coulée douce': '53',
    'le kiosque': '53',
    'croque-lune café': '41', 'croque-lune': '41',
    'le noctambule': '85',
    'quai tabarly': '49',
    'le lieu unique': '44',
    'stéréolux': '44',
    'centre culturel de vendôme': '41',
    'repaire des bons vivants': '49',
    'la luciole': '61',
}

# Patterns de faux positifs pour Paris
PARIS_FALSE_POSITIVE_PATTERNS = [
    r'de\s+paris\b',
    r'd\'paris\b',
    r'\(paris\)',
    r'groupe\s+de\s+paris',
    r'paris\s+comedy',
    r'tatiana\s+paris',
    r'paris[,\s]+le\s+mans',
    r'parisien',
]

PARIS_FALSE_POSITIVE_RE = re.compile(
    '|'.join(PARIS_FALSE_POSITIVE_PATTERNS),
    re.IGNORECASE
)


@dataclass
class RegionalDetection:
    """Résultat de la détection régionale."""
    is_regional: bool
    reason: str
    dept_code: Optional[str] = None
    dept_name: Optional[str] = None


def detect_regional(raw_text: str, lieu_raw: Optional[str] = None,
                    ville_raw: Optional[str] = None) -> RegionalDetection:
    """
    Détecte si un événement est hors département.

    Args:
        raw_text: Texte brut de l'événement
        lieu_raw: Nom du lieu extrait
        ville_raw: Nom de la ville extraite

    Returns:
        RegionalDetection avec is_regional, reason, dept_code, dept_name
    """
    full_text = ' '.join(filter(None, [raw_text or '', lieu_raw or '', ville_raw or '']))
    full_text_lower = full_text.lower()

    # === PRIORITÉ 1: Code (72) explicite → LOCAL ===
    if '(72)' in full_text:
        return RegionalDetection(
            is_regional=False,
            reason="Code département (72) explicite",
            dept_code='72',
            dept_name='Sarthe'
        )

    # === PRIORITÉ 2: ville_raw sarthoise → LOCAL ===
    if ville_raw:
        ville_lower = ville_raw.lower().strip()
        for ville_sarthe in VILLES_SARTHE:
            if ville_sarthe in ville_lower or ville_lower in ville_sarthe:
                return RegionalDetection(
                    is_regional=False,
                    reason=f"Ville sarthoise: '{ville_raw}'",
                    dept_code='72',
                    dept_name='Sarthe'
                )

    # === PRIORITÉ 3: lieu_raw contient "Le Mans" → LOCAL ===
    if lieu_raw:
        lieu_lower = lieu_raw.lower()
        if 'le mans' in lieu_lower or 'mans' in lieu_lower:
            return RegionalDetection(
                is_regional=False,
                reason=f"Lieu au Mans: '{lieu_raw}'",
                dept_code='72',
                dept_name='Sarthe'
            )

    # === PRIORITÉ 4: Code département hors 72 → RÉGIONAL ===
    dept_matches = DEPT_CODE_PATTERN.findall(full_text)
    for dept_code in dept_matches:
        if dept_code != DEPT_LOCAL and dept_code in DEPTS_REGIONAUX:
            return RegionalDetection(
                is_regional=True,
                reason=f"Code département ({dept_code})",
                dept_code=dept_code,
                dept_name=DEPTS_REGIONAUX[dept_code]
            )

    # === PRIORITÉ 5: Lieu connu hors Sarthe → RÉGIONAL ===
    lieu_lower = (lieu_raw or '').lower()
    for lieu, dept in LIEUX_HORS_SARTHE.items():
        if lieu in lieu_lower:
            return RegionalDetection(
                is_regional=True,
                reason=f"Lieu hors Sarthe: '{lieu}'",
                dept_code=dept,
                dept_name=DEPTS_REGIONAUX.get(dept)
            )

    # === PRIORITÉ 6: Ville hors Sarthe → RÉGIONAL ===
    if re.search(r'\bparis\b', full_text_lower):
        if not PARIS_FALSE_POSITIVE_RE.search(full_text_lower):
            if not re.search(r'\([^)]*paris[^)]*\)', full_text_lower):
                return RegionalDetection(
                    is_regional=True,
                    reason="Ville hors Sarthe: 'paris'",
                    dept_code='75',
                    dept_name='Paris'
                )

    for ville in VILLES_HORS_SARTHE:
        pattern = r'\b' + re.escape(ville) + r'\b'
        if re.search(pattern, full_text_lower):
            dept = _get_dept_for_ville(ville)
            return RegionalDetection(
                is_regional=True,
                reason=f"Ville hors Sarthe: '{ville}'",
                dept_code=dept,
                dept_name=DEPTS_REGIONAUX.get(dept) if dept else None
            )

    # === DÉFAUT: LOCAL ===
    return RegionalDetection(
        is_regional=False,
        reason="Défaut (local)",
        dept_code='72',
        dept_name='Sarthe'
    )


def _get_dept_for_ville(ville: str) -> Optional[str]:
    """Retourne le code département pour une ville connue."""
    ville = ville.lower()

    if ville in ['angers', 'cholet', 'saumur', 'avrillé', 'montigné-sur-moine', 'morannes', 'segré']:
        return '49'
    elif ville in ['laval', 'mayenne', 'château-gontier', 'evron', 'ernée']:
        return '53'
    elif ville in ['alençon', 'argentan', 'flers', "l'aigle", 'mortagne']:
        return '61'
    elif ville in ['vendôme', 'blois', 'romorantin', 'savigny-sur-braye']:
        return '41'
    elif ville in ['nantes', 'saint-nazaire', 'st-nazaire', 'st nazaire']:
        return '44'
    elif ville in ['rennes', 'saint-malo', 'st-malo', 'fougères', 'vitré']:
        return '35'
    elif ville in ['la roche-sur-yon', 'montaigu', 'challans', 'fontenay-le-comte']:
        return '85'
    elif ville in ['coutances', 'cherbourg', 'saint-lô', 'granville', 'avranches']:
        return '50'
    elif ville in ['tours', 'amboise', 'chinon', 'loches']:
        return '37'
    elif ville in ['caen', 'lisieux', 'bayeux', 'honfleur']:
        return '14'
    return None


def is_regional_event(raw_text: str, lieu_raw: Optional[str] = None,
                      ville_raw: Optional[str] = None) -> bool:
    """Version simplifiée: retourne True si événement régional."""
    return detect_regional(raw_text, lieu_raw, ville_raw).is_regional

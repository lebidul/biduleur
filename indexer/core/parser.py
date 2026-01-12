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
from core.month_detector import (
    detect_month_sections,
    get_month_for_line,
    is_summer_bidul,
    MonthSection
)
from core.regional_filter import detect_regional

logger = logging.getLogger(__name__)


# =============================================================================
# GESTION DES MOIS EXPLICITES (pour événements hors mois du bidul)
# =============================================================================

# Mapping nom de mois → numéro (1-12)
MOIS_TO_NUMBER = {
    # Formes complètes
    'janvier': 1, 'février': 2, 'fevrier': 2, 'mars': 3, 'avril': 4,
    'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8, 'aout': 8,
    'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12, 'decembre': 12,
    # Abréviations courantes
    'janv': 1, 'jan': 1, 'fev': 2, 'avr': 4, 'juil': 7,
    'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

# Pattern pour extraire le mois explicite d'une date
# Ex: "Dimanche 1er décembre", "Vendredi 9 juillet", "Du 26 au 30 novembre"
# Supporte aussi les abréviations: "Sa 1er Nov", "Di 31 Déc"
MOIS_PATTERN = re.compile(
    r'\b(jan(?:v(?:ier)?)?|f[ée]v(?:rier)?|mars|avr(?:il)?|mai|juin|'
    r'juil(?:let)?|ao[uû]t|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?)\b',
    re.IGNORECASE
)


def extract_explicit_month(date_str: str) -> Optional[int]:
    """
    Extrait le numéro de mois si un nom de mois explicite est présent dans la chaîne.

    Args:
        date_str: Chaîne de date (ex: "Dimanche 1er décembre")

    Returns:
        Numéro du mois (1-12) ou None si pas de mois explicite
    """
    match = MOIS_PATTERN.search(date_str)
    if match:
        mois_str = match.group(1).lower()
        # Normaliser les accents
        mois_str = mois_str.replace('é', 'e').replace('û', 'u')
        return MOIS_TO_NUMBER.get(mois_str)
    return None


def is_noise_line(line: str) -> bool:
    """
    Détecte si une ligne est du "bruit" (texte non-événement).

    Critères de bruit:
    - URLs (www., http, .com, .fr)
    - Balises spéciales (<bi>)
    - Texte "littéraire" (phrases longues sans structure événement)
    - Caractères OCR corrompus (séquences de caractères spéciaux)
    - Texte promotionnel connu

    Args:
        line: Ligne de texte à analyser

    Returns:
        True si c'est du bruit, False sinon
    """
    line_stripped = line.strip()
    if not line_stripped:
        return False

    # 1. URLs et réseaux sociaux
    if re.search(r'www\.|https?://|facebook\.com|instagram\.com|twitter\.com|\.fr/|\.com/', line, re.IGNORECASE):
        return True

    # 2. Balises spéciales de promo
    if '<bi>' in line.lower():
        return True

    # 3. Texte promotionnel/éditorial connu
    promo_phrases = [
        r'Des dates seront ajoutées',
        r'Sortez & soyez curieux',
        r'd\'infos prochainement',
        r'prochainement sur',
        r'Edité par l\'association',
        r'photographie:',
        r'LEZARTUALITE',
        r'^COUP DE GUEULE',  # Texte éditorial
        r'^OYE OYE',  # Annonces diverses
        r'^En voilà qui',  # Texte éditorial
        r'^Chapeau bas',  # Texte éditorial
        r'^Surtout quand on',  # Texte éditorial
        r'recherche des groupes',  # Annonces de recherche
        r'Envoyez vos démo',  # Annonces
        # Rubriques éditoriales des anciens Biduls
        r'Rubrique Cucaracha',
        r'Dicton du mois',
        r'Blagounette',
        r'Le Bidul est tiré à',
        r'Ne pas jétér sur la voie publique',
        r'Ne pas jeter sur la voie publique',
        r'tiré à \d+ exemplaires',
        r'Réponse sur le blog',
        r'Réponse de la blagounette',
    ]
    for phrase in promo_phrases:
        if re.search(phrase, line_stripped, re.IGNORECASE):
            return True

    # 4. Caractères OCR corrompus (séquences de caractères spéciaux/unicode)
    # Plus de 30% de caractères non-alphanumériques standards = probablement corrompu
    if len(line_stripped) > 20:
        non_standard = len(re.findall(r'[^\w\s,.:;!?()€\-\'\"<>/&àâäéèêëïîôùûüç]', line_stripped, re.IGNORECASE))
        if non_standard / len(line_stripped) > 0.3:
            return True

    # 5. Texte "littéraire" - phrases longues sans structure événement
    # Un événement a typiquement: artiste/spectacle, lieu, heure, prix
    # Le texte littéraire a: articles, verbes conjugués, pronoms
    if len(line_stripped) > 100:
        # Mots indicateurs de texte narratif/littéraire
        literary_indicators = [
            r'\bje\b', r'\btu\b', r'\bil\b', r'\belle\b', r'\bnous\b', r'\bvous\b', r'\bils\b',
            r'\bqu\'on\b', r'\bqu\'il\b', r'\bc\'est\b', r'\bj\'ai\b', r'\bj\'admire\b',
            r'\bquand\b', r'\bmais\b', r'\bcar\b', r'\bdonc\b', r'\balors\b',
            r'\btoujours\b', r'\bsouvent\b', r'\bparfois\b',
            r'\bêtre\b', r'\bavoir\b', r'\bfaire\b', r'\bvoir\b', r'\bsavoir\b',
            r'\bplaisir\b', r'\bpassion\b', r'\bfièvre\b', r'\bfrisson\b',
        ]
        literary_count = sum(1 for pattern in literary_indicators if re.search(pattern, line, re.IGNORECASE))
        if literary_count >= 3:
            return True

    # 6. Ligne très longue sans virgule ni structure (probablement OCR corrompu)
    if len(line_stripped) > 150 and line_stripped.count(',') < 2:
        return True

    return False


def truncate_noise_in_line(line: str) -> str:
    """
    Tronque le bruit qui peut apparaître après l'heure/prix dans une même ligne.

    Cas: "ARTISTE, Lieu, 21h LEZARTUALITE blabla..." → "ARTISTE, Lieu, 21h"

    Args:
        line: Ligne de texte

    Returns:
        Ligne nettoyée
    """
    if not line:
        return line

    # Pattern pour détecter le prix ou l'heure (fin typique d'un événement)
    # Supporte: €, E, F (Francs), et les formats "de X à Y"
    prix_pattern = re.compile(
        r'(?:de\s+)?'  # Optionnel: "de " (pour "de 40 à 90F")
        r'(\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?(?:\s*[àa-]\s*\d+(?:[.,]\d+)?)?\s*[€eEfF]'
        r'|gratuit|au chapeau|prix libre|hnc|tnc)'
        r'(?:\s*\([^)]*\))?',  # Optionnel: (- 14 ans)
        re.IGNORECASE
    )
    heure_pattern = re.compile(r'\d{1,2}[hH]\d{0,2}')

    # Chercher le prix et l'heure
    prix_match = prix_pattern.search(line)
    heure_match = heure_pattern.search(line)

    # Déterminer quel marqueur utiliser (le premier qui apparaît)
    # Priorité au prix s'il est dans les 500 premiers caractères (évite les faux positifs OCR)
    end_pos = None

    if prix_match and prix_match.start() < 500:
        # Le prix est proche du début, l'utiliser
        end_pos = prix_match.end()
    elif heure_match:
        # Utiliser l'heure si le prix est trop loin ou absent
        end_pos = heure_match.end()
    elif prix_match:
        # Fallback sur le prix même s'il est loin
        end_pos = prix_match.end()

    if end_pos:
        remaining = line[end_pos:].strip()
        # S'il y a du texte après le marqueur, vérifier si c'est du bruit
        if remaining and is_noise_text(remaining):
            return line[:end_pos].strip()

    return line


def is_noise_text(text: str) -> bool:
    """
    Vérifie si un fragment de texte est du bruit.

    Args:
        text: Fragment de texte à analyser

    Returns:
        True si c'est du bruit
    """
    if not text or len(text.strip()) < 5:
        return False

    text_stripped = text.strip()
    # Ignorer la ponctuation initiale (., :, etc.)
    text_content = re.sub(r'^[.\s:;,!?-]+', '', text_stripped)

    # Patterns de bruit évident
    noise_patterns = [
        r'^LEZARTUALITE',
        r'^LE\s+"?HAS\s+BEEN',
        r'photographie:',
        r'Edité par',
        r'\bπ\b|\bε\b|\bτ\b',  # Caractères grecs (OCR corrompu)
        r'\ble Bidul\b',  # Référence au Bidul lui-même (texte éditorial)
        r'\bLes Arts Services\b',  # Mention de l'éditeur
        r'Ne pas jeter sur la voie publique',
        r'tiré à \d+ exemplaires',
        r'^COUP DE GUEULE',  # Texte éditorial
        r'^OYE OYE',  # Annonces diverses
        r'^En voilà qui',  # Texte éditorial
        r'^Chapeau bas',  # Texte éditorial
        r'recherche des groupes',  # Annonces de recherche
        r'Envoyez vos démo',  # Annonces
    ]
    for pattern in noise_patterns:
        if re.search(pattern, text_stripped, re.IGNORECASE):
            return True

    # Texte littéraire/éditorial (commence par des mots typiques)
    literary_starts = [
        r'^La fête de',
        r'^Quel plaisir',
        r'^Alors\b',
        r'^Depuis\b',
        r'^Mais\b',
        r'^Car\b',
        r'^C\'est\b',
        r'^J\'admire',
        r'^On\s+(?:joue|fait|veut)',
        r'^L\'[A-Z]',  # L'Invasion, L'Affirmation, etc.
        r'^Malgré\b',
        r'^En effet\b',
        r'^Ainsi\b',
        r'^Certes\b',
        r'^Pourtant\b',
        r'^Nous\s+(?:pouvons|devons|avons|sommes)',
        r'^Il\s+(?:existe|nous|y a)',
        r'^Une des raisons',
        r'^Comme toute',
    ]
    for pattern in literary_starts:
        if re.search(pattern, text_content, re.IGNORECASE):
            return True

    # Beaucoup de caractères spéciaux (OCR corrompu)
    if len(text_stripped) > 20:
        special_chars = len(re.findall(r'[^\w\s,.:;!?()€\-\'\"àâäéèêëïîôùûüç]', text_stripped, re.IGNORECASE))
        if special_chars / len(text_stripped) > 0.25:
            return True

    # Texte très long sans structure d'événement (pas de lieu, heure, prix)
    # Un événement typique fait moins de 200 caractères
    if len(text_content) > 300:
        # Vérifier s'il y a des marqueurs d'événement
        has_hour = bool(re.search(r'\d{1,2}[hH]\d{0,2}', text_content))
        has_price = bool(re.search(r'\d+\s*[€eE]|gratuit', text_content, re.IGNORECASE))
        if not has_hour and not has_price:
            return True

    return False


def truncate_after_price(text: str) -> str:
    """
    Tronque le texte "bruit" qui suit les événements.

    Ne coupe QUE s'il y a du texte bruit détecté après une ligne de prix.
    Ne coupe PAS entre plusieurs événements légitimes.

    Types de bruit détectés:
    - Texte promotionnel (balises <bi>, URLs, phrases promo)
    - Texte littéraire/narratif (phrases avec pronoms, verbes conjugués)
    - Texte OCR corrompu (caractères spéciaux, séquences illisibles)
    - Lignes très longues sans structure d'événement

    Args:
        text: Texte brut de l'événement

    Returns:
        Texte sans le bruit final
    """
    if not text:
        return text

    # Pattern pour détecter une ligne se terminant par un prix
    prix_fin_ligne = re.compile(
        r'(?:'
        r'\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?(?:\s*[àa-]\s*\d+(?:[.,]\d+)?)?\s*[€eE]'
        r'|gratuit|au chapeau|prix libre|hnc|tnc'
        r')'
        r'(?:\s*\([^)]*\))?'  # Optionnel: (- 14 ans), (tarif réduit)
        r'\s*$',
        re.IGNORECASE
    )

    lines = text.split('\n')

    # Nettoyer chaque ligne du bruit inline
    cleaned_lines = [truncate_noise_in_line(line) for line in lines]

    # Chercher la dernière ligne avec un prix
    last_price_idx = -1
    for i, line in enumerate(cleaned_lines):
        if prix_fin_ligne.search(line.strip()):
            last_price_idx = i

    # Si pas de prix trouvé, vérifier si le texte contient du bruit évident
    if last_price_idx == -1:
        # Chercher la première ligne de bruit et couper avant
        result_lines = []
        for line in cleaned_lines:
            if is_noise_line(line):
                break
            result_lines.append(line)
        return '\n'.join(result_lines) if result_lines else '\n'.join(cleaned_lines)

    # Vérifier si le texte après le dernier prix contient du bruit
    remaining_lines = cleaned_lines[last_price_idx + 1:]
    has_noise = any(is_noise_line(line) for line in remaining_lines)

    if has_noise:
        # Il y a du bruit après - couper à la première ligne de bruit
        result_lines = []
        for line in cleaned_lines:
            if is_noise_line(line):
                break
            result_lines.append(line)
        return '\n'.join(result_lines)

    # Pas de bruit détecté - retourner le texte nettoyé
    return '\n'.join(cleaned_lines)


def truncate_noise_prefix(text: str) -> str:
    """
    Tronque le préfixe de bruit avant les événements.

    Certains textes OCR commencent par du contenu non-événementiel:
    - Annonces de recherche de groupes
    - Informations de contact
    - Headers de section (Théâtre-Humour-Danse)
    - Mentions de lieux régionaux sans événement

    Cette fonction détecte le premier événement (bullet + date ou date inline)
    et supprime tout ce qui précède.

    Args:
        text: Texte brut potentiellement avec préfixe de bruit

    Returns:
        Texte sans le préfixe de bruit
    """
    if not text:
        return text

    # Patterns de début d'événement:
    # 1. Bullet suivi de date: "* Sa 01", "• Di 15"
    # 2. Date inline: "Sa 01 :", "Ma 28 <<", "Je 15 CONCERT"
    # Le bullet peut être * • ● ► etc.
    bullet_chars = r'[*•●○◦▪▫■□►▸‣⁃❑❒◇◆★☆✦✧♦❖✳✴✵✶✷✸✹→➔➜➤]'
    # Jours: Lu, Ma, Me, Je, Ve, Sa, Di (abréviations exactes)
    # NE PAS utiliser [DLMJVS][aeiou] qui matcherait "le", "de", etc.
    jours = r'(?:Lu|Ma|Me|Je|Ve|Sa|Di)'

    # Pattern 1: Bullet + jour + numéro (format par bloc)
    # Ex: "* Sa 01", "• Di 15/Lu 16"
    bullet_event_pattern = re.compile(
        rf'{bullet_chars}\s*{jours}\s+\d{{1,2}}',
        re.IGNORECASE
    )

    # Pattern 2: Date inline au début de ligne
    # Ex: "Sa 01 :", "Ma 28 <<", "Je 15 CONCERT"
    inline_date_pattern = re.compile(
        rf'^{jours}\s+\d{{1,2}}(?:er|ère|ème|eme)?\s*(?:[:/]|<<|[«"<]|[A-Z]{{2}})',
        re.IGNORECASE | re.MULTILINE
    )

    # Chercher le premier événement
    bullet_match = bullet_event_pattern.search(text)
    inline_match = inline_date_pattern.search(text)

    # Déterminer la position de départ
    start_pos = None
    if bullet_match and inline_match:
        start_pos = min(bullet_match.start(), inline_match.start())
    elif bullet_match:
        start_pos = bullet_match.start()
    elif inline_match:
        start_pos = inline_match.start()

    if start_pos is None or start_pos == 0:
        # Pas de préfixe à supprimer
        return text

    # Vérifier que le préfixe contient bien du bruit
    prefix = text[:start_pos]

    # Patterns de bruit dans le préfixe
    noise_in_prefix = [
        r'recherche\s+des\s+groupes',
        r'Contactez[-\s]',
        r'\d{2}\s*\d{2}\s*\d{2}\s*\d{2}\s*\d{2}',  # Numéro de téléphone
        r'Théâtre[-\s]*Humour[-\s]*Danse',  # Header de section
        r'Concerts[-\s]*Musiques',  # Header de section
        r'L\'Association\b',
        r'\brecherche\b.*\bcontact',
    ]

    has_noise_prefix = any(
        re.search(pattern, prefix, re.IGNORECASE)
        for pattern in noise_in_prefix
    )

    if has_noise_prefix:
        # Supprimer le préfixe
        return text[start_pos:]

    return text


# =============================================================================
# EXTRACTION BASÉE SUR LE FORMATAGE (gras, italique)
# =============================================================================

def extract_formatted_spectacles(text: str) -> list[dict]:
    """
    Extrait les spectacles en utilisant le formatage.

    Règle: Les spectacles sont en GRAS entre guillemets.
    Pattern: <b>"Nom du spectacle"</b> ou <b>"Nom"</b> <i>(style)</i>

    Aussi: spectacles entre guillemets (sans gras) suivis d'un style en italique.

    Guillemets supportés:
    - Ouvrants: « " " „ <<
    - Fermants: » " " >>

    Returns:
        Liste de dicts {'nom': str, 'style': str|None}
    """
    spectacles = []

    # D'abord fusionner les <i> consécutifs (styles coupés par saut de ligne)
    text = _merge_consecutive_italic_tags(text)

    # Classes de guillemets (ouvrants et fermants)
    # Inclut << et >> pour l'OCR qui peut confondre les guillemets
    # U+00AB «, U+00BB », U+201C ", U+201D ", U+201E „, U+0022 "
    open_quotes = r'[«""„\u201c\u201d]|<<'
    close_quotes = r'[»""\u201c\u201d]|>>'

    # Pattern 1: <b>"Spectacle"</b> suivi optionnellement de <i>(style),</i>
    # Note: la virgule peut être dans ou après les parenthèses
    # Guillemets typographiques ou ASCII
    pattern = rf'<b>\s*(?:{open_quotes})([^»""<>]+)(?:{close_quotes})\s*</b>(?:\s*<i>\s*\(([^)]+)\)[,;]?\s*</i>)?'
    matches = re.finditer(pattern, text, re.IGNORECASE)

    for match in matches:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 1:
            spectacles.append({'nom': nom, 'style': style})

    # Pattern 1b: "<b>Spectacle</b>" (<i>style</i>) - guillemets AUTOUR des balises <b>
    # Cas: "<b>Concert à table</b>" (<i>concert >7 ans</i>)
    # Les guillemets encadrent les balises <b>, et le style est en <i> après
    pattern1b = rf'(?:{open_quotes})\s*<b>([^<>]+)</b>\s*(?:{close_quotes})\s*(?:\(?\s*<i>\s*\(?([^)<]+?)\)?\s*</i>\s*\)?)?'
    matches1b = re.finditer(pattern1b, text, re.IGNORECASE)

    for match in matches1b:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 1:
            if not any(s['nom'] == nom for s in spectacles):
                spectacles.append({'nom': nom, 'style': style})

    # Pattern 1c: "<b>Spectacle</b>" Cie XXX (<i>style</i>) - avec Cie entre spectacle et style
    # Cas: "<b>Concerto pour camionneuse</b>" Cie Ordinaire d'exception (<i>funambule</i>)
    # Le style vient APRÈS la Cie, pas directement après le spectacle
    pattern1c = rf'(?:{open_quotes})\s*<b>([^<>]+)</b>\s*(?:{close_quotes})\s+[Cc]ie\s+[^<(]+\s*(?:\(?\s*<i>\s*\(?([^)<]+?)\)?\s*</i>\s*\)?)?'
    matches1c = re.finditer(pattern1c, text, re.IGNORECASE)

    for match in matches1c:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 1:
            # Mettre à jour le style si le spectacle existe déjà sans style
            existing = next((s for s in spectacles if s['nom'] == nom), None)
            if existing:
                if not existing.get('style') and style:
                    existing['style'] = style
            else:
                spectacles.append({'nom': nom, 'style': style})

    # Pattern 2: "Spectacle" (sans gras) suivi de <i>(style)</i>
    # Cas spécial: "Ma tata, mon pingouin..." <i>(concert jeune public)</i>
    # Note: pas de <b> autour du spectacle lui-même, mais peut être après </b> d'un artiste
    pattern2 = rf'(?:{open_quotes})([^»""<>]+)(?:{close_quotes})\s*<i>\s*\(([^)]+)\)[,;]?\s*</i>'
    matches2 = re.finditer(pattern2, text, re.IGNORECASE)

    for match in matches2:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 1:
            # Vérifier que ce n'est pas déjà dans la liste
            if not any(s['nom'] == nom for s in spectacles):
                spectacles.append({'nom': nom, 'style': style})

    # Pattern 3: "Spectacle" (style) - sans balises du tout (OCR brut)
    # Cas: << Bois d'ébène " (lecture, conte)
    # Note: le style est entre parenthèses mais pas en italique
    pattern3 = rf'(?:{open_quotes})\s*([^»""<>]+?)\s*(?:{close_quotes})\s*\(([^)]+)\)'
    matches3 = re.finditer(pattern3, text, re.IGNORECASE)

    for match in matches3:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 2:
            # Vérifier que ce n'est pas déjà dans la liste
            if not any(s['nom'] == nom for s in spectacles):
                spectacles.append({'nom': nom, 'style': style})

    # Pattern 4: << Spectacle " (style) - OCR avec << et guillemet ASCII fermant
    # Cas spécial: <<Bambou de Souffle", (cirque-danse)
    # Le pattern 3 échoue car [^<>] ne peut pas matcher après <<
    # Format: << texte ", (style) ou << texte " (style)
    pattern4 = r'<<\s*([^"]+?)\s*",?\s*\(([^)]+)\)'
    matches4 = re.finditer(pattern4, text, re.IGNORECASE)

    for match in matches4:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 2:
            # Vérifier que ce n'est pas déjà dans la liste
            if not any(s['nom'] == nom for s in spectacles):
                spectacles.append({'nom': nom, 'style': style})

    # Pattern 5: <<Spectacle"> (style) - OCR avec << ouvrant et "> fermant
    # Cas spécial: <<Rien ne laisse présager de l'Etat de l'Eau"> (danse)
    # Le "> est un guillemet fermant mal reconnu (combinaison de " et >)
    # NOTE: Ce pattern doit être AVANT le pattern <<...> pour éviter de capturer " dans le nom
    pattern5 = r'<<\s*([^<>"]+?)\s*">\s*\(([^)]+)\)'
    matches5 = re.finditer(pattern5, text, re.IGNORECASE)

    for match in matches5:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 2:
            if not any(s['nom'] == nom for s in spectacles):
                spectacles.append({'nom': nom, 'style': style})

    # Pattern 5b: <<Spectacle> (style) - OCR avec << ouvrant et > fermant (mal lu)
    # Cas spécial: <<Marrons gagnants> (contes), <<Guth Després> (contes)
    # Le < final est un guillemet fermant mal reconnu
    # NOTE: Exclure " pour ne pas matcher les cas <<..."> qui sont gérés par Pattern 5
    pattern5b = r'<<\s*([^<>"]+?)\s*>\s*\(([^)]+)\)'
    matches5b = re.finditer(pattern5b, text, re.IGNORECASE)

    for match in matches5b:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 2:
            if not any(s['nom'] == nom for s in spectacles):
                spectacles.append({'nom': nom, 'style': style})

    # Pattern 6: <Spectacle" (style) - OCR avec < ouvrant et " fermant
    # Cas spécial: <Ferouër" (danse contemporaine)
    pattern6 = r'<([^<>"]+?)\s*"\s*\(([^)]+)\)'
    matches6 = re.finditer(pattern6, text, re.IGNORECASE)

    for match in matches6:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 2:
            if not any(s['nom'] == nom for s in spectacles):
                spectacles.append({'nom': nom, 'style': style})

    # Pattern 7: "Spectacle> (style) - OCR avec " ouvrant et > fermant
    # Cas spécial: "Métis'sages> (contes et légendes d'ailleurs)
    pattern7 = r'"([^"<>]+?)>\s*\(([^)]+)\)'
    matches7 = re.finditer(pattern7, text, re.IGNORECASE)

    for match in matches7:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 2:
            if not any(s['nom'] == nom for s in spectacles):
                spectacles.append({'nom': nom, 'style': style})

    return spectacles


def _merge_consecutive_bold_tags(text: str) -> str:
    """
    Fusionne les balises <b> consécutives séparées par des espaces/retours.

    Exemple:
    "<b>LES MOYENS </b> <b>DU BORD </b>" → "<b>LES MOYENS DU BORD </b>"
    """
    # Pattern: </b> suivi d'espaces/retours puis <b>
    # On remplace par un seul espace (les espaces internes seront normalisés après)
    merged = re.sub(r'\s*</b>\s*<b>\s*', ' ', text)
    return merged


def _merge_consecutive_italic_tags(text: str) -> str:
    """
    Fusionne les balises <i> consécutives séparées par des espaces/retours.

    Exemple:
    "<i>(post-</i> <i>punk)</i>" → "<i>(post-punk)</i>"
    """
    # Pattern: </i> suivi d'espaces/retours puis <i>
    merged = re.sub(r'\s*</i>\s*<i>\s*', ' ', text)
    return merged


def _clean_style(style: str) -> str:
    """
    Nettoie un style extrait.

    - Retire la virgule finale
    - Retire les balises résiduelles
    - Normalise les espaces
    - Corrige les tirets avec espaces (post- punk → post-punk)
    """
    if not style:
        return style

    # Retirer les balises résiduelles
    style = re.sub(r'</?[bi]+>', '', style)
    # Retirer virgule/point-virgule final
    style = style.rstrip(',;').strip()
    # Normaliser les espaces
    style = re.sub(r'\s+', ' ', style)
    # Corriger les tirets avec espace (post- punk → post-punk)
    style = re.sub(r'-\s+', '-', style)
    style = re.sub(r'\s+-', '-', style)
    return style


def extract_formatted_artistes_musicaux(text: str) -> list[dict]:
    """
    Extrait les artistes musicaux en utilisant le formatage.

    Règle: Les artistes musicaux (concerts) sont en GRAS sans guillemets.
    Pattern: <b>NOM ARTISTE</b> ou <b>NOM</b> <i>(style)</i>

    Exception: Si le gras est suivi de "par" (artiste de théâtre), c'est un spectacle.

    Gère aussi les artistes séparés par "+" (dans ou hors balises).

    Returns:
        Liste de dicts {'nom': str, 'style': str|None, 'is_musical': True}
    """
    artistes = []

    # D'abord fusionner les balises consécutives (sauts de ligne dans le PDF)
    text = _merge_consecutive_bold_tags(text)
    text = _merge_consecutive_italic_tags(text)

    # Pattern: <b>ARTISTE</b> suivi optionnellement d'un style
    # Trois formats de style supportés:
    # - <i>(style)</i> : parenthèses dans l'italique
    # - (<i>style</i>) : italique dans les parenthèses
    # - <i>(style</i>) : ouverture dans italique, fermeture dehors (OCR mal formé)
    # Note: la virgule peut être dans ou après les parenthèses
    # Exclure les spectacles (guillemets) et les textes courts
    # Utilise un lookbehind négatif pour exclure les <b> précédés de guillemets (spectacles)
    # U+00AB «, U+00BB », U+201C ", U+201D ", U+201E „, U+0022 "
    pattern = r'(?<![«»\u201c\u201d„"\'])<b>([^<"»\u201c\u201d„«]+)</b>(?:\s*(?:<i>\s*\(([^)]+)\)[,;]?\s*</i>|\(\s*<i>([^<]+)</i>\s*\)[,;]?|<i>\s*\(([^<]+)</i>\s*\)[,;]?))?'
    matches = re.finditer(pattern, text, re.IGNORECASE)

    for match in matches:
        nom = match.group(1).strip()
        # Style peut être dans groupe 2, 3 ou 4 selon le format
        style = _clean_style(match.group(2) or match.group(3) or match.group(4)) if (match.group(2) or match.group(3) or match.group(4)) else None

        # Vérifier si c'est un spectacle sans guillemets (suivi de "par")
        # Dans ce cas, on ne l'ajoute pas aux artistes
        after_match = text[match.end():]
        if re.match(r'\s*par\s+', after_match, re.IGNORECASE):
            # C'est un spectacle, pas un artiste
            continue

        # Séparer les artistes multiples sur "+" uniquement (ex: "HOLLYSIZ + MEDI")
        # Note: "&" n'est PAS un séparateur car souvent utilisé dans les noms de groupe
        # (ex: "Dr Bones & the Blue Roots", "FRANCOIS HADJI-LAZARO & PIGALE")
        # Le style s'applique à tous les artistes du groupe
        artist_names = re.split(r'\s*\+\s*', nom)

        for artist_name in artist_names:
            artist_name = artist_name.strip()

            # Filtrer les faux positifs
            # - Trop court (moins de 2 caractères)
            # - Mots de liaison
            # - Dates (comme "Lu 02")
            if (len(artist_name) < 2 or
                artist_name.upper() in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET', 'À', 'AU') or
                re.match(r'^[DLMJVS][a-z]\s*\d', artist_name, re.IGNORECASE)):
                continue

            artistes.append({
                'nom': artist_name,
                'style': style,
                'is_musical': True
            })

    return artistes


def extract_formatted_spectacles_unquoted(text: str) -> list[dict]:
    """
    Extrait les spectacles en gras SANS guillemets.

    Règle: Un texte en gras suivi d'un style puis "par" est un spectacle.
    Pattern: <b>Nom spectacle</b> <i>(style)</i> par ...

    Returns:
        Liste de dicts {'nom': str, 'style': str|None}
    """
    spectacles = []

    # D'abord fusionner les balises consécutives
    text = _merge_consecutive_bold_tags(text)
    text = _merge_consecutive_italic_tags(text)

    # Pattern: <b>Spectacle</b> <i>(style)</i> par ...
    pattern = r'<b>([^<"»"„«]+)</b>\s*<i>\s*\(([^)]+)\)[,;]?\s*</i>\s*par\s+'
    matches = re.finditer(pattern, text, re.IGNORECASE)

    for match in matches:
        nom = match.group(1).strip()
        style = _clean_style(match.group(2)) if match.group(2) else None
        if nom and len(nom) > 1:
            spectacles.append({'nom': nom, 'style': style})

    return spectacles


def extract_formatted_styles(text: str) -> list[str]:
    """
    Extrait les styles/genres en utilisant le formatage.

    Règle: Les styles sont en ITALIQUE entre parenthèses.
    Pattern: <i>(style)</i>

    Returns:
        Liste de styles
    """
    styles = []

    # Pattern: <i>(style)</i>
    pattern = r'<i>\s*\(([^)]+)\)\s*</i>'
    matches = re.finditer(pattern, text, re.IGNORECASE)

    for match in matches:
        style = match.group(1).strip()
        if style and len(style) > 1:
            styles.append(style)

    return styles


def strip_formatting_tags(text: str) -> str:
    """
    Retire les balises de formatage du texte.

    Convertit "<b>texte</b> <i>style</i>" en "texte style"
    """
    # Retirer les balises mais garder le contenu
    text = re.sub(r'</?b>', '', text)
    text = re.sub(r'</?i>', '', text)
    text = re.sub(r'</?bi>', '', text)
    # Normaliser les espaces multiples
    text = re.sub(r'  +', ' ', text)
    return text


def has_formatting_tags(text: str) -> bool:
    """Vérifie si le texte contient des balises de formatage."""
    return bool(re.search(r'</?(?:b|i|bi)>', text))


def is_named_event(text: str) -> bool:
    """
    Détermine si le texte représente un événement nommé (festival, soirée thématique).

    Événements nommés (remplir evenement.nom):
    - "Alpa On The Rock #13"
    - "Esc Exp #21 TERIAKI"
    - "Melting Rock"
    - "Les Spectaculaires"
    - "Soirée Solidaire"
    - "Soirée Mix Généraliste avec Dj Vindu"
    - "Soirée OULALA Xmas"
    - "Scène ouverte musicale"

    PAS événements nommés (ne pas remplir evenement.nom):
    - Spectacles entre guillemets: "L'itinérance de Maud"
    - Concerts d'artistes: MENDELSON (poème rock)
    """
    # Patterns d'événements nommés
    # Note: ^[«""„]? permet de matcher avec ou sans guillemets au début
    # Note: (?:\d+[°e]?\s+)? permet de matcher les numéros d'édition (8°, 3e, etc.)
    named_event_patterns = [
        r'^[«""„]?Alpa\s+On\s+The\s+Rock\s+#?\d+',
        r'^[«""„]?Esc\s*Exp\s*#?\d+',  # "Esc Exp #21" ou "EscExp#28"
        r'^[«""„]?Melting\s+Rock',
        r'^[«""„]?Les\s+Spectaculaires',
        r'^[«""„]?Soir[ée]e?\s+[""«]?[\w\s]+',  # Soirée/Soiree Solidaire, Soirée "électro festif"
        r'^[«""„]?Labo\s+d.Impro',
        r'^[«""„]?[Cc]arte\s+[Bb]lanche\s+[àa]',
        r'^[«""„]?(?:\d+[°e]?\s+)?[Ff]estival\s+',  # Festival, 8° festival, 3e Festival
        r'^[«""„]?FESTI(?:VAL)?\s+',  # FESTI BOUAILLE, FESTIVAL X
        r'^[«""„]?Nuit\s+\w+',  # Nuit Blanche, etc.
        r'^[«""„]?Scène\s+ouverte',  # Scène ouverte musicale, etc.
        r'^[«""„]?Open\s+mic',
        r'^[«""„]?Jam\s+session',
        r'^[«""„]?(?:\d+[°e]?\s+)?[Ff]ête\s+',  # Fête interculturelle, 2° Fête de la musique
        r'^[«""„]?Répét\.\s+publique',  # Répétition publique
        r'^[«""„]?Bellevue\s+en\s+balade',  # Événement spécifique
        r'^[«""„]?Apéro\s+concert',  # Apéro concert avec ARTISTE
        # Ciné Pride, Ciné XXX (festivals de cinéma)
        r'^[«""„]?Cin[ée]\s+\w+',
        # Les Rdv XXX, Les Rendez-vous XXX (événements récurrents)
        r'^[«""„]?Les\s+(?:Rdv|Rendez-vous)\s+',
        # LES X ANS DE/DES/DU XXX (anniversaires)
        r'^[«""„]?LES\s+\d+\s+ANS\s+(?:DE|DES|DU|D\')\s*',
        # Nom d'événement en MAJUSCULES suivi de ":" puis artistes en gras
        # Ex: "SPRINGROCK : <b>AS YOU WANT</b>"
        r'^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-]+\s*:\s*<b>',
        # Pattern "XXX présente YYY" ou "XXX présente: YYY" - XXX est le nom de l'événement
        r'^[\w\s]+\s+présente\s*:?\s+',
        # DAMADA FESTIVAL # 11 avec ... - Festival avec numéro et "avec"
        r'^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s]+\s+#\s*\d+\s+avec\s+',
        # NOM CLUB/NIGHT avec ... - Événement type soirée en MAJUSCULES
        r'^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s]+(?:CLUB|NIGHT|PARTY|SESSION|SHOW)\s+avec\s+',
        # Événement nommé avec numéro d'édition: "Syncope fait de la résistance #2"
        # Pattern: Nom en Title Case avec #N
        r'^[«""„]?[A-ZÀ-Ÿ][a-zà-ÿ]+(?:\s+[a-zà-ÿ]+)*\s+#\d+',
        # Pattern: "Nom Event #N:" suivi d'artistes (ex: "No Data #2: ARTISTE...")
        # Le ":" indique que ce qui suit sont les artistes, pas le nom de l'événement
        r'^[«""„]?[\w\s]+\s*#\s*\d+\s*:\s*[A-Z]',
        # Pattern: "Nom Event:" (Title Case) suivi d'artistes en MAJUSCULES
        # Ex: "Siestes Electroniques: HERTZ CANOPY..."
        # Le nom doit être en Title Case (pas tout en majuscules) et suivi de ":"
        r'^[«""„]?[A-ZÀ-Ÿ][a-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)+\s*:\s*[A-Z]{2,}',
        # Pattern: "Les X:" suivi d'un spectacle entre guillemets
        # Ex: "Les Veillées: \"Traces\" (théâtre) par..."
        r'^[«""„]?Les\s+[A-ZÀ-Ÿa-zà-ÿ]+\s*:\s*[""«]',
    ]

    for pattern in named_event_patterns:
        if re.match(pattern, text.strip(), re.IGNORECASE):
            return True

    return False


def extract_event_name(text: str) -> Optional[str]:
    """
    Extrait le nom de l'événement SI c'est un événement nommé.
    Retourne None si c'est un spectacle ou concert simple.

    Pour les soirées avec DJ, extrait la partie avant "avec":
    - "Soirée Mix Généraliste avec Dj Vindu" → "Soirée Mix Généraliste"
    """
    if not is_named_event(text):
        return None

    # Retirer les guillemets de début et fin pour simplifier l'extraction
    clean_text = text.strip()
    clean_text = re.sub(r'^[«""„"\']', '', clean_text)
    clean_text = re.sub(r'[»"""\']$', '', clean_text)
    clean_text = clean_text.strip()

    # Extraire le nom jusqu'au premier ":" ou "avec" ou artiste
    patterns = [
        r'^(Alpa\s+On\s+The\s+Rock\s+#?\d+)',
        r'^(Esc\s*Exp\s*#?\d+(?:\s+\w+)?)',  # "Esc Exp #21" ou "EscExp#28 Teriaki"
        r'^(Melting\s+Rock)',
        r'^(Les\s+Spectaculaires)',
        # Soirée "titre" avec guillemets - avec ou sans style entre parenthèses
        # Ex: 'Soirée "électro festif" avec Dj...' → 'Soirée "électro festif"'
        # Ex: 'Soirée "Prosper au passeport" (rock-hip hop) Le Passeport' → 'Soirée "Prosper au passeport"'
        r'^(Soirée\s*[""«][^""»]+[""»])(?:\s*\([^)]+\))?\s*(?:avec\s+|,|\s+[A-Z])',
        # "Soirée X" entre guillemets → extraire Soirée X sans guillemets
        r'^(Soirée\s+\w+)[»""]',
        # Soirée X avec DJ → extraire seulement "Soirée X"
        r'^(Soirée\s+[\w\s]+?)\s+avec\s+',
        # Soirée X: DJ Y → extraire seulement "Soirée X" (deux-points comme séparateur)
        # Ex: "Soirée Mix Music Festiv': DJ SUPER LUCIEN" → "Soirée Mix Music Festiv'"
        r"^(Soirée\s+[\w\s']+?):\s+",
        # Soirée X (sans "avec" ni ":")
        r'^(Soirée\s+[\w\s]+?)(?:\s*,|$)',
        r'^(Labo\s+d.Impro\s*:\s*"[^"]+")' ,
        # Festival avec numéro d'édition: "8° festival Soirs au Village"
        r'^(\d+[°e]?\s+[Ff]estival\s+[\w\s]+?)(?:[»"""\']?\s+avec\s+|\s*,|$)',
        # FESTI X YEAR - Date ou Festival X - Date (tiret comme séparateur)
        # Ex: "FESTI BOUAILLE 2011 - Samedi 02 Juillet" → "FESTI BOUAILLE 2011"
        # Ex: "Festival Les Pendules à l'Heure - Samedi 16" → "Festival Les Pendules à l'Heure"
        r"^(FESTI(?:VAL)?\s+[A-Za-z\u00C0-\u017F\s']+(?:\s+\d{4})?)\s*-\s*(?:Samedi|Dimanche|Lundi|Mardi|Mercredi|Jeudi|Vendredi|Du\s+\d)",
        r"^(Festival\s+[A-Za-z\u00C0-\u017F\s']+?)\s*-\s*(?:Samedi|Dimanche|Lundi|Mardi|Mercredi|Jeudi|Vendredi|Du\s+\d)",
        r'^([Ff]estival\s+[^:,»"""\'\s]+(?:\s+[^:,»"""\'\s]+)*)(?:[»"""\']?\s+avec\s*:?\s*|\s*,|$)',
        r'^(Nuit\s+\w+)',
        r'^([Cc]arte\s+[Bb]lanche\s+[àa]\s+[^:,]+)',
        r'^(Scène\s+ouverte\s*\w*)',
        r'^(Open\s+mic\s*\w*)',
        r'^(Jam\s+session)',
        # Fête avec numéro d'édition possible
        r'^(\d+[°e]?\s+[Ff]ête\s+[\w\s]+?)(?:\s+avec\s+|\s*,|$)',
        r'^([Ff]ête\s+[\w\s]+?)(?:\s+avec\s+|\s*,|$)',
        r'^(Répét\.\s+publique\s*)',  # Répétition publique
        r'^(Bellevue\s+en\s+balade\s*)',  # Événement spécifique
        r'^(Apéro\s+concert)(?:\s+avec\s+|\s*,|$)',  # Apéro concert
        # Ciné Pride, Ciné XXX (festivals de cinéma) - avec style entre parenthèses
        # Ex: "Ciné Pride du Mans" (festival de cinéma LGBT) avec: ... → "Ciné Pride du Mans"
        r'^(Cin[ée]\s+[^(]+?)(?:\s*\([^)]+\))?\s*(?:avec\s*:?\s*|,|$)',
        # Les Rdv XXX, Les Rendez-vous XXX (événements récurrents)
        # Ex: "Les Rdv Conservatoire Trio Pablo Musik" → "Les Rdv Conservatoire"
        # L'événement se termine avant le nom de groupe/artiste (Title Case ou MAJUSCULES)
        r'^(Les\s+(?:Rdv|Rendez-vous)\s+\w+)(?=\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]|\s*\(|\s*,|$)',
        # LES X ANS DE/DES/DU XXX (anniversaires)
        # Ex: "LES 20 ANS DES ARTS SERVICES" avec ... → "LES 20 ANS DES ARTS SERVICES"
        # Note: [^(»"""\'] exclut les guillemets pour éviter de les capturer dans le nom
        r'^(LES\s+\d+\s+ANS\s+(?:DE|DES|DU|D\')[^(»"""\'\s][^(»"""\']*)(?:\s*\([^)]+\))?[»"""\']?\s*(?:avec\s*:?\s*|,|$)',
        # Nom d'événement en MAJUSCULES suivi de ":" puis artistes
        # Ex: "SPRINGROCK : <b>AS YOU WANT</b>" → "SPRINGROCK"
        r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-]+?)\s*:\s*<b>',
        # Pattern "XXX présente YYY" ou "XXX présente: YYY" - XXX est le nom de l'événement
        # Ex: "Window on a Mix présente BLAST #2" → "Window on a Mix"
        # Ex: "Cortex présente: CHEWBACCA ALL STARS" → "Cortex"
        r'^([\w\s]+?)\s+présente\s*:?\s+',
        # FESTIVAL # XX avec ... - Festival en MAJUSCULES avec numéro
        # Ex: "DAMADA FESTIVAL # 11 avec ..." → "DAMADA FESTIVAL # 11"
        r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s]+\s+#\s*\d+)\s+avec\s+',
        # NOM CLUB/NIGHT avec ... - Événement en MAJUSCULES suivi de "avec" puis artistes
        # Ex: "OULALA CLUB avec QUADRUPEDE (noise rock) + ..." → "OULALA CLUB"
        # Ex: "ROCK NIGHT avec BAND1 + BAND2" → "ROCK NIGHT"
        # Le nom doit contenir au moins 2 mots et se terminer avant "avec"
        r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s]{3,}?(?:CLUB|NIGHT|PARTY|SESSION|SHOW))\s+avec\s+',
        # Pattern: "Nom Event #N:" suivi d'artistes (ex: "No Data #2: ARTISTE...")
        # Ex: "No Data #2: EUPHORIE PAR 1024..." → "No Data #2"
        r'^([\w\s]+\s*#\s*\d+)\s*:\s*[A-Z]',
        # Pattern: "Nom Event:" (Title Case) suivi d'artistes en MAJUSCULES
        # Ex: "Siestes Electroniques: HERTZ CANOPY..." → "Siestes Electroniques"
        r'^([A-ZÀ-Ÿ][a-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)+)\s*:\s*[A-Z]{2,}',
        # Pattern: "Les X:" suivi d'un spectacle entre guillemets
        # Ex: "Les Veillées: \"Traces\" (théâtre) par..." → "Les Veillées"
        r'^(Les\s+[A-ZÀ-Ÿa-zà-ÿ]+)\s*:\s*[""«]',
    ]

    for pattern in patterns:
        match = re.match(pattern, clean_text, re.IGNORECASE)
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
    - "Lu 05/Ma 06/Me 07: ..." → 3 événements (format avec slashes)

    Args:
        raw_text: Texte brut de l'événement
        base_month: Mois du Bidul
        base_year: Année du Bidul

    Returns:
        Liste de tuples (date_obj, heure, texte_nettoyé, date_str)
        Si pas de dates multiples, retourne [(None, None, raw_text, None)]
    """
    # Pattern 1: dates multiples avec jour répété
    # Ex: "Sa 07 & di 08 :", "Lu 02 & Ma 03 :", "Je 05, Sa 07, Sa 14 :", "Lu 05/Ma 06/Me 07:"
    # Format jour abrégé: Lu, Ma, Me, Je, Ve, Sa, Di (insensible à la casse)
    # Supporte les séparateurs: &, , et /
    multi_date_pattern = r'^([DLMJVS][a-z]\s*\d{1,2}(?:\s*[&,/]\s*[A-Za-z]{2,3}\s*\d{1,2})+)\s*:?\s*(.+)$'

    # Pattern 2: un seul jour de semaine suivi de plusieurs numéros
    # Ex: "Je 06,07,08 :" ou "Sa 01,08,15:" (dates consécutives ou non)
    consecutive_dates_pattern = r'^([DLMJVS][a-z])\s*(\d{1,2}(?:\s*,\s*\d{1,2})+)\s*:?\s*(.+)$'

    match = re.match(multi_date_pattern, raw_text.strip(), re.IGNORECASE | re.DOTALL)

    if not match:
        # Essayer le pattern des dates consécutives
        consec_match = re.match(consecutive_dates_pattern, raw_text.strip(), re.IGNORECASE | re.DOTALL)
        if consec_match:
            day_abbr = consec_match.group(1)
            numbers_part = consec_match.group(2)
            event_text = consec_match.group(3)

            # Extraire les numéros de jour
            day_numbers = re.findall(r'\d{1,2}', numbers_part)

            results = []
            # Heure par défaut
            default_hour_match = re.search(r'(\d{1,2}h\d{0,2})', event_text)
            default_hour = default_hour_match.group(1) if default_hour_match else None

            for day_num in day_numbers:
                day_int = int(day_num)
                try:
                    event_date = date(base_year, base_month, day_int)
                except ValueError:
                    continue

                date_str = f"{day_abbr.capitalize()} {day_num}"
                results.append((event_date, default_hour, event_text, date_str))

            if results:
                return results

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
    Ex: "...5€ Lu 05/Ma 06/Me 07: Événement..."

    Pattern de séparation: une nouvelle date au milieu du texte
    Ex: "...17h, 3/5€ Lu 02 & Ma 03 : ..."

    Attention: ne pas confondre avec les heures "sa 20h30" ou prix "7€50"

    Returns:
        Liste de textes d'événements séparés
    """
    # Pattern pour détecter une nouvelle date au milieu
    # Format: "Lu 02", "Ma 03", "Je 05", "Ve 13 & sa 14", "Lu 05/Ma 06/Me 07", etc.
    # Doit être précédé d'un espace, € ou virgule (éviter "7€50")
    # Le lookbehind (?<=[€\s,]) assure qu'on ne splitte pas sur les prix
    # Supporte les séparateurs: &, , et /
    split_pattern = r'(?<=[€\s,])\s*([DLMJVS][aeiou]\s*\d{1,2}(?:\s*[&,/]\s*[A-Za-z]{2,3}\s*\d{1,2})*)\s*:\s*'

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


# =============================================================================
# DÉTECTION SECTION RÉGIONALE "Et un peu plus loin..."
# =============================================================================

# Patterns pour détecter le début de la section régionale
# Note: \s+ inclut les sauts de ligne, donc "Et un peu \nplus loin" est matché
REGIONAL_SECTION_PATTERNS = [
    r'Et\s+un\s+peu\s+plus\s+loin\.{0,3}',  # "Et un peu plus loin..." avec ... optionnel
    r'un\s+peu\s+plus\s+loin\.{0,3}',        # OCR peut couper le "Et"
]

REGIONAL_SECTION_RE = re.compile(
    '|'.join(REGIONAL_SECTION_PATTERNS),
    re.IGNORECASE | re.MULTILINE
)


def split_regional_section(text: str) -> tuple[str, str]:
    """
    Sépare le texte en partie locale et partie régionale.

    La section régionale commence par "Et un peu plus loin..." et contient
    les événements hors département (Orne, Maine-et-Loire, etc.).

    IMPORTANT: Le marqueur doit apparaître APRÈS des événements avec des dates
    pour être considéré comme un séparateur régional. Si le marqueur apparaît
    AVANT les événements (comme dans certains anciens Biduls où c'est un sous-titre
    de la section locale), il est ignoré.

    Le texte peut avoir un header de département juste avant le marqueur:
    - "Dans l'Orne (61):"
    - "Et un peu plus loin..."

    Args:
        text: Texte brut complet

    Returns:
        Tuple (texte_local, texte_regional)
        - texte_local: Événements de la Sarthe (avant "Et un peu plus loin...")
        - texte_regional: Événements hors Sarthe (après le marqueur)

    Example:
        >>> local, regional = split_regional_section(ocr_text)
        >>> if not include_regional:
        ...     text = local  # Ignorer la partie régionale
    """
    match = REGIONAL_SECTION_RE.search(text)
    if match:
        # Trouver le début de la ligne contenant le marqueur
        start_pos = match.start()

        # VÉRIFICATION: Le marqueur doit être APRÈS des événements avec des dates
        # Si le marqueur est AVANT les dates, c'est un sous-titre (ex: "En Sarthe et même un peu plus loin...")
        # Pattern pour détecter une ligne d'événement avec date: "Lu 02:", "Ve 04:", etc.
        date_pattern = re.compile(r'^[LMJVSD][aeiou]\s+\d{1,2}\s*:', re.MULTILINE | re.IGNORECASE)
        text_before_marker = text[:start_pos]
        has_events_before = bool(date_pattern.search(text_before_marker))

        if not has_events_before:
            # Le marqueur est AVANT les événements, ne pas splitter
            logger.debug("Marqueur régional ignoré: apparaît avant les événements (sous-titre)")
            return text, ""

        # Remonter au début de la ligne
        line_start = text.rfind('\n', 0, start_pos)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1  # Après le \n

        # Vérifier si la ligne précédente contient un header de département
        # Ex: "Dans l'Orne (61):", "Dans le Maine-et-Loire (49):"
        if line_start > 0:
            prev_line_end = line_start - 1
            prev_line_start = text.rfind('\n', 0, prev_line_end)
            if prev_line_start == -1:
                prev_line_start = 0
            else:
                prev_line_start += 1

            prev_line = text[prev_line_start:prev_line_end].strip()
            # Si la ligne précédente est un header de département, l'inclure dans la section régionale
            if re.match(r"Dans\s+l[e']", prev_line, re.IGNORECASE):
                line_start = prev_line_start

        local_text = text[:line_start].strip()
        regional_text = text[line_start:].strip()

        logger.debug(f"Section régionale détectée à position {line_start}")
        logger.debug(f"  Local: {len(local_text)} caractères")
        logger.debug(f"  Régional: {len(regional_text)} caractères")

        return local_text, regional_text

    return text, ""


def split_bloc_fused_events(raw_text: str) -> list[str]:
    """
    Sépare les événements fusionnés dans un bloc (format sans dates inline).

    Dans le format "bloc", plusieurs événements d'un même jour peuvent être
    fusionnés sur une seule ligne, séparés par différents patterns:
    - Prix (X€) suivi d'un nom en MAJUSCULES, "Soirée", ou guillemet
    - Heure (XXh) suivie d'un nom en MAJUSCULES (ex: "22h Les Spectaculaires")
    - Numéro de téléphone suivi de MAJUSCULES (ex: "02 43 80 80 82 LE MANS")
    - "chapeau" suivi de MAJUSCULES (ex: "au chapeau Des Astres")

    Ex: "ARTISTE1 (style), Lieu, 21h, 0€ ARTISTE2 (style), Lieu, 20h, 3€"
    Ex: "...0€ \"Spectacle\" (th.), Lieu, 20h30"
    Ex: "...22h Les Spectaculaires: Soirée..."

    Returns:
        Liste de textes d'événements séparés
    """
    # Liste des patterns de split (groupe capturant = ce qui précède le split)
    # Chaque pattern capture le "séparateur" qui reste avec l'événement précédent
    split_patterns = [
        # Pattern 1: prix (X€) suivi de MAJUSCULES, Soirée, Birdland, ou guillemet
        r'(\d+(?:[.,/]\d+)?[€E])\s+(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]{2,}|[Ss]oir[ée]es?\s|Birdland\s|[«"<])',
        # Pattern 1b: prix en Francs (XF ou X-YF) suivi de : puis MAJUSCULES (anciens biduls)
        # Ex: "60-80F: RAG MAMA RAG" -> split avant RAG
        r'(\d+(?:[-/]\d+)?F)\s*:\s*(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]{2,})',
        # Pattern 1c: heure (XXh ou XXhXX) suivie de : puis MAJUSCULES (anciens biduls)
        # Ex: "21h30: TEMPO SLAVIA" -> split avant TEMPO
        r'(\d{1,2}h\d{0,2})\s*:\s*(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]{2,})',
        # Pattern 2: heure (XXh) suivie de nom propre commençant par majuscule - ex: "22h Les Spectaculaires"
        r'(\d{1,2}h(?:\d{2})?)\s+(?=Les\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ])',
        # Pattern 3: numéro de téléphone complet (02 XX XX XX XX) suivi de MAJUSCULES
        r'(0\d\s+\d{2}\s+\d{2}\s+\d{2}\s+\d{2})\s+(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]{2,})',
        # Pattern 4: "chapeau" suivi d'un nom propre avec deux-points
        r'(chapeau)\s+(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç]*\s*:)',
        # Pattern 5: "chapeau" suivi d'un jour de semaine (Lu/Ma/Me/Je/Ve/Sa/Di + numéro)
        # Ex: "au chapeau Ve 06/Sa 07" -> split avant Ve
        r'(chapeau)\s+(?=[LMJVSDlmjvsd][uaeie]\s+\d{1,2})',
        # Pattern 6: parenthèse fermante suivie de guillemets OCR << (double chevron)
        # Ex: "résa.) <<Pièce montée" -> split avant <<
        r'(\))\s+(?=<<[A-Za-zÀ-ÿ])',
    ]

    # Appliquer les patterns successivement
    events = [raw_text]
    for pattern in split_patterns:
        new_events = []
        for event in events:
            parts = re.split(pattern, event)
            if len(parts) <= 1:
                new_events.append(event)
            else:
                # re.split avec groupe capturant: [texte1, sep1, texte2, sep2, texte3, ...]
                # On veut: [texte1 + sep1, texte2 + sep2, texte3]
                i = 0
                while i < len(parts):
                    text_part = parts[i].strip()
                    # Si le prochain élément est un séparateur capturé, l'ajouter au texte
                    if i + 1 < len(parts):
                        sep_part = parts[i + 1]
                        combined = f"{text_part} {sep_part}".strip()
                        if combined and len(combined) >= 10:
                            new_events.append(combined)
                        i += 2
                    else:
                        # Dernier élément (après le dernier séparateur)
                        if text_part and len(text_part) >= 10:
                            new_events.append(text_part)
                        i += 1
        events = new_events

    # Nettoyer les événements vides ou trop courts
    events = [e for e in events if e and len(e.strip()) >= 10]

    return events if events else [raw_text]


def split_festival_multi_day(raw_text: str, base_month: int, base_year: int) -> list[dict]:
    """
    Détecte et splitte les festivals/événements multi-jours avec programme détaillé.

    Pattern reconnu:
    - "Festival X du 25 au 28 août 2011 ... Jeudi 25: •Event1 •Event2 Vendredi 26: •Event3..."
    - Jours complets: Lundi, Mardi, Mercredi, Jeudi, Vendredi, Samedi, Dimanche
    - Événements séparés par bullets (•, ·) ou en MAJUSCULES

    Args:
        raw_text: Texte brut contenant potentiellement un festival multi-jours
        base_month: Mois du Bidul (fallback)
        base_year: Année du Bidul (fallback)

    Returns:
        Liste de dicts avec {text, day_name, day_num, month} pour chaque événement
        Si pas de festival multi-jours, retourne []
    """
    # Pattern pour détecter un header de festival multi-jours
    festival_header_pattern = re.compile(
        r'Festival\s+\w+.*?du\s+\d+\s+au\s+\d+\s+(\w+)\s+(\d{4})',
        re.IGNORECASE
    )

    # Vérifier si c'est un festival multi-jours
    festival_match = festival_header_pattern.search(raw_text)
    if not festival_match:
        return []

    # Extraire le mois et l'année du festival
    month_name = festival_match.group(1).lower()
    year = int(festival_match.group(2))

    month_map = {
        'janvier': 1, 'février': 2, 'fevrier': 2, 'mars': 3, 'avril': 4,
        'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8, 'aout': 8,
        'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12, 'decembre': 12
    }
    festival_month = month_map.get(month_name, base_month)

    # Pattern pour les jours de la semaine complets + numéro
    day_pattern = re.compile(
        r'(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+(\d{1,2})\s*:',
        re.IGNORECASE
    )

    # Trouver tous les jours
    day_matches = list(day_pattern.finditer(raw_text))
    if not day_matches:
        return []

    # Extraire le contenu entre chaque jour
    events = []
    for i, match in enumerate(day_matches):
        day_name = match.group(1)
        day_num = int(match.group(2))

        # Trouver la fin de cette section (début du jour suivant ou fin du texte)
        start_pos = match.end()
        if i + 1 < len(day_matches):
            end_pos = day_matches[i + 1].start()
        else:
            # Pour le dernier jour, chercher la fin du contenu utile
            # Couper avant "Infos et réservations", "PASS Festival", "La Blagounette", etc.
            end_markers = [
                r'Infos\s+et\s+r[ée]servations',
                r'PASS\s+Festival',
                r'<<\s*La\s+Blagounette',
                r'Arts\s+SERVICES\s*$',
            ]
            end_pos = len(raw_text)
            for marker in end_markers:
                marker_match = re.search(marker, raw_text[start_pos:], re.IGNORECASE)
                if marker_match:
                    end_pos = min(end_pos, start_pos + marker_match.start())

        section_text = raw_text[start_pos:end_pos].strip()

        # Splitter la section par événements
        # D'abord par bullets (•, ·)
        bullet_pattern = re.compile(r'[•·]\s*')
        parts = bullet_pattern.split(section_text)

        # Filtrer les parties vides
        parts = [p.strip() for p in parts if p.strip()]

        if not parts:
            continue

        # Pour chaque partie, vérifier si elle contient une heure (= événement valide)
        hour_pattern = re.compile(r'\d{1,2}[hH]\d{0,2}')

        # Certains événements sans bullet peuvent être fusionnés dans une partie
        # Ex: "... 5€ BIONIC ORCHESTRA ..., 18h30, gratuit No Data #2: ..."
        # On doit les re-splitter par le pattern: "prix/gratuit suivi de MAJUSCULES"
        refined_parts = []
        for part in parts:
            # Pattern: prix (€ ou gratuit) suivi d'espace et MAJUSCULES (nouvel événement)
            # Aussi: "No Data #2:" pattern spécifique
            # On capture le prix pour pouvoir le réattacher
            sub_split_pattern = re.compile(
                r'(gratuit|libre|\d+(?:/\d+)?\s*[€eE])\s+(?=[A-Z]{2,}[A-Z\s]+(?:\(|,|\d{1,2}[hH])|No\s+Data)',
                re.IGNORECASE
            )
            sub_parts = sub_split_pattern.split(part)

            if len(sub_parts) > 1:
                # sub_parts alterne: [texte, prix, texte, prix, texte, ...]
                for j in range(0, len(sub_parts), 2):
                    frag = sub_parts[j].strip() if j < len(sub_parts) else ''
                    prix = sub_parts[j + 1].strip() if j + 1 < len(sub_parts) else ''

                    if not frag:
                        continue

                    # Le fragment courant + son prix
                    if prix:
                        refined_parts.append(frag + ' ' + prix)
                    else:
                        refined_parts.append(frag)
            else:
                refined_parts.append(part)

        for part in refined_parts:
            # Vérifier que c'est bien un événement (contient une heure)
            if not hour_pattern.search(part):
                continue

            # Vérifier que ce n'est pas du noise (trop court, pas de lieu/artiste)
            if len(part) < 20:
                continue

            events.append({
                'text': part,
                'day_name': day_name,
                'day_num': day_num,
                'month': festival_month,
                'year': year,
            })

    return events


def split_concatenated_festivals(raw_text: str) -> list[str]:
    """
    Splitte un raw_text contenant plusieurs événements/festivals concaténés.

    Patterns reconnus:
    - "Les festivals en juillet" ou "Les festivals en août" comme séparateur
    - "FESTI X" / "Festival X" comme début d'un nouvel événement
    - "Festival PIC NIC SHOW" etc.

    Exemple:
        "Théâtre sauvage avec la Cie... Les festivals en juillet FESTI BOUAILLE 2011 -
         Samedi 02 Juillet... Festival Kikloche - Samedi 02..."

    Devient:
        ["Théâtre sauvage avec la Cie...",
         "FESTI BOUAILLE 2011 - Samedi 02 Juillet...",
         "Festival Kikloche - Samedi 02..."]

    Args:
        raw_text: Texte brut potentiellement multi-événements

    Returns:
        Liste des événements séparés (ou [raw_text] si pas de split)
    """
    # Pattern "Les festivals en juillet/août" - séparateur de section
    section_separator = re.search(
        r'Les\s+festivals\s+en\s+(juillet|ao[uû]t)',
        raw_text,
        re.IGNORECASE
    )

    if not section_separator:
        # Pas de séparateur de section festivals
        return [raw_text]

    events = []

    # Partie avant "Les festivals en..."
    before_festivals = raw_text[:section_separator.start()].strip()
    if before_festivals and len(before_festivals) > 30:
        events.append(before_festivals)

    # Partie après "Les festivals en..."
    after_festivals = raw_text[section_separator.end():].strip()

    if not after_festivals:
        return events if events else [raw_text]

    # Splitter sur les patterns "Festival X" ou "FESTI X"
    # Pattern: "FESTI" ou "Festival" suivi d'un nom (avec accents/apostrophes)
    # Exclusions: "Festival en juillet", "Festival itinérant" (description)
    # Lookahead pour trouver les positions sans consommer
    festival_pattern = re.compile(
        r"(?=(?:FESTI(?:VAL)?|Festival)\s+(?!en\s+|itin[ée]rant\s+)[A-Za-z\u00C0-\u017F\s']+(?:\s+\d{4}|\s*-))",
        re.IGNORECASE
    )

    # Trouver toutes les positions de début de festival
    positions = [m.start() for m in festival_pattern.finditer(after_festivals)]

    if not positions:
        # Pas de pattern Festival trouvé - retourner le tout après le séparateur
        if after_festivals:
            events.append(after_festivals)
        return events if events else [raw_text]

    # Extraire chaque festival
    for i, pos in enumerate(positions):
        if i + 1 < len(positions):
            festival_text = after_festivals[pos:positions[i + 1]].strip()
        else:
            # Dernier festival - prendre jusqu'à la fin
            # Mais couper avant les signatures/citations
            end_text = after_festivals[pos:]
            # Patterns de fin à ignorer
            end_markers = [
                r'<<\s*La\s+Citation',
                r'<<\s*La\s+Blagounette',
                r'Tant\s+que\s+mes\s+chefs',
            ]
            end_pos = len(end_text)
            for marker in end_markers:
                marker_match = re.search(marker, end_text, re.IGNORECASE)
                if marker_match:
                    end_pos = min(end_pos, marker_match.start())
            festival_text = end_text[:end_pos].strip()

        if festival_text and len(festival_text) > 30:
            events.append(festival_text)

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
        # Format 7€50 (euro au milieu) - doit être en premier
        (r'(\d+)\s*[€]\s*(\d{2})\b', 'euro_middle'),
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
            # Cas spécial: format 7€50 (euro au milieu)
            if num_groups == 'euro_middle':
                euros = match.group(1)
                cents = match.group(2)
                price = float(euros) + float(cents) / 100
                raw = f"{euros}€{cents}"
                return (raw, price, price, False)

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


# =============================================================================
# STRATÉGIE "LIEU D'ABORD" - Nouvelles fonctions de parsing
# =============================================================================

def load_lieu_patterns(lieu_ref_list: list, db_path: str = None) -> list:
    """
    Prépare les patterns de recherche pour les lieux.
    Trie par longueur décroissante pour matcher les plus longs d'abord.
    Inclut les alias de la table lieu_alias.

    Args:
        lieu_ref_list: Liste de tuples (id, nom) ou (id, nom, ville)
        db_path: Chemin vers la base de données (optionnel)

    Returns:
        Liste de dicts avec pattern regex compilé, triée par longueur décroissante
    """
    import sqlite3
    from pathlib import Path

    patterns = []

    # Charger les alias depuis la base de données
    aliases = {}  # variante -> (lieu_nom, lieu_id)
    if db_path is None:
        db_path = Path(__file__).parent.parent / 'database' / 'bidul_archives.db'
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute('SELECT variante, lieu_nom FROM lieu_alias')
        for variante, lieu_nom in cursor:
            aliases[variante.lower()] = lieu_nom
        conn.close()
    except Exception:
        pass  # Si la table n'existe pas, on continue sans les alias

    # Créer un index lieu_nom -> lieu_id
    lieu_nom_to_id = {}
    for lieu_tuple in lieu_ref_list:
        lieu_id = lieu_tuple[0]
        lieu_nom = lieu_tuple[1]
        lieu_nom_to_id[lieu_nom.lower()] = lieu_id

    for lieu_tuple in lieu_ref_list:
        lieu_id = lieu_tuple[0]
        lieu_nom = lieu_tuple[1]

        # Pattern exact avec limites de mots
        # Normaliser les apostrophes pour matcher les deux types (' et ')
        lieu_nom_pattern = re.escape(lieu_nom).replace(r"\'", r"['\u2019]").replace(r"\u2019", r"['\u2019]")
        patterns.append({
            'id': lieu_id,
            'nom': lieu_nom,
            'pattern': re.compile(r'\b' + lieu_nom_pattern + r'\b', re.IGNORECASE),
            'length': len(lieu_nom)
        })

        lieu_nom_lower = lieu_nom.lower()

        # Variantes courtes pour les bars: "Bar Le Barouf" → "Le Barouf", "Barouf"
        if lieu_nom_lower.startswith('bar le '):
            # Variante "Le Barouf" (sans "Bar")
            short1 = lieu_nom[4:]  # "Le Barouf"
            patterns.append({
                'id': lieu_id,
                'nom': lieu_nom,
                'pattern': re.compile(r'(?<![a-zA-Z])\b' + re.escape(short1) + r'\b(?!\s*\()', re.IGNORECASE),
                'length': len(short1)
            })
            # Variante "Barouf" (sans "Bar Le")
            short2 = lieu_nom[7:]  # "Barouf"
            patterns.append({
                'id': lieu_id,
                'nom': lieu_nom,
                'pattern': re.compile(r'(?<![a-zA-Z])\b' + re.escape(short2) + r'\b(?!\s*\()', re.IGNORECASE),
                'length': len(short2)
            })

        elif lieu_nom_lower.startswith('bar '):
            short = lieu_nom[4:]  # sans "bar "
            patterns.append({
                'id': lieu_id,
                'nom': lieu_nom,
                'pattern': re.compile(r'(?<![a-zA-Z])\b' + re.escape(short) + r'\b(?!\s*\()', re.IGNORECASE),
                'length': len(short)
            })

        # Variantes pour les lieux avec article: "L'Oasis" → "Oasis"
        # Gérer les deux types d'apostrophes (droite ' et typographique ')
        if lieu_nom_lower.startswith("l'") or lieu_nom_lower.startswith("l'"):
            short = lieu_nom[2:]  # "Oasis"
            patterns.append({
                'id': lieu_id,
                'nom': lieu_nom,
                'pattern': re.compile(r'\b' + re.escape(short) + r'\b', re.IGNORECASE),
                'length': len(short)
            })

        # Variantes pour "Le XXX" → "XXX"
        if lieu_nom_lower.startswith('le ') and not lieu_nom_lower.startswith('le mans'):
            short = lieu_nom[3:]
            patterns.append({
                'id': lieu_id,
                'nom': lieu_nom,
                'pattern': re.compile(r'(?<![a-zA-Z])\b' + re.escape(short) + r'\b(?!\s*\()', re.IGNORECASE),
                'length': len(short)
            })

        # Variantes pour "La XXX" → "XXX"
        if lieu_nom_lower.startswith('la '):
            short = lieu_nom[3:]
            patterns.append({
                'id': lieu_id,
                'nom': lieu_nom,
                'pattern': re.compile(r'(?<![a-zA-Z])\b' + re.escape(short) + r'\b(?!\s*\()', re.IGNORECASE),
                'length': len(short)
            })

    # Ajouter les patterns pour les alias
    # Normaliser les noms pour le matching (sans accents, sans ponctuation finale)
    import unicodedata
    def normalize_for_match(s):
        # Retirer les accents et normaliser
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        # Retirer la ponctuation finale
        return s.lower().rstrip(')').strip()

    # Créer un index normalisé
    lieu_nom_normalized = {}
    for lieu_tuple in lieu_ref_list:
        lieu_id = lieu_tuple[0]
        lieu_nom = lieu_tuple[1]
        norm_key = normalize_for_match(lieu_nom)
        lieu_nom_normalized[norm_key] = (lieu_id, lieu_nom)

    for alias_variante, alias_lieu_nom in aliases.items():
        # Trouver l'id du lieu correspondant avec matching normalisé
        norm_alias_lieu = normalize_for_match(alias_lieu_nom)
        match_info = lieu_nom_normalized.get(norm_alias_lieu)
        if match_info is None:
            # Essayer un matching partiel
            for norm_key, (lid, lnom) in lieu_nom_normalized.items():
                if norm_alias_lieu in norm_key or norm_key in norm_alias_lieu:
                    match_info = (lid, lnom)
                    break
        if match_info is None:
            continue
        alias_lieu_id, alias_lieu_nom_ref = match_info
        # Ajouter le pattern pour l'alias
        patterns.append({
            'id': alias_lieu_id,
            'nom': alias_lieu_nom_ref,  # Retourne le nom du lieu_ref
            'pattern': re.compile(r'\b' + re.escape(alias_variante) + r'\b', re.IGNORECASE),
            'length': len(alias_variante)
        })

    # Trier par longueur décroissante (matcher les plus longs d'abord)
    patterns.sort(key=lambda x: x['length'], reverse=True)

    return patterns


def find_lieu_in_text_v2(text: str, lieu_patterns: list) -> Optional[tuple]:
    """
    Trouve le lieu dans le texte en utilisant les patterns préparés.

    Stratégie: matcher les patterns les plus longs en premier pour éviter
    les faux positifs (ex: "Le Barouf" avant "Barouf").

    Args:
        text: Texte à analyser
        lieu_patterns: Patterns préparés par load_lieu_patterns()

    Returns:
        (lieu_nom, lieu_id, start_pos, end_pos) ou None
    """
    for pattern_info in lieu_patterns:
        match = pattern_info['pattern'].search(text)
        if match:
            # Vérifier que ce n'est pas dans un contexte de style (parenthèses)
            before = text[:match.start()]
            if before.rstrip().endswith('('):
                continue

            # Vérifier que ce n'est pas précédé de "de" ou "du" (contexte artiste)
            # Ex: "Dr Bones & the Blue Roots" ne doit pas matcher "Blue"
            before_words = before.split()
            if before_words and before_words[-1].lower() in ('de', 'du', 'the', 'and', '&'):
                continue

            # Vérifier que le match n'est pas entre guillemets (spectacle)
            # Chercher les guillemets ouvrants et fermants avant le match
            quotes_open = ['<<', '«', '"', '"', '„']
            quotes_close = ['>>', '»', '"', '"']
            in_quotes = False

            # Compter les guillemets ouvrants et fermants avant la position du match
            for qo in quotes_open:
                count_open = before.count(qo)
                count_close = sum(before.count(qc) for qc in quotes_close)
                if count_open > count_close:
                    in_quotes = True
                    break

            if in_quotes:
                continue

            return (
                pattern_info['nom'],
                pattern_info['id'],
                match.start(),
                match.end()
            )

    return None


def split_on_dates_v2(raw_text: str) -> list[str]:
    """
    Sépare le texte sur les patterns de date au milieu.

    Patterns de séparation:
    - "Lu 02 & Ma 03 :" au milieu du texte
    - "Sa 21 & di 22 :" au milieu du texte
    - "Di 01 :" au milieu du texte
    - "Je 29 -" ou "Je 29 :" au milieu du texte
    - "Je 01/Ve 02 à 20h30:" avec horaires spécifiques

    Ne pas splitter si c'est au début (c'est une date normale).
    Ne pas splitter sur les prix comme "7€50".
    Ne pas splitter sur une date qui fait partie d'une plage (ex: "Je 23 au Sa 25").

    Exemples:
    - "...0€ Sa 21 & di 22 : ..." → split
    - "...7€50" → pas de split (prix décimal)
    - "Je 23 au Sa 25 : ..." → pas de split (plage de dates)
    - "...5€ Je 29 - Cendrillon..." → split

    Returns:
        Liste de textes d'événements séparés
    """
    # Pattern amélioré:
    # - Précédé d'un espace, €, ou fin de mot (mais pas un chiffre seul comme 7€50)
    # - NE PAS être précédé de "au " (plage de dates - mais "à " seul est OK car peut être "...5€ à")
    # - NE PAS être précédé de "et " (date additionnelle dans une date composée)
    # - Jour abrégé + numéro, optionnellement avec &, , ou / et autre jour
    # - Optionnellement suivi de "à XXh" pour les horaires spécifiques par date
    # - Suivi de ":" ou "-" (tiret comme séparateur alternatif)
    # Le lookbehind négatif évite de splitter après un prix décimal comme 7€50
    # Le lookbehind négatif sur "au " évite de splitter sur la fin d'une plage
    # Le lookbehind négatif sur "et " évite de splitter sur une date additionnelle
    # Support des plages "Du Je 23 au Sa 25:"
    # Support des horaires par date "Je 01/Ve 02 à 20h30 et Di 04 à 17h:"
    # Support des dates avec mois explicite: "Ve 01/02:" (Ve 01 février)
    # Support des plages avec mois: "Du 31 au 03/02:" (du 31 janvier au 3 février)
    # Support des caractères parasites OCR avant les dates: +, t, † (ex: "+Ma 14:", "tJe 16:")
    # Pattern strict pour les abréviations de jours (évite de matcher "de 18", "le 14", etc.)
    JOURS_ABBREV = r'(?:[Ll]u|[Mm]a|[Mm]e|[Jj]e|[Vv]e|[Ss]a|[Dd]i)'
    # Caractères parasites OCR qui peuvent précéder une date
    OCR_PARASITES = r'[+†t]?'

    split_pattern = (
        r'(?<![0-9]€)(?<!au )(?<!et )(?<!Du )(?<=[\s€,.])\s*'  # Précédé de espace/€/,/. mais pas après prix décimal, "au ", "et " ou "Du "
        rf'{OCR_PARASITES}'  # Caractère parasite OCR optionnel (+, t, †)
        rf'((?:Du\s+)?'  # Optionnel "Du "
        rf'{JOURS_ABBREV}\s*\d{{1,2}}(?:/\d{{2}})?'  # Premier jour: Lu 02 ou Ve 01/02 (avec mois optionnel)
        rf'(?:\s+(?:au|à)\s+(?:{JOURS_ABBREV}\s*)?\d{{1,2}}(?:/\d{{2}})?)?'  # Plage optionnelle: au Sa 05 ou au 03/02
        r'(?:\s+(?:(?:à|a)\s+)?\d{1,2}h\d{0,2})?'  # Horaire optionnel (avec ou sans "à"): 20h30 ou à 20h30
        rf'(?:\s*[&,/]\s*{JOURS_ABBREV}\s*\d{{1,2}}(?:/\d{{2}})?(?:\s+(?:(?:à|a)\s+)?\d{{1,2}}h\d{{0,2}})?)*'  # Jours additionnels avec horaire
        rf'(?:\s+et\s+{JOURS_ABBREV}\s*\d{{1,2}}(?:/\d{{2}})?(?:\s+(?:(?:à|a)\s+)?\d{{1,2}}h\d{{0,2}})?)*'  # "et Di 04 à 17h" optionnel
        r')\s*[:–-]\s*'  # Séparateur : ou - ou –
    )

    parts = re.split(split_pattern, raw_text, flags=re.IGNORECASE)

    # Pattern alternatif sans séparateur obligatoire
    # Date suivie d'un espace puis d'un mot commençant par majuscule (nom d'événement)
    # ou d'un guillemet ouvrant (<< ou " ou «)
    # NE PAS matcher "Du XX" car c'est le début d'une plage "Du XX au YY"
    # Utilisé pour les cas OCR où le ":" est omis (ex: "Ma 28 <<LE CIRQUE...")
    alt_pattern = (
        r'(?<![0-9]€)(?<!au )(?<!et )(?<=[\s€,.\n])\s*'
        rf'{OCR_PARASITES}'  # Caractère parasite OCR optionnel
        r'((?<!Du\s)'  # NE PAS matcher après "Du " (début de plage)
        rf'{JOURS_ABBREV}\s*\d{{1,2}}(?:/\d{{2}})?'  # Jour simple: Sa 11 ou Ve 01/02
        r')\s+'  # Juste un espace (pas de séparateur)
        r'(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ«""<][a-zA-ZÀ-ÿ\-<"]+)'  # Suivi d'un mot majuscule ou guillemet ouvrant
        r'(?!au\s)'  # NE PAS être suivi de "au " (fin de plage)
    )

    # Si pas de split avec séparateur, essayer sans séparateur sur le texte entier
    if len(parts) <= 1:
        parts = re.split(alt_pattern, raw_text, flags=re.IGNORECASE)

    if len(parts) <= 1:
        return [raw_text]

    events = []

    # Premier événement (avant le premier split)
    first_part = parts[0].strip()
    if first_part:
        # Nettoyer la fin (peut avoir des espaces ou virgules orphelins)
        # Mais attention à ne pas couper une plage de dates "Je 23 au"
        if not re.search(r'\b(?:au|à)\s*$', first_part, re.IGNORECASE):
            first_part = first_part.rstrip(',').rstrip()
        events.append(first_part)

    # Événements suivants: date + texte
    i = 1
    while i < len(parts):
        date_part = parts[i] if i < len(parts) else ''
        text_part = parts[i + 1] if i + 1 < len(parts) else ''
        if date_part and text_part.strip():
            events.append(f"{date_part} : {text_part}".strip())
        i += 2

    # Deuxième passe: appliquer le pattern alternatif sur chaque événement
    # pour séparer les cas comme "Sa 25 : Event1...100F\nMa 28 <<Event2..."
    # où le split principal a capturé l'événement avec séparateur mais pas
    # l'événement suivant sans séparateur
    final_events = []
    for event in events:
        sub_parts = re.split(alt_pattern, event, flags=re.IGNORECASE)
        if len(sub_parts) > 1:
            # Premier sous-événement
            first_sub = sub_parts[0].strip()
            if first_sub:
                if not re.search(r'\b(?:au|à)\s*$', first_sub, re.IGNORECASE):
                    first_sub = first_sub.rstrip(',').rstrip()
                final_events.append(first_sub)
            # Sous-événements suivants
            j = 1
            while j < len(sub_parts):
                sub_date = sub_parts[j] if j < len(sub_parts) else ''
                sub_text = sub_parts[j + 1] if j + 1 < len(sub_parts) else ''
                if sub_date and sub_text.strip():
                    final_events.append(f"{sub_date} : {sub_text}".strip())
                j += 2
        else:
            final_events.append(event)

    return final_events if final_events else [raw_text]


def parse_date_prefix_v2(text: str, base_month: int, base_year: int) -> tuple[list[date], str]:
    """
    Parse le préfixe de date d'une ligne.

    Ex: "Lu 02 & Ma 03 : Événement..." → [(2013-12-02), (2013-12-03)], "Événement..."
    Ex: "Di 01 : Événement..." → [(2013-12-01)], "Événement..."
    Ex: "Me 1er : Événement..." → [(2013-05-01)], "Événement..."
    Ex: "Ve 1º/Sa 02 : Événement..." → [(2013-05-01), (2013-05-02)], "Événement..."
    Ex: "Je 23 au Sa 25 : Festival..." → [(date 23), (date 24), (date 25)], "Festival..."
    Ex: "Du Vendredi 03 au Dimanche 05" → [(date 3), (date 4), (date 5)], "..."
    Ex: "Je 01/Ve 02 à 20h30 et Di 04 à 17h : Event" → [(date 1), (date 2), (date 4)], "Event"
    Ex: "Événement..." → [], "Événement..."

    Returns:
        (liste_dates, texte_restant)
    """
    # Nettoyer les indicateurs ordinaux (º ª) qui perturbent le parsing
    text = text.replace('º', '').replace('ª', '')
    text_stripped = text.strip()

    # Pattern pour les noms de jours (complets, abrégés 3 lettres, abrégés 2 lettres)
    JOURS_PATTERN = r'(?:[Ll]undi|[Mm]ardi|[Mm]ercredi|[Jj]eudi|[Vv]endredi|[Ss]amedi|[Dd]imanche|[Ll]un|[Mm]ar|[Mm]er|[Jj]eu|[Vv]en|[Ss]am|[Dd]im|[Ll]u|[Mm]a|[Mm]e|[Jj]e|[Vv]e|[Ss]a|[Dd]i)'

    # Pattern 1a0: Plage avec mois dans la date de fin (ex: "Du 31 au 03/02:" - 31 janvier au 3 février)
    range_with_month_pattern = rf'^(?:Du\s+)(?:({JOURS_PATTERN})\s+)?(\d{{1,2}})(?:er|e|ème)?\s+(?:au|à)\s+(?:({JOURS_PATTERN})\s+)?(\d{{1,2}})/(\d{{2}})\s*:?\s*(.+)$'
    range_month_match = re.match(range_with_month_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if range_month_match:
        start_day = int(range_month_match.group(2))
        end_day = int(range_month_match.group(4))
        end_month = int(range_month_match.group(5))
        event_text = range_month_match.group(6)

        dates = []
        # Si le jour de fin est avant le jour de début, le début est le mois précédent
        if end_day < start_day:
            start_month = end_month - 1 if end_month > 1 else 12
            start_year = base_year if end_month > 1 else base_year - 1
            # Plage qui traverse les mois: 31/01 au 03/02
            import calendar
            _, last_day_start = calendar.monthrange(start_year, start_month)
            for day in range(start_day, last_day_start + 1):
                try:
                    dates.append(date(start_year, start_month, day))
                except ValueError:
                    pass
            # Puis les jours du mois de fin
            for day in range(1, end_day + 1):
                try:
                    dates.append(date(base_year, end_month, day))
                except ValueError:
                    pass
        else:
            # Même mois
            for day in range(start_day, end_day + 1):
                try:
                    dates.append(date(base_year, end_month, day))
                except ValueError:
                    pass
        return dates, event_text

    # Pattern 1a: Plage de dates avec "au" ou "à" (ex: "Je 23 au Sa 25 :" ou "Du Je 23 au Sa 25 :" ou "Du Vendredi 03 au Dimanche 05")
    # Supporte les noms de jours abrégés (Je, Ve, Sa) ET complets (Jeudi, Vendredi, Samedi)
    range_pattern = rf'^(?:Du\s+)?({JOURS_PATTERN})\s*(\d{{1,2}})(?:er|e|ème)?\s+(?:au|à)\s+({JOURS_PATTERN})\s*(\d{{1,2}})(?:er|e|ème)?\s*:?\s*(.+)$'
    range_match = re.match(range_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if range_match:
        start_day = int(range_match.group(2))
        end_day = int(range_match.group(4))
        event_text = range_match.group(5)

        # Générer toutes les dates de la plage
        dates = []
        for day in range(start_day, end_day + 1):
            try:
                dates.append(date(base_year, base_month, day))
            except ValueError:
                pass
        return dates, event_text

    # Pattern 1b: Deux dates avec "et" (ex: "Samedi 04 et Dimanche 05" - juste 2 jours, pas une plage)
    two_days_pattern = rf'^({JOURS_PATTERN})\s*(\d{{1,2}})(?:er|e|ème)?\s+et\s+({JOURS_PATTERN})\s*(\d{{1,2}})(?:er|e|ème)?\s*:?\s*(.+)$'
    two_days_match = re.match(two_days_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if two_days_match:
        day1 = int(two_days_match.group(2))
        day2 = int(two_days_match.group(4))
        event_text = two_days_match.group(5)

        # Créer les deux dates (pas une plage, juste 2 dates spécifiques)
        dates = []
        try:
            dates.append(date(base_year, base_month, day1))
        except ValueError:
            pass
        try:
            dates.append(date(base_year, base_month, day2))
        except ValueError:
            pass
        return dates, event_text

    # Pattern 1c: Dates multiples avec plage à la fin (ex: "Lu 30/Ma 31/Me 01-04:")
    # Le dernier jour peut avoir une plage DD-DD indiquant continuation dans le mois suivant
    # Lu 30/Ma 31/Me 01-04: → Lu 30 (mars), Ma 31 (mars), puis Me 01 à 04 (avril)
    range_at_end_pattern = (
        rf'^({JOURS_PATTERN})\s*(\d{{1,2}})'  # Premier jour
        rf'(?:\s*[&,/]\s*(?:{JOURS_PATTERN})\s*(\d{{1,2}}))*'  # Jours intermédiaires optionnels
        rf'\s*[&,/]\s*({JOURS_PATTERN})\s*(\d{{1,2}})-(\d{{1,2}})'  # Dernier jour avec plage DD-DD
        r'\s*:\s*(.+)$'  # Séparateur : et contenu
    )
    range_end_match = re.match(range_at_end_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if range_end_match:
        # Extraire tous les jours individuels du texte
        all_days_pattern = rf'({JOURS_PATTERN})\s*(\d{{1,2}})(?!-)'
        individual_days = re.findall(all_days_pattern, text_stripped, re.IGNORECASE)

        # Extraire la plage finale
        range_pattern = rf'({JOURS_PATTERN})\s*(\d{{1,2}})-(\d{{1,2}})\s*:'
        range_match_inner = re.search(range_pattern, text_stripped, re.IGNORECASE)

        dates = []
        prev_day = 0

        # Ajouter les jours individuels
        for day_abbr, day_num in individual_days:
            day_int = int(day_num)
            # Détecter transition de mois: si le jour est plus petit que le précédent
            # et dans une séquence valide (ex: 30, 31, 1 → mois suivant pour 1)
            if day_int < prev_day and prev_day >= 28:
                # Transition au mois suivant
                next_month = base_month + 1 if base_month < 12 else 1
                next_year = base_year if base_month < 12 else base_year + 1
                try:
                    dates.append(date(next_year, next_month, day_int))
                except ValueError:
                    pass
            else:
                try:
                    dates.append(date(base_year, base_month, day_int))
                except ValueError:
                    pass
            prev_day = day_int

        # Ajouter la plage finale (toujours dans le mois suivant)
        if range_match_inner:
            range_start = int(range_match_inner.group(2))
            range_end = int(range_match_inner.group(3))
            next_month = base_month + 1 if base_month < 12 else 1
            next_year = base_year if base_month < 12 else base_year + 1

            for day in range(range_start, range_end + 1):
                try:
                    dates.append(date(next_year, next_month, day))
                except ValueError:
                    pass

        # Extraire le texte de l'événement (après le :)
        event_text = text_stripped.split(':', 1)[1].strip() if ':' in text_stripped else ''

        return dates, event_text

    # Pattern 2: Dates complexes avec horaires (ex: "Je 01/Ve 02 à 20h30 et Di 04 à 17h :")
    # Supporte aussi: "Ma 27 à 19h/Ve 30 à 20h :" (horaire après chaque jour)
    # Supporte aussi: "Ve 06/Sa 07 20h30/Di 08 15h:" (horaire sans "à" - format OCR)
    # Ce pattern capture toute la partie date complexe avant le séparateur
    complex_date_pattern = (
        r'^('
        r'[DLMJVS][a-z]\s*\d{1,2}(?:er|ère|e|ème)?'  # Premier jour
        r'(?:\s+(?:(?:à|a)\s+)?\d{1,2}h\d{0,2})?'  # Horaire optionnel (avec ou sans "à")
        r'(?:\s*[&,/]\s*[A-Za-z]{2,3}\s*\d{1,2}(?:er|ère|e|ème)?(?:\s+(?:(?:à|a)\s+)?\d{1,2}h\d{0,2})?)*'  # Jours additionnels
        r'(?:\s+(?:au|à)\s+[A-Za-z]{2,3}\s*\d{1,2}(?:er|ère|e|ème)?)?'  # Plage "au Ve 09"
        r'(?:\s+et\s+[A-Za-z]{2,3}\s*\d{1,2}(?:er|ère|e|ème)?(?:\s+(?:(?:à|a)\s+)?\d{1,2}h\d{0,2})?)*'  # "et Di 04 à 17h"
        r')'
        r'\s*[:–-]\s*(.+)$'  # Séparateur et contenu
    )
    complex_match = re.match(complex_date_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if complex_match:
        dates_part = complex_match.group(1)
        event_text = complex_match.group(2)

        # Extraire tous les jours (ignorer les suffixes ordinaux et horaires)
        day_pattern = r'([DLMJVS][a-z]|[Ll]u|[Mm]a|[Mm]e|[Jj]e|[Vv]e|[Ss]a|[Dd]i)\s*(\d{1,2})(?:er|ère|e|ème)?'
        days_found = re.findall(day_pattern, dates_part, re.IGNORECASE)

        dates = []
        for day_abbr, day_num in days_found:
            try:
                dates.append(date(base_year, base_month, int(day_num)))
            except ValueError:
                pass

        return dates, event_text

    # Pattern 3a: Date simple avec mois explicite (ex: "Ve 01/02 :" - vendredi 1er février)
    date_with_month_pattern = rf'^({JOURS_PATTERN})\s*(\d{{1,2}})/(\d{{2}})\s*:?\s*(.+)$'
    date_month_match = re.match(date_with_month_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if date_month_match:
        day_num = int(date_month_match.group(2))
        month_num = int(date_month_match.group(3))
        event_text = date_month_match.group(4)

        dates = []
        try:
            dates.append(date(base_year, month_num, day_num))
        except ValueError:
            pass
        return dates, event_text

    # Pattern 3b: Date simple avec nom de mois texte (ex: "Sa 1er Nov :" ou "Di 31 Déc")
    # Utilisé quand les dates s'étendent sur 2 mois (ex: Bidul d'octobre avec événement en novembre)
    # Pattern des noms de mois (abréviations et formes complètes)
    MOIS_NAMES_PATTERN = (
        r'(?:jan(?:v(?:ier)?)?|f[ée]v(?:rier)?|mars?|avr(?:il)?|mai|juin|'
        r'juil(?:let)?|ao[uû]t?|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?)'
    )
    date_with_month_text_pattern = rf'^({JOURS_PATTERN})\s*(\d{{1,2}})(?:er|e|ème)?\s+({MOIS_NAMES_PATTERN})\s*:?\s*(.+)$'
    date_month_text_match = re.match(date_with_month_text_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if date_month_text_match:
        day_num = int(date_month_text_match.group(2))
        month_name = date_month_text_match.group(3).lower()
        event_text = date_month_text_match.group(4)

        # Convertir le nom de mois en numéro
        month_num = MOIS_TO_NUMBER.get(month_name)
        if not month_num:
            # Essayer les formes tronquées (nov -> novembre, dec -> décembre, etc.)
            for key, val in MOIS_TO_NUMBER.items():
                if key.startswith(month_name) or month_name.startswith(key):
                    month_num = val
                    break

        if month_num:
            dates = []
            # Ajuster l'année si le mois est avant le mois de base (ex: Nov dans Bidul d'Oct)
            year = base_year
            if month_num < base_month:
                year = base_year + 1  # Mois de l'année suivante
            try:
                dates.append(date(year, month_num, day_num))
            except ValueError:
                pass
            if dates:
                return dates, event_text

    # Pattern 2b: Un jour de semaine suivi de plusieurs numéros (ex: "Je 06,07,08 :")
    # Format compact pour dates consécutives où le jour de semaine n'est pas répété
    # Ex: "Je 06,07,08 CIE VETUGADIN" → 3 dates (6, 7, 8)
    # Ex: "Sa 01,08,15 Concert" → 3 dates (1, 8, 15)
    consecutive_dates_pattern = r'^([DLMJVS][a-z])\s*(\d{1,2}(?:\s*,\s*\d{1,2})+)\s*:?\s*(.+)$'
    consecutive_match = re.match(consecutive_dates_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if consecutive_match:
        day_abbr = consecutive_match.group(1)
        numbers_part = consecutive_match.group(2)
        event_text = consecutive_match.group(3)

        # Extraire les numéros de jour
        day_numbers = re.findall(r'\d{1,2}', numbers_part)

        dates = []
        for day_num in day_numbers:
            try:
                dates.append(date(base_year, base_month, int(day_num)))
            except ValueError:
                pass

        if dates:
            return dates, event_text

    # Pattern 3: Dates simples multiples (ex: "Lu 02 & Ma 03 :")
    # Gère les suffixes ordinaux: 1er, 2e, 3ème, etc.
    # Gère les séparateurs: & , /
    date_pattern = r'^([DLMJVS][a-z]\s*\d{1,2}(?:er|e|ème)?(?:\s*[&,/]\s*[A-Za-z]{2}\s*\d{1,2}(?:er|e|ème)?)*)\s*:\s*(.+)$'

    match = re.match(date_pattern, text_stripped, re.IGNORECASE | re.DOTALL)

    if not match:
        return [], text

    dates_part = match.group(1)
    event_text = match.group(2)

    # Extraire les jours (ignorer les suffixes ordinaux)
    day_pattern = r'([DLMJVS][a-z])\s*(\d{1,2})(?:er|e|ème)?'
    days_found = re.findall(day_pattern, dates_part, re.IGNORECASE)

    dates = []
    for day_abbr, day_num in days_found:
        try:
            dates.append(date(base_year, base_month, int(day_num)))
        except ValueError:
            pass

    return dates, event_text


def extract_before_lieu(text: str, lieu_start: int) -> dict:
    """
    Extrait et parse ce qui est AVANT le lieu.
    C'est généralement: artiste/spectacle + (style)

    Si le texte contient des balises de formatage (<b>, <i>), utilise
    l'extraction basée sur le formatage pour plus de précision:
    - <b>"Spectacle"</b> → spectacle
    - <b>ARTISTE</b> → artiste musical
    - <i>(style)</i> → style

    Returns:
        dict avec 'spectacles', 'artistes', 'nom_evenement'
    """
    before = text[:lieu_start].strip().rstrip(',').strip()

    # Détecter si le texte commence par >> ou > (artiste direct sans guillemets)
    # Ex: ">> BONOME TETARD (chanson à texte)" ou "> OCT IBOR.K (rock)"
    starts_with_arrow = re.match(r'^>+\s*', before)

    # Nettoyer les symboles décoratifs au début (✪, •, ★, ⚫, →, >, etc.)
    before = re.sub(r'^[✪★☆●○◆◇■□▲△▼▽♦♠♣♥•·⚫⚪→➔➜➤>\-–—\s]+', '', before).strip()

    result = {
        'spectacles': [],
        'artistes': [],
        'nom_evenement': None,
        'style_evenement': None
    }

    # Pattern "//" pour les festivals: "Festival X #N (style) // ARTISTES"
    # Le nom d'événement est AVANT le //, les artistes sont APRÈS
    # Ex: "Festival Les DéciBeilles #1 // <b>LES BONS TUYAUX</b>..."
    # Ex: "Plein Champ #3 (festival d'arts urbains) // <b>JULIEN LEBRUN</b>..."
    double_slash_match = re.search(r'^(.+?)\s*//\s*(.+)$', before)
    if double_slash_match:
        event_part = double_slash_match.group(1).strip()
        artistes_part = double_slash_match.group(2).strip()

        # Extraire le style s'il est entre parenthèses à la fin du nom
        # Ex: "Plein Champ #3 (festival d'arts urbains)" → nom="Plein Champ #3", style="festival d'arts urbains"
        style_match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', event_part)
        if style_match:
            result['nom_evenement'] = style_match.group(1).strip()
            result['style_evenement'] = style_match.group(2).strip()
        else:
            result['nom_evenement'] = event_part

        # Continuer le parsing avec seulement la partie artistes
        before = artistes_part

    # Si le texte commençait par >> ou >, c'est un artiste direct (pas un spectacle)
    # Ex: ">> BONOME TETARD (chanson à texte)" → artiste = "BONOME TETARD", style = "chanson à texte"
    if starts_with_arrow:
        # Pattern: ARTISTE (style) - artiste en majuscules suivi optionnellement d'un style
        arrow_artiste_match = re.match(
            r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\.\-\&\']+?)(?:\s*\(([^)]+)\))?\s*(?:,|$)',
            before
        )
        if arrow_artiste_match:
            artiste_nom = arrow_artiste_match.group(1).strip()
            artiste_style = arrow_artiste_match.group(2).strip() if arrow_artiste_match.group(2) else None
            if artiste_nom and len(artiste_nom) > 2:
                result['artistes'].append({'nom': artiste_nom, 'style': artiste_style})
            # Retirer l'artiste du before pour ne pas le re-parser
            before = before[arrow_artiste_match.end():].strip()
            if before.startswith(','):
                before = before[1:].strip()

    # Pattern "XXX présente YYY (style)" ou "XXX présente: YYY (style)" - XXX est le nom de l'événement, YYY est l'artiste
    # Ex: "Window on a Mix présente BLAST #2 featuring MLC aka Lucien Moullec (House)"
    # Ex: "Cortex présente: CHEWBACCA ALL STARS (soul-garage)"
    presente_match = re.search(
        r'^(.+?)\s+présente\s*:?\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-Za-zÀ-ÿ\s\.\-\&\'#\d]+?)(?:\s*\(([^)]+)\))?\s*(?:,|\+|$)',
        before, re.IGNORECASE
    )
    if presente_match:
        event_name = presente_match.group(1).strip()
        artiste_nom = presente_match.group(2).strip()
        artiste_style = presente_match.group(3).strip() if presente_match.group(3) else None
        if event_name:
            result['nom_evenement'] = event_name
        if artiste_nom and len(artiste_nom) > 2:
            result['artistes'].append({'nom': artiste_nom, 'style': artiste_style})
        # Retirer du before pour ne pas re-parser
        before = before[presente_match.end():].strip()
        if before.startswith(','):
            before = before[1:].strip()

    # Pattern spécial: "NOM AVEC: - *SPECTACLE", (style), Cie ARTISTE - ..."
    # Ex: "LES RENDEZ-VOUS SPECTACLES DE Bouloire (72) AVEC: - *LE CLARINETTISTE", (théâtre), Cie Spectabilis"
    # Ex: "Sa 01 LES RENDEZ-VOUS SPECTACLES DE Bouloire..." (avec préfixe de date)
    # Format: plusieurs spectacles listés avec tirets, chaque spectacle a:
    # - guillemet OCR (* ou <<) + nom + guillemet fermant (")
    # - style entre parenthèses
    # - "Cie" suivi du nom de la compagnie
    # Note: ce pattern doit matcher sur le texte COMPLET (before), pas juste une partie
    if not result['nom_evenement']:
        # Le pattern accepte un préfixe de date optionnel (ex: "Sa 01 ")
        # et capture tout le texte y compris ce qui vient après le lieu initial
        avec_liste_match = re.match(
            r'^(?:[A-Za-z]{2}\s+\d{1,2}\s+)?((?:LES\s+)?[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-Za-zÀ-ÿ\-\s]+?)(?:\s+DE\s+([A-Za-zÀ-ÿ\-]+))?\s*(?:\(\d+\))?\s*AVEC\s*:\s*(.+)',
            before, re.IGNORECASE | re.DOTALL
        )
        if avec_liste_match:
            liste_part = avec_liste_match.group(3)
            # Vérifier que la liste contient bien des spectacles avec tirets et guillemets OCR
            if re.search(r'-\s*(?:\*|<<)[^"]+"\s*,?\s*\([^)]+\)', liste_part):
                event_name = avec_liste_match.group(1).strip()
                # Ajouter le lieu si présent (ex: "DE Bouloire")
                if avec_liste_match.group(2):
                    event_name += f" DE {avec_liste_match.group(2).strip()}"
                result['nom_evenement'] = event_name

                # Parser les spectacles dans la liste
                # Pattern: - *NOM" ou - <<NOM", suivi de (style), puis Cie NOM
                spectacle_liste_pattern = re.compile(
                    r'-\s*(?:\*|<<)([^"]+)"\s*,?\s*\(([^)]+)\)\s*,?\s*(?:Cie\s+)?([^-]+?)(?=\s*-\s*(?:\*|<<)|Grange|Salle|Centre|Espace|$)',
                    re.IGNORECASE
                )
                for spec_match in spectacle_liste_pattern.finditer(liste_part):
                    spec_nom = spec_match.group(1).strip()
                    spec_style = spec_match.group(2).strip()
                    artiste_nom = spec_match.group(3).strip().rstrip(',').strip()

                    if spec_nom and len(spec_nom) > 1:
                        result['spectacles'].append({'nom': spec_nom, 'style': spec_style})
                    if artiste_nom and len(artiste_nom) > 1:
                        # Ajouter "Cie" si pas déjà présent
                        if not artiste_nom.lower().startswith('cie '):
                            artiste_nom = f"Cie {artiste_nom}"
                        result['artistes'].append({'nom': artiste_nom, 'style': spec_style, 'spectacle': spec_nom})

                # Le parsing est terminé pour ce format
                return result

    # Pattern "NomEvent avec ARTISTES" ou "NomEvent avec: ARTISTES"
    # Ex: "Snamshit Troopers part. 1 avec MARTI + KOR + NOTORIOUS NEST (électro)"
    # Ex: "L'instant Eclectik avec ERNESTINE (rock/fusion) + BABEL"
    # Ex: "Drum'n'Breaks Party avec K-POERA + GOLGOTT 14"
    # Ex: "Festival Cosmozik avec: DEEP & BRISK (électro) + AIRLINES (rock)"
    # Le nom d'événement doit:
    # - Commencer par une majuscule (ou apostrophe suivie de majuscule pour L'instant, etc.)
    # - Contenir au moins une minuscule (pas tout MAJUSCULES)
    # - Être suivi de "avec" ou "avec:" puis d'artistes en MAJUSCULES
    # Le groupe artistes capture tout après "avec:" jusqu'à la fin (styles inclus)
    if not result['nom_evenement']:
        # Pattern avec guillemets optionnels pour gérer "Festival Cosmozik" avec: ...
        # Aussi capture un style optionnel entre parenthèses: "Les Rdv Conservatoire (jazz) avec ..."
        # Ex: "Born 2 Moonwalk Party avec ARTISTES" - les chiffres sont autorisés
        avec_artistes_match = re.match(
            r'^[\"«""„]?([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇL\'][A-Za-zÀ-ÿ\'0-9]+(?:[\s\-\'&][A-Za-zÀ-ÿ\'0-9]+)*(?:\s+(?:part|vol|n°|#)\.?\s*\d+)?)[\"»""]?\s*(?:\(([^)]+)\))?\s+avec\s*:?\s*(.+)',
            before
        )
        if avec_artistes_match:
            event_name = avec_artistes_match.group(1).strip()
            event_style = avec_artistes_match.group(2).strip() if avec_artistes_match.group(2) else None
            artistes_part = avec_artistes_match.group(3).strip()
            # Vérifier que le nom n'est pas tout en majuscules (sinon c'est un artiste)
            # et qu'il contient au moins une minuscule
            has_lowercase = any(c.islower() for c in event_name)
            if has_lowercase and len(event_name) > 3:
                result['nom_evenement'] = event_name
                # Si un style a été capturé (ex: "Les Rdv Conservatoire (jazz)"), l'utiliser comme genre
                if event_style and not result.get('genre_evenement'):
                    result['genre_evenement'] = event_style
                # Utiliser directement la partie artistes capturée par le regex
                before = artistes_part

                # D'abord gérer "la Cie "XXX"" ou "la Cie XXX" qui peut rester après "avec"
                cie_quoted = re.match(r'^la\s+[Cc]ie\s+"([^"]+)"', before)
                if cie_quoted:
                    nom = cie_quoted.group(1).strip()
                    if nom and len(nom) > 2:
                        result['artistes'].append({'nom': f"Cie {nom}", 'style': None})
                    before = before[cie_quoted.end():].strip()

                # Parser les artistes restants (format: ARTISTE (style) + ARTISTE2 (style2)...)
                # Le texte commence maintenant directement par les artistes
                artiste_avec_style = re.match(
                    r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\'\&0-9]+?)\s*\(([^)]+)\)',
                    before
                )
                if artiste_avec_style:
                    nom = artiste_avec_style.group(1).strip()
                    style = artiste_avec_style.group(2).strip()
                    if nom and len(nom) > 1:
                        result['artistes'].append({'nom': nom, 'style': style})
                        # Retirer ce qu'on a parsé pour continuer avec d'éventuels autres artistes
                        before = before[artiste_avec_style.end():].strip()
                        # Continuer à parser les artistes suivants séparés par + ou ,
                        while before.startswith('+') or before.startswith(','):
                            before = before[1:].strip()
                            next_artiste = re.match(
                                r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\'\&0-9]+?)\s*\(([^)]+)\)',
                                before
                            )
                            if next_artiste:
                                nom = next_artiste.group(1).strip()
                                style = next_artiste.group(2).strip()
                                if nom and len(nom) > 1:
                                    result['artistes'].append({'nom': nom, 'style': style})
                                before = before[next_artiste.end():].strip()
                            else:
                                # Artiste sans style
                                next_artiste_no_style = re.match(
                                    r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\'\&0-9]+?)(?:\s*[\+,]|\s*$|\s+de\s|\s+\d{1,2}h)',
                                    before
                                )
                                if next_artiste_no_style:
                                    nom = next_artiste_no_style.group(1).strip()
                                    if nom and len(nom) > 1:
                                        result['artistes'].append({'nom': nom, 'style': None})
                                    before = before[next_artiste_no_style.end():].strip()
                                else:
                                    break
                else:
                    # Premier artiste sans style (ex: "SAMUEL FOUCAULT TRIO, Lieu, 15h")
                    artiste_no_style = re.match(
                        r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\'\&0-9]+?)(?:\s*,|\s*\+|\s*$)',
                        before
                    )
                    if artiste_no_style:
                        nom = artiste_no_style.group(1).strip()
                        if nom and len(nom) > 1:
                            result['artistes'].append({'nom': nom, 'style': None})
                        before = before[artiste_no_style.end():].strip()

    # Pattern "NomEvent animée par ARTISTE" - NomEvent est en Title Case
    # Ex: "Afro-latino Party animée par BAILA SUAVE"
    if not result['nom_evenement']:
        animee_par_match = re.match(
            r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç\-]+(?:[\s\-][A-Za-zÀ-ÿ\-]+)*)\s+anim[ée]+\s+par\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-]+)',
            before, re.IGNORECASE
        )
        if animee_par_match:
            event_name = animee_par_match.group(1).strip()
            if not event_name.isupper() and len(event_name) > 3:
                result['nom_evenement'] = event_name

    # Pattern "NomEvent: ARTISTES" - Événement nommé suivi d'artistes
    # Variantes:
    # - "No Data #2: EUPHORIE PAR 1024..." (avec numéro)
    # - "Siestes Electroniques: HERTZ CANOPY..." (Title Case sans numéro)
    if not result['nom_evenement']:
        # D'abord essayer avec numéro (#N)
        event_colon_match = re.match(
            r'^([\w\s]+\s*#\s*\d+)\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ].+)',
            before
        )
        # Sinon essayer Title Case sans numéro
        if not event_colon_match:
            event_colon_match = re.match(
                r'^([A-ZÀ-Ÿ][a-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)+)\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ].+)',
                before
            )
        if event_colon_match:
            result['nom_evenement'] = event_colon_match.group(1).strip()
            # Le reste est la liste des artistes - parser maintenant
            artistes_text = event_colon_match.group(2).strip()
            # Splitter par "+" pour les artistes multiples
            segments = re.split(r'\s*\+\s*', artistes_text)
            for segment in segments:
                segment = segment.strip()
                if not segment:
                    continue
                # Pattern: ARTISTE (FORMATION) (genre) ou ARTISTE (genre)
                # Ex: "DEBRUIT (FULL LIVE BAND) (electro ethnique & visuels)"
                # Ex: "CLARA CLARA (pop électronique)"
                # Ex: "EUPHORIE PAR 1024 (installation vidéo sonore)"
                # Note: utiliser greedy (+) pas lazy (+?) pour capturer le nom complet
                # Pattern 1: "Spectacle" par ARTISTE (style)
                # Ex: "< Axes " par PERCEVAL MUSIC ET LAURENT CHOMETTE (installation vidéo sonore)
                spectacle_par_match = re.match(
                    r'^[""«<]+[^""»>]+[""»>]+\s+par\s+'
                    r'([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-&]+)'
                    r'(?:\s*\(([^)]+)\))?',
                    segment
                )
                if spectacle_par_match:
                    nom = spectacle_par_match.group(1).strip()
                    genre = spectacle_par_match.group(2).strip() if spectacle_par_match.group(2) else None
                    if nom and len(nom) >= 3:
                        result['artistes'].append({'nom': nom, 'style': genre})
                    continue

                # Pattern 2: ARTISTE (FORMATION) (genre) ou ARTISTE (genre)
                # Ex: "DEBRUIT (FULL LIVE BAND) (electro ethnique & visuels)"
                # Ex: "CLARA CLARA (pop électronique)"
                # Ex: "EUPHORIE PAR 1024 (installation vidéo sonore)"
                # Note: utiliser greedy (+) pas lazy (+?) pour capturer le nom complet
                match = re.match(
                    r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-&0-9]+)'  # Nom artiste (greedy)
                    r'(?:\s*\(([A-Z][^)]+)\))?'  # Optionnel: (FORMATION) en majuscules
                    r'(?:\s*\(([^)]+)\))?',  # Optionnel: (genre)
                    segment
                )
                if match:
                    nom = match.group(1).strip()
                    # Si formation (group 2), l'inclure dans le nom
                    if match.group(2):
                        nom = f"{nom} ({match.group(2)})"
                    # Genre: group 3 si présent, sinon group 2 si pas en majuscules
                    genre = None
                    if match.group(3):
                        genre = match.group(3).strip()
                    elif match.group(2) and not match.group(2).isupper():
                        # Le group 2 n'est pas une formation mais un genre
                        genre = match.group(2).strip()
                    if nom and len(nom) >= 3:
                        result['artistes'].append({'nom': nom, 'style': genre})
            # Mise à jour de before pour éviter un re-parsing
            before = ""

    # Utiliser l'extraction basée sur le formatage si disponible
    if has_formatting_tags(before):
        # Extraction basée sur le formatage (plus précise)
        result['spectacles'] = extract_formatted_spectacles(before)
        # Ajouter aussi les spectacles sans guillemets (suivis de "par")
        result['spectacles'].extend(extract_formatted_spectacles_unquoted(before))
        result['artistes'] = extract_formatted_artistes_musicaux(before)

        # Pour les artistes de théâtre (non gras), on continue avec le parsing classique
        # sur le texte sans balises
        before_stripped = strip_formatting_tags(before)

        # Vérifier si c'est un événement nommé (Soirée X, Festival, etc.)
        # Note: On teste d'abord avec les balises (pour matcher "NOM : <b>artiste</b>")
        # puis sans balises pour les autres patterns
        event_name = extract_event_name(before) or extract_event_name(before_stripped)
        if event_name:
            result['nom_evenement'] = event_name
            # Retirer le nom d'événement du texte pour continuer à parser les artistes
            if before.startswith(event_name):
                before = before[len(event_name):].strip()
                before_stripped = strip_formatting_tags(before)
            elif before_stripped.startswith(event_name):
                before_stripped = before_stripped[len(event_name):].strip()
                before = before_stripped  # Utiliser la version sans le nom

        # Pattern "guests" ou "guests!!"
        if re.search(r'\bguests?!*\b', before_stripped, re.IGNORECASE):
            result['artistes'].append({'nom': 'Guests', 'style': None, 'is_musical': True})

        # Extraire les artistes de théâtre: "par XXX" après un spectacle
        # Ces artistes ne sont PAS en gras
        # IMPORTANT: l'ordre est important - les patterns plus spécifiques d'abord
        par_patterns = [
            # "par la Cie XXX" avec guillemets
            (r'par\s+la\s+[Cc]ie\s+[«""„]([^»""]+)[»""]', 'Cie '),
            # "par la Cie XXX" sans guillemets - attention à ne pas matcher trop
            (r'par\s+la\s+[Cc]ie\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-]+?)(?:\s*,|\s*$)', 'Cie '),
            (r'par\s+la\s+[Cc]ompagnie\s+([^,\(\)]+?)(?:\s*,|\s*$)', 'Cie '),
            (r'par\s+le\s+chœur\s+([^,\(\)]+?)(?:\s*,|\s*$)', 'Chœur '),
            (r'par\s+le\s+collectif\s+([^,\(\)]+?)(?:\s*,|\s*$)', 'Collectif '),
            # "par Prénom Nom" - nom de personne (Béatrice Maine, etc.)
            (r'par\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç]+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç]+)+)', ''),
        ]

        for pattern, prefix in par_patterns:
            match = re.search(pattern, before_stripped, re.IGNORECASE)
            if match:
                nom = match.group(1).strip().rstrip(',')
                if nom and len(nom) > 2:
                    full_nom = f"{prefix}{nom}" if prefix else nom
                    # Vérifier que ce n'est pas déjà dans les artistes
                    if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                        result['artistes'].append({'nom': full_nom, 'style': None, 'is_musical': False})
                # Sortir après le premier match pour éviter les doublons
                break

        # Pattern "avec la Cie XXX" (pour les artistes de théâtre)
        avec_patterns = [
            # "avec la Cie "XXX"" avec guillemets ASCII
            (r'avec\s+la\s+[Cc]ie\s+"([^"]+)"', 'Cie '),
            # "avec la Cie «XXX»" avec guillemets typographiques
            (r'avec\s+la\s+[Cc]ie\s+[«""„]([^»""]+)[»""]', 'Cie '),
            # "avec la Cie XXX" sans guillemets
            (r'avec\s+la\s+[Cc]ie\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-]+?)(?:\s*,|\s*$)', 'Cie '),
            (r'avec\s+la\s+[Cc]ompagnie\s+([^,\(\)]+?)(?:\s*,|\s*$)', 'Cie '),
        ]

        for pattern, prefix in avec_patterns:
            match = re.search(pattern, before_stripped, re.IGNORECASE)
            if match:
                nom = match.group(1).strip().rstrip(',')
                if nom and len(nom) > 2:
                    full_nom = f"{prefix}{nom}" if prefix else nom
                    if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                        result['artistes'].append({'nom': full_nom, 'style': None, 'is_musical': False})
                break

        # Pattern "Cie XXX" directement après spectacle (sans "par" ni "avec")
        # Ex: "<b>Spectacle</b>" Cie Ordinaire d'exception (<i>style</i>)
        # Supporte apostrophe droite (') et curly (\u2019)
        if not result['artistes']:
            cie_direct_match = re.search(
                r'[Cc]ie\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\u2019\-/&]+?)(?:\s*,|\s*\d{1,2}h|\s*\(|\s*<|\s*$)',
                before_stripped
            )
            if cie_direct_match:
                nom = cie_direct_match.group(1).strip().rstrip(',')
                if nom and len(nom) > 2:
                    full_nom = f"Cie {nom}"
                    if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                        result['artistes'].append({'nom': full_nom, 'style': None, 'is_musical': False})

        # Pattern "collectif XXX" directement après spectacle (sans "par" ni "avec")
        # Ex: "«Spectacle» (théâtre), collectif Grand Maximum"
        if not result['artistes']:
            collectif_direct_match = re.search(
                r'[Cc]ollectif\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\u2019\-/&]+?)(?:\s*,|\s*\d{1,2}h|\s*\(|\s*<|\s*$)',
                before_stripped
            )
            if collectif_direct_match:
                nom = collectif_direct_match.group(1).strip().rstrip(',')
                if nom and len(nom) > 2:
                    full_nom = f"Collectif {nom}"
                    if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                        result['artistes'].append({'nom': full_nom, 'style': None, 'is_musical': False})

        return result

    # === Fallback: extraction classique sans formatage ===

    # 0. Extraire le nom d'événement et le retirer du texte pour parser la suite
    event_name = extract_event_name(before)
    if event_name and not result['nom_evenement']:
        result['nom_evenement'] = event_name
        # Retirer le nom d'événement du texte pour continuer à parser les artistes
        if before.startswith(event_name):
            before = before[len(event_name):].strip()

    # 0a. Pattern "SpectacleName Cie XXX (style)" - spectacle sans guillemets suivi de Cie
    # Ex: "45° sans eau Cie KL (danse contemporaine)" → spectacle="45° sans eau", cie="Cie KL"
    # Ce pattern doit être testé AVANT les autres pour éviter que Cie soit mal parsé
    # D'abord, retirer "avec:" ou "avec :" du début si présent
    # NOTE: Ne pas matcher si le texte commence par des guillemets OCR (<<, «, ", etc.)
    #       car ces cas sont gérés par pattern 1c
    spectacle_text = before
    if re.match(r'^avec\s*:\s*', before, re.IGNORECASE):
        spectacle_text = re.sub(r'^avec\s*:\s*', '', before, flags=re.IGNORECASE)
        before = spectacle_text  # Mettre à jour before aussi
    # Skip si le texte commence par des guillemets (OCR ou typographiques)
    starts_with_quote = re.match(r'^(?:<<|[«""„<])', spectacle_text)
    spectacle_cie_match = None
    if not starts_with_quote:
        spectacle_cie_match = re.match(
            r'^([^(]+?)\s+[Cc]ie\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-]+?)\s*\(([^)]+)\)',
            spectacle_text
        )
    if spectacle_cie_match:
        spectacle_nom = spectacle_cie_match.group(1).strip()
        cie_nom = spectacle_cie_match.group(2).strip()
        style = spectacle_cie_match.group(3).strip()
        # Ajouter le spectacle
        if spectacle_nom and len(spectacle_nom) > 1:
            result['spectacles'].append({'nom': spectacle_nom, 'style': style})
        # Ajouter la Cie
        if cie_nom and len(cie_nom) > 1:
            result['artistes'].append({'nom': f"Cie {cie_nom}", 'style': style})
        # Retirer ce pattern du texte
        before = spectacle_text[spectacle_cie_match.end():].strip()
        if before.startswith(','):
            before = before[1:].strip()

    # 0b. D'abord essayer extract_formatted_spectacles qui gère << et autres patterns OCR
    formatted_spectacles = extract_formatted_spectacles(before)
    if formatted_spectacles:
        result['spectacles'].extend(formatted_spectacles)

    # 0c. D'abord extraire "avec la Cie "XXX"" AVANT les spectacles
    # pour ne pas que le nom de la Cie soit extrait comme spectacle
    avec_cie_quoted = re.search(r'avec\s+la\s+[Cc]ie\s+"([^"]+)"', before)
    if avec_cie_quoted:
        nom = avec_cie_quoted.group(1).strip()
        if nom and len(nom) > 2:
            result['artistes'].append({'nom': f"Cie {nom}", 'style': None})
        # Retirer ce pattern du texte pour ne pas le re-parser
        before = before[:avec_cie_quoted.start()] + before[avec_cie_quoted.end():]
        before = re.sub(r'\s+', ' ', before).strip()

    # 1. Extraire les spectacles entre guillemets ET le pattern "de ARTISTE (style)"
    # Pattern: "Spectacle" de ARTISTE (style) ou "Spectacle" (style) de ARTISTE
    # Ex: "Abeilles" de GILLES GRANOUILLET (travelling théâtre)
    spectacle_de_pattern = r'[«""„]([^»""]+)[»""](?:\s*\(([^)]+)\))?\s+de\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\&\']+)(?:\s*\(([^)]+)\))?'
    de_match = re.search(spectacle_de_pattern, before)
    if de_match:
        # Spectacle
        result['spectacles'].append({
            'nom': de_match.group(1).strip(),
            'style': de_match.group(2).strip() if de_match.group(2) else None
        })
        # Artiste avec style
        artiste_nom = de_match.group(3).strip()
        artiste_style = de_match.group(4).strip() if de_match.group(4) else None
        if artiste_nom and len(artiste_nom) > 2:
            result['artistes'].append({'nom': artiste_nom, 'style': artiste_style})
        # Retirer ce pattern du texte
        before = before[:de_match.start()] + before[de_match.end():]
        before = re.sub(r'\s+', ' ', before).strip()

    # 1a. Pattern "spectacle" - Cie XXX (style) - spectacle entre guillemets suivi de tiret et Cie
    # Ex: '"45° sans eau" - Cie KL (jonglage)' → spectacle="45° sans eau", artiste="Cie KL", style="jonglage"
    # Ce pattern doit être traité AVANT les spectacles simples pour associer correctement
    spectacle_tiret_cie_pattern = r'[«""„]([^»""]+)[»""]\s*-\s*[Cc]ie\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-]+?)\s*\(([^)]+)\)'
    spectacle_tiret_cie_matches = list(re.finditer(spectacle_tiret_cie_pattern, before))
    for match in spectacle_tiret_cie_matches:
        spectacle_nom = match.group(1).strip()
        cie_nom = match.group(2).strip()
        style = match.group(3).strip()
        # Ajouter l'artiste avec le spectacle associé
        if cie_nom and len(cie_nom) > 1:
            result['artistes'].append({
                'nom': f"Cie {cie_nom}",
                'style': style,
                'spectacle': spectacle_nom
            })
        # Retirer ce pattern du texte pour ne pas le re-parser
        before = before.replace(match.group(0), ' ')
    before = re.sub(r'\s+', ' ', before).strip()

    # 1c. Pattern: <<Spectacle" par la Cie XXX (style) - guillemets OCR << et "
    # Ex: '<<LE CIRQUE CLANDESTIN" par la Cie Les Frères Kazamaroffs (spectacle musical)'
    # Le << est un artefact OCR pour « et " est le fermant
    # Note: le style (entre parenthèses) vient APRÈS le nom de la Cie, et est requis pour matcher
    ocr_spectacle_par_cie = re.search(
        r'<<([^"]+)"\s+par\s+(?:la\s+)?[Cc]ie\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-]+?)\s*\(([^)]+)\)',
        before
    )
    if ocr_spectacle_par_cie:
        spectacle_nom = ocr_spectacle_par_cie.group(1).strip()
        cie_nom = ocr_spectacle_par_cie.group(2).strip()
        style = ocr_spectacle_par_cie.group(3).strip() if ocr_spectacle_par_cie.group(3) else None
        if spectacle_nom and len(spectacle_nom) > 1:
            result['spectacles'].append({'nom': spectacle_nom, 'style': style})
        if cie_nom and len(cie_nom) > 1:
            result['artistes'].append({'nom': f"Cie {cie_nom}", 'style': style})
        # Retirer ce pattern du texte
        before = before[:ocr_spectacle_par_cie.start()] + before[ocr_spectacle_par_cie.end():]
        before = re.sub(r'\s+', ' ', before).strip()

    # Spectacles simples entre guillemets (sans "de ARTISTE")
    # Ne pas ajouter les spectacles déjà trouvés par extract_formatted_spectacles
    # Inclut << et * comme guillemets ouvrants OCR (* peut être confondu avec « dans les scans)
    # Note: exclure les cas où * est suivi d'un jour de la semaine (Sa, Di, etc.) car c'est un bullet
    spectacle_pattern = r'(?:[«""„]|<<|\*(?![SsLlMmJjVvDd][aeiou]\s+\d))([^»""]+)(?:[»""]|>>|(?<=[A-Z])")(?:\s*,?\s*\(([^)]+)\))?'
    spectacle_matches = list(re.finditer(spectacle_pattern, before))

    for match in spectacle_matches:
        nom_raw = match.group(1).strip()
        style = match.group(2).strip() if match.group(2) else None
        # Nettoyer les balises HTML du nom (ex: "<b>Concert</b>" -> "Concert")
        nom = re.sub(r'</?[bi]>', '', nom_raw).strip()
        # Éviter les doublons et exclure les événements nommés (festivals, soirées)
        # qui ne sont pas des spectacles mais des noms d'événements
        is_event_name = is_named_event(nom) or nom.lower().startswith('festival')
        if is_event_name:
            # C'est un nom d'événement, pas un spectacle
            if not result['nom_evenement']:
                result['nom_evenement'] = nom
            continue
        # Vérifier si ce spectacle existe déjà (peut-être avec un style)
        existing = next((s for s in result['spectacles'] if s['nom'].lower() == nom.lower()), None)
        if existing:
            # Si le spectacle existe déjà avec un style, ne pas écraser
            # Si le spectacle existe sans style et on a un style, mettre à jour
            if not existing.get('style') and style:
                existing['style'] = style
        else:
            result['spectacles'].append({'nom': nom, 'style': style})

    # Retirer les spectacles du texte pour parser le reste
    remaining = before
    for match in spectacle_matches:
        remaining = remaining.replace(match.group(0), ' ')
    remaining = re.sub(r'\s+', ' ', remaining).strip()

    # 1b. Pattern: Cie/compagnie après spectacle (sans "par" ni "de")
    # Ex: "\"Cendrillon\" (théâtre) Antartic°K Cie" → "Antartic°K Cie"
    # Ex: "\"Spectacle\" (style), Cie Ceux de l'atelier" → "Cie Ceux de l'atelier"
    # Chercher les patterns Cie dans remaining

    # D'abord: Pattern "XXX Cie" (nom suivi de Cie) - résultat: "XXX Cie"
    # Exclure "par la Cie" qui sera géré par par_cie_patterns
    cie_suffix_match = re.search(r'(?<!par\s)(?<!la\s)\b([A-Za-zÀ-ÿ°][A-Za-zÀ-ÿ°\s\'\-]*?)\s+[Cc]ie\b', remaining)
    if cie_suffix_match:
        nom = cie_suffix_match.group(1).strip()
        # Exclure si le nom est juste "la" ou "par la"
        if nom and len(nom) > 2 and nom.lower() not in ('la', 'par la', 'par'):
            full_nom = f"{nom} Cie"
            if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                result['artistes'].append({'nom': full_nom, 'style': None})

    # Ensuite: Pattern ", Cie XXX" ou "Cie XXX" - résultat: "Cie XXX"
    # Supporte les noms avec "/" pour duo/groupe: "Cie Robin/Juteau"
    # Supporte aussi "Cie XXX (<i>style</i>)" où le style vient après
    if not cie_suffix_match:
        cie_prefix_match = re.search(r'(?:,\s*|^|\s)[Cc]ie\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-/&]+?)(?:\s*,|\s*\d{1,2}h|\s*\(|\s*<|\s*$)', remaining)
        if cie_prefix_match:
            nom = cie_prefix_match.group(1).strip().rstrip(',')
            if nom and len(nom) > 2:
                full_nom = f"Cie {nom}"
                if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                    result['artistes'].append({'nom': full_nom, 'style': None})

    # 1c. Pattern "collectif XXX" après un spectacle (sans "par")
    # Ex: '"Nous ne viendrons pas manger dimanche" (théâtre) collectif Grand Maximum'
    # Note: peut être au début du remaining (après suppression du spectacle), donc on autorise ^
    collectif_match = re.search(r'(?:^|,\s*|\s)[Cc]ollectif\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-/&]+?)(?:\s*,|\s*\d{1,2}h|\s*\(|\s*<|\s*$)', remaining)
    if collectif_match:
        nom = collectif_match.group(1).strip().rstrip(',')
        if nom and len(nom) > 2:
            full_nom = f"Collectif {nom}"
            if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                result['artistes'].append({'nom': full_nom, 'style': None})

    # 2. Pattern "par ARTISTE (style)" - avec style optionnel
    # Ex: "par GREGORY QUESTEL et DAVID MORA", "par YOLAINE (contes)"
    # Ex: "par O. Py" (initiales avec point)
    # Supporte: majuscules, noms propres, "et" entre artistes, initiales (O. Py)
    # IMPORTANT: Ne pas matcher "par la cie" ou "par la compagnie" (géré par par_cie_patterns)
    par_artiste_pattern = re.search(
        r'par\s+(?!la\s+(?:cie|compagnie)\b)([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ](?:\.\s*)?[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\&\'a-zàâäéèêëïîôùûüç\.]+?)(?:\s*\(([^)]+)\))?\s*(?:,|$)',
        remaining, re.IGNORECASE
    )
    if par_artiste_pattern:
        artiste_text = par_artiste_pattern.group(1).strip()
        style = par_artiste_pattern.group(2).strip() if par_artiste_pattern.group(2) else None
        # Gérer "et" entre artistes: "GREGORY QUESTEL et DAVID MORA"
        if artiste_text and len(artiste_text) > 2:
            if not any(a['nom'].lower() == artiste_text.lower() for a in result['artistes']):
                result['artistes'].append({'nom': artiste_text, 'style': style})
        # Retirer du remaining
        remaining = remaining[:par_artiste_pattern.start()] + remaining[par_artiste_pattern.end():]
        remaining = re.sub(r'\s+', ' ', remaining).strip()

    # 2b. Pattern "par la Cie XXX" ou "par la compagnie XXX"
    par_cie_patterns = [
        (r'par\s+la\s+[Cc]ie\s+"?([^",\(\)]+)"?', 'Cie '),
        (r'par\s+la\s+[Cc]ompagnie\s+([^,\(\)]+)', 'Cie '),
        (r'par\s+le\s+chœur\s+([^,\(\)]+)', 'Chœur '),
        (r'par\s+le\s+collectif\s+([^,\(\)]+)', 'Collectif '),
    ]

    for pattern, prefix in par_cie_patterns:
        match = re.search(pattern, remaining, re.IGNORECASE)
        if match:
            nom = match.group(1).strip().rstrip(',')
            if nom and len(nom) >= 2:  # Allow short names like "XY"
                full_nom = f"{prefix}{nom}"
                if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                    result['artistes'].append({'nom': full_nom, 'style': None})
            # Retirer du remaining
            remaining = remaining[:match.start()] + remaining[match.end():]
            remaining = re.sub(r'\s+', ' ', remaining).strip()

    # 3. Pattern "avec la Cie "XXX"" ou "avec la Cie XXX" ou "avec XXX"
    # D'abord essayer le pattern avec guillemets ASCII (plus spécifique)
    avec_cie_quoted = re.search(
        r'avec\s+la\s+[Cc]ie\s+"([^"]+)"',
        remaining, re.IGNORECASE
    )
    if avec_cie_quoted:
        nom = avec_cie_quoted.group(1).strip()
        if nom and len(nom) > 2:
            full_nom = f"Cie {nom}"
            if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                result['artistes'].append({'nom': full_nom, 'style': None})

    # Essayer aussi les guillemets typographiques
    if not avec_cie_quoted:
        avec_cie_quoted2 = re.search(
            r'avec\s+la\s+[Cc]ie\s+[«„]([^»"]+)[»"]',
            remaining, re.IGNORECASE
        )
        if avec_cie_quoted2:
            nom = avec_cie_quoted2.group(1).strip()
            if nom and len(nom) > 2:
                full_nom = f"Cie {nom}"
                if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                    result['artistes'].append({'nom': full_nom, 'style': None})

    # Autres patterns "avec" si pas déjà trouvé
    # Pattern "avec ARTISTE (style)" - avec extraction du style
    # Ex: "avec CEDRIC THIMON (impro)", "avec ALAIN WEBER (spect.sonore/visuel)"
    avec_artiste_style = re.search(
        r'avec\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\'\&]+?)\s*\(([^)]+)\)',
        remaining
    )
    if avec_artiste_style:
        nom = avec_artiste_style.group(1).strip()
        style = avec_artiste_style.group(2).strip()
        if nom and len(nom) > 2 and nom.lower() not in ('la cie',):
            if not any(a['nom'].lower() == nom.lower() for a in result['artistes']):
                result['artistes'].append({'nom': nom, 'style': style})
        # Retirer du remaining
        remaining = remaining[:avec_artiste_style.start()] + remaining[avec_artiste_style.end():]
        remaining = re.sub(r'\s+', ' ', remaining).strip()

    if not result['artistes'] or not any('Cie' in a.get('nom', '') for a in result['artistes']):
        avec_patterns = [
            # "avec la Cie Théâtre d'Air" - sans guillemets (ne doit pas matcher s'il y a des guillemets)
            (r'avec\s+la\s+[Cc]ie\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-]+?)(?:\s*,|\s*\(|$)', 'Cie '),
            # "avec la compagnie XXX"
            (r'avec\s+la\s+[Cc]ompagnie\s+([^,\(\)]+?)(?:\s*,|\s*\(|$)', 'Cie '),
            # "avec ARTISTE" (majuscules) - sans style (fallback si pas de parenthèses)
            (r'avec\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\'\&]+?)(?:\s*et\s|\s*,|$)', ''),
        ]

        for pattern, prefix in avec_patterns:
            matches = re.findall(pattern, remaining, re.IGNORECASE)
            for nom in matches:
                nom = nom.strip().rstrip(',')
                if nom and len(nom) > 2 and nom.lower() not in ('la cie',):
                    full_nom = f"{prefix}{nom}" if prefix else nom
                    if not any(a['nom'].lower() == full_nom.lower() for a in result['artistes']):
                        result['artistes'].append({'nom': full_nom, 'style': None})

    # 4. Pattern DJ: "XXX as Dj" ou "Dj XXX"
    dj_patterns = [
        r'(\w+)\s+as\s+Dj',  # "Mister Eleganz as Dj"
        r'Dj\s+(\w[\w\s]*?\w)(?:\s*,|\s*\(|$)',  # "Dj Vindu"
    ]

    for pattern in dj_patterns:
        matches = re.findall(pattern, remaining, re.IGNORECASE)
        for nom in matches:
            dj_name = f"DJ {nom.strip().upper()}"
            if not any(a['nom'].upper() == dj_name for a in result['artistes']):
                result['artistes'].append({'nom': dj_name, 'style': None})

    # 4b. Pattern Title Case artiste avec style en parenthèses
    # Ex: "Trio Pablo Musik (musique baroque)", "Quatuor Debussy (classique)"
    # Typique pour les ensembles de musique classique/baroque
    # Le nom doit être suivi directement du style entre parenthèses
    if not result['artistes']:
        title_case_match = re.match(
            r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç]+(?:\s+[A-Za-zÀ-ÿ][a-zàâäéèêëïîôùûüç]*)+)\s*\(([^)]+)\)',
            remaining
        )
        if title_case_match:
            nom = title_case_match.group(1).strip()
            style = title_case_match.group(2).strip()
            if nom and len(nom) > 2:
                result['artistes'].append({'nom': nom, 'style': style})
                # Retirer du remaining
                remaining = remaining[title_case_match.end():].strip()

    # 4c. Pattern MAJUSCULES artiste avec style (direct, sans avec/par)
    # Ex: "ACNE (chanson rock)", "BLUES BROTHERS (blues)"
    # Parse aussi les artistes séparés par virgule
    # IMPORTANT: Ne matcher que si le nom est entièrement en MAJUSCULES
    # ET que le match commence au début ou après une virgule (pour éviter de matcher partiellement)
    uppercase_artiste_matches = re.finditer(
        r'(?:^|,\s*)([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\'\&]+?)\s*\(([^)]+)\)',
        remaining
    )
    for match in uppercase_artiste_matches:
        nom = match.group(1).strip()
        style = match.group(2).strip()
        # Vérifier que le nom est bien tout en MAJUSCULES (pas de minuscules)
        if nom and len(nom) > 1 and nom == nom.upper() and nom.upper() not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET'):
            if not any(a['nom'].lower() == nom.lower() for a in result['artistes']):
                result['artistes'].append({'nom': nom, 'style': style})

    # 5. Pattern artistes séparés par "+" (avant guests pour les gérer ensemble)
    # Ex: "BUTE (crust) + guests!!"
    # Ex: "GERMAINE (ch.) 16h + LOLA BAï (ch.) 17h" (avec heures intercalées)
    # Ex: "✪ ORMUZ + OKDAK" (avec symboles décoratifs)
    if '+' in remaining:
        parts = remaining.split('+')
        for part in parts:
            part = part.strip()

            # Ignorer si c'est "guests" - sera géré après
            if re.match(r'^guests?!*$', part, re.IGNORECASE):
                continue

            # Ignorer si la partie contient "avec" - c'est un nom d'événement, pas un artiste
            # Ex: "Festival Soirs au Village avec MANU DIBANGO" - on veut seulement MANU DIBANGO
            if ' avec ' in part.lower():
                # Extraire la partie après "avec" si elle existe
                avec_idx = part.lower().find(' avec ')
                part = part[avec_idx + 6:].strip()  # Skip " avec "
                if not part:
                    continue

            # Nettoyer les symboles décoratifs au début (✪, •, ★, →, etc.)
            part = re.sub(r'^[✪★☆●○◆◇■□▲△▼▽♦♠♣♥•·→➔➜➤\-–—\s]+', '', part).strip()
            if not part:
                continue

            # Pattern: NOM (style) [heure optionnelle] ou NOM
            # Le pattern doit capturer le nom ENTIER jusqu'à l'espace avant (
            # Note: \u2019 est l'apostrophe typographique courante dans les PDFs
            # Supporte aussi les heures après le style: "GERMAINE (ch.) 16h" ou "SEREIN (jazz) à 15h30"
            # Supporte aussi les fins en "..." ou "etc..." : "FUMUJ...Saint Calais" -> "FUMUJ"
            # Supporte les noms commençant par un chiffre: "0' BROTHERS", "2 Many DJs"
            # Supporte les initiales avec point: "L. MARTEAU", "O. BACOU"
            artist_match = re.match(
                r"^((?:\d+'?\s*)?(?:[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]\.\s*)?[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇa-zàâäéèêëïîôùûüç\s'\u2019\-&\.]+?(?:['\u2019]s)?)\s*(?:\(([^)]+)\))?\s*(?:(?:etc)?\.{2,}|(?:à\s*)?\d{1,2}h\d{0,2}|,|$)",
                part.strip()
            )
            if artist_match:
                nom = artist_match.group(1).strip()
                style = artist_match.group(2).strip() if artist_match.group(2) else None
                # Ignorer les faux positifs
                if nom.upper() not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET'):
                    if not any(a['nom'].lower() == nom.lower() for a in result['artistes']):
                        result['artistes'].append({'nom': nom, 'style': style})

    # 6. Pattern "guests" ou "guests!!" (après le split par +)
    if re.search(r'\bguests?!*\b', remaining, re.IGNORECASE):
        if not any(a['nom'].lower() == 'guests' for a in result['artistes']):
            result['artistes'].append({'nom': 'Guests', 'style': None})

    # 7. Pattern artiste simple en MAJUSCULES avec style
    if not result['artistes'] and not result['spectacles']:
        # Ex: "MENDELSON (poème rock)" ou "ZAZ (chanson française)"
        artist_match = re.match(r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][^\(\)]{1,40}?)\s*(?:\(([^)]+)\))?\s*$', remaining)
        if artist_match:
            nom = artist_match.group(1).strip()
            style = artist_match.group(2).strip() if artist_match.group(2) else None
            # Vérifier que ce n'est pas un nom d'événement
            if nom.upper() not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET') and not is_named_event(nom):
                result['artistes'].append({'nom': nom, 'style': style})

    # 8. Pattern mixed case: "Les Echappées du Bocal (cabaret d'improvisation)"
    # ou "Jean-Claude CARRIÈRE (lecture)" ou "Dr Bones & the Blue Roots (blues-rock)"
    if not result['artistes'] and not result['spectacles']:
        # Pattern général mixed case avec style optionnel
        mixed_match = re.match(
            r'^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\'\-\s&]+(?:\s+[A-Za-zÀ-ÿ\'\-\s&]+)*)\s*(?:\(([^)]+)\))?\s*$',
            remaining.strip()
        )
        if mixed_match:
            nom = mixed_match.group(1).strip()
            style = mixed_match.group(2).strip() if mixed_match.group(2) else None
            # Valider que c'est bien un artiste (au moins 3 caractères, pas un mot simple)
            # et que ce n'est pas un nom d'événement
            if len(nom) > 3 and nom.upper() not in ('LE', 'LA', 'LES', 'DE', 'DU', 'DES', 'ET', 'BAR', 'LIEU') and not is_named_event(nom):
                result['artistes'].append({'nom': nom, 'style': style})

    # 9. Détecter nom d'événement (Soirée XXX, etc.) - déjà fait en étape 0
    # (garde pour backward compatibility si extract_event_name est appelé sur texte original)
    if not result['nom_evenement']:
        event_name = extract_event_name(text[:lieu_start])
        if event_name:
            result['nom_evenement'] = event_name

    return result


def extract_after_lieu(text: str, lieu_end: int) -> dict:
    """
    Extrait et parse ce qui est APRÈS le lieu.
    C'est généralement: ville, heure, prix

    Returns:
        dict avec 'heure', 'tarif_raw', 'prix_min', 'prix_max', 'gratuit'
    """
    after = text[lieu_end:].strip().lstrip(',').strip()

    result = {
        'heure': None,
        'tarif_raw': None,
        'prix_min': None,
        'prix_max': None,
        'gratuit': False
    }

    # Extraire l'heure
    hour_patterns = [
        r'(\d{1,2}h\d{0,2})\s*(?:à|&|-)\s*(\d{1,2}h?\d{0,2})',  # 23h-4h, 16h à 18h
        r'(\d{1,2}h\d{0,2})',  # 20h30, 21h
    ]

    for pattern in hour_patterns:
        match = re.search(pattern, after)
        if match:
            result['heure'] = match.group(0)
            break

    # Extraire le tarif avec la fonction existante
    tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved(after)
    result['tarif_raw'] = tarif_raw
    result['prix_min'] = prix_min
    result['prix_max'] = prix_max
    result['gratuit'] = gratuit

    return result


def find_lieu_position_heuristic(text: str) -> Optional[int]:
    """
    Trouve la position de début du lieu dans le texte de manière heuristique.

    Utilisé quand le lieu n'est pas dans le référentiel pour segmenter
    correctement le texte entre artistes et lieu.

    Stratégie:
    1. Chercher des patterns de lieu explicites (L'xxx, Le xxx, La xxx après virgule)
    2. Chercher la première virgule qui n'est pas dans un contexte d'artiste/style

    Ex: "✪ SOUFFLE COURT (rock), L'Epicerie sur le Zinc, 21h"
        -> position de "L'Epicerie" (après la virgule post-style)

    Returns:
        Position de début du lieu ou None si non trouvé
    """
    # Retirer les balises HTML pour l'analyse
    text_clean = strip_formatting_tags(text)

    # Pattern pour identifier un lieu typique en début de segment
    # après une virgule : L'xxx, Le xxx, La xxx, Espace xxx, Salle xxx, etc.
    lieu_start_patterns = [
        r",\s*(L'[A-ZÀ-Ÿ][a-zà-ÿ]+)",  # L'Epicerie, L'Oasis
        r",\s*(Le\s+[A-ZÀ-Ÿ][a-zà-ÿA-ZÀ-Ÿ\s\-]+)",  # Le Circuit, Le Mans
        r",\s*(La\s+[A-ZÀ-Ÿ][a-zà-ÿA-ZÀ-Ÿ\s\-]+)",  # La Fonderie
        r",\s*((?:Espace|Salle|Centre|Théâtre|Médiathèque|Bar|Café|Pub)\s+[A-Za-zÀ-ÿ\s\-\']+)",
        # Pattern générique mais exclut "Cie" (compagnie de théâtre)
        r",\s*(?!Cie\s)([A-ZÀ-Ÿ][a-zà-ÿ]+(?:\s+[A-ZÀ-Ÿ][a-zà-ÿ]+)*)",  # Jean Carmet, Epicerie
    ]

    # Patterns qui indiquent qu'on est encore dans la section artiste/style
    # et qu'il ne faut pas couper ici
    artiste_context_patterns = [
        r'\([^)]*$',  # Parenthèse ouverte non fermée (style en cours)
        r'^\s*\+',  # Suivi d'un + (autre artiste)
    ]

    # Chercher la position après le premier "(style)" complet
    # Pattern: texte (style), -> position après la virgule
    style_then_comma = re.search(r'\([^)]+\)\s*,\s*', text_clean)
    if style_then_comma:
        # Vérifier que ce qui suit ressemble à un lieu
        after_comma = text_clean[style_then_comma.end():]
        # Vérifier que ce n'est pas un autre artiste:
        # - pas en MAJUSCULES avec style
        # - pas "par ARTISTE" ou "de ARTISTE"
        # - pas "Cie XXX" ou "XXX Cie" (compagnie de théâtre)
        # Strip leading whitespace for matching
        after_comma_stripped = after_comma.strip()
        is_artiste_context = (
            re.match(r'^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\&\']+\s*\(', after_comma_stripped) or
            re.match(r'^(?:par|de)\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]', after_comma_stripped, re.IGNORECASE) or
            re.match(r'^[Cc]ie\s+', after_comma_stripped) or  # "Cie XXX"
            re.match(r'^[A-Za-zÀ-ÿ°][A-Za-zÀ-ÿ°\s\'\-]*\s+[Cc]ie\b', after_comma_stripped)  # "XXX Cie"
        )
        if not is_artiste_context:
            # Trouver la position correspondante dans le texte original
            # en cherchant le texte qui suit la virgule
            original_match = re.search(re.escape(after_comma_stripped[:15]), text)
            if original_match:
                return original_match.start()
            # Fallback: retourner la position dans le texte nettoyé
            return style_then_comma.end()

    # Chercher les patterns de lieu explicites
    for pattern in lieu_start_patterns:
        match = re.search(pattern, text_clean)
        if match:
            # Retourner la position du début du lieu (après la virgule et espaces)
            # On cherche la position dans le texte original (avec balises potentielles)
            lieu_text = match.group(1)
            original_match = re.search(re.escape(lieu_text[:10]), text)
            if original_match:
                return original_match.start()
            # Fallback: retourner la position dans le texte nettoyé
            return match.start(1)

    # Si rien trouvé, chercher la première virgule qui n'est pas dans un contexte artiste
    parts = text_clean.split(',')
    pos = 0
    for i, part in enumerate(parts[:-1]):  # Ignorer le dernier segment
        pos += len(part)
        # Vérifier si la partie courante se termine par un style (xxx)
        # et que la partie suivante ne ressemble pas à un artiste
        if i > 0 or re.search(r'\([^)]+\)\s*$', part):
            next_part = parts[i + 1].strip() if i + 1 < len(parts) else ""
            # Si la partie suivante ne commence pas par:
            # - MAJUSCULES avec style
            # - "par ARTISTE" ou "de ARTISTE"
            # - "Cie XXX" ou "XXX Cie" (compagnie de théâtre)
            is_next_artiste = (
                re.match(r'^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\&\']+\s*\(', next_part) or
                re.match(r'^(?:par|de)\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]', next_part, re.IGNORECASE) or
                re.match(r'^[Cc]ie\s+', next_part) or
                re.match(r'^[A-Za-zÀ-ÿ°][A-Za-zÀ-ÿ°\s\'\-]*\s+[Cc]ie\b', next_part)
            )
            if not is_next_artiste:
                # Trouver la position de la virgule dans le texte original
                comma_pos = len(','.join(parts[:i+1]))
                return comma_pos + 1  # Position après la virgule
        pos += 1  # Pour la virgule

    return None


def extract_lieu_fallback(text: str, ville_ref_list: list) -> tuple[Optional[str], Optional[str]]:
    """
    Extrait le lieu et la ville du texte quand le lieu n'est pas dans le référentiel.

    Utilise une approche heuristique:
    - Split par virgule
    - Ignore les spectacles, artistes, genres, heures, prix
    - Premier candidat valide (ressemble à un lieu) = lieu
    - Villes identifiées par le référentiel ville_ref

    Args:
        text: Texte à analyser
        ville_ref_list: Liste de tuples (id, nom) pour les villes

    Returns:
        (lieu_raw, ville_raw)
    """
    from core.normalizer import normalize_ville

    # Retirer les balises de formatage
    text_clean = strip_formatting_tags(text)

    # Split par virgule en préservant les guillemets
    # Ex: '"Stimulant, amer" (th), Lieu' -> ['"Stimulant, amer" (th)', 'Lieu']
    def smart_split(text: str) -> list:
        """Split par virgule en préservant les contenus entre guillemets."""
        parts = []
        current = ""
        in_quotes = False
        quote_char = None
        # Paires de guillemets: (ouverture, fermeture)
        # Note: apostrophe ' exclue car trop courante dans les noms (Val'Rhonne, L'Oasis)
        quote_pairs = {
            '«': '»',    # guillemets français
            '"': '"',    # guillemets anglais ouverture
            '"': '"',    # guillemets anglais fermeture (auto-fermant)
            '„': '"',    # guillemets allemands bas
            '"': '"',    # guillemets droits ASCII
        }

        for i, char in enumerate(text):
            if char in quote_pairs and not in_quotes:
                # Vérifier si c'est vraiment un guillemet ouvrant
                # Un guillemet après une lettre/chiffre est probablement fermant, pas ouvrant
                # Ex: 'AMOUR"' -> le " est fermant (ignore OCR avec << au lieu de «)
                prev_char = text[i - 1] if i > 0 else ''
                if prev_char.isalnum():
                    # C'est un guillemet fermant orphelin, ignorer
                    current += char
                else:
                    in_quotes = True
                    quote_char = quote_pairs[char]
                    current += char
            elif in_quotes and char == quote_char:
                in_quotes = False
                quote_char = None
                current += char
            elif char == ',' and not in_quotes:
                parts.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            parts.append(current.strip())

        return parts

    parts = smart_split(text_clean)

    # Patterns à ignorer
    heure_pattern = re.compile(r'\d{1,2}h\d{0,2}')
    prix_pattern = re.compile(r'\d+[.,]?\d*\s*€|gratuit|libre|prix libre|participation libre', re.IGNORECASE)
    genre_pattern = re.compile(r'^\([^)]+\)$')
    # Spectacles entre guillemets (avec ou sans genre)
    spectacle_pattern = re.compile(r'^[«""„\"].*[»""\"]')
    # Artistes en MAJUSCULES (avec ou sans genre entre parenthèses)
    # Inclut les artistes séparés par + (ARTISTE1 + ARTISTE2)
    artiste_pattern = re.compile(r'^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-\&\.0-9]+(?:\s*\([^)]+\))?(?:\s*\+\s*[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-\&\.0-9]+(?:\s*\([^)]+\))?)*$')
    # Acronymes de lieux connus (ne doivent pas être filtrés comme artistes)
    # ITEMM = Institut Technologique Européen des Métiers de la Musique
    # MJC = Maison des Jeunes et de la Culture
    lieux_acronymes = {'ITEMM', 'MJC', 'FNAC', 'CSC', 'MPT', 'CAC', 'EMM'}
    # Compagnies de théâtre: "Cie XXX", "Compagnie XXX", "Cie XXX/YYY"
    cie_pattern = re.compile(r'^[Cc](?:ie|ompagnie)\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-/&]+$')
    # Texte avec genre entre parenthèses (probablement artiste ou spectacle)
    # Exclut les indications de lieu comme "(extérieur)", "(intérieur)", "(jardin)", "(terrasse)"
    with_genre_pattern = re.compile(r'.+\s*\([^)]+\)\s*$')
    # Exceptions au with_genre_pattern : ce ne sont pas des genres mais des infos lieu ou codes département
    lieu_info_pattern = re.compile(r'\((?:ext[ée]rieur|int[ée]rieur|jardin|terrasse|parking|parvis|cour|dehors|plein air|\d{2,3})\)$', re.IGNORECASE)
    # Texte contenant "+" suivi de texte (probablement artistes/guests)
    multi_artiste_pattern = re.compile(r'\+\s*(?:[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]|guests)', re.IGNORECASE)
    # Noms d'événements: contient "avec", "invite", ":", "soirée", "concert", "scène ouverte", etc.
    event_name_pattern = re.compile(r'\b(?:avec|featuring|feat\.?|invite)\b|^(?:soirée|concert|carte blanche|sc[èe]ne ouverte)', re.IGNORECASE)
    # Pattern pour extraire un lieu bar/espace/salle/centre/théâtre en fin de chaîne ou avant "de Xh"
    lieu_in_text_pattern = re.compile(r'\b((?:bar|espace|salle|centre|théâtre|pub|médiathèque|péniche|café)\s+(?:le\s+|la\s+|l\'|du\s+|de\s+la\s+|des\s+)?[A-Za-zÀ-ÿ\s\-\']+?)(?:\s+de\s+\d{1,2}h|$)', re.IGNORECASE)
    # Fragments de parenthèses (genre coupé) - inclut les artistes avec parenthèse non fermée
    fragment_pattern = re.compile(r'^[^(]*\)|\([^)]*$|^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-\&\.0-9]+\s*\([^)]*$')

    # Pattern pour identifier un lieu explicite (commence par Salle, Bar, Espace, etc.)
    # Prioritaire sur les candidats génériques
    explicit_lieu_pattern = re.compile(
        r'^(?:salle|bar|espace|centre|théâtre|theater|pub|médiathèque|mediatheque|'
        r'péniche|peniche|café|cafe|'
        r'le\s+(?:bar|café|cafe|théâtre|theater|centre)|'
        r'la\s+(?:salle|médiathèque|mediatheque|péniche|peniche)|'
        r'l\'(?:espace|espal))\b',
        re.IGNORECASE
    )

    lieu = None
    lieu_candidats_generiques = []  # Candidats non-explicites
    villes_trouvees = []

    for part in parts:
        if not part:
            continue

        # Ignorer les heures et prix, mais d'abord essayer d'extraire un lieu embarqué
        # Ex: "Bar Le Palais de 19h à 21h" -> extraire "Bar Le Palais"
        if heure_pattern.search(part) or prix_pattern.search(part):
            lieu_match = lieu_in_text_pattern.search(part)
            if lieu_match and lieu is None:
                lieu = lieu_match.group(1).strip()
            continue

        # Ignorer les genres seuls entre parenthèses
        if genre_pattern.match(part):
            continue

        # Ignorer "par Cie X"
        if part.lower().startswith('par '):
            continue

        # Ignorer les spectacles entre guillemets
        if spectacle_pattern.match(part):
            continue

        # Ignorer les artistes en MAJUSCULES (sauf acronymes de lieux connus)
        if artiste_pattern.match(part) and part.upper() not in lieux_acronymes:
            continue

        # Ignorer les compagnies de théâtre (Cie XXX)
        if cie_pattern.match(part):
            continue

        # Ignorer les segments contenant "+" suivi d'artistes (multi-artistes)
        # Mais d'abord, essayer d'extraire un lieu embarqué (ex: "ARTISTE + guests!! Bar le Lézard")
        if multi_artiste_pattern.search(part):
            lieu_match = lieu_in_text_pattern.search(part)
            if lieu_match and lieu is None:
                lieu = lieu_match.group(1).strip()
            continue

        # Ignorer les segments avec genre entre parenthèses (probablement artiste/spectacle)
        # SAUF si c'est une indication de lieu (extérieur, jardin, etc.)
        if with_genre_pattern.match(part) and not lieu_info_pattern.search(part):
            continue

        # Ignorer les noms d'événements (contient "avec", "soirée", "concert", etc.)
        # Mais d'abord, essayer d'extraire un lieu embarqué (ex: "soirée X avec Y, Bar le Z")
        if event_name_pattern.search(part):
            lieu_match = lieu_in_text_pattern.search(part)
            if lieu_match and lieu is None:
                lieu = lieu_match.group(1).strip()
            continue

        # Ignorer les fragments de parenthèses (genre coupé comme "dès 6 ans)")
        if fragment_pattern.match(part):
            continue

        # Ignorer les segments trop longs
        if len(part) > 50:
            continue

        # Ignorer les segments trop courts (moins de 3 caractères)
        if len(part) < 3:
            continue

        # Vérifier si c'est une ville connue (priorité)
        # Note: normalize_ville retourne toujours un ID (Le Mans par défaut),
        # donc on compare le nom normalisé retourné avec le candidat pour
        # déterminer si c'est vraiment une ville reconnue.
        from core.normalizer import normalize_for_matching
        # Retirer le code département éventuel: "Fresnay-sur-Sarthe (72)" -> "Fresnay-sur-Sarthe"
        part_for_ville = lieu_info_pattern.sub('', part).strip()
        ville_id, ville_norm = normalize_ville(part_for_ville)
        # Normaliser les deux pour comparaison (tirets, accents, casse)
        part_normalized = normalize_for_matching(part_for_ville)
        ville_normalized = normalize_for_matching(ville_norm)

        # C'est une ville si le nom retourné correspond au candidat
        # (pas juste "Le Mans" par défaut pour n'importe quel texte)
        if ville_norm.lower() != 'le mans' or part_normalized == ville_normalized:
            villes_trouvees.append({
                'nom': ville_norm,
                'is_lemans': ville_norm.lower() == 'le mans'
            })
            continue

        # Candidat valide pour un lieu
        # Priorité aux lieux explicites (Salle X, Bar le Y, etc.)
        if explicit_lieu_pattern.match(part):
            # Lieu explicite trouvé - remplace tout candidat générique
            if lieu is None or not explicit_lieu_pattern.match(lieu):
                lieu = part
        elif lieu is None:
            # Candidat générique - stocker mais peut être remplacé par un lieu explicite
            lieu_candidats_generiques.append(part)

    # Si pas de lieu explicite trouvé, utiliser le premier candidat générique
    if lieu is None and lieu_candidats_generiques:
        lieu = lieu_candidats_generiques[0]

    # Heuristique pour villes inconnues:
    # Si on a un lieu mais pas de ville, chercher un segment qui ressemble à une ville
    # Pattern: mot(s) en Title Case, pas trop long, généralement après le lieu
    if lieu and not villes_trouvees:
        # Pattern pour noms de villes: commence par majuscule, peut avoir "sur", "en", "lès", etc.
        ville_heuristic_pattern = re.compile(
            r'^[A-ZÀ-Ÿ][a-zà-ÿ]+(?:[\s\-](?:sur|en|lès|les|le|la|du|de|l\')?[\s\-]?[A-ZÀ-Ÿa-zà-ÿ]+)*$'
        )
        # Chercher dans les candidats génériques (après le lieu)
        lieu_found = False
        for candidat in lieu_candidats_generiques:
            if candidat == lieu:
                lieu_found = True
                continue
            if lieu_found and ville_heuristic_pattern.match(candidat):
                # Vérifier que ce n'est pas un mot générique de lieu
                if candidat.lower() not in ['foyer', 'rural', 'salle', 'centre', 'espace', 'mairie']:
                    villes_trouvees.append({'nom': candidat, 'is_lemans': False})
                    break

    # Sélectionner la ville
    ville = None
    if villes_trouvees:
        non_lemans = [v for v in villes_trouvees if not v['is_lemans']]
        if non_lemans:
            ville = non_lemans[0]['nom']
        else:
            ville = villes_trouvees[0]['nom']

    return lieu, ville


def extract_ville_from_text_v2(text: str, ville_ref_list: list) -> tuple[Optional[int], str]:
    """
    Extrait la ville du texte complet.
    Priorise les villes explicites (non Le Mans) si présentes.

    Args:
        text: Texte à analyser
        ville_ref_list: Liste de tuples (id, nom)

    Returns:
        (ville_id, ville_nom)
    """
    # Normaliser les variantes de villes
    normalizations = [
        (r'Sablé\s*s/?Sarthe', 'Sablé-sur-Sarthe'),
        (r'La\s+Ferté\s*Bernard', 'La Ferté-Bernard'),
        (r'Sargé-lès-Le\s*Mans', 'Sargé-lès-Le Mans'),
        (r'Yvré\s*l.Évêque', "Yvré-l'Évêque"),
        (r'Moncé-en-?\s*Belin', 'Moncé-en-Belin'),
        (r'St[\.\s]+Pavace', 'Saint-Pavace'),
        (r'St[\.\s]+Saturnin', 'Saint-Saturnin'),
        (r'Ste[\.\s]+Croix', 'Sainte-Croix'),
        # Nouvelles normalisations
        (r'Savign[ée](?:\s+l.?[EÉée]v[eê]que)?', "Savigné-l'Évêque"),
        (r'St[\.\s]+Mars\s*(?:la\s*)?Bri[èe]re', 'Saint-Mars-la-Brière'),
        (r'Noyen\s*s/?Sarthe', 'Noyen-sur-Sarthe'),
        (r'(?:St[\.\s]+|Saint\s+)Calais', 'Saint-Calais'),
        (r'Fill[ée]\s*s/?Sarthe', 'Fillé-sur-Sarthe'),
        (r'Ch[âa]teau\s+du\s+Loir', 'Château-du-Loir'),
    ]

    text_normalized = text
    for pattern, replacement in normalizations:
        text_normalized = re.sub(pattern, replacement, text_normalized, flags=re.IGNORECASE)

    text_lower = text_normalized.lower()
    # Normaliser tirets en espaces pour le matching (ex: "Brette Les Pins" == "Brette-les-Pins")
    text_lower_normalized = text_lower.replace('-', ' ')

    found = []
    for ville_tuple in ville_ref_list:
        ville_id = ville_tuple[0]
        ville_nom = ville_tuple[1]
        ville_lower = ville_nom.lower()
        # Normaliser aussi les tirets de la ville de référence
        ville_lower_normalized = ville_lower.replace('-', ' ')

        pattern = r'\b' + re.escape(ville_lower_normalized) + r'\b'
        if re.search(pattern, text_lower_normalized):
            found.append((ville_id, ville_nom))

    if not found:
        return None, "Le Mans"

    # Prioriser non-Le Mans
    non_lemans = [(vid, vnom) for vid, vnom in found if vnom.lower() != 'le mans']
    if non_lemans:
        # Prendre la plus longue (plus spécifique)
        return max(non_lemans, key=lambda x: len(x[1]))

    return found[0]


def parse_event_line_v2(
    raw_text: str,
    base_month: int,
    base_year: int,
    lieu_ref_list: list,
    ville_ref_list: list
) -> list[dict]:
    """
    Parse une ligne d'événement avec la stratégie "lieu d'abord".

    Flux:
    1. Détecter si c'est un festival multi-jours (splitting préalable)
    2. Nettoyer le texte
    3. Splitter sur les dates (lignes fusionnées)
    4. Pour chaque ligne:
       a. Parser le préfixe de date
       b. Trouver le lieu (référentiel)
       c. Parser avant le lieu (artistes, spectacles)
       d. Parser après le lieu (ville, heure, prix)

    Returns:
        Liste de dicts représentant les événements parsés
    """
    results = []

    # Vérifier si ce sont plusieurs événements/festivals concaténés
    # Ex: "Théâtre sauvage... Les festivals en juillet FESTI BOUAILLE... Festival Kikloche..."
    split_events = split_concatenated_festivals(raw_text)
    if len(split_events) > 1:
        # Traiter chaque événement séparément
        for split_text in split_events:
            sub_results = parse_event_line_v2(
                split_text,
                base_month,
                base_year,
                lieu_ref_list,
                ville_ref_list
            )
            results.extend(sub_results)
        return results

    # Vérifier si c'est un festival multi-jours
    # Ex: "Festival TERIAKI du 25 au 28 août 2011... Jeudi 25: •Event1 Vendredi 26: •Event2..."
    festival_events = split_festival_multi_day(raw_text, base_month, base_year)
    if festival_events:
        # Traiter chaque événement du festival séparément
        for fest_evt in festival_events:
            sub_results = parse_event_line_v2(
                fest_evt['text'],
                fest_evt['month'],
                fest_evt['year'],
                lieu_ref_list,
                ville_ref_list
            )
            # Ajouter la date du festival si pas déjà présente
            for sub_result in sub_results:
                if not sub_result.get('date_evenement'):
                    try:
                        from datetime import date
                        sub_result['date_evenement'] = date(
                            fest_evt['year'],
                            fest_evt['month'],
                            fest_evt['day_num']
                        )
                        sub_result['date_str'] = f"{fest_evt['day_name']} {fest_evt['day_num']}"
                    except ValueError:
                        pass
                results.append(sub_result)
        return results

    # Tronquer après le prix pour éviter le texte promotionnel
    raw_text = truncate_after_price(raw_text)

    # Nettoyer
    text = clean_pdf_text(raw_text)
    text = expand_abbreviations(text)

    # Format spécial: "NOM AVEC: - *SPECTACLE", (style), Cie ARTISTE - ..."
    # Ex: "Sa 01 LES RENDEZ-VOUS SPECTACLES DE Bouloire (72) AVEC: - *LE CLARINETTISTE", ..."
    # Ce format a le lieu APRÈS la liste des spectacles (ex: "Grange à André")
    avec_liste_match = re.match(
        r'^(?:([A-Za-z]{2})\s+(\d{1,2})\s+)?((?:LES\s+)?[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-Za-zÀ-ÿ\-\s]+?)(?:\s+DE\s+([A-Za-zÀ-ÿ\-]+))?\s*(?:\(\d+\))?\s*AVEC\s*:\s*(.+)',
        text, re.IGNORECASE | re.DOTALL
    )
    if avec_liste_match:
        liste_part = avec_liste_match.group(5)
        # Vérifier que la liste contient bien des spectacles avec tirets et guillemets OCR
        if re.search(r'-\s*(?:\*|<<)[^"]+"\s*,?\s*\([^)]+\)', liste_part):
            # Extraire la date si présente
            date_obj = None
            if avec_liste_match.group(1) and avec_liste_match.group(2):
                try:
                    from datetime import date as date_class
                    day_num = int(avec_liste_match.group(2))
                    date_obj = date_class(base_year, base_month, day_num)
                except ValueError:
                    pass

            event_name = avec_liste_match.group(3).strip()
            if avec_liste_match.group(4):
                event_name += f" DE {avec_liste_match.group(4).strip()}"

            # Parser les spectacles
            spectacles = []
            artistes = []
            spectacle_liste_pattern = re.compile(
                r'-\s*(?:\*|<<)([^"]+)"\s*,?\s*\(([^)]+)\)\s*,?\s*(?:Cie\s+)?([^-]+?)(?=\s*-\s*(?:\*|<<)|Grange|Salle|Centre|Espace|Théâtre|$)',
                re.IGNORECASE
            )
            for spec_match in spectacle_liste_pattern.finditer(liste_part):
                spec_nom = spec_match.group(1).strip()
                spec_style = spec_match.group(2).strip()
                artiste_nom = spec_match.group(3).strip().rstrip(',').strip()

                if spec_nom and len(spec_nom) > 1:
                    spectacles.append({'nom': spec_nom, 'style': spec_style})
                if artiste_nom and len(artiste_nom) > 1:
                    if not artiste_nom.lower().startswith('cie '):
                        artiste_nom = f"Cie {artiste_nom}"
                    artistes.append({'nom': artiste_nom, 'style': spec_style, 'spectacle': spec_nom})

            # Chercher le lieu dans la partie restante (après les spectacles)
            lieu_raw = None
            lieu_match_in_list = re.search(r'(Grange\s+[àa]\s+[A-Za-zÀ-ÿ\-]+|Salle\s+[A-Za-zÀ-ÿ\-\s]+|Centre\s+[A-Za-zÀ-ÿ\-\s]+)', liste_part, re.IGNORECASE)
            if lieu_match_in_list:
                lieu_raw = lieu_match_in_list.group(1).strip()

            # Extraire heure et tarif
            heure_match = re.search(r'(\d{1,2})h(\d{0,2})', liste_part)
            heure = f"{heure_match.group(1)}h{heure_match.group(2)}" if heure_match else None

            tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved(liste_part)

            result = {
                'raw_text': raw_text,
                'nom': event_name,
                'date_evenement': date_obj,
                'date_str': f"{avec_liste_match.group(1)} {avec_liste_match.group(2)}" if avec_liste_match.group(1) else None,
                'lieu_raw': lieu_raw,
                'ville_raw': avec_liste_match.group(4),  # Ville du nom (ex: Bouloire)
                'heure': heure,
                'tarif_raw': tarif_raw,
                'prix_min': prix_min,
                'prix_max': prix_max,
                'gratuit': gratuit,
                'spectacles': spectacles,
                'artistes': artistes
            }
            return [result]

    # Préparer les patterns de lieu
    lieu_patterns = load_lieu_patterns(lieu_ref_list)

    # Splitter sur les dates
    lines = split_on_dates_v2(text)

    for line in lines:
        # Parser le préfixe de date
        dates, event_text = parse_date_prefix_v2(line, base_month, base_year)

        if not dates:
            # Pas de date dans le préfixe
            dates = [None]

        # Trouver le lieu
        lieu_match = find_lieu_in_text_v2(event_text, lieu_patterns)

        # Vérifier si le lieu trouvé fait partie d'un nom d'événement
        # Ex: "Les Rdv Conservatoire" - "Conservatoire" ne doit pas être pris comme lieu
        if lieu_match:
            lieu_nom, lieu_id, lieu_start, lieu_end = lieu_match
            # Texte avant le lieu trouvé
            text_before_lieu = event_text[:lieu_start].strip()
            # Si le texte avant + lieu forme un pattern d'événement nommé, invalider le lieu
            text_including_lieu = event_text[:lieu_end].strip()
            if is_named_event(text_including_lieu) or is_named_event(text_before_lieu + " " + lieu_nom):
                # Le lieu fait partie du nom d'événement - chercher le vrai lieu plus loin
                # Chercher à partir de la position après le lieu actuel
                remaining = event_text[lieu_end:]
                next_lieu_match = find_lieu_in_text_v2(remaining, lieu_patterns)
                if next_lieu_match:
                    next_lieu_nom, next_lieu_id, next_start, next_end = next_lieu_match
                    # Ajuster les positions
                    lieu_match = (next_lieu_nom, next_lieu_id, lieu_end + next_start, lieu_end + next_end)
                else:
                    # Pas de lieu après - utiliser l'extraction heuristique
                    lieu_match = None

        # Vérifier si le lieu trouvé est en fait une ville (erreur du référentiel)
        # Exemple: "La Flèche" est dans lieu_ref mais c'est une ville
        if lieu_match:
            lieu_nom, lieu_id, lieu_start, lieu_end = lieu_match

            # Si le lieu trouvé correspond aussi à une ville, c'est probablement une erreur
            # du référentiel. Dans ce cas, on utilise l'extraction heuristique.
            # Note: normalize_ville retourne toujours un ID (Le Mans par défaut),
            # donc on compare le nom normalisé retourné avec le nom du lieu.
            from core.normalizer import normalize_ville, normalize_for_matching
            _, ville_nom_check = normalize_ville(lieu_nom)
            # Seul invalider si le nom retourné correspond vraiment au nom du lieu
            # (pas juste "Le Mans" par défaut)
            if normalize_for_matching(ville_nom_check) == normalize_for_matching(lieu_nom):
                # Le "lieu" est en fait une ville - invalider le match
                lieu_match = None

        if lieu_match:
            lieu_nom, lieu_id, lieu_start, lieu_end = lieu_match

            # Parser avant et après le lieu
            before_data = extract_before_lieu(event_text, lieu_start)
            after_data = extract_after_lieu(event_text, lieu_end)

            # Si pas d'heure trouvée après le lieu, chercher dans le texte complet
            # (cas des heures individuelles par artiste: "ARTISTE1 16h + ARTISTE2 17h, Lieu")
            if not after_data.get('heure'):
                all_hours = re.findall(r'(\d{1,2})h(\d{0,2})', event_text)
                if all_hours:
                    # Prendre l'heure la plus tôt
                    earliest = min(all_hours, key=lambda x: int(x[0]) * 60 + (int(x[1]) if x[1] else 0))
                    after_data['heure'] = f"{earliest[0]}h{earliest[1]}" if earliest[1] else f"{earliest[0]}h"

            # Extraire la ville du texte complet
            ville_id, ville_nom = extract_ville_from_text_v2(event_text, ville_ref_list)

        else:
            # Lieu non trouvé dans le référentiel - utiliser extraction heuristique
            lieu_id = None

            # Trouver la position du lieu heuristiquement pour segmenter correctement
            lieu_start_heuristic = find_lieu_position_heuristic(event_text)
            if lieu_start_heuristic is not None:
                # Parser avant la position heuristique du lieu
                before_data = extract_before_lieu(event_text, lieu_start_heuristic)
            else:
                # Fallback: utiliser le texte complet pour before
                before_data = extract_before_lieu(event_text, len(event_text))

            # Toujours extraire heure/tarif du texte complet quand lieu non trouvé
            # car la position heuristique n'est pas fiable pour segmenter
            after_data = {
                'heure': None,
                'tarif_raw': None,
                'prix_min': None,
                'prix_max': None,
                'gratuit': False
            }

            # Essayer d'extraire l'heure du texte complet (prendre la plus tôt)
            all_hours = re.findall(r'(\d{1,2})h(\d{0,2})', event_text)
            if all_hours:
                # Prendre l'heure la plus tôt
                earliest = min(all_hours, key=lambda x: int(x[0]) * 60 + (int(x[1]) if x[1] else 0))
                after_data['heure'] = f"{earliest[0]}h{earliest[1]}" if earliest[1] else f"{earliest[0]}h"

            # Extraire tarif du texte complet
            tarif_raw, prix_min, prix_max, gratuit = extract_tarif_improved(event_text)
            after_data['tarif_raw'] = tarif_raw
            after_data['prix_min'] = prix_min
            after_data['prix_max'] = prix_max
            after_data['gratuit'] = gratuit

            # Utiliser l'extraction heuristique pour lieu ET ville
            lieu_nom, ville_from_fallback = extract_lieu_fallback(event_text, ville_ref_list)

            # Utiliser la ville du fallback si trouvée, sinon extract_ville_from_text_v2
            if ville_from_fallback:
                # Normaliser la ville pour avoir l'ID (si dans référentiel)
                from core.normalizer import normalize_ville
                ville_id, ville_norm = normalize_ville(ville_from_fallback)
                # Si normalize_ville retourne "Le Mans" mais ce n'était pas la ville trouvée,
                # garder la ville originale (non normalisée) pour ville_raw
                if ville_norm.lower() == 'le mans' and ville_from_fallback.lower() != 'le mans':
                    ville_nom = ville_from_fallback  # Garder la ville originale
                    ville_id = None  # Pas d'ID référentiel
                else:
                    ville_nom = ville_norm
            else:
                ville_id, ville_nom = extract_ville_from_text_v2(event_text, ville_ref_list)

        # Créer un événement par date
        for event_date in dates:
            # Construire date_str
            date_str = None
            if event_date:
                jours = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di']
                date_str = f"{jours[event_date.weekday()]} {event_date.day}"

            event = {
                # Utiliser event_text (sans préfixe de date) pour raw_text
                'raw_text': event_text.strip(),
                'nom': before_data.get('nom_evenement'),
                'style': before_data.get('style_evenement'),
                'genre_evenement': before_data.get('genre_evenement'),
                'date_str': date_str,
                'date_evenement': event_date,
                'heure': after_data.get('heure'),
                'lieu_raw': lieu_nom,
                'lieu_ref_id': lieu_id,
                'ville_raw': ville_nom,
                'ville_ref_id': ville_id,
                'tarif_raw': after_data.get('tarif_raw'),
                'prix_min': after_data.get('prix_min'),
                'prix_max': after_data.get('prix_max'),
                'gratuit': after_data.get('gratuit', False),
                'spectacles': before_data.get('spectacles', []),
                'artistes': before_data.get('artistes', []),
            }

            results.append(event)

    return results


# =============================================================================
# FIN STRATÉGIE "LIEU D'ABORD"
# =============================================================================


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

    # Spectacles (noms entre guillemets avec style optionnel)
    # Format: [{'nom': 'spectacle', 'style': 'théâtre'}, ...]
    spectacles: list = field(default_factory=list)

    # Genres (texte entre parenthèses) - conservé pour compatibilité
    genres_raw: list[str] = field(default_factory=list)

    # Prix
    tarif_raw: Optional[str] = None
    prix_min: Optional[float] = None
    prix_max: Optional[float] = None
    gratuit: bool = False

    # Type déduit
    type_evenement: Optional[str] = None

    # Genre de l'événement (jazz, rock, théâtre, etc.)
    genre_evenement: Optional[str] = None

    # Qualité
    confidence: float = 0.5

    # Événement hors département (régional)
    is_regional: bool = False

    def is_valid(self) -> bool:
        """
        Vérifie si l'événement est valide (contenu minimal requis).

        Un événement exploitable dans un agenda doit avoir:
        - Une date ET un lieu, OU
        - Une date ET un contenu (artiste/spectacle/nom), OU
        - Un lieu ET un contenu

        Les événements avec seulement artiste+heure+prix (sans date ni lieu)
        ne sont pas exploitables car on ne sait pas où ni quand ils ont lieu.

        Exemples rejetés:
        - "MAGMA 20h30" (artiste + heure, mais pas de date ni lieu)
        - "(réservations au 06 10 53 38 40)" (texte non structuré)
        """
        has_date = self.date_evenement is not None or self.date_str is not None
        has_content = bool(self.artistes) or bool(self.spectacles) or bool(self.nom)
        has_lieu = self.lieu_raw is not None

        # Un événement doit avoir au moins 2 des 3 critères pour être exploitable
        criteria_count = sum([has_date, has_content, has_lieu])
        if criteria_count < 2:
            return False

        # Rejeter les événements qui ne sont que du texte entre parenthèses
        # Ex: "(réservations au 06 10 53 38 40)"
        if self.raw_text.strip().startswith('(') and self.raw_text.strip().endswith(')'):
            if not has_content and not has_lieu:
                return False

        return True

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
    # Jours de la semaine: formes complètes, abréviations 3 lettres, abréviations 2 lettres
    # Complètes: Lundi, Mardi, Mercredi, Jeudi, Vendredi, Samedi, Dimanche
    # 3 lettres: Lun, Mar, Mer, Jeu, Ven, Sam, Dim
    # 2 lettres: Lu, Ma, Me, Je, Ve, Sa, Di
    JOURS = r"(?:[Ll]undi|[Mm]ardi|[Mm]ercredi|[Jj]eudi|[Vv]endredi|[Ss]amedi|[Dd]imanche|LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE|[Ll]un|[Mm]ar|[Mm]er|[Jj]eu|[Vv]en|[Ss]am|[Dd]im|LUN|MAR|MER|JEU|VEN|SAM|DIM|[Ll]u|[Mm]a|[Mm]e|[Jj]e|[Vv]e|[Ss]a|[Dd]i|LU|MA|ME|JE|VE|SA|DI)"
    MOIS = r"(?:[Jj]anvier|[Ff][ée]vrier|[Mm]ars|[Aa]vril|[Mm]ai|[Jj]uin|[Jj]uillet|[Aa]o[uû]t|[Ss]eptembre|[Oo]ctobre|[Nn]ovembre|[Dd][ée]cembre)"
    # Pattern pour dates simples: "Samedi 20", "Mardi 2", "Vendredi 1er", "Vendredi 9 juillet"
    DATE_SIMPLE_PATTERN = re.compile(rf"^({JOURS})\s+(\d{{1,2}})(?:ER|er|ème|eme)?(?:\s+{MOIS})?\s*:?\s*$", re.MULTILINE)
    # Pattern pour dates composées: "Samedi 2 & Dimanche 3", "Ve 10 & Sa 11", "Samedi 04 et Dimanche 05"
    DATE_COMPOSE_PATTERN = re.compile(rf"^({JOURS})\s+(\d{{1,2}})(?:ER|er|ème|eme)?\s*(?:[&,]|et)\s*({JOURS})\s+(\d{{1,2}})(?:ER|er|ème|eme)?\s*:?\s*$", re.MULTILINE | re.IGNORECASE)
    # Pattern pour plages: "Du 6 au 10 juin", "Du 26 juin au 1er juillet", "Du Mercredi 01 au Samedi 07"
    DATE_RANGE_PATTERN = re.compile(rf"^[Dd]u\s+(?:{JOURS}\s+)?(\d{{1,2}})(?:ER|er|ème|eme)?\s*(?:{MOIS})?\s*[aà]u?\s+(?:{JOURS}\s+)?(\d{{1,2}})(?:ER|er|ème|eme)?\s*(?:{MOIS})?\s*$", re.MULTILINE | re.IGNORECASE)
    # Pattern combiné pour matcher n'importe quel format de date (utilisé par _split_by_dates)
    # Supporte:
    # - Dates simples: "Jeudi 02", "Lundi 06", "Vendredi 9 juillet"
    # - Dates composées avec &, , ou et: "Samedi 04 et Dimanche 05", "Ve 10 & Sa 11"
    # - Plages numériques: "Du 6 au 10"
    # - Plages avec jours complets: "Du Mercredi 01 au Samedi 07", "Du Vendredi 03 au Dimanche 05"
    DATE_PATTERN = re.compile(
        rf"^(?:"
        rf"({JOURS})\s+(\d{{1,2}})(?:ER|er|ème|eme)?(?:\s+{MOIS})?(?:\s*(?:[&,]|et)\s*({JOURS})\s+(\d{{1,2}})(?:ER|er|ème|eme)?(?:\s+{MOIS})?)?"  # Simple ou composée (avec mois optionnel)
        rf"|[Dd]u\s+(?:{JOURS}\s+)?(\d{{1,2}})(?:ER|er|ème|eme)?\s*(?:{MOIS})?\s*[aà]u?\s+(?:{JOURS}\s+)?(\d{{1,2}})(?:ER|er|ème|eme)?\s*(?:{MOIS})?"  # Plage (avec ou sans jours complets)
        rf")\s*:?\s*$",
        re.MULTILINE | re.IGNORECASE
    )

    # Pattern pour les bullets (• ou caractères similaires)
    # Inclut: * (astérisque OCR), •●○◦▪▫■□►▸‣⁃ et variantes Unicode (❑❒◇◆★☆✦✧♦❖✳✴✵✶✷✸✹)
    # U+2750-U+2757 (shadowed squares, question marks), U+F06F, U+F071, U+F0B5, U+F0B6 (Private Use Area - polices Wingdings)
    # Inclut aussi les flèches: → ➔ ➜ ➤
    BULLET_CHARS = r"[*•●○◦▪▫■□►▸‣⁃❑❒◇◆★☆✦✧♦❖✳✴✵✶✷✸✹→➔➜➤\u2750-\u2757\uf06f\uf071\uf0b5\uf0b6]"

    # Pattern pour détecter un nouveau événement dans un texte multi-événements
    # Un nouvel événement commence par: bullet OU (retour ligne + artiste en MAJUSCULES)
    # Note: \u2019 est l'apostrophe typographique courante dans les PDFs
    MULTI_EVENT_SPLIT = re.compile(
        r'(?:\n\s*[*•●○◦▪▫■□►▸‣⁃❑❒◇◆★☆✦✧♦❖✳✴✵✶✷✸✹→➔➜➤\u2750-\u2757\uf06f\uf071\uf0b5\uf0b6]\s*)|'  # Bullet sur nouvelle ligne (inclut *)
        r"(?:\n\s*(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s'\u2019\-&]{2,}.*?,.*?\d+[hH]))",  # ARTISTE... , ... XXh
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
    # Gère les suffixes comme 's (BLACK ANGEL's, THEE MVP's)
    # Note: \u2019 est l'apostrophe typographique courante dans les PDFs
    ARTISTE_PATTERN = re.compile(r"([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s'\u2019\-&]{2,}(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ'\u2019\-&]+)*(?:['\u2019]s)?)")

    # Pattern pour les genres entre parenthèses
    GENRE_PATTERN = re.compile(r"\(([^)]+)\)")

    # Pattern pour les spectacles entre guillemets
    SPECTACLE_PATTERN = re.compile(r'[""«]([^""»]+)[""»]')

    def __init__(self, bidul_mois: Optional[int] = None, bidul_annee: Optional[int] = None,
                 date_format: Optional[str] = None, include_regional: bool = True):
        """
        Initialise le parser.

        Args:
            bidul_mois: Mois du Bidul (pour construire les dates complètes)
            bidul_annee: Année du Bidul
            date_format: Format des dates dans le texte:
                - 'inline': chaque ligne commence par la date (ex: "Je 02 : CONCERT...")
                - 'par bloc': dates en en-têtes de sections, événements listés en dessous
                - None: auto-détection (essaie les deux formats)
            include_regional: Si False, exclut la section "Et un peu plus loin..."
                contenant les événements hors département (61, 49, 53, etc.)
        """
        self.bidul_mois = bidul_mois
        self.bidul_annee = bidul_annee
        self.date_format = date_format
        self.include_regional = include_regional
        # Support juillet/août: sections de mois détectées et lignes du texte
        self._month_sections: list[MonthSection] = []
        self._lines: list[str] = []

    # Pattern pour détecter le début d'un événement inline
    # Supporte:
    # - Simple: "Je 01 :"
    # - Composé avec &: "Je 22 & Ve 23 :"
    # - Composé avec /: "Je 01/Ve 02 :" ou "Lu 12 /Ma 13/Me 14 :"
    # - Avec horaires: "Je 01/Ve 02 à 20h30 et Di 04 à 17h :"
    # - Avec tiret: "Je 29 -"
    # - Plage avec "au": "Ma 06 au Ve 09 :"
    # - Sans séparateur: "Sa 11 Afro-latino Party" (suivi d'un mot Title Case)
    # - Sans séparateur OCR: "Ma 28 <<LE CIRQUE" (guillemet OCR suivi de MAJUSCULES)
    # Group 1: Date complète (tout avant le séparateur)
    # Group 2: Contenu de l'événement (après le séparateur)
    # Pattern strict pour les abréviations de jours (évite de matcher "de 14", "le 25", etc.)
    # Lu, Ma, Me, Je, Ve, Sa, Di + formes longues
    _JOURS_INLINE = r'(?:[Ll]u|[Mm]a|[Mm]e|[Jj]e|[Vv]e|[Ss]a|[Dd]i|[Ll]undi|[Mm]ardi|[Mm]ercredi|[Jj]eudi|[Vv]endredi|[Ss]amedi|[Dd]imanche)'

    # Mois pour les dates avec mois explicite (ex: "Sa 1er Nov")
    _MOIS_INLINE = (
        r'(?:jan(?:v(?:ier)?)?|f[ée]v(?:rier)?|mars?|avr(?:il)?|mai|juin|'
        r'juil(?:let)?|ao[uû]t?|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?)'
    )

    INLINE_DATE_PATTERN = re.compile(
        r'^('  # Groupe 1: Date complète
        r'(?:'
        # Option 1: "Du DD" sans jour de semaine (ex: "Du 31 au 03/02:")
        r'Du\s+\d{1,2}(?:er|ère|ème|eme)?'
        r'|'
        # Option 2: "Jour DD" avec jour de semaine optionnel "Du" (ex: "Ma 29:", "Du Je 31:")
        rf'(?:Du\s+)?(?:{_JOURS_INLINE})\s+\d{{1,2}}(?:/\d{{2}})?(?:er|ère|ème|eme)?'
        r')'
        # Mois optionnel après la date (ex: "Sa 1er Nov", "Di 31 Déc")
        rf'(?:\s+{_MOIS_INLINE})?'
        r'(?:'
        # Jours additionnels avec / ou &, chaque jour pouvant avoir une heure (avec ou sans "à")
        # Ex: "Ve 1/Sa 02 à 21h/Di 03 15h30" ou "Ve 06/Sa 07 20h30/Di 08 15h"
        # Le dernier jour peut avoir une plage DD-DD (ex: "Me 01-04") pour les événements récurrents
        rf'(?:\s*[/&]\s*(?:{_JOURS_INLINE})?\s*\d{{1,2}}(?:-\d{{1,2}})?(?:er|ère|ème|eme)?(?:\s+(?:(?:à|a)\s+)?\d{{1,2}}h\d{{0,2}})?)*'
        # Plage "au Ve 09" ou "au 03/02" (avec mois explicite)
        rf'(?:\s+(?:au|à)\s+(?:{_JOURS_INLINE}\s*)?\d{{1,2}}(?:/\d{{2}})?(?:er|ère|ème|eme)?)?'
        r'(?:\s+(?:(?:à|a)\s+)?\d{1,2}h\d{0,2})?'  # Horaire optionnel (avec ou sans "à")
        rf'(?:\s+et\s+(?:{_JOURS_INLINE})?\s*\d{{1,2}}(?:er|ère|ème|eme)?(?:\s+(?:(?:à|a)\s+)?\d{{1,2}}h\d{{0,2}})?)*'  # "et Di 04 à 17h"
        r')?'
        r')'  # Fin groupe 1
        # Séparateur: soit : ou – soit espace suivi de:
        # - mot Title Case (Afro-latino)
        # - mot commençant par L' ou D' (L'Asso, D'artiste)
        # - guillemet ouvrant + mot majuscule (<<LE, <LE, "LE, «LE)
        # - mot tout en MAJUSCULES d'au moins 2 lettres
        # Note: le - seul n'est PAS un séparateur valide (utilisé pour plages DD-DD)
        r"(?:\s*[:–]\s*|\s+(?=[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç']|<{1,2}[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]|[«\"][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]|[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]{2}))"
        r'(.+)$',  # Contenu (groupe 2)
        re.MULTILINE | re.IGNORECASE
    )

    def parse(self, text: str) -> list[ParsedEvent]:
        """
        Parse le texte complet et extrait les événements.

        Supporte deux formats:
        1. Format standard (par bloc): dates sur lignes séparées, événements avec bullets
        2. Format inline: "Je 02 : ARTISTE (genre), Lieu, heure, prix"

        Le format peut être spécifié via self.date_format ou auto-détecté.

        Args:
            text: Texte brut extrait du PDF

        Returns:
            Liste d'événements parsés (dédoublonnés)
        """
        # Séparer le texte local et régional
        local_text, regional_text = split_regional_section(text)

        if not self.include_regional:
            # Mode exclusion: ignorer la section régionale
            if regional_text:
                logger.info(f"Section régionale exclue ({len(regional_text)} caractères)")
            text = local_text
            regional_text = ""

        # Détecter les sections de mois pour les Biduls d'été (juillet couvrant juillet+août)
        if is_summer_bidul(self.bidul_mois):
            self._month_sections = detect_month_sections(text)
            self._lines = text.split('\n')
            if self._month_sections:
                logger.info(f"Bidul juillet: {len(self._month_sections)} section(s) de mois détectée(s)")
                for section in self._month_sections:
                    logger.debug(f"  - Ligne {section.line_number}: mois={section.month} ({section.header_text})")

        # Parser les événements locaux
        local_events = self._parse_text_section(local_text)

        # Parser les événements régionaux si inclus
        regional_events = []
        if regional_text and self.include_regional:
            regional_events = self._parse_text_section(regional_text)
            logger.info(f"Section régionale: {len(regional_events)} événements parsés")

        # Appliquer le flag is_regional en utilisant detect_regional() pour vérification
        all_events = []

        for event in local_events:
            # Vérifier si l'événement est vraiment local avec detect_regional()
            detection = detect_regional(event.raw_text, event.lieu_raw, event.ville_raw)
            event.is_regional = detection.is_regional
            all_events.append(event)

        for event in regional_events:
            # Vérifier si l'événement est vraiment régional avec detect_regional()
            detection = detect_regional(event.raw_text, event.lieu_raw, event.ville_raw)
            # Si dans la section régionale mais detect_regional dit local, on garde local
            # Si detect_regional dit régional, on le marque régional
            event.is_regional = detection.is_regional
            all_events.append(event)

        # Log des corrections
        local_in_local = sum(1 for e in local_events if not e.is_regional)
        regional_in_local = sum(1 for e in local_events if e.is_regional)
        local_in_regional = sum(1 for e in regional_events if not e.is_regional)
        regional_in_regional = sum(1 for e in regional_events if e.is_regional)

        if regional_in_local > 0:
            logger.debug(f"Événements régionaux trouvés dans section locale: {regional_in_local}")
        if local_in_regional > 0:
            logger.info(f"Événements locaux récupérés de section régionale: {local_in_regional}")

        return all_events

    def _parse_text_section(self, text: str) -> list['ParsedEvent']:
        """
        Parse une section de texte (locale ou régionale).

        Args:
            text: Texte de la section

        Returns:
            Liste d'événements parsés (sans le flag is_regional assigné)
        """
        if not text.strip():
            return []

        # Si le format est spécifié, l'utiliser directement
        if self.date_format == 'inline':
            events = self._parse_inline_format(text)
            # Fallback sur l'autre format si rien trouvé
            if not events:
                events = self._parse_standard_format(text)
            return events
        elif self.date_format == 'par bloc':
            events = self._parse_standard_format(text)
            # Fallback sur l'autre format si rien trouvé
            if not events:
                events = self._parse_inline_format(text)
            return events
        elif self.date_format == 'inline_inherited':
            # Format hybride des anciens Biduls (1-16)
            # Date sur la première ligne du jour, événements suivants héritent
            events = self._parse_inline_inherited_format(text)
            # Fallback sur inline si rien trouvé
            if not events:
                events = self._parse_inline_format(text)
            return events

        # Auto-détection: essayer d'abord le format standard (par bloc)
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

            # Calculer le line_number pour cette date (support juillet/août)
            line_number = self._get_line_number_for_text(date_str) if date_str else None

            # Parser toutes les dates de la plage (ex: "Du 3 au 5" → [3, 4, 5])
            all_dates = self._parse_all_dates(date_str, line_number) if date_str else []
            if not all_dates:
                # Fallback sur une seule date si pas de plage
                single_date = self._parse_date(date_str, line_number) if date_str else None
                all_dates = [single_date] if single_date else [None]

            for event_text in event_texts:
                if len(event_text.strip()) < 10:
                    continue

                # Créer un événement pour chaque date de la plage
                for event_date in all_dates:
                    event = self._parse_event_with_date(event_text.strip(), date_str, event_date)
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

        # Prétraitement: joindre les dates splitées sur plusieurs lignes
        # Ex: "Sa 1er\nNov\nEVENT" -> "Sa 1er Nov\nEVENT"
        # Pattern: date seule sur une ligne + mois seul sur la ligne suivante
        text = self._join_split_dates(text)

        # Regrouper les lignes qui appartiennent au même événement
        # (certains événements sont sur plusieurs lignes)
        lines = text.split('\n')
        current_event_lines = []
        current_date = None
        current_line_number = None  # Support juillet/août

        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Vérifier si c'est une nouvelle ligne d'événement (commence par une date)
            match = self.INLINE_DATE_PATTERN.match(line)
            if match:
                # Traiter l'événement précédent
                if current_event_lines and current_date:
                    event_text = ' '.join(current_event_lines)
                    event = self._parse_event(event_text, current_date, current_line_number)
                    if event:
                        signature = self._event_signature(event)
                        if signature not in seen_signatures:
                            seen_signatures.add(signature)
                            events.append(event)

                # Commencer un nouvel événement
                # Group 1: date complète, Group 2: contenu
                current_date = match.group(1).strip()
                current_event_lines = [match.group(2).strip()]
                current_line_number = line_idx  # Mémoriser le numéro de ligne
            else:
                # Continuation de l'événement précédent
                if current_event_lines:
                    current_event_lines.append(line)

        # Traiter le dernier événement
        if current_event_lines and current_date:
            event_text = ' '.join(current_event_lines)
            event = self._parse_event(event_text, current_date, current_line_number)
            if event:
                signature = self._event_signature(event)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    events.append(event)

        return events

    def _parse_inline_inherited_format(self, text: str) -> list[ParsedEvent]:
        """
        Parse le format inline_inherited des anciens Biduls (1-16).

        Format hybride où la date apparaît sur la première ligne d'un jour
        et les événements suivants héritent de cette date:

            dim 01: À CHŒUR OUVERT, PCC, Le Mans, 15h00
            BIG BAND de Changé, Salle François Rabelais, 15h00  <- hérite de dim 01
            mar 03 Concert: LA SORCIERE DU PLACARD
            -PANDORA, Pirate Café, Le Mans, 21h30  <- hérite de mar 03
        """
        events = []
        seen_signatures = set()

        # Pattern pour détecter une ligne qui commence par une date
        # Supporte: dim 01:, mar 03, jeu 05:, etc.
        date_line_pattern = re.compile(
            r'^(lu[n]?|ma[r]?|me[r]?|je[u]?|ve[n]?|sa[m]?|di[m]?)\s+(\d{1,2})(?:er|ème|eme)?[^a-zA-Z0-9]*(.*)$',
            re.IGNORECASE
        )

        # Pattern pour détecter si une ligne est une continuation
        continuation_pattern = re.compile(
            r'^(?:[Ll][Ee]\s*[Mm][Aa][Nn][Ss]|[Mm]ulsanne|[Aa]llonnes|\([^)]+\)|[a-zàâäéèêëïîôùûüç]|\d{1,2}[hH]|[Dd]e \d)'
        )

        # Mots-clés qui indiquent une continuation (lieux, parties de texte)
        continuation_starts = (
            'Salle ', 'salle ', 'Conservatoire', 'Église', 'église', 'Eglise',
            'Nationale', 'nationale', 'École', 'école', 'Ecole', 'ecole',
            'Théâtre', 'théâtre', 'Theatre', 'theatre', 'Cathédrale', 'cathédrale',
            'Place ', 'place ', 'Château', 'château', 'Chateau',
            'Face ', 'face ', 'Espace', 'espace',
        )

        def is_new_event_line(line: str) -> bool:
            """Vérifie si une ligne est un nouvel événement (pas une continuation)."""
            if continuation_pattern.match(line):
                return False
            if line.startswith(continuation_starts):
                return False
            # Un nouvel événement commence par un tiret suivi d'un nom
            if line.startswith('-') and len(line) > 2:
                return True

            # Pattern: Nom d'artiste tout en MAJUSCULES (3+ caractères)
            # Ex: "DOWN TOWN JESUS", "LES HURLEURS", "BUDDY SCAKERS"
            words = line.split()
            if words:
                first_word = words[0]
                # Tout en majuscules et 3+ lettres
                if len(first_word) >= 3 and first_word.isupper() and first_word.isalpha():
                    return True
                # "Les" ou "The" suivi d'un mot en MAJUSCULES
                # Ex: "Les TABOURETS", "The ARTISTES"
                if first_word.lower() in ('les', 'the', 'la', 'le') and len(words) > 1:
                    second_word = words[1]
                    if len(second_word) >= 3 and second_word.isupper():
                        return True
                # Nom d'artiste en TitleCase suivi d'un chiffre ou autre mot
                # Ex: "Cobalt 62", "Hot-Tongs", "Step-Back"
                if len(first_word) >= 3 and first_word[0].isupper() and first_word[1:].islower():
                    lieu_prefixes = ('bar', 'salle', 'centre', 'espace', 'théâtre', 'église',
                                     'cathédrale', 'mairie', 'mjc', 'café', 'pub', 'foyer')
                    if first_word.lower() not in lieu_prefixes:
                        if len(words) > 1 or '-' in first_word:
                            return True

            # Un nouvel événement contient une virgule et commence par un nom en MAJUSCULES
            if ',' in line and len(line) > 5:
                first_part = line.split(',')[0].strip()
                if len(first_part) >= 3 and first_part.isupper():
                    return True
                # Mots-clés d'événements
                event_keywords = ('Concert', 'Audition', 'Soirée', 'Spectacle', 'Festival')
                if first_part.startswith(event_keywords):
                    return True
            return False

        # Prétraitement: séparer les événements fusionnés par une date inline
        # Pattern: "12€ Je 30 L'Asso..." -> "12€\nJe 30 L'Asso..."
        # Détecte: prix/heure suivi d'une date (lu/ma/me/je/ve/sa/di + numéro)
        inline_date_split_pattern = re.compile(
            r'(\d+[€F]|\d{1,2}[hH]\d{0,2})\s+'
            r'((?:lu[n]?|ma[r]?|me[r]?|je[u]?|ve[n]?|sa[m]?|di[m]?)\s+\d{1,2})',
            re.IGNORECASE
        )
        text = inline_date_split_pattern.sub(r'\1\n\2', text)

        lines = text.split('\n')
        mois = self.bidul_mois or 1
        annee = self.bidul_annee or 2023

        # Première passe: joindre les lignes de continuation
        joined_lines = []
        current_line = None

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if is_noise_line(line):
                continue

            is_new_date = date_line_pattern.match(line) is not None
            is_continuation = continuation_pattern.match(line) is not None
            is_new_event = is_new_event_line(line)

            if is_new_date:
                if current_line:
                    joined_lines.append(current_line)
                current_line = line
            elif is_continuation and current_line:
                current_line = current_line + ' ' + line
            elif is_new_event:
                if current_line:
                    joined_lines.append(current_line)
                current_line = line
            elif current_line:
                current_line = current_line + ' ' + line
            else:
                current_line = line

        if current_line:
            joined_lines.append(current_line)

        # Deuxième passe: parser les événements
        current_date_str = None
        current_date = None

        for line_idx, line in enumerate(joined_lines):
            date_match = date_line_pattern.match(line)

            if date_match:
                # Nouvelle date
                jour_abbr = date_match.group(1)
                jour_num = date_match.group(2)
                event_content = date_match.group(3).strip()

                current_date_str = f"{jour_abbr} {jour_num}"
                current_date = self._parse_date(current_date_str, line_idx)

                # Parser l'événement sur cette ligne
                if event_content and len(event_content) >= 5:
                    event = self._parse_event(event_content, current_date_str, line_idx)
                    if event:
                        if current_date and not event.date_evenement:
                            event.date_evenement = current_date
                        signature = self._event_signature(event)
                        if signature not in seen_signatures:
                            seen_signatures.add(signature)
                            events.append(event)

            elif current_date_str and len(line) >= 10 and is_new_event_line(line):
                # Nouvel événement sans date - hérite de la date courante
                # Retirer le tiret initial si présent
                event_text = line[1:].strip() if line.startswith('-') else line
                event = self._parse_event(event_text, current_date_str, line_idx)
                if event:
                    if current_date and not event.date_evenement:
                        event.date_evenement = current_date
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
        # Utiliser date_evenement si disponible (pour les plages de dates)
        date_key = event.date_evenement.isoformat() if event.date_evenement else event.date_str
        return f"{date_key}|{raw_norm}"

    def _split_by_dates(self, text: str) -> list[tuple[str, str]]:
        """Découpe le texte par blocs de dates."""
        blocks = []
        lines = text.split('\n')

        current_date = None
        current_block = []

        # Pattern pour détecter bullet + date sur la même ligne
        # Ex: "* Sa 01/Ve 07/Sa 08" ou "* Sa 01 LES RENDEZ-VOUS..."
        bullet_date_pattern = re.compile(
            rf'^{self.BULLET_CHARS}\s*'
            rf'({self.JOURS})\s+(\d{{1,2}})(?:er|ère|ème|eme)?'
            rf'(?:\s*[/&,]\s*(?:{self.JOURS})\s*\d{{1,2}}(?:er|ère|ème|eme)?)*'
            rf'(?:\s+(?:au|à)\s+(?:{self.JOURS})\s*\d{{1,2}}(?:er|ère|ème|eme)?)?',
            re.IGNORECASE
        )

        for line in lines:
            # Vérifier si c'est une ligne de date
            # Nettoyer les balises de formatage avant de matcher
            line_clean = strip_formatting_tags(line.strip())

            # D'abord essayer le format standard (date seule sur la ligne)
            match = self.DATE_PATTERN.match(line_clean)
            if match:
                # Sauvegarder le bloc précédent
                if current_date and current_block:
                    blocks.append((current_date, '\n'.join(current_block)))

                # Utiliser la ligne nettoyée comme date
                current_date = line_clean
                current_block = []
            else:
                # Essayer le format bullet + date (ex: "* Sa 01/Ve 07/Sa 08")
                bullet_match = bullet_date_pattern.match(line_clean)
                if bullet_match:
                    # Sauvegarder le bloc précédent
                    if current_date and current_block:
                        blocks.append((current_date, '\n'.join(current_block)))

                    # Extraire la date du match (tout après le bullet jusqu'à la fin du pattern)
                    date_start = bullet_match.start(1)  # Début du jour (Sa, Di, etc.)
                    date_end = bullet_match.end()
                    current_date = line_clean[date_start:date_end]

                    # Le reste de la ligne (après la date) fait partie du bloc
                    # IMPORTANT: Inclure la date dans le bloc pour que _split_by_bullets
                    # puisse conserver le contexte complet pour le raw_text
                    remaining = line_clean[date_start:].strip()
                    current_block = [remaining] if remaining else []
                else:
                    current_block.append(line)

        # Dernier bloc
        if current_date and current_block:
            blocks.append((current_date, '\n'.join(current_block)))

        return blocks

    def _truncate_after_price(self, text: str) -> str:
        """
        Tronque le texte après la ligne contenant le prix.

        Évite d'inclure le texte promotionnel qui suit l'événement.
        Délègue à la fonction standalone truncate_after_price().
        """
        return truncate_after_price(text)

    def _split_by_bullets(self, text: str) -> list[str]:
        """Découpe un bloc de texte par événements (bullets)."""
        # Cas spécial: bullets avec dates (ex: "* Sa 01", "* Di 02")
        # Dans ce cas, le caractère * peut aussi être utilisé comme guillemet OCR
        # (ex: *LE SPECTACLE" signifie «LE SPECTACLE»)
        # On split uniquement sur "bullet + jour + numéro"
        bullet_date_pattern = re.compile(
            rf'(?:^|\s){self.BULLET_CHARS}\s*({self.JOURS}\s+\d{{1,2}}(?:er|ère|ème|eme)?(?:à|\s))',
            re.IGNORECASE
        )

        if bullet_date_pattern.search(text):
            # Split sur bullet+date, en préservant la date dans chaque partie
            events = []
            last_end = 0

            for match in bullet_date_pattern.finditer(text):
                # Texte avant ce match (événement précédent ou header)
                before = text[last_end:match.start()].strip()
                if before:
                    events.append(before)

                # Le nouvel événement commence à la date (groupe 1)
                # match.start(1) pointe vers le début de "Sa 01" etc.
                last_end = match.start(1)

            # Dernier événement
            if last_end < len(text):
                remaining = text[last_end:].strip()
                if remaining:
                    events.append(remaining)

            # Post-traitement
            final_events = []
            for event_text in events:
                event_text = self._truncate_after_price(event_text)
                split_events = self._split_multi_events(event_text)
                final_events.extend(split_events)

            return final_events

        # Pattern standard pour bullets simples (sans date)
        # Note: on utilise un pattern qui exclut les bullets suivis de majuscules
        # car dans ce cas c'est probablement un guillemet OCR (ex: *LE SPECTACLE")
        # On ne split que sur les bullets suivis d'un espace puis texte normal
        pattern = re.compile(
            rf"(?:^|\n)\s*{self.BULLET_CHARS}\s*(?=[^A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\"]|$)",
            re.MULTILINE
        )

        parts = pattern.split(text)
        # Filtrer les parties vides
        events = [p.strip() for p in parts if p.strip()]

        # Si aucun split n'a été fait (1 seul élément = texte original), retourner tel quel
        if len(events) <= 1:
            event_text = self._truncate_after_price(text.strip())
            return self._split_multi_events(event_text)

        # Post-traitement: tronquer après le prix et séparer les multi-événements
        final_events = []
        for event_text in events:
            # Tronquer après le prix pour éviter le texte promotionnel
            event_text = self._truncate_after_price(event_text)
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
                    # Note: \u2019 est l'apostrophe typographique courante dans les PDFs
                    if re.match(r"^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s'\u2019\-&]{2,}", line_stripped):
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

        # Pattern : "texte" ou «texte» ou <<texte>> suivi optionnellement de (genre)
        # Inclut les patterns OCR avec << >> et les guillemets mal reconnus
        pattern = re.compile(r'(?:[""«]|<<\s*)([^""»]+?)(?:[""»]|\s*>>)\s*(?:\(([^)]+)\))?')

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

    def _parse_event_with_date(self, text: str, date_str: Optional[str], event_date: Optional[date]) -> Optional[ParsedEvent]:
        """
        Parse un événement avec une date spécifique déjà calculée.
        Utilisé pour les plages de dates où plusieurs événements sont créés.
        """
        event = self._parse_event(text, date_str)
        if event and event_date:
            event.date_evenement = event_date
        return event

    def _parse_event(self, text: str, date_str: Optional[str],
                     line_number: Optional[int] = None) -> Optional[ParsedEvent]:
        if not text:
            return None

        # Nettoyer les artifacts d'extraction
        text = self._clean_raw_text(text)
        if not text:
            return None

        # Supprimer le bruit après le prix/heure
        text = truncate_after_price(text)
        if not text:
            return None

        event = ParsedEvent(raw_text=text)

        if date_str:
            event.date_str = date_str
            event.date_evenement = self._parse_date(date_str, line_number)

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

        # 6. Lieu et ville - sur le texte nettoyé SANS balises de formatage
        text_for_lieu = strip_formatting_tags(text_cleaned)
        event.lieu_raw, event.ville_raw = self._extract_lieu_ville(text_for_lieu)

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

    def _get_line_number_for_text(self, text_fragment: str) -> int:
        """
        Trouve le numéro de ligne approximatif pour un fragment de texte.

        Utilisé pour déterminer le mois contextuel lors du parsing
        des Biduls d'été (juillet couvrant juillet+août).

        Args:
            text_fragment: Fragment de texte à localiser

        Returns:
            Numéro de ligne (0-indexed), ou 0 si non trouvé
        """
        if not self._lines:
            return 0

        text_clean = text_fragment.strip()[:50]  # Premiers 50 chars

        for i, line in enumerate(self._lines):
            if text_clean in line:
                return i

        return 0

    def _parse_date(self, date_str: str, line_number: Optional[int] = None) -> Optional[date]:
        """
        Convertit une date relative en date absolue.

        Args:
            date_str: Chaîne de date (ex: "Samedi 3", "Dimanche 1er décembre")
            line_number: Numéro de ligne pour déterminer le mois contextuel (Biduls d'été)

        Returns:
            Date absolue ou None
        """
        if not self.bidul_mois or not self.bidul_annee:
            return None

        # Déterminer le mois contextuel
        mois = self.bidul_mois
        annee = self.bidul_annee

        # Priorité 1: Mois explicite dans la chaîne de date (ex: "Dimanche 1er décembre")
        explicit_month = extract_explicit_month(date_str)
        if explicit_month is not None:
            mois = explicit_month
            # Si le mois explicite est avant le mois du bidul, c'est l'année suivante
            # Ex: Bidul de décembre avec événement en janvier
            if explicit_month < self.bidul_mois:
                annee = self.bidul_annee + 1

        # Priorité 2: Sections de mois pour les Biduls d'été (juillet/août)
        elif self._month_sections and line_number is not None:
            mois = get_month_for_line(self._month_sections, line_number, self.bidul_mois)

        match = re.search(r"(\d{1,2})", date_str)
        if match:
            jour = int(match.group(1))
            try:
                return date(annee, mois, jour)
            except ValueError:
                return None
        return None

    def _parse_all_dates(self, date_str: str, line_number: Optional[int] = None) -> list[date]:
        """
        Parse toutes les dates d'une chaîne de date (simple, composée, ou plage).

        Retourne une liste de dates:
        - "Samedi 2" → [2018-06-02]
        - "Samedi 2 & Dimanche 3" → [2018-06-02, 2018-06-03]
        - "Du 6 au 10 juin" → [date_6, date_7, ..., date_10]
        - "Du Vendredi 03 au Dimanche 05" → [date_3, date_4, date_5]
        - "Dimanche 1er décembre" → [2019-12-01] (mois explicite)

        Args:
            date_str: Chaîne de date
            line_number: Numéro de ligne pour déterminer le mois contextuel (Biduls d'été)

        Returns:
            Liste de dates
        """
        if not self.bidul_mois or not self.bidul_annee:
            return []

        # Déterminer le mois contextuel
        mois = self.bidul_mois
        annee = self.bidul_annee

        # Priorité 1: Mois explicite dans la chaîne de date (ex: "Dimanche 1er décembre")
        explicit_month = extract_explicit_month(date_str)
        if explicit_month is not None:
            mois = explicit_month
            # Si le mois explicite est avant le mois du bidul, c'est l'année suivante
            # Ex: Bidul de décembre avec événement en janvier
            if explicit_month < self.bidul_mois:
                annee = self.bidul_annee + 1

        # Priorité 2: Sections de mois pour les Biduls d'été (juillet/août)
        elif self._month_sections and line_number is not None:
            mois = get_month_for_line(self._month_sections, line_number, self.bidul_mois)

        dates = []

        # Vérifier si c'est une plage "Du X au Y" (avec jour abrégé ou complet)
        # Pattern: Du [Jour] N au [Jour] M
        # Support des formats avec mois: "Du 31 au 03/02" (31 janvier au 3 février)
        JOURS_PATTERN = r'(?:[Ll]undi|[Mm]ardi|[Mm]ercredi|[Jj]eudi|[Vv]endredi|[Ss]amedi|[Dd]imanche|[Ll]un|[Mm]ar|[Mm]er|[Jj]eu|[Vv]en|[Ss]am|[Dd]im|[Ll]u|[Mm]a|[Mm]e|[Jj]e|[Vv]e|[Ss]a|[Dd]i)'
        # Pattern avec mois optionnel dans la fin de plage: "Du 31 au 03/02"
        range_pattern_with_month = rf'^[Dd]u\s+(?:{JOURS_PATTERN}\s+)?(\d{{1,2}})(?:er|e|ème)?\s+(?:au|à)\s+(?:{JOURS_PATTERN}\s+)?(\d{{1,2}})/(\d{{2}})'
        range_match_month = re.match(range_pattern_with_month, date_str, re.IGNORECASE)

        if range_match_month:
            start_day = int(range_match_month.group(1))
            end_day = int(range_match_month.group(2))
            end_month = int(range_match_month.group(3))
            # Si le jour de fin est avant le jour de début, le début est le mois précédent
            if end_day < start_day:
                start_month = end_month - 1 if end_month > 1 else 12
                start_year = annee if end_month > 1 else annee - 1
            else:
                start_month = end_month
                start_year = annee
            # Générer les dates de début de mois jusqu'à la fin
            # D'abord les jours du mois de début
            if start_month != end_month:
                # Plage qui traverse les mois: 31/01 au 03/02
                import calendar
                _, last_day_start = calendar.monthrange(start_year, start_month)
                for day in range(start_day, last_day_start + 1):
                    try:
                        dates.append(date(start_year, start_month, day))
                    except ValueError:
                        pass
                # Puis les jours du mois de fin
                for day in range(1, end_day + 1):
                    try:
                        dates.append(date(annee, end_month, day))
                    except ValueError:
                        pass
            else:
                # Même mois
                for day in range(start_day, end_day + 1):
                    try:
                        dates.append(date(annee, end_month, day))
                    except ValueError:
                        pass
            return dates

        # Pattern standard sans mois
        range_pattern = rf'^[Dd]u\s+(?:{JOURS_PATTERN}\s+)?(\d{{1,2}})(?:er|e|ème)?\s+(?:au|à)\s+(?:{JOURS_PATTERN}\s+)?(\d{{1,2}})(?:er|e|ème)?'
        range_match = re.match(range_pattern, date_str, re.IGNORECASE)

        if range_match:
            start_day = int(range_match.group(1))
            end_day = int(range_match.group(2))
            # Générer toutes les dates de la plage
            for day in range(start_day, end_day + 1):
                try:
                    dates.append(date(annee, mois, day))
                except ValueError:
                    pass
            return dates

        # Vérifier si c'est une date avec mois explicite: "Ve 01/02" ou "01/02"
        date_with_month_pattern = rf'^(?:{JOURS_PATTERN}\s+)?(\d{{1,2}})/(\d{{2}})'
        date_month_match = re.match(date_with_month_pattern, date_str, re.IGNORECASE)
        if date_month_match:
            jour = int(date_month_match.group(1))
            month_explicit = int(date_month_match.group(2))
            try:
                dates.append(date(annee, month_explicit, jour))
            except ValueError:
                pass
            return dates

        # Extraire tous les numéros de jours (dates simples ou composées)
        # Pattern: jour suivi optionnellement de "er" ou "ème"
        jour_matches = re.findall(r'(\d{1,2})(?:er|ème|eme)?', date_str, re.IGNORECASE)

        for jour_str in jour_matches:
            jour = int(jour_str)
            try:
                dates.append(date(annee, mois, jour))
            except ValueError:
                # Jour invalide pour ce mois (ex: 31 février)
                pass

        return dates

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
            # Gère les suffixes comme 's (BLACK ANGEL's, THEE MVP's)
            # Gère les doubles parenthèses: DEBRUIT (FULL LIVE BAND) (electro ethnique)
            #   - La première parenthèse peut être une formation (incluse dans le nom)
            #   - La dernière parenthèse est le genre musical
            # Note: \u2019 est l'apostrophe typographique courante dans les PDFs
            match = re.match(
                r'^(?:[""«][^""»]+[""»]\s*)?'  # Optionnel: spectacle entre guillemets
                r"((?:\d+\s+)?[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s'\u2019\-&0-9]*?(?:['\u2019]s)?)"  # Nom artiste
                r'(?:\s*\(([A-Z][^)]+)\))?'  # Optionnel: (FORMATION) en majuscules - fait partie du nom
                r'(?:\s*\(([^)]+)\))?'  # Optionnel: (genre) - le vrai genre musical
                r'(?:\s*$|,)',  # Fin de segment
                segment
            )

            if match:
                nom = match.group(1).strip()
                # Si formation (group 2), l'inclure dans le nom
                if match.group(2):
                    nom = f"{nom} ({match.group(2)})"
                genre = match.group(3).strip() if match.group(3) else None

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
            # "par Béatrice Maine" (nom propre) - exclut "par la cie", "par le collectif", etc.
            (r'par\s+(?!la\s+(?:cie|compagnie)\b)(?!le\s+(?:chœur|collectif|groupe)\b)([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç]+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][a-zàâäéèêëïîôùûüç]+)+)(?:\s*,|\s*\(|$)', ''),
            # "par le chœur d'Orphée"
            (r'par\s+le\s+chœur\s+([^,\(\)]+?)(?:\s*,|\s*\(|$)', 'Chœur '),
            # "par le collectif XXX"
            (r'par\s+le\s+collectif\s+([^,\(\)]+?)(?:\s*,|\s*\(|$)', 'Collectif '),
        ]

        seen_noms = set()
        for pattern, prefix in par_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                nom = match.strip()
                if nom and len(nom) > 2:
                    # Éviter les faux positifs
                    skip_words = ['résa', 'réservation', 'issue', 'le bidul', 'tarif']
                    if not any(skip in nom.lower() for skip in skip_words):
                        full_nom = f"{prefix}{nom}" if prefix else nom
                        normalized_nom = _normalize_artist_name(full_nom)
                        # Éviter les doublons
                        if normalized_nom.lower() not in seen_noms:
                            seen_noms.add(normalized_nom.lower())
                            artistes.append(ArtisteInfo(
                                nom=normalized_nom,
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

        # Pattern "collectif XXX" sans "par" (ex: '"spectacle" (théâtre) collectif Grand Maximum')
        collectif_match = re.search(r'(?:^|,\s*|\s)[Cc]ollectif\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\'\-/&]+?)(?:\s*,|\s*\d{1,2}h|\s*\(|\s*<|\s*$)', text)
        if collectif_match:
            nom = collectif_match.group(1).strip().rstrip(',')
            if nom and len(nom) > 2:
                full_nom = f"Collectif {nom}"
                normalized_nom = _normalize_artist_name(full_nom)
                if normalized_nom.lower() not in seen_noms:
                    seen_noms.add(normalized_nom.lower())
                    artistes.append(ArtisteInfo(
                        nom=normalized_nom,
                        genre=None,
                        spectacle=None
                    ))

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

        # Séparer artiste et lieu quand ils sont collés (format anciens biduls)
        # Pattern: "DOWN TOWN JESUS Bar les Alizés" -> "DOWN TOWN JESUS, Bar les Alizés"
        # Le lieu commence par Bar, Salle, Centre, etc.
        artiste_lieu_pattern = re.compile(
            r'([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\'\-\&\.0-9]+?)\s+'
            r'((?:Bar|Salle|Espace|Centre|MJC|Café|Pub|Théâtre|Médiathèque|Péniche)\s+'
            r'(?:le\s+|la\s+|l\'|les\s+|du\s+|de\s+la\s+|des\s+|aux?\s+)?'
            r'[A-Za-zÀ-ÿ\s\'\-]+)',
            re.IGNORECASE
        )
        text_normalized = artiste_lieu_pattern.sub(r'\1, \2', text_normalized)

        # Extraire les villes entre parenthèses après un lieu
        # Pattern: "Bar les Alizés (Coulans/Gée)" -> "Bar les Alizés, Coulans/Gée"
        # Pattern: "Bar le Celtic (le Mans)" -> "Bar le Celtic, Le Mans"
        ville_in_parens_pattern = re.compile(
            r'((?:Bar|Salle|Espace|Centre|MJC|Café|Pub|Théâtre|Médiathèque|Péniche)\s+'
            r'(?:le\s+|la\s+|l\'|les\s+|du\s+|de\s+la\s+|des\s+|aux?\s+)?'
            r'[A-Za-zÀ-ÿ\s\'\-]+?)'
            r'\s*\(([A-Za-zÀ-ÿ\s\'\-/]+?)\)',
            re.IGNORECASE
        )
        text_normalized = ville_in_parens_pattern.sub(r'\1, \2', text_normalized)

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
            else:
                # Vérifier les patterns "Les/The + MAJUSCULES"
                # Ex: "Les TABOURETS", "The ARTISTES"
                words = first_part.split()
                if len(words) >= 2:
                    first_word = words[0]
                    if first_word.lower() in ('les', 'the', 'la', 'le'):
                        # Vérifier si le second mot est en majuscules
                        second_word = words[1]
                        if len(second_word) >= 3 and second_word.isupper():
                            start_idx = 1  # C'est un artiste, commencer à 1

        # Collecter les candidats lieu/ville
        for part in parts[start_idx:]:
            if not part:
                continue

            # Si c'est une heure ou un prix, essayer d'extraire la partie avant
            # Ex: "le Mans 20h" -> extraire "le Mans"
            if self.HEURE_PATTERN.search(part) or self.PRIX_PATTERN.search(part):
                # Essayer d'extraire la partie avant l'heure/prix
                before_heure = re.split(r'\s*\d{1,2}[hH:]\d{0,2}\b', part)[0].strip()
                before_prix = re.split(r'\s*\d+[.,]?\d*\s*[€F]\b', before_heure)[0].strip()
                if before_prix and len(before_prix) >= 3:
                    part = before_prix
                else:
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
        # IMPORTANT: vérifier les villes EN PREMIER car le référentiel lieu_ref peut
        # contenir des erreurs (ex: "La Flèche" comme lieu alors que c'est une ville)
        lieu = None
        ville = None
        villes_trouvees = []  # Collecter toutes les villes trouvées

        from core.normalizer import normalize_for_matching

        for candidate in candidates:
            # Vérifier d'abord si c'est une ville connue (priorité sur lieu)
            # Note: normalize_ville retourne toujours un ID (Le Mans par défaut),
            # donc on compare le nom normalisé retourné avec le candidat pour
            # déterminer si c'est vraiment une ville reconnue.
            ville_id, ville_norm = normalize_ville(candidate)
            candidate_normalized = normalize_for_matching(candidate)
            ville_normalized = normalize_for_matching(ville_norm)

            # C'est une ville si le nom retourné correspond au candidat
            # (pas juste "Le Mans" par défaut pour n'importe quel texte)
            if ville_norm.lower() != 'le mans' or candidate_normalized == ville_normalized:
                villes_trouvees.append({
                    'id': ville_id,
                    'nom': ville_norm,
                    'raw': candidate,
                    'is_lemans': ville_norm.lower() == 'le mans'
                })
                continue

            # Vérifier si c'est un lieu connu
            lieu_id, lieu_norm = normalize_lieu(candidate)
            if lieu_id is not None:
                if lieu is None:
                    lieu = candidate
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

    def _join_split_dates(self, text: str) -> str:
        """
        Joint les dates splitées sur plusieurs lignes et associe les dates
        sans contenu à la ligne de contenu suivante.

        Problème OCR 1: date splitée sur 2 lignes:
            Sa 1er
            Nov
            YACINE AND CO...

        Devient:
            Sa 1er Nov YACINE AND CO...

        Problème OCR 2: dates sans contenu suivies de contenu sans date:
            Ve 31
            Ve 31
            Sa 1er Nov
            EVENT1
            EVENT2
            EVENT3

        Devient:
            Ve 31 EVENT1
            Ve 31 EVENT2
            Sa 1er Nov EVENT3
        """
        lines = text.split('\n')
        result_lines = []

        # Pattern pour détecter une ligne qui est juste une date (sans contenu)
        date_only_pattern = re.compile(
            r'^(?:lu[n]?|ma[r]?|me[r]?|je[u]?|ve[n]?|sa[m]?|di[m]?)\s+\d{1,2}(?:er|ère|ème|eme)?\s*$',
            re.IGNORECASE
        )

        # Pattern pour un mois seul
        month_only_pattern = re.compile(
            r'^(?:jan(?:v(?:ier)?)?|f[ée]v(?:rier)?|mars?|avr(?:il)?|mai|juin|'
            r'juil(?:let)?|ao[uû]t?|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?)\s*$',
            re.IGNORECASE
        )

        # Pattern pour une date complète avec mois mais sans contenu (ex: "Sa 1er Nov")
        date_with_month_only_pattern = re.compile(
            r'^(?:lu[n]?|ma[r]?|me[r]?|je[u]?|ve[n]?|sa[m]?|di[m]?)\s+\d{1,2}(?:er|ère|ème|eme)?\s+'
            r'(?:jan(?:v(?:ier)?)?|f[ée]v(?:rier)?|mars?|avr(?:il)?|mai|juin|'
            r'juil(?:let)?|ao[uû]t?|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?)\s*$',
            re.IGNORECASE
        )

        # Pattern pour détecter si une ligne commence par une date (a du contenu)
        date_with_content_pattern = re.compile(
            r'^(?:lu[n]?|ma[r]?|me[r]?|je[u]?|ve[n]?|sa[m]?|di[m]?)\s+\d{1,2}(?:er|ère|ème|eme)?'
            r'(?:\s+(?:jan(?:v(?:ier)?)?|f[ée]v(?:rier)?|mars?|avr(?:il)?|mai|juin|'
            r'juil(?:let)?|ao[uû]t?|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?))?'
            r'\s+\S',  # Suivi de contenu non-vide
            re.IGNORECASE
        )

        # Pattern pour détecter le DÉBUT d'un nouvel événement
        # (commence par majuscule, guillemet, ou deux-points - PAS de IGNORECASE)
        # Les lignes en minuscule sont des continuations
        new_event_pattern = re.compile(
            r'^(?:[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]|[«\"<]|:)'
        )

        # File de dates en attente (FIFO)
        pending_dates: list[str] = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Vérifier si c'est une date seule (sans contenu)
            if date_only_pattern.match(line):
                # Regarder si la ligne suivante est un mois
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if month_only_pattern.match(next_line):
                        # Joindre date + mois
                        pending_dates.append(f"{line} {next_line}")
                        i += 2
                        continue

                # Date seule sans mois
                pending_dates.append(line)
                i += 1
                continue

            # Vérifier si c'est une date avec mois mais sans contenu
            if date_with_month_only_pattern.match(line):
                pending_dates.append(line)
                i += 1
                continue

            # C'est une ligne de contenu
            # Si elle commence déjà par une date avec contenu, vider les dates en attente
            if date_with_content_pattern.match(line):
                pending_dates.clear()
                result_lines.append(line)
                i += 1
                continue

            # Ligne de contenu sans date - associer avec la première date en attente
            # SEULEMENT si c'est le début d'un nouvel événement (majuscule/guillemet/deux-points)
            if pending_dates and new_event_pattern.match(line):
                date_to_use = pending_dates.pop(0)
                line = f"{date_to_use} {line}"

            result_lines.append(line)
            i += 1

        return '\n'.join(result_lines)

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
            # Villes avec "/" pour "sur" (erreur OCR ou abréviation)
            (r'Coulans\s*/\s*G[ée]e?', 'Coulans-sur-Gée'),
            (r'Brains\s*/\s*G[ée]e?', 'Brains-sur-Gée'),
            # Variantes de Le Mans
            (r'\ble\s+mans\b', 'Le Mans'),
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

    def parse_with_referentiel(
        self,
        text: str,
        lieu_ref_list: list,
        ville_ref_list: list
    ) -> list[ParsedEvent]:
        """
        Parse le texte avec la stratégie "lieu d'abord" utilisant les référentiels.

        Cette méthode est plus précise que parse() car elle:
        1. Trouve d'abord le lieu dans le référentiel
        2. Parse ce qui est avant le lieu (artistes, spectacles)
        3. Parse ce qui est après le lieu (ville, heure, prix)

        Le format peut être spécifié via self.date_format:
        - 'inline': chaque ligne commence par la date (ex: "Je 02 : CONCERT...")
        - 'par bloc': dates en en-têtes de sections, événements listés en dessous
        - None: auto-détection (essaie les deux formats)

        Args:
            text: Texte brut extrait du PDF
            lieu_ref_list: Liste de tuples (id, nom, ville) pour les lieux
            ville_ref_list: Liste de tuples (id, nom) pour les villes

        Returns:
            Liste d'événements parsés (dédoublonnés)
        """
        # Séparer le texte local et régional
        local_text, regional_text = split_regional_section(text)

        if not self.include_regional:
            # Mode exclusion: ignorer la section régionale
            if regional_text:
                logger.info(f"Section régionale exclue ({len(regional_text)} caractères)")
            regional_text = ""

        # Détecter les sections de mois pour les Biduls d'été (juillet couvrant juillet+août)
        if is_summer_bidul(self.bidul_mois):
            self._month_sections = detect_month_sections(local_text)
            self._lines = local_text.split('\n')
            if self._month_sections:
                logger.info(f"Bidul juillet: {len(self._month_sections)} section(s) de mois détectée(s)")
                for section in self._month_sections:
                    logger.debug(f"  - Ligne {section.line_number}: mois={section.month} ({section.header_text})")

        # Parser les événements locaux
        local_events = self._parse_text_section_with_referentiel(local_text, lieu_ref_list, ville_ref_list)

        # Parser les événements régionaux si inclus
        regional_events = []
        if regional_text and self.include_regional:
            regional_events = self._parse_text_section_with_referentiel(regional_text, lieu_ref_list, ville_ref_list)
            logger.info(f"Section régionale: {len(regional_events)} événements parsés")

        # Appliquer le flag is_regional en utilisant detect_regional() pour vérification
        all_events = []

        for event in local_events:
            # Vérifier si l'événement est vraiment local avec detect_regional()
            detection = detect_regional(event.raw_text, event.lieu_raw, event.ville_raw)
            event.is_regional = detection.is_regional
            if event.is_valid():
                all_events.append(event)

        for event in regional_events:
            # Vérifier si l'événement est vraiment régional avec detect_regional()
            detection = detect_regional(event.raw_text, event.lieu_raw, event.ville_raw)
            # Si detect_regional dit local, on le marque local (récupération)
            event.is_regional = detection.is_regional
            if event.is_valid():
                all_events.append(event)

        # Log des corrections
        local_in_local = sum(1 for e in local_events if not e.is_regional)
        regional_in_local = sum(1 for e in local_events if e.is_regional)
        local_in_regional = sum(1 for e in regional_events if not e.is_regional)
        regional_in_regional = sum(1 for e in regional_events if e.is_regional)

        if regional_in_local > 0:
            logger.debug(f"Événements régionaux trouvés dans section locale: {regional_in_local}")
        if local_in_regional > 0:
            logger.info(f"Événements locaux récupérés de section régionale: {local_in_regional}")

        return all_events

    def _parse_text_section_with_referentiel(
        self,
        text: str,
        lieu_ref_list: list,
        ville_ref_list: list
    ) -> list['ParsedEvent']:
        """
        Parse une section de texte (locale ou régionale) avec les référentiels.

        Args:
            text: Texte de la section
            lieu_ref_list: Liste de tuples (id, nom, ville) pour les lieux
            ville_ref_list: Liste de tuples (id, nom) pour les villes

        Returns:
            Liste d'événements parsés (sans le flag is_regional assigné)
        """
        if not text.strip():
            return []

        # Si le format est spécifié, l'utiliser directement
        if self.date_format == 'inline':
            events = self._parse_inline_with_referentiel(text, lieu_ref_list, ville_ref_list)
            # Fallback sur l'autre format si rien trouvé
            if not events:
                events = self._parse_bloc_with_referentiel(text, lieu_ref_list, ville_ref_list)
            return events
        elif self.date_format == 'inline_inherited':
            # Format hybride des anciens Biduls (1-16)
            # Date sur la première ligne du jour, événements suivants héritent
            events = self._parse_inline_inherited_date(text, lieu_ref_list, ville_ref_list)
            # Fallback sur inline si rien trouvé
            if not events:
                events = self._parse_inline_with_referentiel(text, lieu_ref_list, ville_ref_list)
            return events
        elif self.date_format == 'par bloc':
            events = self._parse_bloc_with_referentiel(text, lieu_ref_list, ville_ref_list)
            # Fallback sur l'autre format si rien trouvé
            if not events:
                events = self._parse_inline_with_referentiel(text, lieu_ref_list, ville_ref_list)
            return events
        elif self.date_format == 'mixte':
            # Format mixte: combine inline ET bloc
            # Utilisé quand un bidul a plusieurs sections avec des formats différents
            # Ex: section Concerts en inline, section Théâtre avec bullets
            events_inline = self._parse_inline_with_referentiel(text, lieu_ref_list, ville_ref_list)
            events_bloc = self._parse_bloc_with_referentiel(text, lieu_ref_list, ville_ref_list)

            # Fusionner les résultats en évitant les doublons
            # Priorité au parsing bloc (plus précis) puis inline
            seen_signatures = set()
            seen_raw_texts = set()  # Pour détecter les supersets
            events = []

            # D'abord les événements bloc (plus précis)
            for event in events_bloc:
                sig = self._event_signature(event)
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    # Normaliser le raw_text pour comparaison
                    raw_norm = ''.join(event.raw_text.lower().split())
                    seen_raw_texts.add(raw_norm)
                    events.append(event)

            # Ensuite les événements inline, mais filtrer ceux qui sont des supersets
            for event in events_inline:
                sig = self._event_signature(event)
                if sig not in seen_signatures:
                    # Vérifier si cet événement est un superset d'un événement bloc
                    raw_norm = ''.join(event.raw_text.lower().split())
                    is_superset = any(
                        bloc_raw in raw_norm and len(raw_norm) > len(bloc_raw) * 1.5
                        for bloc_raw in seen_raw_texts
                    )
                    if not is_superset:
                        seen_signatures.add(sig)
                        seen_raw_texts.add(raw_norm)
                        events.append(event)

            return events

        # Auto-détection: essayer d'abord le format par bloc
        events = self._parse_bloc_with_referentiel(text, lieu_ref_list, ville_ref_list)

        # Si aucun événement trouvé, essayer le format inline
        if not events:
            events = self._parse_inline_with_referentiel(text, lieu_ref_list, ville_ref_list)

        return events

    def _parse_bloc_with_referentiel(
        self,
        text: str,
        lieu_ref_list: list,
        ville_ref_list: list
    ) -> list[ParsedEvent]:
        """Parse le format par bloc (dates en en-têtes) avec les référentiels."""
        events = []
        seen_signatures = set()

        # Découper par dates
        date_blocks = self._split_by_dates(text)

        for date_str, block_text in date_blocks:
            # Découper par événements (bullets)
            event_texts = self._split_by_bullets(block_text)

            # Calculer le line_number pour cette date (support juillet/août)
            line_number = self._get_line_number_for_text(date_str) if date_str else None

            # Déterminer le mois et l'année contextuels
            mois = self.bidul_mois or 1
            annee = self.bidul_annee or 2023

            # Priorité 1: Mois explicite dans le header de date (ex: "Dimanche 2 février")
            explicit_month = extract_explicit_month(date_str) if date_str else None
            if explicit_month is not None:
                mois = explicit_month
                # Si le mois explicite est avant le mois du bidul, c'est l'année suivante
                if explicit_month < (self.bidul_mois or 1):
                    annee = (self.bidul_annee or 2023) + 1

            # Priorité 2: Sections de mois pour les Biduls d'été (juillet/août)
            elif self._month_sections and line_number is not None:
                mois = get_month_for_line(self._month_sections, line_number, self.bidul_mois or 7)

            for event_text in event_texts:
                if len(event_text.strip()) < 10:
                    continue

                # Séparer les événements fusionnés (ex: "ARTISTE1, lieu, 5€ ARTISTE2, lieu, 3€")
                # Ceci gère les cas où plusieurs événements sont sur la même ligne
                sub_events = split_bloc_fused_events(event_text.strip())

                for sub_event_text in sub_events:
                    if len(sub_event_text.strip()) < 10:
                        continue

                    # Utiliser parse_event_line_v2 pour chaque ligne
                    # Passer le mois/année contextuels (avec mois explicite si présent)
                    parsed_events = parse_event_line_v2(
                        sub_event_text.strip(),
                        mois,
                        annee,
                        lieu_ref_list,
                        ville_ref_list
                    )

                    for parsed in parsed_events:
                        # Convertir le dict en ParsedEvent
                        # Pour les dates composées, créer un événement par date
                        event_dates = self._parse_all_dates(date_str, line_number)

                        if not event_dates:
                            # Pas de date spécifique (plage ou date invalide)
                            # Utiliser la première date trouvée ou None
                            event = self._dict_to_parsed_event(parsed, date_str)
                            if event:
                                signature = self._event_signature(event)
                                if signature not in seen_signatures:
                                    seen_signatures.add(signature)
                                    events.append(event)
                        else:
                            # Créer un événement pour chaque date
                            for event_date in event_dates:
                                # Reconstruire date_str pour cette date spécifique
                                jours = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di']
                                single_date_str = f"{jours[event_date.weekday()]} {event_date.day}"

                                event = self._dict_to_parsed_event(parsed, single_date_str)
                                if event:
                                    # Forcer la date du bloc SEULEMENT si l'événement n'a pas
                                    # sa propre date (extraite d'un split mid-text)
                                    if not parsed.get('date_evenement'):
                                        event.date_evenement = event_date
                                    signature = self._event_signature(event)
                                    if signature not in seen_signatures:
                                        seen_signatures.add(signature)
                                        events.append(event)

        return events

    def _parse_inline_with_referentiel(
        self,
        text: str,
        lieu_ref_list: list,
        ville_ref_list: list
    ) -> list[ParsedEvent]:
        """Parse le format inline avec la stratégie 'lieu d'abord'."""
        # Nettoyer les indicateurs ordinaux (º ª) qui perturbent le parsing
        text = text.replace('º', '').replace('ª', '')

        # Prétraitement: joindre les dates splitées sur plusieurs lignes
        # et associer les dates sans contenu aux lignes de contenu suivantes
        text = self._join_split_dates(text)

        events = []
        seen_signatures = set()

        # Référence aux attributs pour la closure
        month_sections = self._month_sections
        bidul_mois = self.bidul_mois

        def process_event(event_text: str, date_str: str, line_number: int = None):
            """Traite un événement avec une date (potentiellement composée)."""
            nonlocal events, seen_signatures

            # Déterminer le mois contextuel pour les Biduls d'été
            mois = bidul_mois or 1
            if month_sections and line_number is not None:
                mois = get_month_for_line(month_sections, line_number, bidul_mois or 7)

            # Parser les dates composées
            date_list, _ = parse_date_prefix_v2(
                f"{date_str}: dummy",  # Simuler le format attendu
                mois,
                self.bidul_annee or 2023
            )

            if not date_list:
                # Fallback: utiliser _parse_date pour une date simple
                single_date = self._parse_date(date_str, line_number)
                date_list = [single_date] if single_date else [None]

            # Séparer les événements fusionnés (ex: "ARTISTE1, lieu, 5€ ARTISTE2, lieu, 3€")
            sub_events = split_bloc_fused_events(event_text)

            for sub_event_text in sub_events:
                if len(sub_event_text.strip()) < 10:
                    continue

                # Parser le contenu de l'événement
                parsed_events = parse_event_line_v2(
                    sub_event_text.strip(),
                    mois,
                    self.bidul_annee or 2023,
                    lieu_ref_list,
                    ville_ref_list
                )

                for parsed in parsed_events:
                    # Si parse_event_line_v2 a déjà extrait une date (via split mid-text),
                    # utiliser cette date au lieu de la date du préfixe
                    if parsed.get('date_evenement'):
                        event = self._dict_to_parsed_event(parsed, None)
                        if event:
                            signature = self._event_signature(event)
                            if signature not in seen_signatures:
                                seen_signatures.add(signature)
                                events.append(event)
                    else:
                        # Créer un événement pour chaque date de la liste
                        for event_date in date_list:
                            # Construire date_str pour cette date
                            if event_date:
                                jours = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di']
                                single_date_str = f"{jours[event_date.weekday()]} {event_date.day}"
                            else:
                                single_date_str = date_str

                            event = self._dict_to_parsed_event(parsed, single_date_str)
                            if event:
                                if event_date:
                                    event.date_evenement = event_date
                                signature = self._event_signature(event)
                                if signature not in seen_signatures:
                                    seen_signatures.add(signature)
                                    events.append(event)

        lines = text.split('\n')
        current_event_lines = []
        current_date = None
        current_line_number = None  # Support juillet/août

        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            match = self.INLINE_DATE_PATTERN.match(line)
            if match:
                # Traiter l'événement précédent
                if current_event_lines and current_date:
                    event_text = ' '.join(current_event_lines)
                    process_event(event_text, current_date, current_line_number)

                # Group 1: date complète, Group 2: contenu
                current_date = match.group(1).strip()
                current_event_lines = [match.group(2).strip()]
                current_line_number = line_idx  # Mémoriser le numéro de ligne
            else:
                if current_event_lines:
                    current_event_lines.append(line)

        # Traiter le dernier événement
        if current_event_lines and current_date:
            event_text = ' '.join(current_event_lines)
            process_event(event_text, current_date, current_line_number)

        return events

    def _parse_inline_inherited_date(
        self,
        text: str,
        lieu_ref_list: list,
        ville_ref_list: list
    ) -> list[ParsedEvent]:
        """
        Parse le format hybride des anciens Biduls (1-16).

        Format: La première ligne d'un jour a la date inline, les événements
        suivants du même jour n'ont PAS de date et héritent de la date précédente.

        Exemple:
            Ma 02: CARTE BLANCHE, bar Le Mackeson, LE MANS, 22h15
            SHORT STORIES DJ, café Le Wagon, LE MANS, 20h30  <- hérite de Ma 02
            Je 04: MATMAT HA, bar Aux Viking's, LE MANS, 21h

        Gère aussi les événements sur plusieurs lignes:
            Ma 02: CARTE BLANCHE, bar Le Mackeson,
            LE MANS, 22h15
        """
        events = []
        seen_signatures = set()

        # Pattern pour détecter une ligne qui commence par une date
        # Note: Le contenu (groupe 3) est optionnel car la date peut être seule
        # sur sa ligne (ex: "Je 05:") avec les événements sur les lignes suivantes
        # Supporte:
        #   - Abréviations 2 lettres: Lu, Ma, Me, Je, Ve, Sa, Di
        #   - Abréviations 3 lettres: lun, mar, mer, jeu, ven, sam, dim
        #   - Avec ou sans deux-points après le numéro
        #   - Caractères OCR mal reconnus après le numéro (ex: "dim 01À" au lieu de "dim 01:")
        #   - Dates consécutives: "Je 06,07,08" (groupe 2 capture tous les numéros)
        date_line_pattern = re.compile(
            r'^(lu[n]?|ma[r]?|me[r]?|je[u]?|ve[n]?|sa[m]?|di[m]?)\s+(\d{1,2}(?:,\s*\d{1,2})*)(?:er|ème|eme)?[^a-zA-Z0-9]*(.*)$',
            re.IGNORECASE
        )

        # Pattern pour détecter si une ligne est une continuation
        # (commence par une ville connue, heure, prix, mot en minuscules, ou parenthèse)
        # Note: On ne peut pas utiliser re.IGNORECASE car on veut que [a-z] ne matche que les minuscules
        continuation_pattern = re.compile(
            r'^(?:[Ll][Ee]\s*[Mm][Aa][Nn][Ss]|[Mm]ulsanne|[Aa]llonnes|\([^)]+\)|[a-zàâäéèêëïîôùûüç]|\d{1,2}[hH]|[Dd]e \d)'
        )

        # Un nouvel événement est une ligne qui:
        # 1. Contient une virgule (séparateur typique)
        # 2. N'est PAS une continuation (pas une ville, heure, etc.)
        # 3. Ressemble à un nom d'artiste (au moins 2 caractères avant la virgule)

        # Prétraitement: séparer les événements fusionnés par une date inline
        # Pattern: "12€ Je 30 L'Asso..." -> "12€\nJe 30 L'Asso..."
        # Détecte: prix/heure suivi d'une date (lu/ma/me/je/ve/sa/di + numéro)
        inline_date_split_pattern = re.compile(
            r'(\d+[€F]|\d{1,2}[hH]\d{0,2})\s+'
            r'((?:lu[n]?|ma[r]?|me[r]?|je[u]?|ve[n]?|sa[m]?|di[m]?)\s+\d{1,2})',
            re.IGNORECASE
        )
        text = inline_date_split_pattern.sub(r'\1\n\2', text)

        lines = text.split('\n')
        mois = self.bidul_mois or 1
        annee = self.bidul_annee or 2023

        def is_new_event_line(line: str) -> bool:
            """Vérifie si une ligne est un nouvel événement (pas une continuation)."""
            # Une continuation commence par une ville, heure, prix, parenthèse, ou minuscule
            if continuation_pattern.match(line):
                return False

            # Lignes qui sont clairement des continuations (lieux, parties d'événements)
            # et pas de nouveaux événements
            continuation_starts = (
                'Salle ', 'salle ', 'Conservatoire', 'Église', 'église', 'Eglise',
                'Nationale', 'nationale', 'École', 'école', 'Ecole', 'ecole',
                'Théâtre', 'théâtre', 'Theatre', 'theatre', 'Cathédrale', 'cathédrale',
                'Place ', 'place ', 'Château', 'château', 'Chateau',
                'Face ', 'face ', 'Espace', 'espace', 'Bar ', 'bar ',
                'MJC ', 'Centre ', 'centre ',
            )
            if line.startswith(continuation_starts):
                return False

            # Un nouvel événement commence par un tiret suivi d'un nom
            if line.startswith('-') and len(line) > 2:
                return True

            # Pattern: Nom d'artiste tout en MAJUSCULES (3+ caractères)
            # Ex: "DOWN TOWN JESUS", "LES HURLEURS", "BUDDY SCAKERS"
            words = line.split()
            if words:
                first_word = words[0]
                # Tout en majuscules et 3+ lettres
                if len(first_word) >= 3 and first_word.isupper() and first_word.isalpha():
                    return True
                # "Les" ou "The" suivi d'un mot en MAJUSCULES
                # Ex: "Les TABOURETS", "The ARTISTES"
                if first_word.lower() in ('les', 'the', 'la', 'le') and len(words) > 1:
                    second_word = words[1]
                    if len(second_word) >= 3 and second_word.isupper():
                        return True
                # Nom d'artiste en TitleCase suivi d'un chiffre ou autre mot
                # Ex: "Cobalt 62", "Hot-Tongs", "Step-Back"
                # Pattern: Commence par majuscule, mot de 3+ chars, suivi éventuellement de chiffre
                if len(first_word) >= 3 and first_word[0].isupper() and first_word[1:].islower():
                    # Vérifier que ce n'est pas un lieu (Bar, Salle, etc.)
                    lieu_prefixes = ('bar', 'salle', 'centre', 'espace', 'théâtre', 'église',
                                     'cathédrale', 'mairie', 'mjc', 'café', 'pub', 'foyer')
                    if first_word.lower() not in lieu_prefixes:
                        # Vérifier qu'il y a un second élément (chiffre, autre mot, tiret)
                        if len(words) > 1 or '-' in first_word:
                            return True

            # Un nouvel événement contient une virgule et commence par quelque chose
            # qui ressemble à un nom d'artiste (typiquement en MAJUSCULES ou avec mots-clés)
            if ',' in line and len(line) > 5:
                first_part = line.split(',')[0].strip()
                # Nom d'artiste en majuscules (ex: "SATANAS & LES DIABOLOS")
                if len(first_part) >= 3 and first_part.isupper():
                    return True
                # Mots-clés d'événements (Concert:, Audition, Soirée, etc.)
                event_keywords = ('Concert', 'Audition', 'Soirée', 'Spectacle', 'Festival')
                if first_part.startswith(event_keywords):
                    return True
            return False

        # Première passe: joindre les lignes de continuation
        joined_lines = []
        current_line = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Vérifier si c'est une ligne de bruit (texte éditorial)
            if is_noise_line(line):
                continue

            # Vérifier si c'est une nouvelle date ou un nouvel événement
            is_new_date = date_line_pattern.match(line) is not None
            is_continuation = continuation_pattern.match(line) is not None
            is_new_event = is_new_event_line(line)

            if is_new_date:
                # Nouvelle date - sauvegarder la ligne précédente
                if current_line:
                    joined_lines.append(current_line)
                current_line = line
            elif is_continuation and current_line:
                # Joindre à la ligne précédente
                current_line = current_line + ' ' + line
            elif is_new_event:
                # Nouvel événement - sauvegarder la ligne précédente
                if current_line:
                    joined_lines.append(current_line)
                current_line = line
            elif current_line:
                # Par défaut, considérer comme continuation
                current_line = current_line + ' ' + line
            else:
                current_line = line

        # Sauvegarder la dernière ligne
        if current_line:
            joined_lines.append(current_line)

        # Deuxième passe: parser les événements
        current_date_str = None
        current_date = None

        for line_idx, line in enumerate(joined_lines):
            # Vérifier si la ligne commence par une date
            # Note: on vérifie d'abord la date car des lignes courtes comme "Je 05:"
            # sont valides et doivent établir la date courante
            date_match = date_line_pattern.match(line)

            if date_match:
                # Nouvelle date (potentiellement multiple: "Je 06,07,08")
                jour_abbr = date_match.group(1)
                jour_nums_str = date_match.group(2)
                event_content = date_match.group(3).strip()

                # Extraire tous les numéros de jour
                jour_nums = [int(n.strip()) for n in jour_nums_str.split(',') if n.strip().isdigit()]

                if not jour_nums:
                    continue

                # Pour les dates multiples, créer un événement par date
                if len(jour_nums) > 1 and event_content and len(event_content) >= 5:
                    for jour_num in jour_nums:
                        date_str = f"{jour_abbr} {jour_num}"
                        event_date = self._parse_date(date_str, line_idx)
                        self._process_inherited_event(
                            event_content, date_str, event_date,
                            mois, annee, lieu_ref_list, ville_ref_list,
                            events, seen_signatures
                        )
                    # Mettre à jour current_date avec la dernière date
                    current_date_str = f"{jour_abbr} {jour_nums[-1]}"
                    current_date = self._parse_date(current_date_str, line_idx)
                else:
                    # Date simple
                    jour_num = jour_nums[0]
                    current_date_str = f"{jour_abbr} {jour_num}"
                    current_date = self._parse_date(current_date_str, line_idx)

                    # Parser l'événement sur cette ligne
                    if event_content and len(event_content) >= 5:
                        self._process_inherited_event(
                            event_content, current_date_str, current_date,
                            mois, annee, lieu_ref_list, ville_ref_list,
                            events, seen_signatures
                        )

            elif current_date_str and len(line) >= 10 and is_new_event_line(line):
                # Nouvel événement sans date - hérite de la date courante
                # Note: len >= 10 pour éviter les lignes trop courtes
                self._process_inherited_event(
                    line, current_date_str, current_date,
                    mois, annee, lieu_ref_list, ville_ref_list,
                    events, seen_signatures
                )

        return events

    def _process_inherited_event(
        self,
        event_text: str,
        date_str: str,
        event_date: Optional[date],
        mois: int,
        annee: int,
        lieu_ref_list: list,
        ville_ref_list: list,
        events: list,
        seen_signatures: set
    ):
        """Traite un événement pour le format inline_inherited."""
        # Parser l'événement
        parsed_events = parse_event_line_v2(
            event_text,
            mois,
            annee,
            lieu_ref_list,
            ville_ref_list
        )

        for parsed in parsed_events:
            event = self._dict_to_parsed_event(parsed, date_str)
            if event:
                if event_date and not parsed.get('date_evenement'):
                    event.date_evenement = event_date
                signature = self._event_signature(event)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    events.append(event)

    def _dict_to_parsed_event(self, parsed: dict, date_str: Optional[str]) -> Optional[ParsedEvent]:
        """Convertit un dict de parse_event_line_v2 en ParsedEvent."""
        if not parsed:
            return None

        event = ParsedEvent(raw_text=parsed.get('raw_text', ''))

        # Date - priorité à la date extraite par parse_event_line_v2
        # (qui peut avoir splitté sur des dates mid-text comme "Lu 02 & Ma 03")
        if parsed.get('date_evenement'):
            event.date_evenement = parsed['date_evenement']
            event.date_str = parsed.get('date_str')
        elif date_str:
            event.date_str = date_str
            event.date_evenement = self._parse_date(date_str)

        # Lieu
        event.lieu_raw = parsed.get('lieu_raw')
        event.ville_raw = parsed.get('ville_raw')

        # Heure/Prix
        event.heure = parsed.get('heure')
        event.tarif_raw = parsed.get('tarif_raw')
        event.prix_min = parsed.get('prix_min')
        event.prix_max = parsed.get('prix_max')
        event.gratuit = parsed.get('gratuit', False)

        # Artistes - convertir les dicts en ArtisteInfo
        artistes_raw = parsed.get('artistes', [])
        event.artistes = []
        for a in artistes_raw:
            if isinstance(a, dict):
                event.artistes.append(ArtisteInfo(
                    nom=a.get('nom', ''),
                    genre=a.get('genre') or a.get('style'),
                    spectacle=a.get('spectacle')
                ))
            elif isinstance(a, ArtisteInfo):
                event.artistes.append(a)

        # Spectacles - garder le format dict avec nom et style
        spectacles_raw = parsed.get('spectacles', [])
        event.spectacles = []
        for s in spectacles_raw:
            if isinstance(s, dict):
                # Garder le dict complet avec nom et style
                event.spectacles.append(s)
            else:
                # String simple -> convertir en dict
                event.spectacles.append({'nom': s, 'style': None})

        # Nom d'événement
        event.nom = parsed.get('nom')

        # Genre de l'événement
        event.genre_evenement = parsed.get('genre_evenement')

        # Type et confidence
        event.type_evenement = self._deduce_type(event)
        event.confidence = self._calculate_confidence(event)

        # Bonus confidence si lieu trouvé dans référentiel
        if parsed.get('lieu_ref_id'):
            event.confidence = min(1.0, event.confidence + 0.1)

        return event


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

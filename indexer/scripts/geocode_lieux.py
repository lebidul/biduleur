"""
Script de géocodage des lieux du référentiel.

Utilise Nominatim (OpenStreetMap) pour récupérer les coordonnées géographiques
et les adresses postales.

Les résultats sont sauvegardés dans la base ET dans corpus/lieu.csv.

Usage:
    python scripts/geocode_lieux.py [--limit N] [--dry-run] [--force] [--city-only]
    python scripts/geocode_lieux.py --reverse [--limit N] [--dry-run]

Options:
    --limit N    Limite le nombre de lieux à traiter (pour tests)
    --dry-run    Affiche les résultats sans sauvegarder
    --force      Regéocode même les lieux qui ont déjà des coordonnées
    --city-only  Ne regéocode que les lieux avec précision 'city' (à améliorer)
    --reverse    Mode reverse: récupère les adresses à partir des coordonnées
"""

import argparse
import csv
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import urllib.request
import urllib.parse
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Chemins
DB_PATH = Path(__file__).parent.parent / "database" / "bidul_archives.db"
LIEU_CSV_PATH = Path(__file__).parent.parent / "corpus" / "lieu.csv"

# Configuration Nominatim
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "BiduLIndexer/1.0 (https://github.com/lebidul/biduleur)"
RATE_LIMIT_SECONDS = 1.1  # Nominatim demande 1 requête/seconde max


@dataclass
class GeoResult:
    """Résultat de géocodage."""
    latitude: float
    longitude: float
    source: str = "nominatim"
    precision: str = "exact"
    display_name: Optional[str] = None
    osm_name: Optional[str] = None  # Nom du lieu tel que retourné par OSM
    detected_city: Optional[str] = None  # Ville détectée par le géocodage
    detected_postcode: Optional[str] = None  # Code postal détecté


# Départements autorisés pour le fallback sans ville (Sarthe + voisins)
ALLOWED_DEPARTMENTS = {'72', '49', '53', '61', '41'}


@dataclass
class AddressResult:
    """Résultat de reverse geocoding."""
    house_number: Optional[str] = None
    road: Optional[str] = None
    postcode: Optional[str] = None
    city: Optional[str] = None
    display_name: Optional[str] = None


def geocode_nominatim(lieu: str, ville: str) -> Optional[GeoResult]:
    """
    Géocode un lieu via Nominatim.

    Stratégie de recherche:
    1. Cherche "lieu, ville, France"
    2. Si pas trouvé, cherche "lieu, ville, Sarthe, France"
    3. Si pas trouvé, essaie avec des variantes orthographiques
    4. Si pas trouvé, essaie avec des noms simplifiés
    5. Si pas trouvé, essaie une recherche partielle (premiers mots significatifs)
    6. Si pas trouvé, cherche juste "ville, Sarthe, France" (précision: city)
    """
    # Normaliser la ville
    ville_norm = ville.strip() if ville else "Le Mans"

    # Requêtes principales
    queries = [
        f"{lieu}, {ville_norm}, France",
        f"{lieu}, {ville_norm}, Sarthe, France",
    ]

    for query in queries:
        result = _nominatim_search(query)
        if result:
            return result

    # Essai avec des variantes orthographiques courantes
    for variant in _generate_spelling_variants(lieu):
        if variant != lieu:
            for query in [
                f"{variant}, {ville_norm}, France",
                f"{variant}, {ville_norm}, Sarthe, France",
            ]:
                result = _nominatim_search(query)
                if result:
                    result.precision = "approximate"
                    logger.debug(f"  Trouvé avec variante: {variant}")
                    return result

    # Essai avec des variantes du nom du lieu (simplification)
    lieu_clean = _simplify_lieu_name(lieu)
    if lieu_clean != lieu:
        for query in [
            f"{lieu_clean}, {ville_norm}, France",
            f"{lieu_clean}, {ville_norm}, Sarthe, France",
        ]:
            result = _nominatim_search(query)
            if result:
                result.precision = "approximate"
                return result

    # Essai avec recherche partielle (premiers mots significatifs)
    partial = _extract_search_keywords(lieu)
    if partial and partial != lieu and partial != lieu_clean:
        for query in [
            f"{partial} {ville_norm}",
            f"{partial}, {ville_norm}, France",
        ]:
            result = _nominatim_search(query)
            if result:
                result.precision = "approximate"
                logger.debug(f"  Trouvé avec recherche partielle: {partial}")
                return result

    # Fallback spécial pour Le Mans: recherche sans ville
    # Car "Le Mans" est souvent un fallback pour les lieux sans ville connue
    if ville_norm == "Le Mans":
        result = _search_without_city(lieu)
        if result:
            return result

    # Fallback final: coordonnées de la ville
    city_query = f"{ville_norm}, Sarthe, France"
    result = _nominatim_search(city_query)
    if result:
        result.precision = "city"
        return result

    return None


def _search_without_city(lieu: str) -> Optional[GeoResult]:
    """
    Recherche un lieu sans spécifier de ville.

    Utilisé quand la ville "Le Mans" était un fallback et que le lieu
    pourrait être dans une autre ville de la Sarthe ou départements voisins.

    Returns:
        GeoResult avec detected_city renseigné si trouvé dans un département autorisé
    """
    # Recherche large dans la région
    queries = [
        f"{lieu}, Sarthe, France",
        f"{lieu}, Pays de la Loire, France",
        f"{lieu}, France",
    ]

    for query in queries:
        result = _nominatim_search(query, with_address_details=True)
        if result and result.detected_postcode:
            # Vérifier que le département est autorisé
            dept = result.detected_postcode[:2]
            if dept in ALLOWED_DEPARTMENTS:
                logger.info(f"  -> Trouvé sans ville: {result.detected_city} ({dept})")
                result.precision = "exact"
                return result

    # Essai avec variantes orthographiques
    for variant in _generate_spelling_variants(lieu):
        if variant != lieu:
            for query in [
                f"{variant}, Sarthe, France",
                f"{variant}, France",
            ]:
                result = _nominatim_search(query, with_address_details=True)
                if result and result.detected_postcode:
                    dept = result.detected_postcode[:2]
                    if dept in ALLOWED_DEPARTMENTS:
                        logger.info(f"  -> Trouvé avec variante sans ville: {result.detected_city} ({dept})")
                        result.precision = "approximate"
                        return result

    return None


def _generate_spelling_variants(lieu: str) -> list[str]:
    """
    Génère des variantes orthographiques courantes pour un nom de lieu.

    Gère les erreurs fréquentes comme:
    - Basserie/Brasserie
    - Tirets manquants
    - Accents
    - Acronymes (MPT, MJC, etc.)
    """
    import re
    variants = [lieu]

    # Expansions d'acronymes courants
    acronym_expansions = [
        (r'\bMPT\b', 'Maison Pour Tous'),       # MPT -> Maison Pour Tous
        (r'\bMJC\.?\s*', 'M.J.C. '),            # MJC ou MJC. -> M.J.C.
        (r'\bCSC\b', 'Centre Social et Culturel'),  # CSC -> Centre Social et Culturel
        (r'\bMLC\b', 'Maison des Loisirs et de la Culture'),
        (r'\bMQ\b', 'Maison de Quartier'),
    ]

    for pattern, replacement in acronym_expansions:
        expanded = re.sub(pattern, replacement, lieu, flags=re.IGNORECASE).strip()
        if expanded != lieu and expanded not in variants:
            variants.append(expanded)

    # Corrections courantes de doubles lettres et accents
    corrections = [
        (r'\b[Bb]asserie\b', 'Brasserie'),  # Basserie -> Brasserie
        (r'\b[Bb]raserie\b', 'Brasserie'),   # Braserie -> Brasserie
        (r'\b[Cc]affé\b', 'Café'),           # Caffé -> Café
        (r'\b[Cc]afe\b', 'Café'),            # Cafe -> Café
        (r'\b[Tt]héatre\b', 'Théâtre'),      # Théatre -> Théâtre
        (r'\b[Tt]heatre\b', 'Théâtre'),      # Theatre -> Théâtre
    ]

    for pattern, replacement in corrections:
        corrected = re.sub(pattern, replacement, lieu)
        if corrected != lieu and corrected not in variants:
            variants.append(corrected)

    # Ajouter des tirets entre les mots pour les noms composés
    # Ex: "Septante Deux" -> "Septante-Deux"
    words = lieu.split()
    if len(words) >= 2:
        # Essayer avec tirets
        with_hyphens = '-'.join(words)
        if with_hyphens not in variants:
            variants.append(with_hyphens)

        # Essayer avec tirets partiels (dernier mot)
        partial_hyphen = ' '.join(words[:-1]) + '-' + words[-1]
        if partial_hyphen not in variants:
            variants.append(partial_hyphen)

    return variants


def _extract_search_keywords(lieu: str) -> Optional[str]:
    """
    Extrait les mots-clés significatifs pour une recherche partielle.

    Ex: "Basserie Septante Deux" -> "Brasserie Septante" (premiers mots significatifs corrigés)
    """
    import re

    # Mots à ignorer (articles, prépositions)
    stopwords = {'le', 'la', 'les', 'l', 'de', 'du', 'des', 'au', 'aux', 'et', 'ou'}

    # Séparer en mots
    words = re.findall(r'\w+', lieu.lower())

    # Garder les mots significatifs
    keywords = [w for w in words if w not in stopwords and len(w) > 2]

    if not keywords:
        return None

    # Prendre les 2 premiers mots significatifs
    keywords = keywords[:2]

    # Reconstruire avec casse originale approximative
    result_words = []
    for kw in keywords:
        # Chercher le mot original dans lieu
        for word in lieu.split():
            if word.lower().startswith(kw[:3]):
                result_words.append(word)
                break
        else:
            result_words.append(kw.capitalize())

    result = ' '.join(result_words)

    # Appliquer corrections orthographiques au résultat
    variants = _generate_spelling_variants(result)
    if len(variants) > 1:
        return variants[1]  # Retourner la première variante corrigée

    return result


def _simplify_lieu_name(lieu: str) -> str:
    """Simplifie le nom d'un lieu pour améliorer le géocodage."""
    import re

    # Supprime les préfixes courants
    prefixes = [
        r"^(Bar|Café|Restaurant|Pub|Brasserie|Salle|Le|La|L'|Les|Au|Aux)\s+",
        r"^(Espace|Centre|Maison|Hôtel|Auberge|Théâtre|Cinéma)\s+",
    ]
    result = lieu
    for prefix in prefixes:
        result = re.sub(prefix, "", result, flags=re.IGNORECASE)

    # Supprime les suffixes
    suffixes = [
        r"\s+(Le Mans|Allonnes|La Flèche)$",
    ]
    for suffix in suffixes:
        result = re.sub(suffix, "", result, flags=re.IGNORECASE)

    return result.strip()


def _nominatim_search(query: str, with_address_details: bool = False) -> Optional[GeoResult]:
    """Effectue une requête Nominatim.

    Args:
        query: La requête de recherche
        with_address_details: Si True, récupère les détails d'adresse (ville, code postal)
    """
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "fr"
    }
    if with_address_details:
        params["addressdetails"] = 1

    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        if data and len(data) > 0:
            result = data[0]
            # Extraire le nom OSM (premier élément du display_name, ou name si disponible)
            osm_name = result.get('name')
            if not osm_name and result.get('display_name'):
                # Le display_name est de la forme "Nom, Rue, Ville, ..."
                osm_name = result['display_name'].split(',')[0].strip()

            # Extraire ville et code postal si demandé
            detected_city = None
            detected_postcode = None
            if with_address_details and 'address' in result:
                addr = result['address']
                detected_city = (addr.get('city') or addr.get('town') or
                                addr.get('village') or addr.get('municipality'))
                detected_postcode = addr.get('postcode')

            return GeoResult(
                latitude=float(result['lat']),
                longitude=float(result['lon']),
                source="nominatim",
                precision="exact",
                display_name=result.get('display_name'),
                osm_name=osm_name,
                detected_city=detected_city,
                detected_postcode=detected_postcode
            )
    except Exception as e:
        logger.warning(f"Erreur Nominatim pour '{query}': {e}")

    return None


def reverse_geocode_nominatim(lat: float, lon: float) -> Optional[AddressResult]:
    """
    Reverse geocode: récupère l'adresse à partir des coordonnées.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        AddressResult avec les composants de l'adresse, ou None si échec
    """
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1
    }

    url = f"{NOMINATIM_REVERSE_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        if data and 'address' in data:
            addr = data['address']
            return AddressResult(
                house_number=addr.get('house_number'),
                road=addr.get('road'),
                postcode=addr.get('postcode'),
                city=addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality'),
                display_name=data.get('display_name')
            )
    except Exception as e:
        logger.warning(f"Erreur reverse Nominatim pour ({lat}, {lon}): {e}")

    return None


def load_lieux_for_reverse(conn: sqlite3.Connection) -> list[tuple]:
    """Charge les lieux avec coordonnées mais sans adresse."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, nom, ville, latitude, longitude
        FROM lieu_ref
        WHERE actif = 1
          AND latitude IS NOT NULL
          AND (adresse_voie IS NULL OR adresse_voie = '')
        ORDER BY ville, nom
    ''')
    return cursor.fetchall()


def update_lieu_address(
    conn: sqlite3.Connection,
    lieu_id: int,
    result: AddressResult,
    dry_run: bool = False
) -> None:
    """Met à jour l'adresse d'un lieu dans la base."""
    if dry_run:
        return

    cursor = conn.cursor()
    cursor.execute('''
        UPDATE lieu_ref
        SET adresse_numero = ?, adresse_voie = ?, code_postal = ?
        WHERE id = ?
    ''', (result.house_number, result.road, result.postcode, lieu_id))


def load_lieux_to_geocode(conn: sqlite3.Connection, force: bool = False, city_only: bool = False) -> list[tuple]:
    """Charge les lieux à géocoder.

    Args:
        conn: Connexion à la base
        force: Si True, regéocode tous les lieux actifs
        city_only: Si True, ne regéocode que les lieux avec précision 'city'
    """
    cursor = conn.cursor()

    if city_only:
        # Seulement les lieux avec précision 'city' (à améliorer)
        cursor.execute('''
            SELECT id, nom, ville
            FROM lieu_ref
            WHERE actif = 1 AND geo_precision = 'city'
            ORDER BY ville, nom
        ''')
    elif force:
        # Tous les lieux actifs
        cursor.execute('''
            SELECT id, nom, ville
            FROM lieu_ref
            WHERE actif = 1
            ORDER BY ville, nom
        ''')
    else:
        # Seulement les lieux sans coordonnées
        cursor.execute('''
            SELECT id, nom, ville
            FROM lieu_ref
            WHERE actif = 1 AND latitude IS NULL
            ORDER BY ville, nom
        ''')

    return cursor.fetchall()


def update_lieu_coordinates(
    conn: sqlite3.Connection,
    lieu_id: int,
    result: GeoResult,
    dry_run: bool = False,
    update_city: bool = False
) -> Optional[str]:
    """Met à jour les coordonnées d'un lieu dans la base.

    Args:
        conn: Connexion à la base
        lieu_id: ID du lieu
        result: Résultat du géocodage
        dry_run: Si True, ne pas sauvegarder
        update_city: Si True et detected_city présent, met à jour la ville

    Returns:
        La nouvelle ville si elle a été corrigée, None sinon
    """
    if dry_run:
        return result.detected_city if update_city and result.detected_city else None

    cursor = conn.cursor()

    # Mise à jour avec ou sans correction de ville
    if update_city and result.detected_city:
        cursor.execute('''
            UPDATE lieu_ref
            SET latitude = ?, longitude = ?, geo_source = ?, geo_precision = ?, nom_osm = ?, ville = ?
            WHERE id = ?
        ''', (result.latitude, result.longitude, result.source, result.precision,
              result.osm_name, result.detected_city, lieu_id))
        return result.detected_city
    else:
        cursor.execute('''
            UPDATE lieu_ref
            SET latitude = ?, longitude = ?, geo_source = ?, geo_precision = ?, nom_osm = ?
            WHERE id = ?
        ''', (result.latitude, result.longitude, result.source, result.precision, result.osm_name, lieu_id))
        return None


def export_to_lieu_csv(conn: sqlite3.Connection) -> None:
    """Met à jour corpus/lieu.csv avec les coordonnées géographiques."""
    # Lire le fichier existant pour préserver nom_normalise et adresse
    existing = {}
    if LIEU_CSV_PATH.exists():
        with open(LIEU_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row['nom'], row.get('ville', 'Le Mans'))
                existing[key] = {
                    'nom_normalise': row.get('nom_normalise', ''),
                    'adresse_numero': row.get('adresse_numero', ''),
                    'adresse_voie': row.get('adresse_voie', ''),
                    'code_postal': row.get('code_postal', ''),
                    'nom_osm': row.get('nom_osm', ''),
                }

    # Récupérer les données depuis la base
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nom, ville, adresse_numero, adresse_voie, code_postal,
               latitude, longitude, geo_source, geo_precision, nom_osm
        FROM lieu_ref
        WHERE actif = 1
        ORDER BY ville, nom
    ''')

    rows = cursor.fetchall()

    # Écrire le fichier avec toutes les colonnes
    fieldnames = ['nom', 'ville', 'nom_normalise', 'adresse_numero', 'adresse_voie', 'code_postal',
                  'latitude', 'longitude', 'geo_source', 'geo_precision', 'nom_osm']
    with open(LIEU_CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for nom, ville, addr_num, addr_voie, cp, lat, lon, source, precision, nom_osm in rows:
            key = (nom, ville or 'Le Mans')
            ex = existing.get(key, {})
            writer.writerow({
                'nom': nom,
                'ville': ville or 'Le Mans',
                'nom_normalise': ex.get('nom_normalise', ''),
                'adresse_numero': addr_num or ex.get('adresse_numero', ''),
                'adresse_voie': addr_voie or ex.get('adresse_voie', ''),
                'code_postal': cp or ex.get('code_postal', ''),
                'latitude': lat if lat is not None else '',
                'longitude': lon if lon is not None else '',
                'geo_source': source or '',
                'geo_precision': precision or '',
                'nom_osm': nom_osm or ''
            })

    logger.info(f"Mis à jour {len(rows)} lieux dans {LIEU_CSV_PATH}")


def run_geocode(conn: sqlite3.Connection, args) -> None:
    """Mode géocodage: coordonnées à partir des noms de lieux."""
    lieux = load_lieux_to_geocode(conn, force=args.force, city_only=args.city_only)

    if args.limit:
        lieux = lieux[:args.limit]

    logger.info(f"Lieux à géocoder: {len(lieux)}")

    if args.dry_run:
        logger.info("[MODE DRY-RUN - aucune modification]")

    stats = {'success': 0, 'city': 0, 'failed': 0, 'city_corrected': 0}
    city_corrections = []  # Liste des corrections de ville

    for i, (lieu_id, nom, ville) in enumerate(lieux, 1):
        logger.info(f"[{i}/{len(lieux)}] {nom}, {ville}")

        result = geocode_nominatim(nom, ville)

        if result:
            if result.precision == "city":
                logger.warning(f"  -> Coordonnées de la ville uniquement")
                stats['city'] += 1
            else:
                logger.debug(f"  -> {result.latitude}, {result.longitude}")
                stats['success'] += 1

            # Vérifier si la ville doit être corrigée
            # (lieu trouvé sans ville alors que ville était "Le Mans")
            should_update_city = (
                ville == "Le Mans" and
                result.detected_city and
                result.detected_city != "Le Mans" and
                result.precision != "city"
            )

            new_city = update_lieu_coordinates(
                conn, lieu_id, result,
                dry_run=args.dry_run,
                update_city=should_update_city
            )

            if new_city:
                stats['city_corrected'] += 1
                city_corrections.append((nom, "Le Mans", new_city))
                logger.info(f"  -> Ville corrigée: Le Mans -> {new_city}")
        else:
            logger.warning(f"  -> Non trouvé")
            stats['failed'] += 1

        # Rate limiting
        time.sleep(RATE_LIMIT_SECONDS)

    if not args.dry_run:
        conn.commit()
        export_to_lieu_csv(conn)

    # Résumé
    print(f"\n=== RÉSUMÉ GÉOCODAGE ===")
    print(f"  Exact: {stats['success']}")
    print(f"  Ville: {stats['city']}")
    print(f"  Échec: {stats['failed']}")
    if stats['city_corrected'] > 0:
        print(f"  Villes corrigées: {stats['city_corrected']}")
        print(f"\n=== CORRECTIONS DE VILLE ===")
        for nom, old_city, new_city in city_corrections:
            print(f"  {nom}: {old_city} -> {new_city}")


def run_reverse(conn: sqlite3.Connection, args) -> None:
    """Mode reverse: adresses à partir des coordonnées."""
    lieux = load_lieux_for_reverse(conn)

    if args.limit:
        lieux = lieux[:args.limit]

    logger.info(f"Lieux à reverse-géocoder: {len(lieux)}")

    if args.dry_run:
        logger.info("[MODE DRY-RUN - aucune modification]")

    stats = {'success': 0, 'partial': 0, 'failed': 0}

    for i, (lieu_id, nom, ville, lat, lon) in enumerate(lieux, 1):
        logger.info(f"[{i}/{len(lieux)}] {nom} ({ville}) @ {lat}, {lon}")

        result = reverse_geocode_nominatim(lat, lon)

        if result:
            if result.road:
                addr_str = f"{result.house_number or ''} {result.road}".strip()
                if result.postcode:
                    addr_str += f", {result.postcode}"
                logger.info(f"  -> {addr_str}")
                stats['success'] += 1
            else:
                logger.warning(f"  -> Adresse partielle: {result.display_name[:60]}...")
                stats['partial'] += 1

            update_lieu_address(conn, lieu_id, result, dry_run=args.dry_run)
        else:
            logger.warning(f"  -> Non trouvé")
            stats['failed'] += 1

        # Rate limiting
        time.sleep(RATE_LIMIT_SECONDS)

    if not args.dry_run:
        conn.commit()
        export_to_lieu_csv(conn)

    # Résumé
    print(f"\n=== RÉSUMÉ REVERSE GEOCODING ===")
    print(f"  Complet: {stats['success']}")
    print(f"  Partiel: {stats['partial']}")
    print(f"  Échec: {stats['failed']}")


def main():
    parser = argparse.ArgumentParser(description="Géocode les lieux du référentiel")
    parser.add_argument('--limit', type=int, help="Limite le nombre de lieux")
    parser.add_argument('--dry-run', action='store_true', help="Mode simulation")
    parser.add_argument('--force', action='store_true', help="Regéocode tous les lieux")
    parser.add_argument('--city-only', action='store_true',
                        help="Ne regéocode que les lieux avec précision 'city'")
    parser.add_argument('--reverse', action='store_true', help="Mode reverse: récupère les adresses")
    parser.add_argument('-v', '--verbose', action='store_true', help="Affichage détaillé")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    conn = sqlite3.connect(DB_PATH)

    try:
        if args.reverse:
            run_reverse(conn, args)
        else:
            run_geocode(conn, args)
    finally:
        conn.close()


if __name__ == '__main__':
    main()

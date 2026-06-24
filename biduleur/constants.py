DATE = 'DATE'
DATE_FIN = 'DATE FIN'
BIDUL_COL = 'BIDUL'
GENRE_EVT = 'GENRE'
HORAIRE = 'HEURE'
FESTIVAL = 'FESTOCHE\nEVENEMENT '
STYLE_FESTIVAL = 'STYLE \nFESTOCHE / EVENEMENT '
VILLE = 'VILLE'
LIEU = 'LIEU'
PRIX = 'PRIX'
GENRE_EVT_SV = 'sv'
GENRE_EVT_CONCERT = 'c'
GENRE_EVT_IMAGE = 'img'
GENRE1 = 'GENRE 1'
SPECTACLE1 = 'NOM SPECTACLE 1 ( SV )'
ARTISTE1 = 'COMPAGNIE 1 ( SV ) ou\nGROUPE 1 / ARTISTE 1 ( C )'
STYLE1 = 'STYLE \nSPECTACLE 1 (SV) / CONCERT 1 (C)'
GENRE2 = 'GENRE 2'
SPECTACLE2 = 'NOM SPECTACLE 2 ( SV )'
ARTISTE2 = 'COMPAGNIE 2 ( SV ) ou\nGROUPE 2 / ARTISTE 2 ( C )'
STYLE2 = 'STYLE \nSPECTACLE 2 ( SV ) / CONCERT 2 ( C )'
GENRE3 = 'GENRE 3'
SPECTACLE3 = 'NOM SPECTACLE 3 ( SV )'
ARTISTE3 = 'COMPAGNIE 3 ( SV ) ou\nGROUPE 3 / ARTISTE 3 ( C )'
STYLE3 = 'STYLE \nSPECTACLE 3 ( SV ) / CONCERT 3 ( C )'
GENRE4 = 'GENRE 4'
SPECTACLE4 = 'NOM SPECTACLE 4 ( SV )'
ARTISTE4 = 'COMPAGNIE 4 ( SV ) ou\nGROUPE 4 / ARTISTE 4 ( C )'
STYLE4 = 'STYLE \nSPECTACLE 4 ( SV ) / CONCERT 4 ( C )'
LIEN1 = 'LIEN1'
LIEN2 = 'LIEN2'
LIEN3 = 'LIEN3'
LIEN4 = 'LIEN4'


# --- Colonnes spectacle dynamiques ---
import re
from typing import Dict

# Préfixes de regex pour détecter les colonnes spectacle par numéro
_GENRE_PATTERN = re.compile(r'^GENRE\s+(\d+)$', re.IGNORECASE)
_SPECTACLE_PATTERN = re.compile(r'^NOM\s+SPECTACLE\s+(\d+)', re.IGNORECASE)
_ARTISTE_PATTERN = re.compile(r'^COMPAGNIE\s+(\d+)', re.IGNORECASE)
_STYLE_PATTERN = re.compile(r'^STYLE\s+.*SPECTACLE\s+(\d+)', re.IGNORECASE | re.DOTALL)


def detect_spectacle_columns(columns):
    """
    Détecte dynamiquement les sets de colonnes spectacle (GENRE N, NOM SPECTACLE N,
    COMPAGNIE N, STYLE N) présents dans la liste de colonnes du fichier.

    Returns:
        list[dict]: Liste triée par numéro, chaque dict contient les clés
                    'genre', 'spectacle', 'artiste', 'style' mappées aux noms
                    réels des colonnes du fichier.
    """
    # Collecter les numéros et noms de colonnes détectés
    genre_cols = {}
    spectacle_cols = {}
    artiste_cols = {}
    style_cols = {}

    for col in columns:
        col_str = str(col)
        m = _GENRE_PATTERN.match(col_str)
        if m:
            genre_cols[int(m.group(1))] = col_str
            continue
        m = _SPECTACLE_PATTERN.match(col_str)
        if m:
            spectacle_cols[int(m.group(1))] = col_str
            continue
        m = _ARTISTE_PATTERN.match(col_str)
        if m:
            artiste_cols[int(m.group(1))] = col_str
            continue
        m = _STYLE_PATTERN.match(col_str)
        if m:
            style_cols[int(m.group(1))] = col_str
            continue

    # Construire les sets complets (un set = les 4 colonnes pour un numéro donné)
    all_nums = sorted(set(genre_cols.keys()) | set(spectacle_cols.keys())
                      | set(artiste_cols.keys()) | set(style_cols.keys()))

    result = []
    for n in all_nums:
        if n in genre_cols:
            result.append({
                'num': n,
                'genre': genre_cols.get(n),
                'spectacle': spectacle_cols.get(n),
                'artiste': artiste_cols.get(n),
                'style': style_cols.get(n),
            })

    return result

# OUTPUT_FOLDER_NAME = './outputs/'
# P_MD_OPEN_DATE = '<p class="date">'
# P_MD_CLOSE_DATE = '</p>'
# P_MD_OPEN_DATE_AGENDA = '<p class="date-agenda">'
# P_MD_CLOSE = '</p>'
# P_MD_OPEN = '<p>'
# P_MD_POST_OPEN = '<div class="post">'


COLONNE_INFO = "Coups de coeur et en bref"
COLONNE_FESTIVALS = "Festivals"  # marqueur de date : ligne routée vers la section FESTIVALS (mode été)
OUTPUT_FOLDER_NAME = './outputs/'
LINE_HEIGHT = "0.25"
# P_MD_OPEN = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT}">"""
# P_MD_OPEN = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT}">&ensp;&#9643 """
P_MD_OPEN = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT}">❑ """
# P_MD_OPEN_DATE = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT};background-color:grey">"""
P_MD_OPEN_DATE = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT}">"""
P_MD_OPEN_DATE_AGENDA = f"""<p style="font-family: Arial Narrow;line-height:{LINE_HEIGHT};color:blue">"""
P_MD_CLOSE = f"""</p>"""
P_MD_CLOSE_DATE = f"""</spanp></p>"""
P_MD_POST_OPEN = f"""<p style="font-family: Lucida Console">"""

# Préfixe placeholder pour les sous-en-têtes festival (rendus séparément)
SUBFEST_PREFIX = "{{SUBFEST}}"


# ----------------------------------------------------------------------
# Dictionnaire des noms propres connus (villes + pays)
# Clé = forme lowercase ; valeur = casse correcte attendue dans le rendu.
# Le dictionnaire est utilisé par _smart_lower pour rétablir la casse
# correcte (y compris les majuscules INTERNES, ex. "Le Mans", "New York").
# Trié par longueur décroissante au moment de la compilation regex pour
# matcher les noms longs avant les courts (ex. "Le Mans" avant "Mans").
# ----------------------------------------------------------------------
PROPER_NOUNS_MAP: Dict[str, str] = {
    # ============ Sarthe & Pays de la Loire (région locale) ============
    "sablé-sur-sarthe": "Sablé-sur-Sarthe",
    "fresnay-sur-sarthe": "Fresnay-sur-Sarthe",
    "saint-mars-la-brière": "Saint-Mars-la-Brière",
    "yvré-l'évêque": "Yvré-l'Évêque",
    "parigné-l'évêque": "Parigné-l'Évêque",
    "sargé-lès-le-mans": "Sargé-lès-le-Mans",
    "la chapelle-saint-aubin": "La Chapelle-Saint-Aubin",
    "la ferté-bernard": "La Ferté-Bernard",
    "saint-rémy-de-sillé": "Saint-Rémy-de-Sillé",
    "sillé-le-guillaume": "Sillé-le-Guillaume",
    "saint-calais": "Saint-Calais",
    "ferce-sur-sarthe": "Fercé-sur-Sarthe",
    "fercé-sur-sarthe": "Fercé-sur-Sarthe",
    "montfort-le-gesnois": "Montfort-le-Gesnois",
    "neuville-sur-sarthe": "Neuville-sur-Sarthe",
    "moncé-en-belin": "Moncé-en-Belin",
    "la suze-sur-sarthe": "La Suze-sur-Sarthe",
    "la bazoge": "La Bazoge",
    "le lude": "Le Lude",
    "mamers": "Mamers",
    "allonnes": "Allonnes",
    "changé": "Changé",
    "coulaines": "Coulaines",
    "arnage": "Arnage",
    "bouloire": "Bouloire",
    "brûlon": "Brûlon",
    "piacé": "Piacé",
    "lombron": "Lombron",
    "fillé": "Fillé",
    "teloché": "Teloché",
    "telochée": "Telochée",
    "jupilles": "Jupilles",
    "ecommoy": "Ecommoy",
    "écommoy": "Écommoy",
    "vibraye": "Vibraye",
    "la flèche": "La Flèche",

    # ============ Préfectures de France métropolitaine ============
    "agen": "Agen",
    "ajaccio": "Ajaccio",
    "albi": "Albi",
    "alençon": "Alençon",
    "amiens": "Amiens",
    "angers": "Angers",
    "angoulême": "Angoulême",
    "annecy": "Annecy",
    "arras": "Arras",
    "auch": "Auch",
    "aurillac": "Aurillac",
    "auxerre": "Auxerre",
    "avignon": "Avignon",
    "bar-le-duc": "Bar-le-Duc",
    "bastia": "Bastia",
    "beauvais": "Beauvais",
    "belfort": "Belfort",
    "besançon": "Besançon",
    "blois": "Blois",
    "bobigny": "Bobigny",
    "bordeaux": "Bordeaux",
    "bourg-en-bresse": "Bourg-en-Bresse",
    "bourges": "Bourges",
    "caen": "Caen",
    "cahors": "Cahors",
    "carcassonne": "Carcassonne",
    "chambéry": "Chambéry",
    "charleville-mézières": "Charleville-Mézières",
    "chartres": "Chartres",
    "châlons-en-champagne": "Châlons-en-Champagne",
    "châteauroux": "Châteauroux",
    "chaumont": "Chaumont",
    "clermont-ferrand": "Clermont-Ferrand",
    "colmar": "Colmar",
    "créteil": "Créteil",
    "digne-les-bains": "Digne-les-Bains",
    "dijon": "Dijon",
    "épinal": "Épinal",
    "évreux": "Évreux",
    "évry-courcouronnes": "Évry-Courcouronnes",
    "foix": "Foix",
    "gap": "Gap",
    "grenoble": "Grenoble",
    "guéret": "Guéret",
    "la roche-sur-yon": "La Roche-sur-Yon",
    "la rochelle": "La Rochelle",
    "laon": "Laon",
    "laval": "Laval",
    "le mans": "Le Mans",
    "lorient": "Lorient",
    "le puy-en-velay": "Le Puy-en-Velay",
    "lille": "Lille",
    "limoges": "Limoges",
    "lons-le-saunier": "Lons-le-Saunier",
    "lyon": "Lyon",
    "mâcon": "Mâcon",
    "marseille": "Marseille",
    "melun": "Melun",
    "mende": "Mende",
    "metz": "Metz",
    "montauban": "Montauban",
    "mont-de-marsan": "Mont-de-Marsan",
    "montpellier": "Montpellier",
    "moulins": "Moulins",
    "nancy": "Nancy",
    "nanterre": "Nanterre",
    "nantes": "Nantes",
    "nevers": "Nevers",
    "nice": "Nice",
    "nîmes": "Nîmes",
    "niort": "Niort",
    "orléans": "Orléans",
    "paris": "Paris",
    "pau": "Pau",
    "périgueux": "Périgueux",
    "perpignan": "Perpignan",
    "poitiers": "Poitiers",
    "pontoise": "Pontoise",
    "privas": "Privas",
    "quimper": "Quimper",
    "reims": "Reims",
    "rennes": "Rennes",
    "rodez": "Rodez",
    "rouen": "Rouen",
    "saint-brieuc": "Saint-Brieuc",
    "saint-étienne": "Saint-Étienne",
    "saint-lô": "Saint-Lô",
    "strasbourg": "Strasbourg",
    "tarbes": "Tarbes",
    "toulon": "Toulon",
    "toulouse": "Toulouse",
    "tours": "Tours",
    "troyes": "Troyes",
    "tulle": "Tulle",
    "valence": "Valence",
    "vannes": "Vannes",
    "versailles": "Versailles",
    "vesoul": "Vesoul",

    # ============ Préfectures DOM-TOM ============
    "basse-terre": "Basse-Terre",
    "fort-de-france": "Fort-de-France",
    "cayenne": "Cayenne",
    "saint-denis": "Saint-Denis",
    "mamoudzou": "Mamoudzou",
    "saint-pierre": "Saint-Pierre",
    "papeete": "Papeete",
    "nouméa": "Nouméa",

    # ============ Autres villes françaises notables ============
    "le havre": "Le Havre",
    "brest": "Brest",
    "aix-en-provence": "Aix-en-Provence",
    "saint-nazaire": "Saint-Nazaire",
    "boulogne-billancourt": "Boulogne-Billancourt",
    "saint-malo": "Saint-Malo",
    "saint-tropez": "Saint-Tropez",
    "biarritz": "Biarritz",
    "deauville": "Deauville",
    "honfleur": "Honfleur",
    "cannes": "Cannes",
    "monaco-ville": "Monaco-Ville",

    "gascogne": "Gascogne",

    # ============ Capitales européennes (FR + EN/locale) ============
    "tirana": "Tirana",  # Albanie
    "andorre-la-vieille": "Andorre-la-Vieille",  # Andorre
    "andorra la vella": "Andorra la Vella",
    "vienne": "Vienne",  # Autriche / homonyme avec préfecture FR
    "vienna": "Vienna",
    "wien": "Wien",
    "minsk": "Minsk",  # Biélorussie
    "bruxelles": "Bruxelles",  # Belgique
    "brussels": "Brussels",
    "sarajevo": "Sarajevo",  # Bosnie
    "sofia": "Sofia",  # Bulgarie
    "nicosie": "Nicosie",  # Chypre
    "nicosia": "Nicosia",
    "zagreb": "Zagreb",  # Croatie
    "copenhague": "Copenhague",  # Danemark
    "copenhagen": "Copenhagen",
    "københavn": "København",
    "madrid": "Madrid",  # Espagne
    "tallinn": "Tallinn",  # Estonie
    "helsinki": "Helsinki",  # Finlande
    "tbilissi": "Tbilissi",  # Géorgie
    "tbilisi": "Tbilisi",
    "athènes": "Athènes",  # Grèce
    "athens": "Athens",
    "budapest": "Budapest",  # Hongrie
    "dublin": "Dublin",  # Irlande
    "reykjavik": "Reykjavik",  # Islande
    "reykjavík": "Reykjavík",
    "rome": "Rome",  # Italie
    "roma": "Roma",
    "pristina": "Pristina",  # Kosovo
    "priština": "Priština",
    "riga": "Riga",  # Lettonie
    "vaduz": "Vaduz",  # Liechtenstein
    "vilnius": "Vilnius",  # Lituanie
    "luxembourg": "Luxembourg",  # Luxembourg
    "skopje": "Skopje",  # Macédoine du Nord
    "la valette": "La Valette",  # Malte
    "valletta": "Valletta",
    "chișinău": "Chișinău",  # Moldavie
    "chisinau": "Chisinau",
    "monaco": "Monaco",  # Monaco
    "podgorica": "Podgorica",  # Monténégro
    "oslo": "Oslo",  # Norvège
    "amsterdam": "Amsterdam",  # Pays-Bas
    "la haye": "La Haye",
    "the hague": "The Hague",
    "varsovie": "Varsovie",  # Pologne
    "warsaw": "Warsaw",
    "warszawa": "Warszawa",
    "lisbonne": "Lisbonne",  # Portugal
    "lisbon": "Lisbon",
    "lisboa": "Lisboa",
    "prague": "Prague",  # République tchèque
    "praha": "Praha",
    "bucarest": "Bucarest",  # Roumanie
    "bucharest": "Bucharest",
    "bucurești": "București",
    "londres": "Londres",  # Royaume-Uni
    "london": "London",
    "moscou": "Moscou",  # Russie
    "moscow": "Moscow",
    "saint-pétersbourg": "Saint-Pétersbourg",
    "saint petersburg": "Saint Petersburg",
    "saint-marin": "Saint-Marin",  # Saint-Marin
    "san marino": "San Marino",
    "belgrade": "Belgrade",  # Serbie
    "bratislava": "Bratislava",  # Slovaquie
    "ljubljana": "Ljubljana",  # Slovénie
    "stockholm": "Stockholm",  # Suède
    "berne": "Berne",  # Suisse
    "bern": "Bern",
    "ankara": "Ankara",  # Turquie
    "kiev": "Kiev",  # Ukraine
    "kyiv": "Kyiv",
    "vatican": "Vatican",
    "cité du vatican": "Cité du Vatican",
    "berlin": "Berlin",  # Allemagne

    # ============ Comtés / county towns d'Angleterre ============
    "bedford": "Bedford",
    "reading": "Reading",
    "bristol": "Bristol",
    "aylesbury": "Aylesbury",
    "cambridge": "Cambridge",
    "chester": "Chester",
    "truro": "Truro",
    "carlisle": "Carlisle",
    "derby": "Derby",
    "matlock": "Matlock",
    "exeter": "Exeter",
    "dorchester": "Dorchester",
    "durham": "Durham",
    "beverley": "Beverley",
    "lewes": "Lewes",
    "chelmsford": "Chelmsford",
    "gloucester": "Gloucester",
    "manchester": "Manchester",
    "winchester": "Winchester",
    "hereford": "Hereford",
    "hertford": "Hertford",
    "newport": "Newport",
    "maidstone": "Maidstone",
    "preston": "Preston",
    "leicester": "Leicester",
    "lincoln": "Lincoln",
    "liverpool": "Liverpool",
    "norwich": "Norwich",
    "northallerton": "Northallerton",
    "northampton": "Northampton",
    "morpeth": "Morpeth",
    "alnwick": "Alnwick",
    "nottingham": "Nottingham",
    "oxford": "Oxford",
    "oakham": "Oakham",
    "shrewsbury": "Shrewsbury",
    "taunton": "Taunton",
    "sheffield": "Sheffield",
    "barnsley": "Barnsley",
    "stafford": "Stafford",
    "ipswich": "Ipswich",
    "guildford": "Guildford",
    "newcastle upon tyne": "Newcastle upon Tyne",
    "newcastle": "Newcastle",
    "warwick": "Warwick",
    "birmingham": "Birmingham",
    "chichester": "Chichester",
    "leeds": "Leeds",
    "wakefield": "Wakefield",
    "trowbridge": "Trowbridge",
    "salisbury": "Salisbury",
    "worcester": "Worcester",

    # ============ Capitales d'États américains ============
    "montgomery": "Montgomery",  # Alabama
    "juneau": "Juneau",  # Alaska
    "phoenix": "Phoenix",  # Arizona
    "little rock": "Little Rock",  # Arkansas
    "sacramento": "Sacramento",  # California
    "denver": "Denver",  # Colorado
    "hartford": "Hartford",  # Connecticut
    "dover": "Dover",  # Delaware
    "tallahassee": "Tallahassee",  # Florida
    "atlanta": "Atlanta",  # Georgia
    "honolulu": "Honolulu",  # Hawaii
    "boise": "Boise",  # Idaho
    "springfield": "Springfield",  # Illinois (et autres états)
    "indianapolis": "Indianapolis",  # Indiana
    "des moines": "Des Moines",  # Iowa
    "topeka": "Topeka",  # Kansas
    "frankfort": "Frankfort",  # Kentucky
    "baton rouge": "Baton Rouge",  # Louisiana
    "augusta": "Augusta",  # Maine
    "annapolis": "Annapolis",  # Maryland
    "boston": "Boston",  # Massachusetts
    "lansing": "Lansing",  # Michigan
    "saint paul": "Saint Paul",  # Minnesota
    "jackson": "Jackson",  # Mississippi
    "jefferson city": "Jefferson City",  # Missouri
    "helena": "Helena",  # Montana
    "carson city": "Carson City",  # Nevada
    "concord": "Concord",  # New Hampshire
    "trenton": "Trenton",  # New Jersey
    "santa fe": "Santa Fe",  # New Mexico
    "albany": "Albany",  # New York state
    "raleigh": "Raleigh",  # North Carolina
    "bismarck": "Bismarck",  # North Dakota
    "columbus": "Columbus",  # Ohio
    "oklahoma city": "Oklahoma City",  # Oklahoma
    "salem": "Salem",  # Oregon
    "harrisburg": "Harrisburg",  # Pennsylvania
    "providence": "Providence",  # Rhode Island
    "columbia": "Columbia",  # South Carolina
    "pierre": "Pierre",  # South Dakota (also a French name)
    "nashville": "Nashville",  # Tennessee
    "austin": "Austin",  # Texas
    "salt lake city": "Salt Lake City",  # Utah
    "montpelier": "Montpelier",  # Vermont
    "richmond": "Richmond",  # Virginia
    "olympia": "Olympia",  # Washington
    "charleston": "Charleston",  # West Virginia
    "madison": "Madison",  # Wisconsin
    "cheyenne": "Cheyenne",  # Wyoming
    # Grandes villes US (non-capitales mais courantes)
    "new york": "New York",
    "new york city": "New York City",
    "los angeles": "Los Angeles",
    "chicago": "Chicago",
    "houston": "Houston",
    "philadelphia": "Philadelphia",
    "san francisco": "San Francisco",
    "san diego": "San Diego",
    "dallas": "Dallas",
    "miami": "Miami",
    "seattle": "Seattle",
    "washington": "Washington",
    "washington d.c.": "Washington D.C.",
    "las vegas": "Las Vegas",
    "new orleans": "New Orleans",

    # ============ Autres villes internationales notables ============
    "milan": "Milan",
    "milano": "Milano",
    "florence": "Florence",
    "firenze": "Firenze",
    "venise": "Venise",
    "venice": "Venice",
    "venezia": "Venezia",
    "naples": "Naples",
    "napoli": "Napoli",
    "barcelone": "Barcelone",
    "barcelona": "Barcelona",
    "valencia": "Valencia",
    "séville": "Séville",
    "seville": "Seville",
    "porto": "Porto",
    "rotterdam": "Rotterdam",
    "anvers": "Anvers",
    "antwerp": "Antwerp",
    "antwerpen": "Antwerpen",
    "genève": "Genève",
    "geneva": "Geneva",
    "zurich": "Zurich",
    "zürich": "Zürich",
    "bâle": "Bâle",
    "basel": "Basel",
    "salzbourg": "Salzbourg",
    "salzburg": "Salzburg",
    "innsbruck": "Innsbruck",
    "munich": "Munich",
    "münchen": "München",
    "francfort": "Francfort",
    "frankfurt": "Frankfurt",
    "hambourg": "Hambourg",
    "hamburg": "Hamburg",
    "cologne": "Cologne",
    "köln": "Köln",
    "düsseldorf": "Düsseldorf",
    "leipzig": "Leipzig",
    "dresde": "Dresde",
    "dresden": "Dresden",
    "stuttgart": "Stuttgart",
    "istanbul": "Istanbul",
    "tokyo": "Tokyo",
    "kyoto": "Kyoto",
    "osaka": "Osaka",
    "beijing": "Beijing",
    "pékin": "Pékin",
    "shanghai": "Shanghai",
    "hong kong": "Hong Kong",
    "séoul": "Séoul",
    "seoul": "Seoul",
    "singapour": "Singapour",
    "singapore": "Singapore",
    "bangkok": "Bangkok",
    "mumbai": "Mumbai",
    "new delhi": "New Delhi",
    "delhi": "Delhi",
    "dubaï": "Dubaï",
    "dubai": "Dubai",
    "montréal": "Montréal",
    "montreal": "Montreal",
    "québec": "Québec",
    "toronto": "Toronto",
    "vancouver": "Vancouver",
    "ottawa": "Ottawa",
    "rio de janeiro": "Rio de Janeiro",
    "sao paulo": "São Paulo",
    "são paulo": "São Paulo",
    "buenos aires": "Buenos Aires",
    "mexico": "Mexico",
    "lima": "Lima",
    "bogotá": "Bogotá",
    "bogota": "Bogota",
    "santiago": "Santiago",
    "sydney": "Sydney",
    "melbourne": "Melbourne",
    "auckland": "Auckland",
    "wellington": "Wellington",
    "le caire": "Le Caire",
    "cairo": "Cairo",
    "casablanca": "Casablanca",
    "rabat": "Rabat",
    "marrakech": "Marrakech",
    "tunis": "Tunis",
    "alger": "Alger",
    "dakar": "Dakar",
    "abidjan": "Abidjan",

    # ============ Pays (FR + EN) ============
    "france": "France",
    "allemagne": "Allemagne",
    "germany": "Germany",
    "italie": "Italie",
    "italy": "Italy",
    "espagne": "Espagne",
    "spain": "Spain",
    "portugal": "Portugal",
    "belgique": "Belgique",
    "belgium": "Belgium",
    "pays-bas": "Pays-Bas",
    "netherlands": "Netherlands",
    "luxembourg": "Luxembourg",
    "royaume-uni": "Royaume-Uni",
    "angleterre": "Angleterre",
    "england": "England",
    "écosse": "Écosse",
    "scotland": "Scotland",
    "irlande": "Irlande",
    "ireland": "Ireland",
    "pays de galles": "Pays de Galles",
    "wales": "Wales",
    "suisse": "Suisse",
    "switzerland": "Switzerland",
    "autriche": "Autriche",
    "austria": "Austria",
    "pologne": "Pologne",
    "poland": "Poland",
    "république tchèque": "République tchèque",
    "czech republic": "Czech Republic",
    "slovaquie": "Slovaquie",
    "slovakia": "Slovakia",
    "hongrie": "Hongrie",
    "hungary": "Hungary",
    "roumanie": "Roumanie",
    "romania": "Romania",
    "bulgarie": "Bulgarie",
    "bulgaria": "Bulgaria",
    "grèce": "Grèce",
    "greece": "Greece",
    "turquie": "Turquie",
    "turkey": "Turkey",
    "russie": "Russie",
    "russia": "Russia",
    "ukraine": "Ukraine",
    "biélorussie": "Biélorussie",
    "belarus": "Belarus",
    "moldavie": "Moldavie",
    "moldova": "Moldova",
    "lituanie": "Lituanie",
    "lithuania": "Lithuania",
    "lettonie": "Lettonie",
    "latvia": "Latvia",
    "estonie": "Estonie",
    "estonia": "Estonia",
    "danemark": "Danemark",
    "denmark": "Denmark",
    "suède": "Suède",
    "sweden": "Sweden",
    "norvège": "Norvège",
    "norway": "Norway",
    "finlande": "Finlande",
    "finland": "Finland",
    "islande": "Islande",
    "iceland": "Iceland",
    "croatie": "Croatie",
    "croatia": "Croatia",
    "serbie": "Serbie",
    "serbia": "Serbia",
    "slovénie": "Slovénie",
    "slovenia": "Slovenia",
    "bosnie": "Bosnie",
    "bosnia": "Bosnia",
    "macédoine": "Macédoine",
    "macedonia": "Macedonia",
    "albanie": "Albanie",
    "albania": "Albania",
    "monténégro": "Monténégro",
    "montenegro": "Montenegro",
    "états-unis": "États-Unis",
    "united states": "United States",
    "canada": "Canada",
    "mexique": "Mexique",
    "brésil": "Brésil",
    "brazil": "Brazil",
    "argentine": "Argentine",
    "argentina": "Argentina",
    "chili": "Chili",
    "chile": "Chile",
    "colombie": "Colombie",
    "colombia": "Colombia",
    "pérou": "Pérou",
    "peru": "Peru",
    "venezuela": "Venezuela",
    "uruguay": "Uruguay",
    "japon": "Japon",
    "japan": "Japan",
    "chine": "Chine",
    "china": "China",
    "corée": "Corée",
    "korea": "Korea",
    "corée du sud": "Corée du Sud",
    "south korea": "South Korea",
    "corée du nord": "Corée du Nord",
    "north korea": "North Korea",
    "inde": "Inde",
    "india": "India",
    "pakistan": "Pakistan",
    "thaïlande": "Thaïlande",
    "thailand": "Thailand",
    "vietnam": "Vietnam",
    "indonésie": "Indonésie",
    "indonesia": "Indonesia",
    "philippines": "Philippines",
    "australie": "Australie",
    "australia": "Australia",
    "nouvelle-zélande": "Nouvelle-Zélande",
    "new zealand": "New Zealand",
    "maroc": "Maroc",
    "morocco": "Morocco",
    "tunisie": "Tunisie",
    "tunisia": "Tunisia",
    "algérie": "Algérie",
    "algeria": "Algeria",
    "égypte": "Égypte",
    "egypt": "Egypt",
    "sénégal": "Sénégal",
    "senegal": "Senegal",
    "côte d'ivoire": "Côte d'Ivoire",
    "ivory coast": "Ivory Coast",
    "afrique du sud": "Afrique du Sud",
    "south africa": "South Africa",
    "kenya": "Kenya",
    "nigéria": "Nigéria",
    "nigeria": "Nigeria",
    "israël": "Israël",
    "israel": "Israel",
    "liban": "Liban",
    "lebanon": "Lebanon",
    "iran": "Iran",
    "irak": "Irak",
    "iraq": "Iraq",
    "syrie": "Syrie",
    "syria": "Syria",
    "arabie saoudite": "Arabie saoudite",
    "saudi arabia": "Saudi Arabia",
    # Acronymes pays courants (à laisser en MAJ)
    "usa": "USA",
    "uk": "UK",
    "rdc": "RDC",
    "uae": "UAE",
}


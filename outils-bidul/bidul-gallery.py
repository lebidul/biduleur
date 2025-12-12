#!/usr/bin/env python3
"""
Outil de réorganisation de la galerie Le Bidul
Génère:
- gallery_sorted.html : galerie WordPress avec images triées chronologiquement
- index.html : page de sondage pour voter (max 5 choix)

Usage:
  python bidul_gallery_tool.py gallery_input.html

Le fichier gallery_input.html doit contenir le HTML brut de la galerie WordPress.
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

# Mapping manuel pour les fichiers ambigus (WordPress ID -> numéro Bidul)
MANUAL_MAPPING = {
    # 2011-2014 période avec noms ambigus
    1703: 184,  # Image11.png -> décembre 2013
    1705: 183,  # Bidul-Nov-20131.png -> novembre 2013
    1708: 182,  # Bidul-Octobre-20131.png -> octobre 2013
    1713: 173,  # 1731.jpg -> décembre 2012 (173, pas 173.1)
    1715: 156,  # 156.jpg -> mai 2011
    1717: 175,  # 1751.jpg -> février 2013 (pas 175.1)
    1720: 172,  # 1721.jpg -> novembre 2012 (pas 172.1)
    1736: 187,  # 187-bidule-mars-2014.png
    1970: 190,  # juin-20141.jpg -> juin 2014

    # 2015
    2288: 198,  # couv-mars.png -> mars 2015
    2324: 200,  # Couverture-200ter.jpg -> avril 2015 (numéro 200)
    2359: 201,  # couverture-bidul-mai-2015.jpg -> mai 2015

    # 2016
    2951: 214,  # Couv-septembre-2016.jpg
    3060: 216,  # Image1-2.png -> novembre 2016

    # 2017
    3266: 220,  # poissons.jpg -> mars/avril 2017
    3333: 221,  # visuel-20-ans.jpg -> avril 2017 (20 ans du Bidul)

    # 2018
    4279: 229,  # Sans-titre.jpg -> janvier 2018
    4486: 231,  # une-bidul.png -> mars 2018
    4775: 233,  # Bidul-juin.jpg -> juin 2018
    4868: 234,  # une.png -> juillet 2018
    5105: 236,  # une-octobre.jpg -> octobre 2018
    5169: 237,  # 2018-11-Couv-Bidul.jpg -> novembre 2018
    5248: 239,  # une-deécembre.png -> décembre 2018
    5342: 240,  # une-240.png -> janvier 2019

    # 2019
    5424: 241,  # une-février.png -> février 2019
    5530: 242,  # une-A.png -> mars 2019
    5731: 243,  # une-avril.png -> avril 2019
    5977: 245,  # une-245.png -> juin 2019
    6104: 246,  # Couv-Bidul-246.jpg -> juillet 2019
    6307: 248,  # 2019-10-une.png -> octobre 2019
    6434: 249,  # une-249.png -> novembre 2019
    6568: 250,  # UNE-250.png -> décembre 2019

    # 2020
    6711: 251,  # une-251.png -> janvier 2020
    6838: 252,  # une-252.png -> février 2020
    6923: 253,  # une-253.png -> mars 2020
    7012: 254,  # Couv-Pierre-Frampas-3.jpg -> avril 2020

    # Images avec noms explicites bidul_NNN déjà correctement détectées
    8617: 1,  # bidul_1_fev1997.jpg
    8637: 244,  # bidul_244_couv_mai20.png (mai 2019, pas mai 2020!)
    8638: 247,  # bidul_247_couv_sep19.png
    8639: 255,  # bidul_255_couv_mai20.png
    8623: 256,  # bidul_256_couv_juillAout20.jpg
    8624: 257,  # bidul_257_couv_sep20.jpg
    8625: 258,  # bidul_258_couv_oct20.jpg
    8640: 259,  # bidul_259_couv_juin21.png
    8641: 260,  # bidul_260_couv_juillAout21.png
    8622: 261,  # couv_sep_21.jpg
    8626: 262,  # bidul_262_couv_oct21.jpg
    8627: 264,  # bidul_264_couv_nov21.jpg
    8618: 263,  # couv_dec21.jpg -> en fait c'est 263 (nov-dec confondus?)
    8629: 265,  # couv_jan22-1.jpg
    8628: 266,  # bidul_266_couv_fev22.jpg

    # 2022
    10120: 267,  # couv_mar22_couleur-rotated.jpg
    10123: 268,  # couv_avril22.jpg
    10122: 269,  # couv_mai22.jpg
    10125: 270,  # couv_juin22.jpg
    10121: 271,  # couv_juil22-1.jpg
    11243: 272,  # couv_sep22-2.jpg
    13076: 273,  # couv_oct22.jpg
    13079: 274,  # couv_nov22.jpg
    13078: 275,  # couv_dec22.jpg

    # 2023
    13077: 276,  # couv_jan23-1.jpg
    13269: 277,  # 202302.jpg
    13524: 278,  # 202303-1.jpg
    13890: 279,  # 202304-1.jpg
    14900: 280,  # 202305.jpg
    14899: 281,  # 202306.jpg
    14901: 282,  # 202307-1-scaled.jpg
    16717: 283,  # 202309.jpg
    16715: 284,  # 202310.jpg
    16716: 285,  # 202311.jpg
    16718: 286,  # 202312.jpg

    # 2024
    17213: 287,  # 202401.png
    17202: 288,  # 202402_alt.png
    18131: 289,  # 202403_2.289-scaled.jpg
    18130: 290,  # 202404_2.290-1.png
    18535: 291,  # 202405_291-scaled.jpg
    19172: 292,  # 202406_292.jpg
    19171: 293,  # 202407_293-1.jpg
    21893: 294,  # 202409_294.jpg
    21892: 295,  # 202410_295.jpg
    21898: 296,  # 202411_296.jpg
    21899: 297,  # 202412_297.jpg

    # 2025
    21894: 298,  # 202501_298.jpg
    21891: 299,  # 202502_299-1.jpg
    23911: 300,  # 202503_300.jpg
    23913: 301,  # 202504_301.jpg
    23912: 302,  # 202505_302-1.jpg
    25201: 303,  # 202506_303.jpg
    24604: 304,  # 304.couv_-1.png
    25203: 305,  # 202509_305.png
    25204: 306,  # 202510_306.png
    25202: 307,  # 202511_307-1.png
    25219: 308,  # 202512_308.png
}

# Mois français vers numéro
FRENCH_MONTHS = {
    'janvier': 1, 'jan': 1, 'fevrier': 2, 'fev': 2, 'février': 2,
    'mars': 3, 'mar': 3, 'avril': 4, 'avr': 4, 'mai': 5,
    'juin': 6, 'juil': 7, 'juillet': 7, 'sept': 9, 'septembre': 9,
    'sep': 9, 'octobre': 10, 'oct': 10, 'novembre': 11, 'nov': 11,
    'decembre': 12, 'dec': 12, 'décembre': 12
}


def date_to_issue_number(year, month):
    """Convertit une date en numéro de Bidul approximatif."""
    # Référence: #1 = février 1997
    # ~11 numéros par an (pas de numéro en août)

    ref_year, ref_month = 1997, 2
    ref_issue = 1

    months_diff = (year - ref_year) * 12 + (month - ref_month)
    # Environ 0.92 numéros par mois (11/12)
    issue = ref_issue + int(months_diff * 0.92)
    return max(1, issue)


def extract_issue_from_filename(filename, wp_id):
    """Extrait le numéro de Bidul depuis le nom de fichier."""

    # D'abord vérifier le mapping manuel
    if wp_id in MANUAL_MAPPING:
        return MANUAL_MAPPING[wp_id], 'manual'

    filename_lower = filename.lower()

    # Pattern 1: bidul_NNN_YYYYMM ou bidul_NNN_...
    match = re.search(r'bidul[_-](\d{1,3})[_-]', filename_lower)
    if match:
        return int(match.group(1)), 'bidul_num'

    # Pattern 2: YYYYMM_NNN.jpg (ex: 202405_291.jpg pour mai 2024, numéro 291)
    # Le format est YYYYMM_numéro où numéro est le vrai numéro du Bidul
    match = re.search(r'(\d{4})(\d{2})[_-](\d{2,3})(?:[_.-]|$)', filename_lower)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        num = int(match.group(3))
        if 2020 <= year <= 2030 and 1 <= month <= 12 and 200 <= num <= 400:
            return num, 'yyyymm_num'

    # Pattern 2b: YYYYMM.jpg simple (ex: 202309.jpg) - convertir en date
    match = re.search(r'^(\d{4})(\d{2})(?:-\d)?\.', filename_lower)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 2020 <= year <= 2030 and 1 <= month <= 12:
            return date_to_issue_number(year, month), 'yyyymm_date'

    # Pattern 3: couv_moisYY.jpg (ex: couv_jan22.jpg)
    match = re.search(r'couv[_-]([a-zéû]+)[\-_]?(\d{2})(?:-\d)?\.', filename_lower)
    if match:
        month_name = match.group(1).lower()
        year_short = int(match.group(2))
        year = 2000 + year_short if year_short < 50 else 1900 + year_short
        if month_name in FRENCH_MONTHS:
            month = FRENCH_MONTHS[month_name]
            return date_to_issue_number(year, month), 'couv_mois'

    # Pattern 4: NNN.jpg simple (ex: 156.jpg)
    match = re.match(r'^(\d{1,3})\.(?:jpg|png)$', filename_lower)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 350:
            return num, 'simple_num'

    # Pattern 5: une-NNN.png (ex: une-245.png)
    match = re.search(r'une[_-](\d{3})\.', filename_lower)
    if match:
        return int(match.group(1)), 'une_num'

    # Pattern 6: mois-année dans le nom (ex: juin-20141.jpg)
    for month_name, month_num in FRENCH_MONTHS.items():
        pattern = rf'{month_name}[_-]?(\d{{4}})'
        match = re.search(pattern, filename_lower)
        if match:
            year = int(match.group(1))
            if 1997 <= year <= 2030:
                return date_to_issue_number(year, month_num), 'month_year'

    # Pattern 7: Extraire depuis le path d'upload WordPress
    # /uploads/YYYY/MM/
    return None, 'unknown'


def extract_date_from_path(url):
    """Extrait la date depuis le chemin d'upload WordPress."""
    match = re.search(r'/uploads/(\d{4})/(\d{2})/', url)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def parse_gallery_html(html_content):
    """Parse le HTML de la galerie et extrait les infos de chaque image."""
    images = []

    # Pattern pour extraire les blocs wp:image
    image_pattern = re.compile(
        r'<!-- wp:image \{[^}]*"id":(\d+)[^}]*\} -->\s*'
        r'<figure[^>]*>.*?<a href="([^"]+)"[^>]*>.*?</a>.*?</figure>\s*'
        r'<!-- /wp:image -->',
        re.DOTALL
    )

    for match in image_pattern.finditer(html_content):
        wp_id = int(match.group(1))
        url = match.group(2)
        filename = url.split('/')[-1]

        issue_num, method = extract_issue_from_filename(filename, wp_id)

        # Fallback: utiliser la date d'upload
        if issue_num is None:
            upload_year, upload_month = extract_date_from_path(url)
            if upload_year and upload_month:
                issue_num = date_to_issue_number(upload_year, upload_month)
                method = 'upload_date'

        if issue_num is None:
            issue_num = 9999  # Mettre à la fin si inconnu
            method = 'fallback'

        images.append({
            'wp_id': wp_id,
            'url': url,
            'filename': filename,
            'issue_num': issue_num,
            'method': method,
            'full_block': match.group(0)
        })

    return images


def generate_sorted_gallery_html(images, original_html):
    """Génère le HTML de la galerie triée."""

    # Trier par numéro de Bidul
    sorted_images = sorted(images, key=lambda x: (x['issue_num'], x['wp_id']))

    # Extraire les IDs triés
    sorted_ids = [img['wp_id'] for img in sorted_images]

    # Construire le nouveau HTML
    output_lines = [
        '<p>Nostalgique(s) ? Voici un aperçu de quelques couvertures du Bidul depuis sa création en février 1997...</p>',
        '',
        f'<!-- wp:gallery {{"ids":[{",".join(map(str, sorted_ids))}],"columns":4,"linkTo":"media","align":"center"}} -->',
        '<figure class="wp-block-gallery aligncenter has-nested-images columns-4 is-cropped">'
    ]

    for img in sorted_images:
        output_lines.append(img['full_block'])
        output_lines.append('')

    output_lines.append('</figure>')
    output_lines.append('<!-- /wp:gallery -->')

    return '\n'.join(output_lines), sorted_images


def generate_poll_html(images, max_choices=5):
    """Génère le HTML de la page de sondage."""

    sorted_images = sorted(images, key=lambda x: (x['issue_num'], x['wp_id']))

    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Votez pour vos couvertures préférées du Bidul !</title>
    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }}

        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}

        header p {{
            font-size: 1.2em;
            opacity: 0.9;
        }}

        .selection-counter {{
            position: sticky;
            top: 10px;
            z-index: 100;
            background: white;
            padding: 15px 25px;
            border-radius: 50px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            display: inline-flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 20px;
        }}

        .counter-text {{
            font-size: 1.1em;
            font-weight: 600;
            color: #333;
        }}

        .counter-badges {{
            display: flex;
            gap: 5px;
        }}

        .counter-badge {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #e0e0e0;
            transition: background 0.3s;
        }}

        .counter-badge.filled {{
            background: #667eea;
        }}

        .submit-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .submit-btn:hover:not(:disabled) {{
            transform: scale(1.05);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}

        .submit-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}

        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            padding: 20px 0;
        }}

        .cover-card {{
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            position: relative;
        }}

        .cover-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }}

        .cover-card.selected {{
            box-shadow: 0 0 0 4px #667eea, 0 8px 25px rgba(102, 126, 234, 0.3);
        }}

        .cover-card.selected::after {{
            content: '✓';
            position: absolute;
            top: 10px;
            right: 10px;
            width: 30px;
            height: 30px;
            background: #667eea;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.2em;
        }}

        .cover-card img {{
            width: 100%;
            height: auto;
            display: block;
        }}

        .cover-info {{
            padding: 12px;
            text-align: center;
        }}

        .cover-number {{
            font-weight: 700;
            color: #667eea;
            font-size: 1.1em;
        }}

        /* Modal pour l'email */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}

        .modal-overlay.active {{
            display: flex;
        }}

        .modal {{
            background: white;
            padding: 40px;
            border-radius: 20px;
            max-width: 500px;
            width: 90%;
            text-align: center;
        }}

        .modal h2 {{
            color: #333;
            margin-bottom: 20px;
        }}

        .modal p {{
            color: #666;
            margin-bottom: 25px;
        }}

        .modal input[type="email"] {{
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 1em;
            margin-bottom: 20px;
            transition: border-color 0.3s;
        }}

        .modal input[type="email"]:focus {{
            outline: none;
            border-color: #667eea;
        }}

        .modal-buttons {{
            display: flex;
            gap: 15px;
            justify-content: center;
        }}

        .modal-btn {{
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }}

        .modal-btn.primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
        }}

        .modal-btn.secondary {{
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
        }}

        .modal-btn:hover {{
            transform: scale(1.05);
        }}

        .selected-preview {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
            margin-bottom: 20px;
        }}

        .selected-preview img {{
            width: 60px;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .success-message {{
            display: none;
            color: #4CAF50;
            font-size: 1.2em;
            margin-top: 20px;
        }}

        @media (max-width: 768px) {{
            header h1 {{
                font-size: 1.8em;
            }}

            .gallery {{
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
            }}

            .selection-counter {{
                flex-direction: column;
                padding: 10px 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎨 Votez pour vos couvertures préférées !</h1>
            <p>Sélectionnez jusqu'à {max_choices} couvertures du Bidul qui vous ont marqué</p>
        </header>

        <div style="text-align: center;">
            <div class="selection-counter">
                <span class="counter-text">Sélection : <span id="count">0</span>/{max_choices}</span>
                <div class="counter-badges">
                    {"".join([f'<div class="counter-badge" id="badge-{i}"></div>' for i in range(max_choices)])}
                </div>
                <button class="submit-btn" id="submit-btn" disabled onclick="showModal()">
                    Valider mes choix
                </button>
            </div>
        </div>

        <div class="gallery" id="gallery">
'''

    for img in sorted_images:
        # Utiliser l'URL thumbnail si disponible
        thumb_url = img['url'].replace('.jpg', '-728x1024.jpg').replace('.png', '.png')
        if '-728x1024' not in img['url'] and '-scaled' not in img['url']:
            thumb_url = img['url']  # Garder l'original si pas de thumbnail

        html += f'''            <div class="cover-card" data-id="{img['wp_id']}" onclick="toggleSelection(this)">
                <img src="{img['url']}" alt="Bidul #{img['issue_num']}" loading="lazy">
                <div class="cover-info">
                    <span class="cover-number">N°{img['issue_num']}</span>
                </div>
            </div>
'''

    html += f'''        </div>
    </div>

    <div class="modal-overlay" id="modal">
        <div class="modal">
            <h2>Confirmez votre vote</h2>
            <p>Vos couvertures préférées :</p>
            <div class="selected-preview" id="selected-preview"></div>
            <p>Entrez votre email pour valider (un seul vote par email)</p>
            <input type="email" id="email" placeholder="votre@email.com" required>
            <div class="modal-buttons">
                <button class="modal-btn secondary" onclick="hideModal()">Annuler</button>
                <button class="modal-btn primary" onclick="submitVote()">Confirmer</button>
            </div>
            <p class="success-message" id="success">✓ Merci pour votre vote !</p>
        </div>
    </div>

    <script>
        const MAX_SELECTION = {max_choices};
        let selected = new Set();

        function toggleSelection(card) {{
            const id = card.dataset.id;

            if (selected.has(id)) {{
                selected.delete(id);
                card.classList.remove('selected');
            }} else if (selected.size < MAX_SELECTION) {{
                selected.add(id);
                card.classList.add('selected');
            }}

            updateCounter();
        }}

        function updateCounter() {{
            document.getElementById('count').textContent = selected.size;
            document.getElementById('submit-btn').disabled = selected.size === 0;

            // Mettre à jour les badges
            for (let i = 0; i < MAX_SELECTION; i++) {{
                const badge = document.getElementById('badge-' + i);
                badge.classList.toggle('filled', i < selected.size);
            }}
        }}

        function showModal() {{
            if (selected.size === 0) return;

            // Afficher les préviews
            const preview = document.getElementById('selected-preview');
            preview.innerHTML = '';
            selected.forEach(id => {{
                const card = document.querySelector(`[data-id="${{id}}"]`);
                const img = card.querySelector('img').cloneNode();
                preview.appendChild(img);
            }});

            document.getElementById('modal').classList.add('active');
        }}

        function hideModal() {{
            document.getElementById('modal').classList.remove('active');
        }}

        function submitVote() {{
            const email = document.getElementById('email').value;
            if (!email || !email.includes('@')) {{
                alert('Veuillez entrer un email valide');
                return;
            }}

            // Envoyer le vote (à adapter selon votre backend)
            const voteData = {{
                email: email,
                selections: Array.from(selected),
                timestamp: new Date().toISOString()
            }};

            console.log('Vote:', voteData);

            // Afficher le message de succès
            document.getElementById('success').style.display = 'block';

            // Fermer après 2 secondes
            setTimeout(() => {{
                hideModal();
                // Optionnel: désactiver le formulaire après le vote
                document.querySelectorAll('.cover-card').forEach(card => {{
                    card.style.pointerEvents = 'none';
                }});
                document.getElementById('submit-btn').disabled = true;
                document.getElementById('submit-btn').textContent = 'Vote enregistré !';
            }}, 2000);

            // TODO: Envoyer à votre serveur
            // fetch('/api/vote', {{
            //     method: 'POST',
            //     headers: {{ 'Content-Type': 'application/json' }},
            //     body: JSON.stringify(voteData)
            // }});
        }}

        // Fermer modal en cliquant à l'extérieur
        document.getElementById('modal').addEventListener('click', (e) => {{
            if (e.target.id === 'modal') hideModal();
        }});
    </script>
</body>
</html>
'''

    return html


def print_debug_info(images):
    """Affiche les informations de debug."""
    print("\n" + "=" * 80)
    print("IMAGES PARSÉES ET TRIÉES")
    print("=" * 80)

    sorted_images = sorted(images, key=lambda x: (x['issue_num'], x['wp_id']))

    by_method = defaultdict(list)
    for img in sorted_images:
        by_method[img['method']].append(img)

    print(f"\nTotal: {len(images)} images")
    print("\nPar méthode de détection:")
    for method, imgs in sorted(by_method.items()):
        print(f"  {method}: {len(imgs)} images")

    print("\n" + "-" * 80)
    print(f"{'#':<6} {'WP_ID':<8} {'Méthode':<15} {'Fichier'}")
    print("-" * 80)

    prev_issue = 0
    for img in sorted_images[:50]:  # Afficher les 50 premiers
        gap = ""
        if img['issue_num'] - prev_issue > 1 and prev_issue > 0:
            gap = f" [GAP: {prev_issue + 1}-{img['issue_num'] - 1}]"
        prev_issue = img['issue_num']

        print(f"#{img['issue_num']:<5} {img['wp_id']:<8} {img['method']:<15} {img['filename'][:40]}{gap}")

    if len(sorted_images) > 50:
        print(f"... et {len(sorted_images) - 50} autres images")


def main():
    if len(sys.argv) < 2:
        print("Usage: python bidul_gallery_tool.py <fichier_html_galerie>")
        print("\nExemple: python bidul_gallery_tool.py gallery_input.html")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Erreur: Le fichier '{input_file}' n'existe pas")
        sys.exit(1)

    print(f"📖 Lecture de {input_file}...")
    html_content = input_file.read_text(encoding='utf-8')

    print("🔍 Parsing des images...")
    images = parse_gallery_html(html_content)
    print(f"   → {len(images)} images trouvées")

    # Afficher les infos de debug
    print_debug_info(images)

    # Générer la galerie triée
    print("\n📝 Génération de gallery_sorted.html...")
    gallery_html, sorted_images = generate_sorted_gallery_html(images, html_content)

    output_gallery = input_file.parent / "gallery_sorted.html"
    output_gallery.write_text(gallery_html, encoding='utf-8')
    print(f"   → Sauvegardé dans {output_gallery}")

    # Générer la page de sondage
    print("\n📊 Génération de index.html (sondage, max 5 choix)...")
    poll_html = generate_poll_html(images, max_choices=5)

    output_poll = input_file.parent / "index.html"
    output_poll.write_text(poll_html, encoding='utf-8')
    print(f"   → Sauvegardé dans {output_poll}")

    # Afficher les IDs triés pour WordPress
    sorted_ids = [img['wp_id'] for img in sorted_images]
    print("\n" + "=" * 80)
    print("IDS TRIÉS POUR WORDPRESS (à copier dans le bloc gallery):")
    print("=" * 80)
    print(",".join(map(str, sorted_ids)))

    print("\n✅ Terminé !")


if __name__ == "__main__":
    main()
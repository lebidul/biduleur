#!/usr/bin/env python3
"""
Script pour ajouter des liens PDF à une galerie WordPress du Bidul.
Ajoute un lien PDF sous chaque image de couverture.
"""

import re
import sys
from urllib.parse import quote

# URL de base pour les PDFs
PDF_BASE_URL = "https://www.lebidul.com/wp-content/uploads/biduls_pdf/"

# Liste des fichiers PDF (copiée du document fourni)
PDF_FILES = """
1997-02 Bidul 001.pdf
1997-03 Bidul 002.pdf
1997-04 Bidul 003.pdf
1997-05 Bidul 004.pdf
1997-06 Bidul 005.pdf
1997-07 Bidul 006.pdf
1997-09 Bidul 007.pdf
1997-10 Bidul 008.pdf
1997-11 Bidul 009.pdf
1997-12 Bidul 010.pdf
1998-01 Bidul 011.pdf
1998-02 Bidul 012.pdf
1998-03 Bidul 013.pdf
1998-04 Bidul 014.pdf
1998-05 Bidul 015.pdf
1998-06 Bidul 016.pdf
1998-07 Bidul 017.pdf
1998-10 Bidul 019.pdf
1999-03 Bidul 022.pdf
1999-04 Bidul 023.pdf
1999-05 Bidul 024.pdf
1999-06 Bidul 025.pdf
1999-07 Bidul 026.pdf
1999-09 Bidul 027.pdf
1999-11 Bidul 029.pdf
1999-12 Bidul 030.pdf
2000-01 Bidul 031.pdf
2000-02 Bidul 032.pdf
2000-03 Bidul 033.pdf
2000-04 Bidul 034.pdf
2000-05 Bidul 035.pdf
2000-06 Bidul 036.pdf
2000-07 Bidul 037.pdf
2000-09 Bidul 038.pdf
2000-10 Bidul 039.pdf
2000-11 Bidul 040.pdf
2000-12 Bidul 041.pdf
2001-01 Bidul 042.pdf
2001-02 Bidul 043.pdf
2001-03 Bidul 044.pdf
2001-04 Bidul 045.pdf
2001-05 Bidul 046.pdf
2001-06 Bidul 047.pdf
2001-07 Bidul 048.pdf
2001-09 Bidul 049.pdf
2001-10 Bidul 050.pdf
2001-11 Bidul 051.pdf
2001-12 Bidul 052.pdf
2002-01 Bidul 053.pdf
2002-02 Bidul 054.pdf
2002-03 Bidul 055.pdf
2002-04 Bidul 056.pdf
2002-05 Bidul 057.pdf
2002-06 Bidul 058.pdf
2002-07 Bidul 059.pdf
2002-09 Bidul 060.pdf
2002-10 Bidul 061.pdf
2002-11 Bidul 062.pdf
2002-12 Bidul 063.pdf
2003-01 Bidul 064.pdf
2003-02 Bidul 065.pdf
2003-03 Bidul 066.pdf
2003-04 Bidul 067.pdf
2003-05 Bidul 068.pdf
2003-06 Bidul 069.pdf
2003-07 Bidul 070.pdf
2003-09 Bidul 071.pdf
2003-10 Bidul 072.pdf
2003-11 Bidul 073.pdf
2003-12 Bidul 074.pdf
2004-01 Bidul 075.pdf
2004-02 Bidul 076.pdf
2004-03 Bidul 077.pdf
2004-04 Bidul 078.pdf
2004-05 Bidul 079.pdf
2004-06 Bidul 080.pdf
2004-07 Bidul 081.pdf
2004-09 Bidul 082.pdf
2004-10 Bidul 083.pdf
2004-11 Bidul 084.pdf
2004-12 Bidul 085.pdf
2005-01 Bidul 086.pdf
2005-02 Bidul 087.pdf
2005-03 Bidul 088.pdf
2005-04 Bidul 089.pdf
2005-05 Bidul 090.pdf
2005-06 Bidul 091.pdf
2005-07 Bidul 092.pdf
2005-09 Bidul 093.pdf
2005-10 Bidul 094.pdf
2005-11 Bidul 095.pdf
2005-12 Bidul 096.pdf
2006-01 Bidul 097.pdf
2006-02 Bidul 098.pdf
2006-03 Bidul 099.pdf
2006-04 Bidul 100.pdf
2006-05 Bidul 101.pdf
2006-06 Bidul 102.pdf
2006-07 Bidul 103.pdf
2006-09 Bidul 104.pdf
2006-10 Bidul 105.pdf
2006-11 Bidul 106.pdf
2006-12 Bidul 107.pdf
2007-01 Bidul 108.pdf
2007-02 Bidul 109.pdf
2007-03 Bidul 110.pdf
2007-04 Bidul 111.pdf
2007-05 Bidul 112.pdf
2007-06 Bidul 113.pdf
2007-07 Bidul 114.pdf
2007-09 Bidul 115.pdf
2007-10 Bidul 116.pdf
2007-11 Bidul 117.pdf
2007-12 Bidul 118.pdf
2008-01 Bidul 119.pdf
2008-02 Bidul 120.pdf
2008-03 Bidul 121.pdf
2008-04 Bidul 122.pdf
2008-05 Bidul 123.pdf
2008-06 Bidul 124.pdf
2008-07 Bidul 125.pdf
2008-09 Bidul 126.pdf
2008-10 Bidul 127.pdf
2008-11 Bidul 128.pdf
2008-12 Bidul 129.pdf
2009-01 Bidul 130.pdf
2009-02 Bidul 131.pdf
2009-03 Bidul 132.pdf
2009-04 Bidul 133.pdf
2009-05 Bidul 134.pdf
2009-06 Bidul 135.pdf
2009-07 Bidul 136.pdf
2009-09 Bidul 137.pdf
2009-10 Bidul 138.pdf
2009-11 Bidul 139.pdf
2009-12 Bidul 140.pdf
2010-01 Bidul 141.pdf
2010-02 Bidul 142.pdf
2010-03 Bidul 143.pdf
2010-04 Bidul 144.pdf
2010-05 Bidul 145.pdf
2010-06 Bidul 146.pdf
2010-07 Bidul 147.pdf
2010-09 Bidul 147 bis.pdf
2010-10 Bidul 149.pdf
2010-11 Bidul 150.pdf
2010-12 Bidul 151.pdf
2011-01 Bidul 152.pdf
2011-02 Bidul 153.pdf
2011-03 Bidul 154.pdf
2011-04 Bidul 155.pdf
2011-05 Bidul 156.pdf
2011-06 Bidul 157.pdf
2011-07 Bidul 158.pdf
2011-09 Bidul 159.pdf
2011-10 Bidul 160.pdf
2011-11 Bidul 161.pdf
2011-12 Bidul 162.pdf
2012-01 Bidul 163.pdf
2012-02 Bidul 164.pdf
2012-03 Bidul 165.pdf
2012-04 Bidul 166.pdf
2012-05 Bidul 167.pdf
2012-06 Bidul 168.pdf
2012-07 Bidul 169.pdf
2012-09 Bidul 170.pdf
2012-10 Bidul 171.pdf
2012-11 Bidul 172.pdf
2012-12 Bidul 173.pdf
2013-01 Bidul 174.pdf
2013-02 Bidul 175.pdf
2013-03 Bidul 176.pdf
2013-04 Bidul 177.pdf
2013-05 Bidul 178.pdf
2013-06 Bidul 179.pdf
2013-07 Bidul 180.pdf
2013-09 Bidul 181.pdf
2013-10 Bidul 182.pdf
2013-11 Bidul 183.pdf
2013-12 Bidul 184.pdf
2014-01 Bidul 185.pdf
2014-02 Bidul 186.pdf
2014-03 Bidul 187.pdf
2014-04 Bidul 188.pdf
2014-05 Bidul 189.pdf
2014-06 Bidul 190.pdf
2014-0708 Bidul 191.pdf
2014-09 Bidul 192.pdf
2014-10 Bidul 193.pdf
2014-11 Bidul 194.pdf
2015-01 Bidul 196.pdf
2015-02 Bidul 197.pdf
2015-03 Bidul 198.pdf
2015-04 Bidul 199.pdf
2015-05 Bidul 200.pdf
2015-06 Bidul 201.pdf
2015-07 Bidul 202.pdf
2015-09 Bidul 203.pdf
2015-10 Bidul 204.pdf
2015-11 Bidul 205.pdf
2015-12 Bidul 206.pdf
2016-01 Bidul 207.pdf
2016-02 Bidul 208.pdf
2016-03 Bidul 209.pdf
2016-04 Bidul 210.pdf
2016-05 Bidul 211.pdf
2016-06 Bidul 212.pdf
2016-07 Bidul 213.pdf
2016-09 Bidul 214.pdf
2016-10 Bidul 215.pdf
2016-11 Bidul 216.pdf
2016-12 Bidul 217.pdf
2017-01 Bidul 218.pdf
2017-02 Bidul 219.pdf
2017-03 Bidul 220.pdf
2017-04 Bidul 221.pdf
2017-05 Bidul 222.pdf
2017-06 Bidul 223.pdf
2017-07 Bidul 224.pdf
2017-09 Bidul 225.pdf
2017-10 Bidul 226.pdf
2017-11 Bidul 227.pdf
2017-12 Bidul 228.pdf
2018-01 Bidul 229.pdf
2018-02 Bidul 230.pdf
2018-03 Bidul 231.pdf
2018-04 Bidul 232.pdf
2018-05 Bidul 233.pdf
2018-06 Bidul 234.pdf
2018-07 Bidul 235.pdf
2018-09 Bidul 236.pdf
2018-10 Bidul 237.pdf
2018-11 Bidul 238.pdf
2018-12 Bidul 239.pdf
2019-01 Bidul 240.pdf
2019-02 Bidul 241.pdf
2019-03 Bidul 242.pdf
2019-04 Bidul 243.pdf
2019-05 Bidul 244.pdf
2019-06 Bidul 245.pdf
2019-07 Bidul 246.pdf
2019-09 Bidul 247.pdf
2019-10 Bidul 248.pdf
2019-11 Bidul 249.pdf
2019-12 Bidul 250.pdf
2020-01 Bidul 251.pdf
2020-02 Bidul 252.pdf
2020-03 Bidul 253.pdf
2020-04 Bidul 254.pdf
2020-05 Bidul 255.pdf
2020-07 Bidul 256.pdf
2020-09 Bidul 257.pdf
2020-10 Bidul 258.pdf
2021-06 Bidul 259.pdf
2021-07 Bidul 260.pdf
2021-09 Bidul 261.pdf
2021-10 Bidul 262.pdf
2021-11 Bidul 263.pdf
2021-12 Bidul 264.pdf
2022-01 Bidul 265.pdf
2022-02 Bidul 266.pdf
2022-03 Bidul 267.pdf
2022-04 Bidul 268.pdf
2022-05 Bidul 269.pdf
2022-06 Bidul 270.pdf
2022-07 Bidul 271.pdf
2022-09 Bidul 272.pdf
2022-10 Bidul 273.pdf
2022-11 Bidul 274.pdf
2022-12 Bidul 275.pdf
2023-01 Bidul 276.pdf
2023-02 Bidul 277.pdf
2023-03 Bidul 278.pdf
2023-04 Bidul 279.pdf
2023-05 Bidul 280.pdf
2023-06 Bidul 281.pdf
2023-07 Bidul 282.pdf
2023-09 Bidul 283.pdf
2023-10 Bidul 284.pdf
2023-11 Bidul 285.pdf
2023-12 Bidul 286.pdf
2024-01 Bidul 287.pdf
2024-02 Bidul 288.pdf
2024-03 Bidul 289.pdf
2024-04 Bidul 290.pdf
2024-05 Bidul 291.pdf
2024-06 Bidul 292.pdf
2024-07 Bidul 293.pdf
2024-09 Bidul 294.pdf
2024-10 Bidul 295.pdf
2024-11 Bidul 296.pdf
2024-12 Bidul 297.pdf
2025-01 Bidul 298.pdf
2025-02 Bidul 299.pdf
""".strip().split('\n')

# Mapping manuel WordPress ID -> numéro Bidul (repris du script précédent)
MANUAL_MAPPING = {
    1703: 184, 1705: 183, 1708: 182, 1713: 173, 1715: 156, 1717: 175, 1720: 172,
    1736: 187, 1970: 190, 2288: 198, 2324: 200, 2359: 201, 2951: 214, 3060: 216,
    3266: 220, 3333: 221, 4279: 229, 4486: 231, 4775: 233, 4868: 234, 5105: 236,
    5169: 237, 5248: 239, 5342: 240, 5424: 241, 5530: 242, 5731: 243, 5977: 245,
    6104: 246, 6307: 248, 6434: 249, 6568: 250, 6711: 251, 6838: 252, 6923: 253,
    7012: 254, 8617: 1, 8637: 244, 8638: 247, 8639: 255, 8623: 256, 8624: 257,
    8625: 258, 8640: 259, 8641: 260, 8622: 261, 8626: 262, 8627: 264, 8618: 263,
    8629: 265, 8628: 266, 10120: 267, 10123: 268, 10122: 269, 10125: 270,
    10121: 271, 11243: 272, 13076: 273, 13079: 274, 13078: 275, 13077: 276,
    13269: 277, 13524: 278, 13890: 279, 14900: 280, 14899: 281, 14901: 282,
    16717: 283, 16715: 284, 16716: 285, 16718: 286, 17213: 287, 17202: 288,
    18131: 289, 18130: 290, 18535: 291, 19172: 292, 19171: 293, 21893: 294,
    21892: 295, 21898: 296, 21899: 297, 21894: 298, 21891: 299, 23911: 300,
    23913: 301, 23912: 302, 25201: 303, 24604: 304, 25203: 305, 25204: 306,
    25202: 307
}


def build_pdf_mapping():
    """Construit un mapping numéro Bidul -> nom de fichier PDF"""
    pdf_map = {}
    for pdf_file in PDF_FILES:
        pdf_file = pdf_file.strip()
        if not pdf_file:
            continue
        # Ajouter .pdf si manquant
        if not pdf_file.endswith('.pdf'):
            pdf_file += '.pdf'
        # Extraire le numéro du Bidul
        match = re.search(r'Bidul (\d+)', pdf_file)
        if match:
            num = int(match.group(1))
            pdf_map[num] = pdf_file
    return pdf_map


def extract_bidul_number(wp_id, filename):
    """Extrait le numéro Bidul à partir de l'ID WordPress ou du nom de fichier"""
    wp_id = int(wp_id)

    # Vérifier le mapping manuel d'abord
    if wp_id in MANUAL_MAPPING:
        return MANUAL_MAPPING[wp_id]

    filename_lower = filename.lower()

    # Pattern bidul_NNN
    match = re.search(r'bidul[_-]?(\d{1,3})', filename_lower)
    if match:
        return int(match.group(1))

    # Pattern YYYYMM_NNN (ex: 202405_291)
    match = re.search(r'\d{6}[_-](\d{2,3})', filename_lower)
    if match:
        return int(match.group(1))

    # Pattern une-NNN ou UNE-NNN
    match = re.search(r'une[_-]?(\d{2,3})', filename_lower)
    if match:
        return int(match.group(1))

    # Pattern Couv-Bidul-NNN
    match = re.search(r'couv[_-]bidul[_-]?(\d{2,3})', filename_lower)
    if match:
        return int(match.group(1))

    return None


def process_gallery(html_content):
    """Traite la galerie et ajoute les liens PDF"""
    pdf_map = build_pdf_mapping()

    # Regex pour trouver les blocs wp:image
    # Pattern: <!-- wp:image {"id":XXXX,...} --> ... <!-- /wp:image -->
    pattern = r'(<!-- wp:image \{[^}]*"id":(\d+)[^}]*\} -->\s*<figure[^>]*>)(.*?)(</figure>\s*<!-- /wp:image -->)'

    def replace_image_block(match):
        prefix = match.group(1)
        wp_id = int(match.group(2))
        content = match.group(3)
        suffix = match.group(4)

        # Extraire l'URL de l'image pour obtenir le nom de fichier
        img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
        if not img_match:
            return match.group(0)

        img_url = img_match.group(1)
        filename = img_url.split('/')[-1]

        # Obtenir le numéro Bidul
        bidul_num = extract_bidul_number(wp_id, filename)

        if bidul_num is None:
            print(f"  ⚠️  Impossible de déterminer le numéro pour WP ID {wp_id}: {filename}")
            return match.group(0)

        # Trouver le fichier PDF correspondant
        if bidul_num not in pdf_map:
            print(f"  ⚠️  Pas de PDF trouvé pour Bidul #{bidul_num} (WP ID {wp_id})")
            return match.group(0)

        pdf_filename = pdf_map[bidul_num]
        pdf_url = PDF_BASE_URL + quote(pdf_filename)

        # Supprimer figcaption existant s'il y en a un
        content = re.sub(r'<figcaption[^>]*>.*?</figcaption>', '', content, flags=re.DOTALL)

        # Ajouter le nouveau figcaption avec le lien PDF
        figcaption = f'<figcaption class="wp-element-caption"><a href="{pdf_url}" target="_blank" rel="noreferrer noopener">📄 Lire le PDF</a></figcaption>'

        # Insérer avant </figure>
        new_content = content.rstrip() + figcaption

        return prefix + new_content + suffix

    # Appliquer les remplacements
    result = re.sub(pattern, replace_image_block, html_content, flags=re.DOTALL)

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python add_pdf_links.py <gallery.html>")
        print("       Génère gallery_with_pdf.html")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = "gallery_with_pdf.html"

    print(f"📖 Lecture de {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    print("🔗 Ajout des liens PDF...")
    result = process_gallery(content)

    print(f"💾 Sauvegarde dans {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)

    # Stats
    pdf_count = result.count('📄 Lire le PDF')
    print(f"\n✅ Terminé ! {pdf_count} liens PDF ajoutés.")
    print(f"   Fichier généré: {output_file}")


if __name__ == "__main__":
    main()
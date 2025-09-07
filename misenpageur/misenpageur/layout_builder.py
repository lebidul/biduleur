# misenpageur/misenpageur/layout_builder.py

import yaml
from pathlib import Path
from reportlab.lib.units import mm
from .config import Config


def build_layout_with_margins(base_layout_path: str, cfg: Config) -> str:
    """
    Lit un layout YAML de base, applique les marges de la config,
    et écrit un nouveau fichier YAML temporaire.
    Retourne le chemin du nouveau fichier de layout.
    """
    try:
        pdf_layout_config = cfg.pdf_layout
        # Utilise 4mm comme valeur par défaut si non spécifié
        margin = pdf_layout_config.get('page_margin_mm', 4.0) * mm
        spacing = pdf_layout_config.get('section_spacing_mm', 0) * mm
    except AttributeError:
        margin = 4.0 * mm  # Fallback
        spacing = 0

    with open(base_layout_path, 'r', encoding='utf-8') as f:
        layout_data = yaml.safe_load(f)

    page_w = layout_data['page_size']['width']
    page_h = layout_data['page_size']['height']

    # Itérer sur chaque section et recalculer ses coordonnées
    for name, info in layout_data['sections'].items():
        if info['page'] == 1:
            # Page 1 : Grille 2x2
            available_w = page_w - (2 * margin)
            available_h = page_h - (2 * margin)
            section_w = (available_w - spacing) / 2
            section_h = (available_h - spacing) / 2

            # Déterminer la position dans la grille (approximatif, basé sur les X/Y originaux)
            is_left = info['x'] < page_w / 2
            is_bottom = info['y'] < page_h / 2

            if is_left:
                info['x'] = margin
            else:  # is_right
                info['x'] = margin + section_w + spacing

            if is_bottom:
                info['y'] = margin
            else:  # is_top
                info['y'] = margin + section_h + spacing

            info['w'] = section_w
            info['h'] = section_h

        elif info['page'] == 2:
            # Page 2 : 2 colonnes pleine hauteur
            available_w = page_w - (2 * margin)
            available_h = page_h - (2 * margin)
            section_w = (available_w - spacing) / 2
            section_h = available_h  # Toute la hauteur disponible

            is_left = info['x'] < page_w / 2

            if is_left:
                info['x'] = margin
            else:  # is_right
                info['x'] = margin + section_w + spacing

            info['y'] = margin
            info['w'] = section_w
            info['h'] = section_h

    # Écrire le nouveau layout dans un fichier temporaire à côté du layout de base
    temp_layout_path = Path(base_layout_path).parent / "layout_temp_with_margins.yml"
    with open(temp_layout_path, 'w', encoding='utf-8') as f:
        yaml.dump(layout_data, f, sort_keys=False)

    return str(temp_layout_path)
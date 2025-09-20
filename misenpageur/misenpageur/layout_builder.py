# misenpageur/misenpageur/layout_builder.py
import yaml
from pathlib import Path
from reportlab.lib.units import mm
from .config import Config


def build_layout_with_margins(base_layout_path: str, cfg: Config) -> str:
    """
    Applique la marge et l'espacement de la configuration au layout de base
    et génère un fichier de layout temporaire.
    """
    try:
        pdf_layout_config = cfg.pdf_layout
        margin = pdf_layout_config.get('page_margin_mm', 0.0) * mm
        spacing = pdf_layout_config.get('section_spacing_mm', 0.0) * mm
    except AttributeError:
        margin = 0.0
        spacing = 0

    with open(base_layout_path, 'r', encoding='utf-8') as f:
        layout_data = yaml.safe_load(f)

    page_w = layout_data['page_size']['width']
    page_h = layout_data['page_size']['height']

    for name, info in layout_data['sections'].items():
        page = info.get('page', 1)

        # Les sections du poster ne sont pas affectées
        if page > 2:
            continue

        # Le layout de base (sans marge) sert à déterminer la position relative
        is_left_in_base = info['x'] < page_w / 2

        if page == 1:
            is_bottom_in_base = info['y'] < page_h / 2

            # Calcul de la taille de chaque cellule
            section_w = (page_w - (2 * margin) - spacing) / 2
            section_h = (page_h - (2 * margin) - spacing) / 2

            info['w'], info['h'] = section_w, section_h

            # Assigner les nouvelles positions
            if is_left_in_base:
                info['x'] = margin
            else:  # right
                info['x'] = margin + section_w + spacing

            if is_bottom_in_base:
                info['y'] = margin
            else:  # top
                info['y'] = margin + section_h + spacing

        elif page == 2:
            section_w = (page_w - (2 * margin) - spacing) / 2
            section_h = page_h - (2 * margin)

            info['w'], info['h'] = section_w, section_h
            info['y'] = margin

            if is_left_in_base:
                info['x'] = margin
            else:
                info['x'] = margin + section_w + spacing

    temp_layout_path = Path(base_layout_path).parent / "layout_temp_with_margins.yml"
    with open(temp_layout_path, 'w', encoding='utf-8') as f:
        yaml.dump(layout_data, f, sort_keys=False)
    return str(temp_layout_path)
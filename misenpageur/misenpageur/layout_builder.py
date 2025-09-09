# misenpageur/misenpageur/layout_builder.py
import yaml
from pathlib import Path
from reportlab.lib.units import mm
from .config import Config

def build_layout_with_margins(base_layout_path: str, cfg: Config) -> str:
    try:
        pdf_layout_config = cfg.pdf_layout
        margin = pdf_layout_config.get('page_margin_mm', 4.0) * mm
        spacing = pdf_layout_config.get('section_spacing_mm', 0) * mm
    except AttributeError:
        margin = 4.0 * mm
        spacing = 0

    with open(base_layout_path, 'r', encoding='utf-8') as f:
        layout_data = yaml.safe_load(f)

    page_w = layout_data['page_size']['width']
    page_h = layout_data['page_size']['height']

    for name, info in layout_data['sections'].items():
        if info['page'] == 1:
            available_w = page_w - (2 * margin)
            available_h = page_h - (2 * margin)
            section_w = (available_w - spacing) / 2
            section_h = (available_h - spacing) / 2
            is_left = info['x'] < page_w / 2
            is_bottom = info['y'] < page_h / 2
            if is_left: info['x'] = margin
            else: info['x'] = margin + section_w + spacing
            if is_bottom: info['y'] = margin
            else: info['y'] = margin + section_h + spacing
            info['w'], info['h'] = section_w, section_h
        elif info['page'] == 2:
            available_w = page_w - (2 * margin)
            available_h = page_h - (2 * margin)
            section_w = (available_w - spacing) / 2
            section_h = available_h
            is_left = info['x'] < page_w / 2
            if is_left: info['x'] = margin
            else: info['x'] = margin + section_w + spacing
            info['y'] = margin
            info['w'], info['h'] = section_w, section_h
        # IMPORTANT : On ne touche PAS aux sections de la page 3 ici

    temp_layout_path = Path(base_layout_path).parent / "layout_temp_with_margins.yml"
    with open(temp_layout_path, 'w', encoding='utf-8') as f:
        yaml.dump(layout_data, f, sort_keys=False)
    return str(temp_layout_path)
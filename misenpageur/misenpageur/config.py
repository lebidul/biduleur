# misenpageur/misenpageur/config.py
import yaml
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


# ==================== DÉFINITIONS CENTRALISÉES ====================
@dataclass
class BulletConfig:
    show_event_bullet: bool = True
    event_bullet_replacement: str | None = None
    event_hanging_indent: float = 10.0
    bullet_text_indent: float = -3.0  # Décalage puce/texte


@dataclass
class PosterConfig:
    enabled: bool = False
    design: int = 0
    title: str = "L'AGENDA COMPLET"
    font_name_title: str = "Helvetica-Bold"
    title_logo_path: Optional[str] = None
    title_back_color: str = "#7F7F7F"
    font_size_title: float = 36.0
    font_size_min: float = 6.0
    font_size_max: float = 10.0
    font_size_safety_factor: float = 0.98
    background_image_alpha: float = 0.85
    date_spaceBefore: float = 2.0
    date_spaceAfter: float = 2.0
    date_spaceBefore: float = 2.0
    date_spaceAfter: float = 2.0

# ==================== NOUVEAU DATACLASS POUR LA STRATÉGIE DE PACKING ====================
@dataclass
class PackingStrategy:
    """Définit la stratégie à utiliser pour l'arrangement des logos."""
    algorithm: str = 'Global'  # 'Global', 'BFF', 'BNF'
    sort_algo: str = 'AREA'    # 'AREA', 'MAXSIDE', 'HEIGHT', 'WIDTH'

@dataclass
class Config:
    # --- Paths ---
    input_html: str = "input.html"
    output_pdf: str = "output.pdf"
    cover_image: Optional[str] = None
    auteur_couv: Optional[str] = None
    auteur_couv_url: Optional[str] = None
    logos_dir: str = "assets/logos"
    logos_layout: str = "colonnes"
    logos_padding_mm: float = 1.0 # Marge en mm pour le layout optimisé
    logo_hyperlinks: List[Dict[str, str]] = field(default_factory=list)
    ours_md: str = "assets/ours/ours.md"
    ours_svg: str = "assets/ours/ours_template.svg"
    nobr_file: str = "assets/textes/nobr.txt"

    # --- Font & Layout ---
    font_name: str = "ArialNarrow"
    font_size_min: float = 8.0
    font_size_max: float = 12.0
    leading_ratio: float = 1.15
    inner_padding: float = 10.0
    split_min_gain_ratio: float = 0.10

    # --- Spacing ---
    date_spaceBefore: float = 6.0
    date_spaceAfter: float = 3.0
    event_spaceBefore: float = 1.0
    event_spaceAfter: float = 1.0

    # --- Bullets (maintenant des champs directs) ---
    show_event_bullet: bool = True
    event_bullet_replacement: Optional[str] = None
    event_hanging_indent: float = 10.0
    bullet_text_indent: float = -3.0

    # On initialise avec les valeurs par défaut du dataclass PackingStrategy
    packing_strategy: PackingStrategy = field(default_factory=PackingStrategy)

    # --- Dictionnaires pour les configs complexes ---
    date_box: Dict[str, Any] = field(default_factory=dict)
    date_line: Dict[str, Any] = field(default_factory=dict)
    prepress: Dict[str, Any] = field(default_factory=dict)
    section_1: Dict[str, Any] = field(default_factory=dict)
    pdf_layout: Dict[str, Any] = field(default_factory=dict)
    poster: Dict[str, Any] = field(default_factory=dict)

    skip_cover: bool = False

    cucaracha_box: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Charge la configuration depuis un fichier YAML."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            if 'packing_strategy' in data and isinstance(data['packing_strategy'], dict):
                data['packing_strategy'] = PackingStrategy(**data['packing_strategy'])
            return cls.from_dict(data)
        except FileNotFoundError:
            print(f"[WARN] Fichier de configuration introuvable : {path}. Utilisation des valeurs par défaut.")
            return cls()
        except Exception as e:
            print(f"[ERR] Erreur de lecture du fichier de configuration YAML ({path}): {e}")
            raise

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Config":
        """Crée une instance de Config à partir d'un dictionnaire."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in d.items() if k in known_fields}
        return cls(**kwargs)

@dataclass
class DateBoxConfig:
    enabled: bool = False
    padding: float = 2.0
    border_width: float = 0.5
    border_color: str | None = "#000000"
    back_color: str | None = None

@dataclass
class DateLineConfig:
    enabled: bool = False
    width: float = 0.5
    color: str = "#000000"
    gap_after_text_mm: float = 3.0

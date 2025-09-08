# misenpageur/misenpageur/config.py

import yaml
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class Config:
    # --- Paths ---
    input_html: str = "input.html"
    output_pdf: str = "output.pdf"
    output_scribus: str = "output.py"
    cover_image: Optional[str] = None
    auteur_couv: Optional[str] = None
    auteur_couv_url: Optional[str] = None
    logos_dir: str = "assets/logos"
    ours_md: str = "assets/ours/ours.md"

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
    event_spaceAfter_perLine: float = 0.4
    min_event_spaceAfter: float = 1.0
    first_non_event_spaceBefore_in_S5: float = 0.0

    # --- Bullets ---
    show_event_bullet: bool = True
    event_bullet_replacement: Optional[str] = None
    event_hanging_indent: float = 10.0

    # --- DateBox (dict for flexibility) ---
    date_box: Dict[str, Any] = field(default_factory=dict)

    # --- Prepress ---
    prepress: Dict[str, Any] = field(default_factory=dict)

    # --- Section 1 ---
    section_1: Dict[str, Any] = field(default_factory=dict)

    # --- pdf layout (marge globale)
    pdf_layout: Dict[str, Any] = field(default_factory=dict)

    skip_cover: bool = False  # Par défaut, on génère la couverture

    # ==================== MODIFICATION CI-DESSOUS ====================
    # On ajoute la méthode `from_yaml` qui était manquante.
    # C'est cette méthode que votre `main.py` appelle pour charger la configuration.
    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Charge la configuration depuis un fichier YAML."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # Utilise la méthode from_dict pour créer l'objet
            return cls.from_dict(data)

        except FileNotFoundError:
            print(f"[WARN] Fichier de configuration introuvable : {path}. Utilisation des valeurs par défaut.")
            return cls()  # Retourne une config avec les valeurs par défaut
        except Exception as e:
            print(f"[ERR] Erreur de lecture du fichier de configuration YAML ({path}): {e}")
            raise  # Arrête l'exécution car la config est invalide

    # ====================== FIN DE LA MODIFICATION ======================

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Config":
        """Crée une instance de Config à partir d'un dictionnaire."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in d.items() if k in known_fields}
        return cls(**kwargs)
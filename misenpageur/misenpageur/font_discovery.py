# misenpageur/misenpageur/font_discovery.py
# -*- coding: utf-8 -*-
"""
Découverte dynamique des polices système.

Scanne les répertoires de polices (Windows, macOS, Linux, assets projet)
et extrait les métadonnées TTF (nom de famille, style) pour proposer
un large choix de polices dans le GUI.

Utilise un lecteur natif de la table "name" TTF (module struct),
sans dépendance externe (pas de fontTools).
"""
from __future__ import annotations

import logging
import os
import struct
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FontVariant:
    """Un fichier .ttf individuel avec ses métadonnées."""
    path: str
    subfamily: str  # ex: "Regular", "Bold", "Italic", "Bold Italic"


@dataclass
class FontFamily:
    """Une famille de polices avec ses variantes disponibles."""
    family_name: str
    variants: dict[str, FontVariant] = field(default_factory=dict)
    # Clés : "regular", "bold", "italic", "bolditalic"

    @property
    def regular_path(self) -> str | None:
        v = self.variants.get("regular")
        return v.path if v else None


# ---------------------------------------------------------------------------
# Lecteur natif de la table "name" TTF
# ---------------------------------------------------------------------------

_SUBFAMILY_MAP = {
    "regular": "regular",
    "book": "regular",
    "normal": "regular",
    "roman": "regular",
    "medium": "regular",
    "bold": "bold",
    "demibold": "bold",
    "semibold": "bold",
    "heavy": "bold",
    "black": "bold",
    "italic": "italic",
    "oblique": "italic",
    "bold italic": "bolditalic",
    "bold oblique": "bolditalic",
    "bolditalic": "bolditalic",
    "demibold italic": "bolditalic",
    "semibold italic": "bolditalic",
}


def _classify_subfamily(raw: str) -> str:
    """Normalise un nom de sous-famille en : regular, bold, italic, bolditalic."""
    return _SUBFAMILY_MAP.get(raw.strip().lower(), "regular")


def _read_ttf_family(filepath: str) -> tuple[str, str] | None:
    """
    Extrait (family_name, subfamily) depuis un fichier TTF/OTF
    en lisant directement la table 'name' du format OpenType.
    Retourne None si le fichier est illisible ou invalide.
    """
    try:
        with open(filepath, "rb") as f:
            # Lire l'en-tête du fichier
            header = f.read(4)
            if len(header) < 4:
                return None

            version = struct.unpack(">I", header)[0]
            # 0x00010000 = TrueType, 0x4F54544F = OpenType (CFF)
            if version not in (0x00010000, 0x4F54544F):
                # Pourrait être un TTC (collection) - essayer de lire le premier offset
                f.seek(0)
                tag = f.read(4)
                if tag == b"ttcf":
                    # TrueType Collection : lire la version puis le nombre de fonts
                    f.read(4)  # ttc version
                    num_fonts = struct.unpack(">I", f.read(4))[0]
                    if num_fonts == 0:
                        return None
                    offset = struct.unpack(">I", f.read(4))[0]
                    f.seek(offset)
                    header = f.read(4)
                    version = struct.unpack(">I", header)[0]
                    if version not in (0x00010000, 0x4F54544F):
                        return None
                else:
                    return None

            num_tables = struct.unpack(">H", f.read(2))[0]
            f.read(6)  # searchRange, entrySelector, rangeShift

            # Chercher la table "name"
            name_offset = 0
            for _ in range(num_tables):
                tag = f.read(4)
                f.read(4)  # checksum
                offset, length = struct.unpack(">II", f.read(8))
                if tag == b"name":
                    name_offset = offset
                    break

            if not name_offset:
                return None

            # Lire la table "name"
            f.seek(name_offset)
            _format = struct.unpack(">H", f.read(2))[0]
            count = struct.unpack(">H", f.read(2))[0]
            string_offset = struct.unpack(">H", f.read(2))[0]

            family_name: str | None = None
            subfamily: str | None = None

            records = []
            for _ in range(count):
                rec = struct.unpack(">6H", f.read(12))
                records.append(rec)

            # Parcourir les enregistrements pour trouver nameID 1 et 2
            for platformID, encodingID, _langID, nameID, length, offset in records:
                if nameID not in (1, 2):
                    continue

                # Préférer Windows Unicode BMP (platformID=3, encodingID=1)
                if platformID == 3 and encodingID == 1:
                    pos = f.tell()
                    f.seek(name_offset + string_offset + offset)
                    data = f.read(length)
                    f.seek(pos)
                    try:
                        text = data.decode("utf-16-be")
                    except (UnicodeDecodeError, struct.error):
                        continue

                    if nameID == 1 and family_name is None:
                        family_name = text
                    elif nameID == 2 and subfamily is None:
                        subfamily = text

                # Fallback Mac Roman (platformID=1)
                elif platformID == 1 and encodingID == 0:
                    pos = f.tell()
                    f.seek(name_offset + string_offset + offset)
                    data = f.read(length)
                    f.seek(pos)
                    try:
                        text = data.decode("mac-roman")
                    except (UnicodeDecodeError, LookupError):
                        continue

                    if nameID == 1 and family_name is None:
                        family_name = text
                    elif nameID == 2 and subfamily is None:
                        subfamily = text

                if family_name and subfamily:
                    break

            if family_name:
                return (family_name, subfamily or "Regular")
            return None

    except (OSError, struct.error, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Scan des répertoires de polices
# ---------------------------------------------------------------------------

def _scan_directory(
    directory: str,
    families: dict[str, FontFamily],
    seen_paths: set[str],
    max_depth: int = 2,
    current_depth: int = 0,
) -> None:
    """Scanne récursivement un répertoire pour trouver des fichiers .ttf/.ttc."""
    if current_depth > max_depth:
        return

    try:
        entries = list(os.scandir(directory))
    except (PermissionError, OSError):
        return

    for entry in entries:
        try:
            if entry.is_file(follow_symlinks=False):
                if not entry.name.lower().endswith((".ttf", ".ttc")):
                    continue

                abs_path = os.path.abspath(entry.path)
                if abs_path in seen_paths:
                    continue
                seen_paths.add(abs_path)

                info = _read_ttf_family(abs_path)
                if info is None:
                    continue

                family_name, raw_subfamily = info
                subfamily_key = _classify_subfamily(raw_subfamily)

                if family_name not in families:
                    families[family_name] = FontFamily(family_name=family_name)

                # Garder seulement la première variante trouvée pour chaque style
                if subfamily_key not in families[family_name].variants:
                    families[family_name].variants[subfamily_key] = FontVariant(
                        path=abs_path,
                        subfamily=raw_subfamily,
                    )

            elif entry.is_dir(follow_symlinks=False):
                _scan_directory(
                    entry.path, families, seen_paths,
                    max_depth, current_depth + 1,
                )
        except (PermissionError, OSError):
            continue


def _fonts_roots() -> list[str]:
    """Répertoires où chercher les TTF (projet + système). Dupliqué depuis fonts.py pour éviter l'import de reportlab."""
    here = os.path.dirname(__file__)
    roots = [
        os.path.abspath(os.path.join(here, "..", "assets", "fonts")),
        os.path.abspath(os.path.join(here, "..", "..", "assets", "fonts")),
        os.path.abspath(os.path.join(here, "..", "..", "..", "assets", "fonts")),
        "/usr/share/fonts/truetype/dejavu",
        "/usr/local/share/fonts",
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
        "/Library/Fonts",
        "/System/Library/Fonts",
    ]
    env = os.environ.get("BIDUL_FONTS_DIR")
    if env:
        roots.insert(0, env)
    return roots


@lru_cache(maxsize=1)
def _cached_scan() -> dict[str, FontFamily]:
    """Scan mis en cache (exécuté une seule fois par session)."""
    families: dict[str, FontFamily] = {}
    seen_paths: set[str] = set()

    for root_dir in _fonts_roots():
        if not os.path.isdir(root_dir):
            continue
        _scan_directory(root_dir, families, seen_paths)

    log.info(f"Découverte de polices : {len(families)} familles trouvées "
             f"dans {len(seen_paths)} fichiers")
    return families


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def scan_font_directories() -> dict[str, FontFamily]:
    """
    Scanne les répertoires de polices système et projet.
    Retourne un dict family_name -> FontFamily.
    Le résultat est mis en cache après le premier appel.
    """
    return _cached_scan()


def get_available_font_names() -> list[str]:
    """
    Retourne la liste triée de tous les noms de familles de polices disponibles.
    C'est cette fonction qui alimente les comboboxes du GUI.
    """
    families = scan_font_directories()
    return sorted(families.keys(), key=str.casefold)


def get_font_family(name: str) -> FontFamily | None:
    """Recherche une famille de polices par son nom."""
    return scan_font_directories().get(name)


def get_ttf_path_for_pil(family_name: str) -> str | None:
    """
    Retourne le chemin vers le fichier .ttf regular d'une famille.
    Utilisé par PIL ImageFont.truetype() qui a besoin du chemin fichier.
    """
    fam = get_font_family(family_name)
    if fam:
        return fam.regular_path
    return None


def invalidate_cache() -> None:
    """Vide le cache de scan. Appeler si des polices sont installées/supprimées."""
    _cached_scan.cache_clear()

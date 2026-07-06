import os.path
import datetime
import math
import re
from typing import Dict, Any

import logging

log = logging.getLogger(__name__)


# Dictionnaire des noms propres connus (villes + pays) — défini dans
# biduleur/constants.py pour rester accessible par d'autres modules.
# Aliasé localement comme _PROPER_NOUNS_MAP pour conserver la convention
# "module-private" dans format_utils.
from biduleur.constants import PROPER_NOUNS_MAP as _PROPER_NOUNS_MAP

# Compilation d'une regex unique avec alternation, longueur décroissante pour
# que les noms longs (ex. "Le Mans") matchent avant les courts ("Mans").
_PROPER_NOUNS_RE = re.compile(
    r'\b(' + '|'.join(
        re.escape(k) for k in sorted(_PROPER_NOUNS_MAP.keys(), key=len, reverse=True)
    ) + r')\b',
    re.IGNORECASE | re.UNICODE,
)


def _smart_lower(s: str) -> str:
    """
    Lowercase la chaîne en :
    1. Title-Casant les mots intégralement en majuscules (PARIS → Paris,
       BERLIN → Berlin, LE MANS → Le Mans, etc.)
    2. Restaurant la casse correcte des noms de ville/pays connus listés
       dans `_PROPER_NOUNS_MAP` (préserve les majuscules internes type
       "Le Mans", "New York", "Saint-Pétersbourg").

    Exemples :
        "concert in PARIS, France" → "concert in Paris, France"
        "concert à le mans"        → "concert à Le Mans"
        "festival LE MANS"         → "festival Le Mans"
        "MILAN-BERLIN tour"        → "Milan-Berlin tour"
        "Tribute to Mozart"        → "tribute to mozart" (Mozart pas dans le dict)
    """
    if not s:
        return s

    # Étape 1 : Title-Case des mots tout-en-majuscules ; lowercase pour le reste.
    def _process(match: re.Match) -> str:
        word = match.group(0)
        if word.isupper():
            return word.capitalize()
        return word.lower()

    s = re.sub(r'[^\W\d_]+', _process, s, flags=re.UNICODE)

    # Étape 2 : restaurer la casse correcte des noms propres connus.
    def _restore(match: re.Match) -> str:
        return _PROPER_NOUNS_MAP[match.group(0).lower()]

    s = _PROPER_NOUNS_RE.sub(_restore, s)
    return s

from biduleur.constants import GENRE_EVT_SV, GENRE_EVT_CONCERT, GENRE_EVT_IMAGE, OUTPUT_FOLDER_NAME


def _to_str(value: Any) -> str:
    """
    Convertit une valeur en string de manière robuste.
    Gère les types Excel : datetime.time, datetime.datetime, int, float, None, NaN.
    Filtre aussi la chaîne "nan" qui peut apparaître lors de conversions pandas.
    """
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, datetime.time):
        return value.strftime("%Hh%M")
    if isinstance(value, datetime.datetime):
        return value.strftime("%d/%m/%Y %Hh%M")
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if s.strip().lower() == "nan":
        return ""
    return s


def format_artists_styles(*triplets) -> str:
    artistes_styles = ""
    for index, (genre, spectacle, artiste, style) in enumerate(triplets, start=1):
        genre_str = _to_str(genre)
        if not genre_str or genre_str.lower().strip() in ("", "nan"):
            continue

        # Ignorer le genre image (traité séparément dans event_utils)
        if genre_str.lower() == GENRE_EVT_IMAGE:
            continue

        if genre_str.lower() == GENRE_EVT_SV:
            artistes_styles += format_sv(spectacle, artiste, style, index)
        elif genre_str.lower() == GENRE_EVT_CONCERT:
            artistes_styles += format_concert(artiste, style, index)
    return artistes_styles


def format_sv(piece: str, artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    piece = _to_str(piece)
    artiste = _to_str(artiste)
    style = _to_str(style)

    if piece:
        return f"<strong>{signe_plus}\"{capfirst(piece)}\"</strong>{format_artiste(artiste)}{format_style(style)}"
    elif artiste:
        return f"<strong>{signe_plus}{capfirst(artiste)}</strong>{format_style(style)}"
    elif style:
        return f"<strong>{signe_plus}{capfirst(style)}</strong>"
    return ""


def format_concert(artiste: str, style: str, number: int) -> str:
    signe_plus = " + " if number != 1 else ""
    artiste = _to_str(artiste)
    style = _to_str(style)

    if artiste:
        return f"<strong>{signe_plus}{artiste.upper()}</strong>{format_style(style)}"
    elif style:
        return f"<strong>{signe_plus}{capfirst(style)}</strong>"
    return ""


def format_artiste(artiste: str) -> str:
    artiste = _to_str(artiste)
    if not artiste:
        return ""
    return f" {capfirst(artiste)}"


def fmt_virgule(champ: str) -> str:
    champ = _to_str(champ)
    if not champ:
        return ""
    return f"{champ}, "


def _normalize_url(url: str) -> str:
    """Ajoute https:// si l'URL n'a pas de protocole."""
    url = url.strip()
    if not url:
        return url
    if not url.startswith(('http://', 'https://', 'mailto:')):
        return f"https://{url}"
    return url


def fmt_link(*links: str) -> str:
    formatted_links = ""
    for link in links:
        link = _to_str(link)
        if link:
            # Séparer URL et texte d'affichage si format "url|display"
            if '|' in link:
                url, display = link.split('|', 1)
            else:
                url, display = link, link
            url = _normalize_url(url)
            # Raccourcir le texte d'affichage (enlever protocole)
            display_short = display.replace('https://', '').replace('http://', '').rstrip('/')
            formatted_links += f" - <a href=\"{url}\">{display_short}</a>"
    return formatted_links


def fmt_heure(heure) -> str:
    """
    Formate l'heure. Gère datetime.time depuis Excel.
    """
    replacements = {"h00": "h", " h": "h", " a ": " à ", "h.n.c": "hnc"}

    # Conversion robuste en string
    heure_str = _to_str(heure)

    if not heure_str or heure_str.lower().strip() in ("", "nan"):
        return ""

    return f"{format_string(heure_str, replacements, lower=True)}, "


def fmt_prix(prix) -> str:
    replacements = {" a ": " à ", " €": "€", "gratuit": "0€", "t.n.c": "tnc", "h.n.c": "hnc"}
    prix_str = _to_str(prix)
    return format_string(prix_str, replacements, lower=True)


def format_style(style) -> str:
    replacements = {
        "theâtre": "th.", "théâtre": "th.", "theatre": "th.", "théatre": "th.",
        "Theâtre": "Th.", "Théâtre": "Th.", "Théatre": "Th.", "Theâtre": "Th.",
        "Theatre": "Th.", "electro": "électro", "Electro": "Électro",
        "metal": "métal", "Metal": "Métal"
    }
    style_str = _to_str(style)
    if not style_str or style_str.lower().strip() in ("", "nan"):
        return ""
    # _smart_lower : lowercase tout sauf les mots intégralement en majuscules
    # (préserve les noms de ville en caps comme PARIS, NYC, BERLIN…)
    return f" <em>({_smart_lower(format_string(style_str, replacements, lower=False))})</em>"


def format_string(string, replacement_dictionary: Dict, lower: bool = False) -> str:
    """
    Formate une chaîne avec remplacement. Convertit en string si nécessaire.
    """
    string = _to_str(string)

    if not string or string.lower().strip() in ("", "nan"):
        return ""

    if lower:
        string = string.lower()

    for old, new in replacement_dictionary.items():
        string = string.replace(old, new)

    return string


def format_evenement(evenement, style_evenement) -> str:
    evenement_str = _to_str(evenement)
    if not evenement_str or evenement_str.lower().strip() in ("", "nan"):
        return ""
    return f"{evenement_str}{format_style(style_evenement)} // "


def format_info(info, description_info, url_info) -> str:
    info_str = _to_str(info)
    if not info_str or info_str.lower().strip() in ("", "nan"):
        return ""
    return f"<strong>{info_str} - </strong><em>{_to_str(description_info)}</em>{fmt_link(url_info)}"


def format_lieu(lieu) -> str:
    lieu_str = _to_str(lieu)
    if not lieu_str or lieu_str == "Le Mans" or lieu_str.lower().strip() in ("", "nan"):
        return ""
    return f"{lieu_str}, "


def html_to_md(line: str) -> str:
    return (line.replace("<strong>", "**")
            .replace("</strong>", "**")
            .replace("<em>", "*")
            .replace("</em>", "*"))


def capfirst(s):
    try:
        s = _to_str(s)
        return s[:1].upper() + s[1:]
    except:
        return ''


# =============================================================================
# Renderer WordPress "Le Bidul de nuit"
# Génère un HTML autonome (avec <style> scoped) à coller dans l'éditeur code
# WordPress. Structure 4-lignes par event, layout 2-colonnes (65/35),
# fond nuit à gauche + fond rose pâle à droite pour la sidebar
# Festivals + Coups de cœur.
# =============================================================================

def _wp_esc(s: Any) -> str:
    """HTML-escape robuste."""
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;").replace('"', "&quot;"))


def _wp_link_or_text(raw: Any) -> str:
    """Rend 'url|display' comme <a>, sinon texte échappé."""
    s = _to_str(raw).strip()
    if not s:
        return ""
    if "|" in s:
        url, display = s.split("|", 1)
        return f'<a href="{_wp_esc(_normalize_url(url))}" style="color:inherit;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px">{_wp_esc(display)}</a>'
    return _wp_esc(s)


def _wp_split_date(date_str: str) -> tuple:
    """
    'Vendredi 3' → ('Ven.', '03')
    'Mercredi 1er' → ('Mer.', '01')
    'Dimanche 12 Juillet 2025' → ('Dim.', '12')
    Retourne (nom_court_avec_point, num_padded).
    """
    m = re.match(r'^\s*(\w+)\s+(\d+)', _to_str(date_str))
    if not m:
        return (_to_str(date_str), "")
    weekday = m.group(1)[:3].capitalize() + "."
    num = m.group(2).zfill(2)
    return (weekday, num)


def _wp_extract_spectacles(record: Dict, spectacle_col_sets) -> list:
    """
    Retourne une liste de (label_bold, style_brackets) pour un event.
    Chaque tuple = ('"Spec" Artiste', 'style') ou ('Artiste', 'style').
    Filtre les lignes vides et les rows image.
    """
    items = []
    for cs in spectacle_col_sets or []:
        genre = _to_str(record.get(cs['genre'], '')).strip()
        spectacle = _to_str(record.get(cs['spectacle'], '')).strip()
        artist = _to_str(record.get(cs['artiste'], '')).strip()
        style = _to_str(record.get(cs['style'], '')).strip()

        if not (spectacle or artist):
            continue
        if genre.lower() == GENRE_EVT_IMAGE:
            continue

        # Convention Bidul : les artistes de "concert" sont TOUJOURS en majuscules,
        # les événements "sv" (spectacle vivant) gardent leur casse (capfirst).
        if genre.lower() == GENRE_EVT_CONCERT and artist:
            artist = artist.upper()
        elif artist:
            artist = capfirst(artist)

        parts = []
        if spectacle:
            parts.append(f'"{capfirst(spectacle)}"')
        if artist:
            parts.append(artist)
        label = " ".join(parts)
        if label:
            items.append((label, style))
    return items


def _wp_render_event(record: Dict) -> str:
    """Rend un event en HTML 4-lignes selon le design 'Le Bidul de nuit'."""
    from biduleur.constants import (FESTIVAL, STYLE_FESTIVAL, LIEU, VILLE,
                                     HORAIRE, PRIX)

    festival = _to_str(record.get(FESTIVAL, '')).strip()
    style_fest = _to_str(record.get(STYLE_FESTIVAL, '')).strip()
    lieu = _to_str(record.get(LIEU, '')).strip()
    ville = _to_str(record.get(VILLE, '')).strip()
    horaire = _to_str(record.get(HORAIRE, '')).strip()
    prix = fmt_prix(record.get(PRIX, '')).strip()

    spectacle_col_sets = record.get('_spectacle_col_sets', [])
    items = _wp_extract_spectacles(record, spectacle_col_sets)

    lines = []

    # Ligne 1 (optionnelle) : Festival [+ (style)]
    if festival:
        if style_fest:
            lines.append(
                f'<div class="bdul-nuit-festival">{_wp_esc(festival)} '
                f'<em>({_wp_esc(style_fest)})</em></div>'
            )
        else:
            lines.append(f'<div class="bdul-nuit-festival">{_wp_esc(festival)}</div>')

    # Ligne 2 : artistes/spectacles bold + [style italic] séparés par +
    if items:
        parts = []
        for label, style in items:
            part = f'<strong>{_wp_esc(label)}</strong>'
            if style:
                part += f' <span class="bdul-nuit-style">[{_wp_esc(style)}]</span>'
            parts.append(part)
        artists_html = '<span class="bdul-nuit-plus">+</span>'.join(parts)
        lines.append(f'<div class="bdul-nuit-artists">{artists_html}</div>')

    # Ligne 3 : Lieu, Ville (italic)
    lieu_ville_parts = [p for p in (lieu, ville) if p and p.lower() != 'nan']
    if lieu_ville_parts:
        lines.append(
            f'<div class="bdul-nuit-lieu">{_wp_esc(", ".join(lieu_ville_parts))}</div>'
        )

    # Ligne 4 : Heure — Tarif
    when_parts = []
    if horaire and horaire.lower() != 'nan':
        when_parts.append(_wp_esc(horaire))
    if prix and prix.lower() != 'nan':
        when_parts.append(f'<span class="bdul-nuit-price">{_wp_esc(prix)}</span>')
    if when_parts:
        lines.append(f'<div class="bdul-nuit-when">{" — ".join(when_parts)}</div>')

    return f'<div class="bdul-nuit-event">{"".join(lines)}</div>'


def _wp_render_sidebar_item(record: Dict) -> str:
    """Rend un item de sidebar (FESTIVALS ou Coups de cœur) : titre + desc + lien."""
    from biduleur.constants import FESTIVAL, STYLE_FESTIVAL
    title = _to_str(record.get(FESTIVAL, '')).strip()
    if not title:
        return ""
    desc = _to_str(record.get(STYLE_FESTIVAL, '')).strip()
    # NOM SPECTACLE 1 = potentiellement un URL (format hyperlink)
    spectacle_col_sets = record.get('_spectacle_col_sets', [])
    url_raw = ''
    if spectacle_col_sets:
        url_raw = _to_str(record.get(spectacle_col_sets[0]['spectacle'], '')).strip()
    link_html = ""
    if url_raw:
        link_html = f' <span class="bdul-nuit-side-link">{_wp_link_or_text(url_raw)}</span>'
    return (
        f'<div class="bdul-nuit-side-item">'
        f'<h4>{_wp_esc(title)}</h4>'
        f'<p>{_wp_esc(desc)}{link_html}</p>'
        f'</div>'
    )


def _wp_render_month_title(month_labels: dict, summer_mode: bool) -> str:
    """Titre principal en haut de la colonne de gauche."""
    if summer_mode and month_labels.get(0) and month_labels.get(1):
        # Ex. "JUILLET · AOÛT" en mode été
        m1 = month_labels[0].capitalize()
        m2 = month_labels[1].capitalize()
        return f'{_wp_esc(m1[:3])}<span class="accent">·</span>{_wp_esc(m2[:3])}'
    label = month_labels.get(0) or ""
    if label:
        return f'{_wp_esc(label.capitalize())}'
    return ''


# CSS scoped à `.bdul-agenda-nuit` — inline dans le <style> pour survivre au
# copier-coller dans l'éditeur code de WordPress. Toutes les couleurs et
# proportions sont fixées ; la sortie est self-contained.
_WP_NUIT_CSS = """
.bdul-agenda-nuit *, .bdul-agenda-nuit *::before, .bdul-agenda-nuit *::after { box-sizing: border-box; }
.bdul-agenda-nuit {
  --nt-bg-left: #17172E;
  --nt-bg-right: #EDE8D3;
  --nt-ink-dark: #F0EAD6;
  --nt-ink-light: #17172E;
  --nt-muted-dark: #948CB5;
  --nt-muted-light: #6E6474;
  --nt-accent: #C7F03A;
  --nt-accent-side: #B84A2E;
  --nt-rule-dark: rgba(240, 234, 214, 0.14);
  --nt-rule-light: rgba(23, 23, 46, 0.12);
  display: flex; flex-wrap: wrap;
  font-family: -apple-system, "Helvetica Neue", "Segoe UI", Roboto, Arial, sans-serif;
  font-size: 14px; line-height: 1.5;
  color: var(--nt-ink-dark);
  max-width: 100%; margin: 0 auto;
  overflow-wrap: break-word; word-wrap: break-word;
}
/* Optimisation mobile : le thème WP contraint la largeur, on l'accepte
   comme une "card" avec bords arrondis et paddings internes réduits pour
   maximiser l'espace utile au contenu. */
@media (max-width: 720px) {
  .bdul-agenda-nuit {
    border-radius: 6px !important;
    overflow: hidden !important;
  }
  .bdul-agenda-nuit .bdul-nuit-left,
  .bdul-agenda-nuit .bdul-nuit-right {
    padding: 24px 16px !important;
  }
  .bdul-agenda-nuit .bdul-nuit-month-sep {
    font-size: 32px !important;
    padding-top: 14px !important;
    margin: 16px 0 10px !important;
  }
  .bdul-agenda-nuit .bdul-nuit-day-marker {
    flex: 0 0 48px !important;
    min-width: 48px !important;
  }
  .bdul-agenda-nuit .bdul-nuit-day-num {
    font-size: 36px !important;
  }
  .bdul-agenda-nuit .bdul-nuit-day {
    gap: 12px !important;
  }
}

.bdul-agenda-nuit .bdul-nuit-left {
  background: var(--nt-bg-left); color: var(--nt-ink-dark);
  padding: 32px 28px 36px;
  flex: 3 1 380px; min-width: 0;
}
.bdul-agenda-nuit .bdul-nuit-right {
  background: var(--nt-bg-right); color: var(--nt-ink-light);
  padding: 32px 22px 36px;
  flex: 1 1 240px; min-width: 0;
}

.bdul-agenda-nuit .bdul-nuit-month {
  font-family: Impact, "Antonio", "Bebas Neue", "Franklin Gothic Bold", "Arial Narrow", sans-serif;
  font-weight: 400; font-size: 56px; line-height: 0.85;
  letter-spacing: 0.02em; text-transform: uppercase;
  color: var(--nt-ink-dark); margin: 0 0 4px;
}
.bdul-agenda-nuit .bdul-nuit-month .accent { color: var(--nt-accent); }
.bdul-agenda-nuit .bdul-nuit-year {
  display: block; font-size: 11px; letter-spacing: 0.32em; text-transform: uppercase;
  color: var(--nt-muted-dark); margin-bottom: 28px;
}

.bdul-agenda-nuit .bdul-nuit-month-sep {
  font-family: Impact, "Antonio", "Bebas Neue", "Arial Narrow", sans-serif;
  font-weight: 400; font-size: 44px; line-height: 0.9;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--nt-accent); margin: 24px 0 12px; padding-top: 20px;
  border-top: 1px solid var(--nt-rule-dark);
}
.bdul-agenda-nuit .bdul-nuit-month-sep:first-child { margin-top: 0; padding-top: 0; border-top: 0; }

/* Layout jour = flexbox (plus tolérant que grid dans WP) */
.bdul-agenda-nuit .bdul-nuit-day {
  display: flex; align-items: flex-start; gap: 18px;
  padding: 18px 0; border-top: 1px solid var(--nt-rule-dark);
}
.bdul-agenda-nuit .bdul-nuit-day:first-of-type { border-top: 0; padding-top: 0; }
.bdul-agenda-nuit .bdul-nuit-day-marker {
  display: flex; flex-direction: column; align-items: flex-start;
  line-height: 0.9;
  flex: 0 0 62px; min-width: 62px;
}
.bdul-agenda-nuit .bdul-nuit-day-name {
  font-size: 10px; letter-spacing: 0.24em; text-transform: uppercase;
  color: var(--nt-muted-dark); margin-bottom: 4px;
}
.bdul-agenda-nuit .bdul-nuit-day-num {
  font-family: Impact, "Antonio", "Bebas Neue", "Franklin Gothic Bold", "Arial Narrow", sans-serif;
  font-weight: 400; font-size: 48px; line-height: 0.85;
  color: var(--nt-accent); letter-spacing: -0.02em;
}
.bdul-agenda-nuit .bdul-nuit-day-events {
  display: flex; flex-direction: column; gap: 14px;
  flex: 1 1 auto; min-width: 0;
}

.bdul-agenda-nuit .bdul-nuit-event { padding-left: 20px; position: relative; }
.bdul-agenda-nuit .bdul-nuit-event::before {
  content: "✧"; position: absolute; left: 0; top: 3px;
  color: var(--nt-accent); font-size: 14px;
}
.bdul-agenda-nuit .bdul-nuit-event + .bdul-nuit-event {
  padding-top: 14px; border-top: 1px solid var(--nt-rule-dark);
}
.bdul-agenda-nuit .bdul-nuit-festival {
  font-size: 12px; color: var(--nt-muted-dark); margin-bottom: 3px;
}
.bdul-agenda-nuit .bdul-nuit-festival em { font-style: italic; }
.bdul-agenda-nuit .bdul-nuit-artists {
  margin-bottom: 3px; font-size: 14px; color: var(--nt-ink-dark);
}
.bdul-agenda-nuit .bdul-nuit-artists strong { font-weight: 700; letter-spacing: 0.01em; }
.bdul-agenda-nuit .bdul-nuit-style {
  font-weight: 400; font-style: italic; color: var(--nt-muted-dark); font-size: 13px;
}
.bdul-agenda-nuit .bdul-nuit-plus {
  color: var(--nt-accent); font-weight: 700; padding: 0 5px;
}
.bdul-agenda-nuit .bdul-nuit-lieu {
  font-style: italic; color: var(--nt-muted-dark); font-size: 12px; margin-bottom: 3px;
}
.bdul-agenda-nuit .bdul-nuit-when {
  font-size: 12px; color: var(--nt-ink-dark);
}
.bdul-agenda-nuit .bdul-nuit-price {
  color: var(--nt-accent); font-weight: 700;
}

.bdul-agenda-nuit .bdul-nuit-side-title {
  font-family: Impact, "Antonio", "Bebas Neue", "Arial Narrow", sans-serif;
  font-weight: 400; font-size: 32px; letter-spacing: 0.02em;
  text-transform: uppercase; color: var(--nt-ink-light); margin: 0 0 4px;
  line-height: 0.9;
}
.bdul-agenda-nuit .bdul-nuit-side-title .dot { color: var(--nt-accent-side); }
.bdul-agenda-nuit .bdul-nuit-side-tag {
  font-size: 10px; letter-spacing: 0.24em; text-transform: uppercase;
  color: var(--nt-muted-light); margin-bottom: 18px; display: block;
}
.bdul-agenda-nuit .bdul-nuit-side-item {
  margin-bottom: 18px; padding-left: 14px; position: relative;
}
.bdul-agenda-nuit .bdul-nuit-side-item::before {
  content: "◆"; position: absolute; left: 0; top: 2px; color: var(--nt-accent-side); font-size: 9px;
}
.bdul-agenda-nuit .bdul-nuit-side-item h4 {
  margin: 0 0 3px; font-size: 13px; font-weight: 700; color: var(--nt-ink-light);
}
.bdul-agenda-nuit .bdul-nuit-side-item p {
  margin: 0; font-size: 12px; line-height: 1.45; color: var(--nt-muted-light); font-style: italic;
}
.bdul-agenda-nuit .bdul-nuit-side-item p a {
  color: inherit; word-break: break-all; overflow-wrap: anywhere;
}
.bdul-agenda-nuit .bdul-nuit-side-hr {
  border: 0; height: 1px; background: var(--nt-rule-light); margin: 26px 0;
}
"""


def render_wordpress_agenda(filename: str, filename_2: str = None,
                             summer_mode: bool = False,
                             summer_separator_style: str = "banner") -> str:
    """
    Génère l'HTML complet 'Le Bidul de nuit' à coller dans un bloc HTML
    de l'éditeur WordPress. Sortie 2-colonnes (65% / 35%), fond nuit à gauche
    (agenda datés), fond rose pâle à droite (Festivals + Coups de cœur).

    Args:
        filename: chemin du xlsx principal.
        filename_2: chemin du 2ᵉ xlsx optionnel (mode Bidul d'été).
        summer_mode: si True, insère un séparateur de mois entre les 2 sources.
        summer_separator_style: 'banner' (défaut) — le style 'inline' n'est
            pas encore supporté par ce renderer.

    Returns:
        HTML complet (document autonome avec <!DOCTYPE>, prêt à coller).
    """
    from biduleur.csv_utils import read_and_sort_file, _month_label_from_filename
    from biduleur.constants import DATE, COLONNE_INFO, COLONNE_FESTIVALS
    from itertools import groupby

    records = read_and_sort_file(filename, filename_2=filename_2)
    if not records:
        return ""

    month_labels = {
        0: _month_label_from_filename(filename) or "",
        1: _month_label_from_filename(filename_2) or "" if filename_2 else "",
    }

    festivals_records = [r for r in records if r.get(DATE) == COLONNE_FESTIVALS]
    info_records = [r for r in records if r.get(DATE) == COLONNE_INFO]
    daily_records = [
        r for r in records
        if r.get(DATE) not in (COLONNE_FESTIVALS, COLONNE_INFO)
        and _to_str(r.get(DATE, '')).strip()  # ignore les lignes DATE vide (parasites)
    ]

    # Grouper les events datés par (_source_index, DATE) sans casser l'ordre.
    days_grouped = []
    for (src, date), group in groupby(
        daily_records,
        key=lambda r: (r.get('_source_index', 0) or 0, r.get(DATE, '')),
    ):
        days_grouped.append((src, date, list(group)))

    # Colonne gauche : titre + séparateurs de mois + jours
    left_parts = []
    current_src = None
    for src, date, events in days_grouped:
        if summer_mode and src != current_src:
            label = month_labels.get(src) or f"MOIS {src + 1}"
            # Styles inline en secours (WP peut filtrer le <style>).
            is_first = (current_src is None)
            border_style = "" if is_first else "border-top:1px solid rgba(240,234,214,0.14);padding-top:20px;"
            margin_style = "margin:0 0 12px;" if is_first else "margin:24px 0 12px;"
            left_parts.append(
                f'<div class="bdul-nuit-month-sep" '
                f'style="font-family:Impact,\'Antonio\',\'Bebas Neue\',\'Arial Narrow\',sans-serif;'
                f'font-weight:400;font-size:44px;line-height:0.9;letter-spacing:0.06em;'
                f'text-transform:uppercase;color:#C7F03A;{margin_style}{border_style}">'
                f'{_wp_esc(label)}</div>'
            )
            current_src = src
        weekday, num = _wp_split_date(date)
        events_html = "\n".join(_wp_render_event(e) for e in events)
        # Styles inline en secours si WP filtre le <style> pour certains
        # containers (Gutenberg peut appliquer des règles de reset agressives).
        left_parts.append(
            f'<div class="bdul-nuit-day" style="display:flex;align-items:flex-start;gap:18px;padding:18px 0;border-top:1px solid rgba(240,234,214,0.14);">'
            f'<div class="bdul-nuit-day-marker" style="display:flex;flex-direction:column;flex:0 0 62px;min-width:62px;line-height:0.9;">'
            f'<span class="bdul-nuit-day-name" style="font-size:10px;letter-spacing:0.24em;text-transform:uppercase;color:#948CB5;margin-bottom:4px;">{_wp_esc(weekday)}</span>'
            f'<span class="bdul-nuit-day-num" style="font-family:Impact,\'Antonio\',\'Bebas Neue\',sans-serif;font-size:48px;line-height:0.85;color:#C7F03A;letter-spacing:-0.02em;">{_wp_esc(num)}</span>'
            f'</div>'
            f'<div class="bdul-nuit-day-events" style="display:flex;flex-direction:column;gap:14px;flex:1 1 auto;min-width:0;">{events_html}</div>'
            f'</div>'
        )

    left_html = "\n".join(left_parts)

    # Colonne droite : Festivals + Coups de cœur
    right_parts = []
    if festivals_records:
        right_parts.append('<div class="bdul-nuit-side-title">Festi<span class="dot">·</span>vals</div>')
        right_parts.append('<span class="bdul-nuit-side-tag">Sélection du mois</span>')
        for r in festivals_records:
            item = _wp_render_sidebar_item(r)
            if item:
                right_parts.append(item)
    if festivals_records and info_records:
        right_parts.append('<hr class="bdul-nuit-side-hr">')
    if info_records:
        right_parts.append('<div class="bdul-nuit-side-title">Coups<span class="dot">·</span>Cœur</div>')
        right_parts.append('<span class="bdul-nuit-side-tag">En bref</span>')
        for r in info_records:
            item = _wp_render_sidebar_item(r)
            if item:
                right_parts.append(item)
    right_html = "\n".join(right_parts)

    # Titre principal (mois ou mois·mois)
    main_title = _wp_render_month_title(month_labels, summer_mode)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Agenda du Bidul</title>
<style>{_WP_NUIT_CSS}</style>
</head>
<body style="margin:0;padding:0;">
<div class="bdul-agenda-nuit" style="display:flex;flex-wrap:wrap;max-width:100%;font-family:-apple-system,'Helvetica Neue','Segoe UI',Roboto,Arial,sans-serif;font-size:14px;line-height:1.5;color:#F0EAD6;overflow-wrap:break-word;word-wrap:break-word;">
  <section class="bdul-nuit-left" style="background:#17172E;color:#F0EAD6;padding:32px 28px 36px;flex:3 1 380px;min-width:0;">
    {left_html}
  </section>
  <aside class="bdul-nuit-right" style="background:#EDE8D3;color:#17172E;padding:32px 22px 36px;flex:1 1 240px;min-width:0;">
    {right_html}
  </aside>
</div>
</body>
</html>
"""


def _prettify_agenda_html(body: str) -> str:
    """
    Transforme le body brut de l'agenda en HTML prêt-à-coller dans WordPress :
    - remplace les placeholders internes ({{SUBEV}}, {{MONTH:NOM}})
    - grossit et colore les en-têtes de date
    - transforme les séparateurs de mois en gros bandeaux
    Les styles sont INLINE pour survivre à un copier-coller ou à un éditeur
    WordPress qui filtre les <style>.
    """
    import re as _re

    # 1) Séparateur de mois (mode Bidul d'été) : <p>{{MONTH:NOM}}</p> → gros bandeau
    body = _re.sub(
        r'<p[^>]*>\s*\{\{MONTH:([^}]+)\}\}\s*</p>',
        r'<h2 style="text-align:center;font-family:Arial,sans-serif;font-size:2em;'
        r'color:#b8860b;letter-spacing:0.2em;margin:1.5em 0 0.8em;padding:0.3em 0;'
        r'border-top:3px double #b8860b;border-bottom:3px double #b8860b;">\1</h2>',
        body,
    )

    # 2) En-têtes de date agenda : identifiés par color:blue dans le style inline.
    #    Le format brut ferme via </spanp></p> — on normalise en </p>.
    body = _re.sub(
        r'<p[^>]*color:blue[^>]*>([^<]+?)</spanp></p>',
        r'<p style="font-family:Arial,sans-serif;font-size:1.15em;font-weight:bold;'
        r'text-align:center;color:#ffffff;background:#b8860b;padding:0.35em 0.5em;'
        r'margin:1.2em 0 0.5em;border-radius:3px;line-height:1.3;">\1</p>',
        body,
    )
    # Certains en-têtes de date en agenda n'ont pas le </spanp> foireux : idem sans.
    body = _re.sub(
        r'<p[^>]*color:blue[^>]*>([^<]+?)</p>',
        r'<p style="font-family:Arial,sans-serif;font-size:1.15em;font-weight:bold;'
        r'text-align:center;color:#ffffff;background:#b8860b;padding:0.35em 0.5em;'
        r'margin:1.2em 0 0.5em;border-radius:3px;line-height:1.3;">\1</p>',
        body,
    )

    # 3) Sous-events festival : {{SUBEV}} → indentation + puce ▸
    body = body.replace(
        '{{SUBEV}}',
        '<span style="display:inline-block;width:2.2em">&nbsp;</span>'
        '<span style="color:#b8860b;font-weight:bold">▸</span>&nbsp;'
    )

    # 4) Sous-en-tête de festival (rare mais possible)
    body = body.replace('{{SUBFEST}}', '')

    # 5) Placeholder image (au cas où) : on laisse pour l'instant en clair
    #    (l'agenda WordPress n'utilise pas les images inline)

    # 6) Line-height 0.25 illisible en HTML web → on rehausse.
    body = body.replace('line-height:0.25', 'line-height:1.4')

    return body


def output_html_file(html_body: str, original_file_name: str = None, output_filename: str = None,
                     output_folder_name: str = OUTPUT_FOLDER_NAME, pretty: bool = False):
    pre, ext = os.path.splitext(os.path.basename(original_file_name))
    if not output_filename:
        output_filename = os.path.join(output_folder_name, pre + ".html")
    else:
        output_filename = os.path.join(output_folder_name, output_filename)

    body = _prettify_agenda_html(html_body) if pretty else html_body

    # En mode pretty : wrapper responsive + charset explicite pour un rendu propre
    # une fois collé dans une page WordPress.
    if pretty:
        html_string = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="fr">
<head>
<meta charset="UTF-8"/>
<title>Agenda</title>
</head>
<body style="max-width:820px;margin:1.5em auto;padding:0 1em;color:#222;
font-family:'Arial Narrow',Arial,sans-serif;line-height:1.4;">
{body}
</body>
</html>
"""
    else:
        html_string = f"""<!DOCTYPE html>
<html  xmlns="http://www.w3.org/1999/xhtml" xml:lang="fr">
<head>
<meta charset="UTF-8"/>
<body>
{body}
</body>
</head>
</html>
"""
    open(output_filename, 'w+', encoding='utf-8').write(html_string)
    log.info(f"Évènements mises en forme et exportés das le fichier: {output_filename}")
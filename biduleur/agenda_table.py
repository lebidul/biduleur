"""Agenda HTML « tableau filtrable » pour la page WordPress d'un numéro du Bidul.

Pipeline : fichier tapage (xlsx/csv) -> read_and_sort_file -> événements
normalisés -> enrichissement des lieux via data/lieu.csv -> fragment HTML
autonome (CSS + JS inline, tout préfixé ``bdl-``) à coller dans un bloc
« HTML personnalisé » de WordPress.
"""
import argparse
import csv
import html
import json
import logging
import re
import unicodedata
from datetime import date
from pathlib import Path

from biduleur.constants import (
    COLONNE_FESTIVALS, COLONNE_INFO, DATE, FESTIVAL, HORAIRE, LIEU, PRIX,
    STYLE_FESTIVAL, VILLE,
)
from biduleur.csv_utils import JOURS_SEMAINE, MOIS_FR, _month_label_from_filename, read_and_sort_file
from biduleur.format_utils import _to_str, fmt_prix

log = logging.getLogger(__name__)

LIEUX_CSV = Path(__file__).parent / "data" / "lieu.csv"
TYPES = {"c": "Concert", "sv": "Spectacle"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ---------------------------------------------------------------- lieux
def load_lieux(path: Path = LIEUX_CSV) -> dict[tuple[str, str], dict]:
    """Index (nom normalisé, ville normalisée) -> ligne du CSV."""
    index: dict[tuple[str, str], dict] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ville = _norm(row["ville"])
            for nom in (row["nom"], row.get("nom_normalise", "")):
                if nom:
                    index.setdefault((_norm(nom), ville), row)
    return index


def _lieu_info(row: dict | None) -> dict:
    """Extrait ce qui s'affiche sous le nom du lieu."""
    if not row:
        return {}
    voie = " ".join(p for p in (row["adresse_numero"], row["adresse_voie"]) if p)
    adresse = ", ".join(p for p in (voie, " ".join(p for p in (row["code_postal"], row["ville"]) if p)) if p)
    info = {"adresse": adresse if voie else "",
            "site": row["site"], "facebook": row["facebook"], "instagram": row["instagram"]}
    return {k: v for k, v in info.items() if v}


# ------------------------------------------------------------ événements
def _year_month(path: str) -> tuple[int, int]:
    """Mois/année depuis le nom du fichier : AAAAMM_... ou nom de mois + année."""
    name = Path(path).name
    m = re.match(r"(\d{4})(\d{2})", name)
    if m and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)), int(m.group(2))
    label = _month_label_from_filename(path)
    y = re.search(r"(20\d{2})", name)
    if label and y:
        num = next(n for n, mois in MOIS_FR.items() if mois.upper() == label)
        return int(y.group(1)), num
    raise ValueError("Impossible de déterminer le mois du fichier : son nom doit commencer par AAAAMM "
                     "(ex. 202601_tapage_biduleur_Janvier_2026.xlsx).")


def _clean_url(v: str) -> str:
    return v.split("|", 1)[0] if "|" in v else v


def build_events(records: list[dict], periods: list[tuple[int, int]], lieux: dict) -> tuple[list[dict], list[dict]]:
    """Retourne (événements datés, « coups de coeur / en bref »)."""
    events, brefs = [], []
    for rec in records:
        g = lambda k: _to_str(rec.get(k, "")).strip()
        titres, types = [], []
        for s in rec.get("_spectacle_col_sets", []):
            genre = g(s["genre"]).lower()
            nom, artiste, style = g(s["spectacle"]), g(s["artiste"]), g(s["style"])
            if genre == "img":
                continue
            if "|" in nom:  # lien Excel -> "url|texte"
                nom = nom.split("|", 1)[1]
            titre = f"« {nom} » {artiste}".strip() if nom else artiste
            if titre or style:
                titres.append({"titre": titre or style, "style": style if titre else ""})
            if genre in TYPES:
                types.append(TYPES[genre])
        festival = g(FESTIVAL)
        item = {
            "festival": festival if festival.lower() != "nan" else "",
            "festival_style": g(STYLE_FESTIVAL),
            "titres": titres,
            "types": sorted(set(types)),
            "heure": g(HORAIRE) if g(HORAIRE).lower() != "inc" else "",
            "lieu": g(LIEU), "ville": g(VILLE) or "Le Mans",  # ville vide = Le Mans
            "prix": "" if g(PRIX).lower() == "nan" else fmt_prix(rec.get(PRIX)),
        }
        day = str(rec.get("Day", ""))
        label = g(DATE)
        if label == COLONNE_INFO or not day.isdigit():
            item["label"] = label
            brefs.append(item)
            continue
        year, month = periods[min(int(rec.get("_source_index") or 0), len(periods) - 1)]
        d = date(year, month, int(day))
        item["date"] = d.isoformat()
        item["jour"] = f"{JOURS_SEMAINE[d.weekday()]} {d.day}"
        item["lieu_info"] = _lieu_info(lieux.get((_norm(item["lieu"]), _norm(item["ville"]))))
        events.append(item)
    return events, brefs


# ------------------------------------------------------------- rendu HTML
def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _lieu_cell(ev: dict) -> str:
    out = [f'<div class="bdl-lieu-nom">{_e(ev["lieu"] or ev["ville"])}</div>']
    if ev["lieu"] and ev["ville"]:
        out.append(f'<div class="bdl-ville">{_e(ev["ville"])}</div>')
    info = ev["lieu_info"]
    if info.get("adresse"):
        out.append(f'<div class="bdl-adresse">{_e(info["adresse"])}</div>')
    links = [(label, info[k]) for label, k in
             (("Site", "site"), ("Facebook", "facebook"), ("Instagram", "instagram"))
             if info.get(k)]
    if links:
        out.append('<ul class="bdl-liens">' + "".join(
            f'<li><a href="{_e(u)}" target="_blank" rel="noopener">{label}</a></li>' for label, u in links) + "</ul>")
    return "".join(out)


def _event_cell(ev: dict) -> str:
    out = []
    if ev["festival"]:
        sub = f' <span class="bdl-style">({_e(ev["festival_style"])})</span>' if ev["festival_style"] else ""
        out.append(f'<div class="bdl-festival">{_e(ev["festival"])}{sub}</div>')
    for t in ev["titres"]:
        sub = f' <span class="bdl-style">{_e(t["style"])}</span>' if t["style"] else ""
        out.append(f'<div class="bdl-titre">{_e(t["titre"])}{sub}</div>')
    return "".join(out)


def _row(ev: dict) -> str:
    prix = ev["prix"]
    gratuit = prix.strip().lower() in ("0€", "0 €", "gratuit", "entrée libre")
    search = _norm(" ".join([ev["festival"], ev["lieu"], ev["ville"], ev["prix"]]
                            + [t["titre"] + t["style"] for t in ev["titres"]]))
    heure = f'<span class="bdl-heure">{_e(ev["heure"])}</span>' if ev["heure"] else ""
    types = "".join(f'<span class="bdl-badge bdl-badge-{"c" if t == "Concert" else "sv"}">{t}</span>'
                    for t in ev["types"])
    return (
        f'<tr data-date="{ev["date"]}" data-ville="{_e(ev["ville"])}" data-types="{_e(",".join(ev["types"]))}" '
        f'data-gratuit="{int(gratuit)}" data-search="{search}">'
        f'<td data-label="Date"><span class="bdl-jour">{_e(ev["jour"])}</span>{heure}</td>'
        f'<td data-label="Événement">{_event_cell(ev)}</td>'
        f'<td data-label="Lieu">{_lieu_cell(ev)}</td>'
        f'<td data-label="Type">{types}</td>'
        f'<td data-label="Prix" class="bdl-prix">{_e(prix)}</td></tr>'
    )


def _bref(item: dict) -> str:
    main = item["festival"] or " + ".join(t["titre"] for t in item["titres"])
    sub = f' <span class="bdl-style">{_e(item["festival_style"])}</span>' if item["festival_style"] else ""
    where = ", ".join(p for p in (item["lieu"], item["ville"]) if p)
    return f'<li><strong>{_e(_clean_url(main))}</strong>{sub}{" — " + _e(where) if where else ""}</li>'


def render_html(events: list[dict], brefs: list[dict], title: str) -> str:
    villes = sorted({e["ville"] for e in events if e["ville"]}, key=_norm)
    n_ville = lambda v: sum(1 for e in events if e["ville"] == v)
    opts = "".join(f'<option value="{_e(v)}">{_e(v)} ({n_ville(v)})</option>' for v in villes)
    rows = "\n".join(_row(e) for e in events)
    bref_html = ""
    if brefs:
        bref_html = ('<section class="bdl-brefs"><h3>Coups de cœur et en bref</h3><ul>'
                     + "".join(_bref(b) for b in brefs) + "</ul></section>")
    tpl = (Path(__file__).parent / "templates" / "agenda_table.html").read_text(encoding="utf-8")
    return (tpl.replace("{{TITLE}}", _e(title)).replace("{{VILLES}}", opts)
               .replace("{{ROWS}}", rows).replace("{{BREFS}}", bref_html)
               .replace("{{COUNT}}", str(len(events))))


def render_agenda_table(input_file: str, filename_2: str | None = None,
                        lieux_csv: Path = LIEUX_CSV) -> tuple[str, dict]:
    """Fragment HTML prêt à coller dans un bloc « HTML personnalisé » + statistiques.

    filename_2 : 2ᵉ fichier optionnel (Bidul d'été, 2 mois sur une même page).
    """
    files = [input_file] + ([filename_2] if filename_2 else [])
    periods = [_year_month(f) for f in files]
    records = read_and_sort_file(input_file, filename_2=filename_2)
    if records is None:
        raise ValueError("Lecture du fichier impossible")
    events, brefs = build_events(records, periods, load_lieux(lieux_csv))
    mois = " – ".join(MOIS_FR[m].capitalize() for _, m in periods)
    title = f"Agenda {mois} {periods[-1][0]}"
    # Pas de ligne vide : l'éditeur WordPress y insérerait des <p>/<br> (wpautop).
    fragment = "\n".join(l for l in render_html(events, brefs, title).splitlines() if l.strip())
    stats = {"evenements": len(events), "brefs": len(brefs),
             "lieux_enrichis": sum(1 for e in events if e["lieu_info"]),
             "lieux_sans_correspondance": sorted({f'{e["lieu"]} ({e["ville"]})' for e in events if not e["lieu_info"]})}
    log.info("Agenda tableau : %s", json.dumps({k: v for k, v in stats.items() if k != "lieux_sans_correspondance"}))
    return fragment, stats


def generate(input_file: str, output_file: str, filename_2: str | None = None) -> dict:
    fragment, stats = render_agenda_table(input_file, filename_2)
    Path(output_file).write_text(fragment, encoding="utf-8")
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Génère l'agenda HTML en tableau filtrable")
    ap.add_argument("input_file")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    s = generate(a.input_file, a.out)
    print(f"{s['evenements']} événements, {s['lieux_enrichis']} avec lieu enrichi, {s['brefs']} en bref")
    print("Sans correspondance :", *s["lieux_sans_correspondance"], sep="\n  ")

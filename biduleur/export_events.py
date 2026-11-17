"""Export JSON des événements normalisés (contrat avec bidul.publisher).

Le fichier produit (`events.json`) est la seule interface entre le biduleur et le
publisher : valeurs déjà normalisées (lieu via alias, heure, prix, ville par défaut),
dates ISO, texte brut sans markup. Voir docs/publisher-split.md.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from .agenda_table import _year_month, build_events, load_lieux, LIEUX_CSV
from .csv_utils import read_and_sort_file

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def build_payload(events: list[dict], brefs: list[dict], periods: list[tuple[int, int]],
                  generated_at: datetime | None = None) -> dict:
    """Assemble le document JSON (séparé de l'I/O pour être testable)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "months": [f"{y:04d}-{m:02d}" for y, m in periods],
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "events": sorted(events, key=lambda e: (e["date"], e.get("heure", ""))),
        "brefs": brefs,
    }


def export_events_json(input_file: str, output_file: str, filename_2: str | None = None,
                       lieux_csv: Path = LIEUX_CSV) -> dict:
    """Lit le tapage (CSV/XLS/XLSX), écrit `output_file` et retourne le document."""
    files = [input_file] + ([filename_2] if filename_2 else [])
    periods = [_year_month(f) for f in files]
    records = read_and_sort_file(input_file, filename_2=filename_2)
    if records is None:
        raise ValueError("Lecture du fichier impossible")
    events, brefs = build_events(records, periods, load_lieux(lieux_csv))
    payload = build_payload(events, brefs, periods)
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("events.json : %d événements, %d en bref -> %s", len(events), len(brefs), output_file)
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Exporte les événements du tapage en events.json")
    ap.add_argument("input_file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--input-2", help="2e fichier (Bidul d'été)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    p = export_events_json(a.input_file, a.out, a.input_2)
    print(f"{len(p['events'])} événements, {len(p['brefs'])} en bref -> {a.out}")

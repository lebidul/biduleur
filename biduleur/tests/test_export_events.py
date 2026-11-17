"""Tests du contrat events.json (biduleur -> bidul.publisher)."""
import json
from datetime import datetime

from biduleur.agenda_table import LieuIndex, build_events
from biduleur.constants import DATE, HORAIRE, LIEU, PRIX, VILLE
from biduleur.export_events import SCHEMA_VERSION, build_payload

SPECTACLES = [{"genre": "GENRE 1", "spectacle": "NOM SPECTACLE 1", "artiste": "ARTISTE 1", "style": "STYLE 1"}]


def _record(day, heure, lieu="Le Oﬀ", ville="", prix="10"):
    return {"Day": day, DATE: f"Samedi {day}", HORAIRE: heure, LIEU: lieu, VILLE: ville, PRIX: prix,
            "GENRE 1": "c", "NOM SPECTACLE 1": "", "ARTISTE 1": "Les Frelons", "STYLE 1": "rock",
            "_spectacle_col_sets": SPECTACLES, "_source_index": 0}


def test_payload_contract():
    events, brefs = build_events([_record("14", "20h30"), _record("7", "18h00")], [(2026, 3)], LieuIndex([], {}))
    p = build_payload(events, brefs, [(2026, 3)], generated_at=datetime(2026, 3, 1, 10, 0, 0))
    assert p["schema_version"] == SCHEMA_VERSION
    assert p["months"] == ["2026-03"]
    assert p["generated_at"] == "2026-03-01T10:00:00"
    # trié par date, dates ISO, ville vide = Le Mans, pas de markup
    assert [e["date"] for e in p["events"]] == ["2026-03-07", "2026-03-14"]
    assert p["events"][0]["ville"] == "Le Mans"
    assert p["events"][0]["types"] == ["Concert"]
    assert "{{" not in json.dumps(p) and "<" not in json.dumps(p)


def test_payload_is_json_serializable():
    events, brefs = build_events([_record("1", "")], [(2026, 3)], LieuIndex([], {}))
    json.dumps(build_payload(events, brefs, [(2026, 3)]), ensure_ascii=False)

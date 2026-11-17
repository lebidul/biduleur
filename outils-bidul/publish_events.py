"""Publie events.json d'un tapage comme asset d'une release GitHub `events-AAAA-MM`.

Usage : python outils-bidul/publish_events.py 202603_tapage_biduleur_Mars_2026.xlsx [--dry-run]

Le tag `events-AAAA-MM` ne correspond pas à `bidul-v*` : il ne déclenche donc pas le build de
l'exécutable. Republier le même mois remplace l'asset (--clobber). Le publisher télécharge
toujours `events.json` de la release du mois voulu. Nécessite la CLI `gh` authentifiée.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biduleur.export_events import export_events_json  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_file")
    ap.add_argument("--dry-run", action="store_true", help="exporte et affiche la commande sans publier")
    a = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "events.json"
        payload = export_events_json(a.input_file, str(out))
        tag = "events-" + "-".join(payload["months"])
        print(f"{len(payload['events'])} événements, {len(payload['brefs'])} en bref -> release {tag}")

        exists = subprocess.run(["gh", "release", "view", tag], capture_output=True).returncode == 0
        cmd = (["gh", "release", "upload", tag, str(out), "--clobber"] if exists else
               ["gh", "release", "create", tag, str(out), "--title", f"Événements {' / '.join(payload['months'])}",
                "--notes", "events.json pour bidul.publisher (schema v%d)" % payload["schema_version"]])
        print(" ".join(cmd))
        if a.dry_run:
            return 0
        return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())

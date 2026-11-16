# Split de `publisher/` vers `bidul.publisher` (option 2 : format intermédiaire)

## Principe

Le publisher ne dépend plus du code du biduleur. Le biduleur produit un fichier
**`events.json`** (contrat de données) ; le publisher le lit, filtre par date,
remplit un template HTML/SVG, rend en PNG et publie sur Instagram.

```
tapage xlsx → [biduleur] → events.json ──(artefact / URL / dépôt de données)──▶ [bidul.publisher] → PNG → Instagram
```

## Contrat `events.json` (v1)

```json
{
  "schema_version": 1,
  "month": "2026-03",
  "generated_at": "2026-02-27T10:00:00",
  "events": [
    {
      "date": "2026-03-14",
      "festival": null,
      "titre": "…",
      "genre": "Concert",
      "lieu": "Le Oﬀ",
      "ville": "Le Mans",
      "horaire": "20h30",
      "prix": "10€",
      "spectacles": [{"genre": "Théâtre", "nom": "…"}],
      "lien": "https://…"
    }
  ]
}
```

- Valeurs **déjà normalisées** (heure, prix, ville, lieu via alias) : le publisher n'a aucune
  logique de parsing.
- Dates ISO, pas de « Lundi 22 » à re-parser.
- Pas de HTML ni de markup `{{SUBEV}}` : le texte est brut, la mise en forme appartient aux templates.
- `schema_version` incrémenté à toute rupture.

## Côté biduleur (ce repo)

1. Nouveau module `biduleur/export_events.py` : `export_events_json(tapage_path, out_path)`,
   réutilisant les fonctions de normalisation de `event_utils` / `format_utils` / `LieuIndex`.
2. Option CLI `--out-events-json` (`biduleur.main` et `cli.py`) + case dans Le Truc (optionnel).
3. Test : golden file sur un tapage d'exemple.
4. Suppression de `publisher/`, des workflows `publisher.cron.yml` / `daily-script.yml`,
   des constantes `publisher` de `constants.py`, après le split.

## Côté `bidul.publisher` (nouveau repo)

```
bidul.publisher/
├── publisher/ (instagram, email_notifier, renderer, events.py)
├── templates/ (*.html.j2 ou *.svg + assets, polices)
├── tests/
├── requirements.txt   # instagrapi, html2image/playwright, jinja2, python-dotenv
└── .github/workflows/daily.yml
```

- `events.py` : lecture/validation de `events.json` (dataclass, vérif de `schema_version`).
- Suppression de `gsheet_client` : la source devient `events.json`. À arbitrer : récupérer le
  fichier depuis une release GitHub du biduleur, un Drive, ou un commit dans un dépôt de données.
- `daily_post.py`, `agenda.py`, `main.v0.py`, `templates.py` (templates inline obsolètes) :
  réécrits ou abandonnés au profit de templates fichiers.

## Extraction du repo (avec historique)

```bash
git clone bidul.biduleur bidul.publisher && cd bidul.publisher
git filter-repo --subdirectory-filter publisher
```

Avant de publier : relire l'historique extrait pour les secrets (voir ci-dessous).

## ⚠️ Secrets à traiter avant/pendant le split

- `publisher/constants.py` contient en clair un `SMTP_PASSWORD` (mot de passe d'application Gmail)
  committé dans l'historique de `master` (déjà poussé sur GitHub). **À révoquer** dans le compte
  Google, puis lire les valeurs depuis l'environnement (secrets GitHub, déjà prévus dans le workflow).
- Un simple `filter-repo` conserve ce secret dans l'historique du nouveau repo : soit purger
  (`git filter-repo --replace-text`), soit repartir sans historique. Révoquer reste obligatoire.
- `gcp_creds_biduleur.json` est non suivi à la racine : s'assurer qu'il ne soit jamais ajouté
  (`.gitignore` ne couvre que `gcp_creds.json`).

## Décisions ouvertes

1. Transport de `events.json` (release GitHub, Drive, dépôt de données).
2. Conserver l'historique dans le nouveau repo, ou repartir propre ?
3. Moteur de rendu des templates : `html2image` (actuel) ou Playwright (plus fiable, SVG/polices).

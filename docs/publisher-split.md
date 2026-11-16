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
├── requirements.txt   # instagrapi, playwright, jinja2, python-dotenv
└── .github/workflows/daily.yml
```

- `events.py` : lecture/validation de `events.json` (dataclass, vérif de `schema_version`).
- Suppression de `gsheet_client` : la source devient `events.json`. Le fichier est récupéré depuis
  une release GitHub du biduleur.
- `daily_post.py`, `agenda.py`, `main.v0.py`, `templates.py` (templates inline obsolètes) :
  réécrits ou abandonnés au profit de templates fichiers.

## Création du repo (sans historique)

Nouveau repo `bidul.publisher` initialisé par un commit propre : copier uniquement les fichiers
retenus (sans `constants.py` ni secrets), puis supprimer `publisher/` du biduleur.

## ⚠️ Secrets à traiter avant/pendant le split

- `publisher/constants.py` contient en clair un `SMTP_PASSWORD` (mot de passe d'application Gmail)
  committé dans l'historique de `master` (déjà poussé sur GitHub). **À révoquer** dans le compte
  Google, puis lire les valeurs depuis l'environnement (secrets GitHub, déjà prévus dans le workflow).
- Le nouveau repo repart sans historique, donc sans ce secret. Révoquer reste obligatoire,
  l'historique du biduleur le contenant toujours.
- `gcp_creds_biduleur.json` est non suivi à la racine : s'assurer qu'il ne soit jamais ajouté
  (`.gitignore` ne couvre que `gcp_creds.json`).

## Décisions (tranchées)

1. **Transport** : `events.json` est publié en asset d'une release GitHub du biduleur ; le
   publisher le télécharge (`gh release download` / API) au lancement.
2. **Historique** : on repart propre (pas de `filter-repo`) : le nouveau repo démarre d'un
   commit initial à partir des fichiers utiles, ce qui évite d'emporter le secret SMTP.
   La révocation du mot de passe reste obligatoire.
3. **Rendu** : Playwright (Chromium) à la place de `html2image`.

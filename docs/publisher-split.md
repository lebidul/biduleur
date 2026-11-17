# Split de `publisher/` vers `bidul.publisher` (option 2 : format intermédiaire)

## Principe

Le publisher ne dépend plus du code du biduleur. Le biduleur produit un fichier
**`events.json`** (contrat de données) ; le publisher le lit, filtre par date,
remplit un template HTML/SVG, rend en PNG et publie sur Instagram.

```
tapage xlsx → [biduleur] → events.json ──(asset de release events-AAAA-MM)──▶ [bidul.publisher] → PNG → Instagram
```

## Contrat `events.json` (v1) — implémenté

Produit par `biduleur/export_events.py` (réutilise `agenda_table.build_events`).

```json
{
  "schema_version": 1,
  "months": ["2026-03"],
  "generated_at": "2026-02-27T10:00:00",
  "events": [
    {
      "date": "2026-03-01",
      "jour": "Dimanche 1",
      "festival": "Octavius",
      "festival_style": "",
      "titres": [{"titre": "« … » Artiste", "style": "récital violon"}],
      "types": ["Concert"],
      "heure": "16h00",
      "lieu": "Chapelle St Denis du Tertre",
      "ville": "Saint-Mars-la-Brière",
      "prix": "au chapeau",
      "lieu_info": {"adresse": "…", "site": "…", "facebook": "…", "instagram": "…"}
    }
  ],
  "brefs": [{"label": "Coups de coeur et en bref", "titres": [], "lieu": "", "ville": "Le Mans"}]
}
```

- Valeurs **déjà normalisées** (heure, prix, ville par défaut « Le Mans », lieu enrichi via
  alias) : le publisher n'a aucune logique de parsing. `lieu_info.instagram` sert à taguer les lieux.
- Dates ISO, événements triés par date puis heure.
- Pas de HTML ni de markup `{{SUBEV}}` : texte brut, la mise en forme appartient aux templates.
- `schema_version` incrémenté à toute rupture ; le publisher refuse une version inconnue.
- `titres[].titre` peut contenir des guillemets français « … » ; `heure`, `prix`, `lieu_info` peuvent être vides.

## Transport : release GitHub `events-AAAA-MM`

- `python outils-bidul/publish_events.py <tapage.xlsx>` exporte puis crée (ou met à jour avec
  `--clobber`) la release `events-AAAA-MM` avec `events.json` en asset (CLI `gh` requise).
- Le tag `events-*` ne correspond pas à `bidul-v*` : il ne déclenche pas le build de l'exécutable.
- Le publisher télécharge l'asset du mois voulu (`gh release download events-AAAA-MM -p events.json`
  ou l'API GitHub avec un token en lecture).
- Les tapages ne sont pas dans le repo, d'où une publication manuelle plutôt qu'en CI.

## Côté biduleur (ce repo)

1. ✅ `biduleur/export_events.py` : `export_events_json(tapage_path, out_path)` (PR #115).
2. ✅ Option CLI `--out-events-json` dans `biduleur.main` ; `cli.py` et Le Truc : à brancher si utile.
3. ✅ Tests du contrat : `biduleur/tests/test_export_events.py` ; vérifié sur Mars 2026
   (201 événements, 5 en bref).
4. ✅ `outils-bidul/publish_events.py` : publication en release.
5. À faire après la mise en service du nouveau repo : supprimer `publisher/`, les workflows
   `publisher.cron.yml` / `daily-script.yml` et les constantes `publisher` de `constants.py`.

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

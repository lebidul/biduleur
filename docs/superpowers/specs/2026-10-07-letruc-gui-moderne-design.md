# Le Truc — nouvelle interface moderne et guidée

Date : 2026-10-07 — Statut : design validé, en attente de relecture

## Objectif

Rendre l'interface de Le Truc plus moderne et utilisable par des personnes peu familières avec l'outil.
Cas d'usage cible : chaque mois, la même recette — charger le fichier Excel du mois, vérifier quelques options, exporter.
Les réglages avancés sont rarement touchés.

## Constats sur l'existant

- `leTruc/app.py` : une seule page défilante (canvas + scrollbar, 900×900) contenant ~13 sections (`widgets.create_all`) et plus de 80 variables Tk.
- Tout est visible en même temps ; rien ne distingue l'essentiel de l'avancé.
- Le chemin du PDF et les dossiers de sortie sont demandés explicitement.
- Fin de traitement : `VictoryWindow` ; les erreurs sont celles, techniques, du pipeline.

## Décisions

| Sujet | Décision |
|---|---|
| Base technique | Rester sur Tkinter, ajouter le thème **ttkbootstrap** (pas customtkinter : sa racine `CTk` est incompatible avec `TkinterDnD.Tk` utilisé pour le glisser-déposer) |
| Écran principal | **Colonne unique en 3 blocs** : ① Fichier, ② Options du mois, ③ Création |
| Réglages avancés | **Fenêtre séparée à onglets**, ouverte par un bouton ⚙ |
| Retour utilisateur | Progression en français + écran de fin avec actions ; erreurs traduites en langage simple |

## Architecture

- `leTruc/app.py` : conserve `_initialize_variables` (les `*_var` gardent leurs noms), applique le thème ttkbootstrap, assemble les écrans. Plus de canvas défilant sur l'écran principal.
- `leTruc/ui/main_screen.py` (nouveau) : les trois blocs.
- `leTruc/ui/advanced_window.py` (nouveau) : fenêtre à onglets Polices, Dates, Stories, Images, Abréviations, Logos, Expérimental. Reprend d'abord les fonctions `_create_*_section` de `widgets.py` (déplacées, non réécrites), puis nettoyage.
- `leTruc/ui/paths.py` (nouveau) : déduction des chemins par défaut (fonction pure, testable).
- `leTruc/ui/errors.py` (nouveau) : traduction des erreurs connues en messages simples (fonction pure, testable).
- `leTruc/callbacks.py`, `leTruc/_helpers.py` : inchangés autant que possible ; seuls les points d'accroche aux widgets déplacés sont adaptés.

### Écran principal

**① Votre fichier** — zone de glisser-déposer + « parcourir ». Après sélection, vérification immédiate : « ✔ N événements détectés » ou message d'erreur clair (colonne absente, fichier illisible).

**② Options du mois** — couverture (activer, image, auteur), Cucaracha (type et contenu), titre du poster, taille de police (auto/forcée), sorties (PDF, Stories, HTML), mode Bidul d'été (révèle le second fichier). Chaque option a une phrase d'explication visible sous son libellé.

**③ Création** — bouton « Créer le Bidul ! », bouton Stop pendant l'exécution.

Pied de page : ⚙ Réglages avancés, Importer/Exporter config, « Comment ça marche ? » (ouvre le guide utilisateur existant).

### Fenêtre Réglages avancés

Onglets par thème, contenant tout ce qui n'est pas dans l'écran principal. Y sont aussi : Mode debug, Reset config, bouton « Rétablir les réglages d'origine » (valeurs de `config.yml`).

## Valeurs par défaut

- Chemin du PDF, SVG, Stories, HTML : déduits du fichier Excel (dossier du fichier, nom basé sur le mois), modifiables dans les réglages avancés.
- Réglages avancés : valeurs de `config.yml` via `_load_cfg_defaults`.

## Retour utilisateur

- Progression : libellés d'étapes en français (lecture du fichier, mise en page, export…) alimentés par la file de résultats existante (`result_queue`).
- Fin : écran avec « Ouvrir le PDF » et « Ouvrir le dossier » (remplace `VictoryWindow`).
- Erreurs : message simple + détail technique replié + bouton « Copier le détail ».

## Tests

- pytest : `paths.py` (déduction des chemins, caractères spéciaux, fichier sans mois dans le nom) et `errors.py` (erreurs connues → messages ; erreur inconnue → message générique + détail).
- Vérification manuelle de la GUI à chaque étape (lancement `python run_gui.py`, drag-and-drop, génération complète, import/export config).
- Vérifier que le build PyInstaller (`bidul.spec`) embarque ttkbootstrap.

## Migration

1. Thème ttkbootstrap + nouvel écran principal ; la fenêtre avancée reprend les sections existantes telles quelles.
2. Chemins par défaut, retour utilisateur et messages d'erreur.
3. Nettoyage de `widgets.py` et suppression de ce qui devient mort (canvas défilant, `VictoryWindow`).

## Hors périmètre

- Changement de framework (web, Qt).
- Refonte du pipeline biduleur/misenpageur.
- Gestion multi-profils / niveaux d'utilisateurs.

## Risques

- Les callbacks lisent des widgets par attribut sur `app` : le déplacement des sections doit préserver ces noms.
- ttkbootstrap peut modifier le rendu de widgets `tk.*` mélangés aux `ttk.*` ; à vérifier visuellement.
- Compatibilité de ttkbootstrap avec `TkinterDnD.Tk` à valider dès l'étape 1.

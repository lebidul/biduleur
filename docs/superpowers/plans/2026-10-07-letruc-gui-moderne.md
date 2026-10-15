# Le Truc — interface moderne et guidée : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la longue page unique de Le Truc par un écran en 3 blocs (Fichier / Options du mois / Création) + une fenêtre « Réglages avancés » à onglets, avec thème moderne, retours d'erreur lisibles et écran de fin avec actions.

**Architecture:** On garde Tkinter, `TkinterDnD.Tk` comme racine et **toutes les variables `*_var` et tous les attributs `app.<widget>`** lus par `callbacks.py`. Les fonctions `_create_*_section(parent, app, ui_row)` de `widgets.py` ne sont pas réécrites : on les appelle avec un autre `parent` (bloc ② de l'écran principal, ou onglet de la fenêtre avancée). La fenêtre avancée est créée **tout de suite** (masquée) pour que `callbacks.assign_all` trouve ses widgets. Deux modules purs (`errors.py`, `inputcheck.py`) portent la logique testable.

**Tech Stack:** Python 3.10+, Tkinter/ttk, tkinterdnd2, ttkbootstrap (thème), pytest, PyInstaller 6.6.0.

## Global Constraints

- Python 3.10+ (syntaxe de type moderne : `str | None`) ; logging via `logging.getLogger(__name__)` ; texte d'interface **en français**.
- Ne **jamais** renommer une variable `*_var` d'`app.py` ni un attribut `app.<widget>` utilisé dans `leTruc/callbacks.py` (ex. `input_button`, `run_button`, `drop_zone_label`, `cucaracha_frame`, `html_label`, `reset_config_btn`, `cover_checkbox`…).
- Les modules purs `leTruc/ui/errors.py` et `leTruc/ui/inputcheck.py` n'importent **pas** tkinter.
- Le dépôt contient beaucoup de fichiers non suivis (xlsx, bases, `config.json`, etc.) : **toujours `git add` des chemins explicites**, jamais `git add .` / `-A`.
- Chaque message de commit se termine par la ligne : `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Travail sur une branche `feature/letruc-gui-moderne` (jamais directement sur `master`).
- Vérification GUI manuelle : `python run_gui.py` (une fenêtre doit s'ouvrir sans trace d'erreur dans la console).
- Mise à jour de `RELEASE_NOTES.md` / `TODO.md` **avant** le commit final de la fonctionnalité.

## Écarts assumés par rapport à la spec (à répercuter dans la spec en Task 8)

1. **`paths.py` abandonné** : `_default_paths_from_input` (`leTruc/_helpers.py:737`) déduit déjà tous les chemins, et `on_pick_input` / `on_drop_input_file` les appliquent. On factorise seulement ce code dupliqué (Task 5).
2. **`VictoryWindow` conservée** (animation de cartes qui tombent) : on y *ajoute* « Ouvrir le PDF » / « Ouvrir le dossier » au lieu de la remplacer.
3. **Mode Bidul d'été** : la case à cocher reste dans le bloc ① (sous la zone de dépôt) car `_create_input_section` crée ensemble la case, la 2ᵉ zone de dépôt et le choix de séparateur ; la 2ᵉ zone doit apparaître juste sous la première.
4. **Mode debug conservé** : il pilote encore le masquage des réglages techniques (Ours, Logos, Images inline, Expérimental, marges…). Il est déplacé dans l'onglet « Général » et l'onglet « Expert » n'apparaît qu'en mode debug. Seule la case « Avec couv' » devient toujours visible (elle est dans le bloc ②).
5. **Canvas défilant conservé** pour le bloc central (couverture + Cucaracha rendent l'écran plus haut que 900 px) ; la barre d'action reste fixe en bas.

## File Structure

| Fichier | Action | Responsabilité |
|---|---|---|
| `leTruc/ui/__init__.py` | Create | Package vide |
| `leTruc/ui/errors.py` | Create | `explain_error(message) -> ExplainedError` (pur) |
| `leTruc/ui/inputcheck.py` | Create | `check_input_file(path) -> InputCheck` (pur, réutilise `biduleur.csv_utils`) |
| `leTruc/ui/components.py` | Create | `block()`, `hint()`, `register_wheel_canvas()`, `scrollable_tab()` |
| `leTruc/ui/advanced_window.py` | Create | Fenêtre « Réglages avancés » à onglets, créée masquée |
| `leTruc/ui/main_screen.py` | Create | Blocs ① et ② de l'écran principal |
| `leTruc/ui/error_dialog.py` | Create | Boîte d'erreur lisible avec détail replié |
| `leTruc/app.py` | Modify | Thème, assemblage, barre d'action, molette, résultats |
| `leTruc/callbacks.py` | Modify | `_apply_input_file` (DRY + contrôle du fichier), `cover_checkbox` toujours visible |
| `leTruc/victory.py` | Modify | Boutons « Ouvrir le PDF / dossier » |
| `leTruc/widgets.py` | Modify | Suppression de `create_all` (Task 8) |
| `leTruc/tests/test_errors.py`, `test_inputcheck.py` | Create | Tests pytest |
| `leTruc/requirements.txt`, `bidul.spec` | Modify | Dépendance ttkbootstrap + données PyInstaller |
| `RELEASE_NOTES.md`, `TODO.md`, spec | Modify | Documentation |

---

### Task 1: Branche, dépendance ttkbootstrap et test de compatibilité

**Files:**
- Modify: `.gitignore`, `leTruc/requirements.txt`

- [ ] **Step 1: Créer la branche et ignorer le dossier de maquettes**

```bash
git checkout -b feature/letruc-gui-moderne
printf '\n.superpowers/\n' >> .gitignore
```

- [ ] **Step 2: Ajouter la dépendance** (le fichier est en ASCII/CRLF et sa dernière ligne `Pillow` n'a pas de saut de ligne final)

```bash
printf '\r\nttkbootstrap\r\n' >> leTruc/requirements.txt
pip install ttkbootstrap
```

- [ ] **Step 3: Vérifier la compatibilité ttkbootstrap + TkinterDnD.Tk** (risque n°1 de la spec)

Run :
```bash
python - <<'EOF'
from tkinterdnd2 import TkinterDnD, DND_FILES
import ttkbootstrap as tb
from tkinter import ttk
root = TkinterDnD.Tk()
style = tb.Style(theme="flatly")
f = ttk.Frame(root); f.pack()
f.drop_target_register(DND_FILES)
ttk.Button(f, text="ok").pack()
root.update_idletasks()
print("theme:", style.theme.name)
root.destroy()
EOF
```
Expected: `theme: flatly`, sans exception.
Si ça échoue : noter l'erreur, **ne pas continuer** — le code de `app.py` (Task 5) est déjà écrit avec un repli (`try/except`), mais il faut alors décider avec l'utilisateur d'un autre thème (ex. `clam` + couleurs manuelles).

- [ ] **Step 4: Commit**

```bash
git add .gitignore leTruc/requirements.txt
git commit -m "build(gui): ajouter ttkbootstrap et ignorer .superpowers/"
```

---

### Task 2: `errors.py` — messages d'erreur lisibles (TDD)

**Files:**
- Create: `leTruc/ui/__init__.py` (vide), `leTruc/ui/errors.py`
- Test: `leTruc/tests/test_errors.py`

**Interfaces:**
- Produces: `ExplainedError(headline: str, detail: str)` (dataclass gelée) et `explain_error(message: str | None) -> ExplainedError`. `detail == ""` signifie « rien à replier ».

- [ ] **Step 1: Écrire les tests qui échouent** — `leTruc/tests/test_errors.py`

```python
from leTruc.ui.errors import explain_error


def test_message_deja_lisible_reste_tel_quel():
    msg = "Colonnes manquantes dans le fichier :\n\n• DATE"
    result = explain_error(msg)
    assert result.headline == msg
    assert result.detail == ""


def test_message_vide():
    result = explain_error("")
    assert "inconnue" in result.headline
    assert result.detail == ""


def test_message_none():
    assert explain_error(None).detail == ""


def test_traceback_generique_replie_le_detail():
    msg = (
        "ZeroDivisionError: division by zero\n\n"
        "Traceback (most recent call last):\n  File \"x.py\", line 1\n"
        "ZeroDivisionError: division by zero"
    )
    result = explain_error(msg)
    assert result.headline.startswith("Une erreur inattendue est survenue")
    assert "ZeroDivisionError: division by zero" in result.headline
    assert "Traceback" not in result.headline
    assert result.detail == msg


def test_keyerror_devient_colonne_introuvable():
    msg = "KeyError: 'LIEU'\n\nTraceback (most recent call last):\n  ...\nKeyError: 'LIEU'"
    result = explain_error(msg)
    assert "colonne" in result.headline.lower()
    assert "LIEU" in result.headline
    assert result.detail == msg
```

- [ ] **Step 2: Lancer pour constater l'échec**

Run: `python -m pytest leTruc/tests/test_errors.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'leTruc.ui'`).

- [ ] **Step 3: Implémenter** — créer `leTruc/ui/__init__.py` vide, puis `leTruc/ui/errors.py` :

```python
# leTruc/ui/errors.py
"""Traduit les messages d'erreur du pipeline en texte compréhensible (module pur, sans tkinter)."""
import re
from dataclasses import dataclass

_TRACEBACK_MARK = "Traceback (most recent call last)"
_KEYERROR = re.compile(r"^KeyError: ['\"](?P<col>.+)['\"]\s*$")


@dataclass(frozen=True)
class ExplainedError:
    headline: str  # phrase simple affichée à l'utilisateur
    detail: str    # détail technique à replier ("" s'il n'y en a pas)


def explain_error(message: str | None) -> ExplainedError:
    text = (message or "").strip()
    if not text:
        return ExplainedError("Une erreur inconnue est survenue.", "")

    # Les erreurs prévues (ValueError de biduleur, PermissionError…) sont déjà rédigées en français.
    if _TRACEBACK_MARK not in text:
        return ExplainedError(text, "")

    first_line = text.splitlines()[0].strip()
    match = _KEYERROR.match(first_line)
    if match:
        return ExplainedError(
            f"Une colonne attendue est introuvable dans le fichier : {match['col']}.", text
        )
    return ExplainedError(f"Une erreur inattendue est survenue ({first_line}).", text)
```

- [ ] **Step 4: Lancer les tests**

Run: `python -m pytest leTruc/tests/test_errors.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add leTruc/ui/__init__.py leTruc/ui/errors.py leTruc/tests/test_errors.py
git commit -m "feat(gui): traduction des erreurs du pipeline en messages lisibles"
```

---

### Task 3: `inputcheck.py` — vérification immédiate du fichier Excel (TDD)

**Files:**
- Create: `leTruc/ui/inputcheck.py`
- Test: `leTruc/tests/test_inputcheck.py`

**Interfaces:**
- Consumes: `biduleur.csv_utils._read_and_prepare_one_file(filename) -> (DataFrame, list)` (lève `ValueError` avec un message en français) et `REQUIRED_BASE_COLUMNS`.
- Produces: `InputCheck(ok: bool, message: str, event_count: int = 0)` et `check_input_file(path: str) -> InputCheck`.

- [ ] **Step 1: Écrire les tests** — `leTruc/tests/test_inputcheck.py`

```python
import pandas as pd

from biduleur.csv_utils import REQUIRED_BASE_COLUMNS
from leTruc.ui.inputcheck import check_input_file

VALID_COLUMNS = REQUIRED_BASE_COLUMNS + ["GENRE 1", "NOM SPECTACLE 1"]


def _write_csv(tmp_path, columns, rows=3, name="events.csv"):
    df = pd.DataFrame([{c: "x" for c in columns}] * rows)
    path = tmp_path / name
    df.to_csv(path, index=False, encoding="utf8")
    return str(path)


def test_fichier_valide_compte_les_evenements(tmp_path):
    result = check_input_file(_write_csv(tmp_path, VALID_COLUMNS, rows=3))
    assert result.ok
    assert result.event_count == 3
    assert result.message == "3 événements détectés"


def test_un_seul_evenement_au_singulier(tmp_path):
    result = check_input_file(_write_csv(tmp_path, VALID_COLUMNS, rows=1))
    assert result.message == "1 événement détecté"


def test_colonnes_manquantes(tmp_path):
    result = check_input_file(_write_csv(tmp_path, ["DATE"]))
    assert not result.ok
    assert "Colonnes manquantes" in result.message


def test_fichier_introuvable():
    result = check_input_file("n_existe_pas.csv")
    assert not result.ok
    assert "introuvable" in result.message.lower()


def test_chemin_vide():
    assert not check_input_file("").ok


def test_extension_non_supportee(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("bonjour", encoding="utf8")
    result = check_input_file(str(path))
    assert not result.ok
    assert "non supporté" in result.message
```

- [ ] **Step 2: Lancer pour constater l'échec**

Run: `python -m pytest leTruc/tests/test_inputcheck.py -v`
Expected: FAIL (`ModuleNotFoundError: leTruc.ui.inputcheck`).

- [ ] **Step 3: Implémenter** — `leTruc/ui/inputcheck.py`

```python
# leTruc/ui/inputcheck.py
"""Contrôle rapide du fichier d'entrée avant de lancer la création (module pur, sans tkinter)."""
import logging
import os
from dataclasses import dataclass

from biduleur.csv_utils import _read_and_prepare_one_file

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class InputCheck:
    ok: bool
    message: str
    event_count: int = 0


def _compact(text: str) -> str:
    """Retire les lignes vides des messages multi-lignes de biduleur."""
    return "\n".join(line for line in text.splitlines() if line.strip())


def check_input_file(path: str) -> InputCheck:
    if not path or not os.path.isfile(path):
        return InputCheck(False, "Fichier introuvable.")
    try:
        df, _ = _read_and_prepare_one_file(path)
    except ValueError as exc:  # messages déjà rédigés en français par biduleur
        return InputCheck(False, _compact(str(exc)))
    except Exception as exc:  # noqa: BLE001 - on ne veut jamais planter l'interface ici
        log.warning("Lecture du fichier %s impossible", path, exc_info=True)
        return InputCheck(False, f"Fichier illisible : {exc}")

    count = len(df)
    label = "événement détecté" if count == 1 else "événements détectés"
    return InputCheck(True, f"{count} {label}", count)
```

- [ ] **Step 4: Lancer les tests**

Run: `python -m pytest leTruc/tests -v`
Expected: 11 passed. (Si `test_colonnes_manquantes` échoue parce que le message diffère, relire `biduleur/csv_utils.py:585-590` et ajuster l'assertion — pas le code.)

- [ ] **Step 5: Commit**

```bash
git add leTruc/ui/inputcheck.py leTruc/tests/test_inputcheck.py
git commit -m "feat(gui): contrôle immédiat du fichier d'entrée (nombre d'événements, colonnes)"
```

---

### Task 4: Composants communs et fenêtre « Réglages avancés »

**Files:**
- Create: `leTruc/ui/components.py`, `leTruc/ui/advanced_window.py`

**Interfaces:**
- Produces (`components.py`):
  - `block(parent, title: str) -> ttk.LabelFrame` — bloc numéroté (padding 12, colonne 1 extensible)
  - `hint(parent, text: str, wraplength: int = 760) -> ttk.Label` — phrase d'explication grise
  - `scrollable_tab(app, notebook, title: str) -> ttk.Frame` — ajoute un onglet défilant et renvoie le cadre intérieur ; enregistre son canvas dans `app._wheel_canvases`
- Produces (`advanced_window.py`): `build(app) -> tk.Toplevel` ; pose `app.advanced_window`, `app.advanced_notebook`, `app.debug_checkbox`, `app.reset_config_btn`.
- Consumes: `widgets._create_*_section(parent, app, ui_row)` ; `app._wheel_canvases: list` (créé en Task 5) ; `app._on_reset_config`.

- [ ] **Step 1: Écrire `leTruc/ui/components.py`**

```python
# leTruc/ui/components.py
import tkinter as tk
from tkinter import ttk


def block(parent, title: str) -> ttk.LabelFrame:
    """Bloc numéroté de l'écran principal."""
    frame = ttk.LabelFrame(parent, text=title, padding=12)
    frame.columnconfigure(1, weight=1)
    return frame


def hint(parent, text: str, wraplength: int = 760) -> ttk.Label:
    """Phrase d'explication affichée sous un réglage."""
    return ttk.Label(parent, text=text, foreground="#666666", wraplength=wraplength, justify="left")


def scrollable_tab(app, notebook: ttk.Notebook, title: str) -> ttk.Frame:
    """Ajoute à `notebook` un onglet défilant verticalement ; renvoie le cadre à remplir."""
    outer = ttk.Frame(notebook)
    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas, padding=10)
    inner.columnconfigure(1, weight=1)

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(window_id, width=e.width))

    app._wheel_canvases.append(canvas)
    notebook.add(outer, text=title)
    inner._tab_outer = outer  # pour notebook.hide()/add() de l'onglet Expert
    return inner
```

- [ ] **Step 2: Écrire `leTruc/ui/advanced_window.py`**

```python
# leTruc/ui/advanced_window.py
"""Fenêtre « Réglages avancés ».

Elle est créée dès le démarrage (masquée) : callbacks.assign_all() a besoin que tous
les widgets existent. Le bouton ⚙ ne fait que l'afficher.
"""
import tkinter as tk
from tkinter import ttk

from .. import widgets
from .components import hint, scrollable_tab

# (titre de l'onglet, fonctions de widgets.py à y créer)
_TABS = [
    ("Mise en page", [widgets._create_page_layout_section, widgets._create_poster_section]),
    ("Dates", [widgets._create_date_sep_section]),
    ("Stories", [widgets._create_stories_section]),
    ("Abréviations", [widgets._create_abbreviations_section]),
    ("Sorties", [widgets._create_output_section]),
]
_EXPERT_SECTIONS = [
    widgets._create_ours_section,
    widgets._create_logos_section,
    widgets._create_inline_images_section,
    widgets._create_teriaki_experimental_section,
]


def _fill(inner, app, creators):
    ui_row = {'r': 0}
    for create in creators:
        create(inner, app, ui_row)


def _build_general_tab(app, notebook):
    tab = scrollable_tab(app, notebook, "Général")
    hint(tab, "Les réglages par défaut conviennent à un usage normal. "
              "Ne changez ces options que si vous savez pourquoi.").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

    app.debug_checkbox = tk.Checkbutton(
        tab, text="Mode expert / debug (affiche l'onglet « Expert » et conserve les fichiers intermédiaires)",
        variable=app.debug_mode_var)
    app.debug_checkbox.grid(row=1, column=0, columnspan=3, sticky="w", pady=5)

    # callbacks.on_toggle_config_buttons() fait pack()/pack_forget() sur ce bouton
    reset_frame = ttk.Frame(tab)
    reset_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=10)
    app.reset_config_btn = tk.Button(reset_frame, text="🔄 Rétablir les réglages d'origine",
                                     command=app._on_reset_config)
    app.reset_config_btn.pack(side=tk.LEFT)
    return tab


def build(app) -> tk.Toplevel:
    win = tk.Toplevel(app)
    win.withdraw()
    win.title("Réglages avancés")
    win.geometry("820x720")
    win.transient(app)
    win.protocol("WM_DELETE_WINDOW", win.withdraw)
    app.advanced_window = win

    notebook = ttk.Notebook(win)
    notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    app.advanced_notebook = notebook

    _build_general_tab(app, notebook)
    for title, creators in _TABS:
        _fill(scrollable_tab(app, notebook, title), app, creators)

    expert = scrollable_tab(app, notebook, "Expert")
    _fill(expert, app, _EXPERT_SECTIONS)

    def _sync_expert_tab(*_):
        state = "normal" if app.debug_mode_var.get() else "hidden"
        notebook.tab(expert._tab_outer, state=state)

    app.debug_mode_var.trace_add("write", _sync_expert_tab)
    _sync_expert_tab()
    return win
```

> Note : `widgets._create_page_layout_section` et `_create_poster_section` contiennent encore le titre du poster et la taille de police ; ils sont aussi exposés dans le bloc ② (Task 5) via la **même** `StringVar`, ce qui est volontairement redondant et sans risque.

- [ ] **Step 3: Vérifier que les modules s'importent** (la GUI n'est pas encore branchée)

Run: `python -c "import leTruc.ui.components, leTruc.ui.advanced_window; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add leTruc/ui/components.py leTruc/ui/advanced_window.py
git commit -m "feat(gui): fenêtre Réglages avancés à onglets (créée masquée)"
```

---

### Task 5: Écran principal, thème et réassemblage de `app.py`

**Files:**
- Create: `leTruc/ui/main_screen.py`
- Modify: `leTruc/app.py` (imports, `__init__`, `_create_scrollable_area`, `_create_action_and_status_bar`, molette), `leTruc/callbacks.py` (`on_toggle_config_buttons`, `_apply_input_file`)

**Interfaces:**
- Produces: `main_screen.build(app, parent)` ; pose `app.file_check_label`, `app.main_font_forced_entry`.
- Produces: `Application._open_advanced()`, `Application._scroll_units(widget, units)`, `Application._wheel_canvases: list`.
- Produces: `callbacks._apply_input_file(app, file_path)`.
- Consumes: Tasks 2–4.

- [ ] **Step 1: Écrire `leTruc/ui/main_screen.py`**

```python
# leTruc/ui/main_screen.py
"""Écran principal : ① Votre fichier, ② Options du mois (③ Création est la barre d'action de app.py)."""
import tkinter as tk
from tkinter import ttk

from .. import widgets
from .components import block, hint


def build(app, parent):
    parent.columnconfigure(0, weight=1)

    # ① Votre fichier : zone de dépôt, mode été, modèles (réutilise la section existante)
    step1 = block(parent, "① Votre fichier")
    step1.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
    step1.columnconfigure(0, weight=1)
    widgets._create_input_section(step1, app, {'r': 0})
    app.file_check_label = ttk.Label(step1, text="", wraplength=760, justify="left")
    app.file_check_label.grid(row=step1.grid_size()[1], column=0, columnspan=3, sticky="w", padx=10, pady=(0, 5))

    # ② Options du mois
    step2 = block(parent, "② Options du mois")
    step2.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
    step2.columnconfigure(0, weight=1)
    ui_row = {'r': 0}
    widgets._create_cover_section(step2, app, ui_row)
    widgets._create_cucaracha_section(step2, app, ui_row)
    _create_poster_and_font(step2, app, ui_row)
    _create_outputs(step2, app, ui_row)


def _create_poster_and_font(parent, app, ui_row):
    frame = ttk.Frame(parent)
    frame.grid(row=ui_row['r'], column=0, columnspan=3, sticky="ew", pady=10)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="Titre du poster :").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(frame, textvariable=app.poster_title_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    hint(frame, "Obligatoire : le titre affiché en grand sur le poster.").grid(
        row=1, column=1, sticky="w", padx=5)

    ttk.Label(frame, text="Taille de police :").grid(row=2, column=0, sticky="w", padx=5, pady=(10, 5))
    mode = ttk.Frame(frame)
    mode.grid(row=2, column=1, sticky="w", padx=5, pady=(10, 5))
    ttk.Radiobutton(mode, text="Automatique (recommandé)", variable=app.font_size_mode_var,
                    value="auto").pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(mode, text="Forcée (pt) :", variable=app.font_size_mode_var,
                    value="force").pack(side=tk.LEFT)
    app.main_font_forced_entry = ttk.Entry(mode, textvariable=app.font_size_forced_var, width=6)

    def _sync(*_):
        if app.font_size_mode_var.get() == "force":
            app.main_font_forced_entry.pack(side=tk.LEFT, padx=(5, 0))
        else:
            app.main_font_forced_entry.pack_forget()

    app.font_size_mode_var.trace_add("write", _sync)
    _sync()
    hint(frame, "En automatique, la plus grande taille qui fait tenir tout le texte est choisie.").grid(
        row=3, column=1, sticky="w", padx=5)
    ui_row['r'] += 1


def _create_outputs(parent, app, ui_row):
    frame = ttk.Frame(parent)
    frame.grid(row=ui_row['r'], column=0, columnspan=3, sticky="ew", pady=10)
    frame.columnconfigure(0, weight=1)

    ttk.Label(frame, text="Fichiers à créer :").grid(row=0, column=0, sticky="w", padx=5)
    checks = ttk.Frame(frame)
    checks.grid(row=1, column=0, sticky="w", padx=5, pady=5)

    app._pdf_always_var = tk.BooleanVar(value=True)  # référence conservée pour que la case reste cochée
    ttk.Checkbutton(checks, text="PDF (toujours créé)", variable=app._pdf_always_var,
                    state="disabled").pack(side=tk.LEFT, padx=(0, 15))
    ttk.Checkbutton(checks, text="Stories Instagram", variable=app.generate_stories_var).pack(
        side=tk.LEFT, padx=(0, 15))
    ttk.Checkbutton(checks, text="Fichiers HTML", variable=app.generate_html_var).pack(side=tk.LEFT)

    ttk.Label(frame, textvariable=app.pdf_var, foreground="#666666", wraplength=760).grid(
        row=2, column=0, sticky="w", padx=5)
    hint(frame, "↑ Emplacement du PDF. Les dossiers de destination se règlent dans "
                "⚙ Réglages avancés › Sorties.").grid(row=3, column=0, sticky="w", padx=5)
    ui_row['r'] += 1
```

- [ ] **Step 2: `app.py` — imports et thème**

Remplacer le bloc d'imports `from . import widgets / callbacks / menu` par :

```python
from . import callbacks
from . import menu
from .ui import advanced_window, main_screen
from .ui.error_dialog import ErrorDialog
```
(`widgets` n'est plus importé ici ; `ErrorDialog` est créé en Task 6 — créer maintenant un module vide `leTruc/ui/error_dialog.py` contenant `class ErrorDialog: ...` n'est **pas** nécessaire : exécuter la Task 6 avant de lancer la GUI, ou commenter cet import jusque-là.)

Dans `Application.__init__`, juste après `super().__init__()` :

```python
        # Thème moderne ; repli silencieux sur le thème ttk par défaut si ttkbootstrap est absent
        try:
            import ttkbootstrap as tb
            self.style = tb.Style(theme="flatly")
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Thème ttkbootstrap indisponible : {e}")
```

Remplacer l'étape 4 par :

```python
        # 4. ENFIN, remplir les conteneurs avec les widgets et leurs callbacks
        main_screen.build(self, self.scrollable_frame)
        advanced_window.build(self)
        callbacks.assign_all(self)
```

Remplacer les trois `bind_all` de molette par :

```python
        # Molette : fait défiler le canvas sous le pointeur (écran principal ou onglet avancé)
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", lambda e: self._scroll_units(e.widget, -1))
        self.bind_all("<Button-5>", lambda e: self._scroll_units(e.widget, 1))
```

Titre de fenêtre : conserver tel quel. Géométrie : `self.geometry("900x900")` inchangée.

- [ ] **Step 3: `app.py` — molette et canvas**

Dans `_create_scrollable_area`, après `self.canvas = tk.Canvas(container)` ajouter :

```python
        self._wheel_canvases = [self.canvas]
```
Remplacer `_on_mousewheel` (fin du fichier) par :

```python
    def _scroll_units(self, widget, units):
        """Fait défiler le canvas enregistré le plus proche de `widget` (en remontant les parents)."""
        while widget is not None:
            if widget in self._wheel_canvases:
                widget.yview_scroll(units, "units")
                return
            widget = getattr(widget, "master", None)

    def _on_mousewheel(self, event):
        self._scroll_units(event.widget, -1 * (event.delta // 120))
```

- [ ] **Step 4: `app.py` — barre d'action (bloc ③ + pied de page)**

Remplacer le corps de `_create_action_and_status_bar` à partir de `# Checkbox mode debug` jusqu'à `self.config_buttons_frame.pack(pady=(5, 0))` par :

```python
        # Pied de page : réglages avancés, import/export de config, aide
        footer = ttk.Frame(action_frame)
        footer.pack(pady=(8, 0))
        self.advanced_button = ttk.Button(footer, text="⚙ Réglages avancés", command=self._open_advanced)
        self.advanced_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="📂 Importer config", command=self._on_import_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="💾 Exporter config", command=self._on_export_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="❓ Comment ça marche ?",
                   command=lambda: menu.show_user_guide(self)).pack(side=tk.LEFT, padx=5)
```
(le bouton principal et le bouton Stop juste au-dessus sont conservés ; la case `Mode Debug` et `Reset config` n'existent plus ici — ils sont créés par `advanced_window`). Ajouter la méthode :

```python
    def _open_advanced(self):
        """Affiche la fenêtre des réglages avancés (créée masquée au démarrage)."""
        self.advanced_window.deiconify()
        self.advanced_window.lift()
        self.advanced_window.focus_set()
```

- [ ] **Step 5: `callbacks.py` — gating et refactor des chemins**

Dans `on_toggle_config_buttons`, retirer `app.cover_checkbox,` de la liste `debug_only_widgets` (la case « Avec couv' » est désormais toujours visible) et mettre à jour la docstring en conséquence.

Ajouter, au-dessus de `on_pick_input` :

```python
def _apply_input_file(app, file_path: str) -> None:
    """Applique un fichier d'entrée choisi ou déposé : variable, zone de dépôt, chemins de sortie, contrôle."""
    from .ui.inputcheck import check_input_file

    app.input_var.set(file_path)
    _update_drop_zone_text(app, file_path)

    d = _default_paths_from_input(file_path)
    app.html_var.set(d["html"])
    app.agenda_var.set(d["agenda_html"])
    app.pdf_var.set(d["pdf"])
    app.svg_output_var.set(d["svg_output_dir"])
    app.stories_output_var.set(d["stories_output"])

    label = getattr(app, "file_check_label", None)
    if label is not None:
        result = check_input_file(file_path)
        if result.ok:
            label.config(text=f"✔ {result.message}", foreground="#2e7d32")
        else:
            label.config(text=f"✖ {result.message}", foreground="#c62828")
```
Dans `on_pick_input`, remplacer tout ce qui suit `if not file_path: return` par `_apply_input_file(app, file_path)`. Dans `on_drop_input_file`, remplacer tout ce qui suit le test `os.path.exists` par `_apply_input_file(app, file_path)`.

- [ ] **Step 6: Vérification manuelle** (nécessite la Task 6 ou l'import `ErrorDialog` commenté)

Run: `python run_gui.py`. Vérifier :
1. La fenêtre s'ouvre avec le thème « flatly », blocs ① et ②, barre d'action en bas, aucune trace dans la console.
2. Glisser un `.xlsx` de `biduleur/tapages/` dans la zone : le nom s'affiche, la ligne verte « ✔ N événements détectés » apparaît, le chemin du PDF s'affiche dans le bloc ②.
3. Glisser un fichier non valide (ex. un `.txt`) : ligne rouge « ✖ … ».
4. ⚙ Réglages avancés : la fenêtre s'ouvre, 6 onglets (Général, Mise en page, Dates, Stories, Abréviations, Sorties) ; cocher le mode expert dans Général fait apparaître l'onglet « Expert ».
5. Molette : défile le bloc central quand le pointeur est dessus, et l'onglet courant dans la fenêtre avancée (pas l'écran principal).
6. Cocher « Forcée » : le champ de taille apparaît ; « Automatique » le masque.
7. Mode Bidul d'été : la 2ᵉ zone de dépôt apparaît/disparaît.
8. Une création complète produit un PDF (le résultat s'affiche encore avec l'ancien `messagebox`/`VictoryWindow` jusqu'à Task 6).

- [ ] **Step 7: Commit**

```bash
git add leTruc/ui/main_screen.py leTruc/app.py leTruc/callbacks.py
git commit -m "feat(gui): écran principal en 3 blocs, thème ttkbootstrap, réglages avancés dans une fenêtre"
```

---

### Task 6: Retour utilisateur — boîte d'erreur et écran de fin

**Files:**
- Create: `leTruc/ui/error_dialog.py`
- Modify: `leTruc/victory.py`, `leTruc/app.py` (`_check_thread_for_results`)

**Interfaces:**
- Produces: `ErrorDialog(parent, message: str)` ; `VictoryWindow(parent, summary_text: str, pdf_path: str | None = None)`.
- Consumes: `explain_error` (Task 2), `_helpers.open_file(path)`.

- [ ] **Step 1: Écrire `leTruc/ui/error_dialog.py`**

```python
# leTruc/ui/error_dialog.py
import tkinter as tk
from tkinter import ttk

from .errors import explain_error


class ErrorDialog(tk.Toplevel):
    """Erreur expliquée simplement, avec le détail technique replié."""

    def __init__(self, parent, message: str):
        super().__init__(parent)
        self.title("Un problème est survenu")
        self.transient(parent)
        self.resizable(False, False)
        self._explained = explain_error(message)

        body = ttk.Frame(self, padding=15)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text="😕 La création n'a pas abouti", font=("Arial", 13, "bold")).pack(anchor="w")
        ttk.Label(body, text=self._explained.headline, wraplength=520, justify="left").pack(
            anchor="w", pady=(10, 10))

        buttons = ttk.Frame(body)
        buttons.pack(fill=tk.X)
        self._detail_text = None
        if self._explained.detail:
            self._toggle_btn = ttk.Button(buttons, text="Afficher le détail technique ▸", command=self._toggle)
            self._toggle_btn.pack(side=tk.LEFT)
            ttk.Button(buttons, text="Copier le détail", command=self._copy).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Fermer", command=self.destroy).pack(side=tk.RIGHT)
        self._body = body

        self.grab_set()
        self.focus_set()

    def _toggle(self):
        if self._detail_text is None:
            self._detail_text = tk.Text(self._body, width=70, height=12, wrap="none")
            self._detail_text.insert("1.0", self._explained.detail)
            self._detail_text.config(state=tk.DISABLED)
            self._detail_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            self._toggle_btn.config(text="Masquer le détail technique ▾")
        else:
            self._detail_text.destroy()
            self._detail_text = None
            self._toggle_btn.config(text="Afficher le détail technique ▸")

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self._explained.detail)
```

- [ ] **Step 2: `victory.py` — boutons « Ouvrir le PDF » / « Ouvrir le dossier »**

Ajouter `import os` en tête. Changer la signature en `def __init__(self, parent, summary_text: str, pdf_path: str | None = None):` et remplacer le bloc de création du bouton « Fermer » par :

```python
        # Boutons d'action dans le widget Text
        summary_widget.insert(tk.END, '\n')
        if pdf_path:
            open_pdf_btn = tk.Button(summary_widget, text="Ouvrir le PDF", command=lambda: open_file(pdf_path))
            open_dir_btn = tk.Button(summary_widget, text="Ouvrir le dossier",
                                     command=lambda: open_file(os.path.dirname(pdf_path)))
            summary_widget.window_create(tk.END, window=open_pdf_btn, padx=5, pady=10)
            summary_widget.window_create(tk.END, window=open_dir_btn, padx=5, pady=10)
        close_button = tk.Button(summary_widget, text="Fermer", command=self.destroy)
        summary_widget.window_create(tk.END, window=close_button, padx=10, pady=10)
```
(supprimer les anciennes lignes `close_button = …`, `summary_widget.insert(tk.END, '\n')` et `window_create` du bouton Fermer) et adapter l'import en tête : `from ._helpers import get_resource_path, open_file` (et la variante `except ImportError`).

- [ ] **Step 3: `app.py` — brancher dans `_check_thread_for_results`**

```python
                    if ok:
                        VictoryWindow(self, summary_text=msg, pdf_path=self.pdf_var.get().strip())
                        self.status_var.set("Terminé avec succès.")
                    else:
                        if "interrompu" in msg.lower():
                            self.status_var.set("Interrompu.")
                        else:
                            ErrorDialog(self, msg)
                            self.status_var.set("Échec.")
```

- [ ] **Step 4: Vérification manuelle**

Run: `python run_gui.py`.
1. Création réussie : l'écran de fin garde l'animation et affiche « Ouvrir le PDF », « Ouvrir le dossier », « Fermer » ; chaque bouton fonctionne.
2. Erreur prévue : charger un CSV sans les colonnes requises, lancer → la boîte affiche le message biduleur (« Colonnes manquantes… »), sans bouton de détail.
3. Erreur technique : ouvrir temporairement le PDF de sortie dans un lecteur qui le verrouille → message « Impossible d'écrire le fichier… ». Pour tester le repli, lever temporairement `raise KeyError("LIEU")` au début de `run_pipeline` : la boîte affiche « Une colonne attendue est introuvable… : LIEU », « Afficher le détail technique » déplie le traceback, « Copier le détail » met le texte dans le presse-papiers. **Retirer le `raise` ensuite.**

- [ ] **Step 5: Commit**

```bash
git add leTruc/ui/error_dialog.py leTruc/victory.py leTruc/app.py
git commit -m "feat(gui): erreurs expliquées simplement et actions sur l'écran de fin"
```

---

### Task 7: Textes d'aide pour les débutants

**Files:**
- Modify: `leTruc/ui/main_screen.py`

**Interfaces:**
- Consumes: `hint()` (Task 4).

- [ ] **Step 1: Ajouter une phrase d'explication sous les éléments clés**

Dans `main_screen.build`, après la création de `app.file_check_label`, ajouter :

```python
    hint(step1, "Déposez le tableau Excel (ou CSV) du mois. Un modèle vide est téléchargeable plus bas.").grid(
        row=step1.grid_size()[1], column=0, columnspan=3, sticky="w", padx=10)
```
et, juste avant le bloc ② (`_create_poster_and_font`), un rappel :

```python
    hint(step2, "Ces options changent souvent d'un mois à l'autre. "
                "Les réglages techniques sont dans ⚙ Réglages avancés.").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
    ui_row = {'r': 1}
```
(remplacer la ligne `ui_row = {'r': 0}` existante par la ligne ci-dessus ; les sections suivantes démarrent donc à la ligne 1).

- [ ] **Step 2: Vérification manuelle**

Run: `python run_gui.py` — les deux phrases apparaissent, le texte passe à la ligne sans déborder à 900 px de large.

- [ ] **Step 3: Commit**

```bash
git add leTruc/ui/main_screen.py
git commit -m "feat(gui): phrases d'aide pour les utilisateurs débutants"
```

---

### Task 8: Packaging, nettoyage et documentation

**Files:**
- Modify: `bidul.spec`, `leTruc/widgets.py`, `RELEASE_NOTES.md`, `TODO.md`, `docs/superpowers/specs/2026-10-07-letruc-gui-moderne-design.md`

- [ ] **Step 1: PyInstaller — embarquer ttkbootstrap** (thèmes JSON et images sont des données)

Dans `bidul.spec`, ajouter en tête `from PyInstaller.utils.hooks import collect_data_files`, puis juste après la définition de `datas` :

```python
datas += collect_data_files('ttkbootstrap')
```
et ajouter `'ttkbootstrap'` à `hiddenimports` (ligne `hiddenimports = [...]`).

- [ ] **Step 2: Construire et tester l'exécutable**

Run:
```bash
pip install pyinstaller==6.6.0
pyinstaller bidul.spec --clean --noconfirm
```
Lancer l'exe produit dans `dist/` : la fenêtre doit s'ouvrir avec le thème « flatly » (pas le thème gris par défaut), le glisser-déposer doit marcher, et une création complète doit réussir. Si le thème est absent, vérifier que `collect_data_files` a bien embarqué `ttkbootstrap/themes`.

- [ ] **Step 3: Nettoyage du code mort**

Supprimer `create_all` de `leTruc/widgets.py` (lignes 43-70, plus aucun appelant : vérifier avec `grep -rn "create_all" leTruc` qui ne doit rien renvoyer d'autre que `assign_all`). Vérifier aussi qu'aucun import mort ne reste dans `leTruc/app.py` (`widgets`).

Run: `python -m pytest leTruc/tests misenpageur/tests -q` puis `python run_gui.py` (démarrage sans erreur).

- [ ] **Step 4: Documentation**

- `RELEASE_NOTES.md` : ajouter en tête une section `# Bidul v1.10.0 - Nouvelle interface de Le Truc` (même format que les sections existantes) listant : écran en 3 blocs, fenêtre Réglages avancés, thème ttkbootstrap, contrôle immédiat du fichier, erreurs expliquées, boutons Ouvrir le PDF / dossier.
- `TODO.md` : ajouter en suite possible « simplifier la section Cucaracha du bloc ② (police/taille dans les avancés) » et « contrôle du fichier en thread pour les très gros classeurs ».
- Spec : dans `docs/superpowers/specs/2026-10-07-letruc-gui-moderne-design.md`, remplacer la mention de `paths.py` et de la suppression de `VictoryWindow`, et ajouter les écarts 3–5 de la section « Écarts assumés » de ce plan.

- [ ] **Step 5: Commit final**

```bash
git add bidul.spec leTruc/widgets.py RELEASE_NOTES.md TODO.md docs/superpowers/specs/2026-10-07-letruc-gui-moderne-design.md
git commit -m "chore(gui): packaging ttkbootstrap, nettoyage et notes de release v1.10.0"
```

---

## Auto-revue du plan

- **Couverture de la spec** : thème ttkbootstrap (T1, T5, T8) ; 3 blocs (T5) ; vérification « N événements » (T3, T5) ; fenêtre avancée à onglets + debug + reset (T4) ; chemins par défaut (déjà existants, factorisés T5) ; progression en français (déjà en place dans `run_pipeline`, conservée) ; écran de fin avec actions (T6) ; erreurs simples + détail replié + copie (T2, T6) ; phrases d'aide + « Comment ça marche ? » (T5, T7) ; tests purs (T2, T3) ; PyInstaller (T8). Aucun trou ; les écarts sont listés en tête.
- **Cohérence des noms** : `explain_error` / `ExplainedError(headline, detail)`, `check_input_file` / `InputCheck(ok, message, event_count)`, `scrollable_tab(app, notebook, title)`, `app._wheel_canvases`, `app.file_check_label`, `app.reset_config_btn`, `app.debug_checkbox`, `_apply_input_file` sont utilisés de façon identique dans toutes les tâches.
- **Dépendance d'ordre** : T5 importe `ErrorDialog` (créé en T6) — signalé dans T5 Step 2 ; exécuter T6 Step 1 avant la vérification manuelle de T5, ou commenter l'import le temps de T5.

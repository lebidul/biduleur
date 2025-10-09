Oui — là tu gagnes beaucoup à refactorer.
Je te propose une découpe claire “plan → rendu”, avec un moteur unique de mesure qui tient compte **des espacements** (spaceBefore/spaceAfter) pour éviter les décalages S4 que tu observes, et un endroit unique où gérer les glyphes (❑, €…).

Voici un plan concret, par étapes, + une arborescence cible et des squelettes d’API.

---

# 1) Objectifs du refactor

* **Une seule source de vérité pour la mesure** (wrap+hauteur) et le **rendu** — incluant les *spaceBefore/After* et la détection “événement vs date”.
* **Séparation nette** :

  * *parse → modèle → planification (flow) → rendu (canvas)*
* **Points de personnalisation** isolés : espacements, césure A→B, règles S5, polices/glyphes.
* **Tests simples** (unitaires) sur chaque bloc.

---

# 2) Nouvelle arborescence (proposée)

```
misenpageur/
  __init__.py
  main.py
  config.py
  layout.py

  # 1) Entrée & modèle
  html_parse.py        # parse HTML -> List[Para]
  model.py             # dataclasses: Para(kind=DATE|EVENT|CONTINUATION), SectionID, StyleSpec

  # 2) Styles & glyphes
  styles.py            # paragraph_style(...), mapping police/taille/leading
  glyphs.py            # apply_glyph_fallbacks(text), policy pour '€' et '❑'

  # 3) Espacements & règles
  spacing.py           # SpacingPolicy: compute_space_before/after(kind, context)
  bullets.py           # detection robuste événement (❑) + nettoyage éventuel

  # 4) Moteur de mesure & planification
  measure.py           # measure_flow_height(...), fit_at_fs(...), count_that_fit(...)
  planner.py           # plan_pair_with_split(...), intégrant spacing & césure utile
  fs_search.py         # find_common_font_size(...), utilise measure + spacing

  # 5) Rendu
  render.py            # draw_section_top_aligned(...), with_prelude/with_tail(...)
  drawing.py           # S1 logos + ours, S2 cover (inchangé, mais plus fin)

  # 6) Orchestration
  pdfbuild.py          # lit config/layout, appelle parser -> planner -> render
  fonts.py             # enregistrement polices (Arial Narrow, DejaVuSans)

  tests/               # tests unitaires ciblés
```

---

# 3) Interfaces minimales (squelettes)

### `model.py`

```python
from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

class ParaKind(Enum):
    DATE = auto()
    EVENT = auto()
    CONTINUATION = auto()  # morceaux issus d’une césure

@dataclass
class Para:
    raw_html: str
    kind: ParaKind
    # optionnel: champs pré-calculés (texte nettoyé, etc.)
```

### `bullets.py`

```python
import re
_BULLET = re.compile(r'^\s*(?:❑|□|■|&#9643;)\s*', re.I)

def is_event(text: str) -> bool:
    return bool(_BULLET.match(text or ""))

def strip_leading_bullet_for_render(text: str) -> str:
    # si besoin de masquer le ❑ en rendu (optionnel, pilotable par config)
    return _BULLET.sub("", text, count=1)
```

### `glyphs.py`

```python
from reportlab.pdfbase import pdfmetrics

def apply_glyph_fallbacks(text: str) -> str:
    # ne touche PAS au ❑ (le garder tel quel)
    t = text.replace("&euro;", "€")
    if "DejaVuSans" in pdfmetrics.getRegisteredFontNames():
        t = t.replace("€", '<font name="DejaVuSans">€</font>')
        # si Arial Narrow ne rend pas ❑ correctement:
        t = t.replace("❑", '<font name="DejaVuSans">❑</font>')
    return t
```

### `spacing.py`

```python
from dataclasses import dataclass

@dataclass
class SpacingConfig:
    date_spaceBefore: float = 6.0
    date_spaceAfter: float = 3.0
    event_spaceBefore: float = 1.0
    event_spaceAfter: float = 1.0
    event_spaceAfter_perLine: float = 0.4
    min_event_spaceAfter: float = 1.0
    first_non_event_spaceBefore_in_S5: float = 0.0

class SpacingPolicy:
    def __init__(self, cfg: SpacingConfig, leading: float):
        self.cfg = cfg
        self.leading = leading

    def space_before(self, kind, section_name, is_first_non_event_in_S5):
        if kind.name == "DATE":
            if section_name == "S5" and is_first_non_event_in_S5:
                return self.cfg.first_non_event_spaceBefore_in_S5
            return self.cfg.date_spaceBefore
        return self.cfg.event_spaceBefore

    def space_after(self, kind, para_height):
        if kind.name == "DATE":
            return self.cfg.date_spaceAfter
        # dynamique pour événements
        lines = max(1, int(round(para_height / max(1.0, self.leading))))
        extra = max(0, lines - 1) * self.cfg.event_spaceAfter_perLine
        return max(self.cfg.min_event_spaceAfter, self.cfg.event_spaceAfter + extra)
```

### `measure.py`

```python
# Mesure qui tient compte: wrap -> hauteur + spacing avant/après
from reportlab.platypus import Paragraph
from .styles import paragraph_style
from .glyphs import apply_glyph_fallbacks

def wrap_height(p: Paragraph, w: float) -> float:
    _, ph = p.wrap(w, 1e6)
    return ph

def count_that_fit(section, items, style, spacing_policy, inner_pad, section_name):
    x0 = section.x + inner_pad; y0 = section.y + inner_pad
    w  = max(1.0, section.w - 2*inner_pad)
    h  = max(1.0, section.h - 2*inner_pad)
    y  = y0 + h

    first_non_event_seen_in_S5 = False
    used = 0

    for para in items:
        p = Paragraph(apply_glyph_fallbacks(para.raw_html), style)
        ph = wrap_height(p, w)
        sb = spacing_policy.space_before(para.kind, section_name, (section_name=="S5" and para.kind.name=="DATE" and not first_non_event_seen_in_S5))
        if section_name=="S5" and para.kind.name=="DATE" and not first_non_event_seen_in_S5:
            first_non_event_seen_in_S5 = True
        sa = spacing_policy.space_after(para.kind, ph)

        need = sb + ph + sa
        if (y - need) < y0:
            break
        y -= need
        used += 1
    return used
```

### `fs_search.py`

```python
# Recherche binaire de la taille commune, en utilisant count_that_fit(...)
```

### `planner.py`

```python
# plan_pair_with_split(...) qui:
# - utilise wrap_height + spacing_policy pour A et B
# - n’autorise la césure A→B que si gain >= ratio*hA (ou >= 1 leading)
# - retourne A_full, A_tail (Paragraph), B_prelude (Paragraph), B_full, remaining
```

### `render.py`

```python
# draw_section_top_aligned(...):
# - apply_glyph_fallbacks()
# - Paragraph(...), wrap -> ph -> y -= spaceBefore ; draw ; y -= (ph + spaceAfter)
# - versions with_prelude / with_tail
```

`pdfbuild.py` devient un **orchestrateur mince** : lit config/layout → parse HTML → construit objets `Para` (via `bullets.is_event`) → recherche `fs_common` (avec *spacing* inclus) → planifie les paires (S5→S6, S3→S4) → rend.

---

# 4) Répondre à tes 2 soucis actuels

* **Le caractère `❑` remplacé par un symbole moche**
  → Déplace la gestion dans `glyphs.apply_glyph_fallbacks()` et force `❑` en **DejaVuSans** si Arial Narrow ne le rend pas bien. On enveloppe juste le caractère avec `<font name="DejaVuSans">❑</font>`.

* **Événements manquants en S4**
  → C’est typiquement parce que la **mesure n’intégrait pas les spacings** alors que le rendu, si. Avec ce refactor, `measure.count_that_fit` et le rendu partagent **la même logique d’espacement et de wrap** → plus d’écart, donc plus de “mystère” S4.

---

# 5) Migration progressive (sans tout casser)

1. **Extraire `glyphs.py`** et faire passer tous les Paragraph par `apply_glyph_fallbacks`.
2. **Introduire `spacing.py`** et faire consommer la policy par *textflow* actuel (sans changer l’arborescence).
3. Remplacer la recherche de taille (fs) pour utiliser la **mesure avec spacing**.
4. Extraire `measure.py` et `planner.py` (plan\_pair\_with\_split).
5. Basculer le rendu S3–S6 vers `render.py`.
6. Amincir `pdfbuild.py` (juste orchestration).

À chaque étape, tu peux pousser un commit “vert”.

---

# 6) Tests rapides utiles

* **Unitaires** :

  * bullets.is\_event(❑ …) == True, is\_event(“En bref”) == False
  * spacing: dates vs events, première non-événement S5, perLine
  * measure.count\_that\_fit: cas simples (1–2 paras)
  * planner: césure acceptée/refusée selon gain et place restante

* **Goldens** : rendre un mini-HTML et checker le nombre de paragraphes par section & que S6→S3 ne césure jamais.

---

Si tu veux, je peux te livrer un **PR minimal** qui commence par 1) glyphs + 2) spacing policy intégrée à la mesure, puis on déroule le reste.

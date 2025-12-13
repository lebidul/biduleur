# 🔤 Système d'Abréviations v1.4.2

## Vue d'ensemble

Le système d'abréviations permet de **réduire la longueur du texte** avant le calcul de la taille de police optimale, augmentant ainsi la lisibilité de l'agenda.

**Nouveautés v1.4.2 :**
- ✅ Configuration YAML séparée (`abbreviations.yml`)
- ✅ Décodage automatique des entités HTML (`Th&eacute;&acirc;tre` → `Théâtre`)
- ✅ Normalisation Unicode (compatibilité NFC/NFD)
- ✅ Protection des expressions nobr (noms propres préservés)
- ✅ Interface 4 colonnes (toutes les abréviations visibles sans scrollbar)
- ✅ 22 abréviations prédéfinies, 9 activées par défaut

---

## Architecture

```
bidul/
└── misenpageur/
    ├── abbreviations.yml              ← Configuration des 22 abréviations
    ├── config.yml                     ← Configuration générale (sans abréviations)
    ├── assets/
    │   └── textes/
    │       └── nobr.txt               ← Expressions à protéger (noms propres)
    ├── ABBREVIATIONS.md               ← Cette documentation
    └── misenpageur/
        ├── abbreviations.py           ← Module de traitement
        └── config.py                  ← Configuration générale
```

**Séparation des responsabilités :**
- `abbreviations.yml` : UNIQUEMENT les abréviations (facile à éditer)
- `config.yml` : Tous les autres paramètres (polices, marges, logos, etc.)
- `nobr.txt` : Noms propres à protéger (optionnel)

---

## Utilisation

### Interface graphique (leTruc)

**Section "Abréviations (pour réduire le texte)" :**
- 22 checkboxes organisées en **4 colonnes**
- Toutes les abréviations visibles sans scrollbar
- Boutons "✓ Tout activer" / "✗ Tout désactiver"
- Chargement automatique depuis `abbreviations.yml`

**Workflow :**
1. Cocher les abréviations souhaitées
2. Cliquer sur "Générer"
3. Les abréviations sont appliquées AVANT le calcul de taille de police
4. Le PDF contient le texte abrégé

### Édition du fichier YAML

**Fichier :** `misenpageur/abbreviations.yml`

**Structure :**
```yaml
theatre:
  original: "théâtre"
  replacement: "th."
  description: "Théâtre → Th."
  enabled: true

association:
  original: "association"
  replacement: "asso."
  description: "Association → Asso."
  enabled: true
```

**Champs :**
- `original` : Texte à rechercher (insensible à la casse)
- `replacement` : Texte de remplacement
- `description` : Libellé affiché dans l'interface
- `enabled` : Activé par défaut (true/false)

---

## Fonctionnement technique

### 1. Préservation de la casse

Le remplacement préserve la casse d'origine :

| Original | Remplacement | Résultat |
|----------|--------------|----------|
| `théâtre` | `th.` | `th.` |
| `Théâtre` | `th.` | `Th.` |
| `THÉÂTRE` | `th.` | `TH.` |

**Algorithme :**
```python
def _preserve_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    elif original[0].isupper():
        return replacement.capitalize()
    else:
        return replacement.lower()
```

**Gestion Title Case multi-mots :**
```python
# "Centre Culturel" → "CC" (majuscules préservées)
# "centre culturel" → "cc" (minuscules préservées)
```

### 2. Word Boundaries

Les remplacements utilisent `\b` (word boundaries) pour éviter les remplacements partiels :

| Texte | Abréviation | Résultat | Raison |
|-------|-------------|----------|--------|
| `Théâtre Municipal` | `théâtre` → `th.` | `Th. Municipal` | ✅ Match |
| `Théâtralité` | `théâtre` → `th.` | `Théâtralité` | ❌ Pas de word boundary |

### 3. Tri par longueur

Les abréviations sont triées par longueur **décroissante** avant application :

**Pourquoi ?** Pour traiter les expressions longues d'abord :
```yaml
# Ordre d'application :
1. "centre culturel" (15 caractères)  # Appliqué en premier
2. "centre" (6 caractères)            # Puis celui-ci
```

Sans ce tri, "centre culturel" pourrait devenir "cen. culturel" au lieu de "cc".

### 4. Décodage des entités HTML (v1.4.2)

**Problème :** Les fichiers Excel génèrent parfois des entités HTML :
```html
<p>Th&eacute;&acirc;tre Municipal</p>
```

**Solution :** Décodage automatique AVANT l'application des abréviations :
```python
import html
paras_decoded = [html.unescape(p) for p in paras]
# "Th&eacute;&acirc;tre" → "Théâtre"
```

### 5. Normalisation Unicode (v1.4.2)

**Problème :** Les caractères accentués peuvent être encodés de 2 façons :

| Forme | Représentation | Longueur | Utilisé par |
|-------|----------------|----------|-------------|
| **NFC** (composée) | `â` = 1 caractère | 7 chars | Windows |
| **NFD** (décomposée) | `a` + `^` = 2 caractères | 9 chars | macOS |

**Solution :** Normalisation NFC partout :
```python
import unicodedata

# Dans abbreviations.py
normalized = unicodedata.normalize('NFC', text)

# Garantit que "théâtre" (NFC) == "théâtre" (NFD)
```

### 6. Protection des expressions nobr (v1.4.2)

**Problème :** Les noms propres ne doivent pas être abrégés :
```
"Théâtre de l'Écluse" → NE DOIT PAS devenir "Th. de l'Écluse"
```

**Solution :** Fichier `nobr.txt` avec les expressions à protéger :

**`misenpageur/assets/textes/nobr.txt` :**
```
Théâtre de l'Écluse
Association Bidul
Centre Culturel La Chapelle
```

**Algorithme de protection (3 phases) :**

**Phase 1 : Remplacement temporaire**
```
"Spectacle au Théâtre de l'Écluse"
→ "Spectacle au ___NOBR_0___"
```

**Phase 2 : Application des abréviations**
```
"Un théâtre municipal" → "Un th. municipal"
"___NOBR_0___"        → "___NOBR_0___" (inchangé)
```

**Phase 3 : Restauration**
```
"___NOBR_0___" → "Théâtre de l'Écluse"
```

**Résultat final :**
- ✅ "Théâtre de l'Écluse" reste intact (protégé par nobr)
- ✅ "Un théâtre municipal" devient "Un th. municipal" (abrégé)

**Documentation complète :** Voir `NOBR_PROTECTION.md`

### 7. Pipeline d'exécution

**Ordre d'application dans `_helpers.py` :**

```python
# 1. Extraction des paragraphes HTML
paras = extract_paragraphs_from_html(html_text)

# 2. Décodage des entités HTML (v1.4.2)
import html
paras = [html.unescape(p) for p in paras]
# "Th&eacute;&acirc;tre" → "Théâtre"

# 3. Chargement des expressions nobr (v1.4.2)
nobr_expressions = load_nobr_from_file("nobr.txt")

# 4. Application des abréviations
paras, stats = apply_abbreviations_to_paragraphs(
    paras,
    enabled_abbreviations,
    nobr_expressions  # Protection des noms propres
)

# 5. Calcul de la taille de police optimale
font_size = calculate_optimal_font_size(paras)

# 6. Génération du PDF
build_pdf(paras, font_size)
```

**Ordre critique :** Les abréviations DOIVENT être appliquées AVANT le calcul de taille de police pour maximiser le gain d'espace.

---

## Liste des abréviations

### Préfixes honorifiques
| Original | Remplacement | Description | Défaut |
|----------|--------------|-------------|--------|
| sainte | ste | Sainte → Ste | ❌ |
| saint | st | Saint → St | ❌ |

### Voies
| Original | Remplacement | Description | Défaut |
|----------|--------------|-------------|--------|
| place | pl. | Place → Pl. | ❌ |
| avenue | av. | Avenue → Av. | ❌ |
| quartier | qtr | Quartier → Qtr | ❌ |

### Lieux
| Original | Remplacement | Description | Défaut |
|----------|--------------|-------------|--------|
| espace | esp. | Espace → Esp. | ❌ |
| médiathèque | média. | Médiathèque → Média. | ❌ |
| association | asso. | Association → Asso. | ✅ |
| théâtres | th. | Théâtres → Th. | ✅ |
| théâtre | th. | Théâtre → Th. | ✅ |
| centre culturel | cc | Centre Culturel → CC | ✅ |
| sargé-lès-le-mans | sargé | Sargé-lès-le-Mans → Sargé | ✅ |

### Événements
| Original | Remplacement | Description | Défaut |
|----------|--------------|-------------|--------|
| spectacle | spect. | Spectacle → Spect. | ❌ |
| exposition | expo | Exposition → Expo | ✅ |
| conférence | conf. | Conférence → Conf. | ❌ |
| compagnie | cie | Compagnie → Cie | ✅ |

### Pratique
| Original | Remplacement | Description | Défaut |
|----------|--------------|-------------|--------|
| réservations | résa | Réservations → Résa | ✅ |
| réservation | résa | Réservation → Résa | ✅ |
| entrée | entr. | Entrée → Entr. | ❌ |

### Divers
| Original | Remplacement | Description | Défaut |
|----------|--------------|-------------|--------|
| environ | env. | Environ → Env. | ❌ |
| information | info | Information → Info | ❌ |
| informations | infos | Informations → Infos | ❌ |

**Total :** 22 abréviations  
**Activées par défaut :** 9 (association, théâtre, théâtres, centre culturel, sargé, exposition, compagnie, réservation, réservations)

---

## Ajouter une nouvelle abréviation

### Méthode 1 : Éditer `abbreviations.yml`

```yaml
# Ajouter à la fin du fichier
nouvelle_abbreviation:
  original: "bibliothèque"
  replacement: "bib."
  description: "Bibliothèque → Bib."
  enabled: false
```

**Règles à respecter :**

**✅ DO :**
- Clé unique (pas de duplicata)
- `original` en minuscules (la casse sera gérée automatiquement)
- `replacement` concis (gagne de l'espace)
- `description` claire pour l'interface
- `enabled: false` par défaut (pour tester d'abord)

**❌ DON'T :**
- Abréviation trop agressive : `théâtre` → `t.` (perte de lisibilité)
- Mots trop courts : `au` → `a` (gain minimal, confusion possible)
- Expressions trop génériques : `de` → `d` (risque de faux positifs)
- Remplacements ambigus : `rue` → `r.` (confondu avec "rond-point")

### Méthode 2 : Script Python (pour génération automatique)

```python
import yaml

# Charger le fichier existant
with open('abbreviations.yml', 'r', encoding='utf-8') as f:
    abbrevs = yaml.safe_load(f)

# Ajouter une nouvelle abréviation
abbrevs['bibliotheque'] = {
    'original': 'bibliothèque',
    'replacement': 'bib.',
    'description': 'Bibliothèque → Bib.',
    'enabled': False
}

# Sauvegarder
with open('abbreviations.yml', 'w', encoding='utf-8') as f:
    yaml.dump(abbrevs, f, allow_unicode=True, default_flow_style=False)
```

---

## Débogage

### Mode debug

**Activer le logging détaillé :**

```python
# Dans _helpers.py ou au début de votre script
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Logs générés :**

```
[INFO] Chargé 45 expression(s) nobr à protéger
[INFO] Application de 7 abréviation(s)...
[DEBUG] Exemple avant décodage: <p>Th&eacute;&acirc;tre Municipal</p>
[DEBUG] Exemple après décodage: <p>Théâtre Municipal</p>
[INFO] Abréviations: 23 remplacement(s) effectué(s)
[DEBUG]   - théâtre → th.: 12x
[DEBUG]   - association → asso.: 5x
[DEBUG]   - centre culturel → cc: 6x
[DEBUG]   45 expression(s) nobr protégée(s)
```

### Fichiers de debug générés

**Si le mode debug est activé dans l'interface :**

**`debug_run_<timestamp>/abbreviations.json` :**
```json
{
  "enabled": {
    "theatre": true,
    "association": true,
    "centre_culturel": true
  },
  "stats": {
    "theatre": 12,
    "association": 5,
    "centre_culturel": 6
  }
}
```

**Interprétation :**
- `"theatre": 12` → 12 remplacements effectués
- `"theatre": 0` → Aucun remplacement (vérifier les logs DEBUG)

### Problèmes courants

**1. Aucun remplacement effectué**

**Symptômes :**
```
[INFO] Total: 0 remplacement(s) effectué(s)
```

**Causes possibles :**
- ❌ Abréviation non cochée dans l'interface
- ❌ Entités HTML non décodées (`Th&eacute;&acirc;tre` au lieu de `Théâtre`)
- ❌ Expression protégée par nobr.txt
- ❌ Normalisation Unicode différente (NFC vs NFD)

**Solution :** Consulter `DEBUG_ABBREVIATIONS.md`

**2. Remplacement partiel**

**Exemple :**
```
"Théâtralité" → "Th.ralité" ❌
```

**Cause :** Word boundaries `\b` mal configurés

**Solution :** Vérifier le pattern regex dans `_create_replacement_pattern()`

**3. Noms propres abrégés**

**Exemple :**
```
"Théâtre de l'Écluse" → "Th. de l'Écluse" ❌
```

**Cause :** Expression non présente dans `nobr.txt`

**Solution :** Ajouter dans `misenpageur/assets/textes/nobr.txt` :
```
Théâtre de l'Écluse
```

---

## Import / Export de configuration

### Export

**Depuis l'interface (leTruc) :**
1. Configurer les abréviations souhaitées
2. Cliquer sur "💾 Exporter config"
3. Sauvegarder `config.yml`

**Le fichier généré ne contient PLUS de section `abbreviations`** (v1.4.2).  
Les abréviations sont maintenant dans `abbreviations.yml` séparé.

### Import

**Depuis l'interface (leTruc) :**
1. Cliquer sur "📁 Importer config"
2. Sélectionner un fichier YAML ou JSON
3. Les checkboxes sont automatiquement cochées selon `abbreviations.yml`

**Compatibilité v1.4.1 → v1.4.2 :**
- Les anciens `config.yml` avec section `abbreviations` sont ignorés
- L'état des checkboxes est TOUJOURS chargé depuis `abbreviations.yml`

---

## Compatibilité

### Rétrocompatibilité

**Version 1.4.1 → 1.4.2 :**
- ✅ Les fichiers Excel/CSV continuent de fonctionner
- ✅ Les anciens `config.yml` sont compatibles
- ✅ Si `abbreviations.yml` n'existe pas → aucune abréviation appliquée
- ✅ Si `nobr.txt` n'existe pas → aucune protection nobr

**Pas de modification requise** pour continuer à utiliser le système sans abréviations.

### Versions Python

**Requis :** Python 3.10+  
**Testé avec :** 3.10, 3.11, 3.12

**Dépendances :**
- `pyyaml` : Chargement des fichiers YAML
- `unicodedata` : Normalisation Unicode (module standard)

---

## Exemples d'utilisation

### Exemple 1 : Agenda culturel classique

**Configuration :**
- ✅ Théâtre → Th.
- ✅ Association → Asso.
- ✅ Centre Culturel → CC
- ✅ Exposition → Expo
- ✅ Compagnie → Cie
- ✅ Réservation → Résa

**Paragraphe original :**
```
Exposition "Art Contemporain" au Centre Culturel La Chapelle,
organisée par l'Association Bidul. Réservation conseillée.
Théâtre de l'Écluse : "Les Misérables" par la Compagnie des Arts.
```

**nobr.txt :**
```
Centre Culturel La Chapelle
Association Bidul
Théâtre de l'Écluse
```

**Résultat :**
```
Expo "Art Contemporain" au Centre Culturel La Chapelle,
organisée par l'Association Bidul. Résa conseillée.
Théâtre de l'Écluse : "Les Misérables" par la Cie des Arts.
```

**Gain :** ~30 caractères (centre culturel générique, exposition, compagnie, réservation)  
**Protégé :** Noms propres intacts

### Exemple 2 : Agenda avec lieux récurrents

**Configuration :**
- ✅ Sargé-lès-le-Mans → Sargé
- ✅ Médiathèque → Média.

**Paragraphe :**
```
Concert à Sargé-lès-le-Mans, médiathèque municipale.
Atelier à la médiathèque de Sargé-lès-le-Mans.
```

**Résultat :**
```
Concert à Sargé, média. municipale.
Atelier à la média. de Sargé.
```

### Exemple 3 : Protection sélective

**nobr.txt :**
```
Association pour la Promotion du Théâtre
```

**Paragraphe :**
```
Association pour la Promotion du Théâtre organise un spectacle.
Une association locale présente un théâtre de rue.
```

**Résultat :**
```
Association pour la Promotion du Théâtre organise un spectacle.
Une asso. locale présente un th. de rue.
```

**Explication :**
- Ligne 1 : Nom propre complet protégé (nobr)
- Ligne 2 : Termes génériques abrégés

---

## API Python (usage programmatique)

### Chargement des abréviations

```python
from misenpageur.misenpageur.abbreviations import get_default_abbreviations

# Charger depuis abbreviations.yml
abbrevs = get_default_abbreviations()

# Résultat : dict
# {
#   "theatre": {
#     "original": "théâtre",
#     "replacement": "th.",
#     "description": "Théâtre → Th.",
#     "enabled": True
#   },
#   ...
# }
```

### Application des abréviations

```python
from misenpageur.misenpageur.abbreviations import (
    Abbreviation,
    apply_abbreviations_to_paragraphs
)

# Créer une liste d'abréviations
abbreviations = [
    Abbreviation(
        key="theatre",
        original="théâtre",
        replacement="th.",
        description="Théâtre → Th.",
        enabled=True
    )
]

# Paragraphes à traiter
paragraphs = [
    '<p>Spectacle au Théâtre Municipal</p>',
    '<p>Un théâtre ouvert ce soir</p>'
]

# Charger les expressions nobr (optionnel)
nobr_expressions = ["Théâtre Municipal"]

# Appliquer les abréviations
result, stats = apply_abbreviations_to_paragraphs(
    paragraphs,
    abbreviations,
    nobr_expressions
)

# Résultat :
# result = [
#     '<p>Spectacle au Théâtre Municipal</p>',  # Protégé
#     '<p>Un th. ouvert ce soir</p>'            # Abrégé
# ]
# stats = {"theatre": 1}
```

### Rechargement des abréviations

```python
from misenpageur.misenpageur.abbreviations import reload_abbreviations

# Forcer le rechargement depuis le fichier YAML
# (utile après une modification manuelle)
reload_abbreviations()

# Récupérer les nouvelles valeurs
abbrevs = get_default_abbreviations()
```

---

## Checklist de déploiement

**Avant de déployer v1.4.2 :**

- [ ] Vérifier que `abbreviations.yml` existe dans `misenpageur/`
- [ ] Tester le chargement : `python test_abbreviations.py`
- [ ] Vérifier le décodage HTML : `python test_html_entities.py`
- [ ] Vérifier la normalisation Unicode : `python test_unicode_normalization.py`
- [ ] Tester la protection nobr : `python test_nobr_protection.py`
- [ ] Vérifier que l'interface affiche bien 22 abréviations en 4 colonnes
- [ ] Tester avec un fichier Excel contenant des accents
- [ ] Vérifier que `nobr.txt` contient les noms propres locaux
- [ ] Générer un PDF et vérifier les abréviations appliquées
- [ ] Consulter les logs : `[INFO] Total: X remplacement(s)`
- [ ] Vérifier que les noms propres sont préservés

**Fichiers requis :**
- `misenpageur/abbreviations.yml` (22 abréviations)
- `misenpageur/assets/textes/nobr.txt` (optionnel mais recommandé)
- `misenpageur/misenpageur/abbreviations.py` (module)

**Documentation :**
- `ABBREVIATIONS.md` (ce fichier)
- `NOBR_PROTECTION.md` (protection des noms propres)
- `DEBUG_ABBREVIATIONS.md` (guide de débogage)
- `UNICODE_FIX.md` (problèmes Unicode)

---

**Version :** 1.4.2  
**Dernière mise à jour :** Décembre 2024
# Bidul v1.9.0 - Mode Bidul d'été : édition combinée 2 mois, section FESTIVALS, séparateurs de mois

Nouvelle version dédiée à l'édition spéciale **juillet + août** (ou tout couple
de mois) du Bidul : un seul agenda regroupant 2 mois en entrée, avec une
section **FESTIVALS** en tête et un séparateur visuel entre les 2 mois.

## ✨ Nouveautés

### Mode "Bidul d'été" (`summer_mode`, `input_file_2`)
*   Nouvelle case à cocher **🌞 Mode Bidul d'été** dans la section d'import :
    active la **fusion de 2 fichiers xlsx/csv** d'entrée en un seul agenda
*   Quand la case est cochée, une **2ᵉ zone de drop** apparaît pour glisser
    le fichier du 2ᵉ mois (août typiquement, mais ça marche avec n'importe
    quel couple de mois — testé sur mars/avril, avril/mai, juillet/août)
*   Les événements des 2 fichiers sont **concaténés** au niveau du DataFrame
    puis triés ensemble. Les événements du **1ᵉʳ fichier sont placés avant**
    ceux du 2ᵉ (indépendamment des dates), ce qui garantit que l'agenda
    reste chronologique même quand les dates sont en texte (« Mercredi 1 »
    sans année/mois explicite)

### Section FESTIVALS en début d'agenda
*   Nouveau **marqueur de date** : toute ligne avec `DATE = "Festivals"`
    est routée dans une section **FESTIVALS** placée en tête de l'agenda,
    juste avant la section "Coups de coeur et en bref"
*   Même **logique de mise en page** que la section "Coups de coeur" :
    formatage via `format_info(FESTIVAL, STYLE_FESTIVAL, NOM SPECTACLE 1)`,
    pas de puce ❑, pas d'étiquette `Bidul #xxx`, pas de séparateur de date
*   Les festivals des 2 fichiers sont **cumulés** dans la section globale
    (pas séparés par mois)
*   Idem pour la section "Coups de coeur et en bref"

### Séparateurs de mois — 2 styles au choix
Nouveau radio-button **"Style de séparation entre les 2 mois"** (visible
uniquement quand le mode été est activé), avec 2 options mutuellement
exclusives :

*   **Bandeau de mois (défaut)** : un gros `JUILLET` / `AOÛT` centré, en
    gras, taille majorée (×1.5), est inséré avant le 1er événement de
    chaque fichier. Implémenté via un placeholder `{{MONTH:NOM}}` dans le
    HTML et un nouveau kind `MONTH_HEADER` dans `textflow.py`
*   **Mois inline (Dimanche 12 Avril)** : aucun gros bandeau, mais le nom
    du mois est suffixé à chaque en-tête de date. Pratique quand les dates
    d'entrée sont en texte sans année (« Mercredi 1 » devient « Mercredi
    1 Avril »). Si l'affichage de la date contient déjà le mois (cas des
    dates ISO `2025-04-12` → `Dimanche 12 Avril 2025`), il n'est pas dupliqué

### Détection automatique du nom de mois
*   Le nom du mois affiché dans les séparateurs est **dérivé du nom de
    fichier** :
    1.  Recherche d'un nom de mois français en clair (avec ou sans accents :
        Avril, Mars, Août, Décembre, Fevrier, Aout, ...)
    2.  Fallback : préfixe `YYYYMM_` ou `YYYY-MM` (ex. `202604_…xlsx` →
        `Avril`, `2025-07 Bidul-304.xlsx` → `Juillet`)
    3.  Fallback ultime : `MOIS 1` / `MOIS 2`

### Intégration complète dans Import/Export config
*   Les 3 nouveaux champs (`summer_mode`, `input_file_2`,
    `summer_separator_style`) sont sauvegardés dans **les 3 chemins de
    sérialisation** : `save_current_config_from_app()`, dump debug au
    démarrage du pipeline, et chargement des defaults
*   Round-trip complet : exporter une config en mode été → la réimporter
    restaure la case 🌞, le chemin du 2ᵉ fichier, et le style de séparation
*   Variantes `_*` (`_summer_mode`, `_input_file_2`,
    `_summer_separator_style`) en plus des champs principaux, comme pour
    les autres options (`_date_grouping_enabled`, etc.)

## 🔧 Détails techniques

*   `biduleur/constants.py` : ajout de la constante `COLONNE_FESTIVALS =
    "Festivals"` (marqueur de date, analogue à `COLONNE_INFO = "Coups de
    coeur et en bref"`)
*   `biduleur/csv_utils.py` :
    *   Extraction d'un helper `_read_and_prepare_one_file()` pour la
        lecture per-file (validation colonnes, hyperlinks, filter inactif,
        conversion prix)
    *   `read_and_sort_file()` accepte un `filename_2: Optional[str]`,
        concatène les 2 DataFrames, et tag chaque ligne avec
        `_source_index` (0 ou 1)
    *   Tri étendu : `['info_last', '_source_index', 'Day',
        first_genre_col, HORAIRE]` (3 sections : FESTIVALS=0, INFO=1,
        events=2, puis par source pour préserver l'origine)
    *   Nouveau helper `_month_label_from_filename()` qui dérive le nom du
        mois d'un chemin de fichier
    *   `parse_bidul()` accepte `filename_2`, `summer_mode`,
        `summer_separator_style` et émet soit le placeholder
        `{{MONTH:NOM}}`, soit le suffixe inline sur la date
*   `biduleur/event_utils.py` : `if event[DATE] in (COLONNE_INFO,
    COLONNE_FESTIVALS)` au lieu du seul `COLONNE_INFO` — partage la même
    branche de rendu
*   `misenpageur/misenpageur/config.py` : 3 nouveaux champs dans la
    dataclass `Config` (`summer_mode: bool = False`, `input_file_2:
    Optional[str] = None`, `summer_separator_style: str = "banner"`)
*   `misenpageur/misenpageur/textflow.py` : nouveau kind `MONTH_HEADER`
    avec son style dédié (centré, bold, taille ×1.5) et regex
    `_MONTH_HEADER_RE` pour extraire le nom du mois du placeholder
*   `misenpageur/misenpageur/spacing.py` : politique d'espacement pour
    `MONTH_HEADER` (spaceBefore = `date_spaceBefore × 1.5`)
*   `leTruc/app.py` : 2 nouvelles `tk.StringVar`/`BooleanVar`
    (`input2_var`, `summer_mode_var`, `summer_separator_style_var`)
*   `leTruc/widgets.py` : checkbox 🌞, 2ᵉ drop zone (avec
    `drop_target_register`), et frame radio bandeau/inline
*   `leTruc/callbacks.py` : nouveaux callbacks `on_drop_input_file_2`,
    `on_pick_input_2`, `on_toggle_summer_mode` (gère la visibilité de la
    2ᵉ drop zone ET du frame radio)
*   `leTruc/_helpers.py` : `run_pipeline()` accepte les 3 nouveaux
    paramètres et les propage à `parse_bidul()` ; save/load wiring sur
    les 3 chemins de sérialisation

## 📚 Notes d'utilisation

*   Le mode été marche aussi bien avec des **dates ISO** qu'avec des
    **dates en texte** (style « Mercredi 1 » sans année/mois). Le tri par
    `_source_index` garantit que les événements d'avril ne se mélangent
    jamais avec ceux de mai, même quand les dates ont l'air ambiguës
*   Pour utiliser la **section FESTIVALS** sans le mode été, il suffit de
    mettre `DATE = "Festivals"` dans une ligne de xlsx — ça marche en mode
    normal
*   En mode été, **les 2 fichiers doivent avoir des colonnes spectacle
    compatibles** (GENRE N, NOM SPECTACLE N, etc.). Le set de colonnes le
    plus complet est conservé

---

# Bidul v1.8.1 - Export de config en mode normal, fix import texte Cucaracha

Petite version d'amélioration ergonomique de l'UI : bouton **Exporter config**
disponible en mode normal (pas seulement debug), et correction d'un bug
silencieux lors de l'import du texte Cucaracha.

## ✨ Nouveautés

### Bouton "💾 Exporter config" en mode normal
*   Nouveau bouton accessible **en permanence** (mode normal ET mode debug),
    à côté du bouton "📂 Importer config"
*   Permet de **sauvegarder l'état courant de l'UI** sous forme de fichier
    `config.json` à un emplacement choisi via une boîte de dialogue
*   Le nom suggéré par défaut est dérivé du fichier d'entrée :
    `<input_file>.config.json`
*   Le fichier produit est **directement compatible** avec le bouton
    "Importer config" pour un round-trip complet
*   Inclut tous les paramètres récents : `festival_subgroup_enabled`,
    `bidul_label_*`, `date_color`, `inline_images_auto_scale`,
    `date_grouping_enabled`, `festival_in_date_header`, etc.
*   Inclut aussi les méta-champs `_input_file`, `_abbreviations_enabled`,
    `_split_pdf`, `_print_pdf`, `_generate_html`, etc., comme dans la
    sauvegarde automatique du mode debug

### Boutons config toujours visibles
*   **Importer config** et **Exporter config** sont désormais visibles **en
    permanence** (mode normal ET debug)
*   **Reset config** reste réservé au mode debug (action destructive)

## 🐛 Corrections

### Texte Cucaracha non importé depuis le config
*   Quand un fichier config avec `cucaracha_box.content_type = "text"` était
    importé, le texte était écrit dans la `StringVar` mais **pas dans le
    widget `tk.Text`** affiché à l'utilisateur — le texte était donc
    silencieusement perdu et remplacé par une zone vide
*   Corrigé : le contenu est maintenant restauré dans le widget Text quand
    le type est "text", puis le `_on_run` lit bien la valeur attendue

## 🔧 Détails techniques

*   `leTruc/_helpers.py` : nouvelle fonction `save_current_config_from_app()`
    qui collecte toutes les variables Tkinter de l'`Application` et les
    sérialise en JSON via `asdict(cfg)` ; fix de la branche
    `cucaracha_box.content_value` dans `load_and_apply_config()` pour
    écrire dans le widget Text
*   `leTruc/app.py` : nouvelle méthode `_on_export_config()` qui ouvre une
    boîte de dialogue, suggère un nom, et appelle
    `save_current_config_from_app()` ; bouton "Exporter config" ajouté au
    `config_buttons_frame` ; frame désormais affiché par défaut
*   `leTruc/callbacks.py` : `on_toggle_config_buttons()` ne pack/unpack plus
    le frame entier (toujours visible) — seul le bouton Reset est
    conditionné au mode debug

## 📚 Bonus

*   `biduleur/constants.py` : ajout de "Gascogne" au dictionnaire
    `PROPER_NOUNS_MAP`

---

# Bidul v1.8.0 - Sous-groupement par festival, plages de dates, couleur, label Bidul, auto-scale images, normalisation des noms propres

Cette version étend considérablement les options de mise en page de l'agenda et du poster : **regroupement chronologique des dates consécutives**, **plages "Du X au Y"** via une nouvelle colonne, **sous-groupement par festival** quand plusieurs événements partagent la même valeur de FESTOCHE EVENEMENT, **couleur de police personnalisable** pour les dates, **étiquette "Bidul #xxx"** côté gauche, **auto-scaling des images inline** trop grandes, et un **dictionnaire de ~580 villes/pays** pour normaliser automatiquement la casse des noms propres dans la colonne STYLE.

## ✨ Nouveautés

### Sous-groupement par festival (`festival_subgroup_enabled`)
*   Quand plusieurs événements (≥ 2) partagent la **même date** ET la **même valeur de FESTOCHE EVENEMENT**, ils sont regroupés sous un sous-en-tête portant le nom du festival, suivi des événements avec une **puce différente** `▸` alignée avec la 1ère lettre du nom du festival
*   **Singletons** (1 seul événement avec ce festival ce jour-là) : comportement classique inchangé, festival inline avec ` // ` devant les artistes
*   Le sous-en-tête apparaît à la **position chronologique** du 1er événement du groupe dans la journée — les autres événements du groupe sont déplacés à sa suite
*   Le **style FESTOCHE / EVENEMENT** est ajouté en italique entre parenthèses dans le sous-en-tête (`Jazz Tangentes 2026 *(jazz en ville)*`)
*   Si l'événement en tête du groupe a un STYLE vide alors que d'autres l'ont rempli, le 1er STYLE non-vide trouvé dans le groupe est utilisé
*   La **même mise en page** est appliquée au poster (page 3)
*   Activation via la **case "Mise en Page Globale"** de l'UI (mode normal, désactivée par défaut)

### Regroupement des dates consécutives (`date_grouping_enabled`)
*   Les événements sur des **jours calendaires consécutifs** (ex: Sam 23 + Dim 24 août 2025) sont regroupés sous une date composite : `"Samedi 23 & Dimanche 24 Août 2025"`
*   Gère 2, 3 ou plus de jours consécutifs : `"Samedi 23, Dimanche 24 & Lundi 25 Août 2025"`
*   Gère les transitions de mois : `"Dimanche 31 Août & Lundi 1 Septembre 2025"`
*   Activation via UI en **mode debug** (section "Fonctions expérimentales Teriaki")

### Plage de dates par ligne (colonne `DATE FIN`)
*   Nouvelle colonne **optionnelle** `DATE FIN` dans le fichier Excel : si renseignée pour une ligne, l'événement est affiché avec une plage `"Du <début> au <fin>"`
*   Format intelligent selon le contexte :
    *   Même mois : `"Du Samedi 27 au Dimanche 28 Août 2016"`
    *   Mois différent : `"Du Dimanche 31 Août au Lundi 1 Septembre 2025"`
    *   Année différente : `"Du Mardi 31 Décembre 2024 au Mercredi 1 Janvier 2025"`
*   La colonne est **rétrocompatible** : si elle n'existe pas, aucun impact

### Couleur de police des dates (`date_color`)
*   Nouveau **sélecteur de couleur** dans la section "Configuration des dates" de l'UI
*   Aperçu temps réel via un widget de couleur cliquable
*   Défaut `#000000` (noir)
*   Importable/exportable via `config.json`

### Étiquette "Bidul #xxx" à gauche de la date (`bidul_label_enabled`)
*   Affiche **"Bidul #xxx"** en alignement gauche sur la même ligne qu'une date alignée à droite, où `xxx` est la valeur de la colonne `BIDUL`
*   **Couleur configurable** indépendamment de la couleur des dates
*   Utile pour les numéros d'archives ou les références éditoriales
*   Activation via la section "Configuration des dates" (mode normal)

### Festival dans l'en-tête de date (`festival_in_date_header`)
*   Mode expérimental : déplace la valeur de la colonne FESTOCHE EVENEMENT du 1er événement de la date dans l'en-tête (format `"Date -- Festival"`) au lieu de la préfixer dans chaque ligne
*   Utile quand 1 seul festival par date (cas non couvert par `festival_subgroup_enabled`)
*   Activation via UI en mode debug (section "Fonctions expérimentales Teriaki")

### Auto-scaling des images inline (`inline_images_auto_scale`)
*   Quand activée, une image trop grande pour la section courante (typiquement portrait ne rentrant pas dans S3/S4 hauteur 421pt) est **automatiquement réduite** pour tenir, en préservant le ratio d'aspect
*   Évite les espaces vides dus aux images droppées et la perte d'événements suivants
*   Activation via UI en mode debug (section "Images inline")

### Normalisation intelligente des noms propres dans le STYLE
*   La fonction `format_style` (rendu de la colonne FESTOCHE / EVENEMENT) effectue désormais un **lowercase intelligent** :
    *   Mots tout-en-majuscules → Title Case (`PARIS` → `Paris`)
    *   Mots déjà connus comme villes/pays → casse correcte préservée (`paris` → `Paris`, `le mans` → `Le Mans`, `new york` → `New York`)
    *   Reste du texte en lowercase classique
*   **Dictionnaire de ~580 noms propres** dans `biduleur/constants.py` (`PROPER_NOUNS_MAP`) :
    *   Toutes les **préfectures de France** (métropole + DOM-TOM)
    *   **County towns d'Angleterre** (~48)
    *   **Capitales européennes** (FR + EN/locale)
    *   **Capitales des 50 États américains** + grandes villes US
    *   **Villes locales de la Sarthe** (Le Mans, Sablé-sur-Sarthe, Yvré-l'Évêque, etc.)
    *   **Pays** (FR + EN, ~80)
*   L'utilisateur peut **étendre le dictionnaire** directement dans `constants.py`

## 🔧 Améliorations algorithme de mise en page

### Recherche binaire alignée sur le rendu réel
*   `_simulate_allocation_at_fs` utilise désormais **`plan_pair_with_split`** (paire-aware) au lieu de `measure_fit_at_fs` (par-section), pour aligner la recherche binaire sur le rendu réel et **éviter de sous-estimer ce qui rentre**
*   La police auto-calculée monte plus haut quand c'est possible

### Contrainte anti-orphelin étendue
*   Auparavant, une DATE n'était pas placée seule en bas de section uniquement si le paragraphe suivant était un EVENT
*   Maintenant : la contrainte couvre aussi les paragraphes IMAGE (placeholders d'images inline)
*   Helper `_compute_next_para_need()` centralise la logique pour les 5 emplacements concernés

### Helper `_compute_image_dimensions()`
*   Centralise le calcul des dimensions d'image (taille naturelle + auto-scaling éventuel)
*   Utilisé uniformément par les fonctions de mesure (`measure_fit_at_fs`), de rendu (`draw_section_*`) et de planification (`plan_pair_with_split`)

## 🐛 Corrections

### `pd.NaT` dans `_parse_date`
*   `pd.NaT` (pandas Not-a-Time) passait l'`isinstance(x, pd.Timestamp)` puis crashait sur `weekday()` (qui retourne `nan` au lieu d'un int)
*   Avant ce fix, un fichier Excel avec une colonne `DATE FIN` majoritairement vide générait un PDF entièrement vide
*   Corrigé : détection explicite de NaT/None/NaN scalaires en amont du parsing

### Polices avec variantes manquantes
*   Documentation : pour qu'une police affiche les styles **Bold** et **Italic** des dates, le fichier de fonte doit posséder les variantes correspondantes
*   Exemple : Calibri Light n'a pas de variante Bold sur Windows → le gras est silencieusement ignoré (fallback regular)
*   Préférer Calibri (sans Light) ou Arial pour bénéficier des 4 variantes complètes

## 🔧 Détails techniques

*   `biduleur/constants.py` : constante `BIDUL_COL`, `DATE_FIN`, `SUBFEST_PREFIX` ; nouveau dictionnaire `PROPER_NOUNS_MAP` (~580 entrées)
*   `biduleur/csv_utils.py` : `_apply_date_range_display()` pour les plages DATE FIN, `_group_consecutive_dates()` pour le regroupement chronologique, `_format_du_au_range()` pour les plages, calcul des comptes (date, festival) et des positions effectives pour le sous-groupement
*   `biduleur/event_utils.py` : émission du sous-en-tête festival, marker `{{SUBEV}}` pour les événements de sous-groupe, placeholder `{{BIDUL:xxx}}` pour l'étiquette
*   `biduleur/format_utils.py` : helper `_smart_lower()` avec normalisation des noms propres via `PROPER_NOUNS_MAP`
*   `misenpageur/misenpageur/config.py` : champs `inline_images_auto_scale`, `date_color`, `bidul_label_enabled`, `bidul_label_color`, `festival_subgroup_enabled`, `date_grouping_enabled`, `festival_in_date_header`
*   `misenpageur/misenpageur/textflow.py` : classification `SUBEVENT`, helper `_compute_image_dimensions()`, helper `_compute_next_para_need()`, helper `_draw_bidul_label()`, `configure_bidul_label()`, style SUBEVENT (puce ▸ via DejaVuSans, indent aligné, spacing serré)
*   `misenpageur/misenpageur/draw_logic.py` : `_simulate_allocation_at_fs` utilise `plan_pair_with_split`, `configure_bidul_label()` au début du rendu
*   `leTruc/widgets.py` : nouvelles sections "Fonctions expérimentales Teriaki" (debug) et options dans "Mise en Page Globale" et "Configuration des dates"
*   `leTruc/app.py`, `leTruc/callbacks.py`, `leTruc/_helpers.py` : ~10 nouvelles variables Tkinter, plumbing complet, sauvegarde/import config.json

---

# Bidul v1.7.0 - Images inline, colonnes spectacles dynamiques et formats de date étendus

Cette version introduit le support des **images inline** dans le PDF, un nombre **dynamique** de colonnes de spectacles dans le fichier Excel, de **nouveaux formats de date** (`YYYY`, `MM-YYYY`) pour l'affichage d'événements historiques, et apporte plusieurs corrections importantes.

## ✨ Nouveautés

### Images inline dans l'agenda
*   **Nouveau type d'entrée Excel** : en définissant `GENRE 1 = "img"` et en renseignant le **nom du fichier image** dans la colonne `NOM SPECTACLE 1`, l'image est insérée directement dans le corps de l'agenda à sa position chronologique
*   Les images sont automatiquement **centrées horizontalement** et leur **hauteur est intégrée** au calcul automatique de la taille de police
*   **Contrôles UI (mode debug)** dans la nouvelle section "Images inline" :
    *   Checkbox pour activer/désactiver la fonctionnalité (désactivée par défaut)
    *   Sélecteur de dossier personnalisé pour les images (défaut : `misenpageur/assets/images/`)
    *   **Facteur d'échelle** (0.0 - 1.0, défaut 0.85) pour ajuster la largeur des images par rapport à la section
    *   **Marge (pt)** avant/après chaque image (défaut 1.0pt)
*   Tous ces paramètres sont **importables/exportables** via `config.json`

### Colonnes spectacles dynamiques
*   Le nombre de colonnes de spectacles n'est plus fixé à 4 : le système détecte automatiquement toutes les colonnes `GENRE N`, `NOM SPECTACLE N`, `COMPAGNIE N`, `STYLE N` présentes dans le fichier Excel
*   Support vérifié jusqu'à 10 colonnes (utile pour les événements de type festival avec de nombreuses scènes)

### Formats de date étendus (utile pour les archives historiques)
*   **Format `YYYY`** (ex: `2005`) → rendu tel quel `2005`
*   **Format `MM-YYYY`** (ex: `08-2021`) → rendu en français `Août 2021`
*   Les clés de tri sont **normalisées** au format `YYYY-MM-DD` pour un tri chronologique cohérent entre toutes les dates (partielles et complètes)
*   Les dates partielles (année seule ou mois-année) se placent en début de période, **avant** les dates précises du même mois/année

### Parsing des dates Excel robuste
*   Les objets `Timestamp`/`datetime` d'Excel sont directement reconnus et formatés en français : `"Mercredi 18 Mars 2026"`
*   Les valeurs numériques (`int`/`float` comme `2005`) sont correctement interprétées comme des années
*   Support des formats ISO avec et sans heure (`2014-08-31`, `2014-08-31 00:00:00`)

### Hyperliens Excel cliquables dans le PDF
*   Les hyperliens définis dans les cellules Excel sont extraits via `openpyxl` et rendus **cliquables** dans le PDF final
*   Support du format `"url|texte_affiché"` pour un contrôle fin
*   Les URLs sans protocole sont automatiquement complétées avec `https://`

## 🐛 Corrections

### Chemins SVG corrigés lors de l'import de config
*   Les fichiers SVG ressources du projet (`logos.svg`, `ours.svg`, `logos.impression.svg`) étaient résolus par rapport au dossier du fichier `config.json` au lieu de la racine du projet
*   **Résultat** : après import d'une config issue d'un `debug_run_.../`, les chemins pointaient vers `debug_run_.../misenpageur/assets/logos.svg` (introuvables) au lieu de `<projet>/misenpageur/assets/logos.svg`
*   Corrigé : ces chemins utilisent désormais la racine du projet (`resource_root`)

### Type de séparateur de dates non importé depuis la config
*   Quand `date_line.enabled=false` et `date_box.enabled=false` dans le fichier config, le séparateur restait à sa valeur précédente (par défaut "ligne") au lieu de passer à "aucun"
*   Les trois cas (`ligne`, `box`, `aucun`) sont maintenant correctement gérés à l'import

### Bug de casing sur les abréviations nobr
*   Les occurrences d'un même mot nobr dans des casses différentes (ex: `"BEAUFAY"` et `"Beaufay"`) étaient inversées lors de la restauration
*   Corrigé : chaque occurrence utilise désormais un placeholder unique `___NOBR_{i}_{counter}___`

### "NAN" affiché pour les champs artistes vides
*   Les valeurs `float('nan')` de pandas apparaissaient comme `"nan"` (string truthy) dans le texte rendu
*   Corrigé : `_to_str()` filtre désormais `float('nan')` et la string `"nan"` en chaîne vide

## 🔧 Détails techniques

*   `biduleur/constants.py` : constante `GENRE_EVT_IMAGE = 'img'`, fonction `detect_spectacle_columns()` par regex
*   `biduleur/csv_utils.py` : `_parse_date()` gère les types `int`, `float`, `datetime`/`Timestamp` ; parsing `YYYY` et `MM-YYYY` ; `_extract_hyperlinks()` via openpyxl
*   `biduleur/event_utils.py` : colonnes spectacles dynamiques, détection des images (`{{IMG:filename}}`)
*   `biduleur/format_utils.py` : `_normalize_url()`, filtrage NaN, skip des images dans `format_artists_styles()`
*   `misenpageur/misenpageur/textflow.py` : classification `IMAGE`/`EVENT`/`DATE`, `_calc_image_height_for_width()`, `configure_inline_images()`, rendu via `c.drawImage()` centré
*   `misenpageur/misenpageur/draw_logic.py` : appel `configure_inline_images()` au début du rendu, filtrage des images du poster
*   `misenpageur/misenpageur/abbreviations.py` : placeholders nobr uniques par occurrence
*   `misenpageur/misenpageur/config.py` : champs `inline_images_enabled`, `inline_images_dir`, `inline_images_scale`, `inline_images_margin`
*   `leTruc/widgets.py` : nouvelle section `_create_inline_images_section()` (debug-only)
*   `leTruc/app.py`, `leTruc/callbacks.py`, `leTruc/_helpers.py` : variables Tkinter, toggle debug, validation numérique, câblage run_pipeline, sauvegarde/import config.json

---

# Bidul v1.6.1 - Le Biduloscope ajouté à l'ours et améliorations des dates du poster

Icône de Radio Alpa et texte ajouté à ours.svg. Hyperlink box ajoutée à config.yml. 
Dates du poster suivant le même style que celui du coprs de texte.

## ✨ Nouveautés

### Style des dates unifié dans le poster
*   Les dates du poster (page 3) utilisent désormais le **même style que le corps principal** : police, gras/italique, alignement et boîte de fond
*   Les paramètres `date_box` et `date_style` de la config sont appliqués au poster (auparavant ignorés)

# Bidul v1.6.0 - Première version complète prête pour l'utilisateur

Tag créé sans changement de code pour marquer un changement de version majeur.

# Bidul v1.5.3 - Poster automatique : remplissage fiable et complet

Cette version refond entièrement le calcul de la taille de police du poster pour que **tout le contenu soit toujours affiché**, sans aucun réglage manuel.

## ✨ Nouveautés

### Poster entièrement automatique
*   La mesure de texte du poster utilise désormais **exactement le même pipeline Frame** que le rendu réel (ReportLab), éliminant les divergences entre estimation et affichage
*   L'espacement des dates est intégré directement dans le style des paragraphes (`spaceBefore`/`spaceAfter`) au lieu de `Spacer` séparés, ce qui optimise l'utilisation de l'espace aux transitions de colonnes
*   La recherche binaire descend automatiquement jusqu'à **3pt** si nécessaire pour afficher la totalité du contenu (auparavant bloquée à 6pt)
*   Le **facteur de sécurité police** n'est plus appliqué (défaut = 1.0) — il reste accessible en mode debug si besoin
*   Un avertissement est loggé si la taille de police descend sous le minimum configuré

### Widget "Facteur de sécurité police" masqué en mode normal
*   Le champ est désormais réservé au mode debug (il ne devrait plus être nécessaire)

## 🔧 Détails techniques

*   `misenpageur/misenpageur/textflow.py` : nouvelle fonction `_build_poster_story()` partagée entre mesure et rendu ; `measure_poster_fit_at_fs()` réécrite avec Frame + canvas jetable ; `draw_poster_text_in_frames()` simplifiée
*   `misenpageur/misenpageur/draw_logic.py` : plancher de recherche abaissé à 3pt, suppression du facteur de sécurité, logs de diagnostic détaillés
*   `misenpageur/misenpageur/config.py` : `font_size_safety_factor` default = 1.0
*   `misenpageur/config.yml` : `font_size_safety_factor: 1.0`
*   `leTruc/widgets.py` : widget facteur de sécurité stocké sur `app` pour toggle debug
*   `leTruc/callbacks.py` : ajouté aux `debug_only_widgets`
*   `leTruc/app.py`, `leTruc/_helpers.py` : défaut du facteur mis à 1.0

---

# Bidul v1.5.2 - Génération HTML optionnelle, corrections logos et build

Cette version rend la génération des fichiers HTML optionnelle, corrige le rendu des logos SVG en mode normal, et raccourcit les noms d'artifacts du build GitHub.

## ✨ Nouveautés

### Génération HTML optionnelle
*   **Nouvelle option "Générer les fichiers HTML (biduleur et agenda)"** dans la section Sortie
    *   Par défaut désactivée : les fichiers HTML intermédiaires sont créés en temporaire puis nettoyés
    *   Lorsqu'activée, les fichiers HTML sont générés aux chemins configurés (comme avant)
    *   L'option est visible en mode normal et en mode debug
    *   Les champs de chemin HTML ne s'affichent que si l'option est activée

### Build GitHub Actions : nommage court
*   Les builds manuels utilisent désormais le **hash court du commit** (`DEV-abc1234`) au lieu du nom de branche
*   Corrige les erreurs "path too long" sous Windows lors de la décompression d'artifacts issus de branches au nom long

## 🐛 Corrections

### Logos SVG non rendus en mode normal
*   Le mode de rendu par défaut des logos (`logos_layout`) était `"colonnes"` (PNG) dans le dataclass Config, alors que le GUI proposait `"svg"`
*   En mode non-debug, la valeur du GUI n'était jamais appliquée → les logos SVG n'étaient pas rendus
*   Corrigé : le défaut est désormais `"svg"` dans le dataclass et dans `config.yml`

### Crash couverture absente
*   Corrigé un `OSError` quand `cover_image` est `None` ou vide dans la config
*   Le pipeline ne plante plus si aucune image de couverture n'est configurée
*   Un message d'avertissement est loggé si le fichier est introuvable

## 🔧 Détails techniques

*   `leTruc/app.py` : variable `generate_html_var` (BooleanVar)
*   `leTruc/widgets.py` : checkbox HTML en row 0, réorganisation des rows de la section Sortie
*   `leTruc/callbacks.py` : `on_toggle_html_widgets()` pour afficher/masquer les champs de chemin HTML
*   `leTruc/_helpers.py` : paramètre `generate_html`, fichiers temporaires via `tempfile.mkstemp()`, nettoyage en `finally`
*   `misenpageur/misenpageur/config.py` : `logos_layout` default changé de `"colonnes"` à `"svg"`
*   `misenpageur/config.yml` : ajout de `logos_layout: "svg"`
*   `misenpageur/misenpageur/draw_logic.py` : guard `if cfg.cover_image` avant `os.path.join()`
*   `misenpageur/misenpageur/drawing.py` : vérification d'existence du fichier dans le fallback de `draw_s2_cover`
*   `.github/workflows/bidul.release.yml` : version manuelle `DEV-<sha>` au lieu de `MANUAL-<branch>-<sha>`

---

# Bidul v1.5.1 - Fichiers d'impression et prévisualisation polices

Cette version ajoute la génération de fichiers d'impression avec logos optimisés, la prévisualisation des polices dans les sélecteurs, et des corrections d'import de config.

## ✨ Nouveautés

### Fichiers d'impression (logos optimisés)
*   **Nouvelle option "Créer fichiers d'impression"** dans la section Sortie
    *   Génère un second jeu de fichiers (PDF, PDF par page, SVG) avec le suffixe `.impression`
    *   Utilise un fichier SVG logos spécifique pour l'impression (`logos.impression.svg`)
    *   Le chemin du SVG logos impression est configurable en mode debug (section Paramètres des Logos)
    *   Compatible avec "Générer un PDF par page" et "Générer des SVG éditables"

### Prévisualisation des polices
*   **Labels de prévisualisation** à côté des 4 sélecteurs de polices (corps, dates, cucaracha, stories)
*   Chaque label affiche le nom de la police **rendu dans sa propre typographie**
*   Mise à jour instantanée au changement de sélection

### Chemins par défaut pour les SVG logos et ours
*   Les fichiers `logos.svg`, `logos.impression.svg` et `ours.svg` ont désormais des **chemins par défaut** dans le dataclass Config et config.yml
*   Corrige le problème où les logos/ours n'étaient pas trouvés dans le build GitHub

## 🐛 Corrections

### Import de config : vignette cucaracha
*   La **vignette de l'image cucaracha** est désormais générée lors de l'import d'une config (comme c'est déjà le cas pour la couverture)

## 🔧 Détails techniques

*   `misenpageur/assets/logos.impression.svg` : nouveau fichier SVG logos pour impression (inclus dans le build)
*   `misenpageur/misenpageur/config.py` : champ `logos_print_svg_file` avec valeur par défaut
*   `leTruc/widgets.py` : checkbox "Créer fichiers d'impression" + champ SVG impression + labels preview polices
*   `leTruc/callbacks.py` : `_on_font_selected()` pour les previews + toggle du champ SVG impression + bouton Parcourir
*   `leTruc/_helpers.py` : 2e passe pipeline avec substitution logos SVG, export/import config `_print_pdf`
*   `leTruc/app.py` : variables `print_pdf_var` et `logos_print_svg_var`

---

# Bidul v1.5.0 - Mode debug, polices et poster

Cette version améliore l'interface utilisateur en masquant les paramètres avancés en mode normal, corrige l'import de la couverture et recentre l'image du poster.

## ✨ Nouveautés

### Paramètres avancés réservés au mode debug
*   Les paramètres suivants sont désormais **visibles et éditables uniquement en mode debug** :
    *   Path ours (section complète)
    *   Path logos (section complète)
    *   Avec couv' (checkbox)
    *   Marge globale (mm)
    *   Espace avant/après dates (pt)
*   En mode normal, ces paramètres utilisent les **valeurs par défaut de config.yml**

### Sélecteurs de polices indépendants
*   **Polices distinctes** pour le corps de texte, les dates et les stories Instagram
*   Chaque sélecteur propose toutes les polices système découvertes dynamiquement (~85 sur un Windows typique)
*   Les choix de polices sont sauvegardés/restaurés via l'export/import config

### Poster : image recentrée (Design 0)
*   L'image de couverture du poster ("Image au centre") est **recentrée légèrement vers la droite** pour un meilleur rendu visuel
*   Les colonnes 1 et 3 conservent leur largeur et hauteur d'origine

## 🐛 Corrections

### Import de la couverture
*   La **zone de dépôt visuelle** de l'image de couverture est désormais mise à jour lors de l'import d'une config (le chemin était correctement chargé, mais l'aperçu et le texte de la drop zone n'étaient pas rafraîchis)

## 🔧 Détails techniques

*   `leTruc/widgets.py` : références aux widgets debug-only stockées sur `app` pour le toggle
*   `leTruc/callbacks.py` : `on_toggle_config_buttons()` gère `grid()`/`grid_remove()` des widgets avancés
*   `leTruc/_helpers.py` : surcharges ours/logos/marge/espacement déplacées dans le bloc `if debug_mode:`
*   `leTruc/_helpers.py` : appel `_update_cover_drop_zone()` après import config
*   `misenpageur/misenpageur/draw_logic.py` : décalage de 5pt vers la droite pour l'image poster design 0

---

# Bidul v1.4.5 - Menu Aide et PDF par page

Cette version ajoute un menu Aide complet dans le GUI et la possibilité de générer un PDF par page.

## ✨ Nouveautés

### Menu Aide
*   **Nouveau menu "Aide"** dans la barre de menu avec 3 entrées :
    *   **Guide utilisateur** : Documentation complète intégrée (démarrage rapide, format d'entrée, options, etc.)
    *   **Notes de version** : Affiche le contenu du fichier RELEASE_NOTES.md
    *   **À propos / Crédits** : Version, description et lien cliquable vers le dépôt GitHub

### Génération PDF par page
*   **Nouvelle option "Générer un PDF par page"** dans la section Sortie
    *   Génère des fichiers séparés : `bidul_page1.pdf`, `bidul_page2.pdf`, `bidul_page3.pdf`
    *   Le PDF complet est toujours généré en plus
    *   Utilise PyMuPDF pour un split rapide et sans perte de qualité
    *   Option sauvegardée/restaurée avec l'import/export config (mode debug)

## 🔧 Détails techniques

*   Nouveau module `leTruc/menu.py` pour les dialogues du menu
*   Nouvelle fonction `split_pdf_pages()` dans `pdfbuild.py`
*   Paramètre `split_pdf` ajouté à `run_pipeline()`
*   Champ `_split_pdf` ajouté au fichier `config.json` exporté en mode debug

---

# Bidul v1.4.4 - Optimisations Performance et Bouton Stop

Cette version apporte des améliorations significatives de performance et ajoute un bouton Stop pour interrompre le traitement en cours.

## ✨ Nouveautés

### Bouton Stop pour interrompre le workflow
*   **Interruption propre du pipeline** : Un bouton "⏹ Stop" apparaît pendant le traitement
    *   Permet d'arrêter le workflow à tout moment entre les étapes
    *   Le pipeline s'arrête proprement à la prochaine vérification
    *   Message "Interrompu." affiché sans popup d'erreur
    *   Le bouton disparaît automatiquement à la fin du traitement

### Optimisations de performance
*   **Cache des icônes** (`textflow.py`) : L'aspect ratio des icônes chapeau/free est calculé une seule fois
    *   Gain estimé : 3-5x pour les documents avec beaucoup d'événements "au chapeau" ou "0€"

*   **Regex compilées au niveau module** (`textflow.py`) : 6 regex compilées au chargement du module
    *   `_CHAPEAU_PATTERN`, `_FREE_PATTERN`, `_HTML_TAG_PATTERN`
    *   `_HEAD_BR_PATTERN`, `_TAIL_BR_PATTERN`, `_MULTI_BR_PATTERN`
    *   Gain estimé : 5-10%

*   **Cache des images haute qualité** (`drawing.py`) : Évite de recharger/redimensionner la même image
    *   Particulièrement utile pour l'image de couverture du poster
    *   Gain estimé : 20-30% sur le poster

*   **Cache des ParagraphStyle** (`textflow.py`) : Les styles ReportLab sont réutilisés
    *   Clé de cache basée sur les paramètres pertinents (kind, font_size, bullet_cfg, date_box)
    *   Gain estimé : 10-20%

*   **Guard d'enregistrement des polices** (`fonts.py`) : Évite les recherches de fichiers redondantes
    *   Les polices déjà enregistrées sont ignorées
    *   Utile en mode batch ou lors de générations multiples

## 🛠️ Fonctions utilitaires ajoutées

```python
# Vider les caches entre les sessions (si les configs changent)
from misenpageur.misenpageur.textflow import clear_style_cache
from misenpageur.misenpageur.drawing import clear_image_cache
from misenpageur.misenpageur.fonts import is_font_registered
```

## 🔧 Détails techniques

*   Nouveau paramètre `stop_event` dans `run_pipeline()` pour signaler l'arrêt
*   Exception `StopRequestedException` pour gérer l'interruption proprement
*   Vérifications d'arrêt à chaque étape du pipeline (avant analyse, HTML, PDF, SVG, Stories)

---

# Bidul v1.4.3 - Puces Proportionnelles et Améliorations Debug

Cette version améliore le rendu des puces d'événements et enrichit le mode debug pour faciliter la reproduction des configurations.

## ✨ Nouveautés

### Puces proportionnelles à la taille du texte
*   **Taille de puce ajustable** : La puce (❑) s'adapte maintenant à la taille de la police du texte
    *   Nouveau paramètre `bullet_size_ratio` dans `config.yml` (défaut: 0.8 = 80% de la taille du texte)
    *   Utilise `bulletFontSize` natif de ReportLab pour un rendu optimal
    *   Résout le problème des puces disproportionnées sur le poster

### Mode Debug amélioré
*   **Configuration complète dans `config.json`** : Le fichier debug inclut maintenant :
    *   `_input_file` : Chemin du fichier d'entrée utilisé
    *   `_abbreviations_enabled` : État des abréviations activées
    *   Permet de reproduire exactement une génération précédente

*   **Mode debug configurable via `config.yml`** :
    *   Nouveau paramètre `debug_mode: true/false`
    *   La checkbox "Mode Debug" du GUI reflète la valeur du fichier config au démarrage

### Import de configuration enrichi
*   **Import complet depuis `config.json`** : L'import d'une config debug restaure maintenant :
    *   Le fichier d'entrée (affiché dans la zone de dépôt)
    *   L'état des checkboxes d'abréviations
    *   Le mode debug
    *   Tous les autres paramètres existants

## ⚙️ Nouveaux paramètres config.yml

```yaml
# Puces
bullet_size_ratio: 0.8  # Ratio taille puce / taille texte (0.8 = 80%)

# Debug
debug_mode: false  # Active le mode debug au démarrage du GUI
```

## 🔧 Corrections

*   Correction de l'alignement des lignes multilignes avec la puce (hanging indent)
*   La zone de dépôt du fichier d'entrée se met à jour correctement lors de l'import de config

---

# Bidul v1.4.2 - Système d'Abréviations Automatiques

Cette version introduit un système complet d'abréviations pour réduire automatiquement la longueur du texte et optimiser la taille de police. Le système comprend 22 abréviations configurables, un décodage intelligent des entités HTML, une normalisation Unicode, et une protection des noms propres.

## ✨ Nouveautés

*   **Système d'abréviations automatique** : Réduit le texte AVANT le calcul de la taille de police :
    *   22 abréviations prédéfinies (9 activées par défaut)
    *   Configuration centralisée dans `abbreviations.yml`
    *   Interface graphique avec 22 checkboxes organisées en **4 colonnes** (toutes visibles sans scrollbar)
    *   Boutons "✓ Tout activer" / "✗ Tout désactiver"
    *   Exemples : `théâtre` → `th.`, `association` → `asso.`, `centre culturel` → `cc`

*   **Préservation intelligente de la casse** : Le remplacement adapte automatiquement la casse d'origine :
    *   `théâtre` → `th.` (minuscules)
    *   `Théâtre` → `Th.` (capitalisé)
    *   `THÉÂTRE` → `TH.` (majuscules)
    *   `Centre Culturel` → `CC` (Title Case multi-mots)

*   **Décodage automatique des entités HTML** : Les caractères accentués encodés en HTML sont correctement traités :
    *   `Th&eacute;&acirc;tre` → `Théâtre` (décodage avant remplacement)
    *   Résout les problèmes d'export Excel avec entités HTML
    *   Application transparente (pas de configuration requise)

*   **Normalisation Unicode (NFC)** : Compatibilité totale entre Windows, macOS et Linux :
    *   Gère les deux formes Unicode (NFC composée et NFD décomposée)
    *   Garantit que `théâtre` (Windows) == `théâtre` (macOS)
    *   Fonctionne avec tous les caractères accentués français (é, è, ê, à, â, ç, ô, etc.)

*   **Protection des noms propres (nobr)** : Les expressions dans `nobr.txt` ne sont jamais abrégées :
    *   Fichier : `misenpageur/assets/textes/nobr.txt`
    *   Protection insensible à la casse
    *   Exemples protégés : "Théâtre de l'Écluse", "Association Bidul", "Centre Culturel La Chapelle"
    *   Algorithme en 3 phases : remplacement temporaire → abréviations → restauration
    *   Log : `[DEBUG] X expression(s) nobr protégée(s)`

*   **Word boundaries intelligents** : Évite les remplacements partiels :
    *   `Théâtre Municipal` → `Th. Municipal` ✅
    *   `Théâtralité` → `Théâtralité` (inchangé) ✅
    *   Tri par longueur décroissante pour traiter les expressions composées en premier

*   **Logging détaillé** : Statistiques complètes des remplacements :
    *   `[INFO] Application de 7 abréviation(s)...`
    *   `[INFO] Total: 23 remplacement(s) effectué(s)`
    *   `[DEBUG] - théâtre → th.: 12x`
    *   Export debug : `abbreviations.json` avec stats par abréviation

*   **Interface 4 colonnes** : Toutes les abréviations visibles sans scrollbar :
    *   Ancienne version : 2 colonnes avec scrollbar vertical
    *   Nouvelle version : 4 colonnes, ~6 lignes par colonne
    *   Chargement dynamique depuis `abbreviations.yml`
    *   Gestion des erreurs gracieuse (fallback si fichier absent)

## ⚙️ Pour les Développeuses et Développeurs

*   **Architecture séparée** : Configuration YAML dédiée aux abréviations :
    ```
    bidul/
    └── misenpageur/
        ├── abbreviations.yml          ← 22 abréviations
        ├── config.yml                 ← Autres paramètres (sans section abbreviations)
        └── assets/
            └── textes/
                └── nobr.txt           ← Expressions à protéger (optionnel)
    ```

*   **Module `abbreviations.py`** : Logique complète de traitement :
    ```python
    # Fonctions principales
    load_abbreviations_from_yaml(yaml_path)  # Chargement depuis YAML
    get_default_abbreviations()              # Cache intelligent
    reload_abbreviations()                   # Rechargement forcé
    apply_abbreviations_to_paragraphs(paras, abbrevs, nobr)  # Application
    
    # Dataclasses
    @dataclass
    class Abbreviation:
        key: str
        original: str
        replacement: str
        description: str
        enabled: bool
    
    @dataclass
    class AbbreviationsConfig:
        abbreviations: Dict[str, Abbreviation]
    ```

*   **Décodage HTML dans `_helpers.py`** : Avant l'application des abréviations :
    ```python
    import html
    
    # Décoder les entités HTML : "Th&eacute;&acirc;tre" → "Théâtre"
    paras_decoded = [html.unescape(p) for p in paras]
    
    # Charger les expressions nobr
    nobr_expressions = []
    nobr_file = os.path.join(project_root, "assets", "textes", "nobr.txt")
    if os.path.exists(nobr_file):
        with open(nobr_file, 'r', encoding='utf-8') as f:
            nobr_expressions = [line.strip() for line in f if line.strip()]
    
    # Appliquer les abréviations avec protection nobr
    paras, abbreviation_stats = apply_abbreviations_to_paragraphs(
        paras_decoded,
        enabled_abbrevs,
        nobr_expressions
    )
    ```

*   **Normalisation Unicode partout** : Cohérence NFC dans tout le pipeline :
    ```python
    import unicodedata
    
    # Dans load_abbreviations_from_yaml()
    for key, value in data.items():
        if isinstance(value, dict) and 'original' in value:
            value['original'] = unicodedata.normalize('NFC', value['original'])
    
    # Dans _create_replacement_pattern()
    normalized = unicodedata.normalize('NFC', original)
    
    # Dans apply_abbreviations_to_paragraphs()
    modified = unicodedata.normalize('NFC', para)
    ```

*   **Protection nobr avec placeholders** : Algorithme en 3 phases :
    ```python
    # Phase 1 : Remplacement temporaire
    for i, nobr_expr in enumerate(nobr_expressions):
        placeholder = f"___NOBR_{i}___"
        modified = re.sub(re.escape(nobr_expr), placeholder, modified, flags=re.IGNORECASE)
    
    # Phase 2 : Application des abréviations (les placeholders ne matchent pas)
    for abbr in sorted_abbrevs:
        modified = pattern.sub(replacer, modified)
    
    # Phase 3 : Restauration des expressions originales
    for placeholder, original_text in protected_zones:
        modified = modified.replace(placeholder, original_text, 1)
    ```

*   **Interface 4 colonnes dans `widgets.py`** : Calcul automatique des positions :
    ```python
    # Configuration pour 4 colonnes
    keys = list(abbrev_data.keys())
    num_cols = 4
    rows_per_col = (len(keys) + num_cols - 1) // num_cols  # Arrondi supérieur
    
    for i, key in enumerate(keys):
        # Calcul position : 4 colonnes
        col = i // rows_per_col
        row_in_grid = (i % rows_per_col) + 1  # +1 pour sauter la description
        
        cb = tk.Checkbutton(abbrev_frame, text=description, variable=var)
        cb.grid(row=row_in_grid, column=col, sticky="w", padx=10, pady=2)
    ```

*   **Pipeline d'exécution** : Ordre critique pour maximiser le gain d'espace :
    ```python
    # 1. Extraction des paragraphes HTML
    paras = extract_paragraphs_from_html(html_text)
    
    # 2. Décodage des entités HTML
    paras = [html.unescape(p) for p in paras]
    
    # 3. Chargement nobr
    nobr_expressions = load_nobr_from_file("nobr.txt")
    
    # 4. Application des abréviations (AVANT calcul taille)
    paras, stats = apply_abbreviations_to_paragraphs(paras, abbrevs, nobr_expressions)
    
    # 5. Calcul taille de police optimale
    font_size = calculate_optimal_font_size(paras)
    
    # 6. Génération du PDF
    build_pdf(paras, font_size)
    ```

*   **Format YAML des abréviations** : Structure simple et extensible :
    ```yaml
    # Préfixes honorifiques
    sainte:
      original: "sainte"
      replacement: "ste"
      description: "Sainte → Ste"
      enabled: false
    
    # Lieux
    theatre:
      original: "théâtre"
      replacement: "th."
      description: "Théâtre → Th."
      enabled: true
    
    centre_culturel:
      original: "centre culturel"
      replacement: "cc"
      description: "Centre Culturel → CC"
      enabled: true
    ```

*   **Export debug** : Fichier `abbreviations.json` avec statistiques :
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

---

## 📦 Fichiers Modifiés

### Module `misenpageur`

*   `misenpageur/abbreviations.yml` **[NOUVEAU]** (~3,3 Ko)
    - Configuration complète des 22 abréviations
    - Organisation par catégories (honorifiques, voies, lieux, événements, pratique, divers)
    - 9 abréviations activées par défaut
    - Commentaires explicatifs sur la préservation de la casse

*   `misenpageur/misenpageur/abbreviations.py` **[NOUVEAU]** (~9 Ko)
    - Module complet de gestion des abréviations
    - Fonctions : `load_abbreviations_from_yaml()`, `get_default_abbreviations()`, `reload_abbreviations()`
    - Fonction `apply_abbreviations_to_paragraphs()` avec support nobr
    - Fonction `_preserve_case()` pour la préservation de casse
    - Fonction `_create_replacement_pattern()` avec normalisation Unicode
    - Dataclasses : `Abbreviation`, `AbbreviationsConfig`
    - Cache global `_cached_abbreviations`
    - Logging détaillé (INFO, DEBUG)

*   `misenpageur/misenpageur/config.py` (~10 lignes supprimées)
    - Suppression du champ `abbreviations: Dict[str, Any]` (déplacé vers abbreviations.yml)
    - Suppression de la méthode `get_abbreviations_config()`
    - Suppression de l'import du module abbreviations
    - Note ajoutée : "Les abréviations sont dans abbreviations.yml"

*   `misenpageur/assets/textes/nobr.txt` **[NOUVEAU]** (optionnel)
    - Fichier texte avec expressions à protéger (une par ligne)
    - Exemples : "Théâtre de l'Écluse", "Association Bidul", etc.
    - Commentaires ignorés (lignes vides)

### Module `letruc` (GUI)

*   `letruc/widgets.py` (~80 lignes modifiées)
    - `_create_abbreviations_section()` : passage de 2 à 4 colonnes
    - Suppression du Canvas scrollable
    - Calcul automatique des positions (num_cols = 4, rows_per_col)
    - Import : `from misenpageur.misenpageur.abbreviations import get_default_abbreviations`
    - Chargement TOUJOURS depuis abbreviations.yml (ignore app.abbreviations_data)
    - Logs de debug : `[DEBUG] Chargé X abréviations dans l'interface GUI`
    - Gestion d'erreur gracieuse avec messages console

*   `letruc/_helpers.py` (~50 lignes modifiées)
    - Section abréviations : décodage HTML + chargement nobr + application
    - Import : `html.unescape()` pour décoder les entités HTML
    - Chargement de `nobr.txt` depuis `misenpageur/assets/textes/`
    - Passage du paramètre `nobr_expressions` à `apply_abbreviations_to_paragraphs()`
    - Logs de debug avant/après décodage
    - Log : `[INFO] Chargé X expression(s) nobr à protéger`
    - Suppression : import et utilisation de `cfg.abbreviations` (déplacé vers YAML)
    - Suppression : restauration de l'état des checkboxes depuis config.yml

*   `letruc/app.py` (inchangé)
    - Conservation : `self.abbreviation_vars = {}` (variables des checkboxes)
    - Collecte de l'état des checkboxes inchangée

*   `letruc/callbacks.py` (inchangé)
    - Fonctions `on_abbrev_select_all()` et `on_abbrev_deselect_all()` inchangées

### Documentation

*   `misenpageur/ABBREVIATIONS.md` **[NOUVEAU]** (~15 Ko)
    - Documentation complète du système d'abréviations
    - Architecture, utilisation, fonctionnement technique
    - Liste complète des 22 abréviations avec tableaux
    - Guide d'ajout de nouvelles abréviations
    - Section débogage avec problèmes courants
    - Exemples d'utilisation concrets
    - API Python pour usage programmatique
    - Checklist de déploiement

---

## 🔄 Compatibilité

*   Compatible avec toutes les versions antérieures (v1.4.1 et inférieures)
*   **Aucune modification de `config.yml` requise** (nouveaux champs optionnels)
    - Si `abbreviations.yml` n'existe pas → aucune abréviation appliquée
    - Si `nobr.txt` n'existe pas → aucune protection nobr
*   **Rétrocompatibilité v1.4.1 → v1.4.2** :
    - Les anciens `config.yml` avec section `abbreviations` sont ignorés
    - L'état des checkboxes est TOUJOURS chargé depuis `abbreviations.yml`
    - Les fichiers Excel/CSV sans accents continuent de fonctionner
*   **Migration recommandée** :
    - Créer `abbreviations.yml` avec les 22 abréviations
    - (Optionnel) Créer `nobr.txt` avec les noms propres locaux
    - Tester avec un fichier Excel contenant des accents
    - Vérifier les logs : `[INFO] Total: X remplacement(s)`
*   Fonctionne avec Python 3.10+ sur Windows/Linux/macOS
*   **Nouvelles dépendances** :
    - `pyyaml` : Déjà requis pour config.yml
    - `unicodedata` : Module standard Python (aucune installation)

---

# Bidul v1.4.1 - SVG Natif, Icônes Dynamiques et Filtrage des Événements

Cette version majeure introduit le support natif des fichiers SVG pour les sections Logos et Ours, des icônes automatiques pour les événements gratuits ou au chapeau, et un filtrage des événements inactifs directement depuis le fichier source.

## ✨ Nouveautés

*   **Logos depuis fichier SVG** : La section logos peut maintenant être générée directement depuis un fichier SVG pré-composé (ex: Inkscape) :
    *   Nouveau mode de layout : `svg` (en plus de `colonnes` et `optimisé`)
    *   Conservation des proportions et hyperlinks définis dans le SVG
    *   Mise à l'échelle automatique pour remplir la zone disponible
    *   Idéal pour un contrôle précis du placement des logos
    *   **Poster** : Les images sont automatiquement extraites du SVG et redisposées horizontalement

*   **Ours depuis fichier SVG** : La section "Ours" (mentions légales) supporte également le rendu SVG :
    *   Nouveau mode de layout : `svg` (en plus de `png`)
    *   Permet d'éditer facilement le contenu dans Inkscape
    *   Conservation des liens hypertextes (Facebook, Instagram, site web)
    *   Meilleure qualité d'impression (vectoriel)

*   **Icône "Au Chapeau"** : Remplacement automatique de `, au chapeau` par une icône de chapeau 🎩 :
    *   Checkbox dans l'interface : "Remplacer , au chapeau par une icône"
    *   Taille de l'icône adaptée dynamiquement à la police
    *   Gain d'espace dans l'agenda (le texte est plus court)
    *   Gère les variantes : `, au chapeau`, `au chapeau`, `AU CHAPEAU`, espaces insécables

*   **Icône "Gratuit"** : Remplacement automatique de `, 0€` par une icône FREE :
    *   Checkbox dans l'interface : "Remplacer , 0€ par une icône"
    *   Évite les faux positifs (`10€`, `20€` ne sont pas remplacés)
    *   Gère les variantes : `, 0€`, `0€`, `0 €`, `0&euro;`

*   **Filtrage des événements inactifs** : Nouvelle colonne optionnelle `INACTIF` dans le fichier source :
    *   Si la valeur est `o` ou `O`, la ligne est ignorée
    *   Permet de désactiver temporairement des événements sans les supprimer
    *   Log informatif : `[INACTIF] 3 ligne(s) ignorée(s)`
    *   Aucun impact si la colonne est absente

*   **Import de configuration amélioré** :
    *   Support des fichiers YAML et JSON
    *   Bouton renommé : "📁 Importer config"
    *   Filtre de fichiers : YAML, JSON, ou tous
    *   Import depuis les artefacts de debug (config.json) facilité

## ⚙️ Pour les Développeuses et Développeurs

*   **Nouveau système d'icônes avec placeholder** : Architecture en deux phases pour les remplacements d'icônes :
    ```python
    # Phase 1 : AVANT le calcul de taille de police
    paras = apply_icon_replacements(paras, chapeau_enabled, free_enabled)
    # Remplace ", au chapeau" -> "{{CHAPEAU}}" et ", 0€" -> "{{FREE}}"
    
    # Phase 2 : LORS du rendu (dans _mk_text_for_kind)
    txt = _replace_all_placeholders(txt, font_size)
    # Remplace "{{CHAPEAU}}" -> <img .../> avec la bonne taille
    ```
    Cette approche permet de calculer la taille de police optimale en tenant compte du gain d'espace.

*   **Fonctions ajoutées dans `textflow.py`** :
    *   `apply_chapeau_to_paragraphs()` : Remplace `, au chapeau` par placeholder
    *   `apply_free_to_paragraphs()` : Remplace `, 0€` par placeholder
    *   `apply_icon_replacements()` : Applique les remplacements activés
    *   `_get_icon_img_tag()` : Génère la balise `<img>` dimensionnée
    *   `_replace_all_placeholders()` : Remplace tous les placeholders par les images

*   **Pattern regex robuste pour `0€`** :
    ```python
    # Évite les faux positifs avec lookbehind négatif
    pattern = r',?(?:\s|&nbsp;|\u00A0)*(?<![0-9])0(?:\s|&nbsp;|\u00A0)*(?:€|&euro;)'
    ```
    Ne matche que `0€` isolé, pas `10€`, `20€`, etc.

*   **Nouveaux champs dans `Config`** :
    ```python
    input_file: Optional[str] = None          # Fichier d'entrée (Excel/CSV)
    output_svg_dir: Optional[str] = None      # Dossier de sortie SVG
    generate_svg: bool = True                 # Générer des SVG éditables
    stories_output_dir: Optional[str] = None  # Dossier de sortie stories
    chapeau_icon_enabled: bool = False        # Activer icône chapeau
    free_icon_enabled: bool = False           # Activer icône gratuit
    ```

*   **Support JSON dans `Config`** :
    ```python
    @classmethod
    def from_file(cls, path: str) -> "Config":
        """Charge depuis YAML ou JSON (détection automatique)."""
        ext = os.path.splitext(path)[1].lower()
        if ext == '.json':
            return cls.from_json(path)
        else:
            return cls.from_yaml(path)
    ```

*   **Filtrage des lignes inactives dans `csv_utils.py`** :
    ```python
    def _filter_inactive_rows(df: pd.DataFrame) -> pd.DataFrame:
        """Filtre les lignes où INACTIF = 'o' (case insensitive)."""
        # Cherche la colonne INACTIF (optionnelle)
        # Filtre les lignes où la valeur est 'o' ou 'O'
        # Log le nombre de lignes ignorées
    ```

*   **Rendu SVG avec préservation des hyperlinks** : Le module `svglib` est utilisé pour charger les SVG, et les liens sont extraits puis recréés comme annotations PDF.

---

## 📦 Fichiers Modifiés

### Module `misenpageur`

*   `misenpageur/misenpageur/textflow.py` (~100 lignes ajoutées)
    - Système de placeholders et remplacement d'icônes
    - Fonctions `apply_*_to_paragraphs()` et `_replace_*_placeholder()`
    - Constantes `CHAPEAU_ICON_PATH`, `FREE_ICON_PATH`

*   `misenpageur/misenpageur/draw_logic.py` (~10 lignes modifiées)
    - Appel à `apply_icon_replacements()` avant le calcul de taille
    - Lecture des options `chapeau_icon_enabled` et `free_icon_enabled`
    - Passage de `cfg` à `draw_poster_logos()` pour le support SVG

*   `misenpageur/misenpageur/drawing.py` (~15 lignes modifiées)
    - `draw_poster_logos()` : nouveau paramètre `cfg` optionnel
    - Support du mode SVG pour les logos du poster (page 3)
    - Nouvelle fonction `_extract_images_from_svg()` : extrait les images embarquées (base64 ou externes) avec leurs liens

*   `misenpageur/misenpageur/config.py` (~30 lignes ajoutées)
    - Nouveaux champs : `input_file`, `output_svg_dir`, `generate_svg`, etc.
    - Méthodes `from_json()` et `from_file()`

### Module `letruc` (GUI)

*   `letruc/app.py` (~15 lignes modifiées)
    - Variables `chapeau_icon_var` et `free_icon_var`
    - Dialogue d'import config avec support JSON

*   `letruc/widgets.py` (~10 lignes ajoutées)
    - Checkboxes pour les options icônes chapeau et gratuit

*   `letruc/_helpers.py` (~50 lignes modifiées)
    - `load_and_apply_config()` : support JSON et nouveaux champs
    - `run_pipeline()` : passage des paramètres icônes

### Module `biduleur`

*   `biduleur/csv_utils.py` (~30 lignes ajoutées)
    - Fonction `_filter_inactive_rows()`
    - Constante `INACTIF_COLUMN`

### Nouveaux fichiers

*   `misenpageur/assets/icons/chapeau.png` (icône chapeau, fond transparent)
*   `misenpageur/assets/icons/free.png` (icône FREE, fond transparent)

## 🔄 Compatibilité

*   Compatible avec toutes les versions antérieures
*   Aucune modification de `config.yml` requise (nouveaux champs optionnels)
*   Les fichiers Excel/CSV sans colonne INACTIF continuent de fonctionner
*   Les fichiers SVG sont optionnels (modes PNG/colonnes toujours disponibles)
*   Fonctionne avec Python 3.10+ sur Windows/Linux/macOS

---

# Bidul v1.3.10 - Robustesse Excel et Cucaracha Box Améliorée

Cette version corrige un bug critique lors de l'import de fichiers Excel et améliore la flexibilité de la Cucaracha Box avec le support d'images en arrière-plan.

## ✨ Nouveautés

*   **Compatibilité Excel Renforcée** : Le Bidul gère désormais correctement les fichiers Excel dont les colonnes contiennent des types natifs (dates, heures, nombres) au lieu de texte brut. Plus besoin de reformater manuellement vos fichiers Excel avant import :
    *   **Colonne HORAIRE** : Les heures au format Excel (`datetime.time`) sont automatiquement converties en texte (`14h30`)
    *   **Colonnes DATE** : Les dates Excel (`datetime.datetime`) sont correctement interprétées
    *   **Colonnes numériques** : Les entiers et décimaux sont convertis en texte de manière transparente
    
    **Avant** : `AttributeError: 'datetime.time' object has no attribute 'lower'`
    **Maintenant** : Import fluide, aucune erreur

*   **Cucaracha Box : Image en Arrière-Plan** : Lorsque le type de contenu est `image`, celle-ci est maintenant affichée en arrière-plan de toute la box, permettant au titre de rester visible par-dessus :
    *   L'image est redimensionnée pour couvrir l'intégralité de la box
    *   Le ratio d'aspect est préservé avec centrage automatique
    *   Le titre (souligné) s'affiche par-dessus l'image
    *   Idéal pour des visuels promotionnels avec légende

## ⚙️ Pour les Développeuses et Développeurs

*   **Nouvelle Fonction Helper `_to_str()`** : Ajout dans `format_utils.py` d'une fonction de conversion robuste qui centralise la gestion des types Excel :
    ```python
    def _to_str(value: Any) -> str:
        """Convertit une valeur en string de manière robuste."""
        if value is None:
            return ""
        if isinstance(value, datetime.time):
            return value.strftime("%Hh%M")
        if isinstance(value, datetime.datetime):
            return value.strftime("%d/%m/%Y %Hh%M")
        if isinstance(value, (int, float)):
            return str(value)
        return str(value)
    ```
    Cette fonction est appelée en entrée de toutes les fonctions de formatage (`fmt_heure()`, `format_string()`, `format_style()`, etc.).

*   **Fonctions Modifiées dans `format_utils.py`** :
    *   `fmt_heure()` : Gestion native de `datetime.time`
    *   `format_string()` : Conversion automatique en entrée, suppression du crash sur types non-string
    *   `format_artists_styles()`, `format_sv()`, `format_concert()` : Appels à `_to_str()` sur les paramètres
    *   `format_style()`, `format_lieu()`, `format_evenement()` : Robustesse accrue
    *   Suppression des type hints restrictifs (`: str` → accepte `Any`)

*   **Refactoring de `_draw_cucaracha_box()`** : Réorganisation de l'ordre de dessin dans `drawing.py` :
    ```python
    # Nouvel ordre :
    # 1. Image en background (si content_type == "image")
    # 2. Titre par-dessus (toujours visible)
    # 3. Texte (si content_type == "text")
    ```
    L'image utilise maintenant `preserveAspectRatio=True, anchor='c'` pour un rendu centré couvrant toute la box.

*   **Stratégie de Robustesse** : Plutôt que de normaliser les types dans `csv_utils.py` (à la lecture), la conversion est effectuée dans `format_utils.py` (au formatage). Avantages :
    *   Moins de risque de régression sur le parsing existant
    *   Protection contre tout type inattendu, quelle que soit la source
    *   Code de conversion centralisé et testable

*   **Logs Inchangés** : Aucun nouveau log ajouté. Les erreurs de formatage qui auraient crashé sont maintenant silencieusement converties en chaînes vides ou valeurs par défaut.

---

## 📦 Fichiers Modifiés

*   `biduleur/format_utils.py` (~30 lignes modifiées)
    - Ajout de `_to_str()` et import `datetime`
    - Modification de toutes les fonctions de formatage pour utiliser `_to_str()`
*   `misenpageur/misenpageur/drawing.py` (~25 lignes modifiées)
    - Refactoring de `_draw_cucaracha_box()` : image en background, titre par-dessus

## 🔄 Compatibilité

*   Compatible avec toutes les versions antérieures
*   Aucune modification de `config.yml` requise
*   Les fichiers CSV continuent de fonctionner comme avant
*   Les fichiers Excel avec colonnes texte continuent de fonctionner comme avant
*   Fonctionne avec Python 3.10+ sur Windows/Linux/macOS

---

# Bidul v1.3.9 - Support des Logos Vectoriels (SVG)

Cette version apporte le support complet des logos au format SVG (vectoriel), permettant un rendu parfait à toutes les résolutions, particulièrement important pour l'impression professionnelle et l'affichage web haute définition.

## ✨ Nouveautés

*   **Logos Vectoriels SVG** : Le Bidul accepte maintenant les logos au format `.svg` en plus des formats bitmap (`.png`, `.jpg`, `.jpeg`). Les logos vectoriels offrent :
    *   **Qualité parfaite** à toutes les tailles et résolutions
    *   **Fichiers PDF plus légers** comparé aux bitmaps haute résolution
    *   **Netteté optimale** pour l'impression professionnelle
    *   **Rendu parfait** dans les exports SVG du document

*   **Mix PNG + SVG dans le Même Dossier** : Vous pouvez désormais mélanger logos bitmap et vectoriels dans le dossier `logos/` :
    ```
    logos/
    ├── RadioAlpa.svg          ← Vectoriel
    ├── BlueZinc.svg           ← Vectoriel
    ├── LeMansLaVille.png      ← Bitmap
    └── BrasserieSeptante.svg  ← Vectoriel
    ```
    Le système détecte automatiquement le format et applique le rendu approprié.

*   **Support Complet sur Toutes les Pages** : Les logos SVG sont correctement affichés sur :
    *   **Page 1** : Section ours (colonne de gauche) - layouts "colonnes" et "optimisé"
    *   **Page 4** : Poster avec logos partenaires en bas
    *   Les **hyperlinks** des logos SVG fonctionnent comme pour les PNG

*   **Fallback Automatique** : Si la bibliothèque `svglib` n'est pas installée, les logos SVG sont automatiquement ignorés avec un message de log explicite, sans bloquer la génération du document.

## ⚙️ Pour les Développeuses et Développeurs

*   **Nouvelle Dépendance : `svglib>=1.0.0`** : Bibliothèque pour la conversion SVG → ReportLab Drawing. Installation : `pip install svglib`

*   **Architecture de Support SVG** : Quatre fonctions modifiées dans `drawing.py` pour gérer les logos SVG :

    1. **`list_images()` (ligne 96)** : Détection des fichiers `.svg`
        ```python
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
        ```

    2. **`_load_and_measure_logo()` (nouvelles lignes 275-320)** : Fonction helper universelle
        ```python
        def _load_and_measure_logo(logo_path: str):
            """Charge un logo (PNG, JPG ou SVG) et retourne ses dimensions."""
            # Retourne: (image_object, width, height, is_svg)
        ```
        - Pour SVG : Utilise `svg2rlg()` pour convertir en ReportLab Drawing
        - Pour bitmap : Utilise `ImageReader()` (comportement existant)
        - Gère les erreurs avec logs appropriés

    3. **`_draw_logo_at_position()` (nouvelles lignes 322-352)** : Rendu universel
        ```python
        def _draw_logo_at_position(c, logo_obj, x, y, w, h, is_svg):
            """Dessine un logo (SVG ou bitmap) à la position spécifiée."""
        ```
        - SVG : Applique transformation (scale + translate) puis `renderPDF.draw()`
        - Bitmap : `c.drawImage()` avec masque alpha (comportement existant)

    4. **Intégration dans les fonctions de layout** :
        - `_draw_logos_two_columns()` : Support SVG complet
        - `_draw_logos_optimized()` : Support SVG avec packing intelligent
        - `draw_poster_logos()` : Support SVG pour page 4

*   **Gestion Cohérente des Dimensions** : Les SVG conservent leur aspect ratio natif de la même manière que les bitmaps. Le calcul du fit (largeur/hauteur disponible) est identique pour les deux formats.

*   **Logs de Diagnostic** : Messages explicites pour suivre le chargement des logos :
    ```
    [DEBUG] Logo SVG chargé: BlueZinc.svg (556.0x280.0pt)
    [DEBUG] Logo SVG chargé: BrasserieSeptante-Deux.svg (1572.0x340.0pt)
    ```
    Ou en cas d'absence de svglib :
    ```
    [WARNING] SVG ignoré (svglib non disponible): RadioAlpa.svg
    ```

*   **Compatibilité Ascendante Totale** : Les configurations existantes avec uniquement des PNG/JPG continuent de fonctionner exactement comme avant. Aucune migration nécessaire.

*   **Correctifs Inclus** : Résolution des warnings "cannot identify image file" qui apparaissaient lors de l'utilisation d'`ImageReader()` avec des fichiers SVG. La fonction `draw_poster_logos()` a été corrigée pour utiliser `_load_and_measure_logo()` au lieu d'`ImageReader()` directement.

*   **Tests de Validation** : Testé avec succès sur 13 logos SVG réels issus de partenaires Radio Alpa (BlueZinc, BrasserieSeptante-Deux, LeMansLaVille, etc.). Génération PDF + exports SVG validés sans warnings.

---

## 📦 Fichiers Modifiés

*   `misenpageur/misenpageur/drawing.py` (+150 lignes)
    - Ajout `_load_and_measure_logo()` et `_draw_logo_at_position()`
    - Modification `list_images()`, `_draw_logos_two_columns()`, `_draw_logos_optimized()`, `draw_poster_logos()`
*   `misenpageur/requirements.txt` (ajout `svglib>=1.0.0`)

## 🔄 Compatibilité

*   Compatible avec toutes les versions antérieures
*   Aucune modification de `config.yml` requise
*   Fonctionne avec Python 3.10+ sur Windows/Linux/macOS
*   Dépendance optionnelle : sans `svglib`, les logos SVG sont simplement ignorés

---

# Bidul v1.3.8 - Amélioration de l'Expérience Utilisateur

Cette version apporte trois améliorations significatives pour simplifier l'utilisation du Bidul : nommage cohérent des fichiers SVG, validation robuste des fichiers d'entrée, et gestion avancée de la configuration via l'interface graphique.

## ✨ Nouveautés

*   **Nommage Cohérent des Fichiers SVG** : Les fichiers SVG exportés utilisent désormais automatiquement le même nom de base que le fichier PDF source, facilitant leur identification et leur organisation :
    *   **Avant** : `page_1.svg`, `page_2.svg`, `page_3.svg`, `page_4.svg`
    *   **Après** : `bidul_novembre_1.svg`, `bidul_novembre_2.svg`, `bidul_novembre_3.svg`, `bidul_novembre_4.svg`
    
    Cette amélioration simplifie la gestion des fichiers, particulièrement lors de la génération de plusieurs éditions du Bidul. Les fichiers SVG sont immédiatement identifiables et peuvent être organisés par mois sans confusion.

*   **Validation Améliorée des Fichiers d'Entrée** : Le système détecte désormais les problèmes de fichiers d'entrée **avant** la génération et affiche des messages d'erreur clairs et exploitables :
    *   **Colonnes Manquantes** : Liste précise des colonnes obligatoires absentes du fichier Excel/CSV
        ```
        Colonnes manquantes dans le fichier :
        
        • GENRE
        • VILLE
        • LIEU
        • PRIX
        • GENRE 1
        • NOM SPECTACLE 1 ( SV )
        ...
        ```
    *   **Fichier Excel Corrompu** : Message explicite avec solutions proposées
        ```
        Le fichier Excel est corrompu ou illisible.
        
        Solutions :
        • Ouvrir le fichier dans Excel et l'enregistrer à nouveau
        • Exporter en CSV depuis Excel
        • Vérifier que le fichier n'est pas vide
        ```
    *   **Problèmes de Permissions** : Indication claire si le fichier est ouvert ailleurs ou inaccessible
    
    **Terminé les PDF vides sans explication** : L'utilisateur sait immédiatement ce qui ne va pas et comment le corriger.

*   **Import et Reset de Configuration (Mode Debug)** : Deux nouveaux boutons apparaissent en bas de l'interface quand le mode débogage est activé :
    *   **📁 Importer config.yml** : Permet de charger un fichier de configuration personnalisé et met automatiquement à jour tous les champs de l'interface graphique (chemins des images, polices, marges, couleurs, etc.). Idéal pour :
        *   Tester différentes configurations sans éditer manuellement chaque paramètre
        *   Partager des configurations entre machines
        *   Revenir à une configuration sauvegardée précédemment
    *   **🔄 Reset config** : Restaure instantanément tous les paramètres aux valeurs par défaut du projet
    
    **Comportement intelligent** :
    *   Les paramètres non présents dans le fichier importé conservent leur valeur actuelle (pas d'écrasement complet)
    *   Les chemins relatifs sont automatiquement convertis en chemins absolus
    *   Les boutons n'apparaissent qu'en mode debug pour éviter les manipulations accidentelles

## ⚙️ Pour les Développeuses et Développeurs

*   **Nommage SVG - Modification de `svgbuild.py`** :
    ```python
    # Ligne 273 - Utilisation du nom de base du PDF comme préfixe
    output_prefix = Path(cfg.output_pdf).stem if cfg.output_pdf else "page"
    
    # Résultat : au lieu de page_1.svg, on obtient bidul_novembre_1.svg
    svg_path = output_dir / f"{output_prefix}_{page_num + 1}.svg"
    ```
    Le changement est minimal (une ligne) mais l'impact sur l'expérience utilisateur est significatif.

*   **Validation des Fichiers - Architecture** :
    *   **`biduleur/csv_utils.py`** : Liste exhaustive des colonnes obligatoires définie en constante
        ```python
        REQUIRED_COLUMNS = [
            DATE, GENRE_EVT, HORAIRE, FESTIVAL, STYLE_FESTIVAL, VILLE, LIEU, PRIX,
            GENRE1, SPECTACLE1, ARTISTE1, STYLE1,
            GENRE2, SPECTACLE2, ARTISTE2, STYLE2,
            GENRE3, SPECTACLE3, ARTISTE3, STYLE3,
            GENRE4, SPECTACLE4, ARTISTE4, STYLE4
        ]
        ```
    *   **Validation en deux temps** :
        1. **Vérification de lecture** : Détection des fichiers corrompus ou inaccessibles avec messages contextuels
        2. **Vérification de colonnes** : Liste des colonnes manquantes avec formatage utilisateur-friendly
    *   **Propagation intelligente des erreurs** :
        ```python
        # csv_utils.py - Les ValueError sont propagées, pas les autres exceptions
        except ValueError:
            raise  # Erreurs de validation remontent au GUI
        except Exception as e:
            log.error(f"Error sorting the file: {e}")
            return None
        ```
    *   **`leTruc/_helpers.py`** : Capture des `ValueError` dans `run_pipeline()` et affichage via la queue
        ```python
        try:
            html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(input_file)
        except ValueError as e:
            status_queue.put(('final', False, str(e)))
            return
        ```

*   **Import/Reset Config - Implémentation Complète** :
    *   **`leTruc/app.py`** : Ajout du frame `config_buttons_frame` avec les deux boutons
        *   Frame initialement créé mais masqué (`.pack_forget()`)
        *   Méthodes `_on_import_config()` et `_on_reset_config()` qui appellent `load_and_apply_config()`
    *   **`leTruc/callbacks.py`** : Fonction `on_toggle_config_buttons()` liée à `debug_mode_var`
        ```python
        def on_toggle_config_buttons(app):
            """Affiche/cache les boutons config selon mode debug"""
            if app.debug_mode_var.get():
                app.config_buttons_frame.pack(pady=(5, 0))
            else:
                app.config_buttons_frame.pack_forget()
        ```
    *   **`leTruc/_helpers.py`** : Nouvelle fonction `load_and_apply_config()` (~140 lignes)
        *   Charge le config via `Config.from_yaml()`
        *   Met à jour conditionnellement chaque variable du GUI (if present)
        *   Gère la conversion des chemins relatifs → absolus
        *   Couvre tous les paramètres : images, polices, marges, couleurs, poster, cucaracha, stories

*   **Cas Particuliers Gérés** :
    *   **Validation** : Les messages d'erreur utilisent le caractère `•` pour les listes plutôt que des puces complexes
    *   **Import Config** : Les valeurs `None` ou vides dans le config ne modifient pas les variables du GUI (préservation intelligente)
    *   **Chemins Absolus** : La fonction `make_abs()` dans `load_and_apply_config()` utilise `get_resource_path()` pour garantir la compatibilité PyInstaller

*   **Tests Recommandés** :
    1. **Validation** : Tester avec un fichier Excel manquant les colonnes VILLE, LIEU, PRIX → vérifier que le popup liste ces 3 colonnes
    2. **SVG** : Générer un PDF `test_decembre.pdf` → vérifier que les SVG sont `test_decembre_1.svg`, etc.
    3. **Import/Reset** : 
        *   Activer le debug → boutons apparaissent
        *   Importer un config avec `poster.title = "TEST"` → champ Titre du poster doit se mettre à jour
        *   Reset → tous les champs reviennent aux valeurs par défaut

---

## 📦 Fichiers Modifiés

*   `misenpageur/misenpageur/svgbuild.py` (ligne 273)
*   `biduleur/csv_utils.py` (ajout REQUIRED_COLUMNS + gestion erreurs)
*   `leTruc/app.py` (ajout config_buttons_frame + méthodes import/reset)
*   `leTruc/callbacks.py` (ajout on_toggle_config_buttons)
*   `leTruc/_helpers.py` (ajout load_and_apply_config + try/except parse_bidul)

## 🔄 Compatibilité

*   Compatible avec toutes les versions antérieures
*   Aucune modification de config.yml requise
*   Pas de nouvelle dépendance
*   Fonctionne avec Python 3.10+ sur Windows/Linux/macOS
=======
# Bidul v1.3.8 - QR Codes Stylisés et Modernes

Cette version modernise l'apparence des QR codes présents dans le document (page 1 et page 4) avec des styles visuels personnalisables, permettant un aspect plus professionnel et cohérent avec l'identité graphique de Radio Alpa.

## ✨ Nouveautés

*   **QR Codes Stylisés et Personnalisables** : Ajout de différents fichiers de logos dans le build pour différentes configurations:
    *   **`logos` & `logos.v0`** : Ceux qui ont servi à faire le Biudl #306 (next gen v1.0)
    *   **`logos.vectorized`** : v0 +  vectorisation https://vectorizer.ai/
    *   **`logos.impression`** : v0 +  upsert logos impression Gaelle
*   **QR Codes Stylisés et Personnalisables** : Les QR codes du document bénéficient maintenant de styles visuels modernes configurables. Fini les QR codes noirs et blancs basiques ! Vous pouvez désormais choisir parmi plusieurs styles :
    *   **`rounded`** (recommandé) : Coins arrondis pour un aspect moderne et élégant.
    *   **`circles`** : Points circulaires pour un rendu artistique et original.
    *   **`gapped`** : Carrés espacés pour un look aéré et contemporain.
    *   **`standard`** : QR code classique (comportement par défaut).
    
    Ces styles s'appliquent automatiquement aux **deux QR codes** du document :
    - Le QR code de la section "ours" (page 1, en bas à gauche).
    - Le QR code du poster (page 4, section S7).

*   **Couleurs Personnalisables** : Les QR codes peuvent maintenant être générés dans la couleur de votre choix (au format hexadécimal). Par défaut en noir (`#000000`), vous pouvez les personnaliser aux couleurs de votre charte graphique (par exemple bleu `#3498DB`, rouge `#E74C3C`, etc.). La couleur s'applique de manière cohérente sur les deux pages.

*   **Configuration Centralisée** : Un seul endroit dans `config.yml` pour configurer l'apparence des deux QR codes, garantissant une cohérence visuelle sur l'ensemble du document :
```yaml
    section_1:
      qr_code_style: "rounded"    # Style du QR code
      qr_code_color: "#000000"    # Couleur en hexadécimal
```

*   **Qualité d'Impression Optimisée** : Les QR codes stylisés utilisent une correction d'erreur élevée (`ERROR_CORRECT_H`), permettant une meilleure résistance aux imperfections d'impression tout en conservant une excellente scannabilité.

*   **Fallback Automatique et Fiable** : Si la bibliothèque de styles avancés n'est pas disponible, le système génère automatiquement un QR code standard sans erreur bloquante. Des messages de log clairs indiquent quel style est utilisé, facilitant le diagnostic.

## ⚙️ Pour les Développeuses et Développeurs

*   **Nouvelle Dépendance : `qrcode[pil]`** : La bibliothèque `qrcode` avec support PIL (Pillow) est maintenant requise pour profiter des styles avancés. Cette version inclut :
    *   Les modules de dessin stylisés (`StyledPilImage`, `RoundedModuleDrawer`, `CircleModuleDrawer`, `GappedSquareModuleDrawer`).
    *   Les masques de couleur pour la personnalisation (`SolidFillColorMask`).
    *   Installation : `pip install qrcode[pil]>=7.0.0`

*   **Architecture de Génération Unifiée** : La logique de génération des QR codes stylisés a été implémentée de manière cohérente dans deux fichiers :
    *   **`drawing.py`** (lignes ~234-280) : QR code de la section "ours" (page 1).
    *   **`draw_logic.py`** (lignes ~707-770) : QR code du poster (page 4, section S7).
    
    Les deux utilisent la même fonction helper `hex_to_rgb()` pour convertir les couleurs et la même logique de fallback.

*   **Paramètres de Configuration** : Deux nouveaux paramètres optionnels dans `config.yml` sous `section_1` :
```yaml
    qr_code_style: "rounded"  # Options: standard, rounded, circles, gapped
    qr_code_color: "#000000"  # Code couleur hexadécimal (avec ou sans #)
```
    
    Ces paramètres sont optionnels. Par défaut, le style `standard` et la couleur noire sont utilisés si non spécifiés.

*   **Gestion Intelligente des Erreurs** : Le code implémente un try/except à trois niveaux :
    1. **Tentative de génération stylisée** : Avec StyledPilImage et drawers personnalisés.
    2. **Fallback vers style standard avec couleur** : Si les modules stylisés ne sont pas disponibles.
    3. **Fallback ultime vers noir/blanc** : En cas d'erreur de conversion de couleur.
    
    Chaque niveau est accompagné de logs appropriés (`log.info`, `log.debug`, `log.warning`).

*   **Correction d'Erreur Élevée** : Les QR codes sont maintenant générés avec `error_correction=qrcode.constants.ERROR_CORRECT_H` (correction maximale ~30%) au lieu de la correction par défaut. Cela permet :
    - Une meilleure résistance aux dégradations d'impression.
    - La possibilité future d'ajouter un logo au centre du QR code.
    - Une scannabilité améliorée sur supports usés ou mal imprimés.

*   **Mise à Jour du Requirements** : Le fichier `misenpageur/requirements.txt` doit inclure :
```
    qrcode[pil]>=7.0.0
```
    Cette dépendance sera automatiquement installée lors du build via GitHub Actions.

*   **Logs de Diagnostic** : Des logs informatifs permettent de suivre la génération des QR codes :
```
    QR code généré avec style 'rounded'
    QR code poster (S7) généré avec style 'rounded'
```
    Ou en cas de fallback :
```
    Styles avancés QR code non disponibles: [erreur]
    Utilisation du style QR code standard. Pour les styles avancés, installez: pip install qrcode[pil]
```

*   **Compatibilité Ascendante** : Les configurations existantes sans les nouveaux paramètres `qr_code_style` et `qr_code_color` continuent de fonctionner normalement, générant des QR codes standard noirs et blancs comme avant. Aucune migration nécessaire.

*   **Documentation Complète** : Plusieurs fichiers de documentation ont été créés :
    - `README_QR_STYLES.md` : Guide d'implémentation complet.
    - `config_qr_code_example.yml` : Exemples de configurations avec commentaires détaillés.
    - `QR_CODE_IMPROVEMENTS.md` : Documentation technique des différentes options.
    - `QR_CODE_POSTER_S7.md` : Explications spécifiques pour le QR code du poster.

---

# Bidul v1.3.7 - Correction de la Mise en Page des Dates

Cette version corrige un défaut de mise en page qui pouvait affecter la lisibilité du programme en permettant à des lignes de dates de se retrouver orphelines en bas de section.

## ✨ Nouveautés

*   **Fin des Dates Orphelines** : Le système de mise en page empêche désormais qu'une ligne de date (ex: "SAMEDI 14") se retrouve seule en bas d'une section (S3, S4, S5, S6, S7, S8) sans aucun événement qui la suit. Cette amélioration garantit une mise en page plus cohérente et professionnelle en s'assurant que :
    *   Chaque date est toujours accompagnée d'au moins un événement dans la même section.
    *   Si une date et son premier événement ne peuvent pas tenir ensemble dans l'espace restant, la date passe automatiquement à la section suivante avec ses événements.
    *   La lisibilité du programme est préservée : les dates restent toujours contextualisées par leurs événements associés.

*   **Correction Complète** : Le fix fonctionne maintenant dans **tous les modes de génération** :
    *   **Mode automatique** : Quand la taille de police est calculée automatiquement pour optimiser l'espace.
    *   **Mode forcé** : Quand la taille de police est définie manuellement dans la configuration.
    
    Le problème qui persistait en mode forcé dans les premières versions du fix a été complètement résolu.

## ⚙️ Pour les Développeuses et Développeurs

*   **Contrainte de Lookahead Généralisée** : Le système utilise maintenant une contrainte "anti-orpheline" à 5 endroits stratégiques dans le code de mise en page (`textflow.py`) :
    1. **`measure_fit_at_fs()`** : Mesure combien de paragraphes peuvent être placés dans une section.
    2. **`draw_section_fixed_fs_with_prelude()`** : Dessine les sections S4 et S6 (avec éléments de prélude).
    3. **`draw_section_fixed_fs_with_tail()`** : Dessine les sections S3 et S5 (avec éléments de tail).
    4. **`plan_pair_with_split()` - A_full** : Distribue le contenu pour la première section d'une paire (S3 ou S5).
    5. **`plan_pair_with_split()` - B_full** : Distribue le contenu pour la seconde section d'une paire (S4 ou S6).

*   **Logique de la Contrainte** : Avant de placer une DATE dans une section, le système vérifie maintenant :
```python
    # Si c'est une DATE et qu'il reste des paragraphes après
    if kind == "DATE" and i < len(paras_text) - 1:
        next_kind = "EVENT" if _is_event(paras_text[i + 1]) else "DATE"
        
        # Si le prochain est un EVENT, vérifier l'espace disponible
        if next_kind == "EVENT":
            # Calculer l'espace nécessaire pour DATE + EVENT
            if not assez_d_espace_pour_les_deux:
                break  # Ne pas placer la DATE
```
    Cette logique s'applique de manière cohérente dans toutes les fonctions de mesure et de dessin.

*   **Cas Particuliers Gérés** :
    *   Les dates consécutives (ex: SAMEDI 14 suivi de DIMANCHE 15) ne sont pas contraintes et peuvent se suivre librement.
    *   Une date en dernière position du contenu (fin naturelle du document) peut être placée sans contrainte.
    *   La variable `first_non_event_seen_in_S5` est correctement gérée pour calculer les espacements dans la section S5.

*   **Architecture de la Solution** : La correction initiale ne couvrait que les fonctions de dessin direct, ce qui expliquait pourquoi le problème persistait en mode forcé. L'ajout de la contrainte dans `plan_pair_with_split()` - qui est responsable de la **distribution** du contenu entre sections paires (S3/S4, S5/S6) - résout le problème à la source, avant même que le dessin ne commence.

*   **Tests Recommandés** :
    *   Vérifier qu'aucune date n'est orpheline dans les sections S3 à S8.
    *   Tester avec des configurations en mode automatique et mode forcé.
    *   Vérifier le comportement avec des séquences de dates consécutives.
    *   S'assurer que les documents avec peu d'événements se génèrent correctement.

*   **Fichier Modifié** : `misenpageur/misenpageur/textflow.py` - 5 modifications réparties sur environ 100 lignes de code.

---

# Bidul v1.3.6 - Amélioration de la Qualité SVG et des Images PDF

Cette version apporte une refonte majeure du système de conversion PDF vers SVG et de la gestion des images dans les PDF, avec une amélioration significative de la qualité visuelle pour l'impression professionnelle.

## ✨ Nouveautés

*   **Images Haute Résolution dans les PDF (300 DPI)** : Toutes les images du PDF sont désormais optimisées pour l'impression professionnelle à 300 DPI minimum. Fini les images pixellisées ! Cette amélioration concerne :
    *   **L'image de couverture** (page 1) - rendu parfaitement net.
    *   **Les logos des partenaires** - affichage professionnel et lisible.
    *   **L'image de fond de l'ours** - qualité optimale préservée.
    *   **L'image du poster** (page 4) - résolution maximale pour un impact visuel optimal.
    
    Le système redimensionne intelligemment les images en utilisant le filtre LANCZOS (le plus qualitatif), que l'image source soit trop petite (upscaling) ou trop grande (downscaling pour optimiser la taille du fichier).

*   **Qualité SVG Améliorée** : Les fichiers SVG générés bénéficient désormais d'une résolution d'image doublée (zoom 2×), offrant des visuels 4× plus nets. Les fichiers restent légers tout en conservant une qualité professionnelle pour l'impression et l'affichage numérique.

*   **Conservation Parfaite du Format A4** : Le système de conversion préserve maintenant exactement les dimensions du PDF original (210×297mm pour A4). Fini les SVG mal dimensionnés qui nécessitaient des ajustements manuels dans Inkscape ou Illustrator.

*   **Conversion Plus Fiable et Sans Dépendances Externes** : Le moteur de conversion n'utilise plus `pdf2svg.exe` (qui nécessitait de nombreuses DLLs externes et posait des problèmes de compatibilité). À la place :
    *   **PyMuPDF** est maintenant utilisé par défaut : conversion plus rapide, plus fiable, et fonctionnelle sur tous les systèmes Windows sans configuration supplémentaire.
    *   **Fallback automatique** : Si PyMuPDF n'est pas disponible, le système bascule intelligemment vers pdf2svg.exe avec des messages d'erreur clairs pour guider l'utilisateur.

*   **Meilleure Gestion des Erreurs** : Les messages d'erreur sont maintenant plus explicites et proposent des solutions concrètes en cas de problème (code d'erreur détecté, diagnostic des DLLs manquantes, suggestions d'installation).

## ⚙️ Pour les Développeuses et Développeurs

*   **Nouvelle Fonction Helper : `_load_high_quality_image()`** : Fonction centralisée pour le chargement et l'optimisation des images à 300 DPI minimum. Elle gère :
    *   La conversion RGB automatique (RGBA → RGB avec fond blanc).
    *   Le calcul des dimensions cibles en pixels pour le DPI souhaité.
    *   Le redimensionnement intelligent avec filtre LANCZOS.
    *   La gestion des cas edge (images trop petites, trop grandes, ratios d'aspect).
    
    Cette fonction est maintenant utilisée par toutes les fonctions de dessin d'images, garantissant une qualité homogène dans tout le document.

*   **Nouvelle Dépendance : PyMuPDF** : La bibliothèque `pymupdf` (aussi connue sous le nom de `fitz`) remplace `pdf2svg.exe` comme moteur de conversion principal. Elle offre :
    *   Une API Python native (pas d'appel subprocess).
    *   Un contrôle fin de la qualité via matrices de transformation.
    *   Une compatibilité multiplateforme (Windows, Linux, macOS).

*   **Architecture Modulaire de Conversion** : Le fichier `svgbuild.py` a été restructuré avec :
    *   `_convert_pdf_to_svg_pymupdf()` : Conversion via PyMuPDF avec contrôle de la résolution.
    *   `_convert_pdf_to_svg_pdf2svg()` : Conversion via pdf2svg.exe (fallback) avec diagnostic amélioré.
    *   `_fix_svg_dimensions()` : Fonction dédiée pour corriger les dimensions du SVG et ajouter les attributs `width`, `height` et `viewBox`.
    *   Sélection automatique de la meilleure méthode disponible.

*   **Optimisations des Fonctions de Dessin** : Les fonctions `draw_s2_cover()`, `draw_poster_logos()`, et `draw_s1()` (dans `drawing.py`) ainsi que les fonctions de dessin du poster (dans `draw_logic.py`) ont toutes été refactorisées pour utiliser `_load_high_quality_image()`.

*   **Paramètre de Qualité Configurable** : 
    *   Pour les images PDF : le DPI minimum est paramétrable via l'argument `min_dpi` de `_load_high_quality_image()` (défaut: 300).
    *   Pour les SVG : le facteur de zoom (actuellement `2.0`) est facilement modifiable dans le code pour ajuster le compromis qualité/taille de fichier selon les besoins.

*   **Mise à Jour du Workflow CI/CD** : Le fichier GitHub Actions (`bidul_release.yml`) intègre maintenant l'installation de PyMuPDF pour garantir le bon fonctionnement de la conversion dans les builds automatisés.

*   **Diagnostic Avancé** : En cas d'échec avec pdf2svg.exe, le système détecte maintenant le code d'erreur spécifique `3228369022` (DLLs manquantes) et affiche des instructions précises pour résoudre le problème.

*   **Logs Détaillés** : Des logs DEBUG et INFO ont été ajoutés pour suivre les opérations de redimensionnement d'images (upscaling/downscaling) et faciliter le débogage.

---

# Bidul v1.3.5 - Affichage de la Version et Améliorations Internes

Cette version de maintenance se concentre sur l'amélioration de l'expérience utilisateur et la robustesse du processus de build, en apportant plus de clarté sur la version de l'application utilisée.

## ✨ Améliorations

*   **Affichage du Numéro de Version dans le Titre** : Le numéro de version de l'application (ex: `v1.3.5`) est désormais **automatiquement affiché** dans la barre de titre de la fenêtre principale.
    *   Cela permet aux utilisateurs d'identifier facilement la version qu'ils utilisent, ce qui est crucial pour le support technique et le suivi des bugs.
    *   En mode développement, le titre affichera `v-dev` pour une distinction claire.

## ⚙️ Pour les Développeuses et Développeurs

*   **Injection de Version au Moment du Build** : Le numéro de version n'est plus codé en dur. Il est maintenant injecté dynamiquement lors du processus de build par le workflow GitHub Actions.
    *   Le workflow extrait la version du tag Git (ex: `bidul-v1.3.5`), la "grave" dans un fichier `leTruc/_version.py`, qui est ensuite embarqué dans l'exécutable par PyInstaller.
    *   Cette approche garantit que la version affichée est toujours synchronisée avec la release officielle, éliminant tout risque d'oubli ou d'erreur manuelle.

---

# Bidul v1.3.4 - Fiabilisation de l'Export SVG et du Build Windows

Cette version de maintenance cruciale se concentre sur la résolution de bugs qui pouvaient survenir lors de l'utilisation de l'export SVG, en particulier dans la version "standalone" de l'application (`bidul.exe`). L'application est désormais plus robuste et plus portable, garantissant un fonctionnement identique sur n'importe quelle machine Windows.

## 🔧 Améliorations et Corrections

*   **Correction d'un Crash Critique de l'Export SVG (Conflit de DLL)** : Un bug majeur qui provoquait un plantage de l'application (`pdf2svg.exe - Entry Point Not Found`) lors de la génération de fichiers SVG a été résolu. Ce problème survenait sur les systèmes où un autre logiciel (comme Tesseract-OCR) avait installé une version incompatible d'une bibliothèque partagée (`libfontconfig-1.dll`).

*   **Fiabilisation du Chemin vers `pdf2svg` dans l'Application Portable** : La version "standalone" (`bidul.exe`) trouve désormais de manière fiable l'outil de conversion `pdf2svg.exe` qu'elle embarque. Cela corrige l'erreur `Échec de la conversion SVG` qui survenait après le packaging de l'application.

*   **Nettoyage de la Configuration du Build** : Des dépendances obsolètes (`svglib`) ont été retirées de la configuration de PyInstaller. Cela résout une erreur `ModuleNotFoundError` qui pouvait survenir lors du build sur GitHub Actions et rend le processus de compilation plus propre.

## ⚙️ Pour les Développeuses et Développeurs

*   **Dépendances "Bundlées"** : La dépendance externe `pdf2svg.exe` est désormais livrée avec toutes ses DLLs requises. Le build PyInstaller embarque ce dossier en entier (`bin/win64`), garantissant que l'exécutable est totalement autonome et ne subit plus de conflits avec les bibliothèques installées sur le système de l'utilisateur.
*   **Utilisation de `get_resource_path`** : La fonction utilitaire `get_resource_path` est maintenant utilisée pour trouver le chemin de `pdf2svg.exe` de manière fiable, que l'application soit lancée depuis les sources ou en tant qu'exécutable packagé (via `sys._MEIPASS`).

---

# Bidul v1.3.3 - Modernisation de l'Interface et Aide Contextuelle

Cette version se concentre sur une refonte majeure de l'ergonomie de l'interface graphique, en introduisant des fonctionnalités modernes pour une expérience utilisateur plus intuitive, plus rapide et mieux guidée.

## ✨ Nouveautés

*   **Glisser-Déposer (Drag and Drop) pour les Fichiers** : L'interface a été modernisée pour permettre la sélection de fichiers par glisser-déposer. Les champs "Fichier d'entrée" et "Image de couverture" ont été transformés en grandes zones de dépôt explicites. Vous pouvez désormais :
    *   **Glisser et déposer** votre fichier `.xls`/`.csv` ou votre image de couverture directement dans la zone dédiée.
    *   Ou continuer à utiliser le bouton **"Sélectionner un fichier..."** comme avant.
    Cette amélioration rend la sélection des fichiers plus rapide et aligne l'application sur les standards des logiciels modernes.

*   **Aide Contextuelle Intégrée (Tooltips)** : Pour rendre l'application plus facile à prendre en main, des infobulles d'aide (`tooltips`) ont été ajoutées sur de nombreux paramètres de l'interface. En laissant simplement le curseur de la souris quelques instants sur un champ ou une option, une petite fenêtre apparaît pour expliquer :
    *   Le rôle du paramètre (ex: "Marge globale").
    *   L'impact de chaque option (ex: la différence entre les modes "Automatique" et "Forcée" pour la taille de police).
    *   Les valeurs attendues.
    Cette fonctionnalité transforme l'interface en une documentation interactive, guidant l'utilisateur pas à pas.

## ⚙️ Pour les Développeuses et Développeurs

*   **Intégration de `tkinterdnd2`** : La fonctionnalité de glisser-déposer a été implémentée grâce à la bibliothèque `tkinterdnd2`, qui est maintenant une nouvelle dépendance du projet.
*   **Création d'une Classe `Tooltip` Modulaire** : Toute la logique des infobulles a été encapsulée dans une classe réutilisable (`leTruc/tooltips.py`). Attacher une aide contextuelle à n'importe quel widget se fait désormais en une seule ligne de code, rendant l'extension de cette fonctionnalité très simple.
*   **Fiabilisation du Build** : Le fichier de configuration de PyInstaller (`bidul.spec`) a été mis à jour pour embarquer correctement la nouvelle dépendance `tkinterdnd2`, garantissant le bon fonctionnement de l'exécutable Windows.

---

# Bidul v1.3.2 - Mode Débogage Avancé et Unifié

Cette version introduit une fonctionnalité majeure destinée aux développeurs et aux utilisateurs avancés : un mode de débogage complet et unifié sur l'ensemble des outils du projet (interface graphique, `misenpageur` CLI, `biduleur` CLI).

## ✨ Nouveautés

*   **Mode Débogage Intégré** : L'activation du mode débogage, que ce soit via la nouvelle case à cocher dans l'interface graphique ou via l'option `--debug` en ligne de commande, génère désormais un dossier de diagnostic complet et unique pour chaque exécution.
*   **Historique des Exécutions** : Chaque dossier de débogage est horodaté (ex: `debug_run_2025-10-26_15-30-00`), permettant de conserver un historique détaillé et de comparer facilement les résultats de différentes exécutions.
*   **Rapports de Diagnostic Complets** : Chaque dossier de débogage contient trois fichiers essentiels pour l'analyse et la reproductibilité :
    1.  **`execution.log`** : Un journal détaillé de toutes les étapes du pipeline (parsing, génération PDF, conversion SVG, etc.), incluant les messages d'information, les avertissements (`WARN`) et les erreurs (`ERROR`) avec leur traceback complet.
    2.  **`config.json`** : Un export complet de la configuration exacte utilisée pour cette exécution spécifique, incluant tous les paramètres par défaut et ceux modifiés par l'utilisateur.
    3.  **`summary.info`** : Un résumé lisible du résultat de l'exécution, identique à celui affiché dans la fenêtre de victoire.

## ⚙️ Pour les Développeuses et Développeurs

*   **Système de Logging Centralisé** : Un nouveau module `misenpageur/logger.py` a été créé pour gérer la configuration du logging de manière centralisée. Il est désormais partagé par l'interface graphique et les deux outils en ligne de commande.
*   **Utilisation du module `logging`** : Tous les `print()` informatifs à travers le projet ont été remplacés par des appels au logger standard de Python (`log.info`, `log.warning`, `log.error`), ce qui permet une gestion fine de la verbosité et une capture structurée des messages.
*   **Amélioration des CLIs** :
    *   Les outils `misenpageur` et `biduleur` disposent maintenant d'une option `--debug` pour activer la génération des dossiers de diagnostic.
    *   L'option `-v` / `--verbose` contrôle désormais uniquement l'affichage des logs dans la console, la séparant de la logique de sauvegarde des fichiers.

---
# Bidul v1.3.1 - Amélioration de la Ligne de Commande et Cohérence des Sorties

Cette version se concentre sur l'amélioration de l'outil en ligne de commande (`misenpageur`) et l'harmonisation du comportement des sorties multi-fichiers, rendant l'utilisation en mode script plus flexible et plus intuitive.

## ✨ Nouveautés et Améliorations

*   **Contrôle des Stories depuis la Ligne de Commande** : L'outil `misenpageur` dispose désormais d'options pour piloter la génération des images pour les Stories Instagram. Il est maintenant possible de surcharger la configuration du fichier `config.yml` :
    *   `--stories` : Force la création des images.
    *   `--no-stories` : Empêche la création des images.

*   **Gestion Simplifiée de la Sortie SVG** : Le comportement de la sortie des fichiers SVG a été rendu cohérent avec celui des Stories pour une meilleure expérience utilisateur :
    *   **Sélection par dossier** : Dans l'interface graphique, vous choisissez désormais un dossier de destination pour les SVG, au lieu d'un nom de base de fichier.
    *   **Nommage automatique** : Les fichiers sont automatiquement nommés `page_1.svg`, `page_2.svg`, etc., à l'intérieur du dossier choisi.
    *   **Chemins par défaut intelligents** : L'interface propose maintenant par défaut un dossier `svgs/` situé à côté du fichier d'entrée, simplifiant la configuration initiale.

## ⚙️ Pour les Développeuses et Développeurs

*   **Amélioration du CLI** : L'argument `--stories` a été implémenté en utilisant `action=argparse.BooleanOptionalAction`, une bonne pratique qui crée automatiquement le drapeau `--no-stories` correspondant.
*   **Harmonisation de la Logique de Sortie** : La logique de `svgbuild.py` a été refactorisée pour accepter un dossier de sortie (`out_dir`) au lieu d'un chemin de fichier complet, s'alignant sur le fonctionnement de `image_builder.py`.

---

# Bidul v1.3.0 - Export pour les Réseaux Sociaux et Personnalisation Avancée

Cette version majeure marque une nouvelle étape pour Bidul, en ouvrant la porte à la création de contenu pour les réseaux sociaux et en offrant un contrôle sans précédent sur la mise en page et le rendu final.

## ✨ Nouveautés

*   **Génération d'Images pour les Stories Instagram** : Bidul peut désormais générer des fichiers `.png` parfaitement optimisés pour les formats verticaux (1080x1920). Une nouvelle section dans l'interface graphique offre un contrôle créatif total sur le rendu :
    *   **Personnalisation de la police** : Choisissez la police, la taille et la couleur du texte de l'agenda.
    *   **Fond sur mesure** : Optez pour une couleur de fond unie ou sélectionnez une image de fond personnalisée.
    *   **Contrôle de la transparence** : Lors de l'utilisation d'une image de fond, un voile blanc semi-transparent peut être appliqué, avec un slider pour en régler l'opacité.
    *   **Ajustement fin de la mise en page** : Réglez les marges horizontales et l'interligne du texte pour un résultat parfait (dans fichier de configuration).

*   **Boîte "Cucaracha" Multiligne et Personnalisable** : La boîte de contenu personnalisé a été entièrement revue pour plus de flexibilité :
    *   **Support du texte multiligne** : Le champ de saisie permet désormais d'entrer du texte sur plusieurs lignes avec des sauts de ligne.
    *   **Taille de police configurable** : Vous pouvez maintenant choisir la taille de la police directement depuis l'interface.

## 🔧 Améliorations et Corrections

*   **Contrôle Manuel de la Taille de Police** : Une nouvelle option "Forcée" dans la section "Mise en Page Globale" vous permet de désactiver le calcul automatique de la taille de police de l'agenda et de définir vous-même une valeur fixe. Si le texte dépasse, il sera simplement tronqué.
*   **Amélioration du Retour Utilisateur pendant la Génération** : L'expérience de génération a été rendue plus transparente et informative :
    *   La barre de progression n'est plus une simple animation, elle affiche désormais un **pourcentage réel (de 0 à 100%)** de l'avancement du processus.
    *   Le texte de statut au-dessus de la barre a été amélioré pour indiquer **précisément l'étape en cours** (ex: "Étape 3/5 : Création du PDF...").
    *   Pour les stories, le message de statut final indique le **nombre exact d'images `.png` créées**.
*   **Correction du Bug des Polices Italiques** : Le problème qui empêchait les polices (autres qu'Arial) de s'afficher correctement en italique dans la boîte Cucaracha a été résolu. Le système d'enregistrement des polices a été fiabilisé.

## ⚙️ Pour les Développeuses et Développeurs

*   **Nouveau Moteur de Rendu d'Images avec Pillow** : La génération des stories est gérée par un nouveau module dédié (`misenpageur/image_builder.py`) qui utilise la bibliothèque `Pillow` pour dessiner directement sur des images PNG, indépendamment du moteur PDF ReportLab.
*   **Communication Asynchrone Améliorée** : Le système de communication entre le thread de travail et l'interface graphique a été refactorisé. La fonction `run_pipeline` envoie désormais des messages de statut structurés via une `queue`, permettant à l'interface de mettre à jour le texte et la barre de progression en temps réel.

---

# Bidul v1.2.13 - Prise en charge des Hyperliens dans l'Agenda

Cette version introduit une nouvelle fonctionnalité majeure pour l'interactivité des documents PDF : la reconnaissance automatique des hyperliens présents dans les données sources.

## ✨ Nouveautés

*   **Mise en format des données info (colonne `En Bref`)** : Le moteur de mise en page (`misenpageur`) met désormais en forme les informations info de la manière suivante: Valeurs de la colonne `FESTOCHE\nEVENEMENT ` en gras, infos de la colonne `STYLE \nFESTOCHE / EVENEMENT ` en mode tyle (parenthèse + italique) puis comprend les valuers de la colonne `NOM SPECTACLE 1 ( SV )` comme urls. 
*   **Hyperliens dans l'Agenda** : Le moteur de mise en page (`misenpageur`) reconnaît désormais les balises de lien HTML (`<a href="...">`) présentes dans les descriptions d'événements. Si vos fichiers `.xls` ou `.csv` contiennent des liens, ils seront automatiquement transformés en **liens cliquables** dans le PDF final, ainsi que dans le poster.

## ⚙️ Pour les Développeuses et Développeurs

*   **Amélioration du Parsing HTML** : La fonction `extract_paragraphs_from_html` a été entièrement revue. Elle utilise désormais la bibliothèque `BeautifulSoup4` pour parser le HTML. Au lieu d'extraire uniquement le texte brut, elle préserve les balises de formatage simples (`<a>`, `<strong>`, `<i>`, etc.) que le moteur `Paragraph` de ReportLab sait interpréter.
*   **Nouvelle Dépendance** : La bibliothèque `beautifulsoup4` a été ajoutée aux dépendances du projet.

---

# Bidul v1.2.12 - Amélioration de la Césure et de la Typographie

Cette version se concentre sur l'amélioration de la qualité typographique des textes générés, en résolvant des problèmes de césure (sauts de ligne) indésirables pour les noms propres et les expressions composées.

## 🔧 Améliorations et Corrections

*   **Gestion Avancée de l'Insécabilité** : La logique qui empêche les sauts de ligne inopportuns a été entièrement revue pour être plus intelligente et plus robuste.
    *   **Prise en charge des traits d'union** : Les noms composés avec des traits d'union (ex: "La Chapelle-Saint-Aubin") sont maintenant correctement traités pour éviter d'être coupés.
    *   **Recherche Flexible** : L'algorithme est désormais insensible aux variations d'espacement (espaces multiples) et à la casse (majuscules/minuscules), garantissant que les règles d'insécabilité définies dans le fichier `nobr.txt` sont appliquées de manière fiable.
*   **Correction du bug du "glyphe manquant"** : Une solution précédente qui remplaçait les traits d'union par un caractère spécial (`\u2011`) a été abandonnée car elle causait des problèmes d'affichage avec certaines polices. La nouvelle méthode garantit un rendu visuel parfait tout en assurant l'insécabilité.

## ⚙️ Pour les Développeuses et Développeurs

*   **Logique `_apply_non_breaking_strings` Revue** : La fonction a été refactorée pour utiliser des expressions régulières (`re.sub` avec une fonction `replacer`). Cette approche permet de trouver des correspondances de manière flexible dans le texte source et d'appliquer des remplacements intelligents (transformer les espaces en espaces insécables `\u00A0` tout en préservant les traits d'union).

---



# Bidul v1.2.10 - Améliorations Esthétiques Finales

Cette version se concentre sur le peaufinage de l'expérience utilisateur, en apportant des améliorations esthétiques à l'interface graphique et à la nouvelle fenêtre d'animation de victoire.

## ✨ Améliorations

*   **Animation de Victoire Améliorée** : L'animation "Solitaire" de fin de génération a été affinée pour un effet visuel plus agréable :
    *   La fenêtre de victoire apparaît désormais dans le coin inférieur droit de l'application principale, au lieu du centre.
    *   Les cartes animées apparaissent maintenant plus haut hors de l'écran, créant un effet de "pluie" plus prononcé.
    *   La vitesse des cartes a été légèrement réduite pour une animation plus douce.
*   **Ergonomie de la Fenêtre de Victoire** :
    *   Un bouton "Fermer", aligné à droite, a été ajouté à la fenêtre de résumé pour une fermeture plus intuitive.
    *   La taille de la fenêtre et du résumé a été ajustée pour un meilleur confort de lecture.
*   **Icônes d'Application** : La fenêtre principale et la fenêtre de victoire ont désormais leur propre icône, renforçant l'identité visuelle de l'application.

## 🔧 Corrections du Build Windows (`.exe`)

*   **Correction du Chargement des Assets** : Un bug qui empêchait le chargement des images de l'animation (les cartes) et des icônes dans la version "standalone" a été corrigé. Le fichier de configuration de PyInstaller (`bidul.spec`) a été mis à jour pour embarquer correctement le dossier `leTruc/assets`.

---


# Bidul v1.2.9 - Ajout d'une effet ouaaais dans le cas où le bidul est créé

Cette version ajoute une touche finale amusante et gratifiante à l'expérience utilisateur, ainsi que les dernières corrections sur la mise en page dynamique des hyperliens.

## ✨ Nouveautés

*   **Animation "Solitaire" de Fin de Génération** : Pour célébrer une génération de PDF réussie, une nouvelle fenêtre "Victoire !" s'affiche. Elle présente le résumé du traitement sur un fond d'animation de cartes rebondissantes, un clin d'œil à l'effet classique de Windows Solitaire.
    *   L'animation utilise plusieurs images de cartes différentes pour plus de variété visuelle.
    *   Les paramètres (couleur de fond, taille, etc.) sont facilement personnalisables dans le code.


---

# Bidul v1.2.8 - Amélioration du Layout Dynamique et Prévisualisation d'Images

Cette version apporte des corrections majeures à la gestion des marges dynamiques et améliore considérablement l'ergonomie de l'interface graphique avec l'ajout d'aperçus pour les images.

## ✨ Nouveautés et Améliorations de l'Interface (GUI)

*   **Prévisualisation des Images (Thumbnails)** : L'interface graphique affiche désormais une miniature (thumbnail) pour les champs d'images (Ours, Couverture, Cucaracha).
    *   Les aperçus se chargent automatiquement au démarrage de l'application si des chemins par défaut sont définis.
    *   La miniature se met à jour instantanément lorsque l'utilisateur sélectionne un nouveau fichier image, offrant un retour visuel immédiat.

## 🔧 Améliorations et Corrections du Rendu PDF

*   **Correction Majeure du Positionnement avec Marge** : Le bug critique qui empêchait les éléments de la colonne "Ours" (texte de l'auteur, hyperliens) de se déplacer correctement lors de l'application d'une marge globale a été résolu.
*   **Mise à l'échelle Homothétique** : La logique de dessin a été entièrement revue pour garantir que tous les éléments de l'ours (texte, QR code, espacements) sont non seulement repositionnés mais aussi redimensionnés proportionnellement à la taille de la colonne. Le rendu reste ainsi visuellement cohérent, quelle que soit la marge appliquée.

## ⚙️ Pour les Développeuses et Développeurs

*   **Logique de Positionnement Robuste** : Le calcul des coordonnées dans `drawing.py` a été refactorisé pour utiliser un système de ratio d'échelle basé sur des dimensions de référence. Cela garantit que tous les éléments enfants d'une section s'adaptent de manière prévisible aux changements de taille de leur parent.
*   **Intégration de Pillow dans le GUI** : La nouvelle fonctionnalité de prévisualisation d'images utilise la bibliothèque `Pillow` (`Image` et `ImageTk`) pour créer et afficher les miniatures directement dans l'interface Tkinter.
*   **Nettoyage** : On enlève le trigger sur push du github workflow config file du misenpageur.

---

# Bidul v1.2.7 - Amélioration de l'Expérience Utilisateur et de la Distribution

Cette version se concentre sur l'amélioration de l'expérience utilisateur lors de l'installation et de l'utilisation de l'application, en apportant des corrections importantes à la gestion des erreurs et à la distribution.

## ✨ Améliorations

*   **Gestion de l'Erreur "Fichier Ouvert"** : L'application ne plante plus avec une erreur technique si l'utilisateur essaie de générer un PDF qui est déjà ouvert dans un autre programme (comme Adobe Reader). Une boîte de dialogue claire s'affiche désormais, demandant à l'utilisateur de fermer le fichier avant de continuer.
*   **Ajout d'un Fichier `README.txt` à la Release** : L'archive `.zip` de la release contient maintenant un fichier `README.txt` avec des instructions claires pour les nouveaux utilisateurs. Il explique notamment comment contourner l'avertissement de sécurité "Microsoft Defender SmartScreen" qui peut apparaître au premier lancement.

## ⚙️ Pour les Développeuses et Développeurs

*   **Gestion de `PermissionError`** : La logique de traitement principal (`run_pipeline`) intercepte désormais spécifiquement l'exception `PermissionError` pour la transformer en un message d'erreur compréhensible pour l'utilisateur.
*   **Création Automatisée du `README.txt`** : Le workflow GitHub Actions a été mis à jour pour générer et inclure dynamiquement le fichier `README.txt` dans l'archive de la release à chaque build.

---
# Bidul v1.2.6 - Refactorisation de l'Interface Graphique

Cette version est principalement technique et se concentre sur une refactorisation majeure de l'interface graphique (GUI). L'objectif était d'améliorer la structure du code pour le rendre plus propre, plus maintenable et plus facile à faire évoluer à l'avenir, tout en corrigeant les derniers bugs d'interaction.

## ✨ Améliorations de l'Interface Graphique (GUI)

*   **Finalisation de la `Date Box`** : Le dernier bug lié au séparateur de dates de type "Box" a été corrigé. Le sélecteur de couleur pour le fond de la boîte s'affiche désormais correctement et la couleur choisie est bien appliquée dans le PDF final.
*   **Interface Simplifiée** : L'option de personnalisation de la couleur de la *bordure* de la `date box` a été retirée pour simplifier l'interface. Les boîtes sont maintenant toujours dessinées sans bordure.

## 🔧 Corrections

*   **Fichiers manquants ajoutés** : Logos, modèles (.cv, .xls) 

## ⚙️ Pour les Développeuses et Développeurs

*   **Refactorisation Complète du GUI** : Tout le code de l'interface a été restructuré en suivant les meilleures pratiques :
    *   **Architecture Modulaire** : Le code est maintenant divisé en plusieurs fichiers avec des responsabilités uniques (`app.py` pour la structure, `widgets.py` pour le visuel, `callbacks.py` pour la logique), ce qui remplace l'ancien fichier monolithique `gui.py`.
    *   **Structure Orientée Objet** : L'interface est désormais gérée par une classe `Application`, ce qui permet une meilleure gestion de l'état et une organisation du code plus claire.
*   **Fiabilisation du Build (`.spec`)** : Le fichier de configuration de PyInstaller (`bidul.spec`) a été mis à jour pour s'adapter à la nouvelle structure de fichiers du GUI, garantissant que les builds Windows fonctionnent correctement.

---


# Bidul v1.2.5 - Couleur de Police Automatique et Finalisation

Cette version introduit une nouvelle fonctionnalité intelligente pour le design du poster et finalise les améliorations de l'interface graphique et de la logique de placement des logos.

## ✨ Nouveautés

*   **Couleur de Police Automatique pour le Poster** : Lors de l'utilisation du design "Image en fond" pour le poster, l'application analyse désormais la luminosité de la zone centrale de l'image. Si le fond est détecté comme étant majoritairement sombre, la couleur de la police de l'agenda passe **automatiquement en blanc** pour garantir une lisibilité optimale. Cette fonctionnalité est entièrement configurable (`config.yml`).

## 🔧 Améliorations et Corrections

*   **Prise en Compte de la Transparence** : L'algorithme d'analyse de la luminosité simule désormais l'effet du voile blanc semi-transparent appliqué sur l'image, garantissant une détection de couleur précise et fiable, conforme au rendu final.

## ⚙️ Pour les Développeuses et Développeurs

*   **Analyse d'Image avec Pillow** : La nouvelle fonctionnalité de couleur automatique utilise la bibliothèque `Pillow` (`ImageStat`) pour calculer la luminosité moyenne d'une zone d'image, y compris après une simulation de composition alpha.

---

# Bidul v1.2.4 - Liens sur les Logos et Personnalisation des Dates

Cette version enrichit considérablement les possibilités de personnalisation et l'interactivité des documents PDF générés, en ajoutant des fonctionnalités très demandées.

## ✨ Nouveautés

*   **Hyperliens sur les Logos** : Il est désormais possible de rendre les logos cliquables. En modifiant le fichier `config.yml`, vous pouvez associer une URL à n'importe quel logo. Cette fonctionnalité est disponible pour les deux modes de répartition ("2 Colonnes" et "Optimisé").
*   **Sélecteur de Couleur pour les Séparateurs "Box"** : Lors de la personnalisation des séparateurs de dates dans l'interface graphique, si vous choisissez le type "Box", deux nouveaux boutons apparaissent. Ils permettent d'ouvrir un sélecteur de couleur natif pour choisir interactivement la couleur de la bordure et du fond de la boîte, offrant un contrôle visuel total sur le design.

## 🔧 Améliorations

*   **Interface Contextuelle** : Les nouvelles options de couleur pour les boîtes de date n'apparaissent que lorsque le type "Box" est sélectionné, gardant l'interface claire et épurée.
*   **Configuration centralisée** : Les nouveaux paramètres (liens des logos, couleurs des boîtes) sont gérés via les `dataclasses` de configuration pour un code plus propre et maintenable.

---

# Bidul v1.2.3 - Fiabilisation du Build et Interface Responsive

Cette version de maintenance est cruciale car elle se concentre sur la stabilisation de l'application Windows (`.exe`) et améliore l'ergonomie de l'interface graphique pour une expérience utilisateur plus fluide.

## ✨ Améliorations de l'Interface Graphique (GUI)

*   **Interface "Responsive" avec Barre de Défilement** : La fenêtre de l'application peut désormais être redimensionnée sans casser la mise en page. Si la hauteur de la fenêtre devient insuffisante pour afficher tous les paramètres, une barre de défilement verticale apparaît automatiquement, permettant un accès facile à toutes les options.
*   **Correction du Layout** : Des bugs visuels mineurs, comme un champ "Dossier logos" dupliqué et un positionnement incorrect du champ de marge, ont été corrigés pour une interface plus propre et plus logique.

## 🔧 Corrections du Build Windows (`.exe`)

Cette version corrige plusieurs bugs critiques qui n'apparaissaient que dans la version "standalone" de l'application :
*   **Correction des Erreurs de Traitement** : Un `TypeError` qui pouvait survenir lors du lancement du processus depuis l'interface a été résolu.

## ⚙️ Pour les Développeuses et Développeurs

*   **Fiabilisation du Workflow de Release** : Le script de la GitHub Action a été amélioré pour extraire et afficher correctement les notes de version spécifiques à chaque nouvelle release sur l'interface de GitHub.

---

# Bidul v1.2.2 - Stabilisation du Build Windows et Corrections

Cette version de maintenance se concentre sur la résolution de bugs critiques qui apparaissaient spécifiquement dans l'exécutable Windows (`.exe`) généré via GitHub Actions. L'application est désormais beaucoup plus stable et fiable en mode "standalone".

## 🔧 Améliorations et Corrections

*   **Correction du Chargement des Ressources** : Un bug majeur qui empêchait l'exécutable de trouver les fichiers de configuration par défaut (comme `config.yml`) a été résolu. Les champs de l'interface (image de couverture, dossier des logos, etc.) sont maintenant correctement pré-remplis au démarrage, comme en mode développement.
*   **Correction du Module `rectpack` Manquant** : L'erreur `ModuleNotFoundError: No module named 'rectpack'` qui faisait planter l'application lors de l'utilisation de la répartition optimisée des logos a été corrigée. La bibliothèque est maintenant correctement embarquée dans le build final.
*   **Correction de Bugs dans l'Interface Graphique** :
    *   Un bug de `TypeError` qui survenait lors du lancement de la répartition optimisée des logos a été résolu.
    *   Un champ "Dossier logos" qui apparaissait en double dans l'interface a été supprimé.
*   **Fiabilisation des Imports** : La manière dont les modules internes (comme `misenpageur`) sont chargés a été rendue plus robuste pour garantir leur bon fonctionnement à l'intérieur de l'environnement PyInstaller.

## ⚙️ Pour les Développeuses et Développeurs

*   **Chemins d'accès compatibles PyInstaller** : Une nouvelle fonction `get_resource_path` a été ajoutée. Elle utilise `sys._MEIPASS` lorsque l'application est packagée, garantissant que les assets et les configurations sont trouvés de manière fiable.
*   **Configuration du Build (`.spec`)** : Le fichier `bidul.spec` a été mis à jour pour inclure explicitement la dépendance cachée `rectpack` via l'option `hiddenimports`.

---
# Bidul v1.2.1 - Mise en Page Optimisée des Logos

Cette version introduit une nouvelle fonctionnalité majeure très demandée : un algorithme intelligent pour la mise en page des logos. Elle offre également plus de contrôle aux utilisateurs avancés pour affiner le rendu final.

## ✨ Nouveautés

*   **Répartition Optimisée des Logos** : En plus de la disposition classique en deux colonnes, une nouvelle option "Optimisée" est disponible. Elle utilise un algorithme de *rectangle packing* pour arranger les logos de manière dense et harmonieuse, en maximisant leur taille tout en leur garantissant une **surface visuelle égale**. Le résultat est une mise en page plus professionnelle et équilibrée, particulièrement efficace lorsque les logos ont des formes et des tailles très différentes.
*   **Contrôle Avancé du Packing** : Pour les utilisateurs exigeants, il est désormais possible de piloter finement l'algorithme de packing via le fichier `config.yml`. De nouveaux paramètres (`packing_strategy`) permettent de choisir l'algorithme de placement et la méthode de tri des logos, offrant un contrôle total sur l'esthétique finale.
*   **Marge des Logos Configurable** : La marge entre les logos pour la répartition optimisée peut maintenant être ajustée directement depuis l'interface graphique, permettant d'affiner facilement l'espacement.

## 🔧 Améliorations et Corrections

*   **Correction du Bug de Transparence des Logos** : La logique de placement prend désormais en compte la "bounding box" (le contenu visible) des logos PNG transparents, au lieu des dimensions du fichier. Cela corrige le bug majeur qui causait des chevauchements et des espacements incorrects.
*   **Préservation Garantie du Ratio d'Aspect** : L'algorithme de dessin a été entièrement revu pour garantir mathématiquement que le ratio largeur/hauteur de chaque logo est parfaitement préservé, éliminant tout risque de distorsion.
*   **Correction du Layout de l'Interface** : Un bug mineur qui plaçait mal le champ de configuration de la marge des logos dans l'interface a été corrigé.

## ⚙️ Pour les Développeuses et Développeurs

*   **Intégration de `rectpack`** : La bibliothèque `rectpack` a été ajoutée pour gérer la logique de packing. L'algorithme implémenté combine une recherche binaire sur la surface optimale avec une logique de "fit and center" robuste pour le dessin final.
*   **Configuration Structurée** : La configuration a été enrichie avec un `dataclass` dédié (`PackingStrategy`) pour une gestion propre et typée des nouveaux paramètres de l'algorithme.

---
# Bidul v1.2.0 - Interface Graphique Améliorée et Réactive

Cette version se concentre sur l'amélioration majeure de l'expérience utilisateur en rendant l'interface graphique (GUI) plus interactive, informative et pratique.

## ✨ Améliorations de l'Interface Graphique (GUI)

*   **Interface Réactive et Barre de Progression** : L'application ne se fige plus pendant la génération du PDF. Une barre de progression animée indique clairement que le traitement est en cours. Le bouton "Lancer la Génération" est temporairement désactivé pour éviter les clics multiples accidentels.
*   **Ouverture Automatique du PDF** : Une fois la génération terminée avec succès, l'application vous propose désormais d'ouvrir directement le fichier PDF créé, vous faisant gagner du temps.
*   **Mise à jour du Champ "Ours"** : L'interface a été mise à jour pour correspondre à la nouvelle architecture de l'ours. Le champ demande maintenant correctement une image de fond (`.png`) au lieu d'un fichier Markdown, ce qui est plus intuitif.

## ⚙️ Pour les Développeuses et Développeurs

*   **Exécution en Arrière-Plan (Threading)** : La logique de traitement principal (`run_pipeline`) est maintenant exécutée dans un thread séparé. Cela permet à l'interface graphique Tkinter de rester fluide et réactive, et de mettre à jour la barre de progression pendant que les tâches lourdes (parsing, génération PDF) s'effectuent en arrière-plan.

---

# Bidul v1.1.0 - Refonte de l'Ours et Fiabilisation des Exports

Cette nouvelle version se concentre sur la robustesse du rendu et la correction de bugs importants, notamment pour l'export SVG et la mise en page de la section "Ours", tout en introduisant une méthode beaucoup plus puissante pour la personnaliser.

## ✨ Nouveautés

*   **Ours Graphique Hybride** : La section "Ours" n'est plus limitée à du simple texte. Elle est désormais basée sur un modèle d'image de fond (`.png`), permettant des designs complexes avec des icônes et des polices personnalisées, garantissant une fidélité visuelle parfaite.
*   **Lien sur l'Auteur** : Le nom de l'auteur de la couverture, affiché dans l'ours, peut maintenant être un hyperlien cliquable, configurable via l'argument `--auteur-couv-url`.

## 🔧 Améliorations et Corrections

*   **Correction Majeure de l'Export SVG** : Le bug le plus critique de l'export SVG a été corrigé. Un mauvais caractère n'est plus remplacé à la place des puces d'événements (`❑`). La nouvelle logique de détection géométrique est beaucoup plus fiable et ne cible que les bonnes puces.
*   **Fiabilité du Rendu de l'Ours** : La nouvelle approche corrige tous les problèmes de rendu de l'ancienne méthode SVG :
    *   Les polices personnalisées s'affichent désormais parfaitement.
    *   Les problèmes de superposition de texte et d'espacement incorrect des caractères sont résolus.
    *   Les fonds noirs sur les icônes et les images avec transparence ont disparu.
*   **Détection Automatique de `pdf2svg`** : L'application trouve maintenant l'exécutable `pdf2svg` dans son propre dossier (`bin/win64`) sans nécessiter de configuration manuelle de la variable d'environnement PATH du système.

## ⚙️ Pour les Développeuses et Développeurs

*   **Architecture de l'Ours Revue** : L'approche initiale de parsing SVG direct avec `svglib` a été abandonnée en raison de ses limitations de rendu. Elle est remplacée par le modèle "PNG Hybride" (fond d'image statique + superposition d'éléments dynamiques avec ReportLab) pour garantir une fidélité visuelle parfaite et une interactivité fiable (liens).
*   **Résolution de Dépendance Circulaire** : Une importation circulaire entre les modules `drawing.py` et `draw_logic.py` a été corrigée par la création d'un module `utils.py`, améliorant la stabilité et la maintenabilité du code.

---

# Bidul v1.0.0 - Première Version Stable

Bienvenue dans la première version officielle de **Bidul** ! 🎉

Cette version marque l'aboutissement d'un long cycle de développement et offre un outil complet pour transformer vos listes d'événements en de superbes documents PDF et SVG, prêts à être partagés ou édités.

## 🚀 Fonctionnalités Principales

*   **Conversion de Données** : Importez facilement vos événements depuis des fichiers `.xls`, `.xlsx`, ou `.csv`.
*   **Génération PDF Multi-pages** :
    *   Créez un agenda détaillé sur deux pages avec une taille de police qui s'adapte automatiquement à votre contenu.
    *   Générez un magnifique poster A4 sur une troisième page, parfait pour l'affichage.
*   **Export SVG Éditable** : En plus du PDF, générez des fichiers SVG pour chaque page. Ces fichiers sont parfaits pour des retouches de dernière minute dans des logiciels comme **Inkscape**.
*   **Interface Graphique Intuitive** : Une application de bureau simple pour Windows qui vous guide à travers tout le processus, sans avoir besoin d'utiliser la ligne de commande.

## ✨ Personnalisation Avancée via l'Interface

Tout est configurable directement depuis l'application :

*   **Couverture** : Choisissez votre image de couverture, créditez l'auteur et ajoutez un lien.
*   **Mise en Page** : Ajustez la marge globale de votre document et l'espacement entre les sections.
*   **Boîte "Cucaracha"** : Ajoutez du contenu personnalisé (texte ou image) dans une boîte dédiée sur la première page.
*   **Design du Poster** : Choisissez entre deux designs pour votre poster :
    1.  **Image au centre** : Pour mettre en avant l'illustration.
    2.  **Image en fond** : Pour un style plus immersif, avec un contrôle précis de la transparence.
*   **Séparateurs de Dates** : Personnalisez l'affichage des dates avec des lignes, des boîtes, ou rien du tout.

## ⚙️ Pour les Développeurs (et les curieux)

*   **Architecture Modulaire** : Le projet est divisé en deux modules principaux : `biduleur` (pour le parsing des données) et `misenpageur` (pour la mise en page et le rendu).
*   **Configuration par Fichiers** : Toute la logique de mise en page est contrôlée par des fichiers `config.yml` et `layout.yml`, ce qui la rend facile à modifier sans toucher au code.
*   **Build Automatisé** : Le processus de création de l'exécutable pour Windows est entièrement automatisé grâce à GitHub Actions.

## 📥 Comment l'utiliser

1.  Téléchargez le fichier `bidul-v1.0.0-win64.zip` ci-dessous (dans la section "Assets").
2.  Décompressez l'archive dans un dossier de votre choix.
3.  Double-cliquez sur `bidul.exe` pour lancer l'application.

Un grand merci à tous ceux qui ont contribué et testé cette version. N'hésitez pas à ouvrir une "issue" sur GitHub si vous rencontrez un problème ou si vous avez des suggestions 
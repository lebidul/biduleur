# Misenpageur - Moteur de mise en page PDF

Ce document est destiné aux développeurs souhaitant comprendre, maintenir ou étendre le module `misenpageur`.

## 1. Objectif du Module

`misenpageur` est un moteur de rendu PDF spécialisé. Sa fonction principale est de prendre un contenu textuel semi-structuré (au format HTML), une configuration de style (`config.yml`) et un plan de mise en page géométrique (`layout.yml`) pour produire un document PDF de plusieurs pages (un agenda et un poster) prêt pour l'impression.

Il est conçu pour être le "back-end" de rendu du projet "Biduleur".

## 2. Concepts Fondamentaux

L'architecture de `misenpageur` repose sur une séparation stricte des responsabilités :

-   **Le Contenu (`input.html`)** : Fournit le texte brut des événements et des dates. Sa structure est simple (une suite de paragraphes `<p>`).
-   **La Géométrie (`layout.yml`)** : Définit la position et la taille de chaque "boîte" (section) sur chaque page. Les coordonnées sont exprimées en **points** (`pt`) avec une origine `(0,0)` en bas à gauche de la page. Ce fichier est la seule source de vérité pour la mise en page.
-   **Le Style et le Comportement (`config.yml`)** : Contrôle tous les aspects visuels et algorithmiques : polices, couleurs, marges, espacements, styles des puces, et active/désactive des fonctionnalités comme le poster.

Le code Python (`.py`) agit comme un chef d'orchestre, assemblant ces trois sources pour générer le document final.

## 3. L'Algorithme de Génération de PDF (`build_pdf`)

La fonction `build_pdf` dans `pdfbuild.py` est le cœur du module. Son exécution se déroule en plusieurs phases séquentielles.

### Phase 1 : Initialisation et Configuration

1.  **Création du Canvas** : Un objet `canvas` de ReportLab est créé avec les dimensions de la page définies dans `layout.yml`.
2.  **Enregistrement des Polices** : Les polices personnalisées (Arial Narrow, DS-net Stamped) et de fallback (DejaVu Sans) sont chargées et enregistrées auprès de ReportLab. Le code gère les cas où les polices ne sont pas trouvées sur le système.
3.  **Chargement des Contenus** :
    -   Le contenu HTML des événements est lu et parsé en une liste de chaînes de caractères (`paras`).
    -   Les termes insécables sont chargés depuis `nobr.txt` et appliqués aux `paras`.
    -   Le texte de l'Ours est lu depuis son fichier Markdown.
    -   Les images des logos sont listées depuis leur dossier.
4.  **Chargement des Configurations** : Des objets de configuration typés (`BulletConfig`, `PosterConfig`, etc.) sont créés en lisant les valeurs du `config.yml`. Cela permet d'avoir un accès propre et sécurisé aux paramètres dans le reste du code.

### Phase 2 : Planification du Texte (Pages 1 & 2)

C'est la partie la plus complexe de l'algorithme. L'objectif est de faire tenir un volume de texte variable dans un espace fixe (les sections S3, S4, S5, S6) en ajustant dynamiquement la taille de la police.

1.  **Recherche de la Taille de Police Optimale (`best_fs`)** :
    -   L'algorithme effectue une **recherche dichotomique (binary search)** entre `font_size_min` et `font_size_max`.
    -   À chaque itération, il teste une taille de police intermédiaire (`mid`).
    -   Pour tester cette taille, il appelle la fonction de simulation `_simulate_allocation_at_fs`.

2.  **Simulation (`_simulate_allocation_at_fs`)** :
    -   Cette fonction ne dessine rien. Elle prend la liste complète des paragraphes et tente de les placer "virtuellement" dans les sections de texte (S5, S6, S3, S4, dans cet ordre).
    -   Pour chaque paragraphe, elle calcule sa hauteur à la taille de police donnée, en tenant compte de l'espacement (`SpacingPolicy`), du retrait de puce (`hanging indent`), etc.
    -   Elle retourne le nombre total de paragraphes qu'elle a réussi à placer.
    -   Si tous les paragraphes tiennent (`tot >= len(paras)`), la taille testée est valide, et on peut essayer une taille plus grande. Sinon, il faut une taille plus petite.

3.  **Planification Finale avec Césure (`plan_pair_with_split`)** :
    -   Une fois la taille de police optimale (`best_fs`) trouvée, le texte n'est pas encore prêt à être dessiné. Il faut gérer les cas où un paragraphe est coupé entre deux sections (par exemple, entre le bas de S5 et le haut de S6).
    -   La fonction `plan_pair_with_split` est appelée deux fois : une fois pour la paire (S5, S6) et une fois pour (S3, S4).
    -   Elle remplit la première section avec autant de paragraphes complets que possible.
    -   Pour le premier paragraphe qui ne rentre pas, elle tente de le couper (`p.split()`). Si la partie qui rentre est jugée "suffisamment grande" (`split_min_gain_ratio`), la césure est effectuée.
    -   Elle retourne des listes de texte distinctes pour chaque section, incluant les parties coupées (`tail` et `prelude`).

### Phase 3 : Rendu (Dessin sur le Canvas)

À ce stade, toutes les décisions sont prises. Il ne reste plus qu'à dessiner.

1.  **Rendu de la Page 1** :
    -   `draw_s1` est appelée pour dessiner la section S1 (logos et Ours).
    -   `draw_s2_cover` est appelée pour dessiner l'image de couverture dans S2.
    -   `draw_section_fixed_fs_with_tail` dessine le contenu de S3.
    -   `draw_section_fixed_fs_with_prelude` dessine le contenu de S4.
    -   `c.showPage()` finalise la page 1.

2.  **Rendu de la Page 2** :
    -   Le même processus est appliqué pour S5 et S6 avec le texte planifié correspondant.

3.  **Rendu de la Page 3 (Poster)** :
    -   Cette logique est conditionnelle (`if poster_cfg.enabled:`).
    -   Le texte utilisé est la concaténation du texte planifié pour les pages 1 et 2 (`s5_full + s6_full + ...`).
    -   **Une deuxième recherche dichotomique** est effectuée, spécifiquement pour le poster, avec sa propre plage de tailles de police (`poster_font_size_min/max`). La simulation (`measure_poster_fit_at_fs`) utilise la liste des cadres du poster (`S7_Col1`, `S7_Col2_Top`, etc.).
    -   La logique de **design** est appliquée :
        -   **Design 0 (Image au centre)** : L'image est dessinée dans son cadre, et le texte s'écoule dans les cadres découpés autour.
        -   **Design 1 (Image en fond)** : L'image est dessinée en premier sur toute la page, suivie d'un voile blanc semi-transparent, et le texte s'écoule dans des cadres "pleine hauteur".
    -   Les éléments statiques (titre, logo du titre, QR code, logos du bas) sont dessinés.
    -   Le texte est finalement dessiné avec la taille de police optimale trouvée, après application du `font_size_safety_factor`.

### Phase 4 : Finalisation

-   `c.save()` écrit le fichier PDF sur le disque.
-   Des options de post-traitement (traits de coupe, conversion PDF/X) peuvent être activées.

## 4. Structure des Fichiers Clés

-   `pdfbuild.py`: **Chef d'orchestre**. Contient la fonction principale `build_pdf` et la logique de haut niveau.
-   `textflow.py`: **Le typographe**. Gère la création des `Paragraph`, le style du texte (indentation, justification), la mesure de la hauteur du texte et le flux de texte à travers les cadres.
-   `drawing.py`: **L'illustrateur**. Contient la logique de dessin pour les éléments non-textuels ou statiques (logos, QR code, couverture, boîte Cucaracha).
-   `config.py`: **Le contrat**. Définit les structures de données (`dataclass`) pour tous les paramètres de configuration.
-   `layout.py`: **L'architecte**. Définit les structures de données (`dataclass`) pour le layout (`Page`, `Section`).
-   `fonts.py`: **Le fondeur**. Gère la recherche et l'enregistrement des fichiers de polices.

## 5. Comment Étendre le Module

### Ajouter un nouveau paramètre de configuration (ex: `date_font_style`)

1.  **`config.py`**: Ajoutez le champ `date_font_style: str = "normal"` à la classe `Config`.
2.  **`pdfbuild.py`**: Dans la fonction `_read...` correspondante (ou directement dans `build_pdf`), lisez la nouvelle valeur depuis `cfg` (ex: `date_style = cfg.date_font_style`).
3.  **`textflow.py`**: Modifiez la fonction `_mk_style_for_kind` pour qu'elle utilise ce nouveau paramètre afin de changer le `fontName` du style des dates.

### Modifier la mise en page du poster

1.  **`layout.yml`**: Modifiez simplement les coordonnées `x, y, w, h` des sections `S7_*`.
2.  **`pdfbuild.py`**: Si vous avez ajouté/supprimé des cadres de texte, mettez à jour la liste `poster_frames` en conséquence.

## 6. Dépendances Clés

-   `reportlab`: Pour la génération de PDF.
-   `pyyaml`: Pour lire les fichiers `.yml`.
-   `Pillow`: Pour le pré-traitement des images.
-   `qrcode`: Pour générer le QR code.
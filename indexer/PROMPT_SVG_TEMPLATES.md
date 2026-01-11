# Prompt pour v1.12 : Templates SVG pour zones d'extraction OCR

## Contexte

L'indexer extrait le texte des PDFs scannés du Bidul (fanzine culturel) via OCR. Actuellement, les zones d'extraction sont calculées dynamiquement (sections A6 + colonnes). Cette approche manque de précision pour certains layouts complexes.

## Objectif

Implémenter un système de templates SVG qui permettent de définir avec précision les zones d'extraction du texte. Les templates peuvent être :
1. Générés automatiquement depuis la config CSV existante
2. Édités manuellement dans un éditeur SVG (Inkscape, navigateur)
3. Utilisés en priorité lors de l'extraction OCR

## Spécifications

### 1. Structure des fichiers

```
corpus/
├── biduls.description.csv      # Ajouter colonne 'svg_template'
└── templates/
    ├── bidul_005.svg           # Template personnalisé pour bidul 5
    ├── bidul_006.svg           # etc.
    └── default_paysage_2col.svg  # Templates génériques réutilisables
```

### 2. Format SVG

Le SVG doit avoir un `viewBox` correspondant aux dimensions de l'image PDF (en pixels à 200 DPI).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1654 2339" xmlns="http://www.w3.org/2000/svg">
  <!-- Métadonnées -->
  <metadata>
    <bidul numero="5" pages="2" orientation_pdf="portrait" orientation_texte="paysage"/>
  </metadata>

  <!-- Page 2 -->
  <g id="page-2" transform="rotate(90, 827, 1169)">
    <!-- Section S1 -->
    <g id="p2-s1">
      <rect id="p2-s1-col1" x="0" y="0" width="571" height="860"
            fill="rgba(255,0,0,0.1)" stroke="red" stroke-width="2"
            data-order="1"/>
      <rect id="p2-s1-col2" x="643" y="0" width="572" height="860"
            fill="rgba(0,0,255,0.1)" stroke="blue" stroke-width="2"
            data-order="2"/>
    </g>

    <!-- Section S3 (lue après S1 en mode paysage) -->
    <g id="p2-s3">
      <rect id="p2-s3-col1" x="0" y="870" width="571" height="860"
            fill="rgba(255,0,0,0.1)" stroke="red" stroke-width="2"
            data-order="3"/>
      <rect id="p2-s3-col2" x="643" y="870" width="572" height="860"
            fill="rgba(0,0,255,0.1)" stroke="blue" stroke-width="2"
            data-order="4"/>
    </g>

    <!-- Zones à exclure (logos, headers) -->
    <rect id="p2-exclude-header" x="0" y="0" width="1654" height="50"
          fill="rgba(128,128,128,0.3)" stroke="gray" data-exclude="true"/>
  </g>
</svg>
```

### 3. Convention de nommage des IDs

| Pattern | Usage | Exemple |
|---------|-------|---------|
| `page-{n}` | Groupe de page | `page-2` |
| `p{n}-s{s}` | Groupe de section | `p2-s1` |
| `p{n}-s{s}-col{c}` | Zone de colonne | `p2-s1-col1` |
| `p{n}-exclude-{name}` | Zone à exclure | `p2-exclude-header` |

### 4. Attributs data-*

| Attribut | Usage |
|----------|-------|
| `data-order` | Ordre de lecture (1, 2, 3...) |
| `data-exclude` | Zone à ignorer (true/false) |
| `data-rotation` | Rotation à appliquer avant OCR |

### 5. Priorité de chargement

1. **SVG personnalisé** : `corpus/templates/bidul_{numero}.svg` (si existe)
2. **Template référencé** : Via colonne `svg_template` dans CSV
3. **Calcul par défaut** : Méthode actuelle (sections A6 + colonnes)

### 6. Modification du CSV

Ajouter la colonne `svg_template` :

```csv
numero,type,date_format,...,svg_template,notes
5,scan,inline_inherited,...,bidul_005.svg,Template personnalisé
6,scan,inline_inherited,...,default_paysage_2col.svg,Template générique
7,scan,inline,...,,Calcul par défaut
```

## Tâches à réaliser

### Phase 1 : Générateur de templates

1. **Créer `core/svg_template.py`** avec :
   - `SVGTemplateGenerator` : Génère un SVG depuis la config CSV
   - `SVGTemplateLoader` : Charge et parse un SVG en zones d'extraction
   - `ExtractionZone` : Dataclass représentant une zone (x, y, w, h, order, exclude)

2. **CLI `svg-generate`** :
   ```bash
   python cli.py svg-generate --numero 5 -o corpus/templates/bidul_005.svg
   python cli.py svg-generate --range 1-20  # Génère tous les templates
   ```

3. **CLI `svg-preview`** :
   ```bash
   python cli.py svg-preview --numero 5  # Ouvre le PDF avec overlay SVG
   ```

### Phase 2 : Intégration à l'extraction

1. **Modifier `SectionOCRExtractor`** :
   - Charger le template SVG si disponible
   - Utiliser les zones définies au lieu du calcul par défaut
   - Respecter l'ordre `data-order`
   - Ignorer les zones `data-exclude`

2. **Modifier `biduls.description.csv`** :
   - Ajouter colonne `svg_template`
   - Mettre à jour `ScanConfig.from_csv_row()` et `BidulSectionConfig.from_csv_row()`

### Phase 3 : Tests et documentation

1. **Tests unitaires** dans `tests/test_svg_template.py`
2. **Mise à jour de la documentation** (.claude/instructions.md, release.md)

## Fichiers à modifier

| Fichier | Modification |
|---------|--------------|
| `core/svg_template.py` | **Nouveau** - Génération et chargement des templates |
| `core/section_extractor.py` | Intégrer le chargement des templates SVG |
| `core/ocr.py` | Mettre à jour `ScanConfig.from_csv_row()` |
| `cli.py` | Ajouter commandes `svg-generate`, `svg-preview` |
| `corpus/biduls.description.csv` | Ajouter colonne `svg_template` |
| `tests/test_svg_template.py` | **Nouveau** - Tests unitaires |

## Notes techniques

- Utiliser `xml.etree.ElementTree` ou `lxml` pour parser les SVG
- Les coordonnées sont en pixels à 200 DPI (résolution standard)
- Les transformations CSS (`rotate`, `translate`) doivent être supportées
- Prévoir un fallback si le SVG est invalide ou manquant

## Commandes de test

```bash
# Après implémentation, tester avec :
python cli.py svg-generate --numero 5 -o corpus/templates/bidul_005.svg
python cli.py svg-preview --numero 5
python cli.py ocr-extract --numero 5 --dry-run  # Doit utiliser le template
python -m pytest tests/test_svg_template.py -v
```

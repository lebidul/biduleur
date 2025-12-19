* stocker description biduls dans table ref importable pour exectution (sinon depuis fichier csv) qui puisse être consolidée
* #evenements dans table bidul
* créer fichier CONTEXT.md
* useful queries / views
*  améliorer mauvaises extractions détectées avec:

SELECT *
FROM evenement, json_each(evenement.artistes)
WHERE json_extract(value, '$.nom') in ('L''E', 'K C', 'L''A', 'K L')
ORDER BY date_evenement;

* Consolidation pdf: 
Excellente question. Avec 8000+ événements et 30 ans de formats différents, le full automatique va rater des cas et le full manuel est irréaliste. Voici mon approche hybride :

## Stratégie de consolidation

```
┌─────────────────────────────────────────────────────────────────┐
│                     PIPELINE CONSOLIDATION                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                 │
│  │ Extract  │ ──▶ │  Triage  │ ──▶ │  Review  │                 │
│  │ (auto)   │     │  (auto)  │     │ (manuel) │                 │
│  └──────────┘     └──────────┘     └──────────┘                 │
│       │                │                 │                      │
│       │                │                 │                      │
│       ▼                ▼                 ▼                      │
│  ┌───────────┐     ┌──────────┐     ┌──────────┐                │
│  │ Confidence│     │ Prioriser│     │ Corriger │                │
│  │ scoring   │     │ les cas  │     │ + valider│                │
│  └───────────┘     │ litigieux│     └──────────┘                │
│                    └──────────┘           │                     │
│                                           ▼                     │
│                                     ┌──────────┐                │
│                                     │ Feedback │                │
│                                     │ → Parser │                │
│                                     └──────────┘                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 1. Triage automatique (priorisation)

Catégoriser les événements par niveau de confiance :

| Catégorie | Critères | Action |
|-----------|----------|--------|
| **✅ OK** | confidence ≥ 0.9, lieu matché, date parsée | Aucune |
| **⚠️ À vérifier** | 0.7 ≤ confidence < 0.9, ou lieu non matché | Review rapide |
| **❌ Problématique** | confidence < 0.7, champs critiques manquants | Review détaillé |
| **🔴 Anomalie** | Doublons potentiels, incohérences | Investigation |

## 2. Interface de review (CLI ou web)

```bash
# Review par priorité
python cli.py review --status problematic     # Les pires d'abord
python cli.py review --bidul 280              # Un Bidul spécifique
python cli.py review --no-lieu                # Événements sans lieu matché
python cli.py review --random 20              # Échantillon aléatoire (QA)
```

### Mode interactif

```
═══════════════════════════════════════════════════════════════
 REVIEW EVENT #9964 (Bidul 287)                    [12/847 ⚠️]
═══════════════════════════════════════════════════════════════

RAW TEXT:
  API UIZ + TAENIA TURNER (noise rock), bar Le Lézard, 19h30, 0€ 
  Merci Connasse présente CHEVALIEN (bass music)+ NO GRIZZLY...

PARSED:
  Spectacles: []
  Artistes:   [API UIZ, TAENIA TURNER, CHEVALIEN, NO GRIZZLY...]
  Lieu:       bar Le Lézard → Le Lézard (id=252) ✓
  Ville:      Le Mans ✓
  Heure:      19h30 ✓
  Prix:       0€ (gratuit) ✓

⚠️ PROBLÈMES DÉTECTÉS:
  - Plusieurs lieux détectés (Le Lézard, Le Barouf) → splitter?

───────────────────────────────────────────────────────────────
Actions:
  [v] Valider tel quel     [s] Splitter en 2 événements
  [e] Éditer manuellement  [d] Supprimer (faux positif)
  [f] Flag pour plus tard  [n] Suivant (skip)
  [q] Quitter

Choix: _
```

## 3. Feedback loop vers le parser

Quand tu corriges manuellement, le système apprend :

```python
# Table pour stocker les corrections
CREATE TABLE correction_log (
    id INTEGER PRIMARY KEY,
    evenement_id INTEGER,
    champ TEXT,              -- 'lieu', 'artistes', 'split', etc.
    valeur_avant TEXT,
    valeur_apres TEXT,
    type_correction TEXT,    -- 'typo', 'split', 'merge', 'pattern'
    created_at DATETIME
);
```

### Génération de règles

```bash
# Après N corrections, générer des suggestions d'amélioration
python cli.py analyze-corrections

# Output:
# ═══════════════════════════════════════════════════
# PATTERNS DE CORRECTION DÉTECTÉS
# ═══════════════════════════════════════════════════
# 
# 1. LIEU: "bar le Lézard" → "Le Lézard" (corrigé 12x)
#    → Ajouter règle de normalisation
# 
# 2. SPLIT: Événements avec 2+ lieux splittés 8x
#    → Pattern: plusieurs heures + plusieurs lieux
# 
# 3. SPECTACLE: Texte entre guillemets mal parsé 5x
#    → Améliorer regex guillemets français «»
```

## 4. Rapports de qualité

```bash
python cli.py quality-report
```

```
═══════════════════════════════════════════════════════════════
 RAPPORT QUALITÉ - 2025-12-19
═══════════════════════════════════════════════════════════════

GLOBAL:
  Événements totaux:     8,247
  Vérifiés (verified):   1,203 (14.6%)
  À reviewer:            847 (10.3%)
  
CONFIDENCE:
  ≥ 0.9:   6,421 (77.8%) ████████████████░░░░
  0.7-0.9: 1,102 (13.4%) ███░░░░░░░░░░░░░░░░░
  < 0.7:     724 (8.8%)  ██░░░░░░░░░░░░░░░░░░

CHAMPS:
  Lieu matché:     7,891 (95.7%)
  Date parsée:     8,102 (98.2%)
  Heure présente:  7,654 (92.8%)
  Artistes/Spec:   7,203 (87.3%)

PAR SOURCE:
  CSV:   1,847 (22.4%) - confidence moy: 1.00
  PDF:   6,400 (77.6%) - confidence moy: 0.86

PAR PÉRIODE:
  1997-2005: 2,103 events - conf moy: 0.72 ⚠️ (OCR)
  2006-2015: 2,987 events - conf moy: 0.85
  2016-2024: 3,157 events - conf moy: 0.94

TOP LIEUX NON MATCHÉS:
  "Salle des fêtes" (47x) - ambigu, ville nécessaire
  "Chez Marcel" (12x) - variante de "Chez Marcelle"?
  "MJC" (8x) - laquelle?
```

## 5. Workflow recommandé

```
SEMAINE 1: Extraction initiale
├── Extraire tous les PDFs texte (178-308)
├── Importer les CSV disponibles
└── Générer rapport qualité initial

SEMAINE 2-3: Review prioritaire
├── Corriger les événements confidence < 0.7 (~700)
├── Valider un échantillon aléatoire (5%)
└── Identifier patterns de correction récurrents

SEMAINE 4: Amélioration parser
├── Implémenter les règles déduites des corrections
├── Re-extraire les Biduls les plus problématiques
└── Comparer avant/après

ENSUITE: Maintenance continue
├── Review des nouveaux Biduls à l'ajout
├── Échantillonnage QA mensuel
└── Amélioration continue du parser
```

## 6. Schema enrichi pour consolidation

```sql
-- Ajouter à la table evenement
ALTER TABLE evenement ADD COLUMN verified BOOLEAN DEFAULT FALSE;
ALTER TABLE evenement ADD COLUMN verified_by TEXT;
ALTER TABLE evenement ADD COLUMN verified_at DATETIME;
ALTER TABLE evenement ADD COLUMN review_status TEXT DEFAULT 'pending';
-- 'pending', 'to_review', 'verified', 'flagged', 'deleted'
ALTER TABLE evenement ADD COLUMN review_notes TEXT;
```

---

## Résumé

| Aspect | Automatique | Manuel | Hybride ✓ |
|--------|-------------|--------|-----------|
| Volume | ✓ | ✗ | ✓ |
| Qualité | ✗ | ✓ | ✓ |
| Temps | ✓ | ✗ | ✓ |
| Apprentissage | ✗ | ✗ | ✓ |

**Ma recommandation** : Commencer par le triage automatique, puis review manuel ciblé sur les ~10% problématiques, avec feedback loop pour améliorer le parser au fil du temps.

Tu veux que je prépare le prompt Claude Code pour implémenter le système de review CLI ?
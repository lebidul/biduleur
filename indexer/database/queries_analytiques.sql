-- =============================================================================
-- Requêtes analytiques - Archives du Bidul
-- =============================================================================
-- Base de données SQLite avec extraction automatique des PDFs
-- Architecture v2 avec tables normalisées:
--   - bidul: métadonnées des numéros
--   - evenement: événements avec raw_text, dates, lieux, tarifs
--   - contenu_evenement: artistes et spectacles normalisés (relation 1-N)
--   - lieu_ref / lieu_alias: référentiels lieux avec aliases
--   - ville_ref: référentiel villes
--   - artiste_ref / artiste_alias: référentiels artistes avec aliases
--   - correction_log: historique des corrections manuelles
-- =============================================================================

-- =============================================================================
-- REQUÊTES DE BASE - Exploration des événements
-- =============================================================================

-- Liste des événements d'un Bidul avec artistes et spectacles (normalisés)
SELECT
    e.id,
	e.bidul_numero,
    e.raw_text,
    e.nom,
	e.genre_evenement,
    e.date_evenement,
    e.heure,
	e.lieu_raw,
	lr.nom,
	e.ville_raw,
	vr.nom,
    e.tarif_raw,
    c.nom_spectacle,
	c.artiste,
	ar.nom,
    c.style
FROM evenement e
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
LEFT JOIN contenu_evenement c ON e.id = c.evenement_id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
WHERE e.bidul_numero = 12
--and raw_text like '%xx%'
ORDER BY e.date_evenement,e.raw_text,e.heure;
--ORDER BY e.raw_text,e.date_evenement,e.heure;

select raw_text from bidul where numero = 12;

-- ORDER BY e.date_evenement, e.heure, c.ordre;

-- Teriaki

SELECT
    e.id,
	e.bidul_numero,
    e.raw_text,
    e.nom,
	e.genre_evenement,
    e.date_evenement,
    e.heure,
	e.lieu_raw,
	lr.nom,
	e.ville_raw,
	vr.nom,
    e.tarif_raw,
    c.nom_spectacle,
	c.artiste,
	ar.nom,
    c.style
FROM evenement e
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
LEFT JOIN contenu_evenement c ON e.id = c.evenement_id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
WHERE
-- e.bidul_numero = 292
-- and raw_text like '%ronsard%'
raw_text like '%teriaki%'
ORDER BY bidul_numero,e.date_evenement,e.raw_text,e.heure;

-- Événements d'une date précise avec détails complets (normalisés)
SELECT
    e.id,
    e.heure,
    e.nom AS evenement,
    GROUP_CONCAT(DISTINCT COALESCE(ar.nom, c.artiste)) AS artistes,
    GROUP_CONCAT(DISTINCT c.nom_spectacle) AS spectacles,
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    COALESCE(vr.nom, e.ville_raw, 'Le Mans') AS ville,
    e.tarif_raw AS prix,
    e.type_evenement AS type
FROM evenement e
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
LEFT JOIN contenu_evenement c ON e.id = c.evenement_id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
WHERE e.date_evenement = '2023-05-14'  -- Modifier cette date
GROUP BY e.id
ORDER BY e.heure;

-- =============================================================================
-- ARTISTES - Statistiques et recherche (avec référentiel normalisé)
-- =============================================================================

-- Top 30 artistes les plus programmés (via référentiel normalisé)
SELECT
    COALESCE(ar.nom, c.artiste) AS artiste_normalise,
    COUNT(DISTINCT e.id) AS nb_concerts,
    COUNT(DISTINCT e.bidul_numero) AS nb_biduls,
    MIN(strftime('%Y', e.date_evenement)) AS premiere_annee,
    MAX(strftime('%Y', e.date_evenement)) AS derniere_annee,
    GROUP_CONCAT(DISTINCT c.style) AS styles,
    CASE WHEN c.artiste_ref_id IS NOT NULL THEN 'oui' ELSE 'non' END AS normalise
FROM contenu_evenement c
JOIN evenement e ON c.evenement_id = e.id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
WHERE c.artiste IS NOT NULL
GROUP BY COALESCE(ar.nom, c.artiste)
HAVING nb_concerts >= 2
ORDER BY nb_concerts DESC
LIMIT 30;

-- Recherche d'un artiste (inclut les alias)
SELECT
    e.date_evenement,
    e.heure,
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    COALESCE(vr.nom, e.ville_raw, 'Le Mans') AS ville,
    c.style,
    e.tarif_raw AS prix,
    e.bidul_numero,
    c.artiste AS artiste_raw,
    ar.nom AS artiste_normalise
FROM contenu_evenement c
JOIN evenement e ON c.evenement_id = e.id
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
WHERE c.artiste LIKE '%MOONLIGHT%'  -- Modifier le nom de l'artiste
   OR ar.nom LIKE '%MOONLIGHT%'
ORDER BY e.date_evenement;

-- Artistes par style/genre (normalisés)
SELECT
    c.style,
    COALESCE(ar.nom, c.artiste) AS artiste,
    COUNT(*) AS nb_concerts
FROM contenu_evenement c
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
WHERE c.style IS NOT NULL AND c.artiste IS NOT NULL
GROUP BY c.style, COALESCE(ar.nom, c.artiste)
HAVING COUNT(*) >= 2
ORDER BY c.style, nb_concerts DESC;

-- Duo/groupes qui jouent souvent ensemble (normalisés)
SELECT
    COALESCE(ar1.nom, c1.artiste) AS artiste1,
    COALESCE(ar2.nom, c2.artiste) AS artiste2,
    COUNT(*) AS nb_concerts_ensemble
FROM contenu_evenement c1
JOIN contenu_evenement c2 ON c1.evenement_id = c2.evenement_id
    AND c1.artiste < c2.artiste  -- Évite les doublons A-B et B-A
LEFT JOIN artiste_ref ar1 ON c1.artiste_ref_id = ar1.id
LEFT JOIN artiste_ref ar2 ON c2.artiste_ref_id = ar2.id
WHERE c1.artiste IS NOT NULL AND c2.artiste IS NOT NULL
GROUP BY COALESCE(ar1.nom, c1.artiste), COALESCE(ar2.nom, c2.artiste)
HAVING COUNT(*) >= 3
ORDER BY nb_concerts_ensemble DESC
LIMIT 20;

-- Statistiques de matching artistes
SELECT
    'Total artistes (contenu_evenement)' AS metrique,
    COUNT(*) AS valeur
FROM contenu_evenement WHERE artiste IS NOT NULL
UNION ALL
SELECT 'Artistes matchés (artiste_ref_id)', COUNT(*)
FROM contenu_evenement WHERE artiste_ref_id IS NOT NULL
UNION ALL
SELECT 'Artistes non matchés', COUNT(*)
FROM contenu_evenement WHERE artiste IS NOT NULL AND artiste_ref_id IS NULL
UNION ALL
SELECT 'Taux de matching (%)', ROUND(100.0 * COUNT(artiste_ref_id) / COUNT(*), 1)
FROM contenu_evenement WHERE artiste IS NOT NULL;

-- =============================================================================
-- SPECTACLES - Théâtre, danse, etc.
-- =============================================================================

-- Top spectacles les plus joués
SELECT
    c.nom_spectacle,
    c.style AS genre,
    COUNT(DISTINCT e.id) AS nb_representations,
    MIN(e.date_evenement) AS premiere,
    MAX(e.date_evenement) AS derniere
FROM contenu_evenement c
JOIN evenement e ON c.evenement_id = e.id
WHERE c.nom_spectacle IS NOT NULL
GROUP BY c.nom_spectacle
HAVING nb_representations >= 2
ORDER BY nb_representations DESC
LIMIT 20;

-- Spectacles par style (théâtre, danse, cirque, etc.)
SELECT
    c.style,
    COUNT(DISTINCT c.nom_spectacle) AS nb_spectacles,
    COUNT(DISTINCT e.id) AS nb_representations
FROM contenu_evenement c
JOIN evenement e ON c.evenement_id = e.id
WHERE c.nom_spectacle IS NOT NULL AND c.style IS NOT NULL
GROUP BY c.style
ORDER BY nb_representations DESC;

-- =============================================================================
-- LIEUX - Analyse géographique (avec référentiel normalisé)
-- =============================================================================

-- Top 20 lieux les plus actifs (avec référentiel)
SELECT
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    COALESCE(lr.ville, vr.nom, e.ville_raw, 'Le Mans') AS ville,
    COUNT(*) AS nb_events,
    COUNT(DISTINCT e.bidul_numero) AS nb_biduls,
    MIN(strftime('%Y', e.date_evenement)) AS depuis,
    MAX(strftime('%Y', e.date_evenement)) AS jusqua,
    CASE WHEN e.lieu_ref_id IS NOT NULL THEN 'oui' ELSE 'non' END AS normalise
FROM evenement e
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
WHERE e.lieu_raw IS NOT NULL OR e.lieu_ref_id IS NOT NULL
GROUP BY COALESCE(lr.nom, e.lieu_raw), COALESCE(lr.ville, vr.nom, e.ville_raw)
ORDER BY nb_events DESC
LIMIT 20;

-- Programmation d'un lieu spécifique (recherche avec alias)
SELECT
    e.date_evenement,
    e.heure,
    e.nom AS evenement,
    GROUP_CONCAT(DISTINCT COALESCE(ar.nom, c.artiste)) AS artistes,
    GROUP_CONCAT(DISTINCT c.nom_spectacle) AS spectacles,
    e.type_evenement,
    e.tarif_raw,
    e.lieu_raw AS lieu_brut,
    lr.nom AS lieu_normalise
FROM evenement e
LEFT JOIN contenu_evenement c ON e.id = c.evenement_id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
WHERE lr.nom LIKE '%Oasis%' OR e.lieu_raw LIKE '%Oasis%'
GROUP BY e.id
ORDER BY e.date_evenement DESC
LIMIT 50;

-- Répartition géographique (par ville)
SELECT
    COALESCE(vr.nom, e.ville_raw, 'Le Mans') AS ville,
    COUNT(*) AS nb_events,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1) AS pct
FROM evenement e
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
GROUP BY COALESCE(vr.nom, e.ville_raw)
ORDER BY nb_events DESC
LIMIT 20;

-- Lieux non résolus (pas dans le référentiel)
SELECT
    e.lieu_raw,
    e.ville_raw,
    COUNT(*) AS nb_events
FROM evenement e
WHERE e.lieu_ref_id IS NULL AND e.lieu_raw IS NOT NULL
GROUP BY e.lieu_raw, e.ville_raw
ORDER BY nb_events DESC
LIMIT 30;

-- Statistiques de matching lieux
SELECT
    'Total événements avec lieu_raw' AS metrique,
    COUNT(*) AS valeur
FROM evenement WHERE lieu_raw IS NOT NULL
UNION ALL
SELECT 'Lieux matchés (lieu_ref_id)', COUNT(*)
FROM evenement WHERE lieu_ref_id IS NOT NULL
UNION ALL
SELECT 'Lieux non matchés', COUNT(*)
FROM evenement WHERE lieu_raw IS NOT NULL AND lieu_ref_id IS NULL
UNION ALL
SELECT 'Taux de matching (%)', ROUND(100.0 * COUNT(lieu_ref_id) / COUNT(*), 1)
FROM evenement WHERE lieu_raw IS NOT NULL;

-- =============================================================================
-- RÉFÉRENTIELS - Exploration des tables normalisées
-- =============================================================================

-- Liste des lieux du référentiel
SELECT
    lr.id,
    lr.nom,
    lr.ville,
    lr.actif,
    COUNT(e.id) AS nb_events
FROM lieu_ref lr
LEFT JOIN evenement e ON e.lieu_ref_id = lr.id
GROUP BY lr.id
ORDER BY nb_events DESC;

-- Liste des artistes du référentiel
SELECT
    ar.id,
    ar.nom,
    ar.style,
    ar.actif,
    COUNT(c.id) AS nb_concerts
FROM artiste_ref ar
LEFT JOIN contenu_evenement c ON c.artiste_ref_id = ar.id
GROUP BY ar.id
ORDER BY nb_concerts DESC;

-- Aliases de lieux
SELECT
    la.variante,
    la.lieu_nom,
    lr.ville
FROM lieu_alias la
JOIN lieu_ref lr ON la.lieu_nom = lr.nom
ORDER BY la.lieu_nom, la.variante;

-- Aliases d'artistes
SELECT
    aa.variante,
    aa.artiste_nom
FROM artiste_alias aa
ORDER BY aa.artiste_nom, aa.variante;

-- Artistes avec le plus d'aliases
SELECT
    ar.nom AS artiste,
    COUNT(aa.id) AS nb_aliases,
    GROUP_CONCAT(aa.variante, ', ') AS aliases
FROM artiste_ref ar
JOIN artiste_alias aa ON aa.artiste_nom = ar.nom
GROUP BY ar.nom
HAVING COUNT(aa.id) > 1
ORDER BY nb_aliases DESC
LIMIT 20;

-- Lieux avec le plus d'aliases
SELECT
    lr.nom AS lieu,
    lr.ville,
    COUNT(la.id) AS nb_aliases,
    GROUP_CONCAT(la.variante, ', ') AS aliases
FROM lieu_ref lr
JOIN lieu_alias la ON la.lieu_nom = lr.nom
GROUP BY lr.nom
HAVING COUNT(la.id) > 1
ORDER BY nb_aliases DESC
LIMIT 20;

-- =============================================================================
-- PRIX ET TARIFS
-- =============================================================================

-- Prix moyen par type d'événement
SELECT
    e.type_evenement,
    COUNT(*) AS nb_events,
    ROUND(AVG(e.prix_min), 2) AS prix_min_moyen,
    ROUND(AVG(e.prix_max), 2) AS prix_max_moyen,
    SUM(CASE WHEN e.gratuit = 1 THEN 1 ELSE 0 END) AS nb_gratuits,
    ROUND(100.0 * SUM(CASE WHEN e.gratuit = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_gratuit
FROM evenement e
WHERE e.type_evenement IS NOT NULL
GROUP BY e.type_evenement
ORDER BY nb_events DESC;

-- Évolution du prix moyen par année
SELECT
    strftime('%Y', e.date_evenement) AS annee,
    COUNT(*) AS nb_events,
    ROUND(AVG(e.prix_min), 2) AS prix_min_moyen,
    ROUND(AVG(e.prix_max), 2) AS prix_max_moyen,
    ROUND(100.0 * SUM(CASE WHEN e.gratuit = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_gratuit
FROM evenement e
WHERE e.date_evenement IS NOT NULL AND (e.prix_min IS NOT NULL OR e.gratuit = 1)
GROUP BY annee
ORDER BY annee;

-- Événements les plus chers
SELECT
    e.date_evenement,
    e.nom AS evenement,
    GROUP_CONCAT(DISTINCT COALESCE(ar.nom, c.artiste)) AS artistes,
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    e.tarif_raw,
    e.prix_max
FROM evenement e
LEFT JOIN contenu_evenement c ON e.id = c.evenement_id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
WHERE e.prix_max IS NOT NULL
GROUP BY e.id
ORDER BY e.prix_max DESC
LIMIT 20;

-- =============================================================================
-- TEMPORALITÉ
-- =============================================================================

-- Événements par année
SELECT
    strftime('%Y', date_evenement) AS annee,
    COUNT(*) AS nb_events,
    COUNT(DISTINCT bidul_numero) AS nb_biduls
FROM evenement
WHERE date_evenement IS NOT NULL
GROUP BY annee
ORDER BY annee;

-- Événements par mois (tous les ans confondus)
SELECT
    CASE strftime('%m', date_evenement)
        WHEN '01' THEN 'Janvier'
        WHEN '02' THEN 'Février'
        WHEN '03' THEN 'Mars'
        WHEN '04' THEN 'Avril'
        WHEN '05' THEN 'Mai'
        WHEN '06' THEN 'Juin'
        WHEN '07' THEN 'Juillet'
        WHEN '08' THEN 'Août'
        WHEN '09' THEN 'Septembre'
        WHEN '10' THEN 'Octobre'
        WHEN '11' THEN 'Novembre'
        WHEN '12' THEN 'Décembre'
    END AS mois,
    COUNT(*) AS nb_events
FROM evenement
WHERE date_evenement IS NOT NULL
GROUP BY strftime('%m', date_evenement)
ORDER BY strftime('%m', date_evenement);

-- Événements par jour de la semaine
SELECT
    CASE strftime('%w', date_evenement)
        WHEN '0' THEN 'Dimanche'
        WHEN '1' THEN 'Lundi'
        WHEN '2' THEN 'Mardi'
        WHEN '3' THEN 'Mercredi'
        WHEN '4' THEN 'Jeudi'
        WHEN '5' THEN 'Vendredi'
        WHEN '6' THEN 'Samedi'
    END AS jour,
    COUNT(*) AS nb_events,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement WHERE date_evenement IS NOT NULL), 1) AS pct
FROM evenement
WHERE date_evenement IS NOT NULL
GROUP BY strftime('%w', date_evenement)
ORDER BY
    CASE strftime('%w', date_evenement)
        WHEN '1' THEN 1
        WHEN '2' THEN 2
        WHEN '3' THEN 3
        WHEN '4' THEN 4
        WHEN '5' THEN 5
        WHEN '6' THEN 6
        WHEN '0' THEN 7
    END;

-- Historique d'un jour de l'année (ex: tous les 14 mai)
SELECT
    strftime('%Y', e.date_evenement) AS annee,
    GROUP_CONCAT(DISTINCT COALESCE(ar.nom, c.artiste)) AS artistes,
    COALESCE(lr.nom, e.lieu_raw) AS lieu
FROM evenement e
LEFT JOIN contenu_evenement c ON e.id = c.evenement_id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
WHERE strftime('%m-%d', e.date_evenement) = '05-14'  -- Modifier jour-mois
GROUP BY e.id
ORDER BY annee DESC;

-- =============================================================================
-- STYLES ET GENRES MUSICAUX
-- =============================================================================

-- Top styles/genres
SELECT
    c.style,
    COUNT(DISTINCT e.id) AS nb_events,
    COUNT(DISTINCT COALESCE(ar.nom, c.artiste)) AS nb_artistes
FROM contenu_evenement c
JOIN evenement e ON c.evenement_id = e.id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
WHERE c.style IS NOT NULL
GROUP BY c.style
ORDER BY nb_events DESC
LIMIT 30;

-- Évolution des styles par année
SELECT
    strftime('%Y', e.date_evenement) AS annee,
    c.style,
    COUNT(*) AS nb_events
FROM contenu_evenement c
JOIN evenement e ON c.evenement_id = e.id
WHERE c.style IS NOT NULL AND e.date_evenement IS NOT NULL
GROUP BY annee, c.style
HAVING COUNT(*) >= 5
ORDER BY annee, nb_events DESC;

-- =============================================================================
-- QUALITÉ DES DONNÉES ET REVIEW
-- =============================================================================

-- Répartition par source (CSV vs PDF)
SELECT
    source,
    COUNT(*) AS nb_events,
    ROUND(AVG(confidence), 2) AS confidence_moyenne,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1) AS pct
FROM evenement
GROUP BY source;

-- Répartition par statut de review
SELECT
    COALESCE(review_status, 'pending') AS statut,
    COUNT(*) AS nb_events,
    ROUND(AVG(confidence), 2) AS confidence_moyenne
FROM evenement
GROUP BY review_status
ORDER BY nb_events DESC;

-- Événements vérifiés vs non vérifiés
SELECT
    CASE WHEN verified = 1 THEN 'Vérifié' ELSE 'Non vérifié' END AS statut,
    COUNT(*) AS nb_events,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1) AS pct
FROM evenement
GROUP BY verified;

-- Distribution de confidence
SELECT
    CASE
        WHEN confidence >= 0.9 THEN '0.9+ (excellent)'
        WHEN confidence >= 0.8 THEN '0.8-0.9 (bon)'
        WHEN confidence >= 0.7 THEN '0.7-0.8 (correct)'
        WHEN confidence >= 0.5 THEN '0.5-0.7 (à vérifier)'
        ELSE '<0.5 (problématique)'
    END AS niveau,
    COUNT(*) AS nb_events,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1) AS pct
FROM evenement
GROUP BY niveau
ORDER BY
    CASE niveau
        WHEN '0.9+ (excellent)' THEN 1
        WHEN '0.8-0.9 (bon)' THEN 2
        WHEN '0.7-0.8 (correct)' THEN 3
        WHEN '0.5-0.7 (à vérifier)' THEN 4
        ELSE 5
    END;

-- Événements à faible confidence (à vérifier en priorité)
SELECT
    e.bidul_numero,
    e.date_evenement,
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    e.confidence,
    SUBSTR(e.raw_text, 1, 100) AS raw_text_apercu
FROM evenement e
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
WHERE e.confidence < 0.6
ORDER BY e.confidence
LIMIT 50;

-- Complétude des champs (avec normalisation)
SELECT
    'date_evenement' AS champ,
    COUNT(*) AS rempli,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1) AS pct
FROM evenement WHERE date_evenement IS NOT NULL
UNION ALL
SELECT 'lieu_raw', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1)
FROM evenement WHERE lieu_raw IS NOT NULL
UNION ALL
SELECT 'lieu_ref_id (normalisé)', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1)
FROM evenement WHERE lieu_ref_id IS NOT NULL
UNION ALL
SELECT 'contenu (artiste/spectacle)', COUNT(DISTINCT evenement_id),
    ROUND(100.0 * COUNT(DISTINCT evenement_id) / (SELECT COUNT(*) FROM evenement), 1)
FROM contenu_evenement
UNION ALL
SELECT 'artiste_ref_id (normalisé)', COUNT(*),
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM contenu_evenement WHERE artiste IS NOT NULL), 1)
FROM contenu_evenement WHERE artiste_ref_id IS NOT NULL
UNION ALL
SELECT 'prix', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1)
FROM evenement WHERE prix_min IS NOT NULL OR gratuit = 1
UNION ALL
SELECT 'type_evenement', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1)
FROM evenement WHERE type_evenement IS NOT NULL;

-- =============================================================================
-- CORRECTIONS ET HISTORIQUE
-- =============================================================================

-- Corrections récentes
SELECT
    cl.created_at,
    e.bidul_numero,
    cl.champ,
    cl.ancienne_valeur,
    cl.nouvelle_valeur,
    cl.source
FROM correction_log cl
JOIN evenement e ON cl.evenement_id = e.id
ORDER BY cl.created_at DESC
LIMIT 50;

-- Corrections par champ
SELECT
    champ,
    COUNT(*) AS nb_corrections
FROM correction_log
GROUP BY champ
ORDER BY nb_corrections DESC;

-- Patterns de correction fréquents (pour améliorer l'extraction)
SELECT
    champ,
    ancienne_valeur,
    nouvelle_valeur,
    COUNT(*) AS nb_fois
FROM correction_log
GROUP BY champ, ancienne_valeur, nouvelle_valeur
HAVING COUNT(*) >= 2
ORDER BY nb_fois DESC
LIMIT 30;

-- =============================================================================
-- RECHERCHE FULL-TEXT
-- =============================================================================

-- Recherche dans le texte brut
SELECT
    e.bidul_numero,
    e.date_evenement,
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    SUBSTR(e.raw_text, 1, 200) AS raw_text_apercu
FROM evenement e
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
WHERE e.raw_text LIKE '%jazz%'  -- Modifier le terme recherché
ORDER BY e.date_evenement DESC
LIMIT 20;

-- Recherche d'artiste (inclut alias)
SELECT
    COALESCE(ar.nom, c.artiste) AS artiste,
    COUNT(DISTINCT e.id) AS nb_concerts,
    MIN(e.date_evenement) AS premier,
    MAX(e.date_evenement) AS dernier
FROM contenu_evenement c
JOIN evenement e ON c.evenement_id = e.id
LEFT JOIN artiste_ref ar ON c.artiste_ref_id = ar.id
WHERE c.artiste LIKE '%noir%'  -- Modifier le terme
   OR ar.nom LIKE '%noir%'
GROUP BY COALESCE(ar.nom, c.artiste)
ORDER BY nb_concerts DESC;

-- Recherche de spectacle
SELECT
    c.nom_spectacle,
    c.style,
    COUNT(DISTINCT e.id) AS nb_representations
FROM contenu_evenement c
JOIN evenement e ON c.evenement_id = e.id
WHERE c.nom_spectacle LIKE '%roi%'  -- Modifier le terme
GROUP BY c.nom_spectacle
ORDER BY nb_representations DESC;

-- =============================================================================
-- STATISTIQUES GLOBALES
-- =============================================================================

-- Vue d'ensemble de la base
SELECT
    (SELECT COUNT(*) FROM bidul) AS nb_biduls,
    (SELECT COUNT(*) FROM evenement) AS nb_evenements,
    (SELECT COUNT(DISTINCT artiste) FROM contenu_evenement WHERE artiste IS NOT NULL) AS nb_artistes_bruts,
    (SELECT COUNT(*) FROM artiste_ref WHERE actif = 1) AS nb_artistes_ref,
    (SELECT COUNT(DISTINCT nom_spectacle) FROM contenu_evenement WHERE nom_spectacle IS NOT NULL) AS nb_spectacles_uniques,
    (SELECT COUNT(*) FROM lieu_ref WHERE actif = 1) AS nb_lieux_ref,
    (SELECT COUNT(*) FROM lieu_alias) AS nb_lieux_alias,
    (SELECT COUNT(*) FROM artiste_alias) AS nb_artistes_alias,
    (SELECT COUNT(*) FROM ville_ref) AS nb_villes_ref,
    (SELECT MIN(date_evenement) FROM evenement) AS date_min,
    (SELECT MAX(date_evenement) FROM evenement) AS date_max;

-- Couverture des Biduls
SELECT
    b.numero,
    b.mois || '/' || b.annee AS periode,
    b.type_source,
    b.extraction_status,
    COUNT(e.id) AS nb_events,
    ROUND(AVG(e.confidence), 2) AS confidence_moy
FROM bidul b
LEFT JOIN evenement e ON b.numero = e.bidul_numero
GROUP BY b.numero
ORDER BY b.numero;

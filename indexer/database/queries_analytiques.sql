-- =============================================================================
-- Requêtes analytiques - Archives du Bidul
-- =============================================================================
-- Base: ~14500 événements extraits de 122 numéros (178-308)
-- Sources: CSV (données manuelles, confidence=1.0) et PDF (extraction auto)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- ARTISTES
-- -----------------------------------------------------------------------------

-- Top 20 artistes les plus programmés
SELECT
    value AS artiste,
    COUNT(*) AS nb_concerts,
    MIN(strftime('%Y', date_evenement)) AS premiere_annee,
    MAX(strftime('%Y', date_evenement)) AS derniere_annee
FROM evenement, json_each(evenement.artistes)
WHERE artistes IS NOT NULL
GROUP BY value
ORDER BY nb_concerts DESC
LIMIT 20;

-- Artistes par année
SELECT
    strftime('%Y', date_evenement) AS annee,
    value AS artiste,
    COUNT(*) AS nb_concerts
FROM evenement, json_each(evenement.artistes)
WHERE artistes IS NOT NULL AND date_evenement IS NOT NULL
GROUP BY annee, artiste
ORDER BY annee DESC, nb_concerts DESC;

-- Parcours d'un artiste spécifique (remplacer 'NOM_ARTISTE')
SELECT
    date_evenement,
    lieu_raw AS lieu,
    ville_raw AS ville,
    tarif_raw AS prix
FROM evenement, json_each(evenement.artistes)
WHERE value LIKE '%NOM_ARTISTE%'
ORDER BY date_evenement;

-- -----------------------------------------------------------------------------
-- QUE S'EST-IL PASSÉ TEL JOUR ?
-- -----------------------------------------------------------------------------

-- Événements d'une date précise (format: YYYY-MM-DD)
SELECT
    heure,
    COALESCE(
        (SELECT GROUP_CONCAT(value, ' + ') FROM json_each(artistes)),
        nom,
        'Événement'
    ) AS qui,
    lieu_raw AS lieu,
    ville_raw AS ville,
    type_evenement AS type,
    tarif_raw AS prix
FROM evenement
WHERE date_evenement = '2023-05-14'  -- Modifier cette date
ORDER BY heure;

-- Événements d'un mois (ex: mai 2023)
SELECT
    date_evenement,
    heure,
    COALESCE(
        (SELECT GROUP_CONCAT(value, ' + ') FROM json_each(artistes)),
        nom
    ) AS qui,
    lieu_raw AS lieu,
    type_evenement
FROM evenement
WHERE strftime('%Y-%m', date_evenement) = '2023-05'  -- Modifier ce mois
ORDER BY date_evenement, heure;

-- Historique d'un jour de l'année (ex: tous les 14 mai)
SELECT
    strftime('%Y', date_evenement) AS annee,
    COALESCE(
        (SELECT GROUP_CONCAT(value, ' + ') FROM json_each(artistes)),
        nom
    ) AS qui,
    lieu_raw AS lieu
FROM evenement
WHERE strftime('%m-%d', date_evenement) = '05-14'  -- Modifier jour-mois
ORDER BY annee DESC;

-- -----------------------------------------------------------------------------
-- PRIX ET TARIFS
-- -----------------------------------------------------------------------------

-- Prix moyen par type d'événement
SELECT
    type_evenement,
    COUNT(*) AS nb_events,
    ROUND(AVG(prix_min), 2) AS prix_min_moyen,
    ROUND(AVG(prix_max), 2) AS prix_max_moyen,
    ROUND(AVG((COALESCE(prix_min, 0) + COALESCE(prix_max, 0)) / 2), 2) AS prix_moyen,
    SUM(CASE WHEN gratuit = 1 THEN 1 ELSE 0 END) AS nb_gratuits,
    ROUND(100.0 * SUM(CASE WHEN gratuit = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_gratuit
FROM evenement
WHERE type_evenement IS NOT NULL
GROUP BY type_evenement
ORDER BY nb_events DESC;

-- Évolution du prix moyen par année
SELECT
    strftime('%Y', date_evenement) AS annee,
    COUNT(*) AS nb_events,
    ROUND(AVG(prix_min), 2) AS prix_min_moyen,
    ROUND(AVG(prix_max), 2) AS prix_max_moyen,
    ROUND(100.0 * SUM(CASE WHEN gratuit = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_gratuit
FROM evenement
WHERE date_evenement IS NOT NULL AND (prix_min IS NOT NULL OR gratuit = 1)
GROUP BY annee
ORDER BY annee;

-- Événements les plus chers
SELECT
    date_evenement,
    COALESCE(
        (SELECT GROUP_CONCAT(value, ' + ') FROM json_each(artistes)),
        nom
    ) AS qui,
    lieu_raw AS lieu,
    tarif_raw,
    prix_max
FROM evenement
WHERE prix_max IS NOT NULL
ORDER BY prix_max DESC
LIMIT 20;

-- -----------------------------------------------------------------------------
-- LIEUX
-- -----------------------------------------------------------------------------

-- Top 20 lieux les plus actifs
SELECT
    COALESCE(lieu_raw, 'Inconnu') AS lieu,
    ville_raw AS ville,
    COUNT(*) AS nb_events,
    MIN(strftime('%Y', date_evenement)) AS depuis,
    MAX(strftime('%Y', date_evenement)) AS jusqua
FROM evenement
WHERE lieu_raw IS NOT NULL
GROUP BY lieu_raw, ville_raw
ORDER BY nb_events DESC
LIMIT 20;

-- Programmation d'un lieu spécifique
SELECT
    date_evenement,
    heure,
    COALESCE(
        (SELECT GROUP_CONCAT(value, ' + ') FROM json_each(artistes)),
        nom
    ) AS qui,
    type_evenement,
    tarif_raw
FROM evenement
WHERE lieu_raw LIKE '%Oasis%'  -- Modifier le nom du lieu
ORDER BY date_evenement DESC
LIMIT 50;

-- Répartition géographique (par ville)
SELECT
    COALESCE(ville_raw, 'Le Mans') AS ville,
    COUNT(*) AS nb_events,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1) AS pct
FROM evenement
GROUP BY ville_raw
ORDER BY nb_events DESC
LIMIT 20;

-- -----------------------------------------------------------------------------
-- TEMPORALITÉ
-- -----------------------------------------------------------------------------

-- Événements par année
SELECT
    strftime('%Y', date_evenement) AS annee,
    COUNT(*) AS nb_events
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
ORDER BY strftime('%w', date_evenement);

-- -----------------------------------------------------------------------------
-- GENRES MUSICAUX
-- -----------------------------------------------------------------------------

-- Top genres musicaux
SELECT
    value AS genre,
    COUNT(*) AS nb_events
FROM evenement, json_each(evenement.genres_raw)
WHERE genres_raw IS NOT NULL
GROUP BY value
ORDER BY nb_events DESC
LIMIT 30;

-- Artistes par genre
SELECT
    g.value AS genre,
    a.value AS artiste,
    COUNT(*) AS nb_events
FROM evenement e,
     json_each(e.genres_raw) g,
     json_each(e.artistes) a
WHERE e.genres_raw IS NOT NULL AND e.artistes IS NOT NULL
GROUP BY g.value, a.value
HAVING COUNT(*) >= 2
ORDER BY genre, nb_events DESC;

-- -----------------------------------------------------------------------------
-- QUALITÉ DES DONNÉES
-- -----------------------------------------------------------------------------

-- Répartition par source
SELECT
    source,
    COUNT(*) AS nb_events,
    ROUND(AVG(confidence), 2) AS confidence_moyenne,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1) AS pct
FROM evenement
GROUP BY source;

-- Événements à faible confidence (à vérifier)
SELECT
    bidul_numero,
    date_evenement,
    raw_text,
    confidence
FROM evenement
WHERE confidence < 0.6
ORDER BY confidence
LIMIT 50;

-- Complétude des champs
SELECT
    'date_evenement' AS champ,
    COUNT(*) AS rempli,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1) AS pct
FROM evenement WHERE date_evenement IS NOT NULL
UNION ALL
SELECT 'lieu_raw', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1)
FROM evenement WHERE lieu_raw IS NOT NULL
UNION ALL
SELECT 'artistes', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1)
FROM evenement WHERE artistes IS NOT NULL
UNION ALL
SELECT 'prix', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1)
FROM evenement WHERE prix_min IS NOT NULL OR gratuit = 1
UNION ALL
SELECT 'type_evenement', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM evenement), 1)
FROM evenement WHERE type_evenement IS NOT NULL;

-- -----------------------------------------------------------------------------
-- RECHERCHE FULL-TEXT
-- -----------------------------------------------------------------------------

-- Recherche dans le texte brut
SELECT
    bidul_numero,
    date_evenement,
    lieu_raw,
    raw_text
FROM evenement
WHERE raw_text LIKE '%jazz%'  -- Modifier le terme recherché
ORDER BY date_evenement DESC
LIMIT 20;

-- Recherche d'artiste (insensible à la casse)
SELECT DISTINCT
    value AS artiste,
    COUNT(*) AS nb_concerts
FROM evenement, json_each(evenement.artistes)
WHERE LOWER(value) LIKE '%noir%'  -- Modifier le terme
GROUP BY value
ORDER BY nb_concerts DESC;

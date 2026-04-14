-- =============================================================================
-- Base de données Archives du Bidul - Schema V3
-- =============================================================================
-- Changements V3:
--   - Suppression des colonnes JSON redondantes de evenement:
--     artistes, spectacles, genres_raw, style
--   - Ces données sont dans contenu_evenement (source de vérité)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Table: bidul
-- Un exemplaire du fanzine
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidul (
    numero INTEGER PRIMARY KEY,              -- Numéro = clé naturelle
    mois INTEGER CHECK (mois BETWEEN 1 AND 12),
    annee INTEGER CHECK (annee BETWEEN 1997 AND 2030),
    pdf_filename TEXT,                       -- "2018-02 Bidul 230.pdf"
    type_source TEXT CHECK(type_source IN ('scan', 'texte')),
    source TEXT CHECK(source IN ('csv', 'xlsx', 'pdf', 'scan')),  -- Source d'extraction
    raw_text TEXT,                           -- Texte brut extrait du PDF (OCR ou texte natif)
    config_extraction TEXT,                  -- JSON snapshot config utilisée
    extraction_status TEXT DEFAULT 'pending',
    extraction_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Table: lieu_ref
-- Référentiel des lieux (pour normalisation)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lieu_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE NOT NULL,
    ville TEXT DEFAULT 'Le Mans',
    actif BOOLEAN DEFAULT TRUE
);

-- -----------------------------------------------------------------------------
-- Table: ville_ref
-- Référentiel des villes (pour normalisation)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ville_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE NOT NULL
);

-- -----------------------------------------------------------------------------
-- Table: artiste_ref
-- Référentiel des artistes (pour normalisation)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artiste_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE NOT NULL,
    aliases TEXT,                            -- JSON array d'aliases
    actif BOOLEAN DEFAULT TRUE
);

-- -----------------------------------------------------------------------------
-- Table: evenement
-- Entité centrale - un événement extrait
-- V3: Sans les colonnes JSON redondantes (artistes, spectacles, genres_raw, style)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evenement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bidul_numero INTEGER NOT NULL REFERENCES bidul(numero),

    -- Texte brut (toujours conservé)
    raw_text TEXT NOT NULL,
    raw_text_clean TEXT,                     -- raw_text sans balises de formatage

    -- Champs extraits (texte libre, nettoyés)
    nom TEXT,                                -- Nom événement si présent
    date_evenement DATE,
    heure TEXT,                              -- "20h30" - format brut

    -- Lieu/Ville : texte brut extrait + FK optionnelle après normalisation
    lieu_raw TEXT,
    lieu_ref_id INTEGER REFERENCES lieu_ref(id),
    ville_raw TEXT,
    ville_ref_id INTEGER REFERENCES ville_ref(id),

    -- Prix
    tarif_raw TEXT,                          -- "5€ / 8€", "gratuit"
    prix_min REAL,
    prix_max REAL,
    gratuit BOOLEAN DEFAULT FALSE,

    -- Type déduit (concert, theatre, expo...) - texte libre
    type_evenement TEXT,

    -- Genre de l'événement (concert, spectacle vivant, etc.)
    genre_evenement TEXT,

    -- Qualité extraction
    confidence REAL DEFAULT 0.5,
    needs_review BOOLEAN DEFAULT FALSE,
    verified BOOLEAN DEFAULT FALSE,
    verified_by TEXT,
    verified_at TIMESTAMP,

    -- Statut de révision
    review_status TEXT DEFAULT 'pending',
    review_notes TEXT,

    -- Source
    source TEXT DEFAULT 'pdf',

    -- Événement hors département (région)
    is_regional BOOLEAN DEFAULT FALSE,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evt_date ON evenement(date_evenement);
CREATE INDEX IF NOT EXISTS idx_evt_bidul ON evenement(bidul_numero);
CREATE INDEX IF NOT EXISTS idx_evt_lieu ON evenement(lieu_ref_id);
CREATE INDEX IF NOT EXISTS idx_evt_ville ON evenement(ville_ref_id);
CREATE INDEX IF NOT EXISTS idx_evenement_review_status ON evenement(review_status);
CREATE INDEX IF NOT EXISTS idx_evenement_verified ON evenement(verified);
CREATE INDEX IF NOT EXISTS idx_evenement_is_regional ON evenement(is_regional);

-- -----------------------------------------------------------------------------
-- Table: contenu_evenement
-- Artistes et spectacles d'un événement (source de vérité V3)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contenu_evenement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evenement_id INTEGER NOT NULL REFERENCES evenement(id) ON DELETE CASCADE,
    artiste TEXT,                            -- Nom de l'artiste
    artiste_ref_id INTEGER REFERENCES artiste_ref(id),
    nom_spectacle TEXT,                      -- Nom du spectacle
    style TEXT,                              -- Genre musical (rock, jazz, etc.)
    ordre INTEGER DEFAULT 1,                 -- Ordre d'affichage
    UNIQUE(evenement_id, artiste, nom_spectacle)
);

CREATE INDEX IF NOT EXISTS idx_contenu_evenement ON contenu_evenement(evenement_id);
CREATE INDEX IF NOT EXISTS idx_contenu_artiste ON contenu_evenement(artiste);

-- =============================================================================
-- VUES POUR REQUÊTES ANALYTIQUES
-- =============================================================================

-- Vue : événements avec infos complètes (sans colonnes JSON)
CREATE VIEW IF NOT EXISTS v_evenements AS
SELECT
    e.id,
    e.bidul_numero,
    e.raw_text,
    e.raw_text_clean,
    e.nom,
    e.date_evenement,
    e.heure,
    e.lieu_raw,
    e.lieu_ref_id,
    e.ville_raw,
    e.ville_ref_id,
    e.tarif_raw,
    e.prix_min,
    e.prix_max,
    e.gratuit,
    e.type_evenement,
    e.genre_evenement,
    e.confidence,
    e.needs_review,
    e.verified,
    e.review_status,
    e.source,
    e.created_at,
    b.mois AS bidul_mois,
    b.annee AS bidul_annee,
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    COALESCE(vr.nom, e.ville_raw) AS ville
FROM evenement e
JOIN bidul b ON e.bidul_numero = b.numero
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id;

-- Vue : événements avec contenu agrégé
CREATE VIEW IF NOT EXISTS v_evenements_complets AS
SELECT
    e.id,
    e.bidul_numero,
    e.date_evenement,
    e.heure,
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    COALESCE(vr.nom, e.ville_raw) AS ville,
    e.tarif_raw,
    e.gratuit,
    e.type_evenement,
    e.confidence,
    GROUP_CONCAT(DISTINCT ce.artiste) AS artistes,
    GROUP_CONCAT(DISTINCT ce.nom_spectacle) AS spectacles,
    GROUP_CONCAT(DISTINCT ce.style) AS styles
FROM evenement e
JOIN bidul b ON e.bidul_numero = b.numero
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id
LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
GROUP BY e.id;

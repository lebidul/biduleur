-- =============================================================================
-- Base de données Archives du Bidul - Version simplifiée
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
    source TEXT CHECK(source IN ('csv', 'pdf', 'scan')),  -- Source d'extraction
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
    actif BOOLEAN DEFAULT TRUE,
    -- Coordonnées géographiques (compatibles PostGIS)
    latitude REAL,                           -- WGS84 latitude (ex: 47.9960)
    longitude REAL,                          -- WGS84 longitude (ex: 0.1906)
    geo_source TEXT,                         -- Source des coordonnées (nominatim, google, manual)
    geo_precision TEXT                       -- Précision (exact, street, city, approximate)
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
-- Table: evenement
-- Entité centrale - un événement extrait
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evenement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bidul_numero INTEGER NOT NULL REFERENCES bidul(numero),

    -- Texte brut (toujours conservé)
    raw_text TEXT NOT NULL,

    -- Champs extraits (texte libre, nettoyés)
    nom TEXT,                                -- Nom événement si présent
    date_evenement DATE,
    heure TEXT,                              -- "20h30" - format brut

    -- Lieu/Ville : texte brut extrait + FK optionnelle après normalisation
    lieu_raw TEXT,
    lieu_ref_id INTEGER REFERENCES lieu_ref(id),
    ville_raw TEXT,
    ville_ref_id INTEGER REFERENCES ville_ref(id),

    -- Artistes : JSON array ["ARTISTE1", "ARTISTE2"]
    artistes TEXT,

    -- Spectacle(s) : JSON array ou texte si un seul
    spectacles TEXT,

    -- Genres extraits (texte entre parenthèses) : JSON array
    genres_raw TEXT,

    -- Genre de l'événement (concert, spectacle vivant, etc.)
    genre_evenement TEXT,

    -- Prix
    tarif_raw TEXT,                          -- "5€ / 8€", "gratuit"
    prix_min REAL,
    prix_max REAL,
    gratuit BOOLEAN DEFAULT FALSE,

    -- Type déduit (concert, theatre, expo...) - texte libre
    type_evenement TEXT,

    -- Qualité extraction
    confidence REAL DEFAULT 0.5,
    needs_review BOOLEAN DEFAULT FALSE,
    verified BOOLEAN DEFAULT FALSE,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evt_date ON evenement(date_evenement);
CREATE INDEX IF NOT EXISTS idx_evt_bidul ON evenement(bidul_numero);
CREATE INDEX IF NOT EXISTS idx_evt_lieu ON evenement(lieu_ref_id);
CREATE INDEX IF NOT EXISTS idx_evt_ville ON evenement(ville_ref_id);
CREATE INDEX IF NOT EXISTS idx_evt_annee ON evenement(strftime('%Y', date_evenement));

-- =============================================================================
-- VUES POUR REQUÊTES ANALYTIQUES
-- =============================================================================

-- Vue : événements avec infos complètes
CREATE VIEW IF NOT EXISTS v_evenements AS
SELECT
    e.*,
    b.mois AS bidul_mois,
    b.annee AS bidul_annee,
    b.source AS bidul_source,
    COALESCE(lr.nom, e.lieu_raw) AS lieu,
    COALESCE(vr.nom, e.ville_raw) AS ville
FROM evenement e
JOIN bidul b ON e.bidul_numero = b.numero
LEFT JOIN lieu_ref lr ON e.lieu_ref_id = lr.id
LEFT JOIN ville_ref vr ON e.ville_ref_id = vr.id;

-- PESSOA Suite — SQLite schema
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Canonical property (deduped across sources)
CREATE TABLE IF NOT EXISTS properties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_hash  TEXT UNIQUE NOT NULL,          -- hash(norm_address + price_bucket + m2)
    address         TEXT,
    freguesia       TEXT,
    typology        TEXT,                          -- T0/T1/T2/T3
    area_m2         INTEGER,
    price_eur       INTEGER,
    price_per_m2    REAL,
    built_year      INTEGER,
    energy_cert     TEXT,
    floor           TEXT,
    condominio_eur  INTEGER,
    description     TEXT,
    photo_url       TEXT,
    first_seen      TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen       TEXT DEFAULT CURRENT_TIMESTAMP,
    status          TEXT DEFAULT 'active',         -- active/closed/removed
    raw_json        TEXT                           -- merged snapshot
);

-- Per-source listing occurrences (one property → multiple listings possible)
CREATE TABLE IF NOT EXISTS listings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,                     -- idealista/imovirtual/casa_sapo/supercasa/custojusto
    external_id TEXT,                              -- site-specific listing ID
    url         TEXT NOT NULL,
    asking_price INTEGER,
    first_seen  TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen   TEXT DEFAULT CURRENT_TIMESTAMP,
    days_on_market INTEGER,
    UNIQUE(source, url)
);
CREATE INDEX IF NOT EXISTS idx_listings_property ON listings(property_id);
CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);

-- PESSOA scoring runs
CREATE TABLE IF NOT EXISTS scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    scored_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    score_a     REAL,  -- Financial
    score_b     REAL,  -- Structural
    score_c     REAL,  -- Legal
    score_d     REAL,  -- Location
    score_e     REAL,  -- Risk-adjusted
    composite   REAL,
    verdict     TEXT,  -- strong_buy / buy / hold / pass / strong_pass
    summary_md  TEXT,
    summary_html TEXT,
    agent_a_json TEXT,
    agent_b_json TEXT,
    agent_c_json TEXT,
    agent_d_json TEXT,
    agent_e_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_scores_property ON scores(property_id);
CREATE INDEX IF NOT EXISTS idx_scores_composite ON scores(composite DESC);

-- Scan audit trail
CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at  TEXT,
    scan_type    TEXT,                             -- initial / weekly
    raw_fetched  INTEGER,
    new_properties INTEGER,
    scored_count INTEGER,
    status       TEXT,                             -- ok / partial / failed
    notes        TEXT
);

-- View: latest score per property
CREATE VIEW IF NOT EXISTS v_latest_scores AS
SELECT s.*
FROM scores s
INNER JOIN (
    SELECT property_id, MAX(scored_at) AS max_ts
    FROM scores GROUP BY property_id
) m ON s.property_id = m.property_id AND s.scored_at = m.max_ts;

-- View: top properties with all info
CREATE VIEW IF NOT EXISTS v_top_properties AS
SELECT
    p.*,
    s.score_a, s.score_b, s.score_c, s.score_d, s.score_e,
    s.composite, s.verdict, s.scored_at,
    (SELECT COUNT(*) FROM listings l WHERE l.property_id = p.id) AS source_count,
    (SELECT GROUP_CONCAT(source, ',') FROM listings l WHERE l.property_id = p.id) AS sources_csv
FROM properties p
LEFT JOIN v_latest_scores s ON s.property_id = p.id
WHERE p.status = 'active';

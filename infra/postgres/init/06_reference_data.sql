-- ============================================================================
-- 06_reference_data.sql
-- Reference dimension tables: operators and Congolese departments.
-- These are seeded with canonical data, not loaded from bronze.
-- They live in silver because they are validated, curated reference data.
--
-- Population data: 2023 census figures
-- Administrative divisions reflect the 2023 reform creating 15 departments.
-- ============================================================================

CREATE TABLE silver.operators (
    operator_id             VARCHAR(10)     PRIMARY KEY,
    operator_name           VARCHAR(100)    NOT NULL,
    operator_type           VARCHAR(20)     NOT NULL
                            CHECK (operator_type IN ('mobile', 'fixed', 'isp', 'postal', 'mvno')),
    license_status          VARCHAR(20)     NOT NULL DEFAULT 'active'
                            CHECK (license_status IN ('active', 'suspended', 'revoked', 'pending')),
    license_issued_date     DATE,
    is_state_owned          BOOLEAN         NOT NULL DEFAULT FALSE,
    notes                   TEXT,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE silver.operators IS 'Canonical operator reference data. Seeded manually, updated as licensing changes.';

INSERT INTO silver.operators (operator_id, operator_name, operator_type, license_issued_date, is_state_owned) VALUES
    ('OPA01', 'OperatorA',           'mobile',  '2005-04-15', FALSE),
    ('OPA02', 'OperatorB',           'mobile',  '2007-09-22', FALSE),
    ('OPA03', 'OperatorC',           'mobile',  '2001-01-01', TRUE),
    ('OPA04', 'OperatorC Fixed',     'fixed',   '2001-01-01', TRUE),
    ('OPA05', 'ISP-Avenir',          'isp',     '2012-06-10', FALSE),
    ('OPA06', 'ISP-GVA',             'isp',     '2014-02-28', FALSE),
    ('OPA07', 'ISP-Yoomee',          'isp',     '2016-11-03', FALSE),
    ('OPA08', 'ISP-MicroCom',        'isp',     '2018-08-17', FALSE);

CREATE TABLE silver.regions (
    region_code             VARCHAR(8)      PRIMARY KEY,
    region_name             VARCHAR(50)     NOT NULL,
    region_capital          VARCHAR(50)     NOT NULL,
    population_2023         INTEGER         NOT NULL,
    area_km2                INTEGER         NOT NULL,
    density_per_km2         NUMERIC(10, 2)  NOT NULL,
    zone                    VARCHAR(15)     NOT NULL
                            CHECK (zone IN ('North', 'South', 'Southeast', 'Southwest')),
    is_urban_concentration  BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE silver.regions IS 'Canonical reference data for the 15 administrative departments of Congo (post-2023 reform).';
COMMENT ON COLUMN silver.regions.zone IS 'Geographic zone — proxy for the historical North/South digital divide central to ARPCE policy.';
COMMENT ON COLUMN silver.regions.is_urban_concentration IS 'True for the two cities with density >1000/km2 (Brazzaville and Pointe-Noire) — about 60% of population, dominant share of telecoms activity.';

INSERT INTO silver.regions (region_code, region_name, region_capital, population_2023, area_km2, density_per_km2, zone, is_urban_concentration) VALUES
    -- North zone
    ('SAN', 'Sangha',           'Ouésso',       209701,  55800, 3.80,    'North',     FALSE),
    ('LIK', 'Likouala',         'Impfondo',     325429,  61993, 5.24,    'North',     FALSE),
    ('COB', 'Congo-Oubangui',   'Mossaka',      124100,  25536, 4.86,    'North',     FALSE),
    ('CUV', 'Cuvette',          'Owando',       222640,  26765, 8.30,    'North',     FALSE),
    ('CUO', 'Cuvette-Ouest',    'Ewo',          119328,  26600, 4.50,    'North',     FALSE),
    ('NKA', 'Nkéni-Alima',      'Gamboma',      154230,  17406, 8.86,    'North',     FALSE),
    ('PLA', 'Plateaux',         'Djambala',     129191,  20994, 6.15,    'North',     FALSE),
    -- Southeast zone
    ('DJL', 'Djoué-Léfini',     'Odziba',       174761,  23560, 7.41,    'Southeast', FALSE),
    ('BZV', 'Brazzaville',      'Brazzaville', 2145783,    588, 3649.29, 'Southeast', TRUE),
    ('POO', 'Pool',             'Kinkala',      219771,  10395, 21.14,   'Southeast', FALSE),
    -- South zone
    ('BOU', 'Bouenza',          'Madingou',     363850,  12265, 29.67,   'South',     FALSE),
    ('LEK', 'Lékoumou',         'Sibiti',       100559,  20950, 4.80,    'South',     FALSE),
    ('NIA', 'Niari',            'Dolisie',      334863,  25942, 12.91,   'South',     FALSE),
    -- Southwest zone
    ('KOU', 'Kouilou',          'Loango',       119162,  13103,  9.09,   'Southwest', FALSE),
    ('PNR', 'Pointe-Noire',     'Pointe-Noire',1398812,    288, 4857.00, 'Southwest', TRUE);
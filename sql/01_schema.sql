-- =====================================================================
-- 01_schema.sql  |  Star schema for CMS Medicare Inpatient (DY2023)
-- Portable ANSI SQL: runs on SQLite (used by python/build_database.py)
-- and on MySQL 8+ / PostgreSQL with trivial type changes.
-- Grain of the fact table: one row per hospital x MS-DRG (>=11 discharges).
-- =====================================================================

DROP TABLE IF EXISTS fact_discharge;
DROP TABLE IF EXISTS dim_provider;
DROP TABLE IF EXISTS dim_drg;
DROP TABLE IF EXISTS dim_geography;
DROP TABLE IF EXISTS dim_state;

CREATE TABLE dim_state (
    state_code     CHAR(2)      PRIMARY KEY,
    state_name     VARCHAR(40)  NOT NULL,
    census_region  VARCHAR(12)  NOT NULL        -- Northeast / Midwest / South / West
);

-- RUCA = USDA Rural-Urban Commuting Area code of the hospital's ZIP
CREATE TABLE dim_geography (
    ruca_code      DECIMAL(4,1) PRIMARY KEY,    -- 1-10 primary, x.1-x.3 secondary, 99 = unclassified
    ruca_desc      VARCHAR(200),
    setting        VARCHAR(20)  NOT NULL        -- Metropolitan / Micropolitan / Small town / Rural
);

-- CCN is stored as 6-character TEXT: leading zeros carry the state code
CREATE TABLE dim_provider (
    provider_id    CHAR(6)      PRIMARY KEY,
    provider_name  VARCHAR(120) NOT NULL,
    city           VARCHAR(60),
    street         VARCHAR(120),
    zip5           CHAR(5),
    state_code     CHAR(2)      NOT NULL REFERENCES dim_state(state_code),
    ruca_code      DECIMAL(4,1) REFERENCES dim_geography(ruca_code)
);

CREATE TABLE dim_drg (
    drg_code         CHAR(3)      PRIMARY KEY,
    drg_description  VARCHAR(120) NOT NULL,
    drg_family       VARCHAR(120),              -- description with the severity suffix removed
    severity_tier    INTEGER                    -- 0 none, 1 w/o MCC, 2 CC, 3 MCC (NULL = not a tiered family)
);

CREATE TABLE fact_discharge (
    provider_id           CHAR(6)       NOT NULL REFERENCES dim_provider(provider_id),
    drg_code              CHAR(3)       NOT NULL REFERENCES dim_drg(drg_code),
    total_discharges      INTEGER       NOT NULL CHECK (total_discharges > 0),
    avg_submitted_charge  DECIMAL(14,2) NOT NULL,   -- hospital list price ("chargemaster") per discharge
    avg_total_payment     DECIMAL(14,2) NOT NULL,   -- all payers incl. patient deductible/coinsurance
    avg_medicare_payment  DECIMAL(14,2) NOT NULL,   -- Medicare's share only
    PRIMARY KEY (provider_id, drg_code)
);

CREATE INDEX ix_fact_drg      ON fact_discharge (drg_code);
CREATE INDEX ix_provider_state ON dim_provider (state_code);

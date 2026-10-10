-- =====================================================================
-- 04_severity_mix.sql  |  Documentation / severity-capture screen
--
-- Question: Which hospitals bill a LESS severe mix of cases than comparable
-- peers, and what is the payment effect of that difference?
--
-- Method (all inside one view, readable top to bottom):
--   1. Keep only DRGs that belong to a severity-tiered family
--      (e.g. "SEPTICEMIA ... WITH MCC" / "WITHOUT MCC").
--   2. Peer group = Metropolitan vs Non-metropolitan hospitals.
--   3. For each peer group x family x tier, compute the peer tier mix
--      (share of the family's discharges landing in each tier).
--   4. Value every discharge at the NATIONAL average payment of its DRG, so
--      only the *mix* differs - not wage index, teaching status or DSH.
--         actual_value   = SUM( discharges_in_tier x national payment of tier )
--         expected_value = family discharges x SUM( peer tier share x national payment )
--   5. Shortfall = expected - actual.  Positive = hospital's mix is lighter than peers'.
--
-- This is a SCREEN for clinical-documentation-integrity (CDI) review, not a
-- forecast: lighter mixes can be legitimate (e.g. complex cases transferred out).
-- Depends on: 01_schema.sql, 02_views.sql
-- =====================================================================

DROP VIEW IF EXISTS v_provider_family_mix;
CREATE VIEW v_provider_family_mix AS
WITH tiered AS (                                   -- (1) tiered DRGs only, with peer group
    SELECT  f.provider_id,
            CASE WHEN g.setting = 'Metropolitan' THEN 'Metropolitan' ELSE 'Non-metropolitan' END AS peer_group,
            d.drg_family,
            d.severity_tier,
            f.total_discharges,
            b.nat_payment_per_discharge
    FROM fact_discharge f
    JOIN dim_drg d              ON d.drg_code = f.drg_code AND d.severity_tier IS NOT NULL
    JOIN v_drg_benchmark b      ON b.drg_code = f.drg_code
    JOIN dim_provider p         ON p.provider_id = f.provider_id
    LEFT JOIN dim_geography g   ON g.ruca_code = p.ruca_code
),
tier_nat AS (                                      -- (3) peer mix per family & tier (+ national payment of the tier)
    SELECT  peer_group, drg_family, severity_tier,
            SUM(total_discharges) AS tier_discharges,
            SUM(total_discharges * nat_payment_per_discharge) / SUM(total_discharges) AS tier_payment
    FROM tiered
    GROUP BY peer_group, drg_family, severity_tier
),
fam_nat AS (
    SELECT  peer_group, drg_family, SUM(tier_discharges) AS fam_discharges
    FROM tier_nat
    GROUP BY peer_group, drg_family
),
peer_value AS (                                    -- expected payment per discharge of a family at the peer mix
    SELECT  t.peer_group, t.drg_family,
            SUM(t.tier_discharges * 1.0 / n.fam_discharges * t.tier_payment) AS expected_pay_per_discharge,
            -- share of the family's discharges coded in the highest tier
            SUM(CASE WHEN t.severity_tier = (SELECT MAX(severity_tier) FROM tier_nat x
                                             WHERE x.peer_group = t.peer_group AND x.drg_family = t.drg_family)
                     THEN t.tier_discharges * 1.0 / n.fam_discharges ELSE 0 END) AS peer_top_tier_share
    FROM tier_nat t
    JOIN fam_nat  n ON n.peer_group = t.peer_group AND n.drg_family = t.drg_family
    GROUP BY t.peer_group, t.drg_family
),
prov_fam AS (                                      -- (4) hospital x family actual vs expected
    SELECT  t.provider_id, t.peer_group, t.drg_family,
            SUM(t.total_discharges)                                   AS fam_discharges,
            SUM(t.total_discharges * t.nat_payment_per_discharge)     AS actual_value,
            SUM(CASE WHEN t.severity_tier = m.max_tier THEN t.total_discharges ELSE 0 END) AS top_tier_discharges
    FROM tiered t
    JOIN (SELECT drg_family, MAX(severity_tier) AS max_tier FROM tiered GROUP BY drg_family) m
         ON m.drg_family = t.drg_family
    GROUP BY t.provider_id, t.peer_group, t.drg_family
)
SELECT  pf.provider_id,
        pf.peer_group,
        pf.drg_family,
        pf.fam_discharges,
        pf.top_tier_discharges,
        pv.peer_top_tier_share,
        pf.actual_value,
        pf.fam_discharges * pv.expected_pay_per_discharge AS expected_value
FROM prov_fam pf
JOIN peer_value pv ON pv.peer_group = pf.peer_group AND pv.drg_family = pf.drg_family;

-- (5) Hospital-level screen -------------------------------------------------
DROP VIEW IF EXISTS v_provider_severity_screen;
CREATE VIEW v_provider_severity_screen AS
SELECT  m.provider_id,
        k.provider_name,
        k.state_code,
        k.setting,
        m.peer_group,
        COUNT(*)                                             AS tiered_families,
        SUM(m.fam_discharges)                                AS tiered_discharges,
        SUM(m.top_tier_discharges) * 1.0 / SUM(m.fam_discharges)             AS top_tier_share,
        SUM(m.fam_discharges * m.peer_top_tier_share) / SUM(m.fam_discharges) AS peer_expected_top_tier_share,
        SUM(m.actual_value)                                  AS actual_value,
        SUM(m.expected_value)                                AS expected_value,
        SUM(m.expected_value) - SUM(m.actual_value)          AS severity_shortfall,   -- $ ; >0 = lighter mix than peers
        (SUM(m.expected_value) - SUM(m.actual_value)) / SUM(m.expected_value) AS shortfall_pct
FROM v_provider_family_mix m
JOIN v_provider_kpis k USING (provider_id)
GROUP BY m.provider_id, k.provider_name, k.state_code, k.setting, m.peer_group
HAVING SUM(m.fam_discharges) >= 300 AND COUNT(*) >= 10;   -- enough volume to be meaningful

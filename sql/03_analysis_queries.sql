-- =====================================================================
-- 03_analysis_queries.sql  |  Business-question queries
-- Each block starts with "-- name: <id>" so the notebook can run them by name.
-- Uses: joins, CTEs, window functions (RANK, NTILE, ROW_NUMBER, running SUM).
-- Depends on: 01_schema.sql, 02_views.sql, 04_severity_mix.sql
-- =====================================================================

-- name: q1_headline_kpis
-- Q1. How big is the charge-to-payment gap, and how much of Medicare's payment is Medicare's?
SELECT  COUNT(DISTINCT provider_id)                         AS hospitals,
        COUNT(DISTINCT drg_code)                            AS drgs,
        SUM(total_discharges)                               AS discharges,
        SUM(total_charges)                                  AS total_charges,
        SUM(total_payment)                                  AS total_payment,
        SUM(total_medicare_payment)                         AS medicare_payment,
        SUM(charge_gap)                                     AS charge_gap,
        SUM(total_payment)  / SUM(total_charges)            AS payment_to_charge_ratio,
        SUM(total_medicare_payment) / SUM(total_payment)    AS medicare_share_of_payment,
        SUM(total_payment)  / SUM(total_discharges)         AS payment_per_discharge,
        SUM(payment_exceeds_charge)                         AS rows_payment_exceeds_charge
FROM v_fact;

-- name: q2_provider_concentration
-- Q2. How concentrated is the gap? Running share with a tie-safe window frame.
WITH ranked AS (
    SELECT  provider_id, provider_name, state_code, charge_gap, discharges, charge_index,
            RANK()      OVER (ORDER BY charge_gap DESC)                                   AS gap_rank,
            SUM(charge_gap) OVER (ORDER BY charge_gap DESC, provider_id
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              * 1.0 / SUM(charge_gap) OVER ()                                             AS cum_share
    FROM v_provider_kpis
)
SELECT  gap_rank, provider_name, state_code, charge_gap, charge_index, ROUND(cum_share, 4) AS cum_share
FROM ranked
WHERE gap_rank <= 20
ORDER BY gap_rank;

-- name: q2b_concentration_thresholds
-- Q2b. How many hospitals / DRGs make up 25%, 50% and 80% of the gap?
WITH p AS (
    SELECT charge_gap,
           SUM(charge_gap) OVER (ORDER BY charge_gap DESC, provider_id) * 1.0 / SUM(charge_gap) OVER () AS cum_share,
           COUNT(*) OVER () AS n
    FROM v_provider_kpis
),
d AS (
    SELECT charge_gap,
           SUM(charge_gap) OVER (ORDER BY charge_gap DESC, drg_code) * 1.0 / SUM(charge_gap) OVER () AS cum_share,
           COUNT(*) OVER () AS n
    FROM v_drg_kpis
)
SELECT 'hospitals' AS entity, MAX(n) AS total,
       SUM(cum_share <= 0.25) AS to_25pct, SUM(cum_share <= 0.50) AS to_50pct, SUM(cum_share <= 0.80) AS to_80pct
FROM p
UNION ALL
SELECT 'DRGs', MAX(n), SUM(cum_share <= 0.25), SUM(cum_share <= 0.50), SUM(cum_share <= 0.80)
FROM d;

-- name: q3_charge_index_deciles
-- Q3. Do high-charging hospitals get paid more?  NTILE(10) on the case-mix-adjusted charge index.
WITH tiles AS (
    SELECT *, NTILE(10) OVER (ORDER BY charge_index) AS charge_decile
    FROM v_provider_kpis
)
SELECT  charge_decile,
        COUNT(*)                                         AS hospitals,
        ROUND(MIN(charge_index), 2)                      AS min_charge_index,
        ROUND(MAX(charge_index), 2)                      AS max_charge_index,
        ROUND(SUM(total_charges) / SUM(total_charges / charge_index), 2)  AS charge_index,
        ROUND(SUM(total_payment) / SUM(total_payment / payment_index), 3) AS payment_index,
        ROUND(SUM(total_payment) / SUM(total_charges), 3)                 AS pcr
FROM tiles
GROUP BY charge_decile
ORDER BY charge_decile;

-- name: q4_state_ranking
-- Q4. Which states charge most / are paid most, relative to the national case-mix?
SELECT  RANK() OVER (ORDER BY charge_index DESC)  AS charge_rank,
        RANK() OVER (ORDER BY payment_index DESC) AS payment_rank,
        state_code, state_name, hospitals, discharges,
        ROUND(charge_index, 2)  AS charge_index,
        ROUND(payment_index, 2) AS payment_index,
        ROUND(pcr, 3)           AS pcr,
        charge_gap
FROM v_state_kpis
ORDER BY charge_index DESC;

-- name: q5_setting_comparison
-- Q5. Urban vs rural: volume-weighted comparison.
SELECT  setting,
        COUNT(*)                                        AS hospitals,
        SUM(discharges)                                 AS discharges,
        ROUND(SUM(total_charges) / SUM(total_charges / charge_index), 2)  AS charge_index,
        ROUND(SUM(total_payment) / SUM(total_payment / payment_index), 2) AS payment_index,
        ROUND(SUM(total_payment) / SUM(total_charges), 3)                 AS pcr
FROM v_provider_kpis
GROUP BY setting
ORDER BY discharges DESC;

-- name: q6_same_drg_spread
-- Q6. For the 10 highest-volume DRGs, how much do hospitals differ on CHARGES vs on PAYMENTS?
--     p90/p10 ratio from ROW_NUMBER() ranks inside each DRG (no percentile function needed).
WITH top_drgs AS (
    SELECT drg_code FROM v_drg_kpis ORDER BY discharges DESC LIMIT 10
),
ranked AS (
    SELECT  f.drg_code,
            f.avg_submitted_charge  AS charge,
            f.avg_total_payment     AS payment,
            ROW_NUMBER() OVER (PARTITION BY f.drg_code ORDER BY f.avg_submitted_charge) AS rn_charge,
            ROW_NUMBER() OVER (PARTITION BY f.drg_code ORDER BY f.avg_total_payment)    AS rn_payment,
            COUNT(*)     OVER (PARTITION BY f.drg_code)                                  AS n
    FROM fact_discharge f
    WHERE f.drg_code IN (SELECT drg_code FROM top_drgs)
)
SELECT  r.drg_code,
        d.drg_description,
        MAX(r.n)                                                                                   AS hospitals,
        ROUND(MAX(CASE WHEN rn_charge  = CAST(0.9 * n AS INT) THEN charge  END) /
              MAX(CASE WHEN rn_charge  = CAST(0.1 * n AS INT) + 1 THEN charge  END), 2)            AS charge_p90_p10,
        ROUND(MAX(CASE WHEN rn_payment = CAST(0.9 * n AS INT) THEN payment END) /
              MAX(CASE WHEN rn_payment = CAST(0.1 * n AS INT) + 1 THEN payment END), 2)            AS payment_p90_p10
FROM ranked r
JOIN dim_drg d USING (drg_code)
GROUP BY r.drg_code, d.drg_description
ORDER BY hospitals DESC;

-- name: q7_top_service_lines
-- Q7. Largest service lines by gap, with names (not just codes).
SELECT  drg_code, drg_description, discharges,
        ROUND(nat_charge_per_discharge)  AS charge_per_discharge,
        ROUND(nat_payment_per_discharge) AS payment_per_discharge,
        ROUND(nat_pcr, 3)                AS pcr,
        charge_gap,
        ROUND(charge_gap * 1.0 / SUM(charge_gap) OVER (), 4) AS share_of_gap
FROM v_drg_kpis
ORDER BY charge_gap DESC
LIMIT 15;

-- name: q8_severity_screen_top
-- Q8. Hospitals whose case mix is lightest relative to peers (CDI review candidates).
SELECT  provider_id, provider_name, state_code, tiered_discharges,
        ROUND(top_tier_share, 3)               AS top_tier_share,
        ROUND(peer_expected_top_tier_share, 3) AS peer_expected_share,
        ROUND(severity_shortfall)              AS severity_shortfall,
        ROUND(shortfall_pct, 4)                AS shortfall_pct
FROM v_provider_severity_screen
ORDER BY severity_shortfall DESC
LIMIT 20;

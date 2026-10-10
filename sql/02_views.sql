-- =====================================================================
-- 02_views.sql  |  Single source of truth for every KPI
-- Python, Excel and Power BI all read these definitions.
--
--   Charges        = what the hospital lists (chargemaster price). Not collectible.
--   Payment        = all-payer payment on the claim (Medicare + patient + secondary).
--   PCR            = payment-to-charge ratio = SUM(payment) / SUM(charges)
--   Charge gap     = SUM(charges) - SUM(payment)   [descriptive; NOT recoverable revenue]
--   Charge index   = hospital charges / charges expected if it billed the national
--                    average for each DRG it treated   (1.00 = national, 2.00 = double)
--   Payment index  = same, for payments.  PCR = Payment index / Charge index (national PCR basis)
-- All ratios are volume-weighted (sums of dollars, never averages of ratios).
-- =====================================================================

DROP VIEW IF EXISTS v_fact;
CREATE VIEW v_fact AS
SELECT  f.provider_id,
        f.drg_code,
        f.total_discharges,
        f.avg_submitted_charge,
        f.avg_total_payment,
        f.avg_medicare_payment,
        f.total_discharges * f.avg_submitted_charge  AS total_charges,
        f.total_discharges * f.avg_total_payment     AS total_payment,
        f.total_discharges * f.avg_medicare_payment  AS total_medicare_payment,
        f.total_discharges * (f.avg_submitted_charge - f.avg_total_payment) AS charge_gap,
        CASE WHEN f.avg_total_payment > f.avg_submitted_charge THEN 1 ELSE 0 END AS payment_exceeds_charge
FROM fact_discharge f;

-- National benchmark per DRG (volume-weighted) --------------------------------
DROP VIEW IF EXISTS v_drg_benchmark;
CREATE VIEW v_drg_benchmark AS
SELECT  drg_code,
        COUNT(*)                                   AS hospitals,
        SUM(total_discharges)                      AS discharges,
        SUM(total_charges)  / SUM(total_discharges) AS nat_charge_per_discharge,
        SUM(total_payment)  / SUM(total_discharges) AS nat_payment_per_discharge,
        SUM(total_payment)  / SUM(total_charges)    AS nat_pcr
FROM v_fact
GROUP BY drg_code;

-- Fact rows with the case-mix "expected" values attached ---------------------
DROP VIEW IF EXISTS v_fact_benchmarked;
CREATE VIEW v_fact_benchmarked AS
SELECT  v.*,
        v.total_discharges * b.nat_charge_per_discharge  AS expected_charges,
        v.total_discharges * b.nat_payment_per_discharge AS expected_payment
FROM v_fact v
JOIN v_drg_benchmark b USING (drg_code);

-- Hospital scorecard ----------------------------------------------------------
DROP VIEW IF EXISTS v_provider_kpis;
CREATE VIEW v_provider_kpis AS
SELECT  p.provider_id,
        p.provider_name,
        p.city,
        p.state_code,
        s.census_region,
        COALESCE(g.setting, 'Unclassified')               AS setting,
        COUNT(*)                                          AS drgs_billed,
        SUM(b.total_discharges)                           AS discharges,
        SUM(b.total_charges)                              AS total_charges,
        SUM(b.total_payment)                              AS total_payment,
        SUM(b.charge_gap)                                 AS charge_gap,
        SUM(b.total_payment) / SUM(b.total_charges)       AS pcr,
        SUM(b.total_payment) / SUM(b.total_discharges)    AS payment_per_discharge,
        SUM(b.total_charges) / SUM(b.total_discharges)    AS charge_per_discharge,
        SUM(b.total_charges) / SUM(b.expected_charges)    AS charge_index,
        SUM(b.total_payment) / SUM(b.expected_payment)    AS payment_index
FROM v_fact_benchmarked b
JOIN dim_provider  p USING (provider_id)
JOIN dim_state     s ON s.state_code = p.state_code
LEFT JOIN dim_geography g ON g.ruca_code = p.ruca_code
GROUP BY p.provider_id, p.provider_name, p.city, p.state_code, s.census_region, g.setting;

-- Service-line scorecard ------------------------------------------------------
DROP VIEW IF EXISTS v_drg_kpis;
CREATE VIEW v_drg_kpis AS
SELECT  d.drg_code,
        d.drg_description,
        d.drg_family,
        d.severity_tier,
        b.hospitals,
        b.discharges,
        b.nat_charge_per_discharge,
        b.nat_payment_per_discharge,
        b.nat_pcr,
        b.discharges * (b.nat_charge_per_discharge - b.nat_payment_per_discharge) AS charge_gap
FROM v_drg_benchmark b
JOIN dim_drg d USING (drg_code);

-- State scorecard -------------------------------------------------------------
DROP VIEW IF EXISTS v_state_kpis;
CREATE VIEW v_state_kpis AS
SELECT  state_code,
        state_name,
        census_region,
        COUNT(*)              AS hospitals,
        SUM(discharges)       AS discharges,
        SUM(total_charges)    AS total_charges,
        SUM(total_payment)    AS total_payment,
        SUM(charge_gap)       AS charge_gap,
        SUM(total_payment) / SUM(total_charges)   AS pcr,
        SUM(total_payment) / SUM(discharges)      AS payment_per_discharge,
        SUM(total_charges) / SUM(total_charges / charge_index) AS charge_index,   -- = charges / expected charges
        SUM(total_payment) / SUM(total_payment / payment_index) AS payment_index
FROM v_provider_kpis
JOIN dim_state USING (state_code, census_region)
GROUP BY state_code, state_name, census_region;

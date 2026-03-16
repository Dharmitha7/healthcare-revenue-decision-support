USE cms_medicare;

-- Provider summary view (Tableau-ready)
CREATE OR REPLACE VIEW provider_summary AS
SELECT
  provider_id,
  SUM(total_revenue_gap) AS total_revenue_gap,
  SUM(total_discharges)  AS total_discharges,
  SUM(total_revenue_gap)/NULLIF(SUM(total_discharges),0) AS gap_per_discharge,
  SUM(avg_medicare_payment * total_discharges) /
    NULLIF(SUM(avg_charge * total_discharges),0) AS weighted_efficiency
FROM cleaned_data
GROUP BY provider_id;

-- DRG summary view (Tableau-ready)
CREATE OR REPLACE VIEW drg_summary AS
SELECT
  drg_code,
  SUM(total_revenue_gap) AS total_revenue_gap,
  SUM(total_discharges)  AS total_discharges,
  SUM(total_revenue_gap)/NULLIF(SUM(total_discharges),0) AS gap_per_discharge,
  SUM(avg_medicare_payment * total_discharges) /
    NULLIF(SUM(avg_charge * total_discharges),0) AS weighted_efficiency
FROM cleaned_data
GROUP BY drg_code;
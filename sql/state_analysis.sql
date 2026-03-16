USE cms_medicare;

CREATE OR REPLACE VIEW state_summary AS
SELECT
  state,
  SUM(total_revenue_gap) AS total_revenue_gap,
  SUM(total_discharges) AS total_discharges,
  SUM(total_revenue_gap) / NULLIF(SUM(total_discharges),0) AS gap_per_discharge,
  SUM(avg_medicare_payment * total_discharges) / NULLIF(SUM(avg_charge * total_discharges),0) AS weighted_efficiency
FROM cleaned_data
GROUP BY state;
USE cms_medicare;

-- 1) Top DRGs by exposure
SELECT
  drg_code,
  SUM(total_revenue_gap) AS total_revenue_gap,
  SUM(total_discharges) AS total_discharges,
  SUM(total_revenue_gap)/NULLIF(SUM(total_discharges),0) AS gap_per_discharge
FROM cleaned_data
GROUP BY drg_code
ORDER BY total_revenue_gap DESC
LIMIT 10;

-- 2) DRG Pareto (Top 20)
WITH drg_agg AS (
  SELECT drg_code,
         SUM(total_revenue_gap) AS total_revenue_gap,
         SUM(total_discharges)  AS total_discharges
  FROM cleaned_data
  GROUP BY drg_code
),
drg_share AS (
  SELECT drg_code,
         total_revenue_gap,
         total_discharges,
         total_revenue_gap / SUM(total_revenue_gap) OVER () AS exposure_share
  FROM drg_agg
),
drg_ranked AS (
  SELECT drg_code,
         total_revenue_gap,
         total_discharges,
         exposure_share,
         SUM(exposure_share) OVER (ORDER BY total_revenue_gap DESC) AS cum_share
  FROM drg_share
)
SELECT *
FROM drg_ranked
ORDER BY total_revenue_gap DESC
LIMIT 20;

-- 3) How many DRGs account for 50% and 80% exposure?
WITH drg_agg AS (
  SELECT drg_code, SUM(total_revenue_gap) AS total_revenue_gap
  FROM cleaned_data
  GROUP BY drg_code
),
drg_share AS (
  SELECT drg_code,
         total_revenue_gap,
         total_revenue_gap / SUM(total_revenue_gap) OVER () AS exposure_share
  FROM drg_agg
),
drg_ranked AS (
  SELECT drg_code,
         exposure_share,
         SUM(exposure_share) OVER (ORDER BY total_revenue_gap DESC) AS cum_share
  FROM drg_share
)
SELECT
  SUM(cum_share <= 0.5) AS drgs_to_50pct,
  SUM(cum_share <= 0.8) AS drgs_to_80pct
FROM drg_ranked;
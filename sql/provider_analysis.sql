USE cms_medicare;

-- 1) Top providers by total exposure
SELECT
  provider_id,
  SUM(total_revenue_gap) AS total_revenue_gap,
  SUM(total_discharges) AS total_discharges,
  SUM(total_revenue_gap)/NULLIF(SUM(total_discharges),0) AS gap_per_discharge
FROM cleaned_data
GROUP BY provider_id
ORDER BY total_revenue_gap DESC
LIMIT 10;

-- 2) Provider Pareto table (Top 20)
WITH provider_agg AS (
  SELECT provider_id,
         SUM(total_revenue_gap) AS total_revenue_gap,
         SUM(total_discharges)  AS total_discharges
  FROM cleaned_data
  GROUP BY provider_id
),
provider_share AS (
  SELECT provider_id,
         total_revenue_gap,
         total_discharges,
         total_revenue_gap / SUM(total_revenue_gap) OVER () AS exposure_share
  FROM provider_agg
),
provider_ranked AS (
  SELECT provider_id,
         total_revenue_gap,
         total_discharges,
         exposure_share,
         SUM(exposure_share) OVER (ORDER BY total_revenue_gap DESC) AS cum_share
  FROM provider_share
)
SELECT *
FROM provider_ranked
ORDER BY total_revenue_gap DESC
LIMIT 20;

-- 3) How many providers account for 50% and 80% exposure?
WITH provider_agg AS (
  SELECT provider_id, SUM(total_revenue_gap) AS total_revenue_gap
  FROM cleaned_data
  GROUP BY provider_id
),
provider_share AS (
  SELECT provider_id,
         total_revenue_gap,
         total_revenue_gap / SUM(total_revenue_gap) OVER () AS exposure_share
  FROM provider_agg
),
provider_ranked AS (
  SELECT provider_id,
         exposure_share,
         SUM(exposure_share) OVER (ORDER BY total_revenue_gap DESC) AS cum_share
  FROM provider_share
)
SELECT
  SUM(cum_share <= 0.5) AS providers_to_50pct,
  SUM(cum_share <= 0.8) AS providers_to_80pct
FROM provider_ranked;
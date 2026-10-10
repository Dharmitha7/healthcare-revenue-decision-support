# Data dictionary

Source: CMS *Medicare Inpatient Hospitals - by Provider and Service*, data year 2023 (file `MUP_INP_RY25_P03_V10_DY23_PrvSvc`).
Fee-for-service Medicare only. Hospital x MS-DRG combinations with 10 or fewer discharges are suppressed by CMS.

## Tables (star schema, `sql/01_schema.sql`)

### `fact_discharge`: one row per hospital x DRG (146,427 rows)
| Column | Type | Description |
|---|---|---|
| `provider_id` | CHAR(6) | CMS Certification Number (CCN). First two digits = state. **Stored as text** to keep leading zeros. FK to `dim_provider`. |
| `drg_code` | CHAR(3) | Medicare Severity Diagnosis Related Group. Stored as text (`003`). FK to `dim_drg`. |
| `total_discharges` | INTEGER | Number of Medicare discharges in that hospital x DRG (always >= 11). |
| `avg_submitted_charge` | DECIMAL | Average amount the hospital listed for covered services per discharge (chargemaster price). |
| `avg_total_payment` | DECIMAL | Average payment per discharge from **all payers on the claim**: Medicare + patient deductible/coinsurance + other payers. |
| `avg_medicare_payment` | DECIMAL | Medicare's own share of the payment per discharge (about 83% of total payment overall). |

### `dim_provider` (2,945 hospitals)
`provider_id`, `provider_name`, `city`, `street`, `zip5`, `state_code` (FK `dim_state`), `ruca_code` (FK `dim_geography`).
The Power BI export adds `state_name`, `census_region`, `setting`, and the k-means `segment`.

### `dim_drg` (534 DRGs)
| Column | Description |
|---|---|
| `drg_code`, `drg_description` | Code and CMS title (titles longer than 88 characters are truncated by CMS: 33 DRGs). |
| `drg_family` | Title with the severity suffix removed (e.g. "SEPTICEMIA OR SEVERE SEPSIS WITHOUT MV >96 HOURS"). Populated only when the family spans at least two severity tiers. |
| `severity_tier` | 0 = without CC/MCC, 1 = without MCC, 2 = with CC, 3 = with MCC (or CC/MCC). NULL = not part of a tiered family (132 DRGs). |

### `dim_geography` (19 RUCA codes) and `dim_state` (51)
`ruca_code` (USDA Rural-Urban Commuting Area; decimals are secondary codes), `ruca_desc`, `setting` (Metropolitan 1-3, Micropolitan 4-6, Small town 7-9, Rural 10, Unclassified 99).
`state_code`, `state_name`, `census_region`.

## Derived measures (`sql/02_views.sql`; identical in Python, Excel and DAX)

| Measure | Definition | Notes |
|---|---|---|
| Total charges | SUM(discharges x avg_submitted_charge) | List price, not collectible |
| Total payment | SUM(discharges x avg_total_payment) | All payers |
| **Charge gap** | Total charges - total payment | Descriptive only. **Not** recoverable revenue |
| **Payment-to-charge ratio (PCR)** | SUM(payment) / SUM(charges) | Ratio of sums, never an average of row ratios (simple average gives 26.2% vs the correct 20.5%) |
| National benchmark per DRG | SUM(payment) / SUM(discharges) over all hospitals, per DRG | `v_drg_benchmark` |
| **Charge index** | Hospital charges / charges expected if it billed the national average for each DRG it treated | 1.00 = national, same case mix |
| **Payment index** | Same, for payments | Adjusts for service mix, not for wage index or teaching status |
| **Severity shortfall** | Expected payment at the peer severity mix minus actual, both valued at national DRG payment | `v_provider_severity_screen`; screen, not forecast |
| Shortfall % | Shortfall / expected payment | Used for the review threshold |
| Segment | k-means (k=5) on log volume, log charge index, log payment index, DRG breadth, non-metro flag | Names assigned from cluster profiles |

## Data-quality log

| Check | Result | Treatment |
|---|---|---|
| Duplicate hospital x DRG keys | 0 | n/a |
| Missing RUCA code | 4 rows (1 hospital) | Kept; setting = "Unclassified" |
| Payment > charge | 281 rows (0.19%; 0.16% of discharges) | Kept, flagged (`payment_exceeds_charge`) |
| Truncated DRG titles | 33 | Excluded from severity tiering |
| Leading zeros in CCN / DRG | Present in raw data; lost in v1 | Read and stored as text |

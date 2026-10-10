# Technical notes

## Reproduce
```bash
pip install -r requirements.txt
python python/build_database.py          # raw CSV -> data/healthcare.db (SQLite), runs sql/01, 02, 04
jupyter nbconvert --to notebook --execute --inplace notebooks/healthcare_analysis.ipynb   # figures + exports
python python/build_excel_model.py       # excel/healthcare_opportunity_model.xlsx
```
The SQL uses standard constructs (CTEs, window functions, views) and was run on SQLite; MySQL 8 / PostgreSQL need minor changes
(e.g. `CAST(... AS SIGNED)` instead of `AS INT`, and boolean sums in `q2b`). Not tested on those engines. SQLite is used so the project runs with no server and no credentials.

## SQL map
| File | Purpose | Techniques |
|---|---|---|
| `sql/01_schema.sql` | Star schema with PK/FK/CHECK constraints and indexes | DDL, referential integrity |
| `sql/02_views.sql` | KPI views (fact, DRG benchmark, hospital / DRG / state scorecards) | Joins, aggregation, case-mix indices |
| `sql/03_analysis_queries.sql` | Eight business-question queries | CTEs, `RANK`, `NTILE`, `ROW_NUMBER`, running `SUM() OVER`, `UNION ALL` |
| `sql/04_severity_mix.sql` | Documentation-capture screen | Multi-step CTE pipeline, correlated subquery, `HAVING` volume filter |

## Method: why the severity screen is built this way
- **Peer groups:** metropolitan vs non-metropolitan hospitals, because severity mix differs by setting.
- **Same-price valuation:** every discharge is valued at the *national* average payment of its DRG, so differences in wage index, teaching add-ons and DSH payments cannot masquerade as a documentation gap.
- **Volume gate:** at least 300 tiered discharges and 10 families per hospital. 1,996 of 2,945 hospitals qualify.
- **Threshold:** the Excel model counts only hospitals at least 2% below peers by default; the sensitivity table shows 0-5%.
- **Capture rate:** 10 / 25 / 50% is an assumption, not an estimate from data. It represents the share of a shortfall that clinical validation would support.

## Audit of v1 (kept in `docs/archive_v1/`)
1. `SUM(Provider_Summary!B:B)` included the pivot table's Grand Total row, doubling the total gap ($717.6B vs $358.8B on Medicare payment).
2. "Top DRG optimisation" multiplied 8% by the whole gap instead of the top-10-DRG subtotal (31% of the gap).
3. "Top 20 providers" summed the first 20 rows of an unsorted pivot, not the 20 largest.
4. The README said exposure was "highly concentrated"; the data show a top-20 share of 13%.
5. Hospital and DRG names were dropped, so dashboards showed IDs; CCN leading zeros were lost.
6. A database password was hard-coded in the notebook; a `.venv` and an Excel lock file were committed.

All six are fixed in v2; the corrected figures are in the `v1_Reconciliation` sheet of the Excel model.

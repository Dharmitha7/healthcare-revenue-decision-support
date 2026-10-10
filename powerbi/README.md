# Power BI executive dashboard: build guide

Everything needed to assemble the report in about 30 minutes. The `.pbix` itself is not committed
because it is a binary built in Power BI Desktop; the model, measures and theme below are the reviewable source.

## 1. Load the data
1. Power BI Desktop > **Transform data** > create a text parameter `DataFolder` pointing at `powerbi/data/`.
2. Paste each query from [`load_tables.pq`](load_tables.pq). IDs are typed as **text** so the leading zeros in hospital IDs (`010001`) and DRG codes (`003`) survive.
3. **Home > Apply** to load; **Theme > Browse** and pick [`theme.json`](theme.json).

## 2. Model (star schema)

```
dim_state (state_code) ──1:*── dim_provider (provider_id) ──1:*── fact_discharge (provider_id, drg_code) ──*:1── dim_drg (drg_code)
dim_geography (ruca_code) ──1:*── dim_provider            provider_severity_screen (provider_id) ──1:1── dim_provider
```

| Relationship | Cardinality | Cross-filter |
|---|---|---|
| `dim_provider[provider_id]` → `fact_discharge[provider_id]` | one-to-many | single |
| `dim_drg[drg_code]` → `fact_discharge[drg_code]` | one-to-many | single |
| `dim_state[state_code]` → `dim_provider[state_code]` | one-to-many | single |
| `dim_geography[ruca_code]` → `dim_provider[ruca_code]` | one-to-many | single |
| `dim_provider[provider_id]` ↔ `provider_severity_screen[provider_id]` | one-to-one | both |

Sort `drg_label` by `drg_code`. Mark `state_code` as data category *State or Province* so the map plots correctly.

## 3. Measures
Paste [`measures.dax`](measures.dax) into a `_Measures` table, then create the two what-if parameters it describes
(*Review Threshold* and *Capture Rate*). **Check:** with no filters, `Total Charges` = $432.2B, `Total Payment` = $88.4B and
`Payment-to-Charge Ratio` = 20.5%. If those do not match, a relationship or type is wrong.

## 4. Pages

| Page | Question it answers | Visuals |
|---|---|---|
| **1. Executive summary** | How big is the gap and where is it? | 4 KPI cards (Charges, Payments, PCR, Gap); filled map of `Charge Index` by state; top-10 DRG bar by `Charge Gap`; slicers: setting, segment |
| **2. Why the gap exists** | Is it a payment problem or a pricing problem? | Scatter: `Charge Index` (x) vs `Payment Index` (y), one dot per hospital, colour = `segment`; column chart of `Charge Index` by charge decile |
| **3. Concentration** | Who matters most? | Pareto: columns `Charge Gap` by hospital (top 50) + line `Cumulative Gap Share`; card `Hospitals to Reach 50% of Gap`; table with name, state, segment, `Charge Index`, `Payment Index` |
| **4. Documentation opportunity** | What can a hospital actually change? | Two what-if sliders; cards `Eligible Hospitals`, `Eligible Shortfall`, `Documentation Opportunity`; ranked table of hospitals by `Eligible Shortfall` with a data bar |

Design rules used in this report (and in the README charts): one accent blue plus greys, no rainbow palettes, a single axis per chart,
titles that state the finding ("Charges rise 6x across deciles; payments barely move"), and slicers in one row at the top.

## 5. Publish checklist
- Add a **tooltip page** showing payment per discharge and charge per discharge for the hovered hospital.
- Add a text box on every page: *"Charges are list prices; the gap is descriptive, not recoverable revenue."*
- Export page screenshots to `docs/images/` and link them from the main README.

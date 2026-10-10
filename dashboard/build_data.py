"""Aggregate the Power BI star-schema CSVs into dashboard/data.json (same definitions as powerbi/measures.dax)."""
import json
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parent.parent
d = root / "powerbi" / "data"
read = lambda n: pd.read_csv(d / n, dtype={"provider_id": str, "drg_code": str, "state_code": str})
f, prov, drg, scr = read("fact_discharge.csv"), read("dim_provider.csv"), read("dim_drg.csv"), read("provider_severity_screen.csv")

f = f.merge(drg[["drg_code", "drg_description", "nat_charge_per_discharge", "nat_payment_per_discharge"]], on="drg_code")
f["exp_charge"] = f.total_discharges * f.nat_charge_per_discharge
f["exp_pay"] = f.total_discharges * f.nat_payment_per_discharge

def agg(g):
    s = g[["total_discharges", "total_charges", "total_payment", "exp_charge", "exp_pay"]].sum()
    return pd.Series({
        "discharges": s.total_discharges, "charges": s.total_charges, "payment": s.total_payment,
        "gap": s.total_charges - s.total_payment,
        "pcr": s.total_payment / s.total_charges,
        "ci": s.total_charges / s.exp_charge, "pi": s.total_payment / s.exp_pay})

nat = agg(f)
h = f.groupby("provider_id").apply(agg, include_groups=False).reset_index().merge(
    prov[["provider_id", "provider_name", "state_code", "setting", "segment"]], on="provider_id")
st = f.merge(prov[["provider_id", "state_code"]], on="provider_id").groupby("state_code").apply(agg, include_groups=False).reset_index()
dg = f.groupby(["drg_code", "drg_description"]).apply(agg, include_groups=False).reset_index().sort_values("gap", ascending=False)
dg["share"] = dg.gap / nat.gap

h = h.sort_values("gap", ascending=False).reset_index(drop=True)
h["cum"] = h.gap.cumsum() / h.gap.sum()
n50 = int((h.cum <= 0.5).sum())
h["decile"] = pd.qcut(h.ci.rank(method="first"), 10, labels=False) + 1
dec = h.groupby("decile").apply(lambda g: pd.Series({
    "ci": g.charges.sum() / (g.charges / g.ci).sum(), "pi": g.payment.sum() / (g.payment / g.pi).sum(),
    "pcr": g.payment.sum() / g.charges.sum()}), include_groups=False).reset_index()
seg = h.groupby("segment").apply(lambda g: pd.Series({
    "n": len(g), "gap_share": g.gap.sum() / h.gap.sum(), "pcr": g.payment.sum() / g.charges.sum(),
    "ci": g.charges.sum() / (g.charges / g.ci).sum()}), include_groups=False).reset_index()

import re
tidy = lambda t: re.sub(r"\b(mcc|cc|mv|ecmo|ami|pci)\b", lambda m: m.group(1).upper(), t.lower().capitalize())
r = lambda x, k=4: round(float(x), k)
out = {
    "national": {k: r(v, 4) if k in ("pcr", "ci", "pi") else float(v) for k, v in nat.items()},
    "n50": n50, "n_hosp": len(h),
    "states": [{"s": x.state_code, "ci": r(x.ci), "pcr": r(x.pcr)} for x in st.itertuples()],
    "drgs": [{"c": x.drg_code, "t": tidy(x.drg_description), "gap": float(x.gap), "share": r(x.share)} for x in dg.head(10).itertuples()],
    "hosp": [{"n": x.provider_name, "st": x.state_code, "seg": x.segment, "ci": r(x.ci), "pi": r(x.pi), "gap": float(x.gap), "cum": r(x.cum)} for x in h.itertuples()],
    "deciles": [{"d": int(x.decile), "ci": r(x.ci), "pi": r(x.pi), "pcr": r(x.pcr)} for x in dec.itertuples()],
    "segments": [{"seg": x.segment, "n": int(x.n), "gap_share": r(x.gap_share), "pcr": r(x.pcr), "ci": r(x.ci)} for x in seg.itertuples()],
    "sev": [{"n": x.provider_name, "st": x.state_code, "short": r(x.severity_shortfall, 0), "pct": r(x.shortfall_pct, 5)} for x in scr.itertuples()],
}
(root / "dashboard" / "data.json").write_text(json.dumps(out, separators=(",", ":")))
print(out["national"], n50, out["segments"], sep="\n")

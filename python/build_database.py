"""Build the analytical database from the raw CMS Medicare Inpatient file.

    python python/build_database.py

Steps: read raw CSV (CCN/DRG kept as text so leading zeros survive) -> build
dimension tables -> create the schema in sql/ -> load -> create views ->
sanity-check row counts. Output: data/healthcare.db (SQLite, git-ignored).
The SQL files are plain ANSI SQL, so the same scripts run on MySQL/PostgreSQL.
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "MUP_INP_RY25_P03_V10_DY23_PrvSvc.CSV"
DB = ROOT / "data" / "healthcare.db"
SQL = ROOT / "sql"

STATES = {  # code: (name, census region)
    "AL": ("Alabama", "South"), "AK": ("Alaska", "West"), "AZ": ("Arizona", "West"),
    "AR": ("Arkansas", "South"), "CA": ("California", "West"), "CO": ("Colorado", "West"),
    "CT": ("Connecticut", "Northeast"), "DE": ("Delaware", "South"),
    "DC": ("District of Columbia", "South"), "FL": ("Florida", "South"),
    "GA": ("Georgia", "South"), "HI": ("Hawaii", "West"), "ID": ("Idaho", "West"),
    "IL": ("Illinois", "Midwest"), "IN": ("Indiana", "Midwest"), "IA": ("Iowa", "Midwest"),
    "KS": ("Kansas", "Midwest"), "KY": ("Kentucky", "South"), "LA": ("Louisiana", "South"),
    "ME": ("Maine", "Northeast"), "MD": ("Maryland", "South"),
    "MA": ("Massachusetts", "Northeast"), "MI": ("Michigan", "Midwest"),
    "MN": ("Minnesota", "Midwest"), "MS": ("Mississippi", "South"),
    "MO": ("Missouri", "Midwest"), "MT": ("Montana", "West"), "NE": ("Nebraska", "Midwest"),
    "NV": ("Nevada", "West"), "NH": ("New Hampshire", "Northeast"),
    "NJ": ("New Jersey", "Northeast"), "NM": ("New Mexico", "West"),
    "NY": ("New York", "Northeast"), "NC": ("North Carolina", "South"),
    "ND": ("North Dakota", "Midwest"), "OH": ("Ohio", "Midwest"), "OK": ("Oklahoma", "South"),
    "OR": ("Oregon", "West"), "PA": ("Pennsylvania", "Northeast"),
    "RI": ("Rhode Island", "Northeast"), "SC": ("South Carolina", "South"),
    "SD": ("South Dakota", "Midwest"), "TN": ("Tennessee", "South"), "TX": ("Texas", "South"),
    "UT": ("Utah", "West"), "VT": ("Vermont", "Northeast"), "VA": ("Virginia", "South"),
    "WA": ("Washington", "West"), "WV": ("West Virginia", "South"),
    "WI": ("Wisconsin", "Midwest"), "WY": ("Wyoming", "West"),
}

# severity suffixes of MS-DRG titles, longest first so "WITHOUT CC/MCC" wins over "WITH ... "
SEVERITY_SUFFIXES = [
    (" WITHOUT CC/MCC", 0),
    (" WITHOUT MCC", 1),
    (" WITH CC/MCC", 3),
    (" WITH MCC", 3),
    (" WITH CC", 2),
]


def severity(desc: str):
    """Return (family, tier). Titles cut off by the CMS 88-char limit are left untiered."""
    for suffix, tier in SEVERITY_SUFFIXES:
        if desc.endswith(suffix):
            return desc[: -len(suffix)].strip(), tier
    return None, None


def setting(ruca) -> str:
    if pd.isna(ruca):
        return "Unclassified"
    ruca = int(ruca)  # secondary codes (e.g. 7.2) share the setting of their primary code
    if ruca == 99:
        return "Unclassified"
    if ruca <= 3:
        return "Metropolitan"
    if ruca <= 6:
        return "Micropolitan"
    if ruca <= 9:
        return "Small town"
    return "Rural" if ruca == 10 else "Unclassified"


def main() -> None:
    raw = pd.read_csv(RAW, encoding="cp1252", dtype={"Rndrng_Prvdr_CCN": str, "DRG_Cd": str,
                                                      "Rndrng_Prvdr_Zip5": str})
    raw["Rndrng_Prvdr_CCN"] = raw["Rndrng_Prvdr_CCN"].str.zfill(6)
    raw["DRG_Cd"] = raw["DRG_Cd"].str.zfill(3)
    raw["Rndrng_Prvdr_Zip5"] = raw["Rndrng_Prvdr_Zip5"].str.zfill(5)
    print(f"raw rows: {len(raw):,}")

    dim_state = pd.DataFrame(
        [(k, v[0], v[1]) for k, v in STATES.items()],
        columns=["state_code", "state_name", "census_region"])

    geo = (raw[["Rndrng_Prvdr_RUCA", "Rndrng_Prvdr_RUCA_Desc"]].dropna(subset=["Rndrng_Prvdr_RUCA"])
           .drop_duplicates("Rndrng_Prvdr_RUCA")
           .rename(columns={"Rndrng_Prvdr_RUCA": "ruca_code", "Rndrng_Prvdr_RUCA_Desc": "ruca_desc"}))
    geo["setting"] = geo["ruca_code"].map(setting)

    dim_provider = (raw.drop_duplicates("Rndrng_Prvdr_CCN")[
        ["Rndrng_Prvdr_CCN", "Rndrng_Prvdr_Org_Name", "Rndrng_Prvdr_City", "Rndrng_Prvdr_St",
         "Rndrng_Prvdr_Zip5", "Rndrng_Prvdr_State_Abrvtn", "Rndrng_Prvdr_RUCA"]]
        .set_axis(["provider_id", "provider_name", "city", "street", "zip5", "state_code", "ruca_code"],
                  axis=1))

    dim_drg = (raw.drop_duplicates("DRG_Cd")[["DRG_Cd", "DRG_Desc"]]
               .set_axis(["drg_code", "drg_description"], axis=1))
    sev = dim_drg["drg_description"].map(severity)
    dim_drg["drg_family"] = [s[0] for s in sev]
    dim_drg["severity_tier"] = [s[1] for s in sev]
    # a family is only useful if it spans >= 2 severity tiers
    tiers = dim_drg.dropna(subset=["drg_family"]).groupby("drg_family")["severity_tier"].nunique()
    single = tiers[tiers < 2].index
    dim_drg.loc[dim_drg["drg_family"].isin(single), ["drg_family", "severity_tier"]] = None
    dim_drg["severity_tier"] = dim_drg["severity_tier"].astype("Int64")

    fact = raw[["Rndrng_Prvdr_CCN", "DRG_Cd", "Tot_Dschrgs", "Avg_Submtd_Cvrd_Chrg",
                "Avg_Tot_Pymt_Amt", "Avg_Mdcr_Pymt_Amt"]].set_axis(
        ["provider_id", "drg_code", "total_discharges", "avg_submitted_charge",
         "avg_total_payment", "avg_medicare_payment"], axis=1)

    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript((SQL / "01_schema.sql").read_text())
    for name, df in [("dim_state", dim_state), ("dim_geography", geo), ("dim_provider", dim_provider),
                     ("dim_drg", dim_drg), ("fact_discharge", fact)]:
        df.to_sql(name, con, if_exists="append", index=False)
    for script in ("02_views.sql", "04_severity_mix.sql"):  # view definitions
        con.executescript((SQL / script).read_text())
    con.commit()

    for t in ["dim_state", "dim_geography", "dim_provider", "dim_drg", "fact_discharge"]:
        print(f"{t:15s}", con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    tiered = con.execute("SELECT COUNT(*), COUNT(DISTINCT drg_family) FROM dim_drg "
                         "WHERE severity_tier IS NOT NULL").fetchone()
    print(f"DRGs in severity-tiered families: {tiered[0]} across {tiered[1]} families")
    orphan = con.execute("SELECT COUNT(*) FROM fact_discharge f LEFT JOIN dim_provider p "
                         "USING (provider_id) WHERE p.provider_id IS NULL").fetchone()[0]
    assert orphan == 0, "fact rows without a provider"
    print("database ->", DB)


if __name__ == "__main__":
    main()

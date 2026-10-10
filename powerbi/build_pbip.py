"""Generate the Power BI Project (HospitalPricing.pbip): semantic model (TMDL) + 4-page report (PBIR).

Open HospitalPricing.pbip in Power BI Desktop, then File > Save as to produce a .pbix.
Re-run this script after editing measures or layout; it rewrites both folders.
"""
import json
import shutil
import uuid
from pathlib import Path

import pandas as pd

root = Path(__file__).resolve().parent
NAME = "HospitalPricing"
sm, rp = root / f"{NAME}.SemanticModel", root / f"{NAME}.Report"
data_dir = root / "data"
T = "\t"


def gid(s):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NAME}/{s}"))


# ----------------------------------------------------------------------------- tables
S, I, F = "string", "int64", "double"
TABLES = {
    "fact_discharge": [("provider_id", S), ("drg_code", S), ("total_discharges", I), ("avg_submitted_charge", F),
                       ("avg_total_payment", F), ("avg_medicare_payment", F), ("total_charges", F),
                       ("total_payment", F), ("total_medicare_payment", F), ("charge_gap", F)],
    "dim_provider": [("provider_id", S), ("provider_name", S), ("city", S), ("street", S), ("zip5", S),
                     ("state_code", S), ("ruca_code", F), ("state_name", S), ("census_region", S),
                     ("setting", S), ("segment", S)],
    "dim_drg": [("drg_code", S), ("drg_description", S), ("drg_family", S), ("severity_tier", I), ("hospitals", I),
                ("nat_charge_per_discharge", F), ("nat_payment_per_discharge", F), ("nat_pcr", F)],
    "dim_state": [("state_code", S), ("state_name", S), ("census_region", S)],
    "dim_geography": [("ruca_code", F), ("ruca_desc", S), ("setting", S)],
    "provider_severity_screen": [("provider_id", S), ("provider_name", S), ("state_code", S), ("setting", S),
                                 ("peer_group", S), ("tiered_families", I), ("tiered_discharges", I),
                                 ("top_tier_share", F), ("peer_expected_top_tier_share", F), ("actual_value", F),
                                 ("expected_value", F), ("severity_shortfall", F), ("shortfall_pct", F)],
}
MTYPE = {S: "type text", I: "Int64.Type", F: "type number"}
SUMMARIZE_NONE = {"provider_id", "drg_code", "state_code", "zip5", "ruca_code", "severity_tier"}

# calculated columns on dim_provider (efficient Pareto: hospital gap, rank and cumulative share)
CALC_COLS = {
    "dim_provider": [
        ("gap_total", F, "CALCULATE ( SUM ( fact_discharge[charge_gap] ) )", "$#,0"),
        ("gap_rank", I, "RANKX ( dim_provider, dim_provider[gap_total], , DESC, DENSE )", "0"),
        ("gap_cum_share", F,
         "VAR g = dim_provider[gap_total]\n"
         "RETURN DIVIDE ( SUMX ( FILTER ( ALL ( dim_provider ), dim_provider[gap_total] >= g ), dim_provider[gap_total] ),\n"
         "                SUM ( dim_provider[gap_total] ) )", "0.0%"),
    ],
}

# ----------------------------------------------------------------------------- measures
B, PCT, IDX, MIL, CNT = "$#,0.0", "0.0%", "0.00", "$#,0", "#,0"
MEASURES = [
    ("Discharges", "SUM ( fact_discharge[total_discharges] )", CNT),
    ("Total Charges", "SUM ( fact_discharge[total_charges] )", B),
    ("Total Payment", "SUM ( fact_discharge[total_payment] )", B),
    ("Medicare Payment", "SUM ( fact_discharge[total_medicare_payment] )", B),
    ("Charge Gap", "[Total Charges] - [Total Payment]", B),
    ("Payment-to-Charge Ratio", "DIVIDE ( [Total Payment], [Total Charges] )", PCT),
    ("Payment per Discharge", "DIVIDE ( [Total Payment], [Discharges] )", "$#,0"),
    ("Charge per Discharge", "DIVIDE ( [Total Charges], [Discharges] )", "$#,0"),
    ("Medicare Share of Payment", "DIVIDE ( [Medicare Payment], [Total Payment] )", PCT),
    ("National PCR", "CALCULATE ( [Payment-to-Charge Ratio], ALL ( fact_discharge ), ALL ( dim_provider ), ALL ( dim_drg ), ALL ( dim_state ), ALL ( dim_geography ) )", PCT),
    ("Expected Charges", "SUMX ( fact_discharge, fact_discharge[total_discharges] * RELATED ( dim_drg[nat_charge_per_discharge] ) )", B),
    ("Expected Payment", "SUMX ( fact_discharge, fact_discharge[total_discharges] * RELATED ( dim_drg[nat_payment_per_discharge] ) )", B),
    ("Charge Index", "DIVIDE ( [Total Charges], [Expected Charges] )", IDX),
    ("Payment Index", "DIVIDE ( [Total Payment], [Expected Payment] )", IDX),
    ("Hospital Count", "DISTINCTCOUNT ( dim_provider[provider_id] )", CNT),
    ("Share of Total Gap", "DIVIDE ( [Charge Gap], CALCULATE ( [Charge Gap], ALLSELECTED ( dim_provider ) ) )", PCT),
    ("Hospitals to Reach 50% of Gap", "COUNTROWS ( FILTER ( ALL ( dim_provider ), dim_provider[gap_cum_share] <= 0.5 ) )", CNT),
    ("Top 10 DRG Gap", "IF ( RANKX ( ALL ( dim_drg ), [Charge Gap], , DESC, DENSE ) <= 10, [Charge Gap] )", B),
    ("Top 50 Hospital Gap", "IF ( MIN ( dim_provider[gap_rank] ) <= 50, [Charge Gap] )", B),
    ("Review Threshold Value", "SELECTEDVALUE ( 'Review Threshold'[Review Threshold], 0.02 )", PCT),
    ("Capture Rate Value", "SELECTEDVALUE ( 'Capture Rate'[Capture Rate], 0.25 )", "0%"),
    ("Eligible Shortfall",
     "VAR thr = [Review Threshold Value]\n"
     "RETURN CALCULATE ( SUM ( provider_severity_screen[severity_shortfall] ),\n"
     "    provider_severity_screen[severity_shortfall] > 0,\n"
     "    provider_severity_screen[shortfall_pct] >= thr )", MIL),
    ("Documentation Opportunity", "[Eligible Shortfall] * [Capture Rate Value]", MIL),
    ("Eligible Hospitals",
     "VAR thr = [Review Threshold Value]\n"
     "RETURN CALCULATE ( COUNTROWS ( provider_severity_screen ),\n"
     "    provider_severity_screen[severity_shortfall] > 0,\n"
     "    provider_severity_screen[shortfall_pct] >= thr )", CNT),
]

RELATIONSHIPS = [  # (from_many, to_one, extra properties)
    ("fact_discharge.provider_id", "dim_provider.provider_id", []),
    ("fact_discharge.drg_code", "dim_drg.drg_code", []),
    ("dim_provider.state_code", "dim_state.state_code", []),
    ("dim_provider.ruca_code", "dim_geography.ruca_code", []),
    ("provider_severity_screen.provider_id", "dim_provider.provider_id",
     ["fromCardinality: one", "crossFilteringBehavior: bothDirections"]),
]


def q(name):
    return f"'{name}'" if any(c in name for c in " -%&") else name


def indent_expr(expr, n):
    return "\n".join(T * n + line for line in expr.split("\n"))


def m_source(table):
    cols = TABLES[table]
    typed = ", ".join(f'{{"{c}", {MTYPE[t]}}}' for c, t in cols if t != S or c in ("zip5",) or c.endswith("_id") or c.endswith("_code"))
    lines = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{typed}}}, "en-US")',
    ]
    last = "Typed"
    if table == "dim_drg":
        lines[-1] += ","
        lines.append('    Label = Table.AddColumn(Typed, "drg_label", each [drg_code] & " - " & Text.Proper([drg_description]), type text)')
        last = "Label"
    lines += ["in", f"    {last}"]
    return indent_expr("\n".join(lines), 4)


def column_block(c, t, calc=None):
    out = [f"{T}column {q(c)}"]
    if calc:
        expr, fmt = calc
        if "\n" in expr:
            out[0] += " =\n" + indent_expr(expr, 3)
        else:
            out[0] += f" = {expr}"
        out.append(f"{T*2}dataType: {t}")
        out.append(f"{T*2}isDataTypeInferred")
        out.append(f"{T*2}formatString: {fmt}")
        out.append(f"{T*2}summarizeBy: none")
        out.append(f"{T*2}lineageTag: {gid('col/' + c)}")
        return "\n".join(out)
    out.append(f"{T*2}dataType: {t}")
    out.append(f"{T*2}sourceColumn: {c}")
    out.append(f"{T*2}summarizeBy: {'none' if (t == S or c in SUMMARIZE_NONE) else 'sum'}")
    out.append(f"{T*2}lineageTag: {gid('col/' + c)}")
    return "\n".join(out)


def measure_block(name, expr, fmt):
    if "\n" in expr:
        head = f"{T}measure {q(name)} =\n{indent_expr(expr, 3)}"
    else:
        head = f"{T}measure {q(name)} = {expr}"
    return f"{head}\n{T*2}formatString: {fmt}\n{T*2}lineageTag: {gid('m/' + name)}"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8", newline="\n")


def build_model():
    if sm.exists():
        shutil.rmtree(sm)
    geo = pd.read_csv(data_dir / "dim_geography.csv")
    assert geo.ruca_code.is_unique, "dim_geography.ruca_code must be unique for the relationship"
    write(sm / "definition.pbism", json.dumps({"version": "4.0", "settings": {}}, indent=2))
    write(sm / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    names = list(TABLES) + ["_Measures", "Review Threshold", "Capture Rate"]
    refs = "\n".join(f"ref table {q(n)}" for n in names)
    write(sm / "definition" / "model.tmdl",
          "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n\n"
          f"{refs}\n\nref expression DataFolder\n")
    folder = str(data_dir).rstrip("\\/") + "\\"
    write(sm / "definition" / "expressions.tmdl",
          f'expression DataFolder = "{folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
          f"{T}lineageTag: {gid('expr/DataFolder')}\n")
    for table, cols in TABLES.items():
        parts = [f"table {table}", f"{T}lineageTag: {gid('t/' + table)}", ""]
        for c, t in cols:
            parts += [column_block(c, t), ""]
        if table == "dim_drg":
            parts += [f"{T}column drg_label\n{T*2}dataType: string\n{T*2}sourceColumn: drg_label\n{T*2}sortByColumn: drg_code\n"
                      f"{T*2}summarizeBy: none\n{T*2}lineageTag: {gid('col/drg_label')}", ""]
        for c, t, expr, fmt in CALC_COLS.get(table, []):
            parts += [column_block(c, t, (expr, fmt)), ""]
        parts += [f"{T}partition {table} = m\n{T*2}mode: import\n{T*2}source =\n{m_source(table)}", ""]
        write(sm / "definition" / "tables" / f"{table}.tmdl", "\n".join(parts))
    # measures table
    parts = ["table _Measures", f"{T}lineageTag: {gid('t/_Measures')}", "",
             f"{T}column Value\n{T*2}isHidden\n{T*2}dataType: int64\n{T*2}sourceColumn: [Value]\n{T*2}summarizeBy: none\n{T*2}lineageTag: {gid('col/_v')}", ""]
    for n, e, f in MEASURES:
        parts += [measure_block(n, e, f), ""]
    parts += [f"{T}partition _Measures = calculated\n{T*2}mode: import\n{T*2}source = {{1}}", ""]
    write(sm / "definition" / "tables" / "_Measures.tmdl", "\n".join(parts))
    # what-if tables
    for tname, lo, hi, step, fmt in [("Review Threshold", 0, 0.05, 0.005, "0.0%"), ("Capture Rate", 0.05, 0.5, 0.05, "0%")]:
        write(sm / "definition" / "tables" / f"{tname}.tmdl",
              f"table {q(tname)}\n{T}lineageTag: {gid('t/' + tname)}\n\n"
              f"{T}column {q(tname)}\n{T*2}dataType: double\n{T*2}formatString: {fmt}\n{T*2}sourceColumn: [Value]\n"
              f"{T*2}summarizeBy: none\n{T*2}lineageTag: {gid('col/' + tname)}\n\n"
              f"{T}partition {q(tname)} = calculated\n{T*2}mode: import\n{T*2}source = GENERATESERIES ( {lo}, {hi}, {step} )\n")
    rel = []
    for frm, to, extra in RELATIONSHIPS:
        body = [f"relationship {gid('rel/' + frm + to)}"] + [f"{T}{e}" for e in extra] + [f"{T}fromColumn: {frm}", f"{T}toColumn: {to}"]
        rel.append("\n".join(body))
    write(sm / "definition" / "relationships.tmdl", "\n\n".join(rel) + "\n")


# ----------------------------------------------------------------------------- report
def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def field(kind, table, prop):
    return {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def proj(kind, table, prop):
    return {"field": field(kind, table, prop), "queryRef": f"{table}.{prop}", "nativeQueryRef": prop}


def C(t, p): return ("Column", t, p)
def Ms(p): return ("Measure", "_Measures", p)


def visual(name, vtype, x, y, w, h, roles=None, title=None, sort=None, labels=False, extra_objects=None, z=0):
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if roles:
        qs = {role: {"projections": [proj(*f) for f in fs]} for role, fs in roles.items()}
        v["query"] = {"queryState": qs}
        if sort:
            v["query"]["sortDefinition"] = {"sort": [{"field": field(*sort[0]), "direction": sort[1]}], "isDefaultSort": True}
    objects = dict(extra_objects or {})
    if labels:
        objects["labels"] = [{"properties": {"show": lit("true")}}]
    if vtype in ("clusteredBarChart", "columnChart"):
        objects["categoryAxis"] = [{"properties": {"showAxisTitle": lit("false")}}]
        objects["valueAxis"] = [{"properties": {"showAxisTitle": lit("false")}}]
    if vtype == "card":
        objects["categoryLabels"] = [{"properties": {"show": lit("false")}}]
    if objects:
        v["objects"] = objects
    if title:
        v["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{title}'")}}]}
    return name, {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": name, "position": {"x": x, "y": y, "width": w, "height": h, "z": z, "tabOrder": z}, "visual": v}


def textbox(name, x, y, w, h, text, size="12pt", bold=False, color="#1F2937"):
    style = {"fontSize": size, "color": color}
    if bold:
        style["fontWeight"] = "bold"
    run = {"value": text, "textStyle": style}
    return visual(name, "textbox", x, y, w, h,
                  extra_objects={"general": [{"properties": {"paragraphs": [{"textRuns": [run]}]}}]})


def card(name, x, measure, title):
    return visual(name, "card", x, 112, 290, 90, {"Values": [Ms(measure)]}, title=title)


NOTE = "Charges are list prices; the gap is descriptive, not recoverable revenue. Source: CMS Medicare Inpatient Hospitals by Provider and Service, 2023."
PAGES = []


def page(pid, title, headline, visuals):
    vs = [textbox(f"{pid}_h", 20, 8, 1240, 44, headline, "18pt", True),
          textbox(f"{pid}_n", 20, 690, 1240, 24, NOTE, "9pt", False, "#6B7280")] + visuals
    PAGES.append((pid, title, vs))


page("p1", "1. Executive summary", "The $344B gap is a list-price effect, concentrated in a few service lines", [
    visual("p1_s1", "slicer", 20, 52, 300, 56, {"Values": [C("dim_provider", "setting")]}, extra_objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]}),
    visual("p1_s2", "slicer", 340, 52, 340, 56, {"Values": [C("dim_provider", "segment")]}, extra_objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]}),
    card("p1_c1", 20, "Total Charges", "Total charges"), card("p1_c2", 330, "Total Payment", "Total payments"),
    card("p1_c3", 640, "Payment-to-Charge Ratio", "Payment-to-charge ratio"), card("p1_c4", 950, "Charge Gap", "Charge gap (descriptive)"),
    visual("p1_v1", "clusteredBarChart", 20, 215, 620, 465, {"Category": [C("dim_drg", "drg_label")], "Y": [Ms("Top 10 DRG Gap")]},
           "Ten service lines with the largest gap", (Ms("Top 10 DRG Gap"), "Descending"), labels=True),
    visual("p1_v2", "clusteredBarChart", 660, 215, 600, 465, {"Category": [C("dim_state", "state_name")], "Y": [Ms("Charge Index")]},
           "Charge index by state, same DRG mix (1.00 = national)", (Ms("Charge Index"), "Descending"), labels=True)])

page("p2", "2. Why the gap exists", "Hospitals differ in what they charge, not in what they are paid", [
    visual("p2_v1", "scatterChart", 20, 60, 760, 620,
           {"Category": [C("dim_provider", "provider_name")], "X": [Ms("Charge Index")], "Y": [Ms("Payment Index")], "Series": [C("dim_provider", "segment")]},
           "Each dot is a hospital: charge index (x) vs payment index (y)"),
    visual("p2_v2", "clusteredBarChart", 800, 60, 460, 300, {"Category": [C("dim_provider", "segment")], "Y": [Ms("Charge Index"), Ms("Payment Index")]},
           "Charge index vs payment index by segment", labels=True),
    visual("p2_v3", "clusteredBarChart", 800, 380, 460, 300, {"Category": [C("dim_provider", "segment")], "Y": [Ms("Payment-to-Charge Ratio")]},
           "Payment-to-charge ratio by segment", (Ms("Payment-to-Charge Ratio"), "Ascending"), labels=True)])

page("p3", "3. Concentration", "A small group of hospitals accounts for half of the gap", [
    card("p3_c1", 20, "Hospitals to Reach 50% of Gap", "Hospitals to reach 50% of gap"),
    visual("p3_v1", "clusteredBarChart", 20, 215, 480, 465, {"Category": [C("dim_provider", "provider_name")], "Y": [Ms("Top 50 Hospital Gap")]},
           "Top 50 hospitals by charge gap", (Ms("Top 50 Hospital Gap"), "Descending")),
    visual("p3_v2", "tableEx", 520, 215, 740, 465,
           {"Values": [C("dim_provider", "segment"), Ms("Hospital Count"), Ms("Share of Total Gap"), Ms("Payment-to-Charge Ratio"), Ms("Charge Index")]},
           "Hospital segments", (Ms("Share of Total Gap"), "Descending")),
    card("p3_c2", 330, "Hospital Count", "Hospitals in current selection")])

page("p4", "4. Documentation opportunity", "The lever hospitals control: severity documentation", [
    visual("p4_s1", "slicer", 20, 52, 300, 56, {"Values": [C("Review Threshold", "Review Threshold")]},
           None,
           extra_objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}], "selection": [{"properties": {"singleSelect": lit("true")}}]}),
    visual("p4_s2", "slicer", 340, 52, 300, 56, {"Values": [C("Capture Rate", "Capture Rate")]},
           None, extra_objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}], "selection": [{"properties": {"singleSelect": lit("true")}}]}),
    card("p4_c1", 20, "Eligible Hospitals", "Eligible hospitals"), card("p4_c2", 330, "Eligible Shortfall", "Eligible shortfall"),
    card("p4_c3", 640, "Documentation Opportunity", "Documentation opportunity (shortfall x capture rate)"),
    visual("p4_v1", "tableEx", 20, 215, 1240, 465,
           {"Values": [C("provider_severity_screen", "provider_name"), C("provider_severity_screen", "state_code"), Ms("Eligible Shortfall")]},
           "Hospitals ranked by shortfall vs peers (screen only; clinical and compliance review decides what is supportable)",
           (Ms("Eligible Shortfall"), "Descending"))])


def build_report():
    if rp.exists():
        shutil.rmtree(rp)
    write(rp / "definition.pbir", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2))
    d = rp / "definition"
    write(d / "version.json", json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2))
    write(d / "report.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": {"visual": "2.4.0", "page": "2.0.0", "report": "3.0.0"}, "type": "SharedResources"},
            "customTheme": {"name": "theme.json", "reportVersionAtImport": {"visual": "2.4.0", "page": "2.0.0", "report": "3.0.0"}, "type": "RegisteredResources"}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources", "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "theme.json", "path": "theme.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True}}, indent=2))
    theme_dir = rp / "StaticResources" / "RegisteredResources"
    theme_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(root / "theme.json", theme_dir / "theme.json")
    write(d / "pages" / "pages.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p[0] for p in PAGES], "activePageName": PAGES[0][0]}, indent=2))
    for pid, title, vs in PAGES:
        write(d / "pages" / pid / "page.json", json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name": pid, "displayName": title, "displayOption": "FitToPage", "height": 720, "width": 1280}, indent=2))
        for i, (vname, vj) in enumerate(vs):
            vj["position"]["z"] = vj["position"]["tabOrder"] = i * 10
            write(d / "pages" / pid / "visuals" / vname / "visual.json", json.dumps(vj, indent=2))


if __name__ == "__main__":
    build_model()
    build_report()
    write(root / f"{NAME}.pbip", json.dumps({
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2))
    print("built", root / f"{NAME}.pbip")

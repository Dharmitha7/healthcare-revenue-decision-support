// Power Query (M) - paste each query into Home > Transform data > New Source > Blank Query > Advanced Editor.
// Set the folder path once as a parameter named DataFolder, e.g. "C:\...\healthcare-revenue-decision-support\powerbi\data\"
// IDs are typed as TEXT on purpose: CCN and DRG codes carry leading zeros ("010001", "003") that numeric types would destroy.

// ---- fact_discharge --------------------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "fact_discharge.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"provider_id", type text}, {"drg_code", type text}, {"total_discharges", Int64.Type},
        {"avg_submitted_charge", type number}, {"avg_total_payment", type number}, {"avg_medicare_payment", type number},
        {"total_charges", type number}, {"total_payment", type number}, {"total_medicare_payment", type number},
        {"charge_gap", type number}}, "en-US")
in
    Typed

// ---- dim_provider ----------------------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "dim_provider.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"provider_id", type text}, {"zip5", type text}, {"ruca_code", type number}}, "en-US")
in
    Typed

// ---- dim_drg ---------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "dim_drg.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"drg_code", type text}, {"severity_tier", Int64.Type},
        {"nat_charge_per_discharge", type number}, {"nat_payment_per_discharge", type number}, {"nat_pcr", type number}}, "en-US"),
    Label = Table.AddColumn(Typed, "drg_label", each [drg_code] & " - " & Text.Proper([drg_description]), type text)
in
    Label

// ---- dim_state / dim_geography ---------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "dim_state.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in
    Promoted

let
    Source = Csv.Document(File.Contents(DataFolder & "dim_geography.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"ruca_code", type number}}, "en-US")
in
    Typed

// ---- provider_severity_screen ----------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "provider_severity_screen.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"provider_id", type text}, {"severity_shortfall", type number},
        {"shortfall_pct", type number}, {"top_tier_share", type number}, {"peer_expected_top_tier_share", type number},
        {"tiered_discharges", Int64.Type}}, "en-US")
in
    Typed

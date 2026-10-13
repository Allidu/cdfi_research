"""Export the processed tables to data/outputs/jobago_cdfi_landscape.xlsx and write descriptive
summary tables to data/outputs/tables/. Descriptive only - no Jobago scoring or ranking."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DATA, INTERIM, PROCESSED, TODAY  # noqa: E402

OUT = DATA / "outputs"
TABLES = OUT / "tables"


def descriptive_tables(m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    dep = m[m.has_lending_mix]
    t = {}
    t["counts_by_type"] = m.institution_type.value_counts().rename_axis("institution_type").reset_index(name="n")
    t["focus_by_type"] = pd.crosstab(m.institution_type, m.primary_lending_focus.fillna("(not available)")).reset_index()
    t["focus_basis_by_type"] = pd.crosstab(m.institution_type, m.focus_basis.fillna("none")).reset_index()
    t["median_shares_by_type"] = dep.groupby("institution_type")[
        [c for c in m.columns if c.startswith("share_")] + ["small_business_exposure_pct"]].median().round(1).reset_index()
    cols = ["cdfi_id", "cdfi_name", "institution_type", "hq_state", "members", "total_loan_count", "total_assets_usd",
            "total_loans_usd", "consumer_exposure_pct", "auto_loan_share_pct", "unsecured_consumer_share_pct",
            "primary_lending_focus", "primary_focus_confidence", "market_segment_code", "size_tier", "branch_count", "number_states_branches", "financials_reporting_date"]
    cu = m[m.institution_type == "Credit Union"]
    t["credit_unions_by_members"] = cu.sort_values("members", ascending=False)[cols].head(50)
    t["depositories_by_consumer_exposure_min_100m_loans"] = (
        dep[(dep.total_loans_usd >= 100e6) & dep.include_in_market_totals]
        .sort_values("consumer_exposure_pct", ascending=False)[cols].head(50))
    t["banks_by_small_business_exposure"] = (
        m[m.institution_type == "Bank or Thrift"].sort_values("small_business_exposure_pct", ascending=False)
        [["cdfi_id", "cdfi_name", "hq_state", "total_assets_usd", "small_business_exposure_pct",
          "small_business_loan_count_banks", "primary_lending_focus"]].head(50))
    t["loan_funds_by_irs_assets"] = (
        m[m.institution_type == "Loan Fund"].sort_values("irs_total_assets_usd", ascending=False)
        [["cdfi_id", "cdfi_name", "hq_state", "ein", "irs_total_assets_usd", "irs_total_revenue_usd", "irs_tax_period",
          "irs_ntee_code", "total_cdfi_fund_awards_usd", "award_programs"]].head(50))
    return t


def main() -> None:
    m = pd.read_csv(PROCESSED / "cdfi_master.csv", low_memory=False)
    TABLES.mkdir(parents=True, exist_ok=True)
    tabs = descriptive_tables(m)
    for k, v in tabs.items():
        v.to_csv(TABLES / f"{k}.csv", index=False)

    lend = pd.read_csv(PROCESSED / "cdfi_lending.csv", low_memory=False)
    readme = pd.DataFrame({"item": [
        "Generated", "Universe", "Sheets", "Reported vs derived", "Caution"], "detail": [
        TODAY,
        f"{len(m)} CDFIs on the CDFI Fund certified list as of {m.source_as_of_date.iloc[0]}",
        "master, crosswalk, lending_latest, awards_linked, geography, state_summary, coverage, segments, loan-fund classification + evidence, descriptive tables",
        "See research/data_dictionary.md; derived fields include shares, focus, flags, growth, award summaries",
        "Banks/CUs use 2026-06-30 Call Reports; loan-fund assets are IRS BMF (latest 990, varying tax periods). "
        "BHC values sum subsidiary banks - use include_in_market_totals to avoid double counting.",
    ]})
    latest = lend[lend.reporting_date == lend.reporting_date.max()]
    sheets = {
        "README": readme,
        "master": m,
        "crosswalk": pd.read_csv(PROCESSED / "cdfi_crosswalk.csv"),
        "lending_latest": latest,
        "awards_linked": pd.read_csv(PROCESSED / "cdfi_awards.csv").query("cdfi_id.notna()", engine="python"),
        "geography": pd.read_csv(PROCESSED / "cdfi_geography.csv"),
        "state_summary": pd.read_csv(PROCESSED / "state_summary.csv"),
        "coverage": pd.read_csv(TABLES / "coverage_by_type.csv"),
        "lending_category_map": pd.read_csv(DATA / "reference" / "lending_category_map.csv"),
        "segments": pd.read_csv(PROCESSED / "cdfi_segments.csv"),
        "segment_totals": pd.read_csv(TABLES / "segment_totals.csv"),
        "segment_by_type": pd.read_csv(TABLES / "segment_by_type.csv"),
        "size_tier_by_type": pd.read_csv(TABLES / "size_tier_by_type.csv"),
        "loan_fund_classification": pd.read_csv(PROCESSED / "loan_fund_classification.csv"),
        "focus_evidence": pd.read_csv(PROCESSED / "cdfi_focus_evidence.csv"),
        "focus_text_rules": pd.read_csv(DATA / "reference" / "focus_text_rules.csv"),
        **{k[:31]: v for k, v in tabs.items()},
    }
    xlsx = OUT / "jobago_cdfi_landscape.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name[:31], index=False)
            ws = w.sheets[name[:31]]
            ws.freeze_panes = "B2"
    print(f"wrote {xlsx} and {len(tabs)} tables in {TABLES}")


if __name__ == "__main__":
    main()

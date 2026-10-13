"""Institution-type-specific size tiers, market segmentation and segment-level statistics.

Run after build_processed.py. Adds tier/segment columns to data/processed/cdfi_master.csv (idempotent:
existing columns of the same name are replaced) and writes:
  data/processed/cdfi_segments.csv
  data/outputs/tables/segment_*.csv, size_tier_*.csv
  research/market_structure_report.md (all figures computed here)

Segments are descriptive groupings by PRIMARY lending focus - not a ranking or a Jobago score.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DATA, PROCESSED, RESEARCH, TODAY  # noqa: E402

TABLES = DATA / "outputs" / "tables"
DEP = ["Bank or Thrift", "Bank Holding Company", "Credit Union"]
NONDEP = ["Loan Fund", "Venture Capital Fund"]

# Size tiers: thresholds differ by institution type on purpose (see research/methodology.md section 14).
TIERS = {
    "bank": ("total_assets_usd", [0, 250e6, 1e9, 10e9, np.inf],
             ["S: <$250M", "M: $250M-$1B", "L: $1B-$10B", "XL: >=$10B"]),
    "credit_union": ("total_assets_usd", [0, 100e6, 500e6, 2e9, np.inf],
                     ["S: <$100M", "M: $100M-$500M", "L: $500M-$2B", "XL: >=$2B"]),
    "loan_fund": ("nondep_total_assets_usd", [0, 10e6, 50e6, 250e6, np.inf],
                  ["S: <$10M", "M: $10M-$50M", "L: $50M-$250M", "XL: >=$250M"]),
}
MEMBER_TIERS = ([0, 10_000, 50_000, 200_000, np.inf], ["S: <10K members", "M: 10K-50K", "L: 50K-200K", "XL: >=200K"])
LOAN_PORTFOLIO_TIERS = ([0, 5e6, 25e6, 100e6, np.inf], ["S: <$5M", "M: $5M-$25M", "L: $25M-$100M", "XL: >=$100M"])

SEGMENTS = {
    "A": "A. Consumer-focused",
    "B": "B. Microenterprise / very small business",
    "C": "C. Mortgage / homeownership",
    "D": "D. Small business / commercial / agricultural",
    "E": "E. Real estate, housing development & community facilities (project finance)",
    "F": "F. Intermediary / venture / other",
    "U": "U. Unclassified (insufficient public evidence)",
}
SEG_OF_FOCUS = {"consumer": "A", "microenterprise": "B", "mortgage_homeownership": "C", "small_business": "D",
                "commercial_business": "D", "agriculture": "D", "commercial_real_estate": "E",
                "residential_housing_development": "E", "community_facilities": "E", "intermediary_finance": "F",
                "venture_equity": "F"}
FLAG_TO_SEG = {"consumer_lending_flag": "A", "microenterprise_flag": "B", "mortgage_lending_flag": "C",
               "small_business_flag": "D", "commercial_business_flag": "D", "agriculture_flag": "D",
               "commercial_real_estate_flag": "E", "housing_development_flag": "E", "community_facilities_flag": "E",
               "intermediary_finance_flag": "F", "venture_flag": "F"}


def size_tiers(m: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    # Non-depository assets: 990 end-of-year total assets (same filing as the text evidence), else IRS BMF.
    m["nondep_total_assets_usd"] = m.irs_990_total_assets_eoy_usd.where(m.irs_990_total_assets_eoy_usd.notna(), m.irs_total_assets_usd)
    m["nondep_assets_source"] = np.where(m.irs_990_total_assets_eoy_usd.notna(), "IRS 990 XML (Part X total assets EOY)",
                                         np.where(m.irs_total_assets_usd.notna(), "IRS EO BMF ASSET_AMT", None))
    m.loc[m.institution_type.isin(DEP), ["nondep_total_assets_usd", "nondep_assets_source"]] = [np.nan, None]
    group = np.select([m.institution_type.isin(["Bank or Thrift", "Bank Holding Company"]),
                       m.institution_type.eq("Credit Union")], ["bank", "credit_union"], "loan_fund")
    m["size_tier_group"] = group
    m["size_tier"] = pd.NA
    m["size_tier_basis"] = pd.NA
    for g, (col, bins, labels) in TIERS.items():
        idx = (m.size_tier_group == g) & m[col].notna() & (m[col] > 0)
        m.loc[idx, "size_tier"] = pd.cut(m.loc[idx, col], bins=bins, labels=labels, right=False).astype(str)
        m.loc[idx, "size_tier_basis"] = f"{col} (thresholds specific to {g.replace('_', ' ')}s)"
    m["size_tier_code"] = m.size_tier.str[:2].str.strip(":")
    # Percentile within institution type (BHCs ranked with banks would double count; ranked separately).
    m["size_metric_usd"] = m.total_assets_usd.where(m.institution_type.isin(DEP), m.nondep_total_assets_usd)
    m["size_percentile_within_type"] = (m.groupby("institution_type").size_metric_usd.rank(pct=True) * 100).round(1)
    cu = m.members.notna()
    m.loc[cu, "member_tier"] = pd.cut(m.loc[cu, "members"], bins=MEMBER_TIERS[0], labels=MEMBER_TIERS[1], right=False).astype(str)
    lf = m.notes_loans_receivable_eoy_usd.notna() & m.institution_type.isin(NONDEP) & (m.notes_loans_receivable_eoy_usd > 0)
    m.loc[lf, "loan_portfolio_tier"] = pd.cut(m.loc[lf, "notes_loans_receivable_eoy_usd"], bins=LOAN_PORTFOLIO_TIERS[0],
                                              labels=LOAN_PORTFOLIO_TIERS[1], right=False).astype(str)
    return m


def segments(m: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    seg = m.primary_lending_focus.map(SEG_OF_FOCUS).fillna("U")
    # Microenterprise lenders whose top-scoring category is small_business: if the CDFI is an SBA Microloan
    # intermediary or has microenterprise evidence, segment B (they are the very-small-business specialists).
    sc = pd.read_csv(PROCESSED / "cdfi_focus_category_scores.csv")
    micro_high = set(sc[(sc.category == "microenterprise") & (sc.confidence == "HIGH")].cdfi_id)
    micro_ev = m.cdfi_id.isin(micro_high) | m.sba_microloan_intermediary.eq(True)
    to_b = (seg == "D") & m.primary_lending_focus.eq("small_business") & micro_ev & m.institution_type.isin(NONDEP)
    seg[to_b] = "B"
    m["market_segment_code"] = seg
    m["market_segment"] = seg.map(SEGMENTS)
    m["market_segment_rule"] = np.where(to_b, "primary small_business + (SBA Microloan intermediary or HIGH microenterprise evidence) -> B",
                                        np.where(seg == "U", "no primary focus available", "primary_lending_focus -> segment map"))
    m["market_subsegment"] = np.select(
        [seg.eq("D") & m.primary_lending_focus.eq("agriculture"), seg.eq("D") & m.primary_lending_focus.eq("commercial_business"),
         seg.eq("D"), seg.eq("E") & m.primary_lending_focus.eq("commercial_real_estate"),
         seg.eq("E") & m.primary_lending_focus.eq("residential_housing_development"), seg.eq("E"),
         seg.eq("F") & m.primary_lending_focus.eq("venture_equity"), seg.eq("F")],
        ["D3 agricultural", "D2 commercial (larger business)", "D1 small business", "E1 commercial real estate",
         "E2 housing development", "E3 community facilities", "F2 venture / equity", "F1 intermediary"], "")
    m["segment_confidence"] = m.primary_focus_confidence.fillna("UNKNOWN")
    # Multi-focus: every segment in which the CDFI has a meaningful activity (portfolio share >= 10%,
    # or MEDIUM/HIGH evidence), including its primary.
    mem = []
    for _, r in m.iterrows():
        s = {SEG_OF_FOCUS.get(r.primary_lending_focus)} - {None}
        for flag, code in FLAG_TO_SEG.items():
            if r.get(flag) is True:
                s.add(code)
        mem.append(";".join(sorted(s)))
    m["segment_memberships"] = mem
    m["n_segment_memberships"] = [len([x for x in s.split(";") if x]) for s in mem]
    m["multi_focus"] = m.n_meaningful_activities.fillna(0) >= 2
    return m


def money(x):
    return "" if pd.isna(x) else f"${x / 1e9:,.1f}B" if abs(x) >= 1e9 else f"${x / 1e6:,.0f}M"


def md(df: pd.DataFrame) -> str:
    df = df.copy()
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) or v is None or v is pd.NA else str(v) for v in r.values) + " |")
    return "\n".join(lines)


def segment_stats(m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    inc = m.include_in_market_totals
    rows = []
    for (seg, ty), g in m.groupby(["market_segment", "institution_type"]):
        gi = g[g.include_in_market_totals]
        rows.append({
            "market_segment": seg, "institution_type": ty, "n_cdfis": len(g),
            "pct_of_type": round(len(g) / (m.institution_type == ty).sum() * 100, 1),
            "n_high_conf": int((g.segment_confidence == "HIGH").sum()),
            "total_assets_usd_dedup": gi.total_assets_usd.sum(min_count=1) if ty in DEP else gi.nondep_total_assets_usd.sum(min_count=1),
            "median_assets_usd": g.total_assets_usd.median() if ty in DEP else g.nondep_total_assets_usd.median(),
            "total_loans_usd_dedup": gi.total_loans_usd.sum(min_count=1) if ty in DEP else gi.notes_loans_receivable_eoy_usd.sum(min_count=1),
            "loans_basis": "Call Report total loans" if ty in DEP else "990 notes & loans receivable (EOY)",
            "consumer_loans_usd_dedup": (gi.total_loans_usd * gi.share_consumer_pct / 100).sum(min_count=1) if ty in DEP else np.nan,
            "individual_borrower_loans_usd_dedup": (gi.total_loans_usd * gi.share_individual_borrowers_pct / 100).sum(min_count=1) if ty in DEP else np.nan,
            "members_total": g.members.sum(min_count=1), "members_median": g.members.median(),
            "median_consumer_share_pct": round(g.share_consumer_pct.median(), 1), "median_mortgage_share_pct": round(g.share_mortgage_homeownership_pct.median(), 1),
            "median_small_business_exposure_pct": round(g.small_business_exposure_pct.median(), 1),
            "n_states_hq": g.hq_state.nunique(), "n_native_cdfis": int(g.native_cdfi.sum()),
            "n_multi_focus": int(g.multi_focus.sum()),
        })
    out["segment_by_type"] = pd.DataFrame(rows)
    seg_tot = out["segment_by_type"].groupby("market_segment")[["n_cdfis", "n_high_conf", "total_assets_usd_dedup", "consumer_loans_usd_dedup",
                                                                 "individual_borrower_loans_usd_dedup", "members_total", "n_native_cdfis", "n_multi_focus"]].sum(min_count=1)
    seg_tot["pct_of_all_cdfis"] = (seg_tot.n_cdfis / len(m) * 100).round(1)
    out["segment_totals"] = seg_tot.reset_index()
    out["segment_x_type_counts"] = pd.crosstab(m.market_segment, m.institution_type, margins=True).reset_index()
    out["segment_x_size_tier"] = pd.crosstab([m.institution_type, m.size_tier.fillna("(no size data / zero assets)")], m.market_segment_code).reset_index()
    out["size_tier_by_type"] = (m.groupby(["institution_type", m.size_tier.fillna("(no size data / zero assets)")])
                                .agg(n=("cdfi_id", "size"), median_assets=("size_metric_usd", "median"),
                                     total_assets=("size_metric_usd", "sum"), members_total=("members", "sum"))
                                .reset_index())
    out["member_tiers"] = m[m.institution_type == "Credit Union"].groupby(m.member_tier.fillna("(no data)")).agg(
        n=("cdfi_id", "size"), members=("members", "sum"), median_consumer_share=("share_consumer_pct", "median")).reset_index()
    act = []
    for flag, code in FLAG_TO_SEG.items():
        for ty in m.institution_type.unique():
            g = m[m.institution_type == ty]
            v = g[flag]
            act.append({"activity_flag": flag, "institution_type": ty, "n_true": int((v == True).sum()),  # noqa: E712
                        "n_false": int((v == False).sum()), "n_unknown": int(v.isna().sum())})  # noqa: E712
    out["activity_participation"] = pd.DataFrame(act).pivot_table(index="activity_flag", columns="institution_type", values="n_true", aggfunc="sum").astype(int).reset_index()
    out["multi_focus_by_type"] = m.groupby("institution_type").agg(
        n=("cdfi_id", "size"), classified=("primary_lending_focus", lambda s: s.notna().sum()),
        multi_focus=("multi_focus", "sum"), median_meaningful=("n_meaningful_activities", "median"),
        median_segment_memberships=("n_segment_memberships", "median")).reset_index()
    out["state_x_segment"] = pd.crosstab(m.hq_state, m.market_segment_code).reset_index()
    return out


def report(m: pd.DataFrame, st: dict[str, pd.DataFrame]) -> str:
    d = m[m.focus_basis == "portfolio"]
    lf = m[m.institution_type == "Loan Fund"]
    cu = m[m.institution_type == "Credit Union"]
    bk = m[m.institution_type.isin(["Bank or Thrift", "Bank Holding Company"])]
    sbt = st["segment_by_type"].copy()
    for c in ["total_assets_usd_dedup", "median_assets_usd", "total_loans_usd_dedup", "consumer_loans_usd_dedup", "individual_borrower_loans_usd_dedup"]:
        sbt[c] = sbt[c].map(money)
    for c in ["members_total", "members_median"]:
        sbt[c] = sbt[c].map(lambda x: "" if pd.isna(x) else f"{x:,.0f}")
    tot = st["segment_totals"].copy()
    for c in ["total_assets_usd_dedup", "consumer_loans_usd_dedup", "individual_borrower_loans_usd_dedup"]:
        tot[c] = tot[c].map(money)
    tot["members_total"] = tot.members_total.map(lambda x: "" if pd.isna(x) else f"{x:,.0f}")
    lf_conf = lf.primary_focus_confidence.value_counts()
    ev_src = lf[lf.focus_basis == "evidence"].classification_source.fillna("").str.split(";").explode().value_counts()
    tiers = st["size_tier_by_type"].copy()
    tiers["median_assets"] = tiers.median_assets.map(money)
    tiers["total_assets"] = tiers.total_assets.map(money)
    tiers["members_total"] = tiers.members_total.map(lambda x: "" if pd.isna(x) or x == 0 else f"{x:,.0f}")
    seg_size = st["segment_x_size_tier"]
    multi = st["multi_focus_by_type"]
    near = d.groupby("institution_type").primary_focus_near_tie.mean().mul(100).round(1)

    return f"""# U.S. CDFI Market Structure — Lending Focus, Size Tiers and Segments

_Generated by `scripts/analyze/segment_market.py` on {TODAY}. Universe: {len(m):,} certified CDFIs (CDFI Fund list as of
{m.source_as_of_date.iloc[0]}). Every number below is computed from `data/processed/`. Segments are descriptive groupings by
primary lending focus; **they are not a ranking or a Jobago score.**_

## 1. How lending focus was determined

| Basis | Institutions | Source | What "primary" means |
|---|---|---|---|
| Portfolio | {int((m.focus_basis == 'portfolio').sum())} banks, BHCs, credit unions | FDIC Call Report RC-C (+ Part II size bands); NCUA 5300 (2026-06-30) | Largest standardized category share of total loans |
| Evidence | {int((m.focus_basis == 'evidence').sum())} loan funds / VC funds | IRS 990 program text (expense-weighted), mission, SBA lists, CDFI Fund award programs, FHLB, name | Highest evidence score |
| None | {int((m.focus_basis == 'none').sum())} | — | Not classified (no regulatory data / no usable public evidence) |

Coverage of a primary focus by type:

{md(m.groupby('institution_type').agg(n=('cdfi_id', 'size'), with_primary_focus=('primary_lending_focus', lambda s: int(s.notna().sum()))).assign(pct=lambda x: (x.with_primary_focus / x.n * 100).round(1)).reset_index())}

Loan-fund classification confidence: HIGH {int(lf_conf.get('HIGH', 0))}, MEDIUM {int(lf_conf.get('MEDIUM', 0))}, LOW {int(lf_conf.get('LOW', 0))},
UNKNOWN {int(lf_conf.get('UNKNOWN', 0))} (of {len(lf)}). Evidence types used (loan funds with a classification):
{', '.join(f'{k} {v}' for k, v in ev_src.items() if k)}.

### Primary-rule diagnostics (portfolio basis)
* Near-ties (top two categories within 5 pp): {', '.join(f'{k} {v}%' for k, v in near.items())} — these get confidence LOW.
* Splitting C&I into size bands (microenterprise proxy / small business / larger commercial) changes the primary focus
  of only 4 banks versus treating C&I as one category, so fragmentation does not drive the result.
* Credit-union commercial lending is small: median small-business share {cu.share_small_business_pct.median():.2f}% of loans.

## 2. Primary lending focus by institution type

{md(pd.crosstab(m.primary_lending_focus.fillna('(unclassified)'), m.institution_type, margins=True).reset_index())}

Median portfolio shares (portfolio basis only, % of total loans):

{md(d.groupby('institution_type')[['share_consumer_pct', 'share_mortgage_homeownership_pct', 'share_microenterprise_pct', 'share_small_business_pct', 'share_commercial_business_pct', 'share_commercial_real_estate_pct', 'share_residential_housing_development_pct', 'share_agriculture_pct', 'small_business_exposure_pct']].median().round(1).T.reset_index().rename(columns={'index': 'share'}))}

Borrower type (who repays) — primary borrower type, portfolio basis:

{md(pd.crosstab(d.institution_type, d.primary_borrower_type).reset_index())}

## 3. Multi-focus institutions

{md(multi)}

`multi_focus` = two or more meaningful activities (portfolio share ≥ 10%, or MEDIUM/HIGH evidence for loan funds).
For loan funds, absence of evidence is not evidence of absence; their activity counts are lower bounds.

Activity participation (number of CDFIs with the flag = True):

{md(st['activity_participation'])}

## 4. Size tiers (thresholds differ by type)

Banks/BHCs: assets S <$250M, M $250M–$1B, L $1B–$10B, XL ≥$10B. Credit unions: S <$100M, M $100–500M, L $500M–$2B,
XL ≥$2B. Loan/VC funds (990 or IRS BMF total assets): S <$10M, M $10–50M, L $50–250M, XL ≥$250M. BHC tiers use the
sum of subsidiary banks.

{md(tiers)}

Credit-union member tiers:

{md(st['member_tiers'].assign(members=lambda x: x.members.map(lambda v: f'{v:,.0f}')))}

## 5. Market segments

{md(tot)}

Segment × institution type:

{md(sbt[['market_segment', 'institution_type', 'n_cdfis', 'pct_of_type', 'n_high_conf', 'total_assets_usd_dedup', 'median_assets_usd', 'total_loans_usd_dedup', 'loans_basis', 'consumer_loans_usd_dedup', 'members_total', 'members_median', 'median_consumer_share_pct', 'n_multi_focus']])}

Segment × size tier:

{md(seg_size)}

Notes: dollar totals exclude BHCs whose subsidiaries are separately certified (`include_in_market_totals`). Loan-fund
"loans" are 990 notes & loans receivable (different date and definition from Call Report loans).

## 6. Observations supported by the data

* Credit unions are the consumer-lending part of the market: {int((cu.primary_lending_focus == 'consumer').sum())} of {int(cu.primary_lending_focus.notna().sum())} classified CDFI credit unions are
  primarily consumer lenders, and the rest are mainly mortgage lenders; {int(cu.members.notna().sum())} report {cu.members.sum():,.0f} members in total.
* CDFI banks are mostly real-estate lenders: commercial real estate is the primary focus for
  {int((bk.primary_lending_focus == 'commercial_real_estate').sum())} and mortgages for {int((bk.primary_lending_focus == 'mortgage_homeownership').sum())} of {int(bk.primary_lending_focus.notna().sum())} classified banks/BHCs; consumer lending is a
  median {bk.share_consumer_pct.median():.1f}% of bank loans. Regulatory small-business loans (≤$1MM) are a median
  {bk.small_business_exposure_pct.median():.1f}% of bank loans, but much of that is small CRE, not C&I.
* Loan funds are the business- and housing-lending part of the market: of {int(lf.primary_lending_focus.notna().sum())} classified loan funds,
  {int(lf.market_segment_code.isin(['B', 'D']).sum())} are in segments B or D (micro/small business), {int(lf.market_segment_code.eq('C').sum())} in C (homeownership),
  {int(lf.market_segment_code.eq('E').sum())} in E (housing development / real estate / facilities) and {int(lf.market_segment_code.eq('A').sum())} in A (consumer).
  Loan funds are small: median total assets {money(lf.nondep_total_assets_usd.median())}.
* Native CDFIs ({int(m.native_cdfi.sum())}) are spread across segments: {', '.join(f'{k} {v}' for k, v in m[m.native_cdfi].market_segment_code.value_counts().items())}.

## 7. Caveats

* Evidence-based loan-fund focus is text-derived; it shows what the organization *describes*, not dollar portfolio
  shares. Expense-weighted program descriptions are the strongest signal; SDL/CMF/NMTC awards and names are weak.
* Credit-union microenterprise lending, housing development and community facilities are not observable in the 5300.
* Bank "microenterprise" is a size proxy (C&I loans with original amount ≤ $100K).
* 81 credit unions (mostly Puerto Rico cooperativas) and 16 banks/BHCs have no current regulatory data and are unclassified.
"""


def main() -> None:
    m = pd.read_csv(PROCESSED / "cdfi_master.csv", low_memory=False)
    new_cols = ["nondep_total_assets_usd", "nondep_assets_source", "size_tier_group", "size_tier", "size_tier_basis",
                "size_tier_code", "size_metric_usd", "size_percentile_within_type", "member_tier", "loan_portfolio_tier",
                "market_segment_code", "market_segment", "market_segment_rule", "market_subsegment", "segment_confidence",
                "segment_memberships", "n_segment_memberships", "multi_focus"]
    m = m.drop(columns=[c for c in new_cols if c in m.columns])
    for c in [c for c in m.columns if c.endswith("_flag")] + ["sba_microloan_intermediary"]:
        m[c] = m[c].map(lambda v: True if v in (True, "True") else (False if v in (False, "False") else pd.NA))
    m = segments(size_tiers(m))
    m.to_csv(PROCESSED / "cdfi_master.csv", index=False)
    try:
        m.to_parquet(PROCESSED / "cdfi_master.parquet", index=False)
    except Exception:
        pass
    seg_cols = ["cdfi_id", "cdfi_name", "institution_type", "hq_state", "native_cdfi", "focus_basis", "primary_lending_focus",
                "secondary_lending_focus", "tertiary_lending_focus", "primary_focus_confidence", "meaningful_lending_activities",
                "primary_borrower_type", "market_segment_code", "market_segment", "market_subsegment", "market_segment_rule",
                "segment_confidence", "segment_memberships", "multi_focus", "size_tier_group", "size_tier", "size_metric_usd",
                "size_percentile_within_type", "member_tier", "loan_portfolio_tier", "include_in_market_totals"]
    m[seg_cols].to_csv(PROCESSED / "cdfi_segments.csv", index=False)
    st = segment_stats(m)
    TABLES.mkdir(parents=True, exist_ok=True)
    for k, v in st.items():
        v.to_csv(TABLES / f"{k}.csv", index=False)
    (RESEARCH / "market_structure_report.md").write_text(report(m, st))
    print(m.groupby(["market_segment_code"]).size().to_string())
    print("wrote cdfi_segments.csv, segment tables and research/market_structure_report.md")


if __name__ == "__main__":
    main()

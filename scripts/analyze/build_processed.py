"""Assemble processed, analysis-ready tables from normalized sources and the crosswalk.

Outputs (data/processed/, CSV + Parquet):
  cdfi_financials.csv  one row per CDFI x reporting date (scale variables; banks, BHCs, CUs, + IRS BMF for loan funds)
  cdfi_lending.csv     normalized lending table: CDFI x reporting date x source category
  cdfi_geography.csv   HQ geography + branch footprint (depositories); service area left missing where not public
  cdfi_master.csv      one row per certified CDFI with identifiers, latest scale, lending shares, derived
                       focus fields, award summary and coverage flags
  state_summary.csv    certified CDFIs by HQ state and type, with population and per-capita counts

Conventions
  * Reported values keep their source names/periods; derived fields are listed in research/data_dictionary.md.
  * BHC financials/lending = sum over FDIC-insured subsidiary banks matched with high confidence
    (financial_scope = 'sum_of_fdic_insured_subsidiaries'). Where those subsidiaries are themselves
    certified CDFIs, the BHC row is flagged include_in_market_totals = False to avoid double counting.
  * Nothing is imputed: a missing source value stays missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, PROCESSED, RAW, latest_dated_dir, read_manifest  # noqa: E402

FOCUS_THRESHOLD = 10.0  # % of loans for a lending flag
STD_ORDER = ["consumer", "mortgage_homeownership", "microenterprise", "small_business", "commercial_business",
             "commercial_real_estate", "residential_housing_development", "community_facilities", "intermediary_finance",
             "venture_equity", "agriculture", "other"]
NOT_OBSERVED = {"NCUA": ["microenterprise", "residential_housing_development", "agriculture", "community_facilities",
                         "intermediary_finance", "venture_equity"],
                "FDIC": ["community_facilities", "venture_equity"]}
BORROWER_TYPES = {"individual": ["consumer", "mortgage_homeownership"],
                  "business": ["microenterprise", "small_business", "commercial_business", "agriculture"],
                  "property_project": ["commercial_real_estate", "residential_housing_development", "community_facilities"],
                  "financial_other": ["intermediary_finance", "venture_equity", "other"]}
FLAG_CATEGORIES = ["consumer", "mortgage_homeownership", "microenterprise", "small_business", "commercial_business",
                   "commercial_real_estate", "residential_housing_development", "community_facilities",
                   "intermediary_finance", "venture_equity", "agriculture"]
FLAG_NAME = {"consumer": "consumer_lending_flag", "mortgage_homeownership": "mortgage_lending_flag",
             "microenterprise": "microenterprise_flag", "small_business": "small_business_flag",
             "commercial_business": "commercial_business_flag", "commercial_real_estate": "commercial_real_estate_flag",
             "residential_housing_development": "housing_development_flag", "community_facilities": "community_facilities_flag",
             "intermediary_finance": "intermediary_finance_flag", "venture_equity": "venture_flag", "agriculture": "agriculture_flag"}
NEAR_TIE_PP = 5.0
NONDEP = ["Loan Fund", "Venture Capital Fund"]
FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
    "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
    "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY", "72": "PR",
}


def save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(PROCESSED / f"{name}.csv", index=False)
    try:
        df.to_parquet(PROCESSED / f"{name}.parquet", index=False)
    except Exception as e:  # pragma: no cover
        print(f"  (parquet skipped for {name}: {e})")
    print(f"  {name}: {len(df):,} rows")


def latest(pattern: str, folder: Path) -> list[Path]:
    return sorted(folder.glob(pattern))


# ---------------------------------------------------------------------------
def load():
    t = pd.read_csv(INTERIM / "normalized_treasury" / "treasury_cert_list.csv",
                    dtype={"hq_zip5": str, "hq_zip4": str, "rssd_id": "Int64"})
    xw = pd.read_csv(PROCESSED / "cdfi_crosswalk.csv", dtype={"id_value": str})
    return t, xw


def depository_links(xw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """cdfi_id -> FDIC certs / NCUA charters whose financials are attributed to the CDFI."""
    fd = xw[(xw.id_system == "FDIC_CERT") & xw.relationship.isin(["self", "subsidiary_bank"])
            & xw.match_confidence.isin(["high", "medium"])].copy()
    # A 'self' row from a stale (inactive) institution has match_confidence low and is excluded above.
    fd["fdic_cert"] = fd.id_value.astype(int)
    cu = xw[(xw.id_system == "NCUA_CHARTER") & (xw.relationship == "self") & xw.match_confidence.isin(["high", "medium"])].copy()
    cu["ncua_charter"] = cu.id_value.astype(int)
    return fd[["cdfi_id", "fdic_cert", "relationship", "match_method", "match_confidence"]], \
        cu[["cdfi_id", "ncua_charter", "match_method", "match_confidence"]]


def build_financials(t, fd, cu) -> pd.DataFrame:
    out = []
    for f in latest("fdic_financials_*.csv", INTERIM / "normalized_fdic"):
        fin = pd.read_csv(f)
        m = fd.merge(fin, on="fdic_cert", how="inner")
        num = ["total_assets_usd", "total_deposits_usd", "total_equity_usd", "net_income_ytd_usd", "total_loans_usd",
               "total_loans_gross_usd", "full_time_employees", "domestic_offices_call_report"]
        g = m.groupby("cdfi_id")
        agg = g[num].sum(min_count=1)
        agg["n_entities"] = g.size()
        agg["entity_ids"] = g.fdic_cert.apply(lambda s: ";".join(map(str, sorted(s))))
        agg["financial_scope"] = g.relationship.first().map({"self": "institution", "subsidiary_bank": "sum_of_fdic_insured_subsidiaries"})
        agg["reporting_date"] = m.reporting_date.iloc[0]
        agg["source"] = "FDIC Call Report via BankFind API"
        agg["retrieval_date"] = m.retrieval_date.iloc[0]
        out.append(agg.reset_index())
    for f in latest("ncua_financials_*.csv", INTERIM / "normalized_ncua"):
        fin = pd.read_csv(f)
        m = cu.merge(fin, on="ncua_charter", how="inner")
        m = m.rename(columns={"total_shares_and_deposits_usd": "total_deposits_usd"})
        m["n_entities"] = 1
        m["entity_ids"] = m.ncua_charter.astype(str)
        m["financial_scope"] = "institution"
        out.append(m.drop(columns=["ncua_charter", "match_method", "match_confidence"]))
    fin = pd.concat(out, ignore_index=True)
    fin = fin.merge(t[["cdfi_id", "institution_type"]], on="cdfi_id")
    cols = ["cdfi_id", "institution_type", "reporting_date", "source", "financial_scope", "n_entities", "entity_ids",
            "total_assets_usd", "total_loans_usd", "total_loans_gross_usd", "total_loan_count", "total_deposits_usd",
            "total_equity_usd", "net_income_ytd_usd", "members", "full_time_employees", "domestic_offices_call_report",
            "retrieval_date"]
    return fin.reindex(columns=cols).sort_values(["cdfi_id", "reporting_date"])


def irs_bmf_financials(t, xw) -> pd.DataFrame:
    ein = xw[(xw.id_system == "EIN") & xw.id_value.notna()][["cdfi_id", "id_value", "match_confidence"]]
    d = latest_dated_dir(RAW / "other" / "irs_eo_bmf")
    parts = []
    for f in d.glob("eo_*.csv"):
        b = pd.read_csv(f, dtype=str, usecols=["EIN", "TAX_PERIOD", "ASSET_AMT", "REVENUE_AMT", "INCOME_AMT", "NTEE_CD", "SUBSECTION"])
        parts.append(b[b.EIN.isin(ein.id_value)])
    b = pd.concat(parts).drop_duplicates("EIN")
    m = ein.merge(b, left_on="id_value", right_on="EIN")
    return pd.DataFrame({
        "cdfi_id": m.cdfi_id, "ein": m.EIN, "ein_match_confidence": m.match_confidence,
        "irs_total_assets_usd": pd.to_numeric(m.ASSET_AMT, errors="coerce"),
        "irs_total_revenue_usd": pd.to_numeric(m.REVENUE_AMT, errors="coerce"),
        "irs_tax_period": m.TAX_PERIOD, "irs_ntee_code": m.NTEE_CD, "irs_subsection": m.SUBSECTION,
        "irs_source": f"IRS EO BMF extract (retrieved {d.name}); amounts from latest return on file",
    })


def build_lending(t, fd, cu) -> pd.DataFrame:
    out = []
    for f in latest("fdic_lending_long_*.csv", INTERIM / "normalized_fdic"):
        ln = pd.read_csv(f, low_memory=False)
        m = fd.merge(ln, on="fdic_cert", how="inner")
        keys = ["cdfi_id", "reporting_date", "source", "source_field", "source_count_field", "source_category",
                "standardized_category", "standardized_subcategory", "additive"]
        g = m.groupby(keys, dropna=False)
        agg = g[["loan_balance_usd", "loan_count"]].sum(min_count=1).reset_index()
        agg["entity_ids"] = g.fdic_cert.apply(lambda s: ";".join(map(str, sorted(s)))).values
        out.append(agg)
    for f in latest("ncua_lending_long_*.csv", INTERIM / "normalized_ncua"):
        ln = pd.read_csv(f, low_memory=False)
        m = cu.merge(ln, on="ncua_charter", how="inner")
        m["entity_ids"] = m.ncua_charter.astype(str)
        out.append(m.drop(columns=["ncua_charter", "match_method", "match_confidence", "percent_of_total_loans",
                                   "denominator", "notes", "retrieval_date"]))
    lend = pd.concat(out, ignore_index=True)
    denom = lend[lend.additive].groupby(["cdfi_id", "reporting_date"]).loan_balance_usd.sum(min_count=1)
    lend["percent_of_total_loans"] = lend.loan_balance_usd / pd.MultiIndex.from_frame(lend[["cdfi_id", "reporting_date"]]).map(denom.to_dict().get).astype(float) * 100
    lend.loc[~np.isfinite(lend.percent_of_total_loans), "percent_of_total_loans"] = np.nan
    lend["notes"] = np.where(lend.additive, "", "memo item: overlaps additive categories; not additive")
    return lend.sort_values(["cdfi_id", "reporting_date", "additive", "standardized_category"], ascending=[True, True, False, True])


def focus_fields(lend: pd.DataFrame, rep: dict[str, str]) -> pd.DataFrame:
    """Portfolio-based lending-focus fields for banks, BHCs and credit unions (latest Call Report).

    Shares are of total loans. Categories a regulator does not report separately stay MISSING (not 0):
      credit unions: microenterprise, residential_housing_development, agriculture, community_facilities,
                     intermediary_finance, venture_equity
      banks:         community_facilities, venture_equity; intermediary_finance only where LNNDEPC is reported
    """
    l = lend[lend.apply(lambda r: r.reporting_date == rep.get(r.source.split()[0]), axis=1)]
    add = l[l.additive]
    shares = add.groupby(["cdfi_id", "standardized_category"]).percent_of_total_loans.sum(min_count=1).unstack()
    shares = shares.reindex(columns=STD_ORDER)
    is_fdic = l.groupby("cdfi_id").source.first().str.startswith("FDIC").reindex(shares.index)
    # NCUA: every observed category is exhaustive (the 13 5300 lines sum to total loans), so a missing
    # (cdfi, category) pair - e.g. commercial_business when ACCT_400P was not reclassified - is a true zero.
    ncua_observed = [c for c in STD_ORDER if c not in NOT_OBSERVED["NCUA"]]
    shares.loc[~is_fdic, ncua_observed] = shares.loc[~is_fdic, ncua_observed].fillna(0)
    for c in NOT_OBSERVED["NCUA"]:
        shares.loc[~is_fdic, c] = np.nan
    for c in NOT_OBSERVED["FDIC"]:
        shares.loc[is_fdic, c] = np.nan
    res = pd.DataFrame(index=shares.index)
    for c in STD_ORDER:
        res[f"share_{c}_pct"] = shares[c].round(2)
    ranked = {i: shares.loc[i].drop("other").dropna().sort_values(ascending=False) for i in shares.index}
    ranked = {i: s[s > 0] for i, s in ranked.items()}
    res["primary_lending_focus"] = [s.index[0] if len(s) else pd.NA for s in ranked.values()]
    res["secondary_lending_focus"] = [s.index[1] if len(s) > 1 and s.iloc[1] >= FOCUS_THRESHOLD else pd.NA for s in ranked.values()]
    res["tertiary_lending_focus"] = [s.index[2] if len(s) > 2 and s.iloc[2] >= FOCUS_THRESHOLD else pd.NA for s in ranked.values()]
    top = pd.Series([s.iloc[0] if len(s) else np.nan for s in ranked.values()], index=shares.index)
    gap = pd.Series([s.iloc[0] - s.iloc[1] if len(s) > 1 else np.nan for s in ranked.values()], index=shares.index)
    res["primary_focus_share_pct"] = top.round(2)
    res["primary_focus_margin_pp"] = gap.round(2)
    res["primary_focus_near_tie"] = gap < NEAR_TIE_PP
    res["portfolio_concentration"] = np.select([top >= 50, top >= 30], ["specialized (>=50%)", "focused (30-50%)"], "diversified (<30%)")
    res.loc[top.isna(), "portfolio_concentration"] = pd.NA
    res["primary_focus_confidence"] = np.select([(top >= 50), (top >= 30) & (gap >= NEAR_TIE_PP)], ["HIGH", "MEDIUM"], "LOW")
    res.loc[top.isna(), "primary_focus_confidence"] = pd.NA
    res["primary_focus_source"] = is_fdic.map({True: "FDIC Call Report Schedule RC-C (incl. Part II)", False: "NCUA 5300 Call Report"})
    res["primary_focus_method"] = "portfolio: largest standardized category share of total loans (other excluded)"
    res["focus_reporting_date"] = l.groupby("cdfi_id").reporting_date.first()
    res["meaningful_lending_activities"] = [";".join(s[s >= FOCUS_THRESHOLD].index) for s in ranked.values()]
    res["n_meaningful_activities"] = [int((s >= FOCUS_THRESHOLD).sum()) for s in ranked.values()]
    # Borrower-type rollup (who repays): individuals vs operating businesses vs property/project cash flows.
    for bt, cats in BORROWER_TYPES.items():
        res[f"share_{bt}_borrowers_pct"] = shares[cats].sum(axis=1, min_count=1).round(2)
    bt_cols = [f"share_{bt}_borrowers_pct" for bt in BORROWER_TYPES if bt != "financial_other"]
    res["primary_borrower_type"] = res[bt_cols].idxmax(axis=1).str.replace("share_", "").str.replace("_borrowers_pct", "")
    # Flags: meaningful activity = share >= threshold; missing where not observable.
    for c in FLAG_CATEGORIES:
        res[FLAG_NAME[c]] = (shares[c] >= FOCUS_THRESHOLD).where(shares[c].notna())
    # Regulatory small-business measure (banks): C&I + nonfarm-nonres RE with original amount <= $1MM. Overlaps CRE.
    memo = l[l.source_field.isin(["LNCI4", "LNRENR4"])].groupby("cdfi_id").loan_balance_usd.sum(min_count=1)
    gross = add.groupby("cdfi_id").loan_balance_usd.sum(min_count=1)
    res["small_business_exposure_pct"] = (memo / gross * 100).round(2).reindex(res.index)
    sbn = l[l.source_count_field.isin(["LNCI4N", "LNRENR4N"])].groupby("cdfi_id").loan_count.sum(min_count=1)
    res["small_business_loan_count_banks"] = sbn.reindex(res.index)
    res["consumer_exposure_pct"] = res["share_consumer_pct"]
    res["consumer_share"] = res["share_consumer_pct"]
    res["mortgage_share"] = res["share_mortgage_homeownership_pct"]
    res["small_business_share"] = res[["share_microenterprise_pct", "share_small_business_pct"]].sum(axis=1, min_count=1)
    res["commercial_share"] = res["share_commercial_business_pct"]
    res["cre_share"] = res["share_commercial_real_estate_pct"]
    def sub_share(sub):
        return l[l.standardized_subcategory.isin(sub)].groupby("cdfi_id").percent_of_total_loans.sum(min_count=1).reindex(res.index).round(2)
    res["auto_loan_share_pct"] = sub_share(["auto", "auto_new", "auto_used"])
    res["credit_card_share_pct"] = sub_share(["credit_card"])
    res["unsecured_consumer_share_pct"] = sub_share(["other_unsecured", "payday_alternative", "student"])  # NCUA only
    res.loc[is_fdic.fillna(False), "unsecured_consumer_share_pct"] = np.nan
    res["focus_basis"] = "portfolio"
    return res.reset_index()


def evidence_focus(t: pd.DataFrame) -> pd.DataFrame:
    """Evidence-based focus for loan funds / VC funds, plus program-list flags for every CDFI."""
    p_cls, p_sc = PROCESSED / "loan_fund_classification.csv", PROCESSED / "cdfi_focus_category_scores.csv"
    if not p_cls.exists():
        return pd.DataFrame(columns=["cdfi_id"])
    c = pd.read_csv(p_cls).set_index("cdfi_id")
    sc = pd.read_csv(p_sc)
    ev = pd.read_csv(PROCESSED / "cdfi_focus_evidence.csv", usecols=["cdfi_id", "evidence_type", "evidence_source"])
    out = pd.DataFrame(index=t.cdfi_id)
    nd = t.set_index("cdfi_id").institution_type.isin(NONDEP)
    lists = ev[ev.evidence_type == "program_list"].groupby("cdfi_id").evidence_source.apply(set)
    out["sba_microloan_intermediary"] = out.index.map(lambda i: "SBA Microloan intermediary" in lists.get(i, set()))
    out["sba_community_advantage_lender"] = out.index.map(lambda i: "SBA Community Advantage SBLC" in lists.get(i, set()))
    out["fhlb_member_cdfi_type"] = out.index.map(lambda i: any(x.startswith("FHLB") for x in lists.get(i, set())))
    out["fhlb_member_cdfi_type"] = out["fhlb_member_cdfi_type"].astype("object")
    out.loc[~nd, "fhlb_member_cdfi_type"] = pd.NA  # depository FHLB membership is routine; not evidence
    med = sc[sc.confidence.isin(["HIGH", "MEDIUM"])]
    for col in ["loan_fund_focus_1", "loan_fund_focus_1_confidence", "loan_fund_focus_2", "loan_fund_focus_2_confidence",
                "loan_fund_focus_3", "loan_fund_focus_3_confidence", "classification_source", "classification_evidence",
                "classification_confidence", "meaningful_activities", "all_evidenced_activities",
                "notes_loans_receivable_eoy_usd", "irs_990_total_assets_eoy_usd", "loans_receivable_share_of_assets_pct",
                "program_related_investments_eoy_usd", "irs_990_tax_period_end", "has_irs_990"]:
        out[col] = c[col].reindex(out.index) if col in c else pd.NA
    for cat in FLAG_CATEGORIES:
        hit = set(med[med.category == cat].cdfi_id)
        # evidence-based flags: True where evidence is MEDIUM/HIGH; otherwise unknown (never inferred False)
        out[f"ev_{FLAG_NAME[cat]}"] = [True if i in hit else pd.NA for i in out.index]
    return out.reset_index()


def build_geography(t, fd, cu) -> pd.DataFrame:
    fb = pd.read_csv(INTERIM / "normalized_fdic" / "fdic_branch_summary.csv", dtype={"branch_county_fips": str})
    nb = pd.read_csv(sorted((INTERIM / "normalized_ncua").glob("ncua_branch_summary_*.csv"))[-1])
    fdi = pd.read_csv(INTERIM / "normalized_fdic" / "fdic_institutions.csv", dtype={"STCNTY": str, "CERT": "Int64"}, low_memory=False)
    foicu = pd.read_csv(sorted((INTERIM / "normalized_ncua").glob("ncua_foicu_*.csv"))[-1], dtype={"hq_county_fips": str})

    # Depository branch footprints, aggregated across subsidiaries for BHCs.
    loc = pd.read_csv(latest_dated_dir(RAW / "fdic") / "locations.csv", dtype={"STCNTY": str, "CERT": "Int64", "ZIP": str},
                      usecols=["CERT", "STALP", "STCNTY"])
    fl = fd.merge(loc, left_on="fdic_cert", right_on="CERT")
    g = fl.groupby("cdfi_id")
    fgeo = pd.DataFrame({"branch_count": g.size(), "branch_states": g.STALP.apply(lambda s: ";".join(sorted(s.dropna().unique()))),
                         "number_states_branches": g.STALP.nunique(), "number_counties_branches": g.STCNTY.nunique(),
                         "branch_source": "FDIC BankFind locations"})
    cgeo = cu.merge(nb, on="ncua_charter").set_index("cdfi_id")
    cgeo = pd.DataFrame({"branch_count": cgeo.ncua_site_count, "branch_states": cgeo.branch_states,
                         "number_states_branches": cgeo.branch_state_count, "number_counties_branches": cgeo.branch_county_count,
                         "branch_source": "NCUA Credit Union Branch Information"})
    geo = pd.concat([fgeo, cgeo])

    hq_cnty = pd.concat([
        fd[fd.relationship == "self"].merge(fdi[["CERT", "STCNTY", "COUNTY", "LATITUDE", "LONGITUDE"]], left_on="fdic_cert", right_on="CERT")
          .set_index("cdfi_id")[["STCNTY", "COUNTY", "LATITUDE", "LONGITUDE"]]
          .rename(columns={"STCNTY": "hq_county_fips", "COUNTY": "hq_county_name", "LATITUDE": "latitude", "LONGITUDE": "longitude"})
          .assign(hq_geo_source="FDIC institution record"),
        cu.merge(foicu[["ncua_charter", "hq_county_fips"]], on="ncua_charter").set_index("cdfi_id")[["hq_county_fips"]]
          .assign(hq_geo_source="NCUA FOICU county code"),
    ])
    hq_cnty = hq_cnty[~hq_cnty.index.duplicated()]

    out = t[["cdfi_id", "cdfi_name", "institution_type", "hq_address", "hq_city", "hq_state", "hq_zip5"]].set_index("cdfi_id")
    out = out.join(hq_cnty).join(geo)
    def classify(r):
        if pd.isna(r.number_states_branches):
            return pd.NA
        if r.number_states_branches > 1:
            return "multistate (branch footprint)"
        if r.number_counties_branches <= 1:
            return "single county (branch footprint)"
        return "multi-county, single state (branch footprint)"
    out["branch_footprint_class"] = out.apply(classify, axis=1)
    out["service_area_states"] = pd.NA
    out["service_area_counties"] = pd.NA
    out["service_area_type"] = pd.NA
    out["service_area_note"] = ("CDFI Fund target-market/service-area data is collected (certification application, ACR) "
                                "but not publicly released; branch footprint is NOT a service area")
    out["lending_geography_note"] = "not available at institution level from public sources (CDFI Fund TLR is anonymized)"
    return out.reset_index()


def award_summary(t) -> pd.DataFrame:
    a = pd.read_csv(PROCESSED / "cdfi_awards.csv")
    a = a[a.cdfi_id.notna()]
    g = a[a.counts_toward_grant_total].groupby("cdfi_id")
    s = pd.DataFrame({
        "award_count": a.groupby("cdfi_id").size(),
        "grant_award_count": g.size(),
        "total_cdfi_fund_awards_usd": g.award_amount_usd.sum(),
        "first_award_year": a.groupby("cdfi_id").award_year.min(),
        "latest_award_year": a.groupby("cdfi_id").award_year.max(),
        "years_with_awards": a.groupby("cdfi_id").award_year.nunique(),
        "award_programs": a.groupby("cdfi_id").award_program.apply(lambda s: ";".join(sorted(s.unique()))),
        "nmtc_allocation_total_usd": a[a.award_program == "NMTC"].groupby("cdfi_id").award_amount_usd.sum(),
        "cdfi_fa_award_count": a[a.award_program.isin(["CDFI-FA", "NACA-FA"])].groupby("cdfi_id").size(),
    })
    last = a.sort_values(["award_year", "award_amount_usd"]).groupby("cdfi_id").tail(1).set_index("cdfi_id")
    s["latest_award_program"] = last.award_program
    s["latest_award_amount_usd"] = last.award_amount_usd
    s["award_link_min_confidence"] = a.groupby("cdfi_id").award_match_confidence.agg(
        lambda x: "low" if (x == "low").any() else ("medium" if (x == "medium").any() else "high"))
    s = s.reindex(t.cdfi_id)
    s.index.name = "cdfi_id"
    for c in ["award_count", "grant_award_count", "years_with_awards", "cdfi_fa_award_count"]:
        s[c] = s[c].fillna(0).astype(int)  # zero = no award linked (not necessarily none received)
    return s.reset_index()


def state_summary(t: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    pf = sorted((RAW / "census" / "popest").glob("NST-EST*-ALLDATA.csv"))[-1]
    vint = pf.stem.split("-")[1].replace("EST", "")
    p = pd.read_csv(pf, dtype={"STATE": str})
    p = p[p.SUMLEV.astype(str) == "40"]
    pop = pd.Series(p[f"POPESTIMATE{vint}"].values, index=p.STATE.str.zfill(2).map(FIPS_TO_STATE))
    ct = pd.crosstab(t.hq_state, t.institution_type)
    ct.columns = ["n_" + c.lower().replace(" ", "_") for c in ct.columns]
    ct["n_certified_cdfis"] = ct.sum(axis=1)
    ct["n_native_cdfis"] = t.groupby("hq_state").native_cdfi.sum()
    ct[f"population_{vint}"] = pop.reindex(ct.index)
    ct["cdfis_per_million_residents"] = (ct.n_certified_cdfis / ct[f"population_{vint}"] * 1e6).round(2)
    inc = master[master.include_in_market_totals & master.total_assets_usd.notna()]
    ct["depository_cdfi_assets_usd"] = inc[inc.institution_type.isin(["Bank or Thrift", "Bank Holding Company", "Credit Union"])].groupby("hq_state").total_assets_usd.sum().reindex(ct.index)
    ct["credit_union_cdfi_members"] = master[master.institution_type == "Credit Union"].groupby("hq_state").members.sum(min_count=1).reindex(ct.index)
    ct["population_source"] = f"Census Bureau Vintage {vint} state population estimates (NST-EST{vint})"
    ct["geography_basis"] = "headquarters state (not service area)"
    return ct.reset_index().rename(columns={"hq_state": "state"}).sort_values("n_certified_cdfis", ascending=False)


def main() -> None:
    t, xw = load()
    fd, cu = depository_links(xw)
    print("Building processed tables")
    fin = build_financials(t, fd, cu)
    lend = build_lending(t, fd, cu)
    rep = {"FDIC": fin[fin.source.str.startswith("FDIC")].reporting_date.max(),
           "NCUA": fin[fin.source.str.startswith("NCUA")].reporting_date.max()}
    if rep["FDIC"] != rep["NCUA"]:
        print(f"  NOTE: latest FDIC ({rep['FDIC']}) and NCUA ({rep['NCUA']}) reporting dates differ")
    focus = focus_fields(lend, rep)
    geo = build_geography(t, fd, cu)
    irs = irs_bmf_financials(t, xw)
    aw = award_summary(t)

    # Latest and prior-year scale
    cur = fin[fin.reporting_date == fin.source.str.split().str[0].map(rep)].set_index("cdfi_id")
    prev = fin[fin.reporting_date != fin.source.str.split().str[0].map(rep)].set_index("cdfi_id")
    same_entities = cur.entity_ids.reindex(prev.index) == prev.entity_ids
    def growth(col):
        g = (cur[col] / prev[col].where(same_entities).reindex(cur.index) - 1) * 100
        return g.where(np.isfinite(g)).round(2)

    ids = xw.pivot_table(index="cdfi_id", columns="id_system", values="id_value",
                         aggfunc=lambda s: ";".join(sorted(set(s))))
    ids_self = xw[xw.relationship == "self"].pivot_table(index="cdfi_id", columns="id_system", values="id_value",
                                                           aggfunc=lambda s: ";".join(sorted(set(s))))
    review = xw.groupby("cdfi_id").manual_review_required.any()
    related = xw.groupby("cdfi_id").related_certified_cdfi_id.apply(lambda s: ";".join(sorted(set(s.dropna()))) or pd.NA)
    fdic_inst = pd.read_csv(INTERIM / "normalized_fdic" / "fdic_institutions.csv", low_memory=False, dtype={"CERT": "Int64"})
    spec = fd[fd.relationship == "self"].merge(fdic_inst[["CERT", "SPECGRPN", "MDI_STATUS_DESC"]], left_on="fdic_cert", right_on="CERT").set_index("cdfi_id")
    foicu = pd.read_csv(sorted((INTERIM / "normalized_ncua").glob("ncua_foicu_*.csv"))[-1])
    cuattr = cu.merge(foicu[["ncua_charter", "low_income_designation", "is_mdi"]], on="ncua_charter").set_index("cdfi_id")

    m = t[["cdfi_id", "cdfi_name", "cdfi_name_as_listed", "institution_type", "institution_type_as_listed", "native_cdfi",
           "certification_status", "hq_address", "hq_city", "hq_state", "hq_zip5", "hq_zip4", "website", "website_domain",
           "rssd_id", "source", "source_file", "source_as_of_date", "retrieval_date", "id_assignment_method",
           "dup_rssd_in_list", "shares_website_with"]].set_index("cdfi_id")
    m["certification_date"] = pd.NA  # not published by the CDFI Fund
    m["fdic_cert"] = ids_self.get("FDIC_CERT")
    m["fdic_cert_subsidiaries"] = xw[(xw.id_system == "FDIC_CERT") & (xw.relationship == "subsidiary_bank")].groupby("cdfi_id").id_value.apply(lambda s: ";".join(sorted(set(s))))
    m["ncua_charter"] = ids_self.get("NCUA_CHARTER")
    m["lei"] = ids.get("LEI")
    m["ein"] = ids_self.get("EIN")
    m["regulator_match_status"] = np.select(
        [m.index.isin(cur.index)],
        ["matched_with_current_financials"], default="no_current_regulatory_financials")
    m["crosswalk_review_required"] = review.reindex(m.index).fillna(False)
    m["related_certified_cdfi_ids"] = related.reindex(m.index)
    m["fdic_specialization_group"] = spec.SPECGRPN.reindex(m.index)
    m["mdi_status"] = spec.MDI_STATUS_DESC.reindex(m.index)
    m["ncua_low_income_designation"] = cuattr.low_income_designation.reindex(m.index)
    m["ncua_mdi"] = cuattr.is_mdi.reindex(m.index)

    for c in ["reporting_date", "financial_scope", "n_entities", "total_assets_usd", "total_loans_usd", "total_loan_count",
              "total_deposits_usd", "total_equity_usd", "net_income_ytd_usd", "members", "full_time_employees"]:
        m[c if c != "reporting_date" else "financials_reporting_date"] = cur[c].reindex(m.index)
    m["financials_source"] = cur.source.reindex(m.index)
    m["asset_growth_1y_pct"] = growth("total_assets_usd").reindex(m.index)
    m["loan_growth_1y_pct"] = growth("total_loans_usd").reindex(m.index)
    m["membership_growth_1y_pct"] = growth("members").reindex(m.index)

    # Double counting guard for market totals.
    bhc_all_sub_certified = xw[(xw.relationship == "subsidiary_bank") & (xw.id_system == "FDIC_CERT")].groupby("cdfi_id").related_certified_cdfi_id.apply(lambda s: s.notna().all())
    m["include_in_market_totals"] = ~(m.institution_type.eq("Bank Holding Company") & bhc_all_sub_certified.reindex(m.index).fillna(False).astype(bool))
    m["market_totals_note"] = np.where(m.include_in_market_totals, "", "BHC whose FDIC-insured subsidiaries are all separately certified; exclude from sums")

    irs = irs.set_index("cdfi_id")
    for c in ["irs_total_assets_usd", "irs_total_revenue_usd", "irs_tax_period", "irs_ntee_code", "irs_subsection", "irs_source"]:
        m[c] = irs[c].reindex(m.index)
    m.loc[m.institution_type.isin(["Bank or Thrift", "Bank Holding Company", "Credit Union"]), [
        "irs_total_assets_usd", "irs_total_revenue_usd"]] = np.nan

    # Borrower reach proxy
    m["borrower_reach_value"] = np.where(m.members.notna(), m.members, np.nan)
    m["borrower_reach_proxy"] = np.where(m.members.notna(), "NCUA members (ACCT_083)", pd.NA)
    m["loan_count_value"] = m.total_loan_count
    m["loan_count_proxy"] = np.where(m.total_loan_count.notna(), "NCUA total number of loans and leases (ACCT_025A)", pd.NA)

    f = focus.set_index("cdfi_id")
    for c in f.columns:
        m[c] = f[c].reindex(m.index)
    # Evidence-based focus (loan funds / VC funds) and program-list flags (all types)
    e = evidence_focus(t).set_index("cdfi_id")
    for c in e.columns:
        if not c.startswith("ev_"):
            m[c] = e[c].reindex(m.index)
    nd = m.institution_type.isin(NONDEP)
    has_cls = nd & m.loan_fund_focus_1.notna()
    m.loc[has_cls, "primary_lending_focus"] = m.loc[has_cls, "loan_fund_focus_1"]
    m.loc[has_cls, "secondary_lending_focus"] = m.loc[has_cls, "loan_fund_focus_2"]
    m.loc[has_cls, "tertiary_lending_focus"] = m.loc[has_cls, "loan_fund_focus_3"]
    m.loc[has_cls, "primary_focus_confidence"] = m.loc[has_cls, "loan_fund_focus_1_confidence"]
    m.loc[has_cls, "primary_focus_source"] = m.loc[has_cls, "classification_source"]
    m.loc[has_cls, "primary_focus_method"] = "evidence: 990 program text weighted by program expense + mission text + program lists + awards"
    m.loc[has_cls, "meaningful_lending_activities"] = m.loc[has_cls, "meaningful_activities"]
    m.loc[has_cls, "n_meaningful_activities"] = m.loc[has_cls, "meaningful_activities"].fillna("").map(lambda x: len([y for y in x.split(";") if y]))
    m.loc[has_cls, "focus_basis"] = "evidence"
    m.loc[nd & ~has_cls, "primary_focus_confidence"] = "UNKNOWN"
    m.loc[nd & ~has_cls, "primary_focus_method"] = "not classified: no usable public evidence"
    m.loc[nd & ~has_cls, "focus_basis"] = "none"
    m.loc[~nd & m.primary_lending_focus.isna(), "primary_focus_method"] = "not available: no current regulatory loan data matched"
    m.loc[~nd & m.primary_lending_focus.isna(), "focus_basis"] = "none"
    for cat, flag in FLAG_NAME.items():
        evf = e[f"ev_{flag}"].reindex(m.index)
        if flag not in m:
            m[flag] = pd.NA
        m[flag] = m[flag].astype("object")
        m.loc[nd, flag] = evf[nd]  # evidence-based: True or unknown
        # Depositories: program-list evidence can add microenterprise / small-business participation
        if flag in ("microenterprise_flag", "small_business_flag"):
            m.loc[~nd & (evf == True), flag] = True  # noqa: E712
    m["primary_focus_basis_note"] = np.select(
        [m.focus_basis.eq("portfolio"), m.focus_basis.eq("evidence")],
        ["regulatory loan balances (shares sum to 100%)", "text/program evidence (no balances; flags True = evidenced, blank = unknown)"],
        "no classification")

    gg = geo.set_index("cdfi_id")
    for c in ["hq_county_fips", "hq_county_name", "latitude", "longitude", "branch_count", "branch_states",
              "number_states_branches", "number_counties_branches", "branch_footprint_class"]:
        m[c] = gg[c].reindex(m.index)

    a = aw.set_index("cdfi_id")
    for c in a.columns:
        m[c] = a[c].reindex(m.index)

    # Coverage flags
    m["has_assets"] = m.total_assets_usd.notna() | m.irs_total_assets_usd.notna()
    m["has_regulatory_assets"] = m.total_assets_usd.notna()
    m["has_lending_mix"] = m.share_consumer_pct.notna()
    m["has_evidence_classification"] = m.focus_basis.eq("evidence")
    m["has_primary_focus"] = m.primary_lending_focus.notna()

    master = m.reset_index()
    save(master, "cdfi_master")
    save(fin, "cdfi_financials")
    save(lend, "cdfi_lending")
    save(geo, "cdfi_geography")
    save(state_summary(t, master), "state_summary")


if __name__ == "__main__":
    main()

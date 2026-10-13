"""Normalize NCUA 5300 Call Report quarterly data.

Outputs (data/interim/normalized_ncua/):
  ncua_foicu_<YYYY-MM>.csv          credit-union profile (charter number, RSSD, HQ, low-income designation)
  ncua_financials_<YYYY-MM>.csv     one row per charter: assets, loans, shares, members, net income (USD)
  ncua_lending_long_<YYYY-MM>.csv   one row per charter x 5300 loan line (see data/reference/lending_category_map.csv)
  ncua_branch_summary_<YYYY-MM>.csv site count / states / counties per charter

NCUA amounts are reported in whole dollars. Files are cp1252-encoded; account column names are
upper-cased for consistency across quarters.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, RAW, REFERENCE, read_manifest  # noqa: E402

OUT = INTERIM / "normalized_ncua"
SMALL_BUSINESS_AVG_THRESHOLD = 1_000_000
SCALE_ACCOUNTS = {
    "ACCT_010": "total_assets_usd",
    "ACCT_025B": "total_loans_usd",
    "ACCT_025A": "total_loan_count",
    "ACCT_018": "total_shares_and_deposits_usd",
    "ACCT_083": "members",
    "ACCT_661A": "net_income_ytd_usd",
}


def read_txt(path: Path, **kw) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp1252", low_memory=False, **kw)
    df.columns = df.columns.str.upper()
    return df


def load_accounts(ext: Path, accounts: list[str]) -> pd.DataFrame:
    """Collect the requested ACCT_ columns from whichever FS220*.txt file holds them."""
    found: dict[str, str] = {}
    for f in sorted(ext.glob("FS220*.txt")):
        cols = read_txt(f, nrows=0).columns
        for a in accounts:
            if a in cols and a not in found:
                found[a] = f.name
    missing = set(accounts) - set(found)
    if missing:
        raise ValueError(f"NCUA accounts not found in {ext}: {sorted(missing)}")
    parts = []
    for fname in sorted(set(found.values())):
        cols = [a for a in accounts if found[a] == fname]
        parts.append(read_txt(ext / fname, usecols=lambda c: c.upper() in {"CU_NUMBER", *cols}).set_index("CU_NUMBER")[cols])
    return pd.concat(parts, axis=1)


def process_quarter(qdir: Path, mapping: pd.DataFrame) -> None:
    q = qdir.name
    ext = qdir / "extracted"
    man = read_manifest(qdir / f"call-report-data-{q}.zip")
    retrieved = man["retrieved_at"][:10]

    foicu = read_txt(ext / "FOICU.txt", dtype={"RSSD": str, "ZIP_CODE": str})
    rep = pd.to_datetime(foicu["CYCLE_DATE"].iloc[0]).date().isoformat()
    prof = pd.DataFrame({
        "ncua_charter": foicu["CU_NUMBER"].astype("Int64"),
        "rssd_id": pd.to_numeric(foicu["RSSD"], errors="coerce").astype("Int64").where(lambda s: s > 0),
        "cu_name": foicu["CU_NAME"].str.strip(),
        "street": foicu["STREET"].str.strip(),
        "city": foicu["CITY"].str.strip(),
        "state": foicu["STATE"].str.strip(),
        "zip5": foicu["ZIP_CODE"].astype(str).str[:5].str.zfill(5),
        "state_code_fips": foicu["STATE_CODE"],
        "county_code_fips": foicu["COUNTY_CODE"],
        "cu_type": foicu["CU_TYPE"],
        "low_income_designation": foicu["LIMITED_INC"].astype(str).str.strip().eq("1"),
        "is_mdi": foicu["ISMDI"].astype(str).str.lower().eq("true"),
        "year_opened": foicu["YEAR_OPENED"],
        "peer_group": foicu["PEER_GROUP"],
        "reporting_date": rep,
    })
    prof["hq_county_fips"] = (prof.state_code_fips.astype("Int64").astype(str).str.zfill(2)
                              + prof.county_code_fips.astype("Int64").astype(str).str.zfill(3))
    trade = ext / "TradeNames.txt"
    if trade.exists():
        tn = read_txt(trade)
        name_col = "TRADENAME"
        prof["trade_names"] = prof.ncua_charter.map(
            tn.groupby("CU_NUMBER")[name_col].apply(lambda s: ";".join(sorted(s.dropna().astype(str).str.strip().unique()))))

    ncua_map = mapping[mapping.source == "NCUA"]
    amt_cols = ncua_map.source_field_amount.tolist()
    cnt_cols = ncua_map.source_field_count.dropna().tolist()
    acc = load_accounts(ext, list(SCALE_ACCOUNTS) + amt_cols + cnt_cols)

    fin = acc[list(SCALE_ACCOUNTS)].rename(columns=SCALE_ACCOUNTS).reset_index().rename(columns={"CU_NUMBER": "ncua_charter"})
    fin.insert(1, "reporting_date", rep)
    fin["source"] = "NCUA 5300 Call Report quarterly data"
    fin["retrieval_date"] = retrieved

    rows = []
    for _, m in ncua_map.iterrows():
        rows.append(pd.DataFrame({
            "ncua_charter": acc.index, "reporting_date": rep, "source": "NCUA 5300 Call Report",
            "source_field": m.source_field_amount, "source_count_field": m.source_field_count,
            "source_category": m.source_category, "standardized_category": m.standardized_category,
            "standardized_subcategory": m.standardized_subcategory, "additive": m.additive,
            "loan_balance_usd": acc[m.source_field_amount].values, "loan_count": acc[m.source_field_count].values,
        }))
    long = pd.concat(rows, ignore_index=True)
    # Member business loans not secured by RE: no size bands in the 5300. Default mapping is small_business;
    # reclassify to commercial_business where the average balance per loan exceeds the $1M regulatory
    # small-business threshold (see data/reference/lending_category_map.csv).
    biz = long.source_field == "ACCT_400P"
    avg = long.loan_balance_usd / pd.to_numeric(long.loan_count, errors="coerce").where(lambda c: c > 0)
    large = biz & (avg > SMALL_BUSINESS_AVG_THRESHOLD)
    long.loc[large, "standardized_category"] = "commercial_business"
    long.loc[large, "standardized_subcategory"] = "member_commercial_not_re_secured_large_avg"
    long["avg_balance_per_loan_usd"] = avg.round(0)
    total = acc["ACCT_025B"]
    long["percent_of_total_loans"] = long["loan_balance_usd"] / long["ncua_charter"].map(total).where(lambda s: s > 0) * 100
    long["denominator"] = "total loans and leases (ACCT_025B)"
    long["notes"] = pd.NA
    long.loc[large, "notes"] = "reclassified: average balance per commercial non-RE loan > $1M"
    long["retrieval_date"] = retrieved
    resid = total - long.groupby("ncua_charter")["loan_balance_usd"].sum(min_count=1)
    print(f"  {q}: {len(prof):,} credit unions; |sum(lines) - ACCT_025B| > $100: {(resid.abs() > 100).sum()}")

    br = read_txt(ext / "Credit Union Branch Information.txt", dtype={"PHYSICALADDRESSPOSTALCODE": str})
    st = br["PHYSICALADDRESSSTATECODE"].fillna("").astype(str).str.strip()
    county = br["PHYSICALADDRESSCOUNTYNAME2"].fillna("").astype(str).str.strip()
    br["state_key"] = st.where(st != "")
    br["county_key"] = (st + ":" + county).where((st != "") & (county != ""))
    g = br.groupby("CU_NUMBER")
    branches = pd.DataFrame({
        "ncua_site_count": g.size(),
        "branch_states": g["state_key"].apply(lambda s: ";".join(sorted(s.dropna().unique()))),
        "branch_state_count": g["state_key"].nunique(),
        "branch_county_names": g["county_key"].apply(lambda s: ";".join(sorted(s.dropna().unique()))),
        "branch_county_count": g["county_key"].nunique(),
    }).reset_index().rename(columns={"CU_NUMBER": "ncua_charter"})
    branches["branch_source"] = "NCUA Credit Union Branch Information (all site types)"
    branches["reporting_date"] = rep

    OUT.mkdir(parents=True, exist_ok=True)
    prof.to_csv(OUT / f"ncua_foicu_{q}.csv", index=False)
    fin.to_csv(OUT / f"ncua_financials_{q}.csv", index=False)
    long.to_csv(OUT / f"ncua_lending_long_{q}.csv", index=False)
    branches.to_csv(OUT / f"ncua_branch_summary_{q}.csv", index=False)


def main() -> None:
    mapping = pd.read_csv(REFERENCE / "lending_category_map.csv")
    qdirs = sorted(p for p in (RAW / "ncua" / "call_report").iterdir() if (p / "extracted").exists())
    if not qdirs:
        raise FileNotFoundError("Run scripts/download/ncua_call_report.py first")
    print("Normalizing NCUA")
    for qdir in qdirs:
        process_quarter(qdir, mapping)
    print(f"  wrote {OUT}")


if __name__ == "__main__":
    main()

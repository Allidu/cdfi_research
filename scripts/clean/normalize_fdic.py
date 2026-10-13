"""Normalize FDIC BankFind raw downloads.

Outputs (data/interim/normalized_fdic/):
  fdic_institutions.csv          all institutions (active + inactive), identifiers & HQ
  fdic_financials_<REPDTE>.csv   one row per CERT; dollar fields converted to USD
  fdic_lending_long_<REPDTE>.csv one row per CERT x loan category (see data/reference/lending_category_map.csv)
  fdic_branch_summary.csv        office count / states / counties per CERT from the locations file
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, RAW, REFERENCE, latest_dated_dir, read_manifest  # noqa: E402

OUT = INTERIM / "normalized_fdic"
THOUSANDS = 1000  # FDIC financial dollar fields are reported in $ thousands


def latest_raw_dir() -> Path:
    return latest_dated_dir(RAW / "fdic")


def institutions(raw: Path) -> pd.DataFrame:
    df = pd.read_csv(raw / "institutions.csv", dtype={"FED_RSSD": "Int64", "RSSDHCR": "Int64", "CERT": "Int64",
                                                       "ZIP": str, "STCNTY": str, "LEI": str})
    df["retrieval_date"] = read_manifest(raw / "institutions.csv")["retrieved_at"][:10]
    df["RSSDHCR"] = df["RSSDHCR"].where(df["RSSDHCR"] > 0)
    df["ZIP"] = df["ZIP"].str.zfill(5)
    df["STCNTY"] = df["STCNTY"].str.zfill(5)
    return df


def field_expr(fin: pd.DataFrame, expr: str) -> pd.Series:
    """Evaluate a mapping expression such as 'LNCI', 'LNCI2 + LNCI3' or 'LNCI - LNCI4'.
    The first term must be reported (else missing); later terms that are not reported count as 0."""
    tokens = expr.split()
    out = fin[tokens[0]].astype(float)
    for op, name in zip(tokens[1::2], tokens[2::2]):
        term = fin[name].astype(float).fillna(0)
        out = out + term if op == "+" else out - term
    return out


def financials(raw: Path, repdte: str, mapping: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = raw / f"financials_{repdte}.csv"
    fin = pd.read_csv(path, dtype={"CERT": "Int64"})
    retrieved = read_manifest(path)["retrieved_at"][:10]
    rep = pd.to_datetime(str(repdte), format="%Y%m%d").date().isoformat()

    wide = pd.DataFrame({
        "fdic_cert": fin["CERT"],
        "reporting_date": rep,
        "total_assets_usd": fin["ASSET"] * THOUSANDS,
        "total_deposits_usd": fin["DEP"] * THOUSANDS,
        "total_equity_usd": fin["EQ"] * THOUSANDS,
        "net_income_ytd_usd": fin["NETINC"] * THOUSANDS,
        "roa_pct": fin["ROA"],
        "total_loans_usd": fin["LNLSGR"] * THOUSANDS,          # net of unearned income
        "total_loans_gross_usd": fin["LNLSGRS"] * THOUSANDS,   # = sum of additive categories
        "net_loans_usd": fin["LNLSNET"] * THOUSANDS,
        "full_time_employees": fin["NUMEMP"],
        "domestic_offices_call_report": fin["OFFDOM"],
        "source": "FDIC BankFind Suite API /financials (Call Report)",
        "retrieval_date": retrieved,
    })

    fdic_map = mapping[mapping.source == "FDIC"]
    rows = []
    for _, m in fdic_map.iterrows():
        bal = field_expr(fin, m.source_field_amount) * THOUSANDS
        cnt = field_expr(fin, m.source_field_count) if isinstance(m.source_field_count, str) else pd.Series(pd.NA, index=fin.index)
        rows.append(pd.DataFrame({
            "fdic_cert": fin["CERT"], "reporting_date": rep, "source": "FDIC Call Report (BankFind API)",
            "source_field": m.source_field_amount, "source_count_field": m.source_field_count if isinstance(m.source_field_count, str) else pd.NA,
            "source_category": m.source_category, "standardized_category": m.standardized_category,
            "standardized_subcategory": m.standardized_subcategory, "additive": m.additive,
            "loan_balance_usd": bal, "loan_count": cnt,
        }))
    long = pd.concat(rows, ignore_index=True)
    long["notes"] = long["additive"].map({True: pd.NA, False: "memo item; overlaps additive categories"})

    # Additivity check: additive categories should sum to gross loans (LNLSGRS). Where they do
    # not (mostly large FFIEC 031 filers), the gap is stored as an explicit residual row rather
    # than silently absorbed, so category shares always use gross loans as the denominator.
    gross = wide.set_index("fdic_cert")["total_loans_gross_usd"]
    resid = gross - long[long.additive].groupby("fdic_cert")["loan_balance_usd"].sum(min_count=1)
    resid = resid[resid.abs() > 2 * THOUSANDS]
    print(f"  {repdte}: {len(wide):,} institutions; additivity mismatches vs LNLSGRS: {len(resid)} (stored as residual rows)")
    if len(resid):
        long = pd.concat([long, pd.DataFrame({
            "fdic_cert": resid.index, "reporting_date": rep, "source": "FDIC Call Report (BankFind API)",
            "source_field": "LNLSGRS minus sum of mapped categories", "source_count_field": pd.NA,
            "source_category": "Unallocated residual (gross loans not explained by mapped RC-C categories)",
            "standardized_category": "other", "standardized_subcategory": "unallocated_residual", "additive": True,
            "loan_balance_usd": resid.values, "loan_count": pd.NA,
            "notes": "derived residual; investigate before using category shares for this institution",
        })], ignore_index=True)
    long["percent_of_total_loans"] = long["loan_balance_usd"] / long["fdic_cert"].map(gross).where(lambda s: s > 0) * 100
    long["denominator"] = "gross loans and leases (LNLSGRS)"
    long["retrieval_date"] = retrieved
    return wide, long


def branch_summary(raw: Path) -> pd.DataFrame:
    loc = pd.read_csv(raw / "locations.csv", dtype={"CERT": "Int64", "STCNTY": str, "ZIP": str})
    loc["STCNTY"] = loc["STCNTY"].str.zfill(5)
    g = loc.groupby("CERT")
    out = pd.DataFrame({
        "fdic_location_count": g.size(),
        "branch_states": g["STALP"].apply(lambda s: ";".join(sorted(s.dropna().unique()))),
        "branch_state_count": g["STALP"].nunique(),
        "branch_county_fips": g["STCNTY"].apply(lambda s: ";".join(sorted(s.dropna().unique()))),
        "branch_county_count": g["STCNTY"].nunique(),
    }).reset_index().rename(columns={"CERT": "fdic_cert"})
    out["branch_source"] = "FDIC BankFind /locations"
    out["retrieval_date"] = read_manifest(raw / "locations.csv")["retrieved_at"][:10]
    return out


def main() -> None:
    raw = latest_raw_dir()
    OUT.mkdir(parents=True, exist_ok=True)
    mapping = pd.read_csv(REFERENCE / "lending_category_map.csv")
    print(f"Normalizing FDIC from {raw.name}")
    institutions(raw).to_csv(OUT / "fdic_institutions.csv", index=False)
    for f in sorted(raw.glob("financials_*.csv")):
        repdte = f.stem.split("_")[1]
        wide, long = financials(raw, repdte, mapping)
        wide.to_csv(OUT / f"fdic_financials_{repdte}.csv", index=False)
        long.to_csv(OUT / f"fdic_lending_long_{repdte}.csv", index=False)
    branch_summary(raw).to_csv(OUT / "fdic_branch_summary.csv", index=False)
    print(f"  wrote {OUT}")


if __name__ == "__main__":
    main()

"""Download FDIC BankFind Suite data via the public API (https://api.fdic.gov/banks).

No API key is required. Dollar amounts in the financials endpoint are in $ thousands.

Downloads (cached under data/raw/fdic/<retrieval-date>/):
  institutions.csv      all institutions (active and inactive) with identifiers incl. FED_RSSD,
                        RSSDHCR (top holding company RSSD), LEI, address, lat/long, SPECGRPN.
  financials_<REPDTE>.csv  Call Report-derived financials for every institution filing at REPDTE,
                        for the latest quarter and the same quarter one year earlier.
  locations.csv         all branch/office locations of active institutions.

Usage:  python scripts/download/fdic_bankfind.py [YYYYMMDD ...] [--force]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RAW, TODAY, http_get, write_manifest  # noqa: E402

API = "https://api.fdic.gov/banks"
PAGE = 10_000

INSTITUTION_FIELDS = [
    "CERT", "FED_RSSD", "RSSDHCR", "NAMEHCR", "STALPHCR", "CITYHCR", "NAME", "ACTIVE",
    "INACTIVE", "ENDEFYMD", "CHANGEC1", "NEWCERT", "ADDRESS", "CITY", "STALP", "ZIP",
    "COUNTY", "STCNTY", "LATITUDE", "LONGITUDE", "WEBADDR", "LEI", "BKCLASS", "CHARTER",
    "REGAGNT", "SPECGRP", "SPECGRPN", "CB", "MDI_STATUS_CODE", "MDI_STATUS_DESC", "ESTYMD",
    "OFFDOM", "OFFICES", "ASSET", "REPDTE", "CBSA", "PRIORNAME1", "PRIORNAME2", "PRIORNAME3",
]

# Balance-sheet and loan-composition fields (Call Report Schedule RC-C). See
# research/data_dictionary.md for definitions and the additivity checks.
FINANCIAL_FIELDS = [
    "CERT", "REPDTE", "ASSET", "DEP", "EQ", "NETINC", "ROA", "NUMEMP", "OFFDOM",
    "LNLSGR", "LNLSGRS", "LNLSNET",
    # real estate
    "LNRE", "LNRERES", "LNRELOC", "LNRERSFM", "LNRERSF2", "LNRECONS", "LNRECNFM", "LNRECNOT",
    "LNREMULT", "LNRENRES", "LNRENROW", "LNRENROT", "LNREAG",
    # commercial, agricultural
    "LNCI", "LNAG",
    # consumer
    "LNCON", "LNCRCD", "LNAUTO", "LNCONOTH", "LNCONRP",
    # other
    "LNOTHER", "LS", "LNMUNI", "LNDEP", "LNFG",
    # small-business / small-farm memo items (RC-C Part II; loans with original amounts
    # <= $1MM / <= $500K). Overlap the categories above; not additive.
    "LNCI4", "LNCI4N", "LNRENR4", "LNRENR4N", "LNAG4", "LNAG4N", "LNREAG4", "LNREAG4N",
    # C&I size buckets by original amount (<=$100K, $100-250K, $250K-$1MM); LNCI4 = LNCI1+LNCI2+LNCI3.
    "LNCI1", "LNCI1N", "LNCI2", "LNCI2N", "LNCI3", "LNCI3N",
    # Loans to nondepository financial institutions (part of LNOTHER).
    "LNNDEPC",
]

LOCATION_FIELDS = [
    "CERT", "UNINUM", "NAME", "OFFNAME", "OFFNUM", "MAINOFF", "ADDRESS", "CITY", "STALP",
    "ZIP", "COUNTY", "STCNTY", "LATITUDE", "LONGITUDE", "SERVTYPE", "RUNDATE",
]


def fetch_all(endpoint: str, fields: list[str], filters: str | None = None, sort_by: str = "CERT") -> tuple[pd.DataFrame, str]:
    rows, offset, last_url = [], 0, ""
    while True:
        params = {"fields": ",".join(fields), "limit": PAGE, "offset": offset,
                  "sort_by": sort_by, "sort_order": "ASC", "format": "json"}
        if filters:
            params["filters"] = filters
        r = http_get(f"{API}/{endpoint}", params=params)
        last_url = r.url
        js = r.json()
        batch = [d["data"] for d in js["data"]]
        rows.extend(batch)
        total = js["meta"]["total"]
        offset += PAGE
        if offset >= total or not batch:
            break
    return pd.DataFrame(rows), last_url


def save(df: pd.DataFrame, dest: Path, url: str, **extra) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dest, index=False)
    write_manifest(dest, url, None, rows=len(df), **extra)
    print(f"  saved {dest.name}: {len(df):,} rows")


def latest_repdte() -> str:
    r = http_get(f"{API}/financials", params={"fields": "REPDTE", "sort_by": "REPDTE",
                                              "sort_order": "DESC", "limit": 1}).json()
    return str(r["data"][0]["data"]["REPDTE"])


def main(argv: list[str]) -> None:
    force = "--force" in argv
    out = RAW / "fdic" / TODAY
    dates = [a for a in argv if a.isdigit() and len(a) == 8]
    if not dates:
        latest = latest_repdte()
        dates = [latest, str(int(latest[:4]) - 1) + latest[4:]]
    print(f"FDIC BankFind -> {out}  (report dates {dates})")

    dest = out / "institutions.csv"
    if force or not dest.exists():
        df, url = fetch_all("institutions", INSTITUTION_FIELDS)
        save(df, dest, url, endpoint="institutions", note="all institutions, active and inactive")
    for d in dates:
        dest = out / f"financials_{d}.csv"
        if force or not dest.exists():
            df, url = fetch_all("financials", FINANCIAL_FIELDS, filters=f"REPDTE:{d}")
            save(df, dest, url, endpoint="financials", reporting_date=d,
                 units="USD thousands for dollar fields")
    dest = out / "locations.csv"
    if force or not dest.exists():
        df, url = fetch_all("locations", LOCATION_FIELDS, sort_by="UNINUM")
        save(df, dest, url, endpoint="locations")
    (out / "field_lists.json").write_text(json.dumps(
        {"institutions": INSTITUTION_FIELDS, "financials": FINANCIAL_FIELDS,
         "locations": LOCATION_FIELDS}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])

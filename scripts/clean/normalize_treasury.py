"""Normalize the CDFI Fund certified-CDFI list and assign stable internal IDs.

The Treasury list has no CDFI Fund organization ID. Stable internal IDs (`cdfi_id`, e.g.
CDFI00042) are kept in an append-only registry, data/reference/cdfi_id_registry.csv. On each
run, every listed organization is matched to an existing registry entry by, in order:
  1. RSSD ID (when present and unique within both the list and the registry)
  2. exact normalized name (suffixes kept) + state
  3. website domain + state + institution type
Unmatched rows receive a new ID. Registry entries absent from the current list are kept and
marked as not currently listed (they may have been decertified or renamed), never deleted.

Output: data/interim/normalized_treasury/treasury_cert_list.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, RAW, REFERENCE, TODAY, normalize_domain, normalize_name, read_manifest  # noqa: E402

REGISTRY = REFERENCE / "cdfi_id_registry.csv"
TYPE_MAP = {  # Treasury label -> normalized label. Original preserved in institution_type_as_listed.
    "Bank or Thrift": "Bank or Thrift",
    "Bank Holding Company": "Bank Holding Company",
    "Credit Union": "Credit Union",
    "Loan Fund": "Loan Fund",
    "Venture Capital Fund": "Venture Capital Fund",
    "Venture Capital": "Venture Capital Fund",
}
EXPECTED_COLUMNS = ["Organization Name", "Financial Institution Type", "RSSD ID", "Native CDFI (Y/N)",
                    "City", "State", "Zipcode", "Address", "Organization Website"]


def latest_raw_file() -> Path:
    files = sorted((RAW / "treasury" / "cert_list").glob("*/*.xlsx"))
    if not files:
        raise FileNotFoundError("Run scripts/download/treasury_cert_list.py first")
    return files[-1]


def find_header_row(path: Path) -> int:
    probe = pd.read_excel(path, sheet_name=0, header=None, nrows=40, dtype=str)
    for i, row in probe.iterrows():
        if "Organization Name" in row.values:
            return i
    raise ValueError("Header row with 'Organization Name' not found")


def parse_published_totals(path: Path) -> dict:
    probe = pd.read_excel(path, sheet_name=0, header=None, nrows=10, dtype=str)
    text = " ".join(probe.fillna("").astype(str).values.ravel())
    out = {}
    m = re.search(r"Total Number of Certified CDFIs as of [^:]+:\s*(\d+)", text)
    if m:
        out["published_total"] = int(m.group(1))
    m = re.search(r"Total Number of Certified Native CDFIs as of [^:]+:\s*(\d+)", text)
    if m:
        out["published_native_total"] = int(m.group(1))
    by_type = pd.read_excel(path, sheet_name=1, header=None, dtype=str).dropna(how="all", axis=1)
    out["published_by_type"] = {r.iloc[0]: int(r.iloc[1]) for _, r in by_type.iloc[1:].iterrows()
                                if str(r.iloc[1]).isdigit()}
    return out


def clean(path: Path) -> pd.DataFrame:
    hdr = find_header_row(path)
    raw = pd.read_excel(path, sheet_name=0, header=hdr, dtype=str)
    raw = raw.loc[:, ~raw.columns.astype(str).str.startswith("Unnamed")]
    missing = set(EXPECTED_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Treasury list schema changed; missing columns {missing}")
    raw = raw[raw["Organization Name"].notna()].reset_index(drop=True)
    manifest = read_manifest(path)

    df = pd.DataFrame()
    df["source_row_number"] = raw.index + hdr + 2  # 1-based Excel row number
    df["cdfi_name_as_listed"] = raw["Organization Name"]
    df["cdfi_name"] = raw["Organization Name"].str.replace("`", "", regex=False).str.strip()
    df["institution_type_as_listed"] = raw["Financial Institution Type"].str.strip()
    df["institution_type"] = df["institution_type_as_listed"].map(TYPE_MAP)
    if df["institution_type"].isna().any():
        raise ValueError(f"Unknown institution types: {df.loc[df.institution_type.isna(), 'institution_type_as_listed'].unique()}")
    rssd = raw["RSSD ID"].astype(str).str.strip()
    df["rssd_id"] = rssd.where(rssd.str.fullmatch(r"\d+")).astype("Int64")
    df["native_cdfi"] = raw["Native CDFI (Y/N)"].str.strip().str.upper().eq("Y")
    df["hq_address"] = raw["Address"].str.replace(r"\s*\n\s*", ", ", regex=True).str.strip()
    df["hq_city"] = raw["City"].str.strip()
    df["hq_state"] = raw["State"].str.strip().str.upper()
    z = raw["Zipcode"].astype(str).str.strip()
    df["zip_as_listed"] = z
    df["hq_zip5"] = z.str.extract(r"^(\d{5})")[0]
    zip4 = z.str.extract(r"^\d{5}-+(\d{4})$")[0]
    df["hq_zip4"] = zip4.where(zip4 != "0000")
    web = raw["Organization Website"].astype(str).str.strip()
    df["website"] = web.where(~web.str.lower().isin(["non given", "nan", "none", "", "-"]))
    df["website_domain"] = df["website"].map(normalize_domain).replace("", pd.NA)
    df["name_normalized"] = df["cdfi_name"].map(lambda s: normalize_name(s, strip_suffixes=False))
    df["name_core"] = df["cdfi_name"].map(normalize_name)
    df["certification_status"] = "Certified (on current CDFI Fund list)"
    df["source"] = "U.S. Treasury CDFI Fund - List of Certified CDFIs"
    df["source_file"] = path.name
    df["source_url"] = manifest["source_url"]
    df["source_as_of_date"] = manifest.get("source_as_of_date")
    df["retrieval_date"] = manifest["retrieved_at"][:10]
    return df


def assign_ids(df: pd.DataFrame) -> pd.DataFrame:
    if REGISTRY.exists():
        reg = pd.read_csv(REGISTRY, dtype={"rssd_id": "Int64"})
    else:
        reg = pd.DataFrame(columns=["cdfi_id", "rssd_id", "name_normalized", "hq_state", "website_domain",
                                    "institution_type", "first_seen_list_date", "last_seen_list_date",
                                    "current_name", "currently_listed"])
    as_of = df["source_as_of_date"].iloc[0]
    df = df.copy()
    df["cdfi_id"] = pd.NA
    df["id_assignment_method"] = pd.NA
    used: set[str] = set()

    def try_key(mask_unassigned, reg_keys: pd.Series, row_keys: pd.Series, method: str):
        reg_unique = reg_keys[~reg_keys.duplicated(keep=False) & reg_keys.notna()]
        lookup = dict(zip(reg_unique, reg.loc[reg_unique.index, "cdfi_id"]))
        row_dup = row_keys.duplicated(keep=False)
        for i in df.index[mask_unassigned]:
            k = row_keys.at[i]
            if pd.isna(k) or row_dup.at[i] or k not in lookup or lookup[k] in used:
                continue
            df.at[i, "cdfi_id"] = lookup[k]
            df.at[i, "id_assignment_method"] = method
            used.add(lookup[k])

    if len(reg):
        try_key(df.cdfi_id.isna(), reg["rssd_id"].astype("string"), df["rssd_id"].astype("string"), "registry_rssd")
        try_key(df.cdfi_id.isna(), reg["name_normalized"] + "|" + reg["hq_state"],
                df["name_normalized"] + "|" + df["hq_state"], "registry_name_state")
        try_key(df.cdfi_id.isna(), reg["website_domain"] + "|" + reg["hq_state"] + "|" + reg["institution_type"],
                df["website_domain"] + "|" + df["hq_state"] + "|" + df["institution_type"], "registry_domain_state_type")

    next_n = (reg["cdfi_id"].str[4:].astype(int).max() + 1) if len(reg) else 1
    # Deterministic ordering for new IDs: by state, normalized name, type, row number.
    new = df[df.cdfi_id.isna()].sort_values(["hq_state", "name_normalized", "institution_type", "source_row_number"])
    for i in new.index:
        df.at[i, "cdfi_id"] = f"CDFI{next_n:05d}"
        df.at[i, "id_assignment_method"] = "new_id"
        next_n += 1

    # Update registry (append new, refresh last_seen; never delete).
    cur = df.set_index("cdfi_id")
    reg = reg.set_index("cdfi_id") if len(reg) else reg.set_index("cdfi_id")
    for cid, r in cur.iterrows():
        rec = {"rssd_id": r.rssd_id, "name_normalized": r.name_normalized, "hq_state": r.hq_state,
               "website_domain": r.website_domain, "institution_type": r.institution_type,
               "last_seen_list_date": as_of, "current_name": r.cdfi_name, "currently_listed": True}
        if cid in reg.index:
            for k, v in rec.items():
                reg.at[cid, k] = v
        else:
            rec["first_seen_list_date"] = as_of
            reg.loc[cid] = pd.Series(rec)
    reg.loc[~reg.index.isin(cur.index), "currently_listed"] = False
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    reg.reset_index().sort_values("cdfi_id").to_csv(REGISTRY, index=False)
    return df


def flag_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    r = df["rssd_id"]
    df["dup_rssd_in_list"] = r.notna() & r.duplicated(keep=False)
    df["dup_name_state_in_list"] = (df.name_normalized + "|" + df.hq_state).duplicated(keep=False)
    dom = df["website_domain"]
    grp = df[dom.notna()].groupby("website_domain")["cdfi_id"].apply(lambda s: ";".join(sorted(s)))
    df["shares_website_with"] = [
        ";".join(x for x in grp.get(d, "").split(";") if x and x != cid) or pd.NA if pd.notna(d) else pd.NA
        for d, cid in zip(dom, df.cdfi_id)
    ]
    return df


def main() -> None:
    path = latest_raw_file()
    print(f"Normalizing {path.relative_to(path.parents[4])}")
    df = flag_duplicates(assign_ids(clean(path)))
    totals = parse_published_totals(path)
    n, pub = len(df), totals.get("published_total")
    print(f"  rows: {n}  (Treasury-published total: {pub})")
    if pub is not None and pub != n:
        print(f"  WARNING: row count {n} != published total {pub}")
    print("  by type:", df.institution_type.value_counts().to_dict())
    print("  published by type:", totals.get("published_by_type"))
    out = INTERIM / "normalized_treasury" / "treasury_cert_list.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    pd.Series(totals | {"normalized_rows": n, "run_date": TODAY}, dtype=object).to_json(
        out.with_name("treasury_published_totals.json"), indent=2)
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()

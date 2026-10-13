"""Normalize CDFI Fund awards and link them to certified CDFIs.

The awards export has no organization ID, so linking uses (in order):
  1. exact normalized name + state (+ city to break ties)      -> confidence high (city match) / medium
  2. exact normalized d/b/a alias + state                       -> medium
  3. fuzzy name (token_sort_ratio >= 93) + same state + same city -> low, review-flagged
Ambiguous matches (several certified CDFIs equally plausible) are left unlinked.
Award rows that do not link to a currently certified CDFI are KEPT (cdfi_id empty): they include
non-CDFI BEA/NMTC recipients, decertified or renamed organizations.

Outputs: data/processed/cdfi_awards.csv, data/interim/crosswalks/award_name_matches.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, PROCESSED, RAW, normalize_name, read_manifest  # noqa: E402

PROGRAMS = {  # program code -> (description, award_type, counts_toward_grant_total)
    "CDFI-FA": ("CDFI Program Financial Assistance", "financial_assistance", True),
    "CDFI-TA": ("CDFI Program Technical Assistance", "technical_assistance", True),
    "CDFI-RRP": ("CDFI Rapid Response Program", "financial_assistance", True),
    "CDFI-ERP": ("CDFI Equitable Recovery Program", "financial_assistance", True),
    "NACA-FA": ("Native American CDFI Assistance - Financial Assistance", "financial_assistance", True),
    "NACA-TA": ("Native American CDFI Assistance - Technical Assistance", "technical_assistance", True),
    "NACA Combined FA/TA (Historic)": ("Native American CDFI Assistance - combined FA/TA (historic)", "financial_assistance", True),
    "BEA": ("Bank Enterprise Award", "bank_enterprise_award", True),
    "CMF": ("Capital Magnet Fund", "capital_magnet_fund", True),
    "SDL": ("Small Dollar Loan Program", "financial_assistance", True),
    "HFFI-FA": ("Healthy Food Financing Initiative - Financial Assistance", "financial_assistance", True),
    "DF-FA": ("Disability Fund - Financial Assistance", "financial_assistance", True),
    "FEC": ("Financial Education and Counseling Pilot", "grant_other", True),
    "NMTC": ("New Markets Tax Credit allocation", "tax_credit_allocation", False),
    "BOND": ("CDFI Bond Guarantee Program", "bond_guarantee", False),
}
DBA = re.compile(r"\s+(?:d/?b/?a|dba|a/k/a|aka)\.?\s+", re.I)


def kind(name: str) -> str:
    n = str(name).lower()
    if re.search(r"credit union|\bfcu\b|\bcu\b|cooperativa|coop\b", n):
        return "credit_union"
    if re.search(r"bank|banc|savings|trust company|\bb&t\b", n):
        return "bank"
    return "other"


def names_of(name: str, strip: bool) -> list[str]:
    """Normalized primary name first, then d/b/a and parenthetical aliases."""
    parts = [p for p in DBA.split(str(name)) if p.strip()]
    paren = re.findall(r"\(([^)]+)\)", str(name))
    base = re.sub(r"\([^)]*\)", " ", parts[0]) if parts else str(name)
    out = [normalize_name(base, strip)] + [normalize_name(p, strip) for p in parts[1:]] + \
          [normalize_name(p, strip) for p in paren if len(p) > 3]
    return [o for o in dict.fromkeys(out) if o]


def main() -> None:
    f = sorted((RAW / "awards").glob("*/*_state-awards.csv"))[-1]
    man = read_manifest(f)
    a = pd.read_csv(f, dtype=str)
    a.columns = [c.strip() for c in a.columns]
    aw = pd.DataFrame({
        "award_row_id": range(1, len(a) + 1),
        "awardee_name": a["Awardee"].str.strip(),
        "awardee_city": a["City"].str.strip(),
        "awardee_state": a["State"].str.strip().str.upper(),
        "award_year": pd.to_numeric(a["Year"], errors="coerce").astype("Int64"),
        "award_program": a["Program"].str.strip(),
        "award_amount_usd": pd.to_numeric(a["Amount"].str.replace(r"[$,\s]", "", regex=True), errors="coerce"),
    })
    unknown = set(aw.award_program) - set(PROGRAMS)
    if unknown:
        print(f"  WARNING: unmapped award programs {unknown}")
    aw["award_program_name"] = aw.award_program.map(lambda p: PROGRAMS.get(p, (p, "unknown", False))[0])
    aw["award_type"] = aw.award_program.map(lambda p: PROGRAMS.get(p, (p, "unknown", False))[1])
    aw["counts_toward_grant_total"] = aw.award_program.map(lambda p: PROGRAMS.get(p, (p, "unknown", False))[2])

    t = pd.read_csv(INTERIM / "normalized_treasury" / "treasury_cert_list.csv")
    t["city_n"] = t.hq_city.str.lower().str.strip()
    # Tier 1 keys: full normalized names (legal suffixes kept), primary name + aliases.
    # Tier 2 keys: suffix-stripped core of the primary name only (aliases excluded: too loose).
    rows = []
    for cid, nm, st, c in zip(t.cdfi_id, t.cdfi_name, t.hq_state, t.city_n):
        for j, n in enumerate(names_of(nm, strip=False)):
            rows.append((cid, st, c, n, 1, j == 0))
        rows.append((cid, st, c, names_of(nm, strip=True)[0], 2, True))
    al = pd.DataFrame(rows, columns=["cdfi_id", "state", "city", "key", "tier", "primary"])
    al["kind"] = al.cdfi_id.map(dict(zip(t.cdfi_id, t.cdfi_name.map(kind))))

    # Match each distinct awardee (name, city, state) once.
    keys = aw[["awardee_name", "awardee_city", "awardee_state"]].drop_duplicates().reset_index(drop=True)
    res = []
    for k in keys.itertuples():
        city = str(k.awardee_city).lower().strip()
        pool = al[al.state == k.awardee_state]
        method, conf, cid, score, review = "unmatched", pd.NA, pd.NA, pd.NA, False
        for tier, cands_names in ((1, names_of(k.awardee_name, strip=False)), (2, names_of(k.awardee_name, strip=True)[:1])):
            hit = pool[(pool.tier == tier) & pool.key.isin(cands_names)]
            if tier == 2:  # suffix-stripped names: require the same institution kind
                hit = hit[hit.kind == kind(k.awardee_name)]
            ids = hit.cdfi_id.unique()
            if len(ids) > 1:
                same_city = hit[hit.city == city].cdfi_id.unique()
                ids = same_city if len(same_city) == 1 else ids
            if len(ids) == 1:
                cid = ids[0]
                h = hit[hit.cdfi_id == cid]
                primary = bool((h.primary & (h.key == cands_names[0])).any())
                city_ok = bool((h.city == city).any())
                method = {1: "full_name_state_exact", 2: "core_name_state_exact"}[tier] if primary else "alias_state_exact"
                conf = "high" if (tier == 1 and primary and city_ok) else ("medium" if city_ok or tier == 1 else "low")
                review = conf == "low" or tier == 2 or not primary
                score = 100.0
                break
            if len(ids) > 1:
                method, review = "ambiguous", True
                break
        if method == "unmatched" and len(pool):
            core = pool[(pool.tier == 2) & (pool.kind == kind(k.awardee_name))]
            m = process.extractOne(names_of(k.awardee_name, strip=True)[0], core.key.to_dict(), scorer=fuzz.token_sort_ratio, score_cutoff=93)
            if m and core.at[m[2], "city"] == city:
                cid, method, conf, score, review = core.at[m[2], "cdfi_id"], "fuzzy_name_state_city", "low", round(m[1], 1), True
        res.append({"awardee_name": k.awardee_name, "awardee_city": k.awardee_city, "awardee_state": k.awardee_state,
                    "cdfi_id": cid, "award_match_method": method, "award_match_confidence": conf,
                    "award_name_similarity": score, "award_match_review_required": review})
    mk = pd.DataFrame(res)
    (INTERIM / "crosswalks").mkdir(parents=True, exist_ok=True)
    mk.merge(t[["cdfi_id", "cdfi_name", "hq_city"]], on="cdfi_id", how="left").to_csv(
        INTERIM / "crosswalks" / "award_name_matches.csv", index=False)

    out = aw.merge(mk, on=["awardee_name", "awardee_city", "awardee_state"], how="left")
    out["source"] = "CDFI Fund Searchable Awards Database (CSV export)"
    out["source_file"] = f.name
    out["source_url"] = man["source_url"]
    out["retrieval_date"] = man["retrieved_at"][:10]
    out.to_csv(PROCESSED / "cdfi_awards.csv", index=False)
    linked = out.cdfi_id.notna()
    print(f"Awards: {len(out):,} rows, {linked.sum():,} linked to {out.loc[linked, 'cdfi_id'].nunique()} certified CDFIs")
    print(out.groupby("award_match_method").size().to_string())


if __name__ == "__main__":
    main()

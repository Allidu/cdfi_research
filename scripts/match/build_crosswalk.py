"""Build the CDFI -> external identifier crosswalk.

Matching hierarchy (strongest first):
  Banks/thrifts : Treasury RSSD == FDIC FED_RSSD (active institution)
  BHCs          : Treasury RSSD == FDIC RSSDHCR (subsidiary banks, relationship=subsidiary_bank);
                  falls back to FED_RSSD in case Treasury labelled a bank as a BHC
  Credit unions : Treasury RSSD == NCUA FOICU RSSD
  Depositories without RSSD or unmatched: exact normalized name + state, then fuzzy name within
                  state (always flagged for manual review)
  Loan/VC funds : IRS EO BMF (EIN) by normalized name + state (+ ZIP5), fuzzy only as flagged fallback

Every identifier-based match is also checked for name agreement; divergent names are flagged
for review rather than rejected (Treasury RSSD is treated as authoritative). Ambiguous matches
(several equally good candidates) are never accepted automatically.

Outputs:
  data/interim/crosswalks/crosswalk_long.csv
  data/processed/cdfi_crosswalk.csv
  research/unresolved_matches.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, PROCESSED, RAW, RESEARCH, latest_dated_dir, normalize_name  # noqa: E402

NAME_OK = 80        # token_set_ratio on core names: above = names agree
FUZZY_ACCEPT = 90   # fuzzy name threshold for proposing a candidate (still review-flagged)

COLS = ["cdfi_id", "cdfi_name", "institution_type", "hq_state", "id_system", "id_value", "relationship",
        "external_name", "external_city", "external_state", "match_method", "match_confidence",
        "name_similarity", "manual_review_required", "review_reason", "related_certified_cdfi_id", "notes"]


def sim(a: str, b: str) -> float:
    return float(fuzz.token_set_ratio(normalize_name(a), normalize_name(b)))


def load_inputs():
    t = pd.read_csv(INTERIM / "normalized_treasury" / "treasury_cert_list.csv", dtype={"hq_zip5": str, "rssd_id": "Int64"})
    fi = pd.read_csv(INTERIM / "normalized_fdic" / "fdic_institutions.csv",
                     dtype={"FED_RSSD": "Int64", "RSSDHCR": "Int64", "CERT": "Int64", "LEI": str, "ZIP": str}, low_memory=False)
    q = sorted((INTERIM / "normalized_ncua").glob("ncua_foicu_*.csv"))[-1]
    cu = pd.read_csv(q, dtype={"rssd_id": "Int64", "ncua_charter": "Int64", "zip5": str})
    return t, fi, cu


def row(t, **kw) -> dict:
    base = {"cdfi_id": t.cdfi_id, "cdfi_name": t.cdfi_name, "institution_type": t.institution_type,
            "hq_state": t.hq_state, "manual_review_required": False, "review_reason": pd.NA,
            "related_certified_cdfi_id": pd.NA, "notes": pd.NA}
    base.update(kw)
    return base


def fdic_rows(t, inst: pd.Series, relationship: str, method: str, conf: str, review: list[str]) -> list[dict]:
    s = max([sim(t.cdfi_name, inst.NAME)] + [sim(t.cdfi_name, inst[p]) for p in ("PRIORNAME1", "PRIORNAME2", "PRIORNAME3") if pd.notna(inst[p])])
    if relationship == "self" and s < NAME_OK:
        review = review + [f"name differs from FDIC name ({inst.NAME})"]
    common = dict(relationship=relationship, external_name=inst.NAME, external_city=inst.CITY,
                  external_state=inst.STALP, match_method=method, match_confidence=conf,
                  name_similarity=round(s, 1), manual_review_required=bool(review),
                  review_reason="; ".join(review) or pd.NA)
    out = [row(t, id_system="FDIC_CERT", id_value=str(inst.CERT), **common)]
    if pd.notna(inst.FED_RSSD) and relationship != "self":
        out.append(row(t, id_system="RSSD", id_value=str(inst.FED_RSSD), **common))
    if isinstance(inst.LEI, str) and inst.LEI.strip() and inst.LEI.strip() != "0":
        out.append(row(t, id_system="LEI", id_value=inst.LEI.strip(), **common))
    return out


def inactive_rows(t, inst: pd.Series, relationship: str, fi_by_cert: pd.DataFrame) -> list[dict]:
    """An FDIC institution that is no longer active: record it, plus its successor (via NEWCERT)
    as a separate, review-flagged relationship. Successor financials are NOT attributed to the CDFI."""
    reason = f"RSSD maps to an INACTIVE FDIC institution {inst.NAME} (end {inst.ENDEFYMD}, change code {inst.CHANGEC1})"
    out = [row(t, id_system="FDIC_CERT", id_value=str(inst.CERT), relationship=relationship,
               external_name=inst.NAME, external_city=inst.CITY, external_state=inst.STALP,
               match_method="rssd_exact_inactive" if relationship == "self" else "rssd_holding_company_inactive",
               match_confidence="low", name_similarity=round(sim(t.cdfi_name, inst.NAME), 1),
               manual_review_required=True, review_reason=reason)]
    seen, cert = set(), inst.NEWCERT
    while pd.notna(cert) and int(cert) not in seen and int(cert) in fi_by_cert.index:
        cert = int(cert)
        seen.add(cert)
        nxt = fi_by_cert.loc[cert]
        if isinstance(nxt, pd.DataFrame):
            nxt = nxt.iloc[0]
        if nxt.ACTIVE == 1:
            out.append(row(t, id_system="FDIC_CERT", id_value=str(nxt.CERT), relationship="merger_successor",
                           external_name=nxt.NAME, external_city=nxt.CITY, external_state=nxt.STALP,
                           match_method="fdic_newcert_chain", match_confidence="low",
                           name_similarity=round(sim(t.cdfi_name, nxt.NAME), 1), manual_review_required=True,
                           review_reason=reason + f"; successor is {nxt.NAME} (CERT {nxt.CERT}). Successor financials not attributed.",
                           notes="Treasury list may be stale for this entity, or certification may have passed to the successor"))
            break
        cert = nxt.NEWCERT
    return out


def match_depositories(t_all: pd.DataFrame, fi: pd.DataFrame, cu: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    active = fi[fi.ACTIVE == 1]
    assert not active.FED_RSSD.dropna().duplicated().any(), "duplicate active FED_RSSD"
    by_rssd = active.set_index("FED_RSSD", drop=False)
    inactive_by_rssd = fi[fi.ACTIVE != 1].drop_duplicates("FED_RSSD").set_index("FED_RSSD", drop=False)
    subs = active[active.RSSDHCR.notna()].groupby("RSSDHCR")
    # Banks that ceased since 2024 (e.g. merged) but whose last holding company is the BHC.
    recent_inactive = fi[(fi.ACTIVE != 1) & (pd.to_datetime(fi.ENDEFYMD, format="%m/%d/%Y", errors="coerce") >= "2024-01-01")]
    former_subs = recent_inactive[recent_inactive.RSSDHCR.notna()].groupby("RSSDHCR")
    fi_by_cert = fi.set_index("CERT", drop=False)
    cu_by_rssd = cu[cu.rssd_id.notna()].drop_duplicates("rssd_id").set_index("rssd_id")
    certified_bank_rssd = dict(zip(t_all.loc[t_all.institution_type == "Bank or Thrift", "rssd_id"].dropna(),
                                   t_all.loc[(t_all.institution_type == "Bank or Thrift") & t_all.rssd_id.notna(), "cdfi_id"]))

    for t in t_all[t_all.institution_type.isin(["Bank or Thrift", "Bank Holding Company", "Credit Union"])].itertuples():
        matched = False
        if pd.notna(t.rssd_id):
            rows.append(row(t, id_system="RSSD", id_value=str(t.rssd_id), relationship="self",
                            external_name=pd.NA, external_city=pd.NA, external_state=pd.NA,
                            match_method="treasury_reported", match_confidence="high", name_similarity=pd.NA,
                            notes="RSSD ID as published on the Treasury certified list"))
            if t.institution_type == "Credit Union":
                if t.rssd_id in cu_by_rssd.index:
                    c = cu_by_rssd.loc[t.rssd_id]
                    s = max([sim(t.cdfi_name, c.cu_name)] + ([sim(t.cdfi_name, n) for n in str(c.trade_names).split(";")] if pd.notna(c.trade_names) else []))
                    review = [] if s >= NAME_OK else [f"name differs from NCUA name ({c.cu_name})"]
                    if t.dup_rssd_in_list:
                        review.append("RSSD appears on more than one Treasury row")
                    rows.append(row(t, id_system="NCUA_CHARTER", id_value=str(c.ncua_charter), relationship="self",
                                    external_name=c.cu_name, external_city=c.city, external_state=c.state,
                                    match_method="rssd_exact", match_confidence="high", name_similarity=round(s, 1),
                                    manual_review_required=bool(review), review_reason="; ".join(review) or pd.NA))
                    matched = True
            else:
                if t.rssd_id in by_rssd.index:
                    inst = by_rssd.loc[t.rssd_id]
                    review = [] if t.institution_type == "Bank or Thrift" else ["Treasury type is BHC but RSSD is an FDIC-insured bank"]
                    rows += fdic_rows(t, inst, "self", "rssd_exact", "high", review)
                    matched = True
                elif t.institution_type == "Bank Holding Company" and t.rssd_id in subs.groups:
                    for _, inst in subs.get_group(t.rssd_id).iterrows():
                        rr = fdic_rows(t, inst, "subsidiary_bank", "rssd_holding_company", "high", [])
                        rel = certified_bank_rssd.get(inst.FED_RSSD)
                        for r in rr:
                            r["related_certified_cdfi_id"] = rel if rel else pd.NA
                            r["notes"] = ("subsidiary bank is separately certified; do not double count" if rel
                                          else "subsidiary bank is not separately on the certified list")
                        rows += rr
                    matched = True
                elif t.rssd_id in inactive_by_rssd.index:
                    inst = inactive_by_rssd.loc[t.rssd_id]
                    rows += inactive_rows(t, inst, "self", fi_by_cert)
                    matched = True
                elif t.institution_type == "Bank Holding Company" and t.rssd_id in former_subs.groups:
                    for _, inst in former_subs.get_group(t.rssd_id).iterrows():
                        rows += inactive_rows(t, inst, "former_subsidiary_bank", fi_by_cert)
                    matched = True
                if not matched and t.rssd_id in cu_by_rssd.index:
                    c = cu_by_rssd.loc[t.rssd_id]
                    rows.append(row(t, id_system="NCUA_CHARTER", id_value=str(c.ncua_charter), relationship="self",
                                    external_name=c.cu_name, external_city=c.city, external_state=c.state,
                                    match_method="rssd_exact_other_regulator", match_confidence="medium",
                                    name_similarity=round(sim(t.cdfi_name, c.cu_name), 1), manual_review_required=True,
                                    review_reason="Treasury type is bank/BHC but RSSD belongs to an NCUA credit union"))
                    matched = True
        if not matched:
            rows += name_match_depository(t, active, cu)
    return rows


def name_match_depository(t, active: pd.DataFrame, cu: pd.DataFrame) -> list[dict]:
    reason_prefix = "no RSSD on Treasury list" if pd.isna(t.rssd_id) else "Treasury RSSD not found in FDIC/NCUA data"
    if t.institution_type == "Credit Union":
        pool = cu[cu.state == t.hq_state]
        names, cities, ids, system = pool.cu_name, pool.city, pool.ncua_charter, "NCUA_CHARTER"
    else:
        pool = active[active.STALP == t.hq_state]
        if t.institution_type == "Bank Holding Company":
            pool = pool.assign(NAME=pool.NAMEHCR.fillna(pool.NAME))
        names, cities, ids, system = pool.NAME, pool.CITY, pool.CERT, "FDIC_CERT"
    core = t.name_core
    norm = names.map(normalize_name)
    exact = pool[norm == core]
    if len(exact) == 1 or (len(exact) > 1 and (cities[exact.index].str.lower() == str(t.hq_city).lower()).sum() == 1):
        if len(exact) > 1:
            exact = exact[cities[exact.index].str.lower() == str(t.hq_city).lower()]
        i = exact.index[0]
        city_ok = str(cities[i]).lower() == str(t.hq_city).lower()
        return [row(t, id_system=system, id_value=str(ids[i]), relationship="self" if t.institution_type != "Bank Holding Company" else "subsidiary_bank",
                    external_name=names[i], external_city=cities[i], external_state=t.hq_state,
                    match_method="name_state_exact", match_confidence="medium" if city_ok else "low", name_similarity=100.0,
                    manual_review_required=True, review_reason=f"{reason_prefix}; matched on normalized name + state" + ("" if city_ok else " (city differs)"))]
    cands = process.extract(core, norm.to_dict(), scorer=fuzz.token_sort_ratio, limit=3)
    cands = [c for c in cands if c[1] >= FUZZY_ACCEPT]
    if cands:
        best = cands[0]
        i = best[2]
        ambiguous = len(cands) > 1 and cands[1][1] == best[1]
        return [row(t, id_system=system, id_value=str(ids[i]) if not ambiguous else pd.NA, relationship="self",
                    external_name=names[i], external_city=cities[i], external_state=t.hq_state,
                    match_method="fuzzy_name_state", match_confidence="low", name_similarity=round(best[1], 1),
                    manual_review_required=True,
                    review_reason=f"{reason_prefix}; fuzzy candidate only" + ("; AMBIGUOUS - multiple equal candidates, not accepted" if ambiguous else ""))]
    return [row(t, id_system=system, id_value=pd.NA, relationship="self", external_name=pd.NA, external_city=pd.NA,
                external_state=pd.NA, match_method="unmatched", match_confidence=pd.NA, name_similarity=pd.NA,
                manual_review_required=True, review_reason=f"{reason_prefix}; no candidate found")]


# ---------------------------------------------------------------------------
# Loan funds / VC funds -> IRS EO BMF (EIN)
# ---------------------------------------------------------------------------
def load_bmf(states: set[str]) -> pd.DataFrame:
    d = latest_dated_dir(RAW / "other" / "irs_eo_bmf")
    parts = []
    for st in states:
        f = d / f"eo_{st.lower()}.csv"
        if f.exists():
            parts.append(pd.read_csv(f, dtype=str, usecols=["EIN", "NAME", "SORT_NAME", "STREET", "CITY", "STATE", "ZIP",
                                                              "SUBSECTION", "NTEE_CD", "ASSET_AMT", "REVENUE_AMT", "TAX_PERIOD"]))
    bmf = pd.concat(parts, ignore_index=True)
    # Exclude credit unions (501(c)(1) federal CUs, 501(c)(14) state CUs): suffix-stripped names
    # would otherwise collide with similarly named loan funds.
    bmf = bmf[~bmf.SUBSECTION.isin(["01", "14"])].copy()
    # Group-exemption subordinates carry the parent's NAME and their own name in SORT_NAME.
    bmf["display_name"] = bmf.NAME.where(bmf.SORT_NAME.isna(), bmf.NAME + " / " + bmf.SORT_NAME.fillna(""))
    bmf["zip5"] = bmf.ZIP.str[:5]
    bmf["core"] = bmf.NAME.map(normalize_name)
    bmf["sort_core"] = bmf.SORT_NAME.map(normalize_name)
    bmf["source_dir"] = d.name
    return bmf


def match_nondepositories(t_all: pd.DataFrame) -> list[dict]:
    nd = t_all[t_all.institution_type.isin(["Loan Fund", "Venture Capital Fund"])]
    bmf = load_bmf(set(nd.hq_state.dropna()))
    rows = []
    by_state = {s: g for s, g in bmf.groupby("STATE")}
    for t in nd.itertuples():
        pool = by_state.get(t.hq_state)
        base = dict(id_system="EIN", relationship="self")
        if pool is None:
            rows.append(row(t, **base, id_value=pd.NA, external_name=pd.NA, external_city=pd.NA, external_state=pd.NA,
                            match_method="unmatched", match_confidence=pd.NA, name_similarity=pd.NA,
                            manual_review_required=True, review_reason="no IRS EO BMF file for state"))
            continue
        core = t.name_core
        exact = pool[(pool.core == core) | (pool.sort_core == core)]
        if len(exact) > 1:
            z = exact[exact.zip5 == t.hq_zip5]
            exact = z if len(z) >= 1 else exact
        if len(exact) == 1:
            b = exact.iloc[0]
            zip_ok = b.zip5 == t.hq_zip5
            rows.append(row(t, **base, id_value=b.EIN, external_name=b.display_name, external_city=b.CITY, external_state=b.STATE,
                            match_method="name_state_exact" + ("_zip" if zip_ok else ""),
                            match_confidence="high" if zip_ok else "medium", name_similarity=100.0,
                            manual_review_required=not zip_ok,
                            review_reason=pd.NA if zip_ok else "exact name+state but ZIP differs (filing address may differ)",
                            notes=f"IRS EO BMF {b.source_dir}; subsection {b.SUBSECTION}; NTEE {b.NTEE_CD}"))
            continue
        if len(exact) > 1:
            rows.append(row(t, **base, id_value=pd.NA, external_name="; ".join(exact.NAME.head(5)), external_city=pd.NA,
                            external_state=t.hq_state, match_method="ambiguous", match_confidence=pd.NA, name_similarity=100.0,
                            manual_review_required=True,
                            review_reason=f"AMBIGUOUS: {len(exact)} EO BMF orgs with same normalized name in state; EINs " + ",".join(exact.EIN.head(5))))
            continue
        cands = process.extract(core, pool.core.to_dict(), scorer=fuzz.token_sort_ratio, limit=5, score_cutoff=FUZZY_ACCEPT - 5)
        cands = sorted(cands, key=lambda c: (c[1] + (5 if pool.at[c[2], "zip5"] == t.hq_zip5 else 0)), reverse=True)
        if cands:
            i = cands[0][2]
            b = pool.loc[i]
            zip_ok = b.zip5 == t.hq_zip5
            score = cands[0][1]
            accept = (score >= FUZZY_ACCEPT and zip_ok)
            rows.append(row(t, **base, id_value=b.EIN if accept else pd.NA, external_name=b.NAME, external_city=b.CITY,
                            external_state=b.STATE, match_method="fuzzy_name_state" + ("_zip" if zip_ok else ""),
                            match_confidence="low", name_similarity=round(score, 1), manual_review_required=True,
                            review_reason=("fuzzy name match with same ZIP5 - verify" if accept
                                           else f"fuzzy candidate not accepted (score {score:.0f}, zip {'match' if zip_ok else 'differs'}); EIN {b.EIN}"),
                            notes=f"IRS EO BMF {b.source_dir}; subsection {b.SUBSECTION}; NTEE {b.NTEE_CD}"))
            continue
        rows.append(row(t, **base, id_value=pd.NA, external_name=pd.NA, external_city=pd.NA, external_state=pd.NA,
                        match_method="unmatched", match_confidence=pd.NA, name_similarity=pd.NA, manual_review_required=True,
                        review_reason="no IRS EO BMF candidate (may be for-profit/LLC, or a different legal name)"))
    return rows


def explain_unmatched_credit_unions(xw: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """Attach specific, verifiable explanations to credit unions absent from the latest NCUA file."""
    m = (xw.institution_type == "Credit Union") & (xw.match_method == "unmatched")
    pr = m & (xw.hq_state == "PR")
    xw.loc[pr, "match_method"] = "not_in_ncua_scope"
    xw.loc[pr, "review_reason"] = ("Puerto Rico cooperativa de ahorro y credito: insured/supervised by COSSEC, "
                                   "not NCUA; no NCUA 5300 data exists")
    foicus = sorted((INTERIM / "normalized_ncua").glob("ncua_foicu_*.csv"))
    if len(foicus) > 1:
        prev = pd.read_csv(foicus[-2], dtype={"rssd_id": "Int64"})
        rssd = xw.cdfi_id.map(t.set_index("cdfi_id").rssd_id)
        hit = m & ~pr & rssd.isin(prev.rssd_id.dropna())
        for i in xw.index[hit]:
            p = prev[prev.rssd_id == rssd[i]].iloc[0]
            xw.at[i, "review_reason"] = (f"RSSD found in prior NCUA quarter ({p.reporting_date}: {p.cu_name}, charter {p.ncua_charter}) "
                                         "but not in latest - likely merged or liquidated; Treasury list may be stale")
            xw.at[i, "match_method"] = "absent_from_latest_ncua"
    return xw


def link_related_certified(xw: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """(1) For subsidiary / successor FDIC rows, point to the certified CDFI that IS that bank, so
    aggregates can avoid double counting. (2) For BHCs still unmatched (typically mid-tier holding
    companies, since FDIC RSSDHCR only gives the top-tier holder), propose the certified bank that
    shares the BHC's website as a probable subsidiary - low confidence, review required."""
    self_bank = xw[(xw.id_system == "FDIC_CERT") & (xw.relationship == "self") & (xw.institution_type == "Bank or Thrift")
                   & xw.id_value.notna()].drop_duplicates("id_value").set_index("id_value")["cdfi_id"]
    other = (xw.id_system.isin(["FDIC_CERT", "RSSD", "LEI"])) & (xw.relationship != "self")
    cert_of = xw[other & (xw.id_system == "FDIC_CERT")].set_index(["cdfi_id", "external_name"])["id_value"]
    for i in xw.index[other]:
        key = (xw.at[i, "cdfi_id"], xw.at[i, "external_name"])
        cert = cert_of.get(key)
        if isinstance(cert, pd.Series):
            cert = cert.iloc[0]
        rel = self_bank.get(cert) if cert is not None else None
        if rel and rel != xw.at[i, "cdfi_id"]:
            xw.at[i, "related_certified_cdfi_id"] = rel
            if xw.at[i, "relationship"] == "subsidiary_bank":
                xw.at[i, "notes"] = "subsidiary bank is separately certified; do not double count"
    tt = t.set_index("cdfi_id")
    new = []
    for i in xw.index[(xw.institution_type == "Bank Holding Company") & (xw.match_method == "unmatched")]:
        cid = xw.at[i, "cdfi_id"]
        sib = tt.at[cid, "shares_website_with"]
        if pd.isna(sib):
            continue
        for s_id in str(sib).split(";"):
            if s_id in tt.index and tt.at[s_id, "institution_type"] == "Bank or Thrift":
                hit = xw[(xw.cdfi_id == s_id) & (xw.id_system == "FDIC_CERT") & (xw.relationship == "self") & xw.id_value.notna()]
                for _, h in hit.iterrows():
                    r = xw.loc[i].copy()
                    r.update({"id_system": "FDIC_CERT", "id_value": h.id_value, "relationship": "probable_subsidiary_bank",
                              "external_name": h.external_name, "external_city": h.external_city, "external_state": h.external_state,
                              "match_method": "shared_website_with_certified_bank", "match_confidence": "low",
                              "name_similarity": round(sim(r.cdfi_name, h.external_name), 1), "manual_review_required": True,
                              "review_reason": "BHC RSSD not a top-tier holder in FDIC data; proposed subsidiary via shared website "
                                               f"with certified bank {tt.at[s_id, 'cdfi_name']} - verify in FFIEC NIC",
                              "related_certified_cdfi_id": s_id})
                    new.append(r)
                xw.at[i, "match_method"] = "unmatched_see_probable_subsidiary"
    if new:
        xw = pd.concat([xw, pd.DataFrame(new)], ignore_index=True)
    return xw


def main() -> None:
    t, fi, cu = load_inputs()
    print(f"Crosswalk: {len(t)} certified CDFIs")
    rows = match_depositories(t, fi, cu) + match_nondepositories(t)
    xw = pd.DataFrame(rows)[COLS]
    xw = explain_unmatched_credit_unions(xw, t)
    xw = link_related_certified(xw, t)
    xw = xw.drop_duplicates(subset=["cdfi_id", "id_system", "id_value", "relationship"])
    (INTERIM / "crosswalks").mkdir(parents=True, exist_ok=True)
    xw.to_csv(INTERIM / "crosswalks" / "crosswalk_long.csv", index=False)
    accepted = xw[xw.id_value.notna()]
    accepted.to_csv(PROCESSED / "cdfi_crosswalk.csv", index=False)
    unresolved = xw[xw.manual_review_required].sort_values(["institution_type", "cdfi_id"])
    unresolved.to_csv(RESEARCH / "unresolved_matches.csv", index=False)
    print(f"  crosswalk rows (accepted ids): {len(accepted)}; review-flagged rows: {len(unresolved)}")
    print(xw.groupby(["institution_type", "id_system", "match_method"]).cdfi_id.nunique().to_string())


if __name__ == "__main__":
    main()

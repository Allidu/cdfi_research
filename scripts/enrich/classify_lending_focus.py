"""Evidence-based lending-focus classification for non-depository CDFIs (loan funds, VC funds),
plus program-list evidence for all CDFIs.

Evidence sources (strongest first):
  1. IRS Form 990 Part III program descriptions, weighted by each program's share of program expenses
  2. 990 mission / activity statements; Schedule O explanations of Part III / mission
  3. Federal program participation lists: SBA Microloan intermediaries (microenterprise),
     SBA Community Advantage SBLCs (small business)
  4. CDFI Fund award programs with a defined lending purpose: SDL (small-dollar consumer loans),
     CMF (affordable housing), NMTC (commercial / community real-estate projects), HFFI (healthy food)
  5. Indirect: FHFA FHLB membership (housing finance, supporting only), organization-name keywords,
     990 program-related-investment and program-revenue descriptions

Text rules live in data/reference/focus_text_rules.csv. A text rule fires on a sentence; rules marked
requires_lending_context also need a lending word in the same sentence.

Confidence per CDFI x category:
  HIGH   - explicit lending language in Part III program descriptions covering >= 25% of program
           expenses; or program-list membership corroborated by 990 text
  MEDIUM - explicit lending language elsewhere in the 990 (mission, smaller/unweighted programs,
           Schedule O); or program-list membership alone; or an SDL award (consumer); or >= 2 indirect indicators
  LOW    - a single indirect indicator
  (no row) - no evidence. Absence of evidence is NOT evidence of absence.

Outputs:
  data/interim/crosswalks/program_list_matches.csv
  data/processed/cdfi_focus_evidence.csv         long evidence table (one row per piece of evidence)
  data/processed/cdfi_focus_category_scores.csv  CDFI x category features, score, confidence
  data/processed/loan_fund_classification.csv    one row per loan/VC fund: focus_1..3, evidence, confidence
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, PROCESSED, REFERENCE, normalize_domain, normalize_name  # noqa: E402

CATEGORIES = ["consumer", "mortgage_homeownership", "microenterprise", "small_business", "commercial_business",
              "commercial_real_estate", "residential_housing_development", "community_facilities",
              "intermediary_finance", "venture_equity", "agriculture"]
LENDING = re.compile(r"\b(loan|loans|lend\w*|financ\w*|credit|capital|invest\w*|mortgage\w*|underwrit\w*|borrow\w*|debt|funding|revolving)\b", re.I)
PROGRAM_SOURCES = {"program_1", "program_2", "program_3", "program_other", "program_ez", "schedule_o_part_iii"}
MISSION_SOURCES = {"mission", "activity_or_mission", "primary_exempt_purpose", "schedule_o_mission"}
NONDEP = ["Loan Fund", "Venture Capital Fund"]
CONF_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


# ---------------------------------------------------------------------------
# Program lists -> CDFI matches (all institution types)
# ---------------------------------------------------------------------------
def match_list(lst: pd.DataFrame, t: pd.DataFrame, list_name: str, name_col="name", web_col=None,
               state_col="state", zip_col="zip5", restrict_types=None) -> pd.DataFrame:
    pool = t if restrict_types is None else t[t.institution_type.isin(restrict_types)]
    by_dom = pool.dropna(subset=["website_domain"]).groupby("website_domain").cdfi_id.apply(list).to_dict()
    rows = []
    for r in lst.itertuples():
        nm = getattr(r, name_col)
        st = getattr(r, state_col) if state_col else None
        names = [normalize_name(re.sub(r"\([^)]*\)", " ", str(nm)))] + [normalize_name(a) for a in re.findall(r"\(([^)]+)\)", str(nm)) if len(a) > 3]
        cand, method, conf, score = [], None, None, None
        dom = normalize_domain(getattr(r, web_col)) if web_col else ""
        if dom and dom in by_dom:
            cand, method, conf, score = by_dom[dom], "website_domain", "high", 100.0
            if len(cand) > 1:  # several CDFIs share the website (affiliates): keep the best name match
                sims = {c: max(fuzz.token_sort_ratio(pool.set_index("cdfi_id").at[c, "name_core"], n) for n in names) for c in cand}
                top = max(sims.values())
                cand = [c for c, v in sims.items() if v == top]
        if not cand:
            sp = pool[pool.hq_state == st] if isinstance(st, str) else pool.iloc[0:0]
            hit = sp[sp.name_core.isin(names)]
            if len(hit):
                cand, method, conf, score = hit.cdfi_id.tolist(), "name_state_exact", "high", 100.0
            elif len(sp):
                sc = sp.name_core.map(lambda x: max(fuzz.token_sort_ratio(x, n) for n in names))
                best = sc.max()
                z = getattr(r, zip_col) if zip_col else None
                if best >= 92:
                    top = sp[sc == best]
                    zip_ok = isinstance(z, str) and (top.hq_zip5 == z).any()
                    cand, method = top.cdfi_id.tolist(), "fuzzy_name_state" + ("_zip" if zip_ok else "")
                    conf, score = ("medium" if zip_ok else "low"), round(float(best), 1)
        if len(cand) > 1:  # ambiguous: e.g. BHC + bank sharing a domain -> keep the non-BHC rows
            sub = t[t.cdfi_id.isin(cand) & (t.institution_type != "Bank Holding Company")]
            cand = sub.cdfi_id.tolist() if len(sub) == 1 else cand
        for c in cand:
            rows.append({"list_name": list_name, "list_entity_name": nm, "list_state": st, "cdfi_id": c,
                         "match_method": method, "match_confidence": conf, "name_similarity": score,
                         "ambiguous": len(cand) > 1})
    return pd.DataFrame(rows)


def program_list_matches(t: pd.DataFrame) -> pd.DataFrame:
    d = INTERIM / "program_lists"
    out = []
    if (d / "sba_microlenders.csv").exists():
        out.append(match_list(pd.read_csv(d / "sba_microlenders.csv", dtype=str), t, "SBA Microloan intermediary", web_col="website"))
    if (d / "sba_ca_sblcs.csv").exists():
        out.append(match_list(pd.read_csv(d / "sba_ca_sblcs.csv", dtype=str), t, "SBA Community Advantage SBLC", web_col="website"))
    if (d / "fhlb_members.csv").exists():
        f = pd.read_csv(d / "fhlb_members.csv", dtype=str)
        f = f[f.MEM_TYPE.str.contains("Community Development", na=False)].assign(zip5=lambda x: x.ZIP.str[:5])
        out.append(match_list(f, t, "FHLB member (CDFI membership type)", name_col="MEMBER_NAME", state_col="STATE", restrict_types=NONDEP))
    m = pd.concat(out, ignore_index=True)
    m.to_csv(INTERIM / "crosswalks" / "program_list_matches.csv", index=False)
    return m


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------
def load_rules() -> pd.DataFrame:
    r = pd.read_csv(REFERENCE / "focus_text_rules.csv", dtype=str, keep_default_na=False)
    r["rx"] = r.pattern.map(lambda p: re.compile(p, re.I))
    r["also_rx"] = r.requires_also.map(lambda p: re.compile(p, re.I) if p else None)
    r["ctx"] = r.requires_lending_context.str.upper().eq("TRUE")
    return r


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;:!?])\s+|\s+-\s+|\n+", str(text)) if len(s.strip()) > 3]


def text_evidence(texts: pd.DataFrame, filings: pd.DataFrame, rules: pd.DataFrame) -> pd.DataFrame:
    excl = rules[rules.rule_id.str.startswith("EXCL")]
    rules = rules[~rules.rule_id.str.startswith("EXCL")]
    tp = filings.set_index("object_id").tax_period_end.to_dict()
    rows = []
    for r in texts.itertuples():
        if r.text_source == "program_service_revenue":
            continue  # revenue descriptions are generic ("LOAN INTEREST"); NAICS codes are unreliable
        for s in sentences(r.text):
            ctx = bool(LENDING.search(s))
            for q in rules.itertuples():
                m = q.rx.search(s)
                if not m or (q.ctx and not ctx) or (q.also_rx is not None and not q.also_rx.search(s)):
                    continue
                if q.category == "mortgage_homeownership" and q.rule_id == "MTG1" and any(e.rx.search(s) for e in excl.itertuples()):
                    continue
                rows.append({"cdfi_id": r.cdfi_id, "category": q.category, "evidence_type": "irs_990_text",
                             "evidence_source": r.text_source, "rule_id": q.rule_id, "matched_text": m.group(0),
                             "evidence": s[:400], "program_expense_share": r.program_expense_share,
                             "program_expense_usd": r.expense_usd, "source_document": f"IRS 990 object {r.object_id}",
                             "source_period": tp.get(r.object_id)})
    return pd.DataFrame(rows)


def indirect_evidence(t: pd.DataFrame, lists: pd.DataFrame) -> pd.DataFrame:
    rows = []
    cat_of = {"SBA Microloan intermediary": "microenterprise", "SBA Community Advantage SBLC": "small_business",
              "FHLB member (CDFI membership type)": "housing_supporting"}
    for r in lists[lists.match_confidence.isin(["high", "medium"]) & ~lists.ambiguous].itertuples():
        rows.append({"cdfi_id": r.cdfi_id, "category": cat_of[r.list_name], "evidence_type": "program_list",
                     "evidence_source": r.list_name, "rule_id": "LIST", "matched_text": r.list_entity_name,
                     "evidence": f"Listed as {r.list_name}: {r.list_entity_name} ({r.list_state}); match {r.match_method}",
                     "source_document": r.list_name})
    aw = pd.read_csv(PROCESSED / "cdfi_awards.csv")
    aw = aw[aw.cdfi_id.notna() & aw.award_match_confidence.isin(["high", "medium"])]
    award_cat = {"SDL": ("consumer", "Small Dollar Loan Program award (funds small-dollar consumer loan programs)"),
                 "CMF": ("residential_housing_development", "Capital Magnet Fund award (affordable housing finance)"),
                 "NMTC": ("commercial_real_estate", "New Markets Tax Credit allocation (real-estate / business projects)"),
                 "HFFI-FA": ("community_facilities", "Healthy Food Financing Initiative award (food retail / access projects)")}
    for prog, (cat, why) in award_cat.items():
        g = aw[aw.award_program == prog].groupby("cdfi_id").award_year.agg(["min", "max", "count"])
        for cid, x in g.iterrows():
            rows.append({"cdfi_id": cid, "category": cat, "evidence_type": "cdfi_fund_award", "evidence_source": prog,
                         "rule_id": f"AWARD_{prog}", "matched_text": prog,
                         "evidence": f"{why}; {int(x['count'])} award(s) {int(x['min'])}-{int(x['max'])}",
                         "source_document": "CDFI Fund Searchable Awards Database"})
    name_rules = [("habitat for humanity|habitat", "mortgage_homeownership"), (r"\bmicro", "microenterprise"),
                  (r"school|health|clinic|child ?care", "community_facilities"), (r"assistive technology", "consumer"),
                  (r"\bhousing\b|\bhomes?\b", "residential_housing_development"), (r"\bbusiness\b", "small_business"),
                  (r"\bventure", "venture_equity"), (r"\bfarm|agricult", "agriculture")]
    for r in t[t.institution_type.isin(NONDEP)].itertuples():
        for pat, cat in name_rules:
            if re.search(pat, r.cdfi_name, re.I):
                rows.append({"cdfi_id": r.cdfi_id, "category": cat, "evidence_type": "organization_name",
                             "evidence_source": "Treasury certified list", "rule_id": "NAME", "matched_text": pat,
                             "evidence": f"Organization name: {r.cdfi_name}", "source_document": "CDFI Fund certified list"})
        if r.institution_type == "Venture Capital Fund":
            rows.append({"cdfi_id": r.cdfi_id, "category": "venture_equity", "evidence_type": "treasury_institution_type",
                         "evidence_source": "Treasury certified list", "rule_id": "TYPE_VC", "matched_text": "Venture Capital Fund",
                         "evidence": "CDFI Fund certifies the organization as a Venture Capital Fund", "source_document": "CDFI Fund certified list"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def score_categories(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.copy()
    # FHLB membership supports whichever housing category already has other evidence.
    sup = ev[ev.category == "housing_supporting"]
    ev = ev[ev.category != "housing_supporting"]
    housing = ev[ev.category.isin(["residential_housing_development", "mortgage_homeownership"])][["cdfi_id", "category"]].drop_duplicates()
    sup_rows = sup.drop(columns="category").merge(housing, on="cdfi_id")
    ev = pd.concat([ev, sup_rows], ignore_index=True)

    def feats(g: pd.DataFrame) -> pd.Series:
        txt = g[g.evidence_type == "irs_990_text"]
        prog = txt[txt.evidence_source.isin(PROGRAM_SOURCES)]
        share = prog.drop_duplicates(["evidence_source", "program_expense_usd"]).program_expense_share.sum(min_count=1)
        lists = g[g.evidence_type == "program_list"]
        strong_list = lists.evidence_source.isin(["SBA Microloan intermediary", "SBA Community Advantage SBLC"]).any()
        awards = set(g[g.evidence_type == "cdfi_fund_award"].evidence_source)
        indirect = (len(awards - {"SDL"}) + g.evidence_type.isin(["organization_name"]).any()
                    + lists.evidence_source.str.startswith("FHLB").any()
                    + txt.evidence_source.isin(["program_related_investment"]).any()
                    + (g.evidence_type == "treasury_institution_type").any())
        return pd.Series({
            "program_expense_share": min(share, 1.0) if pd.notna(share) else np.nan,
            "program_text_mention": len(prog) > 0,
            "program_text_no_expense_data": len(prog) > 0 and prog.program_expense_share.isna().all(),
            "mission_text_mention": txt.evidence_source.isin(MISSION_SOURCES).any(),
            "strong_program_list": bool(strong_list),
            "sdl_award": "SDL" in awards,
            "n_indirect_indicators": int(indirect),
            "n_evidence_rows": len(g),
            "evidence_types": ";".join(sorted(g.evidence_type.unique())),
        })

    f = ev.groupby(["cdfi_id", "category"]).apply(feats, include_groups=False).reset_index()
    share = f.program_expense_share.fillna(0)
    text_any = f.program_text_mention | f.mission_text_mention
    high = (share >= 0.25) | (f.program_text_no_expense_data & f.mission_text_mention) | (f.strong_program_list & text_any)
    med = text_any | f.strong_program_list | f.sdl_award | (f.n_indirect_indicators >= 2)
    low = f.n_indirect_indicators >= 1
    f["confidence"] = np.select([high, med, low], ["HIGH", "MEDIUM", "LOW"], default="NONE")
    f["score"] = (4 * share + 1.5 * f.program_text_mention + 1.0 * f.mission_text_mention + 2 * f.strong_program_list
                  + 0.75 * f.sdl_award + 0.5 * f.n_indirect_indicators).round(3)
    f = f[f.confidence != "NONE"]
    return f, ev


def classify(t: pd.DataFrame, f: pd.DataFrame, ev: pd.DataFrame, filings: pd.DataFrame) -> pd.DataFrame:
    nd = t[t.institution_type.isin(NONDEP)][["cdfi_id", "cdfi_name", "institution_type", "hq_state"]].copy()
    order = {c: i for i, c in enumerate(CATEGORIES)}
    f = f.assign(cat_order=f.category.map(order), conf_rank=f.confidence.map(CONF_RANK))
    f = f.sort_values(["cdfi_id", "score", "conf_rank", "cat_order"], ascending=[True, False, False, True])
    out = []
    for cid, g in f.groupby("cdfi_id"):
        rec = {"cdfi_id": cid}
        for k, r in enumerate(g.head(3).itertuples(), 1):
            rec[f"loan_fund_focus_{k}"] = r.category
            rec[f"loan_fund_focus_{k}_confidence"] = r.confidence
            rec[f"loan_fund_focus_{k}_score"] = r.score
            best = ev[(ev.cdfi_id == cid) & (ev.category == r.category)]
            best = best.assign(p=best.evidence_type.map({"irs_990_text": 0, "program_list": 1, "cdfi_fund_award": 2}).fillna(3),
                               s=-best.program_expense_share.fillna(0)).sort_values(["p", "s"])
            rec[f"loan_fund_focus_{k}_evidence"] = " | ".join(f"[{e.evidence_source}] {e.evidence[:220]}" for e in best.head(2).itertuples())
        rec["meaningful_activities"] = ";".join(g[g.conf_rank >= 2].category)
        rec["all_evidenced_activities"] = ";".join(g.category)
        rec["classification_source"] = ";".join(sorted(set(";".join(g.evidence_types).split(";"))))
        out.append(rec)
    c = nd.merge(pd.DataFrame(out), on="cdfi_id", how="left")
    c["classification_confidence"] = c.loan_fund_focus_1_confidence.fillna("UNKNOWN")
    c["classification_evidence"] = c.loan_fund_focus_1_evidence
    c["classification_method"] = np.where(c.loan_fund_focus_1.notna(),
                                          "evidence score (990 program text weighted by program expense, mission text, program lists, awards, indirect indicators)",
                                          "no usable public evidence")
    # Filing context
    fl = filings.set_index("cdfi_id")
    c["irs_990_tax_period_end"] = c.cdfi_id.map(fl.tax_period_end)
    c["irs_990_form"] = c.cdfi_id.map(fl.form)
    c["notes_loans_receivable_eoy_usd"] = c.cdfi_id.map(fl.notes_loans_receivable_eoy_usd)
    c["irs_990_total_assets_eoy_usd"] = c.cdfi_id.map(fl.total_assets_eoy_usd)
    c["program_related_investments_eoy_usd"] = c.cdfi_id.map(fl.program_related_investments_eoy_usd)
    c["loans_receivable_share_of_assets_pct"] = (c.notes_loans_receivable_eoy_usd / c.irs_990_total_assets_eoy_usd * 100).round(1)
    c["has_irs_990"] = c.irs_990_form.notna()
    return c


def main() -> None:
    t = pd.read_csv(INTERIM / "normalized_treasury" / "treasury_cert_list.csv", dtype={"hq_zip5": str})
    texts = pd.read_csv(INTERIM / "irs_990" / "program_texts.csv", dtype={"object_id": str, "ein": str})
    filings = pd.read_csv(INTERIM / "irs_990" / "filings.csv", dtype={"object_id": str, "ein": str})
    lists = program_list_matches(t)
    print("program-list matches:\n" + lists.groupby(["list_name", "match_confidence"]).cdfi_id.nunique().to_string())
    ev = pd.concat([text_evidence(texts, filings, load_rules()), indirect_evidence(t, lists)], ignore_index=True)
    ev = ev.merge(t[["cdfi_id", "institution_type"]], on="cdfi_id", how="left")
    f, ev_scored = score_categories(ev)
    f = f.merge(t[["cdfi_id", "institution_type"]], on="cdfi_id", how="left")
    ev_scored.to_csv(PROCESSED / "cdfi_focus_evidence.csv", index=False)
    f.to_csv(PROCESSED / "cdfi_focus_category_scores.csv", index=False)
    c = classify(t, f[f.institution_type.isin(NONDEP)], ev_scored, filings)
    c.to_csv(PROCESSED / "loan_fund_classification.csv", index=False)
    print(f"evidence rows: {len(ev_scored):,}; non-depository CDFIs classified: {c.loan_fund_focus_1.notna().sum()} / {len(c)}")
    print(pd.crosstab(c.loan_fund_focus_1.fillna("(unknown)"), c.classification_confidence).to_string())


if __name__ == "__main__":
    main()

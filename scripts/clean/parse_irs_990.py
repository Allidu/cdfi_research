"""Parse fetched IRS Form 990-series XML into tidy tables.

Outputs (data/interim/irs_990/):
  filings.csv        one row per selected filing: financial fields incl. Part X line 7 notes & loans receivable
  program_texts.csv  one row per text block usable as lending-focus evidence:
                     mission / activity description, Part III programs 1-3 + "other" (with expense amounts),
                     Schedule O explanations referencing Part III or the mission, program-related-investment
                     descriptions (Schedule D), program-service-revenue descriptions (+ NAICS BusinessCd)
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, RAW  # noqa: E402

NS = "{http://www.irs.gov/efile}"
SRC = RAW / "other" / "irs_990"
OUT = INTERIM / "irs_990"


def tx(el, path: str):
    if el is None:
        return None
    f = el.find(path)
    return f.text.strip() if f is not None and f.text else None


def num(el, path: str):
    v = tx(el, path)
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def parse(path: Path, meta: dict) -> tuple[dict, list[dict]]:
    root = ET.parse(path).getroot()
    hdr = root.find(f"{NS}ReturnHeader")
    form = root.find(f"{NS}ReturnData/{NS}IRS990")
    kind = "990"
    if form is None:
        form, kind = root.find(f"{NS}ReturnData/{NS}IRS990EZ"), "990EZ"
    if form is None:
        form, kind = root.find(f"{NS}ReturnData/{NS}IRS990PF"), "990PF"
    p = f".//{NS}"
    rec = {
        **meta, "form": kind,
        "tax_period_end": tx(hdr, f"{NS}TaxPeriodEndDt"),
        "total_assets_eoy_usd": num(form, f"{p}TotalAssetsGrp/{NS}EOYAmt") or num(form, f"{p}TotalAssetsEOYAmt")
                                 or num(form, f"{p}Form990TotalAssetsGrp/{NS}EOYAmt"),
        "notes_loans_receivable_eoy_usd": num(form, f"{p}OthNotesLoansReceivableNetGrp/{NS}EOYAmt"),
        "notes_loans_receivable_boy_usd": num(form, f"{p}OthNotesLoansReceivableNetGrp/{NS}BOYAmt"),
        "program_related_investments_eoy_usd": num(form, f"{p}InvestmentsProgramRelatedGrp/{NS}EOYAmt"),
        "total_liabilities_eoy_usd": num(form, f"{p}TotalLiabilitiesGrp/{NS}EOYAmt"),
        "net_assets_eoy_usd": num(form, f"{p}NetAssetsOrFundBalancesGrp/{NS}EOYAmt"),
        "total_revenue_usd": num(form, f"{p}CYTotalRevenueAmt") or num(form, f"{p}TotalRevenueAmt"),
        "total_program_expenses_usd": num(form, f"{p}TotalProgramServiceExpensesAmt"),
        "loan_outstanding_ind": tx(form, f"{p}LoanOutstandingInd"),
        "website_990": tx(form, f"{p}WebsiteAddressTxt"),
        "mission_desc": tx(form, f"{NS}MissionDesc") or tx(form, f"{p}PrimaryExemptPurposeTxt"),
    }
    texts: list[dict] = []

    def add(source, text, expense=None, revenue=None, naics=None):
        if text and len(text.strip()) > 2:
            texts.append({"cdfi_id": meta["cdfi_id"], "ein": meta["ein"], "object_id": meta["object_id"],
                          "text_source": source, "text": " ".join(text.split()), "expense_usd": expense,
                          "revenue_usd": revenue, "naics_business_cd": naics})

    if form is not None:
        add("mission", tx(form, f"{NS}MissionDesc"))
        add("activity_or_mission", tx(form, f"{NS}ActivityOrMissionDesc"))
        add("primary_exempt_purpose", tx(form, f"{p}PrimaryExemptPurposeTxt"))
        # Part III program 1 sits directly under IRS990 (Desc, ExpenseAmt, ...); programs 2-3 and "other" in groups.
        if kind == "990":
            add("program_1", tx(form, f"{NS}Desc"), num(form, f"{NS}ExpenseAmt"), num(form, f"{NS}RevenueAmt"))
            for g, label in [("ProgSrvcAccomActy2Grp", "program_2"), ("ProgSrvcAccomActy3Grp", "program_3")]:
                el = form.find(f"{NS}{g}")
                if el is not None:
                    add(label, tx(el, f"{NS}Desc"), num(el, f"{NS}ExpenseAmt"), num(el, f"{NS}RevenueAmt"))
            for el in form.findall(f"{NS}ProgSrvcAccomActyOtherGrp"):
                add("program_other", tx(el, f"{NS}Desc"), num(el, f"{NS}ExpenseAmt"), num(el, f"{NS}RevenueAmt"))
            for el in form.findall(f"{NS}ProgramServiceRevenueGrp"):
                add("program_service_revenue", tx(el, f"{NS}Desc"), None, num(el, f"{NS}TotalRevenueColumnAmt"), tx(el, f"{NS}BusinessCd"))
        else:
            for el in form.iter(f"{NS}ProgramSrvcAccomplishmentGrp"):
                add("program_ez", tx(el, f"{NS}DescriptionProgramSrvcAccomTxt"), num(el, f"{NS}ProgramServiceExpensesAmt"))
    for so in root.iter(f"{NS}SupplementalInformationDetail"):
        ref = (tx(so, f"{NS}FormAndLineReferenceDesc") or "").upper()
        if any(k in ref for k in ("PART III", "PART I, LINE 1", "MISSION", "PROGRAM", "LINE 4")):
            add("schedule_o_" + ("part_iii" if "III" in ref else "mission"), tx(so, f"{NS}ExplanationTxt"))
    for el in root.iter(f"{NS}InvstProgramRelatedOrgGrp"):
        add("program_related_investment", tx(el, f"{NS}Desc"), None, None)
    return rec, texts


def main() -> None:
    sel = pd.read_csv(SRC / "selected_filings.csv", dtype=str)
    sel = sel[sel.xml_file.notna()]
    recs, texts = [], []
    for r in sel.itertuples():
        meta = {"cdfi_id": r.cdfi_id, "ein": r.EIN, "object_id": r.OBJECT_ID, "return_type_index": r.RETURN_TYPE,
                "index_tax_period": r.TAX_PERIOD, "xml_file": r.xml_file}
        try:
            rec, tt = parse(SRC / "xml" / r.xml_file, meta)
        except ET.ParseError as e:
            rec, tt = {**meta, "parse_error": str(e)}, []
        recs.append(rec)
        texts += tt
    OUT.mkdir(parents=True, exist_ok=True)
    f = pd.DataFrame(recs)
    t = pd.DataFrame(texts)
    # Program expense shares within each filing (Part III programs only)
    prog = t.text_source.str.startswith("program_") & ~t.text_source.isin(["program_service_revenue", "program_related_investment"])
    tot = t[prog].groupby("object_id").expense_usd.sum(min_count=1)
    t["program_expense_share"] = (t.expense_usd / t.object_id.map(tot)).where(prog)
    f.to_csv(OUT / "filings.csv", index=False)
    t.to_csv(OUT / "program_texts.csv", index=False)
    print(f"IRS 990 parsed: {len(f)} filings, {len(t)} text blocks")
    print(t.text_source.value_counts().to_string())
    print("filings with Part X line 7 notes/loans receivable:", f.notes_loans_receivable_eoy_usd.notna().sum())


if __name__ == "__main__":
    main()

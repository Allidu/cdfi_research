# Source Inventory — U.S. CDFI Landscape

Investigated 2026-10-11. "Verified" means the URL/endpoint was requested from a script and the
response content inspected. Status column: **Ingested** (in the pipeline now), **Verified, not yet
ingested**, or **Not usable** (with reason).

## Summary

| # | Source | Status | Institution types | Key use |
|---|---|---|---|---|
| 1 | CDFI Fund – List of Certified CDFIs | Ingested | All | Master universe; RSSD for depositories |
| 2 | CDFI Fund – Searchable Awards Database (CSV export) | Ingested | All (awardees) | Award history |
| 3 | CDFI Fund – CDFI/NACA awardee data releases (TLR, CLR, ILR) | Verified, not ingested | Awardees only | Sector benchmarks only (anonymized) |
| 4 | CDFI Fund – ACR / certification application data | Not public | All | — |
| 5 | CDFI Fund – CIMS mapping system | Verified, not ingested | n/a (geography) | Investment-area eligibility, not per-CDFI |
| 6 | FDIC BankFind Suite API (institutions, financials, locations) | Ingested | Banks, BHC subsidiaries | Scale, lending mix, branches, identifiers |
| 7 | NCUA 5300 Call Report quarterly data | Ingested | Credit unions (NCUA-insured) | Scale, members, lending mix, branches |
| 8 | IRS EO Business Master File | Ingested (EIN + latest assets/revenue) | Nonprofit loan funds, VC | EIN crosswalk, coarse scale |
| 9 | IRS Form 990 e-file XML | **Ingested** (441 filings, range requests) | Nonprofit loan funds / VC funds | Loans receivable, program text → lending focus |
| 10 | IRS SOI annual exempt-org extract | Verified, not ingested | Nonprofit loan funds | Bulk 990 financials (lagged) |
| 11 | ProPublica Nonprofit Explorer API | Verified, not ingested | Nonprofits | Fallback EIN search, multi-year 990 summaries |
| 12 | Opportunity Finance Network (OFN) | Not usable (403 to scripts; member-only data) | OFN members | — |
| 13 | Aeris | Not usable (paid) | Rated CDFIs | — |
| 14 | FHFA FHLB membership list | **Ingested** (Q2 2026) | Loan funds that are FHLB members | Housing-finance supporting evidence |
| 15 | SBA Microlender list; SBA Community Advantage SBLC list | **Ingested** (153 / 141 lenders) | Loan funds (and any CDFI) | Microenterprise / small-business evidence |
| 16 | Census population estimates (state) | Ingested | n/a | Per-capita counts |
| 17 | Census ACS (api.census.gov) | Verified (metadata); **data queries need an API key** | n/a | Socioeconomic context |
| 18 | Census Gazetteer files | Verified, not ingested | n/a | Land area / density |
| 19 | Census Geocoder (batch) | Verified, not ingested | All (HQ addresses) | HQ county/tract for all types |
| 20 | Census ZCTA–county relationship file / HUD USPS crosswalk | Verified / HUD needs token | n/a | ZIP→county fallback |
| 21 | FDIC National Survey of Unbanked & Underbanked Households | Verified, not ingested | n/a | State (and large-MSA) unbanked rates |
| 22 | BLS LAUS county unemployment | Verified (bot-blocking; API works) | n/a | Current county unemployment |
| 23 | FFIEC NIC (National Information Center) bulk data | Not usable from scripts (403) | Banks, BHCs | Would resolve mid-tier BHC → bank links |

---

## 1. U.S. Treasury CDFI Fund — List of Certified CDFIs

* **Dataset:** "List of Certified Community Development Financial Institutions (CDFIs) with Contact Information".
* **URL:** linked from https://www.cdfifund.gov/programs-training/certification/cdfi as "Certified CDFIs as of
  <date>". Current: `https://www.cdfifund.gov/media/8018746/download?inline` → `CDFI_Cert_List_Manual_9.17.26.xlsx`.
  The script discovers the link by its title, so a new media ID does not break ingestion.
* **Access / format:** HTTP download, Excel (.xlsx). Sheets: list; counts by type; counts by state. No API.
* **Update frequency:** irregular (the list is "updated periodically" as recertifications are reviewed; observed
  as-of date 2026-09-17, `Last-Modified` header 2026-09-17). No official archive of earlier lists — the pipeline
  keeps dated raw snapshots and an ID registry to track entries over time.
* **Fields:** Organization Name, Financial Institution Type, RSSD ID, Native CDFI (Y/N), City, State, Zipcode,
  Address, Organization Website. Header block gives total (1,281) and Native total (65).
* **Identifiers:** **no CDFI Fund organization ID, no EIN.** RSSD ID (Federal Reserve) is present for 698 of 711
  depository CDFIs (and, unexpectedly, one loan fund).
* **Type labels:** Bank Holding Company, Bank or Thrift, Credit Union, Loan Fund, Venture Capital Fund (plus 7 rows
  labelled "Venture Capital" that the summary sheet counts as Venture Capital Fund).
* **Not included:** certification date, certification status detail (pending recertification), target market,
  service area, financials.
* **Limitations:** entries can be stale (merged banks and credit unions remain listed — see data-quality report);
  ZIPs formatted `NNNNN--NNNN`; free-text address with line breaks; one name has a trailing backtick; "Non given" websites.
* **Automated ingestion:** yes — `scripts/download/treasury_cert_list.py`.

## 2. CDFI Fund — Searchable Awards Database

* **URL:** https://www.cdfifund.gov/awards/state-awards ("Download CSV" link). Export filename is date-stamped,
  e.g. `https://www.cdfifund.gov/system/files/2026-09/2026-09-29_state-awards.csv`; discovered from the page each run.
* **Format:** CSV, 12,633 rows. Columns: Awardee, City, State, Year, Program, Amount (string "$1,750,000").
* **Coverage:** 1996–2025, 15 programs (CDFI-FA, CDFI-TA, NACA-FA/TA, CDFI-RRP, CDFI-ERP, BEA, NMTC, CMF, SDL,
  HFFI-FA, DF-FA, FEC, BOND, NACA historic). 2023 (340 rows) and 2025 (54 rows) look incomplete.
* **Identifiers:** none in CSV. The HTML table links each row to `/awards/state-awards/awardee-profile/{AwardNumber}?orgID={id}`
  — a CDFI Fund org ID exists publicly but only via HTML scraping (~1,264 pages).
* **Limitations:** name-only linkage (mixed case, d/b/a variants, spelling variants). NMTC amounts are tax-credit
  **allocations** and BOND amounts are **guarantees**, not grants. BEA/NMTC recipients include non-CDFIs.
* **Ingestion:** yes — `scripts/download/cdfi_fund_awards.py`, linked by `scripts/match/match_awards.py`.

## 3. CDFI Fund — Awardee data releases (TLR / CLR / ILR)

* **URL:** https://www.cdfifund.gov/documents/data-releases. Latest: `.../system/files?file=2024-12/FY2022_Data_Documentation_Instruction.zip`
  (TLR 1,002,505 loans from 787 orgs; CLR 387,484 rows from 371 orgs). Earlier: FY2018–FY2021; FY2003–2015 (CIIS) with ILR.
* **Fields:** TLR = loan-level purpose (MICRO, BUSINESS, HOMEPURCH, HOMEIMP, CONSUMER, RE construction/rehab by
  type, OTHER), amount, tract FIPS, terms, borrower demographics. CLR = consumer loans aggregated to tract. ILR (2003–2015
  only) = org-level assets, portfolio by purpose, clients.
* **Identifiers:** **anonymized.** Name, EIN, charter, address and website are marked "Publication: No". FY2003–21
  `org_id` is a pseudo-ID (not the Awards orgID); FY2022 renumbers 1..N. Cannot be joined to named institutions.
* **Coverage:** only CDFI/NACA (and RRP) financial-assistance recipients during their reporting period.
* **Use:** sector-level benchmarks (e.g., typical loan sizes by purpose), not institution enrichment.

## 4. CDFI Fund — data collected but not released

* **Collected:** certification applications (target market, service area, financials), Annual Certification and
  Data Collection Report (ACR), abbreviated TLRs from all certified CDFIs, certification dates (AMIS).
* **Released:** none at institution level. ACR FAQ: the Fund "does not publish proprietary or confidential
  information" and reserves the right to publish only name, date certified, type, address, website.
* **Aggregate only:** SNAP STAT (counts by year/type), performance snapshots, research reports.
* **Implication:** certification date, target market and service area are **missing by design** in this dataset.

## 5. CDFI Fund — CIMS mapping system

* https://www.cdfifund.gov/mapping-system — tract/county eligibility (investment areas, NMTC qualified tracts),
  downloadable .dbf files. No per-CDFI service areas. Useful later for tract-level context only.

## 6. FDIC BankFind Suite API

* **Base:** `https://api.fdic.gov/banks/` — endpoints `institutions`, `financials`, `locations`. No key required.
  Field definitions: `https://api.fdic.gov/banks/docs/{risview,institution,location}_properties.yaml`.
* **Format:** JSON (or CSV), paginated (limit 10,000).
* **Update frequency:** quarterly Call Report data (latest REPDTE 2026-06-30 at retrieval); institutions daily.
* **Identifiers:** CERT, FED_RSSD, RSSDHCR (top-tier holding company RSSD), NAMEHCR, LEI, NEWCERT (successor), PRIORNAME1-10.
* **Scale fields:** ASSET, DEP, EQ, NETINC (YTD), LNLSGR (total loans net of unearned income), LNLSGRS (gross),
  NUMEMP, OFFDOM. **Dollar fields are in $ thousands.**
* **Lending (RC-C):** LNRERSFM, LNRERSF2, LNRELOC (1–4 family), LNRECNFM, LNRECNOT (construction), LNREMULT, LNRENROW,
  LNRENROT, LNREAG, LNCI, LNAG, LNCRCD, LNCONRP, LNAUTO, LNCONOTH, LNOTHER, LS, LNMUNI, LNDEP, LNFG. Verified additive
  to LNLSGRS for all but 28 (mostly very large) banks; residual stored explicitly.
* **Small business (RC-C Part II, June report):** LNCI4/LNCI4N (C&I ≤ $1MM original), LNRENR4/LNRENR4N (nonfarm
  nonres RE ≤ $1MM), LNAG4/LNREAG4 (farm ≤ $500K) — amounts and counts.
* **Other:** SPECGRPN (FDIC asset-concentration specialization), MDI status, community-bank flag, lat/long, county FIPS;
  `locations` = every branch with state and county FIPS.
* **Not available:** number of borrowers/customers; consumer loan counts.
* **Covers:** banks/thrifts directly; BHCs only through subsidiary banks (BHC-level FR Y-9C is filed only by large BHCs).
* **Ingestion:** yes — `scripts/download/fdic_bankfind.py`.

## 7. NCUA 5300 Call Report quarterly data

* **URL:** page https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data; files
  `https://ncua.gov/files/publications/analysis/call-report-data-YYYY-MM.zip`.
* **Format:** zip of comma-delimited text (cp1252). FOICU.txt (profile), FS220*.txt (accounts), AcctDesc.txt
  (account dictionary), Credit Union Branch Information.txt, TradeNames.txt.
* **Update frequency:** quarterly (~8 weeks after quarter end; 2026-06 posted 2026-08-24).
* **Identifiers:** CU_NUMBER (charter), RSSD, JOIN_NUMBER.
* **Scale:** ACCT_010 assets, ACCT_025B loans ($), ACCT_025A loans (count), ACCT_018 shares & deposits,
  ACCT_083 members, ACCT_661A net income (YTD). Whole dollars.
* **Lending (13 lines, verified additive to ACCT_025B ±$11, counts additive to ACCT_025A exactly):**
  credit cards 396/993, PAL 397A/994A, private student 698A/963A, other unsecured 397/994, new vehicle 385/958,
  used vehicle 370/968, leases 002/954, other secured non-RE 698C/963C, 1st-lien 1–4 family 703A/959A, junior-lien
  386A/960A, other non-commercial RE 386B/960B, commercial RE-secured 718A5/900K4, commercial non-RE 400P/900P.
* **Other:** LIMITED_INC (low-income designation), IsMDI, county FIPS, branch sites with state/county.
* **Not covered:** Puerto Rico cooperativas (COSSEC-insured), privately insured credit unions.
* **Ingestion:** yes — `scripts/download/ncua_call_report.py`.

## 8. IRS Exempt Organizations Business Master File (EO BMF)

* **URL:** https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf;
  files `https://www.irs.gov/pub/irs-soi/eo_{st}.csv`. Monthly; cumulative (latest information only).
* **Fields:** EIN, NAME, SORT_NAME, STREET, CITY, STATE, ZIP, SUBSECTION, NTEE_CD, TAX_PERIOD, ASSET_AMT,
  INCOME_AMT, REVENUE_AMT, etc.
* **Use:** EIN crosswalk for loan/VC funds (name + state + ZIP), plus latest-return total assets and revenue.
* **Limitations:** tax-exempt organizations only (for-profit LLC funds absent); names uppercase/abbreviated;
  filing address may differ from Treasury address; group-exemption subordinates carry parent name in NAME;
  NTEE codes too noisy for lending focus; no loans receivable; single latest year; tax periods vary (2023–2026).
* **Ingestion:** yes — `scripts/download/irs_eo_bmf.py` (only states with loan/VC funds).

## 9. IRS Form 990 e-file XML

* **URL:** https://www.irs.gov/charities-non-profits/form-990-series-downloads; index
  `https://apps.irs.gov/pub/epostcard/990/xml/{YYYY}/index_{YYYY}.csv`; monthly zips `{YYYY}_TEOS_XML_{MM}{A-D}.zip`.
* **Key fields:** Part X line 7 notes/loans receivable (`OthNotesLoansReceivableNetGrp/EOYAmt`), program-related
  investments, total assets/liabilities/net assets, revenue, program service revenue, mission and Part III program text.
* **Access:** zips are large (≈300 MB) but support HTTP range requests; single returns can be extracted with a few
  requests. Verified on Vermont Community Loan Fund's FY2025 return.
* **Limitations:** 990-EZ filers lack Part X detail; 1–2 year lag; schema variations by year.
* **Status (phase 2): ingested.** `scripts/download/irs_990_xml.py` selects the latest return per EIN from index years
  2024–2026 (435 Form 990, 2 990-EZ, 4 990-PF; 6 EINs had no e-filed return) and extracts members by HTTP range
  requests. Gotchas handled: index batch IDs with lower-case suffixes; members filed in a sibling archive (`_05B`
  instead of `_05A`); Deflate64 compression in some archives (needs `zipfile-deflate64`). Parsed fields: Part III
  programs 1–3 + other with expenses, mission, Schedule O, PRI descriptions, program-revenue descriptions with NAICS
  codes (NAICS rejected as unreliable), Part X total assets and notes & loans receivable.

## 10–11. IRS SOI extract; ProPublica Nonprofit Explorer

* SOI: https://www.irs.gov/statistics/soi-tax-stats-annual-extract-of-tax-exempt-organization-financial-data —
  `24eoextract990.zip` (includes `notesloansrcvblend`, `totassetsend`); lags the XML.
* ProPublica: `https://projects.propublica.org/nonprofits/api/v2/search.json?q=...&state[id]=XX` and
  `/organizations/{EIN}.json`. No key; attribution required; lacks loans receivable. Good fallback for unmatched EINs.

## 12–13. OFN and Aeris

* OFN (ofn.org): CDFI Locator and publications return 403 to scripted requests; locator covers members only;
  "Side by Side" is peer-group aggregates. Not suitable for automated ingestion.
* Aeris: subscription product; not used.

## 14–15. FHFA FHLB membership; SBA lender lists

* FHFA: https://www.fhfa.gov/data/fhlb-membership — quarterly XLSX (`fhlb_members_q22026.xlsx`), 83 members with
  MEM_TYPE "Community Development Financial Institution"; includes CERT/FED_ID/NCUA_ID for depositories.
* SBA microlenders: https://www.sba.gov/loans/microloans/list-of-microlenders/ (≈16 HTML pages; name, states served,
  address). SBA Community Advantage SBLCs: XLSX on legacy.sba.gov (141 lenders). Both need name+address matching.
* **Status (phase 2): ingested** by `scripts/download/program_lists.py` (SBA pages parsed from HTML; Community Advantage
  XLSX discovered on the SBA page and served from legacy.sba.gov; FHFA XLSX discovered from the FHFA page). Matched to
  certified CDFIs by website domain, then name + state.

## 16–20. Census

* **Population estimates (ingested):** `https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv` (no key).
* **ACS:** latest vintage 2024 (`/data/2024/acs/acs5`, `/acs1`, `/profile`, `/subject`); 2025 not yet in API.
  **Data queries now require a free API key** (keyless requests return 302 to `missing_key.html`); metadata endpoints
  work without one. Verified variable IDs: population DP05_0001E / B01003_001E; LFPR DP03_0002PE; unemployment
  DP03_0009PE; median household income DP03_0062E; per-capita income DP03_0088E; poverty DP03_0128PE; bachelor's+
  DP02_0068PE; broadband DP02_0154PE; working-age 18–64 = DP05_0021E − DP05_0029E (or S0101). County level needs acs5.
* **Gazetteer:** `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip` (ALAND_SQMI).
* **Geocoder:** `https://geocoding.geo.census.gov/geocoder/geographies/addressbatch` (≤10,000 rows per batch, no key,
  vintage ACS2024_Current) → county/tract for every HQ including loan funds.
* **Crosswalks:** `rel2020/zcta520/tab20_zcta520_county20_natl.txt` (area-weighted); HUD USPS ZIP crosswalk API (token).
* **Connecticut:** ACS 2024 uses planning regions (091xx), not legacy counties — normalize before joining.

## 21. FDIC National Survey of Unbanked and Underbanked Households

* Latest released survey: **2023** (2025 survey not yet published). Hub https://www.fdic.gov/household-survey;
  downloads https://www.fdic.gov/household-survey/data-downloads-and-resources (household CSV `hh2023_analys.csv`,
  multi-year files on S3). Pre-tabulated: https://household-survey.fdic.gov/custom-data and `/five-year`.
* **Reliable geography:** national, state; MSA for larger MSAs (better with pooled 5-year tool). **No county.**
* **Join level:** state (and CBSA where available) — never attach to an individual CDFI as borrower-level data.

## 22. BLS LAUS

* `https://www.bls.gov/web/metro/laucntycur14.zip` (14-month county data); BLS blocks most scripted downloads.
  Reliable alternative: BLS API v1/v2 (`LAUCN{county FIPS}00000000003` = unemployment rate). Oct–Nov 2025 missing
  (appropriations lapse).

## 23. FFIEC NIC

* `https://www.ffiec.gov/npw/FinancialReport/DataDownload` and the relationships/attributes zip endpoints returned
  403 to scripted requests. Would provide full parent–offspring relationships (resolving mid-tier BHCs). Manual
  download into `data/raw/other/ffiec_nic/` is a straightforward next step.

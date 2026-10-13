# Methodology

## 1. Purpose and scope

The dataset maps the U.S. certified-CDFI market so Jobago can identify CDFIs whose borrowers' repayment
depends on employment income and which have the scale to pilot a career-transition product. This first pass
builds the auditable base: universe, identifiers, scale, lending mix, award history and coverage. **No Jobago
ranking or score has been produced.**

## 2. Pipeline

```
download/  treasury_cert_list → fdic_bankfind → ncua_call_report → cdfi_fund_awards → census_population
clean/     normalize_treasury → normalize_fdic → normalize_ncua → (download/irs_eo_bmf)
match/     build_crosswalk → match_awards
analyze/   build_processed → data_quality_report → export_outputs
```
`./run_pipeline.sh` runs all steps. Raw downloads are cached under `data/raw/<source>/<date>/` with a
`.manifest.json` (URL, retrieval timestamp, SHA-256, HTTP Last-Modified). Raw files are never overwritten unless a
download script is run with `--force`. A full rerun from cache is deterministic (verified: identical master checksum).

## 3. Master universe

* Source: CDFI Fund certified list (one row per listed organization; 1,281 as of 2026-09-17). Row count and type
  counts are checked against the totals Treasury prints in the workbook.
* **Stable internal ID (`cdfi_id`, e.g. `CDFI00042`)**: Treasury publishes no organization ID, so IDs are held in an
  append-only registry (`data/reference/cdfi_id_registry.csv`). Each run re-matches listed organizations to the
  registry by RSSD, then exact normalized name + state, then website domain + state + type. New organizations get new
  IDs; organizations that drop off the list are kept and marked `currently_listed = False` (supports tracking
  decertifications across releases). Organization names are never the primary key.
* Normalizations: trailing characters stripped from names (original kept in `cdfi_name_as_listed`); "Venture Capital"
  → "Venture Capital Fund"; ZIP split into ZIP5/ZIP4; "Non given" websites → missing; website domain extracted.
* Duplicates are flagged, not removed: `dup_rssd_in_list` (BlueOx / IGNITE share one RSSD and one NCUA charter),
  `shares_website_with` (112 CDFIs, mostly BHC + bank pairs and affiliated entities).

## 4. Crosswalk strategy

Priority order (strongest first); each accepted link records `match_method`, `match_confidence`,
`name_similarity`, `manual_review_required`, `review_reason`.

| Type | Step | Method | Confidence |
|---|---|---|---|
| Bank/thrift | Treasury RSSD = FDIC `FED_RSSD` (active) | `rssd_exact` | high (review if names diverge) |
| BHC | Treasury RSSD = FDIC `RSSDHCR` of active banks → subsidiary banks | `rssd_holding_company` | high |
| BHC | RSSD is itself an FDIC bank (Treasury mislabel) | `rssd_exact` + review | high |
| Bank/BHC | RSSD only on an inactive FDIC record → record it + follow `NEWCERT` to successor | `rssd_exact_inactive`, `fdic_newcert_chain` | low, review; successor financials **not** attributed |
| BHC | Not a top-tier holder in FDIC data → certified bank sharing the BHC's website proposed | `shared_website_with_certified_bank` | low, review; not used for financials |
| Credit union | Treasury RSSD = NCUA FOICU `RSSD` | `rssd_exact` | high |
| Credit union | Puerto Rico cooperativas | `not_in_ncua_scope` | n/a (COSSEC-supervised) |
| Credit union | RSSD only in prior NCUA quarter | `absent_from_latest_ncua` | n/a (likely merged) |
| Depository w/o RSSD | exact normalized name + state (+ city) | `name_state_exact` | medium (city match) / low; review |
| Depository | fuzzy name within state (token_sort ≥ 90) | `fuzzy_name_state` | low; review; ambiguous ties rejected |
| Loan/VC fund | IRS EO BMF exact normalized name (or SORT_NAME) + state + ZIP5 | `name_state_exact_zip` | high |
| Loan/VC fund | exact name + state, ZIP differs | `name_state_exact` | medium; review |
| Loan/VC fund | fuzzy name ≥ 90 + same ZIP5 | `fuzzy_name_state_zip` | low; review (accepted) |
| Loan/VC fund | weaker fuzzy candidates | `fuzzy_name_state*` | candidate recorded, **EIN not accepted** |
| Loan/VC fund | several exact candidates | `ambiguous` | not accepted |

Credit unions (IRS subsection 01/14) are excluded from the BMF pool to stop suffix-stripped name collisions.
Only `high`/`medium` matches with relationship `self` or `subsidiary_bank` feed financials and lending.
All review-flagged rows are in `research/unresolved_matches.csv`.

**Double counting.** 146 certified BHCs own only banks that are themselves separately certified. Their financials
are kept (scope `sum_of_fdic_insured_subsidiaries`) but `include_in_market_totals = False`; `related_certified_cdfi_ids`
links them. Market-level sums must filter on this flag.

## 5. Scale variables

* Banks: FDIC Call Report for REPDTE 2026-06-30 (×1,000 to USD). BHCs: sum over matched subsidiary banks.
* Credit unions: NCUA 5300 for 2026-06 (cycle date 2026-06-30). Members = ACCT_083.
* Loan/VC funds: IRS EO BMF `ASSET_AMT`, `REVENUE_AMT` stored in **separate** `irs_*` columns with `irs_tax_period`
  — never merged into `total_assets_usd`, because definitions and periods differ.
* Growth (1-year, vs 2025-06-30) computed only where the same regulatory entities exist in both periods; merger
  effects are not removed.

## 6. Lending-category normalization (standardized taxonomy)

* Source categories are kept verbatim in `cdfi_lending.csv` (`source_field`, `source_category`). The mapping is the
  reviewed reference table `data/reference/lending_category_map.csv` (one row per regulator field or field expression,
  with the reasoning in `notes`). Mapping expressions such as `LNCI - LNCI4` are evaluated in `normalize_fdic.py`.
* **Standardized categories:** `consumer`, `mortgage_homeownership`, `microenterprise`, `small_business`,
  `commercial_business`, `commercial_real_estate`, `residential_housing_development`, `community_facilities`,
  `intermediary_finance`, `venture_equity`, `agriculture` (added: many rural CDFI banks are farm lenders), `other`; plus
  non-additive memo groups `small_business_memo` (LNCI4, LNRENR4) and `small_farm_memo`.

| Category | Banks (FDIC RC-C) | Credit unions (NCUA 5300) | Loan/VC funds |
|---|---|---|---|
| consumer | cards, other revolving, auto, other consumer | cards, PAL, private student, other unsecured, new/used auto, leases, other secured non-RE | evidence |
| mortgage_homeownership | 1–4 family first & junior liens, HELOCs | 1st/junior-lien 1–4 family, other non-commercial RE | evidence |
| microenterprise | **proxy:** C&I with original amount ≤ $100K (LNCI1) | not observable | evidence (+ SBA Microloan list) |
| small_business | C&I $100K–$1M (LNCI2+LNCI3) | member commercial loans not RE-secured (ACCT_400P), unless avg. balance > $1M | evidence (+ SBA Community Advantage list) |
| commercial_business | C&I > $1M (LNCI − LNCI4) | ACCT_400P where average balance > $1M (17 CUs) | evidence |
| commercial_real_estate | owner-occupied & investor nonfarm nonres, other construction/land | commercial RE-secured (ACCT_718A5; includes multifamily/farm) | evidence |
| residential_housing_development | multifamily, 1–4 family construction | not separable | evidence (+ CMF awards) |
| community_facilities | not observable | not observable | evidence |
| intermediary_finance | loans to nondepository FIs (LNNDEPC; reported by ~2% of banks) | not observable | evidence |
| venture_equity | not observable | not observable | evidence (+ Treasury VC type) |
| agriculture | farmland RE, agricultural production | not separable (inside commercial) | evidence |
| other | all other loans, leases, municipal, depository, foreign govt, residual | — | — |

Decisions and accounting issues:
* **Overlaps.** The regulatory small-business measure (C&I + nonfarm-nonres RE with original amount ≤ $1MM) overlaps
  CRE, so it is kept as the non-additive `small_business_exposure_pct`; the additive `small_business` category is C&I
  only. Size bands are by *original* amount but balances are *current*.
* **Mortgages vs residential real estate.** FDIC 1–4 family closed-end/HELOC → `mortgage_homeownership` (includes some
  investor 1–4 family rentals; the Call Report does not split owner-occupancy). 1–4 family construction and
  multifamily → `residential_housing_development` (project finance). NCUA non-commercial RE → mortgage; NCUA commercial
  RE (incl. multifamily) → CRE.
* **Small business vs commercial.** Banks: size bands from RC-C Part II (verified `LNCI4 = LNCI1+LNCI2+LNCI3` and
  `LNCI4 ≤ LNCI` for every bank). Credit unions: no size bands; member business loans default to `small_business`
  (median average balance ≈ $66K) and are reclassified at institution level when the average balance per loan exceeds $1M.
* **Reconciliation.** FDIC categories sum to gross loans (`LNLSGRS`) except 28 (mostly very large) filers; their gap is an
  explicit `unallocated_residual` row in `other`. NCUA's 13 lines sum to ACCT_025B (±$11) for every credit union, so any
  NCUA category without a row is a true zero. Categories a regulator cannot observe are **missing**, never zero.
* **Intermediary.** `LNNDEPC` is broader than CDFI-style intermediary lending (includes mortgage/finance companies) and
  is missing for ~98% of banks; there it stays inside `other`.

## 7. Lending focus — banks and credit unions (portfolio basis)

* `primary_lending_focus` = standardized category with the largest share of total loans, excluding `other`.
  `secondary_` / `tertiary_lending_focus` = next categories if ≥ 10%. `meaningful_lending_activities` = all categories
  ≥ 10% (`n_meaningful_activities`). Flags (`consumer_lending_flag`, …) = share ≥ 10%; missing where not observable.
* `primary_focus_confidence`: HIGH if top share ≥ 50%; MEDIUM if 30–50% and the lead over the second category is
  ≥ 5 pp; LOW otherwise (`primary_focus_near_tie` marks leads < 5 pp). `portfolio_concentration`: specialized
  (≥ 50%), focused (30–50%), diversified (< 30%).
* **Rule diagnostics** (`research/market_structure_report.md` §1): near-ties affect ~21% of banks and ~9% of credit unions;
  splitting C&I into size bands changes the primary focus of only 4 banks, so the rule is not an artifact of category
  granularity. `primary_borrower_type` rolls categories up to who repays (individual = consumer + mortgage;
  business = micro + small + commercial + agriculture; property/project = CRE + housing development + facilities),
  which is robust to category granularity.
* FDIC `SPECGRPN` is kept as `fdic_specialization_group` (asset-based, mostly "All Other") but not used for focus.
* Program lists also count for depositories: SBA Microloan / Community Advantage participation sets
  `microenterprise_flag` / `small_business_flag` to True even where balances are below 10%.

## 8. Missing-data handling

Nothing is imputed. Missing means "not available from the source"; zero means "reported as zero". Award counts of 0
mean "no award linked", not necessarily "no award received". Every coverage rate in the data-quality report is computed.

## 9. Reporting-period alignment

FDIC and NCUA both use 2026-06-30 (aligned). Net income is 6-month YTD. IRS values reflect each organization's latest
return (tax periods 2023-12 to 2026-03). Awards are cumulative 1996–2025 by award year. Treasury list as of 2026-09-17.
Mixing these periods in one metric is avoided; each field carries its own date column.

## 10. Geography

Three concepts are kept separate: **HQ** (Treasury address; county FIPS from FDIC/NCUA records for depositories),
**branch footprint** (FDIC/NCUA branch sites — a physical presence measure, not a service area), and **service area /
lending geography** (not publicly available → left missing with a note). HQ county exists only for directly matched
banks and credit unions; Census batch geocoding would extend it to all CDFIs.

## 11. Jobago-related derived variables still pending

* `employment_income_dependency` — not computed. Draft mapping in
  `data/reference/employment_income_dependency_map_DRAFT.csv`; apply only after review.
* `borrower_reach` — credit-union members only; loan funds need annual-report research.
* Market segments and size tiers **are now implemented** (sections 14–15) as descriptive groupings, not scores.

## 12. Schema

| Table | Grain | Key fields |
|---|---|---|
| `cdfi_master` | 1 row / certified CDFI | `cdfi_id`, identity, external IDs, latest scale, lending shares, focus fields, flags, award summary, coverage flags |
| `cdfi_crosswalk` | CDFI × external ID | `cdfi_id`, `id_system` (RSSD, FDIC_CERT, NCUA_CHARTER, LEI, EIN), `id_value`, `relationship`, `match_method`, `match_confidence`, `manual_review_required` |
| `cdfi_financials` | CDFI × reporting date | assets, loans, deposits/shares, equity, net income YTD, members, employees, `financial_scope`, `entity_ids` |
| `cdfi_lending` | CDFI × date × source category | `source_field`, `source_category`, `standardized_category`, `additive`, `loan_balance_usd`, `loan_count`, `percent_of_total_loans` |
| `cdfi_awards` | award row | awardee name/city/state, year, program, amount, `award_type`, `counts_toward_grant_total`, `cdfi_id` (nullable), match fields |
| `cdfi_geography` | 1 row / CDFI | HQ fields, HQ county, branch footprint, service-area fields (missing) |
| `cdfi_qualitative` | CDFI × attribute × evidence | `attribute`, `value`, `source_url`, `retrieval_date`, `evidence`, `confidence` (empty; for Phase 12) |
| `state_summary` | HQ state | counts by type, population, per-capita, depository assets (deduplicated), CU members |

All processed tables are written as CSV and Parquet. Reference tables: `data/reference/`.

## 13. Variable availability

| Variable | Banks | BHCs | Credit unions | Loan funds | VC funds |
|---|---|---|---|---|---|
| Name, type, HQ address, website, Native flag | Direct (Treasury) | Direct | Direct | Direct | Direct |
| Certification date, target market, service area | **Unavailable publicly** | Unavailable | Unavailable | Unavailable | Unavailable |
| RSSD | Direct | Direct | Direct | — | — |
| FDIC cert / NCUA charter / LEI | Derived (crosswalk) | Derived (subsidiaries) | Derived (NCUA; not PR coops) | — | — |
| EIN | — | — | — | Derived (BMF match, ~79%) | Derived (~56%) |
| Assets, loans, deposits, net income | Direct (Call Report) | Derived (sum of subs) | Direct (5300) | Partial: assets/revenue only (IRS BMF) | Partial (IRS) |
| Loans outstanding (loan funds) | — | — | — | Derivable (990 Part X line 7) – next step | Derivable/limited |
| Members / borrower count | Unavailable | Unavailable | Direct (members) | Manual research (annual reports) | Manual |
| Loan counts | Small-business memo only | Same | Direct (all lines) | Manual | Manual |
| Lending mix | Direct (RC-C) | Derived | Direct (5300) | Manual / 990 text classification | Manual |
| Small-business exposure | Direct proxy (RC-C Part II) | Derived | Not separable (commercial only) | SBA lists + manual | — |
| Microenterprise / community facilities / venture | Unavailable | Unavailable | Unavailable | SBA microlender list + manual | Manual |
| Branch footprint | Direct (FDIC locations) | Derived | Direct (NCUA branches) | Not applicable / manual | — |
| HQ county / lat-long | Direct (FDIC) | Derivable (geocoder) | Direct (county) | Derivable (geocoder) | Derivable |
| Award history | Derived (name match) | Derived | Derived | Derived | Derived |
| Socioeconomic context | Derivable (ACS at HQ/branch counties; needs key) | Same | Same | HQ only | HQ only |
| Technology / borrower support / workforce services | Manual research | Manual | Manual | Manual | Manual |

## 13. Loan-fund lending-focus classification (evidence basis)

Applies to the 561 loan funds and 9 VC funds (`scripts/enrich/classify_lending_focus.py`).

**Sources, strongest first**
1. IRS Form 990 Part III program descriptions with each program's expense share (`scripts/download/irs_990_xml.py`
   fetches the latest 990 per EIN by HTTP range requests; 441 of 447 EINs had an e-filed return; parsed by
   `scripts/clean/parse_irs_990.py`). Part X line 7 notes & loans receivable is also extracted (369 filings).
2. 990 mission / activity statements and Schedule O explanations of Part III or the mission.
3. Federal program lists (`scripts/download/program_lists.py`): SBA Microloan intermediaries (153; 92 matched to
   certified CDFIs), SBA Community Advantage SBLCs (141; 92 matched), FHFA FHLB members of CDFI type (83; 74 matched).
   Matching by website domain, then exact normalized name + state, then fuzzy name + state (+ZIP).
4. CDFI Fund award programs with a defined purpose: SDL (small-dollar consumer loans), CMF (affordable housing),
   NMTC (real-estate/business projects), HFFI (healthy food). Name keywords and FHLB membership are weakest.

**Text rules** are in `data/reference/focus_text_rules.csv` (regex per category; many require a lending word —
loan, lend, financ*, credit, capital, invest*, mortgage, borrow*, debt, funding, revolving — in the same sentence;
one exclusion rule removes "commercial/multifamily mortgage" from homeownership). Every match is stored as an
evidence row with the sentence, source block, program expense share and filing ID (`data/processed/cdfi_focus_evidence.csv`).
NAICS business codes on program revenue were examined and **rejected** (522291 "consumer lending" is used by most
business lenders).

**Scoring and confidence** (per CDFI × category; `cdfi_focus_category_scores.csv`)
* score = 4×(Part III expense share) + 1.5×(Part III mention) + 1×(mission mention) + 2×(SBA list) + 0.75×(SDL award)
  + 0.5×(each indirect indicator).
* HIGH: explicit lending language in Part III programs covering ≥ 25% of program expenses, or a program-list
  membership corroborated by 990 text. MEDIUM: explicit 990 language elsewhere, a program list alone, an SDL award, or
  ≥ 2 indirect indicators. LOW: one indirect indicator. No evidence → no row (UNKNOWN overall).
* `loan_fund_focus_1..3` = top three categories by score, each with its own confidence and evidence snippets;
  `classification_confidence` = confidence of focus 1. Evidence flags are True where MEDIUM/HIGH and **blank (unknown)
  otherwise** — absence of evidence is not evidence of absence.
* Validation: random-sample review of classifications against evidence led to rule fixes (down-payment terms on business
  loans, "financial cooperatives" as intermediary rather than small business, loans to "businesses", assistive-technology
  and vehicle-purchase programs). Residual risks: text describes activities, not dollar shares; multi-purpose lenders
  can be ranked by how much they write about a program.

## 14. Size tiers (institution-type specific)

| Group | Metric | S | M | L | XL |
|---|---|---|---|---|---|
| Banks & BHCs | total assets (BHC = sum of subsidiaries) | < $250M | $250M–$1B | $1B–$10B | ≥ $10B |
| Credit unions | total assets | < $100M | $100M–$500M | $500M–$2B | ≥ $2B |
| Credit unions (reach) | members | < 10K | 10K–50K | 50K–200K | ≥ 200K |
| Loan / VC funds | 990 total assets EOY (else IRS BMF) | < $10M | $10M–$50M | $50M–$250M | ≥ $250M |
| Loan / VC funds (lending) | 990 notes & loans receivable | < $5M | $5M–$25M | $25M–$100M | ≥ $100M |

Thresholds follow common supervisory/peer conventions (community-bank $1B/$10B lines; NCUA's $500M "complex" line;
CDFI loan-fund peer groups) and are deliberately different across types. `size_percentile_within_type` gives a
threshold-free alternative. Zero or missing assets → no tier.

## 15. Market segmentation

Segments group CDFIs by **primary** lending focus (descriptive, not a ranking):

| Code | Segment | Primary focus |
|---|---|---|
| A | Consumer-focused | consumer |
| B | Microenterprise / very small business | microenterprise; or small_business **and** (SBA Microloan intermediary or HIGH microenterprise evidence) for loan funds |
| C | Mortgage / homeownership | mortgage_homeownership |
| D | Small business / commercial / agricultural (D1 small business, D2 larger commercial, D3 agricultural) | small_business, commercial_business, agriculture |
| E | Real estate, housing development & community facilities (E1 CRE, E2 housing development, E3 facilities) | commercial_real_estate, residential_housing_development, community_facilities |
| F | Intermediary / venture / other (F1, F2) | intermediary_finance, venture_equity |
| U | Unclassified | no primary focus |

Multi-focus is kept separately: `segment_memberships` lists every segment in which the CDFI has a meaningful activity
(portfolio share ≥ 10% or MEDIUM/HIGH evidence), and `multi_focus` marks two or more meaningful activities.
`segment_confidence` = primary-focus confidence. Segment statistics (`data/outputs/tables/segment_*.csv`,
`research/market_structure_report.md`) deduplicate BHCs via `include_in_market_totals` and never add Call Report loans
to 990 loans receivable.

# Data Dictionary

Conventions: **R** = reported by a source (possibly unit-converted), **D** = derived in this project.
Types: str, int, float, bool, date (ISO `YYYY-MM-DD`). USD amounts are whole dollars (FDIC values ×1,000).
"Types" column: B = Bank or Thrift, H = Bank Holding Company, C = Credit Union, L = Loan Fund, V = Venture Capital Fund.

## cdfi_master (one row per certified CDFI)

### Identity and certification

| Field | R/D | Type | Definition | Source / original field | Transformation | Types | Period | Limitations |
|---|---|---|---|---|---|---|---|---|
| cdfi_id | D | str | Stable internal ID (`CDFI#####`) | ID registry | Assigned once; re-matched by RSSD → name+state → domain | All | — | Not a Treasury ID |
| cdfi_name | R | str | Organization name | Treasury `Organization Name` | Stray backticks/whitespace removed | All | List as-of date | Legal vs trade names mixed |
| cdfi_name_as_listed | R | str | Name exactly as published | Treasury | none | All | | |
| institution_type | R | str | Treasury financial institution type | Treasury `Financial Institution Type` | "Venture Capital" → "Venture Capital Fund" | All | | |
| institution_type_as_listed | R | str | Original label | Treasury | none | All | | |
| native_cdfi | R | bool | Certified Native CDFI | Treasury `Native CDFI (Y/N)` | Y→True | All | | |
| certification_status | D | str | "Certified (on current CDFI Fund list)" | Treasury list presence | constant | All | | Pending recertifications not visible |
| certification_date | — | date | Always missing | Not published | — | All | | Collected by CDFI Fund, not released |
| hq_address, hq_city, hq_state | R | str | HQ address as listed | Treasury `Address`, `City`, `State` | newlines → ", " | All | | Some are PO boxes |
| hq_zip5, hq_zip4 | R | str | ZIP / ZIP+4 | Treasury `Zipcode` (`NNNNN--NNNN`) | split; `0000` → missing | All | | |
| website, website_domain | R/D | str | Website; normalized domain | Treasury `Organization Website` | "Non given" → missing; domain parsed | All | | |
| rssd_id | R | int | Federal Reserve RSSD ID as listed | Treasury `RSSD ID` | "-" → missing | B,H,C (+1 L) | | BHC rows carry the holding company's RSSD |
| source, source_file, source_as_of_date, retrieval_date | R | str/date | Provenance of the universe row | Treasury manifest | — | All | | |
| id_assignment_method | D | str | How `cdfi_id` was (re)assigned this run | registry match | — | All | | |
| dup_rssd_in_list | D | bool | RSSD appears on >1 Treasury row | Treasury | — | B,H,C | | |
| shares_website_with | D | str | Other `cdfi_id`s with the same domain | Treasury | `;`-joined | All | | Signals affiliates |

### External identifiers and crosswalk status

| Field | R/D | Type | Definition | Source | Types | Limitations |
|---|---|---|---|---|---|---|
| fdic_cert | D | str | FDIC certificate of the institution itself (high/medium/low incl. inactive) | crosswalk (`relationship=self`) | B | Inactive certs possible; see `regulator_match_status` |
| fdic_cert_subsidiaries | D | str | FDIC certs of subsidiary banks | crosswalk (`subsidiary_bank`) | H | Top-tier holder only (FDIC `RSSDHCR`) |
| ncua_charter | D | str | NCUA charter number | crosswalk | C | Not for PR cooperativas |
| lei | D | str | Legal Entity Identifier of bank / subsidiary | FDIC `LEI` | B,H | Many small banks lack LEI |
| ein | D | str | IRS EIN | IRS EO BMF match | L,V | Name-based; review flags in crosswalk |
| regulator_match_status | D | str | `matched_with_current_financials` / `no_current_regulatory_financials` | crosswalk + financials | All | |
| crosswalk_review_required | D | bool | Any crosswalk row for this CDFI needs review | crosswalk | All | |
| related_certified_cdfi_ids | D | str | Other certified CDFIs that are this CDFI's subsidiary/successor bank | crosswalk | B,H | |
| fdic_specialization_group | R | str | FDIC asset-concentration group | FDIC `SPECGRPN` | B | Asset-based; not a lending-purpose code |
| mdi_status | R | str | FDIC minority depository institution status | FDIC `MDI_STATUS_DESC` | B | |
| ncua_low_income_designation, ncua_mdi | R | bool | NCUA low-income designation; MDI | NCUA FOICU `LIMITED_INC`, `IsMDI` | C | |

### Scale (latest regulatory period)

| Field | R/D | Type | Definition | Original field(s) | Types | Period | Limitations |
|---|---|---|---|---|---|---|---|
| financials_reporting_date | R | date | Call Report date | FDIC `REPDTE`; NCUA `CYCLE_DATE` | B,H,C | 2026-06-30 | |
| financial_scope | D | str | `institution` or `sum_of_fdic_insured_subsidiaries` | — | B,H,C | | BHC ≠ consolidated BHC balance sheet |
| n_entities | D | int | Number of regulatory entities summed | — | B,H,C | | |
| total_assets_usd | R | float | Total assets | FDIC `ASSET`×1000; NCUA `ACCT_010` | B,H,C | 2026-06-30 | |
| total_loans_usd | R | float | Total loans & leases | FDIC `LNLSGR`×1000 (net of unearned income); NCUA `ACCT_025B` | B,H,C | | |
| total_loan_count | R | float | Number of loans & leases | NCUA `ACCT_025A` | C | | Not reported by banks |
| total_deposits_usd | R | float | Deposits (banks) / shares & deposits (CUs) | FDIC `DEP`×1000; NCUA `ACCT_018` | B,H,C | | |
| total_equity_usd | R | float | Equity capital | FDIC `EQ`×1000 | B,H | | Not pulled for CUs |
| net_income_ytd_usd | R | float | Net income, year-to-date (6 months) | FDIC `NETINC`; NCUA `ACCT_661A` | B,H,C | Jan–Jun 2026 | Not annualized |
| members | R | float | Current members | NCUA `ACCT_083` | C | | |
| full_time_employees | R | float | Full-time employees | FDIC `NUMEMP` | B,H | | |
| financials_source | R | str | Source label | — | | | |
| asset_growth_1y_pct, loan_growth_1y_pct, membership_growth_1y_pct | D | float | % change vs 2025-06-30 | same fields, prior year | B,H,C | | Only when same entity set; includes merger effects |
| include_in_market_totals | D | bool | False for BHCs whose subsidiaries are all separately certified | crosswalk | All | | Use for market sums |
| market_totals_note | D | str | Reason for exclusion | | | | |
| irs_total_assets_usd, irs_total_revenue_usd | R | float | Total assets / revenue from latest return on IRS file | IRS EO BMF `ASSET_AMT`, `REVENUE_AMT` | L,V | `irs_tax_period` | Not comparable to Call Report; small filers may show 0 |
| irs_tax_period | R | str | Tax period (YYYYMM) of the IRS amounts | BMF `TAX_PERIOD` | L,V | | |
| irs_ntee_code, irs_subsection | R | str | NTEE code; 501(c) subsection | BMF | L,V | | NTEE too noisy for lending focus |
| irs_source | R | str | Provenance | | | | |
| borrower_reach_value / borrower_reach_proxy | D | float/str | Best available reach measure and what it is | NCUA members | C | | Missing for banks and loan funds |
| loan_count_value / loan_count_proxy | D | float/str | Loan count and definition | NCUA `ACCT_025A` | C | | |

### Lending mix and focus (derived from `cdfi_lending`, latest period)

| Field | Type | Definition | Types | Limitations |
|---|---|---|---|---|
| share_<group>_pct (consumer, mortgage_homeownership, commercial_business, commercial_real_estate, residential_housing_development, agriculture, other) | float | Group balance / total loans × 100 | B,H,C | CUs: housing development & agriculture not separable (missing); groups not equivalent across regulators (see methodology §6) |
| primary_lending_focus | str | Group with largest share (excl. other) | B,H,C | Missing for L,V |
| secondary_lending_focus | str | Second-largest group if ≥ 10% | B,H,C | |
| primary_focus_share_pct | float | Share of the primary group | B,H,C | |
| focus_confidence | str | high ≥ 50%, medium 30–50%, low < 30% | B,H,C | |
| focus_source / focus_method / focus_reporting_date | str | Provenance of the focus fields | All | |
| consumer_lending_flag, mortgage_lending_flag, commercial_business_flag, commercial_real_estate_flag, agriculture_flag | bool | Group share ≥ 10% | B,H,C | |
| housing_development_flag | bool | Multifamily + 1–4 family construction ≥ 10% | B,H | Missing for CUs |
| small_business_exposure_pct | float | (LNCI4 + LNRENR4) / gross loans × 100 | B,H | Bank proxy; business loans ≤ $1MM original amount |
| small_business_flag | bool | small_business_exposure_pct ≥ 10 | B,H | |
| small_business_loan_count_banks | float | LNCI4N + LNRENR4N | B,H | |
| consumer_exposure_pct | float | = share_consumer_pct | B,H,C | |
| auto_loan_share_pct, credit_card_share_pct | float | Subcategory share | B,H,C | |
| unsecured_consumer_share_pct | float | Other unsecured + PAL + private student | C | Not separable for banks |
| microenterprise_flag, community_facilities_flag, venture_flag | bool | Always missing in this version | — | Not reported by regulators |

### Geography (also in `cdfi_geography`)

| Field | R/D | Type | Definition | Source | Types |
|---|---|---|---|---|---|
| hq_county_fips, hq_county_name | R | str | HQ county | FDIC `STCNTY`/`COUNTY`; NCUA state+county codes | B,C |
| latitude, longitude | R | float | HQ coordinates | FDIC | B |
| branch_count | R/D | float | Number of offices/sites | FDIC locations; NCUA branch file (all site types) | B,H,C |
| branch_states | D | str | States with a branch | same | B,H,C |
| number_states_branches, number_counties_branches | D | float | Distinct states / counties with branches | same | B,H,C |
| branch_footprint_class | D | str | single county / multi-county single state / multistate | derived | B,H,C |
| service_area_* (geography table) | — | — | Missing by design | not public | All |

### Awards summary (from `cdfi_awards`, linked rows only)

| Field | Type | Definition | Limitations |
|---|---|---|---|
| award_count | int | Linked award rows (all programs) | 0 = none linked |
| grant_award_count | int | Rows excluding NMTC and BOND | |
| total_cdfi_fund_awards_usd | float | Sum of award amounts excluding NMTC allocations and BOND guarantees | Not a size measure |
| nmtc_allocation_total_usd | float | Sum of NMTC allocations | Tax-credit allocation, not cash |
| cdfi_fa_award_count | int | CDFI-FA + NACA-FA rows | |
| first_award_year, latest_award_year, years_with_awards | int | Award-year span | 2023/2025 export incomplete |
| award_programs | str | Distinct programs | |
| latest_award_program, latest_award_amount_usd | str/float | Most recent (largest within year) award | |
| award_link_min_confidence | str | Weakest name-match confidence among linked rows | |

### Coverage flags

`has_assets` (regulatory or IRS), `has_regulatory_assets`, `has_lending_mix`, `has_primary_focus` — bool, D.

## cdfi_crosswalk

| Field | Definition |
|---|---|
| cdfi_id, cdfi_name, institution_type, hq_state | From master |
| id_system | RSSD, FDIC_CERT, NCUA_CHARTER, LEI, EIN |
| id_value | External identifier (only accepted values appear in `data/processed/cdfi_crosswalk.csv`; rejected candidates are in `data/interim/crosswalks/crosswalk_long.csv`) |
| relationship | self, subsidiary_bank, probable_subsidiary_bank, former_subsidiary_bank, merger_successor |
| external_name / city / state | Name and location in the external source |
| match_method, match_confidence | See methodology §4 |
| name_similarity | RapidFuzz token-set/sort ratio on normalized names (0–100) |
| manual_review_required, review_reason | Review flag and reason |
| related_certified_cdfi_id | If the external entity is itself a certified CDFI |
| notes | Provenance notes (e.g., BMF subsection, NTEE) |

## cdfi_financials

One row per `cdfi_id` × `reporting_date` (2026-06-30 and 2025-06-30) with the scale fields above plus
`total_loans_gross_usd` (FDIC `LNLSGRS`), `domestic_offices_call_report` (FDIC `OFFDOM`), `entity_ids`
(certs/charters summed), `source`, `retrieval_date`.

## cdfi_lending

| Field | Definition |
|---|---|
| cdfi_id, reporting_date, source | |
| source_field / source_count_field | Original FDIC/NCUA field(s) for amount and count |
| source_category | Regulator's category label |
| standardized_category, standardized_subcategory | Mapping from `data/reference/lending_category_map.csv` |
| additive | True if the category is part of an exhaustive partition of total loans; False for memo items |
| loan_balance_usd | Outstanding balance (USD) |
| loan_count | Number of loans (NCUA all lines; FDIC small-business/farm memo only) |
| entity_ids | Regulatory entities summed (BHCs) |
| percent_of_total_loans | balance / (sum of additive categories) × 100 |
| notes | Memo/residual notes |

## cdfi_awards

| Field | Definition |
|---|---|
| award_row_id | Row number in the export |
| awardee_name / city / state | As published |
| award_year, award_program, award_amount_usd | Parsed from export |
| award_program_name, award_type | Program description; financial_assistance, technical_assistance, bank_enterprise_award, capital_magnet_fund, tax_credit_allocation, bond_guarantee, grant_other |
| counts_toward_grant_total | False for NMTC and BOND |
| cdfi_id | Linked certified CDFI (empty if not linked) |
| award_match_method / confidence / name_similarity / review_required | Linkage audit fields |
| source, source_file, source_url, retrieval_date | Provenance |

## state_summary

`state`, counts by type (`n_*`), `n_certified_cdfis`, `n_native_cdfis`, `population_<vintage>` (Census estimates),
`cdfis_per_million_residents` (D), `depository_cdfi_assets_usd` (D; deduplicated via `include_in_market_totals`),
`credit_union_cdfi_members` (D), `population_source`, `geography_basis` = headquarters state (not service area).

## Reference tables

* `data/reference/cdfi_id_registry.csv` — stable ID registry (append-only).
* `data/reference/lending_category_map.csv` — regulator field → standardized category, with rationale.
* `data/reference/employment_income_dependency_map_DRAFT.csv` — proposed dependency levels; **not applied**.

---

## Phase 2 additions — lending focus, size tiers, segments

### cdfi_master: lending focus (all types)

| Field | R/D | Type | Definition | Types | Notes |
|---|---|---|---|---|---|
| focus_basis | D | str | `portfolio` (regulatory balances), `evidence` (text/program evidence), `none` | All | |
| share_<category>_pct | D | float | Category share of total loans, for all 12 standardized categories (consumer, mortgage_homeownership, microenterprise, small_business, commercial_business, commercial_real_estate, residential_housing_development, community_facilities, intermediary_finance, venture_equity, agriculture, other) | B,H,C | Missing where the regulator cannot observe the category (see methodology §6); shares sum to 100% |
| consumer_share, mortgage_share, small_business_share, commercial_share, cre_share | D | float | Convenience aliases (small_business_share = microenterprise + small_business) | B,H,C | |
| share_individual_borrowers_pct / share_business_borrowers_pct / share_property_project_borrowers_pct / share_financial_other_borrowers_pct | D | float | Borrower-type rollups | B,H,C | |
| primary_borrower_type | D | str | Largest of individual / business / property_project | B,H,C | |
| primary_lending_focus | D | str | Portfolio: largest category share (excl. other). Evidence: `loan_fund_focus_1` | All | |
| secondary_lending_focus, tertiary_lending_focus | D | str | Next categories (portfolio: ≥10% share; evidence: focus 2/3 at any confidence) | All | |
| primary_focus_share_pct, primary_focus_margin_pp, primary_focus_near_tie | D | float/bool | Top share, lead over 2nd, lead < 5 pp | B,H,C | |
| portfolio_concentration | D | str | specialized ≥50% / focused 30–50% / diversified <30% | B,H,C | |
| primary_focus_confidence | D | str | HIGH / MEDIUM / LOW / UNKNOWN (rules in methodology §7, §13) | All | |
| primary_focus_source, primary_focus_method, primary_focus_basis_note, focus_reporting_date | D | str | Provenance of the focus fields | All | |
| meaningful_lending_activities, n_meaningful_activities | D | str/int | Categories ≥10% share (portfolio) or MEDIUM/HIGH evidence | All | Loan-fund counts are lower bounds |
| consumer_lending_flag, mortgage_lending_flag, microenterprise_flag, small_business_flag, commercial_business_flag, commercial_real_estate_flag, housing_development_flag, community_facilities_flag, intermediary_finance_flag, venture_flag, agriculture_flag | D | bool | Portfolio: share ≥ 10% (False if observed below; blank if unobservable). Evidence: True if MEDIUM/HIGH evidence, otherwise blank (unknown) | All | Depositories: SBA program-list membership also sets micro/small-business flags |
| small_business_exposure_pct | D | float | (LNCI4 + LNRENR4) / gross loans — regulatory small-business measure, overlaps CRE | B,H | Not additive |
| sba_microloan_intermediary, sba_community_advantage_lender | D | bool | Matched to SBA lists | All | |
| fhlb_member_cdfi_type | D | bool | Matched to FHFA FHLB members with CDFI membership type | L,V | Blank for depositories |
| loan_fund_focus_1..3, loan_fund_focus_n_confidence | D | str | Evidence-ranked categories and confidences | L,V | |
| classification_source, classification_evidence, classification_confidence | D | str | Evidence types; best evidence snippets for focus 1; confidence of focus 1 (UNKNOWN if none) | L,V | |
| meaningful_activities, all_evidenced_activities | D | str | MEDIUM/HIGH categories; all categories with any evidence | L,V | |
| notes_loans_receivable_eoy_usd | R | float | Form 990 Part X line 7, end of year | L,V | Tax period in `irs_990_tax_period_end` |
| irs_990_total_assets_eoy_usd, program_related_investments_eoy_usd | R | float | 990 Part X | L,V | |
| loans_receivable_share_of_assets_pct | D | float | Notes & loans receivable / total assets | L,V | Lending intensity |
| has_irs_990, irs_990_tax_period_end | R | bool/date | Whether an e-filed 990 was found; its period end | L,V | |
| has_evidence_classification | D | bool | focus_basis == evidence | All | |

### cdfi_master: size tiers and segments (added by `segment_market.py`)

| Field | Type | Definition |
|---|---|---|
| nondep_total_assets_usd, nondep_assets_source | float/str | Loan/VC fund assets: 990 Part X EOY, else IRS BMF |
| size_tier_group | str | bank / credit_union / loan_fund (threshold set used) |
| size_tier, size_tier_code, size_tier_basis | str | S/M/L/XL with type-specific thresholds (methodology §14) |
| size_metric_usd, size_percentile_within_type | float | Asset metric used; percentile rank within institution type |
| member_tier | str | Credit-union member tier |
| loan_portfolio_tier | str | Loan-fund notes & loans receivable tier |
| market_segment_code, market_segment, market_subsegment | str | A–F/U segment, label, sub-segment (D1–D3, E1–E3, F1–F2) |
| market_segment_rule | str | Rule that assigned the segment |
| segment_confidence | str | = primary_focus_confidence |
| segment_memberships, n_segment_memberships, multi_focus | str/int/bool | All segments with a meaningful activity; ≥ 2 meaningful activities |

### New tables

* `cdfi_segments.csv` — one row per CDFI: focus, segment, tiers (subset of master).
* `loan_fund_classification.csv` — one row per loan/VC fund: focus 1–3 with confidence, score, evidence; 990 context.
* `cdfi_focus_evidence.csv` — one row per piece of evidence: `cdfi_id`, `category`, `evidence_type`
  (irs_990_text / program_list / cdfi_fund_award / organization_name / treasury_institution_type), `evidence_source`
  (e.g. program_1, mission, SDL), `rule_id`, `matched_text`, `evidence` (sentence ≤ 400 chars), `program_expense_share`,
  `program_expense_usd`, `source_document`, `source_period`.
* `cdfi_focus_category_scores.csv` — CDFI × category features (`program_expense_share`, `program_text_mention`,
  `mission_text_mention`, `strong_program_list`, `sdl_award`, `n_indirect_indicators`), `score`, `confidence`.
* `data/interim/irs_990/filings.csv`, `program_texts.csv`; `data/interim/program_lists/*.csv`;
  `data/interim/crosswalks/program_list_matches.csv`.
* Reference: `data/reference/focus_text_rules.csv` (text rules with notes).
* In `cdfi_lending.csv`: new `standardized_category` values `microenterprise`, `small_business`, `intermediary_finance`
  for FDIC rows; `avg_balance_per_loan_usd` for NCUA rows.

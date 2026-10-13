# Jobago and the U.S. CDFI Market
## Research Report: Market Structure, Lending Focus and Next-Stage Priorities

*Data as of: CDFI Fund certified list 17 Sep 2026 · FDIC and NCUA Call Reports 30 Jun 2026 · IRS Form 990 filings for tax years ending 2023–2026*

---

## Executive Summary

**Objective.** Jobago is exploring whether Community Development Financial Institutions (CDFIs) could offer its career-transition services to borrowers whose ability to repay depends on their jobs. This research asked a structural question that comes before choosing partners: *what kinds of CDFIs exist, what do they lend for, how large are they, and which groups of them have borrowers whose repayment is plausibly tied to employment income?*

**What we did:**
- Built a reproducible dataset of all **1,281 CDFIs certified by the U.S. Treasury CDFI Fund** as of 17 September 2026.
- Linked each CDFI to public regulatory and tax records:
  - FDIC bank Call Reports
  - NCUA credit-union Call Reports
  - IRS Form 990 filings and the IRS nonprofit master file
  - SBA lender lists
  - FHFA Federal Home Loan Bank membership
  - CDFI Fund award records
- Assigned each CDFI a **primary lending focus** using two methods:
  - **Measured loan balances** for banks and credit unions.
  - **Documented evidence** (mainly IRS Form 990 program descriptions) for loan funds and venture funds, which publish no standardized loan data.
- Grouped CDFIs into **six descriptive market segments** plus an "unclassified" group.

**Key findings (all verified against the current dataset).**
1. **A primary lending focus could be assigned to 1,106 of 1,281 CDFIs (86%).** The 175 unclassified are mostly:
   - Puerto Rico credit cooperatives outside federal credit-union reporting (77)
   - loan funds with no public filing or no descriptive lending language (78)
   - banks and holding companies that have merged or could not be matched (16)
   - a handful of other credit unions (4)
2. **Credit unions are the consumer-lending core of the CDFI market.**
   - **184 of the 286 classifiable CDFI credit unions (64%) are primarily consumer lenders.**
   - Together they report **7.46 million members** and **$43.3 billion in consumer loans** (30 Jun 2026).
   - Auto loans are the largest consumer product: a median 44% of these credit unions' loans.
3. **CDFI banks are mostly real-estate lenders.** Of 328 classifiable banks and holding companies:
   - 175 lend primarily on commercial real estate and 109 on residential mortgages.
   - Consumer lending is a median of about 3% of bank loan portfolios.
4. **Loan funds are the business- and housing-lending part of the market.** Of 483 classifiable loan funds:
   - **246 fall in the microenterprise (115) or small-business/commercial (131) segments.**
   - 74 are homeownership lenders and 108 finance housing development, real estate or community facilities.
   - They are small: median total assets are about $19 million.
5. **277 CDFIs are primarily mortgage/homeownership lenders.** This count includes 49 bank holding companies that duplicate separately listed subsidiary banks; there are 228 distinct lenders after removing that overlap.

**Implications for Jobago:** Three groups warrant deeper investigation because their borrowers are individuals or owner-operators whose repayment is plausibly tied to personal earnings:
- **consumer-focused credit unions**: the strongest fit on available evidence
- **microenterprise and small-business loan funds**: a plausible but more complex fit
- **mortgage and homeownership lenders**: plausible, but repayment risk is long-dated and often managed through servicing

Commercial real estate, development finance, intermediary and venture CDFIs have weaker direct links to an individual's job.

**What remains unvalidated:** The segments describe *what CDFIs lend for*; they are **not a ranking of Jobago customers**. We have not yet measured:
- digital capability or existing borrower-support programs
- partnership activity or budget
- willingness to buy

There is no evidence yet that job-loss support improves CDFI repayment outcomes. The next phase should shortlist institutions within the priority segments, research them qualitatively, and test demand through interviews.

---

## 1. Research Scope and Objectives

**Market-entry hypothesis.** Many CDFI borrowers have thin financial cushions. When a borrower loses a job, missed payments and defaults become more likely. A CDFI might therefore value a service that helps borrowers regain employment, as a borrower benefit, a hardship tool or a loss-mitigation measure.

**Research questions for this phase.**
1. How many certified CDFIs are there, and of what institutional types?
2. What does each CDFI primarily lend for, and what else does it lend for?
3. How large is each institution relative to others of its type?
4. How should the market be segmented so that Jobago-relevant groups can be studied further?

**Out of scope for this phase:**
- choosing specific partners
- scoring institutions for Jobago attractiveness
- researching technology, coaching or hardship programs
- interviewing CDFIs

---

## 2. Data Sources and Collection

All sources are public. Collection is scripted and repeatable. Every downloaded file is kept unmodified with a provenance record: source URL, retrieval time, file checksum and the server's last-modified date. Full URLs, dates and scripts are in **Appendix A**.

### 2.1 Sources used in the analysis

| Source | What it covers | What we took from it | How it was used |
|---|---|---|---|
| **U.S. Treasury CDFI Fund — List of Certified CDFIs** (Excel; as of 17 Sep 2026) | All 1,281 certified CDFIs | Name, institution type, Federal Reserve **RSSD ID** (banks and credit unions), Native CDFI flag, address, website | Defines the universe; RSSD is the main key for matching to regulators |
| **FDIC BankFind Suite API** (Call Reports; quarters ending 30 Jun 2026 and 30 Jun 2025) | All FDIC-insured banks | Assets, loans, deposits, net income; loan balances by Call Report category (Schedule RC-C) incl. business-loan **size bands**; holding-company RSSD; branch locations | Bank and holding-company size, lending mix, primary focus, branch footprint |
| **NCUA 5300 Call Report** (quarterly bulk files; 30 Jun 2026 and 30 Jun 2025) | Federally insured credit unions | Assets, loans, shares, **members**, balances and counts for 13 loan lines | Credit-union size, membership, lending mix, primary focus |
| **IRS Exempt Organizations Business Master File** (state files; Sep 2026) | Tax-exempt organizations | EIN, name, address, latest-return assets and revenue | Finding EINs (tax IDs) for loan funds; fallback asset figure |
| **IRS Form 990 e-file XML** (latest return per EIN, from IRS index years 2024–2026) | Nonprofits that file electronically | Mission statement; Part III program descriptions **with program expenses**; Schedule O narratives; Part X total assets and **notes & loans receivable** | Evidence-based lending focus and size for loan funds |
| **SBA list of Microloan Program intermediaries** (web pages; retrieved 11 Oct 2026) | 153 SBA microlenders | Name, website, address | Evidence of microenterprise lending |
| **SBA Community Advantage Small Business Lending Companies list** (Excel; file dated Dec 2025) | 141 lenders | Name, website, address | Evidence of small-business lending |
| **FHFA Federal Home Loan Bank membership** (Excel; Q2 2026) | All FHLB members; 83 with "CDFI" membership type | Name, address, member type | Supporting evidence of housing finance (never used alone) |
| **CDFI Fund Searchable Awards Database** (CSV export, 29 Sep 2026) | 12,633 awards, 1996–2025 | Awardee, year, program, amount | Award history; four programs used as lending-purpose evidence |
| **U.S. Census Bureau population estimates** (Vintage 2025) | States | Population | State-level CDFIs per capita (descriptive only) |

### 2.2 Sources investigated but not used for findings

| Source | Status / reason |
|---|---|
| CDFI Fund transaction-level and consumer-loan data releases (FY2003–FY2022) | Organization identities are anonymized, so the data cannot be linked to named CDFIs |
| CDFI Fund Annual Certification Reports, target markets, certification dates | Collected by Treasury but **not publicly released** |
| Opportunity Finance Network (OFN), Aeris | Website blocks automated access / paid subscription |
| Census American Community Survey | Now requires an API key; not yet configured |
| FDIC household survey (unbanked/underbanked), BLS county unemployment | Verified for later geographic context; not ingested |
| FFIEC National Information Center (bank ownership links) | Blocks automated download |

---

## 3. Building the Certified CDFI Dataset

**Why Treasury's list.** CDFI status is a Treasury certification, so the CDFI Fund's list is the authoritative definition of the universe. The list used is dated **17 September 2026**. It contains **1,281 organizations**, exactly matching the total Treasury prints in the file, including 65 Native CDFIs.

| Institution type | Count |
|---|---|
| Loan fund | 561 |
| Credit union | 367 |
| Bank or thrift | 184 |
| Bank holding company | 160 |
| Venture capital fund | 9 (7 labelled "Venture Capital", merged with 2 "Venture Capital Fund") |
| **Total** | **1,281** |

**Cleaning and identifiers.**
- Names, ZIP codes, addresses and websites were standardized.
- Original values were kept alongside the cleaned values.
- Treasury publishes no organization ID, so each CDFI received a permanent internal ID (e.g. `CDFI00042`). IDs are held in a registry that re-matches organizations on later runs by RSSD, then name and state, then website. They never depend on name alone.

**Matching to other datasets.** Matches were made in order of reliability, and weak matches were never silently accepted:
- **Banks:** Treasury's RSSD matched to the FDIC record. 177 of 184 matched exactly; 2 more matched on exact name and state.
- **Credit unions:** RSSD matched to NCUA. 278 of 367 matched exactly; 9 more matched on name and state.
- **Loan and venture funds:** matched to the IRS master file on name, state and ZIP to obtain an EIN.
  - 393 matched with high confidence (exact name and ZIP).
  - 54 accepted matches were flagged for review.
  - 123 have no accepted EIN.
- **Review queue:** every uncertain match is recorded with its method, confidence and reason in `research/unresolved_matches.csv`. 287 CDFIs have at least one review flag.

**Bank holding companies and double counting.** This is the most important structural caveat:
- Holding-company financials are the **sum of their FDIC-insured subsidiary banks**, found through the FDIC's holding-company identifier. This is not a consolidated holding-company balance sheet.
- **146 of the 160 certified holding companies own only banks that are themselves separately certified.** For example, Southern Bancorp Inc. and Southern Bancorp Bank are both on the list.
- Counting both would double-count assets, loans and lenders. These 146 holding companies are therefore flagged `include_in_market_totals = False`, and **every dollar total in this report excludes them.**
- *Institution counts* in this report follow Treasury's list and therefore **do include** both entities. Removing the 146 overlapping holding companies leaves about 1,135 distinct lending organizations.

**Stale entries.** Some listed institutions no longer exist as separate charters:
- 5 banks and the subsidiaries of 4 holding companies merged during 2025–2026.
- 2 credit unions disappeared from NCUA data between 2025 and 2026.

These records are kept and flagged. The successor bank's financials are *not* attributed to them.

**Reporting periods.**
- Bank and credit-union figures are aligned at **30 June 2026**; one-year growth compares against 30 June 2025.
- IRS figures come from each organization's latest return (tax years ending 2023–2026). They are always reported separately from Call Report figures and never added to them.

*Sources: `data/processed/cdfi_master.csv`, `data/processed/cdfi_crosswalk.csv`, `research/data_quality_report.md`; code `scripts/clean/normalize_treasury.py`, `scripts/match/build_crosswalk.py`.*

---

## 4. Lending-Focus Classification Methodology

CDFIs rarely do only one thing, so we record a **primary focus**, **secondary activities** and **activity flags** for each. Two methods were needed because the data differ fundamentally by institution type.

### 4.1 Banks, holding companies and credit unions: portfolio-based

**What is measured.**
- Each loan category's share of outstanding loan balances on 30 June 2026, from the regulator's own categories.
- Balances were used because they are the only standardized, complete measure available. Regulators do not report borrower counts for banks, and credit unions report loan counts but not unique borrowers.
- A balance share shows *where the money is*, not *how many people* are served. A $500,000 commercial mortgage outweighs a hundred $5,000 auto loans.

**Standardized categories.** Regulator line items were mapped to a common taxonomy; the full mapping with reasoning is in `data/reference/lending_category_map.csv`.

| Category | Banks (FDIC Call Report) | Credit unions (NCUA 5300) |
|---|---|---|
| Consumer | Credit cards, other revolving credit, auto loans, other consumer loans | Credit cards, payday-alternative loans, private student loans, other unsecured, new and used vehicle loans, leases, other secured |
| Mortgage / homeownership | 1–4 family first and junior liens, home-equity lines | 1st- and junior-lien 1–4 family loans, other non-commercial real estate |
| Microenterprise *(proxy)* | Business (C&I) loans with original amount **≤ $100,000** | Not observable |
| Small business | Business (C&I) loans with original amount **$100,000–$1 million** | Member business loans not secured by real estate |
| Larger commercial | Business (C&I) loans **> $1 million** | Member business loans where the average loan exceeds $1 million (17 credit unions) |
| Commercial real estate | Owner-occupied and investor nonresidential property, construction and land | Commercial real-estate-secured loans (includes multifamily and farmland) |
| Housing development | Multifamily, 1–4 family construction | Not separable |
| Agriculture | Farmland, farm production loans | Not separable |
| Other | Municipal, loans to other institutions, leases, unreconciled residual | — |

**Handling overlaps and accounting issues.**
- **The categories add up exactly.** For banks they sum to gross loans for all but 28 (mostly very large) banks; the small gap is kept as an explicit "residual" line. For credit unions they sum to total loans (within $11) for every institution.
- **Business-loan size bands.** The FDIC reports business loans by *original* amount in three bands. Their sum always equals the small-business subtotal and never exceeds total business loans (verified for every bank).
  - We use these bands to separate micro-sized, small and larger business lending.
  - The ≤ $100,000 band is a **proxy** for microenterprise lending, not a measure of business size. It is simply the smallest band the Call Report provides.
- **The regulators' own "small business loan" measure** also includes small commercial-property loans, so it overlaps commercial real estate. It is kept as a separate, non-additive indicator rather than mixed into the shares.
- **Categories a regulator cannot observe are left blank, never zero.** For example, credit-union microenterprise lending is not reported.

**Selecting the primary focus.**
- The category with the **largest share of loans** (excluding "other") is the primary focus.
- Categories holding **≥ 10%** of loans are listed as *secondary / meaningful activities* and switch on the corresponding activity flags.

**Confidence.**

| Level | Rule |
|---|---|
| HIGH | Primary category is ≥ 50% of loans |
| MEDIUM | Primary is 30–50% **and** leads the next category by ≥ 5 percentage points |
| LOW | Everything else, including near-ties (lead < 5 points) |

**Checking the rule.**
- Near-ties occur at 21–23% of banks and holding companies and 9% of credit unions. Of the 98 near-ties, 91 are LOW confidence; 7 are HIGH because their top category still exceeds 50%.
- Splitting business loans into size bands changed the primary focus of only 4 banks compared with treating business lending as one category. The results are not an artifact of how finely categories are cut.

**Holding companies** are classified on the combined loan book of their matched subsidiary banks.

**Worked example (portfolio).** *Suncoast Credit Union (FL)*:
- 57.8% consumer loans, of which auto loans are 43.3% of total loans
- 37.6% mortgages; 4.2% commercial real estate
- Primary: **consumer**, HIGH confidence (lead of 20 points); secondary: mortgage
- 1.41 million members; $20.8 billion assets

*Southern Bancorp Bank (AR)*:
- 35.3% commercial real estate, 25.3% mortgage, 15.5% agriculture
- Primary: **commercial real estate**, MEDIUM confidence (lead of 10 points)
- Secondary activities: mortgage and agriculture

### 4.2 Loan funds and venture funds: evidence-based

**Why a different method.** Nonprofit loan funds file no standardized loan-category reports. The CDFI Fund collects such data but releases it only in anonymized form. We therefore classified them from **what they document about their own lending**.

**Evidence used, strongest first.**
1. **IRS Form 990 program descriptions (Part III)**, each carrying the program's share of the organization's program expenses. The latest return was retrieved for 441 of 447 loan and venture funds with an EIN.
2. **Mission and activity statements** and **Schedule O** explanations in the same 990.
3. **SBA program participation:** being an SBA Microloan intermediary (microenterprise) or a Community Advantage lender (small business). 92 certified CDFIs matched each list.
4. **CDFI Fund award programs with a defined purpose:**
   - Small Dollar Loan Program → consumer
   - Capital Magnet Fund → affordable housing
   - New Markets Tax Credits → real-estate/business projects
   - Healthy Food Financing → community facilities
5. **Weak indirect signals:**
   - organization-name keywords (e.g. "Habitat", "Micro", "Housing")
   - FHLB membership (only to support an existing housing finding)
   - descriptions of program-related investments
   - Treasury's "venture capital fund" type

**How text becomes evidence.**
- 990 text is split into sentences and tested against 45 published detection rules (`data/reference/focus_text_rules.csv`). For example, "micro-loan", "loans to small businesses", "down payment assistance" in a housing sentence, or "vehicle loans".
- Most rules fire only if the same sentence also contains a lending word (loan, lend, finance, credit, capital, invest, mortgage, borrow, debt, funding, revolving).
- One exclusion rule stops "commercial mortgage" or "multifamily mortgage" from counting as homeownership.
- Every match is stored with the exact sentence, the 990 section and the program-expense share (`data/processed/cdfi_focus_evidence.csv`, 3,359 evidence records).
- We tested NAICS industry codes in the 990 and **rejected** them: most business lenders label their loan income "consumer lending" (code 522291).

**Scoring.** For each organization and category, the code (`scripts/enrich/classify_lending_focus.py`) computes:

> **Score = 4 × (share of program expenses in programs whose description cites the category)**
> **+ 1.5 × (cited in any Part III program description)**
> **+ 1.0 × (cited in the mission/activity statement)**
> **+ 2.0 × (on the SBA Microloan or Community Advantage list)**
> **+ 0.75 × (received a Small Dollar Loan Program award)**
> **+ 0.5 × (each weak indirect signal)**

*These weights are project-defined heuristics.* They encode a judgement that spending-weighted program descriptions are the strongest evidence, followed by official program participation, explicit mention, and weak signals. They were not statistically calibrated, and no external standard prescribes them.

The highest-scoring category becomes the **primary focus**; the next two are recorded as focus 2 and 3. Ties are broken by confidence, then by a fixed category order.

**Confidence (per category).**

| Level | Rule |
|---|---|
| HIGH | Program descriptions citing the category account for ≥ 25% of program expenses; **or** program text is present without expense data and the mission also cites it; **or** SBA-list membership is corroborated by 990 text |
| MEDIUM | Any explicit 990 mention; **or** SBA-list membership alone; **or** a Small Dollar Loan award; **or** two or more weak signals |
| LOW | Exactly one weak signal |

The 25% threshold is a project-defined cut-off. The overall classification confidence is the confidence of the primary category.

**Multiple activities and conflicting evidence.**
- Every category with evidence is retained. Categories at MEDIUM or HIGH are listed as "meaningful activities".
- Conflicts are not resolved by discarding evidence; the score ranks the categories.
- A blank flag means "no evidence found", **not** "does not do this".

**Errors found and corrected.** A manual review of a random sample (22 institutions) plus targeted checks found and fixed:
- A business lender classified as mortgage because its 990 said "no down payment required". "Down payment" now counts only in a housing sentence.
- An intermediary (Inclusiv) classified as small business because of the phrase "financial cooperatives". This now counts as intermediary finance.
- Missing rules, e.g. loans "to businesses", assistive-technology loans, vehicle-purchase programs, and home-repair wording.

No formal accuracy rate has been measured.

**Worked examples:**
- **Community Capital of Vermont → Microenterprise (HIGH), segment B.**
  - Its only Part III program (100% of program expenses) states: *"Community Capital of Vermont is a statewide small business and microenterprise lender serving low and moderate income entrepreneurs."*
  - It is also an SBA Microloan intermediary.
  - Microenterprise scores 7.5 and small business 6.5 (both HIGH). Focus 2 = small business.
- **The Cares Project (NC) → Consumer (HIGH), segment A.**
  - Its program (100% of expenses): *"made community-funded vehicle loans to 14 low income, credit-challenged working adults…"*
  - The mission repeats the vehicle-loan purpose. Score 6.5.
- **Enterprise Community Loan Fund (MD) → Housing development (HIGH), segment E.**
  - Program text: *"…cumulative loan volume … of $3.1 billion, supporting the development or preservation of affordable housing…"*
  - Supported by Capital Magnet Fund awards and FHLB membership. Score 7.5.
  - A Healthy Food Financing award adds community facilities as a LOW-confidence secondary activity.
- **Justine Petersen (MO): an illustration of method limits.**
  - Correctly classified as microenterprise (HIGH; SBA Microloan intermediary).
  - However, because a single program description mentions both its 857 business loans and its 465 consumer loans, the *full* program-expense share is credited to both categories. Consumer therefore also scores HIGH.
  - Program-expense weighting can overstate secondary activities when one program describes several products.

### 4.3 Portfolio-based and evidence-based results are not equivalent

| | Portfolio-based (614 banks, holding cos., credit unions) | Evidence-based (492 loan and venture funds) |
|---|---|---|
| Measures | Dollars actually outstanding, by regulator category | What the organization says it does, weighted by program spending |
| Shares | Sum to 100% of loans | No dollar shares; categories are ranked by score |
| A "secondary activity" means | ≥ 10% of loans | MEDIUM/HIGH evidence |
| Absence means | Observed to be below threshold (or not observable) | Unknown |
| Main risk | Dollar weighting understates small, numerous loans | Text emphasis may not match the dollar mix |

Both methods answer "what does this lender mainly do?", but with different measuring sticks. Comparisons *within* a method are stronger than comparisons *across* them.

---

## 5. Data Coverage and Classification Limitations

**The exact rule for "unclassified."**
- **Banks, holding companies and credit unions:** unclassified when no current (30 Jun 2026) Call Report loan data could be attached through a high- or medium-confidence match.
- **Loan and venture funds:** unclassified only when **no evidence of any kind** exists. That means no 990 rule match, no SBA list, no relevant award and no name keyword.
  - Any single piece of evidence produces at least a LOW-confidence classification. So *low confidence* and *unclassified* are different states.
  - FHLB membership alone never classifies (it is supporting-only); no unclassified fund was affected.

**Why 175 CDFIs are unclassified.**

| Institution type | Unclassified | Cause | Count | Kind of gap |
|---|---|---|---|---|
| Credit union | 81 | Puerto Rico *cooperativas* supervised by COSSEC, not NCUA; no 5300 report exists | 77 | No source data |
| | | Present in NCUA's June 2025 file, absent in June 2026 (likely merged) | 2 | Stale list entry |
| | | Name match found but city differs, so not accepted | 1 | Uncertain match |
| | | No RSSD on list and no candidate found | 1 | Failed match |
| Bank or thrift | 5 | Bank merged into another bank in 2025–2026 | 5 | Stale list entry |
| Bank holding company | 11 | Only subsidiary bank merged | 4 | Stale list entry |
| | | Holding company not a top-tier owner in FDIC data; a likely subsidiary was proposed but not accepted | 4 | Uncertain match |
| | | No match found | 2 | Failed match |
| | | Several equally good candidates; none accepted | 1 | Ambiguous |
| Loan fund | 78 | No accepted EIN (51 no candidate; 4 weak candidates rejected) and no other evidence | 55 | Failed match / no source |
| | | EIN found but no electronically filed 990 | 3 | No source data |
| | | 990 found, but its text does not describe what it lends for (e.g. "promote economic and community development"), or the program section is blank | 20 | Data present but non-descriptive |
| Venture fund | 0 | — | — | — |
| **Total** | **175** | | | |

**Low confidence is not unclassified.** 136 classified CDFIs carry LOW confidence:
- 93 near-tie or diversified banks and credit unions
- 43 loan and venture funds resting on a single weak signal, including 23 classified on their **name alone**

**Can more research resolve these?** Mostly yes:
- **Puerto Rico cooperatives:** COSSEC publishes statistics; institution-level availability is not yet checked.
- **Bank ownership links** (FFIEC National Information Center): would resolve the holding companies.
- **Organization websites or annual reports:** could resolve most of the 78 loan funds and strengthen the 23 name-only classifications.

**Why leave them unclassified?** A wrong label is worse than a blank. An unsupported "consumer lender" tag could send outreach to the wrong institutions, and would inflate segment counts that leadership may use to size the opportunity.

---

## 6. Market Segmentation

Segments group CDFIs by **primary** lending focus. They are **descriptive market categories, not a measure of Jobago attractiveness.** Each institution belongs to one segment. A separate field (`segment_memberships`) lists every segment in which it has a meaningful activity.

| Segment | Primary focus mapped in | CDFIs | Bank | Holding co. | Credit union | Loan fund | Venture |
|---|---|---|---|---|---|---|---|
| **A. Consumer-focused** | consumer | **232** | 1 | 1 | 184 | 46 | 0 |
| **B. Microenterprise / very small business** | microenterprise; *or* small business at a loan fund that is an SBA Microloan intermediary or has HIGH microenterprise evidence | **115** | 0 | 0 | 0 | 115 | 0 |
| **C. Mortgage / homeownership** | mortgage / homeownership | **277** | 59 | 50 | 94 | 74 | 0 |
| **D. Small business / commercial / agricultural** | small business, larger commercial, agriculture | **171** | 21 | 15 | 0 | 131 | 4 |
| **E. Real estate, housing development & community facilities** | commercial real estate, housing development, community facilities | **298** | 98 | 83 | 8 | 108 | 1 |
| **F. Intermediary / venture** | intermediary finance, venture/equity | **13** | 0 | 0 | 0 | 9 | 4 |
| **U. Unclassified** | none | **175** | 5 | 11 | 81 | 78 | 0 |
| **Total** | | **1,281** | 184 | 160 | 367 | 561 | 9 |

*Counts reconcile to the full universe and to each institution type. Source: `data/processed/cdfi_master.csv` (`market_segment_code`), rule in `scripts/analyze/segment_market.py`.*

**Special rule (segment B).** 66 loan funds whose highest score was "small business" were placed in B rather than D:
- 51 because they are SBA Microloan intermediaries
- 15 because they have HIGH-confidence microenterprise evidence

B therefore contains 49 loan funds whose primary focus is microenterprise plus these 66. This is an analytical choice: SBA Microloan participation is an authoritative signal of very-small-business lending, and microlenders' 990s often describe themselves as "small business" lenders.

**Why segments are separated as they are.** These are analytical choices for Jobago's purposes, built on data definitions:
- **Consumer vs. mortgage.** Both depend on household income, but consumer loans are short, unsecured or auto-secured, and fail quickly when income stops. Mortgages are long-dated and secured by the home.
- **Microenterprise vs. broader business.** A microloan's repayment is closely tied to the *owner's* personal earnings; larger business loans depend on the firm's cash flow.
- **Small business vs. project finance.** Real-estate, housing-development and facility loans are repaid from rents, sales or institutional budgets, not a person's wages.
- **Intermediary and venture.** These lend to other lenders or take equity stakes; the end borrower is at least one step removed.
- **Agriculture is grouped with business lending (D3).** It mostly appears at rural banks (32 of 35 agricultural-primary CDFIs). The slide label "Business / commercial" omits this.

**Size tiers (within type).** Sizes are compared only within an institution type, using thresholds that differ by type.

| Group | Metric | S | M | L | XL |
|---|---|---|---|---|---|
| Banks and holding companies | Assets | < $250M | $250M–$1B | $1B–$10B | ≥ $10B |
| Credit unions | Assets | < $100M | $100M–$500M | $500M–$2B | ≥ $2B |
| Credit unions (reach) | Members | < 10K | 10K–50K | 50K–200K | ≥ 200K |
| Loan / venture funds | 990 total assets | < $10M | $10M–$50M | $50M–$250M | ≥ $250M |

The cut points are **project-defined**. Some align loosely with familiar regulatory lines ($1 billion and $10 billion for banks; $500 million for NCUA's "complex" credit unions), but none is an official CDFI tiering. A percentile within type is also provided as a threshold-free alternative.

---

## 7. Key Market Findings

Each finding is traceable in Appendix C. Unless stated otherwise, counts are **institutions**, not borrowers, members or loans.

1. **Universe.** 1,281 certified CDFIs (Treasury, 17 Sep 2026): 44% loan funds, 29% credit unions, 14% banks, 12% holding companies, 1% venture funds.

2. **Classification coverage.**
   - 1,106 (86%) have a primary focus.
   - 614 are portfolio-based (from regulator data); 492 are evidence-based.
   - 175 are unclassified.
   - Confidence across the 1,106: 653 HIGH, 317 MEDIUM, 136 LOW.

3. **Consumer-focused credit unions are the largest, best-measured consumer channel.**

   | Measure | Value |
   |---|---|
   | Consumer-focused credit unions (segment A) | 184 |
   | Members | 7.46M (median 12,700 per credit union) |
   | Loans outstanding | 4.57M, of which 4.32M are consumer loans |
   | Consumer loan balances | $43.3B |
   | Total assets | $104.8B |
   | Median auto-loan share of total loans | 44% |
   | With NCUA's low-income designation | 180 |
   | With ≥ 50,000 members | 36 |

   **Members and loans are not unique borrowers**, and none of these figures measures job dependence directly.

4. **Banks lend mainly to property, not people.**
   - Median bank portfolio: 3.2% consumer, 26.5% mortgage, 33.8% commercial real estate.
   - Business loans: 1.7% are ≤ $100K and 3.9% are $100K–$1M.
   - The regulators' small-business measure (median 16.7%) is mostly small commercial-property lending.

5. **Loan funds dominate business and microenterprise lending.**
   - 246 loan funds are in segments B (115) or D (131).
   - Strictly, 242 have a micro or small-business primary focus; the other 4 in D are agricultural (3) or larger commercial (1).
   - Of the 246: 88 are SBA Microloan intermediaries and 90 are Community Advantage lenders (overlapping).
   - Their median total assets are $15M. The 187 that report loans receivable hold a combined $3.6B (median $6.5M).

6. **Mortgage lending spans all types.**
   - 277 CDFIs are primarily mortgage/homeownership lenders: 94 credit unions, 74 loan funds, 59 banks and 50 holding companies.
   - 49 of those holding companies duplicate their certified subsidiary banks, leaving **228 distinct lenders**.
   - Deduplicated mortgage balances at the depository institutions total $37.1B.
   - Classification bases differ: depositories by balance share, loan funds by evidence.

7. **Project finance is the largest segment by count.** Segment E (298) is mostly commercial-real-estate banks (203 CDFIs have CRE as primary focus) plus 108 housing-development, real-estate and facility loan funds.

---

## 8. Implications for Jobago

For each priority group, we separate what the data **show**, what we **hypothesize**, and what must still be **answered**. None of this establishes that Jobago reduces defaults or improves repayment; no such evidence exists yet.

### 8.1 Consumer-focused credit unions (segment A, 184)

- **Observed:**
  - Direct membership relationships with individuals.
  - Most lending is consumer credit (median 66% of loans), led by auto loans.
  - 7.46M members and 4.3M consumer loans.
  - Nearly all hold NCUA's low-income designation, meaning a majority of members are low-income by NCUA's definition.
  - Sizes range from small (77 under $100M) to very large (12 over $2B).
- **Hypothesis:**
  - Consumer and auto loans are repaid from wages and become delinquent quickly after job loss. A career-transition benefit could fit into existing financial-wellness, hardship or collections workflows.
  - Credit unions also have a member-service mission and established channels (online banking, branches) to distribute it.
- **Unanswered:**
  - How many members are borrowers, and how many borrowers lose jobs each year?
  - Do these credit unions already offer hardship or workforce programs?
  - Who would buy (lending, member services, collections) and with what budget?
  - Would a referral to Jobago measurably affect repayment?

### 8.2 Microenterprise and small-business loan funds (segments B and D, 246 loan funds)

- **Observed:**
  - Borrowers are entrepreneurs and small firms. Many funds are SBA microlenders.
  - Microloans are typically made to owner-operators.
  - Most funds are small (median assets $15M) and have no member base. Reach is in the hundreds or low thousands of loans per fund, not millions.
- **Hypothesis:**
  - For sole proprietors, household and business income are intertwined. An owner whose business struggles may need wage income to keep paying.
  - Many of these funds also run technical assistance programs, which could be a natural home for career services.
- **Unanswered:**
  - Does a *career-transition* product address an entrepreneur's need? It may matter more for borrowers whose businesses fail, or who rely on side income, than for growing businesses.
  - The fit is likely weaker for larger small-business lending (segment D) than for microlending (segment B).
  - Funding capacity is limited and often grant-dependent.

### 8.3 Mortgage and homeownership lenders (segment C, 228 distinct lenders)

- **Observed:**
  - Credit unions and banks hold mortgages on their books (balance data).
  - Loan funds in this segment describe homebuyer, down-payment, second-mortgage and home-repair programs.
  - Many pair lending with homebuyer counseling.
- **Hypothesis:**
  - Mortgage payments depend on household income. Employment support could complement foreclosure-prevention and loss-mitigation work.
- **Unanswered:**
  - Our data show loans *held*, not who *services* them. Lenders that sell mortgages may have no ongoing borrower relationship.
  - Mortgage delinquency arises over longer horizons, and existing hardship tools (forbearance, modification) may already dominate.

### 8.4 Groups with weaker direct links

These groups have weaker links to an individual borrower's job:
- **Commercial real estate, housing development and community facilities (E):** repaid from rents, property sales or institutional budgets.
- **Intermediary finance (F1):** lends to other lenders.
- **Venture and equity (F2):** investors, not creditors of individuals.

They are not excluded from future consideration, for example as funders or conveners. But they are not natural first buyers of a borrower-facing career-transition product.

**No ranking is implied.** The research supports *where to look first* (A, then B/D and C), not *which institutions to approach*.

---

## 9. Limitations and Interpretation

| Limitation | Why it matters | Affects |
|---|---|---|
| **Data depth differs by type.** Banks and credit unions have audited, standardized balances; loan funds have narrative evidence only | Segment counts mix measured and inferred classifications; comparisons across types are weaker | Comparability, confidence |
| **Evidence-based classifications are not loan shares.** Program text shows activities described, weighted by spending; 100 of 492 rest on no 990 text (lists, awards or name only) | A loan fund labelled "consumer" may still lend mostly elsewhere | Confidence, partner selection |
| **Scoring weights and thresholds are heuristics** (10%, 25%, 30/50%, 5-point, score weights) | Different reasonable choices would move some institutions between segments, mainly LOW/near-tie cases (136) | Confidence |
| **Balances, not borrowers.** Dollar shares understate many small consumer loans relative to a few large loans | A bank with a small consumer share may still serve many consumers | Strategic interpretation |
| **Members ≠ borrowers ≠ job-dependent borrowers.** Only credit unions report members; nobody reports employment status | "Reach" figures are upper-bound proxies | Market sizing, partner selection |
| **Holding company / bank overlap.** 146 holding companies duplicate certified banks | Institution counts overstate distinct lenders (≈1,135 distinct); dollar totals are deduplicated | Market coverage |
| **Reporting periods differ.** Call Reports are June 2026; IRS returns are 2023–2026; the Treasury list is Sep 2026 and includes some merged institutions | Loan-fund figures may be one to two years old | Comparability |
| **Coverage gaps.** 77 Puerto Rico cooperatives, 78 loan funds, 16 banks and holding companies unclassified | Segment counts are lower bounds, especially for consumer-oriented cooperatives | Coverage |
| **Service areas unknown.** Treasury does not publish target markets; branch locations are known only for depositories | Cannot yet target geographies with high job-loss risk | Partner selection |
| **No capability or demand data.** Digital channels, hardship/coaching programs, partnerships and willingness to pay were not studied | Segments say who *might* benefit, not who *would buy* | Partner selection |
| **No outcome evidence.** No data link employment support to CDFI repayment | The value proposition is a hypothesis | Strategic interpretation |

---

## 10. Recommended Next Steps

The current phase delivered the market map. The next phase should identify specific institutions to approach, without an undocumented score: each step should keep its evidence visible.

| Step | Approach | Data available now? |
|---|---|---|
| 1. Identify employment-income-dependent borrowers | Within segments A, B, C (and D1), filter by consumer, auto, unsecured and microloan shares; review and adopt the draft income-dependency mapping (`data/reference/employment_income_dependency_map_DRAFT.csv`) | **Yes** (structured), after review |
| 2. Measure potential reach | Members and loan counts (credit unions); loans receivable (loan funds); branch footprint | **Partly**; loan-fund borrower counts need annual reports |
| 3. Assess size and purchasing capacity | Within-type size tiers, net income, equity, staff counts | **Yes** for depositories; **partly** for loan funds |
| 4. Find existing borrower-support services | Websites, annual reports, 990 text: financial coaching, hardship programs, workforce partnerships | **No**: qualitative research on a shortlist |
| 5. Assess digital maturity and channels | Online banking/apps, borrower portals, core vendors, fintech partnerships | **No**: qualitative |
| 6. Find partnership signals | Press releases, fintech/CUSO partnerships, grant programs | **No**: qualitative |
| 7. Shortlist | Transparent screens (e.g. segment A, ≥ 50K members, consumer share ≥ 50%), with evidence recorded per institution in `cdfi_qualitative.csv` | Structured screens **yes**; final judgement qualitative |
| 8. Validate demand | Interviews with lending, collections and member-services leaders; a small pilot design with outcome measures | **No**: primary research |

Before shortlisting, we also recommend closing the cheapest coverage gaps:
- download FFIEC ownership data
- check COSSEC institution-level data for Puerto Rico
- resolve high-value unclassified loan funds by website review

---

## Appendix A: Data Source Register

| # | Dataset | Organization | URL | Period / version | Collection script | Local raw file(s) |
|---|---|---|---|---|---|---|
| 1 | List of Certified CDFIs | U.S. Treasury CDFI Fund | https://www.cdfifund.gov/programs-training/certification/cdfi (file: /media/8018746/download) | As of 17 Sep 2026 | `scripts/download/treasury_cert_list.py` | `data/raw/treasury/cert_list/2026-09-17/CDFI_Cert_List_Manual_9.17.26.xlsx` |
| 2 | BankFind Suite API: institutions, financials, locations | FDIC | https://api.fdic.gov/banks/ | Call Reports 30 Jun 2026 and 30 Jun 2025; retrieved 11 Oct 2026 | `scripts/download/fdic_bankfind.py` | `data/raw/fdic/2026-10-11/*.csv` |
| 3 | 5300 Call Report quarterly data | NCUA | https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data | Jun 2026 (posted Sep 2026) and Jun 2025 | `scripts/download/ncua_call_report.py` | `data/raw/ncua/call_report/2026-06/`, `2025-06/` |
| 4 | Exempt Organizations Business Master File | IRS | https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf | Files dated 7 Sep 2026 | `scripts/download/irs_eo_bmf.py` | `data/raw/other/irs_eo_bmf/2026-10-11/` |
| 5 | Form 990 e-file XML and index | IRS | https://www.irs.gov/charities-non-profits/form-990-series-downloads | Index years 2024–2026; returns with tax years ending 2023–2026 | `scripts/download/irs_990_xml.py`, `scripts/clean/parse_irs_990.py` | `data/raw/other/irs_990/` |
| 6 | List of microlenders | U.S. SBA | https://www.sba.gov/loans/microloans/list-of-microlenders/ | Retrieved 11 Oct 2026 | `scripts/download/program_lists.py` | `data/raw/other/program_lists/2026-10-11/sba_microlenders_p*.html` |
| 7 | Community Advantage SBLCs | U.S. SBA | https://www.sba.gov/document/support-community-advantage-small-business-lending-companies-ca-sblcs | File dated 8 Dec 2025 (the SBA page reportedly described the list as current as of May 2024; not re-verified) | `scripts/download/program_lists.py` | `.../sba_ca_sblcs.xlsx` |
| 8 | FHLB membership | FHFA | https://www.fhfa.gov/data/fhlb-membership | Q2 2026 | `scripts/download/program_lists.py` | `.../fhlb_members_q22026.xlsx` |
| 9 | Searchable Awards Database (CSV) | CDFI Fund | https://www.cdfifund.gov/awards/state-awards | Export 29 Sep 2026; awards 1996–2025 (2023 and 2025 appear incomplete) | `scripts/download/cdfi_fund_awards.py` | `data/raw/awards/2026-09-29/` |
| 10 | State population estimates | U.S. Census Bureau | https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/ | Vintage 2025 | `scripts/download/census_population.py` | `data/raw/census/popest/` |

Each raw file has a `.manifest.json` with URL, retrieval time and checksum. The full pipeline reruns with `./run_pipeline.sh`.

## Appendix B: Classification Rules and Thresholds

| Item | Value | Purpose | Basis |
|---|---|---|---|
| Meaningful activity (portfolio) | ≥ 10% of loans | Secondary activities and flags | Project-defined |
| Portfolio confidence | HIGH ≥ 50%; MEDIUM 30–50% with ≥ 5-pt lead; LOW otherwise | Confidence in primary focus | Project-defined |
| Near-tie | Lead < 5 percentage points | Flags fragile primaries | Project-defined |
| Microenterprise proxy (banks) | C&I loans with original amount ≤ $100K | Separate micro-sized lending | Smallest FDIC Call Report size band (RC-C Part II); used as a proxy |
| Small business (banks) | C&I $100K–$1M | Small-business lending | FDIC Call Report small-business size definition (≤ $1M) |
| Credit-union business reclassification | Average balance per loan > $1M → larger commercial | Credit unions report no size bands | Regulatory $1M threshold applied by the project to *average* balance |
| 990 text rules | 45 detection rules + 1 exclusion rule (regular expressions); most need a lending word in the same sentence | Detect lending activities | Project-defined; `data/reference/focus_text_rules.csv` |
| Evidence score weights | 4 / 1.5 / 1.0 / 2.0 / 0.75 / 0.5 (see §4.2) | Rank categories for loan funds | Project-defined heuristic; not calibrated |
| Evidence HIGH threshold | ≥ 25% of program expenses | Confidence | Project-defined |
| FHLB membership | Supporting only for housing categories | Avoid classifying on membership alone | Project-defined |
| Segment B exception | Small-business primary + (SBA Microloan intermediary or HIGH microenterprise evidence) → B | Group very-small-business specialists | Analytical choice; affects 66 loan funds |
| Size tiers | See §6 | Within-type scale | Project-defined cut points |
| Market totals deduplication | Exclude holding companies whose subsidiaries are all separately certified | Prevent double counting | Project-defined safeguard (146 holding companies) |

## Appendix C: Claim Verification Table

All values were recomputed from the current processed files on 13 Oct 2026. "Institutions" means certified CDFIs (Treasury list rows).

| Claim | Verified value | Population / denominator | Data source | Code / calculation | Caveat |
|---|---|---|---|---|---|
| Certified U.S. CDFIs | **1,281** institutions | Treasury list | CDFI Fund list, 17 Sep 2026 | `cdfi_master.csv` row count; equals Treasury's printed total | Includes 146 holding companies that duplicate certified banks (≈1,135 distinct lenders) |
| Type mix | 561 LF / 367 CU / 184 bank / 160 holding co. / 9 VC | 1,281 | CDFI Fund list | `institution_type` counts | "Venture Capital" merged into "Venture Capital Fund" |
| Assigned a primary focus | **1,106** (86.3%) | 1,281 | FDIC, NCUA, IRS 990, SBA, CDFI Fund awards, FHFA | `primary_lending_focus` not blank | Includes 136 LOW-confidence; 492 evidence-based, 614 portfolio-based |
| Unclassified | **175** | 1,281 | As above | `market_segment_code == 'U'` | 77 PR cooperatives; 78 loan funds; causes in §5 |
| Consumer-focused credit unions | **184** | 286 classifiable CUs (367 total) | NCUA 5300, 30 Jun 2026 | CU with `primary_lending_focus == 'consumer'` (largest balance share) | Balance-based; 157 HIGH confidence |
| Their members | 7.46M members | 184 CUs | NCUA ACCT_083 | sum `members` | Members ≠ borrowers |
| Their consumer loans | $43.3B; 4.32M loans | 184 CUs | NCUA 5300 loan lines | sum of consumer-category balances and counts | Loan counts ≠ unique borrowers |
| Micro/small-business loan funds | **246** | 483 classified loan funds | IRS 990, SBA lists, awards | Loan funds with `market_segment_code` in {B, D} | 242 if strictly micro/small primary (D includes 3 agriculture + 1 commercial); evidence-based, not loan shares |
| Segment B | 115 loan funds | 561 loan funds | as above | 49 microenterprise primary + 66 via B exception | Exception is an analytical choice |
| Mortgage/homeownership-focused | **277** | 1,106 classified | FDIC, NCUA, IRS 990 | `market_segment_code == 'C'` | 228 after removing 49 overlapping holding companies; mixes balance-based and evidence-based |
| Segments sum to universe | 232 + 115 + 277 + 171 + 298 + 13 + 175 = **1,281** | 1,281 | — | crosstab segment × type | Reconciles by type |
| Banks mostly real-estate lenders | 175 CRE-primary, 109 mortgage-primary | 328 classified banks + holding cos. | FDIC Call Reports | `primary_lending_focus` | Counts include overlapping holding companies |
| Median bank consumer share | 3.2% of loans | 179 banks with data | FDIC RC-C | median `share_consumer_pct` | Balance share |
| Loan-fund median size | ≈ $19M total assets | 436 loan funds with asset data | IRS 990 Part X / IRS master file | median `nondep_total_assets_usd` | Tax years 2023–2026 |
| Near-ties get LOW confidence (existing market report) | 91 of 98 near-ties are LOW; **7 are HIGH** | 614 portfolio-classified | — | rule in `build_processed.py` | Earlier report wording slightly overstated; see discrepancies |
| Jobago reduces defaults | **Not supported** | — | — | — | No evidence collected; hypothesis only |

# Limitations

1. **No Treasury organization ID or certification date.** The universe is keyed on an internal registry ID. The
   CDFI Fund's own orgID exists only in awards-database HTML links.
2. **Stale list entries.** At least 5 banks, 4 BHCs' only subsidiaries and 2 credit unions on the 2026-09-17 list had
   already merged or closed according to FDIC/NCUA data. They are kept, flagged and not given successor financials.
3. **Puerto Rico cooperativas (77 "credit unions")** are COSSEC-supervised and have no NCUA data. COSSEC publishes
   aggregate statistics only (institution-level availability not yet investigated).
4. **BHC financials are sums of FDIC-insured subsidiaries**, not consolidated holding-company statements, and only
   for top-tier holders in FDIC data. Six BHCs remain unresolved without FFIEC NIC relationship data.
5. **Double counting:** 146 BHCs duplicate separately certified banks; use `include_in_market_totals`.
6. **Loan funds (561) and VC funds (9) have no public structured lending *balances*.** Their lending focus is now
   evidence-based (990 text, program lists, awards): it reflects what organizations describe, not dollar shares; 78
   loan funds remain UNKNOWN (mostly no EIN / no e-filed 990 / non-descriptive text). Scale comes from 990 Part X total assets where a 990 was found, otherwise IRS BMF total
   assets/revenue (latest return, varying tax periods, nonprofits only). 119 loan funds and 4 VC funds have no
   accepted EIN (no candidate, ambiguous, or weak fuzzy candidate rejected); 54 accepted EINs are review-flagged
   (fuzzy name or ZIP mismatch).
7. **Regulatory categories are not equivalent.** FDIC and NCUA definitions differ (e.g., NCUA commercial RE includes
   multifamily and farmland; FDIC 1–4 family includes investor loans). Credit-union small-business lending cannot be
   separated from other commercial lending.
8. **Borrower reach** is observed only for NCUA credit unions (members). Banks report no customer/borrower counts;
   assets are not a proxy for reach.
9. **Service area / lending geography unavailable.** Branch footprint is a physical-presence measure, not a service area.
10. **Awards linkage is name-based** (no IDs in export); 4,782 award rows remain unlinked (many are legitimately
    non-CDFI or former CDFIs). Recent award years (2023, 2025) appear incomplete in the export.
11. **Census ACS enrichment is blocked** until a free API key is configured; only state population is ingested.
12. **Growth rates include merger effects** where an institution absorbed another between periods.
13. **Socioeconomic context, when added, will describe HQ/branch geography — not the borrower base.**
14. **Text-classification risk.** Regex rules can misread context (e.g. a business lender mentioning "down payments");
    rules were tuned on a reviewed sample but not exhaustively validated. Evidence snippets are stored for audit.
15. **Bank microenterprise is a size proxy** (C&I ≤ $100K original amount, current balance), not a firm-size measure.
    Credit-union microenterprise, housing-development, agricultural and community-facility lending are unobservable.
16. **Segments use primary focus only.** Multi-focus lenders appear in one segment; use `segment_memberships` for
    overlap. Bank segments are dominated by real-estate lending because that is what bank balance sheets show.
17. **Size tiers** use type-specific, convention-based thresholds; loan-fund assets come from returns with tax periods
    between 2023 and 2026.

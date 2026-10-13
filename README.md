# Jobago — U.S. CDFI Landscape Dataset

A reproducible, auditable dataset of all U.S. Treasury-certified CDFIs. It is enriched with regulatory
financials, lending mix, identifiers and CDFI Fund award history, and supports Jobago's assessment of CDFIs
as channel partners.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run_pipeline.sh          # downloads are cached; ~1-2 min from cache
```

## Layout

* `scripts/download/`: source acquisition. Each file is cached with a provenance `.manifest.json`.
* `scripts/clean/`: per-source normalization into `data/interim/`.
* `scripts/match/`: crosswalk (RSSD / FDIC cert / NCUA charter / LEI / EIN) and award linkage.
* `scripts/enrich/`: evidence-based lending-focus classification for loan funds.
* `scripts/analyze/`: processed tables, the data-quality report and the Excel export.
* `data/raw/`: untouched source files. `data/reference/`: ID registry and category mappings.
* `data/processed/`: `cdfi_master`, `cdfi_crosswalk`, `cdfi_financials`, `cdfi_lending`, `cdfi_awards`,
  `cdfi_geography`, `cdfi_segments`, `loan_fund_classification`, `cdfi_focus_evidence`, `cdfi_focus_category_scores`,
  `cdfi_qualitative` (empty template) and `state_summary`, as CSV (and Parquet for the large tables).
* `data/outputs/jobago_cdfi_landscape.xlsx` and `data/outputs/tables/`.
* `research/`: source inventory, methodology, data dictionary, data-quality report, limitations, unresolved matches.

Start with `research/market_structure_report.md`, `research/data_quality_report.md` and `research/methodology.md`.

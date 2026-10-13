#!/usr/bin/env bash
# Rerun the full CDFI landscape pipeline. Downloads are cached under data/raw/ (pass --force to
# individual download scripts to refresh). Safe to rerun; raw files are never overwritten by default.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}

# 1. Acquire raw sources
$PY scripts/download/treasury_cert_list.py
$PY scripts/download/fdic_bankfind.py
$PY scripts/download/ncua_call_report.py
$PY scripts/download/cdfi_fund_awards.py
$PY scripts/download/census_population.py

# 2. Normalize
$PY scripts/clean/normalize_treasury.py
$PY scripts/clean/normalize_fdic.py
$PY scripts/clean/normalize_ncua.py
$PY scripts/download/irs_eo_bmf.py        # needs the normalized Treasury list (states to fetch)

# 3. Match
$PY scripts/match/build_crosswalk.py
$PY scripts/match/match_awards.py

# 4. Lending-focus evidence for loan funds (IRS 990 XML via range requests; federal program lists)
$PY scripts/download/irs_990_xml.py
$PY scripts/download/program_lists.py
$PY scripts/clean/parse_irs_990.py
$PY scripts/enrich/classify_lending_focus.py

# 5. Assemble, segment, audit, export
$PY scripts/analyze/build_processed.py
$PY scripts/analyze/segment_market.py
$PY scripts/analyze/data_quality_report.py
$PY scripts/analyze/export_outputs.py

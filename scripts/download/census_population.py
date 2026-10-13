"""Download Census Bureau Vintage state population estimates (no API key required).

Source: https://www2.census.gov/programs-surveys/popest/datasets/2020-<V>/state/totals/NST-EST<V>-ALLDATA.csv
The newest available vintage is found by probing from the current year downward.

This is a stop-gap for state-level per-capita counts. Full ACS enrichment (income, poverty,
unemployment, broadband ...) via api.census.gov requires a free API key; see research/source_inventory.md.

Output: data/raw/census/popest/NST-EST<V>-ALLDATA.csv (+ manifest)
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RAW, USER_AGENT, download  # noqa: E402

URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-{v}/state/totals/NST-EST{v}-ALLDATA.csv"


def main(force: bool = False) -> Path:
    for v in range(dt.date.today().year, 2022, -1):
        url = URL.format(v=v)
        if requests.head(url, headers={"User-Agent": USER_AGENT}, timeout=60).status_code == 200:
            print(f"Census population estimates vintage {v}")
            return download(url, RAW / "census" / "popest" / f"NST-EST{v}-ALLDATA.csv", force=force, vintage=v)
    raise RuntimeError("No Census state population estimates file found")


if __name__ == "__main__":
    main(force="--force" in sys.argv)

"""Download NCUA 5300 Call Report quarterly bulk data.

Source page: https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data
Files:       https://ncua.gov/files/publications/analysis/call-report-data-YYYY-MM.zip

Usage:
    python scripts/download/ncua_call_report.py               # latest available + same quarter 1y earlier
    python scripts/download/ncua_call_report.py 2026-06 2025-06

Output: data/raw/ncua/call_report/<YYYY-MM>/call-report-data-YYYY-MM.zip (+ manifest) and an
`extracted/` folder with the comma-delimited text files.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RAW, download, http_get  # noqa: E402

PAGE = "https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data"
URL = "https://ncua.gov/files/publications/analysis/call-report-data-{q}.zip"


def available_quarters() -> list[str]:
    html = http_get(PAGE).text
    return sorted(set(re.findall(r"call-report-data-(\d{4}-\d{2})\.zip", html)))


def fetch(q: str, force: bool = False) -> Path:
    dest = RAW / "ncua" / "call_report" / q / f"call-report-data-{q}.zip"
    download(URL.format(q=q), dest, force=force, source_page=PAGE, reporting_period=q)
    out = dest.parent / "extracted"
    if not out.exists() or force:
        with zipfile.ZipFile(dest) as z:
            z.extractall(out)
    return out


def year_ago(q: str) -> str:
    y, m = q.split("-")
    return f"{int(y) - 1}-{m}"


def main(argv: list[str]) -> None:
    force = "--force" in argv
    qs = [a for a in argv if re.fullmatch(r"\d{4}-\d{2}", a)]
    if not qs:
        latest = available_quarters()[-1]
        qs = [latest, year_ago(latest)]
    for q in qs:
        print(f"NCUA call report {q}")
        fetch(q, force=force)


if __name__ == "__main__":
    main(sys.argv[1:])

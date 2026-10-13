"""Download the CDFI Fund Searchable Awards Database CSV export.

Page:   https://www.cdfifund.gov/awards/state-awards  ("Download CSV" link in the table footer)
Export: https://www.cdfifund.gov/system/files/<YYYY-MM>/<YYYY-MM-DD>_state-awards.csv  (date-stamped;
        the link is discovered from the page on each run)

Columns: Awardee, City, State, Year, Program, Amount. No organization ID, EIN or award number.

Output: data/raw/awards/<export-date>/<filename> (+ manifest)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RAW, download, http_get  # noqa: E402

PAGE = "https://www.cdfifund.gov/awards/state-awards"


def main(force: bool = False) -> Path:
    html = http_get(PAGE).text
    m = re.search(r'href="([^"]*?(\d{4}-\d{2}-\d{2})_state-awards\.csv)"', html)
    if not m:
        raise RuntimeError(f"CSV export link not found on {PAGE}; page layout may have changed")
    href, export_date = m.groups()
    url = href if href.startswith("http") else "https://www.cdfifund.gov" + href
    dest = RAW / "awards" / export_date / url.rsplit("/", 1)[-1]
    print(f"CDFI Fund awards export {export_date}: {url}")
    return download(url, dest, force=force, source_page=PAGE, export_date=export_date)


if __name__ == "__main__":
    main(force="--force" in sys.argv)

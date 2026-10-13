"""Download the current CDFI Fund list of certified CDFIs.

The CDFI Fund publishes the list as an Excel workbook linked from the CDFI certification
page. The media ID changes with each release, so the link is discovered from the page by
its title ("Certified CDFIs as of <Month D, YYYY>") rather than hard-coded.

Output: data/raw/treasury/cert_list/<as_of_date>/<original filename> (+ manifest)
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RAW, download, http_get  # noqa: E402

CERT_PAGE = "https://www.cdfifund.gov/programs-training/certification/cdfi"
BASE = "https://www.cdfifund.gov"


def find_current_list() -> tuple[str, dt.date]:
    html = http_get(CERT_PAGE).text
    m = re.search(
        r'href="(/media/\d+/download[^"]*)"[^>]*title="Certified CDFIs as of ([A-Za-z]+ \d{1,2}, \d{4})"',
        html,
    )
    if not m:
        raise RuntimeError(
            "Could not find the 'Certified CDFIs as of ...' link on the certification page; "
            "the page layout may have changed. Inspect " + CERT_PAGE
        )
    href, date_str = m.groups()
    as_of = dt.datetime.strptime(date_str, "%B %d, %Y").date()
    return BASE + href.replace("&amp;", "&"), as_of


def main(force: bool = False) -> Path:
    url, as_of = find_current_list()
    print(f"Current certified-CDFI list: as of {as_of} -> {url}")
    resp = http_get(url)
    cd = resp.headers.get("Content-Disposition", "")
    fname = re.search(r'filename="?([^";]+)', cd)
    fname = fname.group(1) if fname else f"certified_cdfis_{as_of}.xlsx"
    dest = RAW / "treasury" / "cert_list" / as_of.isoformat() / fname
    return download(url, dest, force=force, source_page=CERT_PAGE, source_as_of_date=as_of.isoformat())


if __name__ == "__main__":
    main(force="--force" in sys.argv)

"""Download IRS Exempt Organizations Business Master File (EO BMF) state extracts.

Source page: https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
Files:       https://www.irs.gov/pub/irs-soi/eo_<st>.csv   (lower-case postal code)

Used only to find EINs for non-depository CDFIs (loan funds, VC funds) by name + state + ZIP.
Only states where such CDFIs are headquartered are downloaded (derived from the normalized
Treasury list), plus eo_pr.csv when Puerto Rico appears.

Output: data/raw/other/irs_eo_bmf/<retrieval-date>/eo_<st>.csv (+ manifests)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, RAW, TODAY, download  # noqa: E402

PAGE = "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf"
URL = "https://www.irs.gov/pub/irs-soi/eo_{st}.csv"


def main(force: bool = False) -> None:
    t = pd.read_csv(INTERIM / "normalized_treasury" / "treasury_cert_list.csv")
    states = sorted(t.loc[t.institution_type.isin(["Loan Fund", "Venture Capital Fund"]), "hq_state"].dropna().unique())
    out = RAW / "other" / "irs_eo_bmf" / TODAY
    print(f"IRS EO BMF: {len(states)} states -> {out}")
    for st in states:
        dest = out / f"eo_{st.lower()}.csv"
        existed = dest.exists()
        try:
            download(URL.format(st=st.lower()), dest, force=force, source_page=PAGE, state=st)
        except RuntimeError as e:
            print(f"  WARNING: {st}: {e}")
        if not existed:
            time.sleep(0.5)


if __name__ == "__main__":
    main(force="--force" in sys.argv)

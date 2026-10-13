"""Fetch the latest IRS Form 990-series e-file XML for each loan-fund / VC-fund EIN.

Source page: https://www.irs.gov/charities-non-profits/form-990-series-downloads
Index:       https://apps.irs.gov/pub/epostcard/990/xml/{YYYY}/index_{YYYY}.csv
Archives:    https://apps.irs.gov/pub/epostcard/990/xml/{YYYY}/{XML_BATCH_ID}.zip  (~100-300 MB each)

The archives support HTTP range requests, so only the zip central directory and the needed
members are downloaded (via a buffered remote file object) instead of whole archives.

Selection: for each accepted EIN in data/processed/cdfi_crosswalk.csv (Loan Fund / Venture Capital
Fund), the filing with the latest TAX_PERIOD across the index years; Form 990 preferred over 990-EZ
for the same period. Index "year" is the IRS processing year, not the tax year.

Outputs: data/raw/other/irs_990/index/index_{YYYY}.csv (+ manifests)
         data/raw/other/irs_990/xml/{OBJECT_ID}_public.xml
         data/raw/other/irs_990/selected_filings.csv  (EIN -> filing chosen, with fetch status)
"""
from __future__ import annotations

import datetime as dt
import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

try:  # some IRS archives use Deflate64 (zip method 9), unsupported by the stdlib
    import zipfile_deflate64  # noqa: F401  (patches zipfile on import)
except ImportError:  # pragma: no cover
    print("  note: install zipfile-deflate64 to read Deflate64-compressed IRS archives")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import PROCESSED, RAW, USER_AGENT, download  # noqa: E402

BASE = "https://apps.irs.gov/pub/epostcard/990/xml"
OUT = RAW / "other" / "irs_990"
CHUNK = 1 << 20  # 1 MB read-ahead keeps request counts low while reading the central directory


class RemoteFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests with a simple read-ahead buffer."""

    def __init__(self, url: str):
        self.url, self.pos, self.requests = url, 0, 0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        h = self.session.head(url, timeout=60, allow_redirects=True)
        h.raise_for_status()
        self.size = int(h.headers["Content-Length"])
        self.buf_start, self.buf = 0, b""

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def _fill(self, start: int, length: int) -> None:
        end = min(start + max(length, CHUNK), self.size) - 1
        r = self.session.get(self.url, headers={"Range": f"bytes={start}-{end}"}, timeout=120)
        r.raise_for_status()
        self.requests += 1
        self.buf_start, self.buf = start, r.content

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        n = min(n, self.size - self.pos)
        if not (self.buf_start <= self.pos and self.pos + n <= self.buf_start + len(self.buf)):
            self._fill(self.pos, n)
        off = self.pos - self.buf_start
        out = self.buf[off:off + n]
        self.pos += len(out)
        return out


def target_eins() -> pd.DataFrame:
    xw = pd.read_csv(PROCESSED / "cdfi_crosswalk.csv", dtype={"id_value": str})
    e = xw[(xw.id_system == "EIN") & xw.institution_type.isin(["Loan Fund", "Venture Capital Fund"])]
    return e[["cdfi_id", "id_value"]].rename(columns={"id_value": "EIN"}).assign(EIN=lambda d: d.EIN.str.zfill(9))


def load_indexes(years: list[int]) -> pd.DataFrame:
    parts = []
    for y in years:
        dest = OUT / "index" / f"index_{y}.csv"
        try:
            download(f"{BASE}/{y}/index_{y}.csv", dest, index_year=y)
        except RuntimeError as e:
            print(f"  index {y} unavailable: {e}")
            continue
        ix = pd.read_csv(dest, dtype=str, low_memory=False)
        ix.columns = [c.strip().upper() for c in ix.columns]
        ix["INDEX_YEAR"] = y
        parts.append(ix)
    return pd.concat(parts, ignore_index=True)


def select_filings(ix: pd.DataFrame, eins: pd.DataFrame) -> pd.DataFrame:
    ix = ix[ix.EIN.str.zfill(9).isin(eins.EIN)].copy()
    ix["EIN"] = ix.EIN.str.zfill(9)
    ix = ix[ix.RETURN_TYPE.isin(["990", "990EZ", "990PF"])]
    ix["form_rank"] = ix.RETURN_TYPE.map({"990": 0, "990EZ": 1, "990PF": 2})
    ix = ix.sort_values(["EIN", "TAX_PERIOD", "form_rank", "INDEX_YEAR"], ascending=[True, False, True, False])
    best = ix.drop_duplicates("EIN")
    return eins.merge(best, on="EIN", how="left")


def fetch(sel: pd.DataFrame) -> pd.DataFrame:
    xml_dir = OUT / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    sel = sel.copy()
    sel["xml_file"] = pd.NA
    sel["archive"] = pd.NA
    sel["fetch_status"] = "no_efiled_return_in_index"
    todo = sel[sel.OBJECT_ID.notna()]
    for batch, g in todo.groupby("XML_BATCH_ID"):
        need = {oid: i for i, oid in zip(g.index, g.OBJECT_ID) if not (xml_dir / f"{oid}_public.xml").exists()}
        for i, oid in zip(g.index, g.OBJECT_ID):
            if oid not in need:
                sel.at[i, "xml_file"], sel.at[i, "fetch_status"] = f"{oid}_public.xml", "cached"
        if not need:
            continue
        # Year comes from the batch ID; some index rows carry lower-case suffixes ("06a") but files are
        # upper-case. Large months are split into sibling archives (..._05A, _05B, ...) and the index does
        # not always name the right one, so siblings are tried for members not found.
        year, rest = batch.split("_", 1)
        stem, letter = rest.upper()[:-1], rest.upper()[-1]
        candidates = [f"{year}_{stem}{letter}"] + [f"{year}_{stem}{c}" for c in "ABCD" if c != letter]
        for arch in candidates:
            if not need:
                break
            url = f"{BASE}/{year}/{arch}.zip"
            try:
                rf = RemoteFile(url)
            except requests.HTTPError:
                continue
            try:
                z = zipfile.ZipFile(rf)
                members = {Path(n).name.split("_")[0]: n for n in z.namelist() if n.endswith(".xml")}
                found = [oid for oid in need if oid in members]
                for oid in found:
                    (xml_dir / f"{oid}_public.xml").write_bytes(z.read(members[oid]))
                    i = need.pop(oid)
                    sel.at[i, "xml_file"], sel.at[i, "fetch_status"] = f"{oid}_public.xml", "fetched"
                    sel.at[i, "archive"] = arch
                print(f"  {arch}: {len(found)} filings, {rf.requests} range requests")
            except Exception as e:  # pragma: no cover - network / format
                print(f"  {arch}: ERROR {e}")
        for oid, i in need.items():
            sel.at[i, "fetch_status"] = "object_not_in_archive"
    sel["source_url_pattern"] = f"{BASE}/<YYYY>/<XML_BATCH_ID upper-cased>.zip"
    sel["retrieval_date"] = dt.date.today().isoformat()
    return sel


def main() -> None:
    this_year = dt.date.today().year
    years = list(range(this_year - 2, this_year + 1))
    eins = target_eins()
    print(f"IRS 990 XML for {eins.EIN.nunique()} EINs; index years {years}")
    sel = select_filings(load_indexes(years), eins)
    sel = fetch(sel)
    sel.drop(columns=["form_rank"], errors="ignore").to_csv(OUT / "selected_filings.csv", index=False)
    print(sel.fetch_status.value_counts().to_string())
    print(sel.RETURN_TYPE.value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()

"""Download and parse public federal program-participation lists used as lending-focus evidence.

1. SBA Microloan Program intermediaries (microenterprise evidence)
   https://www.sba.gov/loans/microloans/list-of-microlenders/  (paginated HTML, ?query-202-page=N)
2. SBA Community Advantage Small Business Lending Companies (small-business evidence)
   https://www.sba.gov/document/support-community-advantage-small-business-lending-companies-ca-sblcs
   -> XLSX on legacy.sba.gov (URL discovered from the page; falls back to the last known URL)
3. FHFA Federal Home Loan Bank membership (housing-finance evidence for non-depository CDFIs)
   https://www.fhfa.gov/data/fhlb-membership -> quarterly XLSX (latest discovered from the page)

Raw pages/files: data/raw/other/program_lists/<retrieval-date>/...
Parsed tables:   data/interim/program_lists/{sba_microlenders,sba_ca_sblcs,fhlb_members}.csv
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import INTERIM, RAW, TODAY, download, http_get, read_manifest  # noqa: E402

RAWDIR = RAW / "other" / "program_lists" / TODAY
OUT = INTERIM / "program_lists"
MICRO = "https://www.sba.gov/loans/microloans/list-of-microlenders/"
CA_PAGE = "https://www.sba.gov/document/support-community-advantage-small-business-lending-companies-ca-sblcs"
CA_FALLBACK = "https://legacy.sba.gov/sites/default/files/2025-12/List%20of%20CA%20SBLCs.xlsx"
FHFA_PAGE = "https://www.fhfa.gov/data/fhlb-membership"


def text(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def sba_microlenders() -> pd.DataFrame:
    first = download(MICRO, RAWDIR / "sba_microlenders_p1.html")
    pages = max(int(p) for p in re.findall(r"query-202-page=(\d+)", first.read_text(errors="ignore")))
    rows = []
    for p in range(1, pages + 1):
        f = first if p == 1 else download(f"{MICRO}?query-202-page={p}", RAWDIR / f"sba_microlenders_p{p}.html")
        s = f.read_text(errors="ignore")
        body = s[s.find("<tbody"):s.find("</tbody>")]
        for tr in re.findall(r"<tr>(.*?)</tr>", body, flags=re.S):
            name_html = re.search(r'sba-dynamic-content__link">(.*?)</p>', tr, flags=re.S)
            states = re.search(r'sba-dynamic-content__states[^"]*">(.*?)</p>', tr, flags=re.S)
            addr = re.findall(r'address-line">(.*?)</span>', tr, flags=re.S)
            web = re.search(r'href="(https?://[^"]+)"', name_html.group(1)) if name_html else None
            last = text(addr[-1]) if addr else ""
            m = re.match(r"(.+?),\s*([A-Z]{2})\s+(\d{5})", last)
            rows.append({"name": text(name_html.group(1)) if name_html else "", "website": web.group(1) if web else pd.NA,
                         "states_served": text(states.group(1)) if states else pd.NA,
                         "address": "; ".join(text(a) for a in addr), "city": m.group(1) if m else pd.NA,
                         "state": m.group(2) if m else pd.NA, "zip5": m.group(3) if m else pd.NA, "page": p})
    df = pd.DataFrame(rows)
    df["source"] = "SBA list of microlenders (Microloan Program intermediaries)"
    df["source_url"] = MICRO
    df["retrieval_date"] = TODAY
    return df


def sba_ca_sblcs() -> pd.DataFrame:
    try:
        page = http_get(CA_PAGE).text
        m = re.search(r'href="([^"]+List[^"]*CA[^"]*SBLC[^"]*\.xlsx)"', page, flags=re.I)
        url = m.group(1) if m else CA_FALLBACK
    except RuntimeError:
        url = CA_FALLBACK
    cands = [url] if url.startswith("http") else ["https://legacy.sba.gov" + url, "https://www.sba.gov" + url]
    f = None
    for u in cands + [CA_FALLBACK]:
        try:
            f = download(u, RAWDIR / "sba_ca_sblcs.xlsx", source_page=CA_PAGE)
            break
        except RuntimeError:
            continue
    if f is None:
        raise RuntimeError("Community Advantage SBLC list not downloadable from " + ", ".join(cands + [CA_FALLBACK]))
    raw = pd.read_excel(f, header=None, dtype=str)
    hdr = next(i for i, r in raw.iterrows() if r.astype(str).str.contains("Lender Name", case=False).any())
    df = pd.read_excel(f, header=hdr, dtype=str).dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    name_col = next(c for c in df.columns if "lender" in c.lower())
    addr_col = next((c for c in df.columns if "address" in c.lower()), None)
    out = pd.DataFrame({"name": df[name_col].str.strip()})
    out["address"] = df[addr_col] if addr_col else pd.NA
    st = out.address.astype(str).str.extract(r",?\s*([A-Z]{2})\s+(\d{5})")
    out["state"], out["zip5"] = st[0], st[1]
    for c in df.columns:
        if c not in (name_col, addr_col):
            out[c.lower().replace(" ", "_")] = df[c]
    out["source"] = "SBA Community Advantage Small Business Lending Companies list"
    out["source_url"] = read_manifest(f)["source_url"]
    out["retrieval_date"] = TODAY
    return out.dropna(subset=["name"])


def fhlb_members() -> pd.DataFrame:
    page = http_get(FHFA_PAGE).text
    links = re.findall(r'href="([^"]*fhlb_members_q(\d)(\d{4})\.xlsx)"', page, flags=re.I)
    if not links:
        raise RuntimeError("FHLB membership XLSX link not found on " + FHFA_PAGE)
    href, q, y = max(links, key=lambda t: (t[2], t[1]))
    url = href if href.startswith("http") else "https://www.fhfa.gov" + href
    f = download(url, RAWDIR / f"fhlb_members_q{q}{y}.xlsx", source_page=FHFA_PAGE, quarter=f"{y}Q{q}")
    df = pd.read_excel(f, dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    df["source"] = f"FHFA FHLB membership {y}Q{q}"
    df["source_url"] = url
    df["retrieval_date"] = TODAY
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("sba_microlenders", sba_microlenders), ("sba_ca_sblcs", sba_ca_sblcs), ("fhlb_members", fhlb_members)]:
        try:
            df = fn()
            df.to_csv(OUT / f"{name}.csv", index=False)
            print(f"  {name}: {len(df):,} rows")
        except Exception as e:  # keep going; a missing list only weakens evidence
            print(f"  WARNING {name}: {e}")


if __name__ == "__main__":
    main()

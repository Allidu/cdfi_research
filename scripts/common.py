"""Shared helpers: project paths, cached HTTP downloads, and provenance manifests.

Every raw download is written once under data/raw/<source>/... and accompanied by a
`<file>.manifest.json` recording URL, retrieval timestamp, HTTP headers of interest and
SHA-256. Raw files are never overwritten unless `force=True` is passed explicitly.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
REFERENCE = DATA / "reference"
RESEARCH = ROOT / "research"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 jobago-cdfi-research"
)

TODAY = dt.date.today().isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def http_get(url: str, *, params=None, retries: int = 3, timeout: int = 120) -> requests.Response:
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # pragma: no cover - network
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} attempts: {url}: {last}")


def write_manifest(path: Path, url: str, resp: requests.Response | None = None, **extra) -> dict:
    manifest = {
        "file": path.name,
        "source_url": url,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }
    if resp is not None:
        for h in ("Last-Modified", "Content-Type", "Content-Disposition", "ETag"):
            if h in resp.headers:
                manifest[h.lower()] = resp.headers[h]
    manifest.update(extra)
    Path(str(path) + ".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def read_manifest(path: Path) -> dict:
    return json.loads(Path(str(path) + ".manifest.json").read_text())


def download(url: str, dest: Path, *, params=None, force: bool = False, **extra) -> Path:
    """Download `url` to `dest` once (cached). Writes a provenance manifest alongside."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        print(f"  cached: {dest.relative_to(ROOT)}")
        return dest
    resp = http_get(url, params=params)
    dest.write_bytes(resp.content)
    full_url = resp.url if params else url
    write_manifest(dest, full_url, resp, **extra)
    print(f"  downloaded: {dest.relative_to(ROOT)} ({len(resp.content):,} bytes)")
    return dest


# ---------------------------------------------------------------------------
# Name normalization (used only as a matching aid, never as a primary key)
# ---------------------------------------------------------------------------
_SUFFIXES = [
    "federal credit union", "community credit union", "credit union", "fcu", "cu",
    "national association", "n a", "na", "bank and trust company", "and trust company",
    "trust company", "savings bank", "bank", "bancorp", "bancshares", "bankshares",
    "financial corporation", "financial corp", "financial group", "holding company",
    "holdings", "corporation", "corp", "company", "co", "incorporated", "inc", "llc", "ltd",
    "the",
]


def normalize_name(name: str | None, strip_suffixes: bool = True) -> str:
    if name is None or (isinstance(name, float)):
        return ""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ").replace("`", "").replace("'", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if strip_suffixes:
        changed = True
        while changed:
            changed = False
            for suf in _SUFFIXES:
                if s.endswith(" " + suf):
                    s = s[: -len(suf) - 1].strip()
                    changed = True
                if s.startswith("the "):
                    s = s[4:]
                    changed = True
    return s


def normalize_domain(url: str | None) -> str:
    if not url or not isinstance(url, str):
        return ""
    s = url.strip().lower()
    if s in {"non given", "none", "n/a", "na", "-"}:
        return ""
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\d?\.", "", s)
    s = s.split("/")[0].split("?")[0].strip(". ")
    return s if "." in s else ""


def latest_dated_dir(parent: Path) -> Path:
    """Most recent YYYY-MM-DD subdirectory (ignores e.g. `_superseded/`)."""
    dirs = sorted(p for p in parent.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))
    if not dirs:
        raise FileNotFoundError(f"No dated download folder under {parent}")
    return dirs[-1]

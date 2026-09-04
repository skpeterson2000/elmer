"""Re-download the source question pools into data/raw.

The URLs are the current public releases.  NCVEC serves plain files; fcc.gov
sits behind a filter that rejects bare scripted requests, so those fetches send
an ordinary browser's header set.
"""
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

BROWSER = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

SOURCES = [
    # NCVEC amateur pools, current releases with all errata applied
    ("tech2026.docx", "https://ncvec.org/downloads/2026-2030%20Technician%20Pool"
                      "%20and%20Syllabus%20Public%20Release%20Feb%2019%202026.docx"),
    ("gen2023.docx", "https://ncvec.org/downloads/General%20Class%20Pool%20and%20"
                     "Syllabus%202023-2027%20Public%20Release%20with%206th%20"
                     "Errata%20Feb%204%202026.docx"),
    ("extra2024.docx", "https://ncvec.org/downloads/2024-2028%20Extra%20Class%20"
                       "Question%20Pool%20and%20Syllabus%20Public%20Release%20with"
                       "%204th%20Errata%20Feb%204%202026.docx"),
    ("tech_figures.pdf", "https://ncvec.org/downloads/TECH_2026/2026-2030%20"
                         "Technician%20Pool%203%20Diagrams.pdf"),
    ("gen_figures.pdf", "https://www.ncvec.org/downloads/G7-1.pdf"),
    ("extra_figures.zip", "https://www.ncvec.org/downloads/e4_2024-svgs.zip"),
    ("extra_figures.pdf", "https://www.ncvec.org/downloads/Extra_Figures_2024-2028-1.pdf"),
    # FCC commercial operator pools
    ("element1.pdf", "https://www.fcc.gov/sites/default/files/Element%201_0.pdf"),
    ("element3.pdf", "https://www.fcc.gov/sites/default/files/Element%203_0.pdf"),
    ("element8.pdf", "https://www.fcc.gov/sites/default/files/Element%208%20"
                     "Question%20Pool%20updated%2003062024.pdf"),
]


def fetch_one(name, url, timeout=120):
    request = urllib.request.Request(url, headers=BROWSER)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    if len(payload) < 4096:
        raise OSError(f"{name}: suspiciously small download ({len(payload)} bytes)")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_bytes(payload)
    return len(payload)


def fetch_all():
    print("Fetching source question pools:")
    failures = []
    for name, url in SOURCES:
        try:
            size = fetch_one(name, url)
            print(f"  {name:22s} {size / 1024:8.0f} KB")
        except Exception as exc:
            print(f"  {name:22s} FAILED - {exc}")
            failures.append(name)
    if failures:
        print(f"\n  {len(failures)} download(s) failed; the existing copies in "
              f"data/raw are untouched.")
    return not failures


if __name__ == "__main__":
    fetch_all()

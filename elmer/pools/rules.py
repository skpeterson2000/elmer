"""Fetch 47 CFR Part 97 from eCFR so rule questions can quote the real rule.

Roughly one amateur question in six carries an FCC citation like ``97.301(d)``.
For those, the best possible explanation is not a paraphrase - it is the text of
the regulation itself, which is a US government work and free to redistribute.

The eCFR API insists on compressed responses, hence the explicit header.
"""
import gzip
import io
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "rules"
API = "https://www.ecfr.gov/api/versioner/v1/full/{date}/title-47.xml?part={part}"
TITLES = "https://www.ecfr.gov/api/versioner/v1/titles.json"
HEADERS = {"User-Agent": "ELMER/1.0 (personal amateur radio study tool)",
           "Accept-Encoding": "gzip"}

RE_SECTION = re.compile(r"^§+\s*(\d+\.\d+)\s*(.*)$")
# a paragraph opening like "(d)" or "(b)(2)"
RE_PARA = re.compile(r"^\((\w+)\)")


def _fetch(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read()
    if response.headers.get("Content-Encoding") == "gzip":
        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    return raw


def _clean(element):
    return " ".join("".join(element.itertext()).split())


def _render_table(table):
    """Flatten a CFR table to text rows.

    The band-privilege tables in 97.301 and 97.303 are the substance of those
    rules; dropping them would leave a citation pointing at a lead-in sentence
    and nothing else.
    """
    rows = []
    for row in table.iter():
        if row.tag not in ("TR", "ROW"):
            continue
        cells = [_clean(c) for c in row if c.tag in ("TD", "TH", "ENT")]
        cells = [c for c in cells if c]
        if cells:
            rows.append(" | ".join(cells))
    return rows


def _blocks_in_order(node):
    """Paragraphs and tables of a section, in the order they are printed."""
    out = []
    for element in node.iter():
        if element.tag == "P":
            text = _clean(element)
            if text:
                out.append(text)
        elif element.tag in ("TABLE", "GPOTABLE"):
            out.extend(_render_table(element))
    return out


def latest_issue_date(title=47):
    """eCFR only serves dates it has actually issued, which lags today."""
    titles = json.loads(_fetch(TITLES))
    for entry in titles.get("titles", []):
        if entry.get("number") == title:
            return entry.get("latest_issue_date")
    raise LookupError(f"title {title} not listed by eCFR")


def fetch_part(part=97, date=None):
    """Return {section_number: {"title": ..., "paragraphs": [...]}}"""
    date = date or latest_issue_date()
    root = ET.fromstring(_fetch(API.format(date=date, part=part)))

    sections = {}
    for node in root.iter():
        if node.get("TYPE") != "SECTION":
            continue
        head = _clean(node.find("HEAD")) if node.find("HEAD") is not None else ""
        match = RE_SECTION.match(head)
        if not match:
            continue
        number, title = match.group(1), match.group(2).strip(" .")
        sections[number] = {
            "number": number, "title": title,
            "paragraphs": _blocks_in_order(node),
        }
    return sections


def _successor(label):
    """The label that ends a block: (d) is followed by (e), (4) by (5)."""
    if label.isdigit():
        return str(int(label) + 1)
    if len(label) == 1 and label.isalpha():
        return chr(ord(label) + 1)
    return None                              # roman numerals: fall back to depth


def _block(paragraphs, label):
    """The paragraphs belonging to one labelled block, sub-items included.

    CFR nests as (a) > (1) > (i) > (A), so a block ends at its own successor
    rather than at the next parenthesis - stopping at the first '(' would cut
    (d) off before the frequency table that is the whole point of citing it.
    """
    stop = _successor(label)
    out, capturing = [], False
    for para in paragraphs:
        match = RE_PARA.match(para)
        tag = match.group(1) if match else None
        if not capturing:
            if tag == label:
                capturing = True
                out.append(para)
            continue
        if tag == stop:
            break
        if stop is None and tag is not None and len(tag) == len(label):
            break
        out.append(para)
    return out


def paragraph_for(section, citation):
    """Pull just the cited paragraph out of a section, e.g. '97.301(d)'.

    Falls back to the whole section when the citation names no paragraph or the
    paragraph cannot be located - better to show more rule than none.
    """
    labels = re.findall(r"\(([^)]+)\)", citation)
    paragraphs = section["paragraphs"]
    if not labels:
        return paragraphs
    for label in labels:
        narrowed = _block(paragraphs, label)
        if not narrowed:
            break
        paragraphs = narrowed
    return paragraphs or section["paragraphs"]


def build(part=97):
    OUT.mkdir(parents=True, exist_ok=True)
    sections = fetch_part(part)
    path = OUT / f"part{part}.json"
    path.write_text(json.dumps(sections, indent=1))
    words = sum(len(" ".join(s["paragraphs"]).split()) for s in sections.values())
    print(f"  47 CFR part {part}: {len(sections)} sections, {words:,} words -> "
          f"{path.relative_to(ROOT)}")
    return sections


if __name__ == "__main__":
    build(97)

"""Regional band plans from the local frequency coordinator.

These are somebody else's work and they change, so they are fetched on demand
and cached rather than shipped with ELMER. The cache lives under data/regional
and is gitignored for the same reason the terrain cache is: it is not ours to
redistribute, and it is specific to where you are.

Adding a coordinator means adding an entry to COORDINATORS with a parser; the
rest of the application does not care which state it is looking at.
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "regional"
USER_AGENT = ("Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MAX_AGE_DAYS = 30
MIN_INTERVAL = 1.1

# A line like "144.60 - 144.90  FM repeater Inputs", with an optional leading
# asterisk and any of several dash characters.
RE_SEGMENT = re.compile(
    r"^\*?\s*(\d{2,4}\.\d{1,4})\s*(?:-|–|—|to|TO)?\s*"
    r"(\d{2,4}\.\d{1,4})?\s+(\S.{2,120}?)\s*$")

_last_call = [0.0]


def _text(url, encoding="cp1252"):
    wait = MIN_INTERVAL - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read()
    page = raw.decode(encoding, "replace")
    page = re.sub(r"(?is)<(script|style).*?</\1>", "", page)
    page = re.sub(r"(?i)<br\s*/?>|</tr>|</p>|</h[1-6]>", "\n", page)
    page = re.sub(r"(?i)</t[dh]>", "\t", page)      # keep cell boundaries
    return html.unescape(re.sub(r"<[^>]+>", "", page)).replace("\xa0", " ")


def _classify(label):
    """Best guess at an activity kind from the coordinator's own wording."""
    text = label.lower()
    pairs = [
        ("repeater", ("repeater", "rptr")),
        ("simplex", ("simplex",)),
        ("satellite", ("satellite", "oscar", "translator")),
        ("beacon", ("beacon",)),
        ("image", ("atv", "sstv", "fast scan", "television")),
        ("digital", ("packet", "digital", "data", "aprs", "rtty", "dstar",
                     "d-star", "dmr", "fusion", "winlink", "link")),
        ("cw", ("cw", "eme", "weak signal")),
        ("phone", ("ssb", "phone", "voice", "fm ")),
        ("calling", ("calling",)),
    ]
    for kind, needles in pairs:
        if any(n in text for n in needles):
            return kind
    return "special"


RE_FREQ_SPEC = re.compile(
    r"^\*?\s*(\d{2,4}\.\d{1,4})\s*(?:-|–|—|to|TO)?\s*(\d{2,4}\.\d{1,4})?\s*(.*)$")
RE_HAS_FREQ = re.compile(r"\d{2,4}\.\d{1,4}")
# Prose that happens to sit near a frequency is not a band segment.
RE_PAIR_LIST = re.compile(r"^/\s*\d{2,4}\.\d")
RE_PROSE = re.compile(r"(?i)\b(are recommended|is recommended|please|see the|"
                      r"note:|frequency|coordinat|pairs|the following)")


def _parse_plan(page):
    """Read a coordinator's plan out of pages that are only loosely tabular.

    The MRC pages put a range on one row and its label on the next as often as
    they put both together, and wrap a long label onto a further row. So rows
    are walked in sequence: a row opening with a frequency starts a segment,
    and the short rows after it that carry no frequency of their own are taken
    as the rest of its label.
    """
    rows = [" ".join(r.replace("\t", " ").split()) for r in page.split("\n")]
    rows = [r for r in rows if r]

    segments, seen, i = [], set(), 0
    while i < len(rows):
        row = rows[i]
        i += 1
        if not RE_HAS_FREQ.match(row.lstrip("*").strip()):
            continue
        m = RE_FREQ_SPEC.match(row)
        if not m:
            continue
        low = float(m.group(1))
        high = float(m.group(2)) if m.group(2) else low
        parts = [m.group(3).strip(" .*")] if m.group(3).strip(" .*") else []

        # Absorb the following label rows, which carry no frequency of their own.
        while i < len(rows) and len(parts) < 3:
            nxt = rows[i]
            if RE_HAS_FREQ.search(nxt) or len(nxt) > 70:
                break
            parts.append(nxt.strip(" .*"))
            i += 1

        label = " ".join(p for p in parts if p).strip(" .*&")
        if not label or len(label) < 3 or RE_PROSE.search(label):
            continue
        # The plans also print tables of coordinated repeater pairs
        # ("52.010/53.010"). Those are pairs, not plan segments.
        if RE_PAIR_LIST.match(label):
            continue
        digits = sum(c.isdigit() or c in "./ " for c in label)
        if digits / len(label) > 0.6:
            continue
        if high < low:
            continue
        key = (low, high, label)
        if key in seen:
            continue
        seen.add(key)
        segments.append({"low": low, "high": high, "label": label,
                         "kind": _classify(label)})
    return segments


MRC_BASE = "https://www.mnrepeaters.org/010902/bandplans/"
MRC_PAGES = {
    "6 m": "6meterbandplan.htm", "2 m": "2meterbandplan.htm",
    "1.25 m": "220bandplan.htm", "70 cm": "440bandplan.htm",
    "23 cm": "1200bandplan.htm",
}


def _fetch_mrc():
    import logging
    log = logging.getLogger("elmer")
    out = {}
    for band, page in MRC_PAGES.items():
        try:
            segments = _parse_plan(_text(MRC_BASE + page))
        except Exception as exc:
            # Log it: a bare continue here once hid a NameError and quietly
            # served a stale cache as though the fetch had worked.
            log.warning("MRC %s plan failed: %s: %s", band,
                        type(exc).__name__, exc)
            continue
        if segments:
            out[band] = segments
    return out


COORDINATORS = {
    "MN": {
        "state": "MN", "state_name": "Minnesota",
        "name": "Minnesota Repeater Council", "short": "MRC",
        "url": "https://www.mnrepeaters.org/",
        "plans_url": "https://www.mnrepeaters.org/plans.html",
        "fetch": _fetch_mrc,
        "note": "Coordinated VHF and UHF segments. The 900 MHz plan is "
                "published only as a PDF and is not parsed here.",
    },
}


def available():
    return [{k: v for k, v in c.items() if k != "fetch"}
            for c in COORDINATORS.values()]


def plan(state, refresh=False):
    """The coordinator's band plan for a state, cached. None if unavailable."""
    state = (state or "").upper()
    entry = COORDINATORS.get(state)
    if not entry:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{state}.json"
    if path.is_file() and not refresh:
        try:
            cached = json.loads(path.read_text())
            age = (time.time() - path.stat().st_mtime) / 86400
            if age < MAX_AGE_DAYS:
                cached["cached"] = True
                cached["age_days"] = round(age, 1)
                return cached
        except ValueError:
            pass

    bands = entry["fetch"]()
    if not bands:
        if path.is_file():                       # stale beats nothing
            try:
                stale = json.loads(path.read_text())
                stale["cached"] = True
                stale["stale"] = True
                return stale
            except ValueError:
                pass
        return None

    data = {k: v for k, v in entry.items() if k != "fetch"}
    data.update({"bands": bands, "fetched": time.strftime("%Y-%m-%d"),
                 "cached": False,
                 "segments": sum(len(v) for v in bands.values())})
    path.write_text(json.dumps(data, indent=1))
    return data

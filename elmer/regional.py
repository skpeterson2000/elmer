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


# --- who coordinates where ---------------------------------------------------
#
# Forty-five organisations cover the fifty states, and not one per state: SERA
# alone covers eight, T-MARC five, NESMC four, and California is carved up five
# ways by band and region. So the table is by organisation with the states it
# covers, not the other way round.
#
# Naming somebody's coordinator and parsing their plan are two different jobs
# and only the first is cheap. There is no registry, no API and no common
# format - a third publish HTML, a third PDF, and the rest sit behind a login
# or a query form. So every state gets a name and a link, which is most of what
# an operator wants, and `fetch` is filled in one at a time for the ones whose
# pages can actually be read. An entry without one is not a gap in the data; it
# is an honest "here is who to ask".
#
# The directory itself rots: the list this was built from still had Wisconsin's
# council, which has dissolved and handed over to another body. Links are worth
# checking occasionally, and a stale link is a far smaller failure than a stale
# band plan presented as current.

COORDINATORS = [
    {"short": "AARR", "name": "Alaska Amateur Radio Repeaters",
     "states": ["AK"], "url": "https://alaskarepeaters.kl7.net/"},
    {"short": "ARC", "name": "Alabama Repeater Council",
     "states": ["AL"], "url": "https://alabamarepeatercouncil.org/"},
    {"short": "AROFCC", "name": "Arizona Repeater Owners Frequency Coordination Committee",
     "states": ["AZ"], "url": "https://azfreqcoord.org/"},
    {"short": "ARC-AR", "name": "Arkansas Repeater Council",
     "states": ["AR"], "url": "https://arkansasrepeatercouncil.org/"},
    {"short": "NARCC", "name": "Northern Amateur Relay Council of California",
     "states": ["CA"], "url": "https://narcc.org/"},
    {"short": "NCDCC", "name": "Northern California Digital Coordination Council",
     "states": ["CA"], "url": "https://ncdcc.net/"},
    {"short": "SCRRBA", "name": "Southern California Repeater and Remote Base Association",
     "states": ["CA"], "url": "https://scrrba.org/"},
    {"short": "TASMA", "name": "Two-Meter Area Spectrum Management Association",
     "states": ["CA"], "url": "https://tasma.org/"},
    {"short": "220SMA", "name": "220 MHz Spectrum Management Association",
     "states": ["CA"], "url": "https://220sma.org/"},
    {"short": "CCARC", "name": "Colorado Council of Amateur Radio Clubs",
     "states": ["CO"], "url": "https://ccarc.net/",
     "plans_url": "https://ccarc.net/frequency-use-plans/",
     "note": "Plans are served from a query form rather than a page, so they "
             "are not read here."},
    {"short": "CSMA", "name": "Connecticut Spectrum Management Association",
     "states": ["CT"], "url": "https://ctspectrum.com/"},
    {"short": "T-MARC", "name": "The Mid-Atlantic Repeater Council",
     "states": ["DE", "DC", "MD", "VA", "WV"], "url": "https://tmarc.org/"},
    {"short": "FASMA", "name": "Florida Amateur Spectrum Management Association",
     "states": ["FL"], "url": "https://fasma.org/"},
    {"short": "SERA", "name": "Southeastern Repeater Association",
     "states": ["GA", "KY", "MS", "NC", "SC", "TN", "VA", "WV"],
     "url": "https://www.sera.org/",
     "note": "Publishes a separate PDF per band, which is not parsed here."},
    {"short": "HARRC", "name": "Hawaii Amateur Radio Repeater Coordination",
     "states": ["HI"], "url": "https://hawaiirepeaters.net/"},
    {"short": "ID", "name": "Idaho Repeater Coordination",
     "states": ["ID"], "url": "https://idahoarrl.info/"},
    {"short": "ILRA", "name": "Illinois Repeater Association",
     "states": ["IL"], "url": "https://ilra.net/"},
    {"short": "IRC", "name": "Indiana Repeater Council",
     "states": ["IN"], "url": "https://ircinc.org/"},
    {"short": "IRC-IA", "name": "Iowa Repeater Council",
     "states": ["IA"], "url": "https://iowarepeater.org/"},
    {"short": "KARC", "name": "Kansas Amateur Repeater Council",
     "states": ["KS"], "url": "https://ksrepeater.com/"},
    {"short": "LCARC", "name": "Louisiana Council of Amateur Radio Clubs",
     "states": ["LA"], "url": "https://lacouncil.net/"},
    {"short": "NESMC", "name": "New England Spectrum Management Council",
     "states": ["ME", "MA", "NH", "RI"], "url": "https://nesmc.org/"},
    {"short": "MARC", "name": "Michigan Area Repeater Council",
     "states": ["MI"], "url": "https://miarc.com/"},
    {"short": "UPARRA", "name": "Upper Peninsula Amateur Radio Repeater Association",
     "states": ["MI"], "url": "https://uparra.org/"},
    {"short": "MRC", "name": "Minnesota Repeater Council",
     "states": ["MN"], "url": "https://www.mnrepeaters.org/",
     "plans_url": "https://www.mnrepeaters.org/plans.html",
     "fetch": "_fetch_mrc",
     "note": "Coordinated VHF and UHF segments. The 900 MHz plan is "
             "published only as a PDF and is not parsed here."},
    {"short": "MRC-MO", "name": "Missouri Repeater Council",
     "states": ["MO"], "url": "https://www.missourirepeater.org/"},
    {"short": "MT", "name": "Montana frequency coordinator",
     "states": ["MT"], "url": "https://www.arrl.org/frequency-coordinators",
     "note": "Coordinated by an individual rather than a society; contact "
             "details are on the ARRL list."},
    {"short": "NE", "name": "Nebraska Frequency Coordination",
     "states": ["NE"], "url": "https://nebraska-repeaters.us/"},
    {"short": "CARCON", "name": "Combined Amateur Radio Relay Council of Nevada",
     "states": ["NV"], "url": "https://carcon.org/"},
    {"short": "SNRC", "name": "Southern Nevada Repeater Council",
     "states": ["NV"], "url": "https://snrc.us/"},
    {"short": "ARCC", "name": "Area Repeater Coordination Council",
     "states": ["NJ", "PA"], "url": "https://www.arcc-inc.org/"},
    {"short": "METROCOR", "name": "Metropolitan Coordination Association",
     "states": ["NJ", "NY"], "url": "https://metrocor.net/"},
    {"short": "NMFCC", "name": "New Mexico Amateur Radio Frequency Coordination Committee",
     "states": ["NM"], "url": "https://www.qsl.net/nmfcc/"},
    {"short": "UNYREPCO", "name": "Upper New York Repeater Council",
     "states": ["NY"], "url": "https://unyrepco.org/"},
    {"short": "WNYSORC", "name": "Western New York and Southern Ontario Repeater Council",
     "states": ["NY"], "url": "https://wnysorc.net/"},
    {"short": "ND", "name": "North Dakota frequency coordinator",
     "states": ["ND"], "url": "https://www.arrl.org/frequency-coordinators",
     "note": "Coordinated by an individual rather than a society; contact "
             "details are on the ARRL list."},
    {"short": "OARC", "name": "Ohio Area Repeater Council",
     "states": ["OH"], "url": "https://www.oarc.com/"},
    {"short": "ORS", "name": "Oklahoma Repeater Society",
     "states": ["OK"], "url": "https://oklahomarepeatersociety.org/"},
    {"short": "ORRC", "name": "Oregon Region Relay Council",
     "states": ["OR", "WA"], "url": "https://orrc.org/"},
    {"short": "WPRC", "name": "Western Pennsylvania Repeater Council",
     "states": ["PA"], "url": "https://wprcinfo.org/"},
    {"short": "PRVI-VFC", "name": "Puerto Rico and Virgin Islands Volunteer Frequency Coordinator",
     "states": ["PR", "VI"], "url": "https://prvi-vfc.org/"},
    {"short": "SD", "name": "South Dakota frequency coordinator",
     "states": ["SD"], "url": "https://www.arrl.org/frequency-coordinators",
     "note": "Coordinated by an individual rather than a society; contact "
             "details are on the ARRL list."},
    {"short": "TXVHFFM", "name": "Texas VHF-FM Society",
     "states": ["TX"], "url": "https://www.txvhffm.org/",
     "plans_url": "https://www.txvhffm.org/coordination/bandplan.php",
     "fetch": "_fetch_txvhffm",
     "note": "One page carrying 6 m, 2 m, 70 cm, 33 cm and 23 cm. There is no "
             "1.25 m plan published here."},
    {"short": "UVHFS", "name": "Utah VHF Society",
     "states": ["UT"], "url": "https://utahvhfs.org/"},
    {"short": "VIRCC", "name": "Vermont Independent Repeater Coordinating Committee",
     "states": ["VT"], "url": "https://www.ranv.org/"},
    {"short": "WI-RA", "name": "Wisconsin Repeater Alliance",
     "states": ["WI"], "url": "https://wi-ra.org/",
     "note": "Took over from the Wisconsin Association of Repeaters, which "
             "dissolved - older directories still point at the old body."},
    {"short": "WRCG", "name": "Wyoming Repeater Coordinator Group",
     "states": ["WY"], "url": "https://wyoham.com/"},
    {"short": "IACC", "name": "Inland Amateur Coordination Council",
     "states": ["WA"], "url": "https://iacc.online/"},
    {"short": "WWARA", "name": "Western Washington Amateur Relay Association",
     "states": ["WA"], "url": "https://www.wwara.org/"},
]

# Name to postal code, so a reverse-geocoded QTH can pick its own coordinator
# instead of the operator hunting for it in a list of forty-five.
US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "district of columbia": "DC", "florida": "FL",
    "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY",
    "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "puerto rico": "PR", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virgin islands": "VI", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY",
}


def state_of(place):
    """The postal code for a reverse-geocoded place, or None.

    Nominatim hands back "Pequot Lakes, Crow Wing County, Minnesota, 56472,
    United States" and the state was being thrown away. Matched on the comma
    fields rather than by searching the whole string, so that Washington County
    in Minnesota does not come out as Washington the state.
    """
    text = place if isinstance(place, str) else (place or {}).get("name", "")
    for field in reversed([f.strip().lower() for f in str(text).split(",")]):
        # West Virginia before Virginia: the longer name is the real one.
        if field in US_STATES:
            return US_STATES[field]
    return None


def for_state(state):
    """Every coordinator covering a state, most specific first."""
    state = (state or "").upper()
    if not state:
        return []
    found = [c for c in COORDINATORS if state in c["states"]]
    return sorted(found, key=lambda c: len(c["states"]))


def readable(state):
    """The coordinator for a state whose plan can actually be read, if any."""
    return next((c for c in for_state(state) if c.get("fetch")), None)


def available():
    """Every coordinator, without the machinery."""
    return [{k: v for k, v in c.items() if k != "fetch"} for c in COORDINATORS]


def states():
    """Every state, with who coordinates it - which is how somebody picks.

    The selector used to be a list of organisations, which asks an operator to
    know that Georgia is SERA before they can find out that Georgia is SERA.
    They know their state; the coordinator is the answer, not the question.
    """
    # title() gives "District Of Columbia", which is not how it is written.
    proper = {"DC": "District of Columbia", "VI": "Virgin Islands"}
    by_code = {}
    for name, code in US_STATES.items():
        by_code[code] = proper.get(code, name.title())
    out = []
    for code in sorted(by_code):
        who = for_state(code)
        out.append({
            "state": code,
            "state_name": by_code[code],
            "coordinators": [c["short"] for c in who],
            "names": [c["name"] for c in who],
            "readable": any(c.get("fetch") for c in who),
        })
    return out


# The Texas VHF-FM Society puts every band on one page under its own heading,
# where Minnesota gives each band a page of its own. Same parser underneath -
# their rows are already the shape it reads, "144.100 - 144.275 Weak Signal
# SSB" - so this only has to find where each band starts and hand it the slice.
TXVHFFM_PLANS = "https://www.txvhffm.org/coordination/bandplan.php"
TX_HEADING = re.compile(r"^([A-Za-z0-9 ./-]{2,24}?)\s+Band\s+Plan$", re.I)
TX_BANDS = {
    "6 meter": "6 m",
    "148 mhz": "2 m",          # their name for it; the plan is 144-148
    "440 to 450 mhz": "70 cm",
    "900 mhz": "33 cm",
    "1200 mhz": "23 cm",
}


def _fetch_txvhffm():
    import logging
    log = logging.getLogger("elmer")
    try:
        rows = [" ".join(r.split()) for r in _text(TXVHFFM_PLANS, "utf-8").split("\n")]
    except Exception as exc:
        log.warning("Texas VHF-FM plan failed: %s: %s", type(exc).__name__, exc)
        return {}
    rows = [r for r in rows if r]

    out, band, chunk = {}, None, []

    def flush():
        if band and chunk:
            segments = _parse_plan("\n".join(chunk))
            if segments:
                out[band] = segments

    for row in rows:
        found = TX_HEADING.match(row)
        if found:
            flush()
            band, chunk = TX_BANDS.get(found.group(1).strip().lower()), []
            continue
        if band:
            chunk.append(row)
    flush()
    return out


FETCHERS = {"_fetch_mrc": _fetch_mrc, "_fetch_txvhffm": _fetch_txvhffm}


def plan(state, refresh=False):
    """The coordinator's band plan for a state, cached. None if unavailable."""
    state = (state or "").upper()
    entry = readable(state)
    if not entry:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    # Cached under the coordinator rather than the state, so an organisation
    # covering eight of them is fetched once and not eight times.
    path = CACHE / f"{entry['short']}.json"
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

    bands = FETCHERS[entry["fetch"]]()
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

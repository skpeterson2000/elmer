"""The NIFOG's nationwide interoperability channels, read from the guide itself.

The National Interoperability Field Operations Guide is a CISA publication and a
work of the US government, so its contents can be reproduced freely.  It is also
revised most years, which is the reason to read the current one rather than
transcribe a copy: a channel list typed out once is a channel list that goes
quietly stale, and somebody programs a radio from it.

So ELMER goes and gets it.  The current edition is found from CISA's own Field
Operations Guides page rather than from a filename remembered here, downloaded,
converted with the poppler tools ELMER already needs for the question pools, and
the channel tables are read out of it.

**Everything parsed here is checked before it is used.**  A wrong digit in a
frequency is not a cosmetic defect in a document somebody programs a radio from,
so a parse that fails its checks is discarded whole and the previous copy kept.
ELMER would rather show nothing, or show something a year old and say so, than
show a number it has not satisfied itself about.

None of these channels is amateur spectrum.  They are here to be known and
monitored, and because an operator supporting a served agency needs to speak the
same channel names as everybody else at the incident - not to be transmitted on
without the authorisation that an amateur licence does not confer.
"""
import json
import logging
import re
import subprocess
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "nifog" / "channels.json"

SAFECOM_PAGE = "https://www.cisa.gov/safecom/field-operations-guides"
NIFOG_PAGE = "https://www.cisa.gov/resources-tools/resources/nifog"

# CISA's CDN refuses curl's TLS fingerprint outright, whatever headers are set,
# but serves urllib perfectly happily with an ordinary browser User-Agent. Worth
# knowing before spending an afternoon on the headers.
UA = ("Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/151.0.0.0 Safari/537.36")
TIMEOUT = 90

# A channel row: assignment, name, then receive and transmit pairs. The tone
# column is a CTCSS frequency in the VHF/UHF tables and a hexadecimal P25
# network access code in the 700 MHz ones, so both shapes are allowed.
ROW = re.compile(r"""^\s*(?P<use>[A-Za-z][A-Za-z /()\-]*?)\s*[*•●]*\s+
                      (?P<name>[A-Z0-9]{4,10}D?)\s+
                      (?P<rx>\d{2,4}\.\d{3,5})\s+(?P<rx_tone>\$?[\w.]+)\s+
                      (?P<tx>\d{2,4}\.\d{3,5})\s+(?P<tx_tone>\$?[\w.]+)\s*$""",
                 re.X)

# Only the nationwide non-federal calling and tactical channels. The federal,
# medical and 25-Cities tables in the guide are for people operating under
# authorities an amateur does not hold, and printing them on an amateur's chart
# would invite exactly the mistake this file is careful about.
NAME = re.compile(r"^(?P<group>V|U|7|8)(?P<kind>CALL|TAC)(?P<number>\d{2})(?P<direct>D?)$")

# Where each group's channels must fall, in MHz. VTAC17 is the inland waterway
# channel and sits up in the marine band, which is why V reaches past 160.
GROUP_BANDS = {"V": (150.0, 163.0), "U": (450.0, 460.0),
               "7": (769.0, 806.0), "8": (806.0, 870.0)}
GROUP_LABELS = {"V": "VHF", "U": "UHF", "7": "700 MHz", "8": "800 MHz"}

# The four nationwide calling channels. If a parse cannot find all four it has
# not understood the document, whatever else it managed to collect.
REQUIRED = ("VCALL10", "UCALL40", "7CALL50", "8CALL90")
MIN_CHANNELS = 30


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def discover():
    """The current NIFOG PDF's URL, from CISA's own page listing it.

    Deliberately not a URL written down here: the file name carries the edition
    and changes with it, and a link that rots silently is worse than a lookup
    that fails loudly.
    """
    html = _get(SAFECOM_PAGE).decode("utf-8", "replace")
    links = re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.I)
    for link in links:
        name = link.rsplit("/", 1)[-1].lower()
        if "nifog" in name and "factsheet" not in name:
            return link if link.startswith("http") else "https://www.cisa.gov" + link
    raise LookupError(f"no NIFOG PDF linked from {SAFECOM_PAGE}")


def to_text(pdf_bytes):
    """The guide as laid-out text, via the poppler tools ELMER already uses."""
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "nifog.pdf"
        pdf.write_bytes(pdf_bytes)
        done = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                              capture_output=True, text=True, timeout=180)
    if done.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {done.stderr.strip()[:200]}")
    return done.stdout


def edition(text):
    """The version and date printed on the cover."""
    head = "\n".join(text.splitlines()[:40])
    version = re.search(r"Version\s+([\d.]+)", head)
    when = re.search(r"\b([A-Z]{3,9}\s+20\d\d)\b", head)
    return {"version": version.group(1) if version else None,
            "dated": when.group(1).title() if when else None}


def parse(text):
    """Every nationwide interoperability channel the guide lists."""
    channels, seen = [], set()
    for line in text.splitlines():
        match = ROW.match(line.rstrip())
        if not match:
            continue
        row = match.groupdict()
        named = NAME.match(row["name"])
        if not named or row["name"] in seen:
            continue
        seen.add(row["name"])
        group = named.group("group")
        channels.append({
            "name": row["name"],
            "group": group,
            "band": GROUP_LABELS[group],
            "kind": named.group("kind"),
            "number": int(named.group("number")),
            "use": " ".join(row["use"].split()),
            "direct": bool(named.group("direct")),
            "rx_mhz": float(row["rx"]),
            "rx_tone": row["rx_tone"],
            "tx_mhz": float(row["tx"]),
            "tx_tone": row["tx_tone"],
        })
    # Read in the order they are used, not by frequency: the calling channel
    # first, then the tactical channels in their numbered order, each followed
    # by its direct variant. That is how the guide prints them and how somebody
    # keys them into a radio.
    order = list(GROUP_LABELS)
    channels.sort(key=lambda c: (order.index(c["group"]), c["kind"] != "CALL",
                                 c["number"], c["direct"]))
    return channels


def problems(channels):
    """Everything wrong with a parse. Empty means it may be used."""
    found = []
    if len(channels) < MIN_CHANNELS:
        found.append(f"only {len(channels)} channels parsed, expected at least "
                     f"{MIN_CHANNELS}")
    names = [c["name"] for c in channels]
    if len(names) != len(set(names)):
        found.append("duplicate channel names")
    for required in REQUIRED:
        if required not in names:
            found.append(f"{required} is missing, so the tables were not understood")
    for channel in channels:
        low, high = GROUP_BANDS[channel["group"]]
        for side in ("rx", "tx"):
            mhz = channel[f"{side}_mhz"]
            if not low <= mhz <= high:
                found.append(f"{channel['name']} {side} {mhz} MHz is outside "
                             f"{low}-{high} MHz")
        if not channel["rx_tone"] or not channel["tx_tone"]:
            found.append(f"{channel['name']} is missing a tone or NAC")
    return found


def load():
    """The cached channels, or None. Never touches the network."""
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return None


def refresh():
    """Fetch, read and check the current guide. Returns the new cache entry.

    Raises rather than storing anything that failed its checks: a stale channel
    list that is known to be right beats a fresh one that might not be.
    """
    url = discover()
    log.info("nifog: fetching %s", url)
    text = to_text(_get(url))
    channels = parse(text)
    wrong = problems(channels)
    if wrong:
        raise ValueError("the NIFOG did not parse cleanly, so nothing was "
                         "changed: " + "; ".join(wrong[:4]))
    record = dict(edition(text), url=url, fetched=date.today().isoformat(),
                  channels=channels, count=len(channels))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(record, indent=1))
    log.info("nifog: %d channels from version %s (%s)", len(channels),
             record["version"], record["dated"])
    return record


def by_band(record=None):
    """The channels grouped for display, in band order."""
    record = record or load()
    if not record:
        return []
    groups = {}
    for channel in record["channels"]:
        groups.setdefault(channel["band"], []).append(channel)
    return [{"band": GROUP_LABELS[g], "channels": groups[GROUP_LABELS[g]]}
            for g in GROUP_LABELS if GROUP_LABELS[g] in groups]

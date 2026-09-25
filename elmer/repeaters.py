"""Repeaters near the station, for the bands where they are the answer.

Above 50 MHz "what can I reach" is a different question than it is on HF. A
2 m vertical at thirty feet reaches other antennas about fifteen miles away,
which around most stations names no towns at all - and ELMER used to say
exactly that and stop, having correctly observed that the repeater is doing the
reaching and then declining to say which repeater.

This is where the repeaters come from. RepeaterBook offers each of its users
a token of their own for programs like this one; an operator who pastes
theirs into the Station panel gets the amateur and GMRS machines for the
state their QTH is in fetched straight from RepeaterBook, under their own
account, and refreshed as the QTH moves. That is the first route, because it
is the one the service offers. TowerWitch, the station's own repeater tool,
already keeps a RepeaterBook export with coordinates on it; if it is
installed alongside, ELMER reads it rather than asking the operator to gather
the same list twice. `--import-repeaters` copies that list into ELMER's own
data so it keeps working on a Pi that has no TowerWitch on it. All three land
in the same list, told apart by nothing but a source name.

Two honesties are carried through to the screen. A coordinate matched only to
the county is marked approximate, because a bearing computed from a county
centroid is a direction to a county, not to a machine on a hill. And nothing
here says a repeater is reachable: it says where it is and how far. Terrain
decides the rest, and terrain is not in a CSV.
"""
import csv
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import bandplan, paths
from .terrain import great_circle

ROOT = Path(__file__).resolve().parents[1]
# Under the state directory, like everything the unit writes - so a test
# run against ELMER_STATE never touches the operator's own list.
STORE = paths.STATE / "repeaters.json"

# A repeater is on a tower or a hill; the operator is usually not. Assuming a
# couple of hundred feet for the far end is what makes the radius resemble the
# distance people actually work, rather than the antenna-to-antenna figure.
ASSUMED_TOWER_FT = 200.0

_cache = {"key": None, "rows": [], "source": None}
_asked = {"at": 0.0}          # when a network TowerWitch was last tried

# RepeaterBook's API (repeaterbook.com/wiki/doku.php?id=api). Access is by
# token, and in two steps. First the *program* is approved: its author
# applies at RB_APPLY, naming the User-Agent it will send, and RepeaterBook
# lists it as an app. Then a person signed in at RepeaterBook makes a token
# for that app on their own account page (RB_TOKENS) - bound to them and to
# the one app - and it goes out in a header with every request. Until the
# first step is done a token cannot be made for ELMER, and a request under
# any other name is refused as ua_mismatch; the User-Agent below is the one
# to give on the form, and it must not drift from it.
#
# The token is the operator's, kept in their own settings on this unit,
# sent to RepeaterBook and to nobody else, and never written to a log - a
# problem report carries the log. RepeaterBook asks for its data to be
# credited, and its terms draw a line ELMER stays behind: what is fetched
# is one state's list, kept on this unit for this operator's own use and
# asked for again a month later, never served on to anybody else and never
# bundled into a release. Their published "more likely approved" case is a
# private, non-commercial, narrowly scoped field tool, which is what this
# is; a public repeater search or a mirror is what it must not become.
RB_EXPORT = "https://www.repeaterbook.com/api/export.php"
RB_TOKENS = "https://www.repeaterbook.com/user/api_apps.php"
RB_APPLY = "https://www.repeaterbook.com/api/token_request.php"
RB_CREDIT = "Data courtesy of RepeaterBook.com"
RB_SOURCE = "RepeaterBook.com"
RB_TIMEOUT = 25.0
RB_FRESH_DAYS = 30            # a state's list is asked for again after this
RB_TOKEN_STARTS = ("rbuapp_", "app_")

# RepeaterBook names a state by its FIPS code, not its letters.
FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10",
    "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35",
    "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56", "AS": "60", "GU": "66", "MP": "69", "PR": "72", "VI": "78",
}


def horizon_km(height_ft, other_ft=ASSUMED_TOWER_FT):
    """Radio horizon between two antennas, 4/3 earth, in kilometers."""
    miles = 1.415 * (math.sqrt(max(float(height_ft), 1.0))
                     + math.sqrt(max(float(other_ft), 1.0)))
    return miles * 1.609


def find_towerwitch():
    """Where TowerWitch is, if it is anywhere obvious."""
    named = os.environ.get("ELMER_TOWERWITCH")
    candidates = [Path(named).expanduser()] if named else []
    candidates += [Path.home() / "TowerWitch", ROOT.parent / "TowerWitch"]
    for path in candidates:
        try:
            if (path / "data").is_dir() or (path / "radio_cache").is_dir():
                return path
        except OSError:
            continue
    return None


# TowerWitch writes where it last was into its own state file. On a unit where
# it is the program holding the GPS - or simply the one that has been running
# long enough to have got a lock - that file is a position ELMER can borrow
# rather than argue with.
#
# The timestamp in that file is when TowerWitch last *wrote* it, which is not
# the age of the position. A station on a bench that has not moved since
# Tuesday has a position from Tuesday that is exactly as correct as one from a
# minute ago; a station in a vehicle does not. Reliable-but-stationary and
# stale are different things, and a write time cannot tell them apart.
#
# So nothing is refused for being old. The age is reported and the operator
# judges, which is the same bargain the typed QTH makes. The only cutoff is an
# absurdity guard: a position from last month is not evidence about today, and
# by then the typed QTH is the better answer anyway.
STATE_MAX_AGE = 30 * 24 * 3600.0


def last_position(path=None):
    """Where TowerWitch last knew itself to be, with the age of that knowledge."""
    where = Path(path).expanduser() if path else find_towerwitch()
    if not where:
        return None
    try:
        state = json.loads((where / "towerwitch_state.json").read_text())
    except (OSError, ValueError):
        return None
    lat, lon = _num(state.get("last_lat")), _num(state.get("last_lon"))
    if lat is None or lon is None:
        return None
    age = None
    stamp = state.get("timestamp")
    if stamp:
        try:
            from datetime import datetime
            age = max(0.0, (datetime.now()
                            - datetime.fromisoformat(stamp)).total_seconds())
        except (TypeError, ValueError):
            age = None
    if age is not None and age > STATE_MAX_AGE:
        return None
    return {"lat": lat, "lon": lon, "town": state.get("nearest_town") or None,
            "age_s": age, "written": stamp, "from": str(where)}


# GMRS repeaters answer on exactly eight frequencies - 462.550 to 462.725
# in 25 kHz steps, the inputs 5 MHz up (47 CFR 95.1763) - so a machine's
# service is certain from its output alone, whatever wrote the row. It
# has to be: a GMRS machine read as a 70 cm amateur repeater would be
# offered to a Technician as one to key, which 95.335 and 95.1761 say an
# amateur transmitter may never do.
GMRS_OUTPUTS = {462.550, 462.575, 462.600, 462.625, 462.650, 462.675, 462.700, 462.725}


def service_of(output):
    """'gmrs' for a GMRS repeater output, else 'amateur'."""
    try:
        return "gmrs" if round(float(output), 3) in GMRS_OUTPUTS else "amateur"
    except (TypeError, ValueError):
        return "amateur"


def _band(mhz):
    if service_of(mhz) == "gmrs":
        return "GMRS"
    band = bandplan.band_at(mhz)
    if isinstance(band, dict):
        return band.get("name")
    return band


def _row(call, output, **kw):
    """One repeater, with the fields the screen needs and nothing else."""
    try:
        output = round(float(output), 4)
    except (TypeError, ValueError):
        return None
    if not call or not 28.0 <= output <= 1300.0:
        return None
    row = {"call": str(call).strip().upper(), "output": output,
           "input": None, "offset": None, "tone": None, "location": "",
           "county": "", "modes": "", "lat": None, "lon": None,
           "approx": False}
    row.update({k: v for k, v in kw.items() if k in row})
    row["band"] = _band(output)
    row["service"] = service_of(output)
    return row


def _num(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _town_key(location, county, state):
    """RepeaterBook writes a site, not a town: "Nisswa - WJJY Tower"."""
    town = str(location or "").split(" - ")[0].split(",")[0].strip().lower()
    return f"{town}|{str(county or '').strip().lower()}|{str(state or '').strip().lower()}", town


def place_table(path):
    """TowerWitch's town coordinates, which are better than a county centroid."""
    try:
        raw = json.loads((Path(path) / "data" / "location_coordinates.json").read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for key, value in raw.items() if isinstance(raw, dict) else []:
        lat, lon = _num((value or {}).get("lat")), _num((value or {}).get("lon"))
        if lat is not None and lon is not None:
            out[str(key).strip().lower()] = (lat, lon)
    return out


def _from_csv(path, places=None):
    """A RepeaterBook export, enriched with coordinates."""
    places = places or {}
    out = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for line in csv.DictReader(handle):
                lat, lon = _num(line.get("Latitude")), _num(line.get("Longitude"))
                if lat is None or lon is None:
                    continue          # no coordinate, no bearing, no entry
                tone = (line.get("Uplink Tone") or line.get("Downlink Tone") or "").strip()
                # A county centroid puts five machines in five different towns
                # at one identical bearing, which looks like precision and is
                # not. Where the town itself is known, use it and say so.
                county = (line.get("County") or "").strip()
                key, town = _town_key(line.get("Location"), county, line.get("State"))
                approx = "county" in (line.get("Match Method") or "").lower()
                if key in places and town and town != county.lower():
                    lat, lon = places[key]
                    approx = False
                row = _row(
                    line.get("Call"), line.get("Output Freq"),
                    input=_num(line.get("Input Freq")),
                    offset=_num(line.get("Offset")), tone=tone or None,
                    location=(line.get("Location") or "").strip(),
                    county=(line.get("County") or "").strip(),
                    modes=(line.get("Modes") or "").strip(),
                    lat=lat, lon=lon,
                    # Where a machine could only be placed by county, say so
                    # rather than implying a bearing to something we have not
                    # actually located.
                    approx=approx)
                if row:
                    out.append(row)
    except (OSError, csv.Error):
        return []
    return out


def _from_cache_json(path):
    """One of TowerWitch's cached lookups, which already carry coordinates."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out = []
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        row = _row(entry.get("call"),
                   entry.get("output") or entry.get("frequency"),
                   input=_num(entry.get("input")),
                   offset=_num(entry.get("offset")),
                   tone=entry.get("tone") or entry.get("pl_tone"),
                   location=(entry.get("location") or "").strip(),
                   lat=_num(entry.get("lat")), lon=_num(entry.get("lon")))
        if row and row["lat"] is not None and row["lon"] is not None:
            out.append(row)
    return out


def _dedupe(rows):
    """One entry per machine. Later sources win only where they say more."""
    best = {}
    for row in rows:
        key = (row["call"], round(row["output"], 3))
        was = best.get(key)
        if was is None or (was["approx"] and not row["approx"]):
            best[key] = row
    return sorted(best.values(), key=lambda r: (r["output"], r["call"]))


def from_towerwitch(path=None):
    """Every repeater TowerWitch knows where it is, with coordinates."""
    path = Path(path).expanduser() if path else find_towerwitch()
    if not path or not path.is_dir():
        return []
    rows = []
    places = place_table(path)
    data = path / "data"
    if data.is_dir():
        # Enriched exports first: they are the same rows with coordinates on.
        for csv_path in sorted(data.glob("*_enriched.csv")):
            rows += _from_csv(csv_path, places)
        for csv_path in sorted(data.glob("*.csv")):
            if not csv_path.name.endswith("_enriched.csv"):
                rows += _from_csv(csv_path, places)
    cache = path / "radio_cache"
    if cache.is_dir():
        for json_path in sorted(cache.glob("repeaters_*.json")):
            rows += _from_cache_json(json_path)
    return _dedupe(rows)


def _newest(path):
    """When TowerWitch last wrote anything, so a fresh lookup is noticed."""
    newest = 0.0
    for folder in ("data", "radio_cache"):
        here = path / folder
        if not here.is_dir():
            continue
        for entry in here.iterdir():
            try:
                newest = max(newest, entry.stat().st_mtime)
            except OSError:
                continue
    return newest


def _from_store():
    """The copy ELMER keeps, so it works with no TowerWitch on the machine."""
    if not STORE.is_file():
        return [], None
    try:
        payload = json.loads(STORE.read_text())
    except (OSError, ValueError):
        return [], None
    rows = [r for r in payload.get("repeaters", []) if r.get("lat") is not None]
    for row in rows:
        row.setdefault("band", _band(row["output"]))
    return rows, (payload.get("source") or "ELMER's own list")


def load():
    """Every repeater ELMER knows about, and where the list came from.

    Both sources, merged - not one or the other. Preferring the saved copy was
    wrong in exactly the case this exists for: drive to Montana, let TowerWitch
    look up what is around you, and ELMER would go on reciting the list it
    imported in Minnesota because a file existed. The saved copy is what makes
    a machine without TowerWitch work; TowerWitch is what makes anywhere work.
    """
    tw = find_towerwitch()
    key = (STORE.stat().st_mtime if STORE.is_file() else None,
           str(tw), _newest(tw) if tw else None)
    if _cache["key"] == key:
        return _cache["rows"], _cache["source"]

    stored, stored_from = _from_store()
    live = from_towerwitch(tw) if tw else []
    # TowerWitch last, so its entries win a tie: it is the one that can have
    # looked up where you are standing this afternoon.
    rows = _dedupe(stored + live)
    # The saved copy is usually an import of the very list beside it, so name
    # each source once rather than saying "TowerWitch and TowerWitch".
    named = list(dict.fromkeys(n for n in (stored_from if stored else None,
                                           f"TowerWitch ({tw})" if live else None)
                               if n))

    _cache.update({"key": key, "rows": rows, "source": " and ".join(named) or None})
    return rows, _cache["source"]


def save(rows, source, repeaterbook=None):
    """Keep a list of ELMER's own, so it works without TowerWitch there."""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    if repeaterbook is None:
        repeaterbook = _rb_log()
    STORE.write_text(json.dumps({
        "note": "Repeaters near this station, with coordinates. Imported "
                "rather than typed; entries marked approx were placed only to "
                "their county, so treat the bearing as a direction to the "
                "county rather than to the machine.",
        "source": source, "imported": time.time(),
        "credit": RB_CREDIT if RB_SOURCE in str(source or "") else None,
        "repeaterbook": repeaterbook,
        "repeaters": rows}, indent=1))
    _cache["key"] = None
    return len(rows)


def import_towerwitch(path=None):
    """Copy TowerWitch's repeater list into ELMER's own data."""
    where = Path(path).expanduser() if path else find_towerwitch()
    if not where:
        return False, ("no TowerWitch installation found - looked at "
                       "$ELMER_TOWERWITCH, ~/TowerWitch and next to ELMER"), 0
    rows = from_towerwitch(where)
    if not rows:
        return False, (f"found {where}, but nothing in it carried both a "
                       f"callsign and a coordinate"), 0
    return True, f"imported {save(rows, f'TowerWitch ({where})')} repeaters", len(rows)


def token_looks_right(token):
    """Whether a pasted token has the shape RepeaterBook hands out - a
    mistyped one is refused here, kindly, rather than by RepeaterBook."""
    token = (token or "").strip()
    return bool(token) and token.startswith(RB_TOKEN_STARTS) and len(token) > 12 and " " not in token


def rb_user_agent():
    """Who is asking: the program, its home and a way to reach the author.
    RepeaterBook refuses a generic one. The operator's own address is not
    in it - the token already says whose account this is."""
    try:
        from .mail import CONTACT
    except Exception:
        CONTACT = "KC9SP@arrl.net"
    return f"ELMER/1.0 (+https://github.com/skpeterson2000/elmer; {CONTACT})"


def _field(entry, *names):
    """A field by any of its names, since the JSON keys are spelt as the
    site's column headings and those have moved before."""
    if not isinstance(entry, dict):
        return None
    want = {n.lower().replace(" ", "").replace("_", "") for n in names}
    for key, value in entry.items():
        if str(key).lower().replace(" ", "").replace("_", "") in want:
            return value
    return None


def _yes(value):
    return str(value or "").strip().lower() in ("yes", "y", "1", "true")


def _rows_from_rb(payload):
    """RepeaterBook's export, as rows of ELMER's own shape."""
    results = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(results, list):
        return []
    out = []
    for entry in results:
        status = str(_field(entry, "Operational Status") or "").strip().lower()
        if status.startswith("off"):
            continue                       # an off-air machine is not a way to reach anybody
        lat, lon = _num(_field(entry, "Lat", "Latitude")), _num(_field(entry, "Long", "Lon", "Longitude"))
        if lat is None or lon is None:
            continue
        tone = str(_field(entry, "PL", "Uplink Tone") or "").strip() or None
        digital = [name for name, keys in (("DMR", ("DMR",)), ("D-STAR", ("D-Star", "DStar")),
                                           ("YSF", ("System Fusion", "YSF")), ("P25", ("APCO P-25", "P25")),
                                           ("NXDN", ("NXDN",)), ("M17", ("M17",)))
                   if _yes(_field(entry, *keys))]
        modes = ", ".join((["FM"] if _yes(_field(entry, "FM Analog")) or not digital else []) + digital)
        town = str(_field(entry, "Nearest City", "City", "Location") or "").strip()
        landmark = str(_field(entry, "Landmark") or "").strip()
        precise = _field(entry, "Precise")
        row = _row(_field(entry, "Callsign", "Call"), _field(entry, "Frequency", "Output Freq"),
                   input=_num(_field(entry, "Input Freq", "Input")),
                   tone=tone, location=(f"{town} - {landmark}" if town and landmark else town or landmark),
                   county=str(_field(entry, "County") or "").strip(), modes=modes, lat=lat, lon=lon,
                   approx=(precise is not None and not _yes(precise)))
        if row and row["input"] and row["output"]:
            row["offset"] = round(row["input"] - row["output"], 4)
        if row:
            out.append(row)
    return out


def from_repeaterbook(state, token, service="amateur"):
    """One state's machines from RepeaterBook, under the operator's own
    token. Returns (rows, error) - the error a plain sentence for the
    Station panel, or None."""
    fips = FIPS.get((state or "").upper())
    if not fips:
        return [], f"RepeaterBook lists US states by number and {state or 'this place'} is not one it knows"
    if not token_looks_right(token):
        return [], "that does not look like a RepeaterBook token - they begin rbuapp_"
    query = {"state_id": fips}
    if service == "gmrs":
        query["stype"] = "gmrs"
    request = urllib.request.Request(
        RB_EXPORT + "?" + urllib.parse.urlencode(query),
        headers={"User-Agent": rb_user_agent(), "X-RB-App-Token": token.strip(),
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=RB_TIMEOUT) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # The refusal is a JSON sentence with a code in it; read it, since
        # "the token is wrong" and "ELMER is not listed" are different errands.
        try:
            payload = json.loads(exc.read())
        except Exception:
            payload = None
        if isinstance(payload, dict) and payload.get("error_code"):
            return [], _rb_refusal(payload)
        if exc.code in (401, 403):
            return [], RB_REFUSALS["auth_invalid"]
        if exc.code == 429:
            return [], RB_REFUSALS["rate_limited"]      # and nothing tries again by itself
        return [], f"RepeaterBook answered {exc.code}"
    except Exception as exc:
        return [], f"RepeaterBook could not be reached ({exc.__class__.__name__})"
    if isinstance(payload, dict) and payload.get("ok") is False:
        return [], _rb_refusal(payload)
    return _rows_from_rb(payload), None


# RepeaterBook's refusals, each in a sentence that says whose move it is.
RB_REFUSALS = {
    "auth_missing": "RepeaterBook wanted a token and did not see one",
    "auth_invalid": "RepeaterBook did not accept the token - check it on your RepeaterBook account page",
    "auth_inactive": "RepeaterBook says that token, or ELMER's listing there, is not active",
    "auth_revoked": "RepeaterBook says access under that token has been revoked",
    "auth_scope_denied": "RepeaterBook says that token is not allowed this export",
    "ua_mismatch": "RepeaterBook does not know this build of ELMER by the name it gave - "
                   "its listing there needs updating, which is the author's to do",
    "rate_limited": "RepeaterBook asked us to slow down; try again later",
}


def _rb_refusal(payload):
    code = str(payload.get("error_code") or payload.get("error") or "refused")
    said = RB_REFUSALS.get(code)
    if said:
        return said
    if code.startswith("auth"):
        return RB_REFUSALS["auth_invalid"]
    return f"RepeaterBook refused: {code}"


def _rb_log():
    """When each state was last fetched, kept in the store."""
    if not STORE.is_file():
        return {}
    try:
        return dict(json.loads(STORE.read_text()).get("repeaterbook") or {})
    except (OSError, ValueError):
        return {}


def rb_fresh(state):
    """Whether this state's list was fetched recently enough to leave be."""
    at = _rb_log().get((state or "").upper())
    return bool(at) and time.time() - float(at) < RB_FRESH_DAYS * 86400


def fetch_repeaterbook(state, token, force=False):
    """Amateur and GMRS machines for a state, from RepeaterBook, into
    ELMER's own list. Returns (ok, message, count). Nothing is fetched
    twice in a month unless asked, so a QTH that moves within the state
    costs RepeaterBook nothing."""
    state = (state or "").upper()
    if not force and rb_fresh(state):
        return True, f"RepeaterBook's list for {state} is under a month old", 0
    fetched = []
    for service in ("amateur", "gmrs"):
        rows, error = from_repeaterbook(state, token, service)
        if error and service == "amateur":
            return False, error, 0
        fetched += rows
    if not fetched:
        return False, f"RepeaterBook returned nothing for {state}", 0
    stored, stored_from = _from_store()
    # RepeaterBook's own rows replace what an older export said about the
    # same machine: they are the same data, newer, and placed precisely.
    keep = {(r["call"], round(r["output"], 3)) for r in fetched}
    rows = _dedupe([r for r in stored if (r["call"], round(r["output"], 3)) not in keep] + fetched)
    names = [n for n in str(stored_from or "").split(" and ") if n and RB_SOURCE not in n]
    source = " and ".join(dict.fromkeys(names + [RB_SOURCE]))
    fetched_log = _rb_log()
    fetched_log[state] = time.time()
    save(rows, source, repeaterbook=fetched_log)
    gmrs = sum(1 for r in fetched if r["service"] == "gmrs")
    log_line = f"{len(fetched) - gmrs} amateur and {gmrs} GMRS repeaters for {state} from RepeaterBook"
    return True, log_line, len(fetched)


# Anything further than this is not "near here" by any reading, so a list
# whose closest entry is beyond it is a list about somewhere else.
COVERED_KM = 120.0
SERVICE_TIMEOUT = 3.0
SERVICE_ASK_EVERY = 180.0   # seconds between attempts at an absent service


def service_url(conn=None):
    """A TowerWitch that answers over the network, if one has been named."""
    where = None
    if conn is not None:
        try:
            from . import db
            where = db.unit_get(conn, "towerwitch_url")
        except Exception:
            where = None
    return (where or os.environ.get("ELMER_TOWERWITCH_URL") or "").strip() or None


def from_service(url, lat, lon, radius_km=100):
    """Ask a TowerWitch on another machine what is around this position.

    The reply is the same shape TowerWitch already writes into radio_cache -
    an object with a `data` list, or a bare list - so the endpoint can return
    its cache payload unchanged. A machine that is off, busy or not listening
    is not an error: the answer is then whatever is already on disk.
    """
    if not url:
        return []
    query = urllib.parse.urlencode({"lat": f"{lat:.5f}", "lon": f"{lon:.5f}",
                                    "radius_km": int(radius_km)})
    joiner = "&" if "?" in url else "?"
    request = urllib.request.Request(
        url + joiner + query,
        headers={"User-Agent": "ELMER/1.0 (personal amateur radio study tool)"})
    try:
        with urllib.request.urlopen(request, timeout=SERVICE_TIMEOUT) as response:
            payload = json.loads(response.read())
    except Exception:
        return []
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out = []
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        row = _row(entry.get("call"), entry.get("output") or entry.get("frequency"),
                   input=_num(entry.get("input")), offset=_num(entry.get("offset")),
                   tone=entry.get("tone") or entry.get("pl_tone"),
                   location=(entry.get("location") or "").strip(),
                   lat=_num(entry.get("lat")), lon=_num(entry.get("lon")))
        if row and row["lat"] is not None:
            out.append(row)
    return out


# What a distance means for a GMRS radio, in the one term that decides it.
# At 462 MHz the radio horizon is the reach: a handheld at head height sees
# a 200-ft tower some twenty-three miles off, an antenna at twenty feet -
# a roof, a mast, the top of a mobile whip on a truck - a few miles more.
# Power buys margin inside that, not distance past it; the words say so.
HANDHELD_FT = 6.0
ROOF_FT = 20.0


def reach_words(km):
    """A distance to a GMRS repeater, as what it takes to reach it."""
    if km <= horizon_km(HANDHELD_FT):
        return "inside a handheld's radio horizon"
    if km <= horizon_km(ROOF_FT):
        return "past a handheld's horizon; an antenna at twenty feet - a roof, a mast - brings it in"
    return "beyond line of sight from here - the ground between decides, and 50 W does not move the horizon"


def coverage(lat, lon):
    """Whether ELMER knows anything about repeaters *here*, as opposed to
    knowing a great deal about somewhere it used to be.

    An empty list means two very different things - there is nothing on the
    air near you, or nobody has ever looked here - and telling an operator the
    first when the truth is the second is how a program loses their trust.
    """
    rows, source = load()
    if not rows:
        return {"known": False, "nearest_km": None, "reason": "none",
                "source": None}
    nearest = min(great_circle(lat, lon, r["lat"], r["lon"])[0] for r in rows)
    return {"known": nearest <= COVERED_KM, "nearest_km": round(nearest),
            "reason": "here" if nearest <= COVERED_KM else "elsewhere",
            "source": source}


def nearby(lat, lon, mhz=None, radius_km=None, height_ft=30.0, limit=8,
           conn=None, service="amateur"):
    """The repeaters within reach of here, nearest first.

    `mhz` restricts the answer to the band being worked: somebody setting up
    for 2 m is not helped by a list of 70 cm machines. `service` keeps the
    amateur machines and the GMRS ones apart - an amateur radio may not
    key a GMRS repeater and a GMRS radio cannot reach an amateur one - and
    None asks for both.
    """
    rows, source = load()
    # Nothing known about here? Ask a TowerWitch on the network, if one has
    # been named - once every few minutes at most, so a machine that is off
    # costs a timeout occasionally rather than on every panel of every page.
    url = service_url(conn)
    if url and time.time() - _asked["at"] > SERVICE_ASK_EVERY:
        here = coverage(lat, lon)
        if not here["known"]:
            _asked["at"] = time.time()
            fetched = from_service(url, lat, lon)
            if fetched:
                merged = _dedupe(rows + fetched)
                save(merged, (source + " and " if source else "")
                     + f"TowerWitch at {url}")
                rows, source = load()
    if not rows:
        return [], None
    if radius_km is None:
        radius_km = horizon_km(height_ft)
    want = _band(mhz) if mhz else None

    out = []
    for row in rows:
        if want and row.get("band") != want:
            continue
        if service and (row.get("service") or service_of(row.get("output"))) != service:
            continue
        km, bearing = great_circle(lat, lon, row["lat"], row["lon"])
        if km > radius_km:
            continue
        entry = dict(row)
        entry["km"] = round(km, 1)
        entry["miles"] = round(km * 0.6214)
        entry["bearing"] = round(bearing)
        entry["where"] = (row.get("location")
                          or (f"{row['county']} County" if row.get("county") else ""))
        out.append(entry)
    out.sort(key=lambda r: r["km"])
    return out[:limit], source

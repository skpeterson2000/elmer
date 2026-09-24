"""Look up a US amateur license so ELMER can use the real one.

Source is callook.info, which serves the FCC ULS record without a key. Only
the parts ELMER actually needs are kept - class, the grant and expiry dates,
and the grid square. The name and street address that the lookup also returns
are public FCC record, but there is no reason for this app to store them, so it
does not.

The FCC's own files come first - see uls.py. The Commission's lookup API
is gone, but it publishes the whole licence database weekly, and a unit
that has read the file for a service answers that service's callsigns from
the FCC's record with no network at all: amateur, GMRS and the commercial
operator licences alike. callook is what answers an amateur call until the
amateur file - two hundred megabytes - has been fetched and read, and
where it cannot be. The same policy on what is kept either way: the
callsign, the class and the dates, the town for placing a far station,
never the name and the street.

A license runs ten years and then has a two-year grace period, during which it
is expired and may not be used but can still be renewed without re-testing.
That is the same shape as the rank decay in :mod:`elmer.ranks`, which is not a
coincidence - the ranks were modelled on it.
"""
import json
import re
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from . import paths, uls

ROOT = Path(__file__).resolve().parents[1]
CACHE = paths.STATE / "callsign"
API = "https://callook.info/{call}/json"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
MAX_AGE_DAYS = 7
GRACE_DAYS = 730                     # two years, per 47 CFR 97.21(b)

RE_CALL = re.compile(r"^[A-Z0-9]{3,10}$")
# Where a licence is renewed: the ULS licence manager, signed in by FRN.
RENEW_URL = "https://wireless2.fcc.gov/UlsEntry/licManager/login.jsp"
# callook reports the class as a single letter.
CLASS_NAMES = {
    "N": "Novice", "T": "Technician", "G": "General",
    "A": "Advanced", "E": "Extra",
    "NOVICE": "Novice", "TECHNICIAN": "Technician", "GENERAL": "General",
    "ADVANCED": "Advanced", "EXTRA": "Extra", "AMATEUR EXTRA": "Extra",
}


# Where a class claim rests. The FCC's record is the one anybody can check;
# anything else is the operator's own word. Both are allowed - callook serves
# the ULS and nothing else, so a Canadian or a British operator holds a
# perfectly good licence that resolves to nothing here, and an upgrade granted
# this week is not in the published file yet - but the two must never be
# mistaken for each other on a screen.
FCC = "fcc"
OWN = "own"
SOURCE = "license_class_source"


def held(settings):
    """The licence class this station holds, and whose word that rests on.

    One answer, for the whole program. Everything that asks what class this
    operator holds asks here: the pool gate, the band plan, the class pickers
    at a table, the printed chart. They used to ask in two different orders -
    the gate took the typed setting first and the print path took the record
    first - which meant a value left in the profile by something else could
    outrank the FCC and open pools that the record did not.

    The record decides wherever there is one. It is read on lookup, stored
    with the licence, and carried to every screen that offers a class, so
    nobody is asked to tell ELMER something the Commission already published.

    An operator may still answer for themselves, and that answer is kept and
    used - but it is marked as theirs, `SOURCE` set to `OWN`, and a screen
    showing the class says which of the two it is looking at. What an own
    answer cannot do is put a claim on paper: see the print path, which asks
    for `record` and falls back to the class only when there is no record.

    Returns {"class", "source", "record", "verified"}.
    """
    settings = settings or {}
    record = settings.get("license") or {}
    record_class = ""
    if record.get("found"):
        record_class = str(record.get("licence_class")
                           or record.get("license_class") or "")
    own = str(settings.get("license_class") or "")
    same = (own.strip().title() == record_class.strip().title())
    if record_class and (not own or same or settings.get(SOURCE) != OWN):
        return {"class": record_class, "source": FCC, "record": record_class,
                "verified": True}
    if own:
        return {"class": own, "source": OWN, "record": record_class,
                "verified": False}
    return {"class": "", "source": "", "record": record_class, "verified": False}


def normalise(call):
    return re.sub(r"[^A-Za-z0-9]", "", call or "").upper()


def _parse_date(text):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def status_for(expiry, grace_days=GRACE_DAYS):
    """Where a license sits: current, grace, or expired past renewal. A
    GMRS licence has no grace period - past the date it is simply gone."""
    if not expiry:
        return {"state": "unknown", "days": None}
    today = date.today()
    days = (expiry - today).days
    if days >= 0:
        # No grace means no date to name: GMRS would otherwise report a
        # "grace_ends" equal to its own expiry, which reads like a grace
        # period to anybody who meets it later.
        out = {"state": "current", "days": days}
        if grace_days:
            out["grace_ends"] = (expiry + timedelta(days=grace_days)).isoformat()
        return out
    if grace_days and -days <= grace_days:
        return {"state": "grace", "days": days,
                "renew_within": grace_days + days,
                "grace_ends": (expiry + timedelta(days=grace_days)).isoformat()}
    return {"state": "expired", "days": days}


def refresh_status(record):
    """A licence record with its status worked out as of today.

    The record is kept with the profile and a licence term runs for years -
    ten, for GMRS - so the day count written into it goes stale the moment
    it is stored. The amateur record was already being recomputed on its way
    to the page and the others were not, which is how a GMRS licence
    thirty-five days from expiry went on reporting four hundred days and
    never tripped the renew-soon warning the band plan draws.

    Each service keeps its own grace: two years for amateur under 47 CFR
    97.21(b), none at all for GMRS, where past the date the licence is
    simply gone. A lifetime permit has no expiry and is handed back as it
    is, and so is a record that was never found.
    """
    if not record or not record.get("found"):
        return record
    if (record.get("status") or {}).get("lifetime") or not record.get("expires"):
        return record
    # callook answers for amateur calls only, and its records carry no
    # service, so the absent case is the amateur one.
    service = (record.get("service") or "amateur").lower()
    grace = (uls.SERVICES.get(service) or {}).get("grace_days", GRACE_DAYS)
    return dict(record, status=status_for(_parse_date(record["expires"]), grace))


def is_gmrs(call):
    return uls.service_of(normalise(call)) == "gmrs"


def lookup(call, refresh=False):
    """Return the license, or None. Never raises on a network failure.

    The FCC's own file answers where the unit has read it; that is every
    GMRS and commercial call, and an amateur call once the amateur file is
    here. callook fills in for amateur calls until then.
    """
    call = normalise(call)
    if not RE_CALL.match(call):
        return None
    service = uls.service_of(call)
    if service in ("gmrs", "commercial"):
        return uls.lookup(call)
    if service == "amateur" and uls.have("amateur"):
        return uls.lookup(call)
    if service == "amateur":
        uls.ensure("amateur")            # start it; callook answers meanwhile
    return _lookup_callook(call, refresh)


def _fetch(call):
    request = urllib.request.Request(API.format(call=call),
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def _lookup_callook(call, refresh=False):

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{call}.json"
    if path.is_file() and not refresh:
        try:
            cached = json.loads(path.read_text())
            if (time.time() - path.stat().st_mtime) / 86400 < MAX_AGE_DAYS:
                cached["cached"] = True
                # Dates age even when the record does not.
                cached["status"] = status_for(_parse_date(cached.get("expires")))
                return cached
        except ValueError:
            path.unlink(missing_ok=True)

    try:
        raw = _fetch(call)
    except Exception:
        if path.is_file():
            try:
                stale = json.loads(path.read_text())
                stale["cached"] = True
                stale["stale"] = True
                stale["status"] = status_for(_parse_date(stale.get("expires")))
                return stale
            except ValueError:
                pass
        return None

    if raw.get("status") != "VALID":
        return {"callsign": call, "found": False,
                "reason": "no current FCC record for this callsign"}

    other = raw.get("otherInfo") or {}
    current = raw.get("current") or {}
    location = raw.get("location") or {}
    expiry = _parse_date(other.get("expiryDate"))
    raw_class = (current.get("operClass") or "").strip().upper()

    record = {
        "callsign": current.get("callsign") or call,
        "found": True,
        "type": raw.get("type"),                       # PERSON or CLUB
        "license_class": CLASS_NAMES.get(raw_class),
        "class_code": raw_class or None,
        "granted": other.get("grantDate"),
        "expires": other.get("expiryDate"),
        "last_action": other.get("lastActionDate"),
        "frn": other.get("frn"),
        "uls_url": other.get("ulsUrl"),
        "grid": location.get("gridsquare") or None,
        "lat": float(location["latitude"]) if location.get("latitude") else None,
        "lon": float(location["longitude"]) if location.get("longitude") else None,
        "checked": date.today().isoformat(),
        "cached": False,
        "source": "callook.info (FCC ULS)",
    }
    record["status"] = status_for(expiry)
    path.write_text(json.dumps(record, indent=1))
    return record

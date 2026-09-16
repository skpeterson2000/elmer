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
        return {"state": "current", "days": days,
                "grace_ends": (expiry + timedelta(days=grace_days)).isoformat()}
    if grace_days and -days <= grace_days:
        return {"state": "grace", "days": days,
                "renew_within": grace_days + days,
                "grace_ends": (expiry + timedelta(days=grace_days)).isoformat()}
    return {"state": "expired", "days": days}


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

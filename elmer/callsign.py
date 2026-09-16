"""Look up a US amateur license so ELMER can use the real one.

Source is callook.info, which serves the FCC ULS record without a key. Only
the parts ELMER actually needs are kept - class, the grant and expiry dates,
and the grid square. The name and street address that the lookup also returns
are public FCC record, but there is no reason for this app to store them, so it
does not.

A GMRS licence is looked up the same way from a different source. callook
holds only the amateur records, and the FCC's own lookup API went dark in
2025; gmrs.io keeps the ULS GMRS file, refreshed daily, behind the search
box on its front page, and answers that box in JSON. There is no published
API, so ELMER asks exactly as the page does, once per save, keeps the answer
a week, and names gmrs.io as the source. The same policy on what is kept:
the callsign and the dates, never the name and town the record carries.

A license runs ten years and then has a two-year grace period, during which it
is expired and may not be used but can still be renewed without re-testing.
That is the same shape as the rank decay in :mod:`elmer.ranks`, which is not a
coincidence - the ranks were modelled on it.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from . import paths

ROOT = Path(__file__).resolve().parents[1]
CACHE = paths.STATE / "callsign"
API = "https://callook.info/{call}/json"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
MAX_AGE_DAYS = 7
GRACE_DAYS = 730                     # two years, per 47 CFR 97.21(b)

RE_CALL = re.compile(r"^[A-Z0-9]{3,7}$")
# GMRS calls are four letters and three digits (WRMP909, WQXY123), or the
# older three letters and four digits (KAB1234) - shapes no amateur call
# has, so the service is certain from the call alone.
RE_GMRS = re.compile(r"^(W[QR][A-Z]{2}\d{3}|K[A-Z]{2}\d{4})$")
GMRS_API = "https://www.gmrs.io/search"
GMRS_SOURCE = "gmrs.io (FCC ULS, updated daily)"
GMRS_ULS = "https://wireless2.fcc.gov/UlsApp/UlsSearch/searchLicense.jsp"
GMRS_USER_AGENT = "ELMER/1.0 (+https://github.com/skpeterson2000/elmer; KC9SP@arrl.net)"
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
    return bool(RE_GMRS.match(normalise(call)))


def _fetch_gmrs(call):
    body = urllib.parse.urlencode({"action": "search", "q": call, "state": "",
                                   "expired": "1", "page": "1"}).encode()
    request = urllib.request.Request(GMRS_API, data=body,
                                     headers={"User-Agent": GMRS_USER_AGENT,
                                              "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def lookup_gmrs(call, refresh=False):
    """A GMRS licence by callsign, or None. Never raises on a network
    failure. Same cache and the same week as the amateur lookup."""
    call = normalise(call)
    if not is_gmrs(call):
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{call}.json"
    if path.is_file() and not refresh:
        try:
            cached = json.loads(path.read_text())
            if (time.time() - path.stat().st_mtime) / 86400 < MAX_AGE_DAYS:
                cached["cached"] = True
                cached["status"] = status_for(_parse_date(cached.get("expires")), 0)
                return cached
        except ValueError:
            path.unlink(missing_ok=True)
    try:
        raw = _fetch_gmrs(call)
    except Exception:
        if path.is_file():
            try:
                stale = json.loads(path.read_text())
                stale.update({"cached": True, "stale": True,
                              "status": status_for(_parse_date(stale.get("expires")), 0)})
                return stale
            except ValueError:
                pass
        return None
    rows = raw.get("results") if isinstance(raw, dict) else None
    hit = next((r for r in rows or [] if str(r.get("callsign", "")).upper() == call), None)
    if not hit:
        return {"callsign": call, "found": False, "service": "gmrs",
                "reason": "no FCC GMRS record for this callsign"}
    expiry = _parse_date(hit.get("expiration_date"))
    record = {
        "callsign": call, "found": True, "service": "gmrs", "type": "GMRS",
        "license_class": None,
        "granted": hit.get("grant_date"), "expires": hit.get("expiration_date"),
        "uls_url": GMRS_ULS,
        "checked": date.today().isoformat(), "cached": False,
        "source": GMRS_SOURCE,
    }
    record["status"] = status_for(expiry, 0)
    path.write_text(json.dumps(record, indent=1))
    return record


def _fetch(call):
    request = urllib.request.Request(API.format(call=call),
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def lookup(call, refresh=False):
    """Return the license, or None. Never raises on a network failure."""
    call = normalise(call)
    if not RE_CALL.match(call):
        return None
    if is_gmrs(call):
        return lookup_gmrs(call, refresh)

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

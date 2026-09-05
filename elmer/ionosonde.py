"""Live ionosonde measurements: how high the F2 layer actually is right now.

An ionosonde is a radar pointed straight up. It sweeps frequency, times the
echo, and reports two things that matter here: foF2, the highest frequency
that comes back at vertical incidence, and hmF2, the height of the F2 peak.
Those are measurements, not models - which is the only honest way to answer
"how do you know where the layer is".

Data comes from prop.kc2g.com, which aggregates the GIRO/Digisonde network.
Stations report on their own schedule and many go quiet, so anything older
than MAX_AGE_HOURS is treated as absent rather than shown as current.
"""
import json
import math
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "ionosonde"
API = "https://prop.kc2g.com/api/stations.json"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
CACHE_MINUTES = 15
MAX_AGE_HOURS = 3.0
EARTH_R = 6371.0

# Where the F2 peak usually sits, for the times there is no station in reach.
TYPICAL = {"day": 300.0, "night": 350.0, "low": 200.0, "high": 450.0}


def _number(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _fetch():
    request = urllib.request.Request(API, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read())


def _clean(rows, now):
    out = []
    for row in rows or []:
        station = row.get("station") or {}
        try:
            when = datetime.fromisoformat(str(row.get("time", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        age = (now - when).total_seconds() / 3600.0
        lat = _number(station.get("latitude"))
        lon = _number(station.get("longitude"))
        fof2 = _number(row.get("fof2"))
        hmf2 = _number(row.get("hmf2"))
        if None in (lat, lon, fof2, hmf2) or age < 0 or age > MAX_AGE_HOURS:
            continue
        if lon > 180:
            lon -= 360.0
        out.append({
            "name": station.get("name") or "unnamed",
            "lat": round(lat, 3), "lon": round(lon, 3),
            "fof2": round(fof2, 2), "hmf2": round(hmf2, 1),
            "mufd": _number(row.get("mufd")),
            "age_minutes": round(age * 60), "time": when.isoformat(),
        })
    return out


def stations(force=False):
    """Every station reporting recently, or None when unreachable."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "stations.json"
    now = datetime.now(timezone.utc)
    if path.is_file() and not force:
        age = (time.time() - path.stat().st_mtime) / 60.0
        if age < CACHE_MINUTES:
            try:
                return _clean(json.loads(path.read_text()), now)
            except ValueError:
                pass
    try:
        raw = _fetch()
    except Exception:
        if path.is_file():                     # stale beats nothing
            try:
                return _clean(json.loads(path.read_text()), now)
            except ValueError:
                pass
        return None
    path.write_text(json.dumps(raw))
    return _clean(raw, now)


def great_circle(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    return EARTH_R * math.acos(max(-1.0, min(1.0,
        math.sin(p1) * math.sin(p2)
        + math.cos(p1) * math.cos(p2) * math.cos(math.radians(lon2 - lon1)))))


def nearest(lat, lon, force=False):
    """The closest recently reporting ionosonde, with its distance."""
    found = stations(force)
    if not found:
        return None
    best = min(found, key=lambda s: great_circle(lat, lon, s["lat"], s["lon"]))
    best = dict(best)
    best["distance_km"] = round(great_circle(lat, lon, best["lat"], best["lon"]))
    return best


def spread(force=False):
    """What the network as a whole is reporting, to show the range."""
    found = stations(force)
    if not found:
        return None
    heights = sorted(s["hmf2"] for s in found)
    fof2 = sorted(s["fof2"] for s in found)
    middle = lambda a: a[len(a) // 2]
    return {
        "count": len(found),
        "hmf2": {"low": heights[0], "high": heights[-1], "median": middle(heights)},
        "fof2": {"low": fof2[0], "high": fof2[-1], "median": middle(fof2)},
        "source": "prop.kc2g.com, aggregating the GIRO/Digisonde network",
    }

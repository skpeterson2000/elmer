"""Ground elevation profiles for path analysis.

Uses the public OpenTopoData SRTM 30 m dataset, which needs no key.  That
service asks for no more than one call a second and a hundred points per call,
so profiles are sampled to fit in a single request, rate limited, and cached on
disk - a path you looked at yesterday costs nothing to look at again.

Everything here degrades to None rather than raising: the path tool still does
the smooth-earth maths when the network is missing, and simply says the terrain
is unknown.
"""
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "terrain"
API = "https://api.opentopodata.org/v1/srtm30m"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
MAX_POINTS = 100          # the service's per-request ceiling
MIN_INTERVAL = 1.1        # seconds between calls, per their fair-use request
EARTH_R = 6371.0

_last_call = [0.0]


def great_circle(lat1, lon1, lat2, lon2):
    """Distance in km and initial bearing in degrees."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    km = 2 * EARTH_R * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dlon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return km, (math.degrees(math.atan2(y, x)) + 360) % 360


def interpolate(lat1, lon1, lat2, lon2, samples):
    """Points along the great circle, ends included."""
    p1, l1 = math.radians(lat1), math.radians(lon1)
    p2, l2 = math.radians(lat2), math.radians(lon2)
    d = 2 * math.asin(min(1.0, math.sqrt(
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2)))
    if d == 0:
        return [(lat1, lon1)] * samples
    out = []
    for i in range(samples):
        f = i / (samples - 1) if samples > 1 else 0.0
        a = math.sin((1 - f) * d) / math.sin(d)
        b = math.sin(f * d) / math.sin(d)
        x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
        y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
        z = a * math.sin(p1) + b * math.sin(p2)
        out.append((math.degrees(math.atan2(z, math.hypot(x, y))),
                    math.degrees(math.atan2(y, x))))
    return out


def _cache_key(lat1, lon1, lat2, lon2, samples):
    return "%.4f_%.4f__%.4f_%.4f__%d.json" % (lat1, lon1, lat2, lon2, samples)


def _throttle():
    wait = MIN_INTERVAL - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def profile(lat1, lon1, lat2, lon2, samples=80):
    """Elevations in metres along the path, or None if terrain is unavailable."""
    samples = max(2, min(MAX_POINTS, int(samples)))
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / _cache_key(lat1, lon1, lat2, lon2, samples)
    if cached.is_file():
        try:
            return json.loads(cached.read_text())
        except ValueError:
            cached.unlink(missing_ok=True)

    points = interpolate(lat1, lon1, lat2, lon2, samples)
    locations = "|".join(f"{a:.6f},{b:.6f}" for a, b in points)
    url = f"{API}?{urllib.parse.urlencode({'locations': locations})}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        _throttle()
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except Exception:
        return None
    if payload.get("status") != "OK":
        return None

    km, bearing = great_circle(lat1, lon1, lat2, lon2)
    elevations = []
    for n, row in enumerate(payload.get("results", [])):
        value = row.get("elevation")
        elevations.append({
            "km": km * n / max(1, samples - 1),
            "elevation": 0.0 if value is None else float(value),
            "lat": row["location"]["lat"], "lon": row["location"]["lng"],
        })
    if len(elevations) < 2:
        return None

    out = {"distance_km": km, "bearing": bearing, "samples": len(elevations),
           "points": elevations, "source": "OpenTopoData SRTM 30 m"}
    cached.write_text(json.dumps(out))
    return out

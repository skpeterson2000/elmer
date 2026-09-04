"""Turn place names into coordinates, and coordinates into place names.

Uses OpenStreetMap's Nominatim, which needs no key but does ask for a
identifying User-Agent and no more than one request a second.  Both are
honoured here, and every lookup is cached on disk, so the same place costs
nothing to look up twice.

Grid squares, decimal coordinates and place names are all accepted by
:func:`resolve`, because asking someone for a Maidenhead locator when they
know the name of the lake they are pointing at is the wrong way round.
"""
import json
import math
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "geocode"
SEARCH = "https://nominatim.openstreetmap.org/search"
REVERSE = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
MIN_INTERVAL = 1.1                      # Nominatim's stated fair-use limit

RE_LATLON = re.compile(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
RE_GRID = re.compile(r"^[A-Ra-r]{2}\d{2}(?:[A-Xa-x]{2})?$")

_last_call = [0.0]


def to_grid(lat, lon, precision=6):
    """Latitude and longitude to a Maidenhead locator."""
    lat = max(-90.0, min(90.0, float(lat))) + 90.0
    lon = max(-180.0, min(180.0, float(lon))) + 180.0
    field = chr(int(lon // 20) + 65) + chr(int(lat // 10) + 65)
    square = f"{int((lon % 20) // 2)}{int(lat % 10)}"
    if precision <= 4:
        return field + square
    sub = (chr(int((lon % 2) / (2 / 24)) + 97)
           + chr(int((lat % 1) / (1 / 24)) + 97))
    return field + square + sub


def from_grid(grid):
    """Maidenhead locator to the coordinates at the centre of the square."""
    g = (grid or "").strip()
    if not RE_GRID.match(g):
        return None
    g = g[:2].upper() + g[2:4] + g[4:].lower()
    lon = (ord(g[0]) - 65) * 20 - 180 + int(g[2]) * 2
    lat = (ord(g[1]) - 65) * 10 - 90 + int(g[3])
    if len(g) == 6:
        lon += (ord(g[4]) - 97) * (2 / 24) + (1 / 24)
        lat += (ord(g[5]) - 97) * (1 / 24) + (0.5 / 24)
    else:
        lon += 1
        lat += 0.5
    return round(lat, 5), round(lon, 5)


def _throttle():
    wait = MIN_INTERVAL - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def _cached(name, fetch):
    CACHE.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9._-]+", "_", name.lower())[:120]
    path = CACHE / f"{safe}.json"
    if path.is_file():
        try:
            return json.loads(path.read_text())
        except ValueError:
            path.unlink(missing_ok=True)
    value = fetch()
    if value is not None:
        path.write_text(json.dumps(value))
    return value


def _get(url, params):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}",
                                     headers={"User-Agent": USER_AGENT,
                                              "Accept-Language": "en"})
    _throttle()
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def _place(row):
    lat, lon = float(row["lat"]), float(row["lon"])
    return {
        "name": row.get("display_name", ""),
        "short": row.get("name") or row.get("display_name", "").split(",")[0],
        "kind": row.get("type"),
        "lat": round(lat, 6), "lon": round(lon, 6),
        "grid": to_grid(lat, lon),
    }


def search(query, limit=6):
    """Places matching a name, best match first. Empty list if nothing found."""
    query = (query or "").strip()
    if not query:
        return []

    def fetch():
        try:
            rows = _get(SEARCH, {"q": query, "format": "jsonv2",
                                 "limit": max(1, min(10, limit)),
                                 "addressdetails": 0})
        except Exception:
            return None
        return [_place(r) for r in rows]

    return _cached(f"s_{query}_{limit}", fetch) or []


def reverse(lat, lon):
    """The name of the place at these coordinates, or None."""
    def fetch():
        try:
            row = _get(REVERSE, {"lat": lat, "lon": lon, "format": "jsonv2",
                                 "zoom": 12})
        except Exception:
            return None
        if not row or "lat" not in row:
            return None
        return _place(row)

    return _cached(f"r_{float(lat):.3f}_{float(lon):.3f}", fetch)


def resolve(text, allow_lookup=True):
    """Accept a grid square, a lat,lon pair or a place name.

    Returns a place dict, or None. Grid squares and coordinates resolve without
    touching the network; only a name needs a lookup.
    """
    text = (text or "").strip()
    if not text:
        return None

    if RE_GRID.match(text):
        point = from_grid(text)
        if point:
            return {"name": text.upper(), "short": text.upper(), "kind": "grid",
                    "lat": point[0], "lon": point[1],
                    "grid": to_grid(point[0], point[1])}

    m = RE_LATLON.match(text)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return {"name": f"{lat:.4f}, {lon:.4f}", "short": f"{lat:.4f}, {lon:.4f}",
                    "kind": "coordinates", "lat": lat, "lon": lon,
                    "grid": to_grid(lat, lon)}

    if not allow_lookup:
        return None
    found = search(text, limit=1)
    return found[0] if found else None

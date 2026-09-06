"""Towns worth naming, near wherever the operator actually is.

An antenna's footprint means little as a circle on a chart and a great deal as
a list of places: "this reaches Duluth and Fargo but not Chicago" is the
sentence that makes a pattern land. Which means ELMER needs to know what is
near *you*, and a list bundled with the program can only ever be a guess at
that.

So there are two sources, and the fetched one wins.

**Fetched.** Given a QTH, OpenStreetMap's Overpass API is asked for populated
places within reach, ranked by their population tag. It works anywhere on
earth, gets the small towns a national list would never carry, and is cached on
disk so it costs one request per operator per radius. This is what makes the
feature honest for somebody in Wales or Hokkaido rather than only in Minnesota.

**Bundled.** A few hundred North American cities ship with the program, so a
Pi that has never seen a network still has something to say. It is a fallback
and is treated as one.

The QTH is typed in by hand, so an off-grid station sets its own location and
keeps working: the only thing the network buys is better names for the places
around it.
"""
import json
import logging
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "data" / "places.json"
CACHE = ROOT / "data" / "places"

OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
TIMEOUT = 90
KEEP = 60                      # how many places to keep from a fetch
MIN_POPULATION = 1500          # below this a "town" is a hamlet with a sign

_bundled = None


def _load_bundled():
    global _bundled
    if _bundled is None:
        try:
            _bundled = json.loads(BUNDLED.read_text())["places"]
        except (OSError, ValueError, KeyError):
            _bundled = []
    return _bundled


def _key(lat, lon, radius_km):
    """A cache name that is stable for anywhere in the same neighbourhood.

    Rounded to a tenth of a degree - about seven miles - because moving the
    station across the garden should not mean fetching the world again.
    """
    return f"{lat:.1f}_{lon:.1f}_{int(radius_km)}".replace("-", "m")


def cached(lat, lon, radius_km):
    """Places already fetched for this neighbourhood, or None."""
    path = CACHE / f"{_key(lat, lon, radius_km)}.json"
    try:
        return json.loads(path.read_text())["places"]
    except (OSError, ValueError, KeyError):
        return None


def _population(element):
    raw = (element.get("tags") or {}).get("population", "")
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else 0


def fetch(lat, lon, radius_km):
    """Ask OpenStreetMap what towns are within reach, and remember the answer.

    Only places carrying a population tag, so the list can be ranked by how
    likely somebody is to have heard of them rather than by whatever happens
    to be nearest.
    """
    query = (f"[out:json][timeout:60];"
             f'(node(around:{int(radius_km * 1000)},{lat:.4f},{lon:.4f})'
             f'["place"~"^(city|town)$"]["population"];);out body;')
    request = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        payload = json.loads(response.read())

    rows = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        name = tags.get("name")
        population = _population(element)
        if not name or population < MIN_POPULATION:
            continue
        rows.append({"name": name,
                     "region": tags.get("is_in:state_code")
                               or tags.get("addr:state") or "",
                     "lat": round(element["lat"], 4),
                     "lon": round(element["lon"], 4),
                     "population": population})
    rows.sort(key=lambda r: -r["population"])
    rows = rows[:KEEP]

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{_key(lat, lon, radius_km)}.json"
    path.write_text(json.dumps(
        {"source": "OpenStreetMap via Overpass, ranked by population",
         "centre": [round(lat, 4), round(lon, 4)], "radius_km": radius_km,
         "places": rows}, indent=1))
    log.info("places: %d towns within %d km of %.3f,%.3f",
             len(rows), radius_km, lat, lon)
    return rows


def known(lat, lon, radius_km):
    """The best list available without going to the network.

    Fetched places if this neighbourhood has been looked up, otherwise whatever
    shipped with the program. Never blocks and never fails: an antenna pattern
    is not worth waiting on a web service for.
    """
    got = cached(lat, lon, radius_km)
    if got:
        return got, "fetched"
    return _load_bundled(), "bundled"


def refresh_in_background(lat, lon, radius_km):
    """Fetch quietly, once, for next time. Failure is not worth reporting."""
    import threading

    if cached(lat, lon, radius_km) is not None:
        return None

    def run():
        try:
            fetch(lat, lon, radius_km)
        except Exception as exc:
            log.debug("places: could not fetch (%s)", exc)

    thread = threading.Thread(target=run, name="places-fetch", daemon=True)
    thread.start()
    return thread

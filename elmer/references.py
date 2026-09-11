"""Parks and summits near enough to be a day out, kept for when there is none.

The programmes are useless to somebody who cannot say what is near them, and
"near" is the part a program can actually answer. So this fetches the parks
and summits within a day's reach while there is a signal, and holds them, so
that a unit in a valley with no bars can still say what is around it and what
the drive is. It is the same bargain the rest of ELMER makes about places:
look it up once, keep it, and be honest afterwards about what is held.

Radius is stated in kilometres because that is what arithmetic wants, but the
number is chosen in hours. Four hours of driving is about as far as anybody
goes and comes back the same day, and four hours of road is roughly this far
in a straight line - less through mountains, more across a plain. The circle
is a stand-in for a drive and it will be generous where the roads are bad.

**Where the data comes from.** POTA answers per location - a state, a province
- from `api.pota.app`, and SOTA answers per region from `api2.sota.org.uk`,
which also publishes a bounding box for every association and region and so
says who is worth asking without downloading the world. The alternative for
summits is a 24 MB list of all 179,000 of them, which is one request and a
great deal of somebody's bandwidth for a county's worth of hills.

**A centre decides who to ask; it never decides what is near.** POTA's
location list carries a coordinate per location, and some of them are simply
wrong - as this was written it placed South Africa's North West province in
Indiana and a Romanian county in Missouri. Trusting those would put a park
2,000 km away on a list of what is nearby. So the centres are used only to
choose whose list to request, and then every reference is measured on its own
coordinates, which are the ones the operator would drive to.
"""
import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

from .terrain import great_circle

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "references.json"

POTA_LOCATIONS = "https://api.pota.app/locations"
POTA_PARKS = "https://api.pota.app/location/parks/{code}"
SOTA_ASSOCIATIONS = "https://api2.sota.org.uk/api/associations"
SOTA_ASSOCIATION = "https://api2.sota.org.uk/api/associations/{code}"
SOTA_REGION = "https://api2.sota.org.uk/api/regions/{assoc}/{region}"

USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
TIMEOUT = 45

# Four hours of driving, give or take the roads.
DEFAULT_RADIUS_KM = 350

# How long a held list stays trustworthy before it is worth fetching again.
#
# Not because it rots - a park that was there last month is almost certainly
# still there - but because the lists move at the edges. POTA adds references
# continually and retires a few; SOTA associations revise summit lists and
# change point values at their own pace. A month is about the cadence at which
# somebody plans another trip, so the reminder lands when it is useful rather
# than while they are packing.
#
# It is a reminder and never a refusal. Stale data in the field beats no data
# in the field, every time, and a unit with no signal cannot act on this
# anyway - which is exactly when it is being read.
STALE_DAYS = 30
# How far outside the circle a location's centre may sit and still be worth
# asking. A state is wide, and its centre can be hundreds of kilometres from
# the corner of it that is close to you.
CENTRE_MARGIN_KM = 600


def _get(url):
    """Ask, and return None rather than raising. Preparing is not worth a
    traceback: a partial answer is still worth keeping, and what is missing
    is recorded instead."""
    try:
        headers = {"User-Agent": USER_AGENT}
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, ValueError, OSError) as exc:
        log.warning("references: %s - %s", url, exc)
        return None


def _box_km(lat, lon, box):
    """How far outside a bounding box a point is - zero when it is inside."""
    if box.get("minLat") is None or box.get("minLong") is None:
        return None
    near_lat = min(max(lat, box["minLat"]), box["maxLat"])
    near_lon = min(max(lon, box["minLong"]), box["maxLong"])
    return great_circle(lat, lon, near_lat, near_lon)[0]


def parks_near(lat, lon, radius_km, say=None):
    """Every POTA park within the radius, measured park by park."""
    say = say or (lambda *_: None)
    locations = _get(POTA_LOCATIONS)
    if not locations:
        return None
    def worth_asking(place):
        if place.get("latitude") is None or place.get("longitude") is None:
            return False
        away = great_circle(lat, lon, place["latitude"], place["longitude"])[0]
        return away < radius_km + CENTRE_MARGIN_KM

    asking = [l for l in locations if worth_asking(l)]
    say(f"POTA: {len(asking)} location lists to read")
    found = []
    for place in asking:
        rows = _get(POTA_PARKS.format(code=place["locationDesc"]))
        for park in rows or ():
            if park.get("latitude") is None or park.get("longitude") is None:
                continue
            km, bearing = great_circle(lat, lon, park["latitude"],
                                       park["longitude"])
            if km > radius_km:
                continue
            found.append({
                "kind": "park", "ref": park["reference"],
                "name": park.get("name") or park["reference"],
                "lat": round(park["latitude"], 4),
                "lon": round(park["longitude"], 4),
                "where": park.get("locationDesc") or "",
                "grid": park.get("grid") or "",
                "activations": park.get("activations") or 0,
                "km": round(km), "bearing": round(bearing),
            })
    return sorted(found, key=lambda p: p["km"])


def summits_near(lat, lon, radius_km, say=None):
    """Every valid SOTA summit within the radius, region by region."""
    say = say or (lambda *_: None)
    associations = _get(SOTA_ASSOCIATIONS)
    if not associations:
        return None
    close = [a for a in associations
             if (_box_km(lat, lon, a) or 1e9) < radius_km]
    say(f"SOTA: {len(close)} association"
        f"{'' if len(close) == 1 else 's'} overlapping the circle")
    found = []
    for association in close:
        code = association["associationCode"]
        detail = _get(SOTA_ASSOCIATION.format(code=code))
        for region in (detail or {}).get("regions") or ():
            if (_box_km(lat, lon, region) or 1e9) >= radius_km:
                continue
            rows = _get(SOTA_REGION.format(assoc=code,
                                           region=region["regionCode"]))
            for summit in (rows or {}).get("summits") or ():
                if summit.get("latitude") is None:
                    continue
                # A delisted summit is still in the data and is worth no
                # points; offering one is sending somebody up a hill for
                # nothing.
                if not summit.get("valid", True):
                    continue
                km, bearing = great_circle(lat, lon, summit["latitude"],
                                           summit["longitude"])
                if km > radius_km:
                    continue
                found.append({
                    "kind": "summit", "ref": summit["summitCode"],
                    "name": summit.get("name") or summit["summitCode"],
                    "lat": round(summit["latitude"], 4),
                    "lon": round(summit["longitude"], 4),
                    "where": summit.get("regionName") or "",
                    "alt_m": summit.get("altM"),
                    "points": summit.get("points"),
                    "activations": summit.get("activationCount") or 0,
                    "km": round(km), "bearing": round(bearing),
                })
    return sorted(found, key=lambda s: s["km"])


def fetch(lat, lon, radius_km=DEFAULT_RADIUS_KM, label=None, say=None):
    """Fetch and hold what is within reach of one place.

    Returns the area record. A programme that could not be reached leaves its
    list absent rather than empty, because those are different answers and an
    operator told "no summits near you" when the truth is "nobody asked" has
    been told the wrong thing.
    """
    say = say or (lambda *_: None)
    parks = parks_near(lat, lon, radius_km, say)
    summits = summits_near(lat, lon, radius_km, say)
    area = {
        "label": label or "here", "lat": round(lat, 4), "lon": round(lon, 4),
        "radius_km": radius_km, "fetched": time.time(),
        "parks": parks, "summits": summits,
        "missing": [name for name, rows in
                    (("parks", parks), ("summits", summits)) if rows is None],
    }
    areas = [a for a in held() if a.get("label") != area["label"]]
    areas.append(area)
    _write(areas)
    return area


def _write(areas):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps({
        "note": "Parks and summits fetched while connected, held for when "
                "there is no signal. Yours, keyed to where you go.",
        "areas": areas}, indent=1))


def held():
    """Every area prepared so far."""
    try:
        return json.loads(STORE.read_text()).get("areas", [])
    except (OSError, ValueError):
        return []


def nearby(lat, lon, kind=None, limit=12, radius_km=None):
    """The references held for anywhere, nearest to here first.

    `limit` of None is all of them, which is how a caller counts what is held
    without its own display cap quietly becoming the answer.

    Distances are recomputed against this position rather than trusted from
    the fetch, because the operator has moved since - that is the entire point
    of having driven somewhere.
    """
    seen, out = set(), []
    for area in held():
        for row in (area.get("parks") or []) + (area.get("summits") or []):
            if kind and row["kind"] != kind:
                continue
            if row["ref"] in seen:
                continue
            seen.add(row["ref"])
            km, bearing = great_circle(lat, lon, row["lat"], row["lon"])
            if radius_km is not None and km > radius_km:
                continue
            out.append(dict(row, km=round(km), bearing=round(bearing)))
    out.sort(key=lambda r: r["km"])
    return out if limit is None else out[:limit]


def age_days(area):
    """How long ago this area was fetched, in days."""
    when = area.get("fetched")
    if not when:
        return None
    return max(0.0, (time.time() - float(when)) / 86400.0)


def coverage(lat, lon):
    """Whether anything has been prepared for *here*.

    Nothing held means two different things - there is nothing near you, or
    nobody has ever looked here - and saying the first when the truth is the
    second is how a program loses an operator's trust.
    """
    areas = held()
    if not areas:
        return {"known": False, "reason": "none", "areas": 0,
                "nearest_km": None}
    def away(area):
        return great_circle(lat, lon, area["lat"], area["lon"])[0]

    nearest = min(away(a) for a in areas)
    inside = any(away(a) <= a["radius_km"] for a in areas)
    # nearby() draws on every held area at once, so the list in front of
    # somebody can be a mix of ages. The one worth reporting is the oldest
    # that is contributing, because that is the one that could mislead.
    ages = [d for d in (age_days(a) for a in areas) if d is not None]
    oldest = max(ages) if ages else None
    return {"known": inside, "reason": "here" if inside else "elsewhere",
            "areas": len(areas), "nearest_km": round(nearest),
            "oldest_days": round(oldest) if oldest is not None else None,
            "stale": bool(oldest is not None and oldest >= STALE_DAYS),
            "stale_days": STALE_DAYS}

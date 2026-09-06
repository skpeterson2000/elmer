"""Getting ready for somewhere the internet is not.

ELMER works with no network - that is the whole design - but several of the
things that make it useful about a *place* are looked up once and then
remembered: the towns around you, where they are, what the ground does between
you and them. Off the grid it can only remember what it was told before you
left.

So this is the packing list. Name where you are going while you still have a
signal, and ELMER fetches and keeps what it will need there: the neighbours,
the coordinates, the grid square. Then in a canyon with no bars it can still
answer "who can I reach from here, and which way do I point".

What it cannot pack is said plainly rather than left to be discovered at the
worst moment. Live solar numbers need the network at the time. Repeaters come
from TowerWitch and are its to fetch. Ground profiles are per-path and there
are more paths than anybody could cache.

Nothing here is required. It is the difference between a program that happens
to work offline and one that was got ready for it.
"""
import json
import time
from pathlib import Path

from . import geocode, places
from .terrain import great_circle

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "trips.json"

# Wide enough to hold an NVIS footprint, a tropo circle and the near half of a
# first HF hop - which is everything the plan view asks for at a destination.
# Wider queries are refused by Overpass more often than they are answered.
DEFAULT_RADIUS_KM = 800


def _read():
    try:
        return json.loads(STORE.read_text()).get("destinations", [])
    except (OSError, ValueError):
        return []


def _write(rows):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps({
        "note": "Places prepared for use without a network. Fetched while "
                "connected so ELMER can answer about them later.",
        "destinations": rows}, indent=1))


def listing():
    """Everywhere prepared, newest first."""
    return sorted(_read(), key=lambda d: -(d.get("prepared") or 0))


def find(name):
    """A prepared destination by name, matched loosely."""
    wanted = str(name or "").strip().lower()
    if not wanted:
        return None
    for row in _read():
        if wanted in (row.get("name") or "").lower() \
                or wanted == (row.get("grid") or "").lower():
            return row
    return None


def forget(name):
    rows = _read()
    kept = [r for r in rows if (r.get("name") or "").lower() != str(name).lower()]
    _write(kept)
    return len(rows) - len(kept)


def resolve(where):
    """Turn what somebody typed into a place: a name, a grid, coordinates."""
    text = str(where or "").strip()
    if not text:
        return None
    if "," in text:
        head, _, tail = text.partition(",")
        try:
            lat, lon = float(head), float(tail)
        except ValueError:
            pass
        else:
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                grid = geocode.to_grid(lat, lon)
                return {"name": grid, "short": grid, "lat": lat, "lon": lon,
                        "grid": grid, "kind": "coords"}
    return geocode.resolve(text)


def prepare(where, radius_km=DEFAULT_RADIUS_KM, progress=None):
    """Fetch and keep what ELMER will need about a place it cannot reach later.

    Returns (ok, message, record). Never raises: preparing for a trip is not
    worth a traceback, and a half-prepared destination is still better than
    none - what was and was not obtained is recorded on the destination.
    """
    say = progress or (lambda *_: None)
    spot = resolve(where)
    if not spot or spot.get("lat") is None:
        return False, (f"could not work out where \"{where}\" is - try a town "
                       f"and state, a grid square, or lat,lon"), None

    say(f"found {spot.get('short') or spot['name']} "
        f"({spot['lat']:.3f}, {spot['lon']:.3f})")

    got, missing = [], []
    try:
        say(f"asking OpenStreetMap for towns within {radius_km} km ...")
        rows = places.fetch(spot["lat"], spot["lon"], radius_km)
        if rows:
            got.append(f"{len(rows)} towns within {radius_km} km")
        else:
            missing.append("no towns came back - the area may be empty, or "
                           "the query too wide to be served")
    except Exception as exc:
        missing.append(f"towns could not be fetched ({type(exc).__name__})")

    record = {
        "name": spot.get("short") or spot.get("name"),
        "grid": spot.get("grid") or geocode.to_grid(spot["lat"], spot["lon"]),
        "lat": round(spot["lat"], 4), "lon": round(spot["lon"], 4),
        "radius_km": radius_km, "prepared": time.time(),
        "have": got, "missing": missing,
    }
    rows = [r for r in _read() if r.get("name") != record["name"]]
    rows.append(record)
    _write(rows)
    return bool(got), ("prepared" if got else "recorded, but nothing was "
                                             "fetched"), record


def cannot_pack():
    """What no amount of preparation will carry into a canyon."""
    return [
        ("Live solar and band conditions",
         "The flux and the K index are read from the network when ELMER asks. "
         "Off-grid it falls back to the physics, which is enough to reason "
         "with and is not the same as knowing."),
        ("Repeaters",
         "These come from TowerWitch, against a data source that is its "
         "subscription. Have it look up where you are going, and run "
         "./elmer.py --import-repeaters before you leave."),
        ("Ground profiles between you and a station",
         "Fetched per path, and there are more paths than anybody could "
         "cache. The path tool falls back to smooth-earth geometry and says "
         "that the terrain is unknown, which is honest and still useful."),
    ]


def distance_from(lat, lon):
    """How far each prepared destination is from here - the nearest one is
    usually the one somebody means."""
    out = []
    for row in listing():
        km, bearing = great_circle(lat, lon, row["lat"], row["lon"])
        out.append(dict(row, km=round(km), bearing=round(bearing)))
    return sorted(out, key=lambda r: r["km"])

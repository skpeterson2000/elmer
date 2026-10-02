"""What people are actually doing at each park, gathered from the spot feed.

The activation record says who made their ten and on which modes. It does
not say which bands, what hour, or anything about where inside the park
they stood - nobody publishes that. The one place the band shows is the
live spot feed: every spot carries a frequency, a mode and a comment, and
the comment is now and then "5 W EFHW" or "north beach lot". The feed is
an hour deep and then gone.

So a unit that has a network samples it, quietly, every so often, and
folds what it saw into a record of its own: for each park, the bands and
modes people were spotted on, the hours, who, and the comments that hint
at an antenna or a spot. It starts empty, grows while the unit is on and
connected, and is honest about how many spots it is standing on. What it
never claims is a position - the grid on a spot is the park's, and a 40 m
spot says nothing about where in a sixty-mile beach it came from.

The feed is public and one request of about thirty kilobytes; the sample
is taken at the same cadence the space weather is.

The latest batch is also kept whole, in memory, for the reach map: who is on
the air from which park right now, on which band. That is the one place a
spot's position is used, and it is the park's, as the feed gives it.
"""
import json
import logging
import re
import threading
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone

from . import bandplan, paths

log = logging.getLogger("elmer")

STORE = paths.STATE / "spots.json"
FEED = "https://api.pota.app/spot/activator"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
TIMEOUT = 20
EVERY_MINUTES = 20
REMEMBER_IDS = 4000            # spots already counted, so a resample is not a recount
KEEP_HINTS = 12                # comments per park worth keeping
LIVE_MAX_AGE_S = 90 * 60       # a batch this old is not "on the air now", whatever it says

# A comment that says something about the station rather than the QSO.
HINT = re.compile(r"\b(efhw|end.?fed|dipole|vertical|whip|yagi|beam|loop|wire|random wire|hamstick|"
                  r"buddi|magloop|mag loop|\d+\s?w\b|qrp|mile|beach|campground|camp|parking|lot|trailhead|"
                  r"trail|summit|overlook|picnic|shelter|cabin|boat|ramp|pier|tower|visitor)\b", re.I)


def _band(frequency_khz):
    try:
        mhz = float(frequency_khz) / 1000.0
    except (TypeError, ValueError):
        return None
    band = bandplan.band_at(mhz)
    return band["name"] if band else None


def _load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"note": "Spots ELMER has seen on the POTA feed while it had a network, folded by "
                        "park: bands, modes, hours and the comments that hint at an antenna or a "
                        "spot. Yours; grown here, never fetched whole.",
                "samples": 0, "first": None, "last": None, "seen": [], "parks": {}}


def _save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data), encoding="utf-8")


def fold(data, spots, when=None):
    """Count a feed's spots into the record, once each. Returns how many
    were new."""
    when = when or datetime.now(timezone.utc)
    seen = set(data.get("seen") or [])
    new = 0
    for spot in spots or []:
        sid = spot.get("spotId")
        ref = (spot.get("reference") or "").upper()
        if not ref or (sid is not None and sid in seen):
            continue
        if sid is not None:
            seen.add(sid)
        park = data["parks"].setdefault(ref, {
            "name": spot.get("name") or ref, "spots": 0, "bands": {}, "modes": {},
            "hours": [0] * 24, "activators": {}, "hints": [], "last": None})
        park["spots"] += 1
        band = _band(spot.get("frequency"))
        if band:
            park["bands"][band] = park["bands"].get(band, 0) + 1
        mode = (spot.get("mode") or "").upper().strip()
        if mode:
            park["modes"][mode] = park["modes"].get(mode, 0) + 1
        try:
            hour = datetime.fromisoformat(str(spot.get("spotTime")).replace("Z", "")).hour
        except ValueError:
            hour = when.hour
        park["hours"][hour] += 1
        call = (spot.get("activator") or "").upper()
        if call:
            park["activators"][call] = park["activators"].get(call, 0) + 1
        text = (spot.get("comments") or "").strip()
        if text and HINT.search(text):
            park["hints"] = ([{"when": when.date().isoformat(), "call": call, "band": band,
                               "text": text[:120]}] + park["hints"])[:KEEP_HINTS]
        park["last"] = when.date().isoformat()
        new += 1
    data["seen"] = list(seen)[-REMEMBER_IDS:]
    data["samples"] = data.get("samples", 0) + 1
    data["first"] = data.get("first") or when.date().isoformat()
    data["last"] = when.date().isoformat()
    return new


_live_lock = threading.Lock()
_live = {"as_of": None, "taken": None, "spots": []}
_failing = [False]             # whether the last sample failed, so a failure is logged once


def _repair(text):
    """A park name the feed sends as UTF-8 read as Windows-1252 - "æ±Ÿè‹"
    for a Chinese name - read back the right way, when that is what it is."""
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
        return text


def live_batch(spots, now=None):
    """The feed's spots as the map wants them: placed, banded, and with the
    moment each one expires. A spot with no position, or marked invalid, is
    left out."""
    now = now or time.time()
    out = []
    for spot in spots or []:
        try:
            lat, lon = float(spot.get("latitude")), float(spot.get("longitude"))
        except (TypeError, ValueError):
            continue
        if spot.get("invalid") or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        try:
            khz = float(spot.get("frequency"))
        except (TypeError, ValueError):
            khz = None
        try:
            expire = max(0, int(spot.get("expire") or 0))
        except (TypeError, ValueError):
            expire = 0
        out.append({"call": (spot.get("activator") or "").upper(), "ref": (spot.get("reference") or "").upper(),
                    "name": _repair(spot.get("name") or ""), "lat": lat, "lon": lon,
                    "mhz": round(khz / 1000, 4) if khz else None, "band": _band(khz) if khz else None,
                    "mode": (spot.get("mode") or "").upper(), "grid": spot.get("grid6") or spot.get("grid4") or "",
                    "spotted": (str(spot.get("spotTime") or "") + "Z") if spot.get("spotTime") else None,
                    "expires": now + expire if expire else None,
                    "comment": (spot.get("comments") or "")[:120]})
    return out


def live(now=None):
    """The activators on the air now, from the latest sample: spots past
    their expiry are dropped, and a batch older than LIVE_MAX_AGE_S is
    none at all."""
    now = now or time.time()
    with _live_lock:
        taken, spots, as_of = _live["taken"], list(_live["spots"]), _live["as_of"]
    if not taken or now - taken > LIVE_MAX_AGE_S:
        return {"as_of": as_of, "spots": [], "stale": bool(taken)}
    return {"as_of": as_of, "stale": False,
            "spots": [s for s in spots if not s["expires"] or s["expires"] > now]}


def sample():
    """One look at the feed, folded in and saved, and kept whole for the
    map. A failure is logged once, and the recovery once."""
    request = urllib.request.Request(FEED, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            spots = json.loads(response.read().decode("utf-8", "replace"))
    except (OSError, ValueError) as exc:           # no network is the usual reason
        if not _failing[0]:
            log.warning("POTA spot feed not reachable, the map's activators wait for it: %s", exc)
            _failing[0] = True
        return None
    if _failing[0]:
        log.info("POTA spot feed reachable again")
        _failing[0] = False
    with _live_lock:
        _live.update(taken=time.time(), spots=live_batch(spots),
                     as_of=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    data = _load()
    new = fold(data, spots)
    try:
        _save(data)
    except OSError as exc:
        log.warning("POTA spot record could not be saved at %s: %s", STORE, exc)
    log.debug("spots: %d on the feed, %d new", len(spots or []), new)
    return new


def watch(minutes=EVERY_MINUTES):
    """Sample every so often, for as long as the server runs."""
    def run():
        from . import activity
        while True:
            # nobody at the unit asked for it: it waits for a game, a net,
            # an exam or somebody studying to finish (see activity.py)
            activity.wait_until_idle("spot sampling")
            sample()
            time.sleep(minutes * 60)
    thread = threading.Thread(target=run, name="spot-watch", daemon=True)
    thread.start()
    return thread


def story(ref):
    """What this unit has seen at one park, or None when nothing."""
    data = _load()
    park = data["parks"].get((ref or "").upper())
    if not park or not park["spots"]:
        return None
    n = park["spots"]
    bands = Counter(park["bands"]).most_common()
    modes = Counter(park["modes"]).most_common()
    hours = park["hours"]
    busy = [h for h in sorted(range(24), key=lambda h: -hours[h])[:3] if hours[h]]
    return {
        "spots": n, "since": data.get("first"), "last": park.get("last"),
        "bands": [{"band": b, "share": round(100 * c / n)} for b, c in bands],
        "modes": [{"mode": m, "share": round(100 * c / n)} for m, c in modes],
        "hours_utc": hours, "busy_utc": sorted(busy),
        "activators": len(park["activators"]),
        "hints": park["hints"],
    }


def sentence(seen):
    if not seen:
        return ""
    n = seen["spots"]
    parts = [f"From {n} spot{'s' if n != 1 else ''} this unit has seen here since {seen['since']}"
             f" ({seen['activators']} activator{'s' if seen['activators'] != 1 else ''}):"]
    if seen["bands"]:
        parts.append(", ".join(f"{b['band']} {b['share']}%" for b in seen["bands"][:4]) + ";")
    if seen["modes"]:
        parts.append(", ".join(f"{m['mode']} {m['share']}%" for m in seen["modes"][:3]) + ".")
    return " ".join(parts)

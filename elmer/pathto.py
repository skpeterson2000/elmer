"""Reaching a particular place: the path from here to there, and how.

The Make Contact page answers "what can I do from here?" - and most real
needs have a destination: a relative's town, the net's location, the club
across the state. This is the other half. Given where the operator stands
and where they are trying to reach, it says how far and which way, whether
either end is in the dark, whether two antennas could see each other (and
past about fifty miles they never can), which bands the ionosphere would
carry it on right now, and then the approach an Elmer would suggest: the
band, the mode, which way to hang the wire, and when to try if not now.

Radio is a science because this can be worked out, at least somewhat, and
an art because some do it better than others; the words here stay measured
- "carries it by one hop right now" is what the numbers say, and "a chance
after dark" is what they do not. Nothing here fetches anything the rest of
ELMER does not already fetch: the ionosphere from the propagation snapshot,
the ground from the terrain cache, the far end from the FCC record or the
gazetteer.
"""
import math
import re

from . import bandplan, callsign, geocode, propagation, reachout, terrain

# Past this a path is the ionosphere's, whatever the antennas: the radio
# horizon from a hundred feet up is about thirty miles, and nobody is asking
# this page from a mountain top with a tower.
SIGHT_KM = 80.0
# Two antennas at about head height, which is what somebody standing there has.
ANTENNA_M = 3.0
# 4/3-earth radius, for the bulge in the middle of a line of sight.
EARTH_KM = 8495.0

# A callsign has the shape prefix-digit-suffix; a grid square does not.
RE_CALLSIGN = re.compile(r"^[A-Z0-9]{1,2}\d[A-Z]{1,4}$")

# 47 CFR 97.301: what a class may key up on HF. Technician has phone on 10 m
# and CW only on three others; General and above have every band (with
# segments this page does not go into).
TECH_BANDS = {"10m": "SSB 28.300-28.500", "15m": "CW only", "40m": "CW only", "80m": "CW only",
              "6m": "all modes"}
# What each band is good for, in a phrase - the Elmer's shorthand.
BAND_MODE = {
    "160m": "CW or FT8 after dark; SSB when it is quiet",
    "80m": "SSB 3.800-4.000 in the evening, FT8 on 3.573",
    "60m": "USB on the channels, 100 W ERP",
    "40m": "SSB above 7.125, FT8 on 7.074, CW low in the band",
    "30m": "FT8 on 10.136 or CW - no phone on 30 m",
    "20m": "SSB 14.150-14.350, FT8 on 14.074",
    "17m": "SSB 18.110-18.168, FT8 on 18.100",
    "15m": "SSB 21.200-21.450, FT8 on 21.074",
    "12m": "SSB 24.930-24.990, FT8 on 24.915",
    "10m": "SSB 28.300-28.500, FT8 on 28.074",
    "6m": "SSB 50.125 calling, FT8 on 50.313",
}


def resolve_to(text):
    """The far end: a callsign (the FCC record has its grid), a grid square,
    a lat,lon, or a place name. None if nothing can be made of it."""
    text = (text or "").strip()
    if not text:
        return None
    # A grid square or a pair of coordinates first: neither costs a lookup,
    # and a grid like EN26 would pass for a callsign otherwise.
    place = geocode.resolve(text, allow_lookup=False)
    if place and place.get("lat") is not None:
        return place
    call = callsign.normalise(text)
    if RE_CALLSIGN.match(call):
        rec = callsign.lookup(call)
        if rec and rec.get("found") and rec.get("lat") is None and rec.get("place"):
            # The FCC's file has the town and not a coordinate; the bundled
            # places usually have the town.
            town = geocode.resolve(rec["place"])
            if town and town.get("lat") is not None:
                rec = dict(rec, lat=town["lat"], lon=town["lon"], grid=town.get("grid"))
        if rec and rec.get("found") and rec.get("lat") is not None:
            return {"name": rec["callsign"], "short": rec["callsign"], "kind": "callsign",
                    "lat": rec["lat"], "lon": rec["lon"],
                    "grid": rec.get("grid") or geocode.to_grid(rec["lat"], rec["lon"]),
                    "license_class": rec.get("license_class")}
        if rec and rec.get("found") is False:
            return {"error": f"no current FCC record for {call}"}
    place = geocode.resolve(text)
    if place and place.get("lat") is not None:
        return place
    return None


def _sight(lat1, lon1, lat2, lon2, km):
    """Whether two head-high antennas could see each other over the ground,
    from the terrain cache where it has the path, else smooth earth."""
    horizon = 4.12 * (math.sqrt(ANTENNA_M) + math.sqrt(ANTENNA_M))    # km, 4/3 earth
    out = {"km": round(km, 1), "horizon_km": round(horizon, 1), "terrain": False}
    if km > SIGHT_KM:
        out["verdict"] = "far past any line of sight - this one is the ionosphere's"
        out["clear"] = False
        return out
    prof = None
    try:
        prof = terrain.profile(lat1, lon1, lat2, lon2, samples=60)
    except Exception:
        prof = None
    if not prof or not prof.get("points"):
        out["clear"] = km <= horizon
        out["verdict"] = (f"within the radio horizon of two head-high antennas ({horizon:.0f} km) over "
                          f"smooth earth" if out["clear"] else
                          f"beyond the radio horizon of head-high antennas ({horizon:.0f} km); height at "
                          f"either end, or a repeater between, is what gets it through")
        return out
    pts = prof["points"]
    a = pts[0]["elevation"] + ANTENNA_M
    b = pts[-1]["elevation"] + ANTENNA_M
    worst = None
    for p in pts[1:-1]:
        d1 = p["km"]
        d2 = km - d1
        line = a + (b - a) * (d1 / km) - (d1 * d2) / (2 * EARTH_KM) * 1000.0
        over = p["elevation"] - line
        if worst is None or over > worst[0]:
            worst = (over, d1, p["elevation"])
    out["terrain"] = True
    out["source"] = prof.get("source")
    if worst is None or worst[0] <= 0:
        out["clear"] = True
        out["verdict"] = "the ground clears between them - a simplex path, line of sight"
    else:
        out["clear"] = False
        out["blocked_km"] = round(worst[1], 1)
        out["blocked_m"] = round(worst[0])
        out["verdict"] = (f"ground in the way {worst[1]:.0f} km along, about {worst[0]:.0f} m above the "
                          f"line - a repeater or height at one end is what gets past it")
    return out


def _allowed(band, license):
    rank = reachout._class_rank(license)
    # CB is a licence-free service, so 11 m is on the list for everybody -
    # with a certified CB radio, which is the condition, not the class.
    if band == "11m":
        return True, "CB: SSB on channels 36-40 (38 LSB to call), 12 W PEP, any certified CB radio"
    if rank < 0:
        return False, "needs an amateur licence"
    if rank >= bandplan.CLASS_RANK.get("General", 2):
        return True, BAND_MODE.get(band, "")
    if band in TECH_BANDS:
        return True, TECH_BANDS[band]
    return False, "not a Technician band"


def _antenna_note(how, bearing):
    if how in ("straight up and back",):
        return ("a dipole low - a fifth of a wave up or less - fires straight up and comes "
                "down where you want; height would only send it past them")
    if how == "ground wave":
        return "a vertical, and the best ground you can give it"
    return (f"hang a dipole broadside to {bearing:.0f} degrees - the wire running "
            f"{(bearing + 90) % 360:.0f}/{(bearing + 270) % 360:.0f} - as high as you can; "
            f"a vertical is the second choice, and a fair one for the low angle")


def predict(here, there, gear=(), license="Technician", watts=100.0, now=None):
    """The path and the approach. `here` and `there` are place dicts with
    lat/lon; the ionosphere is read at the midpoint, which is where a
    one-hop path is reflected."""
    km, bearing = terrain.great_circle(here["lat"], here["lon"], there["lat"], there["lon"])
    back = (bearing + 180.0) % 360.0
    mid_lat = (here["lat"] + there["lat"]) / 2.0
    mid_lon = (here["lon"] + there["lon"]) / 2.0
    sun_here = reachout.sun_state(here["lat"], here["lon"], now)
    sun_there = reachout.sun_state(there["lat"], there["lon"], now)
    sight = _sight(here["lat"], here["lon"], there["lat"], there["lon"], km)
    snap = propagation.snapshot(lat=mid_lat, lon=mid_lon)
    sky = propagation.path_bands(
        km, fof2=snap.get("fof2"), hmf2=snap.get("hmf2") or propagation.HMF2_DEFAULT,
        elevation=snap.get("elevation") or 0.0, k_index=snap.get("k_index") or 2.0,
        muf=snap.get("muf"), watts=watts)

    has_hf = reachout._has_hf(gear)
    has_vhf = reachout._vhf(gear)
    approach = []
    if sight.get("clear") and has_vhf:
        approach.append({"band": "2 m / 70 cm", "how": "line of sight", "odds": "good",
                         "mode": "FM simplex - 146.520 to call, then move off",
                         "antenna": "anything vertical, held high and in the clear",
                         "why": sight["verdict"]})
    elif km <= SIGHT_KM and has_vhf:
        approach.append({"band": "2 m / 70 cm", "how": "by repeater", "odds": "worth trying",
                         "mode": "a repeater that covers both ends - the list below has the ones in range here",
                         "antenna": "vertical, high as you can hold it",
                         "why": sight["verdict"]})
    if has_hf:
        rows = [r for r in sky["bands"] if r["works"]]
        if km <= SIGHT_KM:
            # Across town, HF is ground wave or straight up; the rest of the
            # list would be bands that happen to reach, not the way to go.
            rows = [r for r in rows if r["how"] in ("ground wave", "straight up and back")][:2]
        # Best first: fewer hops, then the band's own rating, then the
        # nearest to the middle of HF - the middle bands are the easy ones.
        rows.sort(key=lambda r: ((r.get("hops") or 1), -(r.get("score") or 0)))
        for r in rows:
            ok, mode = _allowed(r["band"], license)
            if not ok:
                continue
            odds = ("good" if (r.get("hops") or 1) == 1 and (r.get("score") or 50) >= 50
                    else "worth trying" if (r.get("hops") or 1) <= 2 else "long shot")
            approach.append({"band": r["band"], "how": r["how"], "odds": odds, "mode": mode,
                             "antenna": _antenna_note(r["how"], bearing),
                             "why": r.get("cost") or f"carries {km:.0f} km by {r['how']} right now"})
        if not rows:
            reasons = [r for r in sky["bands"] if r.get("why")]
            approach.append({"band": "HF", "how": None, "odds": "long shot",
                             "mode": "FT8 - it hears what SSB cannot",
                             "antenna": _antenna_note("one hop", bearing),
                             "why": (reasons[0]["why"] if reasons else
                                     "no band carries it by the numbers just now")})
    if not has_hf and km > SIGHT_KM:
        # A handheld does not carry a hundred miles on its own, and saying
        # "tick something" to somebody who has nothing else is no help. The
        # ways are a linked system near here, or HF - and which HF band
        # would do it, in case one can be borrowed.
        would = [r["band"] for r in sky["bands"] if r["works"] and _allowed(r["band"], license)[0]]
        approach.append({"band": "VHF/UHF, by a linked system", "how": "repeaters that link", "odds": "worth trying",
                         "mode": ("a linked repeater system, or a repeater with an EchoLink or IRLP node, "
                                  "near here - the list below names the machines in range; ask on one "
                                  "whether it links toward " + (there.get("short") or "there")),
                         "antenna": "vertical, high as you can hold it",
                         "why": f"{km:.0f} km is far past what a handheld reaches on its own"})
        approach.append({"band": ", ".join(would) if would else "HF", "how": "the ionosphere", "odds": "good" if would else "long shot",
                         "mode": ("what would carry it right now, if an HF radio can be borrowed - tick "
                                  "HF above and this fills in" if would else
                                  "an HF radio, and a better hour - tick HF above and this fills in"),
                         "antenna": "", "why": ""})
    if not approach:
        approach.append({"band": None, "how": None, "odds": "the rule",
                         "mode": "tick what you have above - the approach depends on it",
                         "antenna": "", "why": ""})

    # When, if not now. The low bands want dark at both ends; the high ones
    # want light. Said as the state of the two ends, which is what changes.
    when = None
    dark = [s for s in (sun_here, sun_there) if s == "dark"]
    if km > SIGHT_KM:
        if len(dark) == 1:
            when = ("one end is in daylight and the other in the dark: the low bands are "
                    "half open and the high ones half shut - the hour when both ends are "
                    "in the same light is easier, either way")
        elif len(dark) == 2:
            when = "both ends in the dark: 80 m and 40 m are the bands of this hour, 20 m and up have gone quiet"
        elif sun_here == "grey" or sun_there == "grey":
            when = "on the grey line at one end - the hour the low bands carry furthest; it is short"
        else:
            when = "both ends in daylight: 20 m, 17 m and 15 m are the bands of this hour; 40 m after dark"

    return {
        "from": {"short": here.get("short") or here.get("grid"), "grid": here.get("grid"),
                 "sun": sun_here},
        "to": {"short": there.get("short") or there.get("name"), "grid": there.get("grid"),
               "kind": there.get("kind"), "sun": sun_there,
               "license_class": there.get("license_class")},
        "km": round(km), "miles": round(km * 0.621371), "bearing": round(bearing),
        "back_bearing": round(back),
        "sight": sight,
        "sky": {"fof2": sky.get("fof2"), "muf": snap.get("muf"), "blind": sky.get("blind"),
                "one_hop_km": sky.get("one_hop_km"),
                "bands": [{k: r.get(k) for k in ("band", "works", "how", "hops", "why", "label", "score")}
                          for r in sky["bands"]],
                "read_at": "the midpoint of the path, where a hop is reflected"},
        "approach": approach,
        "when": when,
    }

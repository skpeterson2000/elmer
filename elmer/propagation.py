"""Live space-weather snapshot, translated into band-by-band expectations.

Two public sources, both keyless:

* N0NBH's solar XML (hamqsl.com) - the numbers and the day/night band ratings
  that every shack wall chart uses;
* NOAA SWPC JSON - authoritative planetary K index and 10.7 cm flux, used to
  cross-check and to fill in when the XML is stale.

Everything is cached so opening the dashboard repeatedly does not hammer either
service.
"""
import json
import math
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
HAMQSL = "https://www.hamqsl.com/solarxml.php"
SWPC_K = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
SWPC_WIND = "https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json"
CACHE_MINUTES = 15

BANDS = [
    ("160m", 1.8, "80m-40m"), ("80m", 3.5, "80m-40m"), ("60m", 5.3, "80m-40m"),
    ("40m", 7.0, "80m-40m"), ("30m", 10.1, "30m-20m"), ("20m", 14.0, "30m-20m"),
    ("17m", 18.1, "17m-15m"), ("15m", 21.0, "17m-15m"), ("12m", 24.9, "12m-10m"),
    ("10m", 28.0, "12m-10m"), ("6m", 50.0, None),
]
RATING_SCORE = {"Poor": 1, "Fair": 2, "Good": 3, "Band Closed": 0}

_cache = {"at": None, "data": None}


def _fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _hamqsl():
    root = ET.fromstring(_fetch(HAMQSL).decode("utf-8", "replace"))
    data = root.find("solardata")
    out = {"conditions": {}, "vhf": {}}
    for child in data:
        if child.tag == "calculatedconditions":
            for band in child:
                out["conditions"][(band.get("name"), band.get("time"))] = \
                    (band.text or "").strip()
        elif child.tag == "calculatedvhfconditions":
            for band in child:
                out["vhf"][f"{band.get('name')}/{band.get('location')}"] = \
                    (band.text or "").strip()
        else:
            out[child.tag] = (child.text or "").strip()
    return out


def _swpc():
    out = {}
    try:
        rows = json.loads(_fetch(SWPC_K))
        # rows are dicts: {"time_tag", "Kp", "a_running", "station_count"}
        if rows:
            last = rows[-1]
            out["kp"] = float(last["Kp"])
            out["a_running"] = float(last.get("a_running") or 0)
            out["kp_time"] = last["time_tag"]
    except (urllib.error.URLError, ValueError, KeyError, IndexError, TypeError, OSError):
        pass
    try:
        wind = json.loads(_fetch(SWPC_WIND))
        out["solar_wind"] = wind[0].get("proton_speed") if isinstance(wind, list) else None
    except (urllib.error.URLError, ValueError, IndexError, TypeError, OSError):
        pass
    return out


def solar_elevation(lat, lon, when=None):
    """Rough solar elevation in degrees - enough to pick day vs night."""
    when = when or datetime.now(timezone.utc)
    day = when.timetuple().tm_yday
    frac = (when.hour + when.minute / 60.0) / 24.0
    gamma = 2 * math.pi / 365 * (day - 1 + frac - 0.5)
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma)
                       - 0.032077 * math.sin(gamma) - 0.014615 * math.cos(2 * gamma)
                       - 0.040849 * math.sin(2 * gamma))
    minutes = when.hour * 60 + when.minute + eqtime + 4 * lon
    hour_angle = math.radians(minutes / 4.0 - 180.0)
    lat_r = math.radians(lat)
    cos_z = (math.sin(lat_r) * math.sin(decl)
             + math.cos(lat_r) * math.cos(decl) * math.cos(hour_angle))
    return math.degrees(math.asin(max(-1.0, min(1.0, cos_z))))


def estimate_muf(sfi, elevation):
    """A teaching-grade MUF(3000) estimate from flux and solar elevation.

    Not a substitute for an ionosonde - it exists so the dashboard can show how
    critical frequency tracks the sun, which is the point the pools test.
    """
    fof2 = 2.5 + 0.055 * max(0.0, sfi - 60.0)          # night floor to solar max
    day_gain = max(0.0, math.sin(math.radians(max(elevation, 0.0)))) ** 0.35
    fof2 *= 0.55 + 0.75 * day_gain
    # The F layer thins at night; it does not go away. Without a floor the
    # model closed 40m at midnight in a quiet sun, which is the one thing
    # every operator knows to be false - it is the band the night belongs to.
    # Mid-latitude foF2 sits around 2.5 MHz on a quiet night, which is a MUF
    # near 8 MHz, and that is what the floor says.
    fof2 = max(fof2, 2.5)
    return round(fof2 * 3.2, 1), round(fof2, 1)        # secant factor ~3.2


def _band_rows(ham, is_day, muf):
    period = "day" if is_day else "night"
    rows = []
    for name, freq, group in BANDS:
        if group:
            rating = ham["conditions"].get((group, period), "")
        else:
            eskip = ham["vhf"].get("E-Skip/north_america", "")
            rating = "Good" if eskip and "closed" not in eskip.lower() else "Band Closed"
        score = RATING_SCORE.get(rating, 0)
        if freq > muf:
            note = f"above the estimated {muf} MHz MUF - refraction fails, signals escape"
        elif not is_day and freq >= 21:
            note = "high bands normally close after dark"
        elif is_day and freq <= 3.5:
            note = "D-layer absorption keeps the low bands short by day"
        else:
            note = ""
        rows.append({"band": name, "mhz": freq, "rating": rating or "No data",
                     "score": score, "note": note})
    return rows


def snapshot(lat=None, lon=None, force=False):
    """Current conditions, cached. Returns a dict the dashboard renders directly."""
    now = datetime.now(timezone.utc)
    if not force and _cache["at"] and now - _cache["at"] < timedelta(minutes=CACHE_MINUTES):
        cached = dict(_cache["data"])
        cached["cached"] = True
        return cached

    try:
        ham = _hamqsl()
    except Exception as exc:                       # network, DNS, malformed XML
        return {"ok": False, "error": f"could not reach hamqsl.com ({exc})",
                "fetched": now.isoformat()}
    swpc = _swpc()

    def num(key, default=0.0):
        try:
            return float(ham.get(key, "") or default)
        except ValueError:
            return default

    sfi = num("solarflux", 70)
    a_index = num("aindex")
    k_index = swpc.get("kp", num("kindex"))
    a_index = swpc.get("a_running", a_index) or a_index
    elevation = solar_elevation(lat, lon) if lat is not None else None
    if elevation is not None:
        is_day = elevation > -6
    else:
        # no QTH set: the machine's own clock is the best guess we have
        is_day = 6 <= datetime.now().hour < 18
    muf, fof2 = estimate_muf(sfi, elevation if elevation is not None else 20.0)

    data = {
        "ok": True,
        "fetched": now.isoformat(),
        "updated": ham.get("updated", ""),
        "source": ham.get("source", "N0NBH"),
        "sfi": sfi, "a_index": a_index, "k_index": k_index,
        "sunspots": num("sunspots"), "xray": ham.get("xray", ""),
        "solar_wind": swpc.get("solar_wind") or num("solarwind"),
        "aurora": num("aurora"), "aurora_lat": num("latdegree"),
        "geomag": ham.get("geomagfield", ""), "noise": ham.get("signalnoise", ""),
        "muf": muf, "fof2": fof2,
        "elevation": round(elevation, 1) if elevation is not None else None,
        "is_day": is_day, "located": elevation is not None,
        "bands": _band_rows(ham, is_day, muf),
        "vhf": ham["vhf"],
        "verdict": verdict(sfi, k_index, a_index),
        "cached": False,
    }
    _cache["at"], _cache["data"] = now, data
    return data


def verdict(sfi, k, a):
    """One honest sentence about what tonight looks like."""
    if k >= 6 or a >= 30:
        return ("Geomagnetic storm in progress. Expect absorption and auroral "
                "flutter on the high bands and poor polar paths.")
    if k >= 4:
        return ("Unsettled field. Paths over high latitudes will be degraded; "
                "the low bands may be noisy.")
    if sfi >= 150 and k <= 3:
        return ("Strong flux with a quiet field - the high bands should be open "
                "and 10m/12m are worth checking.")
    if sfi >= 100:
        return ("Moderate flux, quiet field. 20m should be reliable; the higher "
                "bands open in daylight.")
    return ("Low flux. Expect the action on 40m and below, with 20m opening "
            "around daylight hours.")


# --- how good a band is, as a number ----------------------------------------
#
# A wall chart says Poor, Fair or Good for a group of bands, twice a day. That
# is enough to know whether to bother; it is not enough to decide whether to
# call CQ on SSB now or wait two hours and use CW, which is the decision an
# operator is actually making. So ELMER computes a number for one band at one
# moment, out of the three things that decide it and can be known here:
#
#   The band against the MUF. Above the maximum usable frequency a signal
#   goes through the F layer instead of coming back, so the band is shut. Just
#   under it is the sweet spot - the least absorption for the longest hop -
#   and well under it the path still works but every hop costs more.
#
#   D-layer absorption. The D layer exists only in daylight and absorbs in
#   proportion to roughly the inverse square of frequency, which is why 80m is
#   a local band at noon and a continental one at midnight.
#
#   The geomagnetic field. A disturbed field means absorption and flutter,
#   worst on paths near the poles, and a noisier low band.
#
# It is a teaching-grade model and says so wherever it is shown. It is not
# VOACAP: it knows nothing about your antenna, your power, the far end, or the
# path between you. What it is honest about is the shape of the day, and the
# shape of the day is what timing decisions are made on.

QUALITY = [(80, "Excellent"), (60, "Good"), (35, "Fair"), (15, "Poor"),
           (0, "Closed")]

# What a score is worth in practice. FT8 and CW get through where SSB will not
# - about 10 to 15 dB below it - so the same band is open for one and shut for
# the other, and saying which is the whole point of a number rather than a
# word.
MODES = [
    (60, "SSB, and anything below it"),
    (38, "CW and FT8 comfortably; SSB will be a struggle"),
    (18, "FT8 and CW only"),
    (0, "nothing much - the band is not open"),
]


def _pick(table, score):
    for floor, label in table:
        if score >= floor:
            return label
    return table[-1][1]


def band_score(mhz, muf, elevation, k_index=2.0):
    """0-100 for one band at one moment, with the reason in words.

    `elevation` is the sun's angle at the operator's QTH: negative is night,
    which is when the D layer is gone and the MUF is at its lowest.
    """
    muf = max(1.0, float(muf or 1.0))
    ratio = mhz / muf
    if ratio <= 1.0:
        # Best just under the MUF, tailing off as the band drops away from it.
        near = 1.0 - abs(ratio - 0.8) / 0.8
        score = 45.0 + 55.0 * max(0.0, near)
        why = (f"{mhz:g} MHz is {ratio:.2f} of the {muf:g} MHz MUF"
               + (" - about where the band works best" if 0.6 <= ratio <= 0.95
                  else ""))
    else:
        # Over the top: it does not fade out, it stops.
        # Not a cliff edge: MUF(3000) is a median for a long hop, and shorter
        # paths, sporadic E and a good day at the far end all live just over
        # the line. Past about a third above it, nothing does.
        score = max(0.0, 34.0 - 100.0 * (ratio - 1.0))
        why = (f"{mhz:g} MHz is above the {muf:g} MHz MUF - signals go through "
               "the F layer instead of coming back")

    sun = max(0.0, math.sin(math.radians(max(elevation, -90.0))))
    # Daytime D-layer absorption, heaviest on the lowest bands and gone by
    # about 10 MHz. The exponent is the textbook inverse-square softened for
    # the fact that this is a rating and not a link budget.
    absorb = 45.0 * (sun ** 0.6) * (3.5 / max(mhz, 1.0)) ** 1.6
    absorb = min(absorb, 55.0)
    if absorb > 6:
        why += ("; daylight D-layer absorption is what limits it"
                if mhz <= 10.1 else "; a little daytime absorption")

    storm = min(40.0, max(0.0, float(k_index or 0) - 2.0) * 7.0)
    if storm > 6:
        why += f"; K {k_index:g} means absorption and flutter, worst near the poles"

    score = max(0.0, min(100.0, score - absorb - storm))
    return {"score": round(score), "label": _pick(QUALITY, score),
            "modes": _pick(MODES, score), "why": why,
            "muf": round(muf, 1), "ratio": round(ratio, 2)}


# How far a measurement is allowed to drag the model. A sonde a few hundred
# miles away measuring twice what the model expects is telling the truth about
# the sky; one disagreeing by more than this is measuring a different sky, or
# is broken, and the curve it would produce is worse than the plain model.
ANCHOR_RANGE = (0.5, 2.0)


def muf_anchor(sfi, lat, lon, measured, when=None):
    """How far the model has to be scaled to meet a measured MUF, bounded.

    The factor is worked out once and used for every hour, so the level comes
    from the ionosonde and the shape from the sun - and, more to the point, so
    the meter that says how good the band is now and the strip that says how
    the day looks cannot contradict each other.
    """
    if not measured or lat is None:
        return 1.0
    when = when or datetime.now(timezone.utc)
    modelled, _ = estimate_muf(sfi, solar_elevation(lat, lon, when))
    if not modelled:
        return 1.0
    low, high = ANCHOR_RANGE
    return max(low, min(high, float(measured) / modelled))


def outlook(mhz, lat, lon, sfi, k_index=2.0, hours=24, start=None,
            muf_now=None, anchor=None):
    """The next 24 hours on one band, hour by hour.

    The sun's position is the one thing about tomorrow that is known exactly,
    and on HF it is most of the answer: it sets the MUF, and it switches the D
    layer on and off. So the flux and the field are held where they are now -
    they move slowly, and pretending to forecast them would be inventing
    numbers - and the sun is allowed to do what it is going to do anyway.

    When a measured MUF is passed in, the modelled curve is scaled to meet it
    at this hour, so the shape is the model's and the level is the ionosphere's.
    """
    start = (start or datetime.now(timezone.utc)).replace(minute=0, second=0,
                                                          microsecond=0)
    if anchor is None:
        anchor = muf_anchor(sfi, lat, lon, muf_now, start)
    out = []
    for step in range(hours + 1):
        when = start + timedelta(hours=step)
        elevation = solar_elevation(lat, lon, when)
        muf, fof2 = estimate_muf(sfi, elevation)
        muf = round(muf * anchor, 1)
        got = band_score(mhz, muf, elevation, k_index)
        got.update({"at": when.isoformat(), "hour": when.hour,
                    "elevation": round(elevation, 1), "fof2": round(fof2, 1),
                    "day": elevation > -6})
        out.append(got)
    return out


def windows(hours, floor=38):
    """When a band is worth using, said as times rather than as a graph.

    The graph shows the shape; this is the sentence somebody reads off it -
    the runs of hours at or above a usable score, in the order they happen.
    """
    runs, live = [], None
    for row in hours:
        if row["score"] >= floor:
            live = live or row
        elif live:
            runs.append((live, row))
            live = None
    if live:
        runs.append((live, hours[-1]))
    return [{"from": a["at"], "to": b["at"],
             "best": max(h["score"] for h in hours
                         if a["at"] <= h["at"] <= b["at"])}
            for a, b in runs]


INDICATORS = [
    ("sfi", "Solar Flux Index",
     "10.7 cm radio emission from the sun, a proxy for ionizing UV. Higher flux "
     "means a denser F layer, a higher critical frequency, and higher usable "
     "frequencies.", "Below 70 is quiet; above 150 opens the high bands."),
    ("k_index", "Planetary K Index",
     "A 0-9 log scale of geomagnetic disturbance over three hours. Disturbance "
     "means absorption and auroral flutter, especially on polar paths.",
     "0-2 quiet, 3-4 unsettled, 5+ storm."),
    ("a_index", "A Index",
     "A linear daily average of geomagnetic activity derived from the K values.",
     "Under 10 is quiet; over 30 means a disturbed day."),
    ("sunspots", "Sunspot Number",
     "Count of visible spots. It tracks the 11-year cycle that drives long-term "
     "HF conditions.", "Tracks the solar cycle rather than today's opening."),
    ("muf", "Estimated MUF",
     "Maximum usable frequency for a long single-hop path. Above it, signals "
     "penetrate the F layer instead of refracting back to earth.",
     "Work below the MUF; the best band is usually just under it."),
    ("fof2", "Estimated foF2",
     "Critical frequency of the F2 layer - the highest frequency reflected "
     "straight up. MUF is roughly foF2 times the secant of the incidence angle.",
     "The vertical-incidence limit that sets the MUF."),
]

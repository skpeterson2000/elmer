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

from . import celestial, ionosonde

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

# Keyed on where as well as when. It always held the sun angle for one QTH;
# now it holds that QTH's ionosonde calibration too, and handing those to a
# second location would put back exactly the disagreement this removes.
# A tenth of a degree is about 11 km - far finer than anything here resolves.
_cache = {"at": None, "data": None, "where": None}


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
    """The sun's angle above the horizon, in degrees.

    Handed to `celestial`, which computes it properly. This used to carry its
    own low-precision series - Spencer's, good to about 26 arcminutes of
    declination - because a band prediction does not care. Then the sextant
    tool needed a sun accurate enough to navigate by, and having two suns in
    one program, one of them knowingly wrong, is not a thing to keep.

    The swap moves this by at most 0.445 degrees, which moves modelled foF2 by
    0.02 MHz against a model whose own error is 1.11, so the constants fitted
    below still stand. It costs about five microseconds a call.
    """
    alt, _ = celestial.altitude_azimuth(
        lat, lon, when or datetime.now(timezone.utc))
    return alt


# --- what the model says the ionosphere is doing -----------------------------
#
#   foF2 = base(flux) x solar(sun angle) x latitude(distance from the tropics)
#
# The shape is Chapman-ish; the constants were fitted to the GIRO/Digisonde
# network - 27 stations spanning 140 degrees of sun angle and 105 of latitude -
# by least squares on log foF2, then checked leave-one-out so they describe the
# ionosphere rather than the evening they were taken from:
#
#   mean absolute error      1.43 -> 1.11 MHz    (out of sample)
#   within 25% of measured   11/27 -> 18/27
#   median bias              0.75x -> 1.00x
#
# What this replaces was flat after dark. The old day term was sin(elevation)
# raised to a power, which is exactly zero at every negative angle, so the
# whole night collapsed to a single number - the same one for every latitude,
# every season and every hour after sunset. It was also a quarter low, and that
# is what put 20m above the MUF at midnight while the wall chart beside it
# still said Fair.
#
# It remains a model of the average ionosphere rather than of yours. What
# closes that gap is `calibration` below, which measures how wrong it is now.

FOF2_FLUX = (7.50, 0.0427)    # foF2 overhead at the equator: floor, and per SFI
FOF2_NIGHT = 0.49             # the share of that which survives the night
FOF2_POWER = 2.57             # how sharply the layer follows the sun by day
FOF2_LATITUDE = 0.72          # how much of it has gone by the poles
FOF2_TROPICS = 20.0           # ...counted from here, not from the equator
ASSUMED_LATITUDE = 45.0       # no QTH: mid-latitudes is the least wrong guess

# foF2 to MUF(3000): the secant of the incidence angle for a 3000 km hop. Every
# sonde reports its own as M(3000)F2, and it is not the 3.2 this used to
# assume - across the network on one evening it ran 2.48 to 3.66, median 2.90.
# When stations are in reach their own figures are used; this is the fallback.
M3000_DEFAULT = 2.9


def _fof2(sfi, elevation, lat=None):
    """Critical frequency of the F2 layer, unrounded. See the note above."""
    base = FOF2_FLUX[0] + FOF2_FLUX[1] * max(0.0, sfi - 60.0)
    # sin(elevation) mapped onto 0-1, so the term goes on varying after sunset
    # instead of clipping to zero the moment the sun touches the horizon.
    drive = max(0.0, min(1.0, 0.5 * (1.0 + math.sin(math.radians(elevation)))))
    solar = FOF2_NIGHT + (1.0 - FOF2_NIGHT) * drive ** FOF2_POWER
    away = max(0.0, abs(ASSUMED_LATITUDE if lat is None else lat) - FOF2_TROPICS)
    return base * solar * max(0.25, 1.0 - FOF2_LATITUDE * away / 70.0)


def levels(sfi, elevation, lat=None, m3000=None, anchor=1.0):
    """foF2 and MUF for one place and one moment, as they will be shown.

    The only place these two numbers are made. Everything that displays either
    of them comes through here, which is what stops the propagation page, the
    band plan and the Lab from each arriving at their own answer.

    The MUF is worked out from the *rounded* foF2 rather than the unrounded
    one, so the pair multiplies out. They appear beside each other, and an
    operator who checks them with a calculator should find that they agree; a
    twentieth of a megahertz of precision is a fair price for that, being far
    inside what the model is right to anyway.
    """
    fof2 = round(_fof2(sfi, elevation, lat) * anchor, 1)
    return round(fof2 * (m3000 or M3000_DEFAULT), 1), fof2


def estimate_muf(sfi, elevation, lat=None, m3000=None):
    """A teaching-grade MUF(3000) and foF2 from flux, sun angle and latitude.

    Not a substitute for an ionosonde - it exists so the dashboard can show how
    critical frequency tracks the sun, which is the point the pools test. Where
    a sonde is in reach, `calibration` scales this to meet what it measured.
    """
    return levels(sfi, elevation, lat, m3000)


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
    where = (round(lat, 1), round(lon, 1)) if lat is not None else None
    if (not force and _cache["at"] and _cache["where"] == where
            and now - _cache["at"] < timedelta(minutes=CACHE_MINUTES)):
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
    # With no QTH there is no sun angle, and this used to take a daytime one
    # for the MUF and a night-time one for everything that read it - a noon MUF
    # scored against midnight absorption, which said 20m was open at 82/100 in
    # the small hours. One assumed angle now, used for both.
    assumed = elevation if elevation is not None else (25.0 if is_day else -25.0)

    # What the ionosonde network makes of the model, if it can see where you
    # are. This is what keeps the three pages agreeing: the propagation page,
    # the band plan and the lab all read the numbers below, so correcting them
    # here corrects them everywhere rather than in one view out of three.
    cal = calibration(sfi, lat, lon)
    muf, fof2 = levels(sfi, assumed, lat, cal and cal["m3000"],
                       cal["factor"] if cal else 1.0)

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
        "muf_source": cal["source"] if cal else "modelled",
        "calibration": cal,
        "elevation": round(elevation, 1) if elevation is not None else None,
        # The angle actually used, which is the assumed one when there is no
        # QTH. Anything deriving its own would drift away from these numbers.
        "elevation_used": round(assumed, 1),
        "is_day": is_day, "located": elevation is not None,
        "bands": _band_rows(ham, is_day, muf),
        "vhf": ham["vhf"],
        "verdict": verdict(sfi, k_index, a_index),
        "cached": False,
    }
    _cache["at"], _cache["data"], _cache["where"] = now, data, where
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

# --- where the absorbing layer actually is -----------------------------------
#
# A point 80 km up does not lose the sun when the ground does. It stays lit
# until the sun is acos(R/(R+h)) below the horizon, and for the D layer that is
# about nine degrees; for the F2 peak at 300 km it is about seventeen.
#
#     D layer    70-90 km    lit to about  -8.5 to -9.6 degrees
#     F2 peak       300 km   lit to about      -17.2 degrees
#
# Between those two the D layer is dark and the F2 is still lit: absorption
# gone, ionisation still up. That is the grey line, it is plain geometry, and
# it lasts the half hour or so the effect is known to last.
#
# The term this replaces used max(0, sin(elevation)) - the sun as the *ground*
# sees it - so absorption switched off at the geometric horizon, nine degrees
# early and all at once. The evening went from full daytime absorption to none
# between one sample and the next, and the window collapsed to an instant.
#
# This is the local half of the problem. It gets the shape of your own evening
# right; it still cannot tell you that the path to a station on the far side of
# the terminator is open, because band_score is handed one sun angle - yours -
# and a path has two ends.
EARTH_RADIUS_KM = 6371.0
D_LAYER_KM = 80.0
D_LAYER_DIP = math.degrees(math.acos(EARTH_RADIUS_KM /
                                     (EARTH_RADIUS_KM + D_LAYER_KM)))

# Absorption at the top of the scale. Lowered from 45 to hold midday where it
# was: shifting the driver by the dip raises it everywhere, and this change is
# meant to be about the terminator rather than a quiet re-tuning of noon.
# 41.5 x sin(45 + dip)^0.6 == 45 x sin(45)^0.6.
D_ABSORPTION = 41.5

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

    # The sun as the D layer sees it, not as the ground does. See the note
    # above: the layer is 80 km up and keeps its daylight about nine degrees
    # longer than you keep yours.
    lit = max(-90.0, min(90.0, elevation + D_LAYER_DIP))
    sun = max(0.0, math.sin(math.radians(lit)))
    # Absorption is heaviest on the lowest bands and gone by about 10 MHz. The
    # exponent is the textbook inverse-square softened for the fact that this
    # is a rating and not a link budget.
    absorb = D_ABSORPTION * (sun ** 0.6) * (3.5 / max(mhz, 1.0)) ** 1.6
    absorb = min(absorb, 55.0)
    if absorb > 6:
        if elevation < 0:
            why += ("; the sun has set here but not on the D layer 80 km up, "
                    "which is still absorbing")
        else:
            why += ("; daylight D-layer absorption is what limits it"
                    if mhz <= 10.1 else "; a little daytime absorption")

    storm = min(40.0, max(0.0, float(k_index or 0) - 2.0) * 7.0)
    if storm > 6:
        why += f"; K {k_index:g} means absorption and flutter, worst near the poles"

    score = max(0.0, min(100.0, score - absorb - storm))
    return {"score": round(score), "label": _pick(QUALITY, score),
            "modes": _pick(MODES, score), "why": why,
            "muf": round(muf, 1), "ratio": round(ratio, 2)}


# --- anchoring the model to what is being measured ---------------------------
#
# A sonde a long way off is not measuring your sky. But it is measuring how
# wrong the model is, and that travels a great deal further than the ionosphere
# does - provided the reading is turned into an error before it is carried
# anywhere.
#
# So each station is compared against what the model would have said at *that
# station's* own sun angle and latitude. What is left over is dimensionless:
# how far out the model is, right now. That is the thing carried to the QTH and
# applied to the model there.
#
# This is what used to be wrong. The old anchor divided a reading taken in
# Idaho by the model evaluated in Minnesota, so "the model is 40% low" and
# "Idaho's sun is eleven degrees higher than mine" came out as one number and
# were applied as though they were the first. That conflation is the reason the
# radius had to be 2000 km - further out, the sun-angle error swamped the
# calibration it was buried in - and with around twenty stations reporting
# worldwide, most operators fell outside it and were given no correction at all.
#
# Corrected for sun angle, distance costs much less. So stations vote out to
# CALIBRATION_KM with a weight that falls away smoothly, rather than being
# accepted or refused at a line, and the vote is a weighted median so that one
# station whose autoscaler lost the trace cannot drag the answer.

CALIBRATION_KM = 5000.0        # past this it is honestly a different ionosphere
CALIBRATION_HALF_KM = 1500.0   # the distance at which a station's vote halves

# How far a measurement is allowed to drag the model. A sonde measuring twice
# what the model expects is telling the truth about the sky; a factor beyond
# this is a broken station or a different planet, and the curve it would
# produce is worse than the plain model.
ANCHOR_RANGE = (0.5, 2.0)


def _weighted_median(pairs):
    """The value with half the weight lying either side of it."""
    if not pairs:
        return None
    pairs = sorted(pairs)
    half = sum(weight for _, weight in pairs) / 2.0
    seen = 0.0
    for value, weight in pairs:
        seen += weight
        if seen >= half:
            return value
    return pairs[-1][0]


def calibration(sfi, lat, lon, when=None, sondes=None):
    """How far out the model is right now, measured where it can be measured.

    Returns None when there is nothing in reach to measure against - which is
    the honest answer. The model then stands on its own, and says so.
    """
    if lat is None:
        return None
    if sondes is None:
        try:
            sondes = ionosonde.stations()
        except Exception:                        # network, cache, malformed
            sondes = None
    if not sondes:
        return None
    when = when or datetime.now(timezone.utc)
    votes, factors, nearest, closest = [], [], None, None
    for station in sondes:
        km = ionosonde.great_circle(lat, lon, station["lat"], station["lon"])
        if km > CALIBRATION_KM:
            continue
        modelled = _fof2(sfi, solar_elevation(station["lat"], station["lon"], when),
                         station["lat"])
        if modelled <= 0:
            continue
        weight = 1.0 / (1.0 + (km / CALIBRATION_HALF_KM) ** 2)
        votes.append((station["fof2"] / modelled, weight))
        if station.get("m3000"):
            factors.append((station["m3000"], weight))
        if nearest is None or km < nearest:
            nearest, closest = km, station
    if not votes:
        return None
    low, high = ANCHOR_RANGE
    raw = _weighted_median(votes)
    factor = max(low, min(high, raw))
    return {
        "factor": round(factor, 3),
        "m3000": round(_weighted_median(factors) or M3000_DEFAULT, 2),
        "stations": len(votes),
        "nearest_km": round(nearest),
        "nearest": closest["name"],
        "age_minutes": closest["age_minutes"],
        "measured_fof2": closest["fof2"],
        "source": ("bounded" if abs(raw - factor) > 1e-9
                   else "measured" if nearest <= CALIBRATION_HALF_KM
                   else "regional"),
    }


def muf_anchor(sfi, lat, lon, measured, when=None, m3000=None):
    """How far the model has to be scaled to meet one measured MUF, bounded.

    The single-station form of `calibration`, for when a MUF has been handed in
    directly rather than looked up. The factor is worked out once and used for
    every hour, so the level comes from the ionosonde and the shape from the
    sun - and so the meter saying how good the band is now and the strip saying
    how the day looks cannot contradict each other.
    """
    if not measured or lat is None:
        return 1.0
    when = when or datetime.now(timezone.utc)
    modelled, _ = estimate_muf(sfi, solar_elevation(lat, lon, when), lat, m3000)
    if not modelled:
        return 1.0
    low, high = ANCHOR_RANGE
    return max(low, min(high, float(measured) / modelled))


def outlook(mhz, lat, lon, sfi, k_index=2.0, hours=24, start=None,
            muf_now=None, anchor=None, m3000=None):
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
        anchor = muf_anchor(sfi, lat, lon, muf_now, start, m3000)
    out = []
    for step in range(hours + 1):
        when = start + timedelta(hours=step)
        elevation = solar_elevation(lat, lon, when)
        muf, fof2 = levels(sfi, elevation, lat, m3000, anchor)
        got = band_score(mhz, muf, elevation, k_index)
        got.update({"at": when.isoformat(), "hour": when.hour,
                    "elevation": round(elevation, 1), "fof2": fof2,
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
    ("muf", "MUF",
     "Maximum usable frequency for a long single-hop path. Above it, signals "
     "penetrate the F layer instead of refracting back to earth. Modelled from "
     "flux, sun angle and latitude, then scaled to meet the ionosondes in "
     "range - so the level is measured even though the shape is modelled.",
     "Work below the MUF; the best band is usually just under it."),
    ("fof2", "foF2",
     "Critical frequency of the F2 layer - the highest frequency reflected "
     "straight up. MUF is foF2 times M(3000)F2, the secant of the incidence "
     "angle for a 3000 km hop, which each sonde measures for itself and which "
     "runs about 2.5 to 3.7.",
     "The vertical-incidence limit that sets the MUF."),
]

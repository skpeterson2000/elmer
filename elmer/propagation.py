"""Live space-weather snapshot, translated into band-by-band expectations.

Two public sources, both keyless:

* N0NBH's solar XML (hamqsl.com) - the numbers and the day/night band ratings
  that every shack wall chart uses;
* NOAA SWPC JSON - authoritative planetary K index and 10.7 cm flux, used to
  cross-check and to fill in when the XML is stale.

Everything is cached so opening the dashboard repeatedly does not hammer either
service.
"""
import functools
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

# The layer does not follow the sun, it chases it. Production switches on with
# sunlight and stops with it, but loss at F2 heights is slow - recombination
# there runs in tens of minutes to hours - so electron density goes on building
# after the sun starts down, and foF2 peaks in the early afternoon rather than
# at local noon. Every sonde in the network shows it.
#
# Modelled as what it is: production put through the layer's own inertia. The
# drive is averaged over the hours behind it with an exponential weight, which
# is the first-order form of dN/dt = production - N/tau and is the standard way
# to say "this responds, but not at once".
#
# A causal average of a symmetric bump peaks after the bump does, which is the
# whole effect and is why an earlier draft of this did not work: taking the
# greater of the drive now and the drive two hours ago slows the evening decay
# but leaves the maximum exactly at noon, and the flat top it appears to
# produce is a tenth of a megahertz of rounding rather than the ionosphere.
#
# Two hours is a middle value for the time constant. The real figure varies
# with season, latitude and longitude sector, and one number cannot carry that
# - this is an approximation and is labelled as one. The direction is not in
# doubt: every sonde in the network shows the afternoon maximum.
#
# One honest cost. The constants below were least-squares fitted against the
# *unlagged* drive, so they are no longer the optimum for this shape: the
# smoothed peak comes out about 3% lower than the fitted one, the morning
# perhaps 8% lower and the evening as much higher. That is well inside the
# model's own 1.11 MHz error, and it is systematic rather than random, which
# is worth saying out loud. They want refitting against the network the next
# time that dataset is to hand. Where a sonde is in reach it does not arise:
# `calibration` measures the model against what was actually observed and
# scales it, and it compares like with like because the lag is applied on both
# sides of that comparison.
F2_LAG_HOURS = 2.0
F2_LAG_STEP = 0.5             # how finely the hours behind are sampled
F2_LAG_SPAN = 6.0             # how far back is worth sampling at all

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

# What the ionosphere has ever actually been observed doing. The model is a
# fitted curve and the anchor is a multiplier, and neither of them knows that:
# left alone they will assert a critical frequency the earth has never had.
# Stacked up - a high flux, an overhead sun, an equatorial latitude, and a
# sonde correction of two - this could reach 130 MHz, which is not an
# ionospheric prediction, it is arithmetic that got away.
#
# foF2 runs from about 1 MHz on a polar winter night to 15 or 16 at the crests
# of the equatorial anomaly on a solar-maximum afternoon. It does not go
# outside that, so neither does this. At 16 MHz and the highest M factor the
# network reports, the ceiling on MUF(3000) works out near 59 MHz - which
# correctly still allows the rare 6 m F2 opening rather than legislating it
# away, and forbids the rest.
FOF2_OBSERVED = (1.0, 16.0)


def _bounded(fof2):
    """Keep a critical frequency inside what has ever been measured."""
    low, high = FOF2_OBSERVED
    return max(low, min(high, fof2))


def _drive(elevation):
    """The sun's grip on the layer, 0 to 1.

    sin(elevation) mapped onto 0-1, so the term goes on varying after sunset
    instead of clipping to zero the moment the sun touches the horizon.
    """
    return max(0.0, min(1.0, 0.5 * (1.0 + math.sin(math.radians(elevation)))))


# Thirteen sun positions per call, and the outlook asks for the same twenty-five
# hours once per band. Cached, that is 25 computations instead of 275 - which
# on a Pi is the difference between 48 ms and single figures for the strip
# behind the propagation page. Small enough that it costs nothing to hold, and
# the keys age out on their own as the hours move.
@functools.lru_cache(maxsize=512)
def f2_drive(lat, lon, when):
    """How hard the layer is being driven, allowing for its own inertia.

    The sun over the hours behind this one, weighted so that the recent hours
    count for most and six hours ago counts for almost nothing. See the note
    above F2_LAG_HOURS for why it is the hours behind rather than this one.
    """
    total = weight = 0.0
    steps = int(F2_LAG_SPAN / F2_LAG_STEP) + 1
    for step in range(steps):
        hours = step * F2_LAG_STEP
        share = math.exp(-hours / F2_LAG_HOURS)
        total += share * _drive(
            solar_elevation(lat, lon, when - timedelta(hours=hours)))
        weight += share
    return total / weight if weight else 0.0


def _fof2(sfi, elevation, lat=None, drive=None):
    """Critical frequency of the F2 layer, unrounded. See the note above.

    `drive` is the layer's own idea of how sunlit it is, from `f2_drive`, for
    callers that know the time and the place and can work it out. Without it
    the layer follows the sun exactly, which is what this did before and is
    still the right answer when all anybody has is an angle.
    """
    base = FOF2_FLUX[0] + FOF2_FLUX[1] * max(0.0, sfi - 60.0)
    if drive is None:
        drive = _drive(elevation)
    solar = FOF2_NIGHT + (1.0 - FOF2_NIGHT) * drive ** FOF2_POWER
    away = max(0.0, abs(ASSUMED_LATITUDE if lat is None else lat) - FOF2_TROPICS)
    return _bounded(base * solar * max(0.25, 1.0 - FOF2_LATITUDE * away / 70.0))


def levels(sfi, elevation, lat=None, m3000=None, anchor=1.0, drive=None):
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
    # Bounded again after the anchor: a measurement can sharpen the model, but
    # a multiplier applied to it must not carry it somewhere the ionosphere has
    # never been.
    fof2 = round(_bounded(_fof2(sfi, elevation, lat, drive) * anchor), 1)
    return round(fof2 * (m3000 or M3000_DEFAULT), 1), fof2


def estimate_muf(sfi, elevation, lat=None, m3000=None):
    """A teaching-grade MUF(3000) and foF2 from flux, sun angle and latitude.

    Not a substitute for an ionosonde - it exists so the dashboard can show how
    critical frequency tracks the sun, which is the point the pools test. Where
    a sonde is in reach, `calibration` scales this to meet what it measured.
    """
    return levels(sfi, elevation, lat, m3000)


def _band_rows(ham, regime, muf):
    period = "day" if regime == "lit" else "night"
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
        elif regime == "twilight" and freq <= 7.0:
            note = ("the sun will not clear the D layer tonight - no grey "
                    "line at this latitude in this season, and absorption "
                    "never reaches zero")
        elif regime == "grey" and freq <= 7.0:
            note = ("grey line - the sun is down here but not on the D layer, "
                    "so absorption is collapsing and the low bands are opening")
        elif regime == "dark" and freq >= 21:
            note = "high bands normally close after dark"
        elif regime == "lit" and freq <= 3.5:
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
        regime = sun_regime(elevation, lat, now)
    else:
        # No QTH set: the machine's own clock is the best guess we have, and a
        # clock cannot see a terminator. Answering only "lit" or "dark" is
        # honest about that - claiming the middle state with no position would
        # be inventing the one thing this change exists to stop inventing.
        regime = "lit" if 6 <= datetime.now().hour < 18 else "dark"
    # The wall chart has a day column and a night column and always will. Grey
    # reads off the night one: that column is about the absorber, and by then
    # the absorber has gone.
    is_day = regime == "lit"
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
    # Only where there is a place and therefore a real sun: with no QTH the
    # assumed angle is a stand-in for a sky nobody has, and lagging a stand-in
    # by two hours would be arithmetic on a guess.
    driven = (f2_drive(lat, lon, now)
              if lat is not None and elevation is not None else None)
    muf, fof2 = levels(sfi, assumed, lat, cal and cal["m3000"],
                       cal["factor"] if cal else 1.0, drive=driven)

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
        # The measured layer height, carried here for the same reason foF2 is:
        # the propagation page, the band plan, the hop tool and the path tool
        # all read this, so it is corrected once rather than in four views.
        "hmf2": (cal or {}).get("measured_hmf2") or HMF2_DEFAULT,
        "hmf2_measured": bool((cal or {}).get("measured_hmf2")),
        "muf_source": cal["source"] if cal else "modelled",
        "calibration": cal,
        "elevation": round(elevation, 1) if elevation is not None else None,
        # The angle actually used, which is the assumed one when there is no
        # QTH. Anything deriving its own would drift away from these numbers.
        "elevation_used": round(assumed, 1),
        "regime": regime,
        # Kept because a two-column wall chart still needs one bit, and three
        # pages read this. It is now "lit", not "not dark".
        "is_day": is_day, "located": elevation is not None,
        "bands": _band_rows(ham, regime, muf),
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

def night_floor(lat, when):
    """The sun's elevation at local solar midnight - the deepest it will get.

    Closed form: at midnight the hour angle is 180 degrees, so cos(lha) is -1
    and the spherical triangle collapses to asin(-cos(lat + dec)). Checked
    against a minute-by-minute scan at Anchorage and Fairbanks on the solstice:
    identical to two decimal places, and it costs one trig call instead of
    1440 solar positions.
    """
    dec = celestial.sun_position(when)["dec"]
    return math.degrees(math.asin(
        max(-1.0, min(1.0, -math.cos(math.radians(lat + dec))))))


def day_ceiling(lat, when):
    """And the highest, at local noon. Below zero means the sun never rises."""
    dec = celestial.sun_position(when)["dec"]
    return 90.0 - abs(lat - dec)


def sun_regime(elevation, lat=None, when=None):
    """Which of four states the sky overhead is in, from the sun's angle.

    "lit"  - the sun is up and the D layer is absorbing.
    "grey" - the sun has set on the ground but not yet on the D layer 80 km up.
             Absorption is collapsing while the F layer stays ionised, and that
             gap is the grey line. It ends at the D layer's own horizon.
    "dark" - the D layer is wholly in shadow. Absorption is already zero and
             has been for some minutes; nothing further happens to it.

    "twilight" - the sun is down and the D layer will not clear tonight, or it
             is up and never rises. There is no grey line here because there is
             no terminator passage: at Anchorage on the solstice the sun bottoms
             out 5.3 degrees down, the layer 80 km up keeps its light all night,
             and 80 m absorption never falls below 8 - a third of its noon
             value. Reported without the two states given lat and `when`, that
             stretch was called "grey line" for five hours, which is the summer
             at high latitude being sold as the best hour of the day.

    The upper edge is the ground terminator and the lower one is the layer
    height, and the interval between them is not a convention - it is exactly
    where `band_score`'s own absorption term falls from a third of its noon
    value to nothing. On 8 September at 46.6 N: 13.3 at sunset, 6.7 a quarter
    of an hour later, 0.0 by the time the sun is nine degrees down.

    What this replaces hung the lower edge on the F2 peak's dip - 17 degrees,
    the angle at which 300 km stops being sunlit - on the reasoning that the
    reflector outlasts the absorber. It does, but not for that reason: F2
    ionisation survives the night by slow recombination, not by staying lit,
    which is why 80 m works at two in the morning with the F layer long dark.
    Hanging the window on illumination put it between 9 and 17 degrees down -
    an hour that began after the absorption had already finished going. It
    named the grey line half an hour after the grey line, and at 50 N in June,
    where the sun never reaches 17 degrees down at all, it named it for five
    hours straight.

    Nothing here is a new model. `_fof2` and `band_score` already ramp
    continuously through all three states; this exists so that the parts which
    have to name a state - a wall chart with two columns, a strip of coloured
    hours, a sentence of advice - name the same one, on the same evidence.
    """
    if elevation is None:
        return None
    if elevation >= 0.0:
        return "lit"
    # A grey line is a terminator passage. Where the sun neither sets on the D
    # layer nor rises at all, there is not one to name, and the honest answer
    # is that this is twilight - which is a real state of its own at latitude,
    # and not the same claim. Without a position this cannot be known, so the
    # geometry is reported as it stands.
    crosses = (lat is None or when is None
               or (night_floor(lat, when) <= -D_LAYER_DIP
                   and day_ceiling(lat, when) >= 0.0))
    if elevation >= -D_LAYER_DIP:
        return "grey" if crosses else "twilight"
    return "dark"

# --- how far inside the auroral oval the operator is -------------------------
#
# `band_score` has always printed "worst near the poles" beside its K-index
# penalty and then applied the same number at every latitude. The words were
# right and the arithmetic was not: a K of 5 in Minnesota is an unsettled
# afternoon, and a K of 5 at Fairbanks is the oval overhead and the polar paths
# shut. Nothing in the score could tell those apart.
#
# What decides it is geomagnetic latitude, not geographic, and the two are far
# apart over North America because the pole is over Arctic Canada rather than
# the geographic one. Pequot Lakes is 46.6 N and 55 geomagnetic; Fairbanks is
# 64.8 and 65.7. A dipole is enough here - checked against published corrected
# geomagnetic latitudes, it lands within a degree at both - and the alternative
# is shipping a field model to scale one penalty.
GEOMAG_POLE = (80.7, -72.7)         # IGRF dipole north pole, near enough

# Where the existing constant was fitted. N0NBH's ratings are aimed at
# mid-latitude North America and Europe, which is about 55 geomagnetic, so the
# factor is 1.0 there and this change moves nobody who was already right.
AURORAL_REF = 55.0
# The quiet equatorward edge of the oval. Superseded by the observed boundary
# when the feed reports one, which is the whole point of it being in the feed.
AURORAL_EDGE = 65.0
AURORAL_MAX = 2.5


def geomagnetic_latitude(lat, lon):
    """Latitude measured from the magnetic pole, which is what aurora obeys."""
    pole_lat, pole_lon = GEOMAG_POLE
    phi, phi_p = math.radians(lat), math.radians(pole_lat)
    d_lon = math.radians(lon - pole_lon)
    return math.degrees(math.asin(max(-1.0, min(1.0,
        math.sin(phi) * math.sin(phi_p)
        + math.cos(phi) * math.cos(phi_p) * math.cos(d_lon)))))


def auroral_factor(geomag_lat, boundary=None):
    """How much harder a disturbed field bites here than at mid-latitudes.

    1.0 at the latitude the K-index penalty was fitted for, falling to 0.5 in
    the tropics where a geomagnetic storm is somebody else's problem, and
    doubling at the oval's edge. It scales the disturbance rather than adding
    absorption of its own: at K 2 and below the field is quiet and this
    multiplies nothing, which is the conservative reading and keeps the model
    from inventing an aurora on a calm day.
    """
    if geomag_lat is None:
        return 1.0
    edge = float(boundary) if boundary else AURORAL_EDGE
    edge = max(AURORAL_REF + 5.0, min(75.0, edge))
    g = abs(geomag_lat)
    if g <= 30.0:
        return 0.5
    if g <= AURORAL_REF:
        return 0.5 + 0.5 * (g - 30.0) / (AURORAL_REF - 30.0)
    if g <= edge:
        return 1.0 + (g - AURORAL_REF) / (edge - AURORAL_REF)
    return min(AURORAL_MAX, 2.0 + 0.5 * (g - edge) / 10.0)


# Absorption at the top of the scale, for the lowest band under a noon sun.
#
# It was 41.5, and at 41.5 a 7 MHz signal taking a full hop through the D
# layer at its thickest lost thirteen points and 40 m read Good, 63/100, at
# noon - the same green as midnight. Every operator knows better: 40 m at
# midday is a regional band, and anything further is CW and FT8 work, not
# SSB. 80 m read Poor at noon when for a long hop it is simply shut. The
# frequency law is unchanged - the D layer's bill falls as roughly 1/f^1.6
# here, a shade softer than the textbook square - so the scale is what was
# wrong, by about a factor of two. At 80: 160 m and 80 m are closed for a
# full hop at noon, 60 m is Poor, 40 m is Fair, 30 m is Good, 20 m is
# untouched - which is the day as it is worked.
D_ABSORPTION = 80.0
D_ABSORPTION_CAP = 70.0        # the most any band can be charged

# How much of the "far below the MUF" penalty comes off once the D layer has
# gone. That penalty and `D_ABSORPTION` are two descriptions of the same loss,
# and after dark only one of them correctly falls to nothing - so without this
# the low bands are charged twice for a layer that is not there, and 80 m
# reads "Good" through the hours it is at its best.
#
# Not 1.0. Being well under the MUF still is not the sweet spot: below the LUF
# nothing works at any hour, and the lowest bands stay noisy after dark
# whatever the ionosphere is doing. What this buys 80 m on a quiet night is
# the difference between Good and Excellent, which is where it belongs.
NIGHT_RELIEF = 0.7

# The shape of a band's score against the MUF, as fractions of it. The peak is
# where the optimum working frequency sits - the FOT, about 0.85 of MUF(3000)
# in the textbooks; 0.8 here, where this scale has always put it. At the MUF
# itself a full hop works about half the time, so the score is half its peak
# there rather than either side of a cliff; a third above, nothing works.
MUF_PEAK = 0.8
MUF_AT_LINE = 50.0            # the score at the MUF itself: half the peak
MUF_OVER_LIMIT = 4.0 / 3.0    # ratio past which the band is simply shut

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


# What to assume when nobody has measured it. The F2 layer is nearer 270 km by
# day and 330 at night, so a single figure is a compromise either way - it is
# here to be replaced by a reading, not to be relied on.
HMF2_DEFAULT = 300.0


def skip_km(mhz, fof2, hmf2=HMF2_DEFAULT):
    """The nearest station this band can reach. 0 means it reaches everywhere.

    None means nothing comes back at any angle. Below the critical frequency a
    signal returns even from straight up, so there is no skip zone at all;
    above it the steepest ray that still returns lands some way out, and
    everything inside that is unreachable however loud you are.
    """
    from . import patterns             # imported here: patterns has no need of us
    if not fof2 or mhz <= 0:
        return 0.0
    steepest = patterns._max_takeoff(mhz, fof2, hmf2)
    if steepest is None:
        return None
    if steepest >= 90.0:
        return 0.0
    return patterns._hop_km(steepest, hmf2)


# The shallowest ray anybody actually gets away, which sets how far one hop
# reaches. Three degrees is generous for a wire and about right for a beam on a
# hill; below that the ground in front of the antenna is in the way whatever
# the ionosphere is doing.
LOWEST_TAKEOFF_DEG = 3.0

# Past this, a signal that is below the critical frequency is not doing NVIS
# any more - it is taking an ordinary low-angle hop, and calling it "straight
# up and back" at fifteen hundred kilometres would be wrong about the geometry
# even though the band does carry it.
NVIS_REACH_KM = 600.0


def one_hop_limit_km(hmf2=HMF2_DEFAULT):
    """The furthest a single hop reaches off a layer at this height."""
    from . import patterns
    return patterns._hop_km(LOWEST_TAKEOFF_DEG, hmf2)


def path_bands(km, fof2=None, hmf2=HMF2_DEFAULT, elevation=0.0,
               k_index=2.0,
               muf=None, watts=100.0):
    """Which bands could carry a contact over this distance, right now.

    The line-of-sight tool answers a different question and answers it well:
    whether two antennas can see each other. When they cannot - and past about
    fifty miles they never can - the contact is not off, it has moved to the
    ionosphere, and the operator is owed the second half of the answer rather
    than a verdict of "no".

    Three ways a band can carry a path, and they are not alternatives so much
    as different distances:

    * **Ground wave** hugs the surface and dies off fast, faster the higher the
      frequency. It is the only thing that works inside the skip zone of the
      band you are on.
    * **Straight up and back** - NVIS - covers everything out to a few hundred
      miles with no hole in the middle, and works only below the critical
      frequency.
    * **One hop** off the F2 layer lands somewhere between the near edge of the
      skip zone and the shallowest ray anybody gets away. Inside that near edge
      the band is deaf however loud you are.

    A band is reported as carrying the path when the distance falls between the
    nearest it reaches and the furthest, or when ground wave alone covers it.
    """
    from . import groundwave

    km = max(0.0, float(km or 0.0))
    far = one_hop_limit_km(hmf2)
    out = []
    # No critical frequency in hand is not the same as a sky that is wide
    # open, and skip_km() answers 0 for both - "reaches everywhere". Taken at
    # face value that would have this tool promising an overhead contact on
    # every low band whenever the ionosonde network was unreachable, which is
    # exactly when nobody can check it.
    blind = not fof2
    for name, mhz, _group in BANDS:
        skip = None if blind else skip_km(mhz, fof2, hmf2)
        ground = groundwave.describe(mhz, watts=watts)
        ground_km = ground.get("km") or 0.0
        by_ground = ground_km >= km
        if skip is None:
            # Nothing comes back at any angle: the sky is shut to this band.
            sky, how = False, None
        elif skip <= 0:
            # Below the critical frequency: it returns at every angle, so the
            # only question is how far one hop carries.
            sky = km <= far
            how = ("straight up and back" if km <= NVIS_REACH_KM else "one hop")
        else:
            sky, how = (skip <= km <= far), "one hop"
        # Beyond one hop is not beyond reach. Two hops is ordinary working,
        # and saying "nothing gets there" about a path people make every day
        # would be the tool at its least useful.
        hops = 1
        if not sky and skip is not None and km > far:
            hops = int(math.ceil(km / far))
            leg = km / hops
            if (skip <= 0 and leg <= far) or (skip is not None and skip <= leg <= far):
                sky, how = True, "%d hops" % hops
        row = {
            "band": name, "mhz": mhz,
            "works": bool(sky or by_ground),
            "how": ("ground wave" if by_ground and not sky else how),
            "hops": hops if sky and hops > 1 else (1 if sky else None),
            "skip_km": None if skip is None else round(skip),
            "ground_km": round(ground_km),
            "one_hop_km": round(far),
        }
        if muf is not None:
            rated = band_score(mhz, muf, elevation, k_index, fof2=fof2,
                               hmf2=hmf2)
            row["score"] = rated.get("score")
            row["label"] = rated.get("label")
        if sky and hops > 1:
            # Geometry says yes; the path still has to be paid for. Each
            # reflection puts the signal through the D layer twice more and
            # bounces it off the ground once, and none of that is free - so a
            # band that closes in four hops is a band to call on, not a band
            # to count on.
            row["cost"] = ("%d hops means %d more trips through the absorbing "
                           "layer and %d ground reflections - possible rather "
                           "than easy" % (hops, 2 * (hops - 1), hops - 1))
        if not row["works"]:
            if blind:
                row["why"] = ("no critical frequency in hand, so ELMER cannot "
                              "say what the sky is doing - fetch an ionosonde "
                              "reading and ask again")
            elif skip is None:
                row["why"] = ("nothing comes back from the ionosphere at this "
                              "frequency just now")
            elif skip > km:
                row["why"] = ("the skip zone reaches %d km and the path is "
                              "%d - too close for this band"
                              % (round(skip), round(km)))
            else:
                row["why"] = ("further than this band reaches, even in hops")
        out.append(row)
    return {"km": round(km), "one_hop_km": round(far),
            "fof2": fof2, "hmf2": hmf2, "blind": blind,
            "bands": out,
            "any": [r for r in out if r["works"]]}


def band_score(mhz, muf, elevation, k_index=2.0, fof2=None,
               hmf2=HMF2_DEFAULT,
               geomag_lat=None, aurora_lat=None):
    """0-100 for one band at one moment, with the reason in words.

    `elevation` is the sun's angle at the operator's QTH: negative is night,
    which is when the D layer is gone and the MUF is at its lowest.

    The score is against MUF(3000) - a full hop, a long path - because that is
    what a MUF is, and it is the right ceiling for the DX this rating is
    usually read for. It is the wrong one for anybody working across the
    county, and a number with no distance attached invites exactly that
    mistake: on a night with foF2 at 4, 30m rates Good and cannot reach
    anything closer than a thousand miles. So when foF2 is known the nearest
    reachable station comes back with the score, and the words say so.
    """
    # The sun as the D layer sees it, not as the ground does. See the note
    # above: the layer is 80 km up and keeps its daylight about nine degrees
    # longer than you keep yours. Worked out here rather than further down
    # because the shape below needs it too.
    lit = max(-90.0, min(90.0, elevation + D_LAYER_DIP))
    sun = max(0.0, math.sin(math.radians(lit)))

    muf = max(1.0, float(muf or 1.0))
    ratio = mhz / muf
    if ratio <= MUF_OVER_LIMIT:
        # Best just under the MUF, tailing off as the band drops away from it
        # - and, past the peak, falling through the MUF rather than off it.
        #
        # MUF(3000) is a median: at the MUF itself a full hop works about
        # half the time, and the shorter paths, sporadic E and a good day at
        # the far end live just over the line. The score used to say 86 at
        # 0.99 of the MUF and 34 at 1.01 - a fifty-point cliff at a number
        # that is itself uncertain by ten percent - so on a night with the
        # measured MUF sitting at 14 MHz, 20 m read Excellent, Poor,
        # Excellent, Poor from one hour to the next as the model's MUF
        # breathed around it. Now it is one curve: 100 at the peak, a soft
        # knee falling to half that at the MUF, nothing a third above it.
        if ratio <= MUF_PEAK:
            near = max(0.0, 1.0 - (MUF_PEAK - ratio) / MUF_PEAK)
            # What the tail under the peak actually charges for is absorption
            # on the way through, and absorption is the D layer's business -
            # which is why it is also charged for below, in `absorb`. In
            # daylight that is one thing said twice and roughly right. After
            # dark it is a bill for a layer that has gone home: `absorb`
            # correctly falls to nothing while this tail does not, and 80 m
            # sits at "Good" through the hours it is at its best. So the
            # shape relaxes as the D layer goes.
            #
            # By exactly as much as that band was being absorbed, and no
            # more. The frequency term is `absorb`'s own, so the relief is
            # the complement of the bill: 80 m gets nearly all of it back,
            # 40 m a third, and 10 m essentially nothing - which is right,
            # because 10 m sitting well under a 100 MHz MUF is not being held
            # down by the D layer and does not improve at nightfall. It
            # relaxes rather than vanishing because being far under the MUF
            # still is not the sweet spot: below the LUF nothing works at any
            # hour, and the low bands stay noisy after dark whatever the
            # ionosphere is doing.
            d_layers_share = min(1.0, (3.5 / max(mhz, 1.0)) ** 1.6)
            near += ((1.0 - near) * NIGHT_RELIEF * d_layers_share
                     * (1.0 - sun ** 0.6))
            score = 45.0 + 55.0 * near
        elif ratio <= 1.0:
            # A soft knee, not a spike: flat leaving the peak - 30 m at 0.85
            # of the MUF is as good as 30 m gets - and steepening into the
            # MUF, where a full hop becomes a coin toss. The first cut of
            # this was a straight line from the peak and turned the broad
            # plateau every band used to show into a point, taking 30 m
            # before dawn from the nineties to the seventies for no reason
            # the ionosphere knew about.
            frac = (ratio - MUF_PEAK) / (1.0 - MUF_PEAK)
            score = 100.0 - (100.0 - MUF_AT_LINE) * frac * frac
            d_layers_share = 0.0
        else:
            score = MUF_AT_LINE * (1.0 - (ratio - 1.0) / (MUF_OVER_LIMIT - 1.0))
            d_layers_share = 0.0
        if ratio > 1.0:
            why = (f"{mhz:g} MHz is above the {muf:g} MHz MUF - a full hop "
                   "mostly goes through the F layer; shorter paths, sporadic "
                   "E and a good day at the far end are what is left")
        elif ratio > 0.95:
            why = (f"{mhz:g} MHz is at the {muf:g} MHz MUF - a coin toss for a "
                   "full hop, and the shorter paths still work")
        else:
            why = (f"{mhz:g} MHz is {ratio:.2f} of the {muf:g} MHz MUF"
                   + (" - about where the band works best" if 0.6 <= ratio <= 0.95
                      else ""))
        if sun < 0.2 and ratio < 0.6 and d_layers_share > 0.25:
            why += ("; well under it, which costs nothing after dark - the "
                    "absorption that penalises a low band is the D layer's, "
                    "and it is not there")
    else:
        # A third above the MUF and more: it does not fade, it stops.
        score = 0.0
        why = (f"{mhz:g} MHz is well above the {muf:g} MHz MUF - signals go "
               "through the F layer instead of coming back")

    # Absorption is heaviest on the lowest bands and gone by about 10 MHz. The
    # exponent is the textbook inverse-square softened for the fact that this
    # is a rating and not a link budget.
    absorb = D_ABSORPTION * (sun ** 0.6) * (3.5 / max(mhz, 1.0)) ** 1.6
    absorb = min(absorb, D_ABSORPTION_CAP)
    if absorb > 6:
        if elevation < 0:
            why += ("; the sun has set here but not on the D layer 80 km up, "
                    "which is still absorbing")
        else:
            why += ("; daylight D-layer absorption is what limits it"
                    if mhz <= 10.1 else "; a little daytime absorption")

    # Scaled by where the operator is with respect to the oval, not asserted to
    # be worse near the poles and then applied flat. See the note above.
    polar = auroral_factor(geomag_lat, aurora_lat)
    storm = min(40.0, max(0.0, float(k_index or 0) - 2.0) * 7.0 * polar)
    if storm > 6:
        why += f"; K {k_index:g} means absorption and flutter"
        if geomag_lat is None:
            why += ", worst near the poles"
        elif polar >= 1.6:
            why += (f", and at {abs(geomag_lat):.0f} degrees geomagnetic you are "
                    "under the auroral oval, where it bites hardest")
        elif polar <= 0.7:
            why += ", though this far from the oval a disturbed field costs little"

    score = max(0.0, min(100.0, score - absorb - storm))
    out = {"score": round(score), "label": _pick(QUALITY, score),
           "modes": _pick(MODES, score), "why": why,
           "muf": round(muf, 1), "ratio": round(ratio, 2)}

    # Who the rating is for. A band can be excellent and useless at once.
    #
    # And when it is useless the operator's next thought is the antenna, which
    # is the wrong lever and an expensive one. The antenna decides what you
    # launch; the ionosphere decides what comes back. If it will not return
    # anything steeper than 31 degrees then launching steeper only throws power
    # into space, and launching shallower - which is what a vertical does -
    # pushes the first landfall further out, not nearer. The lever that works
    # is frequency: get under the critical frequency and the signal comes back
    # from straight overhead. So the band that would do it gets named.
    nearest = skip_km(mhz, fof2, hmf2) if fof2 else 0.0
    if fof2:
        out["skip_km"] = None if nearest is None else round(nearest)
        out["reaches_local"] = nearest == 0.0
        if nearest is None:
            out["why"] += ("; nothing returns at any angle, so this is shut "
                           "over every path, not merely long ones")
        elif nearest > 0:
            out["why"] += ("; and nothing closer than %d miles - below the "
                           "critical frequency a signal comes back from "
                           "overhead, above it the near stations are the ones "
                           "that go" % round(nearest / 1.609))
        under = [name for name, freq, _ in BANDS if freq <= fof2]
        out["fills_the_gap"] = under[-1] if under and nearest else None
    return out


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
    votes, factors, suns, nearest, closest = [], [], [], None, None
    for station in sondes:
        km = ionosonde.great_circle(lat, lon, station["lat"], station["lon"])
        if km > CALIBRATION_KM:
            continue
        sun = solar_elevation(station["lat"], station["lon"], when)
        # The same lag the model uses everywhere else. If the measurement were
        # compared against an unlagged model, the factor would quietly absorb
        # the lag as though it were the station's own error - correcting the
        # model here and then correcting it again by the same amount there.
        modelled = _fof2(sfi, sun, station["lat"],
                         f2_drive(station["lat"], station["lon"], when))
        if modelled <= 0:
            continue
        weight = 1.0 / (1.0 + (km / CALIBRATION_HALF_KM) ** 2)
        votes.append((station["fof2"] / modelled, weight))
        suns.append((sun, weight))
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
        # The sun angle this was measured under. An anchor is evidence about
        # the ionosphere that was overhead the sondes at the time, and the sun
        # is most of what decides that - so carrying it to an hour with a
        # different sun means carrying it past what it can support.
        "sun_deg": round(sum(e * w for e, w in suns) / sum(w for _, w in suns), 1)
                   if suns else None,
        "m3000": round(_weighted_median(factors) or M3000_DEFAULT, 2),
        "stations": len(votes),
        "nearest_km": round(nearest),
        "nearest": closest["name"],
        "age_minutes": closest["age_minutes"],
        "measured_fof2": closest["fof2"],
        # The height as well as the frequency. foF2 says whether a band comes
        # back at all; hmF2 says how far one hop carries it, and everything
        # downstream was defaulting that to a textbook 300 km while the
        # network sat on the disk reporting 245. Taken from the same station
        # and the same fetch as the frequency, so the two cannot disagree.
        "measured_hmf2": closest.get("hmf2"),
        "source": ("bounded" if abs(raw - factor) > 1e-9
                   else "measured" if nearest <= CALIBRATION_HALF_KM
                   else "regional"),
    }


# How far the anchor may be carried from the sky it was measured under.
#
# A calibration is a measurement of how wrong the model is *now*, and "now"
# includes the sun. Applying tonight's factor to tomorrow's noon assumes the
# model's error is the same fraction in daylight as in darkness, and it is not:
# checked against every sonde reporting at one moment, the ratio of measured to
# modelled foF2 ran about 0.77 at the stations in darkness and about 1.20 at
# the stations in daylight. It does not merely change size, it changes sign.
#
# So an anchor taken at night, carried through the following day, is wrong
# twice over - and it was closing 20 m for twenty-four hours straight on a flux
# of 110, against a wall chart that called the same band Good day and night.
#
# The plateau is the span over which the sky has not really changed and the
# measurement still stands; beyond it the anchor fades out and the model is
# left to speak for itself, which is the honest position when there is no
# measurement for that sun angle. Both are chosen rather than fitted - there is
# not enough of a sonde record here to fit them - and they are deliberately
# wide, because letting go of evidence too early is the smaller error.
ANCHOR_PLATEAU_DEG = 12.0
ANCHOR_FADE_DEG = 40.0

# The same sun angle comes round twice a day, and the sky under it is not the
# same sky. An anchor measured at eleven at night, with the F layer still
# carrying the afternoon, was being applied in full at six the next morning
# because the sun was back at the same angle - after seven hours of
# recombination had taken the layer to its lowest of the day. So the hold is
# also a matter of time: full for a few hours either side of the reading, gone
# by the time the other side of the night is reached.
ANCHOR_HOLD_HOURS = 3.0
ANCHOR_FADE_HOURS = 9.0


def anchor_at(anchor, measured_sun, sun, hours_since=None):
    """The anchor's weight at one sun angle, given where it was measured.

    Full strength where the sun is where it was when the sondes were read, so
    the current hour is unchanged; fading to 1.0 - the model alone - as the sky
    moves away from that, or as the hours put the reading behind. Whichever
    has let go further decides.
    """
    if anchor is None:
        return 1.0
    if measured_sun is None:
        return float(anchor)
    gap = abs(float(sun) - float(measured_sun))
    if gap <= ANCHOR_PLATEAU_DEG:
        held = 1.0
    elif gap >= ANCHOR_FADE_DEG:
        held = 0.0
    else:
        held = 1.0 - (gap - ANCHOR_PLATEAU_DEG) / (ANCHOR_FADE_DEG - ANCHOR_PLATEAU_DEG)
    if hours_since is not None:
        age = abs(float(hours_since))
        if age <= ANCHOR_HOLD_HOURS:
            by_time = 1.0
        elif age >= ANCHOR_FADE_HOURS:
            by_time = 0.0
        else:
            by_time = 1.0 - (age - ANCHOR_HOLD_HOURS) / (ANCHOR_FADE_HOURS - ANCHOR_HOLD_HOURS)
        held = min(held, by_time)
    return 1.0 + (float(anchor) - 1.0) * held


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
    # Against the same model the hours will be scored with, lag and all. A
    # factor worked out against an unlagged model and applied to a lagged one
    # would miss the measurement it exists to meet, by exactly the amount the
    # lag moves the layer - which is worst in the morning and the evening,
    # where the anchor is least likely to be checked.
    modelled, _ = levels(sfi, solar_elevation(lat, lon, when), lat, m3000,
                         drive=f2_drive(lat, lon, when))
    if not modelled:
        return 1.0
    low, high = ANCHOR_RANGE
    return max(low, min(high, float(measured) / modelled))


# --- what the wall chart says, and what we say ------------------------------
#
# Two answers to nearly the same question, and they are not the same question.
# N0NBH rates a *group* of bands twice a day from the flux and the field; this
# rates *one* band for *this* hour against a critical frequency measured near
# the operator. They should sometimes differ, and when they do the difference
# is information rather than a fault - on an evening when 30 m is under the MUF
# and 20 m is over it, the group they share can only be right about one of them.
#
# So neither is corrected toward the other and neither is hidden. Ours is shown
# because it is the one that knows where the operator is standing; theirs is
# shown beside it because an independent second opinion from a source every
# operator already reads is worth more than a quiet agreement would be. What is
# added here is the sentence that says which is which, and how far apart they
# are, so a reader is never left to notice a contradiction on their own.
#
# The one honest asymmetry: when a sonde is in reach, ours is anchored to a
# real reading and theirs is not; when there is no sonde, ours is a model and
# theirs is the better-founded of the two. The note says so either way.

WALL_WORDS = {"Good": 2, "Fair": 1, "Poor": 0}


def _as_wall_word(score):
    """Our five words in their three, so the comparison is like for like."""
    if score >= 60:
        return "Good"
    if score >= 35:
        return "Fair"
    return "Poor"


def reconcile(score, rating, muf_source=None, is_group=True):
    """Line our rating up against the wall chart's and say where they part.

    Returns None when there is nothing to compare against, which is the honest
    answer and not an error - the feed does not rate every band.
    """
    rating = (rating or "").strip().title()
    if rating not in WALL_WORDS or score is None:
        return None
    ours = _as_wall_word(score)
    gap = abs(WALL_WORDS[ours] - WALL_WORDS[rating])
    out = {"theirs": rating, "ours": ours, "score": round(score),
           "agree": gap == 0, "gap": gap}
    if gap == 0:
        out["note"] = ""
        return out

    # Why they can differ at all, said once and plainly.
    why = ("The wall chart rates a group of bands twice a day from the flux "
           "and the field. This rates one band for this hour, against the "
           "critical frequency measured nearest you and the sun's angle where "
           "you are standing. Two bands in one group can be on opposite sides "
           "of the MUF, and then one word cannot be right about both."
           if is_group else
           "The wall chart is twice a day from the flux and the field; this "
           "is this hour, at your latitude.")
    # Good against Poor is not a shade of difference and must not be answered
    # as one. It has been a fault here rather than a subtlety, and the fault
    # was ours: a sonde anchor measured at night was carried through the
    # following noon, which held 20 m shut for a whole day at a flux of 110
    # while the wall chart called it Good. Worse, the version of this note
    # that shipped that morning would have said ours was "the better informed
    # of the two", because it had a measured anchor - the code was most
    # confident exactly where it was most wrong.
    #
    # So a flat contradiction claims nothing for either side. Having a
    # measurement did not make the forecast right; misapplying the measurement
    # is what made it wrong, and no amount of provenance protects against that.
    if gap >= 2:
        trust = ("Treat a gap this wide as a reason to doubt this page first. "
                 "Two answers one word apart is the two methods disagreeing; "
                 "Good against Poor usually means one of them is broken, and "
                 "it has been this one before now. Turn the radio on and "
                 "believe what you hear over either of us.")
    elif muf_source == "measured":
        trust = ("Ours is anchored to a sonde reading taken near you within "
                 "the hour, so it knows something about your sky that a "
                 "national figure cannot - but it is a model wearing a "
                 "measurement, and the wall chart is a real second opinion.")
    elif muf_source in ("regional", "bounded"):
        trust = ("Ours is corrected by sondes, but distant ones, so it is a "
                 "regional figure rather than a local measurement.")
    else:
        trust = ("No sonde was in reach, so ours is the model alone and the "
                 "wall chart is the better founded of the two here. Doubt us "
                 "first.")
    out["note"] = ("%s says %s, we make it %s.%s %s"
                   % ("The wall chart", rating, ours,
                      " That is a flat contradiction, not a shade of one."
                      if gap >= 2 else "", why + " " + trust))
    return out


def outlook(mhz, lat, lon, sfi, k_index=2.0, hours=24, start=None,
            muf_now=None, anchor=None, m3000=None, aurora_lat=None,
            anchor_sun=None, hmf2=HMF2_DEFAULT):
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
    # An anchor whose sky was not recorded was still measured under a sky, and
    # it is this one: the calibration is the current hour's. Assuming that is
    # strictly better than the alternative, which is treating it as valid
    # under every sky there is - and that is how a noon ionosonde reading ends
    # up describing midnight, holding the MUF up all night and telling
    # somebody 80 m is mediocre at the hour it is at its best.
    if anchor_sun is None:
        anchor_sun = solar_elevation(lat, lon, start)
    # One geomagnetic latitude for the whole run: the operator does not move
    # over the next day, and the oval's own boundary is a fetched number that
    # this deliberately does not try to forecast either.
    geomag = geomagnetic_latitude(lat, lon)
    out = []
    for step in range(hours + 1):
        when = start + timedelta(hours=step)
        elevation = solar_elevation(lat, lon, when)
        # The anchor is worth what it was measured under, and no more. Held at
        # full strength while the sun is near where the sondes saw it, then
        # released - see `anchor_at`.
        muf, fof2 = levels(sfi, elevation, lat, m3000,
                           anchor_at(anchor, anchor_sun, elevation, hours_since=step),
                           drive=f2_drive(lat, lon, when))
        got = band_score(mhz, muf, elevation, k_index, fof2, hmf2,
                         geomag_lat=geomag, aurora_lat=aurora_lat)
        state = sun_regime(elevation, lat, when)
        got.update({"at": when.isoformat(), "hour": when.hour,
                    "elevation": round(elevation, 1), "fof2": fof2,
                    "regime": state, "day": state == "lit"})
        out.append(got)
    return out


# How near the best hour still counts as being at the best. A score is an
# estimate whose own error is far larger than this, so hours within a few
# points of one another are not distinguishable - and a band's peak is nearly
# always a plateau rather than an instant. Naming one hour out of a flat run
# of them sends somebody to the radio at an hour that was never special, and
# implies the rest are worse when they are the same.
PEAK_TOLERANCE = 3


def _apart(a, b):
    """Hours from one hourly sample to another, and never less than one.

    A window one sample wide is an hour of usable band, not nothing: the
    sample stands for the hour it opens.
    """
    gap = datetime.fromisoformat(b["at"]) - datetime.fromisoformat(a["at"])
    return max(1, round(gap.total_seconds() / 3600.0))


def windows(hours, floor=38):
    """When a band is worth using, said as times rather than as a graph.

    The graph shows the shape; this is the sentence somebody reads off it -
    the runs of hours at or above a usable score, in the order they happen,
    each with the plateau at its peak and how wide that plateau is.
    """
    runs, live, good = [], None, None
    for row in hours:
        if row["score"] >= floor:
            live = live or row
            good = row
        elif live:
            # The last hour that was usable, not the first that was not. A
            # window that ends at the hour the band shut is an hour longer
            # than the band was open.
            runs.append((live, good))
            live = None
    if live:
        runs.append((live, good))
    out = []
    for a, b in runs:
        inside = [h for h in hours if a["at"] <= h["at"] <= b["at"]]
        top = max(h["score"] for h in inside)
        at = next(n for n, h in enumerate(inside) if h["score"] == top)
        # Outward from the peak while the hours are as good as it is, and
        # contiguous - an equally good hour on the far side of a dip is a
        # second opportunity, not part of this one.
        low = high = at
        while low and inside[low - 1]["score"] >= top - PEAK_TOLERANCE:
            low -= 1
        while high + 1 < len(inside) \
                and inside[high + 1]["score"] >= top - PEAK_TOLERANCE:
            high += 1
        out.append({"from": a["at"], "to": b["at"], "hours": _apart(a, b),
                    "best": top, "best_at": inside[at]["at"],
                    # The aperture: when the band is at its best, and for how
                    # long, which is the part a single hour could never say.
                    "best_from": inside[low]["at"],
                    "best_to": inside[high]["at"],
                    "best_hours": _apart(inside[low], inside[high])})
    return out


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

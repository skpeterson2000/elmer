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

"""The weather at a golf course, from the National Weather Service.

A round of golf is played in a day's weather, and the honest way to give
the fairways and greens their life is to give the day one: wind that is
what the forecast says, a shower that is coming or is not, ground that is
soft because it rained this morning. The NWS publishes an hourly forecast
for any point in the United States, free and without a key, and asks only
for a user agent. So when a unit has a network, the course's day starts
from the real one; when it has not, from the card's typical wind, as it
always did. Either way the round's own model takes it from there - see
golf.Day - and this is only the starting point, fetched in the background
when a game is chosen so that a tee-off never waits on it.

The courses ELMER plays are named places, and the weather is that
place's, not the operator's: Pebble Beach's sea breeze on a Minnesota
evening is the point.
"""
import json
import logging
import re
import threading
import time
import urllib.request

from . import paths

log = logging.getLogger("elmer")

CACHE = paths.STATE / "weather"
POINTS = "https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
OBSERVATIONS = ("https://api.weather.gov/stations/{station}/observations"
                "?start={since}&limit=200")
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
TIMEOUT = 8
MAX_AGE_SECONDS = 3600

RAINY = re.compile(r"rain|shower|drizzle|storm|thunder", re.I)
CLOUDY = re.compile(r"cloud|overcast|fog|haze", re.I)

# The day's wind, not the minute's. Somebody who tees off in a calm hour on
# a day that blew twenty-five all afternoon was playing a dead round: the
# forecast's first hourly period is what the wind is doing right now, and a
# round of golf is played in a day. So the figure the round starts from is
# the highest wind of the last day, and the current hour is kept beside it
# because it is still the honest answer to "what is it doing out there".
#
# The last day is asked of the observation stations, which is the only
# place the past is published - the hourly forecast this module already
# fetches runs forward from now. Where the stations cannot be had, the next
# twenty-four hours of that forecast stand in; a round is about to be
# played in them, which is the next best thing to the day behind.
PEAK_HOURS = 24
PEAK_MOST = 100                 # mph; past this the reading is bad data, not weather
# What the observation feed reports wind in. It is SI by default and the
# unit is named on every value, so it is read rather than assumed - a
# station that answers in knots must not be taken for one answering in
# kilometres an hour.
TO_MPH = {
    "wmoUnit:km_h-1": 0.621371, "wmoUnit:m_s-1": 2.236936,
    "wmoUnit:mi_h-1": 1.0, "wmoUnit:kn": 1.150779,
}


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def _mph(text):
    found = re.findall(r"\d+", str(text or ""))
    return max(int(x) for x in found) if found else None


def _sane(mph, why):
    """A wind in miles an hour, or None when it is not weather.

    A station with a stuck anemometer reports three hundred, and a round
    played in three hundred miles an hour is not a round. Anything past
    PEAK_MOST is dropped and said aloud with the value, so a bad station
    shows up in the log rather than in somebody's tee shot.
    """
    if mph is None:
        return None
    try:
        mph = float(mph)
    except (TypeError, ValueError):
        return None
    if mph < 0 or mph > PEAK_MOST:
        log.warning("weather: ignoring %s of %.0f mph - past the %d mph "
                    "this treats as weather", why, mph, PEAK_MOST)
        return None
    return mph


def _peak_from_forecast(periods):
    """The highest wind the next PEAK_HOURS of forecast expect.

    The stand-in for the day behind when the stations cannot be reached.
    Forecast winds come as text - "10 to 15 mph" - which `_mph` already
    reads as the top of the range, which is the number wanted here anyway.
    """
    winds = [_sane(_mph(p.get("windSpeed")), "a forecast wind")
             for p in (periods or [])[:PEAK_HOURS]]
    winds = [w for w in winds if w is not None]
    return max(winds) if winds else None


def _station_of(point):
    """The nearest observation station's observations URL, or None.

    Two hops - the point names a stations list, the list names stations -
    and either can be missing on a point that has no station near it,
    which is a real answer rather than a fault.
    """
    listing = point.get("observationStations")
    if not listing:
        log.warning("weather: the forecast point names no observation "
                    "stations; falling back to the forecast's own peak")
        return None
    features = (_get(listing) or {}).get("features") or []
    for feature in features:
        ident = ((feature.get("properties") or {}).get("stationIdentifier")
                 or "").strip()
        if ident:
            return ident
    log.warning("weather: the station list at %s held no station "
                "identifiers; falling back to the forecast's own peak",
                listing)
    return None


def _peak_from_observations(point):
    """The highest wind actually observed nearby in the last PEAK_HOURS.

    Returns (mph, station) or (None, None). Never raises: every way this
    can fail ends in the forecast's peak being used instead, and says so.
    """
    from datetime import datetime, timedelta, timezone
    station = _station_of(point)
    if not station:
        return None, None
    since = (datetime.now(timezone.utc)
             - timedelta(hours=PEAK_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = OBSERVATIONS.format(station=station, since=since)
    features = (_get(url) or {}).get("features") or []
    if not features:
        log.warning("weather: station %s reported nothing in the last %d "
                    "hours; falling back to the forecast's own peak",
                    station, PEAK_HOURS)
        return None, None

    unknown = set()
    winds = []
    for feature in features:
        props = feature.get("properties") or {}
        for field in ("windSpeed", "windGust"):
            reading = props.get(field) or {}
            value, unit = reading.get("value"), reading.get("unitCode")
            if value is None:
                continue                      # null is ordinary in this feed
            factor = TO_MPH.get(unit)
            if factor is None:
                unknown.add(unit)
                continue
            mph = _sane(value * factor, f"{station}'s {field}")
            if mph is not None:
                winds.append(mph)
    if unknown:
        log.warning("weather: station %s reported wind in %s, which this "
                    "does not know; those readings were skipped",
                    station, ", ".join(sorted(str(u) for u in unknown)))
    if not winds:
        log.warning("weather: station %s had %d observations in the last "
                    "%d hours and no usable wind in any of them; falling "
                    "back to the forecast's own peak",
                    station, len(features), PEAK_HOURS)
        return None, None
    return max(winds), station


def read(periods):
    """The day, from the forecast's hourly periods: the wind now, the
    sky, the chance of rain over the next few hours - and the peak, which
    is what a round is actually played in. See the note on PEAK_HOURS."""
    if not periods:
        return None
    now = periods[0]
    soon = periods[:6]
    rain = [p.get("probabilityOfPrecipitation", {}).get("value") or 0 for p in soon]
    sky_text = now.get("shortForecast") or ""
    sky = "shower" if RAINY.search(sky_text) else "cloud" if CLOUDY.search(sky_text) else "sun"
    return {
        "wind_mph": _mph(now.get("windSpeed")) or 0,
        # What the round starts from: the day's wind, not this minute's.
        # Filled from the forecast here; fetch() prefers what was really
        # observed when it can get it, and says which it used.
        # Rounded, like the observed peak that may replace it: one figure
        # with two types is the sort of thing that reads fine and then
        # lands in a cache as 22.0 beside somebody else's 22.
        "peak_mph": round(_peak_from_forecast(periods)
                          or _mph(now.get("windSpeed")) or 0),
        "peak_source": "forecast",
        "wind_from": now.get("windDirection") or "",
        "temperature_f": now.get("temperature"),
        "sky": sky, "sky_text": sky_text,
        "rain_chance": max(rain) / 100.0,
        "raining": sky == "shower",
        "at": now.get("startTime"),
    }


def fetch(lat, lon):
    """The forecast at a point, read into a day. Raises when it cannot."""
    point = _get(POINTS.format(lat=lat, lon=lon))["properties"]
    hourly = _get(point["forecastHourly"])["properties"]["periods"]
    day = read(hourly)
    if day:
        where = (point.get("relativeLocation") or {}).get("properties") or {}
        day["where"] = ", ".join(x for x in (where.get("city"), where.get("state")) if x)
        # The day behind, where the stations will give it. Everything that
        # can go wrong in there ends in the forecast peak read() already
        # put in, and has said in the log why.
        try:
            observed, station = _peak_from_observations(point)
        except Exception as exc:              # the stations are a bonus, never a fault
            log.warning("weather: the observation stations could not be "
                        "read (%s); using the forecast's own peak", exc)
            observed, station = None, None
        if observed is not None:
            day["peak_mph"] = round(observed)
            day["peak_source"] = "observed"
            day["peak_station"] = station
    return day


def cached(course_id):
    """What is on disk for a course, if fresh enough; else None."""
    path = CACHE / f"{course_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - data.get("fetched_at", 0) > MAX_AGE_SECONDS:
        return None
    return data


def prefetch(course):
    """Fetch the course's day in the background, if the card says where
    the course is and nothing fresh is on disk. Quiet on failure: the
    round starts from the card's typical wind, as it always did."""
    lat, lon = course.get("lat"), course.get("lon")
    if lat is None or lon is None or cached(course["id"]):
        return None

    def run():
        try:
            day = fetch(float(lat), float(lon))
        except Exception as exc:                   # no network is the usual reason
            log.debug("weather: %s not fetched (%s)", course["id"], exc)
            return
        if not day:
            return
        day["fetched_at"] = time.time()
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            (CACHE / f"{course['id']}.json").write_text(json.dumps(day), encoding="utf-8")
        except OSError as exc:
            log.debug("weather: could not save (%s)", exc)
        log.info("weather at %s: %s mph %s now, %s mph the day's peak (%s%s), "
                 "%s, rain %d%%", course["name"], day["wind_mph"], day["wind_from"],
                 day.get("peak_mph"), day.get("peak_source"),
                 " " + day["peak_station"] if day.get("peak_station") else "",
                 day["sky_text"], round(day["rain_chance"] * 100))
    thread = threading.Thread(target=run, name="weather-fetch", daemon=True)
    thread.start()
    return thread

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
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
TIMEOUT = 8
MAX_AGE_SECONDS = 3600

RAINY = re.compile(r"rain|shower|drizzle|storm|thunder", re.I)
CLOUDY = re.compile(r"cloud|overcast|fog|haze", re.I)


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def _mph(text):
    found = re.findall(r"\d+", str(text or ""))
    return max(int(x) for x in found) if found else None


def read(periods):
    """The day, from the forecast's hourly periods: the wind now, the
    sky, and the chance of rain over the next few hours."""
    if not periods:
        return None
    now = periods[0]
    soon = periods[:6]
    rain = [p.get("probabilityOfPrecipitation", {}).get("value") or 0 for p in soon]
    sky_text = now.get("shortForecast") or ""
    sky = "shower" if RAINY.search(sky_text) else "cloud" if CLOUDY.search(sky_text) else "sun"
    return {
        "wind_mph": _mph(now.get("windSpeed")) or 0,
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
        log.info("weather at %s: %s mph %s, %s, rain %d%%", course["name"], day["wind_mph"], day["wind_from"],
                 day["sky_text"], round(day["rain_chance"] * 100))
    thread = threading.Thread(target=run, name="weather-fetch", daemon=True)
    thread.start()
    return thread

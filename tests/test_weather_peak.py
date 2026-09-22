#!/usr/bin/env python3
"""The day's wind, not the minute's.

    python3 tests/test_weather_peak.py

A round of golf is played in a day, and the forecast's first hourly period
is one sample of it. Somebody teeing off in a lull on a day that blew
twenty-five all afternoon was handed a dead round - Pebble Beach without
the sea breeze, because of when they happened to sit down. The round now
starts from the highest wind of the last day.

The past is only published by the observation stations; the hourly forecast
this module already fetches runs forward from now. So there are two hops
more to make and a good many ways for them to fail, and the point of this
test is that *every one of them ends in a playable round* - the forecast's
own peak, or the card's typical wind - and says in the log what failed and
what it did instead.

Nothing here touches the network. The NWS payloads are recorded shapes,
and `_get` is stood in for.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
import logging  # noqa: E402
import random  # noqa: E402
from elmer import golf, weather  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


class Caught(logging.Handler):
    """The log, so a fallback can be shown to announce itself."""

    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append((record.levelname, record.getMessage()))

    def said(self, *words):
        return any(all(w.lower() in m.lower() for w in words)
                   for _, m in self.lines)


caught = Caught()
logging.getLogger("elmer").addHandler(caught)
logging.getLogger("elmer").setLevel(logging.DEBUG)


# ---------------------------------------------------------------- payloads
def hourly(*winds):
    """An hourly forecast whose periods blow these, in order."""
    return [{"windSpeed": f"{w} mph", "windDirection": "NW",
             "temperature": 60, "shortForecast": "Sunny",
             "probabilityOfPrecipitation": {"value": 0},
             "startTime": "2026-09-22T15:00:00-07:00"} for w in winds]


def obs(*readings):
    """An observations payload. Each reading is (value, unitCode) or None."""
    out = []
    for r in readings:
        if r is None:
            out.append({"properties": {"windSpeed": {"value": None,
                                                     "unitCode": "wmoUnit:km_h-1"}}})
        else:
            value, unit = r
            out.append({"properties": {"windSpeed": {"value": value, "unitCode": unit}}})
    return {"features": out}


POINT = {"forecastHourly": "FORECAST",
         "observationStations": "STATIONS",
         "relativeLocation": {"properties": {"city": "Pebble Beach", "state": "CA"}}}
STATIONS = {"features": [{"properties": {"stationIdentifier": "KMRY"}}]}


def serve(table):
    """Stand in for _get with a URL -> payload table."""
    def _get(url):
        for key, value in table.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(f"nothing recorded for {url}")
    return _get


def fetch_with(table):
    caught.lines.clear()
    real = weather._get
    weather._get = serve(table)
    try:
        return weather.fetch(36.5687, -121.9500)
    finally:
        weather._get = real


BASE = {"points/": {"properties": POINT}, "FORECAST": {"properties": {"periods": hourly(6, 9, 22, 14)}}}


# --------------------------------------------------------------- the tests
print("\nthe forecast alone gives the day a peak, not just the hour")
day = weather.read(hourly(6, 9, 22, 14))
check("the wind now is the first period", day["wind_mph"], 6)
check("  the peak is the highest of the day", day["peak_mph"], 22)
check("  and it says where that came from", day["peak_source"], "forecast")
check("  a flat day peaks at what it is doing", weather.read(hourly(7))["peak_mph"], 7)
check("  and no periods is still no day", weather.read([]), None)


print("\nwhat was actually observed beats what is forecast")
day = fetch_with({**BASE, "STATIONS": STATIONS,
                  "observations": obs((48.3, "wmoUnit:km_h-1"))})   # 30 mph
check("the peak is the observed one", day["peak_mph"], 30)
check("  and says so", day["peak_source"], "observed")
check("  naming the station", day["peak_station"], "KMRY")
check("  while the wind now is untouched", day["wind_mph"], 6)
check("  and the town came through", day["where"], "Pebble Beach, CA")

print("\n  every unit the feed uses is read, not assumed")
for value, unit, want in ((10.0, "wmoUnit:m_s-1", 22), (20.0, "wmoUnit:kn", 23),
                          (17.0, "wmoUnit:mi_h-1", 17)):
    day = fetch_with({**BASE, "STATIONS": STATIONS, "observations": obs((value, unit))})
    check(f"  {unit}", day["peak_mph"], want)


print("\nevery way the stations can fail still gives a playable round")

print("\n  the point names no stations")
day = fetch_with({**BASE, "STATIONS": STATIONS,
                  "points/": {"properties": {k: v for k, v in POINT.items()
                              if k != "observationStations"}}})
check("the forecast's peak stands in", day["peak_mph"], 22)
check("  and the log says why", caught.said("no observation stations"), True)

print("\n  the station list is empty")
day = fetch_with({**BASE, "STATIONS": {"features": []}})
check("the forecast's peak stands in", day["peak_mph"], 22)
check("  and the log says why", caught.said("no station identifiers"), True)

print("\n  the station reported nothing in the window")
day = fetch_with({**BASE, "STATIONS": STATIONS, "observations": {"features": []}})
check("the forecast's peak stands in", day["peak_mph"], 22)
check("  and the log names the station", caught.said("KMRY", "reported nothing"), True)

print("\n  every reading is null, which is ordinary in this feed")
day = fetch_with({**BASE, "STATIONS": STATIONS, "observations": obs(None, None, None)})
check("the forecast's peak stands in", day["peak_mph"], 22)
check("  and the log says how many it looked at",
      caught.said("KMRY", "no usable wind"), True)

print("\n  the station answers in a unit this does not know")
day = fetch_with({**BASE, "STATIONS": STATIONS,
                  "observations": obs((30.0, "wmoUnit:furlong_fortnight-1"))})
check("the forecast's peak stands in", day["peak_mph"], 22)
check("  and the log names the unit", caught.said("furlong_fortnight"), True)

print("\n  the anemometer is stuck")
day = fetch_with({**BASE, "STATIONS": STATIONS,
                  "observations": obs((900.0, "wmoUnit:km_h-1"), (32.2, "wmoUnit:km_h-1"))})
check("the bad reading is dropped, the good one kept", day["peak_mph"], 20)
check("  and the log names the value", caught.said("past the", "mph"), True)

print("\n  the stations request itself blows up")
day = fetch_with({**BASE, "STATIONS": OSError("connection reset")})
check("the forecast's peak stands in", day["peak_mph"], 22)
check("  and the round is still playable", day["wind_mph"], 6)
check("  and the log carries the reason",
      caught.said("could not be read", "connection reset"), True)


print("\nthe round starts from the day, and an old forecast still works")
day = golf.Day(random.Random(1), typical_mph=10,
               forecast={"peak_mph": 24, "wind_mph": 6, "sky": "sun",
                         "rain_chance": 0.0, "raining": False})
check("the day's mean is the peak, not the hour", day.mean, 24.0)
old = golf.Day(random.Random(1), typical_mph=10,
               forecast={"wind_mph": 6, "sky": "sun", "rain_chance": 0.0,
                         "raining": False})
check("  a forecast with no peak in it falls back to the hour", old.mean, 6.0)
none = golf.Day(random.Random(1), typical_mph=11)
check("  and no forecast at all is still the card's typical", none.mean, 11.0)


print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)

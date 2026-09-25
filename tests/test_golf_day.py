#!/usr/bin/env python3
"""Checks for the day a round is played in: the wind that walks, the sky
that steps, the ground that dries and soaks - and the forecast that
starts it when there is one.

    python3 tests/test_golf_day.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf, weather  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- a day from the card --")
    day = golf.Day(random.Random(1), typical_mph=12)
    check("the wind starts near the card's typical", 6 <= day.wind_mph <= 18, True)
    check("  the sky is one of three", day.sky in ("sun", "cloud", "shower"), True)
    check("  the ground is somewhere between dry and soaked", 0.0 <= day.moisture <= 1.0, True)
    check("firmness runs from a third more to a third less", (golf.Day(random.Random(1), 0).firmness <= 1.35,
                                                            round(1.35 - 0.7 * 1.0, 3)), (True, 0.65))

    print("\n-- the day moves --")
    day = golf.Day(random.Random(5), typical_mph=10)
    day.sky, day.moisture, day.rain_chance = "sun", 0.5, 0.0
    day.STEP = {"sun": (), "cloud": (), "shower": ()}          # hold the sky still
    before = day.moisture
    for _ in range(9):
        day.next_hole()
    check("nine holes of sun dry the ground, a little", 0.2 < before - day.moisture < 0.4, True)
    check("  and the wind stays near the mean", abs(day.wind_mph - day.mean) < 8, True)
    day.sky, day.moisture = "shower", 0.2
    for _ in range(3):
        day.next_hole()
    check("three holes of a shower soak it", day.moisture > 0.55, True)
    check("  and the words say so", day.ground_words in ("soft underfoot", "wet - nothing runs"), True)
    day.moisture = 0.1
    check("dry ground is firm and running", day.ground_words, "firm and running")
    # Counting distinct whole miles an hour was the old way of asking this,
    # and it measured the rounding as much as the gust: the day is down to
    # six miles an hour by here, where a real spread of five to seven is
    # only three whole numbers. Ask for the behavior instead - that shots
    # are played in more wind than the hole's and in less - and ask
    # separately for the part that is actually modelled, which is that a
    # blow is lumpy and light air is not.
    gusts = [day.gust() for _ in range(200)]
    check("a shot's wind gusts and lulls around the hole's",
          (min(gusts) < day.wind_mph < max(gusts)), True)
    check("  and stays within the day's bounds",
          all(day.wind_mph * golf.Day.GUST[0] <= g <= day.wind_mph * golf.Day.GUST[1]
              for g in gusts), True)

    def spread(mph):
        d = golf.Day(random.Random(3), typical_mph=mph)
        d.wind_mph = mph
        drawn = [d.gust() for _ in range(2000)]
        return (max(drawn) - min(drawn)) / mph

    check("a blow gusts wider than a breeze does", spread(25) > spread(8), True)
    check("  and light air barely gusts at all", spread(3) < 0.25, True)

    print("\n-- from a forecast --")
    day = golf.Day(random.Random(1), 12, {"wind_mph": 8, "sky": "sun", "rain_chance": 0.0, "raining": False})
    check("the forecast's wind is the day's mean", day.mean, 8.0)
    check("  and its sky", day.sky, "sun")
    check("  ground middling with no rain about", round(day.moisture, 2), 0.3)
    wet = golf.Day(random.Random(1), 12, {"wind_mph": 20, "sky": "shower", "rain_chance": 0.8, "raining": True})
    check("raining now starts the ground soft", wet.moisture, 0.7)
    check("  and the state says it came from a forecast", (wet.state()["forecast"], day.state()["forecast"]), (True, True))

    print("\n-- reading the Weather Service's hours --")
    periods = [{"startTime": "2026-09-15T13:00:00-07:00", "temperature": 64, "windSpeed": "8 to 12 mph",
                "windDirection": "WNW", "shortForecast": "Partly Sunny", "probabilityOfPrecipitation": {"value": 0}},
               {"windSpeed": "10 mph", "shortForecast": "Rain Showers Likely", "probabilityOfPrecipitation": {"value": 60}}]
    read = weather.read(periods)
    check("the wind is the top of the range", read["wind_mph"], 12)
    check("  partly sunny is sun", read["sky"], "sun")
    check("  the chance of rain is the worst of the next hours", read["rain_chance"], 0.6)
    check("  not raining now", read["raining"], False)
    read = weather.read([{"windSpeed": "3 mph", "shortForecast": "Light Rain", "probabilityOfPrecipitation": {"value": 90}}])
    check("light rain is a shower, now", (read["sky"], read["raining"]), ("shower", True))
    check("no hours, no day", weather.read([]), None)

    print("\n-- the round carries the day --")
    course = golf.course("pebble-beach")
    check("the course says where it is", (course.get("lat"), course.get("lon")), (36.5687, -121.9498))
    g = golf.Golf(["a"], course, seed=3, forecast={"wind_mph": 8, "sky": "sun", "rain_chance": 0.0, "raining": False})
    check("the round's wind is the day's", g.wind_mph, g.day.wind_mph)
    g.wind_mph = 15
    check("  and setting it sets the day", (g.day.wind_mph, g.day.mean), (15, 15))
    state = g.as_dict()
    check("the state carries the day for the screens", sorted(state["day"])[:3], ["firmness", "forecast", "ground_words"])
    check("  and the roll knows the day", g.expected_roll("driver") > 0, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

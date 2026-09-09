#!/usr/bin/env python3
"""When the sun crosses a height, from the ephemeris already in the program.

    python3 tests/test_sun.py

The sextant page has always needed the sun's altitude for an instant. Sunrise
is that same question asked backwards - which instant gives this altitude - so
it needs no new model, no feed and no cache: a unit with no network computes it
for any date and any latitude from the arithmetic it already carries. These
checks are here to hold that claim up.

The anchor is Greenwich on the June solstice, because that is the one sunrise
in the world with a published time everybody can look up, and because it is on
the prime meridian so a longitude sign error cannot hide in it. The rest are
the cases that catch the mistakes this kind of solver actually makes: the
polar ones, where the honest answer is that the sun never crosses at all; the
symmetry about solar noon, which fails first if the equation of time is
mishandled; and the half degree of refraction and semidiameter, which is why
an equinox day is not exactly twelve hours.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import celestial                                    # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def near(label, got, want, tol):
    ok = got is not None and abs(got - want) <= tol
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r} +/- {tol})"))
    if not ok:
        FAILS.append(label)


def local_midnight(y, m, d, tz_hours):
    """The start of somebody's day, expressed in UTC - what rise_set wants."""
    return datetime(y, m, d, tzinfo=timezone(timedelta(hours=tz_hours))
                    ).astimezone(timezone.utc)


def clock(when, tz_hours):
    """To the nearest minute, the way an almanac prints it - not truncated."""
    if when is None:
        return None
    local = when.astimezone(timezone(timedelta(hours=tz_hours)))
    local += timedelta(seconds=30)
    return local.strftime("%H:%M")


def main():
    print("-- the one sunrise everybody can look up --")
    # Greenwich, June solstice: the almanac prints 04:43 and 21:21 BST.
    start = local_midnight(2026, 6, 21, 1)
    rs = celestial.rise_set(51.4779, 0.0, start)
    check("sunrise over the prime meridian", clock(rs["rise"], 1), "04:43")
    check("  and sunset", clock(rs["set"], 1), "21:21")

    print("\n-- the sun is up longer than half the day, and here is why --")
    # On an equinox the geometric centre would be up for exactly twelve hours.
    # It is not, because sunrise is the upper limb and the atmosphere has
    # already lifted it: 16' of semidiameter and 34' of refraction between them
    # buy several extra minutes at each end.
    start = local_midnight(2026, 3, 20, 0)
    limb = celestial.day_length_hours(0.0, 0.0, start)
    centre = celestial.day_length_hours(0.0, 0.0, start,
                                        altitude=celestial.SUN_CENTRE)
    near("equinox on the equator, upper limb", limb, 12.12, 0.06)
    near("  the geometric centre, near enough twelve", centre, 12.0, 0.02)
    check("  so the illusion lengthens the day", limb > centre + 0.05, True)

    print("\n-- rise and set stand either side of solar noon --")
    # Whatever the date, the two crossings are equidistant from the sun's
    # transit. This is the check that catches an equation-of-time error: it
    # would slide both times the same way and leave the midpoint wrong.
    start = local_midnight(2026, 9, 9, -5)
    rs = celestial.rise_set(46.60, -94.31, start)
    middle = rs["rise"] + (rs["set"] - rs["rise"]) / 2
    noon_alt, noon_az = celestial.altitude_azimuth(46.60, -94.31, middle)
    near("  the sun is due south at the midpoint", noon_az, 180.0, 0.3)
    before = celestial.altitude_azimuth(46.60, -94.31,
                                        middle - timedelta(minutes=20))[0]
    after = celestial.altitude_azimuth(46.60, -94.31,
                                       middle + timedelta(minutes=20))[0]
    check("  and higher there than either side", noon_alt > before
          and noon_alt > after, True)

    print("\n-- what it says where the sun does not cross at all --")
    # Longyearbyen, well inside the circle. The honest answer is not a time.
    summer = celestial.rise_set(78.22, 15.65, local_midnight(2026, 6, 21, 2))
    check("midsummer: no sunrise", summer["rise"], None)
    check("  no sunset either", summer["set"], None)
    check("  because it never went down", summer["up_all_window"], True)
    check("  and that is not the same as polar night",
          summer["down_all_window"], False)
    near("  daylight, all of it",
         celestial.day_length_hours(78.22, 15.65,
                                    local_midnight(2026, 6, 21, 2)), 24.0, 0.01)

    winter = celestial.rise_set(78.22, 15.65, local_midnight(2026, 12, 21, 1))
    check("midwinter: still no sunrise", winter["rise"], None)
    check("  but for the opposite reason", winter["down_all_window"], True)
    near("  and no daylight to have",
         celestial.day_length_hours(78.22, 15.65,
                                    local_midnight(2026, 12, 21, 1)), 0.0, 0.01)

    print("\n-- the answer is where it says it is --")
    # Self-consistency: put the returned instant back through the altitude
    # routine and the sun should be sitting on the height that was asked for.
    # This is what proves the bisection converged rather than stopping nearby.
    for lat, lon, tz, name in [(46.60, -94.31, -5, "Pequot Lakes"),
                               (-33.87, 151.21, 11, "Sydney"),
                               (64.84, -147.72, -8, "Fairbanks")]:
        rs = celestial.rise_set(lat, lon, local_midnight(2026, 9, 9, tz))
        if rs["rise"] is None:
            continue
        alt = celestial.altitude_azimuth(lat, lon, rs["rise"])[0]
        near(f"  {name}: the sun is on the horizon at sunrise", alt,
             celestial.SUN_UPPER_LIMB, 0.0005)

    print("\n-- the heights are different events, and keep their order --")
    # Civil twilight begins before sunrise, nautical before that, astronomical
    # before that. If any pair swapped, a caller asking for "first light" would
    # be handed something after the sun was already up.
    start = local_midnight(2026, 9, 9, -5)
    times = {}
    for name, alt in [("astronomical", celestial.ASTRONOMICAL_TWILIGHT),
                      ("nautical", celestial.NAUTICAL_TWILIGHT),
                      ("civil", celestial.CIVIL_TWILIGHT),
                      ("greyline", -9.03),
                      ("sunrise", celestial.SUN_UPPER_LIMB)]:
        times[name] = celestial.rise_set(46.60, -94.31, start,
                                         altitude=alt)["rise"]
        print(f"        {name:<13} {clock(times[name], -5)}")
    check("astronomical first", times["astronomical"] < times["nautical"], True)
    check("  then nautical", times["nautical"] < times["greyline"], True)
    check("  then the D layer's own horizon",
          times["greyline"] < times["civil"], True)
    check("  then civil, then the sun itself",
          times["civil"] < times["sunrise"], True)

    print("\n-- it needs nothing but a clock --")
    # The point of the whole exercise: no feed, no cache, no stored table. If
    # this ever starts needing the network it will fail here first.
    import urllib.request
    opener = urllib.request.urlopen

    def refuse(*a, **k):
        raise AssertionError("rise_set tried to reach the network")

    urllib.request.urlopen = refuse
    try:
        off_grid = celestial.rise_set(46.60, -94.31,
                                      local_midnight(2031, 2, 14, -6))
        check("a sunrise five years out, with the wire cut",
              clock(off_grid["rise"], -6), "07:23")
    finally:
        urllib.request.urlopen = opener

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Checks for the three states of the sky, and the grey line in the middle.

    python3 tests/test_greyline.py

What this is guarding is not the sun - `test_celestial.py` does that - but the
decision to stop reducing the sun to one bit, and where the middle state is
put. The window is the ground terminator down to the D layer's own horizon
nine degrees below it: the sun has set here and not yet 80 km up, so the
absorber is collapsing while the F layer stays ionised.

The tempting alternative is to end it at the F2 peak's dip instead, 17 degrees
down, on the grounds that the reflector outlasts the absorber. It does, but by
slow recombination rather than by staying lit - so that version began an hour
that started after the absorption had already reached zero, and at 50 N in
June, where the sun never gets 17 degrees down, it ran for five hours. Both
failures are checked for below.

So: that the window sits on the absorption curve rather than beside it, that it
tracks the season on its own, that it stays a window at latitude, and that the
two places which used to answer this separately - the propagation model and the
advice in `reachout` - give the same answer at the same moment for the place.
"""
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import propagation as P, reachout as R  # noqa: E402

FAILS = []

# Pequot Lakes, Minnesota: far enough north that a fixed clock-hour rule comes
# apart on it, which is the failure this replaces.
LAT, LON = 46.5984, -94.3154
CDT = timezone(timedelta(hours=-5))


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def at(hour, minute=0, day=8):
    return datetime(2026, 9, day, hour, minute, tzinfo=CDT)


def regime_at(when):
    return P.sun_regime(P.solar_elevation(LAT, LON, when.astimezone(timezone.utc)))


def crossing(target, rising, month=9, day=8):
    """The minute the sun passes an angle, to the nearest minute."""
    prev = None
    for m in range(0, 24 * 60):
        when = datetime(2026, month, day, 0, 0, tzinfo=CDT) + timedelta(minutes=m)
        e = P.solar_elevation(LAT, LON, when.astimezone(timezone.utc))
        if prev is not None:
            if rising and prev < target <= e:
                return when
            if not rising and prev > target >= e:
                return when
        prev = e
    return None


def main():
    print("\n-- the lower edge is a layer height, not civil twilight --")
    check("the D layer keeps its sun 9 deg past the ground's",
          round(P.D_LAYER_DIP, 2), 9.03)
    check("  which is not the -6 this replaces", P.D_LAYER_DIP > 6.0, True)

    print("\n-- three states, and each boundary on the right side of itself --")
    check("noon is lit", P.sun_regime(45.0), "lit")
    check("the last moment of sunlight is still lit", P.sun_regime(0.0), "lit")
    check("a hair under, the ground has lost the sun and the D layer has not",
          P.sun_regime(-0.01), "grey")
    check("still grey at the D layer's own horizon",
          P.sun_regime(-P.D_LAYER_DIP), "grey")
    check("past that the absorber is wholly in shadow",
          P.sun_regime(-P.D_LAYER_DIP - 0.01), "dark")
    check("no position, no state", P.sun_regime(None), None)

    print("\n-- the window is a window, and it sits on the absorption curve --")
    sunset, d_set = crossing(0.0, False), crossing(-P.D_LAYER_DIP, False)
    span = (d_set - sunset).total_seconds() / 60.0
    check("the evening grey line lasts the best part of an hour",
          30 <= span <= 90, True)
    print(f"       (8 Sep at {LAT:.1f}N: {sunset:%H:%M} to {d_set:%H:%M} CDT,"
          f" {span:.0f} min)")
    check("  it starts at sunset, not an hour after it",
          regime_at(at(19, 45)), "grey")
    check("  and by nine it is over - absorption reached zero at half eight",
          regime_at(at(21, 0)), "dark")
    check("  the morning one ends at sunrise",
          crossing(-P.D_LAYER_DIP, True) < crossing(0.0, True), True)
    check("the states run lit, grey, dark in that order down the evening",
          [regime_at(at(19, 0)), regime_at(at(20, 0)), regime_at(at(21, 0))],
          ["lit", "grey", "dark"])

    print("\n-- absorption is what the window is supposed to be about --")
    # band_score's own D-layer term, read directly. If the state ever drifts
    # off this curve again, these are the numbers that will say so.
    def absorb(when):
        e = P.solar_elevation(LAT, LON, when.astimezone(timezone.utc))
        lit = max(-90.0, min(90.0, e + P.D_LAYER_DIP))
        return P.D_ABSORPTION * (max(0.0, math.sin(math.radians(lit))) ** 0.6)
    check("it is still absorbing when the window opens", absorb(sunset) > 5.0, True)
    check("and absorbing nothing by the time it shuts",
          round(absorb(d_set), 1), 0.0)
    print(f"       (80 m: {absorb(at(18, 30)):.1f} at 18:30, {absorb(sunset):.1f} "
          f"at sunset, {absorb(at(20, 15)):.1f} at 20:15, {absorb(d_set):.1f} after)")

    print("\n-- season comes out of the declination, not a clock hour --")
    lengths = {}
    for mon, dd in ((1, 15), (3, 15), (6, 21), (9, 8), (12, 15)):
        a, b = crossing(0.0, False, mon, dd), crossing(-P.D_LAYER_DIP, False, mon, dd)
        lengths[mon] = (b - a).total_seconds() / 60.0
    check("midsummer's window is the longest - the sun sets at a shallower angle",
          lengths[6] == max(lengths.values()), True)
    check("  and an equinox one the shortest", lengths[3] == min(lengths.values()), True)
    check("  but none of them runs away", max(lengths.values()) < 120, True)
    print("       (" + ", ".join(f"{m:02d}: {v:.0f} min" for m, v in sorted(lengths.items())) + ")")

    print("\n-- and it stays a window as the rig goes north --")
    for la in (40.0, 50.0, 55.0):
        run = best = 0
        t0 = datetime(2026, 6, 21, 12, 0, tzinfo=CDT)
        for mi in range(24 * 60):
            when = (t0 + timedelta(minutes=mi)).astimezone(timezone.utc)
            e = P.solar_elevation(la, LON, when)
            run = run + 1 if P.sun_regime(e, la, when) == "grey" else 0
            best = max(best, run)
        check(f"{la:.0f}N on 21 June is under two hours, not five", best < 120, True)
        print(f"       ({best} min)")

    print("\n-- Alaska in June: a long twilight, which is not a long grey line --")
    # The question this section exists to answer. At Anchorage the sun bottoms
    # out 5.3 degrees down: the ground loses it, the D layer 80 km up does not,
    # and 80 m absorption never falls below a third of its noon value. Calling
    # that the grey line would sell the worst season on the low bands as the
    # best hour of the day.
    june = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    # Same sun angle, four degrees under the horizon, at three places on the
    # same night. What separates them is whether the sun is going to finish the
    # job - and only the two with a position can know that.
    for name, la, want in (("Pequot Lakes", LAT, "grey"),
                           ("Anchorage", 61.22, "twilight"),
                           ("Fairbanks", 64.84, "twilight")):
        floor = P.night_floor(la, june)
        check(f"{name} at 4 deg down on the solstice (night floor {floor:+.1f})",
              P.sun_regime(-4.0, la, june), want)
    check("  and the deepest Anchorage gets is not even that far",
          P.night_floor(61.22, june) > -P.D_LAYER_DIP, True)
    check("  where Minnesota goes twice as deep as the D layer needs",
          P.night_floor(LAT, june) < -P.D_LAYER_DIP * 2, True)
    check("  and Utqiagvik has no night to have one in",
          P.day_ceiling(71.29, june) > 0 and P.night_floor(71.29, june) > 0, True)
    check("nor is polar noon in December a grey line",
          P.sun_regime(-3.0, 71.29, datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)),
          "twilight")
    check("  while the deep part of that day is honestly dark",
          P.sun_regime(-20.0, 71.29, datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)),
          "dark")

    print("\n-- the auroral oval, which the score used to assert and not apply --")
    check("Minnesota is 8 degrees further north magnetically than it is on a map",
          round(P.geomagnetic_latitude(LAT, LON)) , 55)
    check("  Fairbanks is further still", round(P.geomagnetic_latitude(64.84, -147.72)), 66)
    check("the factor is 1 where the K penalty was fitted",
          round(P.auroral_factor(P.AURORAL_REF), 2), 1.0)
    check("  about double under the oval", P.auroral_factor(65.0) >= 1.9, True)
    check("  and least where a storm is somebody else's problem",
          P.auroral_factor(25.0), 0.5)
    check("  a quiet field still costs nothing anywhere",
          P.band_score(7.1, 12.0, -40.0, 2.0, geomag_lat=70.0)["score"],
          P.band_score(7.1, 12.0, -40.0, 2.0)["score"])
    storm_mn = P.band_score(7.1, 12.0, -40.0, 5.0, geomag_lat=55.1)["score"]
    storm_ak = P.band_score(7.1, 12.0, -40.0, 5.0, geomag_lat=65.6)["score"]
    check("a K of 5 costs more at Fairbanks than in Minnesota",
          storm_ak < storm_mn, True)
    print(f"       (40 m at K 5: {storm_mn} in Minnesota, {storm_ak} at Fairbanks)")
    check("  and the words say which one you are getting",
          "auroral oval" in P.band_score(7.1, 12.0, -40.0, 5.0,
                                         geomag_lat=65.6)["why"], True)

    print("\n-- what the old boolean got wrong, at this latitude --")
    # 07:00 and 08:00 CDT: sun up, and the longitude-only rule called it night.
    check("half seven in the morning is daylight, and now says so",
          regime_at(at(7, 30)), "lit")
    check("  the sun agrees", P.solar_elevation(
        LAT, LON, at(7, 30).astimezone(timezone.utc)) > 0, True)
    # And what the first version of the fix got wrong: eight in the evening is
    # twenty minutes past sunset, absorption two thirds gone. That is the grey
    # line. Hanging the window on the F2 dip called it daylight and then put
    # the grey line at nine, when the sky here has been dark for half an hour.
    check("eight in the evening is the grey line, not daylight",
          regime_at(at(20, 0)), "grey")
    check("  and nine o'clock is not - that was the complaint",
          regime_at(at(21, 0)), "dark")

    print("\n-- one sun, answered the same way in both places --")
    for hh, mm in ((7, 30), (13, 0), (20, 50), (23, 0)):
        when = at(hh, mm)
        check(f"reachout and the model agree at {hh:02d}:{mm:02d}",
              R.sun_state(LAT, LON, when.timestamp()), regime_at(when))

    print("\n-- and the wall chart still gets one bit, off the right state --")
    ham = {"conditions": {("80m-40m", "day"): "Poor", ("80m-40m", "night"): "Good",
                          ("30m-20m", "day"): "Good", ("30m-20m", "night"): "Fair",
                          ("17m-15m", "day"): "Good", ("17m-15m", "night"): "Poor",
                          ("12m-10m", "day"): "Fair", ("12m-10m", "night"): "Poor"},
           "vhf": {}}
    lit = {r["band"]: r for r in P._band_rows(ham, "lit", 14.0)}
    grey = {r["band"]: r for r in P._band_rows(ham, "grey", 14.0)}
    dark = {r["band"]: r for r in P._band_rows(ham, "dark", 14.0)}
    check("lit reads the day column", lit["80m"]["rating"], "Poor")
    check("grey reads the night one - that column is about the absorber",
          grey["80m"]["rating"], "Good")
    check("  as does dark", dark["80m"]["rating"], "Good")
    check("and the grey line is named on the low bands",
          "grey line" in grey["80m"]["note"], True)
    check("  where by day the note is the absorption instead",
          "D-layer" in lit["80m"]["note"], True)
    check("  and after dark, nothing about the low bands at all",
          dark["80m"]["note"], "")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Checks for the band-quality model behind the band plan's second bar.

    python3 tests/test_propagation.py

The number this produces gets read by somebody deciding whether to call CQ on
SSB now or come back at eight o'clock and use CW, so what is tested here is not
particular values - it is a model, and the values will move as it is tuned -
but the things about the ionosphere that must never come out backwards.

Nothing here touches the network. The model is arithmetic over a flux figure, a
sun angle and a K index; the fetching is somebody else's job.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import propagation as P  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def score(mhz, muf, elevation, k=2):
    return P.band_score(mhz, muf, elevation, k)["score"]


def main():
    # A quiet sun, a mid-latitude QTH, a settled field.
    day_muf, _ = P.estimate_muf(110, 45)
    night_muf, _ = P.estimate_muf(110, -30)

    print("\n-- the shape of the day --")
    # The D layer exists only in daylight and absorbs hardest at the bottom of
    # the spectrum, which is the whole reason 80m is a local band at noon.
    check("80m is better at night than at noon",
          score(3.5, night_muf, -30) > score(3.5, day_muf, 45), True)
    check("40m is better at night than at noon",
          score(7.0, night_muf, -30) > score(7.0, day_muf, 45), True)
    # And the F layer thins after dark, which takes the high bands with it.
    check("20m is better at noon than at night",
          score(14.0, day_muf, 45) > score(14.0, night_muf, -30), True)

    print("\n-- the MUF is a ceiling, not a suggestion --")
    check("a band well above the MUF is shut", score(28.0, 12.0, 30), 0)
    check("  and just over it is poor, not shut",
          0 < score(13.0, 12.0, 30) < 35, True)
    check("just under the MUF is the best place to be",
          score(10.0, 12.0, 30) > score(3.5, 12.0, 30), True)

    print("\n-- a disturbed field costs everybody --")
    quiet = score(14.0, day_muf, 45, k=1)
    storm = score(14.0, day_muf, 45, k=7)
    check("a K7 storm scores lower than a quiet field", storm < quiet, True)
    check("  and says so in words",
          "flutter" in P.band_score(14.0, day_muf, 45, 7)["why"], True)

    print("\n-- the F layer thins at night, it does not vanish --")
    # The model used to close 40m at midnight in a quiet sun, which is the one
    # thing every operator knows to be false.
    for sfi in (68, 75, 90):
        muf, fof2 = P.estimate_muf(sfi, -40)
        check(f"a quiet midnight at SFI {sfi} still keeps 40m open",
              score(7.0, muf, -40) >= 35, True)

    print("\n-- what a score is worth in practice --")
    check("a good band is open to SSB",
          "SSB" in P.band_score(10.1, 12.0, 20)["modes"], True)
    check("a marginal one is CW and FT8", P._pick(P.MODES, 45),
          "CW and FT8 comfortably; SSB will be a struggle")
    check("a bad one is FT8 or nothing", P._pick(P.MODES, 25),
          "FT8 and CW only")
    check("and a shut band says so", P._pick(P.MODES, 5),
          "nothing much - the band is not open")

    print("\n-- the next 24 hours --")
    start = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    hours = P.outlook(7.0, 44.98, -93.27, sfi=110, k_index=2, start=start)
    check("an hour a piece, and the hour it starts", len(hours), 25)
    check("  starting where it was told to", hours[0]["at"], start.isoformat())
    check("  and every one of them scored",
          all(0 <= h["score"] <= 100 for h in hours), True)
    check("  with day and night in it",
          len({h["day"] for h in hours}), 2)
    # 40m is a night band, so its best hour is not a daylight one. It is not
    # at the grey line either: with no path and no far end, nothing here can
    # produce the terminator enhancement, and the model settles on the middle
    # of the night. Saying otherwise - as this comment used to - was claiming
    # something the numbers do not show.
    best = max(hours, key=lambda h: h["score"])
    check("40m's best hour is not the middle of the day",
          best["elevation"] < 15, True)
    noon = max(hours, key=lambda h: h["elevation"])
    check("20m's best hour is not", max(
        P.outlook(14.0, 44.98, -93.27, sfi=110, start=start),
        key=lambda h: h["score"])["day"], True)
    check("  and the sun is up at local noon", noon["day"], True)

    print("\n-- a measurement beats a model about the level --")
    plain = P.outlook(14.0, 44.98, -93.27, sfi=110, start=start)
    measured = round(plain[0]["muf"] * 1.4, 1)
    anchored = P.outlook(14.0, 44.98, -93.27, sfi=110, start=start,
                         muf_now=measured)
    check("the curve is scaled to meet what was measured",
          abs(anchored[0]["muf"] - measured) < 0.6, True)
    check("  and every hour is scaled with it",
          abs(anchored[12]["muf"] / plain[12]["muf"] - 1.4) < 0.05, True)
    # A reading that disagrees with the model by more than the model could
    # plausibly be wrong by is a different sky, or a broken station.
    check("a wild reading is bounded rather than believed",
          P.muf_anchor(110, 44.98, -93.27, 400.0), P.ANCHOR_RANGE[1])
    check("  and no reading at all changes nothing",
          P.muf_anchor(110, 44.98, -93.27, None), 1.0)

    print("\n-- when a band is worth using --")
    night = P.outlook(3.5, 44.98, -93.27, sfi=110, k_index=2, start=start)
    runs = P.windows(night)
    check("80m has a window and it is at night", bool(runs), True)
    check("  and it does not run the whole day",
          runs[0]["from"] != night[0]["at"] or len(runs) > 1
          or runs[0]["to"] != night[-1]["at"], True)
    shut = [dict(h, score=0) for h in night]
    check("a band that is never open has no window", P.windows(shut), [])

    print("\n-- the absorbing layer is 80 km up, not underfoot --")
    # The D layer keeps its daylight about nine degrees longer than the ground
    # does, because it is 80 km closer to the sun's line. The term this
    # replaces switched absorption off at the geometric horizon, so the low
    # bands opened nine degrees early and did it between one sample and the
    # next.
    import math as _math
    check("the dip is geometry, not a tuned number",
          round(P.D_LAYER_DIP, 3),
          round(_math.degrees(_math.acos(P.EARTH_RADIUS_KM /
                                         (P.EARTH_RADIUS_KM + P.D_LAYER_KM))), 3))
    check("  which for 80 km is about nine degrees",
          8.5 < P.D_LAYER_DIP < 9.6, True)

    def absorbed(mhz, elev):
        """How much the D layer is taking out, in points of score."""
        clear = P.band_score(mhz, 100.0, -90.0, 0)["score"]
        return clear - P.band_score(mhz, 100.0, elev, 0)["score"]

    check("the band is not wide open the moment the sun touches the horizon",
          absorbed(3.5, 0.0) > 5, True)
    check("  and absorption is gone once the layer itself is in the dark",
          absorbed(3.5, -(P.D_LAYER_DIP + 0.5)), 0)
    check("  with nothing left well below that", absorbed(3.5, -20.0), 0)
    # A step would show up as two values where there should be a slope.
    slope = [absorbed(3.5, e) for e in (6, 3, 0, -3, -6, -9)]
    check("the evening is a ramp, not a cliff",
          len(set(slope)), len(slope))
    check("  running downhill the whole way",
          all(a >= b for a, b in zip(slope, slope[1:])), True)
    check("high bands barely notice it either way",
          absorbed(28.0, 30.0) < 3, True)

    print("\n-- the night is not one number --")
    # The old model's day term was sin(elevation) to a power, which is exactly
    # zero at every negative angle, so every hour of every night at every
    # latitude came out identical - and a quarter low. That flatness is what
    # made the band conditions page and the Lab disagree about foF2.
    deep = P._fof2(110, -60, 45)
    dusk = P._fof2(110, -8, 45)
    check("dusk has more layer left than the middle of the night", dusk > deep, True)
    check("  and the difference is real, not rounding",
          dusk - deep > 0.2, True)
    check("the sun still moves it after it has set",
          len({round(P._fof2(110, e, 45), 2) for e in (-40, -20, -10)}), 3)
    check("and noon is well above any of them", P._fof2(110, 60, 45) > dusk, True)

    print("\n-- the model cannot assert an ionosphere that has never existed --")
    # A fitted curve and a multiplier do not know what the earth does. Left
    # alone they stacked up to a MUF near 130 MHz, which is not a prediction,
    # it is arithmetic that got away - and it would be quoted back as fact
    # because it appeared on a screen with a number next to it.
    check("foF2 is held to what has been observed",
          P._fof2(400, 90, 0), P.FOF2_OBSERVED[1])
    check("  even after an ionosonde correction is applied",
          P.levels(400, 90, 0, 3.66, 2.0)[1], P.FOF2_OBSERVED[1])
    check("  and it cannot be talked below the floor either",
          P._fof2(0, -90, 89) >= P.FOF2_OBSERVED[0], True)
    check("the ceiling is where the equatorial anomaly really tops out",
          14.0 <= P.FOF2_OBSERVED[1] <= 17.0, True)
    # It has to stay generous enough for the rare things that do happen.
    check("a 6m F2 opening is still reachable, because it is real",
          P.levels(240, 90, 10, 3.6, 1.3)[0] > 50.0, True)
    check("  while an ordinary evening is untouched",
          P.levels(110, -20, 46)[0] < 15.0, True)

    print("\n-- where you are, not just when --")
    check("the tropics carry more layer than the poles",
          P._fof2(110, 30, 10) > P._fof2(110, 30, 65), True)
    check("  and the two hemispheres are alike",
          P._fof2(110, 30, 40), P._fof2(110, 30, -40))
    check("no QTH is treated as mid-latitude",
          P._fof2(110, 30), P._fof2(110, 30, P.ASSUMED_LATITUDE))

    print("\n-- a reading is carried as an error, not as a level --")
    # The bug this replaces: a sonde's reading was divided by the model
    # evaluated at the *operator's* location, so "the model is low" and "the
    # sonde is in daylight and I am not" arrived as a single number. Corrected
    # at the station's own sun angle, a station that agrees with the model must
    # produce a factor of 1.0 however far away it is and whatever its sun is
    # doing - which is the whole reason the radius can be opened up.
    when = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    here = (45.0, -93.0)

    def honest(lat, lon, scale=1.0):
        """A station reporting exactly what the model expects of it."""
        elev = P.solar_elevation(lat, lon, when)
        return {"lat": lat, "lon": lon, "name": f"{lat},{lon}",
                "fof2": P._fof2(110, elev, lat) * scale, "m3000": 2.9,
                "age_minutes": 5}

    for lon in (-93.0, -120.0, -70.0):
        agrees = P.calibration(110, *here, when=when, sondes=[honest(45.0, lon)])
        check(f"a station at {lon:.0f} that agrees with the model asks for no change",
              agrees["factor"], 1.0)
    far = P.calibration(110, *here, when=when, sondes=[honest(25.0, -110.0)])
    check("  and so does one 2600 km off in a different latitude and sun",
          far["factor"], 1.0)
    check("    which the old anchor could not have managed",
          round(P.muf_anchor(110, *here,
                             P._fof2(110, P.solar_elevation(25.0, -110.0, when), 25.0) * 2.9,
                             when), 2) != 1.0, True)

    # And a station that really does disagree is still believed.
    low = P.calibration(110, *here, when=when, sondes=[honest(45.0, -100.0, 1.4)])
    check("a station reading 40% high moves the model 40%", low["factor"], 1.4)

    print("\n-- one bad station cannot drag it --")
    # The autoscaler loses the F2 trace often enough that this matters, and the
    # broken station is as likely as any other to be the closest one.
    votes = [honest(45.0, -93.0, 3.0),        # nearest, and wrong
             honest(45.0, -100.0), honest(45.0, -86.0)]
    robust = P.calibration(110, *here, when=when, sondes=votes)
    check("the weighted median ignores the outlier", robust["factor"], 1.0)
    check("  though it still counted the station", robust["stations"], 3)
    check("a reading beyond all reason is bounded",
          P.calibration(110, *here, when=when,
                        sondes=[honest(45.0, -93.0, 40.0)])["factor"],
          P.ANCHOR_RANGE[1])
    check("  and says that is what happened",
          P.calibration(110, *here, when=when,
                        sondes=[honest(45.0, -93.0, 40.0)])["source"], "bounded")
    check("nothing in range is admitted rather than guessed",
          P.calibration(110, *here, when=when, sondes=[honest(-40.0, 140.0)]), None)
    check("  and no QTH means no calibration at all",
          P.calibration(110, None, None, when=when, sondes=[honest(45.0, -93.0)]), None)

    print("\n-- distance costs, but is no longer a cliff --")
    near_w = 1.0 / (1.0 + (200.0 / P.CALIBRATION_HALF_KM) ** 2)
    far_w = 1.0 / (1.0 + (4000.0 / P.CALIBRATION_HALF_KM) ** 2)
    check("a close station outvotes a distant one", near_w > 4 * far_w, True)
    check("  but the distant one still has a voice", far_w > 0.0, True)
    check("the old 2000 km cliff is gone", P.CALIBRATION_KM > 2000, True)

    print("\n-- foF2 and MUF are the same number twice --")
    # They are shown on different pages. They must not be able to drift.
    muf, fof2 = P.estimate_muf(110, 30, 45, 2.9)
    check("MUF is foF2 times the secant factor, and nothing else",
          abs(muf - fof2 * 2.9) < 0.1, True)
    check("a measured M(3000) is used when there is one",
          P.estimate_muf(110, 30, 45, 2.5)[0] < P.estimate_muf(110, 30, 45, 3.4)[0],
          True)
    check("  and the fallback is the network median, not 3.2",
          P.M3000_DEFAULT, 2.9)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

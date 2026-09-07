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
    # 40m is a night band. Its best hour is not necessarily "dark" - the
    # model puts it at the grey line, where the D layer has gone but the MUF
    # has not yet fallen through the band, which is where it belongs.
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

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

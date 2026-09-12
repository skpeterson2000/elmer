#!/usr/bin/env python3
"""How far a sonde reading may be carried, and what to say when we disagree.

    python3 tests/test_anchor.py

This exists because of a real failure, and the checks are shaped like it.

20 m sat at Red for twenty-four hours straight on a solar flux of 110, while
the wall chart every operator already reads called the same band Good day and
night. Every sonde in reach was in darkness and they agreed the model reads
high at night, giving an anchor of about 0.74 - and that night factor was then
applied unchanged to the following noon. Checked against every sonde reporting
anywhere at one instant, the ratio of measured to modelled foF2 ran about 0.77
in darkness and about 1.20 in daylight: the model's error does not merely
change size with the sun, it changes sign. So the anchor was wrong twice over
by midday, and put the MUF at 11 MHz where the model alone said 17.

The fix is that an anchor is evidence about the sky it was measured under and
is released as the sky moves away from that. What is guarded here is that it
still holds where it was measured - the nowcast was never the problem - and
that it has let go by the time the sun is properly up.

The second half is what to say when ELMER and the wall chart part company. The
first version of that note claimed ours was "the better informed of the two"
whenever a sonde was in reach, which is precisely what it would have said on
the morning it was wrong for a whole day. A flat contradiction now claims
nothing for either side, and that is checked.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import propagation as P                              # noqa: E402

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


def main():
    print("-- an anchor holds where it was measured --")
    # Measured under a night sky, 27 degrees below the horizon.
    near("at the sun it was read under, full strength",
         P.anchor_at(0.738, -27.0, -27.0), 0.738, 1e-9)
    near("  and a few degrees away, still full strength",
         P.anchor_at(0.738, -27.0, -33.0), 0.738, 1e-9)
    check("  which keeps the current hour exactly as it was",
          P.anchor_at(0.738, -27.0, -27.0) == 0.738, True)

    print("\n-- and lets go as the sky stops being that sky --")
    check("by the time the sun is well up it is gone",
          P.anchor_at(0.738, -27.0, 44.0), 1.0)
    mid = P.anchor_at(0.738, -27.0, 0.0)
    check("  in between it is in between", 0.738 < mid < 1.0, True)
    # It fades in both directions, being strongest at the sky it was read
    # under - so the walk is checked away from that point, not across it.
    walk = [P.anchor_at(0.738, -27.0, e) for e in range(-27, 50, 5)]
    check("  and never goes backwards on the way up",
          all(b >= a - 1e-9 for a, b in zip(walk, walk[1:])), True)
    check("  it is symmetric about the sky it was read under",
          round(P.anchor_at(0.738, -27.0, -47.0), 6),
          round(P.anchor_at(0.738, -27.0, -7.0), 6))
    # An anchor above 1 has to fade the same way, downward to 1.
    check("a high anchor fades down, not up",
          P.anchor_at(1.30, 40.0, -30.0), 1.0)
    check("no anchor at all is simply the model", P.anchor_at(None, 0.0, 0.0), 1.0)
    check("  and an anchor with no sky attached is used as it stands",
          P.anchor_at(0.9, None, 40.0), 0.9)
    # The same sun angle comes round twice a day and the sky under it is not
    # the same sky: a reading from eleven at night must not be applied in full
    # at six the next morning because the sun is back at -27.
    check("held in full three hours on", P.anchor_at(0.738, -27.0, -27.0, hours_since=3), 0.738)
    check("  letting go across the night", 0.738 < P.anchor_at(0.738, -27.0, -27.0, hours_since=6) < 1.0, True)
    check("  and gone by the other side of it, same sun angle or not",
          P.anchor_at(0.738, -27.0, -27.0, hours_since=9), 1.0)
    check("  whichever has let go further decides",
          P.anchor_at(0.738, -27.0, 44.0, hours_since=1), 1.0)

    print("\n-- the failure itself: night must not close the next day --")
    # The numbers from the morning it went wrong.
    sfi, m3000, night_anchor, night_sun = 110.0, 2.81, 0.738, -27.0
    muf_noon_naive = P.levels(sfi, 44.0, 46.6, m3000, night_anchor)[0]
    muf_noon_faded = P.levels(sfi, 44.0, 46.6, m3000,
                              P.anchor_at(night_anchor, night_sun, 44.0))[0]
    check("carried blindly, noon's MUF fell under 20 m",
          muf_noon_naive < 14.0, True)
    check("  released, it is above it", muf_noon_faded > 14.0, True)
    naive = P.band_score(14.0, muf_noon_naive, 44.0, 2, 3.9, 300.0)["score"]
    faded = P.band_score(14.0, muf_noon_faded, 44.0, 2, 5.8, 300.0)["score"]
    # Poor rather than shut, since the score stopped falling off a cliff at
    # the MUF: at 1.16 of it a full hop mostly fails and shorter ones do not.
    check("  and 20 m goes from poor to open at midday",
          (naive < 30, faded > 70), (True, True))
    # The hour it was measured for is untouched by all of this.
    a = P.levels(sfi, night_sun, 46.6, m3000, night_anchor)[0]
    b = P.levels(sfi, night_sun, 46.6, m3000,
                 P.anchor_at(night_anchor, night_sun, night_sun))[0]
    check("  while the night it was measured for is unchanged", a, b)

    print("\n-- the calibration says what sky it was read under --")
    sondes = [{"name": "A", "lat": 43.8, "lon": -112.7, "fof2": 2.58,
               "m3000": 2.81, "age_minutes": 10},
              {"name": "B", "lat": 42.6, "lon": -71.5, "fof2": 2.77,
               "m3000": 2.80, "age_minutes": 12}]
    cal = P.calibration(110.0, 46.6, -94.3, sondes=sondes)
    check("it reports a sun angle at all", cal["sun_deg"] is not None, True)
    check("  and a factor", 0.3 < cal["factor"] < 3.0, True)

    print("\n-- ours against the wall chart --")
    check("nothing to compare against is not an error",
          P.reconcile(50, ""), None)
    check("  nor is a rating we do not know", P.reconcile(50, "Excellent"), None)
    agree = P.reconcile(93, "Good", "measured")
    check("agreement is agreement", (agree["agree"], agree["gap"]), (True, 0))
    check("  and says nothing further", agree["note"], "")
    one = P.reconcile(45, "Good", "measured")
    check("one word apart is a disagreement", (one["agree"], one["gap"]),
          (False, 1))

    print("\n-- a flat contradiction claims nothing for either side --")
    # This is the exact shape of the morning it was wrong: Good against Poor,
    # with a measured anchor in hand. The note must not take our own side.
    for source in ("measured", "regional", "bounded", "estimated", None):
        flat = P.reconcile(5, "Good", source)
        check(f"{source}: it is called a contradiction",
              "flat contradiction" in flat["note"], True)
        check("  and does not claim we are better informed",
              "better informed" in flat["note"], False)
        check("  it says to doubt this page first",
              "doubt this page first" in flat["note"], True)
        check("  and to go and listen",
              "Turn the radio on" in flat["note"], True)
    # One step apart is still allowed to explain which is better founded -
    # that is a real difference of method, not a symptom.
    soft = P.reconcile(45, "Good", "estimated")
    check("one step apart may still say who is better founded",
          "better founded" in soft["note"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

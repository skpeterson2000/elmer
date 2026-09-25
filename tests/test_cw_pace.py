#!/usr/bin/env python3
"""The record keeps how long it took, so the work can be seen working.

    python3 tests/test_cw_pace.py

The one thing a learner cannot see from inside is that they are getting
faster. The percentage they can feel. "K took you three seconds when you
started and under one now" they cannot, because the record knew whether
the answer was right and threw the clock away the moment the session
ended.

It keeps it now: `times` is the recent recognitions in milliseconds and
`first_ms` is what it took at the start, written once from the earliest
few and never touched again - a baseline that moved with the record would
have nothing to say.

Only recognitions are timed. A miss has a duration too and it means
nothing: it is how long somebody waited before guessing.

Nothing here touches the network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import cw, db  # noqa: E402
from elmer.app import app, conn  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def record(ch, ms, copied=None):
    with app.test_request_context("/"):
        k = conn()
        db.cw_record(k, {ch: {"sent": len(ms), "copied": copied if copied is not None else len(ms),
                              "ms": ms}})
        return db.cw_progress(k).get(ch)


def main():
    print("\n-- the clock is kept, and a baseline is taken once --")
    got = record("K", [3200, 3000, 3100, 2900, 3300])
    check("five recognitions are remembered", len(got["times"].split(",")), 5)
    check("  and the baseline is their mean", round(got["first_ms"]), 3100)

    # Four, because the "now" is the mean of the last four: with three the
    # window still has a slow one in it and the figure is honest about that
    # rather than flattering - it reads 1.5 s and 51%, not 0.9 and 70.
    got = record("K", [900, 1000, 880, 920])
    check("more are added", len(got["times"].split(",")), 9)
    check("  and the baseline does not move", round(got["first_ms"]), 3100)

    print("\n-- which makes the before-and-after sayable --")
    said = cw.pace(got)
    check("it took three seconds at the start", said["first_s"], 3.1)
    check("  and about one now", said["now_s"] < 1.2, True)
    check("  which is faster, and worth saying", said["faster"], True)
    check("  by this much", said["by"] >= 60, True)

    print("\n-- and unsayable when it would be noise --")
    check("no baseline yet", cw.pace({"first_ms": None, "times": "900,1000"}), None)
    check("  too few recent answers",
          cw.pace({"first_ms": 3000.0, "times": "900,1000"}), None)
    steady = cw.pace({"first_ms": 1000.0, "times": "980,1010,1000,990"})
    check("  a difference inside the noise is not called faster",
          steady["faster"], False)
    check("  nothing at all", cw.pace(None), None)

    print("\n-- only what was recognized is timed --")
    # The client sends times for right answers only; the record also refuses
    # anything absurd, because a tab left open overnight is not a reaction.
    got = record("M", [800, 0, -5, 900, 999999])
    check("nonsense is dropped", len(got["times"].split(",")), 2)

    print("\n-- the quickest is the one worth showing --")
    quick = {"first_ms": 3000.0, "times": "800,820,810,790"}
    slower = {"first_ms": 1200.0, "times": "1000,1010,990,1005"}
    ranked = cw.paces({"K": quick, "M": slower})
    check("both improved, K by more", [p["ch"] for p in ranked], ["K", "M"])
    check("  and one that has not is left out",
          [p["ch"] for p in cw.paces({"M": {"first_ms": 1000.0, "times": "1000,1000,1000,1000"}})], [])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

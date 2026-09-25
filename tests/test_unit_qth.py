#!/usr/bin/env python3
"""The QTH answers for the station, not only for whoever is signed in.

    python3 tests/test_unit_qth.py

The other programs on the bench ask ELMER where the station is - TowerWitch
does, when the laptop has no receiver and the puck is out in the vehicle -
and they arrive over the LAN as nobody in particular. They were being
answered from whichever profile that turned out to be, which on a unit
where one operator had typed the QTH in and another had not was the one
that had not. ELMER knew where it was and said it did not.

A QTH is where the station is, and a station has one. So when the asking
profile has none, whoever on this unit has named the place is the answer -
under the unit's own position-sharing switch, because "do not tell anything
where I am" has to mean this too, and named in `qth_from` rather than
passed off as the asker's own.

Nothing here touches the network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db as edb  # noqa: E402
from elmer.app import app, conn  # noqa: E402

FAILS = []

PEQUOT = {"lat": 46.60302, "lon": -94.30944, "grid": "EN26uo",
          "short": "Pequot Lakes"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def qth():
    return app.test_client().get("/api/gps").get_json().get("qth")


def main():
    print("\n-- with nobody having named a place --")
    with app.test_request_context("/"):
        k = conn()
        s = edb.get_profile(k)["settings"]
        s.pop("location", None)
        edb.save_settings(k, s)
    check("there is nothing to give", qth(), None)

    print("\n-- one operator on this unit names it --")
    with app.test_request_context("/"):
        k = conn()
        made = edb.add_user(k, "Scott Peterson", "KC9SP")
        k.user_id = made["id"] if isinstance(made, dict) else made
        s = edb.get_profile(k)["settings"]
        s["location"] = dict(PEQUOT)
        edb.save_settings(k, s)
    got = qth()
    check("asked as somebody else, the station still answers",
          (round(got["lat"], 3), round(got["lon"], 3)), (46.603, -94.309))
    check("  with the grid", got["grid"], "EN26uo")
    check("  and says whose it is rather than claiming it",
          got["qth_from"], "KC9SP")

    print("\n-- the unit's own switch governs it --")
    with app.test_request_context("/"):
        edb.unit_set(conn(), "share_position", "off")
    check("position-sharing off means this too", qth(), None)
    with app.test_request_context("/"):
        edb.unit_set(conn(), "share_position", "on")
    check("  and back on again", bool(qth()), True)

    print("\n-- somebody's own QTH is their own, not borrowed --")
    with app.test_request_context("/"):
        k = conn()
        s = edb.get_profile(k)["settings"]
        s["location"] = dict(PEQUOT)
        edb.save_settings(k, s)
    check("no borrowing when the asker has one", qth()["qth_from"], None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

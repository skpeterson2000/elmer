#!/usr/bin/env python3
"""A typed QTH outranks another program's last known position.

    python3 tests/test_qth_outranks_lastknown.py

ELMER will read TowerWitch's state file when it has nothing better, and it
should: on a unit where TowerWitch has been running and ELMER has just
started, it is the difference between knowing roughly where the station is
and knowing nothing at all. gps.py says so, and says the position "is not
a live fix and is not presented as one".

It was presented as one. It came back from place() like any other fix, and
qth_for lets a live fix outrank the typed square because these Pis travel.
So the band plan went to Minneapolis on a station whose operator had set
Pequot Lakes - Minneapolis being the default TowerWitch falls back to when
it has no receiver. The one program on the bench that knew where the
station was, overruled by the one that says outright that it does not.

A real fix still wins. That part was never wrong.

Nothing here touches the network.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db as edb  # noqa: E402
from elmer import gps as elmer_gps  # noqa: E402
from elmer.app import app, conn, qth_for  # noqa: E402

FAILS = []

PEQUOT = {"lat": 46.60302, "lon": -94.30944, "grid": "EN26uo",
          "short": "Pequot Lakes"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def position(found, qth):
    """Where ELMER says the station is, given a fix and a typed QTH."""
    real = elmer_gps.place
    elmer_gps.place = lambda conn: found
    try:
        with app.test_request_context("/"):
            k = conn()
            s = edb.get_profile(k)["settings"]
            if qth:
                s["location"] = dict(qth)
            else:
                s.pop("location", None)
            edb.save_settings(k, s)
            got = qth_for(k, edb.get_profile(k))
            return round(got["lat"], 3) if got.get("lat") is not None else None
    finally:
        elmer_gps.place = real


def last_known(lat, lon):
    return {"lat": lat, "lon": lon, "alt_m": None, "mode": 2,
            "read_at": time.time(), "source": "towerwitch",
            "last_known": True, "from": "TowerWitch's last known position"}


def a_real_fix(lat, lon):
    return {"lat": lat, "lon": lon, "alt_m": None, "mode": 3,
            "read_at": time.time(), "source": "gps"}


def main():
    print("\n-- the operator's own answer wins over a file --")
    check("QTH set, TowerWitch's file says Minneapolis",
          position(last_known(44.9778, -93.265), PEQUOT), 46.603)
    check("  which is the QTH and not the file", 
          position(last_known(44.9778, -93.265), PEQUOT) != 44.978, True)

    print("\n-- but the file is still better than nothing --")
    check("no QTH at all, and TowerWitch has been running",
          position(last_known(44.9778, -93.265), None), 44.978)

    print("\n-- and a real fix still outranks the typed square --")
    # Not a regression to guard against: these Pis travel, and every answer
    # about reach and bearing is an answer about a place.
    check("a receiver with a 3D fix", position(a_real_fix(44.9778, -93.265), PEQUOT), 44.978)
    check("  even a long way from the typed square",
          position(a_real_fix(39.74, -104.98), PEQUOT), 39.74)

    print("\n-- the flag is what tells them apart --")
    check("a last-known carries it", last_known(1, 2).get("last_known"), True)
    check("  a real fix does not", a_real_fix(1, 2).get("last_known"), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Where the position comes from, how it has been going, and what to move.

    python3 tests/test_gps_sleuth.py

The fix says its source; the sleuth reads a quarter hour of samples and
says, in words, which antenna to move - or when a phone is not going to be
enough and a receiver on a lead is the move. A good fix that has held gets
no advice at all. Nothing here touches a receiver: the histories are made up.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import gps, phonegps  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    now = time.time()

    print("\n-- a receiver with a good fix is left alone --")
    good = {"source": "gps", "mode": 3, "sats": 11, "seen": 14, "hdop": 0.9, "read_at": now}
    v = gps.sleuth(good, [{"t": now - 60, "located": True, "source": "gps", "mode": 3, "sats": 11, "hdop": 0.9}])
    check("the source in words", v["words"], "a receiver on this unit (gpsd)")
    check("  the quality in numbers", v["quality"], "3D, 11 satellites of 14 seen, HDOP 0.9")
    check("  and nothing to do", v["advice"], None)

    print("\n-- a receiver short of satellites: move the puck --")
    weak = {"source": "gps", "mode": 2, "sats": 3, "seen": 9, "hdop": 7.2, "read_at": now}
    v = gps.sleuth(weak, [])
    check("says how many", "3 in use" in v["advice"], True)
    check("  and where to put it", "roof" in v["advice"] and "heated glass" in v["advice"], True)

    print("\n-- a phone that keeps dropping: the dash, then a receiver --")
    hist = [{"t": now - 600 + i * 20, "located": i % 4 != 3, "source": "phone", "mode": 3, "sats": 4, "hdop": 6.0}
            for i in range(30)]
    v = gps.sleuth({"source": "phone", "mode": 3, "sats": 4, "hdop": 6.0, "read_at": now}, hist)
    check("counts the drops", v["drops"], 7)
    check("  names the phone", v["words"], "a phone streaming to this unit")
    check("  the dash first", "dash" in v["advice"], True)
    check("  then the receiver on a lead", "USB receiver" in v["advice"], True)

    print("\n-- one weak sample is not a verdict --")
    v = gps.sleuth({"source": "phone", "mode": 3, "sats": 4, "hdop": 6.5, "read_at": now},
                   [{"t": now, "located": True, "source": "phone", "mode": 3, "sats": 4, "hdop": 6.5}])
    check("no advice from one look", v["advice"], None)

    print("\n-- the fix has gone --")
    v = gps.sleuth(None, hist)
    check("says whose fix went", v["words"], "the fix from a phone streaming to this unit has gone")
    check("  and what will have done it", "pocket" in v["advice"], True)
    v = gps.sleuth(None, [{"t": now - 30, "located": True, "source": "gps", "mode": 3, "sats": 8}])
    check("a receiver's fix gone: move the puck", "move the puck" in v["advice"], True)
    check("nothing ever: nothing to say", gps.sleuth(None, [])["advice"], None)

    print("\n-- the phone's GGA carries the satellites and the geometry --")
    body = "GPGGA,061000.00,4635.898,N,09418.924,W,1,04,6.5,380.0,M,-30.0,M,,"
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    got = phonegps.parse(f"${body}*{cs:02X}")
    check("satellites and HDOP", (got["sats"], got["hdop"]), (4, 6.5))

    print("\n-- gpsd's SKY, summarised --")
    sky = {"class": "SKY", "hdop": 1.1, "satellites": [{"used": True}] * 9 + [{"used": False}] * 3}
    check("used, seen, hdop", gps.sky_summary(sky), {"sats": 9, "seen": 12, "hdop": 1.1})

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())

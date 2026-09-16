#!/usr/bin/env python3
"""Checks for the repeater list: a GMRS machine is told from an amateur one
by its frequency, and is offered only to a GMRS radio.

    python3 tests/test_repeaters.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import callsign, reachout, repeaters as R  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        R.STORE = Path(tmp) / "repeaters.json"
        R._cache["key"] = None
        return run()


def run():
    print("\n-- a machine's service is certain from its output --")
    check("462.675 is GMRS", R.service_of(462.675), "gmrs")
    check("  and so is 462.550, written as a string", R.service_of("462.550"), "gmrs")
    check("442.675 is an amateur 70 cm repeater", R.service_of(442.675), "amateur")
    check("  as is 146.940", R.service_of(146.94), "amateur")
    check("462.5625 - FRS channel 1, no repeater there - is not GMRS repeater output", R.service_of(462.5625), "amateur")
    row = R._row("WRXX123", 462.675, tone="141.3", location="Brainerd", lat=46.36, lon=-94.20)
    check("a GMRS row carries its service and its own band", (row["service"], row["band"]), ("gmrs", "GMRS"))
    ham = R._row("W0ABC", 146.94, tone="100.0", location="Brainerd", lat=46.36, lon=-94.20)
    check("  and an amateur row its own", (ham["service"], ham["band"]), ("amateur", "2 m"))

    print("\n-- kept apart in what is offered --")
    R.save([row, ham], "the test")
    near_ham, _ = R.nearby(46.60, -94.31, None, limit=8)
    check("the amateur list has the amateur machine and not the GMRS one", [r["call"] for r in near_ham], ["W0ABC"])
    near_gmrs, _ = R.nearby(46.60, -94.31, None, limit=8, service="gmrs")
    check("  the GMRS list the other", [r["call"] for r in near_gmrs], ["WRXX123"])
    both, _ = R.nearby(46.60, -94.31, None, limit=8, service=None)
    check("  and both when asked for both", len(both), 2)

    print("\n-- on Make Contact --")
    ways = reachout.ways(46.60, -94.31, ["ht"], "Technician")
    keys = [w["key"] for w in ways]
    check("a Technician with a handheld is offered the amateur repeater", "repeater" in keys, True)
    check("  and never the GMRS one", "gmrs-repeater" in keys, False)
    rep = next(w for w in ways if w["key"] == "repeater")
    check("  whose card lists only amateur machines", [r["call"] for r in rep["rows"]], ["W0ABC"])
    ways = reachout.ways(46.60, -94.31, ["gmrs"], "none")
    keys = [w["key"] for w in ways]
    check("a GMRS radio with no amateur licence is offered the GMRS repeater", "gmrs-repeater" in keys, True)
    check("  and no amateur machine", "repeater" in keys, False)
    g = next(w for w in ways if w["key"] == "gmrs-repeater")
    check("  with the input 5 MHz up and the tone", "467.675" in g["do"] and "141.3" in g["do"], True)
    check("  and the licence named as a fee and a form", "no exam" in g["needs"], True)

    print("\n-- the GMRS licence, held --")
    check("a GMRS call is known by its shape", (callsign.is_gmrs("WRMP909"), callsign.is_gmrs("KAB1234"), callsign.is_gmrs("KC9SP")), (True, True, False))
    callsign.CACHE = Path(tempfile.mkdtemp()) / "calls"
    callsign._fetch_gmrs = lambda call: {"results": [{"callsign": "WRMP909", "name": "x", "city": "x", "state": "MN",
                                                       "grant_date": "2021-05-14", "expiration_date": "2031-05-14"}], "page": 1}
    rec = callsign.lookup("WRMP909")
    check("looked up through the one door, filed as GMRS", (rec["found"], rec["service"], rec["expires"]), (True, "gmrs", "2031-05-14"))
    check("  the name and town the record carries are not kept", "name" in rec or "city" in rec, False)
    check("  and it is current", rec["status"]["state"], "current")
    check("a GMRS licence past its date has no grace period", callsign.status_for(callsign._parse_date("2020-01-01"), 0)["state"], "expired")
    check("  where an amateur one would", callsign.status_for(callsign._parse_date("2025-01-01"))["state"], "grace")
    ways = reachout.ways(46.60, -94.31, ["gmrs"], "none", gmrs=rec)
    g = next(w for w in ways if w["key"] == "gmrs-repeater")
    check("the repeater card knows the licence is held", "you hold WRMP909" in g["needs"] and "Say WRMP909" in g["do"], True)
    f = next(w for w in ways if w["key"] == "frs-gmrs")
    check("  and so does the FRS/GMRS card", "you hold WRMP909, good until 2031-05-14" in f["needs"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

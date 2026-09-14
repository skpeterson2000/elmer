#!/usr/bin/env python3
"""A press beside a self-check line does the one thing that line calls for.

    python3 tests/test_doctor_fix.py

The doctor looks and changes nothing; a Fix is offered only on the unit's
own screen, only for a line with one known remedy, and it says what it did.
From across the network the same press is refused, and a remedy nobody
named is not a remedy.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import cohort, db  # noqa: E402
from elmer.app import REMEDIES, app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    c = app.test_client()
    here = {"REMOTE_ADDR": "127.0.0.1"}
    there = {"REMOTE_ADDR": "192.168.1.50"}

    print("\n-- the doctor says whether this screen may press --")
    d = c.get("/api/doctor", environ_base=here).get_json()
    check("local screen may", d["can_fix"], True)
    check("every line carries a fix field", all("fix" in x for x in d["checks"]), True)
    check("and every fix named is a remedy",
          all(x["fix"] in REMEDIES for x in d["checks"] if x["fix"]), True)
    check("across the network it may not",
          c.get("/api/doctor", environ_base=there).get_json()["can_fix"], False)

    print("\n-- the press --")
    check("refused from across the network",
          c.post("/api/doctor/fix", json={"fix": "forget-net"}, environ_base=there).status_code, 403)
    check("a remedy nobody named",
          c.post("/api/doctor/fix", json={"fix": "reboot"}, environ_base=here).status_code, 400)
    with db.connect() as conn:
        db.unit_set(conn, cohort.URL_SETTING, "http://192.168.1.99:5000")
        check("a net remembered", db.unit_get(conn, cohort.URL_SETTING), "http://192.168.1.99:5000")
    r = c.post("/api/doctor/fix", json={"fix": "forget-net"}, environ_base=here)
    check("forget-net is done", r.status_code, 200)
    check("  and says so", r.get_json()["ok"], True)
    check("  in words", bool(r.get_json()["said"]), True)
    with db.connect() as conn:
        check("  and the net is forgotten", db.unit_get(conn, cohort.URL_SETTING) or "", "")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())

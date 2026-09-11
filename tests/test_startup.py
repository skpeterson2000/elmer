#!/usr/bin/env python3
"""What this unit took to become usable, and who can read it.

    python3 tests/test_startup.py

The number is only worth keeping if it is the right number.  Timing the
socket reports a tenth of a second on the slowest board in the fleet, because
the port is bound long before the pools come off the card - so what is
recorded here is the first page actually served, and a static file does not
count as one.

It is written down rather than only logged because the doctor carries it and
the doctor answers over HTTP.  That is what lets one unit read what every
other unit took to start, which is how a median gets taken without walking to
each board.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, diagnostics, startup  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def doctor_line(label):
    for line in diagnostics.collect(port=5000):
        if line["label"] == label:
            return line
    return None


connection = db.connect()
was_build = db.unit_get(connection, startup.KEY_BUILD)
was_after = db.unit_get(connection, startup.KEY_AFTER)
was_at = db.unit_get(connection, startup.KEY_AT)
was_recorded = startup._recorded

try:
    print("\nbefore a page has been served there is nothing to report")
    db.unit_set(connection, startup.KEY_BUILD, None)
    startup._recorded = False
    check("nothing recorded", startup.last(connection), None)
    line = doctor_line("start")
    check("the doctor says so rather than guessing",
          "not timed yet" in (line or {}).get("detail", ""), True)
    check("and does not call it a fault", (line or {}).get("state"), "ok")

    print("\nwhat is kept is what the page cost, not when it was asked for")
    # A unit nobody opens until morning: the page took two and a half
    # seconds to build and the asking came eight hours later.  Recording the
    # wall clock would call that an eight hour start.
    startup.BEGAN = time.monotonic() - 8 * 3600
    took = startup.note_first_page(connection, 2.5)
    check("the page's own time", took, 2.5)
    held = startup.last(connection)
    check("read back", (held or {}).get("build"), 2.5)
    check("and how long it sat unasked, kept apart from it",
          7.9 * 3600 <= (held or {}).get("after", 0) <= 8.1 * 3600, True)
    check("with when", bool((held or {}).get("at")), True)

    again = startup.note_first_page(connection, 0.1)
    check("a second page says nothing about starting", again, None)
    check("and the run knows it is done", startup.waiting(), False)

    print("\nthe doctor reports it, and judges it against the splash's hold")
    from elmer import kiosk
    line = doctor_line("start")
    check("reported", "2.5s" in (line or {}).get("detail", ""), True)
    check("under the hold, so nobody saw a wait", (line or {}).get("state"), "ok")

    db.unit_set(connection, startup.KEY_BUILD, kiosk.HOLD_SECONDS + 6)
    line = doctor_line("start")
    check("past the hold it is worth saying", (line or {}).get("state"), "warn")
    check("and says why", "the wait shows" in (line or {}).get("detail", ""),
          True)

    print("\nit answers over HTTP with the rest of the doctor")
    # The point of writing it down: another unit asks this one, and the
    # number is in the reply without anybody reading a log.
    from elmer.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        body = client.get("/api/doctor").get_json()
    labels = [c["label"] for c in body["checks"]]
    check("the start is in what goes over the wire", "start" in labels, True)
    over_wire = [c for c in body["checks"] if c["label"] == "start"][0]
    check("carrying the seconds", "10.0s" in over_wire["detail"], True)
finally:
    startup._recorded = was_recorded
    db.unit_set(connection, startup.KEY_BUILD, was_build)
    db.unit_set(connection, startup.KEY_AFTER, was_after)
    db.unit_set(connection, startup.KEY_AT, was_at)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")

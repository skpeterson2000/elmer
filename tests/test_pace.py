#!/usr/bin/env python3
"""Checks for the pace ledger: every endpoint timed, folded to one key,
the first cold call left out, a creeper caught by its own baseline, an
over-budget endpoint by its p95, the ledger kept across a restart, and
the field report and the doctor carrying it.

    python3 tests/test_pace.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import pace  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- one key per endpoint --")
    check("numbers and file names fold", pace.key_of("GET", "/library/page/manual/3.png?x=1"), "GET /library/page/manual/*.png")
    check("  so do ids in the path", pace.key_of("GET", "/awards/12/ewac.jpg"), "GET /awards/*/*.jpg")
    check("  a query string is not part of it", pace.key_of("GET", "/api/ways-out?gear=ht"), "GET /api/ways-out")
    check("kinds: a poll, an api call, a page, a print", (pace.kind_of("/api/people"), pace.kind_of("/api/ways-out"), pace.kind_of("/bandplan"), pace.kind_of("/prints/3.pdf")),
          ("poll", "api", "page", "pdf"))

    print("\n-- timed, the cold first call left out --")
    pace.note("GET", "/bandplan", 2200)
    for _ in range(6):
        pace.note("GET", "/bandplan", 30)
    r = next(x for x in pace.rows() if x["key"] == "GET /bandplan")
    check("six warm calls counted, the cold one not", (r["n"], r["max"], r["over"]), (6, 30, False))

    print("\n-- a creeper, by its own baseline --")
    for _ in range(101):
        pace.note("GET", "/api/slow", 20)
    for _ in range(60):
        pace.note("GET", "/api/slow", 90)
    r = next(x for x in pace.rows() if x["key"] == "GET /api/slow")
    check("the first hundred set the baseline", r["base"], 20)
    check("  and a mean that doubled since is a creeper, though under budget", (r["crept"], r["over"]), (True, False))
    for _ in range(46):
        pace.note("GET", "/api/heavy", 700)
    r = next(x for x in pace.rows() if x["key"] == "GET /api/heavy")
    check("an api call with a p95 past 400 ms is over budget", (r["over"], r["crept"]), (True, False))
    check("both are creepers, worst first", [c["key"] for c in pace.creepers()], ["GET /api/heavy", "GET /api/slow"])

    print("\n-- kept across a restart --")
    pace.save()
    pace._loaded = False
    pace._ledger.clear()
    r = next(x for x in pace.rows() if x["key"] == "GET /api/slow")
    check("the ledger comes back with its baseline", (r["n"], r["base"], r["crept"]), (160, 20, True))

    print("\n-- said --")
    lines = pace.report_lines()
    check("the report names the creeper and the over-budget one", any("CREPT" in ln for ln in lines) and any("over budget" in ln for ln in lines), True)
    from elmer import fieldreport
    text = fieldreport.build(None)[0] if isinstance(fieldreport.build(None), tuple) else fieldreport.build(None)
    check("  and the field report carries the table", "the pace" in text and "CREPT" in text, True)
    from elmer import diagnostics
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        diagnostics.check_pace()
    check("  and the doctor warns", "warn" in buf.getvalue().lower() and "crept" in buf.getvalue().lower() or "over budget" in buf.getvalue(), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

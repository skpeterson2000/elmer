#!/usr/bin/env python3
"""The log never holds the station.

    python3 tests/test_log_redaction.py

The problem report took the callsign, the grid, the town and the home folder
out of the log on the way out. That protected the report; the log on the
disk still said whose it was. Now the same redaction happens as each line
is written, in the formatter, so a traceback goes through it too - and a
name the unit holds, registered as it is learned, is taken out by name.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import logs  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


class Keep(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


def main():
    log = logging.getLogger("elmer.test.redaction")
    log.propagate = False
    log.setLevel(logging.DEBUG)
    keep = Keep()
    keep.setFormatter(logs.CleanFormatter(logs.FMT, logs.DATEFMT))
    log.addHandler(keep)
    logs.remember_private("Pequot Lakes", "Ely")

    print("\n-- what a line may not say --")
    log.info("QTH set to EN26uo (Pequot Lakes) for KC9SP at 46.5983,-94.3154 from /home/scott/elmer")
    line = keep.lines[-1]
    check("the callsign is gone", "KC9SP" in line, False)
    check("  the grid is cut to four characters", ("EN26xx" in line, "EN26uo" in line), (True, False))
    check("  the town the unit holds is gone", "Pequot" in line, False)
    check("  the coordinates are gone", "46.5983" in line, False)
    check("  the home folder is gone", "scott" in line, False)
    check("  and the fault is still in it", "QTH set to" in line, True)

    print("\n-- a short name is a syllable, not a secret --")
    log.info("Ely is a town")
    check("three letters are left alone", "Ely" in keep.lines[-1], True)

    print("\n-- a token, and a traceback --")
    log.info("repeaterbook token rbuapp_abcdef123456 refused")
    check("a token never reaches the log", "rbuapp_abcdef" in keep.lines[-1], False)
    try:
        raise RuntimeError("failed for KC9SP in /Users/scott/elmer")
    except RuntimeError:
        log.exception("boom")
    text = keep.lines[-1]
    check("a traceback goes through the same cleaning", ("KC9SP" in text, "scott" in text, "RuntimeError" in text), (False, False, True))

    print("\n-- the console formatter is the same cleaning --")
    colour = logs.ColourFormatter(False)
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "hello W1AW", (), None)
    check("the coloured console line is clean too", "W1AW" in colour.format(rec), False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

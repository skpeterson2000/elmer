#!/usr/bin/env python3
"""Touchstone export: that the file is real, not merely well-formed.

    python3 tests/test_touchstone.py

An export is easy to get plausibly wrong. The file parses, a plot appears, and
the numbers are off by a factor nobody notices until they act on them. So these
checks take the file back apart and compare it with what went in, and they
concentrate on the two mistakes that do not announce themselves:

    The frequency unit. The instrument sweeps in hertz, this program carries
    megahertz for the screen's sake, and Touchstone lets the file say which it
    used. Write 14.2 where 14200000 belongs and the file is valid, readable,
    and wrong by six orders of magnitude - and a reader will plot it happily.

    The reference impedance. Fifty ohms is nearly always right, which is
    exactly why leaving it out goes unnoticed until the one time it is not.

The rest is the format's own rules: a `.s1p` is one port, so one pair of
numbers per row; comments start with `!` and can say anything; the options line
starts with `#` and is the only line that configures the file.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import touchstone                                    # noqa: E402

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


def sweep(n=41, low=14.0, high=14.35):
    """A sweep with a real resonance in it, so the best-match line has a job."""
    rows = []
    for i in range(n):
        mhz = low + (high - low) * i / (n - 1)
        # A notch at 14.175: the reflection coefficient goes through near zero.
        g = (mhz - 14.175) * 2.2
        rows.append({"mhz": round(mhz, 6), "gx": round(g, 6),
                     "gy": round(-0.04 * g, 6)})
    return rows


def main():
    rows = sweep()
    text = touchstone.s1p(rows, device="/dev/ttyACM0")

    print("-- it is a Touchstone file --")
    lines = text.splitlines()
    options = [ln for ln in lines if ln.startswith("#")]
    check("exactly one options line", len(options), 1)
    check("  saying hertz, S-parameters, real and imaginary, 50 ohm",
          options[0].split(), ["#", "HZ", "S", "RI", "R", "50"])
    check("  every other non-data line is a comment",
          all(ln.startswith("!") for ln in lines
              if not ln.startswith("#") and ln and not ln[0].isdigit()
              and not ln[0] == "-"), True)
    data = [ln for ln in lines if ln and (ln[0].isdigit() or ln[0] == "-")]
    check("  one data row per sweep point", len(data), len(rows))
    check("  three numbers on each, because one port is one pair",
          {len(ln.split()) for ln in data}, {3})

    print("-- the frequencies are hertz, and integers --")
    first = data[0].split()
    check("the first row is 14000000 Hz, not 14.0", first[0], "14000000")
    check("  and it is a whole number of hertz", "." in first[0], False)
    last = data[-1].split()
    check("  the last is the top of the span", last[0], "14350000")

    print("-- what went in comes back out --")
    back = touchstone.read(text)
    check("the reader finds every point", len(back["rows"]), len(rows))
    check("  and the reference impedance it was written with", back["z0"], 50.0)
    check("  in the unit it was written in", back["unit"], "HZ")
    check("  in the form it was written in", back["format"], "RI")
    worst_f = max(abs(a["mhz"] - b["mhz"])
                  for a, b in zip(rows, back["rows"]))
    worst_g = max(math.hypot(a["gx"] - b["gx"], a["gy"] - b["gy"])
                  for a, b in zip(rows, back["rows"]))
    near("  frequencies survive the trip", worst_f, 0.0, 1e-6)
    near("  and so does the reflection coefficient", worst_g, 0.0, 1e-6)

    print("-- the comments say what it is without pretending to be data --")
    check("the instrument is named", "!Instrument: /dev/ttyACM0" in text, True)
    check("  the reference impedance is stated in words too",
          "!Reference impedance: 50 ohm" in text, True)
    check("  the best match is called out", "!Best match:" in text, True)
    # It sits at the notch, and it is a comment - a reader that ignores
    # comments loses nothing but a convenience.
    best = [ln for ln in lines if ln.startswith("!Best match:")][0]
    check("  at the resonance, not at an edge", "14.175" in best, True)
    stripped = touchstone.read("\n".join(
        ln for ln in lines if not ln.startswith("!")))
    check("  and the file still reads with every comment removed",
          len(stripped["rows"]), len(rows))

    print("-- the other formats a file may arrive in --")
    # Written only in RI, but the reader honours what the options line says,
    # so a file from another program still comes in correctly.
    ma = ("!from somewhere else\n# MHZ S MA R 75\n"
          "14.2 0.5 90.0\n14.3 1.0 180.0\n")
    got = touchstone.read(ma)
    check("megahertz is read as megahertz", round(got["rows"][0]["mhz"], 4), 14.2)
    check("  and a 75 ohm reference is not silently made 50", got["z0"], 75.0)
    near("  magnitude and angle become real and imaginary",
         got["rows"][0]["gy"], 0.5, 1e-9)
    near("  a half at 90 degrees has no real part",
         got["rows"][0]["gx"], 0.0, 1e-9)
    near("  and unity at 180 degrees is a short", got["rows"][1]["gx"],
         -1.0, 1e-9)

    print("-- it refuses what it cannot write --")
    for label, bad in [("nothing at all", []),
                       ("rows with no reflection in them",
                        [{"mhz": 14.0}])]:
        try:
            touchstone.s1p(bad)
            check(f"{label} is refused", "wrote it anyway", "ValueError")
        except ValueError:
            check(f"{label} is refused", True, True)
    try:
        touchstone.read("14000000 0.1 0.2\n")
        check("a file with no options line is refused", "accepted", "ValueError")
    except ValueError:
        check("a file with no options line is refused", True, True)

    print("-- the name says what is in it --")
    name = touchstone.filename(14.0, 14.35)
    check("it is a one-port file", name.endswith(".s1p"), True)
    check("  and carries the span", "14.000-14.350mhz" in name, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

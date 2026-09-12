"""The Smith chart's numbers: the reactance is the reactance.

    python3 tests/test_smith.py

The analysis used to put the reflection coefficient's real part under the
same key as the reactance, and the second write won - so the page's notes
read "73.0 + j0.27 ohms" for an antenna that was +j42.5, and its "is the
shack matched?" test compared a number that is never bigger than one against
8 ohms and always said yes. The dot on the chart was right the whole time,
which is why nobody saw it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401
from elmer import smith  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


line = next(iter(smith.LINES))
d = smith.analyse(73, 42.5, line, 14.2, 50)
print("\nat the antenna")
check("R is what was given", d["load"]["r"], 73.0)
check("X is the reactance given, not a chart coordinate", d["load"]["x"], 42.5)
check("  and the chart coordinate is under its own name",
      (abs(d["load"]["gx"]) <= 1, abs(d["load"]["gy"]) <= 1), (True, True))
check("  |gamma| agrees with the coordinates",
      round((d["load"]["gx"] ** 2 + d["load"]["gy"] ** 2) ** 0.5, 3), round(d["load"]["gamma_mag"], 3))
print("\nat the shack")
check("the shack's X is in ohms too", abs(d["shack"]["x"]) > 1, True)
check("  with its own chart coordinate", sorted(k for k in d["shack"] if k.startswith("g")),
      ["gamma_mag", "gx", "gy"])
check("a matched load sits at the centre",
      smith.analyse(50, 0, line, 14.2, 50)["load"]["gx"], 0.0)
print("\nthe path along the line is chart coordinates by design")
check("each step has ft, x, y", sorted(d["path"][0]), ["ft", "x", "y"])

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)

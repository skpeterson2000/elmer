#!/usr/bin/env python3
"""Which units this operator reads distances in.

    python3 tests/test_units.py

The preference is deliberately narrow, and the narrowness is the part worth
testing. It governs how far away a thing is - a park, a summit, a repeater.
It does not touch the units the craft speaks in: nobody calls it the forty
yard band, wire is cut in feet because that is how wire is sold, and hmF2 is
in kilometers because that is what ionosondes report. An operator who picks
imperial is saying how they think about a drive, not asking for the 40 m band
to be renamed.

The rest is arithmetic, and the one thing arithmetic like this gets wrong is
disagreeing with itself - a filter that takes miles and a table that answers
in kilometers, which is exactly the mismatch this was built to end.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import units  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\nthree systems, because a maritime operator counts differently")
check("all three are there", sorted(units.SYSTEMS),
      ["imperial", "metric", "nautical"])
check("each has a short form for a column heading",
      all(s["short"] for s in units.SYSTEMS.values()), True)
check("and a long one for a sentence",
      all(s["long"] for s in units.SYSTEMS.values()), True)

print("\nthe conversions are the conversions")
check("a mile is 1.609344 km", round(units.to_km(1, "imperial"), 6), 1.609344)
check("a nautical mile is 1.852 km", round(units.to_km(1, "nautical"), 6),
      1.852)
check("a kilometer is itself", units.to_km(1, "metric"), 1.0)

print("\nand they come back where they started")
for system in units.SYSTEMS:
    there = units.to_km(137.0, system)
    check(f"{system}: 137 there and back", round(units.from_km(there, system), 6),
          137.0)

print("\nsaying a distance puts its unit on it")
check("metric", units.say(350, "metric"), "350 km")
check("imperial", units.say(350, "imperial"), "217 mi")
check("nautical", units.say(350, "nautical"), "189 NM")
check("and nothing is nothing", units.say(None, "metric"), "—")

print("\nan unknown preference is a default, never an error")
# The setting is a stored string. A database from a future version, a typo, a
# half-written value - none of those is worth a traceback on a page load.
check("nonsense falls back", units.system("gallons")["key"], units.DEFAULT)
check("so does empty", units.system("")["key"], units.DEFAULT)
check("so does None", units.system(None)["key"], units.DEFAULT)
check("and the default is a real system", units.DEFAULT in units.SYSTEMS, True)

print("\nthe preference governs everything measured, except the names of bands")
# This used to be a rule about what NOT to build: distance only, no heights
# and no lengths, because wire is sold in feet and an ionosonde reports in
# kilometres. That was the program noting a preference and filing it. The
# operator it is for could not tell you how many metres are in a hundred
# yards, and does not need to be able to.
#
# The one thing that does not move is a band's name. Nobody calls it the
# forty yard band.
check("no wavelength in it",
      any("wavelength" in str(s).lower() for s in units.SYSTEMS.values()), False)
check("the vertical is there now",
      all("short_len" in s for s in units.SYSTEMS.values()), True)
check("  metres for metric", units.say_len(30, "metric"), "30 m")
check("  feet for imperial", units.say_len(30, "imperial"), "98 ft")
check("  and feet for nautical too, which is how a chart reads a height",
      units.say_len(30, "nautical"), "98 ft")
check("the antenna code's own feet come through",
      (units.say_ft(33, "imperial"), units.say_ft(33, "metric")), ("33 ft", "10 m"))
check("  and what is measured across",
      (units.say_in(2.5, "imperial"), units.say_in(2.5, "metric")), ("2.5 in", "63.5 mm"))
check("the module says why, out loud",
      "not a measurement of anything" in (units.__doc__ or ""), True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")

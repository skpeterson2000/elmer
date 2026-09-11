#!/usr/bin/env python3
"""Which units this operator reads distances in.

    python3 tests/test_units.py

The preference is deliberately narrow, and the narrowness is the part worth
testing. It governs how far away a thing is - a park, a summit, a repeater.
It does not touch the units the craft speaks in: nobody calls it the forty
yard band, wire is cut in feet because that is how wire is sold, and hmF2 is
in kilometres because that is what ionosondes report. An operator who picks
imperial is saying how they think about a drive, not asking for the 40 m band
to be renamed.

The rest is arithmetic, and the one thing arithmetic like this gets wrong is
disagreeing with itself - a filter that takes miles and a table that answers
in kilometres, which is exactly the mismatch this was built to end.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
check("a kilometre is itself", units.to_km(1, "metric"), 1.0)

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

print("\nthe preference is about distance, and nothing else")
# Written down as a test because it is a rule about what NOT to build. The
# temptation with a units switch is to run it through everything, and doing
# that would rename the bands.
check("no wavelength in it",
      any("wavelength" in str(s).lower() for s in units.SYSTEMS.values()), False)
check("no feet, no heights",
      any("feet" in str(s).lower() for s in units.SYSTEMS.values()), False)
check("the module says so out loud",
      "forty yard band" in (units.__doc__ or ""), True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")

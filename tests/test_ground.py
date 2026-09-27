#!/usr/bin/env python3
"""One ground table, the ITU's figures where the ITU gives them, read by every
model.

    python3 tests/test_ground.py

The antenna patterns, the ground wave and the Ground tab's rating each kept
their own table of soils, and they had drifted: "poor" was one soil in the
patterns and another in the ground wave. elmer/ground.py is the one table
now. What is held here:

  - the figures are ITU-R P.527-6's, Figure 24, at HF, where it gives the
    soil, and each entry says where its figures come from;
  - "average" and "city" are the two that are not P.527's, and say so;
  - the patterns, the ground wave and the rating all read this table, and
    every name either old table used still answers;
  - on the soils whose figures did not change - average, fresh water and
    city - the answers are the ones the old tables gave, pinned here from a
    run before the change;
  - the changes P.527 makes on purpose are where the changelog says: wet
    ground shorter, sand and ice much shorter, poor a little longer.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []

# Read from ITU-R P.527-6, Attachment to Annex 1, Figure 24, where each
# curve is flat across HF: (relative permittivity, conductivity S/m).
P527 = {"sea": (70.0, 5.0), "wet": (30.0, 0.01), "fresh": (80.0, 0.003),
        "poor": (15.0, 0.001), "sand": (3.0, 0.0001), "ice": (3.0, 5e-5)}
TEXTBOOK = {"average": (13.0, 0.005), "city": (5.0, 0.001)}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import ground, groundwave, patterns, siteground

    print("\n-- the figures and where they come from --")
    for name, want in P527.items():
        check(f"{name}: P.527's figures", ground.constants(name), want)
        check(f"  and it cites P.527", "P.527" in ground.SOILS[name]["source"], True)
    for name, want in TEXTBOOK.items():
        check(f"{name}: the textbook figures", ground.constants(name), want)
        check(f"  and it says it is not P.527's", "not" in ground.SOILS[name]["source"] or "no curve" in ground.SOILS[name]["source"], True)
    check("ice says its conductivity was read by eye", "by eye" in ground.SOILS["ice"]["source"], True)
    check("every soil has a label and a note",
          [n for n, s in ground.SOILS.items() if not (s.get("label") and s.get("note"))], [])
    check("the patterns' old 'good' is P.527's wet ground", ground.constants("good"), P527["wet"])
    check("perfect ground is not a soil", ground.constants("perfect"), None)

    print("\n-- every model reads the one table --")
    names = list(ground.SOILS) + list(ground.ALIASES)
    check("the patterns know every soil and alias, with its figures",
          [n for n in names if patterns.GROUNDS.get(n) != ground.constants(n)], [])
    check("  and perfect ground still", "perfect" in patterns.GROUNDS and patterns.GROUNDS["perfect"] is None, True)
    check("the ground wave's table is the one table", groundwave.GROUND is ground.SOILS, True)
    er, cond_term, lam = groundwave.complex_permittivity(7.0, "wet")
    check("  and its permittivity reads it", (er, round(cond_term / (60.0 * lam), 6)), P527["wet"])
    check("the rating reads it too", siteground._ground is ground, True)
    check("the rating's map to the pattern choices still names soils the patterns know",
          [k for k, v in siteground.PATTERN_OF.items() if v not in patterns.GROUNDS], [])

    print("\n-- where the figures did not move, neither did the answers --")
    # Pinned from a run of the old tables on 2026-09-27.
    check("40 m ground-wave range on average ground", round(groundwave.useful_range_km(7.15, ground="average"), 1), 56.7)
    check("160 m on fresh water", round(groundwave.useful_range_km(1.9, ground="fresh"), 1), 152.1)
    check("80 m on city ground", round(groundwave.useful_range_km(3.6, ground="city"), 1), 48.6)
    check("160 m field at 100 km on average ground, dBuV/m",
          round(groundwave.field_strength(100, 1.9, ground="average")["dbuv_per_m"], 3), 18.458)
    check("80 m on sea water, where only the permittivity moved", round(groundwave.useful_range_km(3.6, ground="sea"), 1), 355.7)
    rh, rv = patterns.fresnel(math.radians(10), 7.15, "average")
    check("the patterns' reflection off average ground at 10 degrees on 40 m",
          (round(abs(rh), 4), round(abs(rv), 4)), (0.9263, 0.2322))

    print("\n-- where P.527 moves them, it moves them the way the changelog says --")
    check("160 m on wet ground: 196 km becomes 160", round(groundwave.useful_range_km(1.9, ground="wet")), 160)
    check("40 m on dry sand: 47 km becomes 26", round(groundwave.useful_range_km(7.15, ground="sand")), 26)
    check("20 m on poor ground: 38 km becomes 42", round(groundwave.useful_range_km(14.2, ground="poor")), 42)
    check("160 m on ice: 71 km becomes 39", round(groundwave.useful_range_km(1.9, ground="ice")), 39)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

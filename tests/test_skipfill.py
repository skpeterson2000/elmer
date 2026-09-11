#!/usr/bin/env python3
"""Whether the antenna can reach into its own skip zone. Usually, yes.

    python3 tests/test_skipfill.py

ELMER used to say, of the hole in the middle of a one-hop pattern, that "the
antenna cannot help you there - a lower band can". The first half of that is
wrong whenever the band is still under the critical frequency, which on 80 m
after dark is most of the time: a horizontal wire and its image in the ground
are a two element array, and the height decides what they do to each other.
Near a quarter wave up the reflection returns in step straight overhead and
the pattern points at the sky. Near a half wave it cancels overhead and splits
into the two lobes that leave the hole.

So the operator inside the skip zone is usually not stuck. They are too high -
and the fix is to lower the antenna, not to change bands.

The case the old wording was right about is kept and tested too: above foF2
nothing comes back from overhead however the wire is hung.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import antenna_advice, patterns  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\na high wire under the critical frequency can be brought down to fill it")
# 130 ft on 80 m is about half a wave: the lobe has split and the hole is open.
fill = patterns.fill_the_gap(3.9, 130, fof2=4.3)
check("there is something to do", bool(fill), True)
check("and it is to come down", fill["to_ft"] < fill["from_ft"], True)
check("to about a fifth of a wavelength", fill["to_ft"], 50)
# The same answer the antenna page gives, from a different module. Two numbers
# for one antenna is how an operator stops believing either.
check("which is what the antenna page says too", fill["to_ft"],
      antenna_advice.nvis_height_ft(3.9, "dipole"))

print("\nsame on 40 m, and the two modules still agree")
fill40 = patterns.fill_the_gap(7.2, 70, fof2=8.0)
check("come down to", fill40["to_ft"], 27)
check("agreeing with the antenna page",
      fill40["to_ft"], antenna_advice.nvis_height_ft(7.2, "dipole"))

print("\na wire already low is already doing it")
check("nothing to say at 60 ft on 80 m",
      patterns.fill_the_gap(3.9, 60, fof2=4.3), None)
check("nor at 20 ft", patterns.fill_the_gap(3.9, 20, fof2=4.3), None)

print("\nabove the critical frequency, no height helps - the old line was right")
check("80 m with foF2 at 3.0", patterns.fill_the_gap(3.9, 130, fof2=3.0), None)
check("20 m with foF2 at 8.0", patterns.fill_the_gap(14.2, 60, fof2=8.0), None)
check("and the note says so rather than staying quiet",
      "no height will fill it" in patterns._gap_note(14.2, 60, 8.0), True)

print("\nwith no ionosonde reading it says which it depends on")
check("no foF2, no claim either way",
      patterns.fill_the_gap(3.9, 130, fof2=None), None)
check("and the note explains the condition",
      "depends on the critical frequency" in patterns._gap_note(3.9, 130, None),
      True)

print("\nthe sentence that was wrong is gone")
note = patterns._gap_note(3.9, 130, 4.3)
check("no 'the antenna cannot help you'",
      "antenna cannot help" in note, False)
check("and it names the mechanism instead",
      "ground reflection" in note, True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")

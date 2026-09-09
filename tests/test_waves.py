#!/usr/bin/env python3
"""Checks for the sound analogy - radio waves as the sound of the same size.

    python3 tests/test_waves.py

The analogy carries a lot of weight, so it has to be arithmetic rather than
poetry: the note really is the sound of a wave that size in air, and the
diffraction verdict really is the ratio of the obstacle to the wavelength.

The part worth testing hardest is where the analogy stops. A good analogy is
dangerous exactly where somebody has quit checking it, and this one has two
places it breaks - polarisation, which sound does not have at all, and
absorption, which runs the opposite way with frequency in the two media.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import waves as W  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the mapping is arithmetic, not decoration --")
    # Same wavelength, different medium. That is the whole conversion.
    for mhz in (1.9, 14.2, 145.0, 446.0):
        lam = W.wavelength_m(mhz)
        check(f"{mhz} MHz is {lam:.2f} m and the air note is that size",
              abs(W.as_sound(mhz) * lam - W.SOUND) < 1e-6, True)
    check("2m lands on a bass note", W.note_name(W.as_sound(145.0)), "E3")
    check("70cm lands in the middle of a voice",
          W.note_name(W.as_sound(446.0)), "C5")
    check("440 Hz is an A4, which is the tuning fork everybody knows",
          W.note_name(440.0), "A4")
    check("and an octave up is the same letter",
          W.note_name(880.0), "A5")

    print("\n-- the low bands are below hearing, which is the point --")
    check("160m maps below the bottom of hearing",
          W.describe(1.9)["audible"], False)
    check("  and it is named as unhearable rather than given a note",
          W.describe(1.9)["note"], None)
    check("2m is audible", W.describe(145.0)["audible"], True)
    check("the higher the band, the higher the note",
          W.as_sound(446.0) > W.as_sound(145.0) > W.as_sound(14.2), True)

    print("\n-- a wave bends round what is smaller than itself --")
    house = 8.0
    check("160m ignores a house entirely",
          W.meets(1.9, house)["verdict"], "goes straight round it")
    check("2m is stopped by one", W.meets(145.0, house)["verdict"],
          "casts a shadow")
    check("  and the verdict is the ratio, not a table",
          round(W.meets(145.0, house)["ratio"], 2),
          round(house / W.wavelength_m(145.0), 2))
    check("the same wave is stopped by a hill and not by a fence post",
          (W.meets(145.0, 60.0)["verdict"], W.meets(145.0, 0.3)["verdict"]),
          ("casts a shadow", "goes straight round it"))
    check("and a bigger obstacle never bends a wave more",
          W.meets(145.0, 2.0)["ratio"] < W.meets(145.0, 20.0)["ratio"], True)

    print("\n-- where the analogy breaks, said out loud --")
    # These are the load-bearing ones. Polarisation has no acoustic
    # counterpart at all, and absorption runs the opposite way.
    text = " ".join(t + " " + x for t, x in W.MISMATCHES).lower()
    check("it says sound has no polarisation", "polaris" in text, True)
    check("  and gives the number that costs", "20 db" in text, True)
    check("it says absorption runs the other way", "absorb" in text, True)
    check("  naming the D layer, which eats the low bands",
          "d layer" in text, True)
    check("it says radio needs no medium", "medium" in text, True)
    check("there are more parallels than exceptions, but not by much",
          len(W.PARALLELS) > len(W.MISMATCHES) >= 3, True)

    print("\n-- and where it holds, it holds on real physics --")
    joined = " ".join(t + " " + x for t, x in W.PARALLELS).lower()
    for idea in ("baffle", "horn", "impedance", "standing wave", "inversion"):
        check(f"the parallels cover {idea}", idea in joined, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

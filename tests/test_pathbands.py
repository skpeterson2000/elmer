#!/usr/bin/env python3
"""Which band could carry a contact this far, when the two cannot see each other.

    python3 tests/test_pathbands.py

The line-of-sight tool answers whether two antennas can see each other, and
past about fifty miles they never can. That is not the end of the contact: it
has moved to the ionosphere, and answering "no line of sight" and stopping
tells an operator the opposite of what is true.

Three ways a band carries a path, and they are distances rather than
alternatives: ground wave hugging the surface, straight up and back with no
hole in the middle, and one or more hops off the F2 layer.

The checks below are against what the bands are actually like on a night with
foF2 around 4.3 MHz, because a model that passes its own algebra and disagrees
with the air is wrong.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import propagation  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


NIGHT = dict(fof2=4.3, hmf2=300.0, elevation=-20.0, muf=13.9)


def carried(km, **kw):
    got = propagation.path_bands(km, **dict(NIGHT, **kw))
    return {r["band"]: r["how"] for r in got["any"]}


print("\nclose in, the low bands go straight up and the high ones crawl")
near = carried(40)
check("80 m covers it overhead", near.get("80m"), "straight up and back")
check("and 20 m only by ground wave", near.get("20m"), "ground wave")

print("\nat a couple of hundred km the high bands have nothing to offer")
# This is the skip zone doing its work: 20 m's nearest return is far beyond.
mid = carried(200)
check("80 m still covers it", mid.get("80m"), "straight up and back")
check("20 m does not", "20m" in mid, False)
check("nor 15 m", "15m" in mid, False)

print("\nfar enough out and it is a hop, not a vertical bounce")
# Below foF2 a band returns at every angle, but at 1800 km the ray leaving is
# a shallow one - calling that "straight up and back" would be wrong about the
# geometry even though the band does carry it.
far = carried(1800)
check("80 m is working by one hop now", far.get("80m"), "one hop")
check("and 40 m has come in", far.get("40m"), "one hop")

print("\nbeyond one hop is not beyond reach")
# The failure this was written to avoid: 5000 km is worked every day.
long_haul = carried(5000)
check("something carries 5000 km", bool(long_haul), True)
check("in two hops", long_haul.get("40m"), "2 hops")
costs = [r.get("cost", "") for r in propagation.path_bands(5000, **NIGHT)["any"]]
check("and it says what that costs",
      all("possible rather than easy" in c for c in costs), True)

print("\na single hop has a reach, and it is stated")
one = propagation.path_bands(1000, **NIGHT)
check("the limit is reported", one["one_hop_km"] > 2500, True)
check("and it is not absurd", one["one_hop_km"] < 5000, True)

print("\nwith no reading in hand it does not guess")
# skip_km answers 0 - "reaches everywhere" - both for a wide open sky and for
# no data at all. Taken at face value that had this tool promising an overhead
# contact on every low band whenever the ionosonde network was unreachable,
# which is exactly when nobody can check it.
blind = propagation.path_bands(300, fof2=None, hmf2=300.0, elevation=-20.0)
check("it says it is blind", blind["blind"], True)
check("and claims no hops",
      any(r["how"] in ("one hop", "straight up and back")
          for r in blind["any"]), False)
check("ground wave is still honest work",
      all(r["how"] == "ground wave" for r in blind["any"]), True)
refused = [r for r in blind["bands"] if not r["works"]][0]
check("and the rest say why", "no critical frequency in hand" in refused["why"],
      True)

print("\nand a band that cannot do it says why")
blocked = [r for r in propagation.path_bands(200, **NIGHT)["bands"]
           if r["band"] == "20m"][0]
check("20 m is refused", blocked["works"], False)
check("with the skip zone named", "skip zone" in blocked["why"], True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")

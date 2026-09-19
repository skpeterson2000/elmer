#!/usr/bin/env python3
"""The band list does not stop at 6 m any more.

    python3 tests/test_hf_by_numbers.py

Reported from a real path: Make Contact's "by the numbers" panel offered
6 m, 2 m, 1.25 m and 70 cm and nothing below, so a tool sitting under a
sentence that had just named six HF bands as open looked like one that had
given up at 6 m.

It had not given up; it was answering a different question. That panel is a
link budget along the terrain between two stations, and on 20 m over a
thousand miles the terrain is not the path - the signal leaves at an angle,
turns in the ionosphere and comes down again. Running the budget there would
print a confident nought per cent for a path that is wide open, which is
worse than declining.

So the HF bands are on the list now and answer with the ionosphere: whether
the band comes back at all on this path, in how many hops, the critical
frequency at the middle of it, the MUF along it, and how far one hop
reaches. What is held down here is that those numbers are the same ones the
bands line above the panel is already using - two panels on one page
disagreeing about the sky over one path is a fault this program has had
before, in the golf card and in the inverted-V.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import pathto  # noqa: E402

FAILS = []
HERE = {"lat": 44.98, "lon": -93.27, "short": "Minneapolis"}
FAR = {"lat": 27.8, "lon": -97.4, "short": "EL16HQ"}       # about 2000 km
NEAR = {"lat": 45.05, "lon": -93.10, "short": "across town"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- every band is on the list --")
    offered = [b["key"] for b in pathto.link(HERE, FAR, band="2m")["bands"]]
    check("the line-of-sight bands come first", offered[:4], ["6m", "2m", "1.25m", "70cm"])
    check("  and the ionosphere's follow, down to 160 m",
          ("160m" in offered, "20m" in offered, "10m" in offered), (True, True, True))
    check("  the list does not stop at 6 m", len(offered) > 4, True)
    kinds = {b["key"]: b.get("kind") for b in pathto.link(HERE, FAR, band="2m")["bands"]}
    check("  and each one says which answer it will give",
          (kinds["2m"], kinds["20m"]), ("ground", "sky"))

    print("\n-- an HF band is answered by the sky, not the terrain --")
    sky = pathto.link(HERE, FAR, band="20m")
    check("the answer knows what kind it is", sky["kind"], "sky")
    check("  it has no link budget in it, because there is no line of sight to budget",
          ("loss" in sky, "odds" in sky), (False, False))
    check("  it says whether the band comes back", isinstance(sky["works"], bool), True)
    check("  and carries the numbers that decide it",
          all(sky.get(k) is not None for k in ("fof2", "muf", "one_hop_km")), True)

    print("\n-- and a VHF band still gets the link budget --")
    ground = pathto.link(HERE, NEAR, band="2m")
    check("the 2 m answer is the ground one", ground.get("kind"), None)
    check("  with odds on it", "odds" in ground, True)

    print("\n-- the two panels agree about the same sky --")
    # The bands line above the panel and the panel itself read the ionosphere
    # at the same point and must not disagree about it.
    whole = pathto.predict(HERE, FAR, gear=("hf_wire",), license="Extra")
    for band in ("160m", "80m", "40m", "20m", "15m", "10m"):
        row = next(r for r in whole["sky"]["bands"] if r["band"] == band)
        one = pathto.link(HERE, FAR, band=band)
        check(f"{band}: the same verdict either way",
              (one["works"], one["how"], one["score"]),
              (row["works"], row["how"], row["score"]))
    check("  and the same reading behind it",
          (pathto.link(HERE, FAR, band="20m")["fof2"], pathto.link(HERE, FAR, band="20m")["muf"]),
          (whole["sky"]["fof2"], whole["sky"]["muf"]))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

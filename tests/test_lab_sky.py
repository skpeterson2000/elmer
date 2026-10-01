#!/usr/bin/env python3
"""The Lab and the Band Plan's reach map read one sky.

    python3 tests/test_lab_sky.py

A 20 m inverted-V 39 ft up on 40 m fires near-vertically. With foF2 at 3.1
MHz that lobe goes through the layer; the reach map drew everything inside
about 1,600 km dark, and the Lab - which read the sky only for NVIS - said the
lobe landed about 250 km out. Both were right about their own question; the
Lab now answers the map's when the sky has been read. What is held here:

  - with the band above foF2 and the lobe too steep, the Lab says the lobe
    goes through, and puts the skip where the map's gate puts it
    (propagation.skip_km), at the same layer height;
  - "nothing comes back" only when no angle at all returns - below its
    half-power edge an antenna still radiates, and that is what the map
    shows working;
  - with the band under foF2 the Lab no longer calls the sky "not in hand";
  - and the Lab's own route asks for the sky on any HF question, with the
    map's layer height when no sonde is near.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import patterns as P, propagation as Pr  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("-- the reported case: 40 m at night, foF2 3.1 MHz, a low inverted V --")
    r = P.reach("invertedv", "dx", 7.074, 39.0, False, 0.0, False, 3.1, 300.0)
    check("the Lab says the main lobe goes through", r.get("through"), True)
    check("  and puts the skip where the reach map gates it",
          r.get("inner_km"), round(Pr.skip_km(7.074, 3.1, 300.0)))
    check("  and does not claim a landing distance for a lobe that does not land", r.get("typical_km"), None)
    check("  and says what does come back, rather than nothing",
          ("radiation under its main lobe" in r["note"]) or ("lower part of its lobe" in r["note"]), True)
    check("  and points at the map", "reach map" in r["note"], True)

    print("\n-- a higher wire: the bottom of its lobe still returns --")
    high = P.reach("invertedv", "dx", 7.074, 70.0, False, 0.0, False, 3.1, 300.0)
    check("its lower lobe is named as what comes back", "lower part of its lobe" in high["note"], True)

    print("\n-- 'nothing comes back' only when no angle does --")
    shut = P.reach("invertedv", "dx", 14.2, 35.0, False, 0.0, False, 1.0, 300.0)
    check("far above foF2, the band is shut whatever the antenna",
          (shut.get("through"), shut.get("radius_km"), "shut from here" in shut["note"]), (True, None, True))

    print("\n-- under foF2 the sky is read, and said --")
    under = P.reach("invertedv", "dx", 7.074, 39.0, False, 0.0, False, 8.0, 300.0)
    check("no 'through' when the band comes back from overhead", under.get("through"), None)
    check("  and no 'not in hand here' when it was read", "not in hand" in under["note"], False)
    check("  and says there is no skip zone tonight", "no skip zone tonight" in under["note"], True)

    print("\n-- with no sky read, the geometry stands as it was --")
    bare = P.reach("invertedv", "dx", 7.074, 39.0, False, 0.0, False, None, None)
    check("a landing distance, and the honest 'not in hand'",
          (bool(bare.get("typical_km")), "not in hand" in bare["note"]), (True, True))

    print("\n-- the Lab's route asks the sky for any HF question --")
    src = (ROOT / "elmer" / "app.py").read_text(encoding="utf-8")
    check("not only for NVIS", 'if nvis or use == "regional" or mhz < 30.0:' in src, True)
    check("  with the map's layer height when no sonde is near",
          "hmf2 = float(snap_hmf2 or propagation.HMF2_DEFAULT)" in src, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

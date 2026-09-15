#!/usr/bin/env python3
"""Checks for what has worked for others at a park or summit, and for the
bundled national parks - all without the network.

    python3 tests/test_programmes.py
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import programmes as P, references as R  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- telling a park from a summit --")
    check("US-0690 is a park", P.kind_of("US-0690"), "park")
    check("W0D/BB-001 is a summit", P.kind_of("w0d/bb-001"), "summit")
    check("a callsign is neither", P.kind_of("KC9SP"), None)
    check("  nor is a town", P.kind_of("Pine River"), None)

    print("\n-- the story, read from a record --")
    d = lambda y, m, day: datetime(y, m, day, tzinfo=timezone.utc)  # noqa: E731
    rows = [(d(2026, 3, 1), 40, 4, 0, 36, "K1AA"), (d(2026, 3, 8), 12, 0, 0, 12, "K2BB"),
            (d(2026, 5, 2), 8, 8, 0, 0, "K3CC"), (d(2025, 3, 3), 60, 0, 30, 30, "K4DD")]
    story = P._story(rows, 10)
    check("the typical haul is the median", story["typical_qsos"], 26)
    check("  and how many made their ten", story["made_it"], 75)
    check("  modes by contacts made", story["modes"], {"cw": 10, "data": 25, "phone": 65})
    check("  the busiest month first", story["busiest"][0], "March")
    check("  the most recent activation first", story["recent"][0]["call"], "K3CC")
    check("  twelve months of counts", sum(story["by_month"]), 4)
    check("no rows, no story", P._story([], 10), None)
    summit = P._story([(d(2026, 8, 22), 5, None, None, None, "NJ0Q")], 4)
    check("a summit's record has no modes", "modes" in summit, False)
    check("  and still says who made it", summit["made_it"], 100)

    print("\n-- the sentence --")
    record = {"ok": True, "kind": "park", "qualifies": 10, "story": story,
              "totals": {"activations": 203, "qsos": 11851}}
    text = P.sentence(record)
    check("the total, the modes, the typical haul, and the last one",
          all(w in text for w in ("203 activations", "11,851 contacts", "65% phone", "26 QSOs", "75% got their 10",
                                  "March", "Last activated 2026-05-02 by K3CC")), True)
    print("       " + text)
    check("an empty record says so kindly", "first one writes" in P.sentence({"ok": True}), True)

    print("\n-- what is on disk beats nothing --")
    P.CACHE.mkdir(parents=True, exist_ok=True)
    old = dict(record, ref="US-0690", name="Padre Island National Seashore", fetched_at=time.time() - 10 * 86400)
    (P.CACHE / "US-0690.json").write_text(json.dumps(old), encoding="utf-8")
    P.POTA_PARK = "http://127.0.0.1:9/park/{ref}"           # nobody home
    got = P.lookup("US-0690")
    check("a stale record comes back when the programme cannot be reached", got.get("name"),
          "Padre Island National Seashore")
    check("  marked stale", got.get("stale"), True)
    check("  with the reason", "could not reach" in got.get("error", ""), True)
    check("and nothing on disk is an honest miss", P.lookup("US-9999").get("ok"), False)

    print("\n-- the national parks, bundled --")
    parks = R.national()
    if parks:
        check("a few hundred National Park Service units", 300 < len(parks) < 700, True)
        check("  every one a park with a position", all(p["kind"] == "park" and p.get("lat") is not None for p in parks), True)
        pais = R.find("US-0690")
        check("Padre Island National Seashore is one of them", pais and pais["name"], "Padre Island National Seashore")
        check("  and it is found by name", any(r["ref"] == "US-0690" for r in R.search("padre island")), True)
        near = R.nearby(27.42, -97.30, kind="park", limit=3)
        check("  and it is the nearest park to its own visitor centre", near and near[0]["ref"], "US-0690")
        check("no national forest slipped in", any("National Forest" in p["name"] for p in parks), False)
        check("  nor a wildlife refuge", any("Wildlife Refuge" in p["name"] for p in parks), False)
        check("coverage says how many are bundled", R.coverage(27.42, -97.30).get("national"), len(parks))
    else:
        print("       (no bundle on disk - tools/build_national_parks.py makes it)")
    check("an unknown reference is None", R.find("US-9999999"), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

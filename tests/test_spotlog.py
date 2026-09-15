#!/usr/bin/env python3
"""Checks for the spot-feed record: what a unit gathers about each park
while it has a network, without ever fetching here.

    python3 tests/test_spotlog.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import spotlog as S  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


FEED = [
    {"spotId": 1, "activator": "K5AAA", "reference": "US-0690", "name": "Padre Island National Seashore",
     "frequency": "14285", "mode": "SSB", "comments": "vertical on the beach at mile 20", "spotTime": "2026-09-15T19:40:31"},
    {"spotId": 2, "activator": "K5AAA", "reference": "US-0690", "name": "Padre Island National Seashore",
     "frequency": "7062", "mode": "CW", "comments": "QSY", "spotTime": "2026-09-15T20:10:00"},
    {"spotId": 3, "activator": "W5BBB", "reference": "US-0690", "name": "Padre Island National Seashore",
     "frequency": "146520", "mode": "FM", "comments": "", "spotTime": "2026-09-15T20:12:00"},
    {"spotId": 4, "activator": "N0CCC", "reference": "US-0006", "name": "Big Bend National Park",
     "frequency": "14060", "mode": "CW", "comments": "5w efhw", "spotTime": "2026-09-15T20:15:00"},
    {"spotId": 5, "activator": "N0DDD", "reference": "", "frequency": "bogus", "mode": "", "comments": ""},
]


def main():
    print("\n-- one look at the feed, folded in --")
    data = S._load()
    when = datetime(2026, 9, 15, 20, 20, tzinfo=timezone.utc)
    check("four spots counted, the one with no park skipped", S.fold(data, FEED, when), 4)
    park = data["parks"]["US-0690"]
    check("three at Padre Island", park["spots"], 3)
    check("  on 20 m, 40 m and 2 m", park["bands"], {"20 m": 1, "40 m": 1, "2 m": 1})
    check("  SSB, CW and FM", park["modes"], {"SSB": 1, "CW": 1, "FM": 1})
    check("  two activators", sorted(park["activators"]), ["K5AAA", "W5BBB"])
    check("  in the 19 and 20 UTC hours", (park["hours"][19], park["hours"][20]), (1, 2))
    check("  and the comment that hints at an antenna and a spot is kept",
          [h["text"] for h in park["hints"]], ["vertical on the beach at mile 20"])
    check("  while 'QSY' is not", any("QSY" in h["text"] for h in park["hints"]), False)
    check("Big Bend's EFHW comment is kept too", data["parks"]["US-0006"]["hints"][0]["text"], "5w efhw")

    print("\n-- the same feed again is not counted twice --")
    check("nothing new on a resample", S.fold(data, FEED, when), 0)
    check("  the counts stand", data["parks"]["US-0690"]["spots"], 3)
    check("  but the sample is", data["samples"], 2)

    print("\n-- the story --")
    # story() reads the saved file; save what was folded first
    S._save(data)
    seen = S.story("US-0690")
    check("three spots, two activators", (seen["spots"], seen["activators"]), (3, 2))
    check("  bands with their shares", seen["bands"][0]["share"], 33)
    check("  the busy hours in UTC", seen["busy_utc"], [19, 20])
    text = S.sentence(seen)
    check("  said in a sentence", "From 3 spots this unit has seen here since 2026-09-15 (2 activators)" in text, True)
    print("       " + text)
    check("a park never seen is None", S.story("US-9999"), None)
    check("  and its sentence is empty", S.sentence(None), "")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Checks for the bench: the cards agree with the pools they cite, live
where the rule puts them, and the arithmetic beside them is right.

    python3 tests/test_bench.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import bench as B  # noqa: E402
from elmer.content import load_pools  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- where each bench lives --")
    check("the instruments are on Tools", [b["key"] for b in B.for_page("tools")], ["analyser", "meter"])
    check("safety, which the exam asks end to end, is in the Lab", [b["key"] for b in B.for_page("lab")], ["safety"])
    check("every bench has a home", sorted(B.HOME), sorted(b["key"] for b in B.BENCHES))

    print("\n-- every card says what, how, reads, why, and names its questions --")
    for bench in B.BENCHES:
        for card in bench["cards"]:
            check(f"  {card['title'][:40]}", all(card.get(k) for k in ("what", "how", "reads", "why")) and bool(card["exam"]), True)
    pools = load_pools()
    qs = B.questions_for(B.BENCHES, pools)
    named = {q for b in B.BENCHES for c in b["cards"] for q in c["exam"]}
    missing = sorted(named - set(qs))
    check("every question a card names is in a pool", missing, [])
    check("  with its answer written out", all(q["answer_text"] for q in qs.values()), True)
    check("  T0A05 is the fuse question", "fuse" in qs["T0A05"]["text"], True)
    check("  answered as the pool answers it", qs["T0A05"]["answer_text"], "Excessive current could cause a fire")
    check("  T0B06 is the ten feet", "power line" in qs["T0B06"]["text"], True)

    print("\n-- the arithmetic --")
    r = B.analyser_reading(50, 0)
    check("50 + j0 is 1:1", r["swr"], 1.0)
    r = B.analyser_reading(35, 22)
    check("35 + j22 is about 1.9:1, inductive - shorten", (r["swr"], "shorten" in r["cut"]), (1.87, True))
    r = B.analyser_reading(35, -22)
    check("  -j22 is the same SWR, capacitive - add", (r["swr"], "add" in r["cut"]), (1.87, True))
    check("a short is no reading", B.analyser_reading(0, 0), None)
    check("12 AWG, ten feet, twenty amps: two thirds of a volt", round(B.drop_volts(12, 10, 20), 2), 0.64)
    check("  16 AWG on the same run loses over a volt and a half", B.drop_volts(16, 10, 20) > 1.5, True)
    check("a twenty-amp rig gets a 25 A fuse", B.fuse_for(20), 25)
    check("  a five-amp load gets 7.5", B.fuse_for(5), 7.5)
    check("20 Ah at 1 A receive, 20 A transmit a fifth of the time: about three hours", round(B.battery_hours(20, 1, 20, 0.2), 1), 3.3)
    check("  listening only, sixteen", round(B.battery_hours(20, 1, 20, 0.0)), 16)
    check("a thirty-foot mast wants the line forty feet off", B.fall_clearance_ft(30), 40.0)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

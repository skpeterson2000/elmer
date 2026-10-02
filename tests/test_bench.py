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
    check("the near field on 40 m reaches about twenty-two feet", round(B.near_field_ft(7.1)), 22)
    check("  on 2 m, a yard", round(B.near_field_ft(146), 1), 1.1)
    check("  and on 160 m, over eighty", round(B.near_field_ft(1.9)), 82)
    check("the analyser says whether to cut at all - a permanent home cuts, the field does not",
          "If it travels, do not" in B.analyser_reading(35, 22)["where"], True)
    print("\n-- the terminator --")
    plan = B.termination_bank()
    check("600 ohms at 100 W: half of it, 50 W, rated half again", (plan["dissipate"], plan["rated"]), (50.0, 75.0))
    check("  at least 38 resistors of 2 W", plan["fewest"], 38)
    check("  every bank carries the heat", all(b["parts"] * 2 >= 75 for b in plan["banks"]), True)
    check("  and lands within ten percent", all(abs(b["total"] / 600 - 1) <= 0.10 for b in plan["banks"]), True)
    check("  forty 1.5k in four-by-ten is offered, exactly 600",
          any((b["series"], b["parallel"], b["value"], b["total"]) == (4, 10, 1500.0, 600.0) for b in plan["banks"]), True)
    check("  each part carries its equal share",
          all(abs(b["watts_each"] - 50 / b["parts"]) < 0.001 for b in plan["banks"]), True)
    hand = B.termination_bank(values=[106], each_watts=100, margin=1)
    check("the handbook's 106 ohm, 100 W resistors: six in series, 636 ohms",
          [(b["series"], b["parallel"], b["total"]) for b in hand["banks"]], [(6, 1, 636.0)])
    big = B.termination_bank(tx_watts=1500, each_watts=5)
    check("1500 W needs 225 parts of 5 W, and finds banks of them", (big["fewest"], len(big["banks"]) > 0), (225, True))
    check("  a wide fan in parallel is flagged by its voltage, or not offered first",
          all(b["volts_ok"] for b in big["banks"][1:]), True)
    check("  peak volts on one part of a single string: the whole share across it",
          B.termination_bank(values=[600], each_watts=100, margin=1)["banks"][0]["volts_peak_each"],
          round((100 * 0.5 * 600) ** 0.5 * 2 ** 0.5, 1))
    check("SSB voice heats it about a third as much as a carrier", B.termination_bank(duty=0.3)["dissipate"], 15.0)
    check("nonsense is no answer", (B.termination_bank(target_ohms=0), B.termination_bank(each_watts=0)), (None, None))
    check("a value that cannot get there says so with no banks",
          B.termination_bank(values=[1], tolerance=0.10, max_parts=20)["banks"], [])
    check("the E12 series is the dozen everyone knows", B.series_values("E12")[:12],
          [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2])
    card = next(c for b in B.BENCHES for c in b["cards"] if c["title"].startswith("The terminator"))
    check("the card says never wirewound, and names the exam's wirewound question",
          ("Never wirewound" in card["how"], "G6A06" in card["exam"]), (True, True))
    check("  and in oil: the right oils, the PCB warning, and a sweep in its can",
          ("mineral oil" in card["aside"]["text"], "PCBs" in card["aside"]["text"],
           "sweep the bank in its oil, in its can" in card["aside"]["text"]), (True, True, True))
    noise = next(c for b in B.BENCHES for c in b["cards"] if c["title"].startswith("Noise"))
    check("the noise card names the transformer and the near field", "transformer" in noise["what"] and "near field" in noise["how"], True)
    check("  and the one measurement: the S-meter against a dummy load", "dummy load" in noise["reads"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

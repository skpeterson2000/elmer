#!/usr/bin/env python3
"""What a tournament is: its length, its draw, and who is declared when.

    python3 tests/test_tournament.py

A tournament used to be an unbounded string of questions drawn with
random.choice over the whole pool. That is three separate faults wearing one
coat: every section equally likely whatever its weight on the examination, the
same question possible twice in an evening, and no end to it - so nobody ever
won anything, they just stopped playing.

It is now modelled on the examination for the licence class being played. The
pool is divided into sections, the exam takes one from each, and the number of
sections in a subelement is its weight on the paper - so drawing the same way
gets the proportions right without a second table to maintain and disagree
with the first.

Length is in blocks of twelve with a winner declared at the end of each.
Technician and General run three blocks, Extra four, which is a perk for
sitting the harder ticket rather than an accident of pool size.

What is deliberately absent is ascending difficulty. It needs a measure of
which questions are hard, this program has never recorded one, and a ramp
built out of a guess would be worse than none. `ordered` says so in a flag
rather than implying a warm-up that is not there - and the flag is tested,
because that is the half a later change drops quietly.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import netcontrol, tournament  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- how long a tournament runs --")
    check("Technician: three blocks of twelve",
          tournament.length_for("technician"), 36)
    check("General the same", tournament.length_for("general"), 36)
    check("Extra gets a fourth block for the harder ticket",
          tournament.length_for("extra"), 48)
    check("and something unheard of still gets a tournament",
          tournament.length_for("martian"), 36)

    print("\n-- where the winners fall --")
    check("the twelfth question ends a block",
          [tournament.ends_a_block(n) for n in (11, 12, 13, 24, 36)],
          [False, True, False, True, True])
    check("and the numbering follows",
          [tournament.block_of(n) for n in (1, 12, 13, 24, 25, 36)],
          [1, 1, 2, 2, 3, 3])

    print("\n-- the draw is the examination's shape --")
    # (key, pool, questions drawn, distinct sections they should cover).
    # Technician and General have 35 sections, so a 36 question draw covers
    # every one of them and doubles up on exactly one. Extra has 50, so a 48
    # question draw covers 48 of them and doubles up on none.
    for key, pool_id, want, spread in (("technician", "tech2026", 36, 35),
                                       ("general", "gen2023", 36, 35),
                                       ("extra", "extra2024", 48, 48)):
        plan = tournament.plan(pool_id, key, rng=random.Random(7))
        ids = [q["id"] for q in plan["questions"]]
        sections = [q["section"] for q in plan["questions"]]
        check(f"{key}: the right number of questions", len(ids), want)
        check("  none of them asked twice", len(set(ids)), want)
        # One per section until the sections run out: a 36 question draw over
        # 35 sections covers every one of them, and a 48 over 50 covers 48.
        check("  and spread one to a section as far as it goes",
              len(set(sections)), spread)
        counts = {}
        for code in sections:
            counts[code] = counts.get(code, 0) + 1
        check("  no section asked three times", max(counts.values()) <= 2, True)

    print("\n-- a draw bigger than the pool stops rather than spinning --")
    short = tournament.draw("tech2026", 100000, rng=random.Random(1))
    check("it gives what there is", len(short) <= 409, True)
    check("  and does not repeat to get there",
          len(short), len({q["id"] for q in short}))

    print("\n-- ascending difficulty, only when it is real --")
    items = [{"id": f"Q{i}", "section": "T1A"} for i in range(12)]
    ordered, ramped = tournament.ordered(items, None)
    check("no measure, no claim of a ramp", ramped, False)
    check("  and the blueprint order is left alone",
          [q["id"] for q in ordered], [q["id"] for q in items])

    hardness = {f"Q{i}": 11 - i for i in range(12)}
    ordered, ramped = tournament.ordered(items, lambda q: hardness[q["id"]])
    check("a full measure ramps it", ramped, True)
    check("  easiest first", [q["id"] for q in ordered][:3],
          ["Q11", "Q10", "Q9"])

    sparse = {f"Q{i}": 1 for i in range(3)}
    ordered, ramped = tournament.ordered(
        items, lambda q: sparse.get(q["id"]))
    check("three questions out of twelve is not a ramp", ramped, False)
    check("  so the order is untouched",
          [q["id"] for q in ordered], [q["id"] for q in items])

    print("\n-- the hall walks the plan and stops at the end --")
    net = netcontrol.Net("Test", 10, "technician")
    net.check_in("u1", "Poldhu", players=2)
    net.check_in("u2", "Clifden", players=2)
    net.set_plan(tournament.plan("tech2026", "technician",
                                 rng=random.Random(3)))
    state = net.plan_state()
    check("the plan is laid out before a question is asked",
          [state["asked"], state["length"], state["blocks"]], [0, 36, 3])
    check("  and does not pretend to a ramp", state["ramped"], False)

    seen, declared = [], []
    for n in range(1, 37):
        question = net.next_question()
        if question is None:
            break
        seen.append(question["id"])
        net.start_round("tech2026", question["id"], 0,
                        {"text": question["text"], "choices": ["a", "b"],
                         "section": question["section"]}, seconds=1)
        # u1 is quicker every round, so the block winner is never a coin toss.
        net.report("u1", n, [{"name": "Ann", "correct": True, "ms": 1000}])
        net.report("u2", n, [{"name": "Bob", "correct": True, "ms": 2000}])
        summary = net.close_round()
        if summary.get("block_won"):
            declared.append(summary["block_won"])

    check("every question of the tournament was asked", len(seen), 36)
    check("  each of them once", len(set(seen)), 36)
    check("nothing is left after the last one", net.next_question(), None)
    check("and the plan says so", net.plan_state()["done"], True)

    check("three winners, one per block", [d["block"] for d in declared],
          [1, 2, 3])
    check("  declared on the twelfths",
          [d["through"] for d in declared], [12, 24, 36])
    check("  the quicker table takes each one",
          {d["name"] for d in declared}, {"Poldhu"})
    check("  and the block names its best player",
          [d["player"]["name"] for d in declared], ["Ann", "Ann", "Ann"])

    print("\n-- a block is the block, not the evening --")
    # The third block's points are the third block's. A table that ran away
    # with the first twelve does not carry that into the declaration of the
    # third, or the declaration means nothing.
    check("block points are not the running total",
          declared[-1]["points"] < net.units["u1"].score, True)
    check("the evening's total is still kept",
          net.units["u1"].score > 0, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

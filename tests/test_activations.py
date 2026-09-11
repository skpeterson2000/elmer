#!/usr/bin/env python3
"""The two programmes' rules, pinned to the documents they were read from.

    python3 tests/test_activations.py

Everything else ELMER states about the outside world is physics or law, and
both hold still. These do not: POTA and SOTA are run by people who change
their own rules, so this file records what the documents said when they were
read, and the date on which somebody read them. When a rule changes, this is
what should fail.

The numbers are the whole point. Ten QSOs and four QSOs are not
interchangeable, one QSO makes a SOTA activation while four make it score,
and a station that is fine in a park is a disqualification on a summit. An
operator who packs for the wrong one of those finds out at the top.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import activations as A, reachout  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the counts, which are not interchangeable --")
    check("POTA wants ten QSOs", A.POTA["qualifies"], 10)
    check("  in one UTC day", "UTC day" in A.POTA["qualifies_note"], True)
    check("SOTA's points want four", A.SOTA["qualifies"], 4)
    check("  each with a different station",
          "different station" in A.SOTA["qualifies_note"], True)
    check("  though one QSO already makes it an activation",
          "One QSO" in A.SOTA["qualifies_note"], True)

    print("\n-- neither counts a repeater, and both count a satellite --")
    for prog in (A.POTA, A.SOTA):
        check(f"{prog['key']}: no terrestrial repeaters",
              prog["repeaters"], False)
        check(f"{prog['key']}: satellites do count", prog["satellites"], True)

    print("\n-- and the vehicle is the difference between them --")
    check("a park allows one", A.POTA["vehicle"], True)
    check("a summit does not", A.SOTA["vehicle"], False)
    check("  because everything is carried and battery powered",
          "carried up" in A.SOTA["power"], True)
    check("  and a generator is named as forbidden",
          "generator" in A.SOTA["power"], True)
    check("the activation zone is the operator's position, not the antenna's",
          "where the operator is" in A.SOTA["where"], True)
    check("  typically 25 metres, and the Association's to set",
          "25 metres" in A.SOTA["where"]
          and "Association" in A.SOTA["where"], True)
    check("a park's boundary covers the equipment too",
          "all of the equipment" in A.POTA["where"], True)

    print("\n-- every gear box on Make Contact has a verdict --")
    for key in reachout.GEAR:
        check(f"{key} is judged", key in A.GEAR_VERDICTS, True)
    for key, row in A.GEAR_VERDICTS.items():
        for prog in ("pota", "sota"):
            check(f"  {key} on {prog}", row[prog] in A.VERDICT_RANK, True)

    print("\n-- and the disqualifying one is reported first --")
    mixed = ["hf_wire", "ht", "hf_mobile", "gmrs"]
    report = A.gear_report("sota", mixed)
    check("worst news first", report[0]["key"], "hf_mobile")
    check("  and it is the vehicle whip that is forbidden",
          report[0]["verdict"], "forbidden")
    check("the same kit is fine in a park",
          A.blockers("pota", mixed), [])
    check("GMRS earns credit in neither",
          A.GEAR_VERDICTS["gmrs"]["pota"], "no credit")

    print("\n-- and every rule says where it was read --")
    for prog in (A.POTA, A.SOTA):
        check(f"{prog['key']} cites a document",
              bool(prog["source"].strip()), True)
        check(f"  and the date it was read", bool(prog["read"]), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

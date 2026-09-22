#!/usr/bin/env python3
"""Telling somebody with no licence on record that they are ready to sit one.

    python3 tests/test_ticket.py

The properties worth holding: nothing is said to an operator whose licence
class is already known, whether the FCC's record said so or they did; nothing
is said before the evidence is there, so the panel is news and not furniture;
"ready" means the exam-proven class tier and outranks a higher class that is
only "approaching"; the reading quotes the pool's own figures; and the
wording never says anybody is unlicensed, because ELMER does not know that -
it knows only what is on this account's record.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import ranks, ticket  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def standing(pool_id, step=0, odds=0.0, passed=0):
    return {"pool_id": pool_id, "step": step, "pass_probability": odds,
            "class_name": pool_id, "exams": {"passed": passed}}


READY = standing("tech2026", step=ranks.CLASS, odds=0.91, passed=4)
NEARLY = standing("tech2026", odds=0.80, passed=1)
NOWHERE = standing("tech2026", step=ranks.LEARNER, odds=0.40, passed=0)


print("\nnothing is said when a licence class is already on record")
fcc = {"license": {"found": True, "license_class": "Technician"}}
check("the FCC's record silences it",
      ticket.call_to_action(fcc, [READY]), None)
check("  and so does the operator's own word",
      ticket.call_to_action({"license_class": "General"}, [READY]), None)
check("  which is what on_record answers", ticket.on_record(fcc), True)
check("  and it is false for a blank account", ticket.on_record({}), False)


print("\nnothing is said before the evidence is there")
check("a beginner gets no panel", ticket.call_to_action({}, [NOWHERE]), None)
check("  nor does an empty standings list", ticket.call_to_action({}, []), None)
check("  good odds with no mock exam passed is not enough",
      ticket.call_to_action({}, [standing("tech2026", odds=0.95)]), None)
check("  nor is a passed exam with poor odds",
      ticket.call_to_action({}, [standing("tech2026", odds=0.4, passed=2)]), None)


print("\napproaching: good odds and a mock exam actually passed")
panel = ticket.call_to_action({}, [NEARLY])
check("the stage", panel["stage"], "approaching")
check("the class it is about", panel["class_name"], "Technician")
check("  and the headline does not claim readiness",
      "ready" in panel["headline"].lower(), False)
check("  the reading quotes the odds", "80%" in panel["reading"], True)
check("  and how many exams it rests on", "1 mock exam " in panel["reading"], True)


print("\nready: the exam-proven class tier")
panel = ticket.call_to_action({}, [READY])
check("the stage", panel["stage"], "ready")
check("the headline says to go and sit it",
      panel["headline"], "You are ready to sit Technician for real")
check("  the reading quotes the odds", "91%" in panel["reading"], True)
check("  and pluralises four exams", "4 mock exams" in panel["reading"], True)
check("  it is an estimate, and says so", "not a promise" in panel["reading"], True)


print("\nready outranks approaching, whatever the class")
panel = ticket.call_to_action({}, [
    standing("tech2026", step=ranks.CLASS, odds=0.92, passed=3),
    standing("gen2023", odds=0.78, passed=1),
])
check("technician-ready beats general-nearly", panel["pool_id"], "tech2026")

print("\n  and the highest class wins when both are at the same stage")
panel = ticket.call_to_action({}, [
    standing("tech2026", step=ranks.CLASS, odds=0.95, passed=5),
    standing("gen2023", step=ranks.ELMER, odds=0.93, passed=6),
])
check("general over technician", panel["pool_id"], "gen2023")
check("  named properly", panel["class_name"], "General")

print("\n  the commercial pools are not part of this ladder")
check("a GROL standing raises no amateur panel",
      ticket.call_to_action({}, [standing("element3", step=ranks.ELMER,
                                          odds=0.99, passed=9)]), None)


print("\nthe panel carries what actually stops people")
panel = ticket.call_to_action({}, [READY])
titles = [s["title"] for s in panel["steps"]]
check("four steps", len(panel["steps"]), 4)
check("  the FRN comes first", "FRN" in titles[0], True)
check("  finding a session is second", titles[1], "Find a session")
check("  the CORES link is on the FRN step", panel["steps"][0]["url"], ticket.CORES)
check("  and the session finder on the second",
      panel["steps"][1]["url"], ticket.SESSION_FINDER)
check("  the fee is shown as something to confirm",
      "confirming" in panel["fee_note"], True)


print("\nnothing here calls anybody unlicensed")
panel = ticket.call_to_action({}, [READY])
words = " ".join(str(v) for v in panel.values()).lower()
check("the word does not appear at all", "unlicensed" in words, False)
check("  what is said instead is about the record",
      panel["record_note"].startswith("No licence is on record"), True)

print("\nand the charge is the reason the panel exists")
check("it names the obligation", "obligations" in panel["charge"], True)
check("  and the generosity", "generous ambassador" in panel["charge"], True)
check("  and the kindness", "kindness" in panel["charge"], True)


print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)

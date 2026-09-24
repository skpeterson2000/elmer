#!/usr/bin/env python3
"""When the drawn shape comes down.

    python3 tests/test_cw_wean.py

The dits and dahs on screen are how a character is met, and they are what
shows a copyist who missed what the sound actually was. While the drill is
running they are something else: the shape can be read off the screen as it
is still being sounded, and then the answer comes from the eye. What that
trains is fluency at a thing nobody does on the air.

So the shape comes down once the sound has been heard for itself - four
clean copies running - and goes back up if the character stops being
copied. This checks the rule at its edges: the run not quite reached, the
run reached and then lost, and the old record that has no run to find
because the window was not being kept when it was written.

Nothing here touches the network or the browser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import cw  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def stat(recent, sent=None, copied=None):
    """A record from a string of sends, newest last: 1 copied, 0 missed."""
    return {"recent": recent,
            "sent": len(recent) if sent is None else sent,
            "copied": recent.count("1") if copied is None else copied,
            "confused": {}}


def main():
    print("\n-- a character not yet heard for itself keeps its shape --")
    check("never sent at all", cw.weaned(None), False)
    check("  met once, right", cw.weaned(stat("1")), False)
    check("  three clean running is not the run", cw.weaned(stat("111")), False)
    check("  three clean with a miss among them", cw.weaned(stat("11011")), False)

    print("\n-- four clean running takes it down --")
    check("four in a row", cw.weaned(stat("1111")), True)
    check("  the run may be anywhere in the window",
          cw.weaned(stat("1111" + "1" * 10)), True)
    check("  a later miss does not put it back on its own",
          cw.weaned(stat("1111" + "1" * 10 + "0")), True)

    print("\n-- but copy falling away does --")
    # Two thirds of the window copied is below the floor: the character is
    # being met again, and a person who has lost it should not have to ask.
    fallen = stat("1111" + "10" * 8)
    check("a run earned, then copy down to %d%%" % round(cw.recent_rate(fallen) * 100),
          cw.weaned(fallen), False)
    check("  and it comes back when the copy does",
          cw.weaned(stat("1111" + "10" * 8 + "1" * 12)), True)
    check("  the floor is where it is said to be", cw.WEAN_FLOOR, 0.7)
    check("  and the run is four, not three", cw.WEAN_RUN, 4)

    print("\n-- a record written before the window was kept --")
    check("solid on its lifetime figures is taken at its word",
          cw.weaned({"recent": "", "sent": 40, "copied": 38}), True)
    check("  not solid, and no run to find, keeps its shape",
          cw.weaned({"recent": "", "sent": 40, "copied": 20}), False)
    check("  and a blank record is not solid by default",
          cw.weaned({"recent": "", "sent": 0, "copied": 0}), False)

    print("\n-- the plan says which is which, and the two make up the lesson --")
    progress = {"K": stat("1" * 25), "M": stat("1111" + "10" * 8), "R": stat("11")}
    the_plan = cw.plan(progress)
    check("K is heard without its shape", "K" in the_plan["weaned"], True)
    check("  M has lost it and is drawn again", "M" in the_plan["drawn"], True)
    check("  R has not earned it yet", "R" in the_plan["drawn"], True)
    check("  every character is in one list or the other",
          sorted(the_plan["weaned"] + the_plan["drawn"]), sorted(the_plan["chars"]))
    check("  and none is in both",
          set(the_plan["weaned"]) & set(the_plan["drawn"]), set())

    print("\n-- a character never met is drawn, which is what meeting it means --")
    check("the new one is in the drawn list",
          all(c in the_plan["drawn"] for c in the_plan["new"]), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

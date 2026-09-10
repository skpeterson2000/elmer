#!/usr/bin/env python3
"""The countdown that stops a table waiting for somebody who is not coming.

    python3 tests/test_party_start.py

A player scans the code, lands on a screen that says "waiting for the next
question", and waits - because a round only ever went up when a person at the
table screen pressed for one. On a club night that is right; the instructor
starts the evening. For one operator with a Pi and a phone it is a program
that does not work, and it looks exactly like a program that is broken.

So a table with somebody in it now starts on its own. What is checked here is
the room's half of that: it holds the countdown as a time, and clears it. What
decides whether to arm one at all - not under a net, nothing already running,
somebody actually here - lives in the app beside the clocks and the request,
and was checked by driving a running unit rather than from here.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import party  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    room = party.Room(cohorts=2)

    print("\n-- an empty table is waiting for nothing in particular --")
    check("no countdown to begin with", room.waiting_to_start(), False)
    check("  and the state says so", room.state()["starts_in"], None)
    check("nobody here", room.people_here(), 0)

    print("\n-- arming one puts a time on it --")
    room.arm_start(15)
    check("armed", room.waiting_to_start(), True)
    left = room.state()["starts_in"]
    check("  and the screens are told how long", 14.0 < left <= 15.0, True)
    time.sleep(0.3)
    check("  which goes down on its own",
          room.state()["starts_in"] < left, True)

    print("\n-- and it never reads as overdue --")
    # A negative number on a countdown means something has gone wrong, not
    # that the moment is near. It floors at zero and the thing that fires it
    # decides what happens next.
    room.arm_start(-5)
    check("a time already past reads as zero",
          room.state()["starts_in"], 0.0)

    print("\n-- disarming clears it --")
    room.disarm_start()
    check("no longer armed", room.waiting_to_start(), False)
    check("  and nothing to count", room.state()["starts_in"], None)

    print("\n-- people are counted apart from practice opponents --")
    player, why = room.join("KC9SP")
    check("a person joined", player is not None, True)
    check("  and is counted", room.people_here(), 1)
    room.fill_bots()
    check("practice opponents arrive", room.state()["bots"] > 0, True)
    check("  and are not people", room.people_here(), 1)
    check("  which is what a countdown for an empty room would turn on",
          room.state()["people"], 1)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

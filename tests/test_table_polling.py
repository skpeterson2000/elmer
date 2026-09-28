#!/usr/bin/env python3
"""The table screen asks for less, and its clocks still count every second.

    python3 tests/test_table_polling.py

A party table screen made 998 requests in ten minutes: its state every
second, the tournament's state every two seconds on a timer of its own,
the net every five and nearby golf every eight. What is held here:

  - /api/party/state carries the tournament's state (auto_state), and the
    table has no timer of its own asking /api/party/auto-state;
  - the state is asked every two seconds while a round is on and every
    five between rounds; the net every fifteen; nearby golf every thirty;
  - the clocks on the screen are counted in the page between polls, from
    the moment each reaches nought.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
ROOT = Path(__file__).resolve().parents[1]
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    page = (ROOT / "elmer" / "templates" / "party_table.html").read_text(encoding="utf-8")

    print("\n-- one poll carries what two did --")
    from elmer.app import app
    from elmer import party
    party.room(create=True)              # a table open, as a screen would find it
    c = app.test_client()
    r = c.get("/api/party/state", environ_base=LOCAL)
    state = r.get_json() or {}
    check("the table's state says whether a tournament is running",
          (r.status_code, set((state.get("auto_state") or {}).keys())), (200, {"auto", "mode"}))
    check("  and the table no longer asks for it on a timer of its own",
          ("setInterval(autoTick" in page, "api('/api/party/auto-state')" in page), (False, False))
    check("  the old route still answers, for a page from an older build",
          c.get("/api/party/auto-state", environ_base=LOCAL).status_code, 200)

    print("\n-- how often --")
    fast = re.search(r"const TABLE_FAST = (\d+), TABLE_WAIT = (\d+);", page)
    check("the state: two seconds during a round, five between",
          fast.groups() if fast else None, ("2000", "5000"))
    check("the net: every fifteen seconds", "setInterval(netTick, 15000)" in page, True)
    check("nearby golf: every thirty seconds", "setInterval(nearbyGolf, 30000)" in page, True)
    per_ten_min = 600 // 2 + 600 // 15 + 600 // 30
    check("  so a table in play asks about 360 times in ten minutes, not a thousand",
          per_ten_min <= 400, True)

    print("\n-- the clocks count here --")
    check("each clock is held as the moment it reaches nought",
          "function holdClock(key, secs)" in page and "setInterval(() => {\n  document.querySelectorAll('[data-count]')" in page,
          True)
    for where, key in (("the round clock", "'round' + (round.number || '')"),
                       ("the start countdown", "holdClock('start', secs)"),
                       ("the pick clock", "holdClock('pick', shoot.pick_remaining)"),
                       ("the hall's pick clock", "holdClock('hallpick', sh.pick_remaining)")):
        check(f"  {where} is one of them", key in page, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

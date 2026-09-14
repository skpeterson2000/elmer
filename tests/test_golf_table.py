#!/usr/bin/env python3
"""Golf at a table: the club chosen before the question, the pause for
choosing, the stroke the round becomes, and the card the phone reads.

    python3 tests/test_golf_table.py

The rules are tested in test_golf.py; this is the room around them. A
table starts a round on the course that goes with its pool; a person
chooses a club and a practice player does not need to; the director
waits for the choosing and not past its clock; the round's answers become
strokes with those clubs; and the view a phone reads has the hole, this
player's ball and clubs, the last strokes in words, and the card.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import app as appmod, autoplay, party  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    client = appmod.app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    party.close_room()
    room = party.room(create=True, cohorts=1)
    ann = room.join("KC9SP")[0].id

    print("\n-- a round starts on the pool's course --")
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "back",
                                             "seconds": 30, "level": "Elmer"}, environ_base=local)
    check("taken", r.status_code, 200)
    s = r.get_json()
    check("  the table is playing golf", s["mode"], "golf")
    check("  on the Old Course, for General", s["golf"]["course"], "st-andrews-old")
    check("  the back nine, from the 10th", (s["golf"]["holes"], s["golf"]["hole"]), (9, 10))
    check("  practice players sat down", len(room.players) > 1, True)
    autoplay.stop()                              # the director is not the subject here

    print("\n-- the club, chosen before the question --")
    v = client.get(f"/api/party/state?player={ann}", environ_base=local).get_json()["golf"]
    check("every club from the tee", v["you"]["clubs"], ["driver", "wood", "iron", "wedge"])
    check("  the sensible one lit until chosen", (v["your_club"], v["you"]["default_club"]), (None, "driver"))
    check("  the table waits for the person", (v["choosing"], room.waiting_for_clubs()), (True, True))
    r = client.post("/api/party/club", json={"player": ann, "club": "iron"}, environ_base=local)
    check("an iron", (r.status_code, r.get_json()["club"]), (200, "iron"))
    check("  and the waiting is over - practice players choose for themselves", room.waiting_for_clubs(), False)
    r = client.post("/api/party/club", json={"player": ann, "club": "putter"}, environ_base=local)
    check("a putter from the tee is refused, naming the clubs", (r.status_code, "driver" in r.get_json()["message"]),
          (409, True))

    print("\n-- the clock on choosing --")
    room.clubs = {}
    room._clubs_since = party._now() - party.CLUB_SECONDS - 1
    check("past its clock, the table does not wait", room.waiting_for_clubs(), False)
    room._clubs_since = party._now()
    check("  and within it, it does", room.waiting_for_clubs(), True)
    room.choose_club(ann, "iron")

    print("\n-- the round is a stroke --")
    room.start_round("technician", "T1A01", 0, seconds=30,
                     payload={"text": "?", "choices": ["a", "b", "c", "d"], "section": "T1A"}, tag=1)
    r = client.post("/api/party/club", json={"player": ann, "club": "wedge"}, environ_base=local)
    check("no changing the club with a question open", r.status_code, 409)
    room.submit(ann, 0, 1500)
    summary = room.close_round()
    shot = summary["golf"]["shots"][ann]
    check("the stroke was played with the iron", shot["club"], "iron")
    check("  a right answer in 1.5 s flew it", shot["kind"] in ("fairway", "green", "sand", "water"), True)
    check("  and the clubs are cleared for the next", room.clubs, {})
    v = client.get(f"/api/party/state?player={ann}", environ_base=local).get_json()["golf"]
    check("the phone reads the playback", any(s["player"] == ann and "iron" in s["words"] for s in v["last"]), True)
    check("  and the card", [r["name"] for r in v["leaderboard"]][:1] != [], True)
    check("  and the table is choosing again", v["choosing"], True)

    print("\n-- strokes given, only with the switch --")
    party.close_room()
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front",
                                             "handicap": False, "level": "Elmer"}, environ_base=local)
    check("off: nobody given anything", r.get_json()["golf"]["handicaps"], False)
    autoplay.stop()
    party.close_room()
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front",
                                             "handicap": True, "level": "Elmer"}, environ_base=local)
    g = r.get_json()["golf"]
    check("on, with no study on this unit: still scratch, and said so",
          (g["handicaps"], g["handicaps_given"]), (False, {}))
    autoplay.stop()

    print("\n-- back to a tournament --")
    r = client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=local)
    check("the round is put away", (r.get_json()["mode"], room.golf), ("tournament", None))
    party.close_room()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    finally:
        autoplay.stop()
        time.sleep(0.1)

#!/usr/bin/env python3
"""The size of the golf group is what you chose, whenever you chose it.

    python3 tests/test_golf_group.py

Reported: "how does one set the number of virtual players in a group? Is
the order of that selection important? I get mixed results, and sometimes
find myself in a surprise group of 4 when I have selected 1, so the order
DOES make a difference."

It did. The count was read once, when the Golf button was pressed, and
never again - so choosing it afterwards did nothing, and the default was a
foursome. Press Golf, then pick "the course to yourself", and tee off with
three strangers. Pick first, then press, and it worked. Nothing on the
screen said which order was the right one, because the only instructions
were tooltips.

The room already knew how to seat or send home practice players wherever
golf was in its life; the page never asked it to. Now the count is sent the
moment it is changed, from the tile or from the clubhouse, and what is held
here is the reported sequence in particular: press first, choose second,
and the group you chose is the group you tee off in.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

from elmer import app as appmod, party  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def bots(room):
    return sorted(p.name for p in room.players.values() if p.bot)


def main():
    from elmer import db, gating
    conn = db.connect()
    st = db.get_profile(conn)["settings"]
    st[gating.SETTING] = "off"
    db.save_settings(conn, st)
    client = appmod.app.test_client()
    party.close_room()
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")

    print("\n-- the reported order: press Golf first, choose the group second --")
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "front",
                                             "seconds": 30, "tee_in": 300, "companions": 3},
                    environ_base=LOCAL)
    check("Golf pressed with the default foursome: a tee time is booked", r.status_code, 200)
    check("  and three practice players are seated", len(bots(room)), 3)
    r = client.post("/api/party/bots", json={"on": True, "companions": 1}, environ_base=LOCAL)
    check("then choosing one companion is taken now, not at the next press", r.status_code, 200)
    check("  two are sent home", len(bots(room)), 1)
    check("  and the clubhouse says so", r.get_json()["clubhouse"]["companions"], 1)
    r = client.post("/api/party/bots", json={"on": True, "companions": 0}, environ_base=LOCAL)
    check("the course to yourself: the last one goes", len(bots(room)), 0)
    r = client.post("/api/party/bots", json={"on": True, "companions": 2}, environ_base=LOCAL)
    check("and back to two seats two", len(bots(room)), 2)

    print("\n-- what you chose last is what you tee off with --")
    client.post("/api/party/bots", json={"on": True, "companions": 1}, environ_base=LOCAL)
    r = client.post("/api/party/tee-off", json={}, environ_base=LOCAL)
    check("tee off", r.status_code, 200)
    people = [p for p in room.players.values() if not p.bot]
    check("the group is you and one companion, not a surprise foursome",
          (len(people), len(bots(room))), (1, 1))

    print("\n-- the count is held to the group's size, and a bad value is ignored --")
    party.close_room()
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "front",
                                         "seconds": 30, "tee_in": 300, "companions": 0}, environ_base=LOCAL)
    check("no companions from the start seats nobody", len(bots(room)), 0)
    client.post("/api/party/bots", json={"on": True, "companions": 9}, environ_base=LOCAL)
    check("  nine is held to a foursome's three", len(bots(room)), 3)
    before = len(bots(room))
    r = client.post("/api/party/bots", json={"on": True, "companions": "lots"}, environ_base=LOCAL)
    check("  and nonsense changes nothing", (r.status_code, len(bots(room))), (200, before))

    print("\n-- the page says how a round goes, on the screen and not in a tooltip --")
    page = (Path(__file__).resolve().parents[1] / "elmer" / "templates" / "party_table.html").read_text(encoding="utf-8")
    check("the tile carries the three steps", all(w in page for w in ("gc-howto", "Press <b>Golf</b>", "Play now")), True)
    check("  the clubhouse has the group control too", "data-club-companions" in page, True)
    check("  the tile's control is live", "golfGroup(parseInt(e.target.value" in page, True)
    check("  and the choice is remembered", "elmer_golf_setup" in page, True)
    check("  and it no longer says practice players make up the rest, whatever you chose",
          "practice players make up the rest" in page, False)

    party.close_room()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

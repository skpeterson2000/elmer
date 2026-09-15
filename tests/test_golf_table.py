#!/usr/bin/env python3
"""Golf at a table: one stroke at a time, nobody on a clock, the club
chosen with the question, and the card the phone reads.

    python3 tests/test_golf_table.py

The rules are tested in test_golf.py; this is the room around them. A
table starts a round on the course that goes with its pool with a
foursome at most; the question goes to whoever is away and nobody else
may answer it; a person chooses a club up to the swing; a practice
player's stroke is quick and its reveal short; the group's question has
a thread; somebody sitting down late gets a ball; and the view a phone
reads has the hole, whose turn it is, this player's ball and clubs, the
last stroke in words, and the card.
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


def bot_id_for_hit(room):
    return next(p.id for p in room.players.values() if p.bot)


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
    check("  practice players sat down, and no more than a foursome",
          (len(room.players) > 1, len(room.players) <= party.FOURSOME), (True, True))
    autoplay.stop()                              # the director is not the subject here
    room.round = None                            # whatever it asked before it stopped

    print("\n-- whose stroke it is --")
    v = client.get(f"/api/party/state?player={ann}", environ_base=local).get_json()["golf"]
    check("on the first tee the person is away - people first", (v["away"], v["your_turn"]), (ann, True))
    check("every club from the tee", v["you"]["clubs"], ["driver", "wood", "iron", "wedge"])
    check("  the sensible one lit until chosen", (v["your_club"], v["you"]["default_club"]), (None, "driver"))
    r = client.post("/api/party/club", json={"player": ann, "club": "iron"}, environ_base=local)
    check("an iron", (r.status_code, r.get_json()["club"]), (200, "iron"))
    r = client.post("/api/party/club", json={"player": ann, "club": "putter"}, environ_base=local)
    check("a putter from the tee is refused, naming the clubs", (r.status_code, "driver" in r.get_json()["message"]),
          (409, True))

    print("\n-- a person's address waits on their Hit --")
    check("the address is theirs: it stands until they say hit", room.golf_prelude(), party.PERSON_ADDRESS)
    check("  and the screens are told the question waits", (room.golf_address_waits(), v["address_waits"]), (True, True))
    r = client.post("/api/party/hit", json={"player": bot_id_for_hit(room)}, environ_base=local)
    check("  a practice player's press is not a hit", r.status_code, 409)
    r = client.post("/api/party/hit", json={"player": ann}, environ_base=local)
    check("  the golfer's is - with no director running there is nothing to hurry, but it is taken", (r.status_code, r.get_json()["hit"]), (200, False))

    print("\n-- the question goes to the player who is away, and is not timed --")
    rnd = appmod._ask_party("general", None, 30)
    check("put to the person", rnd.to, ann)
    check("  with no clock worth the name", rnd.seconds, party.GOLF_SECONDS)
    check("  in this hole's area", (rnd.payload["section"], room.golf.hole_section), (room.golf.hole_section, room.golf.hole_section))
    st = client.get(f"/api/party/state?player={ann}", environ_base=local).get_json()
    check("  the screens are told whose it is", (st["round"]["to"], st["round"]["to_name"]), (ann, "KC9SP"))
    bot = next(p for p in room.players.values() if p.bot)
    check("a practice player cannot play it", room.submit(bot.id, 0, 1000)[1], "not your stroke - KC9SP is away")
    check("  and none is planning to", room.round.bot_plan, {})
    check("  and only the person's answer closes it", room.everyone_answered(), False)
    r = client.post("/api/party/club", json={"player": ann, "club": "wedge"}, environ_base=local)
    check("the club can still change with the question open - up to the swing", r.status_code, 200)
    room.submit(ann, rnd.answer_index, 90000)          # a minute and a half of thinking
    check("  the person's answer closes it", room.everyone_answered(), True)
    summary = room.close_round()
    shots = summary["golf"]["shots"]
    check("the stroke was the person's alone, with the wedge", (list(shots), shots[ann]["club"]), ([ann], "wedge"))
    check("  a right answer flew it, however long it took", shots[ann]["kind"] in ("fairway", "green", "sand", "water", "long"), True)
    check("  and the club is cleared for the next", ann in room.clubs, False)
    check("  a stroke by a person stands until they have read it", room.reveal_seconds(summary, 8.0), party.PERSON_REVEAL)
    r = client.post("/api/party/next", json={}, environ_base=local)
    check("  and Next stroke is a press the table can make", r.status_code, 200)
    v = client.get(f"/api/party/state?player={ann}", environ_base=local).get_json()["golf"]
    check("the phone reads the playback", any(s["player"] == ann and "wedge" in s["words"] for s in v["last"]), True)
    check("  and the card", [r["name"] for r in v["leaderboard"]][:1] != [], True)
    check("  and who is away now: a practice player, still on the tee", (v["away"] != ann, v["your_turn"]), (True, False))

    print("\n-- a practice player's stroke is quick, and its reveal short --")
    rnd = appmod._ask_party("general", None, 30)
    check("put to the practice player who is away", rnd.to, v["away"])
    plan = room.round.bot_plan.get(rnd.to)
    want = party.bot_swing_seconds(rnd.payload, room.golf_pace)
    check("  who swings at reading pace, never under the floor",
          bool(plan) and party.BOT_READ_LEAST <= plan["at"] <= max(want * 1.15, party.BOT_READ_LEAST) + 0.01, True)
    check("  a long question takes longer than a short one",
          party.bot_swing_seconds({"text": " ".join(["word"] * 60), "choices": ["a", "b"]}) >
          party.bot_swing_seconds({"text": "short", "choices": ["a", "b"]}), True)
    check("  and the table's pace caps it", party.bot_swing_seconds({"text": " ".join(["word"] * 200)}, 25), 25.0)
    check("  never under the floor, whatever the pace box says",
          party.bot_swing_seconds({"text": "short"}, 5), party.BOT_READ_LEAST)
    check("  and the tempo scales it", party.bot_swing_seconds({"text": "short"}, None, 2.0), party.BOT_READ_LEAST * 2)
    check("  the address stands before the question - the group is off the tee by now",
          room.golf_prelude(), party.GOLF_PRELUDE)
    check("  (on the tee it would be longer, but a person tees off first here and theirs waits on them)",
          party.TEE_PRELUDE > party.GOLF_PRELUDE, True)
    check("  and a practice player's stroke does not wait on anybody", room.golf_address_waits(), False)
    check("  and the person cannot play it for them", room.submit(ann, 0, 1000)[0], None)
    room.round.opened_at -= plan["at"] + 1
    room.run_bots()
    check("  the swing arrives on its own", room.everyone_answered(), True)
    summary = room.close_round()
    check("  and stands long enough to be read", room.reveal_seconds(summary, 8.0), party.BOT_REVEAL)
    check("  the card stands longer still when the hole is done",
          room.reveal_seconds({"golf": {"shots": {}, "hole_done": True}}, 8.0), party.HOLE_DONE_REVEAL)

    print("\n-- sitting down late: a tee time --")
    late = room.join("W9LATE")[0].id
    check("mid-hole, a tee time rather than a ball", (late in room.golf.balls, late in room.golf.tee_times), (False, True))
    v = client.get(f"/api/party/state?player={late}", environ_base=local).get_json()["golf"]
    check("  and the phone is told so", (v["your_tee_time"], "W9LATE" in v["tee_times"]), (True, True))
    check("  and the group is still a foursome at most", len(room.players) <= party.FOURSOME, True)
    room.leave(late)
    check("leaving takes the ball", late in room.golf.balls, False)

    print("\n-- the next stroke is got ready while this one is read --")
    party.close_room()
    room = party.room(create=True, cohorts=1)
    ann = room.join("KC9SP")[0].id
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front",
                                             "seconds": 30, "level": "Elmer"}, environ_base=local)
    autoplay.stop()
    room.round = None
    rnd = appmod._ask_party("technician", None, 30)
    check("no next stroke is ready before a stroke has closed", room.golf_next, None)
    room.submit(ann, rnd.answer_index, 3000)
    room.close_round()
    nxt = room.golf_next
    check("closing a stroke draws the next question, for whoever is away next",
          (nxt is not None, nxt and nxt["to"] == room.golf.away()), (True, True))
    st = client.get("/api/party/state", environ_base=local).get_json()["golf"]
    check("  and the state names its figure for the screens to fetch, or None",
          "next_figure" in st and st["next_figure"] == (nxt or {}).get("figure"), True)
    rnd2 = appmod._ask_party("technician", None, 30)
    check("  the next stroke asks that very question, and it is used up",
          (rnd2.question_id, room.golf_next), (nxt["id"], None))
    r = client.get("/golf/map/pebble-beach/1.svg", environ_base=local)
    check("the hole map is served, and kept a day", (r.status_code, r.mimetype, r.headers.get("Cache-Control")),
          (200, "image/svg+xml", "public, max-age=86400"))
    r = client.get(f"/api/party/golf/map.svg?player={ann}", environ_base=local)
    check("  and the live one has the balls on it", (r.status_code, "<circle cx=" in r.get_data(as_text=True)), (200, True))
    check("  a hole nobody has", client.get("/golf/map/pebble-beach/99.svg", environ_base=local).status_code, 404)
    r = client.get("/api/party/golf-assets", environ_base=local).get_json()
    check("the round's assets, for warming: the clubhouse and the tees this unit has",
          ("/static/golf/clubhouse/pebble-beach.jpg" in r["urls"], "/static/golf/tee/pebble-beach/1.jpg" in r["urls"]),
          (True, True))
    r = client.get("/static/golf/tee/pebble-beach/1.jpg", environ_base=local)
    check("  which a phone may keep a day", r.headers.get("Cache-Control"), "public, max-age=86400")

    print("\n-- the regulars, and the record board --")
    client.post("/api/party/join", json={"name": "W9REG", "device": "phone"}, environ_base=local)
    r = client.get("/api/party/regulars", environ_base=local).get_json()
    check("somebody who joined is remembered as a regular", "W9REG" in r["regulars"], True)
    from elmer import db as _db
    c2 = _db.connect()
    appmod._note_golf_records(c2, [{"name": "KC9SP", "to_par": 2, "bot": False}, {"name": "Beacon", "to_par": 0, "bot": True}],
                              "pebble-beach", "Pebble Beach Golf Links", [{"name": "KC9SP", "ace": True}])
    appmod._note_golf_records(c2, [{"name": "KC9SP", "to_par": -1, "bot": False}], "st-andrews-old", "The Old Course", [])
    c2.commit(); c2.close()
    r = client.get("/api/party/regulars", environ_base=local).get_json()
    me = next(x for x in r["records"] if x["name"] == "KC9SP")
    check("two rounds, the best kept with its course, the ace counted",
          (me["rounds"], me["best_to_par"], me["best_course"], me["aces"]), (2, -1, "The Old Course", 1))
    check("  and practice players are not on the board", any(x["name"] == "Beacon" for x in r["records"]), False)

    print("\n-- the clubhouse: a tee time, and the group departs --")
    party.close_room()
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    room.arm_start(15)                    # sitting down armed the table's own countdown
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front",
                                             "tee_in": 300, "level": "Elmer"}, environ_base=local)
    st = r.get_json() if r.status_code == 200 else {}
    st = client.get("/api/party/state", environ_base=local).get_json()
    check("a tee time is booked, and no round is on yet", (st["clubhouse"] is not None, st["golf"]), (True, None))
    check("  booking it took the seat's countdown off", room.waiting_to_start(), False)
    room.arm_start(15)                    # and were it still armed, firing does not put a tournament over the booking
    check("  a countdown firing into the clubhouse does nothing",
          (appmod._party_begin(room, "technician", True), room.clubhouse is not None, room.waiting_to_start()),
          (False, True, False))
    check("  five minutes, one in the group of four", (290 < st["clubhouse"]["tee_in"] <= 300, st["clubhouse"]["people"]),
          (True, ["KC9SP"]))
    check("  with the course's clubhouse on the wall", (st["clubhouse"]["backdrop"], st["clubhouse"]["course_name"]),
          ("pebble-beach", "Pebble Beach Golf Links"))
    r = client.post("/api/party/tee-off", json={}, environ_base=local)
    check("  and, on the first tee, the view from it", r.get_json()["golf"]["tee_pic"], "/static/golf/tee/pebble-beach/1.jpg")
    autoplay.stop()
    for n in ("W1AW", "N0CALL", "K9XYZ"):
        client.post("/api/party/join", json={"name": n, "device": "phone"}, environ_base=local)
    st = client.get("/api/party/state", environ_base=local).get_json()
    check("a fourth person fills the group, and it departs", (st["clubhouse"], st["mode"], st["golf"] is not None),
          (None, "golf", True))
    check("  four people, no practice players", sorted(b["name"] for b in st["golf"]["balls"].values()),
          ["K9XYZ", "KC9SP", "N0CALL", "W1AW"])
    autoplay.stop()
    party.close_room()
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "tee_in": 600, "level": "Elmer"},
                environ_base=local)
    r = client.post("/api/party/tee-off", json={}, environ_base=local)
    check("play now departs at once, with practice players making up the four",
          (r.get_json()["ok"], r.get_json()["clubhouse"], len(r.get_json()["golf"]["balls"])), (True, None, 4))
    autoplay.stop()
    r = client.post("/api/party/tee-off", json={}, environ_base=local)
    check("  and there is nothing to depart from twice", r.status_code, 409)
    party.close_room()
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "tee_in": 600, "level": "Elmer"},
                environ_base=local)
    client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=local)
    check("cancelling the tee time empties the clubhouse", room.clubhouse, None)
    check("the timer's word does nothing once the booking has gone", appmod._golf_depart(room, armed_only=True), False)

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

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
    check("  a right answer flew it, however long it took", "foul" in shots[ann]["words"], False)
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
    person = next(p for p in room.players if not room.players[p].bot)
    check("  but a person's putt that finishes the hole stands until they press, not on the hole's clock",
          room.reveal_seconds({"golf": {"shots": {person: {}}, "hole_done": True}}, 8.0), party.PERSON_REVEAL)

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
    check("  with no mark on it yet", 'class="mark"' in r.get_data(as_text=True), False)
    r = client.post("/api/party/aim", json={"player": ann, "at": 330, "off": -12}, environ_base=local)
    check("a tap on the strip is the golfer's mark", (r.status_code, r.get_json()["aim"]), (200, {"at": 330, "off": -12, "set": True}))
    st = client.get(f"/api/party/state?player={ann}", environ_base=local).get_json()["golf"]
    check("  the state carries it, and the strip's geometry for the next tap",
          (st["you"]["aim"]["set"], st["map"]["yards"], st["map"]["w"]), (True, 377, 260))
    r = client.get(f"/api/party/golf/map.svg?player={ann}", environ_base=local)
    check("  and the mark is drawn", 'class="mark"' in r.get_data(as_text=True), True)
    r = client.get("/api/party/golf/map.svg", environ_base=local)
    check("  the table's strip shows where the last stroke was aimed, beside where it went",
          'class="aimed"' in r.get_data(as_text=True), True)
    r = client.post("/api/party/aim", json={"player": ann, "clear": True}, environ_base=local)
    check("  aim at the pin again", r.get_json()["aim"]["set"], False)
    r = client.post("/api/party/aim", json={"player": 99999, "at": 200}, environ_base=local)
    check("  a stranger has no mark here", r.status_code, 404)
    check("  a hole nobody has", client.get("/golf/map/pebble-beach/99.svg", environ_base=local).status_code, 404)
    # The wall is the signed-in operator's own, hung from their account.
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (800, 600), (240, 230, 210)).save(buf, "PNG")
    client.post("/api/awards/add", data={"file": (io.BytesIO(buf.getvalue()), "ewac.png"), "title": "eWAC", "issued": "eQSL.cc"},
                content_type="multipart/form-data", environ_base=local)
    r = client.get("/api/golf/proshop", environ_base=local)
    d = r.get_json()
    check("the pro shop: the wall, with the operator's own certificates",
          (r.status_code, [a["title"][:4] for a in d["wall"]], all(a["issued"] for a in d["wall"])), (200, ["eWAC"], True))
    check("  every certificate on it is served", all(client.get(a["url"], environ_base=local).status_code == 200 for a in d["wall"]), True)
    check("  and the record board is on the counter", isinstance(d["records"], list), True)
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

    print("\n-- the standing game: golf set up before anybody arrives --")
    party.close_room()
    room = party.room(create=True, cohorts=1)
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front",
                                             "tee_in": 120, "level": "Operator"}, environ_base=local)
    st = r.get_json()
    check("on an empty table, golf is the standing game - no round, no clubhouse yet",
          (st["standing"]["mode"], st["standing"]["course_name"], st["standing"]["tee_in"], st["golf"], st["clubhouse"]),
          ("golf", "Pebble Beach Golf Links", 120.0, None, None))
    check("  and nothing is counting down to a tournament", room.waiting_to_start(), False)
    page = client.get("/party/1", environ_base=local).get_data(as_text=True)
    check("  the screen is named for the course, not the table", ("<h1>Pebble Beach</h1>" in page, "Table 1</h1>" in page), (True, False))
    r = client.post("/api/party/join", json={"name": "W1AW", "device": "phone"}, environ_base=local)
    st = client.get("/api/party/state", environ_base=local).get_json()
    check("the first person to scan in is met by the clubhouse, with the tee time the host set",
          (st["clubhouse"] is not None, 110 < (st["clubhouse"] or {}).get("tee_in", 0) <= 120, st["standing"], st["starts_in"]),
          (True, True, None, None))
    check("  and the practice players are the level the host chose, spread",
          sorted(p.bot for p in room.players.values() if p.bot), sorted(["Operator", "Learner", "Elmer"]))
    client.post("/api/party/tee-off", json={}, environ_base=local)
    autoplay.stop()
    check("  and the round is at that course", room.golf.course["id"], "pebble-beach")
    party.close_room()
    room = party.room(create=True, cohorts=1)
    client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "tee_in": 0}, environ_base=local)
    check("with no tee time asked for, a standing game still gives the first arrival five minutes",
          room.standing["tee_in"], appmod.DEFAULT_TEE_IN)
    client.post("/api/party/join", json={"name": "KC9SP", "device": "screen", "build": appmod._build()}, environ_base=local)
    check("  and sitting down at the screen is an arrival too: the clubhouse opens", (room.clubhouse is not None, room.standing), (True, None))
    client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=local)
    party.close_room()
    room = party.room(create=True, cohorts=1)
    client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "tee_in": 0}, environ_base=local)
    client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=local)
    check("  and 'not golf after all' clears it", room.standing, None)
    client.post("/api/party/mode", json={"mode": "cutthroat", "difficulty": "technician"}, environ_base=local)
    check("any game can be the standing game, re-chosen as often as the host likes", room.standing["mode"], "cutthroat")
    client.post("/api/party/mode", json={"mode": "baseball", "innings": 1}, environ_base=local)
    check("  the last choice stands", (room.standing["mode"], room.standing["spec"]["innings"]), ("baseball", 1))
    client.post("/api/party/mode", json={"mode": "cutthroat", "difficulty": "technician"}, environ_base=local)
    client.post("/api/party/join", json={"name": "W1AW", "device": "phone"}, environ_base=local)
    check("  and the first arrival starts it - a CutThroat, with practice players making the field",
          (room.mode, room.cutthroat is not None, room.standing), ("cutthroat", True, None))
    autoplay.stop()
    party.close_room()
    room = party.room(create=True, cohorts=1)
    client.post("/api/party/mode", json={"mode": "baseball", "innings": 1}, environ_base=local)
    client.post("/api/party/join", json={"name": "W1AW", "device": "phone"}, environ_base=local)
    check("  a standing ballgame starts for the first arrival too", (room.mode, room.baseball is not None), ("baseball", True))
    client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=local)

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

    print("\n-- the round comes back to the person, and the screens show it --")
    # The freeze of 2026-09-14: after the person's tee shot the practice
    # players played through, the round came back to the person - and the
    # screens went on showing the last practice player's result, because a
    # closed round stays on the table until the next question is asked and
    # the address is only drawn when there is no round. With an address that
    # waits on the person's Hit, that was a round that stood still for ever.
    party.close_room()
    room = party.room(create=True, cohorts=1)
    ann = room.join("KC9SP")[0].id
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front",
                                             "level": "Elmer"}, environ_base=local)
    driver = autoplay.director()
    check("the round is under way with a director", bool(driver and driver.as_dict()["running"]), True)
    saved = (party.PERSON_REVEAL, party.BOT_REVEAL, party.GOLF_PRELUDE, party.TEE_PRELUDE, party.BOT_READ_LEAST,
             party.BOT_READ_BASE, party.HOLE_DONE_REVEAL, autoplay.BETWEEN_MIN)
    # Fast beats for the test - but a person's address still waits.
    party.PERSON_REVEAL, party.BOT_REVEAL, party.GOLF_PRELUDE, party.TEE_PRELUDE = 0.2, 0.2, 0.2, 0.2
    party.BOT_READ_LEAST, party.BOT_READ_BASE, party.HOLE_DONE_REVEAL, autoplay.BETWEEN_MIN = 0.3, 0.1, 0.2, 0.1
    driver.reveal = 0.2
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not (room.round and not room.round.closed and room.round.to == ann):
            if driver.state == "addressing" and room.golf_away() == ann:
                client.post("/api/party/hit", json={"player": ann}, environ_base=local)
            time.sleep(0.1)
        check("the first question is the person's, after their Hit", room.round is not None and room.round.to == ann, True)
        room.submit(ann, room.round.answer_index, 5000)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not (room.round and room.round.closed):
            time.sleep(0.05)
        st = client.get("/api/party/state", environ_base=local).get_json()
        check("  the person's result stands until they say Next stroke", (st["round"]["closed"], st["addressing"]), (True, False))
        client.post("/api/party/next", json={}, environ_base=local)
        # The practice players play through on their own - every stroke of
        # theirs until the person is farthest out again, which with the
        # club's say in where balls land may be a while - and the address
        # then waits on the person.
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline and not (driver.state == "addressing" and room.golf_away() == ann):
            time.sleep(0.1)
        check("the practice players played through and the person is away again",
              (driver.state, room.golf_away() == ann), ("addressing", True))
        st = client.get(f"/api/party/state?player={ann}", environ_base=local).get_json()
        check("  the state says so - addressing, the question waiting on their Hit",
              (st["addressing"], st["golf"]["address_waits"], st["golf"]["your_turn"]), (True, True, True))
        check("  and the closed round before it is still there for a screen that wants it", st["round"] is not None, True)
        time.sleep(1.0)
        check("  a second later it is still waiting - nobody's clock moves it", driver.state, "addressing")
        client.post("/api/party/hit", json={"player": ann}, environ_base=local)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not (room.round and not room.round.closed and room.round.to == ann):
            time.sleep(0.05)
        check("  Hit, and the question is theirs", (room.round is not None and not room.round.closed, room.round.to), (True, ann))
    finally:
        (party.PERSON_REVEAL, party.BOT_REVEAL, party.GOLF_PRELUDE, party.TEE_PRELUDE, party.BOT_READ_LEAST,
         party.BOT_READ_BASE, party.HOLE_DONE_REVEAL, autoplay.BETWEEN_MIN) = saved
        autoplay.stop()
        if room.round is not None and not room.round.closed:
            room.close_round()            # the next section asks for a tournament, which an open question refuses

    print("\n-- the host says how many companions --")
    room.end_golf()
    room.clear_bots()
    for want in (0, 2, 3):
        r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "back",
                                                 "seconds": 30, "level": "Elmer", "companions": want}, environ_base=local)
        bots = [p for p in room.players.values() if p.bot]
        check(f"asked for {want}: {want} practice player{'s' if want != 1 else ''} sat down", (r.status_code, len(bots)), (200, want))
        autoplay.stop()
        room.round = None
        room.end_golf()
        room.clear_bots()
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "back",
                                             "seconds": 30, "companions": 9}, environ_base=local)
    check("nine is three - the rest of a foursome", len([p for p in room.players.values() if p.bot]), 3)
    autoplay.stop(); room.round = None; room.end_golf(); room.clear_bots()
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "back",
                                             "seconds": 30, "companions": 1, "tee_in": 60}, environ_base=local)
    v = room.clubhouse_view()
    check("one companion with a tee time: the clubhouse says a group of two, one practice player - not one of four",
          (v["group"], v["companions"], len(v["people"])), (2, 1, 1))
    autoplay.stop(); room.round = None; room.end_golf(); room.leave_clubhouse(); room.clear_bots()
    second = room.join("W0ABC")[0].id
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "back",
                                             "seconds": 30, "companions": 3}, environ_base=local)
    check("two people asking for three get two - humans first, four seats", len([p for p in room.players.values() if p.bot]), 2)
    autoplay.stop(); room.round = None; room.end_golf(); room.clear_bots()
    room.leave(second)

    print("\n-- none, chosen after a foursome was booked and the seat emptied --")
    # The sequence from the field: a foursome booked with somebody seated,
    # they leave, Golf pressed again with no companions at the empty table,
    # then somebody scans in and says play now - and departed as four.
    client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "back",
                                         "seconds": 30, "companions": 3, "tee_in": 300}, environ_base=local)
    check("a foursome booked", (room.clubhouse is not None, len([p for p in room.players.values() if p.bot])), (True, 3))
    room.leave(ann)
    r = client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "back",
                                             "seconds": 30, "companions": 0, "tee_in": 300}, environ_base=local)
    check("none chosen at the empty table: the booking and its practice players go", (r.status_code, room.clubhouse, len([p for p in room.players.values() if p.bot])), (200, None, 0))
    r = client.post("/api/party/join", json={"name": "KC9SP"}, environ_base=local)
    ann = r.get_json()["player_id"] if "player_id" in (r.get_json() or {}) else next(p.id for p in room.players.values() if not p.bot)
    check("  the first arrival gets the standing game, alone", (room.clubhouse is not None, len([p for p in room.players.values() if p.bot])), (True, 0))
    r = client.post("/api/party/tee-off", json={}, environ_base=local)
    check("  and plays now, alone", (r.status_code, len(room.players)), (200, 1))
    autoplay.stop(); room.round = None; room.end_golf(); room.clear_bots()

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

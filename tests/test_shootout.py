#!/usr/bin/env python3
"""Shootout: the rules of the game where choosing the question is the move.

    python3 tests/test_shootout.py

The property worth testing hardest is the one the whole design turns on: that
picking a question you cannot answer yourself gains you nothing. Without it
the winning strategy is to find the strangest corner of the pool and wait for
the room to fail, which is a test of who owns the most obscure question rather
than of who knows the most - and the game KC9SP described, "pick the question
you know and your opponent does not", would not be the game that got built.

After that: a subject is spent when it is played, so a strong player works
through their good ones rather than picking the same one until everybody is
out; letters only come from a made shot; a player who is out stops taking them
and stops being handed the pick; and the game ends when one player is left
rather than running a fixed length nobody is still playing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer.shootout import Shootout, is_out, letters  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def right(ms):
    return {"correct": True, "ms": ms}


def wrong(ms=9000):
    return {"correct": False, "ms": ms}


def game(sections=8):
    return Shootout(["ann", "bob", "cat"],
                    sections=[f"T{n}A" for n in range(sections)])


def main():
    print("\n-- the word --")
    check("nothing yet", letters(0), "")
    check("three in", letters(3), "ELM")
    check("spelled", letters(5), "ELMER")
    check("and no further", letters(9), "ELMER")
    check("out at five", [is_out(4), is_out(5)], [False, True])

    print("\n-- a made shot costs the people who missed it --")
    g = game()
    played = g.play("T0A", {"ann": right(1000), "bob": wrong(), "cat": right(2000)})
    check("the picker made it", played["made"], True)
    check("  and only the miss took a letter", played["took"], ["bob"])
    check("  the picker keeps the pick", g.picker, "ann")
    check("  nobody is out on one letter", played["out"], [])

    print("\n-- the shot that was not made costs nobody anything --")
    # This is the design. Ann picks something she cannot answer: Bob and Cat
    # both miss it too, and neither of them pays for it.
    g = game()
    before = dict(g.letters)
    played = g.play("T0A", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("the shot was missed", played["made"], False)
    check("  nobody took a letter", played["took"], [])
    check("  and nothing moved", g.letters, before)

    print("\n-- picking what you cannot answer is worth nothing, repeatedly --")
    # Played out rather than argued: Ann picks eight obscure subjects in a row
    # and answers none of them. If the strategy worked, Bob and Cat would be
    # spelling ELMER by now.
    g = game()
    for n in range(8):
        g.play(f"T{n}A", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("eight bad picks later, nobody has a letter",
          [g.letters["bob"], g.letters["cat"]], [0, 0])
    # Eight subjects, eight bad picks: the subjects are gone, and what that
    # strategy has to show for a whole game is a draw. Not a win.
    check("  the subjects are spent and it is over", g.over(), True)
    check("  and nobody won it", [g.winner(), g.drawn()], [None, True])

    print("\n-- the pick passes on a miss, to the quickest who got it --")
    g = game()
    played = g.play("T0A", {"ann": wrong(), "bob": right(3000), "cat": right(1200)})
    check("it goes to the faster of them", played["next_picker"], "cat")
    check("  and that is who holds it", g.picker, "cat")

    print("\n-- and goes round the table when nobody got it --")
    g = game()
    g.play("T0A", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("the next seat takes it", g.picker, "bob")

    print("\n-- a subject is spent when it is played --")
    g = game()
    g.play("T0A", {"ann": right(100), "bob": wrong(), "cat": wrong()})
    ok, why = g.may_pick("T0A")
    check("it cannot be picked again", ok, False)
    check("  and it says why", why, "that subject has already been played")
    check("  it is off the list", "T0A" in g.available(), False)
    check("  a subject from another pool is refused too",
          g.may_pick("G9Z")[0], False)
    check("  and playing a spent one changes nothing",
          g.play("T0A", {"ann": right(100)}).get("error") is not None, True)

    print("\n-- five letters and you are out --")
    g = game()
    for n in range(5):
        g.play(f"T{n}A", {"ann": right(100), "bob": wrong(), "cat": right(200)})
    check("bob has spelled it", g.letters["bob"], 5)
    check("  and is out", [p["out"] for p in g.standing()], [False, True, False])
    check("  the game is not over - two are still in", g.over(), False)

    # Out means out: no more letters, and never handed the pick.
    played = g.play("T5A", {"ann": right(100), "bob": wrong(), "cat": wrong()})
    check("an eliminated player takes no more letters", g.letters["bob"], 5)
    check("  and only cat was charged", played["took"], ["cat"])

    print("\n-- last one standing --")
    g = game()
    for n in range(5):
        g.play(f"T{n}A", {"ann": right(100), "bob": wrong(), "cat": wrong()})
    check("both of them are out", [g.letters["bob"], g.letters["cat"]], [5, 5])
    check("the game is over", g.over(), True)
    check("  and ann won it", g.winner(), "ann")
    check("  with nobody left picking", g.picker, None)

    print("\n-- the subjects run out --")
    # Played out on the bench first: a round too short for anybody to answer
    # in meant no shot was ever made, no letter ever taken, and after all
    # thirty-five subjects were spent the game went round the table for ever.
    g = Shootout(["ann", "bob", "cat"], sections=["S1", "S2"])
    g.play("S1", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("one subject left: still on", g.over(), False)
    g.play("S2", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("none left: over", g.over(), True)
    check("  nobody ahead, so nobody won", g.winner(), None)
    check("  and it says it is a draw", g.drawn(), True)
    h = Shootout(["ann", "bob"], sections=["S1"])
    h.play("S1", {"ann": right(100), "bob": wrong()})
    check("fewest letters takes it when the subjects run out", h.winner(), "ann")
    check("  which is not a draw", h.drawn(), False)

    print("\n-- the pick has a clock --")
    from elmer import party as P
    room4 = P.Room()
    p1 = room4.join("Ann")[0].id
    p2 = room4.join("Bob")[0].id
    room4.begin_shootout(["S1", "S2"], pick_seconds=0.05)
    check("a person holding the pick is waited on", room4.waiting_for_pick(), True)
    check("  with time on the clock", room4.pick_remaining() is not None, True)
    import time as _t; _t.sleep(0.08)
    check("  until it runs out", room4.pick_overdue(), True)
    passed_to = room4.pass_pick()
    check("then it goes round the table", passed_to, p2)
    check("  for no letter", [room4.shootout.letters[p1], room4.shootout.letters[p2]], [0, 0])
    check("  and the new picker gets a fresh clock",
          room4.pick_remaining() is not None and room4.pick_remaining() > 0.0, True)

    print("\n-- the pick is for the people --")
    # Reported from a real table: the pick never arrived. Two causes, both
    # here. Seated by id, a table that had filled with practice players
    # earlier gave the opening pick to one of them; and a practice player
    # that makes nine shots in ten kept it for ten questions.
    from elmer import party as P2
    r = P2.Room(); r.fill_bots("Elmer")
    ann = r.join("Ann")[0].id
    r.begin_shootout(["T1A", "T1B", "T1C"])
    check("the first pick is a person's, whoever sat down first",
          r.players[r.shootout.picker].name, "Ann")
    check("  and says so", r.shootout.pick_reason, "first")
    bot = next(pid for pid, pl in r.players.items() if pl.bot)
    r.shootout.picker = bot
    out = r.shootout.play("T1A", {bot: right(900), ann: right(1500)})
    check("a practice player's made shot still counts", out["made"], True)
    check("  but it does not keep the pick", out["next_picker"] == bot, False)
    check("  which goes to the quickest person", out["next_picker"], ann)
    check("  and the greeting knows why", r.shootout.pick_reason, "quickest")

    print("\n-- arriving late is being dealt in --")
    r.shootout.letters[ann] = 2
    bob = r.join("Bob")[0].id
    check("the newcomer is in the game", bob in r.shootout.letters, True)
    check("  seated last", r.shootout.order[-1], bob)
    check("  level with the best-placed player still in",
          r.shootout.letters[bob],
          min(r.shootout.letters[p] for p in r.shootout.live() if p != bob))

    print("\n-- why the pick arrived --")
    g = Shootout(["ann", "bob", "cat"], sections=["S1", "S2", "S3", "S4"])
    check("at the start: first", g.pick_reason, "first")
    g.play("S1", {"ann": right(100), "bob": wrong(), "cat": wrong()})
    check("made your shot: kept", g.pick_reason, "kept")
    g.play("S2", {"ann": wrong(), "bob": right(700), "cat": right(400)})
    check("picker missed, cat quickest: quickest", [g.picker, g.pick_reason],
          ["cat", "quickest"])
    g.play("S3", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("nobody got it: round the table", [g.picker, g.pick_reason],
          ["ann", "round"])

    print("\n-- one player is not a game --")
    solo = Shootout(["ann"], sections=["T0A"])
    check("a lone player has not won by default", solo.over(), False)

    print("\n-- at a table: the round is the shot --")
    # The rules module knows nothing about tables; this is the join. A room
    # with two people and a practice player, played through the same round
    # machinery a tournament uses, with the shootout reading each round as a
    # shot the moment it closes.
    from elmer import party
    room = party.Room()
    ann = room.join("Ann")[0].id
    bob = room.join("Bob")[0].id
    bot = room.join("Rig", bot="Listener")[0].id
    started, why = room.begin_shootout(["T1A", "T2B", "T3C"],
                                       {"T1A": "Rules", "T2B": "Operating"})
    check("a shootout starts over the table", why, None)
    check("  and the table says which game it is playing", room.mode, "shootout")
    view = room.shootout_view(ann)
    check("  the first to sit down holds the pick", view["picker"], ann)
    check("  and is told so", view["your_pick"], True)
    first = view["available"][0]
    check("  a subject has its title on it",
          [first["section"], first["title"]], ["T1A", "Rules"])
    check("  and one without a title keeps its code",
          view["available"][2]["title"], "T3C")

    got, why = room.choose(bob, "T1A")
    check("somebody else cannot pick", why, "it is not your pick")
    got, why = room.choose(ann, "G9Z")
    check("nor can the picker pick outside the pool", got, None)
    got, why = room.choose(ann, "T1A")
    check("the picker picks", got, "T1A")
    check("  and it is waiting to be asked", room.take_pick(), "T1A")
    check("  once", room.take_pick(), None)

    room.start_round("tech2026", "T1A01", 0, seconds=30,
                     payload={"text": "?", "choices": ["a", "b"], "section": "T1A"})
    room.submit(ann, 0, 1000)         # right, and she picked it
    room.submit(bob, 1, 2000)         # wrong
    # the bot never answers: not answering is a miss
    summary = room.close_round()
    shot = summary.get("shootout") or {}
    check("the round was scored as a shot", shot.get("made"), True)
    check("  bob and the silent bot took a letter",
          sorted(shot.get("took", [])), sorted([bob, bot]))
    check("  ann keeps the pick", room.shootout.picker, ann)
    view = room.shootout_view(bob)
    check("  the view spells it", [r["word"] for r in view["standing"]],
          ["", "E", "E"])
    check("  and bob is told it is not his pick", view["your_pick"], False)

    print("\n-- a practice player holding the pick picks for itself --")
    room2 = party.Room()
    a = room2.join("Ann")[0].id
    r = room2.join("Rig", bot="Listener")[0].id
    room2.begin_shootout(["T1A", "T2B"])
    room2.shootout.picker = r                 # hand it to the bot
    check("nothing chosen yet", room2.pick, None)
    chosen = room2.choose_for_bot()
    check("the bot chose something on the list", chosen in ("T1A", "T2B"), True)
    check("  and it is waiting to be asked", room2.pick, chosen)
    check("  a person holding it is left alone",
          (setattr(room2.shootout, "picker", a), room2.choose_for_bot())[1], None)

    print("\n-- leaving the table is being out --")
    room3 = party.Room()
    x = room3.join("Xan")[0].id
    y = room3.join("Yves")[0].id
    z = room3.join("Zed")[0].id
    room3.begin_shootout(["T1A"])
    check("xan holds the pick", room3.shootout.picker, x)
    room3.leave(x)
    check("xan is out", room3.shootout.letters[x], 5)
    check("  the pick moved to the next seat", room3.shootout.picker, y)
    check("  and the view says who left",
          [r["name"] for r in room3.shootout_view()["standing"]],
          ["(left)", "Yves", "Zed"])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

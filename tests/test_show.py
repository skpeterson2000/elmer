#!/usr/bin/env python3
"""The host's hand on every screen: announcements, the deck, modes, the programme.

    python3 tests/test_show.py

What a hall's screens show between questions is decided by net control and
carried in the check-in reply every table already polls for. These pin the
rules: an announcement for one seat reaches that seat and no other; an urgent
one stays until cleared; the deck puts a trivia card between every other
kind; the sponsors' cards and the club's notices persist under the state
directory; a programme step makes the hall do the thing.
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import show as S, trivia  # noqa: E402
from elmer import netcontrol  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"   (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("-- announcements, addressed --")
    s = S.Show(random.Random(1))
    lost = s.announce("Lost child at the ARRL booth", S.URGENT, repeat=60, seconds=20, now=1000)
    s.announce("You won the round!", unit="u1", seat="Skippy", now=1000)
    s.announce("Skippy won the round", now=1000)
    check("the winner's phone gets all three",
          [a["text"][:8] for a in s.announcements_for("u1", "Skippy", 1005)],
          ["Lost chi", "You won ", "Skippy w"])
    check("  the seat name is matched without regard to case",
          len(s.announcements_for("u1", "skippy", 1005)), 3)
    check("the winner's table screen gets two - not the seat's line",
          [a["text"][:8] for a in s.announcements_for("u1", None, 1005)], ["Lost chi", "Skippy w"])
    check("another table's phone gets two", len(s.announcements_for("u2", "Bob", 1005)), 2)
    check("urgent sorts first", s.announcements_for("u2", None, 1005)[0]["weight"], "urgent")
    check("a notice is gone after 20 s", [a["text"][:8] for a in s.announcements_for("u2", None, 1025)], [])
    check("  the repeating urgent one is back at 60 s",
          [a["text"][:8] for a in s.announcements_for("u2", None, 1065)], ["Lost chi"])
    check("  and gone again at 85", s.announcements_for("u2", None, 1085), [])
    stay = s.announce("Eyes up front", S.URGENT, now=2000)
    check("an urgent one without a clock stays", bool(s.announcements_for(None, None, 9000)), True)
    check("  until cleared", (s.clear(stay["id"]), s.announcements_for(None, None, 9000)), (True, []))
    check("the pending list is what the host sees", [a["id"] for a in s.pending(2100)], [lost["id"]])
    try:
        s.announce("   ")
        check("nothing to say is refused", False, True)
    except ValueError:
        check("nothing to say is refused", True, True)
    s.hold_attention("One moment", now=3000)
    check("attention is held", s.for_unit("u1", now=3001)["attention"]["text"], "One moment")
    s.hold_attention(None)
    check("  and released", s.for_unit("u1", now=3002)["attention"], None)
    s.clear_all()

    print("\n-- the deck --")
    s = S.Show(random.Random(3))
    kinds = []
    for t in range(0, 12 * 10, 12):
        c = s.card(5000 + t, standings=[{"name": "Poldhu", "score": 3}], join=True)
        kinds.append(c["kind"])
    check("a trivia card sits between every other kind",
          all(kinds[i] == "trivia" or kinds[i + 1] == "trivia" for i in range(len(kinds) - 1)), True)
    check("  standings and the join code both come round", {"standings", "join"} <= set(kinds), True)
    check("  no sponsor card with no sponsors", "sponsor" in kinds, False)
    c1 = s.card(6000); c2 = s.card(6005)
    check("the card holds for its dwell", c1["id"], c2["id"])
    c3 = s.card(6000 + s.dwell + 1)
    check("  and turns over after it", c3["id"] != c1["id"], True)
    decks_seen = set()
    for t in range(0, 12 * 40, 12):
        c = s.card(7000 + t)
        if c["kind"] == "trivia":
            decks_seen.add(c["deck"])
    check("every trivia deck gets a turn", decks_seen, set(trivia.DECKS))
    s.set_deck({"history": False, "quotes": False, "hams": False, "technique": False, "equipment": False,
                "standings": False, "join": False, "programme": False})
    check("with everything off there is no card", s.card(8000, standings=[{"name": "x", "score": 1}]), None)
    s.set_deck({"history": True}, dwell=3)
    check("the dwell has a floor", s.dwell, S.MIN_DWELL)
    s.set_deck(dwell=90)
    check("  and a ceiling", s.dwell, S.MAX_DWELL)

    print("\n-- sponsors and notices persist --")
    s = S.Show(random.Random(4))
    sp = s.add_sponsor("Ham Radio Outlet", "the candy store", "hro.com", None, 2)
    s.add_notice("Club meets", "Second Tuesdays, 7 pm", "")
    again = S.Show.load()
    check("a sponsor survives a reload", [x["name"] for x in again.sponsors], ["Ham Radio Outlet"])
    check("  so does the notice", [x["title"] for x in again.notices], ["Club meets"])
    check("  and their ids stay unique", again._next_id > sp["id"], True)
    kinds = [again.card(9000 + t)["kind"] for t in range(0, 12 * 8, 12)]
    check("the sponsor's card and the notice both play", {"sponsor", "notice"} <= set(kinds), True)
    check("a weight of 2 does not repeat back to back",
          all(not (kinds[i] == "sponsor" and kinds[i + 1] == "sponsor") for i in range(len(kinds) - 1)), True)
    check("removing the sponsor takes it out", (again.remove_sponsor(sp["id"]), again.sponsors), (True, []))
    check("  and the reload agrees", S.Show.load().sponsors, [])
    try:
        s.add_sponsor("")
        check("a sponsor needs a name", False, True)
    except ValueError:
        check("a sponsor needs a name", True, True)
    check("an image name is made safe", S.asset_name("Logo (final).PNG"), "Logo-final-.png".replace("-.", "."))
    check("  and a non-image is refused", S.asset_name("../evil.exe"), None)

    print("\n-- mode, focus, programme --")
    s = S.Show(random.Random(5))
    s.set_focus("T5", "Electrical principles", "Ten minutes on T5", 10, now=10_000)
    check("setting a focus puts the hall in study", s.mode, S.STUDY)
    f = s.for_unit("u1", now=10_060)["focus"]
    check("  and the units get it with the time left", (f["section"], f["remaining"]), ("T5", 540))
    check("  the focus card leads the deck", s.card(10_000)["kind"], "focus")
    s.set_mode(S.PLAY)
    check("back to play clears the focus", s.focus, None)
    try:
        s.set_mode("karaoke")
        check("an unknown mode is refused", False, True)
    except ValueError:
        check("an unknown mode is refused", True, True)
    steps = s.set_programme([{"kind": "intermission", "minutes": 5},
                             {"kind": "rounds", "rounds": 12, "difficulty": "technician"},
                             {"kind": "nonsense"}, {"kind": "thanks"}])
    check("unknown steps are dropped", [x["kind"] for x in steps], ["intermission", "rounds", "thanks"])
    check("the first press is the first step", s.advance(11_000)["kind"], "intermission")
    check("  the view says where we are", (s.programme_view(11_005)["step"], s.programme_view()["next"]),
          (1, "Tournament rounds"))
    s.advance(); s.advance()
    check("past the end is None", s.advance(), None)

    print("\n-- the net carries the show --")
    net = netcontrol.Net("Test net")
    net.show = S.Show(random.Random(6))
    unit, _ = net.check_in("u1", "Table one", 3)
    net.show.announce("Skippy won the round", unit="u1", seat="Skippy")
    got = net.show_for("u1")
    check("the check-in reply carries the hall's mode and a card", (got["mode"], got["card"] is not None), ("play", True))
    check("  seat lines travel to the unit, marked, for it to hand out",
          [(a["seat"], a["mine"]) for a in got["announcements"]], [("Skippy", True)])
    check("  but not to the board, which has no seats", net.board()["show"]["announcements"], [])
    check("  the board gets the show too", "show" in net.board(), True)
    check("a unit reports what it is showing", ("showing" in unit.as_dict()), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

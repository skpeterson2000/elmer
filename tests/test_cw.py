#!/usr/bin/env python3
"""Checks for the Morse tables and the encoder behind the CW page.

    python3 tests/test_cw.py

What matters here is not the timing arithmetic - PARIS is arithmetic and it
either is or is not - but the things that are audibly wrong if they slip: a
prosign sent as two letters, a character that encodes to somebody else's code,
a chart that quietly omits half the alphabet.

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


def codes(text):
    """Flat list of (character, code) for everything encode() produces."""
    return [(s["char"], s["code"]) for word in cw.encode(text) for s in word]


def main():
    print("\n-- the code is a code --")
    # Two characters sharing one code would make the decoder a coin toss.
    check("no two characters share a code",
          len(set(cw.MORSE.values())), len(cw.MORSE))
    check("every code is dits and dahs and nothing else",
          {c for code in cw.MORSE.values() for c in code}, {".", "-"})
    check("the Koch order is the alphabet and then some, with no repeats",
          len(cw.KOCH_ORDER), len(set(cw.KOCH_ORDER)))
    check("  and every character in it can actually be sent",
          [c for c in cw.KOCH_ORDER if c not in cw.MORSE], [])

    print("\n-- a prosign is one sound, not two letters --")
    # This is the whole point of the brackets. AR sent as A R has a three-dit
    # gap in the middle of it and is a different thing to hear.
    check("<AR> is one symbol", codes("<AR>"), [("AR", ".-.-.")])
    check("  and it is not the letters A R",
          codes("AR"), [("A", ".-"), ("R", ".-.")])
    # The elements are the same either way - ".-" + ".-." is ".-.-." - and the
    # difference is entirely the gap: one symbol runs them together, two
    # symbols put three dits between them. That is why sending a prosign as its
    # letters is such an easy mistake to make and such an obvious one to hear.
    check("  the elements are identical, which is the trap",
          cw.PROSIGNS["AR"][0], cw.MORSE["A"] + cw.MORSE["R"])
    check("  so what separates them is the count of symbols, not the code",
          (len(codes("<AR>")), len(codes("AR"))), (1, 2))
    check("a prosign is found with punctuation after it",
          codes("<AR>;"), [("AR", ".-.-.")])
    check("  and in the middle of a line",
          codes("HW? <BT> OK")[3], ("BT", "-...-"))
    check("brackets that are not a prosign are just letters",
          codes("<XY>"), [("X", "-..-"), ("Y", "-.--")])
    check("a bare word is never guessed at as a prosign",
          codes("AS"), [("A", ".-"), ("S", "...")])

    print("\n-- what is sent, and what you write down --")
    check("the angle brackets are not something you can hear",
          cw.plain("W1AW DE K1ABC <BT> HW? <AR>"),
          "W1AW DE K1ABC BT HW? AR")
    check("  and plain text passes through unharmed",
          cw.plain("cq cq de w1aw k"), "CQ CQ DE W1AW K")

    print("\n-- generated material means what it says --")
    # Prosign practice used to send A then R and call it AR, which taught the
    # wrong sound to anybody who believed it.
    prosigns = cw.practice("prosigns", 4, seed=7)[0]
    sent = codes(prosigns)
    check("prosign practice sends prosigns, not their letters",
          all(char in cw.PROSIGNS for char, _ in sent), True)
    check("  one symbol each", len(sent), len(prosigns.split()))
    for template in cw.QSO_TEMPLATES:
        filled = template.format(me="K1ABC", you="W1AW", rst="599", name="JIM",
                                 qth="MN", wx="SUNNY", watts=100)
        for name in ("AR", "SK", "BT"):
            if f"<{name}>" in template:
                check(f"a QSO's {name} is the prosign",
                      (name, cw.PROSIGNS[name][0]) in codes(filled), True)

    print("\n-- the chart shows the whole code --")
    sections = cw.chart()
    shown = {item["char"] for s in sections for item in s["items"]}
    check("every letter and digit is on it",
          [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" if c not in shown],
          [])
    check("every prosign is on it",
          [p for p in cw.PROSIGNS if p not in shown], [])
    check("and every cell has a code to draw",
          [i["char"] for s in sections for i in s["items"] if not i["code"]], [])
    check("the prosigns get the room their meanings need",
          [s["title"] for s in sections if s.get("wide")], ["Prosigns"])

    print("\n-- timing --")
    at20 = cw.timing(20)
    check("a dit is 1200/wpm milliseconds", at20["dit"], 60.0)
    check("  and a dah is three of them", at20["dah"], 180.0)
    check("full speed is not Farnsworth", at20["farnsworth"], False)
    slow = cw.timing(20, 10)
    check("Farnsworth stretches the gaps", slow["char_gap"] > at20["char_gap"], True)
    check("  and never the characters", slow["dit"], at20["dit"])
    check("  and asking for faster spacing than the characters does nothing",
          cw.timing(20, 30)["farnsworth"], False)

    print("\n-- the Q signals, as three letters and not as one --")
    chart = {section["title"]: section for section in cw.chart()}
    check("they are on the chart", "Q signals" in chart, True)
    q = chart["Q signals"]
    check("all of them", len(q["items"]), len(cw.Q_SIGNALS))
    check("  laid out with the code under the name", q.get("stacked"), True)
    qcode = {item["char"]: item["code"] for item in q["items"]}
    check("QRM is Q, R and M with the gaps between them",
          qcode["QRM"], "--.- .-. --")
    check("  which is not what a prosign looks like",
          " " in cw.PROSIGNS["AR"][0], False)
    # The distinction the whole section is about: run together, --.- .-. --
    # would be a single symbol and a different sound entirely.
    check("a Q signal has two gaps in it, one between each pair",
          qcode["QTH"].count(" "), 2)
    check("every one of them carries its meaning",
          all(item["meaning"] for item in q["items"]), True)
    check("  and it is the one the module already had",
          q["items"][0]["meaning"],
          cw.Q_SIGNALS[q["items"][0]["char"]])
    check("the section says how to ask one rather than state it",
          "QRL?" in q["note"], True)

    print("\n-- the plan: the record decides the lesson --")
    p = cw.plan({})
    check("nobody's record is lesson two, K and M new", (p["lesson"], p["chars"], p["new"]), (2, ["K", "M"], ["K", "M"]))
    solid = {c: {"sent": 30, "copied": 29, "confused": "{}"} for c in "KMRSUAPT"}
    p = cw.plan(solid)
    check("eight solid in order is lesson nine, L new", (p["lesson"], p["new"], p["solid"]), (9, ["L"], 8))
    check("  a character is solid at nine in ten over twenty sends, not before",
          (cw.is_solid({"sent": 19, "copied": 19}), cw.is_solid({"sent": 20, "copied": 18}), cw.is_solid({"sent": 20, "copied": 17})), (False, True, False))
    # Judged over the recent past where there is one. A rough first day on
    # a character used to drag its lifetime ratio long after the sound was
    # known; the window forgives it. And the window catches slipping that
    # the lifetime ratio would hide.
    check("  ten misses then thirty hits is solid by the window, though lifetime says 75%",
          (cw.is_solid({"sent": 40, "copied": 30, "recent": "0" * 10 + "1" * 30}),
           cw.is_solid({"sent": 40, "copied": 30})), (True, False))
    check("  thirty hits then ten misses is not, though lifetime says 90%",
          cw.is_solid({"sent": 40, "copied": 36, "recent": "1" * 30 + "0" * 10}), False)
    check("  and a window shorter than twenty does not count yet",
          cw.is_solid({"sent": 19, "copied": 19, "recent": "1" * 19}), False)
    # The deal is by how much work a character still needs: the newest
    # most, each shaky one more the shakier it is, the known ones least
    # and never none. It used to boost only the single worst, so a second
    # shaky character came round no more often than the ones known cold.
    check("two fresh characters are dealt evenly", cw.plan({})["draw"], {"K": 0.5, "M": 0.5})
    d = cw.plan(dict(solid, L={"sent": 3, "copied": 2, "recent": "110"}))["draw"]
    known = [v for c, v in d.items() if c != "L"]
    check("  the newest comes round most - four times a known one",
          round(d["L"] / known[0], 1), 4.0)
    check("  and the known ones share evenly, never none",
          (len(set(known)), min(known) > 0, round(sum(d.values()), 3)), (1, True, 1.0))
    two_weak = dict(solid, R={"sent": 30, "copied": 18, "recent": "1" * 12 + "0" * 18},   # 40%
                    A={"sent": 30, "copied": 24, "recent": "1" * 24 + "0" * 6})           # 80%
    p = cw.plan(two_weak)
    d = p["draw"]
    check("  two shaky characters are both in the lesson - nothing is taken away",
          ("R" in p["chars"], "A" in p["chars"], len(p["chars"])), (True, True, 8))
    check("  and both come round more than a known one, the shakier the more",
          (d["R"] > d["A"] > d["K"], round(d["R"] / d["K"], 1), round(d["A"] / d["K"], 1)),
          (True, 3.4, 1.8))
    slipped = dict(solid, M={"sent": 40, "copied": 30, "recent": "1" * 20 + "0" * 10})   # M, second in, slips
    p = cw.plan(slipped)
    check("  a character slipping does not shrink the lesson behind it",
          (len(p["chars"]), p["chars"][-1], p["earned"]), (8, "T", 8))
    shaky = dict(solid, L={"sent": 12, "copied": 8, "confused": '{"R": 3, "M": 1}'})
    p = cw.plan(shaky)
    check("a shaky character is named, worst first, with what it was heard as", (p["weak"][0]["ch"], p["weak"][0]["heard_as"]), ("L", ["R", "M"]))
    check("  and the lesson waits on it", (p["lesson"], p["new"]), (9, ["L"]))
    p = cw.plan(shaky, setting=14)
    check("a slider pushed ahead is honoured, and said to be ahead", (p["lesson"], p["ahead"], p["earned"]), (14, True, 9))
    gap = dict(solid); del gap["R"]
    check("a gap in the order holds the lesson at the gap", cw.plan(gap)["lesson"], 3)
    done = {c: {"sent": 30, "copied": 30, "confused": "{}"} for c in cw.KOCH_ORDER}
    check("every character solid is done", (cw.plan(done)["done"], cw.plan(done)["lesson"]), (True, len(cw.KOCH_ORDER)))

    print("\n-- the session, and the drill --")
    steps = [s_["kind"] for s_ in cw.session(cw.plan(shaky))]
    check("meet the new one, one at a time, groups, then words once there are words", steps, ["meet", "flash", "koch", "words"])
    check("  no words at lesson two", [s_["kind"] for s_ in cw.session(cw.plan({}))], ["meet", "flash", "koch"])
    check("  and when every character is solid, words and a contact", [s_["kind"] for s_ in cw.session(cw.plan(done))], ["words", "qso"])
    seq = cw.flash_sequence(cw.plan(shaky), 300, seed=5)
    check("the drill draws only the lesson's characters", set(seq) <= set(cw.plan(shaky)["chars"]), True)
    check("  never three of one running", any(seq[i] == seq[i + 1] == seq[i + 2] for i in range(len(seq) - 2)), False)
    check("  and the shaky one comes round more often than a solid one", seq.count("L") > seq.count("K"), True)
    check("words are spelt only from the lesson's characters",
          all(set(w) <= set("KMRSUAPTL") for w in cw.words_for(list("KMRSUAPTL"), 20, seed=1)), True)
    check("  from K and M alone, only the one-letter word K - over", cw.words_for(["K", "M"], 6), ["K"])
    kept = cw.WORDS
    cw.WORDS = ["THE", "AND"]
    check("  and the words kind falls back to groups when there are none", len(cw.practice("words", 5, 2, seed=1)[0].split()), 5)
    cw.WORDS = kept

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    print("\n-- the record counts resends, and an older database learns the column --")
    import sqlite3
    import tempfile
    from elmer import db
    old = Path(tempfile.mkdtemp(prefix="elmer-v6-")) / "old.db"
    raw = sqlite3.connect(old)
    raw.executescript("""
        CREATE TABLE profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '', callsign TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
            streak_days INTEGER NOT NULL DEFAULT 0, best_streak INTEGER NOT NULL DEFAULT 0,
            last_study_day TEXT, last_seen TEXT, settings TEXT NOT NULL DEFAULT '{}',
            pw_salt TEXT NOT NULL DEFAULT '', pw_hash TEXT NOT NULL DEFAULT '',
            seal_salt TEXT NOT NULL DEFAULT '', seal_wrap TEXT NOT NULL DEFAULT '',
            seal_recovery_salt TEXT NOT NULL DEFAULT '', seal_recovery TEXT NOT NULL DEFAULT '');
        INSERT INTO profile (id, name, created) VALUES (1, 'Old Timer', '2026-01-01');
        CREATE TABLE cw_char (user_id INTEGER NOT NULL DEFAULT 1, ch TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0, copied INTEGER NOT NULL DEFAULT 0,
            confused TEXT NOT NULL DEFAULT '{}', updated TEXT, PRIMARY KEY (user_id, ch));
        INSERT INTO cw_char (user_id, ch, sent, copied) VALUES (1, 'K', 10, 9);
        PRAGMA user_version = 6;""")
    raw.commit()
    raw.close()
    db.DB_PATH = old
    conn = db.connect()
    check("a version-6 database comes up to date", conn.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)
    before = db.cw_progress(conn)["K"]
    check("  the old record kept, with no resends yet", (before["sent"], before["copied"], before["repeats"]), (10, 9, 0))
    db.cw_record(conn, {"K": {"sent": 2, "copied": 2, "confused": {}, "repeats": 3},
                        "M": {"sent": 1, "copied": 0, "confused": {"O": 1}}})
    after = db.cw_progress(conn)
    check("a session's resends are folded in", (after["K"]["sent"], after["K"]["copied"], after["K"]["repeats"]), (12, 11, 3))
    check("  a character with none said is none", after["M"]["repeats"], 0)
    db.cw_record(conn, {"K": {"sent": 1, "copied": 1, "repeats": 1}})
    check("  and they add up", db.cw_progress(conn)["K"]["repeats"], 4)

    print("\n-- the code's badges --")
    from elmer import game
    names = lambda fresh: [a["name"] for a in fresh]
    conn2 = db.connect()
    check("nothing yet, nothing earned", game.check_cw_achievements(conn2, {}), [])
    solid = lambda n: {c: {"sent": 20, "copied": 19, "confused": "{}"} for c in cw.KOCH_ORDER[:n]}
    check("the first character copied is First Dit", names(game.check_cw_achievements(conn2, {"K": {"sent": 1, "copied": 0}})), ["First Dit"])
    check("  five solid is Five Solid", names(game.check_cw_achievements(conn2, solid(5))), ["Five Solid"])
    check("  twenty is Half the Code", names(game.check_cw_achievements(conn2, solid(20))), ["Half the Code"])
    check("  all forty is The Whole Code", names(game.check_cw_achievements(conn2, solid(40))), ["The Whole Code"])
    check("  and none of them twice", game.check_cw_achievements(conn2, solid(40)), [])
    check("a block at 90% after a resend is not First Time Through", game.check_cw_achievements(conn2, {}, session_pct=95, resends=2), [])
    check("  with no resend it is", names(game.check_cw_achievements(conn2, {}, session_pct=90, resends=0)), ["First Time Through"])
    check("six days running is not yet Daily Code", game.check_cw_achievements(conn2, {}, streak=6), [])
    check("  seven is", names(game.check_cw_achievements(conn2, {}, streak=7)), ["Daily Code"])
    check("the rating: copying at 12 wpm is Ten Words", names(game.check_cw_achievements(conn2, {}, rating={"copy_wpm": 12})), ["Ten Words"])
    check("  at 20, Twenty Words too", names(game.check_cw_achievements(conn2, {}, rating={"copy_wpm": 20, "send_accuracy": 88})), ["Twenty Words"])
    check("  sending at 90% is Clean Fist", names(game.check_cw_achievements(conn2, {}, rating={"send_accuracy": 90})), ["Clean Fist"])
    check("the ballgame: a hit in the little league is Base Hit", names(game.check_ballgame_achievements(conn2, hit=True)), ["Base Hit"])
    check("  one in the majors is Big League as well", names(game.check_ballgame_achievements(conn2, hit=True, majors=True)), ["Big League"])
    check("  a resend asked for in code and answered is QSM?", names(game.check_ballgame_achievements(conn2, keyed_ask=True)), ["QSM?"])
    check("all twelve are on the list", sum(1 for c, _, _ in game.ACHIEVEMENTS if c.startswith("cw_")), 12)
    check("  and every one earned here is held", len([c for c in game.earned(conn2) if c.startswith("cw_")]), 12)

    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

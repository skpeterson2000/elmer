#!/usr/bin/env python3
"""A supporter's key, the thanks it earns, and the coffee card for everyone else.

    python3 tests/test_supporter.py

The key is cut from the callsign and checks itself; the meter counts hours
actually spent answering; the dashboard card is the thanks for a supporter
and, for everyone else, one light offer at ten hours and not again for a
hundred; the hall's card becomes the honorary one on a supporter's table
and the roll of thanks lists the room. See elmer/supporter.py.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, supporter, show, netcontrol  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


CHANGELOG = """# Changelog

## 2026-09-20

- The newest thing: and why it matters
- Another. With a second sentence

## 2026-09-10

- Older, from before the coffee

## 2026-09-01

- Oldest of all
"""


def main():
    print("\n-- the key is the callsign and six letters cut from it --")
    key = supporter.make_key("kc9sp")
    check("cut from a lower-case call", key[:12], "ELMER-KC9SP-")
    check("  six letters, none of them 0, O, 1 or I", len(key), 18)
    check("  no ambiguous letters", any(c in key[12:] for c in "01OI"), False)
    check("  the same call always cuts the same key", supporter.make_key("KC9SP"), key)
    check("  a portable suffix is stripped, not encoded", supporter.make_key("kc9sp/m"), key)
    check("  not a callsign, no key", supporter.make_key("ab"), None)
    check("it checks", supporter.check_key(key), ("KC9SP", None))
    check("  typed with spaces and in lower case", supporter.check_key(" " + key.lower() + " "), ("KC9SP", None))
    bad = key[:-1] + ("A" if key[-1] != "A" else "B")
    check("  one letter wrong is refused, naming the call",
          supporter.check_key(bad)[1].startswith("that is not the key for KC9SP"), True)
    check("  not a key at all", supporter.check_key("coffee")[1], "a key looks like ELMER-CALLSIGN-XXXXXX")
    check("  nothing", supporter.check_key("")[1], "no key")

    print("\n-- into the settings, beside the rest --")
    settings = {"callsign": "KC9SP"}
    check("a bad key is a reason, and changes nothing",
          (supporter.apply(settings, "ELMER-KC9SP-AAAAAA") or "").startswith("that is not"), True)
    check("  the dict untouched", "supporter" in settings, False)
    check("a good key goes in", supporter.apply(settings, key), None)
    rec = settings["supporter"]
    check("  the callsign with it", rec["callsign"], "KC9SP")
    check("  not named until asked", rec["named"], False)
    check("  dated today", len(rec["since"]), 10)
    settings["supporter"]["since"] = "2026-09-05"
    supporter.apply(settings, key, named=True)
    check("  the same key again keeps its first date", settings["supporter"]["since"], "2026-09-05")
    check("  and can choose to be named", settings["supporter"]["named"], True)
    supporter.apply(settings, named=False)
    check("  or not, without retyping the key", settings["supporter"]["named"], False)
    supporter.apply(settings, "")
    check("an empty key clears it", "supporter" in settings, False)
    check("  and the rest is still there", settings["callsign"], "KC9SP")

    print("\n-- on an account --")
    tmp = Path(tempfile.mkdtemp(prefix="elmer-test-")) / "test.db"
    db.DB_PATH = tmp
    conn = db.connect()
    check("nobody's a supporter to begin with", supporter.record(conn), None)
    check("  so no name for the hall", supporter.named_callsign(conn), "")
    rec, why = supporter.set_key(conn, key, named=True)
    check("a key goes in", (rec or {}).get("callsign"), "KC9SP")
    check("  and comes back from the database", supporter.record(conn)["callsign"], "KC9SP")
    check("  named for the hall", supporter.named_callsign(conn), "KC9SP")
    supporter.set_key(conn, key, named=False)
    check("  unless they would rather not", supporter.named_callsign(conn), "")
    check("a wrong key is refused", supporter.set_key(conn, bad)[1] is not None, True)
    check("  and the record stands", supporter.record(conn)["callsign"], "KC9SP")
    supporter.set_key(conn, "")
    check("cleared", supporter.record(conn), None)

    print("\n-- the meter counts answering, each answer capped --")
    check("nothing yet", supporter.active_hours(conn), 0.0)
    for i in range(3):
        db.log_answer(conn, "technician", f"T1A0{i}", "T1A", 1, 0, 20 * 60 * 1000, "study")
    check("three twenty-minute answers count five minutes each",
          round(supporter.active_hours(conn), 2), 0.25)

    print("\n-- the coffee card: once at ten hours, then not for a hundred --")
    check("not at a quarter of an hour", supporter.card(conn, supporters=[])["kind"], "none")
    for i in range(118):                       # 121 answers at the cap = 10.08 h
        db.log_answer(conn, "technician", f"T1B{i:03d}", "T1B", 1, 0, 300000, "study")
    card = supporter.card(conn, supporters=[])
    check("at ten hours, the offer", card["kind"], "coffee")
    check("  the hours on it", card["hours"], 10)
    check("  the title says so", card["title"], "ELMER has your 10 hours.")
    check("  the observation, not a bill", "competing for their evenings" in card["line"], True)
    check("  and that it stays free", card["foot"], "It stays free for everyone, coffee or no coffee.")
    check("  where the coffee goes", card["url"], "https://github.com/sponsors/skpeterson2000")
    supporter.shown(conn, "coffee")
    check("put away, it stays away", supporter.card(conn, supporters=[])["kind"], "none")
    for i in range(1200):                      # a hundred hours more
        db.log_answer(conn, "general", f"G1A{i:04d}", "G1A", 1, 0, 300000, "study")
    check("  until a hundred hours later", supporter.card(conn, supporters=[])["kind"], "coffee")

    print("\n-- the thanks card: a supporter is thanked, and told what it meant --")
    supporter.set_key(conn, key, named=True)
    conn.execute("UPDATE profile SET settings = json_set(settings, '$.supporter.since', '2026-09-15')")
    conn.commit()
    others = [{"who": "KC9SP", "note": ""}, {"who": "W1AW", "note": ""}, {"who": "VE3ABC", "note": ""}]
    card = supporter.card(conn, supporters=others, changelog=CHANGELOG)
    check("a supporter is thanked, not asked", card["kind"], "thanks")
    check("  by callsign", card["title"], "Thank you, KC9SP, for your generous support of this project.")
    check("  what the coffee meant, off the changelog", card["changes"], 2)
    check("  said in a sentence", card["line"], "Since your coffee in September 2026, ELMER has changed 2 times.")
    check("  the latest lines, first sentence only",
          card["lines"], ["The newest thing", "Another"])
    check("  and the company they are in", card["others_line"], "You and 2 others are on the list.")
    supporter.shown(conn, "thanks")
    check("once a day", supporter.card(conn, supporters=others, changelog=CHANGELOG)["kind"], "none")
    check("the changelog since a day before anything", supporter.changes_since("2026-01-01", CHANGELOG)["count"], 4)
    check("  since after everything", supporter.changes_since("2027-01-01", CHANGELOG)["count"], 0)

    print("\n-- names in a sentence --")
    check("one", supporter.words(["KC9SP"]), "KC9SP")
    check("two", supporter.words(["KC9SP", "W1AW"]), "KC9SP and W1AW")
    check("many", supporter.words([f"N{i}XX" for i in range(9)]),
          "N0XX, N1XX, N2XX, N3XX, N4XX and N5XX and 3 more")
    check("none", supporter.words([]), "")
    check("the honorary line names the game",
          supporter.honour_line("KC9SP", "shootout"),
          "This shootout is brought to you by the generous contribution of KC9SP.")
    check("  a round of golf", supporter.honour_line("KC9SP", "golf"),
          "This round of golf is brought to you by the generous contribution of KC9SP.")
    check("  and something with no game running", supporter.honour_line("KC9SP", None),
          "This session is brought to you by the generous contribution of KC9SP.")

    print("\n-- the hall: net control gathers the room's supporters --")
    net = netcontrol.Net(name="test")
    net.host_supporter = "KC9SP"
    a, _ = net.check_in("unit-a", "Table A", 2, instance="a")
    b, _ = net.check_in("unit-b", "Table B", 2, instance="b")
    a.supporter = "W1AW"
    b.supporter = "KC9SP"                       # the host, again, at a table
    check("the host first, each name once", net.supporters(), ["KC9SP", "W1AW"])
    check("  in the check-in's dict", a.as_dict()["supporter"], "W1AW")
    view = net.show_for("unit-a")
    check("the show goes to the table", "card" in view, True)
    check("  and the show knows the room", net.show.supporters, ["KC9SP", "W1AW"])

    print("\n-- the show: the honorary card and the roll of thanks --")
    s = show.Show()
    s.set_deck({k: False for k in show.TRIVIA_DECKS}, house=1.0)
    s.supporters = ["KC9SP", "W1AW"]
    kinds, honours = [], []
    now = 1000.0
    for _ in range(12):
        view = s.for_unit("unit-a", standings=[], join=True, now=now, supporter="W1AW", game="shootout")
        kinds.append(view["card"]["kind"])
        if view["card"].get("honour"):
            honours.append(view["card"]["text"])
        now += s.dwell + 1
    check("the thanks card is in the rotation", "thanks" in kinds, True)
    check("  and the house card is the supporter's on their table",
          honours[:1], ["This shootout is brought to you by the generous contribution of W1AW."])
    view = s.for_unit(None, standings=[], join=True, now=now)
    plain = [s.for_unit(None, standings=[], join=True, now=now + i * (s.dwell + 1))["card"]
             for i in range(12)]
    check("  a screen with no supporter sees ELMER's own card",
          any(c["kind"] == "house" and not c.get("honour") for c in plain), True)
    roll = next(c for c in plain if c["kind"] == "thanks")
    check("  the roll names the room", roll["supporters"], ["KC9SP", "W1AW"])
    s.supporters = []
    s.set_deck({})
    kinds = [s.for_unit(None, standings=[], join=True, now=now + i * (s.dwell + 1))["card"]["kind"]
             for i in range(12)]
    check("nobody to thank, no card", "thanks" in kinds, False)

    print("\n-- a certificate carries the line --")
    from elmer import certpdf
    pdf = certpdf.build([{"place": 1, "name": "Dana", "lines": ["won"]}],
                        event="Test", thanks="With thanks to KC9SP and W1AW.")
    check("a PDF comes back", pdf[:4], b"%PDF")

    print()
    if FAILS:
        print("FAILURES:", FAILS)
        sys.exit(1)
    print("all ok")


if __name__ == "__main__":
    main()

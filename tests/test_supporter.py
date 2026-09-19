#!/usr/bin/env python3
"""A supporter's key, the thanks it earns, and the coffee card for everyone else.

    python3 tests/test_supporter.py

The key is eight characters bound to the name to be printed, checks
itself for typos, and is real only on the signed roster; the meter counts
hours actually spent answering; the dashboard card is the thanks for a
supporter and, for everyone else, one light offer at ten hours and not
again for a hundred; the hall's card becomes the honorary one on a
supporter's table and the roll of thanks lists the room. See
elmer/supporter.py and elmer/roster.py.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, ed25519, roster, supporter, show, netcontrol  # noqa: E402

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
    # A test issuer: its own key pair, its own roster file, no network.
    tmp = Path(tempfile.mkdtemp(prefix="elmer-test-"))
    seed, pk = ed25519.keypair()
    seed_file = tmp / "issuer.key"
    seed_file.write_text(seed.hex())
    roster.PUBLIC_KEY_HEX = pk.hex()
    roster.FILE = tmp / "supporters.roster"
    roster.CACHE = tmp / "state" / "supporters.roster"
    roster.URL = ""

    print("\n-- the key: eight characters, bound to the name to be printed --")
    key = supporter.make_key("KC9SP")
    check("eight characters with a dash in the middle", (len(key), key[4]), (9, "-"))
    check("  none of them 0, O, 1 or I", any(c in key for c in "01OI"), False)
    check("  the tier letter leads", key[0], "S")
    check("  the same name cuts a different key each time", supporter.make_key("KC9SP") == key, False)
    dana = supporter.make_key("John Doe")
    check("a name with a space cuts a key too", len(dana), 9)
    check("  and so does a club", len(supporter.make_key("Cedar Valley ARC")), 9)
    check("  one letter is not a name", supporter.make_key("K"), None)
    check("it reads right for its name", supporter.check_key(key, "KC9SP"), ("KC9SP", None))
    check("  the name comes back as given, for printing",
          supporter.check_key(dana, " John Doe "), ("John Doe", None))
    check("  typed without the dash, in lower case, with spaces",
          supporter.check_key(" " + key.replace("-", "").lower() + " ", "kc9sp"), ("kc9sp", None))
    check("  under another name it is not that person's key",
          supporter.check_key(key, "W1AW")[1].startswith("that is not the key for W1AW"), True)
    bad = key[:-1] + ("A" if key[-1] != "A" else "B")
    check("  one character wrong is caught on the unit",
          supporter.check_key(bad, "KC9SP")[1].startswith("that is not the key"), True)
    check("  the wrong length", supporter.check_key("ABCD-EFG", "KC9SP")[1],
          "a key is eight letters and digits, shown as XXXX-XXXX")
    check("  a letter the alphabet does not have", supporter.check_key("ABC0-EFGH", "KC9SP")[1],
          "a key is eight letters and digits, shown as XXXX-XXXX")
    check("  no name", supporter.check_key(key, "")[1],
          "the key needs the name it was cut for - the one given in the note")
    check("  nothing", supporter.check_key("", "KC9SP")[1], "no key")

    print("\n-- the roster: a key is real only on the signed list --")
    check("no roster, no key is real", roster.contains(key, "KC9SP"), False)
    check("  and the whole check says so", supporter.verify(key, "KC9SP")[1], supporter.NOT_ON_ROSTER)
    check("  with no network to fetch from", roster.fetch_current()[1], "no roster to fetch from")
    issued_key, count = supporter.issue("KC9SP", seed_path=seed_file)
    check("the developer issues one", count, 1)
    check("  it is on the roster", roster.contains(issued_key, "KC9SP"), True)
    check("  and passes the whole check", supporter.verify(issued_key, "KC9SP"), ("KC9SP", None))
    check("  the key that was only cut is not", roster.contains(key, "KC9SP"), False)
    check("  nor is the issued key under another name", roster.contains(issued_key, "W1AW"), False)
    dana, count = supporter.issue("John Doe", seed_path=seed_file)
    check("a second key, the roster re-signed", count, 2)
    data = json.loads(roster.FILE.read_text())
    check("  the file names nobody", all(len(e) == 64 for e in data["entries"]), True)
    check("  and says how many", data["count"], 2)
    check("  signed by the issuer", data["public_key"], pk.hex())
    tampered = dict(data)
    tampered["entries"] = data["entries"] + [roster.entry(key, "KC9SP")]
    check("an entry added by hand does not check",
          roster.parse(json.dumps(tampered))[1], "the roster's signature does not check")
    other_seed, _ = ed25519.keypair()
    forged = roster.write({roster.entry(key, "KC9SP")}, other_seed, tmp / "forged.roster")
    check("a roster signed with somebody else's key does not check",
          roster.parse(forged)[1], "the roster's signature does not check")
    check("garbage is not a roster", roster.parse("hello")[1], "not a roster")
    check("revoked, a key is not real any more",
          (roster.revoke(issued_key, "KC9SP", seed_path=seed_file), roster.contains(issued_key, "KC9SP")),
          (True, False))
    check("  revoking it again says it was not there", roster.revoke(issued_key, "KC9SP", seed_path=seed_file), False)
    key, count = supporter.issue("KC9SP", seed_path=seed_file)
    check("  and can be reissued", (count, roster.contains(key, "KC9SP")), (2, True))
    roster.CACHE.parent.mkdir(parents=True)
    roster.write(set(json.loads(roster.FILE.read_text())["entries"]) | {roster.entry("SAAA-AAAA", "W1AW")},
                 seed, roster.CACHE, issued="2027-01-01")
    check("a fetched roster issued later is the one used", roster.load()["count"], 3)
    check("  so its keys are real here", roster.contains("SAAA-AAAA", "W1AW"), True)
    roster.CACHE.unlink()
    roster._cache.clear()
    check("  and gone, the shipped one is", roster.load()["count"], 2)

    print("\n-- into the settings, beside the rest --")
    settings = {"callsign": "KC9SP"}
    check("a wrong key is a reason, and changes nothing",
          (supporter.apply(settings, "AAAA-AAAA", "KC9SP") or "").startswith("that is not"), True)
    check("  the dict untouched", "supporter" in settings, False)
    check("a key without its name is a reason too",
          supporter.apply(settings, key), "the key needs the name it was cut for - the one given in the note")
    check("a good key with its name goes in", supporter.apply(settings, key, "KC9SP"), None)
    rec = settings["supporter"]
    check("  stored as XXXX-XXXX", (rec["key"], rec["holder"]), (key, "KC9SP"))
    check("  not named until asked", rec["named"], False)
    check("  dated today", len(rec["since"]), 10)
    settings["supporter"]["since"] = "2026-09-05"
    supporter.apply(settings, key.replace("-", "").lower(), "kc9sp", named=True)
    check("  the same key again keeps its first date", settings["supporter"]["since"], "2026-09-05")
    check("  and is stored tidy however it was typed", settings["supporter"]["key"], key)
    check("  and can choose to be named", settings["supporter"]["named"], True)
    supporter.apply(settings, named=False)
    check("  or not, without retyping the key", settings["supporter"]["named"], False)
    check("the name alone can be corrected", supporter.apply(settings, holder="KC9SP "), None)
    check("  but not to somebody else's",
          (supporter.apply(settings, holder="W1AW") or "").startswith("that is not the key"), True)
    unissued = supporter.make_key("KC9SP")
    check("with the whole check, a key that was only cut is refused",
          supporter.apply(settings, unissued, "KC9SP", check=supporter.verify), supporter.NOT_ON_ROSTER)
    check("  and the record stands", settings["supporter"]["key"], key)
    supporter.apply(settings, "")
    check("an empty key clears it", "supporter" in settings, False)
    check("  and the rest is still there", settings["callsign"], "KC9SP")

    print("\n-- on an account --")
    db.DB_PATH = tmp / "test.db"
    conn = db.connect()
    check("nobody's a supporter to begin with", supporter.record(conn), None)
    check("  so no name for the hall", supporter.named_holder(conn), "")
    rec, why = supporter.set_key(conn, dana, "John Doe", named=True)
    check("an issued key goes in", (rec or {}).get("holder"), "John Doe")
    check("  and comes back from the database", supporter.record(conn)["holder"], "John Doe")
    check("  named for the hall, as printed", supporter.named_holder(conn), "John Doe")
    supporter.set_key(conn, dana, "John Doe", named=False)
    check("  unless they would rather not", supporter.named_holder(conn), "")
    check("a key that was only cut is refused", supporter.set_key(conn, unissued, "KC9SP")[1], supporter.NOT_ON_ROSTER)
    check("  and the record stands", supporter.record(conn)["holder"], "John Doe")
    roster.revoke(dana, "John Doe", seed_path=seed_file)
    check("revoked on the roster, the record is gone from the account", supporter.record(conn), None)
    supporter.issue("John Doe", seed_path=seed_file)     # a different key; the old one stays revoked
    check("  and does not come back with somebody's new key", supporter.record(conn), None)
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
    # "Free for everyone" was the wording here, and it was wider than the
    # licence: PolyForm Noncommercial. The point of the line is that the
    # coffee is not a toll, and that survives without the overclaim.
    check("  and that it stays free", card["foot"], "It stays free, coffee or no coffee.")
    check("  where the coffee goes", card["url"], "https://github.com/sponsors/skpeterson2000")
    supporter.shown(conn, "coffee")
    check("put away, it stays away", supporter.card(conn, supporters=[])["kind"], "none")
    for i in range(1200):                      # a hundred hours more
        db.log_answer(conn, "general", f"G1A{i:04d}", "G1A", 1, 0, 300000, "study")
    check("  until a hundred hours later", supporter.card(conn, supporters=[])["kind"], "coffee")

    print("\n-- the thanks card: a supporter is thanked, and told what it meant --")
    supporter.set_key(conn, key, "KC9SP", named=True)
    conn.execute("UPDATE profile SET settings = json_set(settings, '$.supporter.since', '2026-09-15')")
    conn.commit()
    others = [{"who": "KC9SP", "note": ""}, {"who": "W1AW", "note": ""}, {"who": "VE3ABC", "note": ""}]
    card = supporter.card(conn, supporters=others, changelog=CHANGELOG)
    check("a supporter is thanked, not asked", card["kind"], "thanks")
    check("  by name", card["title"], "Thank you, KC9SP, for your generous support of this project.")
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
    check("two", supporter.words(["KC9SP", "John Doe"]), "KC9SP and John Doe")
    check("many", supporter.words([f"N{i}XX" for i in range(9)]),
          "N0XX, N1XX, N2XX, N3XX, N4XX and N5XX and 3 more")
    check("none", supporter.words([]), "")
    check("the honorary line names the game",
          supporter.honour_line("KC9SP", "shootout"),
          "This shootout is brought to you by the generous contribution of KC9SP.")
    check("  a round of golf, for a club", supporter.honour_line("Cedar Valley ARC", "golf"),
          "This round of golf is brought to you by the generous contribution of Cedar Valley ARC.")
    check("  and something with no game running", supporter.honour_line("KC9SP", None),
          "This session is brought to you by the generous contribution of KC9SP.")

    print("\n-- the hall: net control gathers the room's supporters --")
    net = netcontrol.Net(name="test")
    net.host_supporter = "KC9SP"
    a, _ = net.check_in("unit-a", "Table A", 2, instance="a")
    b, _ = net.check_in("unit-b", "Table B", 2, instance="b")
    a.supporter = "John Doe"
    b.supporter = "KC9SP"                       # the host, again, at a table
    check("the host first, each name once", net.supporters(), ["KC9SP", "John Doe"])
    check("  in the check-in's dict", a.as_dict()["supporter"], "John Doe")
    view = net.show_for("unit-a")
    check("the show goes to the table", "card" in view, True)
    check("  and the show knows the room", net.show.supporters, ["KC9SP", "John Doe"])
    check("  the board knows it too, before any table", net.board()["show"] is not None, True)

    print("\n-- the show: the honorary card and the roll of thanks --")
    s = show.Show()
    s.set_deck({k: False for k in show.TRIVIA_DECKS}, house=1.0)
    s.supporters = ["KC9SP", "John Doe"]
    kinds, honours = [], []
    now = 1000.0
    for _ in range(12):
        view = s.for_unit("unit-a", standings=[], join=True, now=now, supporter="John Doe", game="shootout")
        kinds.append(view["card"]["kind"])
        if view["card"].get("honour"):
            honours.append(view["card"]["text"])
        now += s.dwell + 1
    check("the thanks card is in the rotation", "thanks" in kinds, True)
    check("  and the house card is the supporter's on their table",
          honours[:1], ["This shootout is brought to you by the generous contribution of John Doe."])
    plain = [s.for_unit(None, standings=[], join=True, now=now + i * (s.dwell + 1))["card"]
             for i in range(12)]
    check("  a screen with no supporter sees ELMER's own card",
          any(c["kind"] == "house" and not c.get("honour") for c in plain), True)
    roll = next(c for c in plain if c["kind"] == "thanks")
    check("  the roll names the room", roll["supporters"], ["KC9SP", "John Doe"])
    s.supporters = []
    s.set_deck({})
    kinds = [s.for_unit(None, standings=[], join=True, now=now + i * (s.dwell + 1))["card"]["kind"]
             for i in range(12)]
    check("nobody to thank, no card", "thanks" in kinds, False)

    print("\n-- a certificate carries the line --")
    from elmer import certpdf
    pdf = certpdf.build([{"place": 1, "name": "Dana", "lines": ["won"]}],
                        event="Test", thanks="With thanks to KC9SP and John Doe.")
    check("a PDF comes back", pdf[:4], b"%PDF")

    print()
    if FAILS:
        print("FAILURES:", FAILS)
        sys.exit(1)
    print("all ok")


if __name__ == "__main__":
    main()

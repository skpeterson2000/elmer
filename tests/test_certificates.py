#!/usr/bin/env python3
"""Certificates for the wall: who they name, what they say, and what they do not.

    python3 tests/test_certificates.py

A club that runs a tournament night had nothing to hand the winner. This is
the piece of paper. What is checked: a page per placing; never a practice
player on one, because a bot on a certificate is the program awarding
itself; the facts counted from the game's own history; the event name the
host typed; and the medal art found where it is kept, with the drawn medal
standing in when it is not.

The print shelf and the database are both redirected to temporary places for
the run - a test that leaves certificates on the operator's own shelf, or
writes "Test ARC" into their unit's event details, is the same fault as one
that reads their profile.
"""
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import certpdf, db, netcontrol, party, prints  # noqa: E402

# A temporary database before the app is imported, because the event details
# are saved as a unit setting and a test must not write the operator's.
_spare = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_spare.close()
db.DB_PATH = _spare.name

from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def pages(pdf):
    # Page objects are not inside compressed streams, so this count is honest;
    # the text on them is, so nothing here greps for a sentence.
    return len(re.findall(rb"/Type\s*/Page\b(?!s)", pdf))


tmp = Path(tempfile.mkdtemp())
prints.SHELF = tmp
prints.INDEX = tmp / "index.json"
app.config["TESTING"] = True
client = app.test_client()

print("\nthe sentences a placing carries")
lines = certpdf.lines_for(
    {"answered": 36, "correct": 31, "score": 118, "fastest": 7,
     "blocks_won": [1, 3], "unit_name": "Poldhu"},
    {"label": "Technician", "length": 36, "blocks": 3})
check("the tournament, its length and its blocks",
      lines[0], "in the Technician tournament - 36 questions in 3 blocks of twelve")
check("the score as a fraction, then points", lines[1], "31 of 36 correct - 118 points")
check("fastest, pluralised", lines[2], "fastest correct answer 7 times")
check("blocks won", lines[3], "won blocks 1, 3")
check("the table", lines[4], "at the Poldhu table")
check("a shootout says what it was",
      certpdf.lines_for({"letters": 1}, {"label": "General", "mode": "shootout"})[0],
      "Last one standing in the General shootout")

print("\nthe medals")
for place in (1, 2, 3):
    check(f"art for place {place} is where it is kept",
          certpdf.medal_image(place) is not None, True)
check("no art for a fourth place, so the drawing stands in", certpdf.medal_image(4), None)
pdf = certpdf.build([{"place": p, "name": f"P{p}", "lines": ["x"]} for p in (1, 2, 3, 4)],
                    "Test night")
check("one page per award, art or drawn", pages(pdf), 4)
check("it is a PDF", pdf[:5], b"%PDF-")

print("\na hall's certificates come from the hall's own history")
net = netcontrol.net(create=True, name="Test net", difficulty="technician")
net.check_in("u1", "Poldhu", players=2)
net.check_in("u2", "Clifden", players=2)
for n in range(1, 4):
    net.start_round("tech2026", f"T1A{n:02d}", 0,
                    {"text": "?", "choices": ["a", "b"], "section": "T1A"}, seconds=5)
    # Ann plays as "Sparks" and wants her callsign on the wall; Bob plays as
    # himself and said nothing about a certificate.
    net.report("u1", n, [{"name": "Sparks", "correct": True, "ms": 900, "cert_name": "Ann Example, KX0ANN"},
                         {"name": "Rig", "correct": True, "ms": 700, "bot": "practice"}])
    net.report("u2", n, [{"name": "Bob", "correct": n != 2, "ms": 1500}])
    net.close_round()
try:
    print("\nthe play name is the room's; the certificate name is nobody's until printed")
    check("the board never carries the certificate name",
          any("cert_name" in p for p in net.board()["people"]), False)
    check("  nor does the people board", any("cert_name" in p for p in net.people_board()), False)
    check("  but the host can get it for the awards",
          next(p for p in net.people_for_awards() if p["name"] == "Sparks")["cert_name"],
          "Ann Example, KX0ANN")
    reply = client.post("/api/tournament/certificates",
                        json={"scope": "hall", "event": "Lakes Area ARC", "places": 3})
    check("the route answers", reply.status_code, 200)
    got = reply.get_json()
    check("  with a place on the shelf", bool(got.get("view")), True)
    row = prints.one(got["id"])
    check("  the event name the host typed is the title", row["title"], "Certificates - Lakes Area ARC")
    check("  the practice player is not on it", "Rig" in row["meta"]["awarded"], False)
    check("  the two people are, best first, under the names they asked for",
          row["meta"]["awarded"], ["Ann Example, KX0ANN", "Bob"])
    check("  and the pages match the people", pages(prints.read(got["id"])), 2)
finally:
    netcontrol.close_net()

print("\nand a table's from the table's")
room = party.room(create=True)
for pid in list(room.players):
    room.leave(pid)
ann = room.join("Ann", cert_name="Ann Example", license="tech")[0]
bob = room.join("Bob")[0]
room.fill_bots("Listener")
# The license class is the third thing kept apart from the play name: it is
# held, normalised, never shown, and travels only towards the hall's log.
check("a stated license class is held, normalised", ann.license, "Technician")
check("  and 'did not say' is empty, not None", bob.license, "")
check("  it is nowhere in what a phone or table is shown",
      any("license" in m for c in room.state()["cohorts"] for m in c["members"]), False)
check("  a rejoin keeps it", room.join("Ann", previous=ann.id)[0].license, "Technician")
check("  and can add it later, but not change it",
      (room.join("Bob", previous=bob.id, license="General")[0].license,
       room.join("Ann", previous=ann.id, license="Extra")[0].license), ("General", "Technician"))
check("  with nobody seated twice for it", len([p for p in room.players.values() if not p.bot]), 2)
check("  the table hands it in with the round", room.license_of(ann.id), "Technician")
room.start_round("tech2026", "T1A01", 0, seconds=30,
                 payload={"text": "?", "choices": ["a", "b"], "section": "T1A",
                          "difficulty": "technician"})
room.submit(ann.id, 0, 800)
room.submit(bob.id, 1, 1200)
room.close_round()
print("\nthe host sees who would be awarded before printing, and can fix a name")
preview = client.get("/api/tournament/certificates/preview?scope=table").get_json()
check("the preview names them as they asked", [a["name"] for a in preview["awards"]],
      ["Ann Example", "Bob"])
check("  with the details to fill in", sorted(preview["details"])[:4],
      ["club", "club_signer", "event", "net_control"])
check("  and today's date as a starting point", bool(preview["details"]["when"]), True)

check("  and says whose name is whose",
      [a["chosen"] for a in preview["awards"]], [True, False])

# Bob typed "Bob" on his phone and said nothing about a certificate; the host
# knows him as Robert Example. Ann said what she wanted on the wall, and the
# host's attempt to "correct" that is ignored: nobody turns a Richard into a
# Dick but Richard.
reply = client.post("/api/tournament/certificates", json={
    "scope": "table", "places": 3, "event": "Club Night", "club": "Test ARC",
    "when": "Saturday 17 July 2027", "where": "Brainerd, Minnesota",
    "net_control": "KX0ANN", "club_signer": "The Secretary",
    "names": {"1": "Annie", "2": "Robert Example"}})
check("the route answers for a table", reply.status_code, 200)
row = prints.one(reply.get_json()["id"])
check("  the chosen name stands, the play name is fixed",
      row["meta"]["awarded"], ["Ann Example", "Robert Example"])
check("  titled by the event the host typed", row["title"], "Certificates - Club Night")

print("\nthe event details are kept on the unit for the next print")
again = client.get("/api/tournament/certificates/preview?scope=table").get_json()["details"]
check("the event", again["event"], "Club Night")
check("the club", again["club"], "Test ARC")
check("the date as worded", again["when"], "Saturday 17 July 2027")
check("who signs", [again["net_control"], again["club_signer"]], ["KX0ANN", "The Secretary"])
# ... but not the name fixes, which were about those people and that print.
third = client.get("/api/tournament/certificates/preview?scope=table").get_json()["awards"]
check("the name fix was not kept - it was about that print", [a["name"] for a in third][1], "Bob")
check("  and the table's state never carried it",
      any("cert_name" in m for c in room.state()["cohorts"] for m in c["members"]), False)

print("\nnobody to award is said, not faulted")
room2 = party.room(create=True)
for pid in list(room2.players):
    room2.leave(pid)
reply = client.post("/api/tournament/certificates", json={"scope": "table"})
check("an empty table is a refusal in words", reply.status_code, 409)
check("  with a sentence", bool((reply.get_json() or {}).get("message")), True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)

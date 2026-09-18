#!/usr/bin/env python3
"""Net control speaking in code: a ping to one table, or to the room.

    python3 tests/test_netping.py

A hall is a room with boxes in it and people standing between them, and the
host has always been able to put words on a screen. Words are no use for two
of the things a host actually needs. Finding which box in the room is table
four: the fastest way is to make that one say its own name out loud. And
inviting a room that is not looking at any screen: a sound carries to people
whose backs are turned.

The sound this program has is code, and the vocabulary is the Q-signals the
CW page is already teaching - QRV, QSL, QRT - so the hall speaks the
language of the lessons and a person who sat one this week can read what net
control just said. The words go up on the screens at the same moment, so
nobody who cannot read it yet is left out of what they are being told.

What matters here: a ping meant for one table reaches that table and no
other, the code carries the right name, and net control's own vocabulary is
the only thing that can be keyed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import netcontrol  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the vocabulary --")
    check("a unit asked to identify itself keys its own name",
          netcontrol.ping("ping", "POLDHU", "Test Net")[0], "DE POLDHU")
    check("  and the screens say why it is making a noise",
          netcontrol.ping("ping", "POLDHU", "Test Net")[1],
          "Net control is looking for this unit.")
    check("the invitation is a CQ from the net", netcontrol.ping("cq", "", "FIELD DAY")[0],
          "CQ CQ DE FIELD DAY")
    check("ready there?", netcontrol.ping("qrv")[0], "QRV?")
    check("received, understood", netcontrol.ping("qsl")[0], "QSL")
    check("finish up", netcontrol.ping("qrt")[0], "QRT")
    # A name is somebody's, and it is about to be read to a room: what the
    # keyer cannot send is dropped rather than mangled.
    check("a table's name is reduced to what a keyer can send",
          netcontrol.ping("ping", "Scott's kitchen")[0], "DE SCOTTS KITCHEN")
    check("  and a name with nothing sendable in it falls back to the program's",
          netcontrol.ping("ping", "!!!")[0], "DE ELMER")
    check("nothing else can be keyed - the host does not get a free text line here",
          netcontrol.ping("sos"), (None, None))

    print("\n-- to one table, and to the room --")
    from elmer.app import app
    client = app.test_client()
    netcontrol.close_net()
    client.post("/api/net/open", json={"name": "Test Net", "difficulty": "technician"},
                environ_base=LOCAL)
    for unit, name in (("unit-a", "Poldhu"), ("unit-b", "Glace Bay")):
        client.post("/api/net/checkin", json={"unit": unit, "name": name, "players": 2},
                    environ_base=LOCAL)
    running = netcontrol.net()

    r = client.post("/api/net/ping", json={"say": "ping", "unit": "unit-a"}, environ_base=LOCAL)
    check("the host pings one table", r.status_code, 200)
    check("  and it is that table's own name in the air",
          r.get_json()["pinged"]["cw"], "DE POLDHU")
    mine = running.show.announcements_for(unit="unit-a")
    theirs = running.show.announcements_for(unit="unit-b")
    check("  the table it was meant for has something to key",
          [a["cw"] for a in mine], ["DE POLDHU"])
    check("  and the table next to it hears nothing", theirs, [])

    r = client.post("/api/net/ping", json={"say": "cq"}, environ_base=LOCAL)
    check("a CQ goes to the whole room", r.status_code, 200)
    check("  in the net's own name", r.get_json()["pinged"]["cw"], "CQ CQ DE TEST NET")
    # Sorted: what is on a screen first is the overlay's business, not this
    # test's. What matters is who has it.
    check("  and every table has it now",
          [sorted(a["cw"] for a in running.show.announcements_for(unit=u))
           for u in ("unit-a", "unit-b")],
          [["CQ CQ DE TEST NET", "DE POLDHU"], ["CQ CQ DE TEST NET"]])

    r = client.post("/api/net/ping", json={"say": "have a nice day"}, environ_base=LOCAL)
    check("something that is not in the vocabulary is refused", r.status_code, 400)

    # An ordinary notice is silent. Only a ping carries code, or every word
    # the host typed would be keyed at the room.
    client.post("/api/net/announce", json={"text": "Coffee is on."}, environ_base=LOCAL)
    said = running.show.announcements_for(unit="unit-b")
    check("a notice the host typed is not keyed at anybody",
          [a["cw"] for a in said if a["text"] == "Coffee is on."], [None])
    netcontrol.close_net()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

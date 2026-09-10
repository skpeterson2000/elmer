#!/usr/bin/env python3
"""A table that can hear a net joins it, instead of starting its own.

    python3 tests/test_autojoin.py

This is the difference between a room of Pis playing together and a room of
Pis each running its own quiz, and until now it was the second one: net
control served one question to every table, the tables ran their own rounds -
and the only way to wire a table in was for somebody to type an address into
it.  Nothing did that, so nothing ever joined, and the auto-start then
committed each unit to playing alone fifteen seconds after anybody sat down.

The rule under test is the order of precedence.  Look for a net first; start
one of your own only when there is nothing to join.  And leave a table alone
that somebody has deliberately taken out of a net, because a table that walks
straight back in has not been offered a choice.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import app as appmod, cohort, db  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


TECH = {"url": "http://10.0.0.5:5000", "name": "Technician net",
        "difficulty": "technician", "units": 2}
GENERAL = {"url": "http://10.0.0.6:5000", "name": "General net",
           "difficulty": "general", "units": 6}
UNNAMED = {"url": "http://10.0.0.7:5000", "name": "a net",
           "difficulty": "", "units": 9}

print("\nthe table chooses, and it chooses on the material")
check("a General unit takes the General net",
      appmod._party_pick_net([TECH, GENERAL], "general")["name"], "General net")
check("a Technician unit takes the Technician net",
      appmod._party_pick_net([GENERAL, TECH], "technician")["name"],
      "Technician net")

print("\nwith nothing matching, the busiest net rather than none")
# A General at a Technician table answers Technician questions - material
# they have already passed, asked at speed, which is practice and not a
# misjudgement of their class.
check("an Extra unit still joins in",
      appmod._party_pick_net([UNNAMED, GENERAL], "extra")["name"], "a net")
check("and the fullest is the one offered first",
      appmod._party_pick_net([UNNAMED, TECH], "extra")["units"], 9)

print("\nwith nothing out there it joins nothing")
check("no net, no choice", appmod._party_pick_net([], "technician"), None)

print("\na table cut loose by hand stays loose")
connection = db.connect()
was = db.unit_get(connection, cohort.AUTO_SETTING)
try:
    cohort.set_auto_join(connection, True)
    check("a fresh table will attach itself",
          cohort.auto_join_wanted(connection), True)
    appmod.app.config["TESTING"] = True
    with appmod.app.test_client() as client:
        body = client.post("/api/party/net", json={"join": False}).get_json()
    check("cutting it loose says so", body.get("auto_join"), False)
    check("and it is remembered", cohort.auto_join_wanted(connection), False)
    # It runs inside a request in earnest, which is where its database
    # handle comes from.
    with appmod.app.test_request_context():
        check("so nothing reattaches it",
              appmod._party_auto_join(appmod.party.room(create=True)), False)

    with appmod.app.test_client() as client:
        client.post("/api/party/net", json={"url": "http://127.0.0.1:9/",
                                            "unit": "t", "name": "T"})
    check("wiring it in by hand turns it back on",
          cohort.auto_join_wanted(connection), True)
finally:
    cohort.disconnect(connection)
    db.unit_set(connection, cohort.AUTO_SETTING, was)

print("\nhearing a net is enough - nobody types an address")
# The roster is stood in for, because two ELMERs on one machine share a unit
# id and filter each other out by design.  What is proved here is everything
# downstream of hearing: that a table which hears a net becomes that net's
# table, on its own, with nothing entered by hand.
from elmer import discovery  # noqa: E402


class Heard:
    def __init__(self, nets):
        self._nets = nets

    def nets(self):
        return self._nets


was_hood = discovery.neighbourhood
connection = db.connect()
was_auto = db.unit_get(connection, cohort.AUTO_SETTING)
try:
    cohort.set_auto_join(connection, True)
    cohort.disconnect(connection)
    cohort.set_auto_join(connection, True)      # disconnect() forgets the url
    discovery.neighbourhood = lambda: Heard([TECH, GENERAL])
    check("nothing attached to start with", cohort.bridge(), None)
    with appmod.app.test_request_context():
        joined = appmod._party_auto_join(appmod.party.room(create=True))
    check("it joined by itself", joined, True)
    link = cohort.bridge()
    check("and it is now somebody's table", link is not None, True)
    check("reporting to the net it heard", link.url if link else None,
          TECH["url"])
    check("under this unit's own id",
          (link.unit_id if link else None), cohort.default_unit_id())

    print("\nand having joined, it does not start a game of its own")
    with appmod.app.test_request_context():
        room = appmod.party.room(create=True)
        check("the table is under a net", appmod._party_under_net(), True)
        check("so it may not begin on its own account",
              appmod._party_may_begin(room), False)
finally:
    discovery.neighbourhood = was_hood
    cohort.disconnect(connection)
    db.unit_set(connection, cohort.AUTO_SETTING, was_auto)

print("\nand a unit running the net does not report to itself")
from elmer import netcontrol  # noqa: E402
netcontrol.net(create=True, difficulty="technician")
try:
    with appmod.app.test_request_context():
        check("the host stays the host",
              appmod._party_auto_join(appmod.party.room(create=True)), False)
finally:
    netcontrol.close_net()

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")

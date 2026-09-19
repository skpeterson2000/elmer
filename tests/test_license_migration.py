#!/usr/bin/env python3
"""Undoing a silent write: the licence classes the band plan left behind.

    python3 tests/test_license_migration.py

The band plan's class picker used to save the class being *read* into the
profile, and the profile's class is the one thing the pool gate reads. So
anybody who ever looked at Amateur Extra on that page had every study pool
opened to them, on the dashboard and at the table, and was never told. The
picker was fixed. The values it left behind were not, and they are sitting
in every database that has ever had that page opened on it.

A value it left cannot be told from one somebody typed on purpose, except by
what is missing: no mark saying whose word it is, and no FCC record behind
it. Version 8 clears exactly those, so the station is asked once rather than
quietly believed.

What must survive it: a class the FCC record answers for, and a class marked
as the operator's own. That second one is how a licence from outside the US -
callook serves the FCC and nothing else - and an upgrade the published file
has not caught up with live through this.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import callsign, db, gating  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def record(cls):
    return {"callsign": "KC9SP", "found": True, "license_class": cls,
            "expires": "05/14/2031", "granted": "05/14/2021", "source": "test",
            "status": callsign.status_for(callsign._parse_date("05/14/2031"))}


def settings_of(conn, user_id):
    row = conn.execute("SELECT settings FROM profile WHERE id = ?", (user_id,)).fetchone()
    return json.loads(row["settings"])


def main():
    conn = db.connect()

    # Four stations, as they would have been found on a unit that had been
    # running before the picker was fixed.
    people = {
        1: {"license_class": "Extra"},                              # the leftover
        2: {"license_class": "Advanced", callsign.SOURCE: callsign.OWN},   # said on purpose
        3: {"license_class": "General", "license": record("General")},     # the FCC's word
        4: {"name": "nobody in particular"},                        # never touched it
    }
    conn.execute("DELETE FROM profile")
    for user_id, settings in people.items():
        conn.execute("INSERT INTO profile (id, name, created, settings) VALUES (?, ?, ?, ?)",
                     (user_id, f"op{user_id}", db.today(), json.dumps(settings)))
    conn.execute("PRAGMA user_version = 7")
    conn.commit()

    print("\n-- the upgrade --")
    check("the database says it is version 8 afterwards", db.migrate(conn), 8)
    check("a class with nothing behind it is gone",
          settings_of(conn, 1).get("license_class"), None)
    check("  a class the operator said was theirs stays, and stays marked",
          (settings_of(conn, 2).get("license_class"),
           settings_of(conn, 2).get(callsign.SOURCE)), ("Advanced", callsign.OWN))
    check("  a class the FCC record answers for stays",
          settings_of(conn, 3).get("license_class"), "General")
    check("  and a station that never touched it is left alone",
          settings_of(conn, 4), {"name": "nobody in particular"})

    print("\n-- and it says what it took --")
    # Clearing a class and saying nothing is how a licensed operator opens
    # ELMER the next morning to find it treating them as though they hold
    # nothing, with no way to learn why. The value is left behind by name.
    check("the class it cleared is remembered, to be said",
          settings_of(conn, 1).get("license_class_cleared"), "Extra")
    check("  and a station it did not touch has nothing to say",
          settings_of(conn, 4).get("license_class_cleared"), None)
    from elmer.app import app
    client = app.test_client()
    page = client.get("/", environ_base=LOCAL).data.decode("utf-8")
    check("  the Station panel says so, and what to do about it",
          ("cleared it on an update" in page, "enter your callsign" in page), (True, True))
    # Setting a class again is the end of it, by hand or from the record.
    client.post("/api/settings", json={"license_class": "General"}, environ_base=LOCAL)
    check("  giving it a class again takes the notice away",
          db.get_profile(db.connect())["settings"].get("license_class_cleared"), None)
    check("  and the page stops saying it",
          "cleared it on an update" in client.get("/", environ_base=LOCAL).data.decode("utf-8"),
          False)
    client.post("/api/settings", json={"license_class": ""}, environ_base=LOCAL)

    print("\n-- what the cleared station sees now --")
    holds = callsign.held(settings_of(conn, 1))
    check("it holds nothing, and claims nothing", (holds["class"], holds["source"]), ("", ""))
    check("  so the ladder is back at the beginning",
          sorted(gating.open_pools(settings_of(conn, 1), [],
                                   ["tech2026", "gen2023", "extra2024"])[0]),
          ["tech2026"])
    check("  while the one who said Advanced keeps what that opens",
          sorted(gating.open_pools(settings_of(conn, 2), [],
                                   ["tech2026", "gen2023", "extra2024"])[0]),
          ["extra2024", "gen2023", "tech2026"])

    print("\n-- run again, it does nothing --")
    # Idempotent by construction: every class saved from here on carries the
    # mark, so there is nothing left for it to find. A migration that ate a
    # little more each time it ran would be worse than the bug.
    conn.execute("PRAGMA user_version = 7")
    conn.commit()
    db.migrate(conn)
    check("the deliberate answers are still there",
          (settings_of(conn, 2).get("license_class"), settings_of(conn, 3).get("license_class")),
          ("Advanced", "General"))

    print("\n-- and a class typed today carries the mark --")
    from elmer.app import app
    client = app.test_client()
    client.post("/api/settings", json={"license_class": "Extra"}, environ_base=LOCAL)
    fresh = db.get_profile(db.connect())["settings"]
    check("typed with no record to check it against, it is the operator's word",
          (fresh.get("license_class"), fresh.get(callsign.SOURCE)), ("Extra", callsign.OWN))
    check("  which is what carries it through the next upgrade",
          bool(fresh.get(callsign.SOURCE)), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""One answer to "what class does this station hold?", and the FCC's record
is it.

    python3 tests/test_license_truth.py

The question used to be answered in two different orders. The pool gate read
the typed setting first; the print path read the FCC record first. So a class
left in the profile by something else - the band plan's picker used to leave
one there on every change - outranked the Commission and opened pools the
record did not.

One resolver answers it now. The record decides wherever there is one, and it
is pre-populated on lookup so that no screen asks for something the
Commission has already published. An operator may still answer for
themselves, because callook serves the ULS and nothing else and a licence
from another country resolves to nothing here, and because an upgrade granted
this week is not in the published file yet. That answer is kept, it opens
their pools and their pickers, and it is marked as theirs. What it may not do
is go on paper beside a callsign the FCC has on file at another class.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import callsign, db, gating  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
POOLS = ["tech2026", "gen2023", "extra2024"]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def record(cls):
    return {"callsign": "KC9SP", "found": True, "license_class": cls,
            "expires": "05/14/2031", "granted": "05/14/2021", "source": "test",
            "status": callsign.status_for(callsign._parse_date("05/14/2031"))}


def opened(settings):
    """The amateur pools this profile may study, in ladder order."""
    allowed, _ = gating.open_pools(settings, [], POOLS)
    return [p for p in POOLS if p in allowed]


def main():
    print("\n-- the resolver on its own --")
    check("nothing known, nothing claimed",
          (callsign.held({})["class"], callsign.held({})["source"]), ("", ""))
    own = callsign.held({"license_class": "General"})
    check("no record, so the operator's word stands and is marked as theirs",
          (own["class"], own["source"], own["verified"]), ("General", callsign.OWN, False))
    fcc = callsign.held({"license": record("General")})
    check("a record answers for itself",
          (fcc["class"], fcc["source"], fcc["verified"]), ("General", callsign.FCC, True))
    # The regression. A profile carrying a class from before this rule, with
    # no mark on it, is not a claim against the record - it is a leftover.
    stale = callsign.held({"license": record("General"), "license_class": "Extra"})
    check("a class left in the profile does not outrank the record",
          (stale["class"], stale["source"], stale["record"]), ("General", callsign.FCC, "General"))
    said = callsign.held({"license": record("General"), "license_class": "Extra",
                          callsign.SOURCE: callsign.OWN})
    check("said deliberately, it stands - and stays the operator's word",
          (said["class"], said["source"], said["verified"], said["record"]),
          ("Extra", callsign.OWN, False, "General"))
    agree = callsign.held({"license": record("General"), "license_class": "General",
                           callsign.SOURCE: callsign.OWN})
    check("an answer that agrees with the record is the record",
          (agree["source"], agree["verified"]), (callsign.FCC, True))

    print("\n-- the gate follows the record --")
    check("a General's pools", opened({"license": record("General")}), ["tech2026", "gen2023", "extra2024"])
    check("  Amateur Extra is offered as the next thing to work toward, not as held",
          gating.reach({"license": record("General")}, [])["rung"], 1)
    check("a leftover Extra beside a General record opens no more than General's",
          opened({"license": record("General"), "license_class": "Extra"}),
          ["tech2026", "gen2023", "extra2024"])
    check("  and the gate says whose word it went on",
          gating.reach({"license": record("General"), "license_class": "Extra"}, [])["verified"], True)
    check("a Technician record holds the ladder at Technician and General",
          opened({"license": record("Technician")}), ["tech2026", "gen2023"])
    check("  a leftover Extra cannot open Amateur Extra over it",
          opened({"license": record("Technician"), "license_class": "Extra"}), ["tech2026", "gen2023"])
    check("  but said deliberately, it can - your own study is your own business",
          opened({"license": record("Technician"), "license_class": "Extra",
                  callsign.SOURCE: callsign.OWN}), ["tech2026", "gen2023", "extra2024"])
    check("  and the gate does not call that verified",
          gating.reach({"license": record("Technician"), "license_class": "Extra",
                        callsign.SOURCE: callsign.OWN}, [])["verified"], False)
    check("no licence at all is where everybody starts", opened({}), ["tech2026"])

    print("\n-- the record fills the class in, and clears an older answer --")
    callsign.lookup = lambda call, refresh=False: record("General")
    from elmer.app import app
    c = app.test_client()
    c.post("/api/settings", json={"license_class": "Extra"}, environ_base=LOCAL)
    check("an answer typed before any callsign is the operator's word",
          callsign.held(db.get_profile(db.connect())["settings"])["source"], callsign.OWN)
    c.post("/api/settings", json={"callsign": "KC9SP"}, environ_base=LOCAL)
    settings = db.get_profile(db.connect())["settings"]
    check("the callsign is looked up and the class comes with it",
          (settings.get("license_class"), settings.get(callsign.SOURCE)), ("General", None))
    check("  which is what every screen offering a class now opens on",
          callsign.held(settings)["class"], "General")

    print("\n-- an answer of your own is kept, and marked --")
    c.post("/api/settings", json={"license_class": "Extra"}, environ_base=LOCAL)
    holds = callsign.held(db.get_profile(db.connect())["settings"])
    check("saying Amateur Extra over a General record stands",
          (holds["class"], holds["source"], holds["record"]), ("Extra", callsign.OWN, "General"))
    page = c.get("/bandplan", environ_base=LOCAL).data.decode("utf-8")
    check("  the band plan opens on it", '<option value="Extra" selected>' in page, True)
    check("  and says whose word it is", "your own word" in page, True)
    c.post("/api/settings", json={"license_class": "General"}, environ_base=LOCAL)
    check("saying what the record says takes the mark off",
          callsign.held(db.get_profile(db.connect())["settings"])["source"], callsign.FCC)

    print("\n-- what may go on paper --")
    c.post("/api/settings", json={"license_class": "Extra"}, environ_base=LOCAL)
    d = c.get("/api/bandplan?class=Extra", environ_base=LOCAL).get_json()
    check("a chart with a callsign on it reads the record, not the operator's word",
          d["own_class"], "General")
    check("  so reading Amateur Extra still earns the note", d["above_yours"], True)

    print("\n-- the pickers open where the operator lives --")
    c.post("/api/settings", json={"license_class": "General"}, environ_base=LOCAL)
    page = c.get("/party/1", environ_base=LOCAL).data.decode("utf-8")
    check("a General's table opens on General, not on Technician",
          ('<option value="general" selected>' in page,
           '<option value="technician" selected>' in page), (True, False))
    check("  and Amateur Extra is open to them, the next thing to work toward",
          'value="extra" disabled' in page, False)
    callsign.lookup = lambda call, refresh=False: record("Technician")
    c.post("/api/settings", json={"callsign": "KC9SP"}, environ_base=LOCAL)
    page = c.get("/party/1", environ_base=LOCAL).data.decode("utf-8")
    check("a Technician's table opens on Technician",
          '<option value="technician" selected>' in page, True)
    check("  with Amateur Extra not open yet", 'value="extra" disabled' in page, True)
    from elmer import party
    party.close_room()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

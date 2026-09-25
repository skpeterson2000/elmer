#!/usr/bin/env python3
"""A license opens the pools it entitles you to, and keeps doing so.

    python3 tests/test_license_unlocks.py

Reported as "adding a license to the program no longer unlocks the appropriate
question pools", and there were two faults behind it.

The first was a spelling pass across the whole program. A stored FCC record
could carry its class under either `licence_class` or `license_class`, and the
two places that read it each did so with a pair of `.get` calls, one for each
spelling. Rewriting every British spelling to American rewrote both halves of
each pair to the same key, so the fallback became a duplicate, every record
saved with the old spelling read as having no class at all, and the gate
offered Technician to an operator holding an Extra. Both spellings are read
through one function now, and will go on being read: the old records are
sitting in profiles on units in the field.

The second is older and worse. The Commission takes its own site down for
maintenance in the small hours, and a callsign entered during one of those
windows was written down as "no current FCC record" and left that way for
good - the retry only ever looked at records marked pending. A plain failure
is settled now too, from the unit's own copy of the FCC file, which costs a
local query and cannot fail the same way twice.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import app as appmod, callsign, db, gating, uls  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


POOLS = ["tech2026", "gen2023", "extra2024", "element1", "element3", "element8"]
AMATEUR = ("tech2026", "gen2023", "extra2024")


def opened(settings):
    got = gating.open_pools(settings, [], POOLS)
    return sorted(got["open"] if isinstance(got, dict) and "open" in got else got[0])


def amateur_open(settings):
    return sorted(p for p in opened(settings) if p in AMATEUR)


print("\nwhichever spelling the record was saved with, the class is read")
check("a record saved the old way", callsign.record_class(
    {"found": True, "licence_class": "Extra"}), "Extra")
check("  and the new way", callsign.record_class(
    {"found": True, "license_class": "Extra"}), "Extra")
check("  the new one wins where a record somehow has both", callsign.record_class(
    {"found": True, "license_class": "Extra", "licence_class": "General"}), "Extra")
check("a record that found nothing has no class", callsign.record_class(
    {"found": False, "license_class": "Extra"}), "")
check("  nor has nothing at all", callsign.record_class(None), "")

print("\nand the pools follow the class, either way round")
check("no license: Technician only", amateur_open({}), ["tech2026"])
check("an Extra stored the old way opens all three",
      amateur_open({"license": {"found": True, "callsign": "KC9SP", "licence_class": "Extra"}}),
      ["extra2024", "gen2023", "tech2026"])
check("  and stored the new way, the same",
      amateur_open({"license": {"found": True, "callsign": "KC9SP", "license_class": "Extra"}}),
      ["extra2024", "gen2023", "tech2026"])
# Your own rung and the one above it, which is gating.reach's documented
# promise: the next pool is offered as the thing to work toward. Without a
# license at all there is no next rung offered - that is the start state.
check("a Technician gets Technician and the next one up",
      amateur_open({"license": {"found": True, "callsign": "KC9SP", "licence_class": "Technician"}}),
      ["gen2023", "tech2026"])
check("a General gets General and Extra above it",
      amateur_open({"license": {"found": True, "callsign": "KC9SP", "licence_class": "General"}}),
      ["extra2024", "gen2023", "tech2026"])
check("the commercial pools are not gated on any of it",
      sorted(p for p in opened({}) if p.startswith("element")),
      ["element1", "element3", "element8"])

print("\na claim of no license does not outrank a record that says otherwise")
# The Station panel used to send the class on every save, whatever the
# operator had come there to change - so saving a name while the callsign
# was still being looked up wrote "No license" down as their own word. It
# then outranked the FCC record that arrived a minute later: the band plan
# opened on No license for a station holding an Extra, and the pools stayed
# shut. Nobody tells this program they hold nothing while the Commission
# has them on file.
RECORD = {"found": True, "callsign": "KC9SP", "license_class": "Extra"}
stale = {"license": RECORD, "license_class": "none", callsign.SOURCE: callsign.OWN}
got = callsign.held(stale)
check("the record wins over a claim of nothing", got["class"], "Extra")
check("  and it is marked verified", got["verified"], True)
check("  so the pools open", amateur_open(stale), ["extra2024", "gen2023", "tech2026"])
# A real answer for oneself at a lower class is still the operator's to give.
lower = {"license": RECORD, "license_class": "General", callsign.SOURCE: callsign.OWN}
got = callsign.held(lower)
check("a lower class answered for oneself is left alone", got["class"], "General")
check("  and is marked as their own word", got["verified"], False)
check("  with the record still named beside it", got["record"], "Extra")
# With no record at all, "no license" is the plain truth and stands.
check("with no record, no license is simply true",
      callsign.held({"license_class": "none", callsign.SOURCE: callsign.OWN})["class"], "none")

print("\na service rebuilding its copy is not the same as no record")
# callook.info answers UPDATING while it rebuilds from the Commission's
# publication, which it does in the small hours. Reading that as "no current
# FCC record" was wrong twice: the record exists, and the site that could not
# answer was not the FCC's - which is where an evening went.
was_fetch = callsign._fetch
try:
    callsign._fetch = lambda call: {"status": "UPDATING"}
    got = callsign._lookup_callook("KC9SP", refresh=True)
    check("a rebuilding service is not a missing record", got["found"], False)
    check("  it is marked pending, so it is asked again", got["pending"], True)
    check("  and it names the service that could not answer",
          "callook.info" in got["reason"], True)
    check("  not the FCC", "no current FCC record" in got["reason"], False)
    callsign._fetch = lambda call: {"status": "INVALID"}
    got = callsign._lookup_callook("KC9SP", refresh=True)
    check("a genuinely absent record still says so",
          (got["found"], got["pending"], "no current FCC record" in got["reason"]),
          (False, False, True))
finally:
    callsign._fetch = was_fetch

print("\na lookup that failed on the night is settled from the unit's own file")
# The Commission's site down for maintenance: the record says it found nothing
# and is not marked pending, which is exactly the record that used to be kept
# for good.
was_have, was_lookup, was_service = uls.have, uls.lookup, uls.service_of
conn = db.connect()
try:
    settings = db.get_profile(conn)["settings"]
    settings["license"] = {"callsign": "KC9SP", "found": False,
                           "reason": "no current FCC record for this callsign"}
    db.save_settings(conn, settings)
    check("stored, it opens nothing above Technician",
          amateur_open(db.get_profile(conn)["settings"]), ["tech2026"])

    # No file on the unit yet: nothing is asked, and nothing changes. The point
    # is that this does not go to the network on every page load.
    uls.service_of = lambda call: "amateur"
    uls.have = lambda service: None
    asked = {"n": 0}

    def counted(call):
        asked["n"] += 1
        return {"callsign": "KC9SP", "found": True, "service": "amateur",
                "license_class": "Extra", "expires": "04/26/2032"}
    uls.lookup = counted
    appmod._settle_pending_licenses(conn)
    check("with no file on the unit, nothing is asked", asked["n"], 0)
    check("  and it still opens nothing above Technician",
          amateur_open(db.get_profile(conn)["settings"]), ["tech2026"])

    # The file is here now, so the answer comes off the disk.
    uls.have = lambda service: {"rows": 1602938, "dated": "2026-09-20"}
    appmod._settle_pending_licenses(conn)
    check("with the file here, it is read again", asked["n"], 1)
    after = db.get_profile(conn)["settings"]
    check("  the record is kept", (after["license"]["found"],
                                   after["license"]["license_class"]), (True, "Extra"))
    check("  the class is held", callsign.held(after)["class"], "Extra")
    check("  and the pools open", amateur_open(after), ["extra2024", "gen2023", "tech2026"])

    # Settled once is settled: a found record is left alone.
    appmod._settle_pending_licenses(conn)
    check("a settled record is not looked up again", asked["n"], 1)
finally:
    uls.have, uls.lookup, uls.service_of = was_have, was_lookup, was_service
    conn.close()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)

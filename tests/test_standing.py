#!/usr/bin/env python3
"""The "licensed" pill says what the FCC says, not what was typed.

    python3 tests/test_standing.py

Reported from a real callsign: KA7EVD, once Donny Osmond's, lapsed decades
ago and gone from the FCC's file, came up "licensed" in the account menu.
So would XYZZY. The pill was pinned on anybody with anything in the
callsign box - db.py had it as bool(callsign) - and never looked at the
record beside it.

What is held here:

  - "licensed" is reserved for a license in force today;
  - a record's status is worked out on the day of the lookup and frozen, so
    the standing is recomputed from the expiry date on read - a license that
    was current when fetched and has since run out reads expired;
  - expired within the two-year window says so and says renew; past it says
    expired; cancelled or terminated says so where the FCC still lists it;
  - a callsign the FCC has no record of - lapsed and gone, foreign, or a
    slip; the file cannot tell them apart - says "no FCC record", which is
    the most the program can truthfully say, and never "licensed";
  - a callsign not yet looked up says nothing either way.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def on(days):
    return (date.today() + timedelta(days=days)).strftime("%m/%d/%Y")


def main():
    from elmer import db

    print("\n-- the standing, from the record and today's date --")
    check("no callsign is no standing", db.standing("", {}), None)
    check("a callsign nobody has looked up yet is unchecked", db.standing("XYZZY", {}), "unchecked")
    check("one the FCC has no record of is unfound",
          db.standing("KA7EVD", {"license": {"callsign": "KA7EVD", "found": False}}), "unfound")
    check("one the FCC lists as cancelled says so",
          db.standing("N0OLD", {"license": {"found": False, "fcc_status": "cancelled"}}), "cancelled")
    check("in force is current",
          db.standing("KC9SP", {"license": {"found": True, "expires": on(2000)}}), "current")
    check("run out last month is in grace",
          db.standing("W1AW", {"license": {"found": True, "expires": on(-30)}}), "grace")
    check("run out three years ago is expired",
          db.standing("N0XYZ", {"license": {"found": True, "expires": on(-1100)}}), "expired")
    check("a record frozen as current at lookup, expired since, reads expired now",
          db.standing("K9OLD", {"license": {"found": True, "expires": on(-1100),
                                             "status": {"state": "current"}}}), "expired")

    print("\n-- and 'licensed' means in force, nothing less --")
    conn = db.connect()
    me = conn.user_id
    db.set_callsign(conn, "KA7EVD")
    settings = db.get_profile(conn)["settings"]
    settings["license"] = {"callsign": "KA7EVD", "found": False,
                           "reason": "no FCC amateur record for this callsign"}
    db.save_settings(conn, settings)
    prof = db.get_profile(conn)
    check("KA7EVD on the account: standing unfound", prof["standing"], "unfound")
    check("  and not licensed", prof["licensed"], False)

    settings["license"] = {"callsign": "KA7EVD", "found": True, "expires": on(-3000)}
    db.save_settings(conn, settings)
    prof = db.get_profile(conn)
    check("were the FCC still to list it, long expired: standing expired", prof["standing"], "expired")
    check("  and still not licensed", prof["licensed"], False)

    settings["license"] = {"callsign": "KA7EVD", "found": True, "expires": on(400)}
    db.save_settings(conn, settings)
    prof = db.get_profile(conn)
    check("in force: licensed", (prof["standing"], prof["licensed"]), ("current", True))

    print("\n-- the account list carries the standing to the page --")
    from elmer.app import app
    client = app.test_client()
    client.set_cookie("elmer_user", str(me))
    settings["license"] = {"callsign": "KA7EVD", "found": False}
    db.save_settings(conn, settings)
    row = next(u for u in client.get("/api/users", environ_base=LOCAL).get_json()["users"] if u["id"] == me)
    check("the row says unfound", row.get("standing"), "unfound")
    check("  and does not say licensed", row.get("licensed"), False)

    print("\n-- the dashboard says it under the greeting, worked out today --")
    import re
    from html import unescape

    def license_line():
        page = client.get("/", environ_base=LOCAL).get_data(as_text=True)
        m = re.search(r'<p class="small license-line[^>]*>(.*?)</p>', page, re.S)
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", m.group(1)))).strip() if m else ""

    settings["license"] = {"callsign": "KA7EVD", "found": False}
    db.save_settings(conn, settings)
    check("no record: says so", "KA7EVD · no FCC record" in license_line(), True)
    settings["license"] = {"callsign": "KA7EVD", "found": True, "license_class": "General",
                           "expires": on(-1100), "uls_url": "https://example.test/uls",
                           # frozen as current on the day it was fetched
                           "status": {"state": "current", "days": 400}}
    db.save_settings(conn, settings)
    line = license_line()
    check("expired past grace: says expired and past the grace period, whatever the frozen status said",
          ("expired" in line, "past the grace period" in line, "400 days" in line), (True, True, False))
    settings["license"]["expires"] = on(-30)
    db.save_settings(conn, settings)
    line = license_line()
    check("expired within the window: says how long is left to renew, and not to transmit",
          ("left to renew" in line, "not to be used on the air" in line), (True, True))
    settings["license"]["expires"] = on(45)
    db.save_settings(conn, settings)
    line = license_line()
    check("in force with under ninety days: expiry, the days, and renew soon",
          ("expires" in line, "45 days" in line, "renew soon" in line), (True, True, True))
    settings["license"]["expires"] = on(2000)
    db.save_settings(conn, settings)
    line = license_line()
    check("in force with years to go: expiry and the days, no alarm",
          ("expires" in line, "2000 days" in line, "renew soon" in line), (True, True, False))
    settings["license"] = {"callsign": "KA7EVD", "found": False}
    db.save_settings(conn, settings)

    print("\n-- and the page draws the pill from the standing --")
    src = (Path(__file__).resolve().parents[1] / "elmer" / "static" / "users.js").read_text(encoding="utf-8")
    check("the pill is drawn from the standing", "function standingPill(" in src, True)
    check("  'licensed' only for current", "s === 'current') return '<span class=\"pill info tiny\">licensed" in src, True)
    check("  expired, cancelled and no-record each have their own word",
          all(w in src for w in ("expired &middot; renew", ">expired<", ">cancelled<", ">no FCC record<")), True)
    check("  nothing is pinned on u.licensed any more", "u.licensed ?" in src or "r.licensed ?" in src, False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

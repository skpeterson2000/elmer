#!/usr/bin/env python3
"""A license reads as of today, not as of the day it was looked up.

    python3 tests/test_license_as_of_today.py

The record is kept with the profile, and a license term runs for years -
ten, for GMRS - so the day count written into it is stale the moment it is
stored. The amateur record was already being recomputed on its way to the
page. The GMRS one was not, so a license thirty-five days from expiry went
on reporting whatever it reported the day the call was typed in, and the
band plan's "renew soon" - which it draws below ninety days - could not
fire at all.

Each service keeps its own grace and they are not the same: two years for
amateur under 47 CFR 97.21(b), none whatever for GMRS, where past the date
the license is simply gone. Telling a GMRS licensee they have two years to
renew would be telling them to transmit unlicensed.

Nothing here touches the network.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import callsign  # noqa: E402
from elmer.app import _license_now, _records_for, gmrs_license_for  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def record(service, days_out, stored_days=400):
    """A record whose dates are right and whose day count is a year stale."""
    return {"callsign": "WRAA123", "found": True, "service": service,
            "granted": "2019-01-01",
            "expires": (date.today() + timedelta(days=days_out)).isoformat(),
            "status": {"state": "current", "days": stored_days}}


def main():
    print("\n-- the stored day count is not believed --")
    check("a GMRS license 35 days out says 35, not what was stored",
          gmrs_license_for(None, {"gmrs": record("gmrs", 35)})["status"]["days"], 35)
    check("  and the amateur one, which already did",
          _license_now({"settings": {"license": record("amateur", 35)}})["status"]["days"], 35)
    check("  so the band plan's renew-soon can fire at all",
          gmrs_license_for(None, {"gmrs": record("gmrs", 35)})["status"]["days"] < 90, True)

    print("\n-- each service by its own grace --")
    for service, state in (("amateur", "grace"), ("gmrs", "expired"),
                           ("commercial", "expired")):
        check(f"expired 100 days ago, {service}",
              callsign.refresh_status(record(service, -100))["status"]["state"], state)
    check("  and GMRS names no grace date, having none",
          "grace_ends" in callsign.refresh_status(record("gmrs", 35))["status"], False)
    check("  while amateur does", 
          "grace_ends" in callsign.refresh_status(record("amateur", 35))["status"], True)

    print("\n-- what must not be touched --")
    life = {"callsign": "PG1", "found": True, "service": "commercial",
            "status": {"state": "current", "days": None, "lifetime": True}}
    check("a lifetime permit keeps its status",
          callsign.refresh_status(life)["status"]["lifetime"], True)
    check("  a record with no expiry is handed back",
          callsign.refresh_status({"callsign": "A", "found": True})["callsign"], "A")
    check("  a record never found is handed back",
          callsign.refresh_status({"callsign": "X", "found": False})["found"], False)
    check("  and nothing at all stays nothing", callsign.refresh_status(None), None)
    check("  a callook record, which carries no service, is read as amateur",
          callsign.refresh_status({"callsign": "K0A", "found": True,
                                   "expires": (date.today() - timedelta(days=100)).isoformat()}
                                  )["status"]["state"], "grace")

    print("\n-- the papers view reads them the same way --")
    check("  (papers go through refresh_status too)",
          "refresh_status" in __import__("inspect").getsource(_records_for), True)

    print("")
    print("-- and the pages that draw it read the fresh one --")
    # The Station panel used to read profile.settings.gmrs straight off the
    # record, which is the raw one: the fix above reached the band plan and
    # the papers view and went round this. A source check, because what is
    # wrong here is which variable a template names.
    here = Path(__file__).resolve().parents[1] / "elmer" / "templates"
    base = (here / "base.html").read_text(encoding="utf-8")
    home = (here / "home.html").read_text(encoding="utf-8")
    check("the Station panel does not read the raw record",
          "profile.settings.gmrs or {}" in base, False)
    check("  it reads the one worked out today", "gmrs_own" in base, True)
    check("  and the home page shows a GMRS license at all",
          "gmrs.callsign" in home, True)
    check("  saying there is no grace period after it",
          "no grace period" in home, True)
    # Guarded on the record rather than the callsign, the line printed
    # nothing for somebody who had just typed their call in and whose FCC
    # file had not been read yet - which is the one person most entitled to
    # see something back. The acknowledgement is owed to the callsign.
    check("  shown for the callsign, not for the record",
          "if gmrs.callsign" in home, True)
    check("  and not hidden when the FCC file is not here yet",
          "if gmrs.found %}" in home, False)

    print("")
    print("-- a license asked for too early settles itself --")
    # Entering a GMRS call starts the FCC file downloading and answers at
    # once: "being fetched, look again in a few minutes". The answer was
    # kept as the record and nothing ever went back for it, so looking
    # again showed the same sentence for ever - on the machine that found
    # this, fifteen seconds after the file had landed with the operator's
    # own license in it.
    import elmer.app as elmer_app
    from elmer import db as edb

    pending = {"callsign": "WRMP909", "found": False, "service": "gmrs",
               "pending": True, "reason": "the FCC's GMRS file is being fetched"}
    settled = {"callsign": "WRMP909", "found": True, "service": "gmrs",
               "granted": "05/14/2021", "expires": "05/14/2031",
               "status": {"state": "current", "days": 1693}}

    class FakeConn:
        pass

    saved = {}
    have_answer = {"gmrs": False}
    real = (elmer_app.uls.have, elmer_app.callsign.lookup,
            edb.get_profile, edb.save_settings)
    try:
        elmer_app.uls.have = lambda s: have_answer.get(s)
        elmer_app.callsign.lookup = lambda c, refresh=False: dict(settled)
        edb.get_profile = lambda conn: {"settings": {"gmrs": dict(pending),
                                                     "gmrs_call": "WRMP909"}}
        edb.save_settings = lambda conn, s: saved.update(s)

        elmer_app._settle_pending_licenses(FakeConn())
        check("with the file still absent, nothing is asked and nothing saved",
              saved, {})

        have_answer["gmrs"] = True
        elmer_app._settle_pending_licenses(FakeConn())
        check("once the file is here, the record is read again",
              (saved.get("gmrs") or {}).get("found"), True)
        check("  and kept, with its dates",
              (saved.get("gmrs") or {}).get("expires"), "05/14/2031")
    finally:
        (elmer_app.uls.have, elmer_app.callsign.lookup,
         edb.get_profile, edb.save_settings) = real

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

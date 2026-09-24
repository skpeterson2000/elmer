#!/usr/bin/env python3
"""A licence reads as of today, not as of the day it was looked up.

    python3 tests/test_licence_as_of_today.py

The record is kept with the profile, and a licence term runs for years -
ten, for GMRS - so the day count written into it is stale the moment it is
stored. The amateur record was already being recomputed on its way to the
page. The GMRS one was not, so a licence thirty-five days from expiry went
on reporting whatever it reported the day the call was typed in, and the
band plan's "renew soon" - which it draws below ninety days - could not
fire at all.

Each service keeps its own grace and they are not the same: two years for
amateur under 47 CFR 97.21(b), none whatever for GMRS, where past the date
the licence is simply gone. Telling a GMRS licensee they have two years to
renew would be telling them to transmit unlicensed.

Nothing here touches the network.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import callsign  # noqa: E402
from elmer.app import _license_now, _records_for, gmrs_licence_for  # noqa: E402

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
    check("a GMRS licence 35 days out says 35, not what was stored",
          gmrs_licence_for(None, {"gmrs": record("gmrs", 35)})["status"]["days"], 35)
    check("  and the amateur one, which already did",
          _license_now({"settings": {"license": record("amateur", 35)}})["status"]["days"], 35)
    check("  so the band plan's renew-soon can fire at all",
          gmrs_licence_for(None, {"gmrs": record("gmrs", 35)})["status"]["days"] < 90, True)

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

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

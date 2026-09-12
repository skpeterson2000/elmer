#!/usr/bin/env python3
"""What ELMER says about the law on listening, and what it refuses to say.

    python3 tests/test_monitoring.py

This is the one subject in the program where being confidently wrong does real
harm: telling somebody they are fine when they are not is worse than saying
nothing. So what is tested here is mostly restraint.

Every claim carries the citation and the official link, so the operator can
read the version that is authoritative rather than ELMER's. Anything not read
against the primary source is marked as not having been. And a state nobody
has looked at says so out loud, because an empty panel reads as "no law here",
which is the one thing it must never mean.

The content itself was checked against the statutes, and doing that changed
it: two of the five states everybody lists as banning mobile scanners turn out
to prohibit something else entirely, and New York's amateur exemption does not
cover what it is usually said to cover.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import monitoring  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\nevery statute is citable and linkable, or it is not in here")
for code, entry in sorted(monitoring.STATES.items()):
    for law in entry["statutes"]:
        check(f"{code} {law['cite']}: has a link",
              law["url"].startswith("http"), True)
        check(f"{code} {law['cite']}: says how it was checked",
              law["checked"] in (monitoring.PRIMARY, monitoring.SECONDARY), True)
        check(f"{code} {law['cite']}: primary entries quote the text",
              bool(law["quote"]) if law["checked"] == monitoring.PRIMARY else True,
              True)

print("\nevery state written down has been read against the legislature's own text")
# Indiana and Kentucky were taken from a code aggregator at first and said
# so; they were read against iga.in.gov and apps.legislature.ky.gov on
# 2026-09-11. Nothing in the table is second-hand any more, and a new entry
# that is must still say so - the check above allows it - but not these.
for code, host in (("IN", "iga.in.gov"), ("KY", "apps.legislature.ky.gov"),
                   ("FL", "flsenate.gov"), ("NY", "nysenate.gov")):
    law = monitoring.STATES[code]["statutes"][0]
    check(f"{code} is read against the primary text", law["checked"], monitoring.PRIMARY)
    check(f"  and links to the legislature, not an aggregator", host in law["url"], True)
check("no state is left on second-hand reading",
      [c for c, e in monitoring.STATES.items()
       if any(l["checked"] != monitoring.PRIMARY for l in e["statutes"])], [])
check("Indiana's reading says what the amateur exemption does not cover",
      "not the third" in monitoring.STATES["IN"]["statutes"][0]["reading"], True)
check("Kentucky's quote carries the proviso with the exemption",
      "avoid apprehension" in monitoring.STATES["KY"]["statutes"][0]["quote"], True)

print("\nthe federal part is true everywhere, so it is always given")
for state in ("MN", "Iowa", "", None):
    check(f"{state!r}: federal points present",
          len(monitoring.advice(state)["federal"]), len(monitoring.FEDERAL))
check("and every one of them is citable",
      all(p["cite"] and p["url"].startswith("http")
          for p in monitoring.FEDERAL), True)
check("decryption is one of them",
      any("ecrypt" in p["point"] for p in monitoring.FEDERAL), True)

print("\na state nobody has read says so, rather than going quiet")
iowa = monitoring.advice("Iowa")
check("not claimed as known", iowa["known"], False)
check("no statutes invented", iowa["statutes"], [])
check("and it says that is not the same as there being none",
      "not the same as there being none" in iowa["reading"], True)
check("with somewhere to start looking",
      iowa["look_here"].startswith("http"), True)

print("\nMinnesota, which is where this unit is")
mn = monitoring.advice("Minnesota")
check("found by name as well as by code", mn["known"], True)
check("same answer from the code", monitoring.advice("MN")["name"], "Minnesota")
check("both statutes carried", len(mn["statutes"]), 2)
# The condition almost nobody knows, and the reason this was worth building.
check("the licence-in-the-vehicle condition is surfaced",
      "Carry your licence" in mn.get("do_this", ""), True)
check("299C.37 is the one with the exemption",
      any("299C.37" in s["cite"] for s in mn["statutes"]), True)
check("609.856 is marked as not being a scanner law",
      any("Not a scanner law" in s["reading"] for s in mn["statutes"]), True)

print("\nwhere the popular summary is wrong, ELMER is not")
fl = monitoring.advice("FL")
check("Florida is not called a possession ban",
      "Not a possession law" in fl["reading"], True)
ny = monitoring.advice("NY")
check("New York's exemption is flagged as narrower than reported",
      "narrower" in ny["reading"], True)

print("\nan unlicensed operator is not told about a licensee's exemption")
check("no licence to carry if there is no licence",
      "do_this" in monitoring.advice("MN", licensed=False), False)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")

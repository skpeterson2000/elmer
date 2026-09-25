#!/usr/bin/env python3
"""A license from somewhere else, being used here.

    python3 tests/test_reciprocity.py

47 CFR 97.107 lets an operator holding an amateur authorisation from their
own government be the control operator of a station in the United States,
wherever a reciprocal arrangement reaches: CEPT, the IARP, or a bilateral
one, and Canada's is written into the rule itself. That is worth showing on
the band plan, because a visitor standing in a room with a radio in it has
the same question everybody else in the room has and the page had no answer
for them.

What the rule actually says is narrower than "a Canadian Extra is a US
Extra". A visitor operates under the terms of their own license and the
FCC's rules together, and in no case beyond what an Amateur Extra may do.
So the chart is a ceiling and not a set of privileges, and the page has to
say so: half an answer about the law is the dangerous half.

Three things are held down here. The chart drawn is the Extra ceiling. The
view is not a license class - it cannot be stored as one, it opens no study
pool, and it is not offered in the Station panel, because a profile that
recorded "visiting" as somebody's class would be saying something untrue
about them on every screen that shows one. And nothing prints: a sheet
headed "visiting" with a callsign on it would read as a claim about an
operator's authority in a country whose license they do not hold.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import bandplan, callsign, gating  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
POOLS = ["tech2026", "gen2023", "extra2024"]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the ceiling the rule sets --")
    check("the band plan can be asked for it", bandplan.RECIPROCAL in bandplan.CHOICES, True)
    check("  and it is named for what it is",
          bandplan.CLASS_LABELS[bandplan.RECIPROCAL], "Visiting under reciprocity")
    check("  it draws what an Amateur Extra may do, band for band",
          all(bandplan.privileges_for(b["name"], bandplan.RECIPROCAL)
              == bandplan.privileges_for(b["name"], "Extra") for b in bandplan.BANDS), True)

    print("\n-- but it is not a license class --")
    # Not in CLASSES, which is what every "which class may..." question reads,
    # and what the Station panel offers.
    check("nothing offers it as a class to hold", bandplan.RECIPROCAL in bandplan.CLASSES, False)
    check("  so a hand-edited profile carrying it opens no pool",
          sorted(gating.open_pools({"license_class": bandplan.RECIPROCAL,
                                    callsign.SOURCE: callsign.OWN}, [], POOLS)[0]),
          ["tech2026"])

    from elmer.app import app
    client = app.test_client()
    r = client.post("/api/settings", json={"license_class": bandplan.RECIPROCAL},
                    environ_base=LOCAL)
    check("and it cannot be saved as one", r.status_code, 400)
    check("  nor can anything else that is not a class",
          client.post("/api/settings", json={"license_class": "Wizard"},
                      environ_base=LOCAL).status_code, 400)
    check("  while a real class still saves",
          client.post("/api/settings", json={"license_class": "General"},
                      environ_base=LOCAL).status_code, 200)
    check("  and so does holding none",
          client.post("/api/settings", json={"license_class": bandplan.NO_LICENSE},
                      environ_base=LOCAL).status_code, 200)

    print("\n-- what the page is told --")
    got = client.get("/api/bandplan?class=reciprocal", environ_base=LOCAL).get_json()
    extra = client.get("/api/bandplan?class=Extra", environ_base=LOCAL).get_json()
    check("the view is flagged, so the page can say the rest of the rule",
          got["reciprocal"], True)
    check("  the bands are the Extra ones", got["bands"] == extra["bands"], True)
    check("  and an ordinary class is not flagged", extra["reciprocal"], False)
    # The owl is about reading above the class you hold. A visitor holds no
    # US class at all, so there is nothing for it to be above, and crying
    # wolf at somebody looking up the law that applies to them is how a
    # warning stops being read.
    client.post("/api/settings", json={"license_class": "Technician"}, environ_base=LOCAL)
    check("a Technician reading the visiting view is not scolded for it",
          client.get("/api/bandplan?class=reciprocal", environ_base=LOCAL).get_json()["above_yours"],
          False)
    check("  though reading Amateur Extra still is",
          client.get("/api/bandplan?class=Extra", environ_base=LOCAL).get_json()["above_yours"],
          True)

    print("\n-- and nothing prints --")
    r = client.post("/api/bandplan/pdf", json={"class": bandplan.RECIPROCAL},
                    environ_base=LOCAL)
    check("a chart headed 'visiting' is refused", r.status_code, 400)
    check("  the Amateur Extra chart, which is the same ceiling, is not",
          client.post("/api/bandplan/pdf", json={"class": "Extra", "layout": "card"},
                      environ_base=LOCAL).status_code, 200)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

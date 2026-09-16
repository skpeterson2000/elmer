#!/usr/bin/env python3
"""The two programmes' rules, pinned to the documents they were read from.

    python3 tests/test_activations.py

Everything else ELMER states about the outside world is physics or law, and
both hold still. These do not: POTA and SOTA are run by people who change
their own rules, so this file records what the documents said when they were
read, and the date on which somebody read them. When a rule changes, this is
what should fail.

The numbers are the whole point. Ten QSOs and four QSOs are not
interchangeable, one QSO makes a SOTA activation while four make it score,
and a station that is fine in a park is a disqualification on a summit. An
operator who packs for the wrong one of those finds out at the top.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import activations as A, reachout  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the counts, which are not interchangeable --")
    check("POTA wants ten QSOs", A.POTA["qualifies"], 10)
    check("  in one UTC day", "UTC day" in A.POTA["qualifies_note"], True)
    check("SOTA's points want four", A.SOTA["qualifies"], 4)
    check("  each with a different station",
          "different station" in A.SOTA["qualifies_note"], True)
    check("  though one QSO already makes it an activation",
          "One QSO" in A.SOTA["qualifies_note"], True)

    print("\n-- neither counts a repeater, and both count a satellite --")
    for prog in (A.POTA, A.SOTA):
        check(f"{prog['key']}: no terrestrial repeaters",
              prog["repeaters"], False)
        check(f"{prog['key']}: satellites do count", prog["satellites"], True)

    print("\n-- and the vehicle is the difference between them --")
    check("a park allows one", A.POTA["vehicle"], True)
    check("a summit does not", A.SOTA["vehicle"], False)
    check("  because everything is carried and battery powered",
          "carried up" in A.SOTA["power"], True)
    check("  and a generator is named as forbidden",
          "generator" in A.SOTA["power"], True)
    check("the activation zone is the operator's position, not the antenna's",
          "where the operator is" in A.SOTA["where"], True)
    check("  typically 25 metres, and the Association's to set",
          "25 metres" in A.SOTA["where"]
          and "Association" in A.SOTA["where"], True)
    check("a park's boundary covers the equipment too",
          "all of the equipment" in A.POTA["where"], True)

    print("\n-- every gear box on Make Contact has a verdict --")
    for key in reachout.GEAR:
        check(f"{key} is judged", key in A.GEAR_VERDICTS, True)
    for key, row in A.GEAR_VERDICTS.items():
        for prog in ("pota", "sota"):
            check(f"  {key} on {prog}", row[prog] in A.VERDICT_RANK, True)

    print("\n-- and the disqualifying one is reported first --")
    mixed = ["hf_wire", "ht", "hf_mobile", "gmrs"]
    report = A.gear_report("sota", mixed)
    check("worst news first", report[0]["key"], "hf_mobile")
    check("  and it is the vehicle whip that is forbidden",
          report[0]["verdict"], "forbidden")
    check("the same kit is fine in a park",
          A.blockers("pota", mixed), [])
    check("GMRS earns credit in neither",
          A.GEAR_VERDICTS["gmrs"]["pota"], "no credit")

    print("\n-- and every rule says where it was read --")
    for prog in (A.POTA, A.SOTA):
        check(f"{prog['key']} cites a document",
              bool(prog["source"].strip()), True)
        check(f"  and the date it was read", bool(prog["read"]), True)

    print("\n-- whose land it is: every caution carries its citation --")
    check("the land's rules are a list with a source and a date",
          (bool(A.LAND), bool(A.LAND_SOURCE), bool(A.LAND_READ)), (True, True, True))
    check("  and the four federal owners and the states are all there",
          [r["who"].split(" (")[0] for r in A.LAND],
          ["Any park, any owner", "National Parks", "National Forests",
           "Corps of Engineers lakes", "National Wildlife Refuges",
           "State parks, state forests, wildlife areas, county parks"])
    cites = [r["cite"] for r in A.LAND]
    # The sections quoted are the ones read from the eCFR on the day named:
    # a caution that names the wrong section is worse than none.
    for want in ("36 CFR 1.5(a)", "2.12(a)(1)", "36 CFR 261.10(a)", "36 CFR 327.20",
                 "327.15(a)", "50 CFR 26.21(a)"):
        check(f"  cites {want}", any(want in c for c in cites), True)
    check("  every quotation is closed", all(r["what"].count('"') % 2 == 0 for r in A.LAND), True)
    check("  and the states are not guessed at",
          "does not guess" in A.LAND[-1]["what"], True)

    print("\n-- the band on the page is the list's band, not only the sheet's --")
    from elmer.app import app
    c = app.test_client()
    c.post("/api/settings", json={"location": {"lat": 46.60, "lon": -94.31, "short": "Pequot Lakes", "grid": "EN36"}, "units": "imperial"})
    d = c.get("/api/activations?inner=0&outer=50").get_json()
    farthest = max([p["km"] for p in d["parks"] + d["summits"]] or [0])
    check("nothing listed beyond fifty miles when the box says fifty", farthest <= d["band"]["outer_km"] + 0.01, True)
    check("  and the count is the band's alone - nothing beyond it is tallied or sent", "held_all" in d, False)
    d2 = c.get("/api/activations?inner=30&outer=120").get_json()
    nearest = min([p["km"] for p in d2["parks"]] or [d2["band"]["inner_km"]])   # an empty band lists nothing at all
    check("a band that starts at thirty lists nothing nearer", nearest >= d2["band"]["inner_km"] - 0.01, True)
    d3 = c.get("/api/activations?outer=50&from=Duluth, MN").get_json()
    check("a place typed is the centre", d3["qth"], "Duluth")
    d4 = c.get("/api/activations?outer=50&from=Nowhereville").get_json()
    check("  and one that cannot be found falls back to here, and says so", (d4["qth"], "could not find" in (d4["band"]["note"] or "")), ("Pequot Lakes", True))

    print("\n-- planning a trip: the place typed is the centre of the fetch as well as the list --")
    from elmer import references
    calls = []
    real_fetch = references.fetch
    def fake_fetch(lat, lon, label="here", radius_km=None):
        calls.append((round(lat, 2), round(lon, 2), label))
        return {"label": label, "radius_km": 350, "parks": [{"ref": "US-4321"}], "summits": [], "missing": []}
    references.fetch = fake_fetch
    local = {"REMOTE_ADDR": "127.0.0.1"}
    d = c.get("/api/activations?inner=0&outer=80&from=EL16hq").get_json()
    check("a grid square typed centres the list there", (d["qth"], all(p["km"] <= d["band"]["outer_km"] for p in d["parks"])), ("EL16HQ", True))
    check("  and the bundled national units near it are listed before any fetch", any(p["ref"] == "US-0690" for p in d["parks"]), True)
    r = c.post("/api/activations/prepare", json={"from": "EL16hq"}, environ_base=local)
    check("the fetch goes around the place typed, labelled by it", (r.status_code, calls[-1]), (200, (26.69, -97.38, "EL16HQ")))
    r = c.post("/api/activations/prepare", json={}, environ_base=local)
    check("  and around here when the box is empty", calls[-1][2], "Pequot Lakes")
    r = c.post("/api/activations/prepare", json={"from": "Nowhereville"}, environ_base=local)
    check("  a place that cannot be found is refused, not fetched around here", (r.status_code, len(calls)), (400, 2))
    references.fetch = real_fetch

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

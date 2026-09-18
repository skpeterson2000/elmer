#!/usr/bin/env python3
"""The panel of sondes that vote: named, faded rather than vanished, and graded.

    python3 tests/test_voters.py

Two units in one vehicle disagreed by a third on foF2 because one had a
third sonde in its list and the other did not. Now a station that misses
a cycle keeps its last reading, held and weighted by its age; the
calibration names its voters and says how far it would move if one
dropped out; the ledger keeps the panel hour by hour; and the weekly
report says how steady it was. Nothing here reaches the network.
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import forecastlog as F, ionosonde as I, propagation as P  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


NOW = datetime(2026, 9, 17, 23, 50, tzinfo=timezone.utc)


def sonde(name, lat, lon, fof2, age_min=10, m3000=2.9, held=False):
    return {"name": name, "lat": lat, "lon": lon, "fof2": fof2, "hmf2": 280.0, "mufd": fof2 * m3000,
            "m3000": m3000, "confidence": 90, "age_minutes": age_min, "held": held,
            "time": (NOW - timedelta(minutes=age_min)).isoformat()}


def main():
    lat, lon = 46.6, -94.3
    print("\n-- the calibration names its voters and says how fragile it is --")
    two = [sonde("Boulder", 40.0, -105.3, 5.0), sonde("Millstone Hill", 42.6, -71.5, 5.4)]
    three = two + [sonde("Eglin", 30.5, -86.5, 7.6, age_min=30)]
    c2, c3 = P.calibration(97.0, lat, lon, when=NOW, sondes=two), P.calibration(97.0, lat, lon, when=NOW, sondes=three)
    check("two voters, named nearest first", [v["name"] for v in c2["voters"]], ["Boulder", "Millstone Hill"])
    check("  each with its distance, age, reading and weight", all(k in c2["voters"][0] for k in ("km", "age_minutes", "fof2", "vote", "weight", "held")), True)
    check("a third voter moves the answer", c3["factor"] != c2["factor"], True)
    check("  and the fragility says how much one dropping out could move it", c3["fragility_pct"] > 0 and c2["fragility_pct"] > 0, True)
    check("  a single voter has no fragility figure to give", P.calibration(97.0, lat, lon, when=NOW, sondes=two[:1])["fragility_pct"], 0.0)

    print("\n-- a vote fades with age --")
    fresh = P.calibration(97.0, lat, lon, when=NOW, sondes=[sonde("Boulder", 40.0, -105.3, 5.0, age_min=5), sonde("Eglin", 30.5, -86.5, 7.6, age_min=5)])
    stale = P.calibration(97.0, lat, lon, when=NOW, sondes=[sonde("Boulder", 40.0, -105.3, 5.0, age_min=5), sonde("Eglin", 30.5, -86.5, 7.6, age_min=170)])
    w = lambda c, name: next(v["weight"] for v in c["voters"] if v["name"] == name)
    check("a reading near three hours old carries a fraction of a fresh one's weight", w(stale, "Eglin") < 0.3 * w(fresh, "Eglin"), True)
    check("  and the nearer, fresher station's weight is unchanged", w(stale, "Boulder"), w(fresh, "Boulder"))

    print("\n-- a station that misses a cycle is held, not dropped --")
    tmp = Path(tempfile.mkdtemp(prefix="elmer-sondes-"))
    I.CACHE, I.MEMORY = tmp, tmp / "stations-memory.json"
    first = [sonde("Boulder", 40.0, -105.3, 5.0), sonde("Millstone Hill", 42.6, -71.5, 5.4), sonde("Eglin", 30.5, -86.5, 7.6)]
    merged = I._with_memory(first, NOW, write=True)
    check("the first fetch is remembered", (len(merged), I.MEMORY.is_file()), (3, True))
    later = NOW + timedelta(minutes=40)
    second = [sonde("Boulder", 40.0, -105.3, 5.1), sonde("Millstone Hill", 42.6, -71.5, 5.3)]
    merged = I._with_memory(second, later, write=True)
    held = [s for s in merged if s.get("held")]
    check("a fetch without Eglin still carries Eglin, held, aged forty minutes more", ([s["name"] for s in held], held[0]["age_minutes"]), (["Eglin"], 50))
    check("  the fresh readings are the fresh ones", next(s["fof2"] for s in merged if s["name"] == "Boulder"), 5.1)
    much_later = NOW + timedelta(hours=3, minutes=20)
    merged = I._with_memory(second, much_later, write=True)
    check("  and past three hours the held reading ages out", [s["name"] for s in merged], ["Boulder", "Millstone Hill"])

    print("\n-- the ledger keeps the panel, and grades its steadiness --")
    F.LEDGER = Path(tempfile.mkdtemp(prefix="elmer-ledger-"))
    hour = NOW.replace(minute=0)
    panels = [(two, 0), (two, 1), (three, 2), (three, 3), (two, 4), (two, 5)]
    for sondes, h in panels:
        cal = P.calibration(97.0, lat, lon, when=hour + timedelta(hours=h), sondes=sondes)
        snap = {"muf_source": "regional", "muf": 20.0, "fof2": 6.0, "calibration": cal}
        F.measured(snap, now=hour + timedelta(hours=h))
    v = F.voter_stability(2, now=hour + timedelta(hours=6))
    check("six readings, two voters typically", (v["readings"], v["voters_typical"]), (6, 2))
    check("  the set of voters changed twice", v["set_changes"], 2)
    check("  and the correction moved more when it did than when it did not", v["swing_pct_when_changed"] > (v["swing_pct_otherwise"] or 0.0), True)
    check("  a regional reading is written for the panel but not graded as a measurement",
          ("voters" in F._load(F._day(hour)), F._load(F._day(hour)).get("measured")), (True, {}))

    print("\n-- and the report says so, naming no station --")
    from elmer import fieldreport
    text = fieldreport.build(now=hour + timedelta(hours=6))
    body = text if isinstance(text, str) else json.dumps(text)
    check("the report has the panel's steadiness", "panel of sondes" in body and "set of voters changed 2" in body, True)
    check("  and no sonde's name", ("Boulder" in body, "Millstone" in body, "Eglin" in body), (False, False, False))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Every position says where it came from, and is ranked by what it can vouch for.

    python3 tests/test_position_sources.py

A station whose operator had set Pequot Lakes was put in Minneapolis:
TowerWitch falls back to Minneapolis when it has no receiver, its broadcast
could not say so, and ELMER called every TowerWitch packet a "3D fix" and let
it outrank the typed QTH. What is held here:

  - each source is a fix, typed, or unvouched, with its accuracy and a label
    in words - and the label carries no coordinates and no town;
  - a fix beats the typed QTH (a mobile station's typed QTH is the stale one),
    and the typed QTH beats anything unvouched;
  - two positions farther apart than max(5 km, 3 x their accuracies) are
    flagged, not silently resolved;
  - TowerWitch's packet is read for the fix fields it may carry
    (docs/towerwitch-broadcast.md), and without them is not called a fix;
  - another ELMER passes on what its own source vouches for;
  - the self-check says which position is used, and TowerWitch's town is
    redacted in a report like any other place the unit holds.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
PEQUOT = (46.6030, -94.3094)
MINNEAPOLIS = (44.9778, -93.2650)


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def at(where, **more):
    return {"lat": where[0], "lon": where[1], "read_at": time.time(), **more}


def main():
    from elmer import discovery, gps, provenance as P, towerwitch

    print("\n-- what each source can vouch for --")
    gpsd = at(PEQUOT, source="gps", mode=3, sats=9, hdop=1.2)
    v = P.vouch(gpsd)
    check("gpsd with a 3D fix is a fix, with its accuracy", (v["class"], round(v["accuracy_m"])), ("fix", 6))
    check("  and says so in words", v["label"], "gpsd, 3D fix, 9 satellites, ±6 m")
    check("a phone better than 100 m is a fix", P.vouch(at(PEQUOT, source="phone", mode=3, hdop=2.0))["class"], "fix")
    check("  a phone with no accuracy is not", P.vouch(at(PEQUOT, source="phone", mode=2))["class"], "unvouched")
    check("  nor one too coarse", P.vouch(at(PEQUOT, source="phone", mode=2, hdop=40))["class"], "unvouched")
    old = towerwitch.parse(json.dumps({"source": "TowerWitch", "gps_lat": MINNEAPOLIS[0],
                                       "gps_lon": MINNEAPOLIS[1], "timestamp": "t"}).encode())
    check("TowerWitch's packet as it is today: no mode invented for it", old["mode"], None)
    check("  and not a fix - no fix quality given", (P.vouch(old)["class"], P.vouch(old)["label"]),
          ("unvouched", "TowerWitch - no fix quality given"))
    new = towerwitch.parse(json.dumps({"source": "TowerWitch", "gps_lat": PEQUOT[0], "gps_lon": PEQUOT[1],
                                       "fix_mode": 3, "sats": 8, "hdop": 1.1, "fallback": False}).encode())
    check("TowerWitch saying it has a 3D fix is a fix", (P.vouch(new)["class"], new["sats"], new["hdop"]),
          ("fix", 8, 1.1))
    fell = towerwitch.parse(json.dumps({"source": "TowerWitch", "gps_lat": MINNEAPOLIS[0], "gps_lon": MINNEAPOLIS[1],
                                        "fix_mode": 3, "fallback": True}).encode())
    check("  and saying it fell back is not, whatever mode it claims", P.vouch(fell)["class"], "unvouched")
    check("TowerWitch's state file is its last known position, not a fix",
          P.vouch(at(MINNEAPOLIS, source="towerwitch", last_known=True))["class"], "unvouched")
    check("a browser within 100 m is a fix", P.vouch(at(PEQUOT, source="browser", accuracy_m=25))["class"], "fix")
    guess = P.vouch(at(MINNEAPOLIS, source="browser", accuracy_m=3500))
    check("  a coarse one is said to be a possible IP or Wi-Fi guess",
          (guess["class"], guess["label"]),
          ("unvouched", "the browser's position - may be an IP or Wi-Fi guess, ±3.5 km"))
    check("a typed grid square is typed, as sure as six characters",
          (P.vouch({"lat": 46.6, "lon": -94.3, "kind": "grid", "grid": "EN26uo"}, saved=True)["class"],
           P.vouch({"lat": 46.6, "lon": -94.3, "kind": "grid", "grid": "EN26uo"}, saved=True)["accuracy_m"]),
          ("typed", 4000.0))
    check("a saved sextant fix is a fix", P.vouch({"lat": 46.6, "lon": -94.3, "kind": "celestial"}, saved=True)["class"], "fix")
    labels = [P.vouch(p)["label"] for p in (gpsd, old, new, fell, at(MINNEAPOLIS, source="browser", accuracy_m=3500))]
    check("no label carries a coordinate or a town",
          [lb for lb in labels if any(w in lb for w in ("46.", "94.", "44.", "93.", "Minneapolis", "Pequot"))], [])

    print("\n-- ranked by what they vouch for --")
    typed = {"lat": PEQUOT[0], "lon": PEQUOT[1], "kind": "town", "short": "Pequot Lakes", "name": "Pequot Lakes"}
    chosen, acc = P.choose(typed, old)
    check("the typed QTH beats TowerWitch's unvouched Minneapolis", (chosen is typed, acc["class"]), (True, "typed"))
    check("  and the two are said to disagree",
          (len(acc["disagree"]), acc["disagree"][0]["with"], round(acc["disagree"][0]["km"])),
          (1, "TowerWitch - no fix quality given", 198))
    away = at((47.75, -90.33), source="gps", mode=3, sats=10, hdop=0.9)
    chosen, acc = P.choose(typed, away)
    check("a mobile station's fix beats its stale typed QTH", (chosen is away, acc["class"]), (True, "fix"))
    check("  and the typed QTH it left behind is said to disagree", acc["disagree"][0]["with"].startswith("a typed place name"), True)
    chosen, acc = P.choose({}, old)
    check("with nothing typed, an unvouched position is used - and said to be",
          (chosen is old, acc["class"]), (True, "unvouched"))
    check("with nothing at all, nothing", P.choose({}, None), ({}, None))

    print("\n-- disagreement: max(5 km, 3 x their accuracies) --")
    base = at(PEQUOT, source="gps", mode=3, eph=5)
    near = at((PEQUOT[0] + 0.036, PEQUOT[1]), source="gps", mode=3, eph=5)        # about 4 km north
    far = at((PEQUOT[0] + 0.054, PEQUOT[1]), source="gps", mode=3, eph=5)         # about 6 km north
    check("4 km apart, both precise: they agree", P.disagreement(base, near, P.vouch(base), P.vouch(near)), None)
    check("6 km apart, both precise: they disagree",
          bool(P.disagreement(base, far, P.vouch(base), P.vouch(far))), True)
    coarse = at((PEQUOT[0] + 0.072, PEQUOT[1]), source="browser", accuracy_m=3000)  # 8 km, stated 3 km
    check("8 km apart with 3 km stated: within 9 km, so they agree",
          P.disagreement(base, coarse, P.vouch(base), P.vouch(coarse)), None)

    print("\n-- the probe keeps the best, not the first to answer --")
    real = (gps.read_fix, towerwitch.current, discovery.borrowed_fix)
    import elmer.phonegps as phonegps
    import elmer.repeaters as repeaters
    real_phone, real_last = phonegps.current, repeaters.last_position
    try:
        phone = at(PEQUOT, source="phone", mode=3, hdop=1.5, **{"from": "10.0.0.9 (phone)"})
        gps.read_fix = lambda host=None, port=None, timeout=None: None
        towerwitch.current = lambda: old
        phonegps.current = lambda: phone
        discovery.borrowed_fix = lambda: None
        repeaters.last_position = lambda path=None: None
        got = gps._look("127.0.0.1", 2947)
        check("a phone's fix is kept over TowerWitch's broadcast that says nothing of its fix",
              got["source"], "phone")
        check("  and both are kept, for saying when they disagree",
              sorted(p["source"] for p in gps.heard()), ["phone", "towerwitch-net"])
    finally:
        gps.read_fix, towerwitch.current, discovery.borrowed_fix = real
        phonegps.current, repeaters.last_position = real_phone, real_last

    print("\n-- another ELMER passes on what its source vouches for --")
    wire = discovery._payload("u1", "Duluth", "http://x", "v", new, {})
    peer = discovery.parse(wire, "10.0.0.7")
    check("the announcement carries the class and the label",
          (peer["gps"]["vouch"], peer["gps"]["label"]), ("fix", "TowerWitch's receiver, 3D fix, 8 satellites, ±6 m"))
    wire = discovery._payload("u1", "Duluth", "http://x", "v", old, {})
    peer = discovery.parse(wire, "10.0.0.7")
    real_hood = discovery.neighbourhood

    class Hood:
        def with_fix(self):
            return {"name": "Duluth", "gps": peer["gps"]}
    discovery.neighbourhood = lambda: Hood()
    try:
        borrowed = discovery.borrowed_fix()
    finally:
        discovery.neighbourhood = real_hood
    check("relaying TowerWitch's unvouched position, it stays unvouched",
          (P.vouch(borrowed)["class"], P.vouch(borrowed)["label"]),
          ("unvouched", "another ELMER, relaying TowerWitch - no fix quality given"))

    print("\n-- qth_for, the self-check and the report --")
    from elmer import app as A, bugreport, db, diagnostics
    conn = db.connect()
    settings = db.get_profile(conn)["settings"]
    settings["location"] = typed
    db.save_settings(conn, settings)
    real_place, real_heard, real_enabled = gps.place, gps.heard, gps.enabled
    try:
        gps.enabled = lambda c=None: True
        gps.place = lambda c=None: dict(old, grid="EN34", short="EN34", name="EN34", kind="towerwitch-net")
        gps.heard = lambda: [old]
        where = A.qth_for(conn, db.get_profile(conn))
        check("qth_for keeps the typed Pequot Lakes over TowerWitch's Minneapolis",
              (where["short"], where["position"]["class"]), ("Pequot Lakes", "typed"))
        check("  and carries the disagreement", len(where["position"]["disagree"]), 1)
        diagnostics._collected = []
        real_look = gps._look
        gps._look = lambda host, port: None
        try:
            diagnostics.check_position()
        finally:
            gps._look = real_look
        line = next(r for r in diagnostics._collected if r["label"] == "position used")
        diagnostics._collected = None
        check("the self-check says which is used and what disagrees",
              (line["state"], line["detail"].startswith("from a typed place name"),
               "TowerWitch - no fix quality given is 198 km from it" in line["detail"]),
              ("warn", True, True))
    finally:
        gps.place, gps.heard, gps.enabled = real_place, real_heard, real_enabled
    repeaters.last_position = lambda path=None: {"lat": MINNEAPOLIS[0], "lon": MINNEAPOLIS[1],
                                                  "town": "Minneapolis, Minnesota", "age_s": 3600}
    try:
        calls, places = bugreport.held_names(conn)
        text = bugreport.redact("TowerWitch last knew itself at Minneapolis, Minnesota (44.9778, -93.2650)",
                                places=places, callsigns=calls)
    finally:
        repeaters.last_position = real_last
    check("TowerWitch's town is redacted in a report, with its coordinates",
          text, "TowerWitch last knew itself at [place] ([coord], [coord])")
    conn.close()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The pages say which position they work from, and Locate me asks before
it keeps a guess.

    python3 tests/test_position_labels.py

What is held here:

  - band conditions work from the ranked position (a fix before the typed
    QTH, the typed QTH before anything unvouched) and say which, with any
    disagreement - they used the typed QTH alone while the band plan
    followed the fix;
  - reach-out and the Lab label every source, not only gpsd;
  - Locate me keeps the browser's accuracy, and a browser guess coarser than
    100 m, or a position the server says nobody vouches for, is shown for
    what it is and taken only if the operator says so.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
ROOT = Path(__file__).resolve().parents[1]
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import db, gps, propagation, towerwitch
    from elmer.app import app

    print("\n-- band conditions say where they are for --")
    conn = db.connect()
    settings = db.get_profile(conn)["settings"]
    settings["location"] = {"lat": 46.603, "lon": -94.3094, "kind": "town", "grid": "EN26uo",
                            "short": "Pequot Lakes", "name": "Pequot Lakes"}
    db.save_settings(conn, settings)
    conn.commit()
    old = towerwitch.parse(json.dumps({"source": "TowerWitch", "gps_lat": 44.9778,
                                       "gps_lon": -93.265}).encode())
    real = (gps.place, gps.heard, gps.enabled, propagation.snapshot)
    try:
        gps.enabled = lambda c=None: True
        gps.place = lambda c=None: dict(old, grid="EN34ix", short="EN34ix", name="EN34ix", kind="towerwitch-net",
                                        age_s=1.0)
        gps.heard = lambda: [old]
        propagation.snapshot = lambda lat=None, lon=None, force=False: {
            "ok": True, "lat": lat, "lon": lon, "bands": [], "vhf": {}, "elevation": None}
        d = app.test_client().get("/api/propagation", environ_base=LOCAL).get_json()
        where = d.get("where") or {}
        check("worked from the typed Pequot Lakes, not TowerWitch's Minneapolis",
              (where.get("short"), round(d.get("lat") or 0, 2)), ("Pequot Lakes", 46.6))
        check("  said to be the typed QTH", where["position"]["label"], "a typed place name, ±3.0 km")
        check("  and TowerWitch's position said to disagree",
              [x["with"] for x in where["position"]["disagree"]], ["TowerWitch - no fix quality given"])
        away = {"lat": 47.75, "lon": -90.33, "source": "gps", "mode": 3, "sats": 10, "hdop": 0.9,
                "read_at": time.time()}
        gps.place = lambda c=None: dict(away, grid="EN47", short="EN47", name="EN47", kind="gps", age_s=1.0)
        gps.heard = lambda: [away]
        d = app.test_client().get("/api/propagation", environ_base=LOCAL).get_json()
        check("a mobile station's fix beats its stale typed QTH here too",
              (round(d.get("lat") or 0, 2), d["where"]["position"]["class"]), (47.75, "fix"))
    finally:
        gps.place, gps.heard, gps.enabled, propagation.snapshot = real
        conn.close()

    print("\n-- every source labelled on the pages --")
    prop = (ROOT / "elmer/static/propagation.js").read_text(encoding="utf-8")
    reach = (ROOT / "elmer/static/reachout.js").read_text(encoding="utf-8")
    lab = (ROOT / "elmer/static/lab.js").read_text(encoding="utf-8")
    check("band conditions say where they are worked from, and what disagrees",
          ("Worked from <b>" in prop, "w.disagree" in prop), (True, True))
    check("reach-out labels every source, not only gpsd",
          ("d.qth_source === 'gps'" in reach, "escapeHTML(pos.label)" in reach), (False, True))
    check("the Lab says any source that is not the QTH on file",
          ("if (d.qth_source !== 'gps') return '';" in lab, "pos.class === 'typed'" in lab), (False, True))
    tpl = (ROOT / "elmer/templates/lab.html").read_text(encoding="utf-8")
    check("the Lab's QTH badge no longer claims to be the saved QTH",
          ('title="your saved QTH"' in tpl, "qth.position.label" in tpl), (False, True))

    print("\n-- Locate me keeps what the browser said, and asks about a guess --")
    js = (ROOT / "elmer/static/elmer.js").read_text(encoding="utf-8")
    check("the browser's accuracy is kept, with its source",
          ("latitude: lat, longitude: lon, accuracy" in js, "source: 'browser'" in js), (True, True))
    check("a browser guess coarser than 100 m, or an unvouched server position, is asked about",
          ("const FIX_METRES = 100;" in js, "place.vouch !== 'unvouched'" in js, "window.confirm(" in js), (True, True, True))
    check("  both ways Locate me answers go through the question",
          js.count("confirmUnvouched(") >= 3, True)
    setup = (ROOT / "elmer/static/setup.js").read_text(encoding="utf-8")
    check("first-run setup saves where its position came from",
          ("source: fix.source" in setup, "accuracy_m: fix.accuracy_m" in setup), (True, True))

    from elmer import provenance as P
    saved = {"lat": 44.98, "lon": -93.27, "kind": "city", "source": "browser", "browser": True, "accuracy_m": 3500}
    check("a coarse browser guess saved as the QTH ranks as unvouched, and says so",
          (P.vouch(saved, saved=True)["class"], "IP or Wi-Fi" in P.vouch(saved, saved=True)["label"]),
          ("unvouched", True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

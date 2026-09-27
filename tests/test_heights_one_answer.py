#!/usr/bin/env python3
"""One height, one SWR: the Lab's heights table and the SWR curve beside it
agree.

    python3 tests/test_heights_one_answer.py

The Lab lists the heights where a dipole's feed does something worth knowing
- the 50 ohm match near 0.16 of a wave, the natural 73, the 98 ohm high point
- with the SWR each gives. Beside it the SWR curve was drawn at the
free-space 73 ohms whatever the height, so at the match height the table
said 1.0 and the curve said 1.46: one page, two answers. The curve now reads
the resistance the table prints for the same height. What is held here:

  - at every landmark height in the table, the curve's lowest SWR is the
    table's SWR, and the pattern answer's resistance is the table's, for a
    flat dipole and for an inverted V at two droops;
  - the answer says where its resistance came from: the height, for a
    dipole or a V; the antenna type's own, for anything the table does not
    describe;
  - a low wire's lower resistance narrows its 2:1 bandwidth, since the
    wire's reactance slope is its own and the ground only moves the
    resistance;
  - the sweep at the foot of the tab, handed the same resistance, gives the
    same SWR;
  - the build sheet reads the same resistance through the same function.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer.app import app
    c = app.test_client()
    c.set_cookie("elmer_user", "1")
    mhz = 7.15

    for kind, droop in (("dipole", None), ("invertedv", 35.0), ("invertedv", 45.0)):
        label = kind if droop is None else f"{kind} at {droop:.0f} degrees"
        print(f"\n-- {label}, 40 m: the table and the curve --")
        q = f"/api/antenna-advice?mhz={mhz}&kind={kind}&use=dx" + (f"&droop={droop}" if droop else "")
        adv = c.get(q, environ_base=LOCAL).get_json() or {}
        rows = adv.get("heights") or []
        check("the table has landmark heights", len(rows) > 0, True)
        swr_off, r_off = [], []
        for row in rows:
            p = f"/api/pattern?type={kind}&mhz={mhz}&height={row['wire_ft']}" + (f"&droop={droop}" if droop else "")
            d = c.get(p, environ_base=LOCAL).get_json() or {}
            low = min(pt["swr"] for pt in d.get("swr") or [{"swr": 99}])
            if round(low, 1) != row["swr"]:
                swr_off.append((row["what"], row["swr"], round(low, 2)))
            if abs((d.get("feed_r") or 0) - row["ohms"]) > 1.0:
                r_off.append((row["what"], row["ohms"], d.get("feed_r")))
            if row is rows[0]:
                check("  the answer says the resistance came from the height", d.get("feed_r_from"), "height")
                # The sweep at the foot of the tab, handed the same resistance
                # as the Lab hands it, bottoms out at the same SWR.
                v = c.get(f"/api/vna/sweep?kind={kind}&f0={mhz}&center={mhz}&span=0.14&r={d['feed_r']}",
                          environ_base=LOCAL).get_json() or {}
                best = min(pt["swr"] for pt in v.get("rows") or [] if pt["swr"] is not None) if v.get("rows") else None
                check("  and the sweep at the foot of the tab agrees", round(best, 1) if best else best, row["swr"])
        print(f"     {len(rows)} landmark heights: " + ", ".join(f"{r['what']} {r['wire_ft']} ft SWR {r['swr']}" for r in rows))
        check("  at every one the curve's lowest SWR is the table's", swr_off, [])
        check("  and the pattern's resistance is the table's, to an ohm", r_off, [])

    print("\n-- a type the table does not describe keeps its own resistance --")
    d = c.get(f"/api/pattern?type=quarter&mhz={mhz}&height=0", environ_base=LOCAL).get_json() or {}
    check("a quarter-wave vertical's resistance is its type's", (d.get("feed_r_from"), d.get("feed_r")), ("type", 36.0))

    print("\n-- a low wire is narrower --")
    low = c.get(f"/api/pattern?type=dipole&mhz={mhz}&height=14", environ_base=LOCAL).get_json() or {}
    high = c.get(f"/api/pattern?type=dipole&mhz={mhz}&height=45", environ_base=LOCAL).get_json() or {}
    print(f"     14 ft: {low.get('feed_r')} ohms, {low['bandwidth']['khz']} kHz under 2:1; "
          f"45 ft: {high.get('feed_r')} ohms, {high['bandwidth']['khz']} kHz")
    check("the dipole at 14 ft has a lower resistance than at 45", low["feed_r"] < high["feed_r"], True)
    check("  and a narrower 2:1 bandwidth", low["bandwidth"]["khz"] < high["bandwidth"]["khz"], True)

    print("\n-- the build sheet reads the same resistance --")
    src = (ROOT / "elmer" / "antennapdf.py").read_text(encoding="utf-8")
    check("the sheet asks antenna_advice.feed_r_at, as the Lab's curve does",
          "antenna_advice.feed_r_at(" in src and "r=feed_r" in src, True)
    from elmer import antennapdf
    pdf = antennapdf.build("dipole", mhz, 22.5, "wire14")
    check("  and still builds", pdf[:5], b"%PDF-")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

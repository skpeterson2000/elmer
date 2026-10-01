#!/usr/bin/env python3
"""The V-beam and the rhombic: long horizontal wires, worked out leg by leg.

    python3 tests/test_long_wires.py

Both are summed by the same travelling-wave arithmetic as the terminated vee
(patterns.py): straight legs carrying a current, each with its ground
reflection. The rhombic is two paths of two legs, fed from opposite sides and
ended in a resistor; the V is two open legs, each carrying its outgoing wave
and that wave reflected from the open end - the standing wave as two
travelling ones. What is held here:

  - the V fires both ways along the line that halves it, and the rhombic one
    way, toward its resistor;
  - both gain with longer legs, and the rhombic, terminated, out-gains a V of
    the same legs in spite of the half its resistor takes;
  - the V is laid at ATP 6-02.53's Table E-3 angle for its legs, row for row,
    and straight between the rows;
  - the advice knows which has a resistor, how each is fed, and how much
    ground each takes;
  - the Lab's menu files them by whether they are aimed, and which way.
"""
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import antenna_advice as A  # noqa: E402
from elmer import manuals, patterns as P  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def lobe(kind, mhz, leg_ft, height_ft):
    """Free-space gain, the best elevation, and front against back there."""
    k = P.laid(kind, length_ft=leg_ft, height_ft=height_ft, mhz=mhz)
    h = height_ft / (983.571 / mhz)
    gain = P._travelling_table(k, h)["gain_dbi"]
    elev = max(P.travelling_envelope(k, h), key=lambda r: r[1])[0]
    front, back = P.travelling_raw(k, h, elev, 0), P.travelling_raw(k, h, elev, 180)
    return gain, elev, 20 * math.log10(front / max(back, 1e-9))


def main():
    print("-- which way each fires --")
    v_gain, v_elev, v_fb = lobe("vbeam", 14.2, 140, 40)
    r_gain, r_elev, r_fb = lobe("rhombic", 14.2, 210, 50)
    check("a V-beam fires both ways alike along its bisector (front to back within 1 dB)", abs(v_fb) < 1.0, True)
    check("a rhombic fires one way, toward the resistor (more than 15 dB front to back)", r_fb > 15.0, True)
    check("both throw a low lobe, under 30 degrees, as long-path antennas do", (v_elev < 30, r_elev < 30), (True, True))

    print("\n-- longer legs, more gain; the terminated diamond out-gains the open V --")
    short, _, _ = lobe("vbeam", 14.2, 70, 40)
    long_, _, _ = lobe("vbeam", 14.2, 280, 40)
    check("a V of four wavelengths of leg beats one of one", long_ > short, True)
    same_v, _, _ = lobe("vbeam", 14.2, 210, 50)
    check("a rhombic out-gains a V of the same legs, after its resistor's half", r_gain > same_v, True)
    check("a V of two wavelengths of leg is a beam's gain - 6 to 9 dBi in free space", 6.0 <= v_gain <= 9.0, True)
    check("a V-beam has no resistor and a rhombic's takes half", (P.to_load("vbeam"), P.to_load("rhombic")),
          (0.0, 0.5))

    print("\n-- the V is laid at the ATP's angle --")
    rows = manuals.V_APEX["rows"]
    check("at every length the table prints, its angle", [round(P.vbeam_apex_deg(n)) for n, _ in rows],
          [a for _, a in rows])
    check("between two rows, straight between them: 2.5 wavelengths is 64 degrees", P.vbeam_apex_deg(2.5), 64.0)
    check("past the table's ends, its end rows", (P.vbeam_apex_deg(0.5), P.vbeam_apex_deg(14)), (90.0, 33.0))
    legs = P.travelling_legs("vbeam", 0.5, 2.0, 0.1)
    (amp, [(_, t, _)]) = legs[0]
    check("two wavelengths of leg are laid 35 degrees each side of the bisector, 70 between",
          round(math.degrees(math.atan2(t[1], t[0]))), 35)
    check("a V is two legs each way, a rhombic two paths of two legs",
          (len(legs), [len(path) for _, path in P.travelling_legs("rhombic", 0.7, 3.0, 0.1)]), (4, [2, 2]))

    print("\n-- what the advice says about them --")
    check("the V's footprint is its legs at their angle, apex to the open end",
          A.footprint_ft("vbeam", 14.2, length_ft=140), 115)
    check("the rhombic's is two legs at theirs, feed corner to resistor",
          A.footprint_ft("rhombic", 14.2, length_ft=210), 382)
    check("both are well suited to DX and the wrong shape for the county",
          [A.suits(k, u, 14.2)["verdict"] for k in ("vbeam", "rhombic") for u in ("dx", "regional")],
          ["well suited", "wrong shape for the near end", "well suited", "wrong shape for the near end"])
    check("the rhombic's resistor is sized for half of 100 W",
          A.power_notes("rhombic", 14.2, 100).get("resistor_w"), 50)
    check("  and the V has no resistor to size", "resistor_w" in A.power_notes("vbeam", 14.2, 100), False)
    v = A.recommend(14.2, use="dx", kind="vbeam")
    check("the V is fed on open-wire line, not coax", v["feedline"].startswith("Not coax to the antenna"), True)
    check("its advice quotes the ATP's resistors for one way",
          any("300 ohm terminating resistors" in b for b in v["better"]), True)

    print("\n-- the Lab's menu: aimed or not, and which way --")
    html = (ROOT / "elmer" / "templates" / "lab.html").read_text(encoding="utf-8")
    groups = {m.group(1): re.findall(r'<option value="(\w+)"', m.group(2))
              for m in re.finditer(r'<optgroup label="([^"]+)">(.*?)</optgroup>', html, re.S)}
    named = {label.split(" &mdash;")[0] + " " + label.split("&mdash; ")[1].split(",")[0]: kinds
             for label, kinds in groups.items() if "&mdash;" in label}
    check("all round: the verticals and the whips, nothing that must be aimed",
          named.get("All round no aiming"), ["quarter", "groundplane", "fiveeighth", "jpole", "whip", "screwdriver", "collinear"])
    check("two ways: the wires that fire broadside, and the V along itself",
          named.get("Aim it two ways"), ["dipole", "invertedv", "efhw", "bowtie", "loop", "whipdipole", "vbeam", "deltaloop"])
    check("one way: the beams, the rhombic and the terminated wires",
          named.get("Aim it one way"), ["yagi", "moxon", "hexbeam", "quad", "phased2", "foursquare", "rhombic", "tefv", "termsloper"])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

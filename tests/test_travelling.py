#!/usr/bin/env python3
"""The terminated antennas fire toward their resistor, and lower as the band goes up.

    python3 tests/test_travelling.py

The terminated end-fed vee (the Marines' "vertical half-rhombic") and the
terminated sloping wire come from USMC MCRP 3-40.3C, the Antenna Handbook.
Neither is cut to a band. A resistor at the far end soaks up what the wire
has not radiated, so the current runs one way and does not come back, and
the pattern is worked out as a travelling wave rather than borrowed from a
dipole. What that model has to get right, and what is held here:

  - it fires toward the resistor, off the far end, and not back past the feed;
  - the same wire is more wavelengths long on a higher band, so the lobe
    comes down and the gain goes up as the frequency rises;
  - the gain is honest: a few dBi over ground on 80 m, not a beam's number,
    with half the power left in the resistor;
  - the length and height the operator gave travel with the kind, and the
    kind still reads as its plain name wherever a table is looked up by it;
  - the Lab's pattern request carries the length, and refuses a silly one;
  - the advice calls it a DX antenna, not a county one, and says what the
    resistor has to be rated for.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import antenna_advice, patterns

    def wl(ft, mhz):
        return ft / antenna_advice.wavelength_ft(mhz)

    print("\n-- the kind carries the wire it describes --")
    k = patterns.laid("tefv", 500.0, 50.0, 14.2)
    check("a laid TEFV is still 'tefv' to a dictionary", (k == "tefv", k in patterns.ANTENNA_Q), (True, True))
    check("  and carries its length, height and band",
          (k.length_ft, k.height_ft, k.mhz), (500.0, 50.0, 14.2))
    check("a dipole passes through untouched", type(patterns.laid("dipole", 500.0, 50.0, 14.2)), str)
    check("both are travelling, a dipole is not",
          [patterns.is_travelling(x) for x in ("tefv", "termsloper", "dipole")], [True, True, False])
    check("  and both are pointed like a beam, by the heading",
          (patterns.boresight("tefv", 70.0), patterns.boresight("termsloper", 250.0)), (70.0, 250.0))

    print("\n-- it fires toward the resistor --")
    for kind, ft, mast in (("tefv", 500.0, 50.0), ("termsloper", 250.0, 40.0)):
        for mhz in (7.1, 14.2):
            k = patterns.laid(kind, ft, mast, mhz)
            h = wl(mast, mhz)
            front = max(patterns.travelling_raw(k, h, e, 0.0, mhz) for e in range(3, 60))
            back = max(patterns.travelling_raw(k, h, e, 180.0, mhz) for e in range(3, 60))
            check(f"{kind} on {mhz} MHz: front beats back by 10 dB or more",
                  front > back * 10 ** (10 / 20), True)
            ahead = patterns.field_toward(k, 20.0, 45.0, heading=45.0)
            behind = patterns.field_toward(k, 20.0, 225.0, heading=45.0)
            check(f"  and field_toward agrees, laid toward 45 degrees", ahead > behind * 3, True)
            sl = patterns.elevation_slice(k, h, mhz=mhz)
            peak = max(sl, key=lambda p: p["field"])
            check(f"  the side view peaks in front, below 60 degrees", peak["deg"] < 60.0, True)

    print("\n-- the lobe comes down and the gain goes up with the band --")
    k = patterns.laid("tefv", 500.0, 50.0, 3.6)
    lobes, gains = [], []
    for mhz in (3.6, 7.1, 14.2, 28.4):
        k = patterns.laid("tefv", 500.0, 50.0, mhz)
        env = patterns.travelling_envelope(k, wl(50.0, mhz), mhz)
        lobes.append(max(env, key=lambda t: t[1])[0])
        gains.append(patterns.travelling_gain_dbi(k, wl(50.0, mhz), mhz))
    print("     lobes", lobes, " gains dBi", gains)
    check("500 ft TEFV: each band's lobe lower than the one below it",
          all(a > b for a, b in zip(lobes, lobes[1:])), True)
    check("  and each band's gain higher", all(a < b for a, b in zip(gains, gains[1:])), True)
    check("  80 m lobe is high (NVIS-ish), 10 m lobe is low", (lobes[0] >= 30, lobes[-1] <= 12), (True, True))
    check("  gains are a wire's, not a beam's: between -5 and 15 dBi",
          all(-5.0 < g < 15.0 for g in gains), True)
    short = patterns.travelling_gain_dbi(patterns.laid("tefv", 100.0, 50.0, 14.2), wl(50.0, 14.2), 14.2)
    check("a shorter wire on the same band has less gain", short < gains[2], True)

    print("\n-- the Lab's pattern request carries the length --")
    from elmer.app import app
    c = app.test_client()
    c.set_cookie("elmer_user", "1")

    def pat(q):
        return c.get("/api/pattern?" + q, environ_base=LOCAL)

    r = pat("type=tefv&mhz=14.2&height=50&heading=45&length=500")
    d = r.get_json() or {}
    check("a 500 ft TEFV on 20 m answers", r.status_code, 200)
    check("  with a gain and the length in wavelengths", (d.get("gain_dbi") is not None, round(d.get("length_wl") or 0, 1)),
          (True, round(wl(500.0, 14.2), 1)))
    long = pat("type=tefv&mhz=14.2&height=50&heading=45&length=1000").get_json() or {}
    check("  and 1,000 ft of it has more", (long.get("gain_dbi") or 0) > (d.get("gain_dbi") or 0), True)
    check("a length of 5 ft is refused", pat("type=tefv&mhz=14.2&height=50&length=5").status_code, 400)
    dip = pat("type=dipole&mhz=14.2&height=50").get_json() or {}
    check("a dipole's answer leaves the travelling fields empty",
          (dip.get("gain_dbi"), dip.get("length_wl")), (None, None))

    print("\n-- the advice: a DX antenna, and a resistor that gets hot --")
    for kind in ("tefv", "termsloper"):
        check(f"{kind} for DX on 20 m", antenna_advice.suits(kind, "dx", 14.2)["verdict"], "well suited")
        check(f"{kind} for the county on 80 m", antenna_advice.suits(kind, "regional", 3.6)["verdict"],
              "wrong shape for the near end")
        check(f"{kind} on 6 m", antenna_advice.suits(kind, "dx", 50.1)["verdict"], "out of its range")
    notes = antenna_advice.power_notes("tefv", 14.2, 100.0)
    check("100 W: the resistor is rated for 50 W", notes["resistor_w"], 50)
    check("  and the sheet says so in words", any("50 W" in n and "resistor" in n for n in notes["items"]), True)
    check("a dipole has no resistor to rate", "resistor_w" in antenna_advice.power_notes("dipole", 14.2, 100.0), False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

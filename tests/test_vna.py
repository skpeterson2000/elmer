#!/usr/bin/env python3
"""Checks for the VNA sweep - the trace, and the sentence read off it.

    python3 tests/test_vna.py

The model is two pieces already in the program stitched together: the
feedpoint impedance from `patterns`, and the lossy-line transform from
`smith`. What is worth testing is not either of those but the things the Lab
claims on top of them, because those are the claims a person will act on with
a pair of wire cutters:

  - a long antenna resonates low and a short one high, and the advice says so
    the right way round;
  - the reactance changes sign at resonance, which is the whole reason to own
    the instrument rather than an SWR meter;
  - and the SWR at the shack end of a long lossy run is *better* than the SWR
    at the antenna, which is the counterintuitive one and the one that most
    needs to keep working.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import nanovna, vna  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- a dipole cut exactly right --")
    d = vna.sweep("dipole", f0_mhz=14.2, centre_mhz=14.2, span=0.10)
    check("resonance lands where it was cut", d["antenna"]["resonance_mhz"], 14.2)
    # The best match is a sampled minimum and resonance is an interpolated
    # crossing, so they agree to within one sample and not exactly - which is
    # also what a real instrument does, and why its marker never sits quite on
    # the number you expected.
    step = (d["high_mhz"] - d["low_mhz"]) / (d["points"] - 1)
    check("  and the match is best within a sample of it",
          abs(d["antenna"]["best_mhz"] - 14.2) <= step, True)
    check("  a dipole on 50 ohm coax never quite reaches 1:1",
          1.4 < d["antenna"]["best_swr"] < 1.5, True)
    check("  the advice says nothing needs cutting",
          "essentially where you are looking" in d["read"][0], True)

    print("\n-- which way to cut, which is the whole point --")
    long_one = vna.sweep("dipole", f0_mhz=13.8, centre_mhz=14.2, span=0.12)
    short_one = vna.sweep("dipole", f0_mhz=14.6, centre_mhz=14.2, span=0.12)
    check("cut too long, it resonates low", long_one["antenna"]["resonance_mhz"], 13.8)
    check("  and the advice says shorten", "Shorten" in long_one["read"][0], True)
    check("  and calls it long", "is long" in long_one["read"][0], True)
    check("cut too short, it resonates high", short_one["antenna"]["resonance_mhz"], 14.6)
    check("  and the advice says lengthen", "Lengthen" in short_one["read"][0], True)

    print("\n-- the sign of the reactance is the instruction --")
    rows = long_one["rows"]
    below = [r for r in rows if r["mhz"] < long_one["antenna"]["resonance_mhz"]]
    above = [r for r in rows if r["mhz"] > long_one["antenna"]["resonance_mhz"]]
    check("below resonance the reactance is capacitive",
          all(r["x"] < 0 for r in below), True)
    check("above it the reactance is inductive",
          all(r["x"] > 0 for r in above), True)
    check("  and the resistance does not move with frequency in this model",
          len({r["r"] for r in rows}), 1)

    print("\n-- the coax flatters the antenna, and that is not an improvement --")
    bare = vna.sweep("dipole", f0_mhz=14.6, centre_mhz=14.2, span=0.12, feet=0)
    run = vna.sweep("dipole", f0_mhz=14.6, centre_mhz=14.2, span=0.12,
                    line="rg58", feet=150)
    check("at the antenna, both agree - nothing has been transformed",
          bare["antenna"]["best_swr"], run["antenna"]["best_swr"])
    check("at the shack the same antenna reads better than it is",
          run["shack"]["best_swr"] < run["antenna"]["best_swr"], True)
    check("  and the sweep says why", any("flatters" in t for t in run["read"]), True)
    check("  with the loss named", run["matched_loss_db"] > 1.0, True)
    print(f"       (antenna {run['antenna']['best_swr']}:1, shack "
          f"{run['shack']['best_swr']}:1, {run['matched_loss_db']} dB each way)")
    lossless = vna.sweep("dipole", f0_mhz=14.6, centre_mhz=14.2, span=0.12,
                         line="lmr400", feet=150)
    check("better coax tells less of a lie",
          lossless["shack"]["best_swr"] > run["shack"]["best_swr"], True)

    print("\n-- a whip is sharp and a bowtie is not --")
    whip = vna.sweep("whip", f0_mhz=14.2, centre_mhz=14.2, span=0.08)
    fat = vna.sweep("bowtie", f0_mhz=14.2, centre_mhz=14.2, span=0.08)
    check("the whip's usable width is the narrower",
          whip["antenna"]["band_2to1"]["khz"] < fat["antenna"]["band_2to1"]["khz"],
          True)
    print(f"       (whip {whip['antenna']['band_2to1']['khz']} kHz, "
          f"bowtie {fat['antenna']['band_2to1']['khz']} kHz)")

    print("\n-- the sweep stays inside what the approximation can defend --")
    wide = vna.sweep("dipole", f0_mhz=14.2, span=5.0)
    check("a silly span is clamped, not honoured", wide["span"], vna.MAX_SPAN)
    check("  and the point count is bounded too",
          vna.sweep("dipole", 14.2, points=99999)["points"], 801)

    print("\n-- with no instrument attached, nothing raises --")
    ports, err = nanovna.candidates()
    check("candidates() returns a list either way", isinstance(ports, list), True)
    check("  and never the Pi's own UARTs",
          any("ttyAMA" in p["device"] for p in ports), False)
    info, err = nanovna.identify("/dev/ttyACM-nope")
    check("identify() on nothing gives a reason, not an exception", info, None)
    check("  and the reason is a sentence", bool(err), True)
    got, err = nanovna.measure("/dev/ttyACM-nope", 14.0, 14.35)
    check("measure() on nothing does the same", got, None)
    check("  and a backwards sweep is refused before any port is opened",
          nanovna.measure("/dev/ttyACM-nope", 14.35, 14.0)[1],
          "the stop frequency has to be above the start")

    print("\n-- and driving it only sends what is on the list --")
    # Every one of these has to be refused before a port is opened, which is
    # what the device path proves: it does not exist, so an error that names
    # the port instead of the reason would mean the gate ran second.
    nowhere = "/dev/ttyACM-nope"
    check("an action nobody offered is refused",
          nanovna.control(nowhere, "reboot")[1],
          "reboot is not something ELMER asks a VNA to do")
    check("  and so is an empty one", nanovna.control(nowhere, "")[0], None)
    check("a standard that is not a standard is refused",
          "calibration standard" in nanovna.control(
              nowhere, "cal-step", "banana")[1], True)
    check("a slot out of range is refused",
          "calibration slots are 0 to" in nanovna.control(
              nowhere, "save", 99, confirmed=True)[1], True)
    check("a backwards span is refused here too",
          nanovna.control(nowhere, "sweep",
                          {"start_mhz": 14.35, "stop_mhz": 14.0})[1],
          "the stop frequency has to be above the start")

    print("\n-- and the two that destroy work say so and stop --")
    for action, value in (("cal-reset", None), ("save", 2)):
        refusal = nanovna.control(nowhere, action, value)[1]
        check(f"{action} is refused unconfirmed",
              refusal.startswith("that one destroys"), True)
        check("  and says what would be lost", len(refusal) > 40, True)
    # Confirmed, it gets as far as the port - which is the failure that proves
    # the gate let it through rather than the gate refusing it again.
    check("confirmed, it is the port that stops it, not the gate",
          "could not talk to" in nanovna.control(
              nowhere, "cal-reset", confirmed=True)[1], True)
    check("what is on offer says which ones destroy",
          sorted(o["action"] for o in nanovna.offered() if o["destroys"]),
          ["cal-reset", "save"])

    print("\n-- and the sweep outlives the page that took it --")
    # The instrument and the Smith chart are on different pages now, so a
    # measurement cannot be handed from one to the other in a variable. It
    # goes on the card instead, which also means it survives a reload.
    import json, tempfile          # noqa: E402
    from pathlib import Path as _P  # noqa: E402
    from elmer import sweeps        # noqa: E402
    with tempfile.TemporaryDirectory() as tmp:
        sweeps.STORE = _P(tmp) / "sweep.json"
        check("nothing held to begin with", sweeps.last(), None)
        rows = [{"mhz": 14.0, "swr": 1.4}, {"mhz": 14.1, "swr": 1.2}]
        kept = sweeps.keep({"device": "/dev/ttyACM0", "rows": rows,
                            "low_mhz": 14.0, "high_mhz": 14.1,
                            "over_unity": 0})
        check("a sweep is kept", kept["points"], 2)
        check("  and read back whole", sweeps.last()["rows"], rows)
        check("  with the span it was taken over",
              [sweeps.last()["low_mhz"], sweeps.last()["high_mhz"]],
              [14.0, 14.1])
        check("  and when", sweeps.last()["taken"] > 0, True)
        # One sweep, not a history: the last thing measured is what a page
        # asking "what did it measure" means.
        sweeps.keep({"device": "x", "rows": [{"mhz": 7.1, "swr": 3.0}]})
        check("a second replaces the first", sweeps.last()["points"], 1)
        check("nothing to keep is not kept", sweeps.keep({"rows": []}), None)
        check("  nor is a sweep no instrument could produce",
              sweeps.keep({"rows": [{}] * (sweeps.MAX_POINTS + 1)}), None)
        check("and it can be thrown away", sweeps.forget(), True)
        check("  leaving nothing behind", sweeps.last(), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

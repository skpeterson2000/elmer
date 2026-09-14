#!/usr/bin/env python3
"""Reaching a particular place: the path from here to there, and how.

    python3 tests/test_pathto.py

The far end resolves from a grid without a lookup, a callsign from the FCC
record, and nonsense to a plain refusal. The path says how far and which
way and what the sun is doing at both ends; a short path asks the ground
whether two antennas can see each other and a long one does not; the sky
is read at the midpoint; the approach names bands the class may use, with
the mode and which way to hang the wire. Nothing here reaches the network:
the ionosphere and the ground are stood in for.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import pathto, propagation, terrain  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    here = {"lat": 46.5983, "lon": -94.3154, "grid": "EN26uo", "short": "Brainerd"}
    # A night sky with foF2 at 3.9: the low bands come straight back, 20 m is shut.
    propagation.snapshot = lambda lat=None, lon=None, force=False: {
        "fof2": 3.9, "hmf2": 300.0, "elevation": -20.0, "k_index": 1.0, "muf": 9.0}
    asked = []

    def fake_profile(lat1, lon1, lat2, lon2, samples=80):
        asked.append((lat1, lon1, lat2, lon2))
        km, _ = terrain.great_circle(lat1, lon1, lat2, lon2)
        pts = [{"km": km * i / 9, "elevation": 380.0 + (60.0 if i == 4 else 0.0)} for i in range(10)]
        return {"points": pts, "source": "a hill in the middle"}
    terrain.profile = fake_profile

    print("\n-- the far end --")
    there = pathto.resolve_to("EN34")
    check("a grid square resolves without a lookup", (there["kind"], there["grid"][:4]), ("grid", "EN34"))
    check("  and so do coordinates", pathto.resolve_to("44.9, -93.2")["kind"], "coordinates")
    check("a grid is not mistaken for a callsign", pathto.RE_CALLSIGN.match("EN26") is None, True)
    check("  and a callsign looks like one", bool(pathto.RE_CALLSIGN.match("KC9SP")), True)

    print("\n-- a path across the state, at night --")
    d = pathto.predict(here, there, gear=["hf_wire", "ht"], license="General", now=1789400000)
    check("how far and which way", (d["km"] > 200, 100 < d["bearing"] < 200, d["miles"] < d["km"]), (True, True, True))
    check("  the back bearing is the other way", (d["back_bearing"] - d["bearing"]) % 360, 180)
    check("  the sun at both ends", (d["from"]["sun"] in ("lit", "grey", "dark", "twilight"),
                                     d["to"]["sun"] in ("lit", "grey", "dark", "twilight")), (True, True))
    check("too far for line of sight, and the ground was not asked", (d["sight"]["clear"], asked), (False, []))
    carry = [b["band"] for b in d["sky"]["bands"] if b["works"]]
    check("the low bands carry it straight up and back", ("80m" in carry, "20m" in carry), (True, False))
    check("  read at the midpoint", "midpoint" in d["sky"]["read_at"], True)
    first = d["approach"][0]
    check("the approach leads with a band that carries it", first["band"] in carry, True)
    check("  with a mode", "FT8" in first["mode"] or "SSB" in first["mode"] or "CW" in first["mode"], True)
    check("  and the wire low for a straight-up path", "low" in first["antenna"], True)
    check("  and says when", bool(d["when"]), True)

    print("\n-- the same path for a Technician --")
    d = pathto.predict(here, there, gear=["hf_wire"], license="Technician", now=1789400000)
    check("no band a Technician may not use", all(a["band"] in pathto.TECH_BANDS for a in d["approach"]), True)
    check("  and 80 m is CW only for them", next(a["mode"] for a in d["approach"] if a["band"] == "80m"), "CW only")

    print("\n-- across town, with a hill in the way --")
    near = {"lat": 46.62, "lon": -94.20, "grid": "EN26vo", "short": "next town"}
    d = pathto.predict(here, near, gear=["ht", "hf_wire"], license="General", now=1789400000)
    check("the ground was asked", len(asked), 1)
    check("  and it is in the way", (d["sight"]["terrain"], d["sight"]["clear"]), (True, False))
    check("  so the first approach is a repeater", (d["approach"][0]["band"], d["approach"][0]["how"]),
          ("2 m / 70 cm", "by repeater"))
    check("  and HF across town is ground wave or straight up, not a list",
          all(a["how"] in ("ground wave", "straight up and back") for a in d["approach"][1:]) and len(d["approach"]) <= 3, True)

    print("\n-- with a handheld only, across the state --")
    d = pathto.predict(here, there, gear=["ht"], license="General", now=1789400000)
    check("a linked system first, since a handheld will not carry it", d["approach"][0]["how"], "repeaters that link")
    check("  and which HF band would, if one can be borrowed", "80m" in d["approach"][1]["band"], True)

    print("\n-- with nothing ticked, across town --")
    d = pathto.predict(here, near, gear=[], license="General", now=1789400000)
    check("the approach says to tick something", d["approach"][0]["odds"], "the rule")

    print("\n-- nonsense --")
    check("nothing made of it", pathto.resolve_to("zzzz qqqq nowhere"), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())

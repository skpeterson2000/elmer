#!/usr/bin/env python3
"""A VHF path by the numbers: the link budget along the ground.

    python3 tests/test_linkbudget.py

The pieces come out where the textbooks put them - free space, the knife
edge, the plane earth - and the whole comes out where experience puts it:
two base stations forty kilometres apart on open ground talk on 2 m FM,
two handhelds ten kilometres apart are a long shot, and a hill between
two handhelds is a wall that a base rig into a Yagi gets over. Nothing
here reaches the network: the ground is stood in for.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import linkbudget as L, pathto, terrain  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the pieces, against the textbook --")
    check("free space at 1 km on 2 m is about 76 dB", round(L.free_space_db(1.0, 146.0)), 76)
    check("  and 6 dB more at twice the distance", round(L.free_space_db(2.0, 146.0) - L.free_space_db(1.0, 146.0)), 6)
    check("a knife edge at grazing costs 6 dB", round(L.knife_edge_db(0.0)), 6)
    check("  well below the line, nothing", L.knife_edge_db(-1.0), 0.0)
    check("  and a big edge costs a lot more", L.knife_edge_db(3.0) > 20, True)
    check("plane earth runs as the fourth power: 12 dB for twice the distance",
          round(L.plane_earth_db(20, 9, 9) - L.plane_earth_db(10, 9, 9)), 12)
    check("  and height at either end buys it back", L.plane_earth_db(10, 9, 9) < L.plane_earth_db(10, 2, 2), True)
    check("the Fresnel zone is widest in the middle",
          L.fresnel_radius_m(5, 5, 146) > L.fresnel_radius_m(1, 9, 146), True)
    check("odds: no margin is a coin toss", round(L.odds(0.0), 2), 0.5)
    check("  twenty decibels in hand is near certain", L.odds(20.0) > 0.99, True)
    check("  minus twenty is as good as none", L.odds(-20.0) < 0.01, True)
    check("a residential street is noisier than a quiet site",
          L.noise_floor_dbm(146, 12000, "residential") > L.noise_floor_dbm(146, 12000, "quiet"), True)
    check("  and FT8 needs far less than FM", L.needed_dbm(146, "ft8") < L.needed_dbm(146, "fm") - 25, True)

    print("\n-- whole paths, against experience --")
    b = L.budget(40, None, "2m", "fm", "base", "base")
    check("two base stations 40 km apart on open ground talk on 2 m FM", b["verdict"], "good")
    check("  the ground's reflection is the account paid, not the bulge on top", b["loss"]["mechanism"].startswith("two low"), True)
    b = L.budget(10, None, "2m", "fm", "ht", "ht")
    check("two handhelds 10 km apart are a long shot", b["verdict"] in ("long shot", "no"), True)
    check("  and 3 km apart, good", L.budget(3, None, "2m", "fm", "ht", "ht")["verdict"], "good")
    check("a handheld reaches a base station 10 km off", L.budget(10, None, "2m", "fm", "ht", "base")["verdict"], "good")
    check("  both ways are worked, and the handheld's leg is the weaker",
          b["forward"]["margin_db"] == b["back"]["margin_db"], True)
    ab = L.budget(10, None, "2m", "fm", "ht", "base")
    check("  the base has more to send than the handheld", ab["back"]["leaves_dbm"] > ab["forward"]["leaves_dbm"], True)
    check("  and the odds are the worse leg's", ab["odds"] == min(ab["forward"]["odds"], ab["back"]["odds"]), True)
    check("beams both ends carry 100 km on SSB", L.budget(100, None, "2m", "ssb", "base_beam", "base_beam", "rural")["verdict"], "good")
    check("70 cm loses 10 dB more than 2 m in free space", round(L.free_space_db(20, 446) - L.free_space_db(20, 146)), 10)
    check("  but two low antennas over the ground pay the same on either band - the ground does not care",
          L.budget(20, None, "70cm", "fm", "mobile", "mobile")["loss"]["plane_earth_db"]
          == L.budget(20, None, "2m", "fm", "mobile", "mobile")["loss"]["plane_earth_db"], True)
    check("past 200 km the model says the weather decides", L.budget(250, None, "2m", "ssb", "base_beam", "base_beam")["beyond"], True)

    print("\n-- a hill between --")
    hill = [(8 * i / 40, 300 + (400 if 18 <= i <= 22 else 0)) for i in range(41)]
    flat = [(8 * i / 40, 300.0) for i in range(41)]
    h = L.budget(8, hill, "2m", "fm", "ht", "ht")
    f = L.budget(8, flat, "2m", "fm", "ht", "ht")
    check("the hill costs decibels the flat path does not", h["loss"]["total_db"] > f["loss"]["total_db"] + 5, True)
    check("  over the ground, not the ground's reflection", h["loss"]["mechanism"].startswith("free space and"), True)
    check("  it is named, where it is", (3.5 < h["loss"]["worst"]["km"] < 4.5, h["loss"]["worst"]["above_line_m"] > 300), (True, True))
    check("  and it is a wall to two handhelds", h["verdict"], "no")
    prof = h["profile"]
    check("the profile comes with it for the picture: one row a sample", len(prof), 41)
    check("  the line starts and ends at the antennas", (prof[0]["line"], prof[-1]["line"]), (302.0, 302.0))
    check("  the ground under the hill stands above the line there", prof[20]["ground"] > prof[20]["line"], True)
    check("  and the Fresnel zone is widest in the middle, nothing at the ends",
          (prof[0]["r1"], prof[20]["r1"] > prof[5]["r1"]), (0, True))
    check("  the words say what it costs and where", "getting over the ground" in h["words"] and "4 km along" in h["words"], True)
    up = L.step_up(8, hill, "2m", "fm", "ht", "ht", "residential")
    check("the step up the shelf is named", up is not None and up["here"] is not None, True)
    check("  and it is a base rig into a Yagi", up["here"], "base_beam")
    check("  which gets the odds up", up["odds"] >= 0.6, True)
    check("nothing to step up from when the path is already good", L.step_up(3, L.smooth_profile(3), "2m", "fm", "ht", "ht", "residential"), None)

    print("\n-- the whole, for a path --")
    here = {"lat": 46.5983, "lon": -94.3154, "grid": "EN26uo", "short": "Brainerd"}
    near = {"lat": 46.62, "lon": -94.20, "grid": "EN26vo", "short": "next town"}
    asked = []

    def fake_profile(lat1, lon1, lat2, lon2, samples=80):
        asked.append(samples)
        km, _ = terrain.great_circle(lat1, lon1, lat2, lon2)
        return {"points": [{"km": km * i / 19, "elevation": 380.0 + (90.0 if i == 9 else 0.0)} for i in range(20)],
                "source": "a hill in the middle"}
    terrain.profile = fake_profile
    d = pathto.link(here, near, band="2m", mode="fm", radio_here="ht")
    check("the ground was asked, once", len(asked), 1)
    check("  and the terrain is named", (d["terrain"], d["source"]), (True, "a hill in the middle"))
    check("  the far end is the same radio unless said", d["there"]["key"], "ht")
    # The band list carries the ionosphere's bands as well now, marked, so
    # the page can offer them and say which kind of answer each will give.
    # The four the budget itself works along the ground come first.
    check("  the shelf, the modes and the sites come with it for the page",
          (len(d["shelf"]), [m["key"] for m in d["modes"]], len(d["sites"])),
          (6, ["fm", "ssb", "cw", "ft8"], 4))
    check("  the bands begin with the ones a signal travels the ground on",
          [b["key"] for b in d["bands"]][:4], ["6m", "2m", "1.25m", "70cm"])
    check("  and go on to the ones it does not",
          ([b["key"] for b in d["bands"] if b.get("kind") == "sky"][:3],
           all(b.get("kind") == "ground" for b in d["bands"][:4])),
          (["160m", "80m", "60m"], True))
    check("  bearing and distance", (0 <= d["bearing"] < 360, 5 < d["km"] < 15), (True, True))
    check("  the odds are a fraction and the verdict a word", (0 <= d["odds"] <= 1, d["verdict"] in ("good", "likely", "worth trying", "long shot", "no")), (True, True))
    far = {"lat": 44.9, "lon": -93.2, "grid": "EN34", "short": "the cities"}
    asked.clear()
    d = pathto.link(here, far, band="2m", mode="ssb", radio_here="base_beam")
    check("past the model's reach the ground is not asked", asked, [])
    check("  and the answer says the weather decides", d["beyond"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

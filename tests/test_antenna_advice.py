#!/usr/bin/env python3
"""Checks that the antenna advice follows the antenna somebody chose.

    python3 tests/test_antenna_advice.py

The page offers eleven antennas to calculate and used to teach one. Whatever
you selected, asking for advice answered with a half-wave dipole and quietly
changed the selector to match - because the guidance was keyed on what you were
trying to do, and each intention had a single antenna baked into it.

What is tested here is that every type the calculator can draw is also a type
it can teach, that the teaching is about that antenna rather than a generic
wire, and that choosing one for the wrong job is said out loud rather than
silently corrected.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import antenna_advice as A
from elmer import groundwave as G  # noqa: E402

FAILS = []

# Every option in the calculator's type selector.
CALCULATOR_TYPES = ["dipole", "invertedv", "efhw", "bowtie", "loop", "quarter",
                    "fiveeighth", "jpole", "groundplane", "yagi", "whip",
                    "screwdriver", "whipdipole"]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- every antenna it can draw, it can also teach --")
    check("no calculator type is left without guidance",
          [t for t in CALCULATOR_TYPES if t not in A.TYPES], [])
    check("and none of them is an empty stub",
          [t for t, v in A.TYPES.items()
           if not (v["why"] and v["watch"] and v["better"])], [])
    check("each says which way it is polarised",
          sorted({v["polarisation"] for v in A.TYPES.values()}),
          ["horizontal", "vertical"])

    print("\n-- asking about an antenna answers about that antenna --")
    for kind in CALCULATOR_TYPES:
        got = A.recommend(7.1, "dx", kind)
        check(f"a question about {kind} comes back about {kind}",
              got["type"], kind)
    check("  and says it was the one chosen, not one suggested",
          A.recommend(7.1, "dx", "loop")["chosen"], True)
    check("with no type named it still suggests one",
          A.recommend(7.1, "dx").get("chosen", False), False)
    check("  and that suggestion is a real antenna",
          A.recommend(7.1, "dx")["type"] in A.TYPES, True)

    print("\n-- the advice is about this antenna, not a generic wire --")
    # The old failure was that every answer read the same. Guidance for a
    # vertical should talk about radials; guidance for a whip about loading.
    text = lambda k: " ".join(A.TYPES[k]["why"] + A.TYPES[k]["watch"]
                              + A.TYPES[k]["better"]).lower()
    check("a vertical's advice is about its radials",
          "radial" in text("quarter"), True)
    check("a mobile whip's is about loading and efficiency",
          "loading" in text("whip") and "efficien" in text("whip"), True)
    check("a loop's is about area and its feedpoint impedance",
          "area" in text("loop") and "ohm" in text("loop"), True)
    check("a J-pole's is about common-mode current",
          "common-mode" in text("jpole"), True)
    check("a bowtie's is about bandwidth",
          "bandwidth" in text("bowtie"), True)
    check("and no two of them read the same",
          len({text(k) for k in CALCULATOR_TYPES}), len(CALCULATOR_TYPES))

    print("\n-- choosing one for the wrong job is said, not corrected --")
    # Polarisation is the usual mismatch and it costs about 20 dB, which no
    # amount of anything else gets back.
    bad = A.recommend(146.52, "local", "yagi")
    check("a horizontal beam for FM is called wrong", bad["fit"]["verdict"],
          "wrong shape")
    check("  and the type is still the one asked about", bad["type"], "yagi")
    check("a vertical for near-vertical incidence is called wrong",
          A.recommend(7.1, "regional", "quarter")["fit"]["verdict"],
          "wrong shape for the far end")
    check("  because a low angle is the one direction that does not come back",
          "up" in A.recommend(7.1, "regional", "quarter")["fit"]["note"], True)
    check("a wire hung low is right for regional work, and told to be low",
          "low" in A.recommend(7.1, "regional", "dipole")["fit"]["note"], True)
    check("a dipole for DX is told the height is the argument",
          "height" in A.recommend(7.1, "dx", "dipole")["fit"]["note"], True)
    # A vertical for distance is not merely acceptable, it is the point of the
    # shape - a low takeoff angle without needing height. That is why a short
    # loaded whip on a car works stations a garden wire cannot.
    check("a vertical for DX is called well suited, not merely allowed",
          A.recommend(7.1, "dx", "quarter")["fit"]["verdict"], "well suited")
    check("  and the reason given is the takeoff angle",
          "angle" in A.recommend(7.1, "dx", "whip")["fit"]["note"], True)
    # And the regional verdict must not flatly contradict every operator who
    # has worked somebody down the road on a mobile whip.
    near = A.recommend(7.1, "regional", "whip")["fit"]
    check("a vertical for regional work is wrong only for the far end",
          near["verdict"], "wrong shape for the far end")
    check("  and it is credited with the ground wave it does have",
          "ground wave" in near["note"], True)

    print("\n-- the numbers follow the antenna too --")
    check("a five-eighths vertical is taller than a quarter wave",
          A.recommend(7.1, "dx", "fiveeighth")["height_ft"]
          > A.recommend(7.1, "dx", "quarter")["height_ft"], True)
    check("a mobile whip is not asked to go 60 feet up",
          A.recommend(7.1, "dx", "whip")["height_ft"] < 15, True)
    check("every type gets a height, a feedline note and the band context",
          [k for k in CALCULATOR_TYPES
           if not (A.recommend(7.1, "dx", k)["height_ft"]
                   and A.recommend(7.1, "dx", k)["feedline"])], [])

    print("\n-- the height follows the purpose, not only the antenna --")
    # The bug: an inverted-V for NVIS on 40m was told to go up to 69 ft, and
    # the evaluator three inches below on the same page marked 69 ft as too
    # high for NVIS. Both halves were reading the same antenna and only one of
    # them knew what it was for.
    for kind in ("dipole", "invertedv", "loop", "bowtie"):
        dx = A.recommend(7.1, "dx", kind)["height_ft"]
        near = A.recommend(7.1, "regional", kind)["height_ft"]
        check(f"a {kind} is hung lower for the county than for DX",
              near < dx, True)
    # And it has to land inside the window the Lab's evaluator actually uses,
    # or the two will contradict each other again.
    lam = A.wavelength_ft(7.1)
    for kind in ("dipole", "loop", "bowtie"):
        h = A.recommend(7.1, "regional", kind)["height_ft"]
        check(f"  and a {kind} lands inside 0.15-0.25 wavelengths",
              A.NVIS_LOW <= h / lam <= A.NVIS_HIGH, True)
    # An inverted-V radiates from its current-weighted mean height, not its
    # apex, so the apex has to clear the target by whatever the legs drop.
    apex = A.recommend(7.1, "regional", "invertedv")["height_ft"]
    flat = A.recommend(7.1, "regional", "dipole")["height_ft"]
    check("an inverted-V's apex is raised to allow for the droop", apex > flat, True)
    effective = apex - A.V_CENTROID * (234.0 / 7.1) * math.sin(
        math.radians(A.DEFAULT_DROOP_DEG))
    check("  so that its effective height is what lands in the window",
          A.NVIS_LOW <= effective / lam <= A.NVIS_HIGH, True)
    check("a vertical is not given an NVIS height, because it is not for that",
          A.recommend(7.1, "regional", "quarter")["height_ft"]
          == A.recommend(7.1, "dx", "quarter")["height_ft"], True)

    print("\n-- and the advice under the height agrees with it --")
    # Fixing the number was not enough. Every horizontal antenna's improvement
    # advice began "raise it", which is the whole answer for distance and
    # precisely wrong hung low - so the tool put an inverted-V at 35 ft and
    # then, in the next paragraph, told somebody to raise it.
    # Asserted structurally rather than by keyword: "do not raise it" contains
    # the word raise, and a test that reads prose for banned words fails the
    # sentence that says the right thing.
    for kind in ("dipole", "invertedv", "loop", "bowtie", "efhw"):
        near = A.recommend(7.1, "regional", kind)
        check(f"a {kind} hung low is not given the raise-it advice",
              near["better"] == A.TYPES[kind]["better"], False)
        check(f"  it gets the low-hanging advice instead",
              near["better"][:len(A.NVIS_BETTER)], A.NVIS_BETTER)
        check(f"  and is told plainly that higher is worse",
              "higher is worse" in " ".join(near["better"]), True)
    check("it offers the ground reflector, which is the real NVIS improvement",
          "reflector" in " ".join(A.recommend(7.1, "regional", "dipole")["better"]),
          True)
    check("and points at the band rather than the mast when it stops working",
          "lower band" in " ".join(A.recommend(7.1, "regional", "dipole")["better"]),
          True)
    # The DX advice must keep saying the opposite, because there it is right.
    check("the same antenna hung for DX keeps its own advice, which says go up",
          A.recommend(7.1, "dx", "dipole")["better"], A.TYPES["dipole"]["better"])
    check("  and a vertical is never given the low-hanging advice at all",
          A.recommend(7.1, "regional", "quarter")["better"],
          A.TYPES["quarter"]["better"])

    print("\n-- a bought antenna is not a shopping list of materials --")
    from elmer import conductors as C  # noqa: E402
    whip = [c["key"] for c in C.options(7.1, "whip")]
    check("a mobile whip is offered what whips are made of",
          whip[0], "stainless")
    check("  and not a coat hanger or a tape measure",
          [k for k in ("hanger", "tape", "fence", "emt12") if k in whip], [])
    check("stainless is a poor conductor, and the entry says so",
          "conducts about a fortieth" in
          (next(c for c in C.CONDUCTORS if c["key"] == "stainless")
           .get("caution") or ""), True)
    check("everything else still gets the whole list",
          len(C.options(7.1, "dipole")), len(C.options(7.1)))
    check("  and an unknown antenna is not narrowed by accident",
          len(C.options(7.1, "nonesuch")), len(C.options(7.1)))

    print("\n-- and what somebody has actually got --")
    # "Half a wavelength up" is 69 ft on 40m: a mast on a farm and a daydream
    # in a flat. Printing it at somebody in a flat is not advice.
    ideal = A.recommend(7.1, "dx", "dipole")["height_ft"]
    check("with no site given, the textbook answer is unchanged",
          A.recommend(7.1, "dx", "dipole", None)["height_ft"], ideal)
    check("  and nothing is added to clutter it",
          A.recommend(7.1, "dx", "dipole", None)["reality"], None)
    for site in ("house", "small", "attic", "apartment", "portable"):
        got = A.recommend(7.1, "dx", "dipole", site)
        check(f"a {site} is not told to put a 40m dipole at {ideal} ft",
              got["height_ft"] < ideal, True)
        check(f"  and is told what does work there",
              bool(got["reality"]["works"]), True)
    check("a tower is not capped, because it does not need to be",
          A.recommend(7.1, "dx", "dipole", "tower")["height_ft"], ideal)

    # The honest part: a low antenna is a different antenna, not a broken one,
    # and the arithmetic says which.
    small = A.recommend(7.1, "dx", "dipole", "small")
    check("a capped height explains what it costs, as an angle",
          small["reality"]["takeoff_deg"] > 55, True)
    check("  and names what it is good for instead",
          "region" in small["reality"]["means"], True)
    check("every site says what it is good at rather than only what it lacks",
          [s for s in A.SITES if not A.SITES[s]["good_at"]], [])
    # A flat has no height at all, and that has to not read as an error.
    flat = A.recommend(7.1, "dx", "dipole", "apartment")["reality"]
    check("a flat is capped to nothing and still offered three antennas",
          (flat["height_ft"], len(flat["works"]) >= 3), (0, True))
    check("  and told the noise floor is the real enemy there",
          any("noise" in c for c in flat["costs"]), True)

    print("\n-- somebody in a vehicle --")
    # A car settles the question before the intention does. The advice used to
    # offer a half-wave dipole "as high as you can manage" to somebody who had
    # just said they were in a truck.
    check("mobile is a place you can say you are", "mobile" in A.SITES, True)
    check("  on HF a car gets a loaded whip",
          A.recommend(7.1, site="mobile")["type"], "whip")
    check("  and on 2 m a five-eighths, where the whip is full size already",
          A.recommend(146.0, site="mobile")["type"], "fiveeighth")
    car = A.for_type(7.1, "whip", site="mobile")["reality"]
    check("  the vehicle is named as the other half of the antenna",
          any("other half" in c for c in car["costs"]), True)
    check("  bonding is in the costs, because it beats any coil",
          any("ond" in c for c in car["costs"]), True)
    check("  and so is the noise the car makes itself",
          any("alternator" in c for c in car["costs"]), True)

    print("\n-- a mobile whip works two ways, and they are different contacts --")
    # This text asserted the flat opposite: that a contact from the road was
    # ground wave and "not the ionosphere", measured "in tens of miles rather
    # than hundreds". Distance mobile on 20 m is skywave off a low-launching
    # vertical, and saying otherwise contradicts every operator who has done it.
    better = " ".join(A.TYPES["whip"]["better"])
    check("the ionosphere is not denied", "not the ionosphere" in better, False)
    check("  the ground wave is still credited", "ground wave" in better, True)
    check("  and so is the skywave that does the distance",
          "F layer" in better, True)

    print("\n-- ground wave is an HF answer, and stops being one --")
    check("it is still the mechanism at the top of HF",
          G.useful_range_km(28.0, 100.0, "average") is not None, True)
    for mhz in (50.0, 146.0, 446.0):
        check(f"  at {mhz:g} MHz it is not",
              G.useful_range_km(mhz, 100.0, "average"), None)
    vhf = G.describe(146.0)
    check("  and the description says what carries you instead",
          vhf["applies"], False)
    check("  naming line of sight", "line of sight" in vhf["note"], True)
    # The band plan reads `miles`, so a None there is what keeps the wrong
    # sentence off the screen.
    check("  with no mileage to quote", vhf["miles"], None)

    print("\n-- low is a capability until it is a ground heater --")
    # A fifth of a wavelength up is a deliberate NVIS antenna. A twentieth is
    # not, and telling somebody they have built a fine regional station at
    # 6 ft on 40 m is not honest.
    low = A.recommend(7.1, "dx", "dipole", "mobile")["reality"]
    check("6 ft on 40 m is called what it is",
          "ground under it" in low["means"], True)
    check("  and the fix is named as height, not power",
          "rather than power" in low["means"], True)
    ok_low = A.recommend(7.1, "dx", "dipole", "small")["reality"]
    check("  but 22 ft is still a real regional antenna",
          "region" in ok_low["means"], True)

    print("\n-- the heading names the antenna it picked --")
    # It recommended type "invertedv" under the heading "A low dipole", with an
    # alternative underneath that mentioned a flat dipole - so the page looked
    # like it was proposing two antennas at once to somebody who has never put
    # up either. A title that does not name its own pick is the whole fault.
    NAMES = {"dipole": "dipole", "invertedv": "inverted-v", "jpole": "j-pole",
             "yagi": "beam", "quarter": "quarter", "efhw": "end-fed",
             "loop": "loop", "whip": "whip", "groundplane": "ground",
             "fiveeighth": "eighth", "bowtie": "bowtie"}
    for mhz in (1.9, 3.5, 7.1, 14.2, 28.5, 52.0, 146.0, 446.0):
        for use in ("regional", "dx", "local", None):
            r = A.recommend(mhz, use=use, site="house")
            kind, title = r.get("type"), (r.get("title") or "").lower()
            want = NAMES.get(kind)
            if want is None:
                continue
            check(f"{mhz:g} MHz {use}: {kind} titled {title!r}",
                  want in title, True)

    print("\n-- and an inverted-V is explained as a dipole, not beside one --")
    v = A.recommend(3.5, use="regional", site="house")
    check("the pick is the V", v["type"], "invertedv")
    check("  its own heading says so", "inverted-v" in v["title"].lower(), True)
    said = " ".join(v["why"]).lower()
    check("  and it says the two are the same antenna",
          "an inverted-v is a dipole" in said, True)
    # The second choice has to lead with the case it applies to, or it reads
    # as a competing recommendation rather than a runner-up.
    # "A flat dipole beats an inverted-V" led with the verdict and read as a
    # correction to the recommendation above it. Leading with the case it
    # applies to - "Two supports rather than one?" - makes it a runner-up.
    import re
    for kind, use in (("invertedv", "regional"), ("dipole", "dx")):
        alt = A.recommend(3.5, use=use, site="house")["alternative"]
        first = re.search(r"[.?!]", alt)
        check(f"  the {kind} second choice opens with the condition",
              first and first.group(), "?")

    print("\n-- what you have to work with speaks before what you want --")
    # It used to be asked fourth, and only a vehicle changed the answer: a
    # flat, an attic and a short garden all got "a half-wave dipole, as high
    # as you can manage" - 69 feet of wire offered to a balcony - while the
    # site's own notes a few lines down said a wire out of the window. The
    # program knew and did not act on it.
    flat = A.recommend(14.2, site="apartment")
    check("a flat on 20 m is not offered a dipole", flat["type"], "efhw")
    check("  and the title says what to do with it there",
          "out of the window" in flat["title"], True)
    check("  and says the site chose it", flat.get("steered"), True)
    check("a flat on 80 m, where even the end-fed is too long, gets the rail",
          A.recommend(3.8, site="apartment")["type"], "whip")
    check("  and it is not called mobile",
          "mobile" in A.recommend(3.8, site="apartment")["title"].lower(), False)
    check("a flat on 2 m gets a vertical on the balcony",
          A.recommend(146.52, site="apartment")["type"], "jpole")
    check("an attic on 20 m fits an inverted-V, which the site's notes say",
          A.recommend(14.2, site="attic")["type"], "invertedv")
    check("  and on 40 m it does not, so the end-fed folds",
          A.recommend(7.1, site="attic")["type"], "efhw")
    check("a short garden on 40 m gets the end-fed as a sloper",
          A.recommend(7.1, site="small")["type"], "efhw")
    check("  tuned to its own ground reflection, in so many words",
          "ground reflection" in A.recommend(7.1, site="small")["title"], True)
    check("nothing at home gets what people carry to a park",
          A.recommend(14.2, site="portable")["type"], "efhw")
    check("a house leaves it to the intention, as before",
          A.recommend(14.2, site="house")["type"], "dipole")
    check("  and so does a tower", A.recommend(14.2, site="tower")["type"], "dipole")
    check("  and so does not saying", A.recommend(14.2)["type"], "dipole")
    # Naming an antenna still means being taught that antenna.
    check("somebody who named a loop in a flat is taught the loop",
          A.recommend(14.2, kind="loop", site="apartment")["type"], "loop")

    print("\n-- nothing is ever told to go up 266 feet --")
    # The band plan handed 160 m to a Lab that knew nothing about the site,
    # and the textbook answer was a dipole half a wavelength up - 266 ft,
    # with the physics of why that works explained underneath. Above 200 ft
    # the FAA has to be told (14 CFR 77.9) and the structure registered
    # (47 CFR Part 17); a hundred is a tall tower. Nothing here says more.
    tallest = 0
    for mhz in (1.85, 3.6, 7.1, 14.2, 28.4, 50.1, 146.52):
        for kw in ({}, {"use": "dx"}, {"use": "regional"}, {"use": "digital"},
                   {"kind": "dipole"}, {"kind": "invertedv"}, {"kind": "efhw"},
                   {"kind": "loop"}, {"kind": "yagi"}, {"site": "tower"},
                   {"kind": "dipole", "site": "tower", "use": "dx"}):
            tallest = max(tallest, A.recommend(mhz, **kw)["height_ft"])
    check("the tallest height recommended anywhere is a tall tower",
          tallest <= A.TALL_TOWER_FT, True)
    check("  which is below the FAA line with room to spare",
          A.TALL_TOWER_FT < A.FAA_NOTICE_FT, True)

    print("\n-- on the low bands, distance is a vertical --")
    # Half a wave up is 133 ft on 80 m and 266 on 160. Nobody has that, and
    # at the heights people do have a dipole there is an NVIS antenna. The
    # people who work DX on those bands use verticals, because a vertical
    # wants ground rather than height.
    for mhz in (1.85, 3.6):
        r = A.recommend(mhz, use="dx")
        check(f"{mhz} MHz for DX is a quarter-wave vertical", r["type"], "quarter")
        check("  and it says why the dipole is not",
              "Nobody has that" in " ".join(r["why"]), True)
        check("  and names the FAA line",
              "14 CFR 77.9" in " ".join(r["why"]), True)
    check("40 m for DX is still the dipole - 69 ft is a tall tree, not a tower",
          A.recommend(7.1, use="dx")["type"], "dipole")
    check("160 m named the inverted-L as the usual shape",
          "inverted-L" in " ".join(A.recommend(1.85, use="dx")["watch"]), True)

    print("\n-- NVIS is forgiving, and the number knows it --")
    # A fifth of a wave on 160 m is 106 ft. The lobe is overhead at 40 ft too;
    # the ground takes a little more. Sixty is generous.
    check("a wire hung for NVIS on 160 m stops at what people hang wire from",
          A.nvis_height_ft(1.85, "dipole") <= A.NVIS_REACH_FT, True)
    check("  and on 40 m, where the ideal fits, it is the ideal",
          A.nvis_height_ft(7.1, "dipole") < A.NVIS_REACH_FT, True)
    check("regional on 160 m is an inverted-V at that height, not 96 ft",
          A.recommend(1.85, use="regional")["height_ft"] <= A.NVIS_REACH_FT, True)

    print("\n-- the feed swings with height, and the swings are where the books say --")
    # Mutual impedance of the wire and its image (Kraus), against the curve
    # every antenna book prints: about 22 ohms at a tenth of a wave, 50 near
    # 0.16, the 98 ohm high point at 0.35, back through 73 at half a wave.
    r = A.feedpoint_resistance
    check("a tenth of a wave up: low twenties", round(r(0.10)), 22)
    check("fifty ohms near 0.16", abs(r(0.16) - 50) < 4, True)
    check("the high point near 0.35 is about 98", round(r(0.35)), 98)
    check("back through 73 at half a wave", abs(r(0.5) - 73) < 5, True)
    check("and it settles toward 73", abs(r(1.0) - 73) < 3, True)
    marks = A.matching_heights(7.1, 35)
    kinds = [m["what"] for m in marks]
    check("the first landmark is the 50 ohm match", kinds[0], "match")
    check("  at about 23 ft on 40 m", marks[0]["ft"] in (22, 23), True)
    check("  which a 35 ft garden reaches", marks[0]["reachable"], True)
    check("  and the 98 ohm high point at 46 ft it does not",
          next(m for m in marks if m["what"] == "peak")["reachable"], False)
    check("every landmark carries the SWR into 50 ohm coax",
          all(m["swr"] >= 1.0 for m in marks), True)

    print("\n-- the power changes what has to survive, not the antenna --")
    notes = A.power_notes("dipole", 7.1, 100)
    check("#14 at 100 W on 40 m heats the wire by about two watts",
          notes["wire_heat_w"] < 3, True)
    check("  and the note says a thicker wire loses less, not needs more",
          "not need more" in notes["items"][0], True)
    thick = A.power_notes("dipole", 7.1, 100, od_mm=4.8)["wire_heat_w"]
    check("a thicker element loses less", thick < notes["wire_heat_w"], True)
    steel = A.power_notes("dipole", 7.1, 1500, od_mm=2.5, sigma_rel=0.10)["wire_heat_w"]
    check("fence wire at the legal limit is real but survivable heat",
          30 < steel < 100, True)
    efhw = A.power_notes("efhw", 14.2, 100)
    check("an end-fed's far end at 100 W is hundreds of volts",
          400 < efhw["end_volts"] < 600, True)
    check("  and nearly two thousand at the legal limit",
          A.power_notes("efhw", 14.2, 1500)["end_volts"] > 1800, True)
    check("  and the transformer's rating is mentioned",
          any("49:1" in t for t in efhw["items"]), True)
    check("above the legal limit it says so",
          any("97.313" in t for t in A.power_notes("dipole", 7.1, 2000)["items"]), True)
    check("no power, no notes", A.power_notes("dipole", 7.1, 0), None)

    print("\n-- two whips as a dipole: the fact sheet's numbers, not invented ones --")
    # Virginia RACES, 2001-02: a pair at 20 ft, 40 m ~10 dB down on a
    # half-wave dipole, 75 m ~18 dB, 20 m ~6 dB below a G5RV; 2:1 SWR
    # bandwidths ~100/40/20 kHz on 20/40/75 m. What ELMER says must be what
    # was measured, and say who measured it.
    pair = text("whipdipole")
    check("it says the pair needs no ground", "no ground" in pair, True)
    check("  carries the measured losses", all(x in pair for x in ("10 db", "18 db", "6 db")), True)
    check("  and the measured bandwidths", all(x in pair for x in ("100 khz", "40 khz", "20 khz")), True)
    check("  and who measured them", "virginia races" in pair, True)
    check("  the choke recipe is in it", "2643102002" in pair and "turns of coax" in pair, True)
    check("  and the mast isolation", "fibreglass or pvc" in pair, True)
    check("it is horizontal", A.TYPES["whipdipole"]["polarisation"], "horizontal")
    low = A.for_type(7.2, "whipdipole", use="regional", site="portable")
    check("hung low for the region it is an NVIS antenna", low["nvis"], True)
    check("  at a height a TV mast reaches", 8 <= low["height_ft"] <= 30, True)
    power = A.power_notes("whipdipole", 7.2, 100, coil_loss_ohms=8.0, whip_r_rad=2.7)
    check("the power note heats two coils", "two coils" in power["items"][0], True)
    check("  and wants a balun", any("balun" in i for i in power["items"]), True)
    check("  and does not heat a wire it has not got", "wire_heat_w" in power, False)
    sites = " ".join(" ".join(v["works"]) for v in A.SITES.values()).lower()
    check("the balcony and the car park both offer it", sites.count("dipole mount"), 2)
    from elmer import patterns as P
    check("its 2:1 bandwidths come out near the measured 20/40/100 kHz",
          [P.usable_bandwidth("whipdipole", f, q=P.base_q("whipdipole", f))["khz"]
           for f in (3.9, 7.2, 14.2)], [19, 43, 99])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

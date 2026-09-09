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

from elmer import antenna_advice as A  # noqa: E402

FAILS = []

# Every option in the calculator's type selector.
CALCULATOR_TYPES = ["dipole", "invertedv", "efhw", "bowtie", "loop", "quarter",
                    "fiveeighth", "jpole", "groundplane", "yagi", "whip"]


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

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

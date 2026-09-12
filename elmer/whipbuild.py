"""Building the loaded vertical that goes on a vehicle.

The rest of ELMER can tell you a quarter wave on 40 m is 33 feet. Nobody is
putting 33 feet on a truck, so what actually goes on the bumper is a short rod
with a coil in it, and the whole of the engineering is in what that costs you.

There is a commercial answer and a field answer, and this holds both because
they are not in competition: the bought one is cheap enough that building one
to save money is a poor trade, and the reason to build one anyway is that it
is four o'clock, you are three hundred miles from a dealer, and you want to
be on 40 m tonight.

What the numbers here are for
-----------------------------
A short vertical has a radiation resistance of a couple of ohms. Everything
else in the circuit - the coil's own resistance, the mount, the path back
through the vehicle body - is in series with those two ohms and takes its
share of the power in the same proportion. That is the whole reason this
antenna is hard, and it is why the coil and the bond get the attention here
while the rod itself gets a paragraph.

The arithmetic is shown rather than asserted, because the useful thing about
it is not the answer for one whip. It is seeing that halving the loss
resistance does more for you than any amount of care over the rod.
"""
import math

# The thing to measure a home-built one against, named because a comparison
# with nothing is not a comparison. A HamStick-pattern monoband whip is a
# fibreglass rod with the coil wound along it under heatshrink, a stainless
# tip for tuning, and a 3/8-24 stud at the bottom - the thread the whole
# aftermarket uses.
#
# It is worth saying plainly that building one to save money is a poor trade.
# The reason to build one is that it is four o'clock, you are three hundred
# miles from a dealer, and you want to be on 40 m tonight.
COMMERCIAL = {
    "what": "A monoband loaded whip - the HamStick pattern, and the several "
            "makes that copy it.",
    "how": "A fibreglass rod with the loading winding distributed along it "
           "rather than lumped in one coil, a stainless steel tip that slides "
           "for tuning, and a 3/8-24 stud at the base.",
    "costs": "About the price of a tank of fuel, per band. One band each: the "
             "winding is cut for it and there is no tuning across to another.",
    "why_bother_building": "Not money. A bought one is cheap enough that "
                           "building to save is a poor trade. Build one "
                           "because the dealer is three hundred miles away "
                           "and you want to be on the air tonight, or because "
                           "you want to see the thing work rather than own it.",
    "what_you_are_buying": "Survival, mostly. It takes a car wash, a low "
                           "branch and a winter of road salt, and the "
                           "distributed winding spreads the heat and the loss "
                           "along the rod instead of concentrating it in one "
                           "hot coil.",
}

# Where a home-built one is won or lost, in order. The rod is last on purpose.
PARTS = [
    {
        "key": "ground",
        "title": "The bond to the vehicle body",
        "matters": "First, and by a distance. The current that goes up the "
                   "whip has to come back through the body, and everything "
                   "in that path is in series with a radiation resistance of "
                   "one or two ohms. A mount bolted to painted steel, or a "
                   "boot lid hinged on rubber bushes, can put more ohms in "
                   "the way than the antenna has to give.",
        "do": "Scrape to bright metal under the mount and keep it dry. Bond "
              "the lid, the bumper and the exhaust to the body with braid - "
              "a hinge is not a connection. Test it by measuring, not by "
              "looking at it.",
        "cheat": "A magnetic mount is a capacitor to the roof, not a bond, "
                 "and on the low bands that capacitor is most of your loss. "
                 "It works better than it has any right to on 10 m and worse "
                 "than people believe on 80 m.",
    },
    {
        "key": "coil",
        "title": "The loading coil",
        "matters": "The largest single loss you get to choose. Its resistance "
                   "sits in series with those one or two ohms, so a coil of "
                   "thin wire close-wound on a lossy former can halve your "
                   "signal on its own.",
        "do": "Thick wire, spaced turns, on the least lossy former you have. "
              "Air and PTFE are excellent; dry wood and PVC are usable; "
              "anything that gets warm in a microwave is not. Space the turns "
              "about a wire diameter apart - it raises the Q and stops the "
              "winding arcing at the current maximum.",
        "cheat": "Wind it long rather than fat. A coil whose length is about "
                 "twice its diameter has the best Q for the inductance, and "
                 "it is also the shape that fits on a length of pipe.",
    },
    {
        "key": "where",
        "title": "Where the coil goes",
        "matters": "At the base it is easy to build and it is in the hottest "
                   "part of the circuit. Two thirds of the way up it needs "
                   "about half again as much inductance, and it puts current "
                   "into the part of the rod that is doing the radiating.",
        "do": "Centre-load it if you can hold the weight up there. A bought "
              "whip distributes the winding along the whole rod, which is the "
              "same idea taken further than anybody winds by hand.",
        "cheat": "A capacity hat above the coil - three or four spokes, a "
                 "bicycle wheel rim, a disc of mesh - lowers the inductance "
                 "you need and raises the current in the rod. It is the "
                 "cheapest decibel on the whole antenna.",
    },
    {
        "key": "rod",
        "title": "The rod itself",
        "matters": "Least of the four, which surprises people. The losses "
                   "here are small beside the coil and the bond - a "
                   "commercial whip is stainless, which conducts about a "
                   "fortieth as well as copper, and it is still the right "
                   "choice because it survives the road.",
        "do": "Anything stiff, straight and conductive that will take the "
              "wind at fifty miles an hour. Longer beats fatter: the "
              "radiation resistance goes as the square of the height.",
        "cheat": "See what ELMER already knows it can be made of - the "
                 "material list on Make Contact carries the numbers for each.",
    },
]

# What the bench needs, beyond the tools already counted in fieldkit.
BENCH = [
    "A form to wind on: PVC conduit, a bottle, a length of dry broom handle.",
    "Wire heavier than you think - #14 or #12 solid, enamelled if you have "
    "it, bare if you space the turns.",
    "A mount with a 3/8-24 stud if you want to use bought whips on it later. "
    "It is the thread the whole aftermarket speaks.",
    "Braid for bonding, and something abrasive to get to bright metal.",
    "Something to measure with. A loaded whip cannot be cut to length by "
    "arithmetic alone - the coil moves resonance far more than the tip does, "
    "and you will be trimming the tip while watching a meter.",
]

# --- the maker's own tuning chart -------------------------------------------
# Lakeview's Hamstick instruction sheet: exposed stainless whip, in inches,
# against frequency, one chart per model. Read off a scan of the sheet, so
# these are the sheet's own approximations approximated once more; the sheet
# says in bold that the lengths are only approximate and depend on the mount,
# the coax length, other antennas nearby and the matching. Its rule comes
# first and is repeated wherever this table is shown: DO NOT CUT THE WHIP
# FIRST - find resonance with the whip fully extended, then shorten. And
# never let the whip run into the close-wound part of the coil: on some
# models a wire crosses the hollow rod about 6 inches from the top and the
# whip shears it, which voids the warranty; where the whip would reach the
# coil, cut it (score with a file; wire cutters will not take the alloy) so
# it cannot, or the coil heats badly at that point.
#
# (MHz, inches). Each list spans the chart's own axis and nothing beyond it.
LAKEVIEW_CHARTS = {
    "6 m":  {"model": "#9106", "points": [(50.0, 14.8), (51.0, 13.8), (52.0, 12.7), (53.0, 11.6), (54.0, 10.5)]},
    "10 m": {"model": "#9110", "points": [(27.0, 35.0), (27.5, 33.3), (28.0, 31.6), (28.5, 30.0), (29.0, 28.4), (29.5, 27.0)]},
    "12 m": {"model": "#9112", "points": [(24.80, 39.5), (24.85, 39.0), (24.90, 38.5), (24.95, 38.0), (25.00, 37.5), (25.05, 37.0)]},
    "15 m": {"model": "#9115", "points": [(21.0, 43.0), (21.1, 42.7), (21.2, 42.3), (21.3, 42.0), (21.4, 41.8), (21.5, 41.4)]},
    "17 m": {"model": "#9117", "points": [(18.0, 43.4), (18.1, 43.0), (18.2, 42.5), (18.3, 42.1), (18.4, 41.6), (18.5, 41.2)]},
    "20 m": {"model": "#9120", "points": [(13.9, 36.0), (14.0, 35.0), (14.1, 34.2), (14.2, 33.3), (14.3, 32.5), (14.4, 31.7)]},
    "30 m": {"model": "#9130", "points": [(10.00, 40.0), (10.05, 38.6), (10.10, 37.2), (10.15, 35.7), (10.20, 34.2), (10.25, 32.6)]},
    "40 m": {"model": "#9140", "points": [(6.9, 42.3), (7.0, 40.8), (7.1, 39.3), (7.2, 37.8), (7.3, 36.3), (7.4, 34.8)]},
    "75 m": {"model": "#9175", "points": [(3.5, 50.0), (3.6, 47.0), (3.7, 43.5), (3.8, 40.0), (3.9, 37.0), (4.0, 34.0)]},
}

# The same sheet's Figure 1: a capacitor from the feedpoint to ground, for a
# single whip on a vehicle whose SWR will not come under 1.5:1 by tuning. A
# short vertical's feedpoint is well under 50 ohms, and a shunt capacitance at
# the base with the whip left a little long (inductive) is an L-network with
# the whip as the other half. Measured by Lakeview on centre-loaded whips
# clear of surroundings; the sheet says other mountings change the values,
# and to recheck resonance afterwards because matching moves it a little.
# 1000 V rating. Nothing here applies to the two-whip dipole, whose feedpoint
# is a different animal.
MATCH_CAPACITANCE_PF = {
    "75 m": (900, 1200), "40 m": (450, 600), "30 m": (400, 550),
    "20 m": (200, 300), "15 m": (0, 100), "12 m": (0, 50), "10 m": (0, 25),
}

CHART_NOTE = ("Lakeview's own rule, in bold on the sheet: do not cut the whip "
              "first. Find resonance with the whip fully extended, then slide "
              "it in. The chart is approximate - the mount, the coax length "
              "and anything else nearby move it - and the whip must never run "
              "into the close-wound part of the coil: a wire crosses the rod "
              "about six inches from the top on some models and the whip "
              "shears it, which voids the warranty. Where the whip would reach "
              "the coil, score it with a file and break it off; wire cutters "
              "will not take the alloy.")


def stinger_inches(mhz):
    """What Lakeview's chart says to expose at this frequency, or None.

    Linear between the chart's plotted points and nothing outside them: the
    sheet drew each chart across one band and the program does not know
    what the whip does past the edge of the paper.
    """
    mhz = float(mhz)
    for band, chart in LAKEVIEW_CHARTS.items():
        pts = chart["points"]
        if not pts[0][0] <= mhz <= pts[-1][0]:
            continue
        for (f0, l0), (f1, l1) in zip(pts, pts[1:]):
            if f0 <= mhz <= f1:
                frac = 0.0 if f1 == f0 else (mhz - f0) / (f1 - f0)
                inches = l0 + frac * (l1 - l0)
                return {"band": band, "model": chart["model"],
                        "inches": round(inches, 1),
                        "chart_low": pts[0][0], "chart_high": pts[-1][0],
                        "per_100khz": round((l1 - l0) / (f1 - f0) * 0.1, 2),
                        "match_pf": MATCH_CAPACITANCE_PF.get(band)}
    return None


# Free space, near enough for an antenna a few metres long.
C_M_PER_S = 299_792_458.0
FT_PER_M = 3.280839895


def wavelength_m(mhz):
    return C_M_PER_S / (mhz * 1e6)


def radiation_resistance(mhz, height_ft):
    """The ohms that actually radiate, for a short monopole over a ground.

    Rr = 395 (h/lambda)^2, the standard short-monopole result. It is a
    ferocious little equation: the height is squared, so a whip half as tall
    radiates a quarter as well, and the difference between an eight foot whip
    and a four foot one on 40 m is four to one before anything else is
    considered.
    """
    h_m = height_ft / FT_PER_M
    return 395.0 * (h_m / wavelength_m(mhz)) ** 2


def efficiency(mhz, height_ft, loss_ohms):
    """What share of the power leaves, given everything else in series.

    Rr / (Rr + Rloss), which is all it is. The reason to write it down is that
    people expect the answer to be about the antenna and it is mostly about
    the loss.
    """
    rr = radiation_resistance(mhz, height_ft)
    if rr + loss_ohms <= 0:
        return 0.0
    return rr / (rr + loss_ohms)


def db_down(mhz, height_ft, loss_ohms):
    """The same thing in the units people argue in."""
    eff = efficiency(mhz, height_ft, loss_ohms)
    return -99.0 if eff <= 0 else 10.0 * math.log10(eff)


def base_reactance(mhz, height_ft, radius_mm=2.4):
    """How capacitive a short whip looks at its base, in ohms.

    Xc = -Za cot(beta h), with Za = 60 [ln(2h/a) - 1] the average
    characteristic impedance of the rod. This is the number the loading coil
    has to cancel, and it is large - a few hundred to a couple of thousand
    ohms - which is why the coil is the size it is.
    """
    h_m = max(0.05, height_ft / FT_PER_M)
    a_m = max(0.0005, radius_mm / 1000.0)
    za = 60.0 * (math.log(2.0 * h_m / a_m) - 1.0)
    beta_h = 2.0 * math.pi * h_m / wavelength_m(mhz)
    if beta_h >= math.pi / 2:
        return 0.0                      # already a quarter wave or longer
    return -za / math.tan(beta_h)


def base_loading_uh(mhz, height_ft, radius_mm=2.4):
    """The inductance that resonates it, loaded at the base, in microhenries.

    Base loading is the easy build and the worse antenna: the coil sits where
    the current is highest, so its resistance is in the hottest part of the
    circuit, and the rod above it carries less current than it would if the
    coil were further up. Centre loading is the usual commercial compromise -
    see CENTRE_FRACTION.
    """
    xc = abs(base_reactance(mhz, height_ft, radius_mm))
    if xc <= 0:
        return 0.0
    return xc / (2.0 * math.pi * mhz * 1e6) * 1e6


# A coil moved up the rod needs more inductance and gives more signal. Two
# thirds of the way up is the usual commercial compromise, and roughly this
# much more inductance than the same whip loaded at the base.
CENTRE_FRACTION = 0.6
CENTRE_MULTIPLIER = 1.6


def turns_for(uh, radius_in, length_in):
    """Turns of a single-layer air-wound coil, by Wheeler's formula.

    L = r^2 N^2 / (9r + 10l), inches and microhenries, solved for N. It is
    within a few per cent for a coil longer than about half its diameter,
    which is the shape anybody winds on a bottle or a length of pipe.
    """
    if uh <= 0 or radius_in <= 0 or length_in <= 0:
        return 0
    n2 = uh * (9.0 * radius_in + 10.0 * length_in) / (radius_in ** 2)
    return max(1, int(round(math.sqrt(max(0.0, n2)))))


def plan(mhz, height_ft, radius_mm=2.4, form_dia_in=1.5, form_len_in=4.0,
         loss_ohms=12.0):
    """Everything the build needs for one band, worked out together."""
    base_uh = base_loading_uh(mhz, height_ft, radius_mm)
    centre_uh = base_uh * CENTRE_MULTIPLIER
    r = form_dia_in / 2.0
    return {
        "mhz": mhz,
        "height_ft": height_ft,
        "quarter_wave_ft": wavelength_m(mhz) * FT_PER_M / 4.0,
        "radiation_ohms": radiation_resistance(mhz, height_ft),
        "reactance_ohms": base_reactance(mhz, height_ft, radius_mm),
        "base_uh": base_uh,
        "base_turns": turns_for(base_uh, r, form_len_in),
        "centre_uh": centre_uh,
        "centre_turns": turns_for(centre_uh, r, form_len_in),
        "centre_at_ft": height_ft * CENTRE_FRACTION,
        "efficiency": efficiency(mhz, height_ft, loss_ohms),
        "db_down": db_down(mhz, height_ft, loss_ohms),
        "loss_ohms": loss_ohms,
        "form_dia_in": form_dia_in,
        "form_len_in": form_len_in,
    }

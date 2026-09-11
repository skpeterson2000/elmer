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

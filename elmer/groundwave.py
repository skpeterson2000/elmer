"""Ground wave: the part of the signal that never leaves the ground.

Everything else in ELMER about HF is skywave - up to the ionosphere and back
down, hundreds of miles away. The ground wave is the other thing a transmitter
does: a wave that clings to the surface and follows the curve of the earth,
losing strength as it drags across ground that is a poor conductor. It is what
fills the hole in the middle of a skip zone, and it is the honest answer to
"the band plan says nothing closer than 565 miles, so how do I work the next
county".

It is also the one kind of propagation an antenna really does decide, and the
decision is polarization rather than height:

    A vertical antenna has a ground wave. A horizontal one has almost none.

That is not a rule of thumb, it is geometry. At grazing angles the ground
reflects a horizontally polarized wave with its phase inverted, so the
reflection cancels the direct ray almost exactly and there is nothing left to
crawl along the surface. A vertical polarized wave reflects in phase and
survives. This is why every AM broadcast station is a vertical tower, and why a
dipole at thirty feet is not the antenna for working across town on 80m.

The model is Sommerfeld-Norton: the flat-earth surface wave with the standard
attenuation function. Checked against the broadcast ground-wave curves everyone
uses, it reproduces them to a decibel or so over the range that matters, which
is as much as anybody needs to decide whether to bother.
"""
import math

# Conductivity in siemens per metre and relative permittivity, from the ITU's
# standard ground types. The spread is enormous - sea water conducts five
# thousand times better than dry sand - and it is the single biggest thing
# deciding how far a ground wave goes.
GROUND = {
    "sea": {"sigma": 5.0, "epsilon": 80.0,
            "label": "Sea water",
            "note": "The best ground there is. Coastal stations get ground "
                    "wave ranges inland stations never see."},
    "fresh": {"sigma": 0.003, "epsilon": 80.0,
              "label": "Fresh water",
              "note": "High permittivity, poor conductivity - a lake is not "
                      "the sea and does not behave like it."},
    "wet": {"sigma": 0.02, "epsilon": 30.0,
            "label": "Wet ground, marsh",
            "note": "Rich damp soil, bog, irrigated land. The best ordinary "
                    "ground and worth siting for."},
    "average": {"sigma": 0.005, "epsilon": 13.0,
                "label": "Average ground",
                "note": "The default in every textbook and the right guess "
                        "for ordinary farmland and pasture."},
    "poor": {"sigma": 0.002, "epsilon": 10.0,
             "label": "Poor ground, rocky",
             "note": "Hills, rock, sandy loam. Common and quietly costly."},
    "sand": {"sigma": 0.0002, "epsilon": 10.0,
             "label": "Dry sand, desert",
             "note": "Close to an insulator. A ground wave dies fast on it, "
                     "and radials matter more here than anywhere."},
    "city": {"sigma": 0.001, "epsilon": 5.0,
             "label": "City, industrial",
             "note": "Buildings and dry fill. Poor ground and a high noise "
                     "floor arriving together."},
    "ice": {"sigma": 0.001, "epsilon": 3.0,
            "label": "Ice, frozen ground",
            "note": "Frozen soil conducts far worse than the same soil thawed "
                    "- a winter ground wave is shorter than a summer one."},
}


def complex_permittivity(mhz, ground="average"):
    """The ground's electrical character at this frequency.

    eps_c = eps_r - j*60*lambda*sigma. The conduction term shrinks as frequency
    rises, which is the root of why ground wave is a low-band phenomenon: the
    same soil looks progressively less like a conductor the higher you go.
    """
    soil = GROUND.get(ground) or GROUND["average"]
    lam = 299.792458 / float(mhz)                    # metres
    return soil["epsilon"], 60.0 * lam * soil["sigma"], lam


def numerical_distance(km, mhz, ground="average"):
    """Sommerfeld's p - distance measured in how hard the ground is fighting."""
    eps_r, cond, lam = complex_permittivity(mhz, ground)
    magnitude = math.hypot(eps_r, cond)
    return math.pi * (km * 1000.0) / (lam * magnitude)


def flat_attenuation(km, mhz, ground="average"):
    """How much of the wave survives the drag of the ground, 0 to 1.

    The standard approximation to the Sommerfeld attenuation function, on a
    flat earth. It is the curve every broadcast engineer works from, and it
    reproduces the published ones to a decibel over land.
    """
    p = numerical_distance(km, mhz, ground)
    return (2.0 + 0.3 * p) / (2.0 + p + 0.6 * p * p)


# --- and then the earth curves away ------------------------------------------
#
# Sommerfeld's answer is for a flat earth, and over land that hardly matters:
# the ground itself kills the wave long before the horizon does. Over sea it
# matters completely. Sea water is such a good conductor that the attenuation
# function is still 0.84 at a thousand kilometres, so nothing in the flat model
# stops the wave at all - it was claiming a readable 160m signal three thousand
# miles out, which is a skywave answer arrived at by accident.
#
# What stops it is the surface bending away underneath. Past the horizon the
# field has to diffract around the bulge, and the residue series that describes
# that decays exponentially with distance at a rate going as the cube root of
# frequency.
#
# The coefficient is calibrated rather than derived - fitted so the model
# reproduces the sea-path ranges these frequencies are actually built around:
# an MF coast station reaching about 300 miles, 40m about 150, 20m about 100.
# The frequency law was fitted too. A cube root, which is what the residue
# series suggests for the argument, came out too shallow to hold all three
# anchors at once; two thirds fits every one of them inside six per cent with a
# single coefficient, so that is what is used. It is a fitted curve and is
# labelled as one wherever it is shown, the same as the foF2 constants.
CURVATURE_ONSET_KM = 90.0        # divided by the cube root of frequency
CURVATURE_DB_PER_KM = 0.050      # times frequency in MHz to the two thirds
CURVATURE_EXPONENT = 2.0 / 3.0


def curvature_loss_db(km, mhz):
    """Extra loss from diffracting around the curve of the earth."""
    mhz = float(mhz)
    onset = CURVATURE_ONSET_KM / (mhz ** (1.0 / 3.0))
    beyond = max(0.0, float(km) - onset)
    return CURVATURE_DB_PER_KM * (mhz ** CURVATURE_EXPONENT) * beyond


def attenuation(km, mhz, ground="average"):
    """The whole surface-wave attenuation: ground drag and earth curvature."""
    flat = flat_attenuation(km, mhz, ground)
    return flat * 10 ** (-curvature_loss_db(km, mhz) / 20.0)


# A radiated kilowatt from a short vertical over perfect ground makes 300 mV/m
# at a kilometre. Everything else is scaled from that.
REFERENCE_MV_PER_M = 300.0


def field_strength(km, mhz, watts=100.0, ground="average", gain_dbi=0.0):
    """Field strength at a distance, in microvolts per metre and dB above one.

    `gain_dbi` is the transmitting antenna's gain over an isotrope in the
    direction that matters here, which is along the ground. A quarter-wave
    vertical with a decent radial field is about 0 dBi at the horizon; a poor
    ground system costs several dB before the wave has gone anywhere.
    """
    km = max(0.001, float(km))
    watts = max(0.001, float(watts))
    # 300 mV/m is for 1 kW from a short vertical, which is 1.76 dBi.
    scale = math.sqrt(watts / 1000.0) * 10 ** ((gain_dbi - 1.76) / 20.0)
    mv = REFERENCE_MV_PER_M / km * attenuation(km, mhz, ground) * scale
    uv = mv * 1000.0
    return {"uv_per_m": uv, "dbuv_per_m": 20.0 * math.log10(max(1e-9, uv)),
            "mv_per_m": mv, "attenuation": attenuation(km, mhz, ground)}


# Man-made noise, ITU-R P.372: Fa = c - d*log10(f), in dB above thermal. At HF
# this is what you are listening to, not the receiver - which is why a quiet
# site is worth more than a preamplifier.
NOISE_SITES = {
    "quiet": (53.6, 28.6, "Quiet rural - no power lines in earshot"),
    "rural": (67.2, 27.7, "Rural"),
    "residential": (72.5, 27.7, "Residential"),
    "city": (76.8, 27.7, "Business or industrial"),
}

# What a mode needs above the noise to be copied.
MODE_SNR = {"ssb": 10.0, "cw": 3.0, "ft8": -18.0}


def noise_floor_dbuv(mhz, site="rural", bandwidth_hz=2400.0):
    """The noise field strength at this frequency and site, dB above 1 uV/m."""
    c, d, _ = NOISE_SITES.get(site) or NOISE_SITES["rural"]
    fa = c - d * math.log10(max(0.1, float(mhz)))
    # Thermal floor, plus the external noise, plus the bandwidth.
    dbm = -174.0 + fa + 10.0 * math.log10(max(1.0, bandwidth_hz))
    # Power at a 0 dBi antenna back to a field strength.
    return dbm + 20.0 * math.log10(float(mhz)) + 77.2


# Why a horizontal antenna has no ground wave worth the name.
#
# At the grazing angles a surface wave lives at, the ground reflects a
# horizontally polarized wave with its phase turned over. The reflection
# arrives inverted, on top of the direct ray, and the two very nearly cancel -
# exactly, over a perfect conductor, and near enough over real soil. A
# vertically polarized wave reflects in phase and survives.
#
# So this is not a matter of a few decibels to be made up with an amplifier.
# It is a cancellation, and it is why every broadcast tower is a vertical, why
# marine and aeronautical MF work is vertical, and why a dipole at thirty feet
# is the wrong antenna for reaching across the county on 80m however good it
# is for everything else.
HORIZONTAL_NOTE = (
    "A horizontal antenna has essentially no ground wave. At grazing angles "
    "the ground returns a horizontally polarized wave with its phase inverted, "
    "so the reflection cancels the direct ray instead of adding to it. That is "
    "a cancellation rather than a loss, so power does not buy it back - it "
    "wants a vertical.")


def useful_range_km(mhz, watts=100.0, ground="average", site="rural",
                    mode="ssb", gain_dbi=0.0, bandwidth_hz=2400.0,
                    polarization="vertical"):
    """How far the ground wave stays readable. None if it never does.

    Solved rather than tabulated: the field falls monotonically with distance,
    so the crossing with the noise floor is found by bisection.
    """
    if polarization == "horizontal":
        return None
    needed = noise_floor_dbuv(mhz, site, bandwidth_hz) + MODE_SNR.get(mode, 10.0)
    close = field_strength(0.5, mhz, watts, ground, gain_dbi)["dbuv_per_m"]
    if close < needed:
        return None                       # not readable even next door
    lo, hi = 0.5, 5000.0
    if field_strength(hi, mhz, watts, ground, gain_dbi)["dbuv_per_m"] > needed:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if field_strength(mid, mhz, watts, ground, gain_dbi)["dbuv_per_m"] > needed:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def describe(mhz, watts=100.0, ground="average", site="rural", mode="ssb",
             polarization="vertical", gain_dbi=0.0):
    """The whole answer, in the terms somebody would ask the question in."""
    soil = GROUND.get(ground) or GROUND["average"]
    out = {"ground": ground, "ground_label": soil["label"],
           "ground_note": soil["note"], "polarization": polarization,
           "mhz": float(mhz), "watts": float(watts), "mode": mode,
           "site": site, "fitted": True}
    if polarization == "horizontal":
        out.update({"km": None, "miles": None, "note": HORIZONTAL_NOTE})
        return out
    km = useful_range_km(mhz, watts, ground, site, mode, gain_dbi,
                         polarization=polarization)
    out["km"] = None if km is None else round(km, 1)
    out["miles"] = None if km is None else round(km / 1.609)
    out["note"] = (
        "Nothing readable even close in, on this power over this ground."
        if km is None else
        "About %d miles of ground wave from a vertical, over %s, at %g W to "
        "a %s receiver in a %s setting. This is the part of the signal that "
        "never goes near the ionosphere, so it works when the band is shut "
        "and it fills the near end of a skip zone."
        % (round(km / 1.609), soil["label"].lower(), watts, mode.upper(), site))
    return out

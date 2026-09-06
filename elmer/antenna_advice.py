"""What to put up for a frequency and an intention, and how to get it right.

The antenna calculator answers "how long is a dipole for 14.2 MHz", which is
the easy half. A new licensee's actual question is "what should I put up, how
high, which way round, and why is mine not working" - and the honest answers to
those are mostly about height, polarisation and the feedpoint, not about wire
length.

So this turns a frequency and an intended use into a recommendation with its
reasoning attached: what to build, how high to put it, what to feed it with,
what usually goes wrong, and what to do instead when the garden is too small.
The numbers come from the wavelength; the advice is the ordinary consensus of
the craft, written down in one place because a beginner has to collect it from
twenty.

Nothing here is a rule. It is a starting point good enough to make contacts
with, which is what somebody needs before they have the experience to disagree
with it.
"""

C_FT = 983.571                      # speed of light, feet per microsecond


def wavelength_ft(mhz):
    return C_FT / float(mhz)


# Intentions, in the words somebody would use about their own station.
USES = {
    "local": "Local FM - repeaters and simplex",
    "regional": "Regional - out to a few hundred miles",
    "dx": "DX - as far as the band will carry",
    "digital": "Digital modes - FT8, PSK and the like",
    "portable": "Portable or limited space",
}


def default_use(mhz, kind=None):
    """The intention to assume when nobody has said, from where they are tuned."""
    mhz = float(mhz)
    if kind in ("repeater", "simplex"):
        return "local"
    if mhz >= 50.0:
        return "local"
    if kind == "digital":
        return "digital"
    if mhz <= 7.3:
        return "regional"       # 80 and 40 are where a new licensee works nearby
    return "dx"


def _height(mhz, wavelengths, floor_ft, ceiling_ft=None):
    feet = wavelength_ft(mhz) * wavelengths
    feet = max(feet, floor_ft)
    if ceiling_ft:
        feet = min(feet, ceiling_ft)
    return round(feet)


def _feedline(mhz):
    """What the coax does at this frequency, in terms that change a decision."""
    if mhz >= 100:
        return ("At these frequencies thin coax is expensive. RG-58 loses "
                "roughly 6 dB per 100 ft at 2 m - three quarters of your power "
                "before it reaches the antenna. Use RG-8X for short runs and "
                "LMR-400 or equivalent for anything over about 50 ft.")
    if mhz >= 28:
        return ("RG-8X is fine for a short run here; if the coax has to cross "
                "the garden, RG-213 or LMR-400 keeps the loss under a decibel.")
    return ("Loss is not the problem at HF - almost any 50 ohm coax will do. "
            "RG-8X is easy to handle and RG-213 is worth it on long runs.")


def recommend(mhz, use=None, kind=None):
    """A starting antenna for this frequency and intention, with its reasoning."""
    mhz = float(mhz)
    use = use if use in USES else default_use(mhz, kind)
    lam = wavelength_ft(mhz)
    out = {
        "mhz": mhz, "use": use, "use_label": USES[use],
        "wavelength_ft": round(lam, 1),
        "alternative": None, "nvis": False,
    }

    if use == "local" or mhz >= 50.0:
        out.update({
            "type": "jpole",
            "title": "A vertical, as high as you can get it",
            "height_ft": _height(mhz, 0, 20, 40),
            "why": [
                "FM repeaters and simplex are vertically polarised, and a "
                "horizontal antenna hearing a vertical one loses around 20 dB "
                "- more than any amplifier you could buy would give back. "
                "Getting the polarisation right is the single biggest thing "
                "here.",
                "Above 50 MHz you are working line of sight, so height beats "
                "gain. Ten feet higher usually does more than a bigger "
                "antenna, because it is the roofline and the trees in the way "
                "rather than the power.",
            ],
            "watch": [
                "Mount it clear of metal - a mast, gutter or wall within a "
                "couple of feet detunes it and skews the pattern.",
                "Keep the whole antenna out of reach. At 2 m a person standing "
                "beside a transmitting antenna is the RF exposure case that "
                "actually matters.",
            ],
        })
        out["alternative"] = ("A quarter-wave ground plane with four drooping "
                              "radials does the same job and is easier to "
                              "build; the J-pole's advantage is that it needs "
                              "no radials and can be strapped to a mast.")

    elif use == "regional":
        out.update({
            "type": "invertedv",
            "nvis": True,
            "title": "A low dipole, deliberately low",
            "height_ft": _height(mhz, 0.18, 15),
            "why": [
                f"For a few hundred miles you want the signal going up, not "
                f"out. At about a fifth of a wavelength up - {_height(mhz, 0.18, 15)} "
                f"ft here - a horizontal wire radiates almost straight up and "
                f"the ionosphere returns it over the whole region with no skip "
                f"zone in the middle.",
                "This is the one case where a low antenna is the right answer "
                "rather than a compromise, which is worth knowing before "
                "somebody talks you into a tower.",
            ],
            "watch": [
                "Higher is worse here, not better: get it up near half a "
                "wavelength and you start putting a skip zone between you and "
                "the people you are trying to work.",
                "The ends of a dipole are the high-voltage points. Keep them "
                "above head height and away from anything anybody touches.",
            ],
        })
        out["alternative"] = ("A flat dipole between two supports beats an "
                              "inverted-V slightly; the V is here because it "
                              "needs only one support in the middle.")

    elif use == "portable":
        out.update({
            "type": "efhw",
            "title": "An end-fed half wave",
            "height_ft": _height(mhz, 0.25, 15),
            "why": [
                "Fed at one end, so it needs one support and the feedpoint is "
                "where you are standing. Sloping it up into a tree works.",
                "The end of a half wave is a high-impedance point - around "
                "2400 ohms - so it needs a 49:1 transformer, not a direct coax "
                "connection. That transformer is the whole trick.",
            ],
            "watch": [
                "It needs a counterpoise or it will use your coax braid as "
                "one, which puts RF in the shack and noise in the receiver.",
                "The far end carries the high voltage. Tie it off out of reach.",
            ],
        })
        out["alternative"] = ("A quarter-wave vertical with radials laid on the "
                              "ground packs smaller and is less fussy about "
                              "what it is hung from.")

    else:                                     # dx, and digital on HF
        half_wave = _height(mhz, 0.5, 20)
        out.update({
            "type": "dipole",
            "title": "A half-wave dipole, as high as you can manage",
            "height_ft": half_wave,
            "why": [
                f"Height sets the takeoff angle, and takeoff angle decides "
                f"distance. Half a wavelength up - about {half_wave} ft here - "
                f"puts the main lobe low enough to work DX; much lower and you "
                f"are shouting at the sky above you.",
                "A dipole is the reference every other antenna is measured "
                "against, and a well-hung one beats an expensive antenna hung "
                "badly. Start here before spending money.",
            ],
            "watch": [
                "It is broadside: strongest off the sides of the wire, deaf off "
                "the ends. Hang it across the direction you want to work.",
                "Put a 1:1 choke balun at the feedpoint. Without one the coax "
                "braid radiates, the pattern goes where it likes and RF comes "
                "back into the shack.",
                "The ends are high voltage. Keep them out of reach.",
            ],
        })
        if use == "digital":
            out["watch"].append(
                "Digital modes are 100% duty cycle - full power the whole "
                "transmission, not the fifth of it that voice averages. Turn "
                "the power down, and redo the RF exposure evaluation for the "
                "mode you actually run.")
        out["alternative"] = ("No second support? An inverted-V from a single "
                              "mast gives up about a decibel and takes a "
                              "rounder pattern - a good trade for most gardens.")

    out["feedline"] = _feedline(mhz)
    return out

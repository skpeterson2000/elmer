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
    "local": "Local FM - repeaters, simplex and packet",
    "weaksignal": "Weak signal - SSB, CW and EME on VHF and up",
    "satellite": "Satellites",
    "regional": "Regional - out to a few hundred miles",
    "dx": "DX - as far as the band will carry",
    "digital": "Digital modes - FT8, PSK and the like",
    "portable": "Portable or limited space",
}

# What the band plan calls a segment, and what somebody is therefore doing
# there. Above 50 MHz this decides the polarisation, which is the single
# biggest thing about a VHF antenna: FM is vertical and weak-signal work is
# horizontal, and getting it backwards costs about 20 dB.
VHF_KIND_USE = {
    "repeater": "local", "simplex": "local", "digital": "local",
    "cw": "weaksignal", "phone": "weaksignal", "beacon": "weaksignal",
    "image": "weaksignal", "satellite": "satellite",
}


def frequency_context(mhz):
    """What the band plan says this frequency is for, if it says anything.

    Worth asking before assuming. 146.520 is not "a VHF frequency, so probably
    repeaters" - it is the national FM simplex calling channel, and calling it
    a repeater channel is both wrong and a way to annoy people.
    """
    from . import bandplan
    seg = bandplan.segment_at(float(mhz))
    if not seg:
        return None
    return {"band": seg["band"], "kind": seg["kind"], "label": seg["label"],
            "point": seg["high"] <= seg["low"],
            "low": seg["low"], "high": seg["high"]}


def default_use(mhz, kind=None):
    """The intention to assume, read from the band plan rather than guessed."""
    mhz = float(mhz)
    seg = frequency_context(mhz)
    kind = (seg or {}).get("kind") or kind
    label = ((seg or {}).get("label") or "").lower()

    if mhz >= 50.0:
        if kind == "calling":
            # A calling frequency says what it is calling for in its own name.
            if "ssb" in label or "cw" in label:
                return "weaksignal"
            return "local"
        return VHF_KIND_USE.get(kind, "local")

    if kind == "digital" or (kind == "calling" and "ft8" in label):
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

    # Not "or mhz >= 50": that was the original sin here, a blanket assumption
    # that anything above 50 MHz is somebody chasing repeaters. The frequency
    # decides through the band plan now, and this branch only handles the case
    # where it really is FM.
    if use == "local":
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

    elif use == "weaksignal":
        out.update({
            "type": "yagi",
            "title": "A horizontal beam - and horizontal is the point",
            "height_ft": _height(mhz, 0, 25, 60),
            "why": [
                "SSB, CW and EME on VHF and up are worked horizontally "
                "polarised, by long convention and everywhere. This is the "
                "exact opposite of the FM side of the same band, and it is why "
                "the vertical on your roof hears nothing on 144.200 while the "
                "repeaters come booming in.",
                "Cross-polarisation costs around 20 dB. That is not a "
                "refinement - it is the difference between a solid contact and "
                "not knowing anybody is there.",
                "Weak-signal work rewards gain in a way FM does not, because "
                "you are digging signals out of the noise rather than either "
                "hearing a repeater or not. A small beam you can turn is worth "
                "more here than height alone.",
            ],
            "watch": [
                "Mount it well clear of a vertical on the same mast, and of "
                "gutters and wiring - at these wavelengths a metre is a long "
                "way and everything nearby is part of the antenna.",
                "Rotating it matters. A beam pointed the wrong way is worse "
                "than the dipole you did not put up.",
            ],
        })
        out["alternative"] = ("A plain horizontal dipole is the honest place to "
                              "start: it gets the polarisation right, which is "
                              "most of the battle, and costs almost nothing.")

    elif use == "satellite":
        out.update({
            "type": "yagi",
            "title": "A small beam you can point and twist",
            "height_ft": _height(mhz, 0, 6, 12),
            "why": [
                "A satellite is not on the horizon, it is overhead and moving. "
                "A fixed vertical has a null straight up, which is precisely "
                "where the pass is best - so the antenna most people already "
                "own is the wrong shape for this.",
                "A handheld beam solves it cheaply: you point it, and because "
                "you can rotate it in your hands you can chase the "
                "polarisation as the spacecraft tumbles. Height barely matters "
                "here - a clear view of the sky does.",
            ],
            "watch": [
                "Satellites are usually circularly polarised while your beam is "
                "linear, so the signal fades in and out as the two drift "
                "against each other. Twisting the antenna is the fix, and that "
                "fading is normal rather than a fault.",
                "Doppler shifts the frequency through the pass - up on "
                "approach, down going away. You retune as you go, and on the "
                "higher bands you retune a lot.",
            ],
        })
        out["alternative"] = ("A turnstile or eggbeater is omnidirectional and "
                              "needs no aiming, at the cost of the gain a beam "
                              "gives you - a fair trade for unattended or "
                              "digital work.")

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
                "connection. That transformer is an unun, not a balun: a balun "
                "converts balanced to unbalanced, and an end-fed is unbalanced "
                "on both sides. Half the ones on sale are labelled wrongly.",
            ],
            "watch": [
                "It needs a counterpoise, and a choke on the coax below the "
                "unun - a 1:1 current balun, which really is a balun. Without "
                "them the braid becomes the counterpoise: RF in the shack, "
                "noise in the receiver, and an SWR that moves when you touch "
                "the rig.",
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
    out["context"] = frequency_context(mhz)
    return out

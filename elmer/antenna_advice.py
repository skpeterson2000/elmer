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

import re

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
        # Above 50 MHz the kind alone flattens SSB, CW and FT8 into whatever
        # the band mostly does, which is how 2 m SSB came out as "you want FM
        # repeaters". The label says what the segment is actually for, so read
        # it: horizontal and weak-signal, or vertical and FM, are 20 dB apart
        # on the wrong choice. Where a label carries both - 145.00 is weak
        # signal AND packet AND FM simplex - the kind is the tie-breaker,
        # because that is the band plan's own view of what leads there.
        flat = label.replace("-", " ")
        weak = re.search(r"\b(ssb|cw|ft8|eme|beacon|beacons|weak signal|"
                         r"dx window)\b", flat)
        fm = re.search(r"\b(fm|packet|repeater|repeaters|aprs)\b", flat)
        if weak and not fm:
            return "weaksignal"
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


# --- how to use each antenna, rather than how to build one -------------------
#
# The advice below used to be chosen by what you were trying to do, and it
# picked the antenna for you. That is the right answer to "what should I put
# up", and the wrong one to "I have a full-wave loop, now what" - which came
# back recommending a dipole and quietly changing the selection to match.
#
# So every type the calculator can draw carries its own guidance: what makes it
# work, where to put it, what it is bad at, and what to do next once it is up.
# Not a set of plans. A baseline honest enough to depart from.
#
# `height` is (wavelengths, floor_ft, ceiling_ft) - a fraction of a wavelength,
# never below the floor, capped at the ceiling where going higher stops helping.

TYPES = {
    "dipole": {
        "title": "Half-wave dipole",
        "height": (0.5, 20, None),
        "polarisation": "horizontal",
        "why": [
            "The reference every other antenna is measured against, and the "
            "reason gain is quoted in dBd. A well-hung dipole beats an "
            "expensive antenna hung badly, which is most of what there is to "
            "say about antennas.",
            "Height sets the takeoff angle and takeoff angle sets distance. "
            "Half a wavelength up puts the main lobe low enough for DX; at a "
            "quarter wave it fires nearly straight up, which is useless for "
            "distance and exactly right for working your own region.",
        ],
        "watch": [
            "It is broadside - strongest off the sides of the wire, deaf off "
            "the ends. Hang it across the direction you want to work, not "
            "along it.",
            "Put a 1:1 choke balun at the feedpoint. Without one the coax "
            "braid becomes part of the antenna, the pattern goes wherever it "
            "likes and RF comes back into the shack.",
            "The ends are the high-voltage points. Keep them above head "
            "height and away from anything anybody touches.",
        ],
        "better": [
            "Raise it before you do anything else. Ten feet of height is worth "
            "more than any change of wire, connector or brand.",
            "Once it is as high as it goes, turn it: swing the broadside "
            "toward wherever you actually work.",
            "For a second band, hang another dipole from the same feedpoint "
            "rather than buying a tuner. A fan dipole is two wires and a "
            "spreader.",
        ],
    },
    "invertedv": {
        "title": "Inverted-V dipole",
        "height": (0.5, 20, None),
        "polarisation": "horizontal",
        "why": [
            "A dipole that needs one support instead of two, which is why most "
            "wire antennas in the world are this shape. The apex goes up the "
            "mast and the ends slope away to whatever you can tie them to.",
            "The sloping legs round the pattern out - it is less sharply "
            "broadside than a flat dipole, so it is more forgiving about which "
            "way you hung it, at the cost of about a decibel.",
        ],
        "watch": [
            "Keep the angle between the legs above about 90 degrees. Droop "
            "them further and the halves start cancelling each other: the "
            "feedpoint impedance falls, the pattern collapses and the "
            "efficiency goes with it.",
            "The ends come down to where people are. They are the "
            "high-voltage points of the antenna and they need to be out of "
            "reach even though they are the easy part to tie off.",
            "It wants the same 1:1 choke at the feedpoint as any dipole.",
        ],
        "better": [
            "Raise the apex before you widen the legs. The apex is doing most "
            "of the radiating.",
            "If a second support ever appears, flatten it into a proper "
            "dipole and take the decibel back.",
        ],
    },
    "efhw": {
        "title": "End-fed half wave",
        "height": (0.25, 15, None),
        "polarisation": "horizontal",
        "why": [
            "Fed at one end, so it needs one support and the feedpoint is "
            "where you are standing. Sloping it up into a tree works, which is "
            "why it is the portable operator's antenna.",
            "It is a half wave like any other, so it radiates like one. What "
            "is unusual is only where the feed is.",
        ],
        "watch": [
            "The end of a half wave is a high-impedance point, around 2400 "
            "ohms, so it needs a 49:1 transformer rather than a direct coax "
            "connection. That transformer is an unun, not a balun - an "
            "end-fed is unbalanced on both sides. Half the ones on sale are "
            "labelled wrongly.",
            "It needs a counterpoise and a choke on the coax below the unun. "
            "Without them the braid becomes the counterpoise: RF in the shack, "
            "noise in the receiver, and an SWR that moves when you touch the "
            "rig.",
            "The far end carries the high voltage. Tie it off out of reach.",
        ],
        "better": [
            "A counterpoise about a twentieth of a wavelength long, run away "
            "from the coax, does more for it than any other single change.",
            "Get the far end higher than the feed end. A sloper radiates "
            "mostly from its high half.",
        ],
    },
    "bowtie": {
        "title": "Bowtie dipole",
        "height": (0.5, 20, None),
        "polarisation": "horizontal",
        "why": [
            "A dipole whose legs are two wires spread apart instead of one. "
            "The spread makes it electrically fatter, and a fatter antenna has "
            "a lower Q - which is to say a wider band.",
            "This is the answer to 80 m, where an ordinary dipole is sharp "
            "enough that CW at the bottom and phone at the top are two "
            "different antennas.",
        ],
        "watch": [
            "The width buys bandwidth and does almost nothing for the resonant "
            "length. Cut it as a dipole and let the spreaders do their own "
            "job.",
            "It is still broadside and still needs a choke, and the ends are "
            "still where the voltage is.",
            "More wires and spreaders mean more windage and more to break. It "
            "is a heavier antenna than it looks in a drawing.",
        ],
        "better": [
            "Widen the spread before lengthening anything - that is the knob "
            "that moves bandwidth.",
            "If you only need two spots in a band rather than all of it, a fan "
            "of two thin dipoles is lighter and sharper.",
        ],
    },
    "loop": {
        "title": "Full-wave loop",
        "height": (0.5, 20, None),
        "polarisation": "horizontal",
        "why": [
            "A full wavelength of wire closed on itself. It has a decibel or "
            "two on a dipole and, more usefully, it is quiet: a closed loop "
            "responds to the magnetic field and rejects a good deal of the "
            "local electrical noise a dipole hears.",
            "On a noisy suburban lot that quietness is worth more than the "
            "gain. The signal you can hear beats the signal you cannot.",
            "Hung horizontally and low it fires upward and is a fine regional "
            "antenna; stood up vertically it takes a lower angle and works "
            "distance.",
        ],
        "watch": [
            "The feedpoint is nearer 100 ohms than 50, so it wants a 4:1 balun "
            "or a quarter-wave section of 75-ohm line to match it. Fed "
            "straight with 50-ohm coax it will show a permanent 2:1.",
            "Area matters more than shape. A square is best, a triangle is "
            "fine, and a loop bent around three trees is still a loop - do not "
            "let the geometry stop you putting it up.",
            "It is a full wavelength of wire: on 80 m that is 270 feet, which "
            "is a real estate question before it is an antenna question.",
        ],
        "better": [
            "Get it square before you get it high. Area is the thing.",
            "Feed it at a corner for one polarisation and at the middle of a "
            "side for the other - a free choice most people never make.",
        ],
    },
    "quarter": {
        "title": "Quarter-wave vertical",
        "height": (0.25, 8, None),
        "polarisation": "vertical",
        "why": [
            "Half the wire of a dipole and no need to get it high, because it "
            "works against the ground rather than against its other half. It "
            "radiates at a low angle, which is what distance wants.",
            "It is also the only HF antenna with a ground wave worth the name. "
            "Vertical polarisation survives at the surface where horizontal "
            "cancels against its own reflection, so this is the antenna for "
            "reaching into a skip zone.",
        ],
        "watch": [
            "The radials are the antenna, not an accessory. A quarter wave "
            "over four radials wastes most of its power heating the soil; the "
            "difference between four and thirty-two is several decibels, which "
            "is more than any amplifier in the budget.",
            "More radials buy efficiency, not gain - the pattern hardly "
            "changes. What changes is how much of your power leaves.",
            "It hears everything the neighbourhood emits, because vertical is "
            "the polarisation most noise arrives in. A quiet receiving antenna "
            "and a noisy transmitting one is a normal pairing.",
        ],
        "better": [
            "Lay more radials. Thirty short ones beat four long ones, and they "
            "do not need to be resonant or tidy.",
            "Move it away from the house and toward open ground or water. "
            "What is under the first quarter wavelength matters more than what "
            "the antenna is made of.",
        ],
    },
    "fiveeighth": {
        "title": "5/8-wave vertical",
        "height": (0.625, 8, None),
        "polarisation": "vertical",
        "why": [
            "Taller than a quarter wave and lower-angled for it - about three "
            "decibels toward the horizon, which on VHF is the difference "
            "between reaching the repeater and not.",
            "That is why it is the standard mobile whip on 2 m: the gain goes "
            "where the traffic is rather than up into the sky.",
        ],
        "watch": [
            "Five eighths of a wave is not resonant, so it needs a matching "
            "coil at the base. That coil is part of the antenna and not "
            "optional.",
            "It still needs a ground plane - radials, or a vehicle roof. On a "
            "boot lid or a magnet on a thin panel it is working against "
            "nothing much.",
            "The low angle is a liability as well as an asset: for a repeater "
            "on a hill above you, a quarter wave with its higher lobe can hear "
            "better.",
        ],
        "better": [
            "Get it to the middle of the roof. A ground plane that is "
            "symmetrical beats one that is large.",
            "On HF this is a big antenna for little return - the quarter wave "
            "and better radials is usually the smarter spend.",
        ],
    },
    "jpole": {
        "title": "J-pole",
        "height": (0, 20, 40),
        "polarisation": "vertical",
        "why": [
            "An end-fed half wave with a quarter-wave matching stub built into "
            "the bottom of it, so it needs no radials at all - which is why it "
            "ends up strapped to masts, fences and chimneys everywhere.",
            "Vertically polarised, so it is the right shape for FM repeaters "
            "and simplex, where getting the polarisation right is worth more "
            "than any amount of gain.",
        ],
        "watch": [
            "It is notorious for common-mode current: the feedline runs "
            "alongside the stub and becomes part of the radiator. A choke a "
            "quarter wave below the feedpoint is not optional, and a J-pole "
            "with a hot feedline has a pattern nobody can predict.",
            "Mount it clear of the mast. The mast is a conductor running "
            "parallel to the antenna and it will detune it and skew the "
            "pattern if it is within a foot or so.",
            "Keep the whole thing out of reach. At 2 m somebody standing "
            "beside a transmitting antenna is the RF exposure case that "
            "actually matters.",
        ],
        "better": [
            "Height, then height. Above 50 MHz you are working line of sight "
            "and ten feet usually beats a bigger antenna.",
            "Add the choke before you add anything else, then check whether "
            "the SWR still moves when you touch the coax.",
        ],
    },
    "groundplane": {
        "title": "Ground plane with drooping radials",
        "height": (0, 20, None),
        "polarisation": "vertical",
        "why": [
            "A quarter-wave vertical carried up in the air with its own ground "
            "underneath it - four radials instead of the earth, so the soil "
            "stops mattering.",
            "The radials droop for a reason worth knowing: horizontal, the "
            "feedpoint sits near 36 ohms; sloped to about 45 degrees it rises "
            "to near 50 and matches coax directly. The droop is a matching "
            "device, not a construction convenience.",
        ],
        "watch": [
            "Four radials elevated is genuinely enough - unlike a ground-"
            "mounted vertical, where four is a waste. Elevated radials are a "
            "ground plane; buried ones are a loss reduction scheme.",
            "It is vertically polarised, so it is the wrong antenna for "
            "horizontal weak-signal work on the same band and the right one "
            "for FM.",
            "Keep it clear of the mast and of gutters. Anything conductive "
            "within a fraction of a wavelength joins in.",
        ],
        "better": [
            "Raise it. An elevated ground plane a half wave up is a different "
            "antenna from one on a fence post.",
            "Adjust the droop angle to trim the match before you start cutting "
            "the radiator.",
        ],
    },
    "yagi": {
        "title": "Yagi-Uda beam",
        "height": (0.5, 25, None),
        "polarisation": "horizontal",
        "why": [
            "One driven element and a row of parasitic ones that re-radiate "
            "in step, so the signal adds up forwards and cancels backwards. "
            "The reward is gain in one direction and deafness in the others - "
            "which is as much about not hearing the interference as about "
            "hearing the contact.",
            "Boom length is what buys gain, not element count. A long "
            "three-element beam beats a cramped five-element one, and the "
            "spacing is the design.",
        ],
        "watch": [
            "It has to be pointed. A beam aimed the wrong way is worse than "
            "the dipole you did not put up, and the front-to-back that makes "
            "it quiet also makes it blind.",
            "Height still sets the takeoff angle. A beam at fifteen feet is an "
            "expensive way to work the next county.",
            "It is a real structure in the wind, on a rotator, at the top of a "
            "mast. The engineering is a bigger part of this antenna than the "
            "electrical design.",
        ],
        "better": [
            "Get it higher before adding elements. Height changes the angle; "
            "elements only sharpen what the angle already decided.",
            "Learn where it is deaf. Turning it 20 degrees to null a noise "
            "source is a trick a dipole cannot do at all.",
        ],
    },
    "whip": {
        "title": "Loaded mobile whip",
        "height": (0, 4, 12),
        "polarisation": "vertical",
        "why": [
            "A quarter wave on 40 m is 33 feet and does not fit on a car, so a "
            "coil replaces the missing wire electrically. What is left is a "
            "short radiator that resonates where it should.",
            "It works, and the reason it works at all is worth understanding: "
            "you are trading efficiency for a length that fits, deliberately, "
            "and knowing the size of the trade is what lets you improve it.",
        ],
        "watch": [
            "A shortened antenna has a tiny radiation resistance - a few ohms "
            "on 80 m - so the loss resistance in the coil, the connections and "
            "the ground path is what most of the power goes into. Efficiency, "
            "not SWR, is the thing to work on. A perfect 1:1 can be a perfect "
            "match into a heater.",
            "The vehicle is the other half of the antenna. A bad bond between "
            "the mount, the body and the exhaust does more damage than the "
            "coil.",
            "It is sharp. Moving a hundred kilohertz can be enough to need "
            "retuning, which is why continuously tunable screwdriver antennas "
            "exist.",
        ],
        "better": [
            "Know what you are actually working. A contact made driving down "
            "the road is ground wave - vertically polarised, following the "
            "surface - not line of sight and not the ionosphere. That is why "
            "it works at all on a nine-foot antenna, and why it is measured in "
            "tens of miles rather than hundreds.",
            "Move the coil up the whip. Centre loading beats base loading by "
            "a decibel or two, because it puts current where the radiating "
            "happens.",
            "Bond the vehicle properly, then mount as high and as central as "
            "the car allows - a roof beats a bumper by more than any coil "
            "change.",
        ],
    },
}


# Whether the antenna somebody has chosen suits what they said they are doing.
# Not to overrule them - they may have one mast, one wire and no choice - but
# because the mismatch is the thing worth knowing, and it is almost always
# polarisation or takeoff angle rather than anything exotic.
WANTS = {
    "local": ("vertical", "FM repeaters and simplex are vertically polarised, "
              "and a horizontal antenna hearing a vertical one loses around "
              "20 dB - more than any amplifier would give back."),
    "weaksignal": ("horizontal", "SSB and CW above 50 MHz are worked "
                   "horizontally polarised, everywhere and by long "
                   "convention. This is the opposite of the FM side of the "
                   "same band."),
}
LOW_ANGLE = {"quarter", "fiveeighth", "groundplane", "jpole", "whip"}


def suits(kind, use, mhz):
    """Whether this antenna is the right shape for this intention."""
    spec = TYPES.get(kind)
    if not spec:
        return None
    want = WANTS.get(use)
    if want and spec["polarisation"] != want[0]:
        return {"verdict": "wrong shape",
                "note": "A %s is %s polarised and %s. %s Nothing else you do "
                        "to this antenna will get that back."
                        % (spec["title"].lower(), spec["polarisation"], use,
                           want[1])}
    if use == "regional":
        if kind in LOW_ANGLE:
            # True about the skywave and only half the story. A vertical is
            # the one antenna with a ground wave worth having, so it covers
            # the near end that a low horizontal wire reaches over the top of.
            # Saying only "wrong shape" contradicts every operator who has
            # made contacts down the road on a mobile whip.
            reach = ""
            try:
                from . import groundwave
                km = groundwave.useful_range_km(mhz, 100.0, "average")
                if km:
                    reach = (" What it does have is a ground wave - about %d "
                             "miles of it here at 100 W over average ground, "
                             "vertically polarised and hugging the surface. "
                             "That is the near end a low wire flies straight "
                             "over, and it is the one thing a horizontal "
                             "antenna cannot do at all."
                             % round(km / 1.609))
            except Exception:
                pass
            return {"verdict": "wrong shape for the far end",
                    "note": "Near-vertical incidence needs the signal going "
                            "up, and a %s puts it out along the ground - which "
                            "is the one direction that does not come back down "
                            "a few hundred miles away.%s"
                            % (spec["title"].lower(), reach)}
        return {"verdict": "works, hung low",
                "note": "For regional work hang it deliberately low, around a "
                        "fifth of a wavelength. This is the one case where low "
                        "is the right answer rather than a compromise, and "
                        "getting it up near half a wave puts a skip zone "
                        "between you and the people you are trying to work."}
    if use == "dx" and spec["polarisation"] == "vertical":
        # The thing a vertical is genuinely best at, and the reason a nine-foot
        # whip on a moving car works distance that a wire in a garden does not.
        # It is not that the whip is efficient - it is badly inefficient - it
        # is that what little it radiates leaves at the right angle.
        return {"verdict": "well suited",
                "note": "A vertical needs no height to get a low takeoff "
                        "angle: it has one by its shape, against the ground "
                        "rather than above it. Low angle is what distance "
                        "wants, which is why a short loaded whip on a car "
                        "works stations a horizontal wire in a garden cannot "
                        "reach - not because it is efficient, it is not, but "
                        "because the little it does radiate leaves at the "
                        "right angle. Spend the effort on the ground system, "
                        "which is where the loss is."}
    if use == "dx" and kind in ("dipole", "invertedv", "bowtie", "loop"):
        return {"verdict": "works, hung high",
                "note": "For distance the height is the whole argument: it "
                        "sets the takeoff angle, and a wire antenna below a "
                        "quarter wave is shouting at the sky above it however "
                        "well it is made."}
    if use == "satellite" and kind != "yagi":
        return {"verdict": "wrong shape",
                "note": "A pass is overhead and moving, and a fixed antenna "
                        "has a null exactly where the pass is best. This wants "
                        "something small you can point and twist by hand."}
    return {"verdict": "suits it", "note": ""}


def for_type(mhz, kind, use=None):
    """How to use the antenna somebody has actually chosen.

    The other half of `recommend`. That one answers "what should I put up";
    this answers "I have one of these, now what" - which is the question
    somebody asks once they own an antenna, and the one the tool used to
    answer by recommending a dipole instead.
    """
    mhz = float(mhz)
    spec = TYPES[kind]
    use = use if use in USES else default_use(mhz, kind)
    fraction, floor, ceiling = spec["height"]
    height = _height(mhz, fraction, floor, ceiling)
    fit = suits(kind, use, mhz)
    return {
        "mhz": mhz, "use": use, "use_label": USES[use],
        "wavelength_ft": round(wavelength_ft(mhz), 1),
        "type": kind, "chosen": True,
        "title": spec["title"],
        "height_ft": height,
        "polarisation": spec["polarisation"],
        "why": list(spec["why"]),
        "watch": list(spec["watch"]),
        "better": list(spec["better"]),
        "fit": fit,
        "nvis": use == "regional" and spec["polarisation"] == "horizontal",
        "alternative": None,
        "feedline": _feedline(mhz),
        "context": frequency_context(mhz),
    }


def recommend(mhz, use=None, kind=None):
    """A starting antenna for this frequency and intention, with its reasoning."""
    mhz = float(mhz)
    # Somebody who named an antenna wants to be taught that antenna, not
    # talked back to a dipole.
    if kind in TYPES:
        return for_type(mhz, kind, use)
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
                "On open-wire line instead of coax it becomes an end-fed "
                "Zepp: a real antenna, but only one conductor of the feeder "
                "attaches to the wire, so the feeder currents never balance and "
                "it radiates. Centre-feed it as a doublet if that matters.",
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

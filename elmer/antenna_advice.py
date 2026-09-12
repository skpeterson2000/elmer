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

import math
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
    from . import bandplan, personal
    seg = bandplan.segment_at(float(mhz))
    if not seg:
        # Not ours does not mean not anybody's. A J-pole for 462.675 or a
        # whip for channel 19 is an ordinary antenna question from a GMRS
        # licensee or a CB owner, and the answer is the same physics; what
        # changes is the use assumed - these are all local FM or AM
        # simplex, none of them weak-signal work.
        theirs = personal.service_at(float(mhz))
        if not theirs:
            return None
        return {"band": theirs["name"], "kind": "simplex",
                "label": theirs["label"], "point": True,
                "low": theirs["mhz"], "high": theirs["mhz"],
                "service": theirs}
    return {"band": seg["band"], "kind": seg["kind"], "label": seg["label"],
            "point": seg["high"] <= seg["low"],
            "low": seg["low"], "high": seg["high"]}


def default_use(mhz, kind=None):
    """The intention to assume, read from the band plan rather than guessed."""
    mhz = float(mhz)
    seg = frequency_context(mhz)
    kind = (seg or {}).get("kind") or kind
    label = ((seg or {}).get("label") or "").lower()

    if (seg or {}).get("service") and mhz < 50.0:
        return "regional"       # CB: the next few miles of road, not DX

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


# What anybody actually builds. A hundred feet is a tall amateur tower - most
# are half that - and it is the ceiling on every height this module suggests
# when nothing about the site has been said. Half a wavelength on 160 m is
# 266 ft, and a program that says "aim for 266 ft" has stopped advising and
# started reciting. Above 200 ft the FAA has to be notified before anything
# goes up (14 CFR 77.9) and the structure registered with the FCC (47 CFR
# Part 17), which is a second reason the number is never that.
TALL_TOWER_FT = 100
FAA_NOTICE_FT = 200

# Above this a half-wave dipole is not the answer for distance, whatever the
# textbook says: a wire that high is not a thing most people have, and at the
# heights they do have a dipole on 80 or 160 m is a near-vertical NVIS antenna
# good for a few hundred miles. The people who work DX on those bands use
# verticals, because a vertical wants radials on the ground rather than height
# in the air. Seventy feet is the far edge of what tall trees give.
DIPOLE_REACH_FT = 70

# And the same for a wire hung *for* NVIS: its ideal on 160 m is 106 ft, and
# it works at 40 because the lobe is overhead either way. Sixty is generous.
NVIS_REACH_FT = 60


def _height(mhz, wavelengths, floor_ft, ceiling_ft=None):
    feet = wavelength_ft(mhz) * wavelengths
    feet = max(feet, floor_ft)
    feet = min(feet, ceiling_ft or TALL_TOWER_FT)
    return round(feet)


def _too_high_to_build(mhz, wavelengths):
    """The height the textbook wants, when it is more than anybody builds."""
    wanted = wavelength_ft(mhz) * wavelengths
    return round(wanted) if wanted > TALL_TOWER_FT else None


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
        "better_nvis": [
            "Keep the ends up. They are the part nearest the ground and the "
            "part that loses power into it - a few feet of clearance is worth "
            "having, and they are the high-voltage ends anyway.",
            "The apex has to sit higher than the height you actually want, "
            "because a V radiates from the current-weighted middle of its "
            "legs rather than from its peak. That allowance is already in the "
            "figure above.",
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
            "Know which one you are working, because this antenna does both, and they are not the same contact. Close in it is ground wave - vertically polarised, hugging the surface, tens of miles of it, and the one kind of propagation a horizontal wire cannot manage at all. The contacts that surprise people are the other kind: a short vertical launches at a low angle, so what little it radiates leaves flat and comes back off the F layer hundreds or thousands of miles out. Working across the country from a moving car on 20 m is not ground wave - it is the ionosphere, reached by an antenna that is inefficient but aimed right. Being inefficient and being short-ranged are different failures, and this antenna only has the first.",
            "Move the coil up the whip. Centre loading beats base loading by "
            "a decibel or two, because it puts current where the radiating "
            "happens.",
            "Bond the vehicle properly, then mount as high and as central as "
            "the car allows - a roof beats a bumper by more than any coil "
            "change.",
        ],
    },
    "screwdriver": {
        "title": "Screwdriver - motor-tuned mobile vertical",
        "height": [0, 5, 12],
        "polarisation": "vertical",
        "why": [
            "A loaded whip is resonant on one band. This one moves its own "
            "coil: a motor drives the winding in and out of the form, so the "
            "same antenna is resonant anywhere from 40 m to 10 m - and on the "
            "big ones from 80 - with no tap to change and no tuner to hide "
            "behind. It is named for the cordless screwdriver the first ones "
            "were built out of.",
            "That is a real trick and it is worth having. What it does not do "
            "is make the antenna long. It is the same short radiator with the "
            "same small radiation resistance, and the coil that makes it "
            "resonant is also where a great deal of the power goes.",
        ],
        "watch": [
            "Resonant is not efficient. The motor will find you a 1:1 on any "
            "frequency you like, and a perfect match into a lossy coil is "
            "still a lossy coil. Efficiency climbs steeply with frequency: on "
            "10 m the whip is most of a quarter wave and behaves like one; on "
            "80 m it is largely a heater with an excellent SWR.",
            "It is sharpest exactly where it is least efficient. Reckon on "
            "retuning after a few tens of kilohertz on 40 m and a couple of "
            "hundred on 20 - which is not a fault, it is the reason the motor "
            "is there. ELMER works the figure out for the frequency you are "
            "on rather than quoting one number for the whole decade.",
            "Do not transmit while it is moving. The contact crossing turns "
            "under power arcs, and pitted contacts are how one of these "
            "starts refusing to tune.",
            "When one stops tuning it is nearly always water and corrosion in "
            "the coil rather than the motor. They live on a bumper at 70 mph "
            "in the rain, which is a hard life for a variable inductor.",
            "The vehicle is still the other half of the antenna. A "
            "screwdriver on a badly bonded mount is a good antenna wasted, "
            "exactly as any mobile whip would be.",
        ],
        "better": [
            "A capacitance hat above the coil is the single best thing most "
            "of these can be given. It raises the radiation resistance and "
            "shortens the coil needed to resonate, which is efficiency bought "
            "with a few ounces of wire and a little wind loading.",
            "Get the base up out of the bodywork. A bumper mount low behind a "
            "steel body is shielded from a good part of the world, and height "
            "at the base does more than length at the top.",
            "Counterpoise, on anything that is not a large steel vehicle. A "
            "fibreglass camper, a trailer or a stationary set-up needs "
            "radials laid out, and the difference is not subtle.",
            "Learn roughly where the coil sits for each band. An automatic "
            "controller hunts for minimum SWR, which is fine until it hunts "
            "across a band edge - knowing where it should be is how you catch "
            "that before you key up.",
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


# Near-vertical incidence wants the antenna low, and "low" is a fraction of a
# wavelength rather than a number of feet. These mirror the constants the
# evaluator in the Lab uses, and they have to: the tool told somebody to put an
# inverted-V up at 69 feet for NVIS on 40m and then, three inches further down
# the same page, marked 69 feet as too high for NVIS. Both halves were reading
# the same antenna and only one of them knew what it was for.
NVIS_LOW, NVIS_TARGET, NVIS_HIGH = 0.15, 0.20, 0.25

# An inverted-V does not radiate from its apex. The pattern follows the
# current-weighted mean height, and current is greatest at the centre, so the
# mean sits (pi - 2) / pi of the way out along each sloping leg. The apex
# therefore has to be higher than the height you actually want by whatever the
# legs drop - which is why the right apex for NVIS comes out near 35 ft on 40m
# and not the 28 the bare fraction would suggest.
V_CENTROID = (math.pi - 2) / math.pi
DEFAULT_DROOP_DEG = 35.0          # what the Lab's droop slider starts at


# Where to go from here is a different list when the point is to go up.
#
# Every horizontal antenna's improvement advice began "raise it", because for
# distance that is the whole answer and almost nothing else matters. Hung for
# near-vertical incidence it is precisely wrong, and it was being printed under
# a height that had just been chosen to be low - so the tool told somebody to
# put an inverted-V at 35 feet and then, in the next paragraph, to raise it.
NVIS_BETTER = [
    "Leave it low. This is the one case in the book where higher is worse: "
    "take it up toward half a wavelength and the lobe splits, and a skip zone "
    "opens between you and the people you put it up to work.",
    "Lay a wire on the ground underneath it instead, a few per cent longer "
    "than the antenna and roughly below it. It acts as a reflector, is worth "
    "a couple of decibels over ordinary soil, and steadies the pattern on "
    "ground that would otherwise be swallowing the downward half.",
    "After that the antenna is not the control any more - the band is. NVIS "
    "works while the frequency stays under the critical frequency, so when it "
    "stops working the answer is a lower band, not a higher mast. The "
    "propagation page says what the critical frequency is right now.",
]


def nvis_height_ft(mhz, kind):
    """How high to hang a horizontal antenna when the point is to go up."""
    wanted = NVIS_TARGET * wavelength_ft(mhz)
    if kind == "invertedv":
        # Half of 468/f, the length each leg actually is.
        leg = 234.0 / float(mhz)
        wanted += V_CENTROID * leg * math.sin(math.radians(DEFAULT_DROOP_DEG))
    # On 160 m a fifth of a wave is 106 ft, which is "deliberately low" only
    # in the arithmetic. NVIS is forgiving of being lower than its ideal - the
    # lobe stays overhead, the ground takes a little more - so the number
    # stops at what people hang wire from, and the site's own cap below it.
    return max(12, min(NVIS_REACH_FT, round(wanted)))


# --- what you have actually got ---------------------------------------------
#
# "Half a wavelength up" is 69 feet on 40m. On a farm that is a mast; in a flat
# it is a daydream, and printing it at somebody in a flat is not advice, it is
# a door closing. Worse, it is the wrong answer: a low antenna is not a broken
# one, it is a different one, and the arithmetic says so plainly. At 25 feet on
# 40m the main lobe is straight up - which makes you a near-vertical station
# whether you meant to be or not, and that is a real capability with a name.
#
# So the height is capped by what somebody can actually do, and the consequence
# is stated as a number rather than softened.
SITES = {
    "tower": {
        "label": "A mast or tower, and room for it",
        "max_ft": None,
        "works": ["Whatever the band calls for. This is the case every book "
                  "is written about."],
        "costs": [],
        "good_at": "everything the textbook says, which is why the textbook "
                   "says it",
    },
    "house": {
        "label": "A house, a garden, some trees",
        "max_ft": 35,
        "works": ["A wire from the roofline to a tree, which is most of the "
                  "wire antennas in the world.",
                  "A vertical at the bottom of the garden, where its radials "
                  "can lie under the lawn and it is away from the house wiring."],
        "costs": ["Thirty-five feet is under half a wave below about 14 MHz, "
                  "so on 40m and 80m the takeoff angle stays high. That is a "
                  "regional station on the low bands and a DX one on the high "
                  "ones, from the same wire."],
        "good_at": "20m and up for distance, 40m and 80m for your own region",
    },
    "small": {
        "label": "A small lot or a short garden",
        "max_ft": 22,
        "works": ["A low dipole or inverted-V. At this height on the low bands "
                  "it is a near-vertical antenna, which is a capability rather "
                  "than a compromise - it will work the whole state reliably "
                  "when the tower stations are talking over the top of it.",
                  "A quarter-wave vertical, which needs no height at all. It "
                  "wants radials rather than air, and radials fit under grass."],
        "costs": ["On 40m and below the lobe is essentially straight up. "
                  "Chasing DX from here on those bands is fighting the "
                  "geometry; on 20m and up the same wire is a fair performer."],
        "good_at": "regional work on the low bands, and everything normal "
                   "above 14 MHz",
    },
    "attic": {
        "label": "Indoors - the attic or roof space",
        "max_ft": 25,
        "works": ["A dipole folded to fit the roof line. Bending the ends down "
                  "or back costs less than not having an antenna.",
                  "Anything on 20m and up, where the wire is short enough to "
                  "fit without folding."],
        "costs": ["A decibel or several into the roof, more with a wet roof, "
                  "and foil-backed insulation or a metal roof stops it dead - "
                  "check before you build.",
                  "Everything in the house is now inside the near field. "
                  "Interference to your own electronics and the RF exposure "
                  "assessment become the limits here, not the antenna."],
        "good_at": "getting on the air at all when nothing outside is allowed",
    },
    "apartment": {
        "label": "A flat - a balcony, or a window",
        "max_ft": 0,
        "works": ["A small magnetic loop. It is tunable, it works indoors, it "
                  "is quiet, and it has deep nulls you can turn onto a noise "
                  "source - which in a block of flats is worth more than gain.",
                  "A wire out of a window, sloping to anywhere it can be tied, "
                  "fed against a counterpoise run along the skirting.",
                  "A short vertical clamped to the balcony rail, with the rail "
                  "itself as the counterpoise."],
        "costs": ["No ground and no space, so efficiency is poor and low-angle "
                  "performance is largely out of reach on the low bands.",
                  "The noise floor is usually the real enemy rather than the "
                  "antenna. A city flat can be twenty decibels noisier than a "
                  "field, which costs more than any antenna choice - so a "
                  "quiet antenna beats an efficient one here, and that is why "
                  "the loop is first on the list."],
        "good_at": "20m and up, digital modes, and - if you are high up - "
                   "VHF and UHF from a location most people would envy",
    },
    "mobile": {
        "label": "In the vehicle - mounted on the car or truck",
        # The feedpoint on a roof or a fender sits about here. It is used the
        # same way every other site's cap is: to say what a horizontal antenna
        # would be doing at that height, which on a car is nothing good, and
        # to make the point that height is not the lever here.
        "max_ft": 6,
        "works": ["A loaded whip, which is what this site is for. On 40 m a "
                  "quarter wave is 33 feet and does not fit on a car, so a "
                  "coil stands in for the missing wire and what is left is "
                  "short, sharp and inefficient - deliberately, and knowing "
                  "the size of that trade is what lets you improve it.",
                  "A screwdriver or a tapped coil if you change bands. A "
                  "hamstick is one band and moving a hundred kilohertz can be "
                  "enough to need retuning it.",
                  "VHF and UHF, where a quarter wave is a few inches, the "
                  "whole antenna is full size and efficient, and the car roof "
                  "is a genuinely good ground plane. This is the one place "
                  "where the mobile installation is not a compromise at all."],
        "costs": ["The vehicle is the other half of the antenna, and it is an "
                  "undersized half: a car is about fifteen feet where a 40 m "
                  "quarter wave wants thirty-three. Bond the hood, the trunk, "
                  "the doors and the exhaust to the frame with strap, not "
                  "wire - panels are bolted through paint and are not "
                  "connected at RF until you connect them. A bad bond costs "
                  "more than any coil.",
                  "Most of your power heats the loading coil. Radiation "
                  "resistance on 80 m is a couple of ohms against tens of ohms "
                  "of loss, so a perfect 1:1 can be a perfect match into a "
                  "heater. Efficiency is the thing to work on, and SWR will "
                  "not show it to you.",
                  "The car makes its own noise - alternator, fuel pump, "
                  "ignition, the engine computer. On a quiet band that noise "
                  "floor, not the antenna, is usually what decides whether you "
                  "hear the other station.",
                  "Where it is mounted matters more than what it cost. Centre "
                  "of the roof is best and symmetric; a hitch or bumper mount "
                  "puts the whip at the edge and skews the pattern toward the "
                  "far side of the car. Then remember it is up there - "
                  "garages, drive-throughs and low branches all win.",
                  "It is feet from people, so the exposure evaluation is a "
                  "real one here rather than a formality."],
        "good_at": "far more than it has any right to be - a short vertical "
                   "launches low, so the little it radiates leaves flat and "
                   "works distance on 20 m and 40 m, while the ground wave "
                   "covers the near end a home wire flies over",
    },
    "portable": {
        "label": "Nothing at home - I go out",
        "max_ft": 30,
        "works": ["A wire into a tree, or up a fishing pole. Thirty feet in a "
                  "park is easy and beats anything most people manage at home.",
                  "An end-fed half wave, because the feedpoint ends up where "
                  "you are standing and it needs one support."],
        "costs": ["It has to go up and come down again every time, so "
                  "everything is a compromise with the walk back to the car."],
        "good_at": "having a better antenna than your house allows, which is "
                   "most of why people do this",
    },
}


def takeoff_deg(height_ft, mhz):
    """Where the main lobe of a horizontal antenna sits, in degrees up."""
    waves = max(0.001, float(height_ft) / wavelength_ft(mhz))
    return math.degrees(math.asin(min(1.0, 1.0 / (4.0 * waves))))


# Where a horizontal wire stops being a low antenna and starts being a ground
# heater. It is a soft edge and it is stated as one: efficiency over real earth
# falls away steadily below about a fifth of a wavelength and is bad by a
# tenth. The number is here so the sentence that uses it can name it.
GROUND_LIMIT = 0.10


def reality(kind, mhz, wanted_ft, site):
    """What that height means where somebody actually lives.

    Returns None when the site imposes nothing, so the ordinary case stays
    uncluttered.
    """
    spec = SITES.get(site)
    if not spec:
        return None
    cap = spec["max_ft"]
    out = {"site": site, "label": spec["label"], "works": list(spec["works"]),
           "costs": list(spec["costs"]), "good_at": spec["good_at"],
           "wanted_ft": wanted_ft, "max_ft": cap, "capped": False}
    if cap is None or wanted_ft <= cap:
        out["height_ft"] = wanted_ft
        return out
    out["capped"] = True
    out["height_ft"] = cap
    if TYPES.get(kind, {}).get("polarisation") == "horizontal" and cap > 0:
        angle = takeoff_deg(cap, mhz)
        out["takeoff_deg"] = round(angle)
        waves = cap / wavelength_ft(mhz)
        if waves < GROUND_LIMIT:
            # "Low is a capability" is true at a fifth of a wavelength and a
            # lie at a twentieth. Below about a tenth the pattern argument
            # stops being the point: the ground underneath is absorbing the
            # near field faster than the antenna can radiate it, and telling
            # somebody they have built a fine NVIS station is not honest.
            out["means"] = (
                "At %d ft on %g MHz this is %.2f of a wavelength up, and that "
                "is low enough that the pattern is no longer the problem - the "
                "ground under it is. Below about a tenth of a wave the earth "
                "absorbs the near field faster than the wire radiates it, and "
                "several decibels go into warming the soil. A deliberately low "
                "wire for regional work wants a fifth of a wavelength, %d ft "
                "here; this is a good deal less than that. It will make "
                "contacts and it is worth having over no antenna at all, but "
                "it is losing most of what you put into it, and the fix is "
                "height or a different antenna rather than power."
                % (cap, mhz, waves, round(NVIS_TARGET * wavelength_ft(mhz))))
            return out
        out["means"] = (
            "At %d ft on %g MHz the main lobe sits %d degrees up, not the %d "
            "it would at %d ft. That is not a broken antenna, it is a "
            "different one: %s. Work with it rather than against it - the "
            "contacts it makes easily are the ones the tower stations are "
            "talking over the top of."
            % (cap, mhz, round(angle), round(takeoff_deg(wanted_ft, mhz)),
               wanted_ft,
               "it goes up and comes down over your own region"
               if angle > 55 else
               "it favours a first hop rather than a long one"))
    return out


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
                if mhz > groundwave.SURFACE_WAVE_MAX_MHZ:
                    # Different radio entirely up here. Saying "ground wave"
                    # about a 2 m contact is the wrong name for the right
                    # distance, and the wrong name is what sticks.
                    reach = (" Up here none of that is the question anyway: "
                             "above about 30 MHz there is no ionospheric "
                             "return to be under and no surface wave worth "
                             "the name, so what you work is line of sight and "
                             "whatever diffracts over the edge of it. Height "
                             "and terrain decide that, not takeoff angle.")
                elif km:
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


def for_type(mhz, kind, use=None, site=None):
    """How to use the antenna somebody has actually chosen.

    The other half of `recommend`. That one answers "what should I put up";
    this answers "I have one of these, now what" - which is the question
    somebody asks once they own an antenna, and the one the tool used to
    answer by recommending a dipole instead.
    """
    mhz = float(mhz)
    spec = TYPES[kind]
    use = use if use in USES else default_use(mhz, kind)
    # The height follows what the antenna is being used for, not only what it
    # is. Half a wavelength is right for distance and wrong for the county.
    hanging_low = use == "regional" and spec["polarisation"] == "horizontal"
    if hanging_low:
        height = nvis_height_ft(mhz, kind)
    else:
        fraction, floor, ceiling = spec["height"]
        height = _height(mhz, fraction, floor, ceiling)
    # And then what is actually possible where somebody lives. The ideal
    # height is worth knowing; a number they cannot reach is worth less than
    # the truth about the one they can.
    where = reality(kind, mhz, height, site)
    if where:
        height = where["height_ft"]
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
        "better": (NVIS_BETTER + list(spec.get("better_nvis", []))
                   if hanging_low else list(spec["better"])),
        "fit": fit,
        "reality": where,
        "nvis": use == "regional" and spec["polarisation"] == "horizontal",
        "alternative": None,
        "feedline": _feedline(mhz),
        "context": frequency_context(mhz),
    }


# --- how high, for the feed to match --------------------------------------
#
# A horizontal dipole's feedpoint resistance is not 73 ohms. It is 73 ohms in
# free space; over the ground it swings with height, because the wire sees its
# own reflection - the image antenna, carrying the opposite current - and the
# two couple. At a tenth of a wave up it is about 22 ohms; it crosses 50 near
# 0.16 of a wave, which is the one height where coax matches it with nothing
# in between; it peaks near 98 ohms at 0.35 of a wave, which is the worst
# match to 50 ohm coax you can arrange; it comes back through 73 at half a
# wave, dips to 58 at 0.6, and settles toward 73 as the ground gets further
# away. The period is half a wavelength. KC9SP called it cyclical, and it is.
#
# Worked from the mutual impedance of two parallel half-wave dipoles, which is
# the standard result (Kraus), with the cosine integral done here in plain
# Python so that no unit needs scipy for it. It is the
# perfect-ground curve: over real ground the swings are smaller and shift a
# little, so these are the heights to start looking, not the height to stop
# at. The pattern changes with height too, and that is elsewhere on the page.
_EULER_GAMMA = 0.57721566490153286061


def _ci(x):
    """The cosine integral Ci(x), in plain Python.

    Ci(x) = gamma + ln x + sum_{k>=1} (-1)^k x^(2k) / (2k (2k)!). The
    series converges for every x; the question is only whether the terms get
    large enough on the way to eat the double's precision. The largest
    argument this module ever asks for is about 17 - a dipole a full
    wavelength up - where the biggest term is near 10^5 against an answer
    near 0.1, which double precision carries with ten digits to spare. It
    used to be scipy's, and scipy is 30 MB that Raspberry Pi OS happens to
    have and a clean install does not; the fleet should not depend on that
    for one integral.
    """
    if x <= 0:
        raise ValueError("Ci is defined for x > 0")
    if x > 40:
        # Asymptotic, for completeness: nothing here reaches it.
        f = (1 / x) * (1 - 2 / x**2 + 24 / x**4 - 720 / x**6)
        g = (1 / x**2) * (1 - 6 / x**2 + 120 / x**4 - 5040 / x**6)
        return f * math.sin(x) - g * math.cos(x)
    total, term, k = 0.0, 1.0, 0
    x2 = x * x
    while True:
        k += 1
        # term_k = (-1)^k x^(2k) / (2k)!, built from term_{k-1}
        term *= -x2 / ((2 * k - 1) * (2 * k))
        piece = term / (2 * k)
        total += piece
        if k > 4 and abs(piece) < 1e-17 * max(1.0, abs(total)):
            break
        if k > 400:                                   # pragma: no cover
            break
    return _EULER_GAMMA + math.log(x) + total

FREE_SPACE_OHMS = 73.13


def _mutual_r(d_wavelengths, half_length=0.5):
    """Mutual resistance of side-by-side thin half-wave dipoles, ohms."""
    k = 2.0 * math.pi
    r = math.hypot(d_wavelengths, half_length)
    return 30.0 * (2.0 * _ci(k * d_wavelengths)
                   - _ci(k * (r + half_length)) - _ci(k * (r - half_length)))


def feedpoint_resistance(height_wavelengths):
    """A horizontal half-wave's feedpoint resistance at this height, ohms.

    Over perfect ground. None if the height is too low to mean anything.
    """
    if height_wavelengths <= 0.02:
        return None
    return FREE_SPACE_OHMS - _mutual_r(2.0 * height_wavelengths)


def _swr_into_50(r):
    return max(r, 50.0) / min(r, 50.0)


# Where the curve does something worth knowing, in wavelengths. Found once by
# scanning the curve rather than typed in, so they cannot drift from it.
def _landmarks():
    hs = [i / 1000.0 for i in range(40, 1001)]
    rs = [feedpoint_resistance(h) for h in hs]
    marks = []
    for i in range(1, len(hs) - 1):
        a, b, c = rs[i - 1], rs[i], rs[i + 1]
        if (a - 50.0) * (b - 50.0) <= 0 and a != b:
            marks.append(("match", hs[i], b, "feed near 50 ohms - coax matches it with nothing in between"))
        if (a - FREE_SPACE_OHMS) * (b - FREE_SPACE_OHMS) <= 0 and a != b:
            marks.append(("natural", hs[i], b, "back at its free-space 73 ohms"))
        if b > a and b > c:
            marks.append(("peak", hs[i], b, "the high point: the worst match to 50 ohm coax on the way up"))
        if b < a and b < c:
            marks.append(("dip", hs[i], b, "a shallow dip"))
    # The first "natural" crossing sits a hair above the match and says nothing
    # the match does not; keep landmarks that are at least 0.03 wave apart.
    kept = []
    for m in marks:
        if not kept or m[1] - kept[-1][1] >= 0.03:
            kept.append(m)
    return kept


_LANDMARKS = _landmarks()


def matching_heights(mhz, reach_ft=None):
    """The heights worth knowing about for a horizontal wire on this band.

    Each with the feedpoint resistance there, the SWR that means into 50 ohm
    coax, and whether it is within what the site allows - because a height
    the garden cannot reach is worth knowing about and not worth aiming at.
    """
    lam = wavelength_ft(mhz)
    out = []
    for what, h, r, note in _LANDMARKS:
        ft = round(h * lam)
        out.append({
            "what": what, "wavelengths": round(h, 2), "ft": ft,
            "ohms": round(r), "swr": round(_swr_into_50(r), 1),
            "note": note,
            "reachable": (reach_ft is None) or (ft <= reach_ft),
        })
    return out


# --- what the power changes -------------------------------------------------
#
# Not the antenna. A thicker element does not take more power to drive: the
# power that leaves an antenna is I squared times its radiation resistance,
# and the element's diameter barely touches that - a fat element has a little
# more bandwidth and a little *less* loss, because the RF runs on its skin and
# a fat wire has more skin. QRP operators use thin wire because it is light
# and packs small, and because at five watts its loss is nothing to them; not
# because thin wire needs less power. Say so, because the belief is common.
#
# What the power does change is what has to survive it: the heat in the wire
# (usually nothing, and the number says so), the voltage at the end of an
# end-fed (hundreds of volts at 100 W, thousands at the legal limit), the core
# in a 49:1 transformer or a choke, the coil of a loaded whip, which eats the
# power the short element cannot radiate, the coax, and the people nearby -
# which is the RF exposure tool's job, and this hands it the watts.

COPPER_RHO = 1.72e-8                # ohm metres
LEGAL_LIMIT_W = 1500.0


def conductor_loss_ohms(mhz, od_mm, sigma_rel, length_m):
    """Effective series loss of a half-wave of this wire, at the feedpoint.

    RF runs in a skin about delta deep; a wire's RF resistance per metre is
    rho over (pi d delta). Current on a half wave is sinusoidal, so the loss
    resistance referred to the feedpoint is half the wire's total.
    """
    rho = COPPER_RHO / max(sigma_rel, 1e-3)
    f = mhz * 1e6
    delta = math.sqrt(rho / (math.pi * f * 4e-7 * math.pi))
    d = od_mm / 1000.0
    r_per_m = rho / (math.pi * d * delta)
    return r_per_m * length_m / 2.0


def power_notes(kind, mhz, watts, od_mm=1.63, sigma_rel=1.0, coil_loss_ohms=None,
                whip_r_rad=None):
    """What this much power asks of this antenna, in numbers and sentences."""
    watts = float(watts or 0)
    if watts <= 0:
        return None
    out = {"watts": watts, "items": [], "exposure": True}
    horizontal = kind in ("dipole", "invertedv", "efhw", "bowtie", "loop")
    if horizontal:
        length_m = wavelength_ft(mhz) * 0.3048 * (1.0 if kind == "loop" else 0.5)
        r_loss = conductor_loss_ohms(mhz, od_mm, sigma_rel, length_m)
        r_rad = FREE_SPACE_OHMS
        heat = watts * r_loss / (r_rad + r_loss)
        out["wire_heat_w"] = round(heat, 1)
        out["wire_loss_ohms"] = round(r_loss, 2)
        out["items"].append(
            f"The wire itself turns about {heat:.1f} W of your {watts:.0f} W "
            f"into heat, spread along its whole length - {r_loss:.1f} ohms of "
            f"loss against {r_rad:.0f} of radiation. A thicker wire would lose "
            f"less, not need more: the RF runs on the skin, and a fat wire has "
            f"more skin.")
    if kind == "efhw":
        r_end = 2500.0
        v_end = math.sqrt(watts * r_end)
        out["end_volts"] = round(v_end)
        out["items"].append(
            f"The far end sits near {r_end:.0f} ohms, so at {watts:.0f} W it "
            f"swings to about {v_end:.0f} V. Tie it off on an insulator, out of "
            f"reach, and not through a leaf.")
        out["items"].append(
            "The 49:1 transformer is rated in watts and the rating is real: a "
            "core that saturates heats, the match drifts, and the coax braid "
            "starts radiating. Buy the rating for the power you will actually "
            "run" + (", and at this level that is a large core." if watts > 400 else "."))
    if kind in ("whip", "screwdriver") and coil_loss_ohms and whip_r_rad:
        coil_w = watts * coil_loss_ohms / (coil_loss_ohms + whip_r_rad)
        out["coil_heat_w"] = round(coil_w)
        out["items"].append(
            f"The coil takes what the short element cannot radiate: about "
            f"{coil_w:.0f} W of your {watts:.0f} W becomes heat in it. That is "
            f"the number to size the coil and its former for" +
            (" - and at this level it is a serious amount of heat in a small "
             "space." if coil_w > 50 else "."))
    if watts > 100:
        out["items"].append(
            "Coax has a power rating and it falls with SWR. RG-58 is not for "
            "this; RG-8X is marginal above a few hundred watts; RG-213 or "
            "LMR-400 is the honest choice, and the connectors matter as much.")
    if kind in ("dipole", "invertedv", "bowtie", "loop", "yagi"):
        out["items"].append(
            "A 1:1 current balun at the feed keeps the coax from becoming part "
            "of the antenna. Its core is rated too; above a few hundred watts "
            "use one that says so.")
    if watts > LEGAL_LIMIT_W:
        out["items"].append(
            f"{watts:.0f} W is above the 1500 W PEP the rules allow "
            f"(47 CFR 97.313).")
    return out


def _site_type(mhz, site, use):
    """The antenna the site rules in, or None to let the intention decide.

    Only the sites that impose something have a view. A house with trees and
    a tower with room both leave the choice to what the antenna is for.

    A vehicle: nobody hangs a dipole off a car. Below 30 MHz the quarter wave
    does not fit and a coil stands in for the missing wire; above it the whole
    antenna is full size and a five-eighths gets real gain from a roof that is
    finally a good ground plane.

    A flat: nothing can go up, so on HF the wire goes *out* - an end-fed half
    wave from the window or balcony, sloping to wherever it can be tied, with
    the feedpoint indoors where the radio is. Where even that is too long,
    which is 80 m and below, a loaded vertical clamped to the rail with the
    rail as counterpoise. On VHF a J-pole on the balcony.

    An attic: a dipole folded to the roof line where the wire is short enough,
    which is 20 m and up; below that an end-fed, which bends where a dipole's
    balance would rather it did not.

    A short garden: an inverted-V where the half wave fits, and on the low
    bands an end-fed run as a sloper, which wants one support and works against
    its own ground reflection - a thing worth learning to tune rather than
    fighting for height the garden has not got.

    Nothing at home: the end-fed, which is what most people carry to a park
    for the same reasons - one support, and the feedpoint at your feet.

    FM on VHF is vertical wherever you are, so a J-pole whatever the site.
    """
    if site == "mobile":
        return "fiveeighth" if mhz > 30.0 else "whip"
    if mhz > 30.0:
        if site in ("apartment", "attic"):
            return "jpole"
        return None                          # small, portable: the use decides
    half = wavelength_ft(mhz) / 2.0
    if site == "apartment":
        return "efhw" if half <= 40.0 else "whip"
    if site == "attic":
        return "invertedv" if half <= 35.0 else "efhw"
    if site == "small":
        return "invertedv" if half <= 35.0 else "efhw"
    if site == "portable":
        return "efhw"
    return None


# What to call a site-chosen antenna: the type's name says what it is, this
# says what to do with it where you are, which is the sentence somebody who has
# just said "a flat" is waiting for.
_STEERED_TITLES = {
    ("apartment", "efhw"): "An end-fed half wave out of the window, sloping to "
                           "wherever it can be tied",
    ("apartment", "whip"): "A loaded vertical clamped to the balcony rail, with "
                           "the rail as the counterpoise",
    ("apartment", "jpole"): "A J-pole on the balcony, as clear of the building "
                            "as the rail allows",
    ("attic", "invertedv"): "An inverted-V under the roof line, ends bent to fit",
    ("attic", "efhw"): "An end-fed half wave zigzagged through the roof space",
    ("attic", "jpole"): "A J-pole in the roof space, as high under the ridge as "
                        "it will go",
    ("small", "invertedv"): "An inverted-V from one pole, legs down to the fence",
    ("small", "efhw"): "An end-fed half wave as a sloper, tuned to its own ground "
                       "reflection",
    ("portable", "efhw"): "An end-fed half wave into a tree or up a pole",
    ("mobile", "whip"): "A loaded whip on the vehicle - mag-mount or bumper",
    ("mobile", "fiveeighth"): "A five-eighths wave whip on the roof, which is a "
                              "good ground plane at last",
}


def _steered_title(kind, site, mhz):
    return _STEERED_TITLES.get((site, kind)) or TYPES[kind]["title"]


def recommend(mhz, use=None, kind=None, site=None):
    """A starting antenna for this frequency and intention, with its reasoning."""
    mhz = float(mhz)
    # Somebody who named an antenna wants to be taught that antenna, not
    # talked back to a dipole.
    if kind in TYPES:
        return for_type(mhz, kind, use, site)
    # What somebody has to work with settles the question before what they
    # want to do with it does, because the site is the thing that rules
    # antennas out. This used to be true only of a vehicle; a flat, an attic
    # and a short garden all got "a half-wave dipole, as high as you can
    # manage" - 69 feet of wire offered to a balcony - while the notes for
    # those very sites, a few lines down, said a wire out of the window or a
    # short vertical on the rail. The program knew and did not act on it.
    steered = _site_type(mhz, site, use)
    if steered:
        out = for_type(mhz, steered, use, site)
        out["title"] = _steered_title(steered, site, mhz)
        out["steered"] = True          # the site chose this, not the intention
        return out
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
            "title": "A J-pole vertical, as high as you can get it",
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
            # Named for what it actually is. It said "A low dipole" while
            # recommending an inverted-V, and the alternative underneath
            # mentioned a flat dipole - so the page appeared to be proposing
            # two antennas at once to somebody who has never put up either.
            "title": "An inverted-V, hung deliberately low",
            "height_ft": _height(mhz, 0.18, 15, NVIS_REACH_FT),
            "why": [
                f"For a few hundred miles you want the signal going up, not "
                f"out. At about a fifth of a wavelength up - {_height(mhz, 0.18, 15)} "
                f"ft here - a horizontal wire radiates almost straight up and "
                f"the ionosphere returns it over the whole region with no skip "
                f"zone in the middle.",
                "This is the one case where a low antenna is the right answer "
                "rather than a compromise, which is worth knowing before "
                "somebody talks you into a tower.",
                "An inverted-V is a dipole. Same wire, same length, same "
                "feedpoint - it just hangs from one support in the middle "
                "with the ends sloping away, instead of being stretched flat "
                "between two. That is why the two names turn up in the same "
                "breath: they are one antenna and two ways of hanging it.",
            ],
            "watch": [
                "Higher is worse here, not better: get it up near half a "
                "wavelength and you start putting a skip zone between you and "
                "the people you are trying to work.",
                "The ends of the wire are the high-voltage points, and on a "
                "V they are the ends that come down towards people. Keep them "
                "above head height and away from anything anybody touches.",
            ],
        })
        out["alternative"] = ("Two supports rather than one? Then a flat "
                              "dipole between them is worth about a decibel "
                              "over the V. The V is the pick here because it "
                              "hangs from a single point in the middle, which "
                              "is what most people actually have.")

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

    elif wavelength_ft(mhz) / 2.0 > DIPOLE_REACH_FT:   # dx on the low bands
        # 80 m and 160 m. Half a wave up is 133 and 266 ft; the dipole "as
        # high as you can manage" was being recommended here for years with
        # the physics of why 266 ft works explained underneath, to people
        # with a forty-foot tree. What they actually have room for is the
        # antenna the low-band DXers actually use.
        quarter = _height(mhz, 0.25, 20)
        wanted = round(wavelength_ft(mhz) / 2.0)
        out.update({
            "type": "quarter",
            "title": "A quarter-wave vertical over radials - height is not to "
                     "be had on this band, so use the ground instead",
            "height_ft": quarter,
            "why": [
                f"For distance a dipole wants to be half a wavelength up, and "
                f"on this band that is about {wanted} ft. Nobody has that: a "
                f"hundred feet is a tall tower, and above {FAA_NOTICE_FT} ft "
                f"the FAA has to be told (14 CFR 77.9) and the structure "
                f"registered (47 CFR Part 17). At the heights people do have, "
                f"a dipole here is a near-vertical antenna - good for a few "
                f"hundred miles and no further.",
                f"A quarter-wave vertical is {quarter} ft tall, and what it "
                f"needs is not height but ground: radials laid on it, as many "
                f"as you can manage. Its low takeoff angle is what the dipole "
                f"cannot get without the tower, which is why the people who "
                f"work DX on 80 and 160 use one.",
                "It is vertically polarised, so it hears more noise than a "
                "horizontal wire - the usual arrangement is to transmit on the "
                "vertical and listen on something else.",
            ],
            "watch": [
                "Radials are most of the antenna. Sixteen short ones beat four "
                "long ones; more beat both.",
                "The base is a high-current point, so the ground connection and "
                "radial bond are where losses live. Bond everything.",
                "A full quarter wave on 160 m is 130 ft of vertical. Most "
                "people build a shorter one and load it - an inverted-L, with "
                "the top run out horizontally, is the usual shape.",
            ],
            "better": [
                "An inverted-L: the vertical you can afford, with the rest of "
                "the quarter wave run out horizontally from the top.",
            ],
        })
        out["alternative"] = ("Only working out to a few hundred miles? A "
                              "dipole at whatever height you have - even 30 ft "
                              "- is the better antenna for that, because that "
                              "low it fires straight up and comes down "
                              "regionally.")

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

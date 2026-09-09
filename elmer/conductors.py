"""What the antenna is actually made of, and what that changes.

Most antenna maths is written as though elements were infinitely thin, and
then everybody builds one out of whatever is in the shed. The thickness is not
a detail: it sets how much of the band the antenna covers, and it changes the
length you have to cut.

The rule runs the opposite way to most people's intuition, which is why it is
worth showing rather than asserting. **A fatter conductor has a lower Q**, and
a lower Q is a wider bandwidth. A thin wire is the high-Q, narrow-band case; a
length of copper pipe is the low-Q, wide-band one. It is exactly why a bowtie
or a cage dipole covers a whole band where a thin wire covers part of one, and
why commercial VHF antennas are made of tube rather than wire.

The number behind it is the thickness factor, Omega = 2 ln(4L/d) for a half
element of length L and diameter d - the expansion parameter that appears
whenever a dipole is solved properly. Q rises roughly with Omega, so a
conductor an order of magnitude fatter is perhaps a third lower in Q and a
third wider in band. That is an approximation and is labelled as one; the
direction of it is not in doubt.

Being fatter also shortens the element slightly, which is why an aluminium
tube dipole comes out under the 468/f that wire wants.
"""
import math

# Everything here is stuff somebody can actually get hold of, with the real
# outside diameter rather than the nominal name. Copper tube is named by its
# bore, so half-inch pipe is 15.9 mm across the outside, not 12.7.
CONDUCTORS = [
    {"key": "wire14", "label": "#14 AWG copper wire", "od_mm": 1.63,
     "material": "copper", "sigma": 1.00, "reference": True,
     "note": "The default, and what most wire antennas are. Every rule of "
             "thumb in the books - 468/f and the rest - assumes something "
             "about this thick."},
    {"key": "wire18", "label": "#18 AWG wire / speaker flex", "od_mm": 1.02,
     "material": "copper", "sigma": 1.00,
     "found": "out of anything with a loudspeaker in it",
     "work": "Snips or a knife. Twist a proper splice - it carries RF "
             "unsoldered - and a lighter will solder it if you want it to "
             "last.",
     "note": "Light enough to carry and to hang from a branch. Thin means "
             "high Q and a narrow band, and it will stretch under its own "
             "weight over a long span."},
    {"key": "wire12", "label": "#12 AWG house wire", "od_mm": 2.05,
     "material": "copper", "sigma": 1.00,
     "found": "stripped out of a length of twin-and-earth",
     "work": "Side cutters, or bend it until it snaps. Splice and solder, "
             "or clamp it under a bolt and a washer.",
     "note": "Salvaged from a length of twin-and-earth. Stiff, tough, and "
             "holds a shape - good for a portable dipole that gets packed and "
             "unpacked."},
    {"key": "fence", "label": "Galvanised fence wire", "od_mm": 2.5,
     "material": "steel", "sigma": 0.10,
     "found": "off any farm fence, in any length you like",
     "work": "Fencing pliers or a hacksaw. Solder will not take to zinc: "
             "wrap the joint tight and clamp it, the way the fence itself "
             "is joined.",
     "note": "On a farm it is the wire you already have, in any length you "
             "like.",
     "caution": "Steel conducts about a tenth as well as copper and the skin "
                "effect makes that worse at RF. On a full-size resonant "
                "element the loss is small; on anything loaded or short it is "
                "not."},
    {"key": "hanger", "label": "Coat hanger / welding rod", "od_mm": 2.5,
     "material": "steel", "sigma": 0.10,
     "found": "a closet, a motel wardrobe, a welding kit",
     "work": "Hacksaw, or bend it back and forth until it breaks. File "
             "the paint or plating off wherever it has to make contact.",
     "note": "The classic field expedient for a VHF ground plane: four "
             "radials and a radiator out of a coat hanger works, and works "
             "tonight.",
     "caution": "Steel, so lossy - fine at VHF where the element is a "
                "resonant quarter wave, poor for anything that needs a coil."},
    {"key": "tape", "label": "Steel tape measure blade", "od_mm": 12.7,
     "material": "steel", "sigma": 0.10,
     "found": "the toolbox - and it rolls itself back up",
     "work": "Tin snips. Scrape the coating back to bright steel, then "
             "bolt or clamp - it will not solder and does not need to.",
     "note": "Rolls up, springs out, survives being sat on. The blade is wide "
             "rather than round, which behaves like a conductor about as fat "
             "as it is wide - so it is broadbanded as well as portable.",
     "caution": "Steel, and the width is what buys the bandwidth rather than "
                "the conductivity."},
    {"key": "alu12", "label": "1/2 in aluminium tube", "od_mm": 12.7,
     "material": "aluminium", "sigma": 0.61,
     "found": "a tent pole, a curtain rail, an old TV mast",
     "work": "Hacksaw or a tube cutter. It will not solder with anything "
             "in a toolbox: slit the end, telescope it, and pull a hose "
             "clamp over.",
     "note": "What beams are made of. Light, stiff, telescopes into the next "
             "size up, and does not need soldering."},
    {"key": "alu34", "label": "3/4 in aluminium tube", "od_mm": 19.05,
     "material": "aluminium", "sigma": 0.61,
     "note": "Fat enough to widen a band noticeably and still light enough to "
             "hold up on a mast."},
    {"key": "emt12", "label": "1/2 in EMT conduit", "od_mm": 17.9,
     "material": "steel", "sigma": 0.10,
     "found": "an offcut off any building site or shelf",
     "work": "Hacksaw or a pipe cutter. Self-tapping screws, clamps or "
             "the couplings made for it - the zinc refuses solder.",
     "note": "In every hardware store, cheap, and straight. Good for a "
             "vertical or a mast.",
     "caution": "Steel and usually zinc plated. Solder will not take to it - "
                "use clamps or self-tapping screws - and it is lossier than "
                "it looks."},
    {"key": "pipe12", "label": "1/2 in copper pipe (15.9 mm OD)", "od_mm": 15.9,
     "material": "copper", "sigma": 1.00,
     "found": "the plumbing aisle, or somebody's scrap pile",
     "work": "Tube cutter or hacksaw. It solders properly, but wants a "
             "torch - an iron cannot get half-inch pipe hot enough.",
     "note": "Excellent antenna material and the standard J-pole. Solders "
             "cleanly, holds itself up, and named by its bore - half-inch "
             "pipe is 15.9 mm across the outside."},
    {"key": "pipe34", "label": "3/4 in copper pipe (22.2 mm OD)", "od_mm": 22.2,
     "material": "copper", "sigma": 1.00,
     "note": "Noticeably wider band than wire, and rigid enough to stand on "
             "its own for a couple of metres."},
    {"key": "pipe1", "label": "1 in copper pipe (28.6 mm OD)", "od_mm": 28.6,
     "material": "copper", "sigma": 1.00,
     "note": "About as fat as anybody builds from tube. Heavy, expensive, and "
             "the widest band a single element will give you."},
    # Soft-drawn refrigeration tube, the stuff an ice maker is plumbed with.
    # Sized by its real outside diameter, unlike rigid pipe, which is named by
    # its bore - so a quarter inch here really is 6.35 mm, four times a #14
    # wire. It is sold in coils, which is the point of it: fifty feet of
    # antenna goes in a pannier and comes out straight.
    {"key": "tube14", "label": "1/4 in soft copper tube (ice-maker line)",
     "od_mm": 6.35, "material": "copper", "sigma": 1.00,
     "found": "the coil an ice maker or humidifier is plumbed with",
     "work": "Bend and snap it, or a tube cutter. Solders with a torch, "
             "or flatten the end with a hammer and drill it for a bolt.",
     "note": "The coil of soft copper sold to plumb an ice maker or a "
             "humidifier - 25 and 50 ft rolls, in every hardware store. Four "
             "times the diameter of #14 wire, so a usefully wider band, and it "
             "solders. Annealed, so it uncoils by hand, holds a shape, and "
             "will stand on its own for a metre or two.",
     "caution": "It work-hardens: bend the same spot repeatedly and it "
                "cracks. Heavier than wire, so a long horizontal span needs "
                "support or it will sag and stretch."},
    # What a bought whip is actually made of. Stainless is chosen for the car
    # wash and the pothole, not for the radio: 304 conducts about 2.5% as well
    # as copper, worse even than plain steel. On a full-size element that would
    # be a scandal; on a mobile whip, where the radiation resistance is already
    # a few ohms and the loading coil dominates the losses, it is one more
    # entry on a list of compromises somebody made so the thing would survive
    # being driven around.
    {"key": "stainless", "label": "Stainless steel whip element", "od_mm": 4.8,
     "material": "stainless", "sigma": 0.025, "bought": True,
     "note": "What commercial mobile whips are made of. Springy, it does not "
             "corrode, and it survives a car wash and a low branch - which is "
             "what is being bought.",
     "caution": "It conducts about a fortieth as well as copper, worse than "
                "ordinary steel. On a shortened, loaded antenna the losses are "
                "already the whole game, so this is a real cost and not a "
                "quibble - it is simply the cost of an antenna that survives "
                "the road."},
    {"key": "tube38", "label": "3/8 in soft copper tube", "od_mm": 9.53,
     "material": "copper", "sigma": 1.00,
     "note": "The other size sold in coils. Stiffer and wider-band than the "
             "quarter inch, and still rolls up - a good compromise for a "
             "portable vertical."},
]

INDEX = {c["key"]: c for c in CONDUCTORS}
REFERENCE = next(c for c in CONDUCTORS if c.get("reference"))

# The velocity factor everything in this program is written around: 468/f is
# 0.95 of a half wavelength, and that is the wire case. Fatter elements come
# out shorter, and these are the practical anchors, interpolated on the
# half-length-to-diameter ratio. They are what builders measure, not a model.
K_ANCHORS = [(5000.0, 0.950), (1000.0, 0.945), (300.0, 0.940),
             (100.0, 0.930), (30.0, 0.920), (10.0, 0.900)]

C_FT = 983.571


def half_length_m(mhz):
    """Half of a half-wave element, in metres - the L in the thickness factor."""
    return 0.3048 * (C_FT / float(mhz)) * 0.95 / 4.0


def omega(mhz, od_mm):
    """Thickness factor 2 ln(4L/d): small is fat, and fat is broadbanded."""
    length_m = half_length_m(mhz)
    diameter_m = max(1e-5, float(od_mm) / 1000.0)
    return 2.0 * math.log(max(1.0001, 4.0 * length_m / diameter_m))


def velocity_factor(mhz, od_mm):
    """The shortening this thickness calls for, anchored so wire stays 0.95."""
    length_m = half_length_m(mhz)
    ratio = max(1.0, length_m / max(1e-5, float(od_mm) / 1000.0))
    if ratio >= K_ANCHORS[0][0]:
        return K_ANCHORS[0][1]
    if ratio <= K_ANCHORS[-1][0]:
        return K_ANCHORS[-1][1]
    for (hi_r, hi_k), (lo_r, lo_k) in zip(K_ANCHORS, K_ANCHORS[1:]):
        if lo_r <= ratio <= hi_r:
            span = math.log(hi_r) - math.log(lo_r)
            frac = (math.log(ratio) - math.log(lo_r)) / span if span else 0.0
            return lo_k + frac * (hi_k - lo_k)
    return REFERENCE_K


REFERENCE_K = 0.95


def q_scale(mhz, od_mm):
    """How this conductor's Q compares with ordinary wire's at the same
    frequency. Below 1 means fatter, lower Q, and a wider band."""
    base = omega(mhz, REFERENCE["od_mm"])
    if base <= 0:
        return 1.0
    return omega(mhz, od_mm) / base


def describe(key, mhz):
    """Everything the screen needs about one choice, at one frequency."""
    spec = INDEX.get(key) or REFERENCE
    scale = q_scale(mhz, spec["od_mm"])
    return {
        "key": spec["key"], "label": spec["label"], "od_mm": spec["od_mm"],
        "material": spec["material"], "note": spec.get("note", ""),
        "caution": spec.get("caution", ""),
        "k": round(velocity_factor(mhz, spec["od_mm"]), 4),
        "q_scale": round(scale, 3),
        "band_scale": round(1.0 / scale, 2) if scale else 1.0,
        "reference": bool(spec.get("reference")),
    }


# Some antennas are bought rather than built, and offering a coat hanger as
# the element of a commercial mobile whip is a question nobody is asking. What
# they are asking is what the thing in their hand is made of and what that
# costs them - which is a better question, and has an answer.
BUILT_FROM = {
    "whip": ["stainless", "tube14", "tube38", "alu12"],
    # The radiator above the coil is the same bought whip, and the same
    # argument applies to it: what is being paid for is a thing that survives
    # a car wash and a low branch.
    "screwdriver": ["stainless", "tube14", "tube38", "alu12"],
}


def options(mhz, kind=None):
    """Every choice, sorted thin to fat, so the trend is visible in the list.

    `kind` narrows it to what that antenna is plausibly made of. A mobile whip
    is a bought item with a stainless element; the wire, fence and tape-measure
    entries belong to antennas somebody strings up themselves.
    """
    allowed = BUILT_FROM.get(kind)
    rows = [c for c in CONDUCTORS if allowed is None or c["key"] in allowed]
    return [describe(c["key"], mhz)
            for c in sorted(rows, key=lambda c: (allowed.index(c["key"])
                                                 if allowed else c["od_mm"]))]


def improvised():
    """The entries somebody could plausibly find rather than buy, and where.

    This exists for the Make Contact page, which asks what the operator has on
    hand. The gear list there is radios, and radios are things you either
    brought or did not. The antenna is not like that: it is the part of the
    station that can still be built out of the surroundings, and an operator
    who has not been shown that once does not think of a fence as an antenna.

    So this hands that page a sample, deliberately - the entries this module
    already has real numbers for, each with the everyday place it comes from.
    It is not a catalogue of what can be an antenna and the page says so out
    loud, because a list presented as complete would do the opposite of what
    it is for: the whole point is to send somebody looking at what is actually
    around them, and that is a longer list than any program can hold. What
    settles a candidate is not whether it appears here. It is whether it
    conducts, whether it can be got up and clear, and what a sweep says about
    it - which is why the page hands the question to the VNA in the Lab.
    """
    return [{"key": c["key"], "label": c["label"], "found": c["found"],
             "work": c["work"]}
            for c in CONDUCTORS if c.get("found")]

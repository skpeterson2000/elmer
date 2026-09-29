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
    # Three wires a new operator is offered, or finds on a shelf, and learns
    # about the hard way or the heard way. The sizes are the metal's, which
    # is where RF runs: magnet wire and craft wire are sized in AWG (15 AWG
    # is 1.450 mm, 16 AWG 1.291 mm), and electric-fence wire by the steel
    # wire gauge whatever it is made of, so "14 gauge" aluminium fence wire
    # is 2.0 mm - fatter than #14 copper, which is 1.63.
    {"key": "magnet15", "label": "#15 enameled magnet wire", "od_mm": 1.45,
     "material": "copper", "sigma": 1.00,
     "found": "on a spool sold for winding motors and transformers, or in "
              "the windings of a dead one",
     "work": "Scrape or burn the enamel off before anything will solder or "
             "make contact - it is an insulator, and it is the whole surface. "
             "Twist, then solder.",
     "note": "Solid copper under a varnish thin enough not to change the "
             "length you cut, and nearly invisible against the sky: the "
             "classic stealth wire. Five hundred feet on a small spool is "
             "a big loop or several dipoles.",
     "caution": "Soft copper stretches under the pull of a span, so a dipole "
                "cut to length slowly grows and drifts low in frequency. It "
                "work-hardens and snaps where it flexes - at an insulator, in "
                "the wind - and the enamel is made for the inside of a motor, "
                "not years of sun."},
    # The far end of magnet wire: 40 AWG, 0.0799 mm, four thousand feet on a
    # two-ounce spool. Invisible, and three skin depths across on 40 m, so
    # the loss is real - a third of the power, on a 40 m dipole - and the
    # current at 100 W is half what melts it (antenna_advice.fusing_amps).
    {"key": "magnet40", "label": "40 AWG magnet wire (hair-thin)", "od_mm": 0.0799,
     "material": "copper", "sigma": 1.00,
     "found": "a spool sold for winding pickups and tiny coils",
     "work": "Burn the enamel off the last half inch in a flame or with a "
             "hot iron and a blob of solder, and solder it to something "
             "stout at every end - it will not survive being tied.",
     "note": "The invisible antenna: thinner than most hairs, and four "
             "thousand feet on a spool that fits in a pocket. It radiates, "
             "and on FT8 or CW it makes contacts from where no antenna is "
             "allowed. The Lab's loss figure is not a quibble here - on a "
             "40 m dipole about a third of the power heats the wire.",
     "caution": "QRP only. At 100 W the current at the feed is about half what "
                "melts it, and the enamel goes before that; at 5 W it is fine. "
                "It breaks with a light tug, so a span needs sheltered supports "
                "and no wind, and a bird will end it."},
    # 30 AWG, 0.255 mm, sold as a half-pound spool of some 1,660 feet with a
    # heavy-build enamel rated 220 C. On a 40 m dipole it loses an eighth of
    # 100 W; the current at the feed is about a tenth of what melts it.
    {"key": "magnet30", "label": "30 AWG magnet wire", "od_mm": 0.255,
     "material": "copper", "sigma": 1.00,
     "found": "a half-pound spool sold for transformers, motors and pickups",
     "work": "Burn or scrape the enamel off - heavy-build enamel rated for "
             "220 C takes a hot iron and patience - tin it, and solder; tie "
             "off at the ends around something stout, not the wire alone.",
     "note": "A step up from hair-thin: still near invisible at a distance, "
             "and a spool holds enough for a dozen dipoles. On a 40 m dipole "
             "it heats away about an eighth of the power - a third of what "
             "40 AWG does - and 100 W is well inside what it carries.",
     "caution": "Its strength is the limit, not the current: it stretches, "
                "and a long span in wind or ice will part it. A temperature "
                "rating on the spool is the enamel's, not a current it "
                "can carry."},
    # The common hobby spool between the two: 26 AWG, 0.405 mm, a few hundred
    # feet for a few dollars. Its listing carries a current rating, and that
    # rating is the lesson: it is for a wire wound tight in a coil, where the
    # heat cannot get out, not for one strung in open air.
    {"key": "magnet26", "label": "26 AWG magnet wire", "od_mm": 0.405,
     "material": "copper", "sigma": 1.00,
     "found": "the common small spool sold for coils and speakers",
     "work": "Scrape or burn the enamel off, tin it, and solder; tie off "
             "at the ends with a knot around something stout, not the wire "
             "alone.",
     "note": "Thin enough to disappear against the sky at a distance, sturdy "
             "enough to hang with care. On a 40 m dipole it loses about a "
             "seventh of what 40 AWG does - under a tenth of the power - which "
             "is a fair price for a wire nobody sees.",
     "caution": "The current rating printed on the spool, half an amp or so, "
                "is for a wire wound tight in a coil where its heat cannot "
                "escape. Strung in the open it sheds that heat along its whole "
                "length and carries the 1 A of 100 W at the feed - the rating "
                "is not the limit here. Its strength is: it stretches, and a "
                "long span in wind will part it."},
    # Two-conductor zip cord - speaker wire, lamp cord - sized by the AWG of
    # each conductor (18 AWG 1.024 mm, 22 AWG 0.644 mm). Twenty meters of it
    # is the thrifty 40 m dipole: 65.6 ft is a half wave at about 7.1 MHz.
    {"key": "zip18", "label": "Zip cord / speaker wire, 18 AWG pair", "od_mm": 1.02,
     "material": "copper", "sigma": 1.00,
     "found": "the speaker-wire and lamp-cord reel in any hardware store",
     "work": "Pull the two conductors apart by hand - they split cleanly - "
             "strip, twist and solder; it is stranded, so it bends without "
             "breaking.",
     "note": "The thrifty dipole. Split it from one end to the middle and "
             "pull the two wires out in opposite directions: they are the "
             "legs, and the half left joined is the feed line - one reel, one "
             "antenna, no coax. Or peel one conductor off whole and cut it "
             "at the middle. Stranded and flexible, so it packs and unpacks "
             "without fatigue.",
     "caution": "Its plastic jacket makes it electrically longer, so it "
                "resonates below where bare wire of the same length would - "
                "cut long and trim. As a feed line it is not 50 ohm coax: it "
                "is a lossy two-wire line that wants a balun or a tuner at "
                "the radio, and it is best kept short."},
    {"key": "zip22", "label": "Zip cord / speaker wire, 22 AWG pair", "od_mm": 0.644,
     "material": "copper", "sigma": 1.00,
     "found": "the thin speaker wire and hookup-wire reels",
     "work": "Split, strip, twist and solder, as the 18 AWG - the strands "
             "are fine, so twist them tight before soldering.",
     "note": "The same trick in lighter wire: less to carry, easier to hide, "
             "and still stranded.",
     "caution": "Thin enough that the Lab's loss is worth reading, and the "
                "jacket shortens it like any insulated wire. Weak in a long "
                "span: support it, or keep it short."},
    {"key": "alufence", "label": "Aluminium electric-fence wire (14 ga, 2.0 mm)",
     "od_mm": 2.0, "material": "aluminium", "sigma": 0.61,
     "found": "the farm store, in quarter-mile spools, or off an old "
              "electric fence",
     "work": "Side cutters. It will not take ordinary solder: clamp it, "
             "and where it meets copper, use a connector made for "
             "aluminium to copper.",
     "note": "The cheap way to hang a very long wire - a long-wire, a "
             "terminated antenna or a receiving antenna hundreds of feet "
             "long - and light for its strength: 14 gauge aluminium is "
             "rated to about 215 lb breaking load. Sold by the steel wire "
             "gauge, so it is fatter than #14 copper.",
     "caution": "Clamped straight to copper, the two metals corrode each "
                "other at the joint, and a joint that corrodes is a joint "
                "that goes noisy and then open. Like any solid wire it "
                "fatigues where it flexes."},
    {"key": "alucraft", "label": "Colored aluminium craft wire (16 ga)", "od_mm": 1.29,
     "material": "aluminium", "sigma": 0.61,
     "found": "the craft and jewelry aisle, in every color including copper",
     "work": "Scrape the colored surface back to bright metal at every "
             "connection - it will not conduct through it - and clamp; it "
             "will not take ordinary solder.",
     "note": "It is aluminium whatever color it is sold in. The copper, "
             "gold and bronze are dye in an anodized surface, and anodizing "
             "is a layer of oxide, which does not conduct: the RF runs in "
             "the metal beneath it, so the antenna works, but a connection "
             "made to the color is no connection. Fine for a short portable "
             "dipole, a small loop, a vertical element or a counterpoise.",
     "caution": "Sold as bendable, which means dead soft. Under the pull of a "
                "long horizontal span it stretches - detuning as it goes - "
                "and then parts. Keep the spans short, or give it support."},
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
             "its own for a couple of meters."},
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
             "will stand on its own for a meter or two.",
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

# What the Library's books say about these materials, quoted word for word
# (a table's rows are given as its rows, not in quotation marks). The
# conductivities are the Antenna Engineering Handbook's Table 46-2 - 0.61 for
# aluminium is 3.54 over 5.80 - and the cautions are its chapter 27 and the
# field manuals'. `file` and `page` open the book at the page in the reader
# where this unit has it; the ATP ships with ELMER, the others are an
# operator's own copies and are cited whether or not they are on the shelf.
# What the books do not cover - the fusing current (Preece), wire gauges,
# anodizing - is said in the notes without a book to lean on.
ATP = "ATP 6-02.53, Techniques for Tactical Radios and Retransmission"
MCRP = "MCRP 3-40.3C (MCRP 6-22D), Antenna Handbook"
AEH = "Antenna Engineering Handbook, 3rd ed. (Johnson)"
SOURCES = {
    "wire": {"title": ATP, "where": "para. H-50", "file": "ATP-6-02.53-2025.pdf", "page": 134, "kind": "quote",
             "says": "The best kinds of wire for antennas are copper and aluminum. In an emergency, operators "
                     "use any available wire. The exact length of most antennas is critical."},
    "stretch": {"title": MCRP, "where": "p. 6-4", "file": "MCRP 3-40.3C With Erratum z.pdf", "page": 137, "kind": "quote",
                "says": "To keep the antenna taut and to prevent it from breaking or stretching as the trees sway, "
                        "attach a spring or old inner tube to one end of the antenna."},
    "aluminium": {"title": AEH, "where": "Table 46-2, p. 46-6", "file": "Antenna Engineering Handbook.pdf",
                  "page": 1479, "kind": "table",
                  "says": "Aluminum, commercial hard-drawn, 3.54 × 10⁷ S/m; copper, annealed, "
                          "5.80 × 10⁷ S/m - aluminium conducts 0.61 as well."},
    "steel": {"title": AEH, "where": "Table 46-2, p. 46-6", "file": "Antenna Engineering Handbook.pdf",
              "page": 1479, "kind": "table",
              "says": "Steel, 0.5 to 1.0 × 10⁷ S/m; zinc, 1.74 × 10⁷; copper, annealed, "
                      "5.80 × 10⁷ - steel conducts a tenth to a sixth as well, before its magnetism "
                      "crowds RF further toward the surface."},
    "tin": {"title": AEH, "where": "Table 46-2, p. 46-6", "file": "Antenna Engineering Handbook.pdf",
            "page": 1479, "kind": "table",
            "says": "Tin, 0.869 × 10⁷ S/m; copper, annealed, 5.80 × 10⁷ - tin conducts about "
                    "a seventh as well, which is why it is a plating over the copper and not the conductor."},
    "fatigue": {"title": AEH, "where": "p. 27-3", "file": "Antenna Engineering Handbook.pdf", "page": 938, "kind": "quote",
                "says": "Aluminum and its alloys are very prone to fatigue failure, and the antenna engineer must "
                        "be aware of this problem."},
    "contact": {"title": AEH, "where": "p. 27-3", "file": "Antenna Engineering Handbook.pdf", "page": 938, "kind": "quote",
                "says": "A contact potential of 0.25 V is the maximum permissible for long life in exposed "
                        "conditions."},
    "plastics": {"title": AEH, "where": "pp. 27-3 to 27-4", "file": "Antenna Engineering Handbook.pdf", "page": 938,
                 "kind": "quote",
                 "says": "Plastics do not corrode, but they degrade by oxidation and the action of ultraviolet "
                         "light."},
}
CITES = {
    "wire14": ["wire"], "wire12": ["wire"], "wire18": ["wire"],
    "fence": ["wire", "steel"], "hanger": ["steel"], "tape": ["steel"], "emt12": ["steel"],
    "alu12": ["aluminium", "fatigue"], "alu34": ["aluminium", "fatigue"],
    "magnet15": ["wire", "stretch", "plastics"], "magnet26": ["wire", "stretch", "plastics"],
    "magnet40": ["wire", "stretch", "plastics"], "magnet30": ["wire", "stretch", "plastics"],
    "alufence": ["wire", "aluminium", "fatigue", "contact"],
    "alucraft": ["aluminium", "fatigue", "contact", "stretch"],
    "zip18": ["wire", "tin", "plastics", "stretch"], "zip22": ["wire", "tin", "plastics", "stretch"],
}


def sources(key):
    """The Library's word on a conductor: each source with whether this unit
    has the book, so the Lab can open it at the page."""
    from . import library
    out = []
    for name in CITES.get(key, []):
        s = dict(SOURCES[name])
        try:
            s["have"] = library.book(s["file"]) is not None
        except OSError:
            s["have"] = False            # the shelf unreadable: cite without the link
        out.append(s)
    return out


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
    """Half of a half-wave element, in meters - the L in the thickness factor."""
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
        # how to cut, join and connect it - where most of the hard-won
        # lessons about a material live, and the Lab shows it
        "work": spec.get("work", ""),
        # what the Library's books say about it, cited to the page
        "sources": sources(spec["key"]),
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
    # Hundreds of feet strung between posts and a mast: wire, and nothing a
    # tube or a tape measure could be. The conductor does not set a length
    # here - nothing is resonant - only the loss, which on this much wire
    # is small beside what the resistor takes.
    # Aluminium fence wire belongs here most of all: the quarter-mile spool
    # is what these antennas are cheaply built from.
    "tefv": ["wire14", "wire12", "wire18", "alufence", "magnet15", "fence"],
    "termsloper": ["wire14", "wire12", "wire18", "alufence", "magnet15", "fence"],
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

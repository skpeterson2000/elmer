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
     "note": "Light enough to carry and to hang from a branch. Thin means "
             "high Q and a narrow band, and it will stretch under its own "
             "weight over a long span."},
    {"key": "wire12", "label": "#12 AWG house wire", "od_mm": 2.05,
     "material": "copper", "sigma": 1.00,
     "note": "Salvaged from a length of twin-and-earth. Stiff, tough, and "
             "holds a shape - good for a portable dipole that gets packed and "
             "unpacked."},
    {"key": "fence", "label": "Galvanised fence wire", "od_mm": 2.5,
     "material": "steel", "sigma": 0.10,
     "note": "On a farm it is the wire you already have, in any length you "
             "like.",
     "caution": "Steel conducts about a tenth as well as copper and the skin "
                "effect makes that worse at RF. On a full-size resonant "
                "element the loss is small; on anything loaded or short it is "
                "not."},
    {"key": "hanger", "label": "Coat hanger / welding rod", "od_mm": 2.5,
     "material": "steel", "sigma": 0.10,
     "note": "The classic field expedient for a VHF ground plane: four "
             "radials and a radiator out of a coat hanger works, and works "
             "tonight.",
     "caution": "Steel, so lossy - fine at VHF where the element is a "
                "resonant quarter wave, poor for anything that needs a coil."},
    {"key": "tape", "label": "Steel tape measure blade", "od_mm": 12.7,
     "material": "steel", "sigma": 0.10,
     "note": "Rolls up, springs out, survives being sat on. The blade is wide "
             "rather than round, which behaves like a conductor about as fat "
             "as it is wide - so it is broadbanded as well as portable.",
     "caution": "Steel, and the width is what buys the bandwidth rather than "
                "the conductivity."},
    {"key": "alu12", "label": "1/2 in aluminium tube", "od_mm": 12.7,
     "material": "aluminium", "sigma": 0.61,
     "note": "What beams are made of. Light, stiff, telescopes into the next "
             "size up, and does not need soldering."},
    {"key": "alu34", "label": "3/4 in aluminium tube", "od_mm": 19.05,
     "material": "aluminium", "sigma": 0.61,
     "note": "Fat enough to widen a band noticeably and still light enough to "
             "hold up on a mast."},
    {"key": "emt12", "label": "1/2 in EMT conduit", "od_mm": 17.9,
     "material": "steel", "sigma": 0.10,
     "note": "In every hardware store, cheap, and straight. Good for a "
             "vertical or a mast.",
     "caution": "Steel and usually zinc plated. Solder will not take to it - "
                "use clamps or self-tapping screws - and it is lossier than "
                "it looks."},
    {"key": "pipe12", "label": "1/2 in copper pipe (15.9 mm OD)", "od_mm": 15.9,
     "material": "copper", "sigma": 1.00,
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


def options(mhz):
    """Every choice, sorted thin to fat, so the trend is visible in the list."""
    return [describe(c["key"], mhz)
            for c in sorted(CONDUCTORS, key=lambda c: c["od_mm"])]

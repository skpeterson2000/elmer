"""Radiation patterns and SWR bandwidth - why one antenna beats another.

Two questions a gain figure does not answer. Where does the energy actually go,
and how much of the band can you use before the SWR runs away? They are the
questions that decide whether an antenna is any good for what you want, and
they are the reason a bowtie and a thin wire dipole - identical on paper at
2.15 dBi - behave nothing like each other in a garden.

**Patterns** are computed, not sketched. A half-wave dipole in free space has a
closed form, and over ground the image of the antenna adds a second wave whose
path difference depends only on height - so the lobes and the nulls fall out of
arithmetic rather than out of an artist's impression. That is worth doing
properly because the elevation pattern is the whole argument about antenna
height, and a drawing that is merely suggestive teaches the wrong lesson.

The ground is real earth where the frequency is known, and perfect where it
is not. The image's strength and phase come from the Fresnel reflection
coefficient for the soil - average pastoral ground unless told otherwise,
a relative permittivity of 13 and a conductivity of 5 mS/m, the ARRL
Antenna Book's "average" - and the two polarisations see it differently:
a horizontal wire's image stays nearly reversed, so the null at the horizon
is real; a vertical's image weakens and turns over at low angles, which is
why a ground-mounted vertical over ordinary soil peaks fifteen to twenty
five degrees up and not along the ground, the pseudo-Brewster angle that
every real measurement shows and that perfect ground hides. That is the
two-ray model with a real reflection coefficient: not a full model of the
actual wire over the actual soil, but the shape and the trend a log book
agrees with, which is what the reach map and the Lab are for. Over salt
water the vertical does reach the horizon, and GROUNDS says so.

**Bandwidth** is the resonant-circuit approximation: near resonance an antenna
behaves like a series RLC, and its Q sets how fast reactance climbs as you tune
away. Q is a property of how fat the antenna is, which is exactly what a bowtie
changes - two triangles instead of two wires is a lower Q, and lower Q is a
flatter SWR curve across the band. The Q figures here are typical of the type
rather than derived from the geometry, and are labelled that way.
"""
import cmath
import math

# Typical loaded Q near resonance, and the feedpoint resistance to match.
# Fatness is what sets Q: a thin wire is high Q and narrow, a fan or a cage is
# low Q and wide, and a parasitic array is narrower than its driven element
# alone because the parasitics load it.
# `r` is the resistance the coax actually sees once the antenna is fed the way
# it is normally fed - which is not the same as the bare feedpoint. A Yagi's
# driven element sits near 25 ohms and is brought to 50 by its gamma or hairpin;
# a loop is 115 and is fed through a balun; a J-pole's stub is the match. Using
# the bare figure would report a 2:1 bandwidth of nothing for antennas that in
# practice cover a whole band, which would be arithmetic winning over the truth.
#
# A dipole and a quarter-wave vertical are the honest exceptions: people really
# do feed those straight off 50 ohm coax and really do live with 1.4:1.
ANTENNA_Q = {
    "dipole":      {"q": 13.0, "r": 73.0, "shape": "horizontal",
                    "fed": "straight off 50 ohm coax, so it never quite reaches 1:1"},
    "invertedv":   {"q": 11.0, "r": 50.0, "shape": "horizontal",
                    "fed": "the droop pulls the feedpoint down to about 50 ohms"},
    "bowtie":      {"q": 4.5,  "r": 60.0, "shape": "horizontal",
                    "fed": "fat elements, low Q - this is the whole point of it"},
    "efhw":        {"q": 16.0, "r": 50.0, "shape": "horizontal",
                    "fed": "through its 49:1 transformer"},
    "loop":        {"q": 9.0,  "r": 50.0, "shape": "horizontal",
                    "fed": "115 ohms at the feedpoint, through a 4:1 balun"},
    "quarter":     {"q": 12.0, "r": 36.0, "shape": "vertical",
                    "fed": "straight off 50 ohm coax at about 36 ohms"},
    "fiveeighth":  {"q": 15.0, "r": 50.0, "shape": "vertical",
                    "fed": "through the base loading coil"},
    "jpole":       {"q": 10.0, "r": 50.0, "shape": "vertical",
                    "fed": "the matching stub is the match"},
    "groundplane": {"q": 11.0, "r": 50.0, "shape": "vertical",
                    "fed": "radials drooped to bring the feedpoint to 50 ohms"},
    "yagi":        {"q": 22.0, "r": 50.0, "shape": "horizontal",
                    "fed": "25 ohms at the driven element, through a gamma or hairpin"},
    "whip":        {"q": 55.0, "r": 50.0, "shape": "vertical",
                    "fed": "through its matching network - and the Q is brutal"},
    "screwdriver": {"q": 100.0, "r": 50.0, "shape": "vertical",
                    "fed": "at the base, and the motor is what keeps it there"},
    # Two loaded whips end to end. The Q is worked back from Virginia RACES'
    # measured 2:1 bandwidths (about 100 kHz on 20 m, 40 on 40 m, 20 on
    # 75 m, 2001-02), which is roughly 95 at 14 MHz rising toward 130 at
    # 3.9 - so it scales with band below, gently. The feedpoint is the tiny
    # radiation resistance plus the two coils' loss, which is what brings it
    # anywhere near coax: about 27 ohms on 40 m by the Lab's arithmetic.
    "whipdipole":  {"q": 110.0, "r": 35.0, "shape": "horizontal",
                    "fed": "straight off coax through a 1:1 choke - the loss in "
                           "the two coils is most of what brings it toward 50 ohms"},
}

# A screwdriver is not one antenna but the same antenna at every frequency it
# reaches, and the difference between its ends is the whole story: on 40 m it
# is a very short radiator with a very large coil, sharp enough that a few tens
# of kilohertz needs retuning, and by 10 m the whip is most of a quarter wave
# and behaves like one. One Q figure for all of that would be wrong at both
# ends, so its Q is stated at a reference frequency and scaled from there.
#
# The scaling is anchored to what builders measure rather than derived: about
# 50 kHz of 2:1 bandwidth on 40 m, a couple of hundred on 20 m, most of a
# megahertz on 10 m. That lands on Q falling roughly with the first power of
# frequency. The naive argument - radiation resistance goes as f squared for a
# short radiator, so bandwidth should too - overshoots the measurements badly,
# because the coil's own losses and stored energy move as well. This is an
# approximation and is labelled as one; the direction of it is not in doubt.
#
# The fixed whip deliberately keeps a single figure. It is sold cut for one
# band and used there, so the Q at its own frequency is the only one that ever
# applies to it. The screwdriver is defined by covering a decade, which is
# exactly why it cannot have one number.
Q_SCALES_WITH_BAND = {
    "screwdriver": {"ref_mhz": 7.15, "power": 1.0, "floor": 14.0},
    "whipdipole": {"ref_mhz": 7.15, "power": 0.25, "floor": 60.0},
}


def base_q(kind, mhz):
    """The antenna's own Q at this frequency, before the conductor's share."""
    spec = ANTENNA_Q.get(kind) or ANTENNA_Q["dipole"]
    rule = Q_SCALES_WITH_BAND.get(kind)
    if not rule:
        return spec["q"]
    ratio = rule["ref_mhz"] / max(0.1, float(mhz))
    return max(rule["floor"], spec["q"] * (ratio ** rule["power"]))


# The soils: relative permittivity and conductivity in S/m. "perfect" is
# the textbook conductor, kept for the curves that pre-date the ground and
# for anybody who wants the ideal shape.
GROUNDS = {
    "perfect": None,
    "average": (13.0, 0.005),      # pastoral, medium hills - the Antenna Book's default
    "poor": (5.0, 0.001),          # city, dry sand, rock
    "good": (20.0, 0.03),          # rich farmland, marsh
    "sea": (80.0, 5.0),            # salt water
}


def fresnel(elev_rad, mhz, ground="average"):
    """The ground's reflection coefficients at this grazing angle, for
    horizontal and vertical polarisation - complex, so the image has a
    strength and a phase. Perfect ground is -1 and +1."""
    soil = GROUNDS.get(ground, GROUNDS["average"])
    if soil is None or not mhz:
        return complex(-1.0, 0.0), complex(1.0, 0.0)
    er, sigma = soil
    lam = 299.792458 / float(mhz)
    eps = complex(er, -60.0 * lam * sigma)
    s, c = math.sin(elev_rad), math.cos(elev_rad)
    root = cmath.sqrt(eps - c * c)
    r_h = (s - root) / (s + root) if abs(s + root) > 1e-12 else complex(-1.0, 0.0)
    r_v = (eps * s - root) / (eps * s + root) if abs(eps * s + root) > 1e-12 else complex(-1.0, 0.0)
    return r_h, r_v


def _image(elev_rad, height_wl, reflection):
    """The direct wave and its image, added with the path difference the
    height sets and the reflection the ground gives."""
    return abs(1.0 + reflection * cmath.exp(-1j * 4.0 * math.pi * height_wl * math.sin(elev_rad)))


def _dipole_free(theta):
    """Field of a half-wave dipole at angle `theta` from its own axis."""
    s = math.sin(theta)
    if abs(s) < 1e-9:
        return 0.0
    return abs(math.cos(math.pi / 2 * math.cos(theta)) / s)


def _horizontal_over_ground(rad, height_wl, mhz=None, ground="perfect"):
    """A horizontal wire's ground reflection: image reversed, null at the
    horizon - exactly so over perfect ground, nearly so over real earth."""
    if mhz is None or GROUNDS.get(ground) is None:
        return abs(2 * math.sin(2 * math.pi * height_wl * math.sin(rad)))
    r_h, _ = fresnel(rad, mhz, ground)
    return _image(rad, height_wl, r_h)


def _vertical_over_ground(rad, height_wl, mhz=None, ground="perfect"):
    """A vertical element's: image in phase over perfect ground, so no null
    along the ground; over real earth the image weakens and turns at low
    angles and the lobe lifts to the pseudo-Brewster angle."""
    c = math.cos(rad)
    element = abs(math.cos(math.pi / 2 * math.sin(rad)) / c) if abs(c) > 1e-9 else 0.0
    if mhz is None or GROUNDS.get(ground) is None:
        return element * abs(2 * math.cos(2 * math.pi * height_wl * math.sin(rad)))
    _, r_v = fresnel(rad, mhz, ground)
    return element * _image(rad, height_wl, r_v)


def elevation_raw(kind, height_wl, points=181, mhz=None, ground="average"):
    """The elevation pattern with its level kept: 1.0 is the element alone
    in free space, so the image's reinforcement shows as up to 2.0 and its
    cancellation as 0. `elevation` below normalises to the peak, which is
    the shape; this is the shape and the gain the ground gives."""
    out = []
    for n in range(points):
        deg = 90.0 * n / (points - 1)
        rad = math.radians(deg)
        if ANTENNA_Q.get(kind, {}).get("shape") == "vertical":
            field = _vertical_over_ground(rad, height_wl, mhz, ground)
        else:
            field = _horizontal_over_ground(rad, height_wl, mhz, ground)
        out.append({"deg": round(deg, 2), "field": field})
    return out


def height_gains(kind, height_wl, mhz=None, ground="average"):
    """What this height buys, in decibels against the element alone in free
    space: straight up, at 45 degrees, at 20 degrees, and the best angle
    with its gain. The map's colors saturate near the top; these do not."""
    curve = elevation_raw(kind, height_wl, mhz=mhz, ground=ground)
    by_deg = {p["deg"]: p["field"] for p in curve}

    def db(field):
        return round(20.0 * math.log10(field), 1) if field > 1e-6 else -40.0
    best = max(curve, key=lambda p: p["field"])
    return {"overhead_db": db(by_deg[90.0]), "steep_db": db(by_deg[45.0]), "low_db": db(by_deg[20.0]),
            "best_deg": round(best["deg"]), "best_db": db(best["field"]),
            "height_wl": round(float(height_wl), 3)}


# Where the main lobe has to sit before a wire is an NVIS antenna whatever
# anybody calls it. With the lobe this steep there is no low-angle path out
# of it: the signal goes up, comes down inside a few hundred kilometers, and
# that is the whole of what the antenna can do.
NVIS_LOBE_DEG = 60.0


def is_nvis(kind, height_wl, mhz=None, ground="average"):
    """Whether this antenna, at this height on this band, is an NVIS antenna.

    Not a setting somebody chooses - a fact about the wire and the band it
    is being used on. An inverted V at 35 feet is an eighth of a wavelength
    up on 80 m and puts its whole lobe overhead; the same wire is a
    wavelength up on 10 m and is a DX antenna. Nothing on a screen changes
    that. Height does, and so does which band you tuned to.
    """
    return height_gains(kind, height_wl, mhz=mhz, ground=ground)["best_deg"] >= NVIS_LOBE_DEG


def low_angle_height_wl(kind, mhz=None, ground="average", most=1.2, step=0.02):
    """The lowest height, in wavelengths, whose main lobe has left the
    zenith - what it would take to stop being an NVIS antenna here.

    Walked rather than solved. The ground's reflection puts the lobes on a
    cycle, so there is no single root to find; the first height that clears
    the bar is the one worth telling somebody about, because it is the one
    they would build. None when nothing up to `most` wavelengths does it,
    which is the honest answer for an antenna that cannot get there.
    """
    steps = int(round(most / step))
    for i in range(1, steps + 1):
        h = i * step
        if height_gains(kind, h, mhz=mhz, ground=ground)["best_deg"] < NVIS_LOBE_DEG:
            return round(h, 3)
    return None


def elevation(kind, height_wl, points=181, slope_deg=0.0, mhz=None, ground="average"):
    """Relative field against elevation, with a slope if the wire has one.

    With `mhz` the ground is real earth of the kind named (see GROUNDS);
    without it the ground is perfect, which is the ideal shape and the
    old behavior.

    A wire tilted at an angle is neither a horizontal antenna nor a vertical
    one: it carries a horizontal component of cos(angle) and a vertical
    component of sin(angle), and the two see completely different grounds. The
    horizontal part has its image reversed, so it nulls along the horizon; the
    vertical part has its image in phase, so it does not. Tilting a wire
    therefore fills in the low angles, which is the whole of what a sloper is
    for and the whole of what its reputation rests on.

    The two components are added in power rather than in phase, which is the
    usual way to describe a slanted radiator and is an approximation. It gets
    the shape and the trend right; it is not a substitute for modeling the
    actual wire over the actual soil, and the low-angle end is optimistic
    because perfect ground is assumed throughout.
    """
    if slope_deg:
        out = []
        tilt = math.radians(max(0.0, min(90.0, slope_deg)))
        h_share, v_share = math.cos(tilt) ** 2, math.sin(tilt) ** 2
        for n in range(points):
            deg = 90.0 * n / (points - 1)
            rad = math.radians(deg)
            power = (h_share * _horizontal_over_ground(rad, height_wl, mhz, ground) ** 2
                     + v_share * _vertical_over_ground(rad, height_wl, mhz, ground) ** 2)
            out.append({"deg": round(deg, 2), "field": math.sqrt(power)})
        peak = max(p["field"] for p in out) or 1.0
        for p in out:
            p["field"] = round(p["field"] / peak, 5)
        return out
    return _elevation_plain(kind, height_wl, points, mhz=mhz, ground=ground)


def _elevation_plain(kind, height_wl, points=181, mhz=None, ground="average"):
    """Relative field against elevation angle, 0 at the horizon to 90 overhead.

    Horizontal antennas are worked out by images: the ground reflects a second
    wave, and the two arrive with a path difference set by the height, so the
    array factor is 2*sin(2*pi*h*sin(angle)). That is where the lobes come
    from, and why height rather than gain decides how low you radiate.

    A vertical over ground has no such null at the horizon - its image is in
    phase - which is the whole reason verticals are worth having for DX and
    horizontals have to be got up high before they compete.
    """
    out = []
    for n in range(points):
        deg = 90.0 * n / (points - 1)
        rad = math.radians(deg)
        if ANTENNA_Q.get(kind, {}).get("shape") == "vertical":
            # A monopole over ground: over a perfect one, maximum along the
            # ground and nothing straight up; over real earth the image
            # gives out at low angles and the lobe lifts. Its base is at
            # the height given, which for a ground-mounted vertical is nought.
            field = _vertical_over_ground(rad, height_wl, mhz, ground)
        else:
            # Broadside element, so the free-space term is flat in this plane;
            # the height interference is what shapes it.
            field = _horizontal_over_ground(rad, height_wl, mhz, ground)
        out.append({"deg": round(deg, 2), "field": field})
    peak = max(p["field"] for p in out) or 1.0
    for p in out:
        p["field"] = round(p["field"] / peak, 5)
    return out


# Somewhere to point at. Not a DXCC list - a handful of directions a US
# operator actually thinks in, so a wire's nulls can be named rather than
# merely drawn.
DX_TARGETS = [
    ("Europe", 50.0, 10.0),
    ("Japan / east Asia", 35.7, 139.7),
    ("Australia / NZ", -33.9, 151.2),
    ("South America", -23.5, -46.6),
    ("Africa", -26.2, 28.0),
    ("Caribbean", 18.5, -66.1),
    ("Hawaii / Pacific", 21.3, -157.9),
    ("Alaska", 61.2, -149.9),
]


EARTH_R_KM = 6371.0

# Where the F2 layer sits, roughly: low by day, high at night. The height
# matters because it sets how far one hop reaches, and an hour either side of
# sunset moves it more than any antenna change will.
F2_DAY_KM, F2_NIGHT_KM = 260.0, 350.0


def hop_km(elev_deg, layer_km):
    """Ground distance covered by one ionospheric hop leaving at this angle.

    The same geometry the skip simulator draws, moved here so the antenna's
    own takeoff angle can be turned into a distance. Curvature is included:
    the flat-earth form blows up at low angles and would promise the moon.
    """
    elev = math.radians(max(0.0, min(90.0, float(elev_deg))))
    sin_phi = min(1.0, EARTH_R_KM * math.cos(elev) / (EARTH_R_KM + layer_km))
    phi = math.asin(sin_phi)
    psi = math.pi / 2 - elev - phi          # earth-central angle
    return max(0.0, 2 * EARTH_R_KM * psi)


def _wire_factor(along):
    """The half-wave dipole's own pattern, for a direction whose cosine from
    the wire's axis is `along`: one broadside, nothing off the ends."""
    sin_g = math.sqrt(max(0.0, 1.0 - along * along))
    return abs(math.cos(math.pi / 2 * along) / sin_g) if sin_g > 1e-9 else 0.0


# What a beam actually leaves behind it.
#
# The cosine shape this model uses for a Yagi goes to exactly nothing at 180
# degrees, and nothing is not a number any beam has ever measured. A decent
# three-element Yagi is 15 to 25 dB front-to-back and the rear of the pattern
# is a handful of small lobes, not a hole; the hole only ever survived because
# the plan view is drawn to the pattern's own maximum, where -60 dB and -20 dB
# are both "the middle of the plot". Drawing the back of the elevation cut
# puts it on the screen, so it has to be honest: 20 dB, blended in so the
# forward shape is untouched and the rear settles at a level somebody could
# actually work a station through.
YAGI_FB_DB = 20.0


def _yagi_floor(field):
    """A beam's pattern with its front-to-back held to something real."""
    back = 10.0 ** (-YAGI_FB_DB / 20.0)
    return back + (1.0 - back) * field


def _element_shape(kind, factor):
    """What the antenna's own geometry does to a straight wire's pattern.

    An inverted V and a full-wave loop are half way to round: the current is
    not all in one straight line, so the deep nulls a dipole has off its ends
    are filled in. This used to be stated in field_toward() and nowhere else,
    while field_at() - which is what draws the plan view, what the DX bearing
    table reads and what the sheet prints - returned the plain dipole shape.
    So a V was half way to round when ELMER worked out whether you could hear
    somebody, and a pinched figure-of-eight in the picture of the same antenna
    on the same page. One antenna, two models, disagreeing: the same fault as
    the golf card and as the V's own elevation pattern, which was corrected
    without anybody noticing that the plan view had it too.
    """
    if kind in ("invertedv", "loop"):
        return 0.5 + 0.5 * factor
    return factor


def field_toward(kind, elev_deg, bearing, heading=None):
    """The element's own factor toward a direction, on top of the elevation
    curve at broadside: for a wire, the half-wave dipole's pattern in three
    dimensions - nothing off the ends along the ground, everything overhead,
    which is what makes a low wire an all-round NVIS antenna - an inverted
    V half way to round because its legs slope, a Yagi its forward lobe, a
    vertical the same all round. `heading` None means the direction is not
    known, and the factor is one."""
    if heading is None:
        return 1.0
    shape = ANTENNA_Q.get(kind, {}).get("shape")
    if shape == "vertical":
        return 1.0
    if kind == "yagi":
        return field_at(kind, bearing, heading)
    elev = math.radians(max(0.0, min(90.0, float(elev_deg))))
    along = math.cos(elev) * math.cos(math.radians(bearing - heading))   # cosine of the angle from the wire's axis
    return _element_shape(kind, _wire_factor(along))


def boresight(kind, heading=0.0):
    """The compass bearing an elevation cut is taken along.

    A beam's is where the boom points. A wire's is across itself, because a
    wire radiates broadside and a cut taken along the wire would be a slice
    through its null. A vertical has no such direction, and is given one
    only so the same code can ask.
    """
    heading = float(heading or 0.0)
    if ANTENNA_Q.get(kind, {}).get("shape") == "vertical" or kind == "yagi":
        return heading % 360
    return (heading + 90.0) % 360


def elevation_slice(kind, height_wl, slope_deg=0.0, mhz=None, ground="average",
                    heading=None, points=181):
    """The whole vertical plane: up the front, over the top, down the back.

    `deg` runs 0 to 180 - nought is the horizon the antenna faces, 90 is
    straight up, 180 is the horizon behind it - so the pair of lobes is one
    curve rather than two plots that have to be read together.

    :func:`elevation` is a quarter of this and was what got drawn, which
    made every antenna look as though it fired one way. A vertical does not:
    its pattern is a doughnut, the same in every direction round it, and the
    side view of a doughnut is two lobes. Nor does a dipole, whose two lobes
    are mirror images broadside to the wire. The one antenna where the two
    halves genuinely differ is a beam, and that difference - the
    front-to-back - is the number people buy a beam for. Drawing one lobe
    threw away the only case worth drawing and told a lie about the rest.

    The back half is the same elevation curve scaled by what the element
    does toward the opposite bearing, which for everything but a beam is
    one. `heading` None means nothing is known about which way it is laid,
    and the two halves come out alike.
    """
    front = elevation(kind, height_wl, points=points, slope_deg=slope_deg,
                      mhz=mhz, ground=ground)
    face = boresight(kind, heading if heading is not None else 0.0)
    out = [{"deg": p["deg"], "field": p["field"]} for p in front]
    for p in reversed(front[:-1]):
        ratio = 1.0
        if heading is not None:
            ahead = field_toward(kind, p["deg"], face, heading)
            behind = field_toward(kind, p["deg"], (face + 180.0) % 360, heading)
            ratio = behind / ahead if ahead > 1e-9 else 0.0
        out.append({"deg": round(180.0 - p["deg"], 2),
                    "field": round(p["field"] * ratio, 5)})
    return out


def lobe_edges(kind, height_wl, slope_deg=0.0, drop_db=3.0, mhz=None, ground="average"):
    """The elevation angles where the main lobe has fallen by `drop_db`.

    An antenna does not radiate at one angle, and a single number for "the
    takeoff angle" turns a band of workable distances into a false point. The
    half-power edges of the lobe are what turn it back into a band.

    Give it `mhz` and it reads the lobe off real earth, which is the only
    way to ask this about a vertical. Over perfect ground a vertical peaks
    at zero degrees - along the ground, where the image is exactly in phase
    - and that answer is an idealisation, not a takeoff angle: real earth
    turns the reflection against the direct wave at grazing angles, the
    field goes to nothing at the horizon, and the lobe sits fifteen to
    twenty-five degrees up. Without `mhz` there is no ground to be real
    about and the perfect-ground shape is what comes back.
    """
    curve = elevation(kind, height_wl, slope_deg=slope_deg, mhz=mhz, ground=ground)
    if not curve:
        return None, None, None
    best = max(curve, key=lambda p: p["field"])
    if best["field"] <= 0:
        return None, None, None
    # An antenna a whole wavelength up has two lobes of *equal* amplitude, so
    # taking the global maximum is a coin toss decided by rounding: half a
    # foot of mast would swing the reported reach from 2300 km to 600. The
    # lowest lobe within a decibel of the best is the one that does the DX,
    # and it is the same lobe every time you ask.
    floor = best["field"] * (10 ** (-1.0 / 20.0))
    peak = best
    for n in range(1, len(curve) - 1):
        here = curve[n]
        if (here["field"] >= floor
                and here["field"] >= curve[n - 1]["field"]
                and here["field"] >= curve[n + 1]["field"]):
            peak = here
            break
    threshold = peak["field"] * (10 ** (-drop_db / 20.0))
    # Walk outwards from the peak and stop at the first null. Taking the min
    # and max of everything above the threshold would span a second lobe and
    # the dead ring between them, and report coverage that is not there: at a
    # wavelength up, a dipole has a lobe near 15 degrees and another near 60,
    # and nothing worth having in between.
    index = curve.index(peak)
    low = high = index
    while low > 0 and curve[low - 1]["field"] >= threshold:
        low -= 1
    while high < len(curve) - 1 and curve[high + 1]["field"] >= threshold:
        high += 1
    return curve[low]["deg"], peak["deg"], curve[high]["deg"]


def hop_ring(kind, height_wl, slope_deg=0.0, day=True, mhz=None, ground="average"):
    """How far one hop reaches, as a band of distance rather than a point.

    A high takeoff angle lands close; a low one lands far. So the near edge of
    what this antenna works comes from the top of its lobe and the far edge
    from the bottom of it - which is why height, not power, is what changes an
    HF station's reach.

    `mhz` puts real earth under it - see :func:`lobe_edges`. It matters most
    here: a vertical read over perfect ground has its lower edge at zero
    degrees, and a zero-degree hop is the longest one geometry allows, so
    the ring drawn round the station was the furthest anything could ever
    go rather than where this antenna puts a signal.
    """
    low, peak, high = lobe_edges(kind, height_wl, slope_deg, mhz=mhz, ground=ground)
    if low is None:
        return None
    layer = F2_DAY_KM if day else F2_NIGHT_KM
    near = hop_km(high, layer)              # steepest angle -> shortest hop
    far = hop_km(low, layer)                # shallowest angle -> longest hop
    return {"near_km": round(near), "far_km": round(far),
            "typical_km": round(hop_km(peak, layer)),
            "takeoff_deg": round(peak, 1),
            "lobe_deg": [round(low, 1), round(high, 1)],
            "layer_km": layer}


# --- near-vertical incidence, against the ionosphere that is actually up there
#
# "Good for roughly 300 miles" is the rule of thumb and a fair average. It is
# also the one number an NVIS operator most needs to stop being an average,
# because what decides whether NVIS works at all is not the antenna: it is
# whether the frequency is under the critical frequency. Above it nothing comes
# back from overhead, a skip zone opens, and the near stations the antenna was
# put up to work are the exact ones that vanish. A fixed 500 km cannot say that.
#
# So where the ionosonde network has given us foF2 and the height of the layer,
# both get used. The outer edge is where a low wire's pattern gives out, taken
# as 45 degrees of takeoff - which off a night layer lands near the 500 km this
# used to assume, so the rule of thumb is what the model reduces to on an
# ordinary night rather than something it contradicts.
EARTH_R_KM = 6371.0
NVIS_EDGE_ANGLE = 45.0        # where a low horizontal wire stops being useful
TYPICAL_HMF2 = {True: 270.0, False: 330.0}    # day, night - when none measured


def _incidence(elev_deg, h_km):
    """Angle of incidence at the layer, allowing for the curve of the earth."""
    sin_phi = min(1.0, EARTH_R_KM * math.cos(math.radians(elev_deg))
                  / (EARTH_R_KM + h_km))
    return math.degrees(math.asin(sin_phi))


def _hop_km(elev_deg, h_km):
    """Ground distance covered by one hop leaving at this takeoff angle."""
    psi = 90.0 - elev_deg - _incidence(elev_deg, h_km)
    return 2.0 * EARTH_R_KM * math.radians(max(0.0, psi))


# ---- the layer as the ray sees it -------------------------------------------
#
# The bank shot: a ray leaves at some angle, meets the layer, and comes back
# to land a known distance out. The geometry above treats the layer as a
# mirror at the height of the F2 peak, and for a long hop well under the
# ceiling that is right. But the ionosphere refracts rather than reflects:
# the ray bends gradually and turns back at a depth that depends on its
# frequency and its angle. Breit and Tuve's theorem rescues the mirror -
# the ray lands exactly where a mirror at the *virtual* height would land -
# and Martyn's says the virtual height for an oblique ray is the one a
# vertical ray at the equivalent frequency f cos(phi) would see. So the
# mirror moves with the frequency, and near the critical frequency it runs
# away: the ball sinks deep into the cushion and comes out late and long.
#
# A parabolic layer - a peak at hmF2, a semi-thickness ym, the critical
# frequency at the peak - has that virtual height in closed form, and the
# sonde gives two of its three numbers straight out and pins the third:
# ym is whatever makes the layer's own MUF(3000) come out at the station's
# measured M(3000)F2. Three numbers every fifteen minutes, and the cushion
# has a shape.
YM_DEFAULT_KM = 100.0           # a typical F2 semi-thickness when nothing pins it
YM_RANGE_KM = (40.0, 260.0)
D_LAYER_KM = 90.0               # where the absorbing layer sits, for the angle a ray crosses it


def virtual_height_km(ratio, hmf2, ym=YM_DEFAULT_KM):
    """The mirror's height for a ray whose equivalent vertical frequency is
    `ratio` of the critical frequency: the parabolic layer's virtual height,
    the base of the layer at ratio 0, climbing without limit toward 1."""
    r = max(0.0, min(0.9995, float(ratio)))
    base = hmf2 - ym
    if r <= 0.0:
        return base
    return base + (ym / 2.0) * r * math.log((1.0 + r) / (1.0 - r))


def hop_for(elev_deg, mhz, fof2, hmf2, ym=YM_DEFAULT_KM):
    """(ground km, mirror height) for a ray leaving at this angle on this
    frequency, or None where it goes through: the mirror at the virtual
    height for the ray's own equivalent vertical frequency, which depends
    on the angle it meets the layer at, which depends on the height - so a
    few rounds, and it settles."""
    h = float(hmf2)
    for _ in range(8):
        phi = _incidence(elev_deg, h)
        fv = float(mhz) * math.cos(math.radians(phi))
        if fv >= fof2:
            return None
        h_new = virtual_height_km(fv / fof2, hmf2, ym)
        if abs(h_new - h) < 0.5:
            h = h_new
            break
        h = h_new
    return _hop_km(elev_deg, h), h


def _land_angle(km, h):
    """The takeoff angle whose hop off a mirror at h lands `km`, by
    bisection - the hop shortens as the angle steepens."""
    lo, hi = 0.0, 90.0
    if _hop_km(lo, h) < km:
        return None                       # further than one hop off this mirror
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if _hop_km(mid, h) > km:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def muf_factor(km, hmf2, ym=YM_DEFAULT_KM):
    """MUF(km) / foF2: the highest frequency, as a multiple of the critical
    frequency, that one hop can land at this distance. Straight up it is 1;
    at 3000 km it is the sonde's M(3000)F2. The ray that sets it is the
    one whose equivalent vertical frequency, and so whose mirror height,
    makes f = fv / cos(phi) largest for a hop that still lands here."""
    km = max(0.0, float(km))
    if km <= 1.0:
        return 1.0
    best = 1.0
    r = 0.30
    while r < 0.999:
        h = virtual_height_km(r, hmf2, ym)
        a = _land_angle(km, h)
        if a is not None:
            phi = _incidence(a, h)
            best = max(best, r / max(1e-6, math.cos(math.radians(phi))))
        r += 0.01 if r < 0.9 else 0.002
    return best


def layer_thickness(hmf2):
    """The layer's semi-thickness: about a third of its height, the shape
    the F2 layer usually has, and never so thick that its base falls out
    of the F region. Fitting it to the sonde's M(3000) was tried and gave
    absurd layers when the two numbers disagreed slightly, as a sonde's
    own two numbers can; the sonde's factor is honored by scaling
    instead, below."""
    return max(YM_RANGE_KM[0], min(0.35 * float(hmf2), float(hmf2) - 150.0))


_factor_cache = {}


def muf_factor_table(hmf2, ym=None, m3000=None, step_km=50.0, far_km=4500.0):
    """MUF(km)/foF2 as a function of distance, tabulated once for a layer
    shape and interpolated - a map asks for thousands of cells.

    The shape is the parabolic layer's; the level is the sonde's: with an
    M(3000) given, the curve is scaled so that it passes through 1 straight
    up and through the station's own factor at 3000 km."""
    ym = ym or layer_thickness(hmf2)
    key = (round(hmf2), round(ym), step_km)
    table = _factor_cache.get(key)
    if table is None:
        table = [(d, muf_factor(d, hmf2, ym)) for d in [0.0] + [step_km * i for i in range(1, int(far_km / step_km) + 1)]]
        if len(_factor_cache) > 16:
            _factor_cache.clear()
        _factor_cache[key] = table
    scale = 1.0
    if m3000 and m3000 > 1.0:
        own = muf_factor(3000.0, hmf2, ym)
        if own > 1.0:
            scale = (float(m3000) - 1.0) / (own - 1.0)

    def factor(km):
        km = max(0.0, float(km))
        if km >= table[-1][0]:
            raw = table[-1][1]
        else:
            i = int(km / step_km)
            d0, f0 = table[i]
            d1, f1 = table[min(i + 1, len(table) - 1)]
            t = (km - d0) / max(1e-9, d1 - d0)
            raw = f0 + (f1 - f0) * t
        return 1.0 + (raw - 1.0) * scale
    return factor


def absorption_secant(km, hmf2):
    """How obliquely the ray that lands `km` crosses the D layer: the
    secant of its angle of incidence there. Straight up is 1; a long hop is
    four or five, and pays that much more absorption on each pass."""
    a = _land_angle(max(0.0, float(km)), hmf2)
    if a is None:
        a = 0.0
    phi = _incidence(a, D_LAYER_KM)
    return 1.0 / max(0.2, math.cos(math.radians(phi)))


def _max_takeoff(mhz, fof2, h_km):
    """Steepest ray that still comes back. 90 means even straight up does."""
    if fof2 >= mhz:
        return 90.0
    sin_phi = math.sqrt(max(0.0, 1.0 - (fof2 / mhz) ** 2))
    c = sin_phi * (EARTH_R_KM + h_km) / EARTH_R_KM
    return None if c > 1.0 else math.degrees(math.acos(c))


def _miles(km):
    return round(km / 1.609)


def nvis_reach(mhz, fof2=None, hmf2=None, day=True):
    """What near-vertical incidence will actually do on this frequency now."""
    if not fof2:
        return {"kind": "regional", "radius_km": 500, "outer_km": 500,
                "modelled": False,
                "note": "Near-vertical incidence: the signal goes up and comes "
                        "back down over the whole area, with no skip zone in "
                        "the middle. Good for roughly 300 miles, and it needs "
                        "the frequency to be below the critical frequency - "
                        "which is why NVIS is an 80 and 40 meter trick by day. "
                        "No ionosonde reading is in hand, so that is the rule "
                        "of thumb rather than this evening's figure."}
    height = float(hmf2 or TYPICAL_HMF2[bool(day)])
    where = ("a layer measured at %d km" % round(height) if hmf2
             else "a layer assumed at %d km" % round(height))

    if mhz > fof2:
        # The failure the rule of thumb cannot warn anybody about.
        steepest = _max_takeoff(mhz, fof2, height)
        inner = _hop_km(steepest, height) if steepest is not None else None
        if inner is None:
            return {"kind": "regional", "radius_km": 0, "outer_km": 0,
                    "inner_km": 0, "modelled": True, "works": False,
                    "fof2": round(fof2, 1), "hmf2": round(height),
                    "note": "Not working. The critical frequency is %.1f MHz "
                            "and this is %.3f, so nothing comes back at any "
                            "angle: the band is shut over this path, not "
                            "merely steep." % (fof2, mhz)}
        # The outer edge is still the antenna's own pattern - a wire this low
        # has no gain at the shallow angles it would take to reach past the
        # skip, so scaling the ring up with the skip would be drawing reach the
        # antenna does not have.
        outer = _hop_km(NVIS_EDGE_ANGLE, height)
        if inner >= outer:
            return {"kind": "regional", "radius_km": 0, "outer_km": 0,
                    "inner_km": round(inner), "modelled": True, "works": False,
                    "skip_km": round(inner),
                    "fof2": round(fof2, 1), "hmf2": round(height),
                    "note": "Nothing, on this band, off this antenna. The "
                            "critical frequency is %.1f MHz and you are on "
                            "%.3f, so the steepest ray that comes back already "
                            "lands %d miles out - past everything a wire at "
                            "this height can usefully reach. It is not that "
                            "NVIS is degraded: there is no NVIS here. Off %s."
                            % (fof2, mhz, _miles(inner), where)}
        return {"kind": "regional", "radius_km": round(outer),
                "outer_km": round(outer), "inner_km": round(inner),
                "modelled": True, "works": False, "skip_km": round(inner),
                "fof2": round(fof2, 1), "hmf2": round(height),
                "note": "Near-vertical incidence is not working on this "
                        "frequency now. The critical frequency is %.1f MHz and "
                        "you are on %.3f, so nothing comes back from overhead: "
                        "there is a hole about %d miles across in the middle of "
                        "the footprint, and the near stations this antenna was "
                        "put up to work are the ones inside it. Off %s. A lower "
                        "band gets them back." % (fof2, mhz, _miles(inner), where)}

    radius = _hop_km(NVIS_EDGE_ANGLE, height)
    headroom = fof2 - mhz
    return {"kind": "regional", "radius_km": round(radius),
            "outer_km": round(radius), "modelled": True, "works": True,
            "fof2": round(fof2, 1), "hmf2": round(height),
            "headroom_mhz": round(headroom, 1),
            "note": "Near-vertical incidence, and it is working: the critical "
                    "frequency is %.1f MHz, so %.3f still comes back from "
                    "straight overhead with %.1f MHz to spare. Continuous "
                    "coverage out to about %d miles off %s, with no skip zone "
                    "in the middle. It holds for as long as the critical "
                    "frequency stays above the band, which is the thing to "
                    "watch." % (fof2, mhz, headroom, _miles(radius), where)}


# What a horizontal wire does about its own ground, which is the answer to
# "can the antenna help inside the skip zone" - and the answer is usually yes.
#
# A horizontal antenna over ground is a two element array: the wire, and its
# image below the surface. The reflection arrives phase-reversed, so at about
# a quarter wave up it comes back in step straight overhead and the pattern
# points at the sky. Take it toward half a wave and the same reflection
# cancels overhead and splits the lobe, which is where a skip zone comes from.
# It is tuned the way a loudspeaker is tuned against a wall: the boundary is
# part of the instrument, and the distance to it decides what reinforces and
# what cancels.
#
# So an operator inside a skip zone with the band still under foF2 is not
# stuck. They are too high.
NVIS_FILL_WAVES = 0.20          # where the overhead lobe is strongest
NVIS_SPLIT_WAVES = 0.45         # past here the lobe has split and the gap opens


def fill_the_gap(mhz, height_ft, fof2=None):
    """Whether lowering this antenna would close the hole in the middle.

    None when it would not - which is a real case, and the only one the old
    wording was right about: above the critical frequency nothing comes back
    from overhead however the wire is hung.
    """
    if not fof2 or mhz > fof2:
        return None
    lam_ft = 983.571 / mhz
    if max(0.0, height_ft) / lam_ft <= NVIS_SPLIT_WAVES:
        return None                       # already low enough to be filling it
    return {"to_ft": round(NVIS_FILL_WAVES * lam_ft),
            "from_ft": round(height_ft), "fof2": round(fof2, 1)}


def _gap_note(mhz, height_ft, fof2):
    """What to do about the hole, which depends on whether the sky is shut."""
    fill = fill_the_gap(mhz, height_ft, fof2)
    if fill:
        return (" It is not out of reach, though: %.3f MHz is under the %.1f "
                "MHz critical frequency, so bringing this wire down from about "
                "%d feet to about %d - a fifth of a wavelength - turns it into "
                "an NVIS antenna and fills the middle in. The ground reflection "
                "does it: at that height it returns in step straight overhead "
                "instead of cancelling there."
                % (mhz, fill["fof2"], fill["from_ft"], fill["to_ft"]))
    if fof2 and mhz > fof2:
        return (" Nothing comes back from overhead at %.3f MHz while the "
                "critical frequency is %.1f, so no height will fill it - that "
                "is what a lower band is for." % (mhz, fof2))
    return (" Whether lowering the antenna fills it depends on the critical "
            "frequency, which is not in hand here: under it, a wire down "
            "around a fifth of a wavelength radiates straight up and there is "
            "no hole at all. Above it, only a lower band will do.")



def reach(kind, use, mhz, height_ft=0.0, nvis=False, slope_deg=0.0,
          day=True, fof2=None, hmf2=None):
    """How far this antenna actually works, and what to compare it against.

    The point of asking is that the answer decides who the neighbours are. An
    NVIS wire on 80 m does not reach Europe and never will, so drawing Europe
    on its compass is worse than drawing nothing: it invites somebody to turn
    an antenna to chase a contact the antenna cannot make.
    """
    mhz = float(mhz)
    if use == "satellite":
        return {"kind": "satellite", "radius_km": None,
                "note": "A satellite is overhead and moving, so ground bearings "
                        "do not describe it. What matters is a clear view of the "
                        "sky and being able to follow the pass."}
    if mhz >= 50.0 and use == "weaksignal":
        # SSB and CW on VHF are not line-of-sight work. A beam and a hundred
        # watts routinely make a couple of hundred miles on tropospheric
        # refraction alone, which is why the weak-signal crowd point antennas
        # at towns rather than at the horizon.
        return {"kind": "tropo", "radius_km": 320,
                "note": "Weak-signal VHF: tropospheric refraction carries SSB "
                        "and CW well beyond line of sight - about 200 miles on "
                        "an ordinary day with a beam, much further when the air "
                        "is layered or a band opens. Height and a clear takeoff "
                        "matter more than power."}
    if mhz >= 50.0:
        # Radio horizon, 4/3 earth, to a station at a similar height.
        miles = 1.415 * math.sqrt(max(height_ft, 1.0)) * 2
        return {"kind": "line_of_sight", "radius_km": round(miles * 1.609),
                "note": f"Line of sight: about {round(miles)} miles to another "
                        f"antenna at this height, and much further to a repeater "
                        f"on a tower or a hill."}
    if nvis or use == "regional":
        return nvis_reach(mhz, fof2, hmf2, day)
    # One hop, from this antenna's own takeoff angle. Saying "it depends on
    # the band and the hour" was true and useless: the operator wanted a
    # distance, and the antenna they have already decides most of it.
    lam_ft = 983.571 / mhz
    ring = hop_ring(kind, max(0.0, height_ft / lam_ft), slope_deg, day, mhz=mhz)
    if not ring:
        return {"kind": "dx", "radius_km": None,
                "note": "Ionospheric propagation, so distance depends on the "
                        "band and the hour rather than on the antenna alone."}
    return {
        "kind": "dx", "radius_km": ring["far_km"], "inner_km": ring["near_km"],
        "outer_km": ring["far_km"], "typical_km": ring["typical_km"],
        "takeoff_deg": ring["takeoff_deg"], "lobe_deg": ring["lobe_deg"],
        "layer_km": ring["layer_km"],
        "note": (f"One hop off the F2 layer at about {ring['layer_km']:.0f} km, "
                 f"leaving at {ring['takeoff_deg']}\u00b0: that lands roughly "
                 f"{ring['near_km']}-{ring['far_km']} km out, typically around "
                 f"{ring['typical_km']}. Inside the near edge is the skip "
                 f"zone." + _gap_note(mhz, height_ft, fof2)),
    }


# What the geometry says, and what the day says. Both are true; only one of
# them is a promise, and it is not the first.
QUALIFIED = {
    "dx": ("Geometry only: one hop, a smooth earth, and a layer where the "
           "model puts it.",
           "The band has to be open to that distance at that hour, and the "
           "station at the far end needs to hear you."),
    "regional": ("The signal goes up and comes back down over the whole area, "
                 "with no skip zone in the middle.",
                 "Only while the frequency stays below the critical frequency "
                 "- which is why NVIS is an 80 and 40 meter trick, and why it "
                 "fails on 20."),
    "tropo": ("Refraction in the lower atmosphere, which does not care about "
              "the sun.",
              "Terrain decides it. A ridge in the way beats the calculation, "
              "and a temperature inversion beats the ridge."),
    "line_of_sight": ("Radio horizon over a smooth earth at 4/3 radius.",
                      "Anything solid between the two antennas wins. Height "
                      "is the whole game here: twenty feet up beats twenty "
                      "watts."),
    "satellite": ("A clear view of the sky.",
                  "The pass has to be happening, and you have to be following "
                  "it."),
}


# When a DX ring is actually there, which is the opposite question at the two
# ends of HF and cannot be answered with one sentence. A ring on 20 m and up
# is a daylight thing that shuts after dark. A ring on 80 or 40 is the other
# way round entirely: the day is what kills it, and the hours it reaches are
# the ones after sunset. Printing "closes at night" over an 80 m answer is not
# a caveat, it is the truth upside down - and it is the sort of wrong that
# sends somebody to bed at the hour their band was about to open.
DX_HOURS = [
    (10.0, "Down here that is a night ring. The D layer absorbs most of the "
           "day away and the distance collapses with it; the hours this "
           "reaches are the ones after dark, and the far edge goes on opening "
           "as the night deepens."),
    (18.0, "Through the middle of HF it runs day and night - widest through "
           "the afternoon, and holding open some way past sunset before it "
           "shortens."),
    (None, "Up here it is a daylight ring. It breathes by hundreds of "
           "kilometers through the day and closes after dark, and on a quiet "
           "sun it may not open at all."),
]


def dx_hours(mhz):
    """When the DX ring is actually open, for the band it is drawn on.

    Without a frequency this says nothing about the clock rather than
    guessing: half the guesses would be backwards.
    """
    if not mhz:
        return "When it is open depends on the band and the hour."
    for edge, said in DX_HOURS:
        if edge is None or float(mhz) < edge:
            return said
    return ""


def qualify(span, mhz=None):
    """Attach the lab answer and the real-world answer, separately labelled."""
    lab, real = QUALIFIED.get(span.get("kind"), (None, None))
    if lab:
        span["lab"] = lab
        span["real"] = real
        if span.get("kind") == "dx":
            span["real"] = (real + " " + dx_hours(mhz)).strip()
    return span


def nearby(lat, lon, radius_km, limit=8, inner_km=0.0, spread=False):
    """The places actually inside this antenna's reach, nearest first.

    Nearest rather than spread evenly around the compass: inside an NVIS
    footprint everything is workable, so what the operator wants is their own
    neighbours - the towns they would name if asked - not one token place per
    sector with the obvious ones squeezed out by whatever sat closer.

    The candidates come from :mod:`elmer.places`, which prefers what it fetched
    for this neighbourhood over what shipped with the program. Returns the rows
    and which of the two they came from, because a bundled answer deserves to
    be labelled as one.
    """
    from .terrain import great_circle
    from . import places as place_source

    candidates, source = place_source.known(lat, lon, radius_km)

    # A city takes its suburbs with it. Ranked by population, then a place is
    # only kept if it is well clear of everything bigger already kept - so
    # Minneapolis stands for Coon Rapids and Maple Grove, which is how anybody
    # would say it. Without this the list fills with dormitory towns that
    # happen to sit a few miles nearer than the city they belong to.
    ordered = sorted(candidates, key=lambda p: -(p.get("population") or 0))
    kept = []
    for place in ordered:
        km, bearing = great_circle(lat, lon, place["lat"], place["lon"])
        if km < max(15.0, inner_km) or km > radius_km:
            continue
        if any(great_circle(place["lat"], place["lon"],
                            other["lat"], other["lon"])[0] < 45 for other in kept):
            continue
        kept.append(dict(place, km=round(km), bearing=round(bearing)))

    if spread:
        # A ring is about which way to point, so take the best place in each
        # sector of the compass rather than the nearest few. Nearest-first on
        # an annulus returns eight towns hugging the inner edge in whatever
        # direction happens to be nearest, and the whole question was which
        # direction.
        sectors, step = {}, 360.0 / max(1, limit)
        for row in sorted(kept, key=lambda r: -(r.get("population") or 0)):
            sectors.setdefault(int(row["bearing"] / step), row)
        kept = list(sectors.values())
    kept.sort(key=lambda r: r["km"])
    found = [{"name": r["name"], "region": r.get("region") or "",
              "bearing": r["bearing"], "km": r["km"]} for r in kept[:limit]]
    return sorted(found, key=lambda r: r["bearing"]), source


# Reaches whose signal leaves the ground and comes back. For these the
# takeoff angle to a place is set by how far away it is, and the antenna
# must be asked about that angle. The others - line of sight, tropo, a
# repeater on a hill - really do travel along the ground, and there the
# ground slice is the right one and a wire's end null is real.
SKY_REACH = ("regional", "dx")


def _reach_angle(km, hmf2, sky):
    """The takeoff angle that gets to something `km` away.

    Along the ground for a line-of-sight path. For a skywave path it is
    whatever angle lands there off the layer: steep for the next county,
    shallow for the far side of the country. Falls back to the ground when
    a place is further than one hop, where a single angle is the wrong
    question anyway.
    """
    if not sky or not km:
        return 0.0
    # TYPICAL_HMF2 is this module's own stand-in when nothing was measured;
    # the night figure, because an unmeasured layer is usually an unmeasured
    # evening and the steeper answer is the conservative one here.
    angle = _land_angle(float(km), float(hmf2 or TYPICAL_HMF2[False]))
    return 0.0 if angle is None else angle


def targets(lat, lon, kind, heading, reach_info, hmf2=None):
    """What to draw on the compass: whatever this antenna can actually work.

    Each place is scored at the angle needed to reach *it*. Scoring them all
    along the ground - which is what this did - put a deep null across the
    ends of the wire and marked the towns there as unworkable, on an antenna
    whose whole output leaves at seventy degrees and which is within a
    decibel of round up there. Duluth was called unreachable from a hundred
    miles away because the wire happened to point at it.
    """
    if reach_info["kind"] == "satellite":
        return []

    if reach_info["kind"] == "dx":
        # The well-known parts of the world stay - they are what an operator
        # points a beam at - but the compass now also carries the towns that
        # actually fall in the ring this antenna reaches. "Somewhere in
        # Europe" is a direction; Denver at 1,400 km is a contact.
        reach_info["world"] = dx_bearings(lat, lon, kind, heading, hmf2=hmf2)
        if not reach_info.get("outer_km"):
            return reach_info["world"]
        rows, source = nearby(lat, lon, reach_info["outer_km"],
                              inner_km=reach_info.get("inner_km") or 0.0,
                              spread=True)
        reach_info["places_from"] = source
    else:
        # inner_km matters here too now: when the critical frequency has
        # fallen through the band an NVIS footprint is a ring, and the towns
        # inside the hole are precisely the ones that cannot be worked.
        rows, source = nearby(lat, lon, reach_info["radius_km"],
                              inner_km=reach_info.get("inner_km") or 0.0)
        reach_info["places_from"] = source

    sky = reach_info["kind"] in SKY_REACH
    for row in rows:
        elev = _reach_angle(row.get("km"), hmf2, sky)
        field = field_toward(kind, elev, row["bearing"], heading)
        row["field"] = round(field, 4)
        row["db"] = db(field)
        row["takeoff_deg"] = round(elev, 1)
    return rows


def field_at(kind, bearing, heading=0.0):
    """Relative field toward a compass bearing, for an antenna laid this way.

    `heading` is the bearing the antenna is laid along: the run of the wire for
    a dipole, where the boom points for a beam. A vertical ignores it, which is
    the whole reason it gets called omnidirectional.
    """
    shape = ANTENNA_Q.get(kind, {}).get("shape")
    if shape == "vertical":
        return 1.0
    if kind == "yagi":
        off = math.radians((bearing - heading + 180) % 360 - 180)
        return _yagi_floor(abs(0.5 + 0.5 * math.cos(off)) ** 1.6)
    # A wire radiates broadside: strongest across itself, nothing off the ends.
    # Along the ground, which is what a plan view is, so this is field_toward
    # at nought degrees of elevation and must stay equal to it - it used to be
    # a plain cosine, which is a rounder curve than a dipole's and took no
    # account of an inverted V's sloping legs at all.
    along = math.cos(math.radians(bearing - heading))
    return _element_shape(kind, _wire_factor(along))


def azimuth(kind, heading=0.0, points=361, elev_deg=0.0):
    """Relative field around the compass, as the antenna is actually laid.

    `elev_deg` is the takeoff angle the slice is cut at, and it matters more
    than anything else on the plot. At nought degrees - along the ground -
    a wire has its deepest nulls off the ends, and that is the slice this
    used to be, always, whatever the antenna. But a low wire radiates almost
    nothing along the ground: at the angle it actually works at, those nulls
    have filled in, and by the zenith there is no direction to it at all.

    So a 30 ft inverted V on 80 m was being drawn as a pinched figure-of-eight
    and described as "deaf" east and west, when at its own main lobe - straight
    up - it is within a tenth of a decibel of round. The page now draws both
    slices, because the difference between them is the lesson.
    """
    return [{"bearing": n,
             "field": round(field_toward(kind, elev_deg, n, heading), 5)}
            for n in range(points)]


def db(field):
    """Field as decibels against the pattern's own maximum."""
    if field <= 0.0005:
        return -60.0
    return round(20 * math.log10(field), 1)


def dx_bearings(lat, lon, kind=None, heading=0.0, hmf2=None):
    """Where the well-known parts of the world are, and what the antenna does
    toward each of them - at the angle each one actually needs."""
    from .terrain import great_circle
    out = []
    for name, tlat, tlon in DX_TARGETS:
        km, bearing = great_circle(lat, lon, tlat, tlon)
        row = {"name": name, "bearing": round(bearing), "km": round(km)}
        if kind:
            elev = _reach_angle(km, hmf2, True)
            field = field_toward(kind, elev, bearing, heading)
            row["field"] = round(field, 4)
            row["db"] = db(field)
            row["takeoff_deg"] = round(elev, 1)
        out.append(row)
    return sorted(out, key=lambda r: r["bearing"])


def main_lobe(kind, height_wl, slope_deg=0.0, mhz=None, ground="average"):
    """The elevation angle the antenna actually favors.

    Asked of the same curve the page draws, which means `mhz` has to come in
    with the question. It did not, and the answer was read off perfect
    ground while real earth was on the screen beside it: every vertical was
    reported as strongest at zero degrees, with the marker laid along the
    horizon, against a lobe plainly peaking twenty-odd degrees up. The
    element is strongest along the ground and that much is true of the
    antenna; the ground is what takes the last few degrees back.
    """
    best = max(elevation(kind, height_wl, slope_deg=slope_deg, mhz=mhz, ground=ground),
               key=lambda p: p["field"])
    return best["deg"]


def swr_curve(kind, f0_mhz, z0=50.0, span=0.30, points=121, q=None):
    """SWR against frequency, from the resonant-circuit approximation.

    Near resonance X ~ R*Q*(f/f0 - f0/f), which is the standard series-resonant
    form. It is an approximation and stops being one a long way off resonance,
    so the sweep is kept to +/-15% where it still means something.
    """
    out = []
    for n in range(points):
        f = f0_mhz * (1 - span / 2 + span * n / (points - 1))
        z = feedpoint_z(kind, f, f0_mhz, q)
        g = abs((z - z0) / (z + z0))
        swr = (1 + g) / (1 - g) if g < 0.999999 else float("inf")
        out.append({"mhz": round(f, 4), "swr": round(min(swr, 20.0), 3)})
    return out


def feedpoint_z(kind, mhz, f0_mhz, q=None):
    """The complex impedance at the feedpoint, at one frequency.

    Pulled out of `swr_curve` because an SWR number is not enough to draw what
    an instrument shows. A VNA measures a complex reflection: the resistance
    and the reactance separately, and the sign of the reactance is what tells
    somebody whether the antenna is long or short. Collapsing that to one
    magnitude throws away the half of the answer that says which way to cut.
    """
    spec = ANTENNA_Q.get(kind, ANTENNA_Q["dipole"])
    # `q` overrides the table so the conductor the element is made of can move
    # it: a fatter element is a lower-Q element, and that is the whole reason
    # anybody builds an antenna out of pipe.
    q, r = (spec["q"] if q is None else float(q)), spec["r"]
    return complex(r, r * q * (mhz / f0_mhz - f0_mhz / mhz))


def usable_bandwidth(kind, f0_mhz, limit=2.0, z0=50.0, q=None):
    """The span where SWR stays under `limit`, in MHz and as a percentage."""
    curve = swr_curve(kind, f0_mhz, z0=z0, points=601, q=q)
    good = [p["mhz"] for p in curve if p["swr"] <= limit]
    if not good:
        return {"limit": limit, "low": None, "high": None, "khz": 0, "percent": 0.0}
    low, high = min(good), max(good)
    return {"limit": limit, "low": round(low, 4), "high": round(high, 4),
            "khz": round((high - low) * 1000), "percent": round(100 * (high - low) / f0_mhz, 2)}


# --------------------------------------------------------------------------
# when the answer is "nobody"
# --------------------------------------------------------------------------

def advise_empty(span, mhz, kind, height_ft, use=None, bundled=False):
    """What to do instead, when this antenna on this frequency reaches nobody.

    An empty compass is a real answer and usually a discouraging one, and the
    discouragement is misplaced: it almost never means the operator is out of
    options, only that this combination is the wrong one. So say which knob
    moves - and the answer is rarely the power knob.
    """
    mhz = float(mhz)
    out = []
    reach_kind = span.get("kind")

    # "Nothing in range" and "nothing in the list that shipped with me" are
    # different sentences, and the bundled list is North American. Telling an
    # operator in Bavaria that their antenna reaches nobody would be a data
    # gap wearing the costume of a propagation answer.
    if bundled:
        out.append({
            "do": "Let ELMER look up what is actually around you first",
            "why": ("The list that ships with ELMER is a few hundred North "
                    "American cities. If you are anywhere else, an empty "
                    "compass says more about the list than about your "
                    "antenna. Run ./elmer.py --fetch-places once with a "
                    "network and it will ask OpenStreetMap for your real "
                    "neighbours."),
        })

    if reach_kind == "dx":
        inner = span.get("inner_km") or 0
        if inner > 200:
            out.append({
                "do": "Drop a band",
                "why": (f"Everything inside {inner} km is skip zone for this "
                        f"antenna - the signal is already over their heads. A "
                        f"lower band bends back more steeply and fills that "
                        f"hole in. On 40 or 80 the same wire covers the ground "
                        f"this one steps across."),
            })
            out.append({
                "do": "Lower the antenna, or feed it as an inverted V",
                "why": ("Height buys distance by lowering the takeoff angle, "
                        "and that is exactly what opened the hole. Half a "
                        "wavelength up is the compromise; a quarter is "
                        "deliberately near-vertical."),
            })
        out.append({
            "do": "Work the ring, not the middle",
            "why": (f"The contacts are between {span.get('inner_km', 0)} and "
                    f"{span.get('outer_km', 0)} km out. Point the antenna and "
                    f"the expectations there, and let a lower band have the "
                    f"close-in work."),
        })
    elif reach_kind in ("line_of_sight", "tropo"):
        out.append({
            "do": "Get higher before you get louder",
            "why": ("Above 50 MHz the horizon is the limit and power does not "
                    "move it. Twenty feet up, or a hilltop, changes the answer "
                    "in a way another hundred watts cannot."),
        })
        out.append({
            "do": "Use a machine on a tower",
            "why": ("A repeater is high so you do not have to be. That is the "
                    "whole point of one, and it is why the FM bands are "
                    "arranged around them."),
        })
        if mhz >= 50 and use in (None, "local", "digital"):
            out.append({
                "do": "Try a weak-signal mode instead of FM",
                "why": ("SSB and CW work perhaps 10 to 20 dB further down into "
                        "the noise than FM does, which is the difference "
                        "between a quiet band and an empty one. Turn the "
                        "antenna horizontal for them."),
            })
    else:
        out.append({
            "do": "Try a digital mode",
            "why": ("FT8 and similar decode 10 to 15 dB below what an ear can "
                    "hear. A path that carries nothing you can talk over will "
                    "often still carry data."),
        })

    # Waiting helps everywhere, but not for the same reason - and giving the
    # ionospheric reason to somebody working line of sight is the sort of
    # nearly-right answer that teaches the wrong model.
    if reach_kind in ("line_of_sight", "tropo"):
        out.append({
            "do": "Try again at dawn or dusk",
            "why": ("Tropospheric ducting builds when the air layers, which is "
                    "mostly early morning and evening and after a still, clear "
                    "night. The ionosphere has nothing to do with it at these "
                    "frequencies. Activity helps too: evenings and net nights "
                    "are when anybody is listening."),
        })
    else:
        out.append({
            "do": "Come back at a different hour",
            "why": ("The ionosphere is a different animal at dawn, at noon and "
                    "after dark, and the band that is empty now may be the "
                    "busy one in four hours. Nothing on the antenna changes "
                    "that; waiting does."),
        })
    return out

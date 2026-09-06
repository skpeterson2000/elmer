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

Perfect ground is assumed. Real earth fills the deepest nulls in and takes the
lowest degree or two off, so treat the shape as right and the last few degrees
above the horizon as optimistic - the more so over dry sand, the less over salt
water.

**Bandwidth** is the resonant-circuit approximation: near resonance an antenna
behaves like a series RLC, and its Q sets how fast reactance climbs as you tune
away. Q is a property of how fat the antenna is, which is exactly what a bowtie
changes - two triangles instead of two wires is a lower Q, and lower Q is a
flatter SWR curve across the band. The Q figures here are typical of the type
rather than derived from the geometry, and are labelled that way.
"""
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
}


def _dipole_free(theta):
    """Field of a half-wave dipole at angle `theta` from its own axis."""
    s = math.sin(theta)
    if abs(s) < 1e-9:
        return 0.0
    return abs(math.cos(math.pi / 2 * math.cos(theta)) / s)


def _horizontal_over_ground(rad, height_wl):
    """A horizontal wire's ground reflection: image reversed, null at the horizon."""
    return abs(2 * math.sin(2 * math.pi * height_wl * math.sin(rad)))


def _vertical_over_ground(rad, height_wl):
    """A vertical element's: image in phase, so no null along the ground."""
    c = math.cos(rad)
    element = abs(math.cos(math.pi / 2 * math.sin(rad)) / c) if abs(c) > 1e-9 else 0.0
    return element * abs(2 * math.cos(2 * math.pi * height_wl * math.sin(rad)))


def elevation(kind, height_wl, points=181, slope_deg=0.0):
    """Relative field against elevation, with a slope if the wire has one.

    A wire tilted at an angle is neither a horizontal antenna nor a vertical
    one: it carries a horizontal component of cos(angle) and a vertical
    component of sin(angle), and the two see completely different grounds. The
    horizontal part has its image reversed, so it nulls along the horizon; the
    vertical part has its image in phase, so it does not. Tilting a wire
    therefore fills in the low angles, which is the whole of what a sloper is
    for and the whole of what its reputation rests on.

    The two components are added in power rather than in phase, which is the
    usual way to describe a slanted radiator and is an approximation. It gets
    the shape and the trend right; it is not a substitute for modelling the
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
            power = (h_share * _horizontal_over_ground(rad, height_wl) ** 2
                     + v_share * _vertical_over_ground(rad, height_wl) ** 2)
            out.append({"deg": round(deg, 2), "field": math.sqrt(power)})
        peak = max(p["field"] for p in out) or 1.0
        for p in out:
            p["field"] = round(p["field"] / peak, 5)
        return out
    return _elevation_plain(kind, height_wl, points)


def _elevation_plain(kind, height_wl, points=181):
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
            # Quarter-wave monopole over ground: maximum along the ground,
            # nothing straight up.
            c = math.cos(rad)
            field = (abs(math.cos(math.pi / 2 * math.sin(rad)) / c)
                     if abs(c) > 1e-9 else 0.0)
        else:
            # Broadside element, so the free-space term is flat in this plane;
            # the height interference is what shapes it.
            field = abs(2 * math.sin(2 * math.pi * height_wl * math.sin(rad)))
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


def lobe_edges(kind, height_wl, slope_deg=0.0, drop_db=3.0):
    """The elevation angles where the main lobe has fallen by `drop_db`.

    An antenna does not radiate at one angle, and a single number for "the
    takeoff angle" turns a band of workable distances into a false point. The
    half-power edges of the lobe are what turn it back into a band.
    """
    curve = elevation(kind, height_wl, slope_deg=slope_deg)
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


def hop_ring(kind, height_wl, slope_deg=0.0, day=True):
    """How far one hop reaches, as a band of distance rather than a point.

    A high takeoff angle lands close; a low one lands far. So the near edge of
    what this antenna works comes from the top of its lobe and the far edge
    from the bottom of it - which is why height, not power, is what changes an
    HF station's reach.
    """
    low, peak, high = lobe_edges(kind, height_wl, slope_deg)
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


def reach(kind, use, mhz, height_ft=0.0, nvis=False, slope_deg=0.0,
          day=True):
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
        return {"kind": "regional", "radius_km": 500,
                "note": "Near-vertical incidence: the signal goes up and comes "
                        "back down over the whole area, with no skip zone in the "
                        "middle. Good for roughly 300 miles, and it needs the "
                        "frequency to be below the critical frequency - which is "
                        "why NVIS is an 80 and 40 metre trick by day."}
    # One hop, from this antenna's own takeoff angle. Saying "it depends on
    # the band and the hour" was true and useless: the operator wanted a
    # distance, and the antenna they have already decides most of it.
    lam_ft = 983.571 / mhz
    ring = hop_ring(kind, max(0.0, height_ft / lam_ft), slope_deg, day)
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
                 f"{ring['typical_km']}. Inside the near edge is the skip zone "
                 f"and the antenna cannot help you there - a lower band can."),
    }


# What the geometry says, and what the day says. Both are true; only one of
# them is a promise, and it is not the first.
QUALIFIED = {
    "dx": ("Geometry only: one hop, a smooth earth, and a layer where the "
           "model puts it.",
           "The band has to be open to that distance at that hour, and the "
           "station at the far end needs to hear you. Expect the ring to "
           "breathe by hundreds of kilometres through the day, and to close "
           "entirely at night on the high bands."),
    "regional": ("The signal goes up and comes back down over the whole area, "
                 "with no skip zone in the middle.",
                 "Only while the frequency stays below the critical frequency "
                 "- which is why NVIS is an 80 and 40 metre trick, and why it "
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


def qualify(span):
    """Attach the lab answer and the real-world answer, separately labelled."""
    lab, real = QUALIFIED.get(span.get("kind"), (None, None))
    if lab:
        span["lab"] = lab
        span["real"] = real
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


def targets(lat, lon, kind, heading, reach_info):
    """What to draw on the compass: whatever this antenna can actually work."""
    if reach_info["kind"] == "satellite":
        return []

    if reach_info["kind"] == "dx":
        # The well-known parts of the world stay - they are what an operator
        # points a beam at - but the compass now also carries the towns that
        # actually fall in the ring this antenna reaches. "Somewhere in
        # Europe" is a direction; Denver at 1,400 km is a contact.
        reach_info["world"] = dx_bearings(lat, lon, kind, heading)
        if not reach_info.get("outer_km"):
            return reach_info["world"]
        rows, source = nearby(lat, lon, reach_info["outer_km"],
                              inner_km=reach_info.get("inner_km") or 0.0,
                              spread=True)
        reach_info["places_from"] = source
    else:
        rows, source = nearby(lat, lon, reach_info["radius_km"])
        reach_info["places_from"] = source

    for row in rows:
        field = field_at(kind, row["bearing"], heading)
        row["field"] = round(field, 4)
        row["db"] = db(field)
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
        return abs(0.5 + 0.5 * math.cos(off)) ** 1.6
    # A wire radiates broadside: strongest across itself, nothing off the ends.
    off = math.radians((bearing - (heading + 90) + 180) % 360 - 180)
    return abs(math.cos(off))


def azimuth(kind, heading=0.0, points=361):
    """Relative field around the compass, as the antenna is actually laid."""
    return [{"bearing": n, "field": round(field_at(kind, n, heading), 5)}
            for n in range(points)]


def db(field):
    """Field as decibels against the pattern's own maximum."""
    if field <= 0.0005:
        return -60.0
    return round(20 * math.log10(field), 1)


def dx_bearings(lat, lon, kind=None, heading=0.0):
    """Where the well-known parts of the world are, and what the antenna does
    toward each of them."""
    from .terrain import great_circle
    out = []
    for name, tlat, tlon in DX_TARGETS:
        km, bearing = great_circle(lat, lon, tlat, tlon)
        row = {"name": name, "bearing": round(bearing), "km": round(km)}
        if kind:
            field = field_at(kind, bearing, heading)
            row["field"] = round(field, 4)
            row["db"] = db(field)
        out.append(row)
    return sorted(out, key=lambda r: r["bearing"])


def main_lobe(kind, height_wl, slope_deg=0.0):
    """The elevation angle the antenna actually favours."""
    best = max(elevation(kind, height_wl, slope_deg=slope_deg),
               key=lambda p: p["field"])
    return best["deg"]


def swr_curve(kind, f0_mhz, z0=50.0, span=0.30, points=121, q=None):
    """SWR against frequency, from the resonant-circuit approximation.

    Near resonance X ~ R*Q*(f/f0 - f0/f), which is the standard series-resonant
    form. It is an approximation and stops being one a long way off resonance,
    so the sweep is kept to +/-15% where it still means something.
    """
    spec = ANTENNA_Q.get(kind, ANTENNA_Q["dipole"])
    # `q` overrides the table so the conductor the element is made of can move
    # it: a fatter element is a lower-Q element, and that is the whole reason
    # anybody builds an antenna out of pipe.
    q, r = (spec["q"] if q is None else float(q)), spec["r"]
    out = []
    for n in range(points):
        f = f0_mhz * (1 - span / 2 + span * n / (points - 1))
        x = r * q * (f / f0_mhz - f0_mhz / f)
        num = complex(r - z0, x)
        den = complex(r + z0, x)
        g = abs(num / den)
        swr = (1 + g) / (1 - g) if g < 0.999999 else float("inf")
        out.append({"mhz": round(f, 4), "swr": round(min(swr, 20.0), 3)})
    return out


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

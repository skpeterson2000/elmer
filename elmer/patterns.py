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


def reach(kind, use, mhz, height_ft=0.0, nvis=False):
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
    return {"kind": "dx", "radius_km": None,
            "note": "Ionospheric propagation, so distance depends on the band "
                    "and the hour rather than on the antenna alone."}


def nearby(lat, lon, radius_km, limit=8):
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
        if km < 15 or km > radius_km:
            continue
        if any(great_circle(place["lat"], place["lon"],
                            other["lat"], other["lon"])[0] < 45 for other in kept):
            continue
        kept.append(dict(place, km=round(km), bearing=round(bearing)))

    kept.sort(key=lambda r: r["km"])
    found = [{"name": r["name"], "region": r.get("region") or "",
              "bearing": r["bearing"], "km": r["km"]} for r in kept[:limit]]
    return sorted(found, key=lambda r: r["bearing"]), source


def targets(lat, lon, kind, heading, reach_info):
    """What to draw on the compass: whatever this antenna can actually work."""
    if reach_info["kind"] == "dx":
        rows = dx_bearings(lat, lon, kind, heading)
    elif reach_info["kind"] == "satellite":
        rows = []
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


def swr_curve(kind, f0_mhz, z0=50.0, span=0.30, points=121):
    """SWR against frequency, from the resonant-circuit approximation.

    Near resonance X ~ R*Q*(f/f0 - f0/f), which is the standard series-resonant
    form. It is an approximation and stops being one a long way off resonance,
    so the sweep is kept to +/-15% where it still means something.
    """
    spec = ANTENNA_Q.get(kind, ANTENNA_Q["dipole"])
    q, r = spec["q"], spec["r"]
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


def usable_bandwidth(kind, f0_mhz, limit=2.0, z0=50.0):
    """The span where SWR stays under `limit`, in MHz and as a percentage."""
    curve = swr_curve(kind, f0_mhz, z0=z0, points=601)
    good = [p["mhz"] for p in curve if p["swr"] <= limit]
    if not good:
        return {"limit": limit, "low": None, "high": None, "khz": 0, "percent": 0.0}
    low, high = min(good), max(good)
    return {"limit": limit, "low": round(low, 4), "high": round(high, 4),
            "khz": round((high - low) * 1000), "percent": round(100 * (high - low) / f0_mhz, 2)}

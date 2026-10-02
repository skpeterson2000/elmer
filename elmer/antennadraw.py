"""Diagrams for the printed antenna sheet: the antenna as it goes up, and its patterns.

The Lab draws both on the screen, in the browser. The sheet is drawn here, in
reportlab, from the same numbers the sheet's tables print - the cut lengths
from antennapdf.dimensions and the antenna's own formulas, the patterns from
patterns.py, the module that draws the Lab's - so the picture cannot disagree
with the table beside it. Paper is monochrome-safe: black lines, grey for
what is not the antenna, and every number written on the drawing in words a
tape measure answers to.

`sketch` is the build drawing: to scale where scale says something (a V's
droop, a vertical's radials, a long wire's run), schematic where it would not
(a Yagi's boom is drawn as the elements in order, since no one figure
describes it). `patterns` is the two views the Lab gives - from above, and
from the side through the way it fires - as polar plots.
"""
import logging
import math

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.units import inch

from . import antenna_advice, patterns

log = logging.getLogger("elmer")

INK = colors.HexColor("#1a1a1a")
GREY = colors.HexColor("#8a8a8a")
LIGHT = colors.HexColor("#d9d9d9")
FEED = colors.HexColor("#1f5fa8")
LOBE = colors.HexColor("#c9e3c9")
C_FT = 983.571

WIRES = ("dipole", "bowtie", "efhw", "whipdipole")
VERTICALS = ("quarter", "fiveeighth", "jpole", "groundplane", "collinear", "whip", "screwdriver")


def _label(d, x, y, text, anchor="middle", size=8, color=INK):
    d.add(String(x, y, text, fontName="Helvetica", fontSize=size, fillColor=color, textAnchor=anchor))


def _ground(d, x0, x1, y):
    d.add(Line(x0, y, x1, y, strokeColor=GREY, strokeWidth=1))
    for x in range(int(x0), int(x1), 12):
        d.add(Line(x, y, x - 5, y - 5, strokeColor=LIGHT, strokeWidth=0.6))


def _wire(d, pts, width=2.0, color=INK):
    d.add(PolyLine([c for p in pts for c in p], strokeColor=color, strokeWidth=width))


def _feed(d, x, y):
    d.add(Circle(x, y, 3.2, fillColor=FEED, strokeColor=FEED))


def sketch(kind, mhz, height_ft, say, dims=None, width=7.1 * inch, height=2.3 * inch):
    """The antenna as it goes up, labelled. `say` turns feet into the words the
    sheet prints them in. None when there is nothing honest to draw."""
    try:
        return _sketch(str(kind), float(mhz), float(height_ft or 0.0), say, dims, width, height)
    except (ValueError, ZeroDivisionError, KeyError, TypeError) as exc:
        # A drawing is a help, not the sheet: without it the tables still stand.
        log.warning("no sketch for %s at %s MHz: %s", kind, mhz, exc)
        return None


def _sketch(kind, mhz, h_ft, say, dims, W, H):
    d = Drawing(W, H)
    gy = 22.0                      # the ground line
    top = H - 14.0
    lam = C_FT / mhz
    cx = W / 2.0
    leg = dims["leg_ft"] if dims else None
    whole = dims["overall_ft"] if dims else None

    def scale(run_ft, rise_ft, room_x=W - 140, room_y=top - gy - 18):
        return min(room_x / max(run_ft, 1e-6), room_y / max(rise_ft, 1e-6))

    if kind in WIRES:
        whole = whole or 468.0 / mhz
        hft = max(h_ft, 1.0)
        sc = scale(whole, hft)
        half = whole * sc / 2
        y = gy + hft * sc
        _ground(d, 20, W - 20, gy)
        for x in (cx - half, cx + half) if kind != "efhw" else (cx + half,):
            d.add(Line(x, gy, x, y + 6, strokeColor=GREY, strokeWidth=2.5))
        _wire(d, [(cx - half, y), (cx + half, y)])
        if kind == "efhw":
            d.add(Rect(cx - half - 7, y - 5, 10, 10, strokeColor=INK, fillColor=colors.white))
            _feed(d, cx - half - 2, y)
            _label(d, cx - half, y + 12, "49:1 at this end", "start")
            _label(d, cx, y - 14, f"{say(whole)} of wire")
        else:
            _feed(d, cx, y)
            _label(d, cx, y + 10, "fed here, center")
            _label(d, cx - half / 2, y - 14, f"{say(whole / 2)} each leg")
            _label(d, cx + half / 2, y - 14, f"{say(whole / 2)}")
            d.add(Line(cx, y, cx, gy, strokeColor=FEED, strokeWidth=0.8, strokeDashArray=[3, 2]))
        _label(d, cx + half + 6, (gy + y) / 2, f"{say(hft)} up", "start")
        _label(d, cx, 6, f"{say(whole)} end to end - drawn to scale", color=GREY)
        return d

    if kind == "invertedv":
        legs = (leg or antenna_advice.V_CUT / mhz / 2)
        droop = math.radians(antenna_advice.DEFAULT_DROOP_DEG)
        run, drop = legs * math.cos(droop), legs * math.sin(droop)
        apex = max(h_ft, drop + 1)
        sc = scale(2 * run, apex)
        y = gy + apex * sc
        _ground(d, 20, W - 20, gy)
        d.add(Line(cx, gy, cx, y + 4, strokeColor=GREY, strokeWidth=2.5))
        _wire(d, [(cx - run * sc, y - drop * sc), (cx, y), (cx + run * sc, y - drop * sc)])
        _feed(d, cx, y)
        _label(d, cx, y + 9, f"feed at the apex, {say(apex)} up")
        _label(d, cx + run * sc / 2 + 10, y - drop * sc / 2 + 4, f"{say(legs)} each leg", "start")
        _label(d, cx + run * sc + 6, y - drop * sc - 3, f"ends {say(apex - drop)} up", "start")
        _label(d, cx - run * sc / 2 - 10, y - drop * sc / 2 + 4, f"{antenna_advice.DEFAULT_DROOP_DEG:.0f}° droop", "end")
        _label(d, cx, 6, f"{say(2 * run)} end to end - drawn to scale", color=GREY)
        return d

    if kind == "loop":
        side = (whole or 1005.0 / mhz) / 4
        s = min(140.0, H - 50)
        x0, y0 = cx - s / 2, gy + 12
        d.add(Rect(x0, y0, s, s, strokeColor=INK, strokeWidth=2, fillColor=None))
        _feed(d, cx, y0)
        _label(d, cx, y0 - 10, "fed here")
        _label(d, x0 + s + 8, y0 + s / 2, f"{say(side)} a side, {say(4 * side)} round", "start")
        _label(d, cx, 6, f"seen from above, hung flat {say(h_ft)} up", color=GREY)
        return d

    if kind in VERTICALS:
        rad = whole or (234.0 / mhz)
        if kind == "fiveeighth":
            rad = 0.625 * lam * 0.95
        if kind == "jpole":
            rad = 0.75 * lam * 0.95
        if kind == "collinear":
            rad = (584.0 + 234.0) / mhz
        base = h_ft if kind in ("groundplane", "collinear") else 0.0
        radial = 246.0 / mhz
        total = base + rad
        sc = min((top - gy - 10) / max(total, 1e-6), (W / 2 - 80) / max(radial, 1e-6))
        yb = gy + base * sc
        _ground(d, 20, W - 20, gy)
        if base > 0:
            d.add(Line(cx, gy, cx, yb, strokeColor=GREY, strokeWidth=2.5))
        _wire(d, [(cx, yb), (cx, yb + rad * sc)])
        droop = 0.7 if kind == "groundplane" else 0.0
        for side in (-1, 1):
            rx = radial * sc * (0.7 if droop else 1.0)
            _wire(d, [(cx, yb), (cx + side * rx, yb - radial * sc * droop * (0.7 if base else 0))], 1.2, GREY)
        _feed(d, cx, yb)
        _label(d, cx + 8, yb + rad * sc / 2, f"{say(rad)} radiator", "start")
        if kind not in ("whip", "screwdriver"):
            _label(d, cx + radial * sc * 0.4, yb - 12 if base else gy + 8,
                   f"radials {say(radial)} each" + ("" if base else ", on or under the ground"), "start", color=GREY)
        if base:
            _label(d, cx - 8, yb / 2 + gy / 2, f"{say(base)} up", "end")
        _label(d, cx, 6, "drawn to scale", color=GREY)
        return d

    if kind in patterns.BEAMS or kind in ("phased2", "foursquare"):
        return _beam(d, kind, mhz, h_ft, say, cx, gy, W, H)

    if kind == "deltaloop":
        side = 1038.0 / mhz / 3
        base = max(h_ft, 4.0)
        tall = side * math.sqrt(3) / 2
        sc = scale(side, base + tall)
        yb = gy + base * sc
        _ground(d, 20, W - 20, gy)
        d.add(Line(cx, gy, cx, yb + tall * sc + 4, strokeColor=GREY, strokeWidth=2.5))
        pts = [(cx, yb + tall * sc), (cx - side * sc / 2, yb), (cx + side * sc / 2, yb)]
        d.add(Polygon([c for p in pts for c in p], strokeColor=INK, strokeWidth=2, fillColor=None))
        fx, fy = cx + side * sc / 4, yb + tall * sc / 2
        _feed(d, fx, fy)
        _label(d, fx + 8, fy, "fed a quarter of the way round", "start")
        _label(d, cx, yb - 12, f"{say(side)} each side, base {say(base)} up")
        _label(d, cx, 6, "seen face on: it fires toward you and away from you - drawn to scale", color=GREY)
        return d

    if patterns.is_travelling(kind):
        return _long_wire(d, kind, mhz, h_ft, say, cx, gy, W, H)
    return None


def _beam(d, kind, mhz, h_ft, say, cx, gy, W, H):
    """From above, firing up the page, with the published dimensions."""
    lam = C_FT / mhz
    y0 = gy + 12
    if kind == "moxon":
        A, B, C, Dd, E = 354 / mhz, 56 / mhz, 10 / mhz, 68.8 / mhz, 135.6 / mhz
        sc = min((W - 220) / A, (H - 50) / E)
        hw, yt, yr = A * sc / 2, y0 + E * sc, y0
        _wire(d, [(cx - hw, yt - B * sc), (cx - hw, yt), (cx + hw, yt), (cx + hw, yt - B * sc)])
        _wire(d, [(cx - hw, yr + Dd * sc), (cx - hw, yr), (cx + hw, yr), (cx + hw, yr + Dd * sc)], 2.0, GREY)
        _feed(d, cx, yt)
        _label(d, cx, yt + 6, f"A {say(A)} - driven element, fed here")
        _label(d, cx, yr - 11, "reflector")
        _label(d, cx + hw + 8, yt - B * sc / 2, f"B {say(B)}", "start")
        _label(d, cx + hw + 8, yr + Dd * sc / 2, f"D {say(Dd)}", "start")
        _label(d, cx + hw + 8, (yt - B * sc + yr + Dd * sc) / 2, f"C gap {say(C)}", "start")
        _label(d, cx - hw - 8, (yt + yr) / 2, f"E {say(E)}", "end")
    elif kind == "quad":
        side_d, side_r, gap = 987 / mhz / 4, 1040 / mhz / 4, 123 / mhz
        sc = min((W - 220) / side_r, (H - 60) / gap)
        for y, s, name, col in ((y0 + gap * sc, side_d, "driven loop", INK), (y0, side_r, "reflector loop", GREY)):
            _wire(d, [(cx - s * sc / 2, y), (cx + s * sc / 2, y)], 3.0, col)
            _label(d, cx + s * sc / 2 + 8, y - 3, f"{name}, {say(s)} a side", "start", color=col)
        _feed(d, cx, y0 + gap * sc)
        _label(d, cx - side_r * sc / 2 - 8, y0 + gap * sc / 2, f"{say(gap)} apart", "end")
        _label(d, cx, 6, "seen from above, each loop edge-on; fed at the bottom of the driven loop", color=GREY)
        return d
    elif kind == "hexbeam":
        r = (H - 50) / 2
        cy = gy + 12 + r
        pt = lambda i: (cx + r * math.cos(math.radians(90 - 60 * i)), cy + r * math.sin(math.radians(90 - 60 * i)))  # noqa: E731
        for i in range(6):
            d.add(Line(cx, cy, *pt(i), strokeColor=LIGHT, strokeWidth=1.5))
        _wire(d, [pt(5), pt(0), pt(1)])
        _wire(d, [pt(4), pt(3), pt(2)], 2.0, GREY)
        _feed(d, cx, cy)
        _label(d, cx + r + 10, cy, "a driven W and a reflector W per band; G3TXQ's dimensions", "start")
        _label(d, cx + r + 10, cy - 12, "for each band are in his published table", "start")
    elif kind in ("phased2", "foursquare"):
        sp = 246 / mhz
        s = min(110.0, H - 60)
        dots = ([(cx, gy + 12), (cx, gy + 12 + s)] if kind == "phased2" else
                [(cx - s / 2, gy + 12), (cx + s / 2, gy + 12), (cx - s / 2, gy + 12 + s), (cx + s / 2, gy + 12 + s)])
        for x, y in dots:
            d.add(Circle(x, y, 5, fillColor=INK, strokeColor=INK))
        _label(d, cx + (s / 2 if kind == "foursquare" else 0) + 14, gy + 12 + s / 2,
               f"{say(sp)} apart, each vertical {say(234 / mhz)}", "start")
        if kind == "phased2":
            _label(d, cx + 12, gy + 9, "rear, delayed 90°", "start", color=GREY)
            _label(d, cx + 12, gy + 9 + s, "front", "start")
        aim = " - switched to any of four diagonals" if kind == "foursquare" else ""
        _label(d, cx, 6, "seen from above; fires up the page" + aim, color=GREY)
        return d
    else:   # yagi: the elements in order, schematic
        names = ["reflector", "driven", "director"]
        lens = [0.495 * lam, 0.473 * lam, 0.44 * lam]
        sc = (W - 220) / lens[0]
        for i, (n, ln) in enumerate(zip(names, lens)):
            y = gy + 14 + i * 40
            _wire(d, [(cx - ln * sc / 2, y), (cx + ln * sc / 2, y)], 2.5 if n == "driven" else 2.0,
                  INK if n == "driven" else GREY)
            _label(d, cx + lens[0] * sc / 2 + 10, y - 3, f"{n} about {say(ln)}", "start")
        _feed(d, cx, gy + 54)
        d.add(Line(cx, gy + 8, cx, gy + 100, strokeColor=LIGHT, strokeWidth=3))
        _label(d, cx, 6, "a three-element Yagi in outline - build one to a published design", color=GREY)
        return d
    _label(d, cx, 6, f"seen from above, firing up the page, on a mast {say(h_ft)} up", color=GREY)
    return d


def _long_wire(d, kind, mhz, h_ft, say, cx, gy, W, H):
    """The long wires at the sizes the sheet works them out for."""
    spec = patterns.TRAVELLING.get(kind, {})
    length = spec.get("length_ft", 250.0)
    mast = h_ft or spec.get("height_ft", 40.0)
    lam = C_FT / mhz
    if kind in ("vbeam", "rhombic"):
        legwl = length / lam
        half = (patterns.vbeam_apex_deg(legwl) / 2 if kind == "vbeam" else patterns.rhombic_half_apex_deg(legwl))
        r = math.radians(half)
        depth = length * math.cos(r) * (1 if kind == "vbeam" else 2)
        across = 2 * length * math.sin(r)
        sc = min((W - 200) / depth, (H - 46) / across)
        x0, yc = cx - depth * sc / 2, gy + 10 + across * sc / 2
        if kind == "vbeam":
            _wire(d, [(x0 + depth * sc, yc + across * sc / 2), (x0, yc), (x0 + depth * sc, yc - across * sc / 2)])
            _label(d, x0 + depth * sc + 8, yc, f"apex {2 * half:.0f}° (ATP 6-02.53 Table E-3)", "start")
        else:
            xm = x0 + depth * sc / 2
            d.add(Polygon([x0, yc, xm, yc + across * sc / 2, x0 + depth * sc, yc, xm, yc - across * sc / 2],
                          strokeColor=INK, strokeWidth=2, fillColor=None))
            d.add(Rect(x0 + depth * sc - 4, yc - 4, 8, 8, strokeColor=INK, fillColor=colors.white))
            _label(d, x0 + depth * sc + 8, yc, "resistor", "start")
        _feed(d, x0, yc)
        _label(d, x0 - 6, yc, "fed here", "end")
        _label(d, cx, 6, f"seen from above, to scale: legs {say(length)}, {say(depth)} deep, {say(across)} across, "
                         f"{say(mast)} up", color=GREY)
        return d
    ends = patterns.TRAVELLING_END_FT
    legs = 2 if kind == "tefv" else 1
    legft = length / legs
    rise = min(mast - ends, legft * 0.999)
    run = math.sqrt(max(0.0, legft * legft - rise * rise)) * legs
    sc = min((W - 140) / run, (H - 50) / mast)
    x0 = cx - run * sc / 2
    _ground(d, 20, W - 20, gy)
    yp = gy + ends * sc
    if kind == "tefv":
        xm = cx
        d.add(Line(xm, gy, xm, gy + mast * sc, strokeColor=GREY, strokeWidth=2.5))
        _wire(d, [(x0, yp), (xm, gy + mast * sc), (x0 + run * sc, yp)])
        _feed(d, x0, yp)
    else:
        d.add(Line(x0, gy, x0, gy + mast * sc, strokeColor=GREY, strokeWidth=2.5))
        _wire(d, [(x0, gy + mast * sc), (x0 + run * sc, yp)])
        _feed(d, x0, gy + mast * sc)
    d.add(Rect(x0 + run * sc - 4, gy, 8, max(8, yp - gy), strokeColor=INK, fillColor=colors.white))
    _label(d, x0 + run * sc + 8, yp, "resistor to ground", "start")
    _label(d, cx, 6, f"to scale: {say(length)} of wire on a {say(mast)} support, firing toward the resistor",
           color=GREY)
    return d


# --- the patterns ---------------------------------------------------------

RING = colors.HexColor("#b5b5b5")


def _polar(d, ox, oy, r, points, title, half=False):
    """A polar plot: rings at quarter steps of the field, spokes every 30
    degrees, the lobe filled, and the angles written on - a nearly round
    pattern reads as a measurement, not a blob. `points` are (angle_deg,
    field) with 0 to the right."""
    spokes = range(0, 181, 30) if half else range(0, 360, 30)
    for a in spokes:
        d.add(Line(ox, oy, ox + r * math.cos(math.radians(a)), oy + r * math.sin(math.radians(a)),
                   strokeColor=RING, strokeWidth=0.5))
    for f in (0.25, 0.5, 0.75, 1.0):
        if half:
            steps = [(ox + r * f * math.cos(math.radians(a)), oy + r * f * math.sin(math.radians(a)))
                     for a in range(0, 181, 5)]
            d.add(PolyLine([c for p in steps for c in p], strokeColor=RING, strokeWidth=0.7 if f == 1 else 0.5))
        else:
            d.add(Circle(ox, oy, r * f, strokeColor=RING, strokeWidth=0.7 if f == 1 else 0.5, fillColor=None))
    if half:
        d.add(Line(ox - r - 6, oy, ox + r + 6, oy, strokeColor=GREY, strokeWidth=0.9))
    pts = []
    for ang, field in points:
        a = math.radians(ang)
        pts += [ox + r * field * math.cos(a), oy + r * field * math.sin(a)]
    if half:
        pts += [ox, oy]
    d.add(Polygon(pts, fillColor=LOBE, strokeColor=INK, strokeWidth=1.3))
    if half:
        for a, word in ((0, "0°"), (30, "30°"), (60, "60°"), (90, "90° up"),
                        (120, "60°"), (150, "30°"), (180, "0°")):
            x = ox + (r + 9) * math.cos(math.radians(a))
            y = oy + (r + 7) * math.sin(math.radians(a)) - 2
            _label(d, x, y, word, "start" if a < 90 else "end" if a > 90 else "middle", size=6.5, color=GREY)
        _label(d, ox + r, oy - 10, "the way it fires", "end", size=6.5, color=GREY)
        _label(d, ox - r, oy - 10, "behind it", "start", size=6.5, color=GREY)
        _label(d, ox, oy + r + 16, title, size=8)
    else:
        for b, word in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            a = math.radians(90 - b)
            _label(d, ox + (r + 8) * math.cos(a), oy + (r + 8) * math.sin(a) - 3, word, size=7, color=GREY)
        _label(d, ox, oy + r + 16, title, size=8)


def pattern_pair(kind, mhz, height_ft, width=7.1 * inch, height=2.5 * inch):
    """From above and from the side, as the Lab draws them, laid toward north."""
    try:
        return _pattern_pair(kind, float(mhz), float(height_ft or 0.0), width, height)
    except (ValueError, ZeroDivisionError, KeyError, TypeError) as exc:
        log.warning("no pattern plot for %s at %s MHz: %s", kind, mhz, exc)
        return None


def _pattern_pair(kind, mhz, h_ft, W, H):
    d = Drawing(W, H)
    lam = C_FT / mhz
    k = patterns.laid(kind, mhz=mhz, height_ft=h_ft or None)
    hwl = h_ft / lam
    side = patterns.elevation_slice(k, hwl, mhz=mhz, heading=0.0)
    peak = max(side, key=lambda p: p["field"] if p["deg"] <= 90 else -1)
    lobe = peak["deg"]
    plan = patterns.azimuth(k, 0.0, points=361, elev_deg=min(lobe, 89.0))
    top = max(p["field"] for p in plan) or 1.0
    r = min(H / 2 - 30, W / 4 - 40)
    # north up: bearing b is drawn at 90 - b degrees
    _polar(d, W * 0.25, H / 2 - 4, r,
           [(90 - p["bearing"], p["field"] / top) for p in plan],
           f"From above, at {lobe:.0f}° - north up, laid north")
    top2 = max(p["field"] for p in side) or 1.0
    # the side view: the way it fires on the right, overhead at the top
    _polar(d, W * 0.72, 26, min(r * 1.3, H - 62),
           [(p["deg"], p["field"] / top2) for p in side],
           f"From the side, {hwl:.2f} wavelengths up - strongest at {lobe:.0f}°", half=True)
    _label(d, W / 2, 4, "Worked out by the same model as the Lab's plots, over average ground.", size=7, color=GREY)
    return d


# --- where it lands, by day and by night ------------------------------------
#
# The same main lobe lands farther out at night: the F2 layer it turns back
# from is higher (patterns.F2_DAY_KM, F2_NIGHT_KM). A printed sheet does not
# know the hour it will be used at, so it shows both, on one scale so the
# difference is seen, not read. Each map is the ground round the station: the
# skip zone inside, the band where the lobe comes down, and the antenna's
# own pattern laid over it - darker where it is within 3 dB of its best,
# lighter to 6 dB. Whether the band is open at all is the hour's question,
# which the Lab and the Band Plan's reach map answer from the live sky.

DARK = colors.HexColor("#7fbf7f")


# The sky the sheet assumes, since it cannot know the hour: the model's own
# foF2 at a noon sun and at the dead of night (propagation.levels, the one
# place foF2 is made), at the station's latitude or a mid-latitude 40, on the
# solar flux the unit last read - from its cache only, so printing a sheet
# never reaches for the network - or a typical 100 when it has read none.
DAY_SUN_DEG, NIGHT_SUN_DEG, TYPICAL_SFI, MID_LAT = 50.0, -30.0, 100.0, 40.0


def typical_sky(mhz, lat=None):
    """{"day": ..., "night": ...}, each the MUF over a long hop, foF2, the
    layer's height, whether the band comes back at all, and the skip."""
    from . import propagation
    try:
        with propagation._cache_lock:
            held = propagation._cache.get("data") or {}
        sfi = float(held.get("sfi") or TYPICAL_SFI)
    except (TypeError, ValueError):
        sfi = TYPICAL_SFI
    out = {"sfi": round(sfi), "read": bool(held.get("sfi"))}
    for name, sun, layer in (("day", DAY_SUN_DEG, patterns.F2_DAY_KM), ("night", NIGHT_SUN_DEG, patterns.F2_NIGHT_KM)):
        muf, fof2 = propagation.levels(sfi, sun, lat if lat is not None else MID_LAT)
        skip = propagation.skip_km(float(mhz), fof2, layer)
        out[name] = {"muf": muf, "fof2": fof2, "layer_km": layer,
                     "open": float(mhz) <= muf and skip is not None,
                     "skip_km": skip or 0.0, "limit_km": propagation.one_hop_limit_km(layer)}
    return out


def footprint_pair(kind, mhz, height_ft, unit=None, lat=None, width=7.1 * inch, height=2.7 * inch):
    """The footprint by day and by night, or None when the antenna has no
    skywave ring (a VHF antenna, or nothing the geometry can say)."""
    try:
        return _footprint_pair(kind, float(mhz), float(height_ft or 0.0), unit, lat, width, height)
    except (ValueError, ZeroDivisionError, KeyError, TypeError) as exc:
        log.warning("no footprint for %s at %s MHz: %s", kind, mhz, exc)
        return None


def rings_for(kind, mhz, height_ft):
    """The day and night hops for this antenna at this height."""
    if float(mhz) >= 30.0:
        return None
    k = patterns.laid(kind, mhz=mhz, height_ft=height_ft or None)
    hwl = float(height_ft or 0.0) / (C_FT / float(mhz))
    day = patterns.hop_ring(k, hwl, day=True, mhz=mhz)
    night = patterns.hop_ring(k, hwl, day=False, mhz=mhz)
    return (k, day, night) if day and night else None


def _footprint_pair(kind, mhz, h_ft, unit, lat, W, H):
    from . import units
    got = rings_for(kind, mhz, h_ft)
    if not got:
        return None
    k, day, night = got
    sky = typical_sky(mhz, lat)
    d = Drawing(W, H)
    plan = patterns.azimuth(k, 0.0, points=361, elev_deg=min(day["takeoff_deg"], 89.0))
    top = max(p["field"] for p in plan) or 1.0
    field = {p["bearing"]: p["field"] / top for p in plan}
    # where it really lands: past the sky's own skip, and out to the lobe's
    # far edge - or, when the whole lobe falls inside the skip, the weaker
    # low edge of the pattern out to the longest hop

    def landing(ring, s):
        if not s["open"]:
            return None
        near = max(ring["near_km"], s["skip_km"])
        far = ring["far_km"] if ring["far_km"] > near else s["limit_km"]
        return {"near_km": near, "far_km": far, "lobe": ring["far_km"] > near,
                "typical_km": max(ring["typical_km"], near)}
    lands = {"day": landing(day, sky["day"]), "night": landing(night, sky["night"])}
    reach_km = max([v["far_km"] for v in lands.values() if v] + [night["far_km"], 1.0])
    r = min(H / 2 - 26, W / 4 - 34)
    # rings at round numbers in the operator's own unit, not round kilometers
    per = units.system(unit)["per_km"]
    step_u = next((s for s in (100, 250, 500, 1000, 2000, 4000) if reach_km * per / s <= 4), 4000)
    ring_km = [n * step_u / per for n in range(1, 9) if n * step_u / per <= reach_km * 1.02]
    for n, (when, title) in enumerate((("day", "By day"), ("night", "By night"))):
        ring = lands[when]
        ox, oy = W * (0.25 + 0.5 * n), H / 2 + 2
        sc = r / reach_km
        for km in ring_km:
            d.add(Circle(ox, oy, km * sc, strokeColor=RING, strokeWidth=0.5, fillColor=None))
            a = math.radians(-35)
            _label(d, ox + km * sc * math.cos(a) + 2, oy + km * sc * math.sin(a) - 2, units.say(km, unit),
                   "start", size=6, color=GREY)
        if ring is None:
            # Shut: the layer does not turn this band back at this hour.
            d.add(Circle(ox, oy, 3, fillColor=FEED, strokeColor=FEED))
            _label(d, ox, oy + r * 0.55, f"usually shut: {mhz:g} MHz is above", size=8)
            _label(d, ox, oy + r * 0.55 - 11, f"the {sky[when]['muf']:.1f} MHz the layer turns back", size=8)
            _label(d, ox, oy + r + 16, f"{title}: nothing comes back on this band", size=8)
            continue
        # the landing band, sector by sector, shaded by the antenna's own pattern
        for b in range(0, 360, 3):
            f = min(field.get(b, 0.0), field.get((b + 3) % 360, 0.0))
            if f < 0.5:
                continue
            a0, a1 = math.radians(90 - b), math.radians(90 - b - 3)
            inner, outer = ring["near_km"] * sc, ring["far_km"] * sc
            pts = [ox + inner * math.cos(a0), oy + inner * math.sin(a0),
                   ox + outer * math.cos(a0), oy + outer * math.sin(a0),
                   ox + outer * math.cos(a1), oy + outer * math.sin(a1),
                   ox + inner * math.cos(a1), oy + inner * math.sin(a1)]
            fill = DARK if f >= 0.7071 and ring["lobe"] else LOBE
            d.add(Polygon(pts, fillColor=fill, strokeColor=fill, strokeWidth=0.3))
        if ring["near_km"] > 0:
            d.add(Circle(ox, oy, ring["near_km"] * sc, strokeColor=INK, strokeWidth=0.8,
                         strokeDashArray=[3, 2], fillColor=None))
        d.add(Circle(ox, oy, 3, fillColor=FEED, strokeColor=FEED))
        for b, word in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            a = math.radians(90 - b)
            _label(d, ox + (r + 8) * math.cos(a), oy + (r + 8) * math.sin(a) - 3, word, size=7, color=GREY)
        near = units.say(ring["near_km"], unit) if ring["near_km"] else "the station"
        _label(d, ox, oy + r + 16,
               f"{title}: lands {near} to {units.say(ring['far_km'], unit)}"
               + (f", mostly near {units.say(ring['typical_km'], unit)}" if ring["lobe"]
                  else " - the lobe's low edge"), size=8)
    flux = f"solar flux {sky['sfi']}" + ("" if sky["read"] else ", a typical figure")
    where = "at your latitude" if lat is not None else "at a mid-latitude"
    _label(d, W / 2, 4, f"A typical noon and midnight sky ({flux}, {where}): one hop off the F2 layer; "
                        f"laid north. Dashed: the skip zone's edge. Pale: weaker than the main lobe.",
           size=7, color=GREY)
    return d

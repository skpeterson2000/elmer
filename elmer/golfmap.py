"""The hole, drawn: a yardage-book strip from the card the game plays.

Not a map of the real course - that is the club's, and the game does not
have the routing anyway. This is the hole as the rules see it, which is
the honest picture: the tee at the foot, the green at the head, every
hazard as a band at the yards it covers and on the side it sits, the wind
as an arrow, and the balls where they lie. What it draws is exactly what
the ball obeys, so a golfer reading it is reading the game.

SVG, in the page's own colours, drawn small enough for a phone and clear
enough for the table.
"""
from xml.sax.saxutils import escape

W, H = 260, 560                 # the strip
PAD_TOP, PAD_BOT = 58, 46       # room for the green's cup and the tee's box
FAIR_L, FAIR_R = 95, 165        # the fairway's edges
CENTRE = (FAIR_L + FAIR_R) / 2
# Across the hole: the fairway's half-width in the rules (golf.FAIRWAY_HALF,
# 18 yards) is the fairway's half-width here, so a ball's yards off the
# line and a mark's are the same yards on the strip.
PX_PER_YARD = (FAIR_R - FAIR_L) / 2 / 18.0


def geometry(h):
    """What a screen needs to turn a tap on the strip into yards: the
    box, the paddings, the centre line and the scale."""
    return {"w": W, "h": H, "pad_top": PAD_TOP, "pad_bot": PAD_BOT, "centre": CENTRE,
            "px_per_yard": PX_PER_YARD, "yards": h["yards"], "bend": bend_of(h)}


# A dog-leg: past the bend the line of play swings left or right. The
# strip is a yardage book's, schematic, so the swing is drawn at a third
# of its angle and never runs off the page; the rules do not bend - a
# ball is yards along the line and off it wherever the line goes.
BEND_SCALE = 0.35
BEND_MOST = 62.0


def bend_of(h):
    """The hole's bend as (yards, direction, lateral px per yard along), or
    None. Direction +1 is right."""
    b = (h or {}).get("bend") or {}
    try:
        at, deg = float(b.get("at") or 0), float(b.get("degrees") or 0)
    except (TypeError, ValueError):
        return None
    if not at or not deg or b.get("turn") not in ("left", "right"):
        return None
    import math
    k = math.tan(math.radians(min(75.0, deg))) * BEND_SCALE * PX_PER_YARD
    return {"at": at, "dir": 1 if b["turn"] == "right" else -1, "k": k, "most": BEND_MOST}


def centre_x(at, bend=None):
    """Where the line of play is, across the strip, at these yards."""
    if not bend or at <= bend["at"]:
        return CENTRE
    return CENTRE + bend["dir"] * min(bend["most"], (float(at) - bend["at"]) * bend["k"])


def _x(off, at=None, bend=None):
    """Yards off the line, as a place across the strip - the line itself
    where the hole's bend puts it at these yards."""
    return centre_x(at if at is not None else 0, bend) + float(off or 0) * PX_PER_YARD
SIDE = {"left": (FAIR_L - 34, FAIR_L - 4), "right": (FAIR_R + 4, FAIR_R + 34),
        "across": (FAIR_L, FAIR_R), "front": (FAIR_L, FAIR_R),
        "centre": (FAIR_L + 10, FAIR_R - 10), "around": (FAIR_L - 30, FAIR_R + 30),
        "beyond": (FAIR_L - 10, FAIR_R + 10), "": (FAIR_L, FAIR_R)}
FILL = {"water": "#2f6f9f", "bunker": "#d9c48a", "rough": "#4c6b2f"}
WIND_ARROW = {"with": "↑", "into": "↓", "across": "→", "swirling": "↻"}
LIE_MARK = {"tee": "#e8e8e8", "fairway": "#e8e8e8", "rough": "#c9d13a", "sand": "#d9c48a",
            "green": "#8fe39a", "water": "#7fbfff"}


def _y(yards, total):
    """Yards from the tee, as a height up the strip."""
    usable = H - PAD_TOP - PAD_BOT
    frac = max(0.0, min(1.0, float(yards) / float(total or 1)))
    return H - PAD_BOT - frac * usable


def hole_svg(h, wind=None, wind_mph=None, balls=None, course_name=None, mark=None, aimed=None):
    """One hole as an SVG string. `h` is the card's hole; `balls` a list of
    {name, at, off, lie, holed, picked_up, you}; `mark` the golfer's aim,
    {at, off}, drawn as a cross; `aimed` where the last stroke was aimed,
    drawn fainter beside where the ball went - a shot bounces, rolls, or
    falls off a cliff, and the mark says what was meant."""
    total = float(h["yards"])
    bend = bend_of(h)
    half_yd = float(h.get("width") or 18)
    half_px = half_yd * PX_PER_YARD
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'class="holemap" role="img" aria-label="the {h["n"]} hole, par {h["par"]}, {h["yards"]} yards">']
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="#16221a"/>')
    # the fairway, tee to green, with rough either side - a line of play that
    # bends where the card says, the hole's own width
    top, bot = _y(total, total), _y(0, total)
    line = [(centre_x(0, bend), bot)]
    if bend and 0 < bend["at"] < total:
        line.append((centre_x(bend["at"], bend), _y(bend["at"], total)))
    line.append((centre_x(total, bend), top))
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in line)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#2a4a24" stroke-width="{half_px * 2 + 80:.1f}" '
                 f'stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#4a8a3a" stroke-width="{half_px * 2:.1f}" '
                 f'stroke-linecap="round" stroke-linejoin="round"/>')
    # the hazards, as bands at their yards and on their side, following the line
    for hz in h.get("hazards", []):
        x0, x1 = SIDE.get(hz.get("side", ""), SIDE[""])
        mid = (hz["from"] + hz["to"]) / 2.0
        shift = centre_x(mid, bend) - CENTRE
        # the sides sit just beyond this hole's own width
        if hz.get("side") == "left":
            x0, x1 = CENTRE - half_px - 34, CENTRE - half_px - 4
        elif hz.get("side") == "right":
            x0, x1 = CENTRE + half_px + 4, CENTRE + half_px + 34
        elif hz.get("side") in ("across", "front", ""):
            x0, x1 = CENTRE - half_px, CENTRE + half_px
        y1, y0 = _y(hz["from"], total), _y(hz["to"], total)
        fill = FILL.get(hz["kind"], "#666")
        parts.append(f'<rect x="{x0 + shift:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{max(6.0, y1 - y0):.1f}" '
                     f'rx="8" fill="{fill}" opacity="0.92"><title>{escape(hz.get("name") or hz["kind"])}, '
                     f'{hz["from"]}-{hz["to"]} yards</title></rect>')
    # the green, and the cup, where the line ends
    depth = float(h.get("green") or 28)
    gy = _y(total, total)
    gx = centre_x(total, bend)
    gh = max(18.0, (depth / total) * (H - PAD_TOP - PAD_BOT))
    parts.append(f'<ellipse cx="{gx:.1f}" cy="{gy:.1f}" rx="46" ry="{gh / 2 + 6:.1f}" fill="#8fe39a"/>')
    parts.append(f'<circle cx="{gx:.1f}" cy="{gy:.1f}" r="3.2" fill="#16221a"/>')
    parts.append(f'<line x1="{gx:.1f}" y1="{gy:.1f}" x2="{gx:.1f}" y2="{gy - 22:.1f}" '
                 f'stroke="#e8e8e8" stroke-width="1.5"/>')
    parts.append(f'<polygon points="{gx:.1f},{gy - 22:.1f} {gx + 12:.1f},{gy - 17:.1f} '
                 f'{gx:.1f},{gy - 12:.1f}" fill="#e05a5a"/>')
    # the tee box
    parts.append(f'<rect x="{(FAIR_L + FAIR_R) / 2 - 16}" y="{bot - 6:.1f}" width="32" height="12" rx="3" '
                 f'fill="#c9e2c0" stroke="#16221a"/>')
    # yard marks every 100
    y100 = 100
    while y100 < total:
        yy = _y(y100, total)
        parts.append(f'<line x1="{FAIR_R + 40}" y1="{yy:.1f}" x2="{FAIR_R + 48}" y2="{yy:.1f}" stroke="#8b98a5"/>')
        parts.append(f'<text x="{FAIR_R + 52}" y="{yy + 4:.1f}" font-size="11" fill="#8b98a5" '
                     f'font-family="ui-monospace, monospace">{y100}</text>')
        y100 += 100
    # the head: hole, par, yards, wind
    head = f'{h["n"]} · par {h["par"]} · {h["yards"]} yd'
    parts.append(f'<text x="14" y="26" font-size="17" font-weight="700" fill="#f3f3f3" '
                 f'font-family="system-ui, sans-serif">{escape(head)}</text>')
    if h.get("name"):
        parts.append(f'<text x="14" y="44" font-size="12" fill="#c9d1d9" font-family="system-ui, sans-serif">'
                     f'{escape(h["name"])}</text>')
    if wind:
        arrow = WIND_ARROW.get(wind, "")
        wtxt = f'{arrow} {wind}' + (f' {wind_mph} mph' if wind_mph is not None else '')
        parts.append(f'<text x="{W - 14}" y="26" text-anchor="end" font-size="13" fill="#9ad1ff" '
                     f'font-family="system-ui, sans-serif">{escape(wtxt)}</text>')
    # where the last stroke was aimed, faint, so the result can be read against it
    if aimed and aimed.get("at") is not None:
        ax, ay = _x(aimed.get("off"), float(aimed["at"]), bend), _y(min(float(aimed["at"]), total + 20), total)
        parts.append(f'<g class="aimed" stroke="#ffb454" stroke-width="1.5" fill="none" opacity="0.55" stroke-dasharray="3 2">'
                     f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="8"/>'
                     f'<line x1="{ax - 12:.1f}" y1="{ay:.1f}" x2="{ax + 12:.1f}" y2="{ay:.1f}"/>'
                     f'<line x1="{ax:.1f}" y1="{ay - 12:.1f}" x2="{ax:.1f}" y2="{ay + 12:.1f}"/>'
                     f'<title>aimed here</title></g>')
    # the mark: where the golfer means the ball to land
    if mark and mark.get("at") is not None:
        mx, my = _x(mark.get("off"), float(mark["at"]), bend), _y(min(float(mark["at"]), total + 20), total)
        parts.append(f'<g class="mark" stroke="#ffb454" stroke-width="2" fill="none">'
                     f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="9"/>'
                     f'<line x1="{mx - 14:.1f}" y1="{my:.1f}" x2="{mx + 14:.1f}" y2="{my:.1f}"/>'
                     f'<line x1="{mx:.1f}" y1="{my - 14:.1f}" x2="{mx:.1f}" y2="{my + 14:.1f}"/>'
                     f'<title>aiming {int(mark["at"])} yards{", " + str(abs(int(mark.get("off") or 0))) + " " + ("left" if (mark.get("off") or 0) < 0 else "right") if mark.get("off") else ""}</title></g>')
    # the balls, where they lie - the one that is you ringed, the holed at the cup
    on_the_tee = [b for b in (balls or []) if not b.get("holed") and float(b.get("at") or 0) == 0]
    for i, b in enumerate(balls or []):
        at = total if b.get("holed") else min(float(b.get("at") or 0), total)
        yy = _y(at, total)
        # across the hole where the ball sits; on the tee, side by side so a
        # foursome is four dots, not one
        if at == 0 and b in on_the_tee:
            xx = CENTRE + (on_the_tee.index(b) - (len(on_the_tee) - 1) / 2) * 14
        else:
            xx = _x(b.get("off"), at, bend)
        color = LIE_MARK.get(b.get("lie") or "fairway", "#e8e8e8")
        if b.get("picked_up"):
            color = "#8b98a5"
        parts.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="{7 if b.get("you") else 5.5}" fill="{color}" '
                     f'stroke="{"#ffb454" if b.get("you") else "#16221a"}" stroke-width="{2.5 if b.get("you") else 1}">'
                     f'<title>{escape(str(b.get("name") or ""))}</title></circle>')
    parts.append("</svg>")
    return "".join(parts)


# ------------------------------------------------------------- the green
# On the green the strip is the green: the whole of it, the cup at its
# centre, every ball on it at its feet from the cup, the way it falls as an
# arrow, and the golfer's mark. The wind is not on it - on the green the
# wind stops mattering and the slope starts.
GW, GH = 260, 300
GREEN_HALF_FT = 14 * 3          # golf.GREEN_HALF, in feet


def green_geometry(h):
    """What a screen needs to turn a tap on the green into feet from the
    cup, and then into the yards the mark is kept in."""
    depth_ft = float(h.get("green") or 28) * 3
    px_per_ft = min((GW / 2 - 20) / GREEN_HALF_FT, (GH / 2 - 30) / (depth_ft / 2))
    return {"view": "green", "w": GW, "h": GH, "cx": GW / 2, "cy": GH / 2, "px_per_ft": px_per_ft,
            "yards": h["yards"], "depth_ft": depth_ft}


def green_svg(h, balls=None, mark=None, aimed=None, slope=None):
    """The green as an SVG string: `balls` those on it, with `feet_along`
    (short negative) and `feet_across` (left negative); `mark` and
    `aimed` in the same feet; `slope` {"falls", "grade"}."""
    geo = green_geometry(h)
    cx, cy, k = geo["cx"], geo["cy"], geo["px_per_ft"]
    ry, rx = geo["depth_ft"] / 2 * k, GREEN_HALF_FT * k

    def at(fa, fx):
        return cx + float(fx or 0) * k, cy - float(fa or 0) * k

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GW} {GH}" class="holemap greenmap" role="img" '
             f'aria-label="the {h["n"]} green">',
             f'<rect x="0" y="0" width="{GW}" height="{GH}" rx="14" fill="#16221a"/>',
             f'<ellipse cx="{cx}" cy="{cy}" rx="{rx + 10:.1f}" ry="{ry + 10:.1f}" fill="#2a4a24"/>',
             f'<ellipse cx="{cx}" cy="{cy}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#8fe39a"/>']
    # feet rings, every ten
    for ft in (10, 20, 30):
        if ft * k < max(rx, ry):
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{ft * k:.1f}" fill="none" stroke="#5fb36c" stroke-width="0.8" '
                         f'stroke-dasharray="3 3"/>')
            parts.append(f'<text x="{cx + ft * k + 3:.1f}" y="{cy - 3}" font-size="9" fill="#2a4a24" '
                         f'font-family="ui-monospace, monospace">{ft}</text>')
    # the slope, as an arrow the way the green falls
    s = slope or {}
    if s.get("grade", 0) > 0:
        dirs = {"front": (0, 1), "back": (0, -1), "left": (-1, 0), "right": (1, 0)}
        dx, dy = dirs.get(s.get("falls"), (0, 1))
        ax, ay = cx + dx * 22, cy + dy * 22
        bx, by = cx + dx * 62, cy + dy * 62
        parts.append(f'<g class="slope" stroke="#1d3a22" stroke-width="2" fill="#1d3a22" opacity="0.7">'
                     f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}"/>'
                     f'<polygon points="{bx + dx * 8:.1f},{by + dy * 8:.1f} {bx - dy * 5:.1f},{by + dx * 5:.1f} {bx + dy * 5:.1f},{by - dx * 5:.1f}"/>'
                     f'<title>falls to the {escape(str(s.get("falls")))}, {s.get("grade")}%</title></g>')
        parts.append(f'<text x="14" y="{GH - 12}" font-size="11" fill="#c9d1d9" font-family="system-ui, sans-serif">'
                     f'falls {escape(str(s.get("falls")))} · {s.get("grade"):g}%</text>')
    # the cup
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#16221a"/>')
    parts.append(f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - 24}" stroke="#e8e8e8" stroke-width="1.5"/>')
    parts.append(f'<polygon points="{cx},{cy - 24} {cx + 12},{cy - 19} {cx},{cy - 14}" fill="#e05a5a"/>')
    # where the last putt was aimed, faint; the mark, bright
    if aimed and aimed.get("feet_along") is not None:
        x, y = at(aimed["feet_along"], aimed["feet_across"])
        parts.append(f'<g class="aimed" stroke="#ffb454" stroke-width="1.5" fill="none" opacity="0.55" stroke-dasharray="3 2">'
                     f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8"/><line x1="{x - 12:.1f}" y1="{y:.1f}" x2="{x + 12:.1f}" y2="{y:.1f}"/>'
                     f'<line x1="{x:.1f}" y1="{y - 12:.1f}" x2="{x:.1f}" y2="{y + 12:.1f}"/><title>aimed here</title></g>')
    if mark and mark.get("feet_along") is not None:
        x, y = at(mark["feet_along"], mark["feet_across"])
        parts.append(f'<g class="mark" stroke="#ffb454" stroke-width="2" fill="none">'
                     f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9"/><line x1="{x - 14:.1f}" y1="{y:.1f}" x2="{x + 14:.1f}" y2="{y:.1f}"/>'
                     f'<line x1="{x:.1f}" y1="{y - 14:.1f}" x2="{x:.1f}" y2="{y + 14:.1f}"/><title>your mark</title></g>')
    # the balls on the green
    for b in balls or []:
        if b.get("holed"):
            continue
        x, y = at(b.get("feet_along"), b.get("feet_across"))
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{7 if b.get("you") else 5.5}" fill="#ffffff" '
                     f'stroke="{"#ffb454" if b.get("you") else "#16221a"}" stroke-width="{2.5 if b.get("you") else 1}">'
                     f'<title>{escape(str(b.get("name") or ""))}, {b.get("feet", "?")} feet</title></circle>')
    head = f'{h["n"]} · the green · par {h["par"]}'
    parts.append(f'<text x="14" y="22" font-size="15" font-weight="700" fill="#f3f3f3" font-family="system-ui, sans-serif">'
                 f'{escape(head)}</text>')
    parts.append("</svg>")
    return "".join(parts)

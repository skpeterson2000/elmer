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
            "px_per_yard": PX_PER_YARD, "yards": h["yards"]}


def _x(off):
    """Yards off the line, as a place across the strip."""
    return CENTRE + float(off or 0) * PX_PER_YARD
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


def hole_svg(h, wind=None, wind_mph=None, balls=None, course_name=None, mark=None):
    """One hole as an SVG string. `h` is the card's hole; `balls` a list of
    {name, at, off, lie, holed, picked_up, you}; `mark` the golfer's aim,
    {at, off}, drawn as a cross."""
    total = float(h["yards"])
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'class="holemap" role="img" aria-label="the {h["n"]} hole, par {h["par"]}, {h["yards"]} yards">']
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="#16221a"/>')
    # the fairway, tee to green, with rough either side
    top, bot = _y(total, total), _y(0, total)
    parts.append(f'<rect x="{FAIR_L - 40}" y="{top - 30}" width="{FAIR_R - FAIR_L + 80}" '
                 f'height="{bot - top + 60}" rx="30" fill="#2a4a24"/>')
    parts.append(f'<rect x="{FAIR_L}" y="{top}" width="{FAIR_R - FAIR_L}" height="{bot - top}" '
                 f'rx="22" fill="#4a8a3a"/>')
    # the hazards, as bands at their yards and on their side
    for hz in h.get("hazards", []):
        x0, x1 = SIDE.get(hz.get("side", ""), SIDE[""])
        y1, y0 = _y(hz["from"], total), _y(hz["to"], total)
        fill = FILL.get(hz["kind"], "#666")
        parts.append(f'<rect x="{x0}" y="{y0:.1f}" width="{x1 - x0}" height="{max(6.0, y1 - y0):.1f}" '
                     f'rx="8" fill="{fill}" opacity="0.92"><title>{escape(hz.get("name") or hz["kind"])}, '
                     f'{hz["from"]}-{hz["to"]} yards</title></rect>')
    # the green, and the cup
    depth = float(h.get("green") or 28)
    gy = _y(total, total)
    gh = max(18.0, (depth / total) * (H - PAD_TOP - PAD_BOT))
    parts.append(f'<ellipse cx="{(FAIR_L + FAIR_R) / 2}" cy="{gy:.1f}" rx="46" ry="{gh / 2 + 6:.1f}" fill="#8fe39a"/>')
    parts.append(f'<circle cx="{(FAIR_L + FAIR_R) / 2}" cy="{gy:.1f}" r="3.2" fill="#16221a"/>')
    parts.append(f'<line x1="{(FAIR_L + FAIR_R) / 2}" y1="{gy:.1f}" x2="{(FAIR_L + FAIR_R) / 2}" y2="{gy - 22:.1f}" '
                 f'stroke="#e8e8e8" stroke-width="1.5"/>')
    parts.append(f'<polygon points="{(FAIR_L + FAIR_R) / 2},{gy - 22:.1f} {(FAIR_L + FAIR_R) / 2 + 12},{gy - 17:.1f} '
                 f'{(FAIR_L + FAIR_R) / 2},{gy - 12:.1f}" fill="#e05a5a"/>')
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
    # the mark: where the golfer means the ball to land
    if mark and mark.get("at") is not None:
        mx, my = _x(mark.get("off")), _y(min(float(mark["at"]), total + 20), total)
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
            xx = _x(b.get("off"))
        color = LIE_MARK.get(b.get("lie") or "fairway", "#e8e8e8")
        if b.get("picked_up"):
            color = "#8b98a5"
        parts.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="{7 if b.get("you") else 5.5}" fill="{color}" '
                     f'stroke="{"#ffb454" if b.get("you") else "#16221a"}" stroke-width="{2.5 if b.get("you") else 1}">'
                     f'<title>{escape(str(b.get("name") or ""))}</title></circle>')
    parts.append("</svg>")
    return "".join(parts)

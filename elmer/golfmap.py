"""The hole, drawn: a yardage-book strip from the card the game plays.

Not a map of the real course - that is the club's, and the game does not
have the routing anyway. This is the hole as the rules see it, which is
the honest picture: the tee at the foot, the green at the head, every
hazard as a band at the yards it covers and on the side it sits, the wind
as an arrow, and the balls where they lie. What it draws is what the ball
obeys, so a golfer reading it is reading the game - drawn as grass rather
than geometry: the outlines are softened by a yard or two, never more, and
always outward for what helps (the drawn green is never smaller than the
rules' green, the fairway never narrower) and inward for what hurts (a
bunker is drawn inside its band, never beyond it). The shapes come from
the card's numbers seeded by the hole, so a hole looks the same every
round and no two holes look alike.

SVG, in the page's own colours, drawn small enough for a phone and clear
enough for the table.
"""
import math
import random
import zlib
from xml.sax.saxutils import escape

W, H = 260, 560                 # the strip
PAD_TOP, PAD_BOT = 58, 46       # room for the green's cup and the tee's box
FAIR_L, FAIR_R = 95, 165        # the fairway's edges
CENTRE = (FAIR_L + FAIR_R) / 2
# Across the hole: the fairway's half-width in the rules (golf.FAIRWAY_HALF,
# 18 yards) is the fairway's half-width here, so a ball's yards off the
# line and a mark's are the same yards on the strip.
PX_PER_YARD = (FAIR_R - FAIR_L) / 2 / 18.0


class Plan:
    """The hole in plan: the same yard both ways, the dogleg at its true
    angle, turned so the tee is at the foot and the green at the head,
    and fitted to the strip. The rules do not bend - a ball is yards along
    the line of play and off it wherever the line goes - and this is the
    map from those yards to the page and back.

    The line is a polyline in yards: the tee at the origin, the first leg
    straight up, the second leg turned by the card's degrees at the
    card's yards. It is rotated so the tee-to-green line stands vertical
    and scaled to fit, no more than PX_MOST a yard so a par 3 does not
    fill the strip with one green.
    """
    PX_MOST = 2.4
    MARGIN = 52                  # yards either side of the line kept in view: the rough and the sand

    def __init__(self, h):
        self.total = float(h["yards"])
        b = (h or {}).get("bend") or {}
        try:
            at, deg = float(b.get("at") or 0), float(b.get("degrees") or 0)
        except (TypeError, ValueError):
            at, deg = 0.0, 0.0
        if at <= 0 or at >= self.total or deg <= 0 or b.get("turn") not in ("left", "right"):
            at, deg = self.total, 0.0
        sign = 1 if b.get("turn") == "right" else -1
        # the legs in yards, x right and y up, before rotation
        self.legs = []                   # (at0, x0, y0, heading) - heading in radians from up, clockwise
        pts = [(0.0, 0.0)]
        head = 0.0
        self.legs.append((0.0, 0.0, 0.0, head, at))
        x1, y1 = 0.0, at
        if deg:
            head = sign * math.radians(min(80.0, deg))
            self.legs.append((at, x1, y1, head, self.total - at))
            x2, y2 = x1 + math.sin(head) * (self.total - at), y1 + math.cos(head) * (self.total - at)
        else:
            x2, y2 = x1, y1
        # rotate so the tee-to-green line stands up
        self.rot = math.atan2(x2, y2)
        self.scale = 1.0
        self.ox, self.oy = 0.0, 0.0
        xs, ys = [], []
        for at_, x, y, hd, ln in self.legs:
            for f in (0.0, 1.0):
                for off in (-self.MARGIN, self.MARGIN):
                    px, py = self._rotate(x + math.sin(hd) * ln * f + math.cos(hd) * off, y + math.cos(hd) * ln * f - math.sin(hd) * off)
                    xs.append(px); ys.append(py)
        span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
        self.scale = min(self.PX_MOST, (H - PAD_TOP - PAD_BOT) / max(span_y, 1.0), (W - 8) / max(span_x, 1.0))
        # centre it, both ways, in the room the paddings leave
        self.ox = W / 2 - (min(xs) + max(xs)) / 2 * self.scale
        self.oy = (PAD_TOP + (H - PAD_BOT)) / 2 + (min(ys) + max(ys)) / 2 * self.scale

    def _rotate(self, x, y):
        c, s_ = math.cos(-self.rot), math.sin(-self.rot)
        return x * c - y * s_, x * s_ + y * c

    def heading(self, at):
        """The line's heading at these yards, in radians clockwise from up, on the page."""
        leg = self.legs[-1] if at >= self.legs[-1][0] else self.legs[0]
        return leg[3] - self.rot

    def at(self, at, off=0.0):
        """Yards along the line and off it (right positive), as a point on
        the page. At the turn itself the offset is mitred - along the
        bisector of the two legs - so a band's edge turns the corner
        without folding over itself."""
        at = float(at)
        off = float(off or 0)
        if len(self.legs) > 1 and abs(at - self.legs[1][0]) < 0.5:
            h1, h2 = self.legs[0][3], self.legs[1][3]
            bis = (h1 + h2) / 2
            stretch = 1.0 / max(0.35, math.cos((h2 - h1) / 2))
            x0, y0 = self.legs[1][1], self.legs[1][2]
            x, y = x0 + math.cos(bis) * off * stretch, y0 - math.sin(bis) * off * stretch
        else:
            leg = self.legs[-1] if at >= self.legs[-1][0] else self.legs[0]
            at0, x0, y0, hd, _ln = leg
            d = at - at0
            x, y = x0 + math.sin(hd) * d + math.cos(hd) * off, y0 + math.cos(hd) * d - math.sin(hd) * off
        rx, ry = self._rotate(x, y)
        return self.ox + rx * self.scale, self.oy - ry * self.scale

    def legs_px(self):
        """The line as the page sees it, for a tap to be turned back into yards."""
        out = []
        for at0, x0, y0, hd, ln in self.legs:
            x1, y1 = self.at(at0)
            x2, y2 = self.at(at0 + ln)
            out.append({"at0": at0, "x1": round(x1, 1), "y1": round(y1, 1), "x2": round(x2, 1), "y2": round(y2, 1), "yards": ln})
        return out


def geometry(h):
    """What a screen needs to turn a tap on the plan into yards: the
    line's legs on the page and the scale. A tap is projected onto the
    nearest leg; its distance along that leg is yards along the hole,
    its distance across is yards off the line."""
    plan = Plan(h)
    return {"view": "plan", "w": W, "h": H, "px_per_yard": round(plan.scale, 4), "yards": h["yards"],
            "legs": plan.legs_px(), "bend": bend_of(h)}


def bend_of(h):
    """The hole's bend as the card has it, or None: kept for the screens
    that ask whether there is one."""
    b = (h or {}).get("bend") or {}
    try:
        at, deg = float(b.get("at") or 0), float(b.get("degrees") or 0)
    except (TypeError, ValueError):
        return None
    if not at or not deg or b.get("turn") not in ("left", "right"):
        return None
    return {"at": at, "dir": 1 if b["turn"] == "right" else -1, "degrees": deg}


SIDE = {"left": (FAIR_L - 34, FAIR_L - 4), "right": (FAIR_R + 4, FAIR_R + 34),
        "across": (FAIR_L, FAIR_R), "front": (FAIR_L, FAIR_R),
        "centre": (FAIR_L + 10, FAIR_R - 10), "around": (FAIR_L - 30, FAIR_R + 30),
        "beyond": (FAIR_L - 10, FAIR_R + 10), "": (FAIR_L, FAIR_R)}
FILL = {"water": "#2f6f9f", "bunker": "#d9c48a", "rough": "#4c6b2f"}
WIND_ARROW = {"with": "↑", "into": "↓", "across": "→", "swirling": "↻"}
LIE_MARK = {"tee": "#e8e8e8", "fairway": "#e8e8e8", "rough": "#c9d13a", "sand": "#d9c48a",
            "green": "#8fe39a", "fringe": "#6fbf7a", "water": "#7fbfff"}
GREEN_FILL, FRINGE_FILL, FAIRWAY_FILL, ROUGH_FILL, GROUND = "#8fe39a", "#5fa86a", "#4a8a3a", "#2a4a24", "#16221a"


# ------------------------------------------------------------ the shapes
# Grass, not geometry. Every outline is an ellipse or a band with its edge
# pushed out (or pulled in) by a slow wobble round it, the wobble drawn
# from a seed the hole owns, so the green on the strip, the approach and
# the green view is the one green.
TREE_GREENS = ("#1d3a1c", "#254a22", "#1a3320")
SAND, SAND_LIP, WATER, WATER_EDGE = "#d9c48a", "#b9a56c", "#2f6f9f", "#5b9ccc"
STRIPE = "rgba(255,255,255,0.055)"


def _seed(h, tag=""):
    return zlib.crc32(f"{h.get('n')}|{h.get('name')}|{h.get('yards')}|{h.get('par')}|{tag}".encode("utf-8"))


def _outline(seed, n=36, wobble=0.13, inward=False):
    """Radius factors round a closed shape, one per angle. Outward: from
    1 to 1 + wobble, so the drawn edge is never inside the rules' edge;
    inward: from 1 - wobble to 1, never outside it."""
    r = random.Random(seed)
    a, b, c = (r.uniform(0, 2 * math.pi) for _ in range(3))
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        noise = 0.5 + 0.5 * (0.55 * math.sin(2 * t + a) + 0.3 * math.sin(3 * t + b) + 0.15 * math.sin(5 * t + c))
        out.append((1 - wobble * (1 - noise)) if inward else (1 + wobble * noise))
    return out


def _smooth(pts):
    """A closed path through the points, curved (Catmull-Rom as cubics)."""
    n = len(pts)
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d) + "Z"


def _blob(cx, cy, rx, ry, factors, rot=0.0):
    """An ellipse with the outline's wobble, as a path."""
    n = len(factors)
    pts = []
    for i, f in enumerate(factors):
        t = 2 * math.pi * i / n
        x, y = rx * f * math.cos(t), ry * f * math.sin(t)
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)))
    return _smooth(pts)


def _band(x0, x1, y0, y1, seed, wobble=0.1, inward=False):
    """A band with soft, slightly irregular edges - a bunker in its yards,
    a creek across the fairway - as a path within (or just over) its box."""
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    return _blob(cx, cy, rx, ry, _outline(seed, 28, wobble, inward), 0.0)


def _strip(edges_left, edges_right, seed, wobble_px, swell=0.0):
    """A long shape from a left edge and a right edge, top to bottom, each
    pushed outward by up to `wobble_px`, ends rounded - and, for a
    fairway, a swell of up to `swell` px where the tee shots land, a
    little short of the middle of the hole, the way a fairway opens
    there."""
    r = random.Random(seed)
    a, b = r.uniform(0, 6.28), r.uniform(0, 6.28)

    def push(i, n, side):
        f = i / max(1, n - 1)                       # 0 at the green end, 1 at the tee
        t = f * 6.0
        bulge = swell * max(0.0, math.cos((f - 0.42) * 2.6)) ** 2 * (0.85 + 0.15 * math.sin(a + side))
        return bulge + wobble_px * (0.5 + 0.5 * math.sin(t * 1.7 + a + side) * 0.7 + 0.3 * math.sin(t * 3.1 + b - side) * 0.5)

    n = len(edges_left)
    left = [(x - push(i, n, 0.0), y) for i, (x, y) in enumerate(edges_left)]
    right = [(x + push(i, n, 2.0), y) for i, (x, y) in enumerate(reversed(edges_right))]
    return _smooth(left + right)


def _trees(parts, points, seed, side):
    """A tree line: dark crowns scattered along the outside of the rough."""
    r = random.Random(seed + (7 if side > 0 else 11))
    for x, y in points:
        if r.random() < 0.35:
            continue
        rad = r.uniform(3.2, 6.5)
        parts.append(f'<circle cx="{x + side * r.uniform(2, 9):.1f}" cy="{y + r.uniform(-6, 6):.1f}" r="{rad:.1f}" '
                     f'fill="{r.choice(TREE_GREENS)}"/>')


def _stripes(parts, clip_id, y0, y1, step=14, x0=0, x1=W, diagonal=False):
    """Mown stripes: alternate bands a shade lighter, clipped to the grass."""
    parts.append(f'<g clip-path="url(#{clip_id})">')
    if diagonal:
        span = (y1 - y0) + (x1 - x0)
        k = 0
        y = y0 - (x1 - x0)
        while y < y1 + span:
            if k % 2 == 0:
                parts.append(f'<polygon points="{x0},{y:.1f} {x1},{y - (x1 - x0):.1f} {x1},{y - (x1 - x0) + step:.1f} {x0},{y + step:.1f}" fill="{STRIPE}"/>')
            y += step
            k += 1
    else:
        k = 0
        y = y0
        while y < y1:
            if k % 2 == 0:
                parts.append(f'<rect x="{x0}" y="{y:.1f}" width="{x1 - x0}" height="{step}" fill="{STRIPE}"/>')
            y += step
            k += 1
    parts.append("</g>")


def _sand(parts, x0, x1, y0, y1, seed, title):
    parts.append(f'<path d="{_band(x0, x1, y0, y1, seed, 0.22, inward=True)}" fill="{SAND}" stroke="{SAND_LIP}" '
                 f'stroke-width="1.2"><title>{escape(title)}</title></path>')


def _water(parts, x0, x1, y0, y1, seed, title):
    parts.append(f'<path d="{_band(x0, x1, y0, y1, seed, 0.08)}" fill="{WATER}" stroke="{WATER_EDGE}" stroke-width="1" '
                 f'opacity="0.95"><title>{escape(title)}</title></path>')
    r = random.Random(seed)
    for _ in range(3):
        x, y = r.uniform(x0 + 8, x1 - 16), r.uniform(y0 + 4, y1 - 4)
        parts.append(f'<path d="M{x:.1f},{y:.1f} q3,-2 6,0 t6,0" fill="none" stroke="#9ad1ff" stroke-width="0.8" opacity="0.6"/>')


def _rough_patch(parts, x0, x1, y0, y1, seed, title):
    parts.append(f'<path d="{_band(x0, x1, y0, y1, seed, 0.12)}" fill="#3f6127" opacity="0.95"><title>{escape(title)}</title></path>')
    r = random.Random(seed)
    for _ in range(int((x1 - x0) * (y1 - y0) / 90)):
        parts.append(f'<circle cx="{r.uniform(x0 + 3, x1 - 3):.1f}" cy="{r.uniform(y0 + 3, y1 - 3):.1f}" r="0.9" fill="#2f4a1e"/>')


def _hazard(parts, h, hz, x0, x1, y0, y1, i):
    """One hazard in its box, drawn as what it is."""
    title = f'{hz.get("name") or hz["kind"]}, {hz["from"]}-{hz["to"]} yards'
    seed = _seed(h, f"hz{i}")
    if hz["kind"] == "bunker":
        if x1 - x0 > 3.2 * max(8.0, y1 - y0):
            # a wide, shallow band - bunkers "around" the green - is two
            # traps, one each side, not a moat
            w = (x1 - x0) * 0.28
            _sand(parts, x0, x0 + w, y0, y1, seed, title)
            _sand(parts, x1 - w, x1, y0, y1, seed + 1, title)
        else:
            _sand(parts, x0, x1, y0, y1, seed, title)
    elif hz["kind"] == "water":
        _water(parts, x0, x1, y0, y1, seed, title)
    else:
        _rough_patch(parts, x0, x1, y0, y1, seed, title)


def _cross(parts, x, y, cls, r, width, opacity, dash, title):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    parts.append(f'<g class="{cls}" stroke="#ffb454" stroke-width="{width}" fill="none" opacity="{opacity}"{extra}>'
                 f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}"/><line x1="{x - r - 5:.1f}" y1="{y:.1f}" x2="{x + r + 5:.1f}" y2="{y:.1f}"/>'
                 f'<line x1="{x:.1f}" y1="{y - r - 5:.1f}" x2="{x:.1f}" y2="{y + r + 5:.1f}"/><title>{escape(title)}</title></g>')


def _ball(parts, x, y, b):
    color = "#8b98a5" if b.get("picked_up") else LIE_MARK.get(b.get("lie") or "fairway", "#e8e8e8")
    parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{7 if b.get("you") else 5.5}" fill="{color}" '
                 f'stroke="{"#ffb454" if b.get("you") else GROUND}" stroke-width="{2.5 if b.get("you") else 1}">'
                 f'<title>{escape(str(b.get("name") or ""))}</title></circle>')


def _flag(parts, x, y):
    parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{GROUND}"/>')
    parts.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y - 22:.1f}" stroke="#e8e8e8" stroke-width="1.5"/>')
    parts.append(f'<polygon points="{x:.1f},{y - 22:.1f} {x + 12:.1f},{y - 17:.1f} {x:.1f},{y - 12:.1f}" fill="#e05a5a"/>')


def _mark_title(mark, total):
    short = total - float(mark["at"])
    where = (f"{abs(int(round(short)))} short of the pin" if short > 0 else f"{abs(int(round(short)))} past the pin" if short < 0 else "at the pin")
    off = mark.get("off") or 0
    return f"aiming {where}" + (f', {abs(int(off))} {"left" if off < 0 else "right"}' if off else "")


# --------------------------------------------------------------- the hole

def hole_svg(h, wind=None, wind_mph=None, balls=None, course_name=None, mark=None, aimed=None):
    """One hole as an SVG string, in plan. `h` is the card's hole; `balls`
    a list of {name, at, off, lie, holed, picked_up, you}; `mark` the
    golfer's aim, {at, off}, drawn as a cross; `aimed` where the last
    stroke was aimed, drawn fainter beside where the ball went - a shot
    bounces, rolls, or falls off a cliff, and the mark says what was
    meant."""
    from . import golf
    total = float(h["yards"])
    plan = Plan(h)
    k = plan.scale
    half_yd = float(h.get("width") or 18)
    seed = _seed(h)
    uid = f"h{h['n']}{seed % 1000}"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'class="holemap" role="img" aria-label="the {h["n"]} hole, par {h["par"]}, {h["yards"]} yards">']
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="{GROUND}"/>')
    # the line of play, sampled tee to green; the rough and the fairway are
    # bands either side of it, their edges softened. Where the line turns
    # the samples crowd the corner so the bands turn with it.
    ats = sorted(set([total * i / 28 for i in range(29)] + ([plan.legs[1][0]] if len(plan.legs) > 1 else [])))
    rough_l = [plan.at(a, -half_yd - 30) for a in ats]
    rough_r = [plan.at(a, half_yd + 30) for a in ats]
    parts.append(f'<path d="{_strip(rough_l, rough_r, seed + 3, 9)}" fill="{ROUGH_FILL}"/>')
    _trees(parts, [plan.at(a, -half_yd - 34) for a in ats[1:-1]], seed, -1)
    _trees(parts, [plan.at(a, half_yd + 34) for a in ats[1:-1]], seed, 1)
    # the fairway ends at the front of the fringe; beside the green is rough
    front = total - golf.green_edge(h) - golf.FRINGE + 2
    fats = [a for a in ats if a < front] + [front]
    fair_l = [plan.at(a, -half_yd) for a in fats]
    fair_r = [plan.at(a, half_yd) for a in fats]
    fairway = _strip(fair_l, fair_r, seed + 5, 4, swell=9)
    parts.append(f'<defs><clipPath id="{uid}f"><path d="{fairway}"/></clipPath></defs>')
    parts.append(f'<path d="{fairway}" fill="{FAIRWAY_FILL}"/>')
    _stripes(parts, f"{uid}f", 0, H)
    # the hazards, at their yards and where they sit across the hole,
    # turned with the line
    for i, hz in enumerate(h.get("hazards", [])):
        _plan_hazard(parts, h, hz, plan, i, k)
    # the green and its fringe, where the line ends - the one shape every view draws
    gx, gy = plan.at(total)
    rot = plan.heading(total)
    ry = golf.green_edge(h) * k
    rx = golf.green_half(h) * k
    fr = golf.FRINGE * k
    shape = _outline(_seed(h, "green"))
    parts.append(f'<path d="{_blob(gx, gy, rx + fr, ry + fr, shape, rot)}" fill="{FRINGE_FILL}"/>')
    parts.append(f'<path d="{_blob(gx, gy, rx, ry, shape, rot)}" fill="{GREEN_FILL}"/>')
    _flag(parts, gx, gy)
    # the tee box
    tx, ty = plan.at(0)
    parts.append(f'<rect x="{tx - 14:.1f}" y="{ty - 5:.1f}" width="28" height="10" rx="3" fill="#c9e2c0" stroke="{GROUND}"/>')
    # yard marks every 100, beside the line
    y100 = 100
    while y100 < total:
        mx, my = plan.at(y100, half_yd + 40)
        parts.append(f'<line x1="{mx - 4:.1f}" y1="{my:.1f}" x2="{mx + 4:.1f}" y2="{my:.1f}" stroke="#8b98a5"/>')
        parts.append(f'<text x="{mx + 7:.1f}" y="{my + 4:.1f}" font-size="10" fill="#8b98a5" '
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
    if aimed and aimed.get("at") is not None:
        ax, ay = plan.at(min(float(aimed["at"]), total + 20), aimed.get("off"))
        _cross(parts, ax, ay, "aimed", 8, 1.5, 0.55, "3 2", "aimed here")
    if mark and mark.get("at") is not None:
        mx, my = plan.at(min(float(mark["at"]), total + 20), mark.get("off"))
        _cross(parts, mx, my, "mark", 9, 2, 1, "", f'aiming {int(mark["at"])} yards' + (f', {abs(int(mark.get("off") or 0))} {"left" if (mark.get("off") or 0) < 0 else "right"}' if mark.get("off") else ""))
    # the balls, where they lie - the one that is you ringed, the holed at the cup
    on_the_tee = [b for b in (balls or []) if not b.get("holed") and float(b.get("at") or 0) == 0]
    for b in balls or []:
        at = total if b.get("holed") else min(float(b.get("at") or 0), total)
        if at == 0 and b in on_the_tee:
            xx, yy = plan.at(0, (on_the_tee.index(b) - (len(on_the_tee) - 1) / 2) * 7)
        else:
            xx, yy = plan.at(at, b.get("off"))
        _ball(parts, xx, yy, b)
    parts.append("</svg>")
    return "".join(parts)


def _plan_hazard(parts, h, hz, plan, i, k):
    """One hazard on the plan: at its yards along the line and its
    measured yards across it, turned with the line where it sits. A
    band across the hole spans the fairway; a hazard beside it is a
    blob at its offset; "around" the green is a blob each side."""
    from . import golf
    title = f'{hz.get("name") or hz["kind"]}, {hz["from"]}-{hz["to"]} yards'
    seed = _seed(h, f"hz{i}")
    half = golf.fairway_half(h)
    lo, hi = float(hz["from"]), float(max(hz["to"], hz["from"] + 4))
    mid = (lo + hi) / 2
    side = hz.get("side", "")
    rot = plan.heading(mid)
    ry = (hi - lo) / 2 * k
    if side in ("across", "front", "centre", "") and hz.get("off") is None:
        offs, rx = [0.0], half * k * (0.75 if side == "centre" else 1.0)
    elif side == "beyond" and hz.get("off") is None:
        offs, rx = [0.0], (golf.green_half(h) + 6) * k
    elif side == "around" and hz.get("off") is None:
        offs, rx = [-(golf.green_half(h) + 8), golf.green_half(h) + 8], 7 * k
    else:
        off = golf.hazard_off(h, hz)
        if hz["kind"] == "water" and side in ("left", "right") and hi - lo > 80:
            # water down one side of the hole, the length of it: a band out to the edge
            offs, rx = [off + (18 if off > 0 else -18)], 24 * k
        elif hz["kind"] == "water" and side in ("across", "front"):
            offs, rx = [off], half * k
        else:
            offs, rx = [off], (8 if hz["kind"] == "bunker" else 12) * k
    if hi - lo > 60:
        # A hazard the length of a leg or more - the bay down the 18th, a
        # creek along the hole, a run of bunkers - follows the line, as a
        # band between two offsets, rather than one shape across the turn.
        ats = [lo + (hi - lo) * i / 12 for i in range(13)]
        if len(plan.legs) > 1 and lo < plan.legs[1][0] < hi:
            ats = sorted(ats + [plan.legs[1][0]])
        for j, off in enumerate(offs):
            inner, outer = off - rx / k, off + rx / k
            left = [plan.at(a, inner) for a in ats]
            right = [plan.at(a, outer) for a in ats]
            d = _strip(left, right, seed + j, 3)
            if hz["kind"] == "bunker":
                parts.append(f'<path d="{d}" fill="{SAND}" stroke="{SAND_LIP}" stroke-width="1.2"><title>{escape(title)}</title></path>')
            elif hz["kind"] == "water":
                parts.append(f'<path d="{d}" fill="{WATER}" stroke="{WATER_EDGE}" stroke-width="1" opacity="0.95"><title>{escape(title)}</title></path>')
            else:
                parts.append(f'<path d="{d}" fill="#3f6127" opacity="0.95"><title>{escape(title)}</title></path>')
        return
    for j, off in enumerate(offs):
        cx, cy = plan.at(mid, off)
        rx_ = max(rx, 5.0)
        ry_ = max(ry, 5.0)
        if hz["kind"] == "bunker":
            parts.append(f'<path d="{_blob(cx, cy, rx_, ry_, _outline(seed + j, 28, 0.22, inward=True), rot)}" fill="{SAND}" '
                         f'stroke="{SAND_LIP}" stroke-width="1.2"><title>{escape(title)}</title></path>')
        elif hz["kind"] == "water":
            parts.append(f'<path d="{_blob(cx, cy, rx_, ry_, _outline(seed + j, 28, 0.08), rot)}" fill="{WATER}" '
                         f'stroke="{WATER_EDGE}" stroke-width="1" opacity="0.95"><title>{escape(title)}</title></path>')
            r = random.Random(seed)
            for _ in range(2):
                x, y = cx + r.uniform(-rx_ * 0.5, rx_ * 0.5), cy + r.uniform(-ry_ * 0.5, ry_ * 0.5)
                parts.append(f'<path d="M{x:.1f},{y:.1f} q3,-2 6,0 t6,0" fill="none" stroke="#9ad1ff" stroke-width="0.8" opacity="0.6"/>')
        else:
            parts.append(f'<path d="{_blob(cx, cy, rx_, ry_, _outline(seed + j, 28, 0.12), rot)}" fill="#3f6127" opacity="0.95">'
                         f'<title>{escape(title)}</title></path>')


# ------------------------------------------------------------- the green
# On the green the strip is the green: the whole of it, the cup at its
# centre, every ball on it at its feet from the cup, the way it falls as
# shading and contours, the sand beside it, and the golfer's mark. The
# wind is not on it - on the green the wind stops mattering and the slope
# starts.
GW, GH = 260, 300
GREEN_HALF_FT = 14 * 3          # golf.GREEN_HALF, in feet
FRINGE_FT = 3 * 3               # golf.FRINGE, in feet


def green_geometry(h):
    """What a screen needs to turn a tap on the green into feet from the
    cup, and then into the yards the mark is kept in."""
    depth_ft = float(h.get("green") or 28) * 3
    px_per_ft = min((GW / 2 - 36) / (GREEN_HALF_FT + FRINGE_FT), (GH / 2 - 34) / (depth_ft / 2 + FRINGE_FT))
    return {"view": "green", "w": GW, "h": GH, "cx": GW / 2, "cy": GH / 2, "px_per_ft": px_per_ft,
            "yards": h["yards"], "depth_ft": depth_ft}


def _greenside(h):
    """The hazards that sit at the green: within its depth of the pin."""
    from . import golf
    near = golf.green_edge(h) + 12
    return [hz for hz in h.get("hazards", []) if hz["to"] >= h["yards"] - near]


def green_svg(h, balls=None, mark=None, aimed=None, slope=None):
    """The green as an SVG string: `balls` those on it, with `feet_along`
    (short negative) and `feet_across` (left negative); `mark` and
    `aimed` in the same feet; `slope` {"falls", "grade"}."""
    from . import golf
    geo = green_geometry(h)
    cx, cy, k = geo["cx"], geo["cy"], geo["px_per_ft"]
    ry, rx = (golf.green_edge(h) * 3) * k, golf.green_half(h) * 3 * k
    fr = FRINGE_FT * k
    seed = _seed(h, "green")
    uid = f"g{h['n']}{seed % 1000}"
    shape = _outline(seed)

    def at(fa, fx):
        return cx + float(fx or 0) * k, cy - float(fa or 0) * k

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GW} {GH}" class="holemap greenmap" role="img" '
             f'aria-label="the {h["n"]} green">',
             f'<rect x="0" y="0" width="{GW}" height="{GH}" rx="14" fill="{GROUND}"/>',
             f'<path d="{_blob(cx, cy, rx + fr + 16, ry + fr + 16, _outline(seed + 1, 36, 0.14))}" fill="{ROUGH_FILL}"/>']
    # the sand and the water at the green, on the side the card puts them
    for i, hz in enumerate(_greenside(h)):
        side = hz.get("side", "")
        dy = -((hz["from"] + hz["to"]) / 2.0 - h["yards"]) * 3 * k
        boxes = []
        if hz.get("off") is not None and hz["kind"] == "bunker":
            ox = cx + float(hz["off"]) * 3 * k
            boxes.append((ox - 13, ox + 13, cy + dy - 20, cy + dy + 20))
            side = "measured"
        if side in ("left", "around"):
            boxes.append((cx - rx - fr - 26, cx - rx - fr - 2, cy + dy - 22, cy + dy + 22))
        if side in ("right", "around"):
            boxes.append((cx + rx + fr + 2, cx + rx + fr + 26, cy + dy - 22, cy + dy + 22))
        if side in ("front", "across", "", "centre"):
            boxes.append((cx - 30, cx + 30, cy + ry + fr + 2, cy + ry + fr + 22))
        if side == "beyond":
            boxes.append((cx - 40, cx + 40, cy - ry - fr - 24, cy - ry - fr - 2))
        for j, (x0, x1, y0, y1) in enumerate(boxes):
            _hazard(parts, h, hz, x0, x1, y0, y1, 100 + i * 4 + j)
    # the fringe and the green
    parts.append(f'<path d="{_blob(cx, cy, rx + fr, ry + fr, shape)}" fill="{FRINGE_FILL}"><title>the fringe</title></path>')
    green = _blob(cx, cy, rx, ry, shape)
    parts.append(f'<defs><clipPath id="{uid}"><path d="{green}"/></clipPath>')
    s = slope or {}
    dirs = {"front": (0, 1), "back": (0, -1), "left": (-1, 0), "right": (1, 0)}
    dx, dy = dirs.get(s.get("falls"), (0, 1))
    if s.get("grade", 0) > 0:
        # the fall, as shade: the high side light, the low side dark
        parts.append(f'<linearGradient id="{uid}s" x1="{0.5 - dx * 0.5}" y1="{0.5 - dy * 0.5}" x2="{0.5 + dx * 0.5}" y2="{0.5 + dy * 0.5}">'
                     f'<stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="{min(0.34, 0.09 * s["grade"]):.2f}"/></linearGradient>')
    parts.append('</defs>')
    parts.append(f'<path d="{green}" fill="{GREEN_FILL}"/>')
    _stripes(parts, uid, cy - ry - 10, cy + ry + 10, 12, int(cx - rx - 10), int(cx + rx + 10), diagonal=True)
    if s.get("grade", 0) > 0:
        parts.append(f'<path d="{green}" fill="url(#{uid}s)"/>')
        # contours across the fall, bowed the way the ground would show them
        parts.append(f'<g clip-path="url(#{uid})" fill="none" stroke="#3f8a4c" stroke-width="0.9" opacity="0.55">')
        for f in (-0.5, -0.17, 0.17, 0.5):
            px, py = cx + dx * f * (rx if dx else ry) * 1.6, cy + dy * f * (ry if dy else rx) * 1.6
            if dx:
                parts.append(f'<path d="M{px:.1f},{cy - ry - 6:.1f} Q{px + dx * 10:.1f},{cy:.1f} {px:.1f},{cy + ry + 6:.1f}"/>')
            else:
                parts.append(f'<path d="M{cx - rx - 6:.1f},{py:.1f} Q{cx:.1f},{py + dy * 10:.1f} {cx + rx + 6:.1f},{py:.1f}"/>')
        parts.append('</g>')
        ax, ay = cx + dx * (rx if dx else ry) * 0.55, cy + dy * (ry if dy else rx) * 0.55
        bx, by = ax + dx * 26, ay + dy * 26
        parts.append(f'<g stroke="#1d3a22" stroke-width="2" fill="#1d3a22" opacity="0.7">'
                     f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}"/>'
                     f'<polygon points="{bx + dx * 7:.1f},{by + dy * 7:.1f} {bx - dy * 4:.1f},{by + dx * 4:.1f} {bx + dy * 4:.1f},{by - dx * 4:.1f}"/>'
                     f'<title>falls to the {escape(str(s.get("falls")))}, {s.get("grade")}%</title></g>')
        parts.append(f'<text x="14" y="{GH - 12}" font-size="11" fill="#c9d1d9" font-family="system-ui, sans-serif">'
                     f'falls {escape(str(s.get("falls")))} · {s.get("grade"):g}%</text>')
    # a scale: ten feet
    sx, sy = GW - 14 - 10 * k, GH - 14
    parts.append(f'<line x1="{sx:.1f}" y1="{sy}" x2="{sx + 10 * k:.1f}" y2="{sy}" stroke="#c9d1d9" stroke-width="1.5"/>'
                 f'<text x="{sx + 5 * k:.1f}" y="{sy - 4}" text-anchor="middle" font-size="10" fill="#c9d1d9" font-family="ui-monospace, monospace">10 ft</text>')
    _flag(parts, cx, cy)
    if aimed and aimed.get("feet_along") is not None:
        x, y = at(aimed["feet_along"], aimed["feet_across"])
        _cross(parts, x, y, "aimed", 8, 1.5, 0.55, "3 2", "aimed here")
    if mark and mark.get("feet_along") is not None:
        x, y = at(mark["feet_along"], mark["feet_across"])
        _cross(parts, x, y, "mark", 9, 2, 1, "", "your mark")
    for b in balls or []:
        if b.get("holed"):
            continue
        x, y = at(b.get("feet_along"), b.get("feet_across"))
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{7 if b.get("you") else 5.5}" fill="#ffffff" '
                     f'stroke="{"#ffb454" if b.get("you") else GROUND}" stroke-width="{2.5 if b.get("you") else 1}">'
                     f'<title>{escape(str(b.get("name") or ""))}, {b.get("feet", "?")} feet</title></circle>')
    head = f'{h["n"]} · the green · par {h["par"]}'
    parts.append(f'<text x="14" y="22" font-size="15" font-weight="700" fill="#f3f3f3" font-family="system-ui, sans-serif">'
                 f'{escape(head)}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------- the approach
# When the green is the target - the club in hand reaches the pin, or the
# ball is inside a wedge of it - the strip zooms to the green and what is
# round it: the fringe, the bunkers and the water at their yards, the
# fairway running in, the yards from the pin ticked off. The same yard in
# both directions, so the mark can be put on the front edge, the collar,
# or the far side of the bunker, and mean it.
APPROACH_PX = 3.75              # pixels a yard, both ways
APPROACH_BEYOND = 30            # yards past the pin the view shows: the back of the green and its collar
APPROACH_PAD_TOP = 40


def geometry_for(g, h, ball):
    """The geometry for this ball's view of the hole: the green when the
    ball is on it or on its fringe, the approach when the green is the
    target (golf.Golf.approaching), the whole hole otherwise."""
    if h is None:
        return None
    if ball and ball.get("lie") in ("green", "fringe") and not ball.get("holed"):
        return green_geometry(h)
    if ball and ball.get("approaching"):
        return approach_geometry(h)
    return geometry(h)


def approach_geometry(h):
    """What a screen needs to turn a tap on the approach into yards along
    the hole and off the line."""
    k = APPROACH_PX
    top = float(h["yards"]) + APPROACH_BEYOND           # the yards at the top of the view
    shows = (H - APPROACH_PAD_TOP - 12) / k             # yards the view covers, top to bottom
    return {"view": "approach", "w": W, "h": H, "cx": W / 2, "top_y": APPROACH_PAD_TOP, "px_per_yard": k,
            "top": top, "yards": h["yards"], "from": top - shows}


def approach_svg(h, wind=None, wind_mph=None, balls=None, mark=None, aimed=None):
    """The last hundred yards, drawn: `balls`, `mark` and `aimed` as
    hole_svg takes them. A ball short of the view is shown at its foot
    with its yards, so the golfer knows where they are hitting from."""
    from . import golf
    geo = approach_geometry(h)
    k, cx, top = geo["px_per_yard"], geo["cx"], geo["top"]
    total = float(h["yards"])
    half_yd = float(h.get("width") or 18)
    seed = _seed(h)
    uid = f"a{h['n']}{seed % 1000}"

    def y_at(at):
        return geo["top_y"] + (top - float(at)) * k

    def x_off(off):
        return cx + float(off or 0) * k

    foot = geo["from"]
    edge = golf.green_edge(h)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="holemap approachmap" role="img" '
             f'aria-label="the approach to the {h["n"]} green">',
             f'<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="{GROUND}"/>']
    # the rough, with its trees, and the fairway running in to the green's front
    ats = [foot - 10 + (total + 4 - foot + 10) * i / 16 for i in range(17)]
    rough_l = [(x_off(-half_yd - 22), y_at(a)) for a in ats]
    rough_r = [(x_off(half_yd + 22), y_at(a)) for a in ats]
    parts.append(f'<path d="{_strip(rough_l, rough_r, seed + 3, 14)}" fill="{ROUGH_FILL}"/>')
    _trees(parts, [(max(x - 6, 10.0), y) for x, y in rough_l[1:-1]], seed, -1)
    _trees(parts, [(min(x + 6, W - 10.0), y) for x, y in rough_r[1:-1]], seed, 1)
    fats = [a for a in ats if a <= total - edge - golf.FRINGE + 2] + [total - edge - golf.FRINGE + 2]
    fair_l = [(x_off(-half_yd), y_at(a)) for a in fats]
    fair_r = [(x_off(half_yd), y_at(a)) for a in fats]
    fairway = _strip(fair_l, fair_r, seed + 5, 6)
    parts.append(f'<defs><clipPath id="{uid}f"><path d="{fairway}"/></clipPath></defs>')
    parts.append(f'<path d="{fairway}" fill="{FAIRWAY_FILL}"/>')
    _stripes(parts, f"{uid}f", geo["top_y"], H, 16)
    # the hazards, as they are at these yards and on their side
    for i, hz in enumerate(h.get("hazards", [])):
        if hz["to"] < foot - 5:
            continue
        side = hz.get("side", "")
        if hz.get("off") is not None:
            # measured: where it sits across the hole, a bunker's width wide
            o = float(hz["off"])
            w = 9 if hz["kind"] == "bunker" else 14
            if hz["kind"] == "water" and side in ("left", "right") and hz["to"] - hz["from"] > 80:
                o0, o1 = (o, o + 40) if o > 0 else (o - 40, o)
            elif hz["kind"] == "water" and side in ("across", "front"):
                o0, o1 = -half_yd, half_yd
            else:
                o0, o1 = o - w / 2, o + w / 2
        elif side == "left":
            o0, o1 = -half_yd - 18, -half_yd - 2
        elif side == "right":
            o0, o1 = half_yd + 2, half_yd + 18
        elif side == "around":
            o0, o1 = -half_yd - 16, half_yd + 16
        elif side == "beyond":
            o0, o1 = -half_yd - 6, half_yd + 6
        elif side == "centre":
            o0, o1 = -half_yd + 5, half_yd - 5
        else:
            o0, o1 = -half_yd, half_yd
        y1, y0 = y_at(hz["from"]), y_at(hz["to"])
        y0, y1 = max(y0, geo["top_y"] - 8), min(y1, H + 8)
        if y1 - y0 < 10:
            y0, y1 = (y0 + y1) / 2 - 5, (y0 + y1) / 2 + 5
        _hazard(parts, h, hz, x_off(o0), x_off(o1), y0, y1, i)
    # the green and its fringe, the one shape every view draws
    gy = y_at(total)
    shape = _outline(_seed(h, "green"))
    parts.append(f'<path d="{_blob(cx, gy, (golf.green_half(h) + golf.FRINGE) * k, (edge + golf.FRINGE) * k, shape)}" '
                 f'fill="{FRINGE_FILL}"><title>the fringe</title></path>')
    green = _blob(cx, gy, golf.green_half(h) * k, edge * k, shape)
    parts.append(f'<defs><clipPath id="{uid}g"><path d="{green}"/></clipPath></defs>')
    parts.append(f'<path d="{green}" fill="{GREEN_FILL}"/>')
    _stripes(parts, f"{uid}g", gy - edge * k - 10, gy + edge * k + 10, 9, int(cx - 70), int(cx + 70), diagonal=True)
    _flag(parts, cx, gy)
    # the yards from the pin, every ten, up the left
    yd = 10
    while total - yd > foot:
        yy = y_at(total - yd)
        parts.append(f'<line x1="10" y1="{yy:.1f}" x2="18" y2="{yy:.1f}" stroke="#8b98a5"/>')
        parts.append(f'<text x="22" y="{yy + 4:.1f}" font-size="10" fill="#8b98a5" font-family="ui-monospace, monospace">{yd}</text>')
        yd += 10
    head = f'{h["n"]} · the approach'
    parts.append(f'<text x="14" y="26" font-size="15" font-weight="700" fill="#f3f3f3" font-family="system-ui, sans-serif">'
                 f'{escape(head)}</text>')
    if wind:
        wtxt = f'{WIND_ARROW.get(wind, "")} {wind}' + (f' {wind_mph} mph' if wind_mph is not None else '')
        parts.append(f'<text x="{W - 14}" y="26" text-anchor="end" font-size="12" fill="#9ad1ff" '
                     f'font-family="system-ui, sans-serif">{escape(wtxt)}</text>')
    if aimed and aimed.get("at") is not None:
        _cross(parts, x_off(aimed.get("off")), y_at(min(float(aimed["at"]), top)), "aimed", 8, 1.5, 0.55, "3 2", "aimed here")
    if mark and mark.get("at") is not None:
        _cross(parts, x_off(mark.get("off")), y_at(min(float(mark["at"]), top)), "mark", 9, 2, 1, "", _mark_title(mark, total))
    # the balls: on the view where they lie; short of it, at its foot with the yards
    for b in balls or []:
        if b.get("holed"):
            continue
        at = float(b.get("at") or 0)
        if at >= foot:
            _ball(parts, x_off(b.get("off")), y_at(at), b)
        elif b.get("you"):
            _ball(parts, x_off(b.get("off")), H - 10, b)
            parts.append(f'<text x="{x_off(b.get("off")) + 11:.1f}" y="{H - 6}" font-size="11" fill="#ffb454" '
                         f'font-family="system-ui, sans-serif">you, {int(round(total - at))} out</text>')
    parts.append("</svg>")
    return "".join(parts)

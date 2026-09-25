"""The course, drawn: the club's routing from OpenStreetMap, in the strip's colors.

golfmap.py draws a hole as the rules see it, a yardage-book strip from the
card, because the game did not have the routing. Now it does:
tools/fetch_golf_map.py keeps each course's fairways, greens, tees,
bunkers, water, coastline and hole lines, in meters, beside its card
(data/golf/<course>.map.json, OpenStreetMap contributors' data under the
ODbL, credited on every picture). This draws from that. The whole course
is the frame on the clubhouse wall; one hole, turned tee-at-the-foot like
the strip, is the frame a person waiting for a tee time watches the group
on.

A frame is filled. The course is fitted to whatever width and height the
screen has, and the ground is allowed to stretch to fill it - a golf
course is a long thin thing and a clubhouse frame is not - up to a limit,
STRETCH_MOST, past which the picture is centerd with margins rather than
squashed into nonsense. The stretch is done to the geometry here, not by
the browser to the picture, so the hole numbers, the flags and the line
widths stay true while the ground gives. The screenshots this replaces
were the same data through somebody else's renderer, at their scale, in
their colors, with their labels; this is the same facts in ELMER's hand.

SVG, plain, the strip's palette (golfmap.FILL and friends), no
libraries; the files are a hundred kilobytes and a course draws in a few
milliseconds, cached a day.
"""
import json
import math
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from . import golfmap

DATA = Path(__file__).resolve().parents[1] / "data" / "golf"

STRETCH_MOST = 1.5          # the ground may be pulled this far out of true, no further
SEA = "#1d3d5c"
LAND = "#233a25"            # the ground outside the course: the strip's GROUND, a shade greener
COURSE = golfmap.ROUGH_FILL
FAIRWAY = golfmap.FAIRWAY_FILL
GREEN = golfmap.GREEN_FILL
TEE = "#c9e2c0"
SAND, SAND_LIP = golfmap.SAND, golfmap.SAND_LIP
WATER, WATER_EDGE = golfmap.WATER, golfmap.WATER_EDGE
LINE = "#f3f3f3"
INK = "#f3f3f3"
CREDIT = "Map data © OpenStreetMap contributors"


@lru_cache(maxsize=8)
def load(course_id):
    """The course's routing, or None when the unit has no map for it."""
    path = DATA / f"{course_id}.map.json"
    try:
        with open(path, encoding="utf8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def has_map(course_id):
    return load(course_id) is not None


def _bounds(rings):
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return min(xs), min(ys), max(xs), max(ys)


class Fit:
    """Meters to the frame: turned by `turn` radians, then scaled to fill
    width x height, stretching one way up to STRETCH_MOST."""

    def __init__(self, rings, width, height, turn=0.0, margin_m=25.0, stretch_most=STRETCH_MOST):
        self.turn = turn
        self.c, self.s = math.cos(turn), math.sin(turn)
        turned = [[self._rot(p) for p in r] for r in rings]
        x0, y0, x1, y1 = _bounds(turned)
        x0, y0, x1, y1 = x0 - margin_m, y0 - margin_m, x1 + margin_m, y1 + margin_m
        self.w, self.h = width, height
        sx, sy = width / max(1e-9, x1 - x0), height / max(1e-9, y1 - y0)
        # fill the frame, but let neither axis be more than stretch_most times the other
        if sx > sy * stretch_most:
            sx = sy * stretch_most
        elif sy > sx * stretch_most:
            sy = sx * stretch_most
        self.sx, self.sy = sx, sy
        # center what is left over
        self.ox = (width - sx * (x1 - x0)) / 2 - sx * x0
        self.oy = (height - sy * (y1 - y0)) / 2 + sy * y1
        self.scale = math.sqrt(sx * sy)          # for things that must stay round: a meter, on average

    def _rot(self, p):
        x, y = p
        return (x * self.c - y * self.s, x * self.s + y * self.c)

    def xy(self, p):
        x, y = self._rot(p)
        return (self.ox + self.sx * x, self.oy - self.sy * y)

    def path(self, ring, close=True):
        pts = [self.xy(p) for p in ring]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        return d + (" Z" if close else "")


def _polys(parts, fit, rings, fill, stroke=None, width=0.0, opacity=None, title=None):
    for r in rings:
        if len(r) < 3:
            continue
        extra = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ' stroke="none"'
        if opacity is not None:
            extra += f' opacity="{opacity}"'
        t = f"<title>{escape(title)}</title>" if title else ""
        parts.append(f'<path d="{fit.path(r)}" fill="{fill}"{extra}>{t}</path>' if t
                     else f'<path d="{fit.path(r)}" fill="{fill}"{extra}/>')


def _chains(pieces, tol=1.0):
    """Coastline ways chained end to end into as many polylines as they make."""
    pieces = [list(map(tuple, c)) for c in pieces if len(c) >= 2]
    chains = []
    while pieces:
        chain = pieces.pop(0)
        grew = True
        while pieces and grew:
            grew = False
            for i, p in enumerate(pieces):
                if math.dist(p[0], chain[-1]) < tol:
                    chain += p[1:]
                elif math.dist(p[-1], chain[0]) < tol:
                    chain = p[:-1] + chain
                elif math.dist(p[-1], chain[-1]) < tol:
                    chain += list(reversed(p))[1:]
                elif math.dist(p[0], chain[0]) < tol:
                    chain = list(reversed(p))[:-1] + chain
                else:
                    continue
                pieces.pop(i)
                grew = True
                break
        chains.append(chain)
    return chains


def _sea(parts, fit, m):
    """The water beyond the coast. OSM's rule is land on the left of a
    coastline way, but pieces arrive in any order and some are turned by
    the chaining, so the longest chain is oriented by the one fact that is
    certain here: the course is on land. Its middle must lie on the chain's
    left; if it does not, the chain is reversed. The sea is then the chain
    closed far out on its right-hand side. A coast that does not cross the
    frame leaves land where the water is, which is the honest failure."""
    chains = _chains(m.get("coast") or [])
    if not chains:
        return
    chain = max(chains, key=lambda c: sum(math.dist(a, b) for a, b in zip(c, c[1:])))
    rings = [m["outline"]] if m.get("outline") else list(m.get("holes", {}).values())
    cx = sum(p[0] for r in rings for p in r) / max(1, sum(len(r) for r in rings))
    cy = sum(p[1] for r in rings for p in r) / max(1, sum(len(r) for r in rings))
    # The nearest segment of the chain to the course's middle decides the
    # side - judged on the screen, y down, where the walk round the frame
    # happens too: there, a positive cross product puts a point on the
    # right of travel, and the course must be on the left.
    pts = [fit.xy(p) for p in chain]
    # Every segment votes: a point a little to its left, and one to its
    # right, are each tested against the course's outline (or, without one,
    # against the nearest-segment rule from the course's middle). Land is
    # the side with more points in the course. One segment cannot be
    # trusted - in a cove the shore runs every way - but the coast can.
    ring = [fit.xy(tuple(q)) for q in m["outline"]] if m.get("outline") else None
    step_px = 30.0 * fit.scale
    left_votes = right_votes = 0
    if ring:
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            n = math.hypot(dx, dy)
            if n == 0:
                continue
            mx, my = (ax + bx) / 2, (ay + by) / 2
            rgt = (mx - dy / n * step_px, my + dx / n * step_px)    # (-dy, dx): right of travel on screen
            lft = (mx + dy / n * step_px, my - dx / n * step_px)
            left_votes += _in_ring(lft, ring)
            right_votes += _in_ring(rgt, ring)
    if left_votes == right_votes:
        sx, sy = fit.xy((cx, cy))
        best = min(range(len(pts) - 1), key=lambda i: _dist_seg((sx, sy), pts[i], pts[i + 1]))
        (ax, ay), (bx, by) = pts[best], pts[best + 1]
        right_votes = int((bx - ax) * (sy - ay) - (by - ay) * (sx - ax) > 0)
        left_votes = 1 - right_votes
    if right_votes > left_votes:       # the course is on the right: the chain runs the wrong way
        pts = list(reversed(pts))
    # Run both ends on, straight, well past the frame, then close the water
    # by walking a big rectangle's edge clockwise from the far end back to
    # the far start: with the water on the right of travel, clockwise is
    # the water's side. The frame's own clip trims the rest.
    far = max(fit.w, fit.h) * 3
    L, T, R, B = -far, -far, fit.w + far, fit.h + far
    def run_on(a, b):
        """From b, on in the direction a->b, to where it meets the big rectangle."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        ts = []
        if dx > 0:
            ts.append((R - b[0]) / dx)
        elif dx < 0:
            ts.append((L - b[0]) / dx)
        if dy > 0:
            ts.append((B - b[1]) / dy)
        elif dy < 0:
            ts.append((T - b[1]) / dy)
        t = min(ts) if ts else 0.0
        return (b[0] + dx * t, b[1] + dy * t)
    pts = [run_on(pts[1], pts[0])] + pts + [run_on(pts[-2], pts[-1])]
    def edge_of(p):
        """Which edge of the big rectangle p is on, 0 top 1 right 2 bottom 3 left, clockwise."""
        x, y = p
        d = [abs(y - T), abs(x - R), abs(y - B), abs(x - L)]
        return d.index(min(d))
    def along(p, e):
        """How far clockwise along its edge p sits."""
        x, y = p
        return (x - L, y - T, R - x, B - y)[e]
    corner_after = [(R, T), (R, B), (L, B), (L, T)]      # the corner that ends each edge, clockwise
    e_end, e_start = edge_of(pts[-1]), edge_of(pts[0])
    walk = []
    e = e_end
    for _ in range(4):
        if e == e_start and (e != e_end or along(pts[0], e) > along(pts[-1], e)):
            break
        walk.append(corner_after[e])
        e = (e + 1) % 4
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts + walk) + " Z"
    parts.append(f'<path d="{d}" fill="{SEA}" stroke="none"/>')


def _hole_lines(parts, fit, m, only=None, numbers=True):
    for n, line in sorted(m.get("holes", {}).items(), key=lambda kv: int(kv[0])):
        if only is not None and int(n) != only:
            continue
        pts = [fit.xy(tuple(p)) for p in line]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="1.2" opacity="0.7" '
                     f'stroke-dasharray="4 3"/>')
        gx, gy = pts[-1]
        # the flag at the green end
        parts.append(f'<line x1="{gx:.1f}" y1="{gy:.1f}" x2="{gx:.1f}" y2="{gy - 11:.1f}" stroke="{INK}" stroke-width="1.2"/>')
        parts.append(f'<polygon points="{gx:.1f},{gy - 11:.1f} {gx + 6:.1f},{gy - 8.5:.1f} {gx:.1f},{gy - 6:.1f}" fill="#e05a5a"/>')
        if numbers:
            tx, ty = pts[0]
            parts.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="8" fill="{golfmap.GROUND}" stroke="{INK}" stroke-width="1"/>')
            parts.append(f'<text x="{tx:.1f}" y="{ty + 3.5:.1f}" font-size="9.5" font-weight="700" fill="{INK}" '
                         f'text-anchor="middle" font-family="system-ui, sans-serif">{int(n)}</text>')


def _credit(parts, w, h):
    parts.append(f'<text x="{w - 6}" y="{h - 5}" font-size="9" fill="#8b98a5" text-anchor="end" '
                 f'font-family="system-ui, sans-serif" opacity="0.9">{escape(CREDIT)}</text>')


def _ground(parts, fit, m, w, h):
    parts.append(f'<rect x="0" y="0" width="{w}" height="{h}" fill="{LAND}"/>')
    _sea(parts, fit, m)
    if m.get("outline"):
        _polys(parts, fit, [m["outline"]], COURSE)
    _polys(parts, fit, m.get("rough") or [], COURSE)
    _polys(parts, fit, m.get("fairways") or [], FAIRWAY)
    _polys(parts, fit, m.get("range") or [], FAIRWAY, opacity=0.6)
    _polys(parts, fit, m.get("water") or [], WATER, WATER_EDGE, 0.8)
    _polys(parts, fit, m.get("bunkers") or [], SAND, SAND_LIP, 0.6)
    _polys(parts, fit, m.get("greens") or [], GREEN)
    _polys(parts, fit, m.get("tees") or [], TEE, opacity=0.9)


def course_svg(course_id, width=640, height=280, title=None):
    """The whole course, filling width x height."""
    m = load(course_id)
    if m is None:
        return None
    rings = [m["outline"]] if m.get("outline") else (m.get("fairways") or []) + list(m.get("holes", {}).values())
    fit = Fit(rings, width, height, margin_m=40.0)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'role="img" aria-label="{escape(title or m.get("name") or course_id)}, mapped">']
    parts.append(f'<clipPath id="frame"><rect x="0" y="0" width="{width}" height="{height}" rx="10"/></clipPath>')
    parts.append('<g clip-path="url(#frame)">')
    _ground(parts, fit, m, width, height)
    _hole_lines(parts, fit, m)
    parts.append("</g>")
    if title:
        parts.append(f'<text x="12" y="20" font-size="13" font-weight="700" fill="{INK}" '
                     f'font-family="system-ui, sans-serif">{escape(title)}</text>')
    _credit(parts, width, height)
    parts.append("</svg>")
    return "".join(parts)


def hole_svg(course_id, n, width=260, height=420, balls=None, title=None):
    """One hole, turned so the tee is at the foot and the green at the head,
    with what lies within a hundred meters of its line; the strip's cousin,
    drawn from the ground rather than the card. `balls` may carry the
    game's balls as (yards along, yards off) for the group being watched;
    they are placed along the hole's own line."""
    m = load(course_id)
    if m is None:
        return None
    line = m.get("holes", {}).get(str(n))
    if not line or len(line) < 2:
        return None
    line = [tuple(p) for p in line]
    tee, green = line[0], line[-1]
    # turn so that tee -> green points up the frame (north on the page is the line's bearing)
    ang = math.atan2(green[1] - tee[1], green[0] - tee[0])
    turn = math.pi / 2 - ang
    reach = 100.0
    # fitted to the hole's own line, with room either side for its bunkers
    # and a bank of rough; the neighbours fall where they fall and are clipped
    fit = Fit([line], width, height, turn=turn, margin_m=45.0)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'role="img" aria-label="the {n}, mapped">']
    parts.append(f'<clipPath id="frame"><rect x="0" y="0" width="{width}" height="{height}" rx="10"/></clipPath>')
    parts.append('<g clip-path="url(#frame)">')
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{LAND}"/>')
    _sea(parts, fit, m)
    if m.get("outline"):
        _polys(parts, fit, [m["outline"]], COURSE)
    sub = {k: [r for r in (m.get(k) or []) if _near_line(r, line, reach * 1.5)]
           for k in ("rough", "fairways", "range", "water", "bunkers", "greens", "tees")}
    _polys(parts, fit, sub["rough"], COURSE)
    _polys(parts, fit, sub["fairways"], FAIRWAY)
    _polys(parts, fit, sub["water"], WATER, WATER_EDGE, 0.8)
    _polys(parts, fit, sub["bunkers"], SAND, SAND_LIP, 0.6)
    _polys(parts, fit, sub["greens"], GREEN)
    _polys(parts, fit, sub["tees"], TEE, opacity=0.9)
    # the other holes' lines faintly, this one's clearly
    _hole_lines(parts, fit, {"holes": {k: v for k, v in m["holes"].items() if int(k) != int(n)}}, numbers=False)
    _hole_lines(parts, fit, {"holes": {str(n): line}})
    for b in balls or []:
        x, y = fit.xy(_along(line, b.get("at", 0) * 0.9144, b.get("off", 0) * 0.9144))
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{golfmap.LIE_MARK.get(b.get("lie") or "fairway", "#e8e8e8")}" '
                     f'stroke="{golfmap.GROUND}" stroke-width="1"><title>{escape(b.get("name") or "")}</title></circle>')
    parts.append("</g>")
    if title:
        parts.append(f'<text x="10" y="18" font-size="12" font-weight="700" fill="{INK}" '
                     f'font-family="system-ui, sans-serif">{escape(title)}</text>')
    _credit(parts, width, height)
    parts.append("</svg>")
    return "".join(parts)


def _near_line(ring, line, reach):
    """Does any point of the ring lie within reach meters of the polyline?"""
    for p in ring[:: max(1, len(ring) // 24)]:
        for a, b in zip(line, line[1:]):
            if _dist_seg(p, a, b) <= reach:
                return True
    return False


def _in_ring(pt, ring):
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _dist_seg(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _along(line, meters, off_m=0.0):
    """The point `meters` along the polyline, offset `off_m` to its right."""
    left = meters
    for a, b in zip(line, line[1:]):
        seg = math.dist(a, b)
        if left <= seg or (a, b) == (line[-2], line[-1]):
            t = 0.0 if seg == 0 else max(0.0, min(1.0, left / seg))
            x, y = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
            if seg:
                ux, uy = (b[0] - a[0]) / seg, (b[1] - a[1]) / seg
                x, y = x + uy * off_m, y - ux * off_m
            return (x, y)
        left -= seg
    return line[-1]

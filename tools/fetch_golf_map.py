#!/usr/bin/env python3
"""Fetch a course's routing from OpenStreetMap and write it beside its card.

    python3 tools/fetch_golf_map.py pebble-beach
    python3 tools/fetch_golf_map.py --all

The card in data/golf/<course>.json has the course's coordinates. This asks
the Overpass API for everything tagged golf within a mile and a half of
them, plus the coastline and the water, keeps what lies inside the named
golf course's own polygon (a radius that size takes in the neighbours'
holes too, and Pebble Beach has three), projects it to meters about the
course's center, rounds it to the half meter, and writes
data/golf/<course>.map.json. The renderer, elmer/coursemap.py, draws the
course from that and never touches the network; the file ships with the
program the way the card does.

The data is OpenStreetMap contributors', under the ODbL, and the file says
so; every picture drawn from it carries the credit. Run this again when
somebody has moved a bunker on OSM. It is a developer's tool, not
something a unit does.
"""
import argparse
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DATA = HERE / "data" / "golf"
OVERPASS = "https://overpass-api.de/api/interpreter"
RADIUS_M = 2200
CACHE = DATA / ".osm"          # the raw answers, kept so a re-run does not ask Overpass again
ROUND_M = 0.5

KEEP = {
    # osm golf=* value -> our layer; holes are lines with numbers and are kept apart
    "green": "greens", "tee": "tees", "bunker": "bunkers",
    "fairway": "fairways", "rough": "rough", "water_hazard": "water",
    "lateral_water_hazard": "water", "driving_range": "range",
}


def query(lat, lon):
    q = f"""[out:json][timeout:90];
(
  way["golf"](around:{RADIUS_M},{lat},{lon});
  relation["golf"](around:{RADIUS_M},{lat},{lon});
  way["leisure"="golf_course"](around:{RADIUS_M},{lat},{lon});
  relation["leisure"="golf_course"](around:{RADIUS_M},{lat},{lon});
  way["natural"="coastline"](around:{RADIUS_M},{lat},{lon});
  way["natural"="water"](around:{RADIUS_M},{lat},{lon});
  relation["natural"="water"](around:{RADIUS_M},{lat},{lon});
);
(._;>;);
out body;"""
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "ELMER golf course map (github.com/skpeterson2000/elmer)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def project(lat0, lon0):
    """Equirectangular about the course: meters east and north. A course is
    a couple of kilometers across; the error is centimeters."""
    k = 111_320.0
    cx = math.cos(math.radians(lat0))

    def to_xy(lat, lon):
        return ((lon - lon0) * k * cx, (lat - lat0) * k)
    return to_xy


def ring_xy(way, nodes, to_xy):
    pts = []
    for nid in way.get("nodes", []):
        n = nodes.get(nid)
        if n:
            pts.append(to_xy(n["lat"], n["lon"]))
    return pts


def rounded(pts):
    out = []
    for x, y in pts:
        p = (round(x / ROUND_M) * ROUND_M, round(y / ROUND_M) * ROUND_M)
        if not out or out[-1] != p:
            out.append(p)
    return out


def relation_rings(rel, ways, nodes, to_xy):
    """The outer rings of a multipolygon relation, chained from its ways."""
    outers = [ways[m["ref"]] for m in rel.get("members", [])
              if m["type"] == "way" and m.get("role", "outer") in ("outer", "") and m["ref"] in ways]
    pieces = [ring_xy(w, nodes, to_xy) for w in outers]
    pieces = [p for p in pieces if len(p) >= 2]
    rings = []
    while pieces:
        ring = pieces.pop(0)
        grown = True
        while grown and (len(ring) < 3 or ring[0] != ring[-1]):
            grown = False
            for i, p in enumerate(pieces):
                if p[0] == ring[-1]:
                    ring += p[1:]
                elif p[-1] == ring[-1]:
                    ring += list(reversed(p))[1:]
                elif p[-1] == ring[0]:
                    ring = p[:-1] + ring
                elif p[0] == ring[0]:
                    ring = list(reversed(p))[:-1] + ring
                else:
                    continue
                pieces.pop(i)
                grown = True
                break
        rings.append(ring)
    return rings


def point_in_ring(pt, ring):
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def fetch(card, refresh=False):
    """The raw Overpass answer for a course, from the cache unless asked to refresh."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{card['id']}.json"
    if path.is_file() and not refresh:
        return json.load(open(path, encoding="utf8"))
    raw = query(float(card["lat"]), float(card["lon"]))
    with open(path, "w", encoding="utf8") as f:
        json.dump(raw, f)
    return raw


def build(card, refresh=False):
    lat, lon = float(card["lat"]), float(card["lon"])
    raw = fetch(card, refresh)
    els = raw["elements"]
    nodes = {e["id"]: e for e in els if e["type"] == "node"}
    ways = {e["id"]: e for e in els if e["type"] == "way"}
    rels = [e for e in els if e["type"] == "relation"]
    to_xy = project(lat, lon)

    # The course's own outline: the golf_course polygon whose name matches
    # the card's, else the one containing the card's point.
    want = card["name"].lower()
    outline = None
    candidates = []
    for w in ways.values():
        t = w.get("tags", {})
        if t.get("leisure") == "golf_course":
            candidates.append((t.get("name", ""), ring_xy(w, nodes, to_xy)))
    for r in rels:
        t = r.get("tags", {})
        if t.get("leisure") == "golf_course":
            for ring in relation_rings(r, ways, nodes, to_xy):
                candidates.append((t.get("name", ""), ring))
    # Names differ in their last word (OSM's "Pebble Beach Golf Course", the
    # card's "Pebble Beach Golf Links"): the first two words have to agree.
    lead = " ".join(want.replace("the ", "").split()[:2])
    for name, ring in candidates:
        if name and len(ring) >= 3 and " ".join(name.lower().replace("the ", "").split()[:2]) == lead:
            outline = ring
            break
    if outline is None:
        # else the polygon the card's point is in, else the one whose middle is nearest it
        for name, ring in candidates:
            if len(ring) >= 3 and point_in_ring((0.0, 0.0), ring):
                outline = ring
                break
    if outline is None and candidates:
        outline = min((r for _n, r in candidates if len(r) >= 3), key=lambda r: math.hypot(*centroid(r)), default=None)
    inside = (lambda pts: point_in_ring(centroid(pts), outline)) if outline else (lambda pts: True)

    layers = {k: [] for k in set(KEEP.values())}
    holes = {}
    seen_hole_refs = {}

    def add(tags, pts, closed):
        g = tags.get("golf")
        if g == "hole":
            ref = tags.get("ref") or tags.get("name", "")
            try:
                n = int(str(ref).strip())
            except ValueError:
                return
            # a hole line is the course's if either end is - the 18th at Pebble
            # runs along the seawall, half of it outside the polygon
            if len(pts) >= 2 and (inside(pts) or inside(pts[:1]) or inside(pts[-1:])):
                # the longest line for a number wins: some courses map a
                # hole as two ways, tee to landing and landing to green
                length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
                if n not in seen_hole_refs or length > seen_hole_refs[n]:
                    holes[n] = pts
                    seen_hole_refs[n] = length
            return
        layer = KEEP.get(g)
        if layer is None and tags.get("natural") == "water":
            layer = "water"
        if layer and len(pts) >= 3 and inside(pts):
            layers[layer].append(pts)

    for w in ways.values():
        t = w.get("tags", {})
        if not t:
            continue
        pts = ring_xy(w, nodes, to_xy)
        add(t, pts, pts and pts[0] == pts[-1])
    for r in rels:
        t = r.get("tags", {})
        if not t or (t.get("golf") is None and t.get("natural") != "water"):
            continue
        if t.get("golf") == "hole":
            continue
        for ring in relation_rings(r, ways, nodes, to_xy):
            add(t, ring, True)

    coast = [ring_xy(w, nodes, to_xy) for w in ways.values() if w.get("tags", {}).get("natural") == "coastline"]
    coast = [c for c in coast if len(c) >= 2]

    out = {
        "course": card["id"], "name": card["name"], "lat": lat, "lon": lon,
        "units": "meters east and north of lat/lon",
        "attribution": "Map data (c) OpenStreetMap contributors, ODbL 1.0; fetched by tools/fetch_golf_map.py",
        "outline": rounded(outline) if outline else None,
        "holes": {str(n): rounded(p) for n, p in sorted(holes.items())},
        "coast": [rounded(c) for c in coast],
    }
    for k, v in layers.items():
        out[k] = [rounded(p) for p in v]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("courses", nargs="*", help="course ids, as in data/golf/<id>.json")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="ask Overpass again rather than using the cached answer")
    a = ap.parse_args()
    ids = a.courses
    if a.all:
        ids = sorted(p.stem for p in DATA.glob("*.json") if not p.stem.endswith(".map"))
    if not ids:
        ap.print_help()
        return 2
    for cid in ids:
        card = json.load(open(DATA / f"{cid}.json", encoding="utf8"))
        m = build(card, a.refresh)
        path = DATA / f"{cid}.map.json"
        with open(path, "w", encoding="utf8", newline="\n") as f:
            json.dump(m, f, separators=(",", ":"))
        counts = ", ".join(f"{len(m[k])} {k}" for k in ("greens", "tees", "bunkers", "fairways", "rough", "water", "coast") if m.get(k))
        print(f"{cid}: holes {sorted(int(n) for n in m['holes'])}; {counts}; outline {'yes' if m['outline'] else 'no'}; "
              f"{path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

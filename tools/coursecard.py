#!/usr/bin/env python3
"""Measure a golf card from GolfTraxx's hole maps.

    python3 tools/coursecard.py pebble-beach "Pebble Beach Golf Links" 93953
    python3 tools/coursecard.py pebble-beach "Pebble Beach Golf Links" 93953 --compare

GolfTraxx (https://golftraxx.com) lays a yardage book over a satellite
photo of each hole: the tee, the turning point of the line of play, the
front, centre and back of the green, and every bunker and hazard with a
flag on its near edge ("reach") and one on its far edge ("carry"), each
a latitude and longitude. This reads those eighteen pages once - the
static ones, which need no login and which the site's robots.txt allows
- keeps a copy under data/golf/.golftraxx/ so a second run reads nothing
twice, and turns the coordinates into the numbers the card plays by:
yards along the line of play and off it, the dogleg where the line
turns, the green's depth, the three pins.

What the card keeps of its own: the hole's name, its wind, its slope and
its width - GolfTraxx does not measure those - and the course's own
notes. What it gets from the measurement replaces what was written from
memory: the bend, the hazards, the green's depth. The card says where it
was checked against, and when.

Run by the author, by hand, before a release; ELMER itself fetches
nothing at play. GolfTraxx is credited in NOTICE.
"""
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "data" / "golf"
CACHE = CARDS / ".golftraxx"
PAGE = "https://golftraxx.com/hole-layout?coursename={course}&zipcode={zipcode}&hole={hole}&static=true"
UA = "ELMER/1.0 (+https://github.com/skpeterson2000/elmer; KC9SP@arrl.net)"
PAUSE = 1.5                     # seconds between pages: eighteen reads, politely
YARDS_PER_METRE = 1.0936
FAIRWAY_HALF = 18               # golf.FAIRWAY_HALF: inside it a hazard is across the hole, not beside it
BEND_LEAST = 8                  # degrees: a turn smaller than this is a straight hole


def fetch(course, zipcode, hole):
    """The hole's page, from the cache or the site."""
    CACHE.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", course.lower()).strip("-")
    path = CACHE / f"{slug}-{zipcode}-{hole}.html"
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore")
    url = PAGE.format(course=urllib.parse.quote_plus(course), zipcode=urllib.parse.quote_plus(zipcode), hole=hole)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "ignore")
    path.write_text(html, encoding="utf-8")
    time.sleep(PAUSE)
    return html


# ------------------------------------------------------------ the page

def parse(html):
    """What the page holds: the tee, the turning point, the green, the
    landmarks with both edges, the par and the yardages."""
    def var(name):
        m = re.search(rf'var {name} = "([-\d.]+)"', html)
        return float(m.group(1)) if m else None

    marks = [dict(re.findall(r'data-(\w+)="([^"]*)"', a))
             for a in re.findall(r'<div class="extraslisting"([^>]*)>', html)]
    tee = next(((float(m["reachlat"]), float(m["reachlong"])) for m in marks
                if m.get("landmarkname", "").lower().endswith("tee") and m.get("reachlat")), None)
    out = {
        "tee": tee,
        "turn": (var("ttlatitude"), var("ttlongitude")),
        "front": (var("gflatitude"), var("gflongitude")),
        "centre": (var("gclatitude"), var("gclongitude")),
        "back": (var("gblatitude"), var("gblongitude")),
        "marks": [m for m in marks if m.get("reachlat") and not m.get("landmarkname", "").lower().endswith("tee")],
    }
    m = re.search(r"Par:\s*(\d+)", html)
    out["par"] = int(m.group(1)) if m else None
    m = re.search(r"Hcp:\s*(\d+)", html)
    out["hcp"] = int(m.group(1)) if m else None
    yards = {}
    for tee_name, key in (("Pro", "pro"), ("Champ", "championship"), ("Mens", "mens"), ("Womens", "womens")):
        m = re.search(rf'{tee_name}<font size=6>\s*(?:&nbsp;)?\s*(\d+)', html)
        if m:
            yards[key] = int(m.group(1))
    out["yards"] = yards
    return out


# --------------------------------------------------------- the geometry

def xy(p, origin):
    """A point as yards east and north of the origin."""
    lat0 = math.radians(origin[0])
    return ((p[1] - origin[1]) * 111320 * math.cos(lat0) * YARDS_PER_METRE,
            (p[0] - origin[0]) * 110540 * YARDS_PER_METRE)


def line_of_play(page):
    """The legs of the line: tee to the turning point to the green's
    centre - one leg when the turn is the green, or missing."""
    tee, turn, centre = page["tee"], page["turn"], page["centre"]
    legs = []
    if (turn and turn[0] is not None and math.hypot(*xy(turn, centre)) > 20
            and math.hypot(*xy(turn, tee)) > 20):
        legs.append((tee, turn))
        legs.append((turn, centre))
    else:
        legs.append((tee, centre))
    return legs


STRAY = 70                      # yards from the line beyond which a mark is another hole's


def place(p, legs, origin):
    """Yards along the line of play and off it (right positive) for a
    point: on whichever leg it is nearest to, and how far off the line
    it is at its nearest, so a mark that belongs to another hole - the
    site's pages carry a few of those - can be left out."""
    best = None
    base = 0.0
    for a, b in legs:
        ax, ay = xy(a, origin)
        bx, by = xy(b, origin)
        px, py = xy(p, origin)
        L = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / L, (by - ay) / L
        t = (px - ax) * ux + (py - ay) * uy
        off = (px - ax) * uy - (py - ay) * ux
        tc = max(0.0, min(L, t))
        near = math.hypot(px - (ax + ux * tc), py - (ay + uy * tc))
        if best is None or near < best[0]:
            best = (near, base + tc, off)
        base += L
    return best[1], best[2], best[0]


def bend(legs, origin):
    """The dogleg: at what yards, which way, how many degrees - or None."""
    if len(legs) < 2:
        return None
    (a, b), (_b, c) = legs
    ax, ay = xy(a, origin); bx, by = xy(b, origin); cx, cy = xy(c, origin)
    h1 = math.atan2(bx - ax, by - ay)
    h2 = math.atan2(cx - bx, cy - by)
    deg = math.degrees((h2 - h1 + math.pi) % (2 * math.pi) - math.pi)   # + = clockwise = right
    if abs(deg) < BEND_LEAST:
        return None
    return {"at": int(round(math.hypot(bx - ax, by - ay))), "turn": "right" if deg > 0 else "left",
            "degrees": int(round(abs(deg)))}


# ------------------------------------------------------------- the card

WATER = ("water", "creek", "pond", "lake", "ocean", "sea", "barranca", "ditch", "burn", "river", "bay", "cove", "hazard")
ROUGH = ("tree", "rough", "oob", "out of bounds", "wall", "road", "gorse", "heather")


def kind_of(name):
    n = name.lower()
    if "bunker" in n or "trap" in n or "sand" in n:
        return "bunker"
    if any(w in n for w in WATER):
        return "water"
    if any(w in n for w in ROUGH):
        return "rough"
    return None


def words(name):
    """'1stFairwayBunker' -> 'the 1st fairway bunker'."""
    t = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name.replace("_", " ")).strip().lower()
    t = t.replace("greenside", "greenside ").replace("fair way", "fairway").replace("  ", " ").strip()
    return "the " + t if not t.startswith("the ") else t


def hazards(page, legs, origin, total, scale=1.0):
    out = []
    for m in page["marks"]:
        name = m.get("landmarkname", "")
        kind = kind_of(name)
        if kind is None:
            continue                       # "Fairway End" and the like: a number, not a hazard
        reach = (float(m["reachlat"]), float(m["reachlong"]))
        carry = (float(m["carrylat"]), float(m["carrylong"])) if m.get("carrylat") else reach
        a1, o1, n1 = place(reach, legs, origin)
        a2, o2, n2 = place(carry, legs, origin)
        if min(n1, n2) > STRAY or max(a1, a2) < 15:
            continue                       # another hole's mark, left on this page
        if "greenside" in name.lower() and max(a1, a2) < total - 80:
            continue                       # a greenside bunker nowhere near this green: the last hole's
        lo, hi = sorted((a1 * scale, a2 * scale))
        off = (o1 + o2) / 2
        label = (m.get("landmarkposition") or "").lower()
        greenside = hi >= total - 30
        if abs(off) > FAIRWAY_HALF * 0.75 or label in ("left", "right"):
            side = "left" if off < 0 else "right"
        elif greenside:
            side = "beyond" if lo > total else "front"
        else:
            side = "across" if kind == "water" else "centre"
        if label == "back" and greenside:
            side = "beyond"
        out.append({"kind": kind, "from": int(round(lo)), "to": int(round(max(hi, lo + 4))), "side": side,
                    "name": words(name) + (f", {side}" if side in ("left", "right") and "left" not in name.lower() and "right" not in name.lower() else "")})
    out.sort(key=lambda z: z["from"])
    # The site marks a few bunkers twice, once under each name; one is enough.
    kept = []
    for z in out:
        if any(k["kind"] == z["kind"] and k["side"] == z["side"] and abs(k["from"] - z["from"]) <= 6
               and abs(k["to"] - z["to"]) <= 6 for k in kept):
            continue
        kept.append(z)
    return kept


def measure(page):
    origin = page["tee"]
    legs = line_of_play(page)
    total = sum(math.hypot(xy(b, origin)[0] - xy(a, origin)[0], xy(b, origin)[1] - xy(a, origin)[1]) for a, b in legs)
    # The scorecard's yardage is the hole's number; the measured line runs
    # through the turning point and comes out a few yards longer. Every
    # measured yard is scaled to the scorecard's, so the hazards, the
    # bend and the green sit where the scorecard counts them.
    card_yards = page["yards"].get("championship") or page["yards"].get("pro") or int(round(total))
    scale = card_yards / total if total else 1.0
    front_at, _, _ = place(page["front"], legs, origin)
    back_at, _, _ = place(page["back"], legs, origin)
    centre_at, _, _ = place(page["centre"], legs, origin)
    turn = bend(legs, origin)
    if turn:
        turn["at"] = int(round(turn["at"] * scale))
    return {
        "measured_yards": int(round(total)), "yards": card_yards,
        "bend": turn,
        "green": int(round((back_at - front_at) * scale)),
        "pins": {"front": int(round((front_at - centre_at) * scale)), "back": int(round((back_at - centre_at) * scale))},
        "hazards": hazards(page, legs, origin, total, scale),
    }


def update_card(card_id, course, zipcode, compare=False):
    path = CARDS / f"{card_id}.json"
    card = json.loads(path.read_text(encoding="utf-8"))
    by_n = {h["n"]: h for h in card["holes"]}
    changed = unmeasured = 0
    for n in range(1, 19):
        html = fetch(course, zipcode, n)
        page = parse(html)
        if not page["tee"] or page["centre"][0] is None:
            print(f"  {n:2d}: the page has no tee or green - left as it was")
            continue
        got = measure(page)
        h = by_n.get(n)
        if h is None:
            print(f"  {n:2d}: not on the card")
            continue
        yards = got["yards"] if (page["yards"].get("championship") or page["yards"].get("pro")) else got["measured_yards"]
        line = (f"  {n:2d}: par {page['par'] or h['par']}, {yards} yd (measured {got['measured_yards']}), "
                f"green {got['green']} deep, bend {got['bend']}, {len(got['hazards'])} hazards")
        print(line)
        if compare:
            print("       card had:", [(z["kind"], z["from"], z["to"], z["side"]) for z in h["hazards"]])
            print("       measured:", [(z["kind"], z["from"], z["to"], z["side"], z["name"]) for z in got["hazards"]])
            continue
        if page["par"]:
            h["par"] = page["par"]
        h["yards"] = yards
        h["green"] = max(18, got["green"])
        h["pins"] = got["pins"]
        if got["bend"]:
            h["bend"] = got["bend"]
        else:
            h.pop("bend", None)
        # The site marks the sand; the ocean, a creek, a chasm it mostly
        # does not. The card's water stays where the measurement has no
        # water near it - the Pacific down the 18th is not in doubt.
        water = [z for z in h["hazards"] if z["kind"] == "water"
                 and not any(g["kind"] == "water" and abs(g["from"] - z["from"]) < 60 for g in got["hazards"])]
        if not any(kind_of(m.get("landmarkname", "")) for m in page["marks"]):
            # The site marked nothing on this hole but the tee and the green
            # - the Old Course's pages are like that - so the card's own
            # hazards stand, on the measured line.
            unmeasured += 1
        else:
            h["hazards"] = sorted(got["hazards"] + water, key=lambda z: z["from"])
        changed += 1
    if not compare:
        what = ("Doglegs, green depths and pin positions" if unmeasured == 18
                else "Hazards, doglegs, green depths and pin positions")
        card["source"] = (f"{what} measured from GolfTraxx's hole maps (https://golftraxx.com) on "
                          f"{date.today().isoformat()}; wind, slope, width and names are ELMER's own"
                          + ("; the hazards are the card's own, from published descriptions - the maps mark none here."
                             if unmeasured == 18 else
                             f"; on {unmeasured} holes the maps mark no hazards and the card's own stand." if unmeasured else "."))
        card.pop("hazards_note", None)
        path.write_text(json.dumps(card, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{changed} holes written to {path.name}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 3:
        print(__doc__)
        sys.exit(2)
    update_card(args[0], args[1], args[2], compare="--compare" in sys.argv)

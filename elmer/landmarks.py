"""Named spots inside the places people operate from, with no network.

A geocoder can find "Padre Island". It cannot find mile 55 of the beach,
because nobody has told it there is a post there - and the person standing
at that post has no bars, which is the whole reason they want to know
whether a handheld reaches the park office. So this is a small list, held
with the program, of the spots inside a handful of places that a QTH picker
and a far-end box should resolve before they ask anybody: a visitor center,
a trailhead, a summit, and the mile markers down a beach.

Two kinds of entry, and they are honest about different things. A *point*
is a fix; those marked "about" were read from a map by eye and are good to
a few hundred meters, and those not marked came from a program's own
list (SOTA publishes every summit's position). A *line* is a run of markers
laid along an arc between two fixed ends - the beach bows, so a straight
line would put mile 30 in the surf - and is good to about a mile, which is
what a post in the sand is good to and about a hundredth of anything the
radio arithmetic can tell apart.

Every spot carries the program reference of the place it is in, so a QTH
set to the summit knows it is W0D/BB-001 without being told twice.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "landmarks.json"

_loaded = None


def _grid(lat, lon):
    from . import geocode                   # geocode reads this module too
    return geocode.to_grid(lat, lon)


def _along(line, n):
    """Where marker `n` of a line falls: a fraction of the way along an arc
    from one end to the other, bowed sideways in longitude by a half sine,
    which is the shape a coast makes between two points on it."""
    f = n / float(line["miles"])
    (lat1, lon1), (lat2, lon2) = line["from"], line["to"]
    lat = lat1 + (lat2 - lat1) * f
    lon = lon1 + (lon2 - lon1) * f + line.get("bulge_lon", 0.0) * math.sin(math.pi * f)
    return round(lat, 4), round(lon, 4)


def _expand(group):
    ref = {k: group[k] for k in ("pota", "sota") if group.get(k)}
    out = []
    for point in group.get("points", []):
        out.append({"name": point["name"], "short": point["name"],
                    "aliases": list(point.get("aliases", [])),
                    "kind": point.get("kind", "landmark"),
                    "lat": point["lat"], "lon": point["lon"],
                    "about": bool(point.get("about")),
                    "landmark": group["name"], "region": group.get("region", ""),
                    **ref})
    for line in group.get("lines", []):
        for n in range(0, int(line["miles"]) + 1, int(line.get("every", 1))):
            lat, lon = _along(line, n)
            out.append({"name": line["name"].format(n=n), "short": line["name"].format(n=n),
                        "aliases": [a.format(n=n) for a in line.get("aliases", [])],
                        "kind": line.get("kind", "marker"), "lat": lat, "lon": lon,
                        "about": True, "mile": n,
                        "landmark": group["name"], "region": group.get("region", ""),
                        **ref})
    return out


def groups():
    """Every place with spots in it, as written."""
    return _load()["groups"]


def _load():
    global _loaded
    if _loaded is None:
        try:
            data = json.loads(STORE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {"groups": []}
        spots = []
        for group in data.get("groups", []):
            spots.extend(_expand(group))
        _loaded = {"groups": data.get("groups", []), "spots": spots}
    return _loaded


def spots():
    """Every resolvable spot, expanded."""
    return list(_load()["spots"])


def place(spot):
    """A spot in the shape the geocoder answers with, so the picker and the
    path tool need not know where it came from."""
    out = {"name": spot["name"] + (", " + spot["landmark"] if spot["landmark"] != spot["name"] else ""),
           "short": spot["short"], "kind": spot["kind"],
           "lat": spot["lat"], "lon": spot["lon"], "grid": _grid(spot["lat"], spot["lon"]),
           "landmark": spot["landmark"], "about": spot["about"]}
    for key in ("pota", "sota", "mile"):
        if key in spot:
            out[key] = spot[key]
    return out


def _words(text):
    return [w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split() if w]


def _score(spot, tokens):
    """How well a typed phrase fits a spot: every token must begin some word
    of the name or an alias; a token that is a whole word counts double, the
    name beats an alias, and the whole phrase beats a phrase inside a longer
    one - so "mile 5" lists mile 5 before mile 50 and "Harney Peak" finds
    the summit before the trailhead named after it."""
    best = 0
    for n, text in enumerate([spot["name"]] + spot["aliases"]):
        words = _words(text)
        score = 0
        for token in tokens:
            if token in words:
                score += 2
            elif any(w.startswith(token) for w in words):
                score += 1
            else:
                score = 0
                break
        if score:
            score += 1 if n == 0 else 0
            # the whole phrase, not a phrase inside a longer one: "Harney
            # Peak" is the summit before it is the trailhead named after it
            score += 2 if len(tokens) == len(words) else 0
            # a named spot before a marker: "padre" means the visitor
            # center before it means the fifth post down the beach
            score += 0 if "mile" in spot else 1
            best = max(best, score)
    return best


def search(query, limit=8):
    """Spots matching a typed name, best first; [] when nothing fits."""
    tokens = _words(query or "")
    if not tokens:
        return []
    scored = [(_score(s, tokens), s) for s in _load()["spots"]]
    scored = [(sc, s) for sc, s in scored if sc]
    scored.sort(key=lambda p: (-p[0], p[1].get("mile", -1), p[1]["name"]))
    return [place(s) for _, s in scored[:limit]]


def resolve(text):
    """The one spot a phrase means, or None when it is not clearly one:
    a single hit, or a hit that is a whole-word match ahead of the rest."""
    tokens = _words(text or "")
    if not tokens:
        return None
    scored = sorted(((_score(s, tokens), s) for s in _load()["spots"]),
                    key=lambda p: (-p[0], p[1].get("mile", -1)))
    scored = [(sc, s) for sc, s in scored if sc]
    if not scored:
        return None
    if len(scored) == 1 or scored[0][0] > scored[1][0]:
        return place(scored[0][1])
    return None


def group_for(ref=None, name=None):
    """The place a program reference or a name belongs to, with its spots -
    what a park card shows as "where people set up"."""
    for group in _load()["groups"]:
        if ref and ref in (group.get("pota"), group.get("sota")):
            pass
        elif name and group["name"].lower() == (name or "").lower():
            pass
        else:
            continue
        return {"name": group["name"], "region": group.get("region", ""),
                "pota": group.get("pota"), "sota": group.get("sota"),
                "about": group.get("about_lines", ""),
                "spots": [place(s) for s in _load()["spots"] if s["landmark"] == group["name"]]}
    return None

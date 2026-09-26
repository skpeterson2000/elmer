"""What the ground is like where an antenna is going up - read from the surveys.

Every antenna sits on ground, and the ground decides more than most operators
are told: how far a ground wave goes, how low a vertical fires, how many
radials are worth laying, whether a ground rod goes in at all. ELMER has always
reasoned with the ITU's standard ground types (groundwave.GROUND) and asked the
operator to pick one, and nearly everybody leaves it on "average", because
nobody knows what their ground is.

The public surveys do. Three are read here, all free and with no key:

**The soil survey** (USDA NRCS, SSURGO, through its Soil Data Access service).
One question with a latitude and longitude gets back the mapped soil at that
spot, at the scale of a field: its name, texture, how well it drains, how deep
the water table and the bedrock are, whether it floods or ponds, and how salty
it is. That is most of what decides how a soil conducts. Wet clay with water a
foot down is some of the best ground there is; excessively drained sand is
close to an insulator.

**The water nearby** (USGS National Hydrography Dataset). The sea, a bay or an
estuary within a few hundred yards turns a vertical into a different antenna,
and a marsh or a lake shore counts too.

**The lie of the land** (the elevation service the path tool already uses).
Ground that falls away in front of an antenna lowers its takeoff that way and
is worth the walk; a hollow is the opposite.

What comes out is a rating: an ITU ground type, and the pattern tools' ground
beside it, with the reasons in plain words, and the practical side - whether a
rod will go in, whether it floods, what radials will do, what winter does to
it. It is an estimate from surveys, and it says so: radio sees a meter and more
into the ground, and the soil survey describes the top couple.

**Kept for the field.** A spot rated with a signal is kept on the unit, so the
same answer is there in a field with none. A trip prepared before leaving
(trip.py) rates its destination the same way. Nothing here raises: a survey
that does not answer is recorded as missing, and a spot outside the United
States - which is where these surveys stop - is said to be unrated rather than
guessed at.
"""
import json
import logging
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import groundwave, paths, terrain

log = logging.getLogger("elmer")

CACHE = paths.STATE / "ground"
SOIL_URL = "https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest"
NHD_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/{layer}/query"
USER_AGENT = "ELMER amateur radio study assistant (ground survey)"
TIMEOUT = 30

# The hydrography layers asked, and what their feature types mean. NHD
# numbers every kind of water; these are the ones that matter to an antenna.
NHD_AREA, NHD_WATERBODY, NHD_FLOWLINE = 9, 12, 6
SALT = {445: "the sea", 312: "a bay", 493: "an estuary", 364: "a foreshore", 566: "the coast"}
MARSH = {466: "a marsh or swamp"}
LAKE = {390: "a lake or pond", 436: "a reservoir"}
STREAM = {460: "a stream or river", 336: "a canal or ditch"}
WATER_NEAR_M, WATER_WITHIN_M = 300, 1500
LAKE_MIN_KM2 = 0.02            # a farm pond is not worth a word; a lake is
LIE_RADIUS_M = 400             # how far out the lie of the land is read
LIE_FLAT_M = 3.0               # less than this either way is flat
FREEZE_LAT = 37.0              # north of this the ground freezes most winters

# The pattern tools know four grounds, the ground-wave tools eight: which of
# the four each of the eight is nearest.
PATTERN_OF = {"sea": "sea", "fresh": "good", "wet": "good", "average": "average",
              "poor": "poor", "sand": "poor", "city": "poor", "ice": "poor"}

SOIL_SQL = (
    "SELECT TOP 1 mu.muname, ma.drclassdcd, ma.brockdepmin, ma.wtdepannmin, ma.flodfreqdcd, "
    "ma.pondfreqprs, c.compname, c.comppct_r, c.drainagecl, h.hzdepb_r, h.claytotal_r, "
    "h.sandtotal_r, h.ec_r, h.om_r, t.texdesc "
    "FROM mapunit mu JOIN muaggatt ma ON ma.mukey = mu.mukey "
    "JOIN component c ON c.mukey = mu.mukey AND c.majcompflag = 'Yes' "
    "LEFT JOIN chorizon h ON h.cokey = c.cokey AND h.hzdept_r = 0 "
    "LEFT JOIN chtexturegrp t ON t.chkey = h.chkey AND t.rvindicator = 'Yes' "
    "WHERE mu.mukey IN (SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('point({lon:.6f} {lat:.6f})')) "
    "ORDER BY c.comppct_r DESC")


# ----------------------------------------------------------------- fetching

def _post_json(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _number(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def soil_at(lat, lon):
    """The mapped soil at a point, as a dict, or None where there is no
    survey. Raises on a network fault, for the caller to record."""
    got = _post_json(SOIL_URL, {"format": "JSON+COLUMNNAME", "query": SOIL_SQL.format(lat=lat, lon=lon)})
    table = got.get("Table") or []
    if len(table) < 2:
        return None
    row = dict(zip(table[0], table[1]))
    return {
        "name": row.get("muname") or "",
        "drainage": (row.get("drclassdcd") or row.get("drainagecl") or "").strip(),
        "bedrock_cm": _number(row.get("brockdepmin")),
        "water_table_cm": _number(row.get("wtdepannmin")),
        "flooding": (row.get("flodfreqdcd") or "").strip(),
        "ponding_pct": _number(row.get("pondfreqprs")),
        "texture": (row.get("texdesc") or "").strip(),
        "clay_pct": _number(row.get("claytotal_r")),
        "sand_pct": _number(row.get("sandtotal_r")),
        "salinity_ds_m": _number(row.get("ec_r")),
        "organic_pct": _number(row.get("om_r")),
        "topsoil_cm": _number(row.get("hzdepb_r")),
    }


def _water_query(layer, lat, lon, radius_m):
    url = NHD_URL.format(layer=layer) + "?" + urllib.parse.urlencode({
        "geometry": f"{lon:.6f},{lat:.6f}", "geometryType": "esriGeometryPoint", "inSR": 4326,
        "distance": radius_m, "units": "esriSRUnit_Meter", "spatialRel": "esriSpatialRelIntersects",
        # every field: the layers do not all carry the same ones, and naming
        # one a layer lacks fails the whole query
        "outFields": "*", "returnGeometry": "false", "f": "json",
        "resultRecordCount": 50})
    got = _get_json(url)
    if got.get("error"):
        raise OSError(f"hydrography said: {got['error'].get('message', got['error'])}")
    return [f.get("attributes") or {} for f in got.get("features") or []]


def water_near(lat, lon):
    """The water that matters within WATER_WITHIN_M, nearest kind first:
    {"salt"|"marsh"|"lake"|"stream": {"what", "name", "near": bool}}.
    Raises on a network fault."""
    found = {}

    def sort(rows, near):
        for a in rows:
            ft = a.get("FTYPE")
            area = _number(a.get("AREASQKM")) or 0.0
            for kind, table in (("salt", SALT), ("marsh", MARSH), ("lake", LAKE), ("stream", STREAM)):
                if ft in table and (kind != "lake" or area >= LAKE_MIN_KM2):
                    have = found.get(kind)
                    if not have or (near and not have["near"]):
                        found[kind] = {"what": table[ft], "name": a.get("GNIS_NAME") or "", "near": near}

    for layer in (NHD_AREA, NHD_WATERBODY, NHD_FLOWLINE):
        wide = _water_query(layer, lat, lon, WATER_WITHIN_M)
        if not wide:
            continue
        sort(wide, near=False)
        sort(_water_query(layer, lat, lon, WATER_NEAR_M), near=True)
    return found


def lie_of_land(lat, lon):
    """How the ground falls away round the spot: the drop to each of eight
    points LIE_RADIUS_M out, and what that says. None when there is no
    elevation to be had."""
    ring = [(lat, lon)]
    bearings = [0, 45, 90, 135, 180, 225, 270, 315]
    for b in bearings:
        d = LIE_RADIUS_M / 6371000.0
        la, lo, br = math.radians(lat), math.radians(lon), math.radians(b)
        la2 = math.asin(math.sin(la) * math.cos(d) + math.cos(la) * math.sin(d) * math.cos(br))
        lo2 = lo + math.atan2(math.sin(br) * math.sin(d) * math.cos(la), math.cos(d) - math.sin(la) * math.sin(la2))
        ring.append((math.degrees(la2), math.degrees(lo2)))
    heights = terrain.points(ring)
    if not heights or len(heights) != len(ring):
        return None
    here = heights[0]
    drops = {name: round(here - h, 1) for name, h in zip(("N", "NE", "E", "SE", "S", "SW", "W", "NW"), heights[1:])}
    falls = [k for k, v in drops.items() if v >= LIE_FLAT_M]
    rises = [k for k, v in drops.items() if v <= -LIE_FLAT_M]
    steepest = max(drops, key=drops.get)
    if len(falls) >= 7:
        says = "a rise: the ground falls away all round - low takeoff every way"
    elif len(rises) >= 7:
        says = "a hollow: the ground rises all round, and holds the takeoff up"
    elif not falls and not rises:
        says = "flat all round"
    elif falls:
        says = (f"falls away to the {', '.join(falls)} - {drops[steepest]:g} m in {LIE_RADIUS_M} m to the "
                f"{steepest}: a lower takeoff that way")
    else:
        says = f"rises to the {', '.join(rises)} - the takeoff is held up that way"
    return {"elevation_m": round(here, 1), "drops_m": drops, "falls": falls, "rises": rises, "says": says}


# ------------------------------------------------------------------- rating

def _drainage(s):
    return (s or "").lower()


def rate(soil, water, lie, lat=None):
    """The ground, from what the surveys said. Pure: no network, no disk.

    Returns {"ground", "label", "pattern", "sigma", "epsilon", "headline",
    "why": [...], "practical": [...]}; "ground" is None when there was no
    soil survey to read."""
    why, practical = [], []
    water = water or {}
    if not soil:
        return {"ground": None, "label": "Unrated", "pattern": None, "sigma": None, "epsilon": None,
                "headline": "No soil survey here - the surveys ELMER reads cover the United States. "
                            "Choose the ground by hand.",
                "why": [], "practical": []}
    name = soil["name"].lower()
    drain = _drainage(soil["drainage"])
    wt, rock = soil["water_table_cm"], soil["bedrock_cm"]
    sand, clay, salt = soil["sand_pct"], soil["clay_pct"], soil["salinity_ds_m"]

    if name == "water" or name.startswith("water,") or name.startswith("water "):
        kind = "sea" if "salt" in water and water["salt"]["near"] else "fresh"
        why.append("The spot is mapped as open water.")
    elif "urban land" in name or name.startswith(("pits", "dumps", "made land", "udorthents")):
        kind = "city"
        why.append(f"Mapped as {soil['name']} - built on or made ground, not a natural soil.")
    elif "rock outcrop" in name or (rock is not None and rock <= 50):
        kind = "poor"
        why.append("Rock at or near the surface" + (f" - bedrock about {round(rock / 2.54)} in down." if rock is not None else "."))
    elif drain in ("very poorly drained", "poorly drained") or (wt is not None and wt <= 30):
        kind = "wet"
        why.append(f"{soil['drainage'] or 'Wet'}" + (f", with the water table about {round(wt / 2.54)} in down at its highest" if wt is not None else "") + ".")
    elif drain in ("excessively drained", "somewhat excessively drained") or (sand is not None and sand >= 85):
        kind = "sand"
        why.append(f"{soil['drainage'] or 'Sandy'} - {round(sand)}% sand at the surface." if sand is not None else f"{soil['drainage']}.")
    elif sand is not None and sand >= 65:
        kind = "poor"
        why.append(f"Sandy - {round(sand)}% sand at the surface, and it drains.")
    else:
        kind = "average"
        why.append(f"{soil['drainage'] or 'A'} {soil['texture'].lower() or 'soil'} - ordinary ground.".replace("  ", " "))
    if soil["texture"]:
        why.append(f"Topsoil: {soil['texture'].lower()}" + (f", {round(clay)}% clay" if clay is not None else "") + ".")
    if salt is not None and salt >= 4 and kind in ("average", "poor", "wet"):
        kind = "wet"
        why.append(f"Salty soil ({salt:g} dS/m) - salt water in the ground conducts, and lifts it to the best of the ordinary grounds.")

    for key in ("salt", "marsh", "lake"):
        w = water.get(key)
        if not w:
            continue
        where = "beside it" if w["near"] else "within a mile"
        named = f" ({w['name']})" if w["name"] else ""
        if key == "salt":
            why.append(f"Salt water {where}: {w['what']}{named}. A vertical near the sea is a different antenna - "
                       f"the sea is the best ground there is, and it lowers the takeoff toward it.")
        elif key == "marsh":
            why.append(f"A marsh {where}{named} - wet ground at its best.")
        else:
            why.append(f"{w['what'][0].upper()}{w['what'][1:]} {where}{named}. Fresh water reflects well but conducts poorly - "
                       f"it is not the sea.")

    g = groundwave.GROUND[kind]
    # The practical side: the rod, the radials, the water, the winter.
    if rock is not None and rock <= 100:
        practical.append(f"Ground rod: rock about {round(rock / 2.54)} in down - a full 8 ft rod will not go in. "
                         f"Lay radials or a counterpoise instead.")
    elif clay is not None and clay >= 35:
        practical.append("Ground rod: heavy clay - hard driving when it is dry, easy after rain, and it holds well.")
    elif sand is not None and sand >= 65:
        practical.append("Ground rod: sand drives easily and holds poorly, and a rod in dry sand is barely grounded.")
    else:
        practical.append("Ground rod: no rock in the survey to stop it.")
    if kind in ("sand", "poor", "city"):
        practical.append("Radials: they matter most on ground like this - lay as many as you can.")
    elif kind in ("wet", "sea"):
        practical.append("Radials: the ground is doing much of the work - a handful on the surface goes a long way.")
    else:
        practical.append("Radials: ordinary ground - the usual advice holds, and more is better up to a few dozen.")
    flood = (soil["flooding"] or "").lower()
    if flood and flood not in ("none", "very rare"):
        practical.append(f"Flooding: {flood} - check before leaving gear out.")
    if (soil["ponding_pct"] or 0) >= 50:
        practical.append("Water stands on this ground in most years - wet feet, and a wet feed line connector.")
    if lat is not None and abs(lat) >= FREEZE_LAT and kind not in ("sea", "city"):
        practical.append("Winter: this ground freezes, and frozen ground conducts far worse than the same ground "
                         "thawed - a winter ground wave is shorter.")

    headline = g["note"]          # the label is said beside it; this is the why
    return {"ground": kind, "label": g["label"], "pattern": PATTERN_OF.get(kind, "average"),
            "sigma": g["sigma"], "epsilon": g["epsilon"], "headline": headline,
            "why": why, "practical": practical}


# ------------------------------------------------------------ keeping it

def _key(lat, lon):
    return f"{lat:.4f}_{lon:.4f}.json"


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("ground survey: could not read %s: %s", path.name, exc)
        return None


def cached(lat, lon):
    path = CACHE / _key(lat, lon)
    return _read(path) if path.is_file() else None


def survey(lat, lon, name="", refresh=False):
    """Rate the ground at a point, from the surveys or from what was kept.

    A spot rated before is answered from the unit unless `refresh` is asked
    for - which is what makes it work in a field with no signal. Never
    raises; what could not be fetched is listed under "missing"."""
    lat, lon = round(float(lat), 4), round(float(lon), 4)
    kept = cached(lat, lon)
    if kept and not refresh:
        kept["kept"] = True
        if name and not kept.get("name"):
            kept["name"] = name
        return kept
    missing = []
    soil = water = lie = None
    try:
        soil = soil_at(lat, lon)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("ground survey: soil survey did not answer for %.4f,%.4f: %s", lat, lon, exc)
        missing.append(f"the soil survey did not answer ({type(exc).__name__})")
    try:
        water = water_near(lat, lon)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("ground survey: hydrography did not answer for %.4f,%.4f: %s", lat, lon, exc)
        missing.append(f"the water survey did not answer ({type(exc).__name__})")
    lie = lie_of_land(lat, lon)
    if lie is None:
        missing.append("the elevation service did not answer - the lie of the land is unknown")
    if soil is None and water is None and lie is None:
        if kept:                                  # a refresh that failed keeps what there was
            kept.update({"kept": True, "refresh_failed": missing})
            return kept
        return {"ok": False, "lat": lat, "lon": lon, "name": name, "missing": missing,
                "error": "nothing could be fetched - no network?" if missing else "no survey covers this spot"}
    out = {"ok": True, "lat": lat, "lon": lon, "name": name or (kept or {}).get("name", ""),
           "rated": time.time(), "estimate": True, "kept": False, "missing": missing,
           **rate(soil, water, lie, lat), "lie": lie, "soil": soil, "water": water,
           "sources": {"soil": "USDA NRCS soil survey (SSURGO)", "water": "USGS National Hydrography Dataset",
                       "lie": "SRTM 30 m elevation"}}
    if soil is None and "the soil survey did not answer" not in " ".join(missing):
        out["missing"].append("no soil survey covers this spot")
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        (CACHE / _key(lat, lon)).write_text(json.dumps(out), encoding="utf-8")
    except OSError as exc:
        log.warning("ground survey: could not keep the rating for %.4f,%.4f: %s", lat, lon, exc)
    log.info("ground survey: %s at %.4f,%.4f%s - %s", out.get("ground") or "unrated", lat, lon,
             f" ({name})" if name else "", "; ".join(missing) or "all surveys answered")
    return out


def kept_spots():
    """Every spot rated on this unit, newest first - what is to hand offline."""
    if not CACHE.is_dir():
        return []
    rows = []
    for path in CACHE.glob("*.json"):
        r = _read(path)
        if r and r.get("ok"):
            rows.append({k: r.get(k) for k in ("name", "lat", "lon", "ground", "label", "rated")})
    rows.sort(key=lambda r: -(r.get("rated") or 0))
    return rows

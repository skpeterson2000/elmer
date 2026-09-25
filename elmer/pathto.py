"""Reaching a particular place: the path from here to there, and how.

The Make Contact page answers "what can I do from here?" - and most real
needs have a destination: a relative's town, the net's location, the club
across the state. This is the other half. Given where the operator stands
and where they are trying to reach, it says how far and which way, whether
either end is in the dark, whether two antennas could see each other (and
past about fifty miles they never can), which bands the ionosphere would
carry it on right now, and then the approach an Elmer would suggest: the
band, the mode, which way to hang the wire, and when to try if not now.

Radio is a science because this can be worked out, at least somewhat, and
an art because some do it better than others; the words here stay measured
- "carries it by one hop right now" is what the numbers say, and "a chance
after dark" is what they do not. Nothing here fetches anything the rest of
ELMER does not already fetch: the ionosphere from the propagation snapshot,
the ground from the terrain cache, the far end from the FCC record or the
gazetteer.
"""
import math
import re

from . import bandplan, callsign, geocode, linkbudget, propagation, reachout, terrain, units

# Past this a path is the ionosphere's, whatever the antennas: the radio
# horizon from a hundred feet up is about thirty miles, and nobody is asking
# this page from a mountain top with a tower.
SIGHT_KM = 80.0
# Two antennas at about head height, which is what somebody standing there has.
ANTENNA_M = 3.0
# 4/3-earth radius, for the bulge in the middle of a line of sight.
EARTH_KM = 8495.0

# A callsign has the shape prefix-digit-suffix; a grid square does not.
RE_CALLSIGN = re.compile(r"^[A-Z0-9]{1,2}\d[A-Z]{1,4}$")

# 47 CFR 97.301: what a class may key up on HF. Technician has phone on 10 m
# and CW only on three others; General and above have every band (with
# segments this page does not go into).
TECH_BANDS = {"10m": "SSB 28.300-28.500", "15m": "CW only", "40m": "CW only", "80m": "CW only",
              "6m": "all modes"}
# What each band is good for, in a phrase - the Elmer's shorthand.
BAND_MODE = {
    "160m": "CW or FT8 after dark; SSB when it is quiet",
    "80m": "SSB 3.800-4.000 in the evening, FT8 on 3.573",
    "60m": "USB on the channels, 100 W ERP",
    "40m": "SSB above 7.125, FT8 on 7.074, CW low in the band",
    "30m": "FT8 on 10.136 or CW - no phone on 30 m",
    "20m": "SSB 14.150-14.350, FT8 on 14.074",
    "17m": "SSB 18.110-18.168, FT8 on 18.100",
    "15m": "SSB 21.200-21.450, FT8 on 21.074",
    "12m": "SSB 24.930-24.990, FT8 on 24.915",
    "10m": "SSB 28.300-28.500, FT8 on 28.074",
    "6m": "SSB 50.125 calling, FT8 on 50.313",
}


def resolve_to(text):
    """The far end: a callsign (the FCC record has its grid), a grid square,
    a lat,lon, or a place name. None if nothing can be made of it."""
    text = (text or "").strip()
    if not text:
        return None
    # A grid square or a pair of coordinates first: neither costs a lookup,
    # and a grid like EN26 would pass for a callsign otherwise.
    place = geocode.resolve(text, allow_lookup=False)
    if place and place.get("lat") is not None:
        return place
    call = callsign.normalise(text)
    if RE_CALLSIGN.match(call):
        rec = callsign.lookup(call)
        if rec and rec.get("found") and rec.get("lat") is None and rec.get("place"):
            # The FCC's file has the town and not a coordinate; the bundled
            # places usually have the town.
            town = geocode.resolve(rec["place"])
            if town and town.get("lat") is not None:
                rec = dict(rec, lat=town["lat"], lon=town["lon"], grid=town.get("grid"))
        if rec and rec.get("found") and rec.get("lat") is not None:
            return {"name": rec["callsign"], "short": rec["callsign"], "kind": "callsign",
                    "lat": rec["lat"], "lon": rec["lon"],
                    "grid": rec.get("grid") or geocode.to_grid(rec["lat"], rec["lon"]),
                    "license_class": rec.get("license_class")}
        if rec and rec.get("found") is False:
            return {"error": f"no current FCC record for {call}"}
    place = geocode.resolve(text)
    if place and place.get("lat") is not None:
        return place
    return None


def _sight(lat1, lon1, lat2, lon2, km, unit=units.DEFAULT):
    """Whether two head-high antennas could see each other over the ground,
    from the terrain cache where it has the path, else smooth earth."""
    horizon = 4.12 * (math.sqrt(ANTENNA_M) + math.sqrt(ANTENNA_M))    # km, 4/3 earth
    out = {"km": round(km, 1), "horizon_km": round(horizon, 1), "terrain": False}
    if km > SIGHT_KM:
        out["verdict"] = "far past any line of sight - this one is the ionosphere's"
        out["clear"] = False
        return out
    prof = None
    try:
        prof = terrain.profile(lat1, lon1, lat2, lon2, samples=60)
    except Exception:
        prof = None
    if not prof or not prof.get("points"):
        out["clear"] = km <= horizon
        out["verdict"] = (f"within the radio horizon of two head-high antennas ({units.say(horizon, unit)}) over "
                          f"smooth earth" if out["clear"] else
                          f"beyond the radio horizon of head-high antennas ({units.say(horizon, unit)}); height at "
                          f"either end, or a repeater between, is what gets it through")
        return out
    pts = prof["points"]
    a = pts[0]["elevation"] + ANTENNA_M
    b = pts[-1]["elevation"] + ANTENNA_M
    worst = None
    for p in pts[1:-1]:
        d1 = p["km"]
        d2 = km - d1
        line = a + (b - a) * (d1 / km) - (d1 * d2) / (2 * EARTH_KM) * 1000.0
        over = p["elevation"] - line
        if worst is None or over > worst[0]:
            worst = (over, d1, p["elevation"])
    out["terrain"] = True
    out["source"] = prof.get("source")
    if worst is None or worst[0] <= 0:
        out["clear"] = True
        out["verdict"] = "the ground clears between them - a simplex path, line of sight"
    else:
        out["clear"] = False
        out["blocked_km"] = round(worst[1], 1)
        out["blocked_m"] = round(worst[0])
        out["verdict"] = (f"ground in the way {units.say(worst[1], unit)} along, about {units.say_len(worst[0], unit)} above the "
                          f"line - a repeater or height at one end is what gets past it")
    return out


def _allowed(band, license):
    rank = reachout._class_rank(license)
    # CB is a license-free service, so 11 m is on the list for everybody -
    # with a certified CB radio, which is the condition, not the class.
    if band == "11m":
        return True, "CB: SSB on channels 36-40 (38 LSB to call), 12 W PEP, any certified CB radio"
    if rank < 0:
        return False, "needs an amateur license"
    if rank >= bandplan.CLASS_RANK.get("General", 2):
        return True, BAND_MODE.get(band, "")
    if band in TECH_BANDS:
        return True, TECH_BANDS[band]
    return False, "not a Technician band"


def _antenna_note(how, bearing):
    if how in ("straight up and back",):
        return ("a dipole low - a fifth of a wave up or less - fires straight up and comes "
                "down where you want; height would only send it past them")
    if how == "ground wave":
        return "a vertical, and the best ground you can give it"
    return (f"hang a dipole broadside to {bearing:.0f} degrees - the wire running "
            f"{(bearing + 90) % 360:.0f}/{(bearing + 270) % 360:.0f} - as high as you can; "
            f"a vertical is the second choice, and a fair one for the low angle")


# Line of sight for a personal radio: two handhelds at head height see each
# other about this far over flat ground - FRS, MURS, GMRS simplex.
PERSONAL_SIGHT_KM = 8.0


def ladder(km, sight, sky, license=None, unit=units.DEFAULT):
    """The same path, asked three ways: with no license, as a Technician,
    as a General - each with the radio that class would have in hand, not
    the gear ticked. Put side by side so the distance between the rungs
    is visible: what a Technician can do that an unlicensed person cannot,
    and what a General can that a Technician cannot. The carrot, if it is
    one; the numbers either way."""
    works = [r for r in sky["bands"] if r["works"]]
    works.sort(key=lambda r: ((r.get("hops") or 1), -(r.get("score") or 0)))
    near = km <= SIGHT_KM
    clear = bool(sight.get("clear"))
    if near:
        # Across town HF is ground wave or straight up, and two bands say
        # it; ten would be a list of bands that happen to reach.
        works = [r for r in works if r["how"] in ("ground wave", "straight up and back") or r["band"] == "11m"]

    def hf_ways(rank_name):
        out = []
        for r in works:
            if r["band"] == "11m":
                continue
            ok, mode = _allowed(r["band"], rank_name)
            if ok:
                out.append({"band": r["band"], "how": r["how"], "mode": mode,
                            "odds": "good" if (r.get("hops") or 1) == 1 and (r.get("score") or 50) >= 50
                            else "worth trying" if (r.get("hops") or 1) <= 2 else "long shot"})
            if near and len(out) >= 2:
                break
        return out

    # No license: FRS, MURS, GMRS simplex only by line of sight, a few
    # miles; a GMRS repeater within reach of both ends past that, if there
    # is one; CB on 11 m by ground wave or skip when the sky says so.
    none = []
    if km <= PERSONAL_SIGHT_KM and clear:
        none.append({"band": "FRS / GMRS / MURS", "how": "line of sight", "odds": "good"})
    elif near:
        none.append({"band": "GMRS", "how": "a repeater covering both ends, if one exists", "odds": "worth trying"})
    cb = next((r for r in works if r["band"] == "11m"), None)
    if cb:
        none.append({"band": "11 m (CB)", "how": cb["how"], "odds": "worth trying" if (cb.get("hops") or 1) <= 2 else "long shot"})
    elif km <= 20:
        none.append({"band": "11 m (CB)", "how": "ground wave", "odds": "worth trying"})

    # Technician: 2 m / 70 cm by sight or by repeater; 6 m and 10 m when
    # open; CW on 40, 15 and 80 m - the code, not a rig, is the limit.
    tech = []
    if clear:
        tech.append({"band": "2 m / 70 cm", "how": "line of sight", "odds": "good"})
    elif near:
        tech.append({"band": "2 m / 70 cm", "how": "by repeater", "odds": "worth trying"})
    tech += hf_ways("Technician")

    general = []
    if clear:
        general.append({"band": "2 m / 70 cm", "how": "line of sight", "odds": "good"})
    elif near:
        general.append({"band": "2 m / 70 cm", "how": "by repeater", "odds": "worth trying"})
    general += hf_ways("General")

    def words(ways, who):
        if not ways:
            far = units.say(km, unit)
            return {"none": f"nothing reaches {far} without a license right now",
                    "Technician": f"nothing on a Technician's bands carries {far} right now",
                    "General": f"no band carries {far} by the numbers right now"}[who]
        good = [w for w in ways if w["odds"] == "good"]
        return (f"{len(ways)} way{'s' if len(ways) != 1 else ''}, {len(good)} of them good"
                if good else f"{len(ways)} way{'s' if len(ways) != 1 else ''} worth trying, none certain")

    # Reaching somebody is two-way or it is nothing: 97.113(b) forbids the
    # one-way call, and a station that can be heard but cannot answer has
    # not been reached. So each rung says what the far end needs as well.
    rungs = [
        {"key": "none", "label": "No license", "radio": "an FRS, GMRS, MURS or CB radio", "ways": none, "verdict": words(none, "none"),
         "far_end": "the same kind of radio at the far end - FRS to FRS, CB to CB; no license either side"},
        {"key": "Technician", "label": "Technician", "radio": "a 2 m handheld, a 10 m or 6 m rig, and the code on 40 m",
         "ways": tech, "verdict": words(tech, "Technician"),
         "far_end": "an amateur at the far end, licensed for that band - a General there can meet you on 2 m or 10 m; you cannot meet them on 20 m"},
        {"key": "General", "label": "General and above", "radio": "an HF rig on every band", "ways": general,
         "verdict": words(general, "General"),
         "far_end": "an amateur at the far end with a rig for that band - and if they hold a Technician license, only the bands they may answer on"},
    ]
    # The distance between the rungs, in one sentence each way.
    step_up = []
    if len(tech) > len(none):
        step_up.append(f"a Technician license opens {len(tech) - len(none)} more way{'s' if len(tech) - len(none) != 1 else ''} to reach there than no license")
    elif not tech and not none:
        step_up.append("neither no license nor Technician reaches there right now")
    if len(general) > len(tech):
        step_up.append(f"General opens {len(general) - len(tech)} more than Technician - the HF bands that carry {units.say(km, unit)} at this hour")
    elif tech and len(general) == len(tech):
        step_up.append("right now General adds nothing a Technician has not got - the hour, not the license, is the limit")
    you = (license or "").strip()
    return {"rungs": rungs, "step": step_up,
            "two_way": ("Reaching them is two-way or it is nothing - a one-way transmission is forbidden on the amateur bands "
                        "(97.113(b)), and a station that can hear you but cannot answer has not been reached. "
                        "Each column needs its far end too."),
            "yours": you if you in ("none", "Technician", "General") else
            ("General" if reachout._class_rank(you) >= bandplan.CLASS_RANK.get("General", 2) else you)}


# The bands this panel will answer for, in the order a band list runs. The
# four at the top are the line-of-sight ones, worked as a link budget along
# the ground; the rest are the ionosphere's, and are answered by the sky
# rather than by the terrain.
#
# The list used to be the four alone, so a selector that started at 6 m and
# offered nothing below it read as a tool that had given up - and the HF
# answer, which this program computes in full, was in a different panel that
# nobody had been pointed at. Asking about 20 m gets the ionosphere's answer
# now, and says that is what it is.
SKY_BANDS = ("160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "11m", "10m")


def _band_choices(ground):
    """Every band this panel answers for, the line-of-sight ones first.

    `ground` is the link budget's own list, which is the four bands it can
    work along the terrain. The sky's bands follow, marked, so the page can
    say which kind of answer a choice will get before it is made.
    """
    out = [dict(row, kind="ground") for row in (ground or [])]
    out += [{"key": key, "label": key.replace("m", " m"), "kind": "sky"}
            for key in SKY_BANDS]
    return out


def _sky_link(here, there, band, watts=100.0, mode="ssb", site="residential"):
    """The ionosphere's answer for one band on this path, and then the
    budget's.

    On these bands the ground between the two stations is not the path, so
    the first thing measured is the sky at the midpoint of it: the critical
    frequency there, the MUF along the path, whether this band comes back at
    all, and in how many hops. The same reading the rest of the page runs
    on, asked one band at a time. Then, for a band that does come back, what
    these watts in this mode put at the far end against what it needs -
    which is the part five watts and a kilowatt disagree about.
    """
    km, bearing = terrain.great_circle(here["lat"], here["lon"], there["lat"], there["lon"])
    # The same midpoint the panel above reads at. Two panels on one page
    # disagreeing about the sky over the same path is the kind of thing this
    # program has been caught doing before.
    mid_lat = (here["lat"] + there["lat"]) / 2.0
    mid_lon = (here["lon"] + there["lon"]) / 2.0
    snap = propagation.snapshot(lat=mid_lat, lon=mid_lon)
    sky = propagation.path_bands(
        km, fof2=snap.get("fof2"), hmf2=snap.get("hmf2") or propagation.HMF2_DEFAULT,
        elevation=snap.get("elevation") or 0.0, k_index=snap.get("k_index") or 2.0,
        muf=snap.get("muf"), watts=watts, emission=mode, site=site)
    row = next((r for r in sky["bands"] if r["band"] == band), None)
    return {
        "kind": "sky", "band": band, "km": round(km), "miles": round(km * 0.621371),
        "bearing": round(bearing),
        "works": bool(row and row["works"]),
        "sky": bool(row and row.get("sky")),
        "how": (row or {}).get("how"),
        "hops": (row or {}).get("hops"),
        "score": (row or {}).get("score"),
        "label": (row or {}).get("label"),
        "why": (row or {}).get("why"),
        "budget": (row or {}).get("budget"),
        "watts": (row or {}).get("watts"), "emission": (row or {}).get("emission"),
        "site": site,
        # The MUF is the snapshot's, the same as the panel above reads:
        # path_bands returns the critical frequency and not the maximum
        # usable one.
        "fof2": sky.get("fof2"), "muf": snap.get("muf"),
        "one_hop_km": sky.get("one_hop_km"),
        "read_at": sky.get("read_at"),
        "bands": _band_choices(None) if False else None,   # filled by link()
        "to": {"short": there.get("short") or there.get("name"), "grid": there.get("grid")},
    }


def link(here, there, band="2m", mode="fm", radio_here="ht", radio_there=None, site="residential",
         watts=100.0):
    """The same path by the numbers: a link budget along the ground on the
    bands that travel along it, and the ionosphere's own verdict on the
    bands that do not.

    The sight test says whether the ground clears; the budget says what the
    ground costs and whether these two radios have it to spend. Neither
    question means anything on 20 m over a thousand miles - the signal goes
    up and comes back, and the numbers that matter are the critical
    frequency, the MUF along the path and how many hops it takes.
    """
    if band in SKY_BANDS:
        # FM is the VHF page's default and is not an HF mode below 10 m; a
        # sky band asked about in FM is asked about in SSB, or the budget
        # would charge FM's 12 kHz against a band nobody runs it on.
        if mode == "fm":
            mode = "ssb"
        out = _sky_link(here, there, band, watts=watts, mode=mode, site=site)
        out["bands"] = _band_choices(linkbudget.for_bands()
                                     if hasattr(linkbudget, "for_bands") else None)
        return out
    km, bearing = terrain.great_circle(here["lat"], here["lon"], there["lat"], there["lon"])
    out = linkbudget.for_path(here, there, km, band=band, mode=mode, radio_here=radio_here,
                              radio_there=radio_there, site=site)
    out["bearing"] = round(bearing)
    out["bands"] = _band_choices(out.get("bands"))
    out["to"] = {"short": there.get("short") or there.get("name"), "grid": there.get("grid")}
    return out


def predict(here, there, gear=(), license="Technician", watts=100.0, now=None,
            unit=units.DEFAULT):
    """The path and the approach. `here` and `there` are place dicts with
    lat/lon; the ionosphere is read at the midpoint, which is where a
    one-hop path is reflected.

    `unit` is the operator's own - see units.py, whose whole subject is that a
    distance across the ground answers "how far is that" and belongs to the
    person reading it, while the band names do not. This page said 2448 km to
    an operator who had asked for miles, in the same sentence as 20 m and
    40 m, which are not a measurement of anything on this path.
    """
    km, bearing = terrain.great_circle(here["lat"], here["lon"], there["lat"], there["lon"])
    back = (bearing + 180.0) % 360.0
    mid_lat = (here["lat"] + there["lat"]) / 2.0
    mid_lon = (here["lon"] + there["lon"]) / 2.0
    sun_here = reachout.sun_state(here["lat"], here["lon"], now)
    sun_there = reachout.sun_state(there["lat"], there["lon"], now)
    sight = _sight(here["lat"], here["lon"], there["lat"], there["lon"], km, unit)
    snap = propagation.snapshot(lat=mid_lat, lon=mid_lon)
    sky = propagation.path_bands(
        km, fof2=snap.get("fof2"), hmf2=snap.get("hmf2") or propagation.HMF2_DEFAULT,
        elevation=snap.get("elevation") or 0.0, k_index=snap.get("k_index") or 2.0,
        muf=snap.get("muf"), watts=watts, unit=unit)

    has_hf = reachout._has_hf(gear)
    has_vhf = reachout._vhf(gear)
    approach = []
    if sight.get("clear") and has_vhf:
        approach.append({"band": "2 m / 70 cm", "how": "line of sight", "odds": "good",
                         "mode": "FM simplex - 146.520 to call, then move off",
                         "antenna": "anything vertical, held high and in the clear",
                         "why": sight["verdict"]})
    elif km <= SIGHT_KM and has_vhf:
        approach.append({"band": "2 m / 70 cm", "how": "by repeater", "odds": "worth trying",
                         "mode": "a repeater that covers both ends - the list below has the ones in range here",
                         "antenna": "vertical, high as you can hold it",
                         "why": sight["verdict"]})
    if has_hf:
        rows = [r for r in sky["bands"] if r["works"]]
        if km <= SIGHT_KM:
            # Across town, HF is ground wave or straight up; the rest of the
            # list would be bands that happen to reach, not the way to go.
            rows = [r for r in rows if r["how"] in ("ground wave", "straight up and back")][:2]
        # Best first: fewer hops, then the band's own rating, then the
        # nearest to the middle of HF - the middle bands are the easy ones.
        # Best first: the most in hand at these watts, then fewer hops, then
        # the band's own rating - the margin is the thing power moves.
        rows.sort(key=lambda r: (-((r.get("budget") or {}).get("margin_db") or 0.0),
                                 (r.get("hops") or 1), -(r.get("score") or 0)))
        for r in rows:
            ok, mode = _allowed(r["band"], license)
            if not ok:
                continue
            b = r.get("budget") or {}
            # The odds are the margin's where there is one - the thing power
            # moves - and the geometry's where the path is ground wave.
            if b:
                odds = ("good" if b["verdict"] == "solid"
                        else "worth trying" if b["verdict"] == "workable" else "long shot")
                why = (f"carries {units.say(km, unit)} by {r['how']}; at {b['watts']:g} W {b['emission'].upper()} "
                       f"it arrives {b['margin_db']:+.0f} dB against what the far end needs")
            else:
                odds = ("good" if (r.get("hops") or 1) == 1 and (r.get("score") or 50) >= 50
                        else "worth trying" if (r.get("hops") or 1) <= 2 else "long shot")
                why = r.get("cost") or f"carries {units.say(km, unit)} by {r['how']} right now"
            approach.append({"band": r["band"], "how": r["how"], "odds": odds, "mode": mode,
                             "antenna": _antenna_note(r["how"], bearing),
                             "why": why, "margin_db": b.get("margin_db")})
        # Bands the sky carries and these watts do not: worth a line, because
        # the fix is an amplifier or a narrower mode and not a different day.
        short = [r for r in sky["bands"] if r.get("sky") and not r["works"]
                 and _allowed(r["band"], license)[0]]
        for r in short[:2]:
            b = r["budget"]
            fix = (f"about {b['watts_for']:.0f} W would do, or a mode that hears deeper - CW, or FT8"
                   if b.get("legal") else
                   ("wait for dark - the D layer has it by day" if b.get("daylight")
                    else "a mode that hears deeper - CW, or FT8"))
            approach.append({"band": r["band"], "how": r["how"], "odds": "not at this power",
                             "mode": fix,
                             "antenna": _antenna_note(r["how"], bearing),
                             "why": r.get("why"), "margin_db": b.get("margin_db")})
        if not rows:
            reasons = [r for r in sky["bands"] if r.get("why")]
            approach.append({"band": "HF", "how": None, "odds": "long shot",
                             "mode": "FT8 - it hears what SSB cannot",
                             "antenna": _antenna_note("one hop", bearing),
                             "why": (reasons[0]["why"] if reasons else
                                     "no band carries it by the numbers just now")})
    if not has_hf and km > SIGHT_KM:
        # A handheld does not carry a hundred miles on its own, and saying
        # "tick something" to somebody who has nothing else is no help. The
        # ways are a linked system near here, or HF - and which HF band
        # would do it, in case one can be borrowed.
        would = [r["band"] for r in sky["bands"] if r["works"] and _allowed(r["band"], license)[0]]
        approach.append({"band": "VHF/UHF, by a linked system", "how": "repeaters that link", "odds": "worth trying",
                         "mode": ("a linked repeater system, or a repeater with an EchoLink or IRLP node, "
                                  "near here - the list below names the machines in range; ask on one "
                                  "whether it links toward " + (there.get("short") or "there")),
                         "antenna": "vertical, high as you can hold it",
                         "why": f"{units.say(km, unit)} is far past what a handheld reaches on its own"})
        approach.append({"band": ", ".join(would) if would else "HF", "how": "the ionosphere", "odds": "good" if would else "long shot",
                         "mode": ("what would carry it right now, if an HF radio can be borrowed - tick "
                                  "HF above and this fills in" if would else
                                  "an HF radio, and a better hour - tick HF above and this fills in"),
                         "antenna": "", "why": ""})
    if not approach:
        approach.append({"band": None, "how": None, "odds": "the rule",
                         "mode": "tick what you have above - the approach depends on it",
                         "antenna": "", "why": ""})

    # When, if not now. The low bands want dark at both ends; the high ones
    # want light. Said as the state of the two ends, which is what changes.
    when = None
    dark = [s for s in (sun_here, sun_there) if s == "dark"]
    if km > SIGHT_KM:
        if len(dark) == 1:
            when = ("one end is in daylight and the other in the dark: the low bands are "
                    "half open and the high ones half shut - the hour when both ends are "
                    "in the same light is easier, either way")
        elif len(dark) == 2:
            when = "both ends in the dark: 80 m and 40 m are the bands of this hour, 20 m and up have gone quiet"
        elif sun_here == "gray" or sun_there == "gray":
            when = "on the gray line at one end - the hour the low bands carry furthest; it is short"
        else:
            when = "both ends in daylight: 20 m, 17 m and 15 m are the bands of this hour; 40 m after dark"

    return {
        "from": {"short": here.get("short") or here.get("grid"), "grid": here.get("grid"),
                 "sun": sun_here},
        "to": {"short": there.get("short") or there.get("name"), "grid": there.get("grid"),
               "kind": there.get("kind"), "sun": sun_there,
               "license_class": there.get("license_class")},
        "km": round(km), "miles": round(km * 0.621371), "bearing": round(bearing),
        "back_bearing": round(back),
        "sight": sight,
        "sky": {"fof2": sky.get("fof2"), "muf": snap.get("muf"), "blind": sky.get("blind"),
                "one_hop_km": sky.get("one_hop_km"),
                "bands": [{k: r.get(k) for k in ("band", "works", "how", "hops", "why", "label", "score")}
                          for r in sky["bands"]],
                "read_at": "the midpoint of the path, where a hop is reflected"},
        "approach": approach,
        "when": when,
        "ladder": ladder(km, sight, sky, license, unit),
    }

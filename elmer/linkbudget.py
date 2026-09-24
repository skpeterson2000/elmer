"""A VHF or UHF path by the numbers: the link budget along the ground.

The path tool says whether two antennas can see each other, and past the
horizon that they cannot - which is true and is not the whole answer. A 2 m
signal does not stop at the horizon; it loses so many decibels getting past
it, and whether the contact is made is whether the radios have those
decibels in hand. A handheld with its own rubber duck has very few. A base
rig into a Yagi thirty feet up has a great many. The same hill is a wall
to one and a nuisance to the other, and the only honest way to say which is
to add it up.

So this adds it up, the way a link budget is always added up:

    what leaves       transmitter power, plus the antenna's gain, less the
                      feedline - in dBm
    what the path     free space, plus knife-edge diffraction over whatever
    costs             the terrain profile puts above the line, the bulge of
                      the earth included, by Deygout's method - the main
                      edge, then the edges it hides on either side; or the
                      plane-earth two-ray loss, where two low antennas
                      over open ground have the ground's reflection
                      cancelling most of the direct ray - whichever of the
                      two is the greater, since they are two accounts of
                      the same ground and are not added
    what arrives      the difference, in dBm
    what is needed    the receiver's noise floor at this bandwidth, at this
                      site - the man-made noise of a residential street is
                      well above a receiver's own at 2 m - plus what the
                      mode needs above it to be copied
    the margin        what arrives less what is needed, in dB

The margin is turned into odds because a path is not one number. Terrain
the profile did not sample, trees, the building the far end is standing
behind, the season: measured against models like this one, real paths
scatter about the prediction with a spread of some eight decibels. The odds
are the chance the real path is inside the margin, and they are said as
such. Twenty decibels in hand is near certain, none is a coin toss, and
minus ten is a long shot you may still get on a good day.

It is a teaching-grade model and it says so where it is shown. It does not
know about tropospheric ducting, aircraft scatter, the far end's building,
or the trees in either yard; what it knows is the terrain between, the
heights, the gains, the watts and the mode, which is what decides most
paths most of the time.
"""
import math

from . import groundwave, terrain

# The bands, and the frequency the budget is worked at.
BANDS = {"6m": 50.2, "2m": 146.0, "1.25m": 223.5, "70cm": 446.0}


def for_bands():
    """The bands this budget can work: the ones a signal travels the ground
    on. Asked for by the page's band list, which also offers the sky's."""
    return [{"key": k, "label": BAND_LABELS[k]} for k in BANDS]
BAND_LABELS = {"6m": "6 m", "2m": "2 m", "1.25m": "1.25 m", "70cm": "70 cm"}

# The shelf. Each is a radio and the antenna that goes with it as people
# actually own them, in the order somebody steps up through them - so the
# next entry is the next thing to buy. Gains are over an isotrope, at the
# horizon, and are the round figures the antennas' own makers would not
# argue with; the base feedline is a hundred feet of good coax, whose loss
# climbs with frequency. The heights are the antenna's above the ground it
# stands on.
#
# The FT-991A barefoot is 50 W on 2 m and 70 cm, 100 W on 6 m; the shelf's
# base rig is that radio, since it is what is on so many shelves.
RADIOS = {
    "ht": {"label": "a handheld at 5 W on its own rubber duck",
           "short": "handheld, rubber duck", "watts": {"6m": 5.0, "2m": 5.0, "1.25m": 5.0, "70cm": 5.0},
           "gain_dbi": {"6m": -8.0, "2m": -3.0, "1.25m": -2.0, "70cm": -1.0},
           "height_m": 2.0, "feed_db": {"6m": 0.0, "2m": 0.0, "1.25m": 0.0, "70cm": 0.0}},
    "ht_whip": {"label": "a handheld at 5 W on a half-wave whip",
                "short": "handheld, half-wave whip", "watts": {"6m": 5.0, "2m": 5.0, "1.25m": 5.0, "70cm": 5.0},
                "gain_dbi": {"6m": -2.0, "2m": 2.0, "1.25m": 2.0, "70cm": 2.0},
                "height_m": 2.0, "feed_db": {"6m": 0.0, "2m": 0.0, "1.25m": 0.0, "70cm": 0.0}},
    "mobile": {"label": "a mobile at 50 W, a quarter wave on the roof",
               "short": "mobile, quarter wave", "watts": {"6m": 50.0, "2m": 50.0, "1.25m": 50.0, "70cm": 40.0},
               "gain_dbi": {"6m": 0.0, "2m": 1.0, "1.25m": 1.0, "70cm": 1.0},
               "height_m": 2.0, "feed_db": {"6m": 0.3, "2m": 0.5, "1.25m": 0.6, "70cm": 0.9}},
    "mobile_gain": {"label": "a mobile at 50 W, a 5/8 wave on the roof",
                    "short": "mobile, 5/8 wave", "watts": {"6m": 50.0, "2m": 50.0, "1.25m": 50.0, "70cm": 40.0},
                    "gain_dbi": {"6m": 0.0, "2m": 3.0, "1.25m": 3.0, "70cm": 4.5},
                    "height_m": 2.0, "feed_db": {"6m": 0.3, "2m": 0.5, "1.25m": 0.6, "70cm": 0.9}},
    "base": {"label": "a base rig at 50 W - an FT-991A barefoot - into a vertical 30 ft up",
             "short": "base, vertical at 30 ft", "watts": {"6m": 100.0, "2m": 50.0, "1.25m": 50.0, "70cm": 50.0},
             "gain_dbi": {"6m": 2.0, "2m": 5.0, "1.25m": 5.5, "70cm": 7.5},
             "height_m": 9.0, "feed_db": {"6m": 0.9, "2m": 1.5, "1.25m": 1.9, "70cm": 2.7}},
    "base_beam": {"label": "a base rig at 50 W into a Yagi 30 ft up, pointed at them",
                  "short": "base, Yagi at 30 ft", "watts": {"6m": 100.0, "2m": 50.0, "1.25m": 50.0, "70cm": 50.0},
                  "gain_dbi": {"6m": 8.0, "2m": 12.0, "1.25m": 12.5, "70cm": 14.0},
                  "height_m": 9.0, "feed_db": {"6m": 0.9, "2m": 1.5, "1.25m": 1.9, "70cm": 2.7}},
}
SHELF = ["ht", "ht_whip", "mobile", "mobile_gain", "base", "base_beam"]

# The Make Contact page's gear, as the shelf reads it.
GEAR_TO_RADIO = {"ht": "ht", "mobile_vhf": "mobile", "vhf_ssb": "base"}

# A receiver's own noise, over the thermal floor. Five decibels is an
# ordinary FM rig; the SSB rigs are a little better and it hardly matters,
# because at VHF the site's noise is on top of it.
NOISE_FIGURE_DB = 5.0

# The spread of real paths about a prediction like this one, in dB. Eight
# is what the terrain models are measured to hold over irregular ground.
SPREAD_DB = 8.0

# 4/3-earth radius, for the bulge in the middle of a path.
EARTH_KM = 8495.0

# Past this the budget is not the question: what carries a VHF signal two
# hundred kilometres is the weather - tropospheric bending and ducting -
# and this model does not do weather.
MAX_KM = 200.0

# How many points the ground is asked for. The terrain service's ceiling
# is a hundred a call.
SAMPLES = 100


def free_space_db(km, mhz):
    """Free-space path loss, dB."""
    return 32.45 + 20.0 * math.log10(max(0.001, km)) + 20.0 * math.log10(mhz)


def plane_earth_db(km, h1_m, h2_m):
    """The two-ray loss over flat ground, dB: the direct ray and the
    ground's reflection nearly cancel when both antennas are low, and the
    loss runs as the fourth power of the distance and not the second."""
    d = max(1.0, km * 1000.0)
    return 40.0 * math.log10(d) - 20.0 * math.log10(max(0.1, h1_m)) - 20.0 * math.log10(max(0.1, h2_m))


def knife_edge_db(nu):
    """ITU-R P.526's approximation to the loss over one knife edge, dB, for
    the Fresnel parameter nu. Nothing for an edge well below the line."""
    if nu <= -0.78:
        return 0.0
    return 6.9 + 20.0 * math.log10(math.sqrt((nu - 0.1) ** 2 + 1.0) + nu - 0.1)


def fresnel_radius_m(d1_km, d2_km, mhz):
    """The first Fresnel zone's radius at a point d1 from one end and d2
    from the other, metres."""
    d = d1_km + d2_km
    if d <= 0 or d1_km <= 0 or d2_km <= 0:
        return 0.0
    return 17.32 * math.sqrt(d1_km * d2_km / ((mhz / 1000.0) * d))


def _clearances(pts, ha_m, hb_m, mhz):
    """For each interior point: (index, km, height above the line in m, nu).
    The line runs from the antenna at one end to the antenna at the other
    and sags by the earth's bulge; a point above it is an obstruction."""
    d = pts[-1][0]
    a = pts[0][1] + ha_m
    b = pts[-1][1] + hb_m
    out = []
    for i in range(1, len(pts) - 1):
        d1, elev = pts[i]
        d2 = d - d1
        if d1 <= 0 or d2 <= 0:
            continue
        line = a + (b - a) * (d1 / d) - (d1 * d2) / (2.0 * EARTH_KM) * 1000.0
        h = elev - line
        r1 = fresnel_radius_m(d1, d2, mhz)
        nu = h * math.sqrt(2.0) / r1 if r1 > 0 else 0.0
        out.append((i, d1, h, nu))
    return out


def series(pts, ha_m, hb_m, mhz):
    """The profile as the page draws it: at each sample, the ground, the
    line between the antennas sagging by the earth's bulge, and the first
    Fresnel zone's radius there - all in metres, distance in km."""
    d = pts[-1][0]
    a = pts[0][1] + ha_m
    b = pts[-1][1] + hb_m
    out = []
    for km, elev in pts:
        d1, d2 = km, d - km
        line = a + (b - a) * (d1 / d) - (d1 * d2) / (2.0 * EARTH_KM) * 1000.0 if d > 0 else a
        r1 = fresnel_radius_m(d1, d2, mhz) if 0 < d1 < d else 0.0
        out.append({"km": round(km, 2), "ground": round(elev), "line": round(line, 1), "r1": round(r1)})
    return out


def deygout_db(pts, ha_m, hb_m, mhz, depth=0):
    """Diffraction loss over the profile, dB, by Deygout: the main edge -
    the point with the largest Fresnel parameter - then, on the sub-paths
    it makes on either side, the same again, once. Returns the loss and
    the edges as (km, m above the line, nu, dB)."""
    if len(pts) < 3:
        return 0.0, []
    cl = _clearances(pts, ha_m, hb_m, mhz)
    if not cl:
        return 0.0, []
    i, d1, h, nu = max(cl, key=lambda c: c[3])
    if nu <= -0.78:
        return 0.0, []
    loss = knife_edge_db(nu)
    edges = [(d1, h, nu, loss)]
    if depth < 1 and h > 0.0:
        # the edge's summit is the new end of each sub-path - only under an
        # edge that stands above the line; a line that merely grazes open
        # ground has no edges hiding behind the grazing
        left, more = deygout_db(pts[:i + 1], ha_m, 0.0, mhz, depth + 1)
        right, more2 = deygout_db(pts[i:], 0.0, hb_m, mhz, depth + 1)
        loss += left + right
        edges += more + more2
    return loss, edges


# Atmospheric noise: lightning, somewhere in the world, arriving the same way
# everything else on the low bands arrives. ITU-R P.372 gives the man-made
# figures above as two constants each, and gives this one as a book of maps -
# it depends on frequency, on the hour, on the season and on how far you are
# from the tropics, because that is where the storms are.
#
# What follows is a straight line through those maps for a mid-latitude
# station, not the maps themselves: Fa = A - B log10(MHz), fitted to their
# shape rather than read off them. It is the part this calculation had
# missing altogether, and leaving it out flattered a quiet site enormously -
# man-made noise alone says a rural station hears 80 m at about S4, and no
# rural station has ever heard 80 m at S4 on a summer night. You cannot get
# away from lightning by moving out of town.
#
# These being a fit and not a table, they are meant to be argued with: an
# operator who knows what their own bands sound like can move them, and
# tools/noise_floor.py prints the S-meter readings they produce.
ATMOSPHERIC_NIGHT = (83.0, 49.0)      # A, B - after dark, storms propagating in
ATMOSPHERIC_DAY = (71.0, 49.0)        # by day: the D layer absorbs it as it does everything
ATMOSPHERIC_WINTER_DB = -10.0         # fewer storms, and further away
ATMOSPHERIC_DAY_DEG = 0.0             # sun elevation that counts as daylight


def atmospheric_fa(mhz, sun_deg=None, when=None, lat=None):
    """Atmospheric noise in dB above kTB at this frequency.

    `sun_deg` is the sun's elevation where the noise is being heard; None
    means unknown and takes the mean of day and night, which is the honest
    answer when nobody has said what time it is. `when` and `lat` give the
    season - summer is the noisy half, and which half that is depends on
    the hemisphere.
    """
    night_a, night_b = ATMOSPHERIC_NIGHT
    day_a, day_b = ATMOSPHERIC_DAY
    lf = math.log10(max(0.1, float(mhz)))
    night = night_a - night_b * lf
    day = day_a - day_b * lf
    if sun_deg is None:
        fa = (night + day) / 2.0
    else:
        fa = day if float(sun_deg) > ATMOSPHERIC_DAY_DEG else night
    if when is not None:
        month = getattr(when, "month", None)
        if month:
            southern = lat is not None and float(lat) < 0
            summer = month in ((11, 12, 1, 2, 3, 4) if southern else (5, 6, 7, 8, 9, 10))
            if not summer:
                fa += ATMOSPHERIC_WINTER_DB
    return fa


def noise_floor_dbm(mhz, bandwidth_hz, site="residential", sun_deg=None, when=None, lat=None):
    """The receiver's floor in dBm: thermal noise in the bandwidth, plus
    the greater part of the receiver's own noise, the site's man-made noise
    and the sky's own, added as powers. At 2 m in a residential street the
    site wins; on 80 m after dark the sky does, wherever the site is."""
    c, d, _ = groundwave.NOISE_SITES.get(site) or groundwave.NOISE_SITES["residential"]
    fa = c - d * math.log10(max(1.0, mhz))            # dB above kTB, ITU-R P.372
    external = 10.0 ** (max(0.0, fa) / 10.0)
    # Above 30 MHz the storms are below the horizon and stay there; what is
    # left up here is the galaxy, which the site figures already stand in for.
    if mhz <= 30.0:
        external += 10.0 ** (max(0.0, atmospheric_fa(mhz, sun_deg, when, lat)) / 10.0)
    internal = 10.0 ** (NOISE_FIGURE_DB / 10.0)
    return -174.0 + 10.0 * math.log10(max(1.0, bandwidth_hz)) + 10.0 * math.log10(external + internal)


def needed_dbm(mhz, mode="fm", site="residential", sun_deg=None, when=None, lat=None):
    """What has to arrive for this mode to be copied at this site."""
    m = groundwave.mode_of(mode)
    return noise_floor_dbm(mhz, m["bandwidth_hz"], site, sun_deg, when, lat) + m["snr"]


def odds(margin_db):
    """The chance the real path is inside the margin, as a fraction: the
    normal distribution's tail at margin over the spread."""
    z = margin_db / SPREAD_DB
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def odds_words(p):
    if p >= 0.9:
        return "good"
    if p >= 0.6:
        return "likely"
    if p >= 0.35:
        return "worth trying"
    if p >= 0.1:
        return "long shot"
    return "no"


def smooth_profile(km, samples=41):
    """A flat earth's profile - sea level all the way - for a path the
    terrain service could not describe. The bulge is still in the maths."""
    n = max(3, samples)
    return [(km * i / (n - 1), 0.0) for i in range(n)]


def _radio(key, band):
    r = RADIOS.get(key) or RADIOS["ht"]
    return {"key": key if key in RADIOS else "ht", "label": r["label"], "short": r["short"],
            "watts": r["watts"][band], "gain_dbi": r["gain_dbi"][band],
            "height_m": r["height_m"], "feed_db": r["feed_db"][band]}


def budget(km, profile_pts, band="2m", mode="fm", here="ht", there="ht", site="residential"):
    """The whole sum, both ways. `profile_pts` is a list of (km, elevation
    in metres) from here to there, ends included, or None for a path the
    ground could not be asked about, which is then taken as flat."""
    band = band if band in BANDS else "2m"
    mhz = BANDS[band]
    mode = mode if mode in groundwave.MODES else "fm"
    a = _radio(here, band)
    b = _radio(there, band)
    pts = list(profile_pts) if profile_pts and len(profile_pts) >= 3 else smooth_profile(km)
    terrain_known = bool(profile_pts and len(profile_pts) >= 3)
    if pts[-1][0] <= 0:
        pts = smooth_profile(max(0.05, km))
    km = pts[-1][0]

    fspl = free_space_db(km, mhz)
    plane = plane_earth_db(km, a["height_m"], b["height_m"])
    diff_db, edges = deygout_db(pts, a["height_m"], b["height_m"], mhz)
    # Two accounts of the same ground: the direct ray diffracting over what
    # stands in its way, or the ground's reflection cancelling it between
    # two low antennas. The path pays the greater, not both - charging the
    # bulge on top of the two-ray loss had a pair of base stations forty
    # kilometres apart on open ground rated a long shot, which every club
    # net on 2 m disproves on a Tuesday night.
    over = fspl + diff_db
    loss = max(over, plane)
    mechanism = ("two low antennas over the ground" if plane > over
                 else "free space" if diff_db < 0.5 else "free space and the ground between")

    def leg(tx, rx):
        out_dbm = 10.0 * math.log10(tx["watts"] * 1000.0) + tx["gain_dbi"] - tx["feed_db"]
        arrives = out_dbm + rx["gain_dbi"] - rx["feed_db"] - loss
        need = needed_dbm(mhz, mode, site)
        margin = arrives - need
        return {"leaves_dbm": round(out_dbm, 1), "arrives_dbm": round(arrives, 1),
                "needed_dbm": round(need, 1), "margin_db": round(margin, 1),
                "odds": round(odds(margin), 3)}

    forward = leg(a, b)          # you, heard there
    back = leg(b, a)             # them, heard here
    worse = forward if forward["margin_db"] <= back["margin_db"] else back
    p = worse["odds"]
    main_edge = max(edges, key=lambda e: e[3]) if edges else None
    clear_m = None
    if pts and len(pts) >= 3:
        cl = _clearances(pts, a["height_m"], b["height_m"], mhz)
        if cl:
            i, d1, h, nu = max(cl, key=lambda c: c[3])
            clear_m = {"km": round(d1, 1), "above_line_m": round(h),
                       "fresnel_m": round(fresnel_radius_m(d1, km - d1, mhz)),
                       "fraction_clear": round(-h / max(1.0, fresnel_radius_m(d1, km - d1, mhz)), 2)}
    return {
        "band": band, "band_label": BAND_LABELS[band], "mhz": mhz, "mode": mode,
        "mode_label": groundwave.mode_of(mode)["label"], "site": site,
        "km": round(km, 1), "miles": round(km * 0.621371, 1),
        "here": a, "there": b, "terrain": terrain_known,
        "loss": {"free_space_db": round(fspl, 1), "plane_earth_db": round(plane, 1),
                 "mechanism": mechanism, "diffraction_db": round(diff_db, 1), "total_db": round(loss, 1),
                 "edges": [{"km": round(e[0], 1), "above_line_m": round(e[1]), "nu": round(e[2], 2), "db": round(e[3], 1)}
                           for e in edges],
                 "worst": clear_m},
        "forward": forward, "back": back,
        "profile": series(pts, a["height_m"], b["height_m"], mhz),
        "margin_db": worse["margin_db"], "odds": round(p, 3), "verdict": odds_words(p),
        "words": _words(km, a, b, band, mode, site, loss, mechanism, diff_db, main_edge, forward, back, p),
        "spread_db": SPREAD_DB,
        "beyond": km > MAX_KM,
    }


def _words(km, a, b, band, mode, site, loss, mechanism, diff_db, edge, fwd, back, p):
    mi = km * 0.621371
    lbl = BAND_LABELS[band]
    ml = groundwave.mode_of(mode)["label"]
    ridge = (f", the worst of it {edge[0]:.0f} km along, {edge[1]:.0f} m above the line"
             if edge and edge[1] > 0 else "")
    if mechanism.startswith("two low"):
        how = (f"two low antennas over the ground, the ground's reflection cancelling most of the direct "
               f"ray, so the loss runs as the fourth power of the distance"
               + (f" - the ground in the way{ridge} is inside that figure" if ridge else ""))
    elif diff_db < 0.5:
        how = "all of it free space"
    else:
        how = f"{loss - diff_db:.0f} in free space and {diff_db:.0f} more getting over the ground{ridge}"
    s = f"{a['short']} to {b['short']}, {mi:.0f} miles on {lbl} {ml}: the path costs {loss:.0f} dB - {how}. "
    if fwd["margin_db"] <= back["margin_db"]:
        s += (f"Your signal arrives at {fwd['arrives_dbm']:.0f} dBm against the {fwd['needed_dbm']:.0f} an {ml} receiver "
              f"needs in a {site} setting: {fwd['margin_db']:+.0f} dB in hand")
        if abs(fwd["margin_db"] - back["margin_db"]) >= 1.0:
            s += f", theirs {back['margin_db']:+.0f} coming back"
    else:
        s += (f"Their signal arrives here at {back['arrives_dbm']:.0f} dBm against the {back['needed_dbm']:.0f} an {ml} "
              f"receiver needs in a {site} setting: {back['margin_db']:+.0f} dB in hand, yours {fwd['margin_db']:+.0f} going out")
    s += f". Real paths scatter about a figure like this by some {SPREAD_DB:.0f} dB, so call it {100 * p:.0f}% odds."
    if km > MAX_KM:
        s += " Past a couple of hundred kilometres the weather decides - tropospheric bending and ducts - and this model does not do weather."
    return s


def step_up(km, profile_pts, band, mode, here, there, site, want=0.6):
    """The smallest change on the shelf that gets the odds to `want`: your
    end first, then both ends. None if nothing on the shelf does."""
    base = budget(km, profile_pts, band, mode, here, there, site)
    if base["odds"] >= want:
        return None
    start = SHELF.index(here) if here in SHELF else 0
    for key in SHELF[start + 1:]:
        b = budget(km, profile_pts, band, mode, key, there, site)
        if b["odds"] >= want:
            return {"here": key, "there": there, "label": RADIOS[key]["label"], "odds": b["odds"],
                    "margin_db": b["margin_db"], "both": False,
                    "words": f"Your end on {RADIOS[key]['label']} and the odds are {100 * b['odds']:.0f}%."}
    start2 = SHELF.index(there) if there in SHELF else 0
    for key in SHELF[max(start, start2) + 1:]:
        b = budget(km, profile_pts, band, mode, key, key, site)
        if b["odds"] >= want:
            return {"here": key, "there": key, "label": RADIOS[key]["label"], "odds": b["odds"],
                    "margin_db": b["margin_db"], "both": True,
                    "words": f"Both ends on {RADIOS[key]['label']} and the odds are {100 * b['odds']:.0f}%."}
    return {"here": None, "there": None, "label": None, "odds": None, "margin_db": None, "both": True,
            "words": "Nothing on the shelf gets there by the numbers: this one wants a repeater between, or height at one end."}


def profile_points(prof):
    """The terrain module's profile as (km, elevation) pairs, or None."""
    if not prof or not prof.get("points"):
        return None
    pts = [(float(p["km"]), float(p["elevation"])) for p in prof["points"]]
    return pts if len(pts) >= 3 else None


def for_path(here, there, km, prof=None, band="2m", mode="fm", radio_here="ht", radio_there=None, site="residential"):
    """The budget for a path between two places, with the profile if one is
    in hand, else the ground asked for it (cached, throttled) when the path
    is short enough for the answer to mean anything."""
    if km > MAX_KM:
        prof = None
    elif prof is None:
        try:
            prof = terrain.profile(here["lat"], here["lon"], there["lat"], there["lon"], samples=SAMPLES)
        except Exception:
            prof = None
    pts = profile_points(prof)
    radio_there = radio_there or radio_here
    out = budget(km, pts, band, mode, radio_here, radio_there, site)
    out["step_up"] = step_up(km, pts, band, mode, out["here"]["key"], out["there"]["key"], site)
    out["source"] = (prof or {}).get("source") if pts else None
    out["shelf"] = [{"key": k, "label": RADIOS[k]["label"], "short": RADIOS[k]["short"]} for k in SHELF]
    out["bands"] = for_bands()
    out["modes"] = [{"key": k, "label": groundwave.MODES[k]["label"]} for k in ("fm", "ssb", "cw", "ft8")]
    out["sites"] = [{"key": k, "label": v[2]} for k, v in groundwave.NOISE_SITES.items()]
    return out

"""Where you are, from the sun and a clock.

A sextant measures how high the sun is. That single number puts you somewhere
on a circle drawn on the earth - every point on it sees the sun at that
altitude at that instant, and its centre is the geographical position, the spot
where the sun is directly overhead. One sight is a circle. Two sights an hour
apart are two circles, and they cross. That crossing is the fix, and it is the
whole idea; everything below is arithmetic in service of it.

Navigators did this with an almanac, a table of logarithms and a plotting
sheet, because the arithmetic was the expensive part. It is not expensive any
more, so ELMER does it directly: it can work out the sun's true altitude for
any position and instant, so it searches for the position that best predicts
every sight you took. No assumed position, no tables, no plotting.

What that buys is accuracy the method deserves. A careful sight is good to
about a nautical mile, and this is arithmetic all the way down rather than
interpolation between printed rows.

    This is not `propagation.solar_elevation`, and deliberately so. That one
    answers "roughly how high is the sun, is the D layer lit" and its solar
    model is wrong by up to 26 arcminutes of declination - which is nothing to
    a band prediction and twenty-six nautical miles to a navigator. The two
    cannot share a sun.
"""
import math
from datetime import datetime, timezone

# Meeus, *Astronomical Algorithms*, chapter 25 - the "low accuracy" solar
# position, which is good to about 0.01 degrees. That is 0.6 of a nautical
# mile, comfortably better than anyone can hold a sextant.

J2000 = 2451545.0


def julian_day(when):
    """Julian Day for a UTC datetime, fractional."""
    y, m = when.year, when.month
    d = (when.day + (when.hour + when.minute / 60.0
                     + (when.second + when.microsecond / 1e6) / 3600.0) / 24.0)
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    b = 2 - a + a // 4                      # Gregorian calendar
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + d + b - 1524.5)


def sun_position(when):
    """The sun's declination and Greenwich hour angle, in degrees.

    Declination is how far north or south of the equator the sun is overhead.
    Greenwich hour angle is how far west of Greenwich it is. Together they are
    the geographical position: the one point on earth with the sun exactly
    overhead at this instant, and the centre of every circle of position.
    """
    jd = julian_day(when)
    t = (jd - J2000) / 36525.0

    # Geometric mean longitude and mean anomaly of the sun.
    l0 = (280.46646 + 36000.76983 * t + 0.0003032 * t * t) % 360.0
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    mr = math.radians(m)

    # Equation of the centre: the orbit is an ellipse, so the sun runs ahead
    # of and behind its mean position through the year.
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr)
         + 0.000289 * math.sin(3 * mr))
    true_long = l0 + c

    # Apparent longitude: nutation and aberration.
    omega = 125.04 - 1934.136 * t
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))

    # Obliquity of the ecliptic, with the same nutation term.
    eps0 = (23.0 + 26.0 / 60.0 + 21.448 / 3600.0
            - (46.8150 * t + 0.00059 * t * t - 0.001813 * t ** 3) / 3600.0)
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))

    lr, er = math.radians(lam), math.radians(eps)
    dec = math.degrees(math.asin(math.sin(er) * math.sin(lr)))
    ra = math.degrees(math.atan2(math.cos(er) * math.sin(lr), math.cos(lr))) % 360.0

    # Greenwich mean sidereal time, then the sun's hour angle west of it.
    gmst = (280.46061837 + 360.98564736629 * (jd - J2000)
            + 0.000387933 * t * t - t ** 3 / 38710000.0) % 360.0
    gha = (gmst - ra) % 360.0

    # Semi-diameter: the sun is half a degree wide, and a sextant is brought to
    # one edge of it rather than to a centre nobody can see.
    radius_au = 1.000001018 * (1 - 0.016708634 ** 2) / (
        1 + 0.016708634 * math.cos(mr + math.radians(c)))
    return {"dec": dec, "gha": gha, "ra": ra,
            "semidiameter_arcmin": 16.0 / radius_au,
            "distance_au": radius_au}


def altitude_azimuth(lat, lon, when, sun=None):
    """The altitude and bearing of the sun from a place, in degrees.

    East longitude positive. Azimuth is measured clockwise from true north.
    """
    sun = sun or sun_position(when)
    lha = math.radians((sun["gha"] + lon) % 360.0)     # local hour angle, west
    phi, dec = math.radians(lat), math.radians(sun["dec"])
    sin_alt = (math.sin(phi) * math.sin(dec)
               + math.cos(phi) * math.cos(dec) * math.cos(lha))
    alt = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))
    az = math.degrees(math.atan2(
        -math.cos(dec) * math.sin(lha),
        math.sin(dec) * math.cos(phi) - math.cos(dec) * math.sin(phi) * math.cos(lha)))
    return alt, az % 360.0


# --- getting from what the sextant said to what the sky did ------------------
#
# A sextant reading is not an altitude. It is an altitude plus everything
# between you and the sun: the instrument's own error, the fact that you are
# above the sea and can see slightly over the horizon, the atmosphere bending
# the light, and the fact that you brought the sun's edge down rather than a
# centre you cannot see. Each is a named correction and each is shown.

def dip_arcmin(height_ft):
    """How far below true horizontal the sea horizon is, from eye height."""
    return 0.9698 * math.sqrt(max(0.0, height_ft))


def refraction_arcmin(apparent_alt_deg):
    """Bennett's formula. The atmosphere lifts the sun; this puts it back."""
    h = max(-0.9, apparent_alt_deg)
    return 1.0 / math.tan(math.radians(h + 7.31 / (h + 4.4)))


def altitude_from_shadow(object_height, shadow_length):
    """The sun's altitude from a stick and the shadow it throws.

    No instrument at all: altitude = atan(height / shadow), in whatever units
    you like as long as they are the same. A metre stick with the shadow tip
    read to a centimetre is good to about a third of a degree, which is twenty
    nautical miles - loose for a sextant and ample for a four-character grid.

    The shadow's edge is soft because the sun is half a degree wide, so read
    the middle of the fuzz: that is where the centre of the sun puts it.
    """
    if object_height <= 0 or shadow_length <= 0:
        return None
    return math.degrees(math.atan2(float(object_height), float(shadow_length)))


def reduce_sight(hs_deg, when, index_error_arcmin=0.0, height_ft=0.0,
                 limb="lower", horizon="sea"):
    """A sextant reading worked up to a true altitude, with the working shown.

    `horizon` is "sea" for a real horizon, or "artificial" for a pan of water -
    which is what anybody inland has to use. An artificial horizon reflects the
    sun, so the sextant reads twice the altitude and there is no dip: you are
    not looking at a horizon at all.
    """
    steps = []
    sun = sun_position(when)
    h = float(hs_deg)
    steps.append(("sextant reading", h, "what you read off the arc"))

    if horizon == "artificial":
        h /= 2.0
        steps.append(("halved for the artificial horizon", h,
                      "the reflection doubles the angle, so half of it is the "
                      "altitude"))
    elif horizon == "shadow":
        steps[-1] = ("angle from the shadow", h,
                     "atan(height / shadow length) - no instrument in it, so "
                     "no instrument error either")

    if index_error_arcmin:
        h += index_error_arcmin / 60.0
        steps.append(("index error", h,
                      "%+.1f' for the instrument's own zero" % index_error_arcmin))

    if horizon not in ("artificial", "shadow") and height_ft:
        d = dip_arcmin(height_ft)
        h -= d / 60.0
        steps.append(("dip", h,
                      "-%.1f' - from %.0f ft up you see over the horizon"
                      % (d, height_ft)))

    apparent = h
    r = refraction_arcmin(apparent)
    h -= r / 60.0
    steps.append(("refraction", h,
                  "-%.1f' - the atmosphere lifts it, so take it back off" % r))

    sd = sun["semidiameter_arcmin"]
    if horizon == "shadow":
        steps.append(("semi-diameter", h,
                      "none - the soft edge of a shadow is thrown by the whole "
                      "disc, so its middle is already the sun's centre"))
    elif limb == "lower":
        h += sd / 60.0
        steps.append(("semi-diameter", h,
                      "+%.1f' - you brought the lower edge down, the centre is "
                      "half a diameter above it" % sd))
    elif limb == "upper":
        h -= sd / 60.0
        steps.append(("semi-diameter", h, "-%.1f' - upper limb" % sd))

    p = 0.15 * math.cos(math.radians(h))
    h += p / 60.0
    steps.append(("parallax", h,
                  "+%.2f' - the earth has a radius and you are on its surface" % p))

    sigma = (shadow_sigma_arcmin(h) if horizon == "shadow"
             else SIGHT_SIGMA_ARCMIN)
    return {"ho": h, "apparent": apparent, "steps": steps,
            "dec": sun["dec"], "gha": sun["gha"],
            "semidiameter_arcmin": sd, "sigma_arcmin": round(sigma, 2)}


# --- the fix -----------------------------------------------------------------
#
# Every sight says "you are somewhere on this circle". Two circles cross at two
# points; three usually agree on one of them. Rather than plot them, the
# position that best predicts every sight is searched for directly - coarsely
# over the whole earth first, because somebody who needs this may have no idea
# where they are, then sharpened by Gauss-Newton.
#
# The derivative is the one piece of navigation worth knowing by heart: move a
# nautical mile toward the sun's bearing and its altitude rises by one minute
# of arc. So d(altitude) = cos(Z) dlat + sin(Z) cos(lat) dlon, which is why a
# sight draws a line at right angles to the bearing of the body, and why two
# sights on the same bearing tell you nothing.

EARTH_NM_PER_DEG = 60.0


def _residuals(lat, lon, sights):
    out = []
    for s in sights:
        alt, az = altitude_azimuth(lat, lon, s["when"])
        out.append((s["ho"] - alt, az))
    return out


def _rms_arcmin(lat, lon, sights):
    r = _residuals(lat, lon, sights)
    return math.sqrt(sum((d * 60.0) ** 2 for d, _ in r) / len(r))


def _refine(lat, lon, sights, rounds=12):
    """Gauss-Newton on (lat, lon). Returns the position and how well it fits."""
    for _ in range(rounds):
        rows, rhs = [], []
        for s in sights:
            alt, az = altitude_azimuth(lat, lon, s["when"])
            zr = math.radians(az)
            rows.append((math.cos(zr), math.sin(zr) * math.cos(math.radians(lat))))
            rhs.append(s["ho"] - alt)
        # Normal equations for two unknowns, solved directly.
        a = sum(r[0] * r[0] for r in rows)
        b = sum(r[0] * r[1] for r in rows)
        c = sum(r[1] * r[1] for r in rows)
        u = sum(r[0] * v for r, v in zip(rows, rhs))
        v = sum(r[1] * v for r, v in zip(rows, rhs))
        det = a * c - b * b
        if abs(det) < 1e-12:
            break                       # the sights are all on one bearing
        dlat = (c * u - b * v) / det
        dlon_cos = (a * v - b * u) / det
        coslat = max(0.05, math.cos(math.radians(lat)))
        lat = max(-89.9, min(89.9, lat + dlat))
        lon = ((lon + dlon_cos / coslat + 180.0) % 360.0) - 180.0
        if abs(dlat) < 1e-9 and abs(dlon_cos) < 1e-9:
            break
    return lat, lon


def fix(sights, hint=None):
    """Where you are, from two or more sights. Returns the answer and the working.

    `sights` are dicts with "ho" (true altitude, degrees) and "when" (aware UTC
    datetime). `hint` is a rough position if one is known - it is used only to
    choose between solutions, never to bias the answer.
    """
    if len(sights) < 2:
        return {"ok": False,
                "error": "two sights at least: one is a circle, not a place."}

    # Coarse sweep of the whole earth, so no assumed position is needed.
    best = []
    for ilat in range(-88, 89, 4):
        for ilon in range(-180, 180, 4):
            best.append((_rms_arcmin(ilat, ilon, sights), float(ilat), float(ilon)))
    best.sort()

    # Refine the promising basins and keep the distinct answers.
    found = []
    for _, la, lo in best[:40]:
        p_lat, p_lon = _refine(la, lo, sights)
        rms = _rms_arcmin(p_lat, p_lon, sights)
        if any(_separation_nm(p_lat, p_lon, f["lat"], f["lon"]) < 30 for f in found):
            continue
        found.append({"lat": p_lat, "lon": p_lon, "rms_arcmin": rms})
    found.sort(key=lambda f: f["rms_arcmin"])
    if not found:
        return {"ok": False, "error": "no position fits these sights"}

    # Two circles cross at two points, and from one body both fit perfectly.
    # That is not a defect in the arithmetic, it is the geometry: two sun
    # sights genuinely do not say which of two places you are in. A rough idea
    # of where you are settles it, and so does a third sight. Guessing silently
    # would be the one unforgivable thing for a tool somebody might actually be
    # lost with.
    rival = None
    if len(found) > 1 and found[1]["rms_arcmin"] < found[0]["rms_arcmin"] + 1.0:
        rival = found[1]
    if hint:
        found.sort(key=lambda f: _separation_nm(f["lat"], f["lon"],
                                                hint[0], hint[1]))
        rival = None
    chosen = found[0]

    # How well the sights were placed, rather than how well they were taken.
    # Two bearings close together cross at a shallow angle and the crossing
    # slides a long way for a small error in either.
    bearings = sorted(az for _, az in _residuals(chosen["lat"], chosen["lon"], sights))
    spread = _widest_gap(bearings)
    others = [f for f in found[1:] if f["rms_arcmin"] < chosen["rms_arcmin"] + 2.0]

    return {"ok": True, "lat": round(chosen["lat"], 4),
            "lon": round(chosen["lon"], 4),
            "rms_arcmin": round(chosen["rms_arcmin"], 2),
            "sights": len(sights),
            "ambiguous": rival is not None,
            "ambiguity_note": (
                "Two sights of one body cross at two points and both fit. You "
                "are at one of these and this cannot tell you which: take a "
                "third sight, or say roughly where you think you are."
                if rival else ""),
            "bearing_spread_deg": round(spread, 1),
            "uncertainty_nm": _uncertainty_nm(chosen["lat"], chosen["lon"], sights),
            "geometry": ("good" if spread >= 60 else
                         "usable" if spread >= 25 else "poor"),
            "alternatives": [{"lat": round(f["lat"], 4), "lon": round(f["lon"], 4),
                              "rms_arcmin": round(f["rms_arcmin"], 2),
                              "away_nm": round(_separation_nm(
                                  chosen["lat"], chosen["lon"], f["lat"], f["lon"]))}
                             for f in others[:2]]}


# A sight taken carefully is good to about a minute of arc. That is the number
# the uncertainty is worked out from, rather than from how well the sights
# happen to agree with each other - because with two sights and two unknowns
# they agree perfectly by construction, and a residual of zero would report a
# perfect fix from two readings that were both wrong.
SIGHT_SIGMA_ARCMIN = 1.0          # a careful sextant sight
SHADOW_PRECISION = 0.005          # half a centimetre read on a metre of stick


def shadow_sigma_arcmin(alt_deg, precision=SHADOW_PRECISION):
    """How good a stick-and-shadow altitude is, at this altitude.

    Only the ratio of the reading error to the stick's height matters, not the
    size of either: a two metre pole read to a centimetre is the same sight as
    a metre stick read to half of one. Differentiating atan(h/s) gives an error
    of (e/h) x sin^2(altitude), which says something useful - a shadow sight is
    at its best with the sun low and its shadow long, exactly the opposite of a
    sextant, which prefers the sun high where refraction is small. Take stick
    sights in the morning and the evening.
    """
    return math.degrees(precision * math.sin(math.radians(alt_deg)) ** 2) * 60.0


def _uncertainty_nm(lat, lon, sights):
    """How far a normal sight error moves this fix. Nautical miles.

    This is the number that matters and the residual is not. A tight group of
    sights crosses at a shallow angle, so an arcminute of error in one of them
    slides the crossing a long way - and it does that silently, leaving the
    residual small and the position wrong. Standard least squares covariance:
    the same idea as the dilution of precision a GPS reports.
    """
    a = b = c = 0.0
    for sight in sights:
        _, az = altitude_azimuth(lat, lon, sight["when"])
        zr = math.radians(az)
        dn, de = math.cos(zr), math.sin(zr)
        # Weighted by how good each sight is, so a stick reading does not get
        # a sextant's confidence attached to it.
        w = 1.0 / max(1e-6, sight.get("sigma", SIGHT_SIGMA_ARCMIN)) ** 2
        a += w * dn * dn
        b += w * dn * de
        c += w * de * de
    det = a * c - b * b
    if abs(det) < 1e-12:
        return None                      # all on one bearing: no fix at all
    # The weights are in inverse arcminutes squared, so the inverse comes back
    # in arcminutes - which on the earth's surface are nautical miles.
    return round(math.sqrt(c / det + a / det), 1)


def _separation_nm(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d = math.acos(max(-1.0, min(1.0,
        math.sin(p1) * math.sin(p2)
        + math.cos(p1) * math.cos(p2) * math.cos(math.radians(lon2 - lon1)))))
    return math.degrees(d) * EARTH_NM_PER_DEG


def _widest_gap(bearings):
    """The angular spread of the sights, as the largest arc they straddle."""
    if len(bearings) < 2:
        return 0.0
    best = 0.0
    for i, a in enumerate(bearings):
        for b in bearings[i + 1:]:
            gap = abs(b - a) % 360.0
            best = max(best, min(gap, 360.0 - gap))
    return best

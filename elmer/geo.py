"""The shape of the earth, once: its radii, the distance and bearing between
two places, and how far one ionospheric hop reaches.

These were written out wherever they were needed - the radius in eight
modules, the great circle in two, the hop twice in one - and copies drift.
Everything that measures across the ground now asks here.

There are three radii, and they are not rival guesses at one number:

  - EARTH_R_KM, the mean radius, is the earth itself: distances along the
    ground, the curve under an ionospheric hop, the dip to a layer.
  - EFFECTIVE_R_KM is the "4/3 earth" radio engineers draw a VHF path over.
    The lower atmosphere bends a radio wave down a little, and a straight ray
    over an earth a third bigger is the standard way of drawing that bend.
    4/3 of 6371 is 8494.7; 8495 is the figure the literature rounds to.
  - EQUATORIAL_R_KM is the one the Moon's distance is worked from. The
    Moon's horizontal parallax is defined against the equatorial radius, so
    that is the one its formula wants.
"""
import math

EARTH_R_KM = 6371.0
EFFECTIVE_R_KM = 8495.0
EQUATORIAL_R_KM = 6378.14


def great_circle(lat1, lon1, lat2, lon2):
    """Distance in km and initial bearing in degrees, from the first place to
    the second, along the great circle.

    Haversine for the distance, because it keeps its precision over short
    paths, where the law of cosines loses it.
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    km = 2 * EARTH_R_KM * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dlon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return km, (math.degrees(math.atan2(y, x)) + 360) % 360


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    return great_circle(lat1, lon1, lat2, lon2)[0]


def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial great-circle bearing in degrees, 0 to 360, north through east."""
    return great_circle(lat1, lon1, lat2, lon2)[1]


def hop_km(elev_deg, layer_km):
    """Ground distance covered by one ionospheric hop leaving at this angle
    off a layer this high.

    Curvature is included: the flat-earth form blows up at low angles and
    would promise the moon. The angle is held to 0-90 degrees.
    """
    elev = math.radians(max(0.0, min(90.0, float(elev_deg))))
    sin_phi = min(1.0, EARTH_R_KM * math.cos(elev) / (EARTH_R_KM + layer_km))
    phi = math.asin(sin_phi)                # angle of incidence at the layer
    psi = math.pi / 2 - elev - phi          # earth-central angle
    return max(0.0, 2 * EARTH_R_KM * psi)

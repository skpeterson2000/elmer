"""Where a state or province is, roughly: a box round each one.

Enough to catch a place that has landed on the wrong continent - which a
geocoder asked for "Mobile AL" will do, since there is a Mobile in New
South Wales and the query never said which country. The boxes are generous
(a degree or so of slack), so a border town passes and Sydney does not.
Used when the bundled place list is built and checked; never for anything
that needs a real boundary.
"""

# (south, north, west, east), in degrees, with slack.
BOXES = {
    "AL": (30.0, 35.2, -88.7, -84.7), "AK": (51.0, 71.7, -180.0, -129.0), "AZ": (31.1, 37.2, -115.0, -108.8),
    "AR": (32.8, 36.7, -94.8, -89.4), "CA": (32.3, 42.2, -124.7, -113.9), "CO": (36.8, 41.2, -109.3, -101.8),
    "CT": (40.8, 42.2, -73.9, -71.6), "DE": (38.2, 40.0, -75.9, -74.8), "DC": (38.6, 39.2, -77.3, -76.7),
    "FL": (24.3, 31.2, -87.8, -79.8), "GA": (30.2, 35.2, -85.8, -80.6), "HI": (18.7, 22.5, -160.5, -154.5),
    "ID": (41.8, 49.2, -117.5, -110.8), "IL": (36.8, 42.7, -91.7, -87.2), "IN": (37.6, 41.9, -88.3, -84.6),
    "IA": (40.2, 43.7, -96.9, -90.0), "KS": (36.8, 40.2, -102.3, -94.4), "KY": (36.3, 39.4, -89.8, -81.7),
    "LA": (28.7, 33.2, -94.3, -88.6), "ME": (42.8, 47.7, -71.3, -66.7), "MD": (37.7, 39.9, -79.7, -74.8),
    "MA": (41.0, 43.0, -73.7, -69.7), "MI": (41.5, 48.5, -90.6, -82.2), "MN": (43.3, 49.6, -97.5, -89.3),
    "MS": (29.8, 35.2, -91.9, -87.9), "MO": (35.8, 40.8, -95.9, -88.9), "MT": (44.1, 49.2, -116.3, -103.8),
    "NE": (39.8, 43.2, -104.3, -95.1), "NV": (34.8, 42.2, -120.2, -113.8), "NH": (42.5, 45.5, -72.8, -70.4),
    "NJ": (38.7, 41.6, -75.8, -73.6), "NM": (31.1, 37.2, -109.3, -102.8), "NY": (40.3, 45.2, -80.0, -71.6),
    "NC": (33.6, 36.8, -84.5, -75.2), "ND": (45.7, 49.2, -104.3, -96.3), "OH": (38.2, 42.2, -85.0, -80.3),
    "OK": (33.4, 37.2, -103.2, -94.2), "OR": (41.7, 46.5, -124.8, -116.2), "PA": (39.5, 42.5, -80.8, -74.4),
    "RI": (41.0, 42.2, -72.1, -71.0), "SC": (31.8, 35.5, -83.6, -78.3), "SD": (42.2, 46.2, -104.3, -96.2),
    "TN": (34.7, 36.9, -90.5, -81.4), "TX": (25.6, 36.7, -106.9, -93.3), "UT": (36.7, 42.2, -114.3, -108.8),
    "VT": (42.5, 45.2, -73.6, -71.3), "VA": (36.3, 39.7, -83.9, -75.0), "WA": (45.3, 49.2, -124.9, -116.7),
    "WV": (37.0, 40.8, -82.9, -77.5), "WI": (42.3, 47.3, -93.0, -86.5), "WY": (40.8, 45.2, -111.3, -103.8),
    # Canada
    "AB": (48.8, 60.2, -120.2, -109.8), "BC": (48.0, 60.2, -139.2, -114.0), "MB": (48.8, 60.2, -102.2, -88.8),
    "NB": (44.4, 48.3, -69.3, -63.5), "NL": (46.4, 60.6, -67.9, -52.3), "NS": (43.2, 47.2, -66.6, -59.5),
    "NT": (59.8, 79.0, -136.7, -101.8), "ON": (41.5, 57.0, -95.4, -74.2), "QC": (44.8, 62.8, -79.9, -57.0),
    "SK": (48.8, 60.2, -110.2, -101.2), "YT": (59.8, 69.8, -141.2, -123.8),
    # the neighbours a Florida or Texas antenna reaches
    "MX": (14.3, 32.9, -118.6, -86.5), "BS": (20.7, 27.4, -80.6, -72.6), "CU": (19.6, 23.5, -85.2, -74.0),
    "PR": (17.7, 18.7, -67.5, -65.1), "BM": (32.1, 32.6, -65.0, -64.5),
}

NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories", "ON": "Ontario",
    "QC": "Quebec", "SK": "Saskatchewan", "YT": "Yukon",
    "MX": "Mexico", "BS": "Bahamas", "CU": "Cuba", "PR": "Puerto Rico", "BM": "Bermuda",
}


def at(lat, lon, among=None):
    """The region a point is most likely in, from the boxes: the one whose
    box holds it and whose center is nearest. A box is not a boundary, so
    near a state line this can name the neighbour - which is why the name
    on a reverse-geocoded place is asked first and this only when the QTH
    is a bare grid square. None when no box holds it."""
    best, best_km2 = None, None
    for code, (south, north, west, east) in BOXES.items():
        if among is not None and code not in among:
            continue
        if not (south <= lat <= north and west <= lon <= east):
            continue
        d = (lat - (south + north) / 2) ** 2 + (lon - (west + east) / 2) ** 2
        if best_km2 is None or d < best_km2:
            best, best_km2 = code, d
    return best


def inside(region, lat, lon):
    """Whether a point is within the region's box; True for an unknown
    region, since no box is not the same as the wrong box."""
    box = BOXES.get((region or "").upper())
    if not box:
        return True
    south, north, west, east = box
    return south <= lat <= north and west <= lon <= east

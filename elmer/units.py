"""Which units this operator reads distances in.

One preference, and a deliberately narrow one: it governs **how far away a
thing is**. It does not touch the units the craft itself speaks in, and the
distinction matters more than it looks.

Nobody calls it the forty yard band. Wavelength is metres because the bands
are named in metres, wire is cut in feet because that is how wire is sold and
how every table in every handbook prints it, heights above ground are feet for
the same reason, hmF2 and skip distance are kilometres because that is what
ionosondes report and what every propagation paper uses. Converting those
would not be respectful of a preference, it would be vandalism - an operator
who sets "imperial" is telling ELMER how they think about a drive to a park,
not asking for the 40 m band to be renamed.

So what moves is the answer to "how far is that": parks and summits, repeaters,
the distance to a place. Three systems, because a maritime operator thinks in
nautical miles and has as much right to their own units as anybody else.
"""

KM_PER_MI = 1.609344
KM_PER_NMI = 1.852

SYSTEMS = {
    "metric": {
        "key": "metric", "label": "Metric", "short": "km",
        "per_km": 1.0, "long": "kilometres",
        "note": "Kilometres. What most of the world and every ionosonde uses.",
    },
    "imperial": {
        "key": "imperial", "label": "Imperial", "short": "mi",
        "per_km": 1.0 / KM_PER_MI, "long": "miles",
        "note": "Statute miles. What a road sign says in the United States.",
    },
    "nautical": {
        "key": "nautical", "label": "Nautical", "short": "NM",
        "per_km": 1.0 / KM_PER_NMI, "long": "nautical miles",
        "note": "Nautical miles. One minute of latitude, and what a chart "
                "and a maritime mobile operator work in.",
    },
}

DEFAULT = "imperial"


def system(name):
    """The system asked for, or the default. Never raises on a bad name."""
    return SYSTEMS.get(str(name or "").strip().lower()) or SYSTEMS[DEFAULT]


def from_km(km, name=DEFAULT):
    """A distance in kilometres, in the operator's units."""
    if km is None:
        return None
    return float(km) * system(name)["per_km"]


def to_km(value, name=DEFAULT):
    """The other way, for anything typed in."""
    if value is None:
        return None
    return float(value) / system(name)["per_km"]


def say(km, name=DEFAULT, digits=0):
    """A distance with its unit on it, for a screen or a sheet."""
    if km is None:
        return "—"
    value = from_km(km, name)
    unit = system(name)["short"]
    if digits <= 0:
        return "%d %s" % (round(value), unit)
    return "%.*f %s" % (digits, value, unit)


def short(name=DEFAULT):
    """Just the abbreviation, for a column heading or a field label."""
    return system(name)["short"]


def long_name(name=DEFAULT):
    return system(name)["long"]

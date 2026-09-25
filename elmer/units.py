"""Which units this operator reads in.

One preference, and it governs everything the program measures except the
names of the bands. Forty metres is called forty metres in Alabama and in
Aberdeen, because that is its name and not a measurement of anything; but how
far away a repeater is, how high a wire is hung, how long that wire is, how
far up the F2 layer sits and how tall the hill in the way stands are all
answers to a question the operator asked, and they come back in the units the
operator asked in.

This file used to argue the opposite, and argued it at length: that wire is
cut in feet because that is how wire is sold, that hmF2 is kilometres because
that is what an ionosonde reports and what every propagation paper prints, and
that converting those would be vandalism rather than respect. It reads well
and it is wrong. A paper printing kilometres tells you about the paper. The
operator this program is for is an American amateur who could not tell you how
many metres are in a hundred yards, and does not need to be able to; being
handed 300 km and 340 m by a program they told they read in miles is being
told their preference was noted and filed.

Two things keep their own units, and they are the same thing twice: a name is
not a measurement. Forty metres is the name of a band. hmF2 carries its units
in its name as well - it is what the ionosonde calls that number, it is how
every operator who has ever read one says it, and "the F2 layer is 186 miles
up" is not a translation, it is a different sentence. Where a quantity is
named rather than measured, the name wins.

Feet, for imperial and for nautical both. A nautical chart measures depth in
fathoms and height in feet, and a maritime operator in America is not reaching
for metres to find out how high to hang an antenna. The nautical mile is what
makes that system its own; the vertical is feet either way.

The helpers below have a counterpart in elmer.js - away(), high(), and the
text forms - and any measurement on a screen should come through one of them
rather than a multiplication written in place.
"""

KM_PER_MI = 1.609344
KM_PER_NMI = 1.852
M_PER_FT = 0.3048
M_PER_IN = 0.0254
M_PER_FT_INV = 1.0 / M_PER_FT
M_PER_IN_INV = 1.0 / M_PER_IN

SYSTEMS = {
    "metric": {
        "key": "metric", "label": "Metric", "short": "km",
        "per_km": 1.0, "long": "kilometers",
        # The vertical, and anything measured along a wire.
        "short_len": "m", "per_m": 1.0, "long_len": "meters",
        "short_small": "mm", "per_small": 1000.0, "long_small": "millimeters",
        "note": "Kilometers and meters.",
    },
    "imperial": {
        "key": "imperial", "label": "Imperial", "short": "mi",
        "per_km": 1.0 / KM_PER_MI, "long": "miles",
        "short_len": "ft", "per_m": M_PER_FT_INV, "long_len": "feet",
        "short_small": "in", "per_small": M_PER_IN_INV, "long_small": "inches",
        "note": "Statute miles and feet. What a road sign says in the "
                "United States, and how every antenna in it is measured.",
    },
    "nautical": {
        "key": "nautical", "label": "Nautical", "short": "NM",
        "per_km": 1.0 / KM_PER_NMI, "long": "nautical miles",
        # Feet, the same as imperial: a chart gives height in feet, and a
        # maritime operator in America hangs a wire in feet like everybody else.
        "short_len": "ft", "per_m": M_PER_FT_INV, "long_len": "feet",
        "short_small": "in", "per_small": M_PER_IN_INV, "long_small": "inches",
        "note": "Nautical miles for distance - one minute of latitude, what a "
                "chart works in - and feet for everything vertical.",
    },
}

DEFAULT = "imperial"


def system(name):
    """The system asked for, or the default. Never raises on a bad name."""
    return SYSTEMS.get(str(name or "").strip().lower()) or SYSTEMS[DEFAULT]


def from_km(km, name=DEFAULT):
    """A distance in kilometers, in the operator's units."""
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
        # Grouped: four figures of miles is a number somebody has to read.
        return "%s %s" % (format(int(round(value)), ","), unit)
    return "%.*f %s" % (digits, value, unit)


def short(name=DEFAULT):
    """Just the abbreviation, for a column heading or a field label."""
    return system(name)["short"]


def long_name(name=DEFAULT):
    return system(name)["long"]


# ---------------------------------------------------------------- the vertical
#
# Heights, depths and lengths of wire. Metres for metric; feet for imperial and
# for nautical both - see the note at the top about why nautical is not an
# exception here.


def from_m(metres, name=DEFAULT):
    """A height or a length in metres, in the operator's units."""
    if metres is None:
        return None
    return float(metres) * system(name)["per_m"]


def to_m(value, name=DEFAULT):
    """The other way, for anything typed in."""
    if value is None:
        return None
    return float(value) / system(name)["per_m"]


def say_len(metres, name=DEFAULT, digits=0):
    """A height or a length with its unit on it."""
    if metres is None:
        return "—"
    value = from_m(metres, name)
    unit = system(name)["short_len"]
    if digits <= 0:
        return "%s %s" % (format(int(round(value)), ","), unit)
    return "%.*f %s" % (digits, value, unit)


def short_len(name=DEFAULT):
    """Just the abbreviation - m or ft - for a heading or a field label."""
    return system(name)["short_len"]


def long_len(name=DEFAULT):
    return system(name)["long_len"]


def from_small(metres, name=DEFAULT):
    """Something measured across rather than along: wire gauge, a gap."""
    if metres is None:
        return None
    return float(metres) * system(name)["per_small"]


def say_small(metres, name=DEFAULT, digits=1):
    if metres is None:
        return "—"
    return "%.*f %s" % (digits, from_small(metres, name), system(name)["short_small"])


def short_small(name=DEFAULT):
    return system(name)["short_small"]


def say_ft(feet, name=DEFAULT, digits=0):
    """A length already in feet, in the operator's own units.

    The antenna code works in feet throughout - a half wave on 40 m is 33 feet
    to everyone who has ever cut one - so this takes that and renders it. Feet
    stay feet for imperial and nautical; metric gets metres, because that is
    what the operator asked for and a program that answers in feet anyway has
    not understood the question.
    """
    if feet is None:
        return "—"
    return say_len(float(feet) * M_PER_FT, name, digits)


def from_ft(feet, name=DEFAULT):
    """The number alone, for a caller placing its own unit."""
    if feet is None:
        return None
    return from_m(float(feet) * M_PER_FT, name)


def say_in(inches, name=DEFAULT, digits=1):
    """A length already in inches, in the operator's own - inches or mm."""
    if inches is None:
        return "—"
    return say_small(float(inches) * M_PER_IN, name, digits)

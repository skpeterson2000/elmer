"""The colors ELMER paints with, in one place.

Four families, one a kind of thing, so that a color on any page can be
read for what it is about before the label is read:

- BANDS, one distinct color a band, neighbours far apart. The family that
  has to be told apart at a glance and remembered: a band's color is the same
  wherever its name appears - the reach map, the band buttons, the Lab's
  chips, the outlook rows, the printed chart.
- KIND_COLOR, for what happens on a band - CW, digital, phone, image,
  beacons, satellite, repeaters, simplex, calling, special - the same
  color for a kind on every band. The pastel family: lightened and
  softened, so that a mode reads as a softer thing than a band even
  before the label is read, and the two families stay out of each
  other's way.
- CLASS_COLOR, for the license classes and the license-free services:
  the earth tones, the strata a person climbs through, older and quieter
  than the spectrum.
- ATTENTION, one color, for the one thing on a screen that must be
  found at once whatever else is there: the safety orange of ANSI Z535,
  which is the only published color convention in any of this. Used
  for "you are here" and nothing else, so that it keeps its meaning.

Nobody publishes a color a band: the FCC's rules carry none, and the
ARRL's band chart colors its bars by what may be sent there - CW, data,
phone, image - not by which band it is. So the band hues are ELMER's own.
They used to run the rainbow in frequency order, red at 160 m through to
violet at UHF, and that had two faults: adjacent bands, which are the ones
that have to be told apart, were the nearest colors of all, and the whole
row read as a pride flag on the dashboard rather than as a set of things.
Now each band has a color of its own, chosen so that its neighbours are
far from it - warm beside cool, light beside dark - the way a set of
resistors or a box of colored pencils is told apart, with no order in the
hues to be read as anything. 11 m is CB, not amateur, and is gray on
purpose: it borrows no hue from a band. The color is never the only cue;
the name is always printed beside it.

Chosen against simulated color blindness (Machado 2009, deutan, protan
and tritan) with the eight bands everyone uses - 160, 80, 40, 20, 15, 10,
2 m and 70 cm - kept apart under each by hue and by lightness both, so
that red-green blindness, which turns every pink into a blue and every
green into a yellow, still finds them distinct; every adjacent pair of
bands is close to 30 units apart in CIELAB or more, where 10 is plainly
different. The rarer bands sit where they do not crowd a common one. Every
band reads on the dark panel at 4.5:1 or better, because a band's name is
printed in it.

Each band has two values: the color for the dark screen, and the same
hue darkened into an ink for white paper. Keyed by the canonical name
("20 m"); look up with band_color(), which takes "20m" as well, because
the propagation model and every URL write it without the space.
"""

# The band family. Frequency order; the screen color, then the ink.
BANDS = {
    "160 m": ("#ef5a4c", "#ea1805"),
    "80 m": ("#74b9f2", "#0575d2"),
    "60 m": ("#a9a95a", "#797939"),
    "40 m": ("#f6c445", "#986d00"),
    "30 m": ("#9d9470", "#7e7552"),
    "20 m": ("#3dd6ae", "#138568"),
    "17 m": ("#f4b183", "#c65304"),
    "15 m": ("#c7b0ff", "#824fff"),
    "12 m": ("#f7c1b3", "#db3308"),
    "11 m": ("#9aa5b1", "#667789"),
    "10 m": ("#5b7cff", "#4268ff"),
    "6 m": ("#fff08a", "#857400"),
    "2 m": ("#ff5ec8", "#dd0092"),
    "1.25 m": ("#a3cf8c", "#4c842f"),
    "70 cm": ("#8ff0f5", "#038187"),
    "33 cm": ("#d8b78e", "#9c6a2c"),
    "23 cm": ("#dff5d8", "#34871a"),
}

# The mode family: pastel on the screen, the same hues as ink on paper.
KIND_COLOR = {
    "cw": "#a6caff", "digital": "#bfa0ff", "phone": "#b8f2c0", "image": "#f7e0a0",
    "beacon": "#f2a0a0", "satellite": "#9fe3e6", "repeater": "#f2ad78",
    "simplex": "#c9d072", "calling": "#ffffff", "special": "#8b98a5",
}
KIND_INK = {
    "cw": "#3d7ebf", "digital": "#7a4fbf", "phone": "#1f8f4e", "image": "#b8791f",
    "beacon": "#b03a48", "satellite": "#1f8f8f", "repeater": "#c2571f",
    "simplex": "#8a8f3a", "calling": "#111111", "special": "#666666",
}

# The license family: the strata, from the license-free services up.
CLASS_COLOR = {
    "none": "#d8c39a",        # sand - FRS, MURS, CB: no license
    "gmrs": "#8a9a5b",        # moss - a fee and a form
    "Novice": "#bfa77a",
    "Technician": "#c9a24a",  # ochre
    "General": "#c9784a",     # clay
    "Advanced": "#9a7a5b",    # umber
    "Extra": "#7c8a9a",       # slate
    "ham": "#c9784a",         # any amateur license, where the class is not the point
}

# The attention color: ANSI Z535 safety orange. One thing a screen.
ATTENTION = "#ff7900"

BAND_COLOR = {name: pair[0] for name, pair in BANDS.items()}
BAND_INK = {name: pair[1] for name, pair in BANDS.items()}


def band_key(name):
    """"20 m" and "20m" are the same band: the key is the name without spaces."""
    return str(name or "").replace(" ", "").lower()


_COLOR_BY_KEY = {band_key(k): v for k, v in BAND_COLOR.items()}
_INK_BY_KEY = {band_key(k): v for k, v in BAND_INK.items()}


def band_color(name, ink=False):
    """The band's color, for the screen or (ink=True) for paper; None if
    the name is not a band this program knows."""
    return (_INK_BY_KEY if ink else _COLOR_BY_KEY).get(band_key(name))


def rgb(hex_color):
    """"#52e888" as "82,232,136", for rgba() in a stylesheet."""
    return ",".join(str(int(hex_color[i:i + 2], 16)) for i in (1, 3, 5))


def contrast(hex_color, against="#0d1117"):
    """WCAG contrast ratio of a color on a background - the panel's, by
    default. 4.5 is the floor for text; the tests hold every band to it."""
    def luminance(h):
        parts = []
        for i in (1, 3, 5):
            c = int(h[i:i + 2], 16) / 255
            parts.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
        r, g, b = parts
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = luminance(hex_color), luminance(against)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def band_palette(names):
    """The bands named, each with its key and both colors, for the page
    head: the CSS custom properties and the JavaScript map are written from
    this, so there is one copy of the palette and it is here."""
    return [{"key": band_key(n), "name": n, "color": BAND_COLOR[n], "ink": BAND_INK[n],
             # the custom property's name (a CSS ident: 1.25 m is band-1-25m)
             # and the color as r,g,b, so a page can tint with rgba() and
             # need no color arithmetic of its own
             "css": "band-" + band_key(n).replace(".", "-"),
             "rgb": rgb(BAND_COLOR[n])}
            for n in names if n in BAND_COLOR]

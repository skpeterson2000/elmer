"""The colours ELMER paints with, in one place.

Four families, one a kind of thing, so that a colour on any page can be
read for what it is about before the label is read:

- BANDS, the saturated rainbow in frequency order. The family that has to
  be told apart at a glance and remembered: a band's colour is the same
  wherever its name appears - the reach map, the band buttons, the Lab's
  chips, the outlook rows, the printed chart.
- KIND_COLOUR, for what happens on a band - CW, digital, phone, image,
  beacons, satellite, repeaters, simplex, calling, special - the same
  colour for a kind on every band. The pastel family: the same hues
  lightened and softened, so that a mode reads as a softer thing than a
  band even before the label is read, and the two rainbows stay out of
  each other's way.
- CLASS_COLOUR, for the licence classes and the licence-free services:
  the earth tones, the strata a person climbs through, older and quieter
  than the spectrum.
- ATTENTION, one colour, for the one thing on a screen that must be
  found at once whatever else is there: the safety orange of ANSI Z535,
  which is the only published colour convention in any of this. Used
  for "you are here" and nothing else, so that it keeps its meaning.

Nobody publishes a colour a band: the FCC's rules carry none, and the
ARRL's band chart colours its bars by what may be sent there - CW, data,
phone, image - not by which band it is. So the band hues are ELMER's
own, and they are chosen so the order of the spectrum is the order of the
rainbow: red at 160 m, through yellow and green to blue at 10 m, then
violet and pink for VHF and UHF. A band not yet learnt can be placed by
its neighbours. 11 m is CB, not amateur, and is grey on purpose: it
borrows no hue from a band. The colour is never the only cue; the name is
always printed beside it.

Tuned against simulated colour blindness (Machado 2009, deutan, protan
and tritan) with the eight bands everyone uses - 160, 80, 40, 20, 15,
10, 2 m and 70 cm - kept apart by lightness where hue collapses: red-green
blindness turns every pink into a blue and every green into a yellow, so
those bands step light and dark along the spectrum rather than only round
it. The rarer bands may sit near their neighbours. Every band reads on the
dark panel at 4.5:1 or better, because a band's name is printed in it.

Each band has two values: the colour for the dark screen, and the same
hue darkened into an ink for white paper. Keyed by the canonical name
("20 m"); look up with band_colour(), which takes "20m" as well, because
the propagation model and every URL write it without the space.
"""

# The band family. Frequency order; the screen colour, then the ink.
BANDS = {
    "160 m": ("#ff3b3b", "#c11f25"),
    "80 m": ("#f5871a", "#9f4c00"),
    "60 m": ("#d9b25a", "#7a6018"),
    "40 m": ("#ffe14d", "#726300"),
    "30 m": ("#aef03c", "#377100"),
    "20 m": ("#52e888", "#00752e"),
    "17 m": ("#35d0b8", "#007361"),
    "15 m": ("#5cc0f8", "#006b96"),
    "12 m": ("#7a9cff", "#3f60ad"),
    "11 m": ("#9aa5b1", "#5b646d"),
    "10 m": ("#5570ff", "#4258cd"),
    "6 m": ("#a070ff", "#724cbf"),
    "2 m": ("#ff5ebe", "#b02c7e"),
    "1.25 m": ("#d68af0", "#864b9b"),
    "70 cm": ("#ffcbea", "#7e586f"),
    "33 cm": ("#dc94c0", "#895174"),
    "23 cm": ("#ffd9c9", "#785d52"),
}

# The mode family: pastel on the screen, the same hues as ink on paper.
KIND_COLOUR = {
    "cw": "#a6caff", "digital": "#bfa0ff", "phone": "#b8f2c0", "image": "#f7e0a0",
    "beacon": "#f2a0a0", "satellite": "#9fe3e6", "repeater": "#f2ad78",
    "simplex": "#c9d072", "calling": "#ffffff", "special": "#8b98a5",
}
KIND_INK = {
    "cw": "#3d7ebf", "digital": "#7a4fbf", "phone": "#1f8f4e", "image": "#b8791f",
    "beacon": "#b03a48", "satellite": "#1f8f8f", "repeater": "#c2571f",
    "simplex": "#8a8f3a", "calling": "#111111", "special": "#666666",
}

# The licence family: the strata, from the licence-free services up.
CLASS_COLOUR = {
    "none": "#d8c39a",        # sand - FRS, MURS, CB: no licence
    "gmrs": "#8a9a5b",        # moss - a fee and a form
    "Novice": "#bfa77a",
    "Technician": "#c9a24a",  # ochre
    "General": "#c9784a",     # clay
    "Advanced": "#9a7a5b",    # umber
    "Extra": "#7c8a9a",       # slate
    "ham": "#c9784a",         # any amateur licence, where the class is not the point
}

# The attention colour: ANSI Z535 safety orange. One thing a screen.
ATTENTION = "#ff7900"

BAND_COLOUR = {name: pair[0] for name, pair in BANDS.items()}
BAND_INK = {name: pair[1] for name, pair in BANDS.items()}


def band_key(name):
    """"20 m" and "20m" are the same band: the key is the name without spaces."""
    return str(name or "").replace(" ", "").lower()


_COLOUR_BY_KEY = {band_key(k): v for k, v in BAND_COLOUR.items()}
_INK_BY_KEY = {band_key(k): v for k, v in BAND_INK.items()}


def band_colour(name, ink=False):
    """The band's colour, for the screen or (ink=True) for paper; None if
    the name is not a band this program knows."""
    return (_INK_BY_KEY if ink else _COLOUR_BY_KEY).get(band_key(name))


def rgb(hex_colour):
    """"#52e888" as "82,232,136", for rgba() in a stylesheet."""
    return ",".join(str(int(hex_colour[i:i + 2], 16)) for i in (1, 3, 5))


def contrast(hex_colour, against="#0d1117"):
    """WCAG contrast ratio of a colour on a background - the panel's, by
    default. 4.5 is the floor for text; the tests hold every band to it."""
    def luminance(h):
        parts = []
        for i in (1, 3, 5):
            c = int(h[i:i + 2], 16) / 255
            parts.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
        r, g, b = parts
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = luminance(hex_colour), luminance(against)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def band_palette(names):
    """The bands named, each with its key and both colours, for the page
    head: the CSS custom properties and the JavaScript map are written from
    this, so there is one copy of the palette and it is here."""
    return [{"key": band_key(n), "name": n, "colour": BAND_COLOUR[n], "ink": BAND_INK[n],
             # the custom property's name (a CSS ident: 1.25 m is band-1-25m)
             # and the colour as r,g,b, so a page can tint with rgba() and
             # need no colour arithmetic of its own
             "css": "band-" + band_key(n).replace(".", "-"),
             "rgb": rgb(BAND_COLOUR[n])}
            for n in names if n in BAND_COLOUR]

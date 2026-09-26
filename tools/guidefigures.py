#!/usr/bin/env python3
"""Drawn figures for the User's Guide - the diagrams, not the screenshots.

    python3 tools/guidefigures.py           # every figure
    python3 tools/guidefigures.py cw        # one chapter's
    python3 tools/guidefigures.py --list    # what there is

tools/guideshots.py takes pictures *of the program*: this panel, that pane,
the thing being described. Those answer "where is it". They cannot answer
"what is a dah", "what does Farnsworth actually change", "why is fifteen
minutes five passes of three" - because none of those is a thing on a
screen. They are ideas, and an idea needs a drawing.

That distinction is the whole reason this file exists beside the other one.
A chapter with nothing but screenshots reads, to somebody who scans the
pictures first, as a chapter with no pictures at all: every figure is a
photograph of some furniture, and the argument is still locked in the prose.

So these are drawn on purpose, for the two things they have to survive:

- **Print.** The guide is a book somebody takes to the garden or the bench.
  These are dark ink on white, with no screenshot's dark panel to put a
  block of toner on the page, and they are drawn large enough that the
  scale the PDF applies leaves the labels at about ten point.
- **Being read alone.** Everything is labelled inside the frame. Somebody
  who reads only the figures and its caption should come away with the
  point; the prose is then the detail, which is the order a good many
  people read in and the order this guide had been refusing to serve.

Each figure is a small HTML page drawn with inline SVG and photographed by
the same headless Chromium the rest of the tooling uses. SVG because the
typography has to be right, and a browser because it is already here.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

FIGURES_DIR = ROOT / "docs" / "figures" / "guide"

# The page these are printed on is white, so the ink is dark. The accents are
# picked to survive a grayscale printer as well: the amber is dark enough to
# read as "marked" against the green even with the color thrown away.
INK = "#1b2733"
MUTED = "#6b7885"
RULE = "#c3ccd4"
SOFT = "#eef2f6"
AMBER = "#a8620a"
GREEN = "#2f7d32"
RED = "#b3261e"
SANS = "Segoe UI, Inter, system-ui, -apple-system, sans-serif"
MONO = "Consolas, DejaVu Sans Mono, monospace"

# Drawn at this width, which the PDF scales to the text frame. It is chosen
# so a 22 px label lands at about ten point on the page - big enough to read
# without holding the book up to the light.
WIDE = 1100


def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, size=22, fill=INK, anchor="start", weight="400", font=SANS, style=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" '
            f'style="{style}">{esc(s)}</text>')


def line(x1, y1, x2, y2, stroke=RULE, width=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}"{d}/>')


def rect(x, y, w, h, fill=INK, rx=3, stroke="none", width=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0.0, w):.1f}" height="{h:.1f}" '
            f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"{d}/>')


def brace(x1, x2, y, label, color=MUTED, size=19, drop=10, anchor="middle"):
    """A measurement under something, with its label below it.

    Centred by default, which is right until the span is short and near an
    edge - then the label hangs off the page and the first word of it is
    lost. `anchor` of "start" or "end" pins it to that end of the brace
    instead. The check in :func:`take` is what catches the ones missed.
    """
    at = {"middle": (x1 + x2) / 2, "start": x1, "end": x2}[anchor]
    return "".join([
        line(x1, y, x2, y, color, 1.4),
        line(x1, y - 5, x1, y + 5, color, 1.4),
        line(x2, y - 5, x2, y + 5, color, 1.4),
        text(at, y + drop + size, label, size, color, anchor),
    ])


# --------------------------------------------------------------- the code

MORSE = {
    "K": "-.-", "M": "--", "R": ".-.", "S": "...", "H": "....", "5": ".....",
    "A": ".-", "U": "..-", "P": ".--.", "E": ".",
}


def elements(code):
    """A character's marks and the gaps inside it, in units: (width, ink)."""
    out = []
    for n, mark in enumerate(code):
        if n:
            out.append((1, False))
        out.append((3 if mark == "-" else 1, True))
    return out


def keyed(word, unit=30, gap_letter=3, gap_word=7):
    """A string of characters as a run of (x, width, ink) in pixels, and the
    span of each letter, so a diagram can label what it is pointing at."""
    x, runs, spans = 0.0, [], []
    for n, ch in enumerate(word):
        if ch == " ":
            x += gap_word * unit
            continue
        if n and word[n - 1] != " ":
            x += gap_letter * unit
        start = x
        for width, ink in elements(MORSE[ch]):
            if ink:
                runs.append((x, width * unit, True))
            x += width * unit
        spans.append((ch, start, x))
    return runs, spans, x


def keyline(word, y, unit=30, height=34, color=INK, gap_letter=3, gap_word=7,
            baseline=True, x0=0.0):
    """One line of keying, drawn: marks as bars, silence as the space left."""
    runs, spans, width = keyed(word, unit, gap_letter, gap_word)
    out = []
    if baseline:
        out.append(line(x0, y + height + 9, x0 + width, y + height + 9, RULE, 1.2))
    for x, w, _ in runs:
        out.append(rect(x0 + x, y, w, height, color, 4))
    return "".join(out), spans, width


# -------------------------------------------------------------- figure: timing

def fig_cw_timing():
    """Everything in the code is one length or three, and so is the silence."""
    u, y = 30, 150
    body, spans, width = keyline("KM R", y, unit=u)
    x0 = (WIDE - width) / 2
    body, spans, width = keyline("KM R", y, unit=u, x0=x0)
    out = [body]
    for ch, a, b in spans:
        out.append(text(x0 + (a + b) / 2, y - 26, ch, 30, INK, "middle", "600", MONO))
    # What each piece is, pointed at where it happens.
    k_dah_1 = (x0, x0 + 3 * u)
    k_gap = (x0 + 3 * u, x0 + 4 * u)
    k_dit = (x0 + 4 * u, x0 + 5 * u)
    letter_gap = (x0 + 9 * u, x0 + 12 * u)
    word_gap = (x0 + 19 * u, x0 + 26 * u)
    out.append(brace(*k_dah_1, y + height_of() + 22, "dah - 3"))
    out.append(brace(*k_dit, y + height_of() + 22, "dit - 1"))
    out.append(brace(*k_gap, y + height_of() + 72, "1", AMBER))
    out.append(text(x0 + 4.5 * u, y + height_of() + 132, "inside a letter", 19, AMBER, "middle"))
    out.append(brace(*letter_gap, y + height_of() + 22, "3", AMBER))
    out.append(text(x0 + 10.5 * u, y + height_of() + 82, "between letters", 19, AMBER, "middle"))
    out.append(brace(*word_gap, y + height_of() + 22, "7", AMBER))
    out.append(text(x0 + 22.5 * u, y + height_of() + 82, "between words", 19, AMBER, "middle"))
    out.append(text(WIDE / 2, 56, "One unit is one dit. Everything else is counted in them.",
                    24, MUTED, "middle"))
    return svg(out, 330)


def height_of():
    return 34


# ---------------------------------------------------------- figure: Farnsworth

def fig_cw_farnsworth():
    """Why the gaps are stretched and the characters never are."""
    out = []
    total = 820
    x0 = (WIDE - total) / 2

    # Slowed the wrong way: the whole thing dilated, characters and all.
    slow_u = total / 19.0
    body, spans, _ = keyline("KM", 130, unit=slow_u, x0=x0)
    out.append(body)
    for ch, a, b in spans:
        out.append(text(x0 + (a + b) / 2, 112, ch, 26, INK, "middle", "600", MONO))
    out.append(text(x0, 72, "Slowed the usual way", 24, RED, "start", "600"))
    out.append(text(x0, 232,
                    "The letter itself is slower, so it is a different sound - and a sound "
                    "learned at five", 20, MUTED))
    out.append(text(x0, 258,
                    "words a minute has to be unlearned to copy at twenty.", 20, MUTED))

    # Farnsworth: characters at speed, the silence between them stretched.
    fast_u = 18.0
    chars = (9 + 7) * fast_u
    gap = total - chars
    body = []
    x = x0
    for n, ch in enumerate("KM"):
        if n:
            body.append(rect(x, 360, gap, 34, SOFT, 4))
            body.append(brace(x, x + gap, 424, "the gap does the slowing", AMBER))
            x += gap
        start = x
        for width, ink in elements(MORSE[ch]):
            if ink:
                body.append(rect(x, 360, width * fast_u, 34, INK, 4))
            x += width * fast_u
        body.append(text((start + x) / 2, 342, ch, 26, INK, "middle", "600", MONO))
        body.append(brace(start, x, 403, "at full speed", GREEN, 18, 4))
    out.append(line(x0, 403, x0 + total, 403, RULE, 1.2))
    out.append("".join(body))
    out.append(text(x0, 306, "Farnsworth - what ELMER sends", 24, GREEN, "start", "600"))
    out.append(text(x0, 500,
                    "Both lines take the same time to send. The letter sounds the same at "
                    "five words a", 20, MUTED))
    out.append(text(x0, 526,
                    "minute as it will at twenty, so nothing has to be unlearned later.",
                    20, MUTED))
    return svg(out, 560)


# --------------------------------------------------------------- figure: Koch

def fig_cw_koch():
    """The order characters arrive in, and where a learner stands in it."""
    from elmer import cw
    out, per = [], 8
    bw, bh, gx, gy = 122, 92, 12, 16
    left = (WIDE - (per * bw + (per - 1) * gx)) / 2
    for n, ch in enumerate(cw.KOCH_ORDER):
        col, row = n % per, n // per
        x = left + col * (bw + gx)
        y = 106 + row * (bh + gy)
        first = n < 2
        out.append(rect(x, y, bw, bh, "#ffffff", 8,
                        AMBER if first else RULE, 2.5 if first else 1.5))
        out.append(text(x + bw / 2, y + 40, ch, 30, INK, "middle", "600", MONO))
        # The code under it, drawn rather than spelled: the shape is the thing
        # being learned, and reading ".-" is not hearing it.
        code = cw.MORSE.get(ch, "")
        w = sum(3 if m == "-" else 1 for m in code) + max(0, len(code) - 1)
        cx = x + bw / 2 - w * 4.0
        for m, mark in enumerate(code):
            width = (3 if mark == "-" else 1) * 8.0
            out.append(rect(cx, y + 58, width, 9, MUTED, 2))
            cx += width + 8.0
    out.append(text(left, 48, "K and M first - with one character there is nothing to tell apart",
                    22, AMBER))
    out.append(text(left, 78, "One more joins when every character you already have is solid",
                    22, MUTED))
    return svg(out, 106 + 5 * (bh + gy) + 20)


# ---------------------------------------------------------------- figure: day

def fig_cw_day():
    """Fifteen minutes, two ways - and why the gaps are the lesson."""
    out = []
    total, x0 = 900, (WIDE - 900) / 2
    out.append(text(x0, 56, "Fifteen minutes in one sitting", 24, RED, "start", "600"))
    out.append(rect(x0, 78, total, 54, SOFT, 6, RULE, 1.5))
    out.append(text(x0 + total / 2, 113, "one pass, fifteen minutes", 22, MUTED, "middle"))
    out.append(text(x0, 168,
                    "Nothing is fetched from cold after the first minute of it. What you take "
                    "from the", 20, MUTED))
    out.append(text(x0, 194, "eleventh minute of K and M is not K and M.", 20, MUTED))

    out.append(text(x0, 268, "Fifteen minutes as five passes of three", 24, GREEN, "start", "600"))
    each, gap = 120, 75
    for n in range(5):
        x = x0 + n * (each + gap)
        out.append(rect(x, 290, each, 54, "#ffffff", 6, GREEN, 2))
        out.append(text(x + each / 2, 325, "3 min", 21, GREEN, "middle", "600"))
        if n < 4:
            gx = x + each
            out.append(line(gx + 8, 317, gx + gap - 8, 317, AMBER, 1.6, "5 5"))
            out.append(text(gx + gap / 2, 372, "away", 18, AMBER, "middle"))
    out.append(text(x0, 432,
                    "Same quarter of an hour. The difference is that each pass starts with the "
                    "character", 20, MUTED))
    out.append(text(x0, 458,
                    "fetched again from cold, after your mind has been somewhere else - and "
                    "that fetch is", 20, MUTED))
    out.append(text(x0, 484, "the rep that counts. The gaps are not a rest; they are the "
                             "mechanism.", 20, MUTED))
    return svg(out, 520)


# ---------------------------------------------------------------- figure: set

def fig_cw_set():
    """A set of passes carries into the next day rather than expiring."""
    out = []
    x0, pip, gap = 90, 96, 18
    out.append(text(x0, 58, "One set of five passes", 24, INK, "start", "600"))
    done = [("Mon evening", 3, GREEN), ("Tue morning", 2, GREEN)]
    x = x0
    for label, count, color in done:
        start = x
        for _ in range(count):
            out.append(rect(x, 96, pip, 56, "#ffffff", 6, color, 2))
            out.append(text(x + pip / 2, 132, "pass", 19, color, "middle"))
            x += pip + gap
        out.append(brace(start, x - gap, 178, label, MUTED))
    out.append(brace(x0, x - gap, 244, "still one set - it carries", AMBER))

    x2 = x0 + 620
    out.append(text(x2, 58, "The day after that", 24, MUTED, "start", "600"))
    for n in range(2):
        out.append(rect(x2 + n * (pip + gap), 96, pip, 56, "#ffffff", 6, RULE, 1.5, "5 4"))
        out.append(text(x2 + n * (pip + gap) + pip / 2, 132, "new", 19, MUTED, "middle"))
    out.append(brace(x2, x2 + pip * 2 + gap, 178, "a new set opens", MUTED))
    # One statement across the full width. Two columns of prose under two
    # columns of drawing is how the left one ran into the right one.
    out.append(text(x0, 322,
                    "Three passes before the evening went sideways is three of five, not a "
                    "failure, and the last", 20, MUTED))
    out.append(text(x0, 348,
                    "two are offered the next morning. Past that day a new set opens, "
                    "because a set that never", 20, MUTED))
    out.append(text(x0, 374, "closes is not a set either.", 20, MUTED))
    return svg(out, 410)


# --------------------------------------------------------------- figure: cold

def fig_cw_cold():
    """The first rep of a sitting, and the day after it."""
    out = []
    x0 = 90
    out.append(text(x0, 56, "One sitting, one character", 24, INK, "start", "600"))
    out.append(line(x0, 150, WIDE - 90, 150, RULE, 1.5))
    xs = [x0 + 120, x0 + 300, x0 + 360, x0 + 420, x0 + 486, x0 + 548, x0 + 612]
    for n, x in enumerate(xs):
        cold = n == 0
        out.append(rect(x - 17, 122, 34, 56, "#ffffff", 6, AMBER if cold else RULE,
                        2.5 if cold else 1.5))
        out.append(text(x, 161, "K", 24, AMBER if cold else MUTED, "middle", "600", MONO))
    out.append(brace(x0, xs[0] - 17, 206, "a minute or more since the last K",
                     AMBER, anchor="start"))
    out.append(text(xs[0], 100, "cold", 21, AMBER, "middle", "600"))
    out.append(brace(xs[1] - 17, xs[-1] + 17, 206, "warm - the drill is running", MUTED))
    out.append(text(x0, 296,
                    "The cold one is the rep that says the learning is there. It is how a dog "
                    "is judged on", 20, MUTED))
    out.append(text(x0, 322,
                    "“sit” - not the tenth in a row with a treat already in the air, "
                    "but the first of the walk.", 20, MUTED))

    out.append(text(x0, 402, "And the morning after", 24, INK, "start", "600"))
    days = [("Mon", True), ("Tue", True), ("Wed", False)]
    for n, (day, hit) in enumerate(days):
        x = x0 + n * 150
        out.append(rect(x, 430, 120, 64, "#ffffff", 8, GREEN if hit else RULE,
                        2 if hit else 1.5, None if hit else "5 4"))
        out.append(text(x + 60, 462, day, 20, MUTED, "middle"))
        out.append(text(x + 60, 484, "cold, landed" if hit else "not yet", 17,
                        GREEN if hit else MUTED, "middle"))
    out.append(text(x0 + 470, 462,
                    "Two separate days is a night survived, and a night", 21, GREEN))
    out.append(text(x0 + 470, 490,
                    "is the only thing that settles anything.", 21, GREEN))
    return svg(out, 540)


# -------------------------------------------------------------- figure: solid

def fig_cw_solid():
    """The two roads to a character being solid."""
    out = []
    x0, box, gap = 90, 26, 7
    out.append(text(x0, 56, "Nine in ten of the last thirty", 24, INK, "start", "600"))
    misses = {4, 17, 25}
    for n in range(30):
        x = x0 + n * (box + gap)
        hit = n not in misses
        out.append(rect(x, 80, box, box, GREEN if hit else RED, 4))
    out.append(brace(x0, x0 + 30 * (box + gap) - gap, 132,
                     "the last thirty sends - a rough first day is forgiven", MUTED))

    out.append(text(x0, 246, "Or twelve clean in a row, one of them cold", 24, INK, "start", "600"))
    for n in range(12):
        x = x0 + n * (box + gap)
        out.append(rect(x, 270, box, box, GREEN, 4))
    out.append(rect(x0 - 3, 267, box + 6, box + 6, "none", 6, AMBER, 2.5))
    out.append(text(x0 - 14, 289, "cold", 17, AMBER, "end"))
    out.append(brace(x0, x0 + 12 * (box + gap) - gap, 322,
                     "the shorter road, for somebody who already knows it", MUTED))
    out.append(text(x0, 404,
                    "Twelve clean in a row is the stronger evidence of the two: eighteen right "
                    "out of", 20, MUTED))
    out.append(text(x0, 430,
                    "twenty makes a 35 per cent case that a character is above nine in ten, and "
                    "a clean", 20, MUTED))
    out.append(text(x0, 456, "run of twelve makes a 75 per cent case - in eight fewer sends.",
                    20, MUTED))
    return svg(out, 490)


# ------------------------------------------------------------ figure: qualify

def fig_cw_qualify():
    """Five minutes sent, one clean minute asked for, and it ends there."""
    out = []
    x0, total = 90, WIDE - 180
    minute = total / 5.0
    out.append(text(x0, 50, "Five minutes of plain traffic, at the speed you name",
                    24, INK, "start", "600"))
    out.append(rect(x0, 96, total, 62, SOFT, 6, RULE, 1.5))
    clean_from, clean_to = x0 + minute * 1.6, x0 + minute * 2.6
    out.append(rect(clean_from, 96, clean_to - clean_from, 62, "#ffffff", 6, GREEN, 3))
    out.append(text((clean_from + clean_to) / 2, 134, "one clean minute", 21, GREEN,
                    "middle", "600"))
    out.append(rect(clean_to, 96, x0 + total - clean_to, 62, "none", 6, RULE, 1.5, "6 5"))
    out.append(text((clean_to + x0 + total) / 2, 134, "never asked for", 20, MUTED, "middle"))
    for n in range(6):
        x = x0 + n * minute
        out.append(line(x, 158, x, 176, RULE, 1.5))
        out.append(text(x, 200, f"{n}:00", 18, MUTED, "middle"))
    out.append(line(clean_to, 92, clean_to, 176, AMBER, 2, "6 4"))
    out.append(text(clean_to, 84, "it ends here", 21, AMBER, "middle", "600"))
    out.append(text(x0, 272,
                    "A miss ends the stretch and a new one starts, so a scrambled first half "
                    "minute is", 20, MUTED))
    out.append(text(x0, 298,
                    "not held against you: what counts is the best clean minute anywhere in "
                    "the run.", 20, MUTED))
    out.append(text(x0, 324,
                    "The run's sends are real sends, so what you copied opens the lesson.",
                    20, MUTED))
    return svg(out, 356)


# ------------------------------------------------------------- figure: ladder

def fig_cw_ladder():
    """Where the speeds sit, and who is up there."""
    from elmer import cw
    out = []
    x0, total, h = 80, WIDE - 160, 70
    rungs = cw.SPEED_LADDER
    step = total / len(rungs)
    for n, rung in enumerate(rungs):
        x = x0 + n * step
        top = n % 2 == 0
        out.append(rect(x, 150, step - 6, h, "#ffffff", 6, RULE, 1.5))
        span = (f"{rung['from']}-{rung['to']}" if rung["to"] < 900
                else f"{rung['from']}+")
        out.append(text(x + step / 2 - 3, 194, span, 24, INK, "middle", "600"))
        name = rung["name"]
        if len(name) > 22:
            name = name.split(",")[0]
        y = 126 if top else 248
        out.append(text(x + step / 2 - 3, y, name, 18, MUTED, "middle"))
        out.append(line(x + step / 2 - 3, 150 if top else 220,
                        x + step / 2 - 3, 136 if top else 234, RULE, 1.2))
    out.append(text(x0, 66, "Words a minute, and what is done at each", 24, INK, "start", "600"))
    out.append(text(x0, 98, "5 was Novice, 13 was General, 20 was Extra - the tests are gone, "
                            "the speeds are not", 20, MUTED))
    out.append(text(x0, 312, "Somewhere in the teens the ear stops assembling letters and "
                             "starts hearing whole words.", 20, MUTED))
    out.append(text(x0, 338, "That is the change worth waiting for, and it is what all of this "
                             "is for.", 20, MUTED))
    return svg(out, 370)


# ------------------------------------------------------------- figure: shapes

def fig_cw_shapes():
    """Why particular pairs get confused, drawn rather than described."""
    out = []
    u, x0 = 30, 110
    pairs = [("K", "R", "mirror images of each other"),
             ("S", "H", "the same sound, one dit longer")]
    for n, (a, b, why) in enumerate(pairs):
        top = 90 + n * 210
        for m, ch in enumerate((a, b)):
            y = top + m * 76
            body, _, width = keyline(ch, y, unit=u, height=30, x0=x0, baseline=False)
            out.append(body)
            out.append(text(x0 - 26, y + 24, ch, 28, INK, "end", "600", MONO))
        out.append(text(x0 + 420, top + 62, why, 21, MUTED))
    out.append(text(x0 - 26, 56, "K and R", 22, AMBER, "start", "600"))
    out.append(text(x0 - 26, 266, "S and H", 22, AMBER, "start", "600"))
    out.append(text(x0 - 26, 470,
                    "A miss is worth more than a hit here: what a character was heard as is "
                    "what still", 20, MUTED))
    out.append(text(x0 - 26, 496,
                    "needs separating, and ELMER keeps it per character and tells you.",
                    20, MUTED))
    return svg(out, 530)


# ------------------------------------------------------------------ the frame

def svg(parts, height):
    return (f'<svg id="fig" xmlns="http://www.w3.org/2000/svg" width="{WIDE}" '
            f'height="{height:.0f}" viewBox="0 0 {WIDE} {height:.0f}">'
            f'<rect width="{WIDE}" height="{height:.0f}" fill="#ffffff"/>'
            + "".join(parts) + "</svg>")


# ------------------------------------------------------- figure: a band strip

def fig_band_strip():
    """How to read one band's bar, which is the whole page in miniature."""
    out = []
    x0, w, y = 110, WIDE - 220, 170
    # 40 meters, 7.000 to 7.300, as the chart lays it out for a General.
    segs = [("CW, data", 0.00, 0.42, False), ("phone", 0.42, 0.58, True),
            ("phone", 0.58, 1.00, False)]
    out.append(text(x0, 56, "One band, and what the bar is telling you", 24, INK,
                    "start", "600"))
    out.append(text(x0, 88, "40 meters, as it looks to a General - the same shape every "
                            "band's bar has.", 20, MUTED))
    hatch = ('<defs><pattern id="nope" width="10" height="10" '
             'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             f'<line x1="0" y1="0" x2="0" y2="10" stroke="{RED}" stroke-width="4"/>'
             '</pattern></defs>')
    out.append(hatch)
    for label, a, b, barred in segs:
        out.append(rect(x0 + w * a, y, w * (b - a), 76, "#ffffff", 4, RULE, 1.5))
        out.append(rect(x0 + w * a, y, w * (b - a), 76, GREEN if not barred else "#ffffff",
                        4, RULE, 1.5))
        if barred:
            out.append(rect(x0 + w * a, y, w * (b - a), 76, "url(#nope)", 4, RED, 2))
        out.append(text(x0 + w * (a + b) / 2, y + 46, label, 20,
                        "#ffffff" if not barred else RED, "middle", "600"))
    for frac, mhz in ((0.0, "7.000"), (0.42, "7.125"), (0.58, "7.175"), (1.0, "7.300")):
        x = x0 + w * frac
        out.append(line(x, y + 76, x, y + 92, RULE, 1.4))
        out.append(text(x, y + 116, mhz, 19, MUTED, "middle"))
    out.append(brace(x0, x0 + w * 0.42, y + 148, "what you may use, and for what", GREEN))
    out.append(brace(x0 + w * 0.42, x0 + w * 0.58, y + 148, "hatched: not your class", RED))
    out.append(rect(x0, 400, WIDE - 220, 130, SOFT, 8))
    out.append(text(x0 + 24, 436, "Hatched is the part of the band your license does not "
                                  "reach.", 21, INK, "start", "600"))
    out.append(text(x0 + 24, 466, "Change the class at the top and the hatching moves - "
                                  "which is how you find out whether the", 20, MUTED))
    out.append(text(x0 + 24, 492, "upgrade is worth sitting for. It changes only what is on "
                                  "the screen: it is not a claim about", 20, MUTED))
    out.append(text(x0 + 24, 518, "what you hold, and it opens no study pool.", 20, MUTED))
    return svg(out, 560)


# --------------------------------------------------- figure: what upgrading buys

def fig_band_classes():
    """What a class is actually worth, on the one band people argue about."""
    out = []
    x0, w = 210, 560
    rows = [("Technician", [(0.00, 0.10)], "a sliver of CW, and no more"),
            ("General", [(0.00, 0.42), (0.58, 1.00)], "most of it, phone included"),
            ("Amateur Extra", [(0.00, 1.00)], "the whole band")]
    out.append(text(110, 56, "The same band, three licenses", 24, INK, "start", "600"))
    out.append(text(110, 88, "40 meters. This is the argument for sitting the next exam, "
                             "drawn.", 20, MUTED))
    for n, (name, spans, why) in enumerate(rows):
        y = 140 + n * 104
        out.append(text(x0 - 24, y + 42, name, 21, INK, "end", "600"))
        out.append(rect(x0, y, w, 62, SOFT, 5, RULE, 1.4))
        for a, b in spans:
            out.append(rect(x0 + w * a, y, w * (b - a), 62, GREEN, 5))
        out.append(text(x0 + w + 20, y + 42, why, 20, MUTED))
    out.append(text(x0, 480, "7.000", 19, MUTED, "middle"))
    out.append(text(x0 + w, 480, "7.300", 19, MUTED, "middle"))
    out.append(text(110, 528, "Read a class above your own on purpose - that is what the "
                              "picker is for. A chart printed", 20, MUTED))
    out.append(text(110, 554, "for a class you do not hold says on its face that it is a "
                              "study sheet and not a license.", 20, MUTED))
    return svg(out, 590)


# ------------------------------------------------- figure: will this contact work

def fig_contact_budget():
    """Why a link works or does not, as the sum it actually is."""
    out = []
    steps = [("your power", 46, GREEN), ("your antenna", 14, GREEN),
             ("the path", -128, RED), ("their antenna", 12, GREEN)]
    noise = -78.0                       # their noise floor, not a subtraction
    # The scale comes from the numbers rather than being guessed at: a path
    # loss is a hundred and more decibels, and a waterfall drawn to a fixed
    # unit walks straight off the bottom of the page.
    levels, level = [0.0], 0.0
    for _, db, _c in steps:
        level += db
        levels.append(level)
    lo, hi = min(levels + [noise]), max(levels)
    top, bottom = 200, 470
    unit = (bottom - top) / float(hi - lo)
    def at(value):
        return bottom - (value - lo) * unit
    x0, w, gap = 130, 118, 18
    x, level = x0, 0.0
    for label, db, color in steps:
        y_from, y_to = at(level), at(level + db)
        out.append(rect(x, min(y_from, y_to), w, abs(y_to - y_from), color, 4))
        out.append(text(x + w / 2, min(y_from, y_to) - 12, f"{db:+d} dB", 20, color,
                        "middle", "600"))
        out.append(text(x + w / 2, 512, label, 18, MUTED, "middle"))
        level += db
        out.append(line(x + w, at(level), x + w + gap, at(level), RULE, 1.4, "4 4"))
        x += w + gap
    out.append(line(x0 - 26, at(0.0), x + 24, at(0.0), INK, 2))
    out.append(text(x0 - 34, at(0.0) + 6, "0", 19, MUTED, "end"))
    out.append(line(x0 - 26, at(level), x + 150, at(level), AMBER, 2.5, "7 5"))
    out.append(text(x + 24, at(level) - 12, "what lands there", 20, AMBER))
    # The noise floor is a threshold, not a term in the sum: the question is
    # whether what arrives is above it, and by how much.
    out.append(line(x0 - 26, at(noise), x + 150, at(noise), RED, 2.5, "7 5"))
    out.append(text(x + 24, at(noise) + 24, "their noise floor", 20, RED))
    out.append(line(x + 110, at(level), x + 110, at(noise), GREEN, 2.5))
    out.append(line(x + 104, at(level), x + 116, at(level), GREEN, 2.5))
    out.append(line(x + 104, at(noise), x + 116, at(noise), GREEN, 2.5))
    out.append(text(x + 128, (at(level) + at(noise)) / 2 + 6, "22 dB to spare", 20, GREEN))
    out.append(text(110, 56, "A contact is a sum, and every term but one is yours to move",
                    24, INK, "start", "600"))
    out.append(text(110, 88, "The path is the path. That is why the answer to a marginal "
                             "link is a better antenna or a", 20, MUTED))
    out.append(text(110, 114, "narrower mode, and almost never more watts.", 20, MUTED))
    out.append(rect(110, 546, WIDE - 220, 100, SOFT, 8))
    out.append(text(134, 582, "Ten watts to a hundred is 10 dB. A dipole to a beam is much "
                              "the same, both ways.", 21, INK, "start", "600"))
    out.append(text(134, 612, "CW gets through some 10 to 15 dB below where SSB gives up, "
                              "and FT8 lower again.", 20, MUTED))
    return svg(out, 672)


# ---------------------------------------------------- figure: the schedule

def fig_study_spacing():
    """Why a question comes back when it does, which is the whole scheduler."""
    out = []
    x0, top, floor = 100, 150, 258
    nine = 232                                  # the nine-in-ten line
    stops = [("now", 0.06), ("10 min", 0.14), ("a day", 0.27),
             ("3 days", 0.45), ("10 days", 0.68), ("a month", 1.0)]
    span = WIDE - x0 - 110
    xs = [x0 + f * span for _, f in stops]
    out.append(line(x0 - 10, nine, WIDE - 110, nine, AMBER, 1.6, "7 5"))
    out.append(text(WIDE - 110, nine - 12, "nine in ten", 19, AMBER, "end"))
    # A sawtooth of forgetting: each review resets it, and the next gap is
    # longer because the memory now lasts longer.
    for n in range(len(xs) - 1):
        a, b = xs[n], xs[n + 1]
        pts = []
        for m in range(25):
            t = m / 24.0
            y = top + (nine - top) * (t ** 0.55)
            pts.append(f"{a + (b - a) * t:.1f},{y:.1f}")
        out.append(f'<polyline points="{" ".join(pts)}" fill="none" '
                   f'stroke="{GREEN}" stroke-width="2.6"/>')
        out.append(line(b, nine, b, top, GREEN, 2.6))
    for n, x in enumerate(xs):
        out.append(f'<circle cx="{x:.1f}" cy="{top}" r="6" fill="{GREEN}"/>')
        out.append(line(x, floor, x, floor + 12, RULE, 1.4))
        out.append(text(x, floor + 36, stops[n][0], 19, MUTED, "middle"))
    out.append(text(x0 - 10, 120, "how well you still know it", 20, MUTED))
    out.append(text(x0 - 10, 56, "A question comes back just before you would forget it",
                    24, INK, "start", "600"))
    out.append(text(x0 - 10, 88,
                    "Each time you get it right the gap doubles out - and the pool "
                    "quietly gets smaller.", 20, MUTED))
    out.append(brace(xs[3], xs[4], floor + 62, "the gaps grow because the memory does", MUTED))
    # And the miss, which is the part people take badly and should not.
    out.append(rect(x0 - 10, 390, WIDE - x0 - 100, 120, SOFT, 8))
    out.append(text(x0 + 20, 428, "Get one wrong", 22, RED, "start", "600"))
    out.append(text(x0 + 20, 458,
                    "It comes back in about ten minutes - and then keeps a share of the "
                    "spacing it had already", 20, MUTED))
    out.append(text(x0 + 20, 484,
                    "earned, rather than starting again from nothing. A miss is the "
                    "measurement, not a setback.", 20, MUTED))
    return svg(out, 540)


# ------------------------------------------------------- figure: a first week

def fig_study_week():
    """What the first week actually looks like, day by day."""
    out = []
    days = [
        ("Day 1", "Press Study.", "Answer thirty or forty.", "Get a lot wrong -", "everybody does."),
        ("Day 2", "Press Study again.", "It starts with what", "you are about to", "forget."),
        ("Day 3", "Same again.", "Shorter, because", "some of it has", "stuck."),
        ("Day 4", "A mock exam.", "Not to pass it -", "to find the thin", "sections."),
        ("Day 5+", "Follow the card.", "Weak spots, then", "back to the drill.", ""),
    ]
    w, gap = 190, 24
    x0 = (WIDE - (len(days) * w + (len(days) - 1) * gap)) / 2
    for n, (day, *lines_) in enumerate(days):
        x = x0 + n * (w + gap)
        out.append(rect(x, 110, w, 210, "#ffffff", 10, GREEN if n < 4 else AMBER, 2))
        out.append(rect(x, 110, w, 42, SOFT, 10))
        out.append(text(x + w / 2, 140, day, 22, INK, "middle", "600"))
        for m, s in enumerate([l for l in lines_ if l]):
            out.append(text(x + 16, 186 + m * 28, s, 18, INK if not m else MUTED))
        if n < len(days) - 1:
            out.append(text(x + w + gap / 2, 222, "→", 26, MUTED, "middle"))
    out.append(text(x0, 56, "A week of this beats the week before the exam", 24, INK,
                    "start", "600"))
    out.append(text(x0, 88, "Fifteen minutes a day. The loop does not change after this; "
                            "it just gets shorter.", 20, MUTED))
    out.append(text(x0, 374,
                    "Nothing in a mock exam is wasted - every answer in it feeds the same "
                    "schedule the drill uses.", 20, MUTED))
    return svg(out, 410)


# ---------------------------------------------------------- figure: the modes

def fig_study_modes():
    """Which of the five modes draws from which part of the pool."""
    out = []
    x0, w = 110, WIDE - 220
    parts = [("never seen", 0.32, "#ffffff"), ("due for review", 0.24, SOFT),
             ("lapsed", 0.14, "#ffffff"), ("known, resting", 0.30, SOFT)]
    x = x0
    for label, frac, fill in parts:
        out.append(rect(x, 110, w * frac, 74, fill, 6, RULE, 1.5))
        out.append(text(x + w * frac / 2, 154, label, 19, MUTED, "middle"))
        x += w * frac
    out.append(brace(x0, x0 + w, 200, "the whole question pool", MUTED))
    modes = [("Drill", 0.34 + 0.11, "due first, then new - press this"),
             ("New", 0.17, "only what you have never seen"),
             ("Weak spots", 0.41, "your lowest mastery first"),
             ("Lapses", 0.41, "what you have got wrong")]
    for n, (name, frac, why) in enumerate(modes):
        y = 268 + n * 58
        out.append(rect(x0, y - 26, 158, 40, "#ffffff", 8,
                        GREEN if not n else RULE, 2.5 if not n else 1.5))
        out.append(text(x0 + 79, y + 1, name, 21, GREEN if not n else INK, "middle",
                        "600" if not n else "400"))
        out.append(text(x0 + 180, y + 1, why, 20, MUTED))
    out.append(text(x0, 56, "Five ways in, and one of them is the answer almost always",
                    24, INK, "start", "600"))
    out.append(text(x0, 522, "Contest is the fifth: a fast random round against a clock, "
                             "for the evening you do not feel like", 20, MUTED))
    out.append(text(x0, 548, "studying. It still counts, and everything it asks still "
                             "feeds the schedule.", 20, MUTED))
    return svg(out, 580)


# ------------------------------------------------------ figure: ready to sit?

def fig_study_ready():
    """The three numbers, read together, that say whether to book the test."""
    out = []
    x0, w = 120, 620
    pass_at = 0.74
    rows = [
        ("Coverage", 0.86, "of the pool met - under about two thirds, the rest is guesswork"),
        ("Likely score", 0.81, "with its range - the low end is what matters"),
    ]
    out.append(text(x0, 56, "Three numbers, and none of them alone", 24, INK, "start", "600"))
    out.append(text(x0, 88, "Read them in this order. Any one of them on its own will "
                            "flatter you.", 20, MUTED))
    for n, (label, value, why) in enumerate(rows):
        y = 150 + n * 150
        out.append(text(x0, y + 6, label, 21, INK, "start", "600"))
        out.append(rect(x0 + 160, y - 18, w, 38, SOFT, 6))
        out.append(rect(x0 + 160, y - 18, w * value, 38, GREEN, 6))
        out.append(text(x0 + 160 + w + 18, y + 8, f"{int(value * 100)}%", 21, INK))
        out.append(text(x0 + 160, y + 80 if label == "Likely score" else y + 46,
                        why, 19, MUTED))
        if label == "Likely score":
            lo, hi = 0.70, 0.90
            bar = x0 + 160
            out.append(line(bar + w * lo, y + 40, bar + w * hi, y + 40, AMBER, 3))
            out.append(line(bar + w * lo, y + 34, bar + w * lo, y + 46, AMBER, 3))
            out.append(line(bar + w * hi, y + 34, bar + w * hi, y + 46, AMBER, 3))
            out.append(text(bar + w * hi + 16, y + 46, "the range", 19, AMBER))
            out.append(line(bar + w * pass_at, y - 28, bar + w * pass_at, y + 30,
                            RED, 2.5, "5 4"))
            out.append(text(bar + w * pass_at, y - 38, "pass mark", 19, RED, "middle"))
    y = 442
    out.append(text(x0, y + 6, "Mock exams", 21, INK, "start", "600"))
    for n, score in enumerate((0.78, 0.83, 0.80)):
        cx = x0 + 200 + n * 130
        out.append(rect(cx - 46, y - 24, 92, 50, "#ffffff", 8, GREEN, 2))
        out.append(text(cx, y + 8, f"{int(score * 100)}%", 22, GREEN, "middle", "600"))
    out.append(text(x0 + 600, y + 8, "three in a row, on different days,", 20, MUTED))
    out.append(text(x0 + 600, y + 34, "all clear of the pass mark", 20, MUTED))
    out.append(rect(x0, 516, WIDE - 240, 74, SOFT, 8))
    out.append(text(x0 + 24, 548, "That is the honest signal - and it is still your call, "
                                  "not the program's.", 21, INK, "start", "600"))
    out.append(text(x0 + 24, 576, "ELMER does not know what a bad day at the test session "
                                  "looks like.", 20, MUTED))
    return svg(out, 620)


# --------------------------------------------------------------- figure: hop

def fig_lab_hop():
    """The skip zone, which is the picture the whole tool exists to draw."""
    import math
    out = []
    ground, sky = 460, 150
    out.append(rect(90, sky - 26, WIDE - 180, 52, SOFT, 6))
    out.append(text(WIDE - 100, sky + 6, "the F layer", 20, MUTED, "end"))
    out.append(line(90, ground, WIDE - 90, ground, INK, 2.5))
    station = 170
    out.append(line(station, ground, station, ground - 54, AMBER, 5))
    out.append(text(station, ground + 30, "you", 20, AMBER, "middle", "600"))

    def ray(x_up, x_down, color=GREEN, dash=None, label=None):
        top_y = sky + 4
        mid = (x_up + x_down) / 2
        # A quadratic reaches half way to its control point, so the control
        # is solved from where the ray has to graze rather than guessed.
        ctrl = 2 * (top_y + 6) - 0.5 * ((ground - 50) + ground)
        d = (f'M {x_up:.0f},{ground - 50} Q {mid:.0f},{ctrl:.0f} '
             f'{x_down:.0f},{ground}')
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.6"{da}/>')

    # Too steep: through the layer and gone.
    out.append(f'<path d="M {station},{ground - 50} L {station + 120},{sky - 30} '
               f'L {station + 160},60" fill="none" stroke="{RED}" stroke-width="2.6"/>')
    out.append(f'<path d="M {station + 150},80 l 14,-24 l 6,16 z" fill="{RED}"/>')
    out.append(text(station + 176, 96, "too steep - it goes through and is gone", 20, RED))
    # The steepest that comes back, and a shallow one that goes a long way.
    near, far = 600, 980
    out.append(ray(station, near))
    out.append(ray(station, far))
    out.append(text(near + 12, ground - 42, "the first hop lands here", 20, GREEN))
    out.append(text(880, ground - 176, "a shallower ray, further out", 20, GREEN, "middle"))
    # The ground wave, and the hole between it and the first hop.
    out.append(f'<path d="M {station},{ground - 6} Q {station + 60},{ground - 30} '
               f'{station + 150},{ground - 4}" fill="none" stroke="{INK}" stroke-width="3"/>')
    out.append(text(station + 40, ground + 30, "ground wave", 20, INK))
    out.append(line(station + 155, ground, near, ground, RED, 5))
    out.append(brace(station + 155, near, ground + 58,
                     "the skip zone - too far for the ground wave, too near for the hop", RED))
    out.append(text(90, 48, "Why a band is open to Europe and dead to the next county",
                    24, INK, "start", "600"))
    return svg(out, 560)


# --------------------------------------------------------------- figure: SWR

def fig_lab_swr():
    """What a mismatch actually costs, which is not what most people are told."""
    out = []
    x0, w = 200, 520
    for n, (swr, back) in enumerate(((1.0, 0.0), (2.0, 0.111), (3.0, 0.25))):
        y = 130 + n * 96
        out.append(text(x0 - 22, y + 30, f"{swr:.0f}:1", 24, INK, "end", "600"))
        out.append(rect(x0, y, w, 46, GREEN, 6))
        if back:
            out.append(rect(x0 + w * (1 - back), y, w * back, 46, AMBER, 6))
        out.append(text(x0 + w + 20, y + 30,
                        "all of it forward" if not back
                        else f"{int(round(back * 100))}% turned back at the antenna",
                        20, MUTED))
    out.append(text(90, 56, "A mismatch does not throw your power away", 24, INK,
                    "start", "600"))
    out.append(text(90, 88, "What comes back is not burned; most of it is re-sent by the "
                            "transmitter and goes out anyway.", 20, MUTED))
    out.append(rect(90, 424, WIDE - 180, 116, SOFT, 8))
    out.append(text(114, 460, "The real cost is the extra trip through the feedline.",
                    21, INK, "start", "600"))
    out.append(text(114, 490, "On good coax at HF that is a fraction of a decibel and you "
                              "will never hear it. On lossy", 20, MUTED))
    out.append(text(114, 516, "cable at VHF, or at 5:1, it is worth fixing - and the tab "
                              "puts the number on it in watts.", 20, MUTED))
    return svg(out, 570)


# ------------------------------------------------------- figure: the sondes

def fig_prop_sondes():
    """Where the critical frequency over you actually comes from."""
    import math
    out = []
    cx, cy = 330, 300
    for km, r in ((1000, 70), (3000, 140), (5000, 210)):
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{RULE}" '
                   f'stroke-width="1.4" stroke-dasharray="5 5"/>')
        out.append(text(cx, cy + r + 22, f"{km:,} km", 17, MUTED, "middle"))
    out.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="{AMBER}"/>')
    out.append(text(cx, cy + 32, "you", 20, AMBER, "middle", "600"))
    sondes = [(-48, -46, "heavy vote - near, and recent", GREEN), (96, 34, "", GREEN),
              (-130, 96, "", MUTED), (116, -166, "a light one - far away", MUTED),
              (-192, -40, "", MUTED)]
    for dx, dy, label, color in sondes:
        out.append(f'<circle cx="{cx + dx}" cy="{cy + dy}" r="7" fill="{color}"/>')
        out.append(line(cx, cy, cx + dx, cy + dy, color, 1.6 if color == GREEN else 1.0,
                        None if color == GREEN else "4 4"))
        if label:
            out.append(text(cx + dx, cy + dy - 16, label, 18, color, "middle"))
    x1 = 700
    out.append(text(x1, 130, "The model says one thing.", 22, INK, "start", "600"))
    out.append(text(x1, 162, "The sondes that can see your sky", 20, MUTED))
    out.append(text(x1, 188, "say another, and they are", 20, MUTED))
    out.append(text(x1, 214, "measurements.", 20, MUTED))
    out.append(text(x1, 268, "So each one votes, weighted by", 20, MUTED))
    out.append(text(x1, 294, "how far away it is and how old", 20, MUTED))
    out.append(text(x1, 320, "its reading is, and the model's", 20, MUTED))
    out.append(text(x1, 346, "figure is corrected to meet them.", 20, MUTED))
    out.append(text(x1, 400, "With no sonde in range the page", 20, MUTED))
    out.append(text(x1, 426, "says", 20, MUTED))
    out.append(text(x1 + 46, 426, "Est.", 20, AMBER, "start", "600", MONO))
    out.append(text(x1 + 104, 426, "and means it.", 20, MUTED))
    out.append(text(90, 56, "The critical frequency over you is measured, not guessed",
                    24, INK, "start", "600"))
    return svg(out, 540)


# ---------------------------------------------------- figure: calibrate

def fig_prop_calibrate():
    """What the five minutes of Calibrate my forecast actually buys."""
    import math
    out = []
    x0, w, mid = 120, WIDE - 240, 300
    months = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    step = w / 11.0
    read, guess = [], []
    for n in range(12):
        x = x0 + n * step
        actual = mid - 70 * math.sin((n + 1.6) / 12.0 * 2 * math.pi) - 18
        model = mid - 44 * math.sin((n + 2.4) / 12.0 * 2 * math.pi) + 16
        read.append((x, actual))
        guess.append((x, model))
        out.append(text(x, 402, months[n], 19, MUTED, "middle"))
        out.append(line(x, actual, x, model, RULE, 1.4))
    out.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in read)
               + f'" fill="none" stroke="{GREEN}" stroke-width="3"/>')
    out.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in guess)
               + f'" fill="none" stroke="{AMBER}" stroke-width="3" stroke-dasharray="7 5"/>')
    # A key, rather than labels hung off the ends of the lines where the
    # page has no room for them.
    out.append(line(x0, 158, x0 + 44, 158, GREEN, 3))
    out.append(text(x0 + 56, 165, "what the sondes read", 20, GREEN))
    out.append(line(x0 + 300, 158, x0 + 344, 158, AMBER, 3, "7 5"))
    out.append(text(x0 + 356, 165, "what ELMER forecast, blind", 20, AMBER))
    out.append(text(90, 56, "Calibrate: a year of being wrong, measured", 24, INK,
                    "start", "600"))
    out.append(text(90, 88, "It runs the forecast blind across the last year of readings "
                            "near you - each hour given only what", 20, MUTED))
    out.append(text(90, 114, "it would have known at the time - and keeps the gap between "
                             "the two lines.", 20, MUTED))
    out.append(rect(90, 440, WIDE - 180, 100, SOFT, 8))
    out.append(text(114, 476, "That gap is the correction, by month and by hour.", 21, INK,
                    "start", "600"))
    out.append(text(114, 506, "Saved when the run finishes; every forecast for this place "
                              "uses it from then on.", 20, MUTED))
    return svg(out, 570)


# ------------------------------------------------- figure: turning the wire

def _plan_lobe(cx, cy, r, heading, color=GREEN):
    """A dipole's figure-of-eight, laid along `heading`, drawn as a path."""
    import math
    pts = []
    for n in range(0, 361, 3):
        off = math.radians(n - heading)
        f = abs(math.sin(off)) ** 1.1          # broadside to the wire
        rr = r * (0.06 + 0.94 * f)
        a = math.radians(n - 90)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    return f'<path d="{d}" fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-width="2.5"/>'


def fig_ant_turn():
    """The one interaction people miss: the bearing turns the whole picture."""
    import math
    out = []
    r = 140
    for n, heading in enumerate((0, 45)):
        cx = 290 + n * 520
        cy = 300
        for ring in (0.33, 0.66, 1.0):
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r * ring:.1f}" fill="none" '
                       f'stroke="{RULE}" stroke-width="1.2"/>')
        for label, ang in (("N", -90), ("E", 0), ("S", 90), ("W", 180)):
            a = math.radians(ang)
            out.append(text(cx + (r + 26) * math.cos(a), cy + (r + 26) * math.sin(a) + 7,
                            label, 20, MUTED, "middle"))
        out.append(_plan_lobe(cx, cy, r, heading))
        # The wire itself, laid along the heading it is set to.
        a = math.radians(heading - 90)
        out.append(line(cx - r * 0.86 * math.cos(a), cy - r * 0.86 * math.sin(a),
                        cx + r * 0.86 * math.cos(a), cy + r * 0.86 * math.sin(a),
                        AMBER, 5))
        out.append(text(cx, cy + r + 76, f"wire runs {heading}°", 22, AMBER,
                        "middle", "600"))
        out.append(text(cx, cy + r + 106,
                        "hears east and west" if heading == 0 else "hears northwest and southeast",
                        20, MUTED, "middle"))
    out.append(text(90, 58, "Drag the bearing; the pattern turns with it", 24, INK,
                    "start", "600"))
    out.append(text(90, 90,
                    "A wire radiates across itself and is deaf off its ends, so which way you "
                    "string it decides what you hear.", 20, MUTED))
    # The control that does it, drawn where somebody would look for it.
    out.append(text(WIDE / 2, 312, "→", 38, MUTED, "middle"))
    out.append(rect(WIDE / 2 - 180, 580, 360, 44, "#ffffff", 22, RULE, 1.8))
    out.append(line(WIDE / 2 - 160, 602, WIDE / 2 + 160, 602, RULE, 4))
    out.append(f'<circle cx="{WIDE / 2 - 60}" cy="602" r="15" fill="{AMBER}"/>')
    out.append(text(WIDE / 2, 658, "the bearing slider sits under the plot it moves - "
                                   "so does every slider in the Lab", 20, MUTED, "middle"))
    return svg(out, 690)


FIGURES = [
    {"name": "band-strip", "chapter": "bandplan", "draw": fig_band_strip,
     "why": "How to read one band's bar, hatching and all."},
    {"name": "band-classes", "chapter": "bandplan", "draw": fig_band_classes,
     "why": "What the next license is actually worth, on one band."},
    {"name": "contact-budget", "chapter": "contact", "draw": fig_contact_budget,
     "why": "That a link is a sum, and which terms a person can move."},
    {"name": "study-spacing", "chapter": "study", "draw": fig_study_spacing,
     "why": "Why a question comes back when it does, and what a miss really costs."},
    {"name": "study-week", "chapter": "study", "draw": fig_study_week,
     "why": "The first week, day by day, for somebody who wants telling."},
    {"name": "study-modes", "chapter": "study", "draw": fig_study_modes,
     "why": "Which of the five modes draws from which part of the pool."},
    {"name": "study-ready", "chapter": "study", "draw": fig_study_ready,
     "why": "The three numbers that decide whether to book the test."},
    {"name": "lab-hop", "chapter": "lab", "draw": fig_lab_hop,
     "why": "The skip zone - open to Europe, dead to the next county."},
    {"name": "lab-swr", "chapter": "lab", "draw": fig_lab_swr,
     "why": "What a mismatch costs, which is not what most people are told."},
    {"name": "prop-sondes", "chapter": "propagation", "draw": fig_prop_sondes,
     "why": "That the critical frequency over you is measured, and how."},
    {"name": "prop-calibrate", "chapter": "propagation", "draw": fig_prop_calibrate,
     "why": "What the five minutes of Calibrate my forecast buys."},
    {"name": "ant-turn", "chapter": "antennas", "draw": fig_ant_turn,
     "why": "That the plan view is a control, not a picture - and where the control is."},
    {"name": "cw-timing", "chapter": "cw", "draw": fig_cw_timing,
     "why": "What a dit and a dah are, and that the silence is counted too."},
    {"name": "cw-farnsworth", "chapter": "cw", "draw": fig_cw_farnsworth,
     "why": "The one thing Farnsworth changes, against the thing it refuses to."},
    {"name": "cw-koch", "chapter": "cw", "draw": fig_cw_koch,
     "why": "The order the forty arrive in, with the two you start on."},
    {"name": "cw-day", "chapter": "cw", "draw": fig_cw_day,
     "why": "Fifteen minutes one way and the other, with the gaps drawn."},
    {"name": "cw-set", "chapter": "cw", "draw": fig_cw_set,
     "why": "A set of passes carrying into the next morning."},
    {"name": "cw-cold", "chapter": "cw", "draw": fig_cw_cold,
     "why": "The cold rep in a sitting, and the day that follows it."},
    {"name": "cw-solid", "chapter": "cw", "draw": fig_cw_solid,
     "why": "The two roads to solid, side by side."},
    {"name": "cw-qualify-run", "chapter": "cw", "draw": fig_cw_qualify,
     "why": "Five minutes, the clean minute inside it, and where it stops."},
    {"name": "cw-ladder", "chapter": "cw", "draw": fig_cw_ladder,
     "why": "Words a minute as a scale somebody can find themselves on."},
    {"name": "cw-shapes", "chapter": "cw", "draw": fig_cw_shapes,
     "why": "The pairs that get confused, and why they do."},
]

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:#fff}}
svg{{display:block}}</style></head><body>{svg}</body></html>"""


# Where a figure can be wrong without anybody noticing.
#
# Text in SVG is placed by a coordinate and sized by whatever font the browser
# resolves. Nothing wraps, nothing reflows, and nothing complains: a label two
# words longer than the room it has simply runs off the edge of the picture, or
# straight through the label beside it. Both shipped into the guide before an
# operator spotted them on the page - a brace label near the left edge with its
# first word cut away, and two columns of prose overlapping in the middle.
#
# Guessing text widths in Python would be guessing. The browser drawing the
# figure knows exactly where every glyph landed, so it is asked: anything
# outside the frame, and any two labels sharing space. SLACK keeps a couple of
# pixels of antialiasing and the odd deliberate near-touch from crying wolf.
SLACK = 3.0
MEASURE = """(() => {
  const svg = document.querySelector('#fig');
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const slack = %f;
  const boxes = [], out = {over: [], clash: []};
  svg.querySelectorAll('text').forEach(t => {
    const b = t.getBBox(), s = (t.textContent || '').trim().slice(0, 42);
    if (!s) return;
    boxes.push({s: s, x: b.x, y: b.y, r: b.x + b.width, b: b.y + b.height});
    if (b.x < -slack || b.y < -slack || b.x + b.width > W + slack
        || b.y + b.height > H + slack) out.over.push(s);
  });
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], c = boxes[j];
      const w = Math.min(a.r, c.r) - Math.max(a.x, c.x);
      const h = Math.min(a.b, c.b) - Math.max(a.y, c.y);
      if (w > slack && h > slack) out.clash.push(a.s + '  ><  ' + c.s);
    }
  return JSON.stringify(out);
})()""" % SLACK


def take(fig, out_dir, chromium_settle=0.8):
    """Draw one figure, photograph it, and measure what was drawn.

    Returns (path, faults). A figure whose labels fall off the frame or land
    on each other is not written out: it would go straight into the book, and
    the book is the one place nobody looks again.
    """
    import _browser
    svg_markup = fig["draw"]()
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(PAGE.format(svg=svg_markup))
        page = handle.name
    target = out_dir / (fig["name"] + ".png")
    measured = None
    try:
        url = Path(page).as_uri()
        measured = _browser.evaluate(url, MEASURE, width=WIDE + 40, height=1400,
                                     settle=chromium_settle, out=str(target),
                                     clip="#fig")
    finally:
        try:
            os.unlink(page)
        except OSError:
            pass
    faults = []
    try:
        report = json.loads(measured) if isinstance(measured, str) else (measured or {})
    except ValueError:
        report = {}
    for label in report.get("over") or []:
        faults.append("off the frame: " + label)
    for pair in report.get("clash") or []:
        faults.append("overlapping: " + pair)
    if not target.is_file() or target.stat().st_size < 900:
        if target.is_file():
            target.unlink()
        return None, faults or ["nothing drawn"]
    if faults:
        target.unlink()
        return None, faults
    return target, []


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("chapter", nargs="?", help="only this chapter's figures")
    ap.add_argument("--list", action="store_true", help="what there is, and why")
    args = ap.parse_args()

    if args.list:
        for fig in FIGURES:
            print(f"{fig['name']:<18} {fig['chapter']:<8} {fig['why']}")
        return 0

    import _browser
    if not _browser.available():
        print("no chromium on this machine - these are drawn in one")
        return 1
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    wanted = [f for f in FIGURES if not args.chapter or f["chapter"] == args.chapter]
    if not wanted:
        print(f"no figures for {args.chapter!r}")
        return 1
    bad = 0
    for fig in wanted:
        got, faults = take(fig, FIGURES_DIR)
        if got:
            print(f"ok      {fig['name']:<18} {got.stat().st_size // 1024} KB")
        else:
            bad += 1
            print(f"FAILED  {fig['name']:<18} {faults[0]}")
            for line in faults[1:]:
                print(" " * 26 + line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

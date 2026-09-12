"""The antenna sheet: what to cut, how high to hang it, and what to expect.

Everything the Lab works out about an antenna lives on a screen, and the screen
is indoors. The tape measure is not. This prints the same answers on a piece of
paper somebody can take out to the garden with a pencil - the cut lengths for
the conductor they actually have, the height that job needs, what the takeoff
angle will be when they get there, and what the thing is honestly good for.

It is a build sheet and an evaluation in one, because those are the same
document read at two different moments: before, it says what to make; after, it
says what you have got. Both halves are printed either way, so the sheet still
answers the second question when it is found in a toolbox a year later.

The numbers are the program's own, recomputed here from the same modules the
page uses rather than passed in from the browser - a sheet that disagreed with
the screen would be worse than no sheet. What the caller sends is the choices:
the antenna, the band, the conductor, the height, the site.

Like `rfpdf`, this is reportlab and no browser, so it renders the same from a
phone on the LAN as from the Pi itself.
"""
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Line, Rect
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from . import antenna_advice, bandplan, bandpdf, conductors, patterns

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#555555")
RULE = colors.HexColor("#999999")
BAND = colors.HexColor("#eeeeee")
WARN = colors.HexColor("#b3261e")

C_FT = 983.571

# What the principal dimension of each antenna actually is, as a fraction of a
# wavelength, and what to call it. A dipole is cut as a half wave and hung by
# its middle, so the number somebody needs at the bench is the leg. A quarter
# wave vertical has one leg and some radials. A loop is a circumference. And
# some of these are not cut to length at all: a Yagi is a boom and a set of
# elements that no single figure describes, and a bought whip is bought.
CUTS = {
    "dipole": {"whole": 0.5, "legs": 2, "leg_name": "each leg",
               "note": "Cut both legs the same and feed the middle."},
    "invertedv": {"whole": 0.5, "legs": 2, "leg_name": "each leg",
                  "note": "Same wire as a flat dipole - the droop changes the "
                          "pattern and the feedpoint impedance, not the "
                          "length. Cut it flat, hang it, then trim."},
    "bowtie": {"whole": 0.5, "legs": 2, "leg_name": "each side",
               "note": "Each side is a pair of wires spread apart. The spread "
                       "is what buys the bandwidth; the length is still a "
                       "half wave."},
    "efhw": {"whole": 0.5, "legs": 1, "leg_name": "the wire",
             "note": "One wire, fed at the end through a transformer - the "
                     "length is a half wave even though only one end is used."},
    "quarter": {"whole": 0.25, "legs": 1, "leg_name": "the radiator",
                "note": "Plus radials, each about the same length. More "
                        "radials matter more than longer ones."},
    "groundplane": {"whole": 0.25, "legs": 1, "leg_name": "the radiator",
                    "note": "Four radials of the same length, sloped down "
                            "about 45 degrees, brings the feedpoint near 50 "
                            "ohms."},
    "fiveeighth": {"whole": 0.625, "legs": 1, "leg_name": "the radiator",
                   "note": "Needs a matching coil at the base - five eighths "
                           "is not resonant on its own."},
    "loop": {"whole": 1.0, "legs": 1, "leg_name": "the full loop",
             "note": "A full wavelength of wire round the perimeter, not "
                     "across it."},
    "jpole": {"whole": 0.75, "legs": 1, "leg_name": "overall",
              "note": "Three quarters of a wave overall: a half-wave radiator "
                      "standing on a quarter-wave matching stub."},
}

NOT_CUT = {
    "yagi": "A Yagi is a driven element, a reflector and one or more directors "
            "on a boom, and no single length describes it. The driven element "
            "is near a half wave, the reflector about 5% longer and each "
            "director about 5% shorter, but the spacings are what set the "
            "gain and the pattern - build one to a published design rather "
            "than to a rule of thumb.",
    "whip": "A mobile whip is bought, not cut. The element is stainless steel "
            "and the loading coil is what makes a short antenna resonate; "
            "tuning is done by moving the tap or the tip, following the "
            "instructions that came with it.",
    "screwdriver": "A screwdriver is bought, not cut: the motor moves the coil "
                   "and that is the tuning. What there is to build is the "
                   "mount, the bond to the vehicle and the counterpoise.",
    "whipdipole": "Two mobile whips, bought by band, on a dipole mount - about "
                  "sixteen feet tip to tip, and nothing to cut. Tune by "
                  "sliding both stingers the same amount, phone end to CW "
                  "end; fit 3/8-24 quick-disconnects and colour-code the "
                  "whips by band. Put a 1:1 current balun at the mount, "
                  "choke the coax (six turns a foot across, or four or five "
                  "Fair-Rite 2643102002 cores) and keep the top mast section "
                  "non-conductive. Virginia RACES measured a pair at 20 ft "
                  "about 10 dB below a full-size dipole on 40 m, 18 dB on "
                  "75 m and 6 dB below a G5RV on 20 m - and worked Europe "
                  "with it.",
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"],
                                fontName="Helvetica-Bold", fontSize=16,
                                spaceAfter=2, textColor=INK),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=9.5,
                              textColor=MUTED, spaceAfter=10),
        "h": ParagraphStyle("h", parent=base["Heading2"],
                            fontName="Helvetica-Bold", fontSize=11,
                            spaceBefore=12, spaceAfter=5, textColor=INK),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9,
                               leading=12.5, alignment=TA_LEFT, textColor=INK),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontSize=7.8,
                                leading=10.5, textColor=MUTED),
        "warn": ParagraphStyle("w", parent=base["Normal"], fontSize=8.6,
                               leading=11.5, textColor=WARN),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8.4,
                               leading=11),
    }


# The card's bar height rather than the chart's, because like the card's it
# appears once here instead of repeating down a page. Not enlarged: what makes
# one of these recognisable is the pattern of the segments, not their size -
# 60 m is five channels and could not be mistaken for anything at any scale -
# and that recognition comes from having seen the bar before. It needs no
# help from the layout and none from the page pointing at it.
STRIP_H = bandpdf.BAR_H


def covers_whole(span, band):
    """Whether this antenna holds under 2:1 right across the band."""
    if span.get("low") is None or span.get("high") is None:
        return False
    return span["low"] <= band["low"] and span["high"] >= band["high"]


def _band_strip(mhz, span, license_class, width):
    """The whole band this antenna is cut for, with its slice marked on it.

    Drawn by the same code as the band chart, deliberately: an operator with
    both printed should see one picture, not two dialects of it. What is added
    here is where this particular antenna sits - the span it holds under 2:1,
    outlined on the band, so the sheet answers "what else is this good for"
    without being asked.
    """
    band = bandplan.band_at(mhz)
    if not band:
        return None, None
    name = band["name"]
    drawing = bandpdf.activity_bar(name, license_class, width, height=STRIP_H)
    low, high = band["low"], band["high"]
    reach = (high - low) or 1.0

    def at(f):
        return max(0.0, min(width, (f - low) / reach * width))

    base = bandpdf.CHART_LABEL_H
    # An antenna whose 2:1 window is wider than the band has no slice to
    # outline - the outline would sit exactly on the bar's own edges and
    # vanish, while implying the opposite of what is true. That case is told
    # in words underneath instead, where it is better news anyway.
    if not covers_whole(span, band) and span.get("low") is not None:
        x0, x1 = at(span["low"]), at(span["high"])
        # Outlined twice, pale over dark, so it reads on any of the segment
        # colours underneath rather than only on the light ones.
        for colour, inset, wide in ((colors.white, 0.0, 2.4),
                                    (colors.black, 1.2, 1.0)):
            drawing.add(Rect(x0 + inset, base + inset,
                             max(1.5, x1 - x0 - 2 * inset),
                             STRIP_H - 2 * inset,
                             fillColor=None, strokeColor=colour,
                             strokeWidth=wide))
    tick = at(mhz)
    drawing.add(Line(tick, base - 2, tick, base + STRIP_H + 2,
                     strokeColor=colors.black, strokeWidth=2.0))
    drawing.add(Line(tick, base - 2, tick, base + STRIP_H + 2,
                     strokeColor=colors.white, strokeWidth=0.8))
    return drawing, band


def _band_legend(name, style):
    """What the colours in that band mean - only the ones actually in it."""
    seen = []
    for _low, _high, kind, _label in bandplan.activity_for(name):
        if kind not in seen:
            seen.append(kind)
    if not seen:
        return None
    parts = []
    for kind in seen:
        colour = bandpdf.KIND_COLOUR.get(kind, colors.grey)
        parts.append(f'<font color="#{colour.hexval()[2:]}">&#9608;</font> '
                     f'{bandpdf.KIND_LABEL.get(kind, kind)}')
    return Paragraph(" &nbsp;".join(parts), style)


def _feet_inches(feet):
    """Feet and inches, because that is what the tape measure is marked in."""
    if feet is None:
        return "—"
    whole = int(feet)
    inches = (feet - whole) * 12.0
    if round(inches, 1) >= 12.0:
        whole, inches = whole + 1, 0.0
    return f"{whole} ft {inches:.1f} in"


def _grid(rows, widths, styles, extra=None):
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.4),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.4),
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    table.setStyle(TableStyle(style + (extra or [])))
    return table


def dimensions(kind, mhz, conductor_key):
    """What to cut, for this antenna on this band out of this material.

    The velocity factor is the conductor's, not a constant: 468/f is the wire
    answer and a fatter element comes out shorter. Both are printed, because
    the difference between them is the thing worth understanding and somebody
    checking this against a book needs to see why it disagrees.
    """
    cut = CUTS.get(kind)
    if not cut:
        return None
    spec = conductors.describe(conductor_key, mhz)
    free_ft = C_FT / float(mhz)
    whole_ft = free_ft * cut["whole"] * spec["k"]
    wire_ft = free_ft * cut["whole"] * conductors.REFERENCE_K
    leg_ft = whole_ft / cut["legs"] if cut["legs"] > 1 else whole_ft
    return {
        "conductor": spec,
        "free_space_ft": free_ft,
        "overall_ft": whole_ft,
        "leg_ft": leg_ft,
        "leg_name": cut["leg_name"],
        "legs": cut["legs"],
        "wire_reference_ft": wire_ft,
        "shorter_by_in": (wire_ft - whole_ft) * 12.0,
        "note": cut["note"],
    }


def build(kind, mhz, height_ft, conductor_key="wire14", site="house",
          use=None, callsign="", nvis=False, license_class="Extra"):
    """The sheet, as PDF bytes."""
    st = _styles()
    advice = antenna_advice.for_type(mhz, kind, use=use, site=site)
    title = advice.get("title") or kind
    dims = dimensions(kind, mhz, conductor_key)
    spec = conductors.describe(conductor_key, mhz)

    height_ft = float(height_ft)
    lam_ft = C_FT / float(mhz)
    takeoff = antenna_advice.takeoff_deg(height_ft, mhz)
    # What the job wants is the antenna's own ideal, asked for without a site
    # so nothing has capped it yet; `reality` is then what the site does to
    # that. Passing the planned height in as the wanted one - which the first
    # draft did - made every row of the table echo the same figure back.
    wanted_ft = antenna_advice.for_type(mhz, kind, use=use).get("height_ft")
    reality = antenna_advice.reality(kind, mhz, wanted_ft or height_ft, site)
    nvis_ft = antenna_advice.nvis_height_ft(mhz, kind)

    # base_q rather than the table, because an antenna that covers a decade
    # does not have one Q - see patterns.Q_SCALES_WITH_BAND.
    q = spec["q_scale"] * patterns.base_q(kind, mhz)
    z = patterns.feedpoint_z(kind, mhz, mhz, q=q)
    span = patterns.usable_bandwidth(kind, mhz, q=q)

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=LETTER,
                            leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            title=f"{title} for {mhz:.3f} MHz",
                            author="ELMER")
    flow = [Paragraph(f"{title} &mdash; {mhz:.3f} MHz", st["title"])]
    made = date.today().isoformat()
    who = f"{callsign} &middot; " if callsign else ""
    flow.append(Paragraph(
        f"{who}Build sheet and evaluation &middot; {made} &middot; "
        f"wavelength {lam_ft:.1f} ft &middot; {advice.get('use_label', '')}",
        st["sub"]))

    # --- the band it lives on -----------------------------------------------
    # Once per sheet and near the top. An antenna cut for one frequency covers
    # a slice of a band, and the rest of that band is full of things the same
    # wire will do - a mode nobody thought of is usually only out of mind
    # because it was out of sight, which is the reason the sheet says so.
    #
    # It is also what tells one sheet from another in a pile, since no two
    # bands share a pattern of segments. That half is for whoever maintains
    # this and not for the operator: it works by having been seen before, so
    # it wants no tailoring and no explaining on the page.
    strip, band = _band_strip(mhz, span, license_class, 7.1 * inch)
    if strip is not None:
        flow.append(Spacer(1, 2))
        flow.append(strip)
        legend = _band_legend(band["name"], st["sub"])
        if legend is not None:
            flow.append(legend)
        if covers_whole(span, band):
            where = (f"<b>{band['name']}</b> &mdash; this antenna holds under "
                     f"2:1 across the whole band, so everything on the bar is "
                     f"within reach of it without retuning anything. Most of "
                     f"what is up there is a mode rather than a frequency.")
        elif span.get("low") is not None:
            # Quoted inside the band, because a window that runs off the end
            # of it is not usable width - it is width spent somewhere the
            # licence does not go.
            low = max(span["low"], band["low"])
            high = min(span["high"], band["high"])
            khz = round((high - low) * 1000)
            where = (f"<b>{band['name']}</b> &mdash; the outlined slice is "
                     f"where this antenna holds under 2:1: {low:.3f} to "
                     f"{high:.3f} MHz, {khz} kHz of the {band['name']} band. "
                     f"The rest of the bar is still there, and most of what is "
                     f"in it is a mode rather than a frequency.")
        else:
            where = (f"<b>{band['name']}</b> &mdash; nothing here holds under "
                     f"2:1 with this antenna as described. The marked line is "
                     f"what it is cut for, and the bar is the band it is "
                     f"sitting in.")
        flow.append(Paragraph(where, st["sub"]))

    # --- what to cut --------------------------------------------------------
    flow.append(Paragraph("What to cut", st["h"]))
    if dims:
        rows = [["", "Length", "In metres"]]
        if dims["legs"] > 1:
            rows.append([dims["leg_name"].capitalize(),
                         _feet_inches(dims["leg_ft"]),
                         f"{dims['leg_ft'] * 0.3048:.3f} m"])
        rows.append(["Overall", _feet_inches(dims["overall_ft"]),
                     f"{dims['overall_ft'] * 0.3048:.3f} m"])
        if not dims["conductor"].get("reference"):
            rows.append([Paragraph("If it were #14 wire", st["cell"]),
                         _feet_inches(dims["wire_reference_ft"]),
                         f"{dims['wire_reference_ft'] * 0.3048:.3f} m"])
        flow.append(_grid(rows, [2.2 * inch, 1.7 * inch, 1.5 * inch], st))
        flow.append(Spacer(1, 5))
        flow.append(Paragraph(dims["note"], st["body"]))
        flow.append(Paragraph(
            "Cut it long and trim. Every published length is a starting point: "
            "the ground under it, the trees beside it and the feedline all "
            "move resonance, and taking wire off is easy where putting it back "
            "is not. Trim both legs equally, an inch at a time, and check "
            "after each cut.", st["body"]))
        if abs(dims["shorter_by_in"]) >= 0.5:
            flow.append(Paragraph(
                f"This comes out {abs(dims['shorter_by_in']):.1f} in "
                f"{'shorter' if dims['shorter_by_in'] > 0 else 'longer'} than "
                f"the 468/f a book would give you, because that rule assumes "
                f"thin wire and this is {spec['label']}. A fatter conductor is "
                f"electrically a little shorter and covers "
                f"{spec['band_scale']:.2f}&times; the bandwidth.", st["body"]))
    else:
        flow.append(Paragraph(NOT_CUT.get(kind, "This antenna is not cut to a "
                                                "single length."), st["body"]))

    # --- the material -------------------------------------------------------
    flow.append(Paragraph("What it is made of", st["h"]))
    mat = [["Conductor", "Diameter", "Velocity factor", "Bandwidth vs wire"],
           [Paragraph(spec["label"], st["cell"]), f"{spec['od_mm']} mm",
            f"{spec['k']:.4f}", f"{spec['band_scale']:.2f}×"]]
    flow.append(_grid(mat, [2.4 * inch, 1.1 * inch, 1.3 * inch, 1.4 * inch],
                      st))
    flow.append(Spacer(1, 5))
    flow.append(Paragraph(spec["note"], st["body"]))
    if spec.get("caution"):
        flow.append(Paragraph("Watch: " + spec["caution"], st["warn"]))

    # --- how high -----------------------------------------------------------
    flow.append(Paragraph("How high, and what that buys", st["h"]))
    hrows = [["", "Height", "As wavelengths", "Takeoff angle"],
             ["Planned", _feet_inches(height_ft),
              f"{height_ft / lam_ft:.2f} λ", f"{round(takeoff)}°"]]
    if wanted_ft and abs(float(wanted_ft) - height_ft) >= 1.0:
        want = float(wanted_ft)
        hrows.append([Paragraph("What the job wants", st["cell"]),
                      _feet_inches(want), f"{want / lam_ft:.2f} λ",
                      f"{round(antenna_advice.takeoff_deg(want, mhz))}°"])
    if abs(float(nvis_ft) - height_ft) >= 1.0:
        hrows.append([Paragraph("For NVIS, deliberately low", st["cell"]),
                      _feet_inches(nvis_ft), f"{nvis_ft / lam_ft:.2f} λ",
                      f"{round(antenna_advice.takeoff_deg(nvis_ft, mhz))}°"])
    flow.append(_grid(hrows, [2.0 * inch, 1.3 * inch, 1.3 * inch, 1.5 * inch],
                      st))
    flow.append(Spacer(1, 5))
    if reality.get("means"):
        flow.append(Paragraph(reality["means"], st["body"]))
    if reality.get("capped"):
        flow.append(Paragraph(
            f"Capped at {reality['max_ft']} ft by the site, not by the "
            f"arithmetic. A low antenna is not a broken one - it is a "
            f"different one, and the takeoff angle above says which.",
            st["body"]))

    # --- electrically -------------------------------------------------------
    flow.append(Paragraph("What the instrument should see", st["h"]))
    erows = [["At resonance", "Feedpoint", "Under 2:1 SWR", "Feedline"],
             [f"{mhz:.3f} MHz",
              f"{z.real:.0f} + j{z.imag:.0f} Ω" if z.imag >= 0
              else f"{z.real:.0f} − j{abs(z.imag):.0f} Ω",
              f"{span['khz']:.0f} kHz" if span else "—",
              Paragraph(str(advice.get("feedline", "")), st["cell"])]]
    flow.append(_grid(erows, [1.3 * inch, 1.5 * inch, 1.2 * inch, 2.1 * inch],
                      st))
    flow.append(Spacer(1, 5))
    if span:
        flow.append(Paragraph(
            f"That is {span['low']:.3f} to {span['high']:.3f} MHz "
            f"({span['percent']:.1f}% of centre) — which is what says whether "
            f"one antenna covers the whole band or only the end of it you cut "
            f"it for.", st["body"]))
    flow.append(Paragraph(
        "Those are modelled, not measured, and they assume the antenna is "
        "clear of everything. A real one over real ground reads differently, "
        "and the sign of the reactance is the useful part: inductive (+j) "
        "means it is long, capacitive (−j) means it is short.", st["body"]))

    # --- what it is for -----------------------------------------------------
    flow.append(Paragraph("What it is for", st["h"]))
    for line in advice.get("why") or []:
        flow.append(Paragraph(str(line), st["body"]))
    for line in advice.get("watch") or []:
        flow.append(Paragraph("Watch: " + str(line), st["warn"]))
    for line in advice.get("better") or []:
        flow.append(Paragraph("Better: " + str(line), st["body"]))

    # --- the site -----------------------------------------------------------
    flow.append(KeepTogether([
        Paragraph(f"Where you are putting it &mdash; {reality.get('label', '')}",
                  st["h"])]))
    for line in reality.get("works", []):
        flow.append(Paragraph("• " + str(line), st["body"]))
    for line in reality.get("costs", []):
        flow.append(Paragraph("– " + str(line), st["warn"]))
    if reality.get("good_at"):
        flow.append(Paragraph("Good at: " + str(reality["good_at"]), st["body"]))

    flow.append(Spacer(1, 12))
    flow.append(Paragraph(
        "Every figure here is a model, and a model is a baseline honest enough "
        "to depart from. It knows the frequency, the height, the material and "
        "the ground it was told about; it does not know your trees, your soil "
        "or the shed roof. Build it, measure it, and trust the instrument over "
        "this sheet where they disagree — then you will know something "
        "the arithmetic could not tell you. Made by ELMER.", st["small"]))

    doc.build(flow)
    return out.getvalue()

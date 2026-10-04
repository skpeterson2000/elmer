"""One band, in one place: the sheet for the glovebox.

The full chart answers "what is where on every band". Somebody heading out
with a handheld has a narrower question - what is on 2 m *there* - and on
VHF and UHF the answer is mostly local: the coordinator's plan for that
state, and the repeaters within driving distance. So this sheet takes one
band and one place, which is the QTH in use when it is printed, or wherever
the operator typed for a trip, and puts on one sheet:

* the band as the full chart prints it (bandpdf.band_block), so the two
  never disagree about a band;
* the band drawn once more with the repeaters near the place ticked on it,
  outputs above the line and inputs below, over the coordinator's segments -
  where the pairs crowd and where simplex is clear, which no table shows;
* the simplex and calling frequencies, national and coordinated;
* the repeaters, nearest first, with how far and which way;
* where every one of those came from, and how old it is.

On HF most of that is absent - coordinators plan VHF and up, and FM
repeaters start at 10 m - and the sheet is the band's own block and its
sources. Nothing is padded to look fuller.
"""
import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import units
from .bandplan import BAND_INDEX, CLASSES, activity_for
from .bandpdf import (CHART_WIDTH, KIND_COLOR, KIND_LABEL, NOT_HELD, _styles,
                      _table, band_block)

# Repeaters start here: an FM repeater below 10 m is not a thing the lists hold.
REPEATERS_FROM_MHZ = 28.0
# A city's 2 m list within fifty miles can run past sixty machines. The sheet
# stops at a number that keeps it to a sheet, and says how many it left off.
MAX_REPEATERS = 60
DEFAULT_RADIUS_KM = 80.47          # fifty miles
MAX_RADIUS_KM = 400.0

STRIP_H = 46
TICK_OUT = colors.HexColor("#1d1d1d")
TICK_IN = colors.HexColor("#8f8f8f")
GROUND = colors.HexColor("#f1f1f1")

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(bearing):
    """A bearing in degrees as the point of the compass it is nearest."""
    return COMPASS[int((float(bearing) % 360) / 22.5 + 0.5) % 16]


def has_repeaters(name):
    band = BAND_INDEX.get(name)
    return bool(band) and band["high"] >= REPEATERS_FROM_MHZ


def _mhz(value):
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def _segments(name, regional):
    """The coordinator's segments for the band where there is a plan,
    the national convention where there is not, and which it was."""
    if regional and (regional.get("bands") or {}).get(name):
        return [(s["low"], s["high"], s["kind"]) for s in regional["bands"][name]], regional["short"]
    return [(low, high, kind) for low, high, kind, _ in activity_for(name)], "national"


def occupancy(name, rows, regional, width=CHART_WIDTH):
    """The band, with every repeater near the place ticked on it.

    Outputs above the line in ink, inputs below it in gray, over the
    segments faintly colored as the legend colors them. A tick outside the
    band - a cross-band input - is left off rather than drawn at the edge,
    where it would claim a frequency it is not on.
    """
    band = BAND_INDEX[name]
    low, high = band["low"], band["high"]
    span = (high - low) or 1.0
    drawing = Drawing(width, STRIP_H)
    mid = STRIP_H / 2 + 4
    half = 13

    def x(mhz):
        return (float(mhz) - low) / span * width

    drawing.add(Rect(0, mid - half, width, 2 * half, fillColor=GROUND, strokeColor=None))
    segments, _ = _segments(name, regional)
    for a, b, kind in segments:
        if b <= a:
            continue
        ink = KIND_COLOR.get(kind, colors.gray)
        tint = colors.Color(ink.red, ink.green, ink.blue, alpha=0.22)
        drawing.add(Rect(x(max(a, low)), mid - half, max(0.6, x(min(b, high)) - x(max(a, low))),
                         2 * half, fillColor=tint, strokeColor=None))
    drawing.add(Line(0, mid, width, mid, strokeColor=colors.HexColor("#777777"), strokeWidth=0.4))
    for row in rows:
        out = row.get("output")
        if out is not None and low <= out <= high:
            drawing.add(Line(x(out), mid, x(out), mid + half - 1, strokeColor=TICK_OUT, strokeWidth=0.7))
        inp = row.get("input")
        if inp is not None and low <= inp <= high:
            drawing.add(Line(x(inp), mid, x(inp), mid - half + 1, strokeColor=TICK_IN, strokeWidth=0.7))
    drawing.add(String(0, 0, f"{low:g}", fontSize=6.5, fontName="Helvetica"))
    drawing.add(String(width, 0, f"{high:g} MHz", fontSize=6.5, fontName="Helvetica",
                       textAnchor="end"))
    drawing.add(String(width / 2, 0, "outputs above the line, inputs below",
                       fontSize=6.5, fontName="Helvetica", textAnchor="middle",
                       fillColor=colors.HexColor("#555555")))
    return drawing


def simplex(name, regional):
    """The simplex and calling frequencies: the national convention's, and
    the coordinator's where their plan names them. Each says whose it is."""
    out = [(low, high, kind, label, "national")
           for low, high, kind, label in activity_for(name) if kind in ("simplex", "calling")]
    if regional:
        out += [(s["low"], s["high"], s["kind"], s["label"], regional["short"])
                for s in (regional.get("bands") or {}).get(name) or []
                if s["kind"] in ("simplex", "calling")]
    return sorted(out, key=lambda r: (r[0], r[4] != "national"))


def _repeater_table(rows, system, s):
    head = ["Call", "Output", "Input", "Tone", "Modes", "Where",
            "Distance", "Bearing"]
    body = [head]
    for r in rows:
        # The input where the list has it, the offset where that is all it has.
        inp = r.get("input")
        inp_text = (_mhz(inp) if inp is not None
                    else str(r["offset"]) if r.get("offset") not in (None, "") else "")
        where = escape(r.get("where") or "")
        if r.get("approx"):
            where += " <font color='#8a6d1f'>(county)</font>"
        body.append([r["call"], _mhz(r["output"]), inp_text, str(r.get("tone") or ""),
                     Paragraph(escape(str(r.get("modes") or "")), s["cell"]),
                     Paragraph(where, s["cell"]),
                     units.say(r["km"], system, 1 if r["km"] < 16 else 0),
                     f"{int(r['bearing'])}° {compass(r['bearing'])}"])
    widths = [0.85, 0.75, 0.75, 0.6, 1.5, 3.55, 0.85, 0.85]
    t = Table(body, colWidths=[w * inch for w in widths], hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 7.4),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.4),
        ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 7.4),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aaaaaa")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return t


def covers(regional, name):
    """Whether the coordinator's plan says anything about this band. The MRC's
    says nothing about 20 m, and a 20 m sheet that credited it would be
    claiming it did."""
    return bool(regional) and bool((regional.get("bands") or {}).get(name))


def header_note(name, place, regional=None, coordinators=()):
    """The line under the title: where the sheet is for, and whose plan is on
    it - or who coordinates there when ELMER cannot read their plan."""
    band = BAND_INDEX[name]
    where = place.get("label") or place.get("grid") or "here"
    said = (f"For {escape(where)}"
            + (f" ({escape(place['grid'])})" if place.get("grid") else "")
            + (", which is not this station's QTH" if place.get("away") else ", this station's QTH")
            + f", printed {date.today().isoformat()}. Privileges per 47 CFR 97.301 and 97.305; "
              "activity segments are convention, not law.")
    covered = covers(regional, name)
    if regional and not covered:
        said += (f" The {escape(regional['name'])}'s plan does not cover {name}, so only the "
                 "national convention is here.")
    elif covered:
        said += (f" Coordinated segments from the {escape(regional['name'])} "
                 f"({escape(regional['short'])}), fetched {escape(regional.get('fetched') or '')}"
                 + (" - an old copy, as a fresh one could not be had" if regional.get("stale") else "")
                 + ".")
    elif coordinators and has_repeaters(name):
        c = coordinators[0]
        said += (f" {escape(place.get('state') or 'This state')} is coordinated by the "
                 f"{escape(c['name'])} ({escape(c.get('url') or '')}); ELMER cannot read their plan, "
                 "so their segments are not on this sheet. Check it before you key up.")
    elif band["low"] >= 50:
        said += " ELMER knows of no coordinator for this place, so only the national convention is here."
    return said


def build(name, license_class, place, regional=None, coordinators=(),
          repeaters=None, repeater_note="", repeater_source=None,
          radius_km=DEFAULT_RADIUS_KM, system=units.DEFAULT, station=None,
          own=True, spare=None, class_label=None):
    """The sheet, as PDF bytes.

    `place` is {"label", "grid", "state", "away"}: where the sheet is for,
    and whether that is somewhere other than the QTH. `regional` is the
    coordinator's plan for that place's state, or None; `coordinators` names
    who coordinates there, so a plan ELMER cannot read is still a name and
    an address on the sheet. `repeaters` are rows from repeaters.nearby, or
    None on a band below the repeaters; `repeater_note` says why the list is
    empty when it is, which matters more than the list being empty.
    """
    station = station or {}
    s = _styles()
    # The class as the page names it - "No license", "Visiting under
    # reciprocity" - for the reader; the key itself goes to the privileges.
    label = class_label or license_class
    where = place.get("label") or place.get("grid") or "here"
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(LETTER),
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.45 * inch, bottomMargin=0.45 * inch,
                            title=f"{name} near {where}",
                            author=station.get("callsign") or "ELMER")
    who = f" &mdash; {escape(station['callsign'])}" if station.get("callsign") else ""
    flow = [Paragraph(f"{name} near {escape(where)} &mdash; {escape(label)}{who}", s["title"])]
    if not own and license_class in CLASSES:
        flow.append(Paragraph(NOT_HELD % license_class.upper(), s["sub"]))
    covered = covers(regional, name)
    flow.append(Paragraph(header_note(name, place, regional, coordinators), s["sub"]))

    legend = [[Paragraph(f'<font color="{KIND_COLOR[k].hexval()}">&#9632;</font> {label}',
                         s["cell"]) for k, label in KIND_LABEL.items()]]
    lt = Table(legend, colWidths=[0.95 * inch] * len(legend[0]), hAlign="LEFT")
    lt.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    flow.append(lt)

    block = band_block(name, license_class, regional, s)
    flow.append(KeepTogether(block[:2]))
    flow.extend(block[2:])

    freqs = simplex(name, regional)
    if freqs:
        rows = [["Frequency", "What", "Whose"]]
        style = []
        for n, (low, high, kind, label, whose) in enumerate(freqs, start=1):
            rows.append([_mhz(low) if high == low else f"{_mhz(low)}–{_mhz(high)}",
                         Paragraph(escape(label), s["cell"]),
                         "national convention" if whose == "national" else whose])
            style.append(("TEXTCOLOR", (0, n), (0, n), KIND_COLOR.get(kind, colors.black)))
        flow.append(KeepTogether([Paragraph("Simplex and calling", s["band"]),
                                  _table(rows, style, widths=(1.3, 6.0, 1.3))]))

    if repeaters is not None:
        shown = repeaters[:MAX_REPEATERS]
        head = (f"Repeaters within {units.say(radius_km, system)} of {escape(where)}"
                + (f" &mdash; {len(repeaters)}" if repeaters else ""))
        part = [Paragraph(head, s["band"])]
        if repeaters:
            part += [occupancy(name, shown, regional), Spacer(1, 4)]
        flow.append(KeepTogether(part))
        if shown:
            flow.append(_repeater_table(shown, system, s))
            if len(repeaters) > len(shown):
                flow.append(Paragraph(
                    f"The nearest {len(shown)} of {len(repeaters)}; the rest are further out. "
                    "A smaller radius gives a shorter list.", s["small"]))
        if repeater_note:
            flow.append(Paragraph(escape(repeater_note), s["small"]))

    sources = ["Distances and bearings are straight lines from " + escape(where)
               + "; terrain decides what is actually reachable."]
    if repeaters is not None:
        sources.append("Nothing here says a repeater is on the air today: it says where the list "
                       "puts it. A machine placed only to its county is marked so, and its bearing "
                       "is to the county.")
        if repeater_source:
            sources.append("Repeaters from " + escape(repeater_source) + ".")
    if covered:
        sources.append("Coordinated segments are reproduced from the coordinator's published "
                       "plan; check with them before relying on it.")
    sources.append("Produced by ELMER.")
    flow += [Spacer(1, 8), Paragraph(" ".join(sources), s["small"])]
    if spare is not None:
        flow.append(spare)
    doc.build(flow)
    return buf.getvalue()

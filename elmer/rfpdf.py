"""Render an RF exposure evaluation as a station record you can post.

A compliance record has to survive being read by someone other than its author,
so this prints the inputs, the equation, the intermediate values and the
conclusion - not just a verdict. Generated with reportlab, which needs no
browser and so works the same from a phone on the LAN as it does on the Pi.
"""
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#555555")
RULE = colors.HexColor("#999999")
BAND = colors.HexColor("#eeeeee")
PASS = colors.HexColor("#1a7f37")
FAIL = colors.HexColor("#b3261e")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=16, spaceAfter=2, textColor=INK),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=9.5,
                              textColor=MUTED, spaceAfter=10),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontName="Helvetica-Bold",
                            fontSize=11, spaceBefore=12, spaceAfter=5, textColor=INK),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9,
                               leading=12.5, alignment=TA_LEFT, textColor=INK),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontSize=7.8,
                                leading=10.5, textColor=MUTED),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8.4, leading=11),
    }


def _fmt(value, digits=3, dash="—"):
    """Format a number to fit its column.

    Very large and very small values go to scientific notation: a wildly
    non-compliant station can produce six-figure power densities, and a number
    that overflows its cell and collides with the next one is worse than no
    number at all in a document meant to be read by someone else.
    """
    if value is None:
        return dash
    if isinstance(value, float):
        if value != 0 and abs(value) < 10 ** -digits:
            return f"{value:.2e}"
        if abs(value) >= 100000:
            return f"{value:.2e}"
        return f"{value:,.{digits}f}"
    return str(value)


def _grid(rows, widths, style_extra=None, styles=None):
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.4),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.4),
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if style_extra:
        style.extend(style_extra)
    table.setStyle(TableStyle(style))
    return table


def _mhz(value):
    """A frequency written the way an operator writes one.

    Three decimals is how band edges are said aloud, so 1.800 rather than 1.8;
    the 60 m channels genuinely need a fourth; and 1240 MHz does not want four
    zeroes after it.
    """
    if value >= 1000 and abs(value - round(value)) < 1e-9:
        return f"{value:.0f}"
    text = f"{value:.4f}".rstrip("0")
    whole, _, frac = text.partition(".")
    return f"{whole}.{(frac + '000')[:max(3, len(frac))]}"


def _privileges_page(evaluation, s):
    """A reference table of what this operator may actually transmit on.

    Only their own class, and only the bands they hold something on: a sheet
    that lists everybody's privileges is a wall chart, while this one answers
    "what may I do?" for the person whose callsign is at the top of it. It sits
    behind the evaluation and is clearly not part of it - nothing here has been
    checked against the station, it is the rules as they stand.
    """
    from . import bandplan

    licence_class = (evaluation.get("licence_class")
                     or (evaluation.get("station") or {}).get("licence_class") or "")
    table = bandplan.privilege_table(licence_class)
    if not table["bands"]:
        return []

    rows = [["Band", "Segment (MHz)", "What this licence may send there"]]
    spans, n = [], 1
    for band in table["bands"]:
        first = n
        for segment in band["segments"]:
            rows.append([band["name"] if n == first else "",
                         f"{_mhz(segment['low'])} \u2013 {_mhz(segment['high'])}",
                         segment["terms"]])
            n += 1
        if n - first > 1:                       # merge the repeated band name
            spans.append(("SPAN", (0, first), (0, n - 1)))
            spans.append(("VALIGN", (0, first), (0, n - 1), "TOP"))

    flow = [
        PageBreak(),
        Paragraph(f"Operating privileges &#8212; {licence_class}", s["h"]),
        Paragraph(
            "A reference for the operator named above, and for that class only. "
            "These are privileges, which are law: 47 CFR 97.301 and 97.305. "
            "They are <b>not part of the exposure evaluation</b> overleaf and "
            "nothing here has been checked against this station. Power is "
            "1500 W PEP maximum except where a segment says otherwise "
            "(47 CFR 97.313), and you must always use the minimum power needed.",
            s["small"]),
        Spacer(1, 6),
        _grid(rows, [0.8 * inch, 1.5 * inch, 4.2 * inch], spans),
    ]

    if table["none_on"]:
        flow += [Spacer(1, 6), Paragraph(
            "<b>No privileges at all on:</b> " + ", ".join(table["none_on"]) +
            ". Transmitting there is a violation whatever the exposure figures say.",
            s["small"])]

    if any(b["channelised"] for b in table["bands"]):
        channels = ", ".join(_mhz(c["mhz"]) for c in table["channels_60m"])
        flow += [Spacer(1, 4), Paragraph(
            "<b>60 m is five fixed channels</b>, not a band: " + channels +
            " MHz (centre frequencies, USB). No other frequency in that range "
            "may be used.", s["small"])]

    flow += [Spacer(1, 8), Paragraph(
        "Segment edges are the edges of the privilege, not of your signal: your "
        "whole emission has to fall inside them, so a sideband's width counts "
        "against the edge you are near.", s["small"])]
    return flow


def build(evaluation, station=None):
    """Return the PDF bytes for one evaluation."""
    station = station or evaluation.get("station") or {}
    s = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        leftMargin=0.72 * inch, rightMargin=0.72 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title="RF Exposure Evaluation",
        author=station.get("callsign") or "Amateur station")

    flow = [
        Paragraph("RF Exposure Evaluation", s["title"]),
        Paragraph("Station evaluation required by 47 CFR 97.13(c), against the "
                  "limits of 47 CFR 1.1310, using the methods of FCC OET "
                  "Bulletin 65 Supplement B.", s["sub"]),
    ]

    when = station.get("date") or date.today().isoformat()
    header = [["Station", station.get("callsign") or "—",
               "Evaluated", when],
              ["Location", station.get("location") or "—",
               "Grid square", station.get("grid") or "—"]]
    flow.append(_grid(header, [0.85 * inch, 2.7 * inch, 0.95 * inch, 2.5 * inch],
                      [("BACKGROUND", (0, 0), (0, -1), BAND),
                       ("BACKGROUND", (2, 0), (2, -1), BAND),
                       ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8.4),
                       ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 8.4),
                       ("FONT", (1, 0), (1, -1), "Helvetica", 8.4)]))

    overall = evaluation.get("compliant")
    verdict = ("This station is compliant at the distances evaluated."
               if overall else
               "One or more evaluated positions EXCEED the applicable limit. "
               "Action is required to prevent exposure above the limit.")
    flow += [Spacer(1, 9),
             Paragraph(f'<font color="{(PASS if overall else FAIL).hexval()}">'
                       f'<b>{verdict}</b></font>', s["body"])]

    # Exposure compliance is not permission to operate, and a green line above
    # a description of an operation the licence does not allow would read as
    # though it were. Said immediately, next to the verdict it qualifies.
    if evaluation.get("privilege_warnings"):
        flow += [Paragraph(
            f'<font color="{FAIL.hexval()}"><b>This is an exposure evaluation '
            f'only. The operation described below is not one this licence '
            f'permits &#8212; see the notes.</b></font>', s["body"])]

    warnings = evaluation.get("warnings") or []
    if warnings:
        flow += [Spacer(1, 5), Paragraph("<b>Check these before relying on it</b>",
                                         s["body"])]
        flow += [Paragraph(f'<font color="{FAIL.hexval()}">&#8226;</font> {w}',
                           s["small"]) for w in dict.fromkeys(warnings)]

    for case in evaluation["cases"]:
        block = [Paragraph(
            f"{case['band']} &mdash; {_fmt(case['frequency_mhz'], 3)} MHz, "
            f"{case.get('antenna') or 'antenna'}", s["h"])]

        inputs = [["Transmitter PEP", f"{_fmt(case['pep_watts'], 0)} W",
                   "Mode", case["mode_label"]],
                  ["Mode duty factor", f"{case['mode_duty'] * 100:.0f}%",
                   "Transmitting fraction", f"{case['transmit_fraction'] * 100:.0f}%"],
                  ["Combined duty cycle", f"{case['duty_cycle'] * 100:.1f}%",
                   "Average power", f"{_fmt(case['average_watts'], 2)} W"],
                  ["Antenna gain", f"{_fmt(case['gain_dbd'], 2)} dBd "
                                   f"({_fmt(case['gain_dbi'], 2)} dBi)",
                   "Gain figure",
                   "modelled from the antenna"
                   if case.get("gain_source") == "modelled"
                   else "entered by the operator"]]
        block.append(_grid(inputs, [1.35 * inch, 1.75 * inch, 1.5 * inch, 2.4 * inch],
                           [("BACKGROUND", (0, 0), (0, -1), BAND),
                            ("BACKGROUND", (2, 0), (2, -1), BAND),
                            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8.4),
                            ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 8.4),
                            ]))

        rows = [["Environment", "Averaging", "MPE limit\n(mW/cm²)",
                 "Distance\n(ft)", "Estimated\n(mW/cm²)", "% of\nlimit",
                 "Compliant\nbeyond (ft)", "Result"]]
        styling = []
        for n, r in enumerate(case["results"], start=1):
            rows.append([
                Paragraph(r["environment"], s["cell"]),
                f"{r['averaging_minutes']} min",
                _fmt(r["limit"], 3),
                _fmt(r["distance_ft"], 1) + ("\u2020" if r["near_field"] else ""),
                _fmt(r["density"], 4),
                _fmt(r["margin_ratio"] * 100, 1) if r["margin_ratio"] else "—",
                _fmt(r["compliance_distance_ft"], 1),
                "PASS" if r["compliant"] else "EXCEEDS",
            ])
            styling.append(("TEXTCOLOR", (7, n), (7, n), PASS if r["compliant"] else FAIL))
            styling.append(("FONT", (7, n), (7, n), "Helvetica-Bold", 8.4))
        block.append(_grid(
            rows, [1.5 * inch, 0.6 * inch, 0.75 * inch, 0.62 * inch, 0.78 * inch,
                   0.52 * inch, 0.85 * inch, 0.68 * inch],
            styling + [("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                       ("ALIGN", (7, 1), (7, -1), "CENTER")]))

        flagged = [r for r in case["results"] if r["near_field"]]
        if flagged:
            block.append(Paragraph(
                "\u2020 Distances marked with a dagger fall within roughly "
                f"{_fmt(flagged[0]['near_field_boundary_ft'], 1)} ft of the antenna, "
                "which is inside the near field at this frequency. The far-field "
                "equation is used anyway; treat those figures as indicative and "
                "keep people further away where practical.", s["small"]))
        flow.append(KeepTogether(block))

    method = evaluation["method"]
    flow += [
        Paragraph("Method and assumptions", s["h"]),
        Paragraph(
            f"Power density estimated as <b>{method['equation']}</b>, where "
            f"P<sub>avg</sub> is average power in watts, G is numeric antenna gain "
            f"referenced to isotropic, and R is distance in metres. A ground "
            f"reflection factor of {method['reflection_field']} on field strength "
            f"({method['reflection_power']:.2f} on power density) is applied "
            f"throughout, as recommended for a conservative amateur estimate. "
            f"Average power is transmitter PEP reduced by the mode duty factor and "
            f"by the fraction of the averaging period spent transmitting.", s["body"]),
        Paragraph(
            "Limits are those of 47 CFR 1.1310: controlled/occupational exposure "
            "averaged over 6 minutes, general population/uncontrolled exposure "
            "averaged over 30 minutes. Reference: " + method["reference"] + ". "
            "Requirement: " + method["requirement"] + ".", s["body"]),
        Paragraph(method["note"], s["small"]),
        Paragraph(
            "Antenna gain is the largest single lever on every figure above, and "
            "this evaluation takes it as given. Where the table says a gain was "
            "entered by the operator, nothing here has checked it against a real "
            "antenna; where it says modelled, it was computed by ELMER from the "
            "antenna's geometry and rounded up. Neither is a measurement.",
            s["small"]),
        # Said on paper as well as on screen: the sheet is what gets kept, and
        # somebody reading it later should know which way it was built to err.
        Paragraph("<b>Where this evaluation errs.</b> " + method["conservatism"],
                  s["small"]),
        Spacer(1, 18),
        Paragraph("I have evaluated this station and, to the best of my knowledge, "
                  "the information above is correct.", s["body"]),
        Spacer(1, 26),
        _grid([["Signature", "", "Date", ""]],
              [0.75 * inch, 2.8 * inch, 0.55 * inch, 1.9 * inch],
              [("BACKGROUND", (0, 0), (-1, -1), colors.white),
               ("GRID", (0, 0), (-1, -1), 0, colors.white),
               ("LINEBELOW", (1, 0), (1, 0), 0.6, INK),
               ("LINEBELOW", (3, 0), (3, 0), 0.6, INK),
               ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 8.4),
               ("FONT", (2, 0), (2, 0), "Helvetica-Bold", 8.4)]),
        Spacer(1, 14),
        Paragraph("Produced by ELMER. This is the licensee's own evaluation; it is "
                  "not filed with the FCC and carries no approval. Keep it with your "
                  "station records and repeat the evaluation whenever power, "
                  "antenna, or the position of people around the station changes.",
                  s["small"]),
    ]

    # The operator's own privileges, behind the evaluation and clearly apart
    # from it. Nothing is added when the licence class is not known, rather
    # than printing somebody else's bands under this callsign.
    flow += _privileges_page(evaluation, s)

    doc.build(flow)
    return buffer.getvalue()

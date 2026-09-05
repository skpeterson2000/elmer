"""Band chart as a printable station reference."""
import io
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Image, Line, Rect, String
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .bandplan import (BAND_INDEX, KINDS, activity_for, gaps_for,
                        privileges_for, usable_answer)

KIND_COLOUR = {
    "cw": colors.HexColor("#3d7ebf"), "digital": colors.HexColor("#7a4fbf"),
    "phone": colors.HexColor("#1f8f4e"), "image": colors.HexColor("#b8791f"),
    "beacon": colors.HexColor("#b03a48"), "satellite": colors.HexColor("#1f8f8f"),
    "repeater": colors.HexColor("#c2571f"), "simplex": colors.HexColor("#8a8f3a"),
    "calling": colors.HexColor("#111111"), "special": colors.HexColor("#666666"),
}
KIND_LABEL = dict(KINDS)


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=15,
                                spaceAfter=2, alignment=0),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=8.5,
                              textColor=colors.HexColor("#555555"), spaceAfter=8),
        "band": ParagraphStyle("b", parent=base["Heading2"], fontSize=10.5,
                               spaceBefore=9, spaceAfter=3),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=7.4, leading=9),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontSize=7,
                                leading=9, textColor=colors.HexColor("#555555")),
    }


def build(bands, licence_class, regional=None, station=None, interop=False):
    station = station or {}
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(LETTER),
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.45 * inch, bottomMargin=0.45 * inch,
                            title="Band plan")
    flow = [Paragraph("US Amateur Band Plan", s["title"])]
    line = (f"Privileges shown for <b>{licence_class}</b> class, per 47 CFR 97.301 "
            f"and 97.305. Activity segments are convention, not law.")
    if regional:
        line += (f" Regional segments from the {regional['name']} "
                 f"({regional['short']}), fetched {regional.get('fetched', '')}.")
    flow += [Paragraph(line, s["sub"])]

    legend = [[Paragraph(f'<font color="{KIND_COLOUR[k].hexval()}">&#9632;</font> {label}',
                         s["cell"]) for k, label in KINDS]]
    lt = Table(legend, colWidths=[0.95 * inch] * len(KINDS), hAlign="LEFT")
    lt.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    flow += [lt]

    for name in bands:
        band = BAND_INDEX.get(name)
        if not band:
            continue
        allowed = privileges_for(name, licence_class)
        gaps = gaps_for(name, licence_class)
        head = f"{name} &mdash; {band['low']:g} to {band['high']:g} MHz"
        if not allowed:
            head += "  (no privileges for this class)"
        block = [Paragraph(head, s["band"])]

        rows = [["From", "To", "Activity", "What happens there", "You?"]]
        style = []
        n = 0
        for low, high, kind, label in activity_for(name):
            n += 1
            you = usable_answer(name, licence_class, low, high, kind)
            state = you["state"]
            ok = state != "no"
            # Not dict.get with a default: the default is evaluated whatever
            # the state is, and on a "no" row there is no range to format.
            answer = (f"{_mhz(you['low'])}\u2013{_mhz(you['high'])}"
                      if state == "part" else state)
            # The reason goes beside the thing it is about. A range on its own
            # in the last column tells the reader something is different
            # without telling them what.
            body = label
            if you["note"] and state != "yes":
                body += f'<br/><font size="6" color="#8a6d1f">{you["note"]}</font>'
            rows.append([f"{low:.4f}".rstrip("0").rstrip("."),
                         f"{high:.4f}".rstrip("0").rstrip(".") if high != low else "",
                         KIND_LABEL.get(kind, kind),
                         Paragraph(body, s["cell"]),
                         answer])
            style.append(("TEXTCOLOR", (2, n), (2, n), KIND_COLOUR.get(kind, colors.black)))
            if state == "part":
                style.append(("TEXTCOLOR", (4, n), (4, n), colors.HexColor("#b8791f")))
            if not ok:
                style.append(("TEXTCOLOR", (4, n), (4, n), colors.HexColor("#b03a48")))
                style.append(("BACKGROUND", (0, n), (-1, n), colors.HexColor("#f6f6f6")))
        block.append(_table(rows, style))

        if regional and name in (regional.get("bands") or {}):
            block.append(Paragraph(
                f"{regional['short']} coordinated segments for {name}", s["small"]))
            rrows = [["From", "To", "Activity", "Coordinated use"]]
            rstyle = []
            for m, seg in enumerate(regional["bands"][name], start=1):
                rrows.append([f"{seg['low']:g}", f"{seg['high']:g}" if seg["high"] != seg["low"] else "",
                              KIND_LABEL.get(seg["kind"], seg["kind"]),
                              Paragraph(seg["label"], s["cell"])])
                rstyle.append(("TEXTCOLOR", (2, m), (2, m),
                               KIND_COLOUR.get(seg["kind"], colors.black)))
            block.append(_table(rrows, rstyle,
                                widths=[0.8, 0.8, 1.1, 6.6]))
        if gaps and allowed:
            block.append(Paragraph(
                "Outside your privileges on this band: " +
                ", ".join(f"{a:g}–{b:g}" for a, b in gaps) + " MHz.", s["small"]))
        flow.append(KeepTogether(block))

    flow += [Spacer(1, 10), Paragraph(
        "Privileges are law. Activity segments are voluntary band plan convention "
        "and carry no legal force, but operating against them is what causes "
        "complaints. Regional segments come from the local frequency coordinator "
        "and are reproduced from their published plan; check with them before "
        "relying on it. Produced by ELMER.", s["small"])]
    # Off unless asked for. A band chart is a one-page thing to pin up, and
    # three pages of channels nobody on this chart may transmit on is paper
    # wasted on almost everybody who prints it.
    if interop:
        flow += _interop_page(s)
    doc.build(flow)
    return buf.getvalue()


# --------------------------------------------------------------------------
# the one-page chart
# --------------------------------------------------------------------------
# A picture of the bands, drawn from ELMER's own reading of 47 CFR 97.301 and
# 97.305. The allocations are facts and belong to nobody; the drawing of them
# is ours, and is deliberately not modelled on anybody else's chart.

BAR_H = 15                     # height of a band's bar, points
ROW_H_MAX = 50                 # a band and its labels, at its most generous
# What is left for the drawing once the title, the note under it, the legend
# and the footnote have taken their share of a landscape page. A Drawing that
# does not fit is not shrunk by reportlab - it is moved to the next page, and
# on a one-page chart that means it silently disappears. So the rows are sized
# to the space rather than hoped to fit.
DRAWING_SPACE = 460
LABEL_W = 60                   # room for "1.25 m" and the range under it
EDGE_GAP = 26                  # closest two edge labels may sit, points

# What a segment lets you do, which is the thing worth seeing at a glance.
SEG_COLOUR = {
    "phone": colors.HexColor("#1f8f4e"),      # voice and image as well
    "data": colors.HexColor("#7a4fbf"),       # CW and digital
    "cw": colors.HexColor("#3d7ebf"),         # CW only
}
SEG_LABEL = {"phone": "Phone, image, CW, data", "data": "CW and data",
             "cw": "CW only"}
NO_PRIV = colors.HexColor("#e4e4e4")


def _segment_kind(emissions):
    if "phone" in emissions:
        return "phone"
    if "data" in emissions:
        return "data"
    return "cw"


def _band_row(group, x, y, width, name, licence_class):
    """One band: its name, its bar, and the edges worth reading off it."""
    from .bandplan import BAND_INDEX, emissions_in, limits_in, privileges_for

    band = BAND_INDEX.get(name)
    if not band:
        return
    low, high = band["low"], band["high"]
    span = high - low or 1.0
    bar_x = x + LABEL_W
    bar_w = width - LABEL_W

    group.add(String(x, y + 3, name, fontName="Helvetica-Bold", fontSize=8.5))
    group.add(String(x, y - 6, f"{_mhz(low)}\u2013{_mhz(high)}", fontSize=5.4,
                     fillColor=colors.HexColor("#666666")))

    # The whole band first, so anything not filled in afterwards is visibly
    # somewhere this licence may not go.
    group.add(Rect(bar_x, y - 2, bar_w, BAR_H, fillColor=NO_PRIV,
                   strokeColor=colors.HexColor("#9a9a9a"), strokeWidth=0.4))

    segments = sorted(privileges_for(name, licence_class))
    if not segments:
        group.add(String(bar_x + bar_w / 2, y + 3.5, "no privileges",
                         fontSize=6, textAnchor="middle",
                         fillColor=colors.HexColor("#8a8a8a")))
        return

    # 60 m is five 2.8 kHz channels, not a segment. Drawing it as a filled bar
    # would say, in the only language a chart has, that the whole range is
    # yours - so the channels are drawn where they actually are.
    if band.get("channelised"):
        from .bandplan import CHANNELS_60M
        kind = _segment_kind(emissions_in(segments[0][2]))
        width_mhz = 0.0028
        for centre, label in CHANNELS_60M:
            sx = bar_x + (centre - low) / span * bar_w
            sw = max(2.0, width_mhz / span * bar_w)
            group.add(Rect(sx - sw / 2, y - 2, sw, BAR_H,
                           fillColor=SEG_COLOUR[kind],
                           strokeColor=colors.white, strokeWidth=0.3))
            group.add(String(sx, y - 13, _mhz(centre), fontSize=5,
                             textAnchor="middle",
                             fillColor=colors.HexColor("#444444")))
        pep, erp = limits_in(segments[0][2])
        if erp:
            group.add(String(bar_x + bar_w, y + BAR_H + 1.5, f"{erp} W ERP, USB",
                             fontSize=5.5, textAnchor="end",
                             fillColor=colors.HexColor("#444444")))
        return

    edges, last_label_x = [], -999
    for seg_low, seg_high, terms in segments:
        kind = _segment_kind(emissions_in(terms))
        sx = bar_x + (seg_low - low) / span * bar_w
        sw = max(1.2, (seg_high - seg_low) / span * bar_w)
        group.add(Rect(sx, y - 2, sw, BAR_H, fillColor=SEG_COLOUR[kind],
                       strokeColor=colors.white, strokeWidth=0.3))
        pep, erp = limits_in(terms)
        ceiling = f"{pep} W" if pep else (f"{erp} W ERP" if erp else None)
        if ceiling and sw > 34:
            group.add(String(sx + sw / 2, y + 3.0, ceiling, fontSize=5,
                             textAnchor="middle", fillColor=colors.white))
        edges += [(seg_low, sx), (seg_high, sx + sw)]

    # Edges go under the bar, but a narrow segment - the CW-only sliver at the
    # bottom of 6 m and 2 m - would collide with the band edge beside it and be
    # dropped, leaving a stripe the reader cannot put a number to. Those go
    # above the bar instead, where there is nothing to collide with.
    above_x = -999
    for value, at in sorted(edges):
        if at - last_label_x >= EDGE_GAP:
            group.add(String(at, y - 13, _mhz(value), fontSize=5,
                             textAnchor="middle",
                             fillColor=colors.HexColor("#444444")))
            group.add(Line(at, y - 4, at, y - 7.5,
                           strokeColor=colors.HexColor("#888888"), strokeWidth=0.4))
            last_label_x = at
        elif at - above_x >= EDGE_GAP:
            group.add(String(at, y + BAR_H + 1.5, _mhz(value), fontSize=5,
                             textAnchor="middle",
                             fillColor=colors.HexColor("#444444")))
            group.add(Line(at, y + BAR_H - 1, at, y + BAR_H + 0.5,
                           strokeColor=colors.HexColor("#888888"), strokeWidth=0.4))
            above_x = at


def _colophon(group, x, y, width, licence_class, station):
    """Fill the corner the shorter column leaves empty.

    The VHF and up bands run out four rows before the HF ones do, and a hole
    under the right column makes a printed sheet look like a draft. The mark
    goes there, and with it the provenance: who the sheet was drawn for,
    against which class, and on what day - all of which a chart pinned above a
    radio for two years ought to be able to answer for itself.
    """
    icon = Path(__file__).resolve().parents[1] / "elmer" / "static" / "icon.png"
    right = x + width
    size = 54

    if icon.is_file():
        group.add(Image(right - size, y - size, size, size, str(icon)))
        mark_right = right - size - 12
    else:
        mark_right = right

    group.add(String(mark_right, y - 22, "ELMER", fontName="Helvetica-Bold",
                     fontSize=15, textAnchor="end"))
    group.add(String(mark_right, y - 34, "radio study & propagation", fontSize=6.5,
                     textAnchor="end", fillColor=colors.HexColor("#666666")))

    # Below both, so nothing sits under the icon.
    line = [p for p in (station.get("callsign"), licence_class,
                        date.today().isoformat()) if p]
    group.add(String(right, y - size - 13, "  \u00b7  ".join(line), fontSize=7,
                     textAnchor="end", fillColor=colors.HexColor("#444444")))
    group.add(String(right, y - size - 24,
                     "Privileges change. Check the current 47 CFR 97.301 and "
                     "97.305 before relying on this sheet.",
                     fontSize=6, textAnchor="end",
                     fillColor=colors.HexColor("#888888")))


def build_card(licence_class, station=None):
    """A single-page picture of the bands this class may use.

    Everything on it is drawn from the allocations themselves: what may be
    transmitted where is a fact of 47 CFR, and this is ELMER's own way of
    showing it rather than anybody else's.
    """
    from .bandplan import BANDS

    station = station or {}
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(LETTER),
                            leftMargin=0.4 * inch, rightMargin=0.4 * inch,
                            topMargin=0.35 * inch, bottomMargin=0.35 * inch,
                            title=f"US amateur bands - {licence_class}")

    who = f" &mdash; {station['callsign']}" if station.get("callsign") else ""
    flow = [Paragraph(f"US Amateur Bands &mdash; {licence_class}{who}", s["title"]),
            Paragraph(
                "Privileges per 47 CFR 97.301 and 97.305, drawn to scale within "
                "each band. Grey is spectrum this licence may not transmit on. "
                "1500 W PEP unless a segment says otherwise, and always the "
                "minimum power needed (97.313).", s["sub"])]

    hf = [b["name"] for b in BANDS if b.get("group") == "HF"]
    vhf = [b["name"] for b in BANDS if b.get("group") != "HF"]
    rows = max(len(hf), len(vhf))
    row_h = min(ROW_H_MAX, DRAWING_SPACE / rows)

    page_w = landscape(LETTER)[0] - 0.8 * inch
    col_w = (page_w - 26) / 2
    height = rows * row_h + 8
    drawing = Drawing(page_w, height)
    top = height - 14

    for column, names in ((0, hf), (1, vhf)):
        x = column * (col_w + 26)
        for n, name in enumerate(names):
            _band_row(drawing, x, top - n * row_h, col_w, name, licence_class)

    # The right column is the short one, so its leftover space gets the mark.
    if len(vhf) < rows:
        _colophon(drawing, col_w + 26, top - len(vhf) * row_h - 16, col_w,
                  licence_class, station)

    flow += [drawing, Spacer(1, 2)]

    legend = Drawing(page_w, 14)
    at = 0
    for kind in ("phone", "data", "cw"):
        legend.add(Rect(at, 2, 16, 9, fillColor=SEG_COLOUR[kind],
                        strokeColor=colors.white, strokeWidth=0.3))
        legend.add(String(at + 20, 4.5, SEG_LABEL[kind], fontSize=7))
        at += 26 + len(SEG_LABEL[kind]) * 3.6
    legend.add(Rect(at, 2, 16, 9, fillColor=NO_PRIV,
                    strokeColor=colors.HexColor("#9a9a9a"), strokeWidth=0.4))
    legend.add(String(at + 20, 4.5, "Not this licence", fontSize=7))
    flow += [legend, Paragraph(
        "60 m is five fixed channels rather than a band, and they are drawn "
        "where they are and at the width they are. Segment edges bound your "
        "whole emission, not the carrier. Produced by ELMER from the "
        "allocations themselves.", s["small"])]

    doc.build(flow)
    return buf.getvalue()


def _mhz(value):
    """A channel frequency, whole.

    Not "%g": these run to five decimals - 769.24375 - and %g stops at six
    significant digits, which silently rounds that to 769.244. A frequency
    somebody keys into a radio is the one number on the page that may not be
    approximated.
    """
    return f"{value:.5f}".rstrip("0").rstrip(".")


def _interop_page(s):
    """The nationwide interoperability channels, on a page of their own.

    Deliberately not folded into the band chart. Everything on the first page is
    spectrum the holder of this chart may transmit on; nothing on this one is,
    and the two must not be read as one list. A separate page with its own
    heading and its own warning is the only honest way to carry both.
    """
    from . import nifog
    record = nifog.load()
    if not record:
        return []

    flow = [PageBreak(),
            Paragraph("Nationwide interoperability channels", s["title"]),
            Paragraph(
                f"From the National Interoperability Field Operations Guide, "
                f"version {record.get('version') or '?'} "
                f"({record.get('dated') or 'undated'}), published by CISA and "
                f"read on {record.get('fetched')}. A work of the US government, "
                f"reproduced freely.", s["small"]),
            Paragraph(
                "<b>None of these channels is amateur spectrum, and this chart "
                "is not authority to transmit on any of them.</b> They are here "
                "to be monitored, and so that an operator supporting a served "
                "agency knows the names everyone else at the incident is using. "
                "Transmitting needs an authorisation an amateur licence does "
                "not confer. Tones are CTCSS in Hz; a value beginning $ is a "
                "P25 network access code in hexadecimal.", s["small"]),
            Spacer(1, 6)]

    for group in nifog.by_band(record):
        rows = [["Channel", "Use", "RX (MHz)", "RX tone", "TX (MHz)", "TX tone"]]
        for channel in group["channels"]:
            rows.append([channel["name"], channel["use"],
                         _mhz(channel["rx_mhz"]), channel["rx_tone"],
                         _mhz(channel["tx_mhz"]), channel["tx_tone"]])
        block = [Paragraph(group["band"], s["band"]),
                 _table(rows, [("ALIGN", (2, 0), (2, -1), "RIGHT"),
                               ("ALIGN", (4, 0), (4, -1), "RIGHT"),
                               ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 7.4)],
                        widths=(0.9, 1.9, 1.0, 0.8, 1.0, 0.8)),
                 Spacer(1, 7)]
        flow.append(KeepTogether(block))
    return flow


def _table(rows, extra, widths=(0.8, 0.8, 1.1, 4.9, 1.0)):
    t = Table(rows, colWidths=[w * inch for w in widths], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 7.4),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.4),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aaaaaa")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ] + list(extra)))
    return t

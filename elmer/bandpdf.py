"""Band chart as a printable station reference."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from .bandplan import BAND_INDEX, KINDS, activity_for, gaps_for, privileges_for

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


def build(bands, licence_class, regional=None, station=None):
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
            ok = any(a <= low and high <= b for a, b, _ in allowed)
            rows.append([f"{low:.4f}".rstrip("0").rstrip("."),
                         f"{high:.4f}".rstrip("0").rstrip(".") if high != low else "",
                         KIND_LABEL.get(kind, kind),
                         Paragraph(label, s["cell"]),
                         "yes" if ok else "no"])
            style.append(("TEXTCOLOR", (2, n), (2, n), KIND_COLOUR.get(kind, colors.black)))
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
    doc.build(flow)
    return buf.getvalue()


def _table(rows, extra, widths=(0.8, 0.8, 1.1, 5.4, 0.5)):
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

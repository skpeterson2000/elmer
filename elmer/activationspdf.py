"""The parks and summits near here, on paper for the trip out.

The screen version of this list answers "is there anything up there" from a
chair. This one goes in the vehicle, and that changes what belongs on it.

Coordinates are printed, because the next thing anybody does with a reference
they have chosen is type it into something that wants numbers, and a phone
with no signal at a trailhead will not look it up. The bearing is printed
beside the distance because both are straight lines and saying so once is
worth more than a reader assuming otherwise twice. And the count held is
printed against the count shown, so a sheet listing thirty parks cannot be
mistaken for the whole of what is within reach.

Parks and summits keep the colours they have on the screen - green and blue -
because somebody who compared the two lists there should not have to learn a
second scheme here.
"""
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#555555")
RULE = colors.HexColor("#999999")
BAND = colors.HexColor("#eeeeee")
PARK = colors.HexColor("#1a7f37")
SUMMIT = colors.HexColor("#1f5fbf")

# How many of each go on the sheet. Enough that a day's driving has choices on
# it, few enough that it is a sheet rather than a directory - the whole list
# is four hundred parks in some places, and nobody carries that to a lake.
DEFAULT_LIMIT = 30

# Miles, because the filter is set in miles and this sheet is read in a
# vehicle. Both units are printed against each distance: the screen counts in
# kilometres and a sheet that quietly switched would have somebody comparing
# two numbers that are not the same number.
MI_PER_KM = 0.621371


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=15,
                                spaceAfter=2, textColor=INK),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=8.6,
                              textColor=MUTED, spaceAfter=10, leading=11.5),
        "head": ParagraphStyle("h", parent=base["Normal"], fontSize=11,
                               spaceBefore=12, spaceAfter=4, textColor=INK),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=8.6,
                               leading=11.5, textColor=INK),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8,
                               leading=9.6, textColor=INK),
    }


def _table(rows, widths, tint):
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), tint),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (0, 1), (0, -1), tint),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return table


def _away(row):
    km = row.get("km")
    if km is None:
        return "—"
    return "%d mi \u00b7 %d km" % (round(km * MI_PER_KM), round(km))


def _band(inner_km, outer_km):
    """The band in the operator's own units, for the line under the title."""
    inner_mi = round((inner_km or 0) * MI_PER_KM)
    outer_mi = round((outer_km or 0) * MI_PER_KM)
    if not outer_km:
        return ""
    if inner_mi:
        return "Between %d and %d miles out." % (inner_mi, outer_mi)
    return "Out to %d miles." % outer_mi


def _coords(row):
    lat, lon = row.get("lat"), row.get("lon")
    if lat is None or lon is None:
        return row.get("grid") or "—"
    return "%.4f, %.4f" % (lat, lon)


def _parks(rows, s):
    out = [["Reference", "Name", "Away", "Brg", "Coordinates", "Where"]]
    for row in rows:
        out.append([
            row.get("ref", ""),
            Paragraph(row.get("name", ""), s["cell"]),
            _away(row),
            "%s°" % row.get("bearing", "—"),
            _coords(row),
            Paragraph(row.get("where") or "", s["cell"]),
        ])
    return _table(out, [0.82 * inch, 2.1 * inch, 0.9 * inch, 0.42 * inch,
                        1.2 * inch, 1.56 * inch], PARK)


def _summits(rows, s):
    out = [["Reference", "Name", "Away", "Brg", "Coordinates", "Alt", "Pts"]]
    for row in rows:
        out.append([
            row.get("ref", ""),
            Paragraph(row.get("name", ""), s["cell"]),
            _away(row),
            "%s°" % row.get("bearing", "—"),
            _coords(row),
            "%s m" % row["alt_m"] if row.get("alt_m") else "—",
            str(row.get("points") or "—"),
        ])
    return _table(out, [1.0 * inch, 1.93 * inch, 0.9 * inch, 0.42 * inch,
                        1.2 * inch, 0.55 * inch, 0.35 * inch], SUMMIT)


def _section(title, shown, held, colour, s):
    more = ("" if held <= shown else
            "  Nearest %d of %d held." % (shown, held))
    return Paragraph(
        '<font color="%s"><b>%s</b></font><font size="8.6" color="%s">'
        '   %d listed.%s</font>'
        % (colour.hexval(), title, MUTED.hexval(), shown, more), s["head"])


def build(parks, summits, want="both", station=None, radius_km=None,
          limit=DEFAULT_LIMIT, inner_km=0.0, outer_km=None):
    """The sheet. `want` is 'parks', 'summits' or 'both'.

    `inner_km` and `outer_km` are a band rather than a cap, because the trips
    people take are bands. Nought to ten miles is an evening after work;
    thirty to forty is somewhere worth the drive with nothing already worked
    in between. A list that always starts at the doorstep buries the second
    kind under the first.
    """
    station = station or {}
    s = _styles()
    held = {"parks": len(parks), "summits": len(summits)}
    parks = parks[:limit] if want in ("parks", "both") else []
    summits = summits[:limit] if want in ("summits", "both") else []

    named = {"parks": "Parks", "summits": "Summits",
             "both": "Parks and summits"}[want]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
        title="%s near %s" % (named, station.get("grid") or "here"),
        author=station.get("callsign") or "Amateur station")

    where = station.get("place") or station.get("grid") or "the station"
    flow = [
        Paragraph("%s near %s" % (named, where), s["title"]),
        Paragraph(
            "Distances and bearings are straight lines from %s, taken %s. A "
            "road is not a straight line - reckon on more. Nothing here says a "
            "reference is open, reachable, or that the track up it is passable "
            "today; it says where it is."
            % (station.get("grid") or "the station",
               station.get("date") or date.today().isoformat()),
            s["sub"]),
    ]
    band = _band(inner_km, outer_km)
    if band:
        flow.append(Paragraph("<b>%s</b>  Nothing nearer or further is on this "
                              "sheet." % band, s["body"]))
    elif radius_km:
        flow.append(Paragraph(
            "Held within %d km of %s." % (radius_km,
                                          station.get("grid") or "here"),
            s["body"]))

    # "None in the radius" and "none in the band" are different statements,
    # and on a sheet asked for between thirty and forty miles the first one is
    # wrong: there may be a dozen of them at five.
    none = ("None held in that band." if band else
            "None held within the radius.")
    if want in ("parks", "both"):
        flow.append(_section("Parks on the Air", len(parks), held["parks"],
                             PARK, s))
        flow.append(_parks(parks, s) if parks else
                    Paragraph(none, s["body"]))
    if want in ("summits", "both"):
        flow.append(_section("Summits on the Air", len(summits),
                             held["summits"], SUMMIT, s))
        flow.append(_summits(summits, s) if summits else
                    Paragraph(none, s["body"]))

    flow += [Spacer(1, 12), Paragraph(
        "A park contact and a summit contact answer to different rules - a "
        "vehicle is ordinary in a park and a disqualification on a summit. "
        "ELMER's Parks and summits page has both sets.", s["sub"])]

    doc.build(flow)
    return buffer.getvalue()

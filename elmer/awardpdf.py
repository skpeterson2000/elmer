"""An achievement as a piece of paper: one page, for the wall.

The dashboard's badges are a study record's milestones, and a few of them
- the whole code copied, a mock exam passed, the first thing ever keyed
that was answered - are worth more than a pill on a screen. So any badge
a person holds can be printed: the same page shape as the tournament
certificates in :mod:`elmer.certpdf`, the same mark and inks, a star in
place of the medal, the badge's name and what it was for, whose it is and
when. The foot says what it is not. Built on demand and kept on the print
shelf like every other printout, so it opens in the browser's own viewer
with the print button where it always is.
"""
import math
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.pdfgen import canvas

from .certpdf import DIM, ICON, INK, _fit

RULE = colors.HexColor("#c8a24a")
STAR = colors.HexColor("#e0b23c")
STAR_EDGE = colors.HexColor("#9a7318")
FOOTER = ("A badge earned in ELMER, the radio study assistant. It marks practice - "
          "the record of a person at the table - and is not a license, an award of "
          "any body, or a claim of either.")


def _star(c, x, y, r, points=5):
    """A five-pointed star, filled and edged, centerd on (x, y)."""
    path = c.beginPath()
    for i in range(points * 2):
        rad = r if i % 2 == 0 else r * 0.42
        ang = math.pi / 2 + i * math.pi / points
        px, py = x + rad * math.cos(ang), y + rad * math.sin(ang)
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    path.close()
    c.setFillColor(STAR)
    c.setStrokeColor(STAR_EDGE)
    c.setLineWidth(2)
    c.drawPath(path, fill=1, stroke=1)


def build(name, description, who, callsign=None, when=None, code=None):
    """One page: the badge `name`, `description` of what it was for, and
    `who` it belongs to (with their `callsign`, if they hold one). Returns
    the PDF bytes."""
    when = when or f"{date.today().day} {date.today():%B %Y}"
    W, H = landscape(LETTER)
    margin = 0.7 * 72
    import io
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(LETTER))
    c.setTitle(f"{name} - ELMER achievement")
    c.setAuthor("ELMER")

    # Border: the double rule the certificates wear.
    c.setStrokeColor(RULE)
    c.setLineWidth(3)
    c.rect(margin, margin, W - 2 * margin, H - 2 * margin)
    c.setLineWidth(0.8)
    c.rect(margin + 8, margin + 8, W - 2 * margin - 16, H - 2 * margin - 16)

    # The mark, top left; what this is, top right.
    top = H - margin - 30
    if ICON.is_file():
        c.drawImage(str(ICON), margin + 24, top - 40, 46, 46, mask="auto")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin + 80, top - 18, "ELMER")
    c.setFont("Helvetica", 8)
    c.setFillColor(DIM)
    c.drawString(margin + 80, top - 30, "radio study & propagation")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(W - margin - 24, top - 18, "Achievement")
    c.setFont("Helvetica", 10)
    c.setFillColor(DIM)
    c.drawRightString(W - margin - 24, top - 33, when)

    # The star, left of center; the words, right of it.
    sx, sy, sr = margin + 160, H / 2 - 6, 92
    _star(c, sx, sy, sr)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(sx, sy - 4, "ELMER")

    tx = sx + sr + 60
    tw = W - margin - 24 - tx
    c.setFillColor(INK)
    size = _fit(c, name, "Helvetica-Bold", 40, tw)
    c.setFont("Helvetica-Bold", size)
    c.drawString(tx, sy + 78, name)

    c.setFont("Helvetica", 12)
    c.setFillColor(DIM)
    c.drawString(tx, sy + 56, "is awarded to")

    owner = str(who or "").strip() or "the operator"
    if callsign and callsign.strip().upper() not in owner.upper():
        owner = f"{owner}, {callsign.strip().upper()}"
    size = _fit(c, owner, "Helvetica-Bold", 44, tw)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", size)
    c.drawString(tx, sy + 12, owner)

    c.setFont("Helvetica", 13)
    c.setFillColor(INK)
    line = f"for this: {description}" if description else ""
    if line:
        size = _fit(c, line, "Helvetica", 13, tw, floor=9)
        c.setFont("Helvetica", size)
        c.drawString(tx, sy - 18, line)
    if code:
        c.setFont("Helvetica", 8.5)
        c.setFillColor(DIM)
        c.drawString(tx, sy - 40, f"badge {code} - one of ELMER's own, kept in the record on the unit it was earned on")

    # The date line along the foot, for a hand to add anything to.
    fy = margin + 62
    c.setStrokeColor(INK)
    c.setLineWidth(0.8)
    c.line(W - margin - 240, fy, W - margin - 60, fy)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(DIM)
    c.drawString(W - margin - 240, fy - 12, f"Earned — {when}")

    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(DIM)
    c.drawCentredString(W / 2, margin + 22, FOOTER)
    c.showPage()
    c.save()
    return buffer.getvalue()

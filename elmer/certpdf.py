"""A certificate for the wall: who placed where, at which event, on what day.

A club that runs a tournament night has nothing to hand the winner. The score
was on a screen and the screen has moved on; the evening is over and the
person who won it goes home with the memory. This is the piece of paper -
landscape, one placing to a page, large type, a medal, two signature lines and
the date - because if it is not there it will never be used, and a thing on
somebody's wall is the most persistent form a result can take.

What it says is what the program measured: the placing, the name played
under, the tournament by class and length, the questions answered and the
fastest-correct count, the blocks won. What it does *not* say is anything
about a licence. A game result is not an examination and this paper is not a
claim of one, and it says so in small type at the foot, because a certificate
with "Technician" in large letters on it will be read that way by somebody
unless the paper itself says otherwise.

The medal is art if there is art - `elmer/static/medals/gold.png`, silver,
bronze - and a drawn rosette if there is not, so the certificate never waits
on a file.
"""
import io
import math
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "elmer" / "static" / "icon.png"
MEDALS = ROOT / "elmer" / "static" / "medals"

PLACE_WORD = {1: "First place", 2: "Second place", 3: "Third place"}
PLACE_FILE = {1: "gold", 2: "silver", 3: "bronze"}
MEDAL_TINT = {1: ("#d4a017", "#f5d47a"), 2: ("#9aa3ad", "#dfe4e8"),
              3: ("#a0622d", "#d69a66")}

INK = colors.HexColor("#1b2430")
DIM = colors.HexColor("#5a6572")
RULE = colors.HexColor("#c8a24a")


def medal_image(place):
    """The art for this placing, if the artwork has been put where it goes."""
    name = PLACE_FILE.get(place)
    if not name:
        return None
    for ext in ("png", "jpg", "jpeg"):
        candidate = MEDALS / f"{name}.{ext}"
        if candidate.is_file():
            return candidate
    return None


def _ribbon(c, cx, cy, r):
    """Two tails behind the disc, in the blue the artwork's ribbon was."""
    c.saveState()
    c.setFillColor(colors.HexColor("#1f4fa3"))
    for sign in (-1, 1):
        p = c.beginPath()
        p.moveTo(cx + sign * r * 0.35, cy + r * 0.2)
        p.lineTo(cx + sign * r * 0.95, cy + r * 1.9)
        p.lineTo(cx + sign * r * 0.25, cy + r * 1.9)
        p.lineTo(cx + sign * r * 0.05, cy + r * 0.6)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def _rosette(c, cx, cy, r, place):
    """A drawn medal: a rim, a disc, and the placing on it."""
    dark, light = (colors.HexColor(h) for h in MEDAL_TINT.get(place, MEDAL_TINT[3]))
    c.saveState()
    # Rim, disc, inner ring.
    c.setFillColor(dark)
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFillColor(light)
    c.circle(cx, cy, r * 0.86, fill=1, stroke=0)
    c.setStrokeColor(dark)
    c.setLineWidth(max(1.0, r * 0.05))
    c.circle(cx, cy, r * 0.68, fill=0, stroke=1)
    # Scallops around the rim.
    c.setFillColor(dark)
    for i in range(24):
        a = 2 * math.pi * i / 24
        c.circle(cx + math.cos(a) * r * 0.97, cy + math.sin(a) * r * 0.97,
                 r * 0.07, fill=1, stroke=0)
    # The number.
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", r * 0.9)
    c.drawCentredString(cx, cy - r * 0.32, str(place))
    c.restoreState()


def _medal(c, cx, cy, r, place):
    _ribbon(c, cx, cy, r)
    art = medal_image(place)
    if art is not None:
        c.drawImage(str(art), cx - r, cy - r, r * 2, r * 2,
                    mask="auto", preserveAspectRatio=True, anchor="c")
    else:
        _rosette(c, cx, cy, r, place)


def _fit(c, text, font, size, width, floor=14):
    """The largest size at or under `size` that fits the text in `width`."""
    while size > floor and c.stringWidth(text, font, size) > width:
        size -= 1
    return size


def _page(c, award, event, when, where, footer):
    W, H = landscape(LETTER)
    margin = 0.7 * 72
    place = int(award.get("place") or 1)

    # Border: a double rule, the outer heavier, in the medal's colour family.
    c.setStrokeColor(RULE)
    c.setLineWidth(3)
    c.rect(margin, margin, W - 2 * margin, H - 2 * margin)
    c.setLineWidth(0.8)
    c.rect(margin + 8, margin + 8, W - 2 * margin - 16, H - 2 * margin - 16)

    # The mark, top left; the event, top right.
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
    size = _fit(c, event, "Helvetica-Bold", 15, W / 2 - margin)
    c.setFont("Helvetica-Bold", size)
    c.drawRightString(W - margin - 24, top - 18, event)
    c.setFont("Helvetica", 10)
    c.setFillColor(DIM)
    c.drawRightString(W - margin - 24, top - 33, when)

    # The medal, left of centre; the words, right of it.
    mx, my, mr = margin + 160, H / 2 - 6, 92
    _medal(c, mx, my, mr, place)

    tx = mx + mr + 60
    tw = W - margin - 24 - tx
    c.setFillColor(INK)
    word = PLACE_WORD.get(place, f"{place}th place")
    c.setFont("Helvetica-Bold", 40)
    c.drawString(tx, my + 78, word)

    c.setFont("Helvetica", 12)
    c.setFillColor(DIM)
    c.drawString(tx, my + 56, "is awarded to")

    name = str(award.get("name") or "").strip() or "the player"
    size = _fit(c, name, "Helvetica-Bold", 44, tw)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", size)
    c.drawString(tx, my + 12, name)

    c.setFont("Helvetica", 13)
    c.setFillColor(INK)
    y = my - 18
    for line in award.get("lines") or []:
        size = _fit(c, line, "Helvetica", 13, tw, floor=9)
        c.setFont("Helvetica", size)
        c.drawString(tx, y, line)
        y -= size + 6

    # Where, if known.
    if where:
        c.setFont("Helvetica", 10)
        c.setFillColor(DIM)
        c.drawString(tx, y - 6, where)

    # Two signature lines and the date, along the foot.
    sy = margin + 62
    c.setStrokeColor(INK)
    c.setLineWidth(0.8)
    for x0, label in ((margin + 60, "Net control"),
                      (W / 2 - 90, "Club or event"),
                      (W - margin - 240, "Date")):
        c.line(x0, sy, x0 + 180, sy)
        c.setFont("Helvetica", 8.5)
        c.setFillColor(DIM)
        c.drawString(x0, sy - 12, label)

    # And what this paper is not.
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(DIM)
    c.drawCentredString(W / 2, margin + 22, footer)


def build(awards, event="ELMER tournament", when=None, where=None, footer=None):
    """One page per award. `awards`: [{place, name, lines: [...]}, ...]."""
    when = when or date.today().strftime("%-d %B %Y")
    footer = footer or (
        "A tournament result, recorded by ELMER. It is a game played on the "
        "licence question pools; it is not an examination, a licence, or a "
        "claim of either.")
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(LETTER))
    c.setTitle(f"{event} - certificates")
    c.setAuthor("ELMER")
    for award in awards:
        _page(c, award, event, when, where, footer)
        c.showPage()
    c.save()
    return buffer.getvalue()


def lines_for(entry, game):
    """The facts about a placing, in sentences a certificate can carry.

    `entry` is a row from the hall's people board or a table's players;
    `game` says what was played - difficulty label, length, blocks.
    """
    out = []
    what = game.get("label") or "tournament"
    length = game.get("length")
    blocks = game.get("blocks")
    if game.get("mode") == "shootout":
        out.append(f"Last one standing in the {what} shootout")
        if entry.get("letters") is not None:
            word = "ELMER"[:int(entry["letters"])] or "no letters"
            out.append(f"finishing on {word}")
    else:
        out.append(f"in the {what} tournament" +
                   (f" - {length} questions" if length else "") +
                   (f" in {blocks} blocks of twelve" if blocks and blocks > 1 else ""))
        if entry.get("answered"):
            out.append(f"{entry.get('correct', 0)} of {entry['answered']} correct"
                       + (f" - {entry['score']} points" if entry.get("score") is not None else ""))
        if entry.get("fastest"):
            n = entry["fastest"]
            out.append(f"fastest correct answer {n} time{'s' if n != 1 else ''}")
        if entry.get("blocks_won"):
            b = entry["blocks_won"]
            out.append("won block" + ("s " if len(b) > 1 else " ") +
                       ", ".join(str(x) for x in b))
    if entry.get("unit_name"):
        table = str(entry["unit_name"])
        # "at the Table 4 table" is what a table named "Table 4" would get.
        out.append(f"at {table}" if table.lower().startswith("table")
                   else f"at the {table} table")
    return out

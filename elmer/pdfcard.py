"""A card in the space a printout leaves over.

Most sheets end part way down their last page. That space can hold one of
the cards the waiting screens show - a quotation, a piece of the history -
if the operator wants it to. It must fit what is left and never spill: a
card that does not fit would be pushed onto a page of its own, and a sheet
of paper with one quotation on it is a waste the operator did not ask for.

ReportLab tells the last thing in a story how much of the frame is left
when it asks that thing how big it is. So the card goes in last, measures
each candidate at the real width in the real type, takes the first that
fits, and takes nothing - no height at all - when none does or when the gap
is too small for a card to look intended rather than squeezed.

Which cards are candidates is the operator's setting, read by the route
(see candidates()). Off is the default: a band chart is a reference first.
"""
import logging
import random
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Paragraph

from . import trivia

log = logging.getLogger("elmer")

MODES = ("off", "auto", "mine")

# Less room than this and the sheet ends where it ends. A card in a sliver
# reads as a mistake, not a choice.
MIN_GAP = 0.6 * inch
# Clear space above the card, so it does not read as the sheet's last line.
PAD = 14
# A quotation set across a ten-inch landscape page is one long thin line;
# it is held to a book's measure and centered instead.
MAX_WIDTH = 6.2 * inch

# The decks that suit each kind of sheet, best first. Every deck is still a
# candidate after these - they lead, they do not exclude.
FITS = {
    "band-chart": ("technique", "history"),
    "band-sheet": ("technique", "hams"),
    "antenna": ("equipment", "technique"),
    "activations": ("hams", "technique"),
}

QUOTE = ParagraphStyle("card", fontName="Helvetica-Oblique", fontSize=8.6,
                       leading=11.2, textColor=colors.HexColor("#333333"))
SOURCE = ParagraphStyle("card-source", fontName="Helvetica", fontSize=7,
                        leading=9, textColor=colors.HexColor("#666666"),
                        spaceBefore=2, leftIndent=10)
RULE = colors.HexColor("#bbbbbb")


def candidates(settings, kind, rng=None):
    """The cards to try on a sheet of this kind, in the order to try them,
    or None when the operator has cards on printouts turned off.

    "auto" is every deck, the ones that suit the sheet first, each shuffled.
    "mine" is the cards the operator picked, shuffled; when none of those
    fits, the sheet goes out without one rather than with a card nobody chose.
    """
    rng = rng or random
    mode = (settings or {}).get("print_cards") or "off"
    if mode == "mine":
        picks = list((settings or {}).get("print_card_picks") or [])
        cards = trivia.by_id(picks)
        if len(cards) < len(picks):
            log.info("print cards: %d picked card(s) no longer in the decks",
                     len(picks) - len(cards))
        rng.shuffle(cards)
        return cards
    if mode != "auto":
        return None
    first = FITS.get(kind, ())
    every = trivia.every_card()
    lead = [c for c in every if c["deck"] in first]
    rest = [c for c in every if c["deck"] not in first]
    rng.shuffle(lead)
    rng.shuffle(rest)
    return lead + rest


class SpareCard(Flowable):
    """The last thing in a story: one card if one fits, otherwise nothing.

    After the build, `chosen` is the card that went on the page, or None.
    """

    def __init__(self, cards, min_gap=MIN_GAP):
        super().__init__()
        self.cards = list(cards or [])
        self.min_gap = min_gap
        self.chosen = None
        self._parts = None
        self._width = 0

    def _set(self, card, width):
        quote = Paragraph(escape(card["text"]), QUOTE)
        source = Paragraph("&mdash; " + escape(card["about"]), SOURCE)
        _, qh = quote.wrap(width, 10 ** 6)
        _, sh = source.wrap(width - SOURCE.leftIndent, 10 ** 6)
        return (quote, qh, source, sh), PAD + qh + SOURCE.spaceBefore + sh

    def wrap(self, avail_width, avail_height):
        # Asked again with the same room, the answer must be the same: the
        # frame may measure more than once before it draws.
        self.chosen, self._parts = None, None
        self.width, self.height = avail_width, 0
        self._width = min(avail_width, MAX_WIDTH)
        if avail_height < self.min_gap:
            return self.width, 0
        for card in self.cards:
            parts, height = self._set(card, self._width)
            if height <= avail_height:
                self.chosen, self._parts, self.height = card, parts, height
                break
        return self.width, self.height

    def split(self, avail_width, avail_height):
        # Never on two pages. wrap() never asks for more than it was given,
        # so this is only reached by a frame being unusual - and then the
        # answer is no card, not a card on a page of its own.
        return []

    def draw(self):
        if not self._parts:
            return
        quote, qh, source, sh = self._parts
        x = (self.width - self._width) / 2
        top = qh + SOURCE.spaceBefore + sh
        self.canv.setStrokeColor(RULE)
        self.canv.setLineWidth(0.5)
        self.canv.line(x, top + PAD / 2, x + 0.8 * inch, top + PAD / 2)
        quote.drawOn(self.canv, x, sh + SOURCE.spaceBefore)
        source.drawOn(self.canv, x + SOURCE.leftIndent, 0)

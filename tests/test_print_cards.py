#!/usr/bin/env python3
"""ELMER's cards are found by the Library's search, and can fill a printout's
spare space without ever costing a page.

    python3 tests/test_print_cards.py

Two things the waiting-screen cards now do.

The Library's search reaches them, in a section of their own beneath the
books. A card's source line is searched as well as its words, because that
is often where the name is: the Collier's quotation of 1926 never says
"Tesla". And the source goes out with every card, since several of them say
the attribution is doubtful.

A printout can carry one in what its last page leaves over. The promise
that matters is the one about paper: a card goes on only where it fits
whole, a gap too small to look meant is left empty, and a sheet never gains
a page because of it. That is proved here by sweeping a sheet's length
through a whole page and comparing page counts with and without the card.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from reportlab.lib.pagesizes import LETTER  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate  # noqa: E402
from elmer import library, pdfcard, prints, trivia  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


class Probe(Flowable):
    """Takes no room; remembers how much the page had left when asked."""

    def __init__(self):
        super().__init__()
        self.gap = None

    def wrap(self, avail_width, avail_height):
        self.gap = avail_height
        return avail_width, 0

    def draw(self):
        pass


def sheet(lines, last):
    """A one-column letter sheet `lines` paragraphs long, then `last`.
    Returns the number of pages it came to."""
    body = getSampleStyleSheet()["Normal"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=inch, rightMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    flow = [Paragraph("Line %d of the sheet, long enough to be a line." % n, body)
            for n in range(lines)]
    doc.build(flow + [last])
    return doc.page


def main():
    print("\n-- the cards, by name --")
    ids = [c["id"] for c in trivia.every_card()]
    check("every card has its own id", len(ids), len(set(ids)))
    check("an id is the same asked twice", ids == [c["id"] for c in trivia.every_card()], True)

    print("\n-- found by the Library's search --")
    tesla = trivia.search(library._terms("Tesla"))
    abouts = [c["about"] for c in tesla]
    colliers = [c for c in tesla if "Collier's" in c["about"]]
    check("the Collier's quotation is found by his name", len(colliers), 1)
    check("  though the quotation itself never says it",
          "tesla" in colliers[0]["text"].lower() if colliers else None, False)
    check("  and the patent card, which does", any("Marconi v. United States" in a for a in abouts), True)
    einstein = trivia.search(library._terms("einstein"))
    check("the cat story comes with its doubt attached",
          bool(einstein) and "none quote him directly" in einstein[0]["about"], True)
    check("every word must be there, as for a page",
          trivia.search(library._terms("tesla zzqx")), [])
    check("nothing asked, nothing found", trivia.search([]), [])

    found = library.search("Tesla")
    check("library.search carries the cards apart from the pages",
          [c["id"] for c in found["cards"]], [c["id"] for c in tesla])
    check("  and none in among the pages", found["hits"], [])
    check("the reader's search inside one book takes no cards",
          library.search("Tesla", book_name="nothing.pdf")["cards"], [])

    print("\n-- which cards are tried --")
    one = trivia.every_card()[3]
    check("off is no card at all", pdfcard.candidates({}, "antenna"), None)
    check("  and so is a mode nobody set", pdfcard.candidates({"print_cards": "loud"}, "antenna"), None)
    check("only the picked cards when only picks are wanted",
          [c["id"] for c in pdfcard.candidates(
              {"print_cards": "mine", "print_card_picks": [one["id"], "0000000000"]}, "antenna")],
          [one["id"]])
    auto = pdfcard.candidates({"print_cards": "auto"}, "antenna")
    lead = len([c for c in trivia.every_card() if c["deck"] in pdfcard.FITS["antenna"]])
    check("ELMER's choice tries every card", len(auto), len(ids))
    check("  the ones that suit the sheet first",
          {c["deck"] for c in auto[:lead]} <= set(pdfcard.FITS["antenna"]), True)

    print("\n-- the paper: never a page more --")
    spilled, carried, crowded = [], 0, []
    for lines in range(0, 60):
        probe = Probe()
        bare = sheet(lines, probe)
        spare = pdfcard.SpareCard(pdfcard.candidates({"print_cards": "auto"}, "band-chart"))
        with_card = sheet(lines, spare)
        if with_card != bare:
            spilled.append(lines)
        if spare.chosen is not None:
            carried += 1
            if probe.gap < pdfcard.MIN_GAP:
                crowded.append(lines)
    check("no length of sheet gains a page from its card", spilled, [])
    check("no card squeezed into a gap smaller than the minimum", crowded, [])
    check("and most lengths have room for one", carried > 30, True)

    tight = pdfcard.SpareCard(trivia.every_card())
    check("a gap with room for none of them is left empty",
          (tight.wrap(6 * inch, pdfcard.MIN_GAP - 1), tight.chosen), ((6 * inch, 0), None))
    longest = max(trivia.every_card(), key=lambda c: len(c["text"]))
    picky = pdfcard.SpareCard([longest])
    picky.wrap(6 * inch, pdfcard.MIN_GAP + 1)
    check("a picked card that does not fit is not forced in", picky.chosen, None)
    check("  and never split across pages", picky.split(6 * inch, 10 ** 6), [])

    print("\n-- the routes --")
    from elmer.app import app
    client = app.test_client()
    client.post("/api/users/switch", json={"id": 1}, environ_base=LOCAL)

    def made(layout=None):
        body = {"class": "Technician"}
        if layout:
            body["layout"] = layout
        r = client.post("/api/bandplan/pdf", json=body, environ_base=LOCAL)
        return prints.one(r.get_json()["id"])["meta"]

    check("a sheet goes out with no card until one is asked for", "card" in made(), False)
    r = client.post("/api/settings", json={"print_cards": "loud"}, environ_base=LOCAL)
    check("a mode that is not one is refused", r.status_code, 400)
    short = min(trivia.every_card(), key=lambda c: len(c["text"]) + len(c["about"]))
    r = client.post("/api/settings", json={"print_cards": "mine",
                                           "print_card_picks": [short["id"], "not-a-card", short["id"]]},
                    environ_base=LOCAL)
    check("the picks are kept, once each, and only real cards",
          r.get_json()["settings"].get("print_card_picks"), [short["id"]])
    meta = made()
    check("the full chart carries the picked card, and the shelf says which",
          (meta.get("card") or {}).get("id"), short["id"])
    check("the one-page chart takes no card", "card" in made("card"), False)
    every = client.get("/api/cards/all", environ_base=LOCAL).get_json()
    check("the picker is offered every card", len(every["cards"]), len(ids))
    page = client.get("/prints", environ_base=LOCAL).data.decode("utf-8")
    check("the Printouts page has the setting", "A card in the spare space" in page, True)
    check("  and names the card a sheet went out with", "with a card:" in page, True)
    found = client.get("/api/library/search?q=tesla", environ_base=LOCAL).get_json()
    check("the Library's search answers with the cards over the wire",
          any("Collier's" in c["about"] for c in found["cards"]), True)

    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()

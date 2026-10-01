"""Tables from the manuals on the shelf, as printed, with the page each is on.

The Library's books are free to copy (data/shelf/manifest.json says why for
each), and some of what is in them is exactly what somebody standing in a
field wants without opening a 160-page PDF: how far a signal leaving at 25
degrees comes down, how long the inverted L's top wire is on 80 m. So the
pertinent tables are here, copied from the page - never paraphrased, never
"improved" - and the pages that use them show the row that applies, with
the citation and a link that opens the book at that page.

Each table was read off the rendered page, not the PDF's text: the text
layer of ATP 6-02.53's Table E-1 lays the angle column out apart from the
distances, so pairing them from the text would have shipped a table that
looked right and was not. tests/test_manuals.py pins every number to the
page it came from.

Where a printed figure is plainly a slip, it is still printed as it is, and
the slip is said beside it.
"""
import logging

from . import library

log = logging.getLogger("elmer")

ATP = {"file": "ATP-6-02.53-2025.pdf",
       "short": "ATP 6-02.53",
       "title": "ATP 6-02.53, Techniques for Tactical Radios and Retransmission",
       "edition": "31 July 2025"}

# Table E-1, printed page 87 (the PDF's page 97). Take-off angle in degrees,
# then the distance to where the wave comes down off the F2 layer by day and
# by night, each in kilometers and miles as the table prints them.
TAKEOFF_DISTANCE = {
    "book": ATP,
    "name": "Table E-1. Antenna take-off angle versus distance",
    "page": 87,
    "pdf_page": 97,
    "columns": ["Take off angle (degrees)", "F2 daytime km", "F2 daytime miles",
                "F2 nighttime km", "F2 nighttime miles"],
    "rows": [
        (0, 3220, 2000, 4508, 2800),
        (5, 2415, 1500, 3703, 2300),
        (10, 1932, 1200, 2898, 1800),
        (15, 1450, 900, 2254, 1400),
        (20, 1127, 700, 1771, 1100),
        (25, 966, 600, 1610, 1000),
        (30, 725, 450, 1328, 825),
        (35, 644, 400, 1127, 700),
        (40, 564, 350, 966, 600),
        (45, 443, 275, 805, 500),
        (50, 403, 250, 685, 425),
        (60, 258, 160, 443, 275),
        (70, 153, 95, 290, 180),
        (80, 80, 50, 145, 90),
        (90, 0, 0, 0, 0),
    ],
}


# Table E-3, printed page 91 (the PDF's page 101): the V antenna's optimum
# apex angle by the length of its legs in wavelengths. "When using the V
# antenna with more than one frequency or wavelength, operators should use an
# apex angle that is midway between the extreme angles as determined in
# table E-3" (E-34, the same page).
V_APEX = {
    "book": ATP,
    "name": "Table E-3. Leg angle for V antenna",
    "page": 91,
    "pdf_page": 101,
    "columns": ["Antenna Length (Wavelength)", "Optimum Apex Angle (Degrees)"],
    "rows": [(1, 90), (2, 70), (3, 58), (4, 50), (6, 40), (8, 35), (10, 33)],
    "rule": "E-34. The angle between the legs varies with the length of the legs to achieve maximum "
            "performance. Table E-3 shows the angle and the length of the legs. When using the V antenna with "
            "more than one frequency or wavelength, operators should use an apex angle that is midway between "
            "the extreme angles as determined in table E-3.",
}


def _row(r):
    return {"deg": r[0], "day_km": r[1], "day_mi": r[2], "night_km": r[3], "night_mi": r[4]}


def cite(table):
    """Where a table is: the book, the table's own name, its page, and the
    reader's link that opens the book there - or no link when the book is
    not in this unit's Library."""
    book = table["book"]
    link = None
    try:
        if library.book(book["file"]) is not None:
            link = f"/library/read/{book['file']}?page={table['pdf_page']}"
    except OSError as exc:
        log.warning("could not look for %s on the shelf: %s", book["file"], exc)
    return {"book": book["short"], "title": book["title"], "edition": book["edition"],
            "table": table["name"], "page": table["page"], "link": link}


def takeoff_distance(angle_deg):
    """Table E-1 at this take-off angle: the row itself where the angle is one
    the table prints, else the rows either side of it. ELMER does not draw a
    line between them - the table is the Army's, and what lies between two of
    its rows is not.

    Returns {"angle", "rows": [one or two rows], "exact", "cite"}, or None for
    an angle outside 0-90."""
    try:
        a = float(angle_deg)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= a <= 90.0:
        return None
    rows = TAKEOFF_DISTANCE["rows"]
    near = round(a)
    exact = next((r for r in rows if r[0] == near and abs(a - near) < 0.5), None)
    if exact:
        picked = [exact]
    else:
        below = max((r for r in rows if r[0] <= a), key=lambda r: r[0])
        above = min((r for r in rows if r[0] >= a), key=lambda r: r[0])
        picked = [below] if below is above else [below, above]
    return {"angle": round(a, 1), "rows": [_row(r) for r in picked], "exact": len(picked) == 1,
            "cite": cite(TAKEOFF_DISTANCE)}


def for_page():
    """What a page needs to look rows up for itself as its inputs move: the
    tables and their citations, small enough to hand over with the page."""
    return {"takeoff_distance": {"rows": [_row(r) for r in TAKEOFF_DISTANCE["rows"]],
                                 "cite": cite(TAKEOFF_DISTANCE)},
            "v_apex": {"rows": [list(r) for r in V_APEX["rows"]], "cite": cite(V_APEX)}}


AUXFOG = {"file": "AUXFOG-1.1-2016.pdf",
          "short": "AUXFOG 1.1",
          "title": "AUXFOG: Auxiliary Communications Field Operations Guide, Version 1.1",
          "edition": "June 2016"}

# The plans: a figure where the figure is free to copy, the manual's own words
# for building it, word for word, and the page. A word pdftotext joined where
# the page broke it at a hyphen ("field-/expedient") gets its hyphen back, as
# the page prints it; nothing else is touched, slips included ("cable tie,
# The insulation").
#
# The AUXFOG's ground-plane drawing and photograph and its coaxial-sleeve
# photograph (pp. D-2, D-3, D-5) are marked "Courtesy of Tom Brown / N4TAB":
# his, not the government's, so they are not copied here; the card says
# where they are and links to them. Its coaxial-sleeve drawing on p. D-4
# carries no such mark.
#
# `kinds` are the Lab's antenna types a plan is shown with, and `mhz` the
# range it is for - the AUXFOG's ground plane is cut for 2 m and 70 cm and is
# no help on 40 m.
PLANS = [
    {"key": "atp-dipole", "book": ATP,
     "title": "The improvised half-wave dipole, and the center-fed half-wave on wood",
     "kinds": ["dipole", "invertedv", "bowtie"], "mhz": (1.0, 1000.0),
     "figures": [
         {"file": "atp-e11-dipole.png", "name": "Figure E-11. Half-wave dipole (doublet) antenna",
          "page": 96, "pdf_page": 106},
         {"file": "atp-e12-center-fed.png", "name": "Figure E-12. Center-fed half-wave antenna",
          "page": 97, "pdf_page": 107}],
     "words": [
         "E-49. The dipole (doublet) antenna, also considered a center fed antenna, is a half-wave antenna "
         "consisting of two-quarter wavelength sections on each side of the center. Figure E-11 is an example of "
         "the improvised dipole (doublet) antenna used with VHF and UHF radios.",
         "E-51. Operators may use pieces of wood to support center-fed half-wave frequency modulation antennas. "
         "These antennas rotate to any position to obtain the best performance. If the antenna is vertical, the "
         "transmission line should be positioned horizontally from the antenna or a distance equal to at least "
         "one-half of the antenna's length, before dropping down to the radio set. Figure E-12 on page 97 shows "
         "examples of horizontal (A) and vertical (B) center-fed half-wave antennas."],
     "page": 96, "pdf_page": 106},
    {"key": "atp-vertical", "book": ATP,
     "title": "The improvised vertical half-wave, hung from a tree",
     "kinds": ["quarter", "groundplane", "jpole", "fiveeighth"], "mhz": (30.0, 1000.0),
     "figures": [
         {"file": "atp-e13-vertical.png", "name": "Figure E-13. Improvised vertical half-wave antennas",
          "page": 98, "pdf_page": 108}],
     "words": [
         "E-52. Figure E-13 on page 98 is an example of an improvised vertical half-wave antenna. VHF and UHF "
         "radios primarily use this technique. An improvised vertical half-wave antenna is effective in heavily "
         "wooded areas to increase the range of portable radios. The top guy wire can connect to a limb or pass "
         "over the limb and connect to the tree trunk or a stake."],
     "page": 97, "pdf_page": 107},
    {"key": "atp-insulators", "book": ATP,
     "title": "Insulators from what is to hand",
     "kinds": ["dipole", "invertedv", "bowtie", "efhw", "loop", "tefv", "termsloper"], "mhz": (1.0, 1000.0),
     "figures": [
         {"file": "atp-h19-insulators.png", "name": "Figure H-19. Examples of field expedient antenna insulator",
          "page": 145, "pdf_page": 155}],
     "words": [
         "H-160. Operators may use many common items as expedient field insulators. Plastic or glass, including "
         "plastic spoons, buttons, bottlenecks, and plastic bags are the best insulator. Wood and rope also act as "
         "insulators, though they are less effective than plastic or glass. The antenna wire should only touch the "
         "antenna terminal and be electronically isolated from all other objects other than the supporting "
         "insulator. Figure H-19 on page 145 shows examples of field expedient antenna insulators."],
     "page": 144, "pdf_page": 154},
    {"key": "auxfog-groundplane", "book": AUXFOG,
     "title": "A ground plane from a length of coax, for 2 m or 70 cm",
     "kinds": ["groundplane", "quarter"], "mhz": (100.0, 500.0),
     "figures": [],
     "elsewhere": "The manual's drawing and photograph of it, on pp. D-2 and D-3, are marked \"Courtesy of "
                  "Tom Brown / N4TAB\" and are not copied here - open the page to see them.",
     "elsewhere_pdf_page": 94,
     "words": [
         "Field expedient antennas for VHF/UHF use are typically quarter-wavelength vertically polarized and "
         "consist of a radiating element and a counterpoise. These include a simple VHF \"ground plane\" vertical, "
         "using 19.5 inches of the center conductor of the coaxial cable as the radiator and four 19 inch wires "
         "attached to the coaxial cable shield as the counterpoise (ground plane) (see Figure 1 and Figure 2). The "
         "counterpoise wires can be fitted to an SO-239 connector if available, or may be simply wrapped around "
         "the braid and soldered. Form a loop or hook at the top of the center conductor for hanging the antenna. "
         "Counterpoise wires should be bent downward such that they form a 45 degree angle with respect to the "
         "horizontal plane.",
         "A similar UHF antenna can be constructed by cutting the vertical element to 9 inches, making the "
         "counterpoise wires 8.5 inches in length and also bent downward at a 45 degree angle."],
     "slips": ["The text gives a 19.5 inch radiator over 19 inch counterpoise wires; the length table in its "
               "Figure 1, on p. D-2, gives 19 inches for all elements at 145 MHz."],
     "page": "D-1", "pdf_page": 93},
    {"key": "auxfog-sleeve", "book": AUXFOG,
     "title": "A coaxial sleeve antenna, the feedline's own braid turned back as the counterpoise",
     "kinds": ["jpole", "groundplane"], "mhz": (100.0, 500.0),
     "figures": [
         {"file": "auxfog-d4-coax-sleeve.png", "name": "Figure 3. Coaxial Sleeve Antenna Design",
          "page": "D-4", "pdf_page": 96}],
     "elsewhere": "The manual's photograph of one, on p. D-5, is marked \"Courtesy of Tom Brown / N4TAB\" and is "
                  "not copied here.",
     "elsewhere_pdf_page": 97,
     "words": [
         "Another useful and simple antenna for VHF operation is a coaxial sleeve antenna that uses the center "
         "conductor of the coaxial cable as the radiating element and the shield braid of the coaxial cable as the "
         "counterpoise. In this example, the outer jacket is removed to expose 19.5 inches of the shield braid. "
         "The braid is compressed to expand its diameter and rolled inside-out over the outer jacket, forming a "
         "coaxial sleeve. This sleeve is stretched tightly downward and secured to the outer jacket with tape or a "
         "cable tie, The insulation surrounding the center conductor is trimmed away to expose the bare center "
         "conductor wire. Make a loop or hook at the top of the center conductor for hanging the antenna.",
         "A similar UHF antenna can be constructed by cutting the vertical element to 9 inches and making the "
         "coaxial sleeve 8.5 inches in length."],
     "slips": ["The text exposes 19.5 inches of braid; its Figure 3 labels the braid 22 inches and the center "
               "conductor trimmed to 19."],
     "page": "D-4", "pdf_page": 96},
    {"key": "auxfog-dipole", "book": AUXFOG,
     "title": "Building and trimming a single-band dipole",
     "kinds": ["dipole", "invertedv"], "mhz": (1.0, 30.0),
     "figures": [],
     "words": [
         "Single-band dipoles are among the easiest antennas to build. All you need is some stranded, copper wire "
         "(insulated or non-insulated) and three plastic or ceramic insulators. A 1/2-wavelength dipole is made up "
         "of two pieces of wire, each 1/4-wavelength long.",
         "Calculating the lengths of the 1/2-wavelength wires is simple. Just grab a calculator and perform the "
         "following bit of division:",
         "Length (feet) = 468/frequency (MHz)",
         "Note: The functional difference between insulated and non-insulated wire is that the insulation adds "
         "dielectric loading. This results in the radial being electrically longer by roughly 4%.",
         "You should add about six inches to the results of your calculations. You'll need that length margin to "
         "trim and tune for the lowest SWR. (SWR stands for Standing Wave Ratio). It is measured with a device "
         "known as an SWR meter. Many modern transceivers include SWR meters, or you can purchase them "
         "separately. An ideal SWR is 1:1.",
         "Join the two wires in the center with an insulator, then place insulators at both ends. Solder the "
         "center conductor of your coaxial cable feed line to one side of the center insulator. (It doesn't "
         "matter which side.) Solder the shield braid of your cable to the other side. Connect ropes, nylon "
         "string or whatever to the end insulators and haul your antenna skyward. Get it as high as you can and "
         "as straight as possible. Don't hesitate to bend your dipole if that's what it takes to make it fit.",
         "Once your dipole is safely airborne, power up your transmitter and check the SWR at many points "
         "throughout the band. (It helps if you can plot the results on graph paper.) If you see that the SWR is "
         "getting lower as you move lower in frequency, your antenna is too long. Trim a couple of inches from "
         "each end and try again. On the other hand, if you see that the SWR is getting higher as you go lower in "
         "frequency, your antenna is too short. You'll need to add wire to both ends and make another series of "
         "measurements.",
         "When you've finished trimming your dipole, you'll probably end up with an SWR of 1.5:1 or less at the "
         "center frequency, rising to 2:1 or somewhat higher at either end of the band. Don't expect a 1:1 SWR "
         "across the entire band. By carefully trimming the antenna you can move the low-SWR portion to cover "
         "your favorite frequencies."],
     # The box on the appendix's first page, about the same dipoles: its own page, said as such.
     "aside": {"words": "When installing dipole antennas between two trees, ensure that you leave enough slack to "
                        "account for the trees moving in windy conditions. If the dipole is too tight, the trees "
                        "will not be forgiving.",
               "page": "D-1", "pdf_page": 93},
     "table": {"name": "Suggested Dipole Wire Length (Based on 14 AWG Wire)",
               "columns": ["Frequency", "Non-Insulated Wire (ft)", "Insulated Wire (ft)"],
               "rows": [["1.900 MHz", "246.4", "236.4"], ["3.800 MHz", "123.2", "118.2"],
                        ["3.900 MHz", "120.0", "114.0"], ["5.370 MHz", "87.2", "42.8"],
                        ["7.200 MHz", "65.0", "61.8"], ["14.200 MHz", "33.0", "31.4"]],
               "footnote": "The lengths shown are the overall length. Each leg of the dipole is one half (1/2) "
                           "of the length shown.",
               "page": "D-7", "pdf_page": 99},
     "slips": ["The table's insulated length for 5.370 MHz, 42.8 ft, is half what the rest of the table implies: "
               "about 4% under the 87.2 ft bare length would be near 83.8 ft."],
     "page": "D-6", "pdf_page": 98},
]


def _link(book, pdf_page):
    """The reader's link to this page of the book, or None when the book is not
    in this unit's Library - a citation still, without a link to a 404."""
    try:
        if library.book(book["file"]) is not None:
            return f"/library/read/{book['file']}?page={pdf_page}"
    except OSError as exc:
        log.warning("could not look for %s on the shelf: %s", book["file"], exc)
    return None


def plans_for(kind, mhz):
    """The manuals' plans for this antenna at this frequency, ready to show:
    the figures that are free to copy, the manual's words, any slip in them,
    and the links that open the book at each page."""
    try:
        f = float(mhz)
    except (TypeError, ValueError):
        return []
    out = []
    for plan in PLANS:
        lo, hi = plan["mhz"]
        if kind not in plan["kinds"] or not lo <= f <= hi:
            continue
        book = plan["book"]
        card = {"key": plan["key"], "title": plan["title"], "book": book["short"], "book_title": book["title"],
                "edition": book["edition"], "page": plan["page"], "link": _link(book, plan["pdf_page"]),
                "words": list(plan["words"]), "slips": list(plan.get("slips", [])),
                "figures": [dict(fig, src="/static/manuals/" + fig["file"], link=_link(book, fig["pdf_page"]))
                            for fig in plan["figures"]]}
        if plan.get("elsewhere"):
            card["elsewhere"] = plan["elsewhere"]
            card["elsewhere_link"] = _link(book, plan["elsewhere_pdf_page"])
        if plan.get("table"):
            card["table"] = dict(plan["table"], link=_link(book, plan["table"]["pdf_page"]))
        if plan.get("aside"):
            card["aside"] = dict(plan["aside"], link=_link(book, plan["aside"]["pdf_page"]))
        out.append(card)
    return out

#!/usr/bin/env python3
"""Checks for the operator's own licence papers: kept for the account that
handed them over and shown to nobody else, read for the callsign and the
dates where the file has text, and laid beside the FCC record.

    python3 tests/test_papers.py

Needs reportlab (to make a licence-shaped PDF) and poppler (to read it), as
the Library does.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import callsign, library, papers  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def licence_pdf(call, granted, expires):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "FEDERAL COMMUNICATIONS COMMISSION")
    c.drawString(72, 700, f"Call Sign: {call}   Grant Date: {granted}   Expiration Date: {expires}")
    c.showPage()
    c.drawString(72, 720, f"Wallet copy - {call}")
    c.save()
    return buf.getvalue()


def main():
    if not library.tool("pdftotext"):
        print("poppler is not here; nothing to check")
        return 0
    # The FCC record, without the network.
    callsign.lookup = lambda call, refresh=False: {
        "callsign": "KC9SP", "found": True, "license_class": "General", "expires": "05/14/2031",
        "granted": "05/14/2021", "status": callsign.status_for(callsign._parse_date("05/14/2031")),
        "source": "test"}
    from elmer.app import app
    cl = app.test_client()
    cl.post("/api/settings", json={"callsign": "KC9SP"})

    print("\n-- kept, and read --")
    r = cl.post("/api/papers/add", data={"kind": "amateur", "file": (io.BytesIO(licence_pdf("KC9SP", "05-14-2021", "05-14-2031")), "l.pdf")},
                content_type="multipart/form-data")
    d = r.get_json()
    check("the licence is kept", (r.status_code, d["message"]), (200, "Amateur licence kept"))
    held = d["held"][0]
    check("  the paper's callsign and dates read off it", (held["says"]["calls"], held["says"]["granted"], held["says"]["expires"]),
          (["KC9SP"], "2021-05-14", "2031-05-14"))
    check("  two pages, the wallet copy the second", held["pages"], 2)
    check("  laid beside the FCC record, which it agrees with", (held["record"]["callsign"], held["agrees"]), ("KC9SP", True))
    r = cl.post("/api/papers/add", data={"kind": "gmrs", "file": (io.BytesIO(b"hello there"), "x.pdf")}, content_type="multipart/form-data")
    check("something that is not a PDF is refused", r.status_code, 400)
    r = cl.post("/api/papers/add", data={"kind": "passport", "file": (io.BytesIO(licence_pdf("KC9SP", "1", "2")), "x.pdf")}, content_type="multipart/form-data")
    check("  and so is a kind ELMER does not keep", r.status_code, 400)

    print("\n-- shown back --")
    check("the page", cl.get("/papers/amateur").status_code, 200)
    check("  the file", cl.get("/papers/file/amateur").status_code, 200)
    if library.can_draw_pages():
        check("  the pages, drawn", (cl.get("/papers/page/amateur/1.png").status_code, cl.get("/papers/page/amateur/2.png").status_code), (200, 200))
        check("  and not a third", cl.get("/papers/page/amateur/3.png").status_code, 404)
    check("the Library carries the card", "Your licences" in cl.get("/library").get_data(as_text=True), True)
    check("nothing of it on the shelf", library.shelf(), [])

    print("\n-- theirs alone --")
    r = cl.post("/api/users/add", json={"name": "Second"})
    check("a second person joins the unit", r.status_code, 200)
    check("  and sees no papers", cl.get("/api/papers").get_json()["held"], [])
    check("  nor the page, nor the file, nor a page image",
          (cl.get("/papers/amateur").status_code, cl.get("/papers/file/amateur").status_code, cl.get("/papers/page/amateur/1.png").status_code),
          (404, 404, 404))

    print("\n-- the record disagreeing --")
    callsign.lookup = lambda call, refresh=False: {
        "callsign": "KC9SP", "found": True, "license_class": "General", "expires": "05/14/2029",
        "granted": "05/14/2019", "status": callsign.status_for(callsign._parse_date("05/14/2029")), "source": "test"}
    cl.post("/api/users/switch", json={"id": 1})
    cl.post("/api/settings", json={"callsign": "KC9SP"})
    held = cl.get("/api/papers").get_json()["held"][0]
    check("a paper that says a different date from the record is said not to agree", held["agrees"], False)

    print("\n-- removed --")
    r = cl.post("/api/papers/remove", json={"kind": "amateur"})
    check("gone on request", (r.status_code, r.get_json()["held"]), (200, []))
    check("  the folder is empty", list(papers.folder(1).glob("*.pdf")), [])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

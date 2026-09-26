#!/usr/bin/env python3
"""Checks for the wall: a person's certificates hang from their own account,
sized once, captioned, shown to the table under their call, taken down only
by them, and never carried by the program.

    python3 tests/test_awards.py
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import awards  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def picture(w=1600, h=1200, mode="RGBA"):
    from PIL import Image
    buf = io.BytesIO()
    Image.new(mode, (w, h), (200, 180, 120, 255) if mode == "RGBA" else (200, 180, 120)).save(buf, "PNG")
    return buf.getvalue()


def main():
    from PIL import Image
    from elmer.app import app
    c = app.test_client()

    print("\n-- hung --")
    r = c.post("/api/awards/add", data={"file": (io.BytesIO(picture()), "eWAC.png"), "title": "eWAC · Worked All Continents",
                                        "detail": "six continents", "issued": "eQSL.cc, 16 August 2022", "number": "477016"},
               content_type="multipart/form-data")
    d = r.get_json()
    check("a certificate hangs, named from its title", (r.status_code, d["name"]), (200, "ewac-worked-all-continents.jpg"))
    a = d["wall"][0]
    check("  with its caption", (a["title"], a["detail"], a["issued"], a["number"]), ("eWAC · Worked All Continents", "six continents", "eQSL.cc, 16 August 2022", "477016"))
    r = c.get(a["url"])
    check("  sized to the wall, as a JPEG, on white", (r.status_code, r.mimetype, Image.open(io.BytesIO(r.data)).size), (200, "image/jpeg", (1400, 1050)))
    r = c.post("/api/awards/add", data={"file": (io.BytesIO(picture()), "eWAC.png"), "title": "eWAC · Worked All Continents"}, content_type="multipart/form-data")
    check("a second with the same title hangs beside it, not over it", r.get_json()["name"], "ewac-worked-all-continents-2.jpg")
    r = c.post("/api/awards/add", data={"file": (io.BytesIO(b"not a picture"), "x.png")}, content_type="multipart/form-data")
    check("something that is not a picture is refused", r.status_code, 400)
    r = c.post("/api/awards/add", data={"file": (io.BytesIO(picture(800, 600, "RGB")), "small.png")}, content_type="multipart/form-data")
    check("a small picture is hung as it is, named from its file", (r.status_code, r.get_json()["name"]), (200, "small.jpg"))
    r = c.post("/api/awards/caption", json={"name": "small.jpg", "title": "First contact", "issued": "the club"})
    check("  and captioned afterwards", next(x["title"] for x in r.get_json()["wall"] if x["name"] == "small.jpg"), "First contact")

    print("\n-- in the pro shop, under the person's call --")
    c.post("/api/settings", json={"callsign": "KC9SP"})
    p = c.get("/api/golf/proshop").get_json()
    check("the wall is theirs", (p["whose"], len(p["wall"])), ("KC9SP", 3))

    print("\n-- another person at the table --")
    c.post("/api/users/add", json={"name": "Second", "shared": False})
    check("has a wall of their own, empty", c.get("/api/awards").get_json()["wall"], [])
    check("  the pro shop shows theirs, not the first person's", len(c.get("/api/golf/proshop").get_json()["wall"]), 0)
    check("  may look at the first person's certificate - a wall is for looking at", c.get(a["url"]).status_code, 200)
    check("  but cannot take it down", c.post("/api/awards/remove", json={"name": a["name"]}).status_code, 404)

    print("\n-- in the lounge --")
    c.post("/api/users/switch", json={"id": 1})
    html = c.get("/lounge").get_data(as_text=True)
    # Against the list, not a number: the room's picture was replaced on
    # 22 September and its frames measured again, and a count written into
    # this test failed for a week without anything being wrong.
    from elmer.app import LOUNGE_FRAMES, LOUNGE_SMALL
    check("the lounge renders, with a frame for every plate in the picture",
          (html.count('class="lg-frame"'), html.count('class="lg-small"')), (len(LOUNGE_FRAMES), len(LOUNGE_SMALL)))
    check("  and the picture has frames to hang things in", (len(LOUNGE_FRAMES) > 0, len(LOUNGE_SMALL) > 0), (True, True))
    check("  and the room itself", "golf/lounge.jpg" in html, True)
    c.post("/api/users/switch", json={"id": 2})

    print("\n-- taken down --")
    c.post("/api/users/switch", json={"id": 1})
    r = c.post("/api/awards/remove", json={"name": a["name"]})
    check("by its owner", (r.status_code, len(r.get_json()["wall"])), (200, 2))
    check("  and the picture is gone", c.get(a["url"]).status_code, 404)
    import subprocess
    tracked = subprocess.run(["git", "ls-files", "artwork/awards", "elmer/static/golf/awards", "data/awards", "data/awards.json"],
                             cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True).stdout.split()
    check("the program carries nobody's wall", tracked, [])

    print("\n-- ELMER's own badges, printed for the wall --")
    from elmer import db, game
    c.post("/api/users/switch", json={"id": 1})
    r = c.post("/api/awards/print", json={"code": "cw_whole"})
    check("a badge not held is not printed", (r.status_code, r.get_json()["ok"]), (409, False))
    r = c.post("/api/awards/print", json={"code": "nope"})
    check("  nor one that is not a badge", r.status_code, 404)
    dbc = db.connect()
    dbc.user_id = 1
    game.award(dbc, ["cw_first", "first_light"])
    dbc.commit()
    mine = c.get("/api/awards/mine").get_json()
    check("the shelf lists what is held, in the list's order", [a["name"] for a in mine["earned"]], ["First Light", "First Dit"])
    check("  and how many are left", mine["more"], len(game.ACHIEVEMENTS) - 2)
    r = c.post("/api/awards/print", json={"code": "cw_first"})
    d = r.get_json()
    check("a badge held is printed to the shelf", (r.status_code, d["ok"], d["name"], d["title"]), (200, True, "award-cw_first.pdf", "Award - First Dit"))
    pdf = c.get(d["pdf"])
    check("  and the page opens inline as a PDF", (pdf.status_code, pdf.mimetype, pdf.data[:4]), (200, "application/pdf", b"%PDF"))
    r = c.get("/library")
    check("the Library's bottom shelf shows the plaque", (r.status_code, b"First Dit" in r.data, b"awardcard.js" in r.data), (200, True, True))
    r = c.get("/lounge")
    check("  and so does the Lounge", (r.status_code, b"First Dit" in r.data), (200, True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

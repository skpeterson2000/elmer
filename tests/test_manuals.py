#!/usr/bin/env python3
"""The manuals' tables are the manuals', row for row, and the Lab reads them.

    python3 tests/test_manuals.py

elmer/manuals.py copies the pertinent tables out of the books on the shelf so
the pages that use them can show the row that applies without sending
anybody into a 160-page PDF. What is held here:

  - every row of ATP 6-02.53's Table E-1 is on the page the module says it
    is on, in the PDF exactly as the Army serves it - read with pdftotext,
    whose text layer is good enough to find each number though not to pair
    them (it lays the angle column out apart from the distances, which is
    why the rows were copied off the rendered page);
  - an angle the table prints gives that row, one between gives the rows
    either side and nothing made up between them, and an angle that is not
    an angle gives nothing;
  - the citation opens the book at the table's page when the book is here,
    and is still a citation, with no link, when it is not;
  - the Lab's take-off angle carries the table's row.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402
from elmer import manuals  # noqa: E402

FAILS = []
SHIPPED = ROOT / "data" / "shelf"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def on_the_page():
    print("-- Table E-1 is on page 87 of the ATP, every number of it --")
    t = manuals.TAKEOFF_DISTANCE
    pdf = SHIPPED / t["book"]["file"]
    check("the ATP ships", pdf.exists(), True)
    check("pdftotext is on this machine", bool(shutil.which("pdftotext")), True)
    if not pdf.exists() or not shutil.which("pdftotext"):
        return
    text = subprocess.run(["pdftotext", "-f", str(t["pdf_page"]), "-l", str(t["pdf_page"]), "-layout",
                           str(pdf), "-"], capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout
    check("the PDF's page carries the table's name", t["name"] in text, True)
    check("  and its printed page number", f"{t['page']}" in text.split("\n")[-3:][0] + text[-200:], True)
    missing = [n for r in t["rows"] for n in r[1:] if f"{n:,}" not in text]
    check("every distance in the module is printed on that page", missing, [])
    check("fifteen rows, 0 to 90 degrees", [r[0] for r in t["rows"]],
          [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90])
    check("the 70 and 80 degree rows, which sit apart from their angles in the text layer",
          [r for r in t["rows"] if r[0] in (70, 80)], [(70, 153, 95, 290, 180), (80, 80, 50, 145, 90)])


def v_apex_on_the_page():
    print("\n-- Table E-3, the V's apex angle by leg length, is on page 91 --")
    t = manuals.V_APEX
    pdf = SHIPPED / t["book"]["file"]
    if not pdf.exists() or not shutil.which("pdftotext"):
        check("the ATP and pdftotext are here", False, True)
        return
    text = subprocess.run(["pdftotext", "-f", str(t["pdf_page"]), "-l", str(t["pdf_page"]), str(pdf), "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    check("the PDF's page carries the table's name", t["name"] in text, True)
    # The text layer prints the table as its two rows, lengths then angles.
    check("its lengths, in order", "Antenna Length (Wavelength) 1 2 3 4 6 8 10" in " ".join(text.split()), True)
    check("its angles, in order", "Optimum Apex Angle (Degrees) 90 70 58 50 40 35 33" in " ".join(text.split()), True)
    check("the module's rows are those", [list(r) for r in t["rows"]],
          [[1, 90], [2, 70], [3, 58], [4, 50], [6, 40], [8, 35], [10, 33]])
    check("and E-34, quoted, is on the same page", _squash(t["rule"]) in _squash(text), True)


def lookups():
    print("\n-- a row where the table prints one, the two either side where it does not --")
    at25 = manuals.takeoff_distance(25)
    check("25 degrees is its own row", (at25["exact"], at25["rows"][0]["day_km"], at25["rows"][0]["night_km"]),
          (True, 966, 1610))
    between = manuals.takeoff_distance(55)
    check("55 degrees gives the 50 and 60 rows, nothing between",
          ([r["deg"] for r in between["rows"]], between["exact"]), ([50, 60], False))
    check("an angle off the ends is not an angle", (manuals.takeoff_distance(-3), manuals.takeoff_distance(95)),
          (None, None))
    check("  nor is a word", manuals.takeoff_distance("high"), None)
    c = at25["cite"]
    check("the citation names the book, the table and the page",
          (c["book"], c["table"].split(".")[0], c["page"]), ("ATP 6-02.53", "Table E-1", 87))
    # _isolate points the shipped shelf at an empty directory, so the book is
    # not here: the citation stands without a link rather than linking to a 404.
    check("  with no link when the book is not on this unit's shelf", c["link"], None)
    page = manuals.for_page()["takeoff_distance"]
    check("the page is handed all fifteen rows and the citation", (len(page["rows"]), page["cite"]["page"]), (15, 87))


DRIVE = """
new Promise(async resolve => { try {
  const nap = ms => new Promise(x => setTimeout(x, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof calcAnt === 'function' && window.MANUAL_TABLES, 15000);
  const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input')); };
  set('an-type', 'dipole'); await nap(300);
  set('an-f', '14.2'); set('an-h', '35'); await nap(600);
  const note = () => (document.querySelector('.manual-note') || {}).textContent || '';
  await until(() => note().includes('Table E-1'), 8000);
  const first = note();
  set('an-h', '20'); await nap(600);
  resolve(JSON.stringify({tables: !!window.MANUAL_TABLES.takeoff_distance, at35: first, at20: note()}));
} catch (e) { resolve(JSON.stringify({error: String(e)})); } })
"""


def in_the_lab():
    print("\n-- the Lab's take-off angle carries the table's row --")
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    serve = ("import sys; sys.path.insert(0, %r)\nfrom elmer import app as appmod\n"
             "appmod.app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port))
    server = subprocess.Popen([sys.executable, "-c", serve], env=dict(os.environ),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab", DRIVE, width=1200, height=1600,
                                           settle=1.0, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    if got.get("error"):
        print("  page:", got["error"])
    check("the page is handed the table", got.get("tables"), True)
    # A 20 m dipole 35 ft up is half a wave up: its lobe is near 30 degrees.
    at35 = got.get("at35", "")
    check("a 20 m dipole at 35 ft reads the 30 degree row, by day and by night, in the operator's unit",
          ("30" in at35 and (("725 km" in at35 and "1,328 km" in at35) or ("450 mi" in at35 and "825 mi" in at35))),
          True)
    check("  and says where it is from", "ATP 6-02.53, Table E-1, p. 87" in got.get("at35", ""), True)
    check("lowered to 20 ft the lobe rises and the row follows it", got.get("at20") != got.get("at35")
          and "Table E-1" in got.get("at20", ""), True)


FOOTER = re.compile(r"^(AUXFOG|D-\d+|\d+|ATP 6-02\.53|31 July 2025|Appendix [A-Z]|"
                    r"High Frequency Radio Networks|Antenna Selection and Techniques)$")


def _page_text(pdf, n):
    """The page's words without its running head and foot, so a paragraph
    that runs over the page break reads as the one paragraph it is."""
    text = subprocess.run(["pdftotext", "-f", str(n), "-l", str(n), str(pdf), "-"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout
    return "\n".join(line for line in text.splitlines() if not FOOTER.match(line.strip()))


def _squash(text):
    """Letters and digits only: pdftotext joins a word broken at a hyphen
    without its hyphen and breaks lines where the page does, and neither is
    a difference in what the manual says."""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def plans():
    print("\n-- every plan's words are the manual's, on the page it names --")
    have = shutil.which("pdftotext")
    for plan in manuals.PLANS:
        pdf = SHIPPED / plan["book"]["file"]
        if not have or not pdf.exists():
            check(f"{plan['key']}: the book and pdftotext are here", False, True)
            continue
        # a plan's words may run onto the next page, as the AUXFOG dipole's do
        pages = _squash(_page_text(pdf, plan["pdf_page"]) + _page_text(pdf, plan["pdf_page"] + 1))
        astray = [w[:50] for w in plan["words"] if _squash(w) not in pages]
        check(f"{plan['key']}: every paragraph is on p. {plan['page']} as quoted", astray, [])
        for fig in plan["figures"]:
            check(f"  its {fig['name'].split('.')[0]} ships", (ROOT / "elmer" / "static" / "manuals" / fig["file"]).exists(),
                  True)
            check(f"  and its name is printed on p. {fig['page']}",
                  _squash(fig["name"]) in _squash(_page_text(pdf, fig["pdf_page"])), True)
        if plan.get("aside"):
            a = plan["aside"]
            check(f"  its aside is on p. {a['page']}, the page it names",
                  _squash(a["words"]) in _squash(_page_text(pdf, a["pdf_page"])), True)
        if plan.get("table"):
            t = plan["table"]
            text = _page_text(pdf, t["pdf_page"])
            check(f"  its table's every figure is on p. {t['page']}",
                  [c for r in t["rows"] for c in r if c not in text], [])
    shipped = sorted(p.name for p in (ROOT / "elmer" / "static" / "manuals").iterdir())
    used = sorted(f["file"] for p in manuals.PLANS for f in p["figures"])
    check("every figure shipped is one a plan shows, and no other", shipped, used)
    # N4TAB's drawing and photographs are his: none of their pages is copied.
    n4tab = {94, 95, 97}
    check("nothing is copied from the AUXFOG pages marked Courtesy of Tom Brown / N4TAB",
          [f["file"] for p in manuals.PLANS if p["book"] is manuals.AUXFOG for f in p["figures"]
           if f["pdf_page"] in n4tab], [])
    check("  and the cards that would want them say where they are",
          all("N4TAB" in p.get("elsewhere", "") for p in manuals.PLANS
              if p["key"] in ("auxfog-groundplane", "auxfog-sleeve")), True)

    print("\n-- the right plans for the antenna and the band --")
    keys = lambda kind, mhz: [c["key"] for c in manuals.plans_for(kind, mhz)]  # noqa: E731
    check("a 40 m dipole: the ATP's dipole and insulators, the AUXFOG's dipole",
          keys("dipole", 7.2), ["atp-dipole", "atp-insulators", "auxfog-dipole"])
    check("a 2 m ground plane: the ATP's tree vertical, the AUXFOG's ground plane and sleeve",
          keys("groundplane", 146.52), ["atp-vertical", "auxfog-groundplane", "auxfog-sleeve"])
    check("a 40 m quarter wave is not handed a 2 m ground plane", keys("quarter", 7.15), [])
    check("a 2 m dipole is not handed the HF dipole's trimming table",
          "auxfog-dipole" in keys("dipole", 146.52), False)
    from elmer import app as appmod
    client = appmod.app.test_client()
    client.set_cookie("elmer_user", "1")
    got = client.get("/api/antenna-advice?mhz=7.2&kind=dipole&use=regional").get_json() or {}
    check("the Lab's advice carries the plans for the antenna it advises on",
          [c["key"] for c in got.get("plans") or []], ["atp-dipole", "atp-insulators", "auxfog-dipole"])
    check("the AUXFOG's 5.370 MHz slip is printed as printed, and said",
          (["5.370 MHz", "87.2", "42.8"] in manuals.PLANS[-1]["table"]["rows"],
           any("42.8" in s for s in manuals.PLANS[-1]["slips"])), (True, True))


def main():
    on_the_page()
    v_apex_on_the_page()
    lookups()
    plans()
    in_the_lab()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

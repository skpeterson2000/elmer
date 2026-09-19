#!/usr/bin/env python3
"""A page between two chapters has to be reachable, and look it.

    python3 tests/test_reader_turn.py

Reported while reading the guide: Calibrate my forecast opens on page 13, the
next chapter is on page 15, and nothing appeared to open page 14. Page 14 was
there and rendered perfectly well. The way to it was invisible.

The reader's page turns sat at zero opacity and appeared on hover, so the
only means of moving through a book was hidden from anybody not already
sweeping a mouse across it - and the kiosk is a touchscreen, where there is
no hover at all and they could never appear. What was left was the chapter
list, which by its nature lists chapter openings and so steps straight over
every page in between.

They rest visible now. This checks that they do, that they work, and that the
page in between is real, because an arrow that shows a blank is no better
than one nobody can see.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402
from elmer import db, library, manual  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


check("chromium is on this machine", bool(_browser.available()), True)
if not _browser.available():
    print("\nFAILED: this test needs chromium")
    sys.exit(1)

# The guide, on the shelf and read, so there is a book with chapters in it.
placed = manual.place(db.connect())
check("the guide is on the shelf", placed["did"] in ("built", "kept"), True)
chapters = library.outline(manual.NAME)
check("  with chapters", len(chapters) > 20, True)

# A page that no chapter starts on: the one the reader could not reach.
starts = {c["page"] for c in chapters}
between = next((p for p in range(2, 30) if p not in starts and (p - 1) in starts), None)
check("  and a page between two chapter openings", between is not None, True)

PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\n"
     "from elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

URL = (f"http://127.0.0.1:{PORT}/library/read/{manual.NAME}?page={(between or 2) - 1}")

JS = r"""(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const next = $('next'), prev = $('prev');
  const out = {
    opened_on: $('pg') ? $('pg').value : null,
    next_rests_visible: next ? +getComputedStyle(next).opacity > 0.1 : null,
    prev_rests_visible: prev ? +getComputedStyle(prev).opacity > 0.1 : null,
  };
  next.click();
  await sleep(1500);
  out.page_after_click = $('pg').value;
  out.image_after_click = $('pageimg').src.split('/').pop();
  out.image_loaded = $('pageimg').naturalWidth > 100;
  return JSON.stringify(out);
})()"""


def main():
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/library", timeout=1).read()
            break
        except Exception:
            time.sleep(0.2)

    print("\n-- the way through a book is visible --")
    got = json.loads(_browser.evaluate(URL, JS, settle=3.0))
    check("the reader opens where it was pointed", got["opened_on"], str(between - 1))
    check("  and the page turns can be seen without hovering over them",
          (got["next_rests_visible"], got["prev_rests_visible"]), (True, True))

    print("\n-- and it reaches the page no chapter starts on --")
    check(f"a turn from {between - 1} lands on {between}", got["page_after_click"], str(between))
    check("  and that page is a real one, drawn", got["image_loaded"], True)
    check("  from the book, not a placeholder", got["image_after_click"], f"{between}.png")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


try:
    code = main()
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
sys.exit(code)

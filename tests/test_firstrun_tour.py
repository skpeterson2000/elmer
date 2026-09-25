#!/usr/bin/env python3
"""The first-run tour, while the Commission's file comes down.

    python3 tests/test_firstrun_tour.py

The FCC's amateur file used to be started by somebody typing their callsign,
which put a couple of hundred megabytes on the critical path of the one
question a new licensee most wants answered - so the answer came from
callook.info instead, and on a night when callook was rebuilding its own copy
the program reported no FCC record for a license with nine years left on it.

The file is fetched with the program now. That leaves a few minutes on a fresh
unit where it is on its way, and this is what fills them: a pass through what
the program does, in its own screenshots, with the real download underneath.
The bar is the bytes and then the rows; where the server sends no length it
says so rather than inventing a percentage. It is skippable at every moment.

Checked here: it is shown to a unit that is new and still waiting and to
nobody else, the slides advance and can be steered, the progress read is the
real one, and when the file lands the card says so.
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
from elmer import uls  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\nwho sees it")
from elmer import app as appmod  # noqa: E402

client = appmod.app.test_client()
local = {"REMOTE_ADDR": "127.0.0.1"}
page = client.get("/", environ_base=local).get_data(as_text=True)
check("a new unit with no FCC file yet is shown the tour", 'id="firstrun"' in page, True)

was_state = uls.state
uls.state = lambda: {"amateur": {"have": {"rows": 1602938, "dated": "2026-09-20"},
                                 "fetching": False, "file": "l_amat.zip", "progress": None}}
try:
    page = client.get("/", environ_base=local).get_data(as_text=True)
    check("  a unit that already has the file is not", 'id="firstrun"' in page, False)
    check("  and the script is not loaded either", "firstrun.js" in page, False)
finally:
    uls.state = was_state

print("\nthe progress read, which is the real one")
check("nothing running, nothing said", uls.progress("amateur"), None)
uls._note("amateur", phase="downloading", bytes=3 << 20, total=24 << 20, rows=0, label="amateur")
got = uls.progress("amateur")
check("mid-download it carries the bytes and the total",
      (got["phase"], got["bytes"], got["total"]), ("downloading", 3 << 20, 24 << 20))
uls._note("amateur", phase="reading", rows=845000)
check("then the rows as they are read",
      (uls.progress("amateur")["phase"], uls.progress("amateur")["rows"]), ("reading", 845000))
check("and state() carries it to the page", "progress" in uls.state()["amateur"], True)
uls._progress.pop("amateur", None)

check("\nchromium is on this machine", bool(_browser.available()), True)
if not _browser.available():
    print("\nFAILED: this test needs chromium")
    sys.exit(1)

PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

JS = r"""(async () => {
  const out = {errors: []};
  window.addEventListener('error', e => out.errors.push(String(e.message)));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const box = $('firstrun');
  out.shown = !!box && !box.hidden;
  if (!box) return out;
  out.heads = [];
  out.dots = $('fr-dots').querySelectorAll('.fr-dot').length;
  out.first = $('fr-head').textContent;
  out.text = ($('fr-text').textContent || '').length;
  /* The picture is a real one, fetched from the guide. */
  await sleep(1200);
  const img = $('fr-shot');
  out.shot_src = (img.getAttribute('src') || '');
  out.shot_loaded = img.complete && img.naturalWidth > 0;
  /* Steering it: the third dot puts the third slide up. */
  $('fr-dots').querySelectorAll('.fr-dot')[2].click();
  await sleep(300);
  out.steered = $('fr-head').textContent;
  /* The progress line is saying something about the file. */
  await sleep(2200);
  out.note = ($('fr-note').textContent || '').slice(0, 80);
  out.bar = $('fr-bar').style.width;
  /* Skip takes it away and is remembered. */
  $('fr-skip').click();
  await sleep(200);
  out.hidden_after_skip = box.hidden;
  try { out.remembered = localStorage.getItem('elmer.tour.skipped'); } catch (e) { out.remembered = 'blocked'; }
  return out;
})()"""

try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=1).close()
            break
        except Exception:
            time.sleep(0.2)
    else:
        print("\nFAILED: the server did not come up")
        sys.exit(1)

    print("\nthe tour itself, in a browser")
    got = _browser.evaluate(f"http://127.0.0.1:{PORT}/", JS, settle=3.0)
    if isinstance(got, str):
        got = json.loads(got)
    check("no javascript error", got.get("errors"), [])
    check("the card is up", got["shown"], True)
    check("  with a slide on it", bool(got["first"]) and got["text"] > 40, True)
    check("  one dot per slide", got["dots"], 7)
    # Assigning img.src stores the browser's resolved absolute URL, so the
    # path is looked for inside it rather than at the front.
    check("  showing a real screenshot from the guide",
          "/guide/shot/" in got["shot_src"], True)
    check("  which actually loaded", got["shot_loaded"], True)
    check("  and a dot steers it", got["steered"] != got["first"], True)
    check("the line underneath is about the FCC file",
          "FCC" in got["note"] or "Fetching" in got["note"], True)
    check("Skip takes it away", got["hidden_after_skip"], True)
    check("  and is remembered", got["remembered"], "1")
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)

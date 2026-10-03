#!/usr/bin/env python3
"""The CW lamp's full screen says what it is and has something to send.

    python3 tests/test_cw_lamp_full.py

It used to put the bare lamp full screen, and the lamp is dark until
something is sent - so an operator got a black screen with the browser's
"Esc to exit" on it and nothing else. Now the lamp's stage goes full screen
with a bar that says what it is, sends a practice group, follows it
(counting down, sending, sent) and fades while the code goes out.

A headless browser will not go full screen without a real hand on the
mouse, so the page is told the stage is the full-screen element and given
the browser's own fullscreenchange event; the bar's behaviour is what is
held, and a picture is taken with the full-screen styles copied on.
"""
import json
import os
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

FAILS = []
SHOT = os.environ.get("LAMP_SHOT")      # a path, to keep a picture of the bar


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


JS = r"""
(async () => {
  const nap = ms => new Promise(r => setTimeout(r, ms));
  const sel = document.getElementById('cw-output'); sel.value = 'lamp'; sel.dispatchEvent(new Event('change'));
  const stage = document.getElementById('cw-lamp-stage'), lamp = document.getElementById('cw-lamp');
  const out = {};
  // The button asks for the stage, not the bare lamp.
  let asked = null;
  stage.requestFullscreen = () => { asked = 'stage'; return Promise.resolve(); };
  lamp.requestFullscreen = () => { asked = 'lamp'; return Promise.resolve(); };
  document.getElementById('cw-lamp-full').click();
  out.asked = asked;
  // Full screen, as far as the page can tell.
  Object.defineProperty(document, 'fullscreenElement', {configurable: true, get: () => stage});
  document.dispatchEvent(new Event('fullscreenchange'));
  // the full-screen styles, copied onto the stage for the picture and the checks
  const css = document.createElement('style');
  css.textContent = [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } })
    .map(r => r.cssText).filter(t => t.includes('.cw-lamp-stage:fullscreen'))
    .map(t => t.split('.cw-lamp-stage:fullscreen').join('.cw-lamp-stage.gs-fs')).join('\n') +
    '\n.cw-lamp-stage.gs-fs { position: fixed !important; inset: 0; z-index: 9999; }';
  document.head.appendChild(css);
  stage.classList.add('gs-fs');
  await nap(300);
  const shown = id => { const el = document.getElementById(id); return !!el && !el.hidden && el.offsetParent !== null; };
  out.bar = shown('cw-lamp-over');
  out.words = document.getElementById('cw-lamp-words').textContent.replace(/\s+/g, ' ').trim();
  out.idle = {send: shown('cw-lamp-send'), again: shown('cw-lamp-again'), stop: shown('cw-lamp-stop'),
              back: shown('cw-lamp-exit')};
  // Send, and watch it follow - at 25 wpm, so the group is out inside the test's patience.
  settings.wpm = 25; settings.effective = 25;
  document.getElementById('cw-lamp-send').click();
  let saw = new Set(), faded = false, lit = false;
  for (let i = 0; i < 400; i++) {
    await nap(100);
    saw.add(document.getElementById('cw-lamp-words').textContent.slice(0, 20));
    if (stage.classList.contains('sending')) faded = true;
    if (lamp.classList.contains('lit')) lit = true;
    if (i === 15) out.busy = {send: shown('cw-lamp-send'), stop: shown('cw-lamp-stop')};
    if (faded && !sending) break;
  }
  out.lit = lit; out.faded = faded;
  await nap(400);                       // the bar follows on its own tick, every 150 ms
  out.waited = saw.size;
  out.after = {words: document.getElementById('cw-lamp-words').textContent, again: shown('cw-lamp-again'),
               fadedNow: stage.classList.contains('sending')};
  // Back.
  let exited = false;
  document.exitFullscreen = () => { exited = true; return Promise.resolve(); };
  document.getElementById('cw-lamp-exit').click();
  out.back = exited;
  await nap(700);                       // the bar's fade back in, before any picture
  return JSON.stringify(out);
})()
"""


def main():
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        print("\nFAILED: this test needs chromium")
        return 1
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=1).close()
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise SystemExit("the throwaway server never answered")
        got = json.loads(_browser.evaluate("http://127.0.0.1:%d/cw" % port, JS, width=1280, height=800, settle=2.0,
                                           out=SHOT, flags=("--autoplay-policy=no-user-gesture-required",)))
    finally:
        server.terminate()

    print("\n-- full screen takes the stage, and says what it is --")
    check("the button asks for the stage, not the bare lamp", got["asked"], "stage")
    check("the bar shows", got["bar"], True)
    check("  and says the lamp is dark until something is sent", "dark until something is sent" in got["words"], True)
    check("  with Send practice and Back, and nothing to repeat or stop yet",
          got["idle"], {"send": True, "again": False, "stop": False, "back": True})

    print("\n-- it sends, and follows what it is doing --")
    check("while it goes out, Stop instead of Send", got.get("busy"), {"send": False, "stop": True})
    check("the lamp flashes the group", got["lit"], True)
    check("  and the bar fades while it does", got["faded"], True)
    check("sent: it says where to check the copy, offers it again, and is bright again",
          ("Copy practice" in got["after"]["words"], got["after"]["again"], got["after"]["fadedNow"]), (True, True, False))
    check("Back leaves full screen", got["back"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

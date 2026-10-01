#!/usr/bin/env python3
"""Code by light: the lamp, and reading one with a camera.

    python3 tests/test_cw_lamp.py

Morse is a timing, not a sound. A signal lamp sends it between ships in
silence, a prisoner blinked it on film, and a phone's flashlight will send
it across a room. The CW page can now send by sound, by lamp or both, and
read a lamp through the camera. What is held here, in a real browser:

  - lamp only: the lamp flashes once for every dit and dah, and the tone
    stays silent;
  - both: the lamp and the tone together;
  - your own keying lights the lamp while the key is down;
  - the lamp reader decodes a light's coming and going - fed a light
    keying SOS, frame by frame at camera rate, it reads SOS;
  - the lamp panel shows only when the lamp is on, and carries the stories
    of code without a radio, with their sources.
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


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof lampStep === 'function', 10000);
  const out = {};
  const sel = document.getElementById('cw-output');
  out.panelHiddenForSound = document.getElementById('cw-lamp-panel').hidden;
  const pick = v => { sel.value = v; sel.dispatchEvent(new Event('change')); };
  const lamp = document.getElementById('cw-lamp');
  // Watch the lamp and the gain while a word is sent.
  const watch = async (text) => {
    const enc = await (await fetch('/api/cw/encode?wpm=20&text=' + encodeURIComponent(text))).json();
    player.ensure();
    let flashes = 0, was = false, loudest = 0, done = false;
    player.send(enc.groups, enc.timing, null, () => { done = true; });
    const t0 = Date.now();
    while (!done && Date.now() - t0 < 10000) {
      const lit = lamp.classList.contains('lit');
      if (lit && !was) flashes++;
      was = lit;
      loudest = Math.max(loudest, player.gain.gain.value);
      await new Promise(r => setTimeout(r, 4));
    }
    return {flashes: flashes, loudest: loudest,
            elements: enc.groups.reduce((n, w) => n + w.reduce((m, c) => m + c.code.length, 0), 0)};
  };
  pick('lamp');
  out.panelShownForLamp = !document.getElementById('cw-lamp-panel').hidden;
  out.lampOnly = await watch('TEST');
  pick('both');
  out.both = await watch('TEST');
  // The key lights it.
  showMode('key');
  keyStart(); await nap(200);
  out.keyLit = lamp.classList.contains('lit');
  keyEnd(); await nap(50);
  out.keyDark = !lamp.classList.contains('lit');
  // The reader, fed a light keying SOS at 12 wpm, a frame every 33 ms.
  lampReaderReset(0);
  const dit = 100, seq = [];
  const put = (on, ms) => seq.push([on, ms]);
  const letter = code => { [...code].forEach((e, i) => { put(true, e === '.' ? dit : 3 * dit); if (i < code.length - 1) put(false, dit); }); };
  put(false, 600); letter('...'); put(false, 3 * dit); letter('---'); put(false, 3 * dit); letter('...'); put(false, 1500);
  let t = 0;
  for (const [on, ms] of seq) {
    for (let x = 0; x < ms; x += 33) { lampStep(on ? 230 + Math.random() * 10 : 30 + Math.random() * 10, t + x); }
    t += ms;
  }
  camDecoder.flush();
  out.read = camDecoder.text.trim();
  const d = document.querySelector('#cw-lamp-panel details');
  out.stories = d ? d.textContent : '';
  out.links = d ? [...d.querySelectorAll('a')].map(a => a.href) : [];
  resolve(JSON.stringify(out));
})
"""


def main():
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/cw", DRIVE, width=1300, height=1400,
                                           settle=1.5, cookies={"elmer_user": "1"},
                                           flags=("--autoplay-policy=no-user-gesture-required",)) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    print("\n-- the lamp --")
    check("the lamp panel is hidden while sending by sound, and shown for the lamp",
          (got.get("panelHiddenForSound"), got.get("panelShownForLamp")), (True, True))
    lo = got.get("lampOnly") or {}
    check("lamp only: a flash for every dit and dah of TEST", lo.get("flashes"), lo.get("elements"))
    check("  and the tone silent", lo.get("loudest"), 0)
    both = got.get("both") or {}
    check("both: the flashes and the tone together",
          (both.get("flashes") == both.get("elements"), (both.get("loudest") or 0) > 0), (True, True))
    check("your keying lights the lamp while the key is down, and it goes dark after",
          (got.get("keyLit"), got.get("keyDark")), (True, True))
    print("\n-- reading a lamp --")
    check("a light keying SOS, a frame every 33 ms, reads as SOS", got.get("read"), "SOS")
    print("\n-- code without a radio --")
    stories = got.get("stories") or ""
    check("the stories are there: the lamp at sea, Denton, the Tennessee couple, Morse as a voice",
          all(w in stories for w in ("signal lamp", "Denton", "Lebanon, Tennessee", "Gboard")), True)
    check("  with their sources", sum(1 for h in got.get("links") or [] if "newsweek" in h or "wikipedia" in h
                                      or "fox29" in h), 3)


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)

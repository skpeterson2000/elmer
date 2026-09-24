#!/usr/bin/env python3
"""The countdown before copy practice sends, in a real browser.

    python3 tests/test_cw_countdown.py

Pressing Send puts a hand on the mouse, and the copy wants it on the keyboard
or a pencil. Without a moment to get there the first group is lost to the
setup and scored as if it were the ear. So Send counts down - 3, 2, 1, a tick
with each - and only then keys the text. Checked here:

  - the count is shown, in order, and nothing is keyed until it is done;
  - any key starts it at once, and that key is not typed into the copy;
  - Stop during the count calls it off, and nothing is keyed after;
  - a Resend called off in the count was never heard, so it is not counted;
  - 0 on the slider turns it off.

This test requires Chromium and fails - not skips - without it, and asks for
the autoplay policy that lets the audio clock run without a click.
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

FAILS = []
ROOT = Path(__file__).resolve().parents[1]
FLAGS = ("--autoplay-policy=no-user-gesture-required",)


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


check("chromium is on this machine", bool(_browser.available()), True)
if not _browser.available():
    print("\nFAILED: this test needs chromium")
    sys.exit(1)

PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\n"
     "from elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

URL = f"http://127.0.0.1:{PORT}/cw#copy"

# player.send is wrapped so the test knows the moment anything is keyed.
COUNTDOWN_JS = r"""(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const until = async (f, ms) => { for (let i = 0; i < ms / 20; i++) { if (f()) return true; await sleep(20); } return false; };
  const setCount = n => { const s = $('cw-countdown'); s.value = n; s.dispatchEvent(new Event('input')); };
  let keyed = 0;
  const realSend = player.send.bind(player);
  player.send = (...a) => { keyed++; return realSend(...a); };
  const status = () => $('cw-copy-status').textContent;
  const out = {};
  $('cw-qsay').click();                       // no Q keying before each press
  out.default = settings.countdown;
  out.label = $('cw-countdown-v').textContent;

  // Left to run: every number shown, in order, and the text only after.
  const seen = [];
  $('cw-send').click();
  const t0 = performance.now();
  let keyedAt = null;
  while (performance.now() - t0 < 6000) {
    const s = status();
    if (seen[seen.length - 1] !== s) seen.push(s);
    if (keyed && keyedAt === null) keyedAt = performance.now() - t0;
    if (s === 'sending…') break;
    await sleep(20);
  }
  out.run = {seen: seen.filter(s => s && s !=='fetching…'), keyed: keyed, after_ms: Math.round(keyedAt || 0)};
  $('cw-stop').click();
  await sleep(300);

  // Any key: sent at once, and the key kept out of the copy.
  keyed = 0;
  $('cw-send').click();
  await until(() => /start now$/.test(status()), 3000);
  const ev = new KeyboardEvent('keydown', {key: 'a', bubbles: true, cancelable: true});
  $('cw-typed').dispatchEvent(ev);
  await sleep(50);
  out.skip = {keyed: keyed, status: status(), kept: ev.defaultPrevented};
  $('cw-stop').click();
  await sleep(300);

  // Stop in the count: nothing keyed, now or later.
  keyed = 0;
  $('cw-send').click();
  await until(() => /start now$/.test(status()), 3000);
  $('cw-stop').click();
  await sleep(3800);
  out.stop = {keyed: keyed, status: status(), send_back: !$('cw-send').hidden, stop_gone: $('cw-stop').hidden};

  // A Resend called off in the count is not a resend.
  $('cw-repeat').hidden = false;
  const before = copyResends;
  keyed = 0;
  $('cw-repeat').click();
  await until(() => /start now$/.test(status()), 3000);
  $('cw-stop').click();
  await sleep(300);
  out.resend = {before: before, after: copyResends, keyed: keyed};

  // Off.
  setCount(0);
  out.off_label = $('cw-countdown-v').textContent;
  keyed = 0;
  $('cw-send').click();
  await until(() => keyed > 0, 3000);
  out.off = {keyed: keyed, status: status()};
  $('cw-stop').click();
  return JSON.stringify(out);
})()"""


def main():
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/cw", timeout=1).read()
            break
        except Exception:
            time.sleep(0.2)

    got = json.loads(_browser.evaluate(URL, COUNTDOWN_JS, settle=3.0, flags=FLAGS,
                                       cookies={'elmer_user': '1'}))

    print("\n-- Send counts down before it keys anything --")
    check("three seconds unless changed", (got["default"], got["label"]), (3, "3 s"))
    check("each number shown in turn, then the sending",
          got["run"]["seen"], ["3… any key to start now", "2… any key to start now",
                               "1… any key to start now", "sending…"])
    check("  keyed once, and not before the count is done",
          (got["run"]["keyed"], got["run"]["after_ms"] >= 2900), (1, True))

    print("\n-- any key says ready --")
    check("a key in the count sends at once",
          (got["skip"]["keyed"], got["skip"]["status"]), (1, "sending…"))
    check("  and is not typed into the copy", got["skip"]["kept"], True)

    print("\n-- Stop calls it off --")
    check("nothing keyed, then or later", got["stop"]["keyed"], 0)
    check("  and the buttons are put back",
          (got["stop"]["status"], got["stop"]["send_back"], got["stop"]["stop_gone"]),
          ("stopped", True, True))
    check("a Resend called off in the count is not counted",
          (got["resend"]["after"] - got["resend"]["before"], got["resend"]["keyed"]), (0, 0))

    print("\n-- 0 turns it off --")
    check("the slider says off", got["off_label"], "off")
    check("  and Send keys straight away", (got["off"]["keyed"], got["off"]["status"]), (1, "sending…"))

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

#!/usr/bin/env python3
"""Learning a character, at the learner's pace, in a real browser.

    python3 tests/test_cw_learn.py

Two things are checked here, and neither can be checked without a JavaScript
engine and a running audio clock.

The naming. "Name it afterwards" used to put the bare letter on the screen.
Naming a character means saying what it is called - Kilo - which is what the
Today session has always done and what the lesson pane did not.

The waiting. The lesson runner sounds one character and then stops, for as
long as the learner needs. That is the whole point of it: somebody still
comparing what they heard against the shapes above is not on a clock, and a
runner that moved on by itself after a decent interval would be a test of
copying rather than a way of learning to tell two sounds apart. So this
presses Begin, waits well past any plausible interval, and checks that
nothing has moved.

This test requires Chromium and fails - not skips - without it, and it asks
for the autoplay policy that lets an audio clock run without a click: a
headless browser suspends its AudioContext otherwise, and a lesson driven by
the audio clock would never finish its first character.
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
# The audio clock does not run in a headless browser without this, and the
# whole lesson is driven by it.
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

URL = f"http://127.0.0.1:{PORT}/cw#learn"

# The lesson, driven the way a person drives it: the Q-code keying switched
# off so a press is a press, three characters to learn, and a wait after
# Begin that is longer than anything the runner could be waiting on.
LESSON_JS = r"""(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const out = {};
  $('cw-qsay').click();                       // no Q keying before each press
  const slider = $('cw-lesson');
  slider.value = 3; slider.dispatchEvent(new Event('input'));
  out.review = $('cw-lesson-chars').children.length;
  out.review_has_code = !!$('cw-lesson-chars').querySelector('.cw-code i');
  $('cw-learn-begin').click();
  await sleep(2500);
  out.sounded = {count: $('cw-learn-count').textContent,
                 again: !$('cw-learn-again').hidden,
                 got: !$('cw-learn-got').hidden,
                 begin_gone: $('cw-learn-begin').hidden,
                 named_yet: $('cw-teach-word').textContent};
  await sleep(3500);
  out.still = $('cw-learn-count').textContent;
  $('cw-learn-got').click();
  await sleep(500);
  out.named = {letter: $('cw-teach-letter').textContent,
               word: $('cw-teach-word').textContent,
               shown: $('cw-teach-word').classList.contains('show')};
  await sleep(3000);
  out.moved_on = {count: $('cw-learn-count').textContent,
                  waiting: !$('cw-learn-again').hidden};
  $('cw-learn-stop').click();
  await sleep(500);
  out.stopped = {begin_back: !$('cw-learn-begin').hidden,
                 again_gone: $('cw-learn-again').hidden};
  return JSON.stringify(out);
})()"""

# The other way of running the lesson: all of them together, each named as it
# goes by. The word is what is being checked - it is the thing that was
# missing - so the run is watched until a word appears.
TOGETHER_JS = r"""(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  $('cw-qsay').click();
  const slider = $('cw-lesson');
  slider.value = 2; slider.dispatchEvent(new Event('input'));
  $('cw-hear').click();
  for (let i = 0; i < 60; i++) {
    await sleep(250);
    const w = $('cw-teach-word');
    if (w.textContent) return JSON.stringify({word: w.textContent, letter: $('cw-teach-letter').textContent});
  }
  return JSON.stringify({word: '', letter: $('cw-teach-letter').textContent});
})()"""


def main():
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/cw", timeout=1).read()
            break
        except Exception:
            time.sleep(0.2)

    print("\n-- one at a time, and the machine waits --")
    got = json.loads(_browser.evaluate(URL, LESSON_JS, settle=3.0, flags=FLAGS))
    check("the lesson's characters are on the screen to compare against", got["review"], 3)
    check("  drawn as shapes, not written as dots", got["review_has_code"], True)
    check("Begin sounds the first one and hands over the controls",
          (got["sounded"]["count"], got["sounded"]["again"], got["sounded"]["got"],
           got["sounded"]["begin_gone"]), ("1 of 3", True, True, True))
    check("  and does not name it yet - that is what the thinking is for",
          got["sounded"]["named_yet"], "")
    # The heart of it. Nothing moves on its own.
    check("left alone, it is still on the same character", got["still"], "1 of 3")
    check("'I have it' names the character, phonetically",
          (got["named"]["letter"], got["named"]["word"], got["named"]["shown"]),
          ("K", "Kilo", True))
    check("  and only then does the next one sound, and wait in its turn",
          (got["moved_on"]["count"], got["moved_on"]["waiting"]), ("2 of 3", True))
    check("Stop puts the lesson away",
          (got["stopped"]["begin_back"], got["stopped"]["again_gone"]), (True, True))

    print("\n-- run together, each one named as it goes by --")
    got = json.loads(_browser.evaluate(URL, TOGETHER_JS, settle=3.0, flags=FLAGS))
    check("the character is named, not just shown", (got["letter"], got["word"]), ("K", "Kilo"))

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

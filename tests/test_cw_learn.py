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

The answer. The letter that goes on the screen is the one the learner picked,
green when it was right and red when it was not; the name that is said is the
character that was actually sent, either way. A wrong pick must not be able to
put a wrong name against a sound - that is the one thing this pane could do
that would teach the wrong thing - so the test picks wrong on purpose and
checks what was said.

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
  const chip = c => [...$('cw-lesson-chars').children].find(b => b.dataset.char === c);
  const out = {};
  $('cw-qsay').click();                       // no Q keying before each press
  // The slider is pushed up on purpose. The lesson must ignore it: a fresh
  // record has earned two characters, and two is what it gets.
  const slider = $('cw-lesson');
  slider.value = 6; slider.dispatchEvent(new Event('input'));
  $('cw-learn-begin').click();
  // Two characters never heard are met first - sounded, drawn, named, with
  // nothing asked - and only then is the first one sent as a question.
  await sleep(1200);
  out.meeting = {hint: $('cw-teach-hint').textContent, waiting: !$('cw-learn-again').hidden,
                 chars: learnChars.slice()};
  await sleep(8500);
  const sent = learnCur;
  out.sounded = {count: $('cw-learn-count').textContent,
                 again: !$('cw-learn-again').hidden,
                 begin_gone: $('cw-learn-begin').hidden,
                 answering: $('cw-lesson-chars').classList.contains('picking'),
                 named_yet: $('cw-teach-word').textContent,
                 review: $('cw-lesson-chars').children.length,
                 review_has_code: !!$('cw-lesson-chars').querySelector('.cw-code i'),
                 in_set: learnChars.includes(sent)};
  await sleep(3500);
  out.still = {count: $('cw-learn-count').textContent, same: learnCur === sent};

  // Wrong on purpose: the letter shown is theirs, in red; the word is the
  // truth, and the same character comes round again.
  const wrong = learnChars.find(c => c !== sent);
  chip(wrong).click();
  await sleep(600);
  const letter = $('cw-teach-letter');
  out.missed = {shown: letter.textContent, red: letter.classList.contains('wrong'),
                green: letter.classList.contains('right'),
                word: $('cw-teach-word').textContent, was: phoneticWord(sent)};
  await sleep(3000);
  out.again_same = {count: $('cw-learn-count').textContent, sent: learnCur === sent};

  // Right this time, by clicking it.
  chip(sent).click();
  await sleep(600);
  out.got = {shown: letter.textContent, green: letter.classList.contains('right'),
             red: letter.classList.contains('wrong'), word: $('cw-teach-word').textContent};
  await sleep(3000);
  out.moved_on = {count: $('cw-learn-count').textContent,
                  waiting: !$('cw-learn-again').hidden};

  // And by typing it, for anybody with a keyboard under their hands.
  const second = learnCur;
  document.dispatchEvent(new KeyboardEvent('keydown', {key: second, bubbles: true}));
  await sleep(600);
  out.typed = {shown: letter.textContent, green: letter.classList.contains('right')};
  await sleep(3000);
  out.after_typed = $('cw-learn-count').textContent;

  $('cw-learn-stop').click();
  await sleep(500);
  out.stopped = {begin_back: !$('cw-learn-begin').hidden,
                 again_gone: $('cw-learn-again').hidden,
                 answering: $('cw-lesson-chars').classList.contains('picking')};
  // What the record now holds: every answer, and nothing from the meetings.
  const prog = CWS.progress || {};
  out.record = Object.fromEntries(learnChars.map(c => [c, {sent: (prog[c] || {}).sent || 0,
                                                            copied: (prog[c] || {}).copied || 0}]));
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

    print("\n-- the record decides what is in the lesson, not the slider --")
    got = json.loads(_browser.evaluate(URL, LESSON_JS, settle=3.0, flags=FLAGS, cookies={'elmer_user': '1'}))
    check("a fresh record earns two characters, whatever the slider says",
          got["meeting"]["chars"], ["K", "M"])
    check("  and a character never heard is met first - named, nothing asked",
          (got["meeting"]["hint"].startswith("new: "), got["meeting"]["waiting"]), (True, False))
    check("the lesson's characters are on the screen to compare against", got["sounded"]["review"], 2)
    check("  drawn as shapes, not written as dots", got["sounded"]["review_has_code"], True)
    check("then the first one is sent, and the controls are handed over",
          (got["sounded"]["count"], got["sounded"]["again"], got["sounded"]["begin_gone"]),
          ("1 heard \u00b7 0 of 40 solid", True, True))
    check("  it is one of the lesson's own", got["sounded"]["in_set"], True)
    check("  the row above becomes the answer buttons", got["sounded"]["answering"], True)
    check("  and nothing is named yet - that is what the thinking is for",
          got["sounded"]["named_yet"], "")
    # The heart of it. Nothing moves on its own.
    check("left alone, it is still on the same character",
          (got["still"]["count"], got["still"]["same"]), ("1 heard \u00b7 0 of 40 solid", True))

    print("\n-- a wrong answer: their letter in red, the true name spoken --")
    check("the letter shown is the one they picked, and it is red",
          (got["missed"]["shown"] == got["missed"]["was"][0], got["missed"]["red"],
           got["missed"]["green"]), (False, True, False))
    check("  the word said is the character that was sent, not the mistake",
          got["missed"]["word"], got["missed"]["was"])
    check("  and the same character comes round again",
          (got["again_same"]["count"], got["again_same"]["sent"]), ("1 heard \u00b7 0 of 40 solid", True))

    print("\n-- a right answer: their letter in green, and the same name --")
    check("the letter shown is green",
          (got["got"]["green"], got["got"]["red"]), (True, False))
    check("  named the same way it is named when they miss it",
          got["got"]["word"], got["missed"]["word"])
    check("  and only then does the next one sound, and wait in its turn",
          (got["moved_on"]["count"], got["moved_on"]["waiting"]), ("2 heard \u00b7 0 of 40 solid", True))
    check("typed rather than clicked, it is the same answer",
          got["typed"]["green"], True)
    check("  and moves on the same way", got["after_typed"], "3 heard \u00b7 0 of 40 solid")
    check("Stop puts the lesson away",
          (got["stopped"]["begin_back"], got["stopped"]["again_gone"],
           got["stopped"]["answering"]), (True, True, False))

    print("\n-- and every answer went into the record --")
    # Three sends were answered: one miss, two hits. The two meetings were
    # not sends and left nothing behind.
    rec = got["record"]
    check("three sends recorded, no more",
          sum(v["sent"] for v in rec.values()), 3)
    check("  two of them copied", sum(v["copied"] for v in rec.values()), 2)

    print("\n-- the record earns the next character, one at a time --")
    # No browser for this part: a learner is walked through the record the
    # way the lesson writes it, one send at a time, and the plan is asked
    # what it has earned after each step.
    # A second account with a fresh record, made in the same isolated state
    # the server is reading, so the browser's few sends on the first do not
    # muddy the count.
    from elmer import db as _db
    walker = _db.add_user(_db.connect(), "Walker")
    walker = walker["id"] if isinstance(walker, dict) else walker

    def send(ch, hit):
        body = json.dumps({"per_char": {ch: {"sent": 1, "copied": 1 if hit else 0,
                                             "confused": {} if hit else {"M": 1},
                                             "outcomes": "1" if hit else "0"}}}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/cw/result", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Cookie": f"elmer_user={walker}"}, method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=10).read())["learn"]

    learn = None
    for _ in range(19):
        learn = send("K", True)
    check("nineteen in a row is not yet solid - twenty is the least that counts",
          (learn["solid"], learn["chars"]), (0, ["K", "M"]))
    for _ in range(19):
        learn = send("M", True)
    learn = send("K", True)
    check("  the twentieth makes K solid, but M is not yet, so nothing joins",
          (learn["solid"], learn["chars"]), (1, ["K", "M"]))
    learn = send("M", True)
    check("both solid: R is earned, named as new, and takes a third of the deal",
          (learn["solid"], learn["chars"], learn["new"], learn["draw"].get("R")),
          (2, ["K", "M", "R"], ["R"], 0.35))
    # A bad start on R, then a good run: the window forgives what the
    # lifetime ratio would not.
    for _ in range(10):
        learn = send("R", False)
    for _ in range(30):
        learn = send("R", True)
    check("ten misses then thirty hits is solid by the window (lifetime says 75%)",
          (learn["solid"], learn["chars"][-1]), (3, "S"))
    check("  and S, the newest, takes a third of the deal",
          learn["draw"].get("S"), 0.35)

    print("\n-- run together, each one named as it goes by --")
    got = json.loads(_browser.evaluate(URL, TOGETHER_JS, settle=3.0, flags=FLAGS, cookies={'elmer_user': '1'}))
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

#!/usr/bin/env python3
"""The calibration cards stand as long as they take to read, and a tap holds one.

    python3 tests/test_calibration_cards.py

While a calibration runs, the Propagation page shows cards from the decks -
history, quotations, hams people have heard of. They used to turn every
twelve seconds whatever was on them, which cut a long quotation off halfway
and left a short one standing long after it was read. What is held here:

  - a card stands for 5 seconds plus 0.33 seconds a word, counting the
    attribution with the text;
  - one tap on the card holds it: its timer is stopped and the card says so;
  - a second tap moves on to the next card, which is timed by its own words;
  - the keyboard does what the tap does, since the card is a button;
  - a card that is not held moves on by itself when its time is up.

Driven in a real headless browser against the page's own calibrate.js,
with the clock and the server stubbed so the test waits for nothing.
"""
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# Two cards with known word counts. The first: ten words and a three-word
# attribution, 13 words, 5 + 0.33 * 13 = 9.29 s. The second: a three-word
# name and a three-word note, 6 words, 5 + 0.33 * 6 = 6.98 s.
STUBS = r"""
<script>
window.__timers = []; let nextId = 1; const live = new Map();
window.setTimeout = (fn, ms) => { const id = nextId++; live.set(id, fn); window.__timers.push(ms); return id; };
window.clearTimeout = id => { live.delete(id); };
window.setInterval = () => 0; window.clearInterval = () => {};
window.__live = () => live.size;
window.__fire = () => { const e = [...live.entries()].pop(); if (e) { live.delete(e[0]); e[1](); } };
window.__cards = 0;
window.api = async url => {
  if (url.startsWith('/api/calibrate/status')) return {state: 'running', fraction: 0.1, days: 365, findings: []};
  if (url.startsWith('/api/cards')) {
    window.__cards++;
    return window.__cards === 1
      ? {deck: 'quotes', text: 'one two three four five six seven eight nine ten', about: 'Some Body, 1920'}
      : {deck: 'hams', text: 'Hiram Percy Maxim', about: 'founded the ARRL'};
  }
  return {};
};
window.postJSON = async () => ({});
window.escapeHTML = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
</script>
"""

PAGE = """<!doctype html><html><body>
<div id="cal-choices"><button data-cal-days="365">Year</button></div>
<button id="cal-stop" hidden>Stop</button>
<div id="cal-state"></div>
<div id="cal-stage" hidden><div id="cal-bar"></div><div id="cal-progress"></div>
<ul id="cal-findings"></ul>
{card}
</div>
<div id="cal-result" hidden></div>
{stubs}
<script>
{script}
</script>
</body></html>"""

# Each step waits a moment for the awaited fetch to settle.
DRIVE = r"""
new Promise(async done => {
 // A step that throws answers with the error: an async executor that
 // throws never calls done, and the promise would never settle.
 try {
  const nap = ms => new Promise(r => window.__realTimeout(r, ms));
  const card = document.getElementById('cal-card');
  const hint = () => document.getElementById('cal-card-hint').textContent;
  const out = {};
  await nap(300);
  out.first = {cards: window.__cards, ms: window.__timers[window.__timers.length - 1],
               live: window.__live(), hint: hint()};
  card.click(); await nap(100);
  out.held = {cards: window.__cards, live: window.__live(), hint: hint(),
              pressed: card.getAttribute('aria-pressed')};
  card.click(); await nap(300);
  out.next = {cards: window.__cards, ms: window.__timers[window.__timers.length - 1],
              live: window.__live(), hint: hint(), pressed: card.getAttribute('aria-pressed')};
  window.__fire(); await nap(300);
  out.expired = {cards: window.__cards, live: window.__live()};
  card.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true})); await nap(100);
  out.key = {live: window.__live(), pressed: card.getAttribute('aria-pressed')};
  done(JSON.stringify(out));
 } catch (e) { done('EXCEPTION ' + e); }
})
"""


def the_real_card():
    """The card markup as the Propagation page has it."""
    page = (ROOT / "elmer" / "templates" / "propagation.html").read_text(encoding="utf-8")
    m = re.search(r'<div class="panel tight" id="cal-card".*?</div>\s*</div>', page, re.S)
    return m.group(0) if m else ""


def main():
    print("\n-- the card on the page is a button that says it can be held --")
    card = the_real_card()
    check("the Propagation page has the card", bool(card), True)
    check("  it is a button, focusable, not yet pressed",
          ('role="button"' in card, 'tabindex="0"' in card, 'aria-pressed="false"' in card), (True, True, True))
    check("  and it carries the hint", 'id="cal-card-hint"' in card, True)

    if not _browser.available():
        check("chromium is on this machine", False, True)
        print("\nFAILED: this test needs chromium")
        return 1

    script = (ROOT / "elmer" / "static" / "calibrate.js").read_text(encoding="utf-8")
    stubs = STUBS.replace("<script>", "<script>\nwindow.__realTimeout = window.setTimeout.bind(window);", 1)
    scratch = Path(tempfile.mkdtemp(prefix="elmer-cards-"))
    try:
        page = scratch / "cards.html"
        page.write_text(PAGE.format(card=card, stubs=stubs, script=script), encoding="utf-8")
        with _browser.serve(scratch) as base:
            got = _browser.evaluate(base + "/cards.html", DRIVE, settle=0.5)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    try:
        out = json.loads(got)
    except (TypeError, ValueError):
        check("the page ran", got, "a JSON report")
        return 1

    print("\n-- timed by its words --")
    first = out["first"]
    check("the first card is fetched when the run is found going", first["cards"], 1)
    check("  and stands 5 s + 0.33 s x 13 words = 9.29 s", first["ms"], 9290)
    check("  one timer running, and the card says it can be held",
          (first["live"], first["hint"]), (1, "Tap to hold this card."))

    print("\n-- one tap holds it --")
    held = out["held"]
    check("tapped once: no timer, the same card", (held["live"], held["cards"]), (0, 1))
    check("  and it says it is held", (held["hint"], held["pressed"]), ("Held. Tap for the next card.", "true"))

    print("\n-- a second tap moves on --")
    nxt = out["next"]
    check("tapped again: the next card is fetched", nxt["cards"], 2)
    check("  timed by its own words: 5 s + 0.33 s x 6 = 6.98 s", nxt["ms"], 6980)
    check("  running again, and says so", (nxt["live"], nxt["hint"], nxt["pressed"]),
          (1, "Tap to hold this card.", "false"))

    print("\n-- left alone, it moves on by itself; the keyboard holds it too --")
    check("when its time is up the next card comes", out["expired"]["cards"], 3)
    check("Enter on the card holds it, as a tap does", (out["key"]["live"], out["key"]["pressed"]), (0, "true"))

    # This test once wrote its page where a snap Chromium could not see it,
    # its script threw before it could answer, and the CI job waited six
    # hours on a browser that had nothing more to say. Held here: a page
    # that never answers fails the test, quickly and by name.
    print("\n-- a page that never answers fails the test rather than hanging it --")
    real = _browser.ANSWER_S
    _browser.ANSWER_S = 3.0
    scratch = Path(tempfile.mkdtemp(prefix="elmer-silent-"))
    started = time.monotonic()
    try:
        (scratch / "silent.html").write_text("<!doctype html><p>nothing</p>", encoding="utf-8")
        with _browser.serve(scratch) as base:
            _browser.evaluate(base + "/silent.html", "new Promise(() => {})", settle=0.1)
        said = None
    except _browser.PageSilent as exc:
        said = str(exc)
    finally:
        _browser.ANSWER_S = real
        shutil.rmtree(scratch, ignore_errors=True)
    check("a promise that never settles is reported, naming the page",
          bool(said and "silent.html" in said), True)
    check("  within seconds, not hours", time.monotonic() - started < 30, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

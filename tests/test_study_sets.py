#!/usr/bin/env python3
"""Study comes in sets of ten, and stopping after one is finishing it.

    python3 tests/test_study_sets.py

A drill with no bottom is a pile, and the only way off a pile is to walk
away from it. So after every ten answers the page stops and says how the set
went, and offers another - or "That will do", which is a perfectly good
answer. What is held here, in a real browser:

  - ten answers in, the page shows the set, not an eleventh question;
  - "Another set" carries on with a question;
  - the verdict's wording says when a question comes round again, not when
    a review is due.
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


PLAY = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms));
  const until = async (test, ms) => { for (let i = 0; i < ms / 50; i++) { if (test()) return true; await nap(50); } return false; };
  const out = {answered: 0, verdicts: []};
  for (let i = 0; i < 10; i++) {
    if (!await until(() => document.querySelector('#card .choice'), 8000)) break;
    document.querySelector('#card .choice').click();
    if (!await until(() => document.getElementById('next'), 8000)) break;
    out.verdicts.push(document.getElementById('verdict').textContent);
    out.answered++;
    document.getElementById('next').click();
  }
  await nap(300);
  out.heading = (document.querySelector('#card h2') || {}).textContent || '';
  out.another = !!document.getElementById('another');
  out.questionShown = !!document.querySelector('#card .choice');
  if (out.another) {
    document.getElementById('another').click();
    out.carriedOn = await until(() => document.querySelector('#card .choice'), 8000);
  }
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
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/study/tech2026", PLAY, width=1200,
                                           height=900, settle=1.5, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    check("ten questions answered", got.get("answered"), 10)
    check("then the set, not an eleventh question",
          (got.get("heading"), got.get("questionShown")), ("That is a set", False))
    check("  offering another", got.get("another"), True)
    check("  which carries on", got.get("carriedOn"), True)
    words = " ".join(got.get("verdicts") or []).lower()
    # The schedule's own phrases; a question's explanation may well say "due to".
    check("no verdict says review or due",
          [w for w in ("next review", "due for review", "overdue", "review in") if w in words], [])


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)

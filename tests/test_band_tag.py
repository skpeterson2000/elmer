#!/usr/bin/env python3
"""The band tag under a frequency box names the band the box actually holds.

    python3 tests/test_band_tag.py

Reported from a screenshot: 3.695 MHz in the antenna calculator, with the
tag underneath reading "20 m . SSB". Nothing was wrong with the antenna -
it was cut for 80 m, the elevation pattern was drawn at 0.133 wavelengths,
which is 48 ft on 80 m and nothing like 48 ft on 20 m - and the band table
says 3.695 is 80 m at every layer that was asked. Only the label was wrong.

The cause: typing in the box fires `input` and the tag follows, but ELMER
setting the box from code - which is what "suggest one" does, and what every
carry-over between panes does - assigns `.value` and fires nothing. So the
tag kept naming the band of whatever was there before.

This is the same fault as the golf card and the inverted V: one number with
two renderings that are allowed to disagree. The fix is one function that
sets a frequency and repaints what is derived from it, so the next carry-over
cannot reintroduce this.
"""
import os
import re
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
LAB = ROOT / "elmer" / "static" / "lab.js"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- no frequency is set from code without repainting the tag --")
    source = LAB.read_text(encoding="utf-8")
    check("the helper exists", "function setFrequency(" in source, True)
    check("  and a repaint with it", "function repaintBandMeters(" in source, True)
    # A bare assignment to any of the metered boxes is the bug itself.
    stray = re.findall(r"getElementById\(['\"](?:s-f|an-f|sm-f|p-f|r-f)['\"]\)\.value\s*=", source)
    check("no metered box is assigned directly any more", stray, [])

    if not _browser.available():
        print("\nFAILED: the rest of this test needs chromium")
        return 1

    print("\n-- and the tag agrees with the box, in a browser --")
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\n"
         "from elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
         % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise SystemExit("the throwaway server never answered")

        # Set the box the way ELMER's own suggestion does - from code, with
        # no typing - and read the tag back. 3.695 is the reported case; the
        # others cross a band boundary in each direction.
        js = """(async () => {
          const out = [];
          for (const mhz of [14.200, 3.695, 7.180, 28.400, 3.695]) {
            setFrequency('an-f', mhz);
            await new Promise(r => setTimeout(r, 60));
            const tag = document.querySelector('#an-f').closest('.field')
                        .querySelector('.bandmeter');
            out.push(mhz + ' -> ' + (tag ? tag.textContent.trim() : '(no tag)'));
          }
          return out.join(' | ');
        })()"""
        # evaluate() already awaits a promise the expression returns.
        said = _browser.evaluate(f"http://127.0.0.1:{port}/lab#antennas", js, settle=3.0)
        print(f"    {said}")
        pairs = [p.strip() for p in str(said).split("|")]
        want = {"14.2": "20 m", "3.695": "80 m", "7.18": "40 m", "28.4": "10 m"}
        for pair in pairs:
            mhz, _, tag = pair.partition("->")
            mhz, tag = mhz.strip(), tag.strip()
            if mhz in want:
                check(f"{mhz} MHz is named {want[mhz]}", tag.startswith(want[mhz]), True)
        # The reported case appears twice on purpose: once cold, and once
        # after the box has been somewhere else, which is the state the
        # screenshot was taken in.
        check("and it is still right on the way back to it",
              pairs[-1].split("->")[1].strip().startswith("80 m"), True)
    finally:
        server.terminate()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

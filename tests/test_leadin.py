#!/usr/bin/env python3
"""The run-up to a question, and the program keeping its own time.

    python3 tests/test_leadin.py

KC9SP, 2026-09-12: when the program runs an intermission, a countdown on
the screens - not obtrusive, not hidden; and before the game starts again,
a five-second warning on every player's screen: "Get ready!" for two
seconds from five, then three, two, one. So the shift into the game is not
abrupt, nobody can say their time was hindered, and the field is as level
as we can make it.

What is proved here: the program's clock and the rule for when a timed
step is up; the timekeeper moving the program on and handing over from a
finished game, once; the run-up on the net and in every view the screens
read; and, in the Chromium the kiosk runs, the words the screens draw from
what is left.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402
from elmer import hall, netcontrol, show as showmod  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# ------------------------------------------------------ the program's clock
print("\na timed step has a clock; a step the host ends has none")
sh = showmod.Show()
sh.set_program([{"kind": "intermission", "minutes": 2},
                  {"kind": "rounds", "rounds": 3},
                  {"kind": "intermission", "minutes": 1},
                  {"kind": "thanks"}])
t0 = 1000.0
sh.advance(now=t0)
view = sh.program_view(now=t0 + 30)
check("intermission: kind on the view", view["kind"], "intermission")
check("  ninety seconds left", view["remaining"], 90.0)
check("  not up with ninety seconds left", sh.step_due(now=t0 + 30, lead=5), False)
check("  up five seconds early when a game follows",
      sh.step_due(now=t0 + 115.1, lead=5), True)
check("  but not with six seconds left", sh.step_due(now=t0 + 114, lead=5), False)
sh.advance(now=t0 + 115)
check("rounds: no clock", sh.program_view(now=t0 + 120)["remaining"], None)
check("  and never due by the clock", sh.step_due(now=t0 + 9999, lead=5), False)
sh.advance(now=t0 + 200)
check("an intermission before 'thanks' runs its full minute",
      sh.step_due(now=t0 + 256, lead=5), False)
check("  and is up at nought", sh.step_due(now=t0 + 260, lead=5), True)

print("\nadvancing from a step is refused if the program has moved on")
check("from the right step", sh.advance_from(2, now=t0 + 260)["kind"], "thanks")
check("from a step that is gone", sh.advance_from(2, now=t0 + 261), None)
check("  and the program did not skip", sh.step, 3)

# ------------------------------------------------------------ the timekeeper
print("\nthe timekeeper moves a timed step on, and hands over from a game")
net = netcontrol.Net()
net.show.set_program([{"kind": "intermission", "minutes": 1},
                        {"kind": "rounds", "rounds": 1},
                        {"kind": "intermission", "minutes": 1},
                        {"kind": "thanks"}])
moved = []
keeper = hall.Timekeeper(net, lambda index: moved.append(index) or
                         net.show.advance_from(index), lead_in=5.0)
net.show.advance(now=t0)
check("nothing due at once", keeper.due(now=t0 + 1), None)
check("due in the last five seconds", keeper.due(now=t0 + 56), 0)
check("  a tick moves it on", keeper._tick(now=t0 + 56), True)
check("  to the rounds", (net.show.current_step() or {}).get("kind"), "rounds")
check("  told the app which step it left", moved, [0])
check("rounds are not due while nothing conducts", keeper.due(now=t0 + 60), None)


class Done:
    state = "finished"


class Busy:
    state = "asking"


was = hall.conductor
try:
    hall.conductor = lambda: Busy()
    check("  nor while the conductor is asking", keeper.due(now=t0 + 60), None)
    finished = Done()
    hall.conductor = lambda: finished
    check("  due once the rounds are played", keeper.due(now=t0 + 60), 1)
    keeper._tick(now=t0 + 60)
    check("  handed over to the intermission",
          (net.show.current_step() or {}).get("kind"), "intermission")
    # The finished conductor is still there; the intermission step is not a
    # game, and the game step it came from is not handed over twice.
    check("  and not again", keeper.due(now=t0 + 61), None)
    net.show.step = 1                         # walk it back, as a host might
    check("the same finished conductor does not hand over a second time",
          keeper.due(now=t0 + 62), None)
    hall.conductor = lambda: Done()           # a new conducting, finished
    check("  a new one does", keeper.due(now=t0 + 62), 1)
finally:
    hall.conductor = was

# ----------------------------------------------------------- the run-up view
print("\nthe run-up is on the net, where every screen reads it")
net = netcontrol.Net()
check("none to begin with", net.lead_in_view(), None)
net.begin_lead_in(5.0)
view = net.lead_in_view()
check("five seconds, counting", 4.5 < view["remaining"] <= 5.0, True)
check("  of five", view["seconds"], 5.0)
check("  in the units' show", net.show_for("t1")["lead_in"] is not None, True)
check("  on the board", net.board()["show"]["lead_in"] is not None, True)
net.start_round("technician", "T001", 0, {"text": "q", "choices": ["a", "b"]})
check("the question ends it", net.lead_in_view(), None)
net.begin_lead_in(5.0)
net.cancel_lead_in()
check("and so does cancelling", net.lead_in_view(), None)

# --------------------------------------------------------------- the screen
print("\nthe screens draw the words from what is left")
check("chromium is on this machine", bool(_browser.available()), True)
ROOT = Path(__file__).resolve().parents[1]
PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\n"
     "from elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise SystemExit("the throwaway server never answered")

    # The page's own polls carry no hall, so the show is handed to the
    # drawing code directly, reading by reading, the way a poll would.
    script = """
      (() => {
        const out = {};
        const word = () => { const w = document.querySelector('#hs-leadin .hs-word'); return w && !document.getElementById('hs-leadin').hidden ? w.textContent : null; };
        const clock = () => { const c = document.getElementById('hs-clock'); return c && !c.hidden ? c.textContent : null; };
        hallShow.overlay({mode: 'intermission', program: {step: 1, kind: 'intermission', now: 'Intermission', remaining: 272}});
        out.clock = clock(); out.noLead = word();
        hallShow.overlay({mode: 'intermission', program: {step: 1, kind: 'intermission', now: 'Intermission', remaining: 272}, lead_in: {remaining: 4.6, seconds: 5, at: 1}});
        out.ready = word(); out.clockDuringLead = clock();
        hallShow.overlay({lead_in: {remaining: 2.9, seconds: 5, at: 1}});
        out.three = word();
        // A stale reading - a poll that arrived late says more is left than
        // there is - must not push the count back up.
        hallShow.overlay({lead_in: {remaining: 3.8, seconds: 5, at: 1}});
        out.stillThree = word();
        hallShow.overlay({lead_in: {remaining: 1.4, seconds: 5, at: 1}});
        out.two = word();
        hallShow.overlay({lead_in: {remaining: 0.7, seconds: 5, at: 1}});
        out.one = word();
        hallShow.overlay({lead_in: {remaining: 0, seconds: 5, at: 1}});
        out.go = word();
        hallShow.overlay({mode: 'play'});
        out.gone = word(); out.clockGone = clock();
        // A new run-up, later, starts from the top even though the last one
        // ran down.
        hallShow.overlay({lead_in: {remaining: 4.9, seconds: 5, at: 2}});
        out.again = word();
        hallShow.overlay(null);
        return JSON.stringify(out);
      })()
    """
    got = json.loads(_browser.evaluate(f"http://127.0.0.1:{PORT}/party", script,
                                       settle=1.5, cookies={'elmer_user': '1'}) or "{}")
    check("the corner clock reads the step's time", got.get("clock"),
          "Intermission4:32")
    check("  and there is no run-up on the screen", got.get("noLead"), None)
    check("five seconds out: Get ready!", got.get("ready"), "Get ready!")
    check("  and the corner clock steps aside", got.get("clockDuringLead"), None)
    check("three", got.get("three"), "3")
    check("  a stale reading does not push it back", got.get("stillThree"), "3")
    check("two", got.get("two"), "2")
    check("one", got.get("one"), "1")
    check("nought: Go!", got.get("go"), "Go!")
    check("the question takes it off", got.get("gone"), None)
    check("  and the clock with it", got.get("clockGone"), None)
    check("a later run-up starts from the top", got.get("again"), "Get ready!")
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")

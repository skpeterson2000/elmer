#!/usr/bin/env python3
"""A CW contact with a virtual partner: the safe place to learn to talk.

    python3 tests/test_cw_qso.py

The partner answers a CQ or calls one, gives a report, trades names and
QTHs, talks rig and weather, and says 73 - and copies what the operator's
fist actually sent, not what they meant. What is held here:

  - an over is read the way an operator reads one: calls, a report (5NN is
    599), a name, a QTH, questions, AGN, QRS and QRQ, and a prosign keyed
    run-together, which decodes as its punctuation twin (AR is "+", KN "(");
  - either end can call CQ, and the contact runs to 73 and SK;
  - a call that would not decode gets QRZ, not an answer to somebody else;
  - a ragged fist gets PSE QRS, and a readability in the report to match;
  - AGN has the last over sent again; QRS slows them and they say so;
  - they use what they copied, wrong letters and all;
  - on the page: the contact keys through "Your sending", their text is
    hidden until asked for, a typed over is answered, and a keyed over
    ending in K is sent by itself once the key has been quiet.
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
from elmer import qso  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def unit():
    print("\n-- an over, read --")
    g = qso.parse("W1AW DE KC9SP GE UR RST 5NN 5NN NAME SCOTT SCOTT QTH PEQUOT LAKES MN HW? KN")
    check("calls, a report (5NN is 599), a name, a QTH, a question and the hand-over",
          (g["to"], g["de"], g["rst"], g["fields"].get("name"), g["fields"].get("qth"), g["asks"], g["over"]),
          ("W1AW", "KC9SP", "599", "SCOTT", "PEQUOT LAKES MN", {"hw"}, "KN"))
    g = qso.parse("R R TNX + K9XYZ DE KC9SP (")
    check("a prosign keyed run-together, decoded as its twin, is the prosign", g["over"], "KN")
    check("  AR among the words too", "AR" in g["words"], True)
    check("questions asked by name: UR RIG? WX?", qso.parse("UR RIG? WX? K")["asks"], {"rig", "wx"})
    check("AGN, QRS and QRQ", [qso.parse(t)[k] for t, k in (("AGN?", "agn"), ("QRS PSE K", "qrs"),
                                                            ("QRQ K", "qrq"))], [True, True, True])

    print("\n-- they call CQ, you answer --")
    s, say = qso.start("them", 18, seed=3, hour=20)
    pc = s["partner"]["call"]
    check("they call CQ", say, f"CQ CQ CQ DE {pc} {pc} K")
    s2, say2, notes = qso.turn(dict(s, heard={}, told=[], qualities=[]), f"{pc} DE K*9SP K", 0.9, 18)
    check("a call that would not decode gets QRZ, not an answer", say2.startswith("QRZ?"), True)
    check("  and the page is told why", any("could not copy your call" in n for n in notes), True)
    s, say, _ = qso.turn(s, f"{pc} DE KC9SP KC9SP K", 0.95, 20)
    check("your call copied: they answer with a report, name and QTH",
          (say.startswith(f"KC9SP DE {pc}"), "UR RST 5" in say, f"NAME {s['partner']['name']}" in say,
           say.endswith("KN")), (True, True, True, True))
    check("  at your speed", s["wpm"], 20)
    s, say, _ = qso.turn(s, "R R TNX FER RPT NAME JOM JOM QTH MN HW? K", 0.95, 20)
    check("they use what they copied, wrong letters and all", "FB JOM" in say, True)
    check("  and answer how they copy you", "UR SIGS 5" in say, True)
    last = say
    s, say, notes = qso.turn(s, "AGN?", 0.95, 20)
    check("AGN has the last over sent again", say, "OK AGN " + last)
    s, say, notes = qso.turn(s, "QRS PSE K", 0.95, 20)
    check("QRS slows them, and they say so", (say.startswith("QRS OK"), s["wpm"]), (True, 17))
    s, say, notes = qso.turn(s, "FB WX HR COLD ES SNOW K", 0.4, 17)
    check("a ragged fist gets PSE QRS", say.startswith("PSE QRS"), True)
    check("  and a report of that readability", qso.readability(0.4), 2)
    s, say, _ = qso.turn(s, "TNX FER QSO JOM 73 SK", 0.95, 17)
    check("73 and SK from you: they close, and the contact is over",
          ("73" in say, "<SK>" in say, s["phase"]), (True, True, "done"))
    check("what they copied of you", qso.summary(s)["heard"].get("call"), "KC9SP")

    print("\n-- you call CQ --")
    s, say = qso.start("me", 15, seed=5, hour=9)
    check("they wait for your CQ", say, "")
    s, say, _ = qso.turn(s, "CQ CQ DE KC9SP KC9SP K", 0.9, 15)
    pc = s["partner"]["call"]
    check("and answer it", say, f"KC9SP DE {pc} {pc} K")
    s, say, _ = qso.turn(s, f"{pc} DE KC9SP GM UR RST 579 NAME SCOTT QTH MN HW? KN", 0.9, 15)
    check("your first over: R R, your name, thanks for the report, theirs back",
          (say.startswith("R R GM SCOTT TNX FER 579"), "UR RST" in say), (True, True))


DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof qsoStart === 'function', 10000);
  settings.wpm = 35;
  showMode('contact');
  const out = {contact: !document.getElementById('cw-contact').hidden, key: !document.getElementById('cw-key').hidden};
  document.querySelector('[data-qso-start="them"]').click();
  await until(() => qso.log.length >= 1, 8000);
  out.first = qso.log[0] && qso.log[0].who;
  out.hidden = !!document.querySelector('[data-qso-reveal]');
  const call = qso.last && qso.last.summary && qso.last.summary.partner.call;
  await until(() => !qso.busy, 20000);
  const typed = document.getElementById('cw-qso-type');
  typed.value = call + ' de kc9sp kc9sp k';
  document.getElementById('cw-qso-typed').click();
  await until(() => qso.log.length >= 3, 8000);
  out.answer = qso.log[2] && qso.log[2].text;
  await until(() => !qso.busy, 40000);
  // Keyed: the decoder's text, ending in K, sent by itself after the pause.
  keyDecoder.text = 'R R NAME SCOTT K';
  await until(() => qso.log.length >= 5, 8000);
  out.keyed = qso.log[3] && qso.log[3].text;
  out.reply = qso.log[4] && qso.log[4].who;
  resolve(JSON.stringify(out));
})
"""


def main():
    unit()
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
                                           settle=1.5, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    print("\n-- on the page --")
    check("Contact shows its pane and the key beneath it", (got.get("contact"), got.get("key")), (True, True))
    check("their CQ arrives, its text hidden until asked for", (got.get("first"), got.get("hidden")), ("them", True))
    check("a typed over is answered with a report", "UR RST" in (got.get("answer") or ""), True)
    check("a keyed over ending in K goes by itself once the key is quiet",
          (got.get("keyed"), got.get("reply")), ("R R NAME SCOTT K", "them"))


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)

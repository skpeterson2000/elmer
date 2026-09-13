#!/usr/bin/env python3
"""The problem report: the operator's words first, and whose it is only by
their choice.

    python3 tests/test_bugreport.py

The log cannot say what the person was doing when it went wrong, so the
report opens with their account of it when they give one, and the subject
leads with its first line. Without the box ticked nothing on the report
says whose it is - a callsign typed into their own words included. With it,
the report says whose it is at the top, so a reply can reach them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import bugreport, db  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# The heading as a line of its own. The report's header quotes the latest
# commit subject, and a commit about this very feature put the words "in the
# operator's words" there too - so the phrase alone proves nothing.
WORDS = "\nwhat happened, in the operator's words\n"


def section_order(text, *names):
    """Where each heading falls in the report, so 'first' can be checked."""
    return [text.find(n) for n in names]


def run():
    conn = db.connect()
    db.set_callsign(conn, "KC9SP")
    conn.commit()

    print("\n-- with nothing said --")
    text, redacted = bugreport.build(conn, lines=20)
    check("the report opens as before", text.startswith("ELMER problem report"), True)
    check("  no words section", WORDS in text, False)
    check("  no from line", "\nfrom " in text, False)
    check("  redacted", redacted, True)
    check("  no headline", bugreport.headline(""), "")

    print("\n-- what the operator said comes first --")
    said = "The band plan tab went blank\nwhen I pressed print.\n\nSecond try was fine."
    text, redacted = bugreport.build(conn, lines=20, said=said)
    words, selfcheck, log_tail = section_order(
        text, WORDS, "\nself-check\n", "log lines")
    check("the words are in", "The band plan tab went blank" in text, True)
    check("  ahead of the self-check", 0 < words < selfcheck, True)
    check("  and the self-check ahead of the log", selfcheck < log_tail, True)
    check("  paragraphs kept", "\n\nSecond try was fine." in text, True)
    check("the headline is the first line", bugreport.headline(said),
          "The band plan tab went blank")
    check("  a long first line is cut for a subject",
          bugreport.headline("x" * 80).endswith("...") and len(bugreport.headline("x" * 80)) <= 60,
          True)
    check("  blank lines first are skipped", bugreport.headline("\n\n  hello  world \n"),
          "hello world")

    print("\n-- whose it is, only by choice --")
    text, redacted = bugreport.build(conn, lines=20, said="KC9SP here, it went blank")
    check("without the box, redacted", redacted, True)
    check("  their callsign in their own words is taken out too",
          "KC9SP" in text, False)
    check("  and replaced", "[callsign] here" in text, True)
    check("  no from line", "\nfrom " in text, False)
    text, redacted = bugreport.build(conn, lines=20, include_station=True,
                                     said="KC9SP here, it went blank")
    check("with the box, not redacted", redacted, False)
    check("  the callsign stays in their words", "KC9SP here" in text, True)
    check("  and the report says whose it is, at the top",
          "from       KC9SP - included so a reply can reach them" in text.split("\n", 6)[:6],
          True)

    print("\n-- too much said is cut, not refused --")
    text, _ = bugreport.build(conn, lines=20, said="y" * (bugreport.SAID_MOST + 500))
    check("cut to the most", text.count("y" * 100) * 100 <= bugreport.SAID_MOST, True)

    print("\n-- and it is written, where the page can open it --")
    path, redacted, text = bugreport.write(conn, lines=20, said="it went blank")
    check("written", path.exists(), True)
    check("  with the words", "it went blank" in path.read_text(), True)
    check("  found by its name", bugreport.locate(path.name), path)
    check("  and by no other", bugreport.locate("../" + path.name), None)
    check("  nor a name shaped like one that is not there",
          bugreport.locate("elmer-report-20000101-000000.txt"), None)
    check("  nor the log", bugreport.locate("elmer.log"), None)
    from elmer import app as elmer_app
    client = elmer_app.app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    r = client.get(f"/report/{path.name}", environ_base=local)
    check("the page opens it", (r.status_code, b"it went blank" in r.data), (200, True))
    check("  inline", r.headers["Content-Disposition"].startswith("inline"), True)
    r = client.get(f"/report/{path.name}?save=1", environ_base=local)
    check("  or saves it", r.headers["Content-Disposition"].startswith("attachment"), True)
    r = client.get(f"/report/{path.name}", environ_base={"REMOTE_ADDR": "10.0.0.5"})
    check("  from this screen only", r.status_code, 403)
    r = client.get("/report/elmer.log", environ_base=local)
    check("  and only reports", r.status_code, 404)
    path.unlink()
    conn.close()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())

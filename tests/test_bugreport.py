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

    print("\n-- four kinds, and only a problem carries the log --")

    # The log's sections, found by their headings: each is a line of its own.
    # The words alone are not enough - the build line quotes the last commit's
    # subject, and a commit about the self-check put "self-check" in every
    # report, suggestions included.
    def log_sections(report):
        lines = report.splitlines()
        return ("self-check" in lines,
                any(line.startswith("last ") and line.endswith(" log lines") for line in lines),
                any(line.startswith("errors and warnings in the last ") for line in lines))

    sugg, red = bugreport.build(conn, lines=20, said="the reach map could show the county's mean score", kind="suggestion")
    check("a suggestion opens as one", (sugg.startswith("ELMER suggestion"), "kind       suggestion" in sugg), (True, True))
    check("  carries the words and the build", ("reach map could" in sugg, "build      " in sugg), (True, True))
    check("  and nothing from the log", log_sections(sugg), (False, False, False))
    check("  redacted like any other", red, True)
    prob, _ = bugreport.build(conn, lines=20, said="it went blank", kind="problem")
    check("a problem still carries the log", log_sections(prob)[:2], (True, True))
    check("a kind the page never named is a problem", bugreport.kind_of("wishlist"), "problem")
    empty, _ = bugreport.build(conn, lines=20, kind="comment")
    check("a comment with nothing written says so", "a comment with nothing written in it" in empty, True)
    from elmer import app as elmer_app
    client = elmer_app.app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    r = client.post("/api/report", json={"kind": "question", "said": "why is 30 m shut at noon?"}, environ_base=local)
    d = r.get_json()
    check("the route writes a question", (r.status_code, d["text"].startswith("ELMER question"), "log lines" in d["text"]), (200, True, False))
    written = __import__("pathlib").Path(d["path"])
    if written.exists():
        written.unlink()

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

    print("\n-- every name the unit holds comes out, and nothing else --")
    # A second account with its own callsign and a GMRS call, a QTH, a trip,
    # a rated ground spot and a place asked of the gazetteer - each kept
    # where the program keeps it, in this test's own state directory.
    import json
    from elmer import geocode, siteground, trip
    mine = db.get_profile(conn)["settings"]
    mine["location"] = {"short": "Pequot Lakes", "grid": "EN26uo",
                        "name": "Pequot Lakes, Crow Wing County, Minnesota"}
    db.save_settings(conn, mine)
    other = db.add_user(conn, "Second Op", "KD0XYZ")
    me, conn.user_id = conn.user_id, other["id"]
    theirs = db.get_profile(conn)["settings"]
    theirs["gmrs_call"] = "WRXY123"
    db.save_settings(conn, theirs)
    conn.user_id = me
    conn.commit()
    trip.STORE.parent.mkdir(parents=True, exist_ok=True)
    trip.STORE.write_text(json.dumps({"destinations": [
        {"name": "Grand Marais", "lat": 47.75, "lon": -90.33, "prepared": 1}]}))
    siteground.CACHE.mkdir(parents=True, exist_ok=True)
    (siteground.CACHE / "46.1000_-94.2000.json").write_text(json.dumps(
        {"ok": True, "name": "Uncle Bob's Field", "lat": 46.1, "lon": -94.2, "rated": 1}))
    geocode.CACHE.mkdir(parents=True, exist_ok=True)
    (geocode.CACHE / "s_nisswa_1.json").write_text(json.dumps(
        [{"short": "Nisswa", "name": "Nisswa, Crow Wing County, Minnesota"}]))
    held = ("KC9SP", "KD0XYZ", "WRXY123", "Pequot Lakes", "Grand Marais",
            "Uncle Bob's Field", "Nisswa")
    said = ("KC9SP here with kd0xyz and WRXY123. Home is Pequot Lakes; we "
            "packed for Grand Marais, rated the ground at Uncle Bob's Field "
            "and looked up Nisswa.")
    text, redacted = bugreport.build(conn, lines=20, said=said, kind="comment")
    check("every callsign and place held is gone",
          [n for n in held if n.lower() in text.lower()], [])
    check("  each callsign is called a callsign", text.count("[callsign]"), 3)
    check("  and each place a place", text.count("[place]"), 4)

    said = ("Question T1A01 showed twice; my Mobile antenna was on 2 m. "
            "W1AW was on the air too.")
    text, _ = bugreport.build(conn, lines=20, said=said, kind="comment")
    check("a question id survives", "T1A01" in text, True)
    check("  a word that is also a bundled town survives", "Mobile antenna" in text, True)
    check("  a callsign no account holds is nobody's secret", "W1AW" in text, True)
    check("  and a held name inside a longer word is left alone",
          bugreport.redact("Nisswan", places=["Nisswa"]), "Nisswan")

    print("\n-- the log learns them too, as callsigns and as places --")
    from elmer import logs
    elmer_app._remember_private_names(conn)
    check("the log calls a callsign a callsign",
          logs.clean("second op is KD0XYZ at Grand Marais"),
          "second op is [callsign] at [place]")
    conn.close()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())

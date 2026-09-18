#!/usr/bin/env python3
"""The supporters, named where the build is.

    python3 tests/test_credits.py

SUPPORTERS.md is a plain list at the top of the checkout; the dashboard's
Software panel names the people on it. The list parses the way a person
would write it, the prose above it is not mistaken for names, and the
dashboard's payload carries it.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import credits  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the list, as a person writes it --")
    text = ("# Supporters\n\nThe people whose support - and it is theirs - pays.\n\n"
            "## Supporters\n\n- KC9SP - since September 2026\n- W1AW\n* VE3ABC — a club night in Kingston\n\n- \n")
    got = credits.parse(text)
    check("three entries, the prose left alone", [e["who"] for e in got], ["KC9SP", "W1AW", "VE3ABC"])
    check("  the note after the spaced dash", got[0]["note"], "since September 2026")
    check("  none when there is none", got[1]["note"], "")
    check("  an em dash is a dash", got[2]["note"], "a club night in Kingston")
    check("  a bare dash is not an entry", len(got), 3)

    print("\n-- the line the dashboard prints --")
    check("one name", credits.words([{"who": "KC9SP"}]), "KC9SP")
    check("two names", credits.words([{"who": "KC9SP"}, {"who": "W1AW"}]), "KC9SP and W1AW")
    eight = [{"who": f"N{i}XX"} for i in range(8)]
    check("many names, the rest counted", credits.words(eight).endswith("and 2 more"), True)
    check("nobody yet, nothing said", credits.words([]), "")

    print("\n-- the file, at the top of the checkout --")
    check("SUPPORTERS.md is there, beside the README", (credits.SOURCE.is_file(), credits.SOURCE.parent == credits.paths.ROOT), (True, True))
    check("  and it parses, whatever it holds", isinstance(credits.supporters(), list), True)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "SUPPORTERS.md"
        p.write_text("- KC9SP\n", encoding="utf-8")
        check("  a file handed in is read as given", [e["who"] for e in credits.supporters(p)], ["KC9SP"])

    print("\n-- on the dashboard --")
    from elmer.app import app
    c = app.test_client()
    r = c.get("/api/update")
    check("the update payload carries the supporters", (r.status_code, "supporters" in r.get_json()), (200, True))
    check("  as a list with the words to print", (isinstance(r.get_json()["supporters"], list), "supporter_words" in r.get_json()), (True, True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

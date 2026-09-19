#!/usr/bin/env python3
"""What ELMER says about its own licence matches its licence.

    python3 tests/test_license_words.py

ELMER is under PolyForm Noncommercial 1.0.0: free for personal study, clubs,
schools and other noncommercial use, not for commercial use, and deliberately
not an OSI open-source licence. The README and DESIGN.md have always said
exactly that.

Nine other sentences said "free for everyone". Each was making a true and
worthwhile point - that a cup of coffee for the developer is thanks and not a
toll - and each made it in words wider than the licence: a commercial user is
part of everyone, and for them ELMER is not free, they are not licensed at
all. The phrase was walked past for a long time because every sentence it
sat in was otherwise right.

So this reads every file a person might see and holds two lines:

  - nothing calls ELMER open source, free software, or free for everyone;
  - every place that states the licence names the one in LICENSE.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []

# Everything with words in it that a person reads. Not the data/ tree, which
# carries other people's licences and a browser profile, and not the
# CHANGELOG, which is a record of what was said at the time and is not
# rewritten.
SEEN_BY_PEOPLE = (
    list((ROOT / "elmer" / "templates").glob("*.html"))
    + list((ROOT / "elmer" / "static").glob("*.js"))
    + list((ROOT / "elmer").glob("*.py"))
    + [ROOT / p for p in ("README.md", "DESIGN.md", "USER-GUIDE.md",
                          "SUPPORTERS.md", "NOTICE", "elmer.py")]
)

# The wider promises. "free for everyone" is the one that was actually made;
# the others are the same mistake in the words somebody would reach for next.
OVERCLAIMS = re.compile(
    r"free for (everyone|everybody|all|anyone)\b|open[- ]source software|"
    r"\bfree software\b|\bFOSS\b|\bcopyleft\b|\bGPL\b|MIT licen[cs]e",
    re.IGNORECASE)

# Where a mention is the docstring saying the phrase was removed, or the
# sentence that says ELMER is deliberately *not* open source.
ALLOWED = re.compile(
    r"was the phrase here|deliberately not an OSI open-source|"
    r"not an open-source license in the OSI sense|open-source license\. Details",
    re.IGNORECASE)


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the licence itself --")
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    check("LICENSE is PolyForm Noncommercial 1.0.0",
          "PolyForm Noncommercial License 1.0.0" in text, True)
    check("  and carries the required notice", "Required Notice:" in text, True)

    print("\n-- nothing a person reads promises more than that --")
    for path in sorted(SEEN_BY_PEOPLE):
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        hits = []
        for n, line in enumerate(body.splitlines(), 1):
            if OVERCLAIMS.search(line) and not ALLOWED.search(line):
                hits.append(f"{n}: {line.strip()[:70]}")
        check(f"{path.relative_to(ROOT).as_posix()}", hits, [])

    print("\n-- and where the licence is named, it is the right one --")
    for doc in ("README.md", "DESIGN.md"):
        body = (ROOT / doc).read_text(encoding="utf-8")
        check(f"{doc} names PolyForm Noncommercial",
              "PolyForm Noncommercial 1.0.0" in body, True)
        check(f"  and says it is not OSI open source",
              "not an OSI open-source" in body or "not an open-source license in the OSI sense" in body,
              True)

    print("\n-- the coffee is still thanks and not a toll --")
    sup = (ROOT / "elmer" / "supporter.py").read_text(encoding="utf-8")
    check("the coffee card still says it stays free",
          "It stays free, coffee or no coffee." in sup, True)
    base = (ROOT / "elmer" / "templates" / "base.html").read_text(encoding="utf-8")
    check("  and the Station panel says free for noncommercial use",
          "free for\n      noncommercial use" in base or "free for noncommercial use" in base, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

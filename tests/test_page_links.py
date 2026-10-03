#!/usr/bin/env python3
"""Every page a template or script links to is a page the server serves.

    python3 tests/test_page_links.py

The Library's "the whole shelf" pointed at /printouts, where nothing has
ever been - the shelf is /prints - and nothing noticed until an operator
pressed it. Every href to a page of ELMER's own, in every template and
script, is asked for here, and one that does not answer fails the suite.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer.app import app  # noqa: E402

# href="/page", href="/page#part" or href="/page?q=..." - a page, not an API or a file
LINK = re.compile(r'href="(/[a-z][a-z0-9_-]*)(?:[#?][^"]*)?"')


def main():
    sources = sorted((ROOT / "elmer" / "templates").glob("*.html")) + sorted((ROOT / "elmer" / "static").glob("*.js"))
    found = {}
    for path in sources:
        for page in LINK.findall(path.read_text(encoding="utf-8")):
            found.setdefault(page, path.name)
    client = app.test_client()
    broken = []
    for page, where in sorted(found.items()):
        status = client.get(page, environ_base={"REMOTE_ADDR": "127.0.0.1"}).status_code
        if status >= 400:
            broken.append("%s -> %s (linked from %s)" % (page, status, where))
    print("  %d pages linked from %d files" % (len(found), len(sources)))
    for line in broken:
        print("  FAIL  " + line)
    if len(found) < 10:
        print("  FAIL  fewer than ten pages found - the pattern has stopped matching")
        return 1
    print("\n" + ("ALL PASS" if not broken else "FAILURES: %d broken links" % len(broken)))
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())

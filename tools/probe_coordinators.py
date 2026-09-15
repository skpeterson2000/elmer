#!/usr/bin/env python3
"""Which coordinators publish a plan the generic reader can read?

    python3 tools/probe_coordinators.py

Every coordinator's front page and plan page (where one is listed) is
fetched and read with regional.generic - the parser that files each
"144.60 - 144.90 label" row under the band its frequency falls in - and the
count of segments per band is printed. A site that yields a dozen segments
across several bands is one to give a plans_url; one that yields none
publishes a PDF, an image, or a page the reader cannot follow, and gets a
link instead. Run when adding coordinators; it is a minute or two of
polite requests.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elmer import regional  # noqa: E402


def main():
    for c in regional.COORDINATORS:
        for key in ("plans_url", "url"):
            url = c.get(key)
            if not url:
                continue
            try:
                bands = regional.generic(url)
            except Exception as exc:
                print(f"{c['short']:10} {key:9} {url}\n    failed: {type(exc).__name__}: {exc}")
                continue
            total = sum(len(v) for v in bands.values())
            summary = ", ".join(f"{b} {len(v)}" for b, v in sorted(bands.items()))
            print(f"{c['short']:10} {key:9} {url}\n    {total} segments: {summary or '-'}", flush=True)


if __name__ == "__main__":
    main()

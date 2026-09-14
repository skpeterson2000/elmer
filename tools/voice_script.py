#!/usr/bin/env python3
"""Print the narrator's recording script: one line a snippet, `stem: words`.

    python3 tools/voice_script.py            # to the terminal
    python3 tools/voice_script.py --md       # as docs/narration/voice-script.md

Record each line as its own file, named by the stem, as MP3, into
elmer/static/golf/voice/ - three.mp3, addresses-the-ball.mp3 - and the
narrator says what it has. A regular's name is name-<slug>.mp3, the slug
being the name lowercased with anything but letters and digits made a
hyphen: "Ann Lee" is name-ann-lee.mp3.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import voice  # noqa: E402

GROUPS = [
    ("Numbers - reused for yards, feet, strokes, miles an hour", lambda k: k in voice.NUMBER_WORDS.values() or k in ("hundred", "and")),
    ("The holes", lambda k: k.startswith("the-") and k[4:] in voice.ORDINALS),
    ("The calls - the golfer's word at contact", lambda k: k.startswith("call-")),
    ("Everything else - the address, the stroke, the wind, the card", lambda k: True),
]


def grouped():
    seen = set()
    for title, pick in GROUPS:
        rows = [(k, w) for k, w in voice.VOCABULARY.items() if k not in seen and pick(k)]
        seen.update(k for k, _ in rows)
        yield title, rows


def as_markdown():
    out = ["# The narrator's script", "",
           "One line a snippet. Record each as its own MP3, named by the stem, into",
           "`elmer/static/golf/voice/`; the narrator says what it has and is silent",
           "for the rest. Names: `name-<slug>.mp3`, the slug the name lowercased with",
           "anything but letters and digits made a hyphen (*Ann Lee* is",
           "`name-ann-lee.mp3`). Regenerate this file with `python3 tools/voice_script.py --md`.",
           "",
           "How a line is pieced together (the game composes these; see `elmer/voice.py`):",
           "",
           "- the hole, at the tee: *pebble-beach · the-first · par · four · three · hundred · and · seventy · seven · yards · the-breeze-is-behind-you · twelve · miles-an-hour*",
           "- the address: *name-scott · addresses-the-ball · the-driver · in-hand · three · hundred · and · seventy · seven · to-go · from-the-tee*",
           "- the stroke: *the-driver · two · hundred · and · fifty · five · yards · fairway · one · hundred · and · twenty · two · to-go*",
           "- the call: one of the *call-* files",
           "- the card: *thats-the-hole · name-scott · for-a-bogey · name-ann · for-par · on-to-the-next*",
           ""]
    for title, rows in grouped():
        out += [f"## {title}", ""]
        out += [f"- `{k}`: {w}" for k, w in rows]
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    if "--md" in sys.argv:
        target = Path(__file__).resolve().parents[1] / "docs" / "narration" / "voice-script.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(as_markdown(), encoding="utf-8")
        print(f"wrote {target} ({len(voice.VOCABULARY)} snippets)")
    else:
        for title, rows in grouped():
            print(f"\n# {title}")
            for k, w in rows:
                print(f"{k}: {w}")

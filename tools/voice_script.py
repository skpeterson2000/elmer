#!/usr/bin/env python3
"""Print the narrator's recording script: one line a snippet, `stem: words`.

    python3 tools/voice_script.py            # to the terminal
    python3 tools/voice_script.py --md       # as docs/narration/voice-script.md
    python3 tools/voice_script.py --have     # what is recorded, what is still to do
    python3 tools/voice_script.py --adopt    # rename a reader's files ('29.One_hundred.mp3') to the stems

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


GROUPS = [g for g in GROUPS if g[0] != "The letters - phonetic, for a callsign with no name file"]
GROUPS.insert(1, ("The letters - phonetic, for a callsign with no name file", lambda k: k.startswith("phon-")))


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
           "",
           voice.whole_number_note(),
           ""]
    for title, rows in grouped():
        out += [f"## {title}", ""]
        out += [f"- `{k}`: {w}" for k, w in rows]
        out.append("")
    return "\n".join(out)


def shelf_report():
    """What is on the shelf and what is not: the recordings in
    elmer/static/golf/voice/ against the script, so a batch can be checked
    before a round is played. Whole numbers (n-377) and names (name-scott)
    are listed as extras; a file the script does not know is flagged, since
    a typo in a stem is a snippet the narrator will never say."""
    folder = Path(__file__).resolve().parents[1] / "elmer" / "static" / "golf" / "voice"
    have = sorted(p.stem for p in folder.glob("*.mp3")) if folder.is_dir() else []
    known = set(voice.VOCABULARY)
    numbers = [h for h in have if h.startswith("n-") and h[2:].isdigit()]
    names = [h for h in have if h.startswith("name-")]
    scripted = [h for h in have if h in known]
    strays = [h for h in have if h not in known and h not in numbers and h not in names]
    missing = [k for k in voice.VOCABULARY if k not in have]
    out = [f"{folder}", "",
           f"recorded: {len(scripted)} of {len(known)} scripted snippets, "
           f"{len(numbers)} whole numbers, {len(names)} names"]
    if strays:
        out += ["", "not in the script (check the stem - the narrator will never say these):"]
        out += [f"  {h}" for h in strays]
    if missing:
        out += ["", f"still to record ({len(missing)}):"]
        for title, rows in grouped():
            todo = [k for k, _ in rows if k in missing]
            if todo:
                out.append(f"  {title}: " + ", ".join(todo))
    else:
        out += ["", "every scripted snippet is recorded."]
    return "\n".join(out)


def _key(text):
    """Letters and digits only, lowercased: 'That'll play.' and
    'Thatll_play' and '12.That_ll_play' all come to the same thing."""
    import re
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


NUMBER_WORDS_TO_N = {w: n for n, w in voice.NUMBER_WORDS.items()}


def adopt(dry_run=False):
    """Rename what a text-to-speech reader produced - files named for the
    line's text, with a number in front ('29.One_hundred.mp3') - to the
    stems the narrator listens for, by matching the text against the
    script. Whole numbers ('Three hundred seventy seven') become n-377.
    Files already named for a stem are left alone; a file that matches
    nothing is listed, not touched."""
    import re
    folder = Path(__file__).resolve().parents[1] / "elmer" / "static" / "golf" / "voice"
    by_words = {_key(words): stem for stem, words in voice.VOCABULARY.items()}
    stems = set(voice.VOCABULARY)
    renamed, strays = [], []
    for p in sorted(folder.glob("*.mp3")) if folder.is_dir() else []:
        if p.stem in stems or re.match(r"^(n-\d+|name-[a-z0-9-]+)$", p.stem):
            continue
        text = re.sub(r"^\d+\.", "", p.stem)          # the reader's running number
        key = _key(text)
        target = by_words.get(key)
        if target is None and len(key) >= 12:
            # the reader cuts a long line's name short: a unique prefix will do
            starts = [stem for k, stem in by_words.items() if k.startswith(key)]
            if len(starts) == 1:
                target = starts[0]
        if target is None:
            target = _whole_number(text)
        if target is None:
            strays.append(p.name)
            continue
        dest = folder / f"{target}.mp3"
        if dest.exists():
            strays.append(f"{p.name} (would be {dest.name}, which exists)")
            continue
        renamed.append((p.name, dest.name))
        if not dry_run:
            p.rename(dest)
    return renamed, strays


def _whole_number(text):
    """'Three hundred seventy seven' -> 'n-377'; 'Forty' alone is a piece,
    not a whole number, and is matched by the script instead."""
    import re
    words = re.findall(r"[a-z]+", str(text).lower().replace("-", " "))
    if not words:
        return None
    n, hundreds = 0, False
    for w in words:
        if w == "hundred":
            n *= 100
            hundreds = True
        elif w == "and":
            continue
        elif w in NUMBER_WORDS_TO_N:
            n += NUMBER_WORDS_TO_N[w]
        else:
            return None
    if not hundreds and len(words) < 2:
        return None                         # a single number word is a piece of the script
    return f"n-{n}" if 0 < n <= 999 else None


if __name__ == "__main__":
    if "--adopt" in sys.argv:
        dry = "--dry-run" in sys.argv
        renamed, strays = adopt(dry_run=dry)
        for a, b in renamed:
            print(f"{'would rename' if dry else 'renamed'}  {a}  ->  {b}")
        for name in strays:
            print(f"not in the script: {name}")
        print(f"{len(renamed)} adopted, {len(strays)} left as they were")
    elif "--have" in sys.argv:
        print(shelf_report())
    elif "--md" in sys.argv:
        target = Path(__file__).resolve().parents[1] / "docs" / "narration" / "voice-script.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(as_markdown(), encoding="utf-8")
        print(f"wrote {target} ({len(voice.VOCABULARY)} snippets)")
    else:
        for title, rows in grouped():
            print(f"\n# {title}")
            for k, w in rows:
                print(f"{k}: {w}")

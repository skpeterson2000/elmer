#!/usr/bin/env python3
"""Print the narrator's recording script: one line a snippet, `stem: words`.

    python3 tools/voice_script.py            # to the terminal
    python3 tools/voice_script.py --md       # as docs/narration/voice-script.md
    python3 tools/voice_script.py --have     # what is recorded, what is still to do
    python3 tools/voice_script.py --adopt    # rename a reader's files ('29.One_hundred.mp3') to the stems
    python3 tools/voice_script.py --adopt --hole 2   # a batch of color for the second hole

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
    holes = [h for h in have if h.startswith("hole-")]        # a hole's reads and color
    scripted = [h for h in have if h in known]
    strays = [h for h in have if h not in known and h not in numbers and h not in names and h not in holes]
    missing = [k for k in voice.VOCABULARY if k not in have]
    out = [f"{folder}", "",
           f"recorded: {len(scripted)} of {len(known)} scripted snippets, "
           f"{len(numbers)} whole numbers, {len(names)} names, {len(holes)} hole reads and lines of color"]
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

# What a reader said that means a scripted snippet in other words.
ALIASES = {"milesperhour": "miles-an-hour", "mph": "miles-an-hour"}


def adopt(dry_run=False, hole=None):
    """Rename what a text-to-speech reader produced - files named for the
    line's text, with a number in front ('29.One_hundred.mp3') - to the
    stems the narrator listens for, by matching the text against the
    script. The number in front is the reader's and is dropped before
    anything is matched. Whole numbers ('Three hundred seventy seven')
    become n-377. A hole read whole becomes hole-<course>-<n>, or a
    further -read-<k> when one is there; a line of color becomes
    hole-<course>-<n>-<where>-<k>, for the hole the batch is for -
    `hole`, or the hole a line names, or the first. Files already named
    for a stem are left alone; a file that matches nothing is listed,
    not touched."""
    import re
    folder = Path(__file__).resolve().parents[1] / "elmer" / "static" / "golf" / "voice"
    by_words = {_key(words): stem for stem, words in voice.VOCABULARY.items()}
    stems = set(voice.VOCABULARY)
    renamed, strays = [], []
    taken = {p.stem for p in folder.glob("*.mp3")} if folder.is_dir() else set()
    # the hole the batch is for: said, or read off a line that names one
    batch_hole = hole
    if batch_hole is None:
        for p in sorted(folder.glob("*.mp3")) if folder.is_dir() else []:
            n = _named_hole(re.sub(r"^\d+\.", "", p.stem))
            if n:
                batch_hole = n
                break
    def reader_order(path):
        # the reader's number is the script's order: 2 before 10
        m = re.match(r"^(\d+)\.", path.stem)
        return (int(m.group(1)) if m else 10 ** 9, path.stem)
    for p in sorted(folder.glob("*.mp3"), key=reader_order) if folder.is_dir() else []:
        if p.stem in stems or re.match(r"^(n-\d+|name-[a-z0-9-]+|hole-[a-z0-9-]+-\d+(-(tee|green|fairway|rough|sand|water|read)-\d+)?)$", p.stem):
            continue
        text = re.sub(r"^\d+\.", "", p.stem)          # the reader's running number
        key = _key(text)
        target = by_words.get(key) or ALIASES.get(key)
        if target is None and len(key) >= 12:
            # the reader cuts a long line's name short: a unique prefix will do
            starts = [stem for k, stem in by_words.items() if k.startswith(key)]
            if len(starts) == 1:
                target = starts[0]
        if target is None:
            target = _whole_hole(text, taken)
        if target is None:
            target = _hole_note(text, taken, batch_hole or 1)
        if target is None:
            target = _whole_number(text)
        if target is None:
            strays.append(p.name)
            continue
        dest = folder / f"{target}.mp3"
        if target in taken:
            strays.append(f"{p.name} (would be {dest.name}, which exists)")
            continue
        taken.add(target)
        renamed.append((p.name, dest.name))
        if not dry_run:
            p.rename(dest)
    return renamed, strays


def _named_hole(text):
    """The hole a line names - 'Hole two ...', 'the second hole' - or None."""
    import re
    low = str(text).lower().replace("_", " ")
    words = {w: n for n, w in voice.NUMBER_WORDS.items()}
    ordinals = {w: i + 1 for i, w in enumerate(voice.ORDINALS)}
    m = re.search(r"\bhole[\s_]+([a-z]+|\d+)\b", low)
    if m:
        w = m.group(1)
        return words.get(w) or (int(w) if w.isdigit() else None)
    m = re.search(r"\bthe\s+([a-z]+)\s+hole\b", low)
    if m:
        return ordinals.get(m.group(1))
    return None


def _whole_hole(text, taken=()):
    """'Hole one is a par four at ...' -> hole-pebble-beach-1: a hole read
    whole, named by the course the script is for and the number it opens
    with; a second read of the same hole is -read-2, and so on. Pebble
    Beach is the course of the first recordings."""
    import re
    low = str(text).lower().replace("_", " ")
    m = re.match(r"^\s*hole[\s_]+([a-z0-9]+)", low)
    m2 = re.match(r"^\s*the\s+(\w+)\s+hole\s+at\s+pebble", low)
    if m:
        words = {w: n for n, w in voice.NUMBER_WORDS.items()}
        n = words.get(m.group(1)) or (int(m.group(1)) if m.group(1).isdigit() else None)
    elif m2:
        n = {w: i + 1 for i, w in enumerate(voice.ORDINALS)}.get(m2.group(1))
    else:
        return None
    if not n:
        return None
    if f"hole-pebble-beach-{n}" not in taken:
        return f"hole-pebble-beach-{n}"
    k = 2
    while f"hole-pebble-beach-{n}-read-{k}" in taken:
        k += 1
    return f"hole-pebble-beach-{n}-read-{k}"


def _hole_note(text, taken, hole=1):
    """A line of color about a hole - anything not in the script that
    reads like a sentence - becomes hole-pebble-beach-<hole>-<where>-<k>:
    where the line is spoken from, read off its words - the sand when it
    speaks of bunkers, the water, the rough, the fairway (a hazard ahead,
    the second shot), the green (the putting) - and the tee otherwise;
    numbered after the ones already there."""
    import re
    words = str(text).replace("_", " ").strip()
    # a line of color is a sentence; three words are a piece of the
    # script the reader phrased another way, and belong in ALIASES
    if len(words.split()) < 5:
        return None
    low = words.lower()
    where = "tee"
    for name, pat in (("sand", r"\b(bunkers?|sand|traps?)\b"), ("water", r"\b(water|ocean|creek|sea|lake|pond|splash)\b"),
                      ("rough", r"\b(rough|grass|trees)\b"),
                      ("fairway", r"\b(fairway|barranca|ravine|gully|ditch|in two|second shot|lay(ing)? up|go for it)\b"),
                      ("green", r"\b(green|putt|putting)\b")):
        if re.search(pat, low):
            where = name
            break
    k = 1
    while f"hole-pebble-beach-{hole}-{where}-{k}" in taken:
        k += 1
    return f"hole-pebble-beach-{hole}-{where}-{k}"


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
        # --hole 2: the hole this batch of color is for, when no line names it
        hole = int(sys.argv[sys.argv.index("--hole") + 1]) if "--hole" in sys.argv else None
        renamed, strays = adopt(dry_run=dry, hole=hole)
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

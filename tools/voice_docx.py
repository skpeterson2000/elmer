#!/usr/bin/env python3
"""The narrator's script as a Word document, one line a snippet, for feeding
a text-to-speech reader one line at a time.

    python3 tools/voice_docx.py                 # docs/narration/voice-script.docx
    python3 tools/voice_docx.py --missing       # only what is not yet recorded

Each line is the words to read, capitalised as a sentence - the reader
gives a stronger read that way - in the order the first hole needs them, so
a partial batch is a playable one. The file the reader produces for a line
is named for the line's text; `tools/voice_script.py --adopt` renames those
to the stems the narrator listens for.

Written without python-docx: a .docx is a zip of XML, and this needs three
small files in it.
"""
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elmer import voice  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VOICE_DIR = ROOT / "elmer" / "static" / "golf" / "voice"

# The first hole first: what a round at Pebble Beach says on the 1st, in the
# order it says it, then the rest of the script.
FIRST_HOLE = [
    "hundred", "and", "the-first", "par", "yards", "feet", "to-go", "pebble-beach",
    "the-breeze-is-behind-you", "into-the-breeze", "a-crosswind", "miles-an-hour",
    "the-player", "addresses-the-ball", "in-hand", "the-driver", "the-wood", "the-iron", "the-wedge",
    "the-putter", "from-the-tee", "from-the-fairway", "from-the-rough", "from-the-sand", "on-the-green",
    "your-shot", "fairway", "a-foul-ball", "into-the-sand", "into-the-water", "into-the-rough",
    "short-and-into-the-rough", "through-the-green", "drop-and-a-penalty-stroke",
    "putt-holed", "putt-missed", "in-the-hole", "picked-up",
    "for-a-birdie", "for-par", "for-a-bogey", "for-a-double-bogey", "for-a-triple-bogey", "over-par",
    "thats-the-hole", "on-to-the-next",
    "call-fairway-1", "call-fairway-2", "call-fairway-3", "call-green-1", "call-green-2", "call-green-3",
    "call-rough-1", "call-rough-2", "call-rough-3", "call-sand-1", "call-sand-2", "call-sand-3",
    "call-water-1", "call-water-2", "call-water-3", "call-holed-1", "call-holed-2", "call-holed-3",
    "call-missed-1", "call-missed-2", "call-missed-3", "call-long-1", "call-long-2", "call-long-3",
]


def sentence(words):
    """The words to read, capitalised as a sentence."""
    w = str(words).strip()
    return w[:1].upper() + w[1:] if w else w


def lines(missing_only=False):
    have = {p.stem for p in VOICE_DIR.glob("*.mp3")} if VOICE_DIR.is_dir() else set()
    order = [k for k in FIRST_HOLE if k in voice.VOCABULARY]
    order += [k for k in voice.VOCABULARY if k not in order]
    out = []
    for stem in order:
        if missing_only and stem in have:
            continue
        out.append((stem, sentence(voice.VOCABULARY[stem])))
    return out


def paragraph(text, bold=False, size=None):
    rpr = ""
    if bold or size:
        rpr = "<w:rPr>" + ("<w:b/>" if bold else "") + (f'<w:sz w:val="{size}"/>' if size else "") + "</w:rPr>"
    return f'<w:p><w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def build(target, missing_only=False):
    rows = lines(missing_only)
    body = [paragraph("The narrator's script", bold=True, size=32),
            paragraph("One line at a time. The reader names each file for its text; "
                      "python3 tools/voice_script.py --adopt renames them for the game.", size=18),
            paragraph("")]
    body += [paragraph(text) for _, text in rows]
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body>' + "".join(body) + '<w:sectPr/></w:body></w:document>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/word/document.xml" '
                     'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                     '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return len(rows)


if __name__ == "__main__":
    missing = "--missing" in sys.argv
    target = ROOT / "docs" / "narration" / ("voice-script-missing.docx" if missing else "voice-script.docx")
    n = build(target, missing)
    print(f"wrote {target} ({n} lines)")

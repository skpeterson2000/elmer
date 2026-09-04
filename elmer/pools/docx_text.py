"""Extract plain text from a .docx without third-party deps.

A .docx is a zip; word/document.xml holds the body. We turn paragraph and
break tags into newlines, tabs into tabs, then strip the remaining markup.
"""
import html
import re
import zipfile

_PARA = re.compile(r"</w:p>")
_TAB = re.compile(r"<w:tab[^>]*/>")
_BR = re.compile(r"<w:br[^>]*/>")
_TAG = re.compile(r"<[^>]+>")
# Word smart punctuation confuses downstream regexes; normalise to ASCII.
_PUNCT = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
}


def normalize_punct(text):
    for bad, good in _PUNCT.items():
        text = text.replace(bad, good)
    return text


def docx_to_text(path):
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    xml = _PARA.sub("\n", xml)
    xml = _TAB.sub("\t", xml)
    xml = _BR.sub("\n", xml)
    text = html.unescape(_TAG.sub("", xml))
    return normalize_punct(text).replace("\r", "\n")

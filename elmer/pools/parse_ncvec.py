"""Parse an NCVEC amateur radio question pool (.docx) into normalized JSON.

The released pool documents start with a changelog of errata, then the syllabus,
then the pool body with every erratum already applied.  We therefore parse the
whole file and let later definitions of a question win, which lands us on the
corrected body text.

Body format:

    T1A01 (C) [97.1]
    Which of the following is part of the Basis and Purpose ...?
    A. Providing personal radio communications ...
    B. ...
    C. ...
    D. ...
    ~~

Withdrawn questions appear as ``G1C08  Question Deleted (section not renumbered)``.
"""
import re

from .docx_text import docx_to_text

QID = r"[TGE]\d[A-Z]\d\d"
RE_HEAD = re.compile(rf"^({QID})\s*\(([A-D])\)\s*(?:\[(.*?)\])?\s*$")
RE_DELETED = re.compile(rf"^({QID})\s+Question Deleted", re.I)
RE_CHOICE = re.compile(r"^([A-D])\.\s*(.*)$")
RE_SUBEL = re.compile(
    r"^SUBELEMENT\s+([TGE]\d)\s*[-–]\s*(.+?)\s*"
    r"\[\s*(\d+)\s*exam questions?\s*[-–]\s*(\d+)\s*groups?\s*\]"
    r"\s*(?:(\d+)\s*Questions)?\s*$",
    re.I,
)
RE_GROUP = re.compile(rf"^([TGE]\d[A-Z])\s*[-–]?\s+(\S.*)$")
MAX_STEM_LINES = 12
RE_FIGURE = re.compile(r"figure\s+([TGE])-?(\d)?-?(\d)", re.I)


def _figure_ref(text):
    """Return a normalized figure id, e.g. 'T-2', 'E9-1'. Handles 'E73' typos."""
    m = RE_FIGURE.search(text)
    if not m:
        return None
    letter, major, minor = m.group(1).upper(), m.group(2), m.group(3)
    if letter == "T":
        return f"T-{minor}"
    return f"{letter}{major}-{minor}" if major else f"{letter}-{minor}"


def parse(path):
    lines = [ln.strip() for ln in docx_to_text(path).split("\n")]
    questions, subelements, groups, deleted = {}, {}, {}, set()

    i = 0
    while i < len(lines):
        line = lines[i]

        m = RE_SUBEL.match(line)
        if m:
            code, title, exam_q, n_groups, n_quest = m.groups()
            prev = subelements.get(code, {})
            subelements[code] = {
                "code": code,
                "title": title.strip().rstrip("-").strip(),
                "exam_questions": int(exam_q),
                "groups": int(n_groups),
                # the count only appears in the syllabus copy of the header
                "pool_questions": int(n_quest) if n_quest else prev.get("pool_questions"),
            }
            i += 1
            continue

        m = RE_DELETED.match(line)
        if m:
            deleted.add(m.group(1))
            i += 1
            continue

        m = RE_HEAD.match(line)
        if m:
            qid, answer, refs = m.groups()
            block, nxt = _read_block(lines, i + 1)
            if block is None:
                i = max(nxt, i + 1)
                continue
            i = nxt
            if block:
                text, choices = block
                questions[qid] = {
                    "id": qid,
                    "subelement": qid[:2],
                    "group": qid[:3],
                    "answer": "ABCD".index(answer),
                    "refs": refs.strip() if refs else None,
                    "text": text,
                    "choices": choices,
                    "figure": _figure_ref(text),
                }
            continue

        m = RE_GROUP.match(line)
        # a group header is prose ("E6B Diodes"), not a question or a deletion
        if m and not RE_DELETED.match(line) and len(m.group(2)) > 2:
            groups[m.group(1)] = m.group(2).strip()

        i += 1

    for qid in deleted:
        questions.pop(qid, None)

    return questions, subelements, groups, deleted


def _read_block(lines, i):
    """Read question text then the four choices, ending at the '~~' terminator.

    Returns ``(block_or_None, next_index)``.  Errata sections restate a question
    header with no body (e.g. a bare rule-citation fix), so we bail out as soon
    as the shape stops looking like a question and hand back the starting index
    rather than swallowing the lines that follow.
    """
    start = i
    text_parts = []
    while i < len(lines) and not RE_CHOICE.match(lines[i]):
        ln = lines[i]
        if (ln == "~~" or RE_HEAD.match(ln) or RE_DELETED.match(ln)
                or RE_SUBEL.match(ln) or ln.upper().startswith("SUBELEMENT")
                or i - start > MAX_STEM_LINES):
            return None, start
        if ln:
            text_parts.append(ln)
        i += 1

    choices, current = [], None
    while i < len(lines) and lines[i] != "~~":
        if RE_HEAD.match(lines[i]) or lines[i].upper().startswith("SUBELEMENT"):
            return None, start
        m = RE_CHOICE.match(lines[i])
        if m:
            if current is not None:
                choices.append(" ".join(current).strip())
            current = [m.group(2)]
        elif lines[i] and current is not None:
            current.append(lines[i])       # wrapped choice text
        i += 1
    if current is not None:
        choices.append(" ".join(current).strip())

    if len(choices) != 4 or not text_parts:
        return None, start
    return (" ".join(text_parts).strip(), choices), i + 1

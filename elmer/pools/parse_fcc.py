"""Parse an FCC commercial operator question pool (PDF) into normalized JSON.

Layout of the released PDFs::

    Subelement A - Principles: 8 Key Topics, 8 Exam Questions
    Key Topic 1: Electrical Elements
    3-1A1 The product of the readings of an AC voltmeter and AC ammeter is called:
        A. Apparent power.
        ...
    Answer Key:     3-1A1: A     3-1A2: B     3-1A3 A   ...

Three things make this messier than it looks:

* correct answers live in a per-key-topic answer key, not beside the question;
* many key topics lay the choices out in two columns, so a single text line
  holds both ``A.`` and ``C.``;
* the published PDFs contain typos - ``D No ...`` for ``D. No ...``, ``D,`` for
  ``D.``, and question ids that drop the element prefix (``13B1``, ``13A3``).

Ids are therefore rebuilt from the surrounding Key Topic heading rather than
trusted verbatim, and the answer key is reconciled against the parsed
questions afterwards.
"""
import re
import subprocess

RE_QUESTION = re.compile(r"^(\d)-?(\d+)([A-Z])(\d+)\s+(\S.*)$")
RE_SUBEL = re.compile(r"^Subelement\s+(?:\d-?)?([A-Z])\s*[-–]\s*(.+)$", re.I)
RE_TOPIC = re.compile(r"^Key Topic\s+(\d+)\s*[:–-]\s*(\S.*)$", re.I)
RE_ANSWER_KEY = re.compile(r"^Answer Key\s*:?\s*(.*)$", re.I)
RE_ANSWER_PAIR = re.compile(r"((?:\d-)?\d+[A-Z]\d+)\s*[:.]?\s+([A-D])\b")
RE_FOOTER = re.compile(r"^\s*\d{4} FCC Commercial Element .*Page\s*\d+\s*$", re.I)
RE_HEADER = re.compile(r"^\s*FCC Commercial Element \d+ Question Pool", re.I)
RE_END = re.compile(r"\[?END OF PROPOSED|^End of Proposed", re.I)
RE_FIGURE = re.compile(r"(?:figure|fig\.?)\s+(\d[A-Z]\d+)", re.I)
# A choice marker: line start or a wide column gap, then A-D, then optional
# punctuation (the PDFs use '.', ',' and sometimes nothing at all).
RE_CHOICE_TOKEN = re.compile(r"(?:^|\s{2,})([A-D])([.,)]?)\s+(?=\S)")
_PUNCT = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}


def pdf_to_text(path):
    out = subprocess.run(
        ["pdftotext", "-layout", "-nopgbrk", str(path), "-"],
        check=True, capture_output=True,
    ).stdout.decode("utf-8", "replace")
    for bad, good in _PUNCT.items():
        out = out.replace(bad, good)
    return out


def _split_choices(line, assigned):
    """Return [(letter, text), ...] found on one line, or [] if it isn't choices.

    Handles the two-column layout ("A. foo    C. bar") and rejects prose that
    merely happens to start with a capital letter.
    """
    tokens = list(RE_CHOICE_TOKEN.finditer(line))
    if not tokens:
        return []
    letters = [t.group(1) for t in tokens]
    if len(set(letters)) != len(letters) or letters != sorted(letters):
        return []
    if any(ltr in assigned for ltr in letters):
        return []
    # An unpunctuated marker is only believable as the next choice in sequence
    # on an indented line - otherwise it is wrapped prose starting with "A ".
    expected = "ABCD"[len(assigned)] if len(assigned) < 4 else None
    if not tokens[0].group(2):
        if letters[0] != expected or not line[:1].isspace():
            return []
    if tokens[0].start() != 0 and not line[:tokens[0].start()].isspace():
        return []

    out = []
    for n, tok in enumerate(tokens):
        end = tokens[n + 1].start() if n + 1 < len(tokens) else len(line)
        out.append((tok.group(1), line[tok.end():end].strip()))
    return out


def parse(path, element):
    lines = pdf_to_text(path).split("\n")

    questions, subelements, topics = {}, {}, {}
    raw_answers = []                 # (raw_id, topic, answer_index)
    subel, topic, current = None, None, None
    field = None                     # 'stem' | 'choices' | 'answerkey'

    def flush():
        nonlocal current, field
        if current and len(current["choices"]) == 4:
            current["choices"] = [current["choices"][c] for c in "ABCD"]
            questions[current["id"]] = current
        current, field = None, None

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or RE_FOOTER.match(line) or RE_HEADER.match(line):
            continue
        if RE_END.search(stripped):
            flush()
            continue

        m = RE_ANSWER_KEY.match(stripped)
        if m:
            flush()
            field = "answerkey"
            for qid, ans in RE_ANSWER_PAIR.findall(m.group(1)):
                raw_answers.append((qid, topic, "ABCD".index(ans)))
            continue
        if field == "answerkey":
            pairs = RE_ANSWER_PAIR.findall(stripped)   # keys sometimes wrap
            if pairs:
                for qid, ans in pairs:
                    raw_answers.append((qid, topic, "ABCD".index(ans)))
                continue
            field = None

        m = RE_SUBEL.match(stripped)
        if m:
            flush()
            subel = m.group(1).upper()
            subelements[subel] = {"code": subel,
                                  "title": m.group(2).split(":")[0].strip(" -")}
            continue

        m = RE_TOPIC.match(stripped)
        if m:
            flush()
            topic = int(m.group(1))
            topics[topic] = {"number": topic, "title": m.group(2).strip(),
                             "subelement": subel}
            continue

        m = RE_QUESTION.match(stripped)
        if m and topic is not None:
            flush()
            letter, num, text = m.group(3), m.group(4), m.group(5)
            # rebuild the id from the Key Topic heading; the printed prefix is
            # unreliable ("13A3" for 1-3A3, "13B1" for 3-13B1)
            qid = f"{element}-{topic}{letter}{num}"
            current = {"id": qid, "element": element, "subelement": subel,
                       "topic": topic, "text": text.strip(),
                       "choices": {}, "figure": None}
            field = "stem"
            continue

        if current is None:
            continue

        found = _split_choices(line, current["choices"])
        if found:
            for letter, text in found:
                current["choices"][letter] = text
            field = "choices"
            continue

        if field == "stem":
            current["text"] += " " + stripped
        elif field == "choices" and current["choices"]:
            last = max(current["choices"])
            current["choices"][last] += " " + stripped

    flush()

    # Reconcile the answer key against the questions we actually found.
    unmatched = []
    for raw_id, key_topic, answer in raw_answers:
        for cand in _candidates(raw_id, element, key_topic):
            if cand in questions:
                questions[cand]["answer"] = answer
                break
        else:
            unmatched.append(raw_id)

    for q in questions.values():
        q.setdefault("answer", None)
        m = RE_FIGURE.search(q["text"])
        if m:
            q["figure"] = m.group(1).upper()

    return questions, subelements, topics, unmatched


def _candidates(raw_id, element, topic):
    """Plausible canonical ids for an answer-key entry, best guess first."""
    body = raw_id.split("-", 1)[1] if "-" in raw_id else raw_id
    out = [f"{element}-{body}"]
    if body[:1] == str(element):
        out.append(f"{element}-{body[1:]}")
    m = re.match(r"\d*([A-Z]\d+)$", body)
    if m and topic is not None:
        out.append(f"{element}-{topic}{m.group(1)}")
    return out
